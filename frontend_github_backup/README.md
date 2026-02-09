# EasyAgenda Frontend v2 (Vite)

This is the primary frontend (React + Vite) used by the project.

## Local development

```powershell
cd frontend_v2
npm ci
npm run dev
```

Open: http://localhost:3002

## Build

```powershell
npm run build
npm run preview
```

## Production (Cloudflare Pages)

Recommended setup:

- Frontend: `https://easy-agenda.com` (Cloudflare Pages)
- API: `https://api.easy-agenda.com` (VPS)

Because the API is on a different origin, the frontend must know the API base URL.
This project supports setting it via env at build time:

- `VITE_API_URL=https://api.easy-agenda.com`

Cloudflare Pages build settings:

- **Root directory**: `frontend_v2`
- **Build command**: `npm run build`
- **Build output directory**: `dist`
- **Environment variables**: set `VITE_API_URL` as above

Backend must allow CORS for the frontend origin (set `FRONTEND_URLS=https://easy-agenda.com`).

