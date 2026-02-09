# EasyAgenda — System Overview (source-of-truth map)

This document explains **how the SaaS works end-to-end** and points to the **exact code/docs** that implement each part.

## Start here (reading order)

1) `EMERGENT_PROMPT.md` — copy/paste prompt + minimal map for a builder AI
2) `PRODUCT_DECISIONS_AND_PROMPT.md` — product rules + UX decisions + API contracts
3) `LAUNCH_SNAPSHOT.md` — what’s shipped + what to verify
4) `DOMAIN_LAUNCH_CHECKLIST.md` + `DEPLOY_PROD_CLOUDFLARE_OVH.md` — production deployment
5) `STRIPE_RUNBOOK.md` — Stripe subscriptions wiring and verification

## Roles

- **Visitor/Customer (public)**: uses the booking link, chooses slot, confirms; can download `.ics` and respond to confirmation messages.
- **Admin (establishment owner/staff)**: configures business/services/professionals, manages appointments/clients, billing.
- **Superadmin (ops)**: diagnostics and test utilities (some routes are protected or disabled in production).

## Frontend structure

Main app: `frontend_v2/` (React)

Key pages:
- Public booking UI: `frontend_v2/src/pages/BookingPremium.jsx` (route: `/booking/:slug`)
- Finance (Stripe CTA + portal): `frontend_v2/src/pages/Finance.jsx`
- Notifications ops: `frontend_v2/src/pages/NotificationsOps.jsx`

i18n:
- Frontend dictionary: `frontend_v2/src/i18n/i18n.js`

## Backend structure

FastAPI app entry:
- `Backend/app/main.py` includes routers (no global `/api` prefix).

Routers (selected):
- Public booking: `Backend/app/api/booking/routes.py` (tags=["booking"]) — **source of truth** for booking rules and `.ics`.
- Admin: `Backend/app/api/admin/routes.py`
- Auth: `Backend/app/api/auth/routes.py`
- Billing/Stripe: `Backend/app/api/billing/routes.py`
- Notifications webhook/ops: `Backend/app/api/notifications/routes.py`
- WhatsApp inbound webhook (Twilio): `Backend/app/api/whatsapp/routes.py`

Core models (SQLAlchemy): `Backend/app/models/models.py`

## Core data model (conceptual)

- `Estabelecimento` (business): name, slug, default language (`idioma_padrao`), optional `lembrete_horas_antes`, etc.
- `SetupProfile` (JSON payload per establishment): **feature flags & policies** (trial/billing/locale/confirmation config).
- `Service`: service name, duration, buffer, price, display interval.
- `Funcionario` (professional): belongs to establishment.
- `Cliente` (customer): phone, name, `idioma`.
- `Agendamento` (appointment): datetime (stored as tz-aware), links to customer/professional/service.
- `Notificacao`: queued outbound messages (Twilio/SMS/WhatsApp/SMTP), with idempotency and retries.
- `PendingAction`: future actions (e.g., auto-cancel if no confirmation response).
- `Invoice`: billing records + Stripe gateway fields (for SaaS subscription / future payments).

## Public booking: API and flow

Public booking is a strict backend-driven flow.

Key endpoints (public):
- `GET /config?slug=` → services + professionals + business basics
- `GET /availability?date=YYYY-MM-DD&service_id=&professional_id=` → available slots
- `GET /occupancy?from=&to=&service_id=&professional_id=` → day heatmap states
- `POST /appointments` → creates appointment (also returns `calendar_url`)
- `GET /appointments/{appointment_id}/calendar.ics?token=...` → public `.ics` download (JWT purpose=ics)

Frontend route:
- `/booking/:slug` (SPA route) uses the endpoints above.

### `.ics` calendar download

Implemented in `Backend/app/api/booking/routes.py`.

Requirements:
- Public but secure: requires JWT token with `purpose=ics` and appointment/establishment ids.
- Deterministic, timezone-safe:
  - event times stored/handled in UTC and rendered consistently
  - includes `VALARM` when appointment is in the future
- Localized: text fields (summary/description/alarm description) follow the customer language.

## Confirmation policy (slot visibility + deadlines)

The booking system uses a confirmation/cutoffs policy derived from:
- `SetupProfile.payload.confirmation` OR `SetupProfile.payload.business.confirmation`

