Testing locally (light, safe)

1. Ensure Docker Desktop is installed and running.
2. From project root, create a .env file with test values (important: enable mock to avoid Twilio costs):

MOCK_NOTIFICATIONS=true
DATABASE_URL=postgresql://easya:easya@db:5432/easya
# Add other env vars as needed (SECRET_KEY, OPENAI_API_KEY, etc.)

3. Start lightweight stack (uses docker-compose.override.yml automatically):

docker compose up --build -d

4. Open Locust in another terminal:

pip install locust
locust -f loadtest/locustfile.py --host http://localhost:8000

5. Open http://localhost:8089 and start with:
- Number of users: 100
- Spawn rate: 10

6. Monitor:
- Locust UI: p50/p95/p99 latencies, failures/sec
- Docker: docker compose ps and docker compose logs --tail=100 backend
- Task Manager / Docker Desktop: CPU & RAM

7. After test, bring down stack:

docker compose down

---

Smoke test (public booking flow)

Runs an end-to-end check: `GET /availability` → `POST /appointments` → download `calendar.ics`.

From project root (Windows PowerShell):

```powershell
\scripts\smoke-booking.ps1
```

Notes:
- The script auto-picks a free port starting at 8000.
- It starts/stops a local uvicorn process automatically.

---

PC test: open the calendar (.ics)

This creates a real appointment, downloads its `.ics`, and opens it with your default calendar app on Windows.

From project root (Windows PowerShell):

```powershell
\scripts\open-calendar.ps1
```

Notes:
- `MOCK_NOTIFICATIONS=true` prevents real Twilio/SMTP calls and logs simulated sends.
- Start with 100 users and increase only if CPU/RAM allow.
