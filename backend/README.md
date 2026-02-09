# EasyA Backend — Production setup quickstart

This README lists essential steps to run the backend in production.

Prerequisites
- Server (Ubuntu 22.04+ recommended)
- PostgreSQL or other supported DB
- Redis (for Celery)
- Python 3.10+

Steps
1. Clone repo and create venv

```bash
git clone <repo>
cd Backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Environment variables
Create `.env` or set env vars (example):

```
DATABASE_URL=postgresql://user:pass@localhost:5432/easya
REDIS_URL=redis://localhost:6379/0
TWILIO_SID=xxxx
TWILIO_TOKEN=xxxx
TWILIO_WHATSAPP_NUMBER=whatsapp:+1415...
SENTRY_DSN=https://...@sentry.io/12345
ENV=production
```

3. Run Alembic migrations

```bash
alembic -c alembic.ini upgrade head
```

4. Start services (systemd examples provided in `deploy/`)

```bash
# copy service files to /etc/systemd/system/
sudo cp deploy/easya-backend.service /etc/systemd/system/
sudo cp deploy/celery-worker.service /etc/systemd/system/
sudo cp deploy/celery-beat.service /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable --now easya-backend.service
sudo systemctl enable --now celery-worker.service
sudo systemctl enable --now celery-beat.service
```

5. Nginx & TLS
- Configure Nginx reverse proxy to forward to `127.0.0.1:8000` and use Certbot for TLS.

Twilio setup (SMS/WhatsApp)
1. Create a Twilio account at https://www.twilio.com/.
2. Get Account SID and Auth Token and set them as `TWILIO_SID` and `TWILIO_TOKEN` in environment variables.
3. For WhatsApp, enable the Twilio WhatsApp sandbox or request a WhatsApp sender number and set `TWILIO_WHATSAPP_NUMBER` (format: `whatsapp:+1555...`).
4. Use the admin endpoint to validate configuration and enqueue a test SMS:

```bash
# protected endpoint; see backend `admin` routes for auth placeholder
curl -X POST "https://your-host/admin/test-sms" \
	-H "Authorization: Bearer superadmintoken" \
	-H "Content-Type: application/json" \
	-d '{"to":"+34600000000","message":"Teste EasyA: isso é só um teste","canal":"sms"}'
```

5. Monitor results in Sentry and in the `notificacoes` DB table; `provider_response` will contain provider details on success.

Notes:
- For local testing you can use Twilio test credentials and magic phone numbers documented by Twilio to avoid real SMS charges.
- Ensure you comply with country SMS regulations and include opt-out instructions if sending marketing messages.

6. Monitoring & alerts
- Configure Sentry (DSN) and create alerts for `permanent_failure` spikes.

Troubleshooting
- Check logs: `journalctl -u easya-backend -f` and `journalctl -u celery-worker -f`
- Database migrations issues: ensure `DATABASE_URL` points to correct DB and user has create/alter rights.

