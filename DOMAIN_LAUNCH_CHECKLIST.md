# Domain + Launch Checklist (Spain / EU)

This project is already functionally complete for booking logic and calendar `.ics` generation.
Before going live on a domain, align the production settings below.

## 1) Suggested domain layout

- Frontend: `https://app.<your-domain>`
- API: `https://api.<your-domain>`

This avoids mixing SPA routing and API routes, and keeps `.ics` links stable.

## 2) DNS records (typical)

If you host on a VPS with a public IPv4:
- `A app` -> `<SERVER_IP>`
- `A api` -> `<SERVER_IP>`

If you host frontend on a CDN (e.g. Cloudflare Pages/Vercel):
- `CNAME app` -> provider target
- `A api` -> `<SERVER_IP>`

## 3) Reverse proxy + HTTPS

- Terminate TLS in Nginx (Let’s Encrypt / Certbot)
- Forward to Uvicorn on `127.0.0.1:8000`
- Ensure `X-Forwarded-Proto` is set by Nginx
- Ensure Uvicorn trusts proxy headers (already configured in systemd template)

## 4) Backend env vars (minimum)

Set these on the server (systemd Environment= or `.env` loaded by your process manager):

- `ENV=production`
- `SECRET_KEY=<strong random>`
- `DATABASE_URL=postgresql://...`
- `REDIS_URL=redis://...` (optional if Celery disabled)

Public URL generation:
- `FRONTEND_URLS=https://app.<your-domain>`
- `FRONTEND_BASE_URL=https://app.<your-domain>`
- `BOOKING_PUBLIC_BASE_URL=https://app.<your-domain>`
- `API_PUBLIC_BASE_URL=https://api.<your-domain>`  (this makes `calendar_url` absolute)

Important: in production, do **not** use wildcard CORS.

## 4b) Stripe (optional, for card payments)

If you want card payments for SaaS subscriptions:
- Set `STRIPE_SECRET_KEY`, `STRIPE_SUBSCRIPTION_PRICE_ID`, `STRIPE_WEBHOOK_SECRET` on the backend.
- Configure Stripe webhook URL:
	- `https://api.<your-domain>/billing/stripe/webhook`
- Enable events:
	- `checkout.session.completed`
	- `customer.subscription.created`
	- `customer.subscription.updated`
	- `customer.subscription.deleted`

Runbook: [STRIPE_RUNBOOK.md](STRIPE_RUNBOOK.md)

## 5) Production safety toggles

The backend includes local-dev helpers.
In production (`ENV=production`) they are automatically disabled:
- auto create tables (`AUTO_CREATE_DB`)
- auto dev migrations (`AUTO_DEV_MIGRATIONS`)
- `POST /auth/dev-login`
- `POST /admin/seed-test-data`

## 6) Smoke checks after pointing the domain

- `GET https://api.<your-domain>/ping` returns ok
- Frontend loads on `https://app.<your-domain>`
- Booking creates appointment and returns `calendar_url` starting with `https://api.<your-domain>/appointments/.../calendar.ics?...`
- Open the `.ics` on PC and import to New Outlook calendar
- Send the `.ics` link over WhatsApp and open on mobile

## 8) Database migrations (Alembic) — production-safe

Goal: never rely on runtime `create_all` in production.

- First-time setup (new DB): run `alembic upgrade head` (baseline revision creates tables).
- Ongoing deploys: run `alembic upgrade head` before restarting the backend.

If using systemd on the VPS:
- Install units from `Backend/deploy/`:
	- `easya-migrate.service` (oneshot)
	- `easya-backend.service` (now depends on migrations)
- Ensure `/opt/easya-backend/.env` contains `DATABASE_URL` and `ENV=production`.

## 9) Backups (Postgres) + restore drill

Minimal reliable approach:
- Daily `pg_dump` via systemd timer (`easya-backup.timer`)
- Keep retention (default 14 days)
- Perform a restore drill before go-live

Files:
- `Backend/deploy/backup_postgres.sh`
- `Backend/deploy/restore_postgres.sh`
- `Backend/deploy/easya-backup.service`
- `Backend/deploy/easya-backup.timer`

Prereq on Ubuntu:
- Install client tools: `sudo apt-get update && sudo apt-get install -y postgresql-client`
- Ensure backup directory exists and is writable (default `/var/backups/easya/postgres`).

Restore drill (recommended):
- Restore into a fresh DB (or a staging DB) using `restore_postgres.sh <backup.dump>`.
- Run the smoke checks again.

## 10) Observability mínima

- Public health endpoints (for LB/uptime monitor):
	- `GET /healthz` (DB ping)
	- `GET /readyz` (currently same as health)
- Admin diagnostics (protected): `GET /admin/health`
- Logs:
	- systemd: `journalctl -u easya-backend -f`
	- docker: `docker compose logs -f backend`

Simple monitoring suggestion:
- Configure an external uptime check to hit `https://api.<domain>/healthz` every 1–5 minutes.

## 7) What is not blocked by the domain

You can keep shipping without the domain, as long as you have:
- stable DB schema/migrations
- production env var strategy (secrets)
- basic monitoring/logging

The domain becomes necessary when you want real-world flows:
- WhatsApp sharing with a public URL
- testing calendar imports outside your machine
- stable HTTPS cookies/session behaviors
