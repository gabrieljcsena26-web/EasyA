import pytest
from fastapi.testclient import TestClient
from app.db.database import SessionLocal
from app.models.models import Estabelecimento, Cliente, Service, Funcionario

from main import app


def setup_establishment():
    s = SessionLocal()
    est = s.query(Estabelecimento).first()
    s.close()
    return est


def test_public_post_assigns_cliente_to_professional_establishment():
    client = TestClient(app)
    est = setup_establishment()
    assert est is not None

    # get available services/professionals for this establishment
    cfg = client.get(f"/config?slug={est.slug}").json()
    services = cfg.get("services") or []
    pros = cfg.get("professionals") or []

    # fallback to DB if config doesn't include services/professionals in test DB
    s = SessionLocal()
    # Prefer a professional that has services in the same estabelecimento
    prof_id = None
    service_id = None
    profs_db = s.query(Funcionario).all()
    for p in profs_db:
        svc = s.query(Service).filter(Service.estabelecimento_id == p.estabelecimento_id).first()
        if svc:
            prof_id = p.id
            service_id = svc.id
            break

    # Fallback: use config response if DB scan didn't find pair
    if not prof_id or not service_id:
        if pros and services:
            prof_id = pros[0]["id"]
            service_id = services[0]["id"]
        else:
            any_prof = s.query(Funcionario).first()
            any_service = s.query(Service).first()
            assert any_prof is not None and any_service is not None, "no professionals/services in DB"
            prof_id = any_prof.id
            service_id = any_service.id
    s.close()

    phone = "+999900000"
    # pick an available slot using the availability endpoint to avoid conflicts
    slot = None
    for day in ["2026-02-01","2026-02-02","2026-02-03","2026-02-04","2026-02-05","2026-02-06"]:
        av = client.get(f"/availability?date={day}&service_id={service_id}&professional_id={prof_id}")
        if av.status_code == 200:
            items = av.json() or {}
            # items is { ok: True, ... } with list of professionals
            if isinstance(items, dict) and items.get("ok"):
                for it in items.get("data", []) if items.get("data") else items.get("availability", []) or []:
                    # support different shapes; look for matching professional_id
                    pid = it.get("professional_id") or it.get("professional_id")
                    if str(pid) == str(prof_id) or int(pid) == int(prof_id):
                        slots = it.get("slots") or []
                        if slots:
                            slot = (day, slots[0])
                            break
            # fallback: some implementations return list per professional
            if not slot and isinstance(items, list):
                for it in items:
                    if str(it.get("professional_id")) == str(prof_id):
                        slots = it.get("slots") or []
                        if slots:
                            slot = (day, slots[0]); break
        if slot: break

    if not slot:
        pytest.skip("no free slot found in test DB for chosen professional")

    payload = {
        "service_id": service_id,
        "professional_id": prof_id,
        "date": slot[0],
        "start_time": slot[1],
        "channel": "landing",
        "customer_name": "OwnerTest",
        "customer_whatsapp": phone,
    }

    # POST without slug — backend should derive establishment from professional
    r = client.post("/appointments", json=payload)
    if r.status_code != 200:
        print('POST /appointments failed:', r.status_code, r.text)
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    appt = body.get("appointment")
    assert appt and appt.get("id")

    # verify Cliente created/linked to the same estabelecimento as the professional
    s = SessionLocal()
    cliente = s.query(Cliente).filter(Cliente.telefone == phone).first()
    assert cliente is not None
    prof = s.query(Funcionario).filter(Funcionario.id == prof_id).first()
    assert prof is not None
    assert cliente.estabelecimento_id == prof.estabelecimento_id
    s.close()
