from fastapi.testclient import TestClient

from app.db.database import SessionLocal
from app.models.models import Estabelecimento, Service, Funcionario, SetupProfile

from main import app


def test_availability_allows_small_end_of_shift_grace():
    """If a service+buffer ends a few minutes after closing, it can be allowed via config.

    This should NOT impact breaks (break overlaps remain blocked).
    """
    client = TestClient(app)

    s = SessionLocal()
    try:
        est = s.query(Estabelecimento).first()
        assert est is not None

        prof = s.query(Funcionario).filter(Funcionario.estabelecimento_id == est.id).first()
        assert prof is not None

        # Service: 60 min + 5 min buffer => 65 min.
        # Slot at 12:00 with close 13:00 ends 13:05.
        svc = s.query(Service).filter(Service.estabelecimento_id == est.id).first()
        assert svc is not None
        svc.duration_min = 60
        svc.buffer_min = 5
        svc.display_interval_min = 30

        # Ensure setup profile exists with Monday hours 09:00-13:00 and 5 min grace.
        # 2026-02-02 is a Monday.
        payload = {
            "business": {
                "timezone": "Europe/Madrid",
                "openingHours": {
                    "monday": {"active": True, "open": "09:00", "close": "13:00"}
                },
                "endOfShiftGraceMinutes": 5,
            }
        }

        sp = s.query(SetupProfile).filter(SetupProfile.estabelecimento_id == est.id).first()
        if not sp:
            sp = SetupProfile(estabelecimento_id=est.id, payload=payload)
            s.add(sp)
        else:
            sp.payload = payload

        s.commit()

        # Capture IDs/slug before closing the session (avoid DetachedInstanceError).
        svc_id = svc.id
        prof_id = prof.id
        slug = est.slug
    finally:
        s.close()

    r = client.get(
        f"/availability?date=2026-02-02&service_id={svc_id}&professional_id={prof_id}&slug={slug}"
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True

    # Find that professional and ensure 12:00 is offered
    found = None
    for it in body.get("availability") or []:
        if str(it.get("professional_id")) == str(prof.id):
            found = it
            break
    assert found is not None
    slots = [str(x) for x in (found.get("slots") or [])]
    assert "12:00" in slots
