# Launch snapshot (EasyAgenda)

Date: 2026-02-07

## What’s shipped (core)
- Deterministic locale + timezone policy (no accidental pt-BR/Brazil defaults).
- Admin can change establishment language anytime; booking defaults to establishment language but visitor can switch; visitor-facing artifacts (ICS/reminders) follow visitor language.
- Booking flow end-to-end including localized `.ics` download.
- Reminder scheduler: “official confirmation schedule” rule implemented + unit tests.
- Billing transparency (“modo B”): WhatsApp budget included, warn at 80%, charge only overage.
- Trial hard-stop: 4-day trial; day 5 blocked.
  - Enforced in booking endpoints and appointment-notification sending.
  - Booking UX handles `402` with `{ code: "TRIAL_EXPIRED" }`.
- Admin conversion UX:
  - `GET /admin/trial-status`.
  - Global banner + Finance CTA.
  - i18n keys for pt/en/es/ca/fr.

## Onboarding: transfer/import (premium)
- Setup Wizard step “Integrar agenda” supports:
  - Clients import (CSV): preview + commit (upsert by phone), delimiter/encoding detection, duplicate signals.
  - Calendar import (.ics file): preview (conflicts + missing WhatsApp) + editable table + commit.
  - Google Calendar fast integration (no OAuth): iCal secret URL preview with SSRF protections → “Edit & import”.
- Backend endpoints covered by tests:
  - `/admin/import/ics/preview`
  - `/admin/import/ics/preview-url`
  - `/admin/import/clients-csv/preview`
  - `/admin/import/clients-csv/commit`

## Known risks / things to verify before production
- Production env secrets: `SECRET_KEY` must be set (never commit real `.env`).
- CORS + allowed hosts align with actual domains (`FRONTEND_URLS`, `ALLOWED_HOSTS`).
- WhatsApp sending:
  - Ensure production has `MOCK_NOTIFICATIONS=false` and templates configured.
  - Verify reminder scheduler is running (celery/worker) and can reach WhatsApp provider.
- Trial gating: confirm it blocks booking + notifications after day 4 for a real establishment.
- Import:
  - iCal URL imports are “snapshot” imports (not continuous sync). OAuth sync is a future upgrade.
- Stripe subscriptions (if enabled):
  - Ensure `STRIPE_SECRET_KEY`, `STRIPE_SUBSCRIPTION_PRICE_ID`, `STRIPE_WEBHOOK_SECRET` are set in production.
  - Configure Stripe webhook URL to `https://api.<domain>/billing/stripe/webhook` and enable subscription events.
  - Verify webhook flips `trial.active_plan=true` after successful subscription so the 4-day hard-stop is bypassed.

## Minimum “go/no-go” checklist
1) API health: `GET /healthz` returns 200 behind Nginx/Cloudflare.
2) Public booking smoke:
   - `GET /config` → `GET /availability` → `POST /appointments` → download `calendar.ics`.
3) Admin:
   - Login works; `/admin/config` loads.
   - Trial banner shows correctly; expired trial blocks booking.
4) Reminders:
   - Create a future appointment; confirm reminders are scheduled and sent.
5) Transfer:
   - Import small CSV (clients) + small .ics (events) and confirm appointments exist + reminders scheduled.
6) Stripe (if card payments are enabled):
  - Finance → “Pay by card” redirects to Stripe Checkout.
  - After payment, `GET /billing/subscription/status` shows `trial.active_plan=true`.

## Stripe runbook
- See [STRIPE_RUNBOOK.md](STRIPE_RUNBOOK.md)

## Useful scripts (local/dev)
- `scripts/dev_check.ps1` (Windows): seeds + checks config alignment + public booking smoke.
- `scripts/smoke_booking_http.py`: HTTP smoke test for booking + ICS download.
