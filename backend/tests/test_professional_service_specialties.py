import copy

from app.db.database import SessionLocal
from app.models.models import Estabelecimento, Funcionario, Service, SetupProfile


def test_service_specialties_filter_availability_and_block_booking(client):
    s = SessionLocal()

    old_setup_payload = None

    try:
        est = s.query(Estabelecimento).first()
        assert est is not None

        # Ensure two services exist
        svc1 = s.query(Service).filter(Service.estabelecimento_id == est.id).order_by(Service.id.asc()).first()
        assert svc1 is not None

        svc2 = s.query(Service).filter(Service.estabelecimento_id == est.id).order_by(Service.id.desc()).first()
        if svc2 is None or svc2.id == svc1.id:
            svc2 = Service(
                estabelecimento_id=est.id,
                name="Service B",
                duration_min=30,
                buffer_min=0,
                price_cents=2000,
                display_interval_min=30,
            )
            s.add(svc2)
            s.flush()

        # Ensure two professionals exist
        prof1 = s.query(Funcionario).filter(Funcionario.estabelecimento_id == est.id).order_by(Funcionario.id.asc()).first()
        assert prof1 is not None

        prof2 = s.query(Funcionario).filter(Funcionario.estabelecimento_id == est.id).order_by(Funcionario.id.desc()).first()
        if prof2 is None or prof2.id == prof1.id:
            prof2 = Funcionario(nome="Demo Prof 2", telefone="+222222222", estabelecimento_id=est.id)
            s.add(prof2)
            s.flush()

        sp = s.query(SetupProfile).filter(SetupProfile.estabelecimento_id == est.id).first()
        if sp and isinstance(sp.payload, dict):
            old_setup_payload = copy.deepcopy(sp.payload)

        # Specialties: prof1 only svc1, prof2 only svc2
        payload = {
            "business": {
                "timezone": "Europe/Madrid",
                "openDays": {
                    "monday": True,
                    "tuesday": True,
                    "wednesday": True,
                    "thursday": True,
                    "friday": True,
                    "saturday": True,
                    "sunday": True,
                },
                "openingHours": {
                    "monday": {"active": True, "open": "09:00", "close": "18:00"},
                    "tuesday": {"active": True, "open": "09:00", "close": "18:00"},
                    "wednesday": {"active": True, "open": "09:00", "close": "18:00"},
                    "thursday": {"active": True, "open": "09:00", "close": "18:00"},
                    "friday": {"active": True, "open": "09:00", "close": "18:00"},
                    "saturday": {"active": True, "open": "09:00", "close": "18:00"},
                    "sunday": {"active": True, "open": "09:00", "close": "18:00"},
                },
                # Keep confirmation container present but permissive.
                "confirmation": {},
            },
            "team": {
                "perProfessional": {
                    str(getattr(prof1, "nome", "")): {"servicesAllowed": [int(svc1.id)]},
                    str(getattr(prof2, "nome", "")): {"servicesAllowed": [int(svc2.id)]},
                }
            },
        }

        if not sp:
            sp = SetupProfile(estabelecimento_id=est.id, payload=payload)
            s.add(sp)
        else:
            sp.payload = payload

        s.commit()

        slug = est.slug
        svc1_id = int(svc1.id)
        svc2_id = int(svc2.id)
        prof1_id = int(prof1.id)
        prof2_id = int(prof2.id)
    finally:
        s.close()

    target_date = "2099-02-02"

    try:
        r1 = client.get(f"/availability?date={target_date}&service_id={svc1_id}&slug={slug}")
        assert r1.status_code == 200
        body1 = r1.json()
        assert body1.get("ok") is True

        by_prof_1 = {str(it.get("professional_id")): [str(x) for x in (it.get("slots") or [])] for it in (body1.get("availability") or [])}
        assert str(prof1_id) in by_prof_1
        assert str(prof2_id) in by_prof_1
        assert len(by_prof_1[str(prof1_id)]) > 0
        assert by_prof_1[str(prof2_id)] == []

        r2 = client.get(f"/availability?date={target_date}&service_id={svc2_id}&slug={slug}")
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2.get("ok") is True
        by_prof_2 = {str(it.get("professional_id")): [str(x) for x in (it.get("slots") or [])] for it in (body2.get("availability") or [])}
        assert len(by_prof_2[str(prof2_id)]) > 0
        assert by_prof_2[str(prof1_id)] == []

        # Booking should be blocked if choosing a professional that doesn't offer the service.
        bad = client.post(
            f"/appointments?slug={slug}",
            json={
                "service_id": svc1_id,
                "professional_id": prof2_id,
                "date": target_date,
                "start_time": "09:00",
                "channel": "booking_public",
                "customer_name": "Test",
                "customer_whatsapp": "+34999999999",
            },
        )
        assert bad.status_code == 400
    finally:
        # restore setup
        s2 = SessionLocal()
        try:
            est2 = s2.query(Estabelecimento).first()
            if est2 is not None:
                sp2 = s2.query(SetupProfile).filter(SetupProfile.estabelecimento_id == est2.id).first()
                if sp2 is not None and old_setup_payload is not None:
                    sp2.payload = old_setup_payload
                    s2.commit()
        finally:
            s2.close()
