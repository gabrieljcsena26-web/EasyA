from datetime import datetime, timedelta

from app.db.database import SessionLocal
from app.models.models import Estabelecimento, Funcionario, Service


def test_public_booking_calendar_ics_download(client):
    s = SessionLocal()
    try:
        est = s.query(Estabelecimento).first()
        assert est is not None

        svc = s.query(Service).filter(Service.estabelecimento_id == est.id).first()
        assert svc is not None

        prof = s.query(Funcionario).filter(Funcionario.estabelecimento_id == est.id).first()
        assert prof is not None
    finally:
        s.close()

    target_date = (datetime.now() + timedelta(days=4)).date().isoformat()

    # Pick a real free slot to avoid test-order conflicts.
    r0 = client.get(
        f"/availability?date={target_date}&service_id={int(svc.id)}&slug={est.slug}&professional_id={int(prof.id)}"
    )
    assert r0.status_code == 200, r0.text
    b0 = r0.json()
    assert b0.get("ok") is True

    chosen_prof_id = None
    chosen_start_time = None
    for it in b0.get("availability") or []:
        slots = it.get("slots") or []
        if slots:
            chosen_prof_id = int(it.get("professional_id"))
            chosen_start_time = str(slots[0])
            break
    assert chosen_prof_id is not None and chosen_start_time is not None

    payload = {
        "service_id": int(svc.id),
        "professional_id": chosen_prof_id,
        "date": target_date,
        "start_time": chosen_start_time,
        "channel": "booking_public",
        "customer_name": "Calendar Test",
        "customer_whatsapp": "+34000000000",
    }

    r = client.post(f"/appointments?slug={est.slug}", json=payload)
    assert r.status_code == 200, r.text

    body = r.json()
    assert body.get("ok") is True
    assert body.get("appointment") and body["appointment"].get("id")

    calendar_url = body.get("calendar_url")
    assert isinstance(calendar_url, str) and calendar_url.startswith("/appointments/")
    assert "calendar.ics" in calendar_url and "token=" in calendar_url

    r2 = client.get(calendar_url)
    assert r2.status_code == 200, r2.text
    assert "text/calendar" in (r2.headers.get("content-type") or "")

    txt = r2.text
    assert "BEGIN:VCALENDAR" in txt
    assert "BEGIN:VEVENT" in txt
    assert "SUMMARY:" in txt
