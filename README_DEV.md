# Development quickstart

Steps to get a stable local dev environment with frontend (CRA) and backend (FastAPI).

1) Install deps

```powershell
# Backend (python venv recommended)
cd Backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Frontend
cd ..\frontend_v2
npm ci
```

2) Start both services (Windows PowerShell)

```powershell
# From repo root (this script opens two PowerShell windows)
.\scripts\dev-start.ps1
```

The script sets `SECRET_KEY` and `ACCESS_TOKEN_EXPIRE_MINUTES` for the backend window. If you need a different secret, pass parameters:

```powershell
.\scripts\dev-start.ps1 -SecretKey "my-secret" -AccessTokenExpireMinutes 1440
```

3) Dev token usage

- To generate a token locally, use `Backend/generate_token.py` (when backend uses the same `SECRET_KEY`).
- In the browser console you can set `window.__DEV_TOKEN__ = '<JWT>'` or run:

```js
localStorage.setItem('DEV_JWT_TOKEN','<JWT>')
```

4) Notes

- Frontend `package.json` already configures a proxy to `http://127.0.0.1:8000` for dev; leave `REACT_APP_API_URL` blank to use proxy.
- Backend CORS can be controlled with `FRONTEND_URLS` env var (default in `.env.example`).
