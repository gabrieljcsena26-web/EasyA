# Emergent prompt (copy/paste)

Goal: give a builder-AI an accurate, minimal-ambiguity spec of the current EasyAgenda system + the upgrades we want, aligned with the repo.

Recommended repo reading order:
- `EMERGENT_PROMPT.md` (this file)
- `SYSTEM_OVERVIEW.md` (how the SaaS works + where each rule lives)
- `PRODUCT_DECISIONS_AND_PROMPT.md` (product decisions + API contracts)

## Prompt

You are an expert full‑stack SaaS engineer. Upgrade an existing booking SaaS (EasyAgenda) to premium, launch‑grade quality, PR‑by‑PR, without breaking current behavior. Keep API contracts stable, add/extend tests, and optimize for reliability + minimal messaging cost.

Current system facts (do not reinvent)
- Public booking URL: `/booking/:slug`.
- Public calendar download exists and must remain: `GET /appointments/{appointment_id}/calendar.ics?token=...` (JWT with `purpose=ics`). ICS must be deterministic, timezone correct, include `VALARM`, and localized to the customer language.
- Reminder/handshake today is confirmation flows + auto-cancel:
  - Far (>= configurable threshold 24h/36h): send `pre_confirmacao` immediately + schedule `confirmacao_oficial` on the previous day (morning appt: send 14:00 prev day, cap deadline 17:00; afternoon appt: send 17:00 prev day, deadline send+3h). If no response by deadline => auto-cancel.
  - Near (< threshold): send `confirmacao_urgente` immediately with a response window (default 6h), capped before appointment start; also auto-cancel if no response.
  - Customer replies by text: `1` confirm, `2` reschedule (needs human follow-up), `3` cancel.
- Booking availability/slot visibility uses a confirmation/cutoffs policy derived from `SetupProfile.payload.confirmation` (or `payload.business.confirmation`):
  - Defaults include: `minLeadHours=4`, `quietHoursStart=21:00`, `quietHoursEnd=08:00`, `immediateHorizonHours=36`, `immediateWindowHours=4`.
  - Quiet-hours mode: when booked during quiet hours, only allow tomorrow slots `>= 14:00`; schedule send at `08:00` and deadline `12:00` next day; short-lead slots during quiet hours are hidden.
  - Optional opt-in modes exist: `prevDayWindowsEnabled`; and `simpleModeEnabled` / `availabilityCutoffsOnly`.
- Notifications are queued in DB with idempotency keys, retry/backoff, Twilio SMS/WhatsApp sending, and a trial hard stop that blocks appointment-related sends after trial expiry.

Goals (must deliver)
1) Booking flow excellence (public)
- Premium UX: service → professional (if applicable) → date/time (only truly bookable slots) → customer details → confirm → success page.
- Success page must always show actions/buttons:
  - Add to Calendar (ICS)
  - Confirm presence / Cancel / Request reschedule (customer self-serve, tokenized, no login)
  - Contact via WhatsApp deep link (no secrets exposed)
  - View details (service, professional, address, policies, timezone)
- Anti double-booking: DB-level protection + transaction strategy + idempotency for booking confirmation.

2) Messaging cost minimization (explicit rule)
- Primary reminder is the customer’s phone calendar alarms (ICS + `VALARM`) => zero messaging cost.
- Paid channels (WhatsApp/SMS/email) are used mainly for handshake confirmation and critical updates.
- Enforce dedupe: never send the same `tipo` twice for the same appointment and channel; idempotency must be end-to-end.

3) Quiet hours + confirmation policy correctness (no regressions)
- Keep current semantics and config keys.
- Ensure timezone correctness everywhere (establishment timezone for scheduling math; store UTC in DB).

4) Worker/scheduler production hardening
- Productionize queue processing (Celery+Redis recommended) with safe retries/backoff, idempotency, and provider message-id storage.
- Keep existing admin diagnostics usable.

5) WhatsApp provider path (future phase, but structure now)
- Keep Twilio working.
- Introduce provider abstraction so Meta WhatsApp Cloud API can be added later.
- Webhooks must be validated.

6) Billing/trial/Stripe (must stay correct)
- Trial is a hard stop: day 5 blocks booking endpoints and notification sending; return HTTP 402 with code `TRIAL_EXPIRED`.
- Stripe subscription checkout + billing portal + signed webhooks exist under `/billing/*` including `/billing/stripe/webhook`. Webhook must be idempotent and flips plan state (`trial.active_plan`).

7) i18n/locale rules (must hold)
- Establishment has default language; visitor/customer can pick language. Booking UI + ICS + reminders follow the stored customer language. No implicit pt-BR/Brazil defaults.

Acceptance criteria
- `/booking/:slug` availability matches real schedules immediately; admin changes reflect without stale caching bugs.
- Double-booking is impossible under concurrency; retries are idempotent.
- ICS is secure/tokenized, timezone correct, includes alarms, localized.
- Confirmation flows + quiet hours behavior match current semantics and are reliable in background processing.
- Trial expiry blocks booking and sending with 402 `TRIAL_EXPIRED`.
- Stripe test checkout triggers webhook and activates plan; status endpoint reflects it.

Deliver in small PRs with tests and short runbook updates.

## Repo pointers (source of truth)
- Booking + policy + ICS: `Backend/app/api/booking/routes.py`
- Confirmation scheduler (pre/oficial/urgente): `Backend/app/services/scheduler.py`
- Notifications queue + sending: `Backend/app/services/notifications_v2.py`
- Pending actions (auto-cancel): `Backend/app/services/pending_actions.py`
- Stripe runbook: `STRIPE_RUNBOOK.md`
- Launch snapshot: `LAUNCH_SNAPSHOT.md`
- Domain checklist: `DOMAIN_LAUNCH_CHECKLIST.md`
- Product decisions: `PRODUCT_DECISIONS_AND_PROMPT.md`
