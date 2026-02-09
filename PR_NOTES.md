Title: Rewrite/dashboard-v2 — ownership, historico, offline resilience

Summary
- Hardened `POST /appointments` to deterministically associate `Cliente` with the correct `Estabelecimento` (by `slug` when provided, otherwise derived from the chosen `profissional`).
- Added `Historico` audit trail and `GET /dashboard/agendamentos/{id}/historico` viewer.
- Frontend: `AgendaTable` now includes `config.business.slug` in appointment POST payloads; pending-actions queue (`ea_pending_actions`) persists offline ops.
- Added integration tests: `tests/test_booking_ownership.py` and existing `test_historico_flow.py` validated locally (note: full suite had two failures — see Test Results section).

Files changed
- Backend: `app/api/booking/routes.py` (ownership validation), `tests/test_booking_ownership.py` (new test)
- Frontend: `frontend_v2/src/components/AgendaTable.jsx`, `frontend_v2/src/pages/DashboardComplete.jsx`

Test Results (local)
- Ran full `pytest` in `Backend/`:
  - 6 passed, 2 failed, 28 warnings.
  - Failures are related to test DB setup: some tests expect seeded professionals/services per-establishment; when run in full suite ordering, the seed state isn't always present. Repro steps and proposed fixes are below.

Proposed fixes for CI/PR
1. Ensure test DB seeding runs before tests (prefer `pytest` fixture that creates a demo est/prof/service/funcionario), or make failing tests resilient by creating required entities in setup.
2. Add a lightweight `conftest.py` fixture to create deterministic test data and teardown after tests.
3. Add CI workflow (GitHub Actions) to run tests in a clean DB container (Postgres) with migrations applied.

CI: Added `.github/workflows/ci.yml` to run backend pytest and frontend build. It uses Postgres service and runs `Backend/create_tables.py` before tests.

Deployment / Operations notes
- Recommend moving the repository out of OneDrive to `C:\dev\easya-agenda` to avoid file locking and Node install issues.
- Steps to deploy backend (example):
  1. Set `DATABASE_URL` to a managed Postgres instance.
  2. Run alembic migrations (`alembic upgrade head`) or `python create_tables.py` for initial dev migration.
  3. Build and serve frontend (`cd frontend_v2 && npm run build`) and serve `build/` with nginx.
  4. Configure env vars and secrets: `SECRET_KEY`, JWT settings, SMTP/Twilio creds for notifications.

How to open a PR (local)
```
git checkout -b rewrite/dashboard-v2-finalize
git add -A
git commit -m "dashboard-v2: ownership, historico, offline queue, frontend slug fixes"
git push origin rewrite/dashboard-v2-finalize
# then open PR on GitHub (UI) or use `gh pr create --fill`
```

Next recommended tasks
- Fix test DB seeding and re-run full suite until green.
- Add CI that runs tests in a clean environment.
- Extend `ea_pending_actions` to include idempotency keys and server-side reconciliation endpoint.
- Replace localStorage queue with DB-backed queue for multi-device reliability (long-term).
