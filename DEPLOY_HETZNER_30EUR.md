# Deploy plan (Hetzner ~€30/mo)

Goal: a solid launch setup sized for ~200–500 concurrent users, with a clean upgrade path to 1k.

## Recommended Hetzner server

Best value under ~€30/mo:
- **Hetzner Cloud CPX31** (typically 4 vCPU / 8 GB RAM / 160 GB NVMe)

Why:
- 4 vCPU gives headroom for FastAPI workers + Postgres.
- 8 GB is enough to run Nginx + backend + Postgres + small Redis.

## Architecture (Phase 1: one server)

On the same VPS:
- Nginx (TLS + reverse proxy)
- Backend (Uvicorn)
- Postgres
- Optional: Redis (if you enable Celery/cache)

This keeps ops simple and cheap.

## Upgrade path (Phase 2: when traffic grows)

When you start seeing sustained CPU/latency spikes:
- Move Postgres to a dedicated DB (managed or a second VPS)
- Add a second backend instance and load-balance
- Add PgBouncer if Postgres connections grow
- Add short TTL caching for heavy endpoints (10–30s)

## What to enable in Hetzner

- **Backups** (Hetzner backups option) OR nightly snapshots
- **Firewall**: allow only 22, 80, 443 to the server
- SSH key login, disable password login

## Minimal production env vars

See Backend/.env.production.example for the full list.

Minimum:
- `ENV=production`
- `SECRET_KEY=<strong random>`
- `DATABASE_URL=postgresql://...`

Public URLs (when you have the domain):
- `FRONTEND_URLS=https://app.YOUR_DOMAIN_HERE`
- `FRONTEND_BASE_URL=https://app.YOUR_DOMAIN_HERE`
- `BOOKING_PUBLIC_BASE_URL=https://app.YOUR_DOMAIN_HERE`
- `API_PUBLIC_BASE_URL=https://api.YOUR_DOMAIN_HERE`
- `ALLOWED_HOSTS=api.YOUR_DOMAIN_HERE`

## Suggested worker count

Start with:
- `--workers 4` (matches 4 vCPU)

Then tune based on CPU usage.

## Quick acceptance checks

- `GET /ping` returns ok
- Booking flow creates an appointment
- Response returns an absolute `calendar_url` once `API_PUBLIC_BASE_URL` is set
- `.ics` opens/imports in New Outlook and mobile