This policy **controls slot visibility and confirmation windows**.

Key config keys (defaults shown):
- `minLeadHours` (default 4)
- `quietHoursStart` (default 21:00), `quietHoursEnd` (default 08:00)
- `immediateHorizonHours` (default 36), `immediateWindowHours` (default 4)
- Quiet-hours special mode:
  - `tomorrowAfterQuietMinTime` (default 14:00)
  - `nightSendTime` (default 08:00)
  - `nightConfirmDeadline` (default 12:00)
- Batch (day-before) window:
  - `sendTimePrevDay` (default 17:00)
  - `capDeadlinePrevDay` (default 20:00)
- Optional modes (opt-in):
  - `prevDayWindowsEnabled` + `prevDay*` keys
  - `simpleModeEnabled` / `availabilityCutoffsOnly`

Implementation: `Backend/app/api/booking/routes.py` (`_extract_confirmation_policy`, `_confirmation_times_for_slot`, `_slot_passes_confirmation_filter`).

## Outbound messages: what actually exists today

This system currently relies on **confirmation flows (handshake)** rather than generic “N hours before” reminders.

Scheduler (source of truth): `Backend/app/services/scheduler.py`
- Far appointments (>= threshold 24h/36h):
  - send `pre_confirmacao` immediately
  - schedule `confirmacao_oficial` on previous day (14:00/17:00 rules)
  - schedule `PendingAction(auto_cancel_no_response)` at the deadline
- Near appointments (< threshold):
  - send `confirmacao_urgente` immediately
  - schedule `PendingAction(auto_cancel_no_response)` at the deadline
- Incoming response parsing:
  - `1` confirm, `2` reschedule, `3` cancel

Pending actions: `Backend/app/services/pending_actions.py`
- `auto_cancel_no_response` marks appointment as `cancelado_sem_resposta` if no outcome.

Notification queue + sending: `Backend/app/services/notifications_v2.py`
- Stores notifications in DB with idempotency keys
- Sends via Twilio (SMS/WhatsApp) or SMTP
- Retries with exponential backoff
- Enforces **trial hard stop** for appointment-related sends

Twilio delivery receipts webhook: `Backend/app/api/notifications/routes.py` (`/notifications/webhook/twilio`).

Note: `Estabelecimento.lembrete_horas_antes` exists and is exposed in admin config, but the current scheduler flow primarily uses the confirmation types above.

## Trial gating

- Trial length is 4 days; day 5 blocks:
  - booking endpoints (public)
  - appointment-related notification sending
- API returns HTTP 402 with `{ code: "TRIAL_EXPIRED" }`.

Source:
- Booking gating: `Backend/app/api/booking/routes.py`
- Notification sending gating: `Backend/app/services/notifications_v2.py`

## Billing / Stripe subscriptions

Runbook: `STRIPE_RUNBOOK.md`

Endpoints:
- `GET /billing/subscription/status` (admin auth)
- `POST /billing/subscription/checkout` (admin auth)
- `POST /billing/subscription/portal` (admin auth)
- `POST /billing/stripe/webhook` (public, signed)

State:
- Stripe state stored in `SetupProfile.payload.billing.stripe`.
- Subscription activation flips `SetupProfile.payload.trial.active_plan=true` (webhook-driven).

## Imports (onboarding)

Admin endpoints (see `LAUNCH_SNAPSHOT.md` for list):
- iCal (.ics) preview + commit
- iCal URL preview + commit
- CSV clients preview + commit

## Deployment / ops shape

- Docker Compose overlays: base + prod + http/tls.
- Reverse proxy: Nginx, often behind Cloudflare.
- Health endpoints: `/healthz`.

See:
- `DEPLOY_PROD_CLOUDFLARE_OVH.md`
- `deploy/VPS_SETUP_OVH_DEBIAN.md`
- `DOMAIN_LAUNCH_CHECKLIST.md`

## Testing & smoke scripts

- Backend unit/integration tests: `Backend/tests/`
- Smoke scripts:
  - `scripts/dev_check.ps1` (Windows)
  - `scripts/smoke_booking_http.py`
  - `Backend/scripts/smoke_public_booking_flow.py`

---

If you are a builder AI: start with `EMERGENT_PROMPT.md`, then validate every claim here by reading the referenced files before implementing changes.
