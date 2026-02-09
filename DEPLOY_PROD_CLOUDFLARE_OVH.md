# Go-live: easy-agenda.com (Cloudflare Pages) + api.easy-agenda.com (OVH VPS)

This guide lets you advance now (even before you have the VPS IP) and then finish quickly once OVH provisions the server.

## 1) Cloudflare — DNS (do now)

In Cloudflare dashboard for `easy-agenda.com`:

### A) Create the API record (you can add it now and fill IP later)

- DNS → Records → Add record
- Type: `A`
- Name: `api`
- IPv4 address: (leave for later if UI requires, otherwise set once you have the IP)
- Proxy status: **DNS only** (recommended for first deploy; later you can switch to proxied if you want)
- TTL: Auto

### B) Frontend record (Cloudflare Pages will handle)

When you attach `easy-agenda.com` to Cloudflare Pages, Cloudflare will create the needed DNS record(s) or ask you to.

## 2) Cloudflare Pages — Frontend deploy (do now)

Pages → Create a project → Connect your Git repo.

Build configuration:

- Framework preset: **Vite**
- Root directory: `frontend_v2`
- Build command: `npm run build`
- Output directory: `dist`

Environment variables (Production):

- `VITE_API_URL` = `https://api.easy-agenda.com`

Custom domains:

- Pages → Your project → Custom domains
- Add `easy-agenda.com` (and optionally `www.easy-agenda.com` → redirect to apex)

## 3) OVH VPS — prepare server (once you have IP)

SSH into the VPS (Debian 12):

- Install Docker + Docker Compose plugin
- Open firewall ports: `80/tcp`, `443/tcp`

Then deploy the backend stack from this repo.

## 4) Backend — required production env

Set these environment variables for the backend container (values shown are examples):

- `ENV=production`
- `LOG_LEVEL=INFO`
- `ALLOWED_HOSTS=api.easy-agenda.com`
- `FRONTEND_URLS=https://easy-agenda.com`

Also set strong secrets/passwords and disable dev/demo behavior:

- `MOCK_NOTIFICATIONS=false`
- any dev seed/dev-login flags must be off in prod

## 5) HTTPS

Terminate TLS for `api.easy-agenda.com` (recommended options):

- Option A: Nginx on VPS with Let’s Encrypt (Certbot)
- Option B: Caddy (simplest)

Once HTTPS works, validate:

- `https://api.easy-agenda.com/healthz`
- Booking page loads from `https://easy-agenda.com/booking` and calls the API successfully

## 6) Smoke checks

- Open booking: `https://easy-agenda.com/booking/dev` (or your real slug)
- Create an appointment end-to-end
- Check dashboard login and list appointments

