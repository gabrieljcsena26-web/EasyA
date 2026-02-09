from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.database import SessionLocal
from app.models.models import Estabelecimento, Funcionario, Service

from main import app


def _auth_header_for_est(est: Estabelecimento) -> dict:
    token = create_access_token(
        {
            "username": est.slug,
            "slug": est.slug,
            "estabelecimento_id": est.id,
        },
        expires_in_minutes=30,
    )
    return {"Authorization": f"Bearer {token}"}


def _get_demo_entities():
    s = SessionLocal()
    try:
        est = s.query(Estabelecimento).first()
        assert est is not None
        prof = s.query(Funcionario).filter(Funcionario.estabelecimento_id == est.id).first()
        assert prof is not None
        svc = s.query(Service).filter(Service.estabelecimento_id == est.id).first()
        assert svc is not None
        return est, prof, svc
    finally:
        s.close()


def test_admin_import_ics_preview_upload_ok():
    client = TestClient(app)
    est, prof, svc = _get_demo_entities()

    headers = _auth_header_for_est(est)

    ics = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//EasyAgenda Tests//EN
BEGIN:VEVENT
UID:evt-1
DTSTAMP:20260101T000000Z
DTSTART:20260110T090000Z
DTEND:20260110T100000Z
SUMMARY:Maria +34123456789
DESCRIPTION:Corte
END:VEVENT
BEGIN:VEVENT
UID:evt-2
DTSTAMP:20260101T000000Z
DTSTART:20260111T090000Z
DTEND:20260111T093000Z
SUMMARY:Sem telefone
END:VEVENT
END:VCALENDAR
"""

    files = {"file": ("demo.ics", ics.encode("utf-8"), "text/calendar")}
    data = {"professional_id": str(prof.id), "service_id": str(svc.id)}

    r = client.post("/admin/import/ics/preview", headers=headers, files=files, data=data)
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert body.get("professional_id") == prof.id
    assert body.get("service_id") == svc.id

    counts = body.get("counts") or {}
    assert counts.get("total") == 2
    assert counts.get("needs_phone") == 1

    items = body.get("items") or []
    assert len(items) == 2
    assert items[0].get("start_local")


def test_admin_import_ics_preview_url_rejects_non_https():
    client = TestClient(app)
    est, prof, svc = _get_demo_entities()

    headers = _auth_header_for_est(est)

    r = client.post(
        "/admin/import/ics/preview-url",
        headers=headers,
        json={"url": "http://example.com/basic.ics", "professional_id": prof.id, "service_id": svc.id},
    )
    assert r.status_code == 400


def test_admin_import_clients_csv_preview_and_commit():
    client = TestClient(app)
    est, _, _ = _get_demo_entities()

    headers = _auth_header_for_est(est)

    csv_text = """nome;whatsapp;idioma
Alice;+34111111111;es-ES
Bob;;
"""

    files = {"file": ("clients.csv", csv_text.encode("utf-8"), "text/csv")}

    r = client.post("/admin/import/clients-csv/preview", headers=headers, files=files)
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True

    counts = body.get("counts") or {}
    assert counts.get("total") == 2
    assert counts.get("ready") == 1
    assert counts.get("needs_phone") == 1

    items = body.get("items") or []
    assert isinstance(items, list)
    assert items[0].get("phone")

    r2 = client.post("/admin/import/clients-csv/commit", headers=headers, json={"items": items})
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2.get("ok") is True
    assert isinstance(body2.get("created"), int)
    assert isinstance(body2.get("updated"), int)
    assert isinstance(body2.get("skipped"), int)
