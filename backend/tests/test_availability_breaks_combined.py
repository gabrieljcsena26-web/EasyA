import copy

from app.db.database import SessionLocal
from app.models.models import Estabelecimento, Funcionario, Service, SetupProfile


def test_availability_respects_business_break_even_with_prof_break(client):
    s = SessionLocal()

    # Preserve prior state to avoid order-dependent tests.
    old_setup_payload = None
    old_service_fields = None

    try:
        est = s.query(Estabelecimento).first()
        assert est is not None

        prof = s.query(Funcionario).filter(Funcionario.estabelecimento_id == est.id).first()
        assert prof is not None

        svc = s.query(Service).filter(Service.estabelecimento_id == est.id).first()
        assert svc is not None

        old_service_fields = {
            "duration_min": svc.duration_min,
            "buffer_min": svc.buffer_min,
            "display_interval_min": svc.display_interval_min,
        }

        sp = s.query(SetupProfile).filter(SetupProfile.estabelecimento_id == est.id).first()
        if sp and isinstance(sp.payload, dict):
            old_setup_payload = copy.deepcopy(sp.payload)

        # Make slot grid deterministic: 60min service, 30min display interval.
        svc.duration_min = 60
        svc.buffer_min = 0
        svc.display_interval_min = 30

        prof_key = str(getattr(prof, "nome", "") or str(getattr(prof, "id", "")))
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
                # Business lunch break
                "breakStart": "12:00",
                "breakEnd": "14:00",
            },
            "team": {
                "perProfessional": {
                    prof_key: {
                        # Professional-specific break
                        "breakStart": "15:30",
                        "breakEnd": "16:00",
                    }
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
        prof_id = int(prof.id)
        svc_id = int(svc.id)
    finally:
        s.close()

    target_date = "2099-02-02"

    try:
        r = client.get(
            f"/availability?date={target_date}&service_id={svc_id}&professional_id={prof_id}&slug={slug}"
        )
        assert r.status_code == 200
        body = r.json()
        assert body.get("ok") is True

        found = None
        for it in body.get("availability") or []:
            if str(it.get("professional_id")) == str(prof_id):
                found = it
                break
        assert found is not None

        slots = [str(x) for x in (found.get("slots") or [])]

        # Business break must still apply even if the professional has their own break.
        assert "12:00" not in slots
        assert "13:00" not in slots

        # And the professional break should still apply.
        assert "15:00" not in slots

        # Sanity: there should still be bookable slots around the breaks.
        assert "11:00" in slots
        assert "14:00" in slots
    finally:
        # Restore previous state to avoid test order coupling.
        s2 = SessionLocal()
        try:
            est2 = s2.query(Estabelecimento).first()
            if est2 is not None and old_service_fields is not None:
                svc2 = s2.query(Service).filter(Service.estabelecimento_id == est2.id).first()
                if svc2 is not None:
                    svc2.duration_min = old_service_fields.get("duration_min")
                    svc2.buffer_min = old_service_fields.get("buffer_min")
                    svc2.display_interval_min = old_service_fields.get("display_interval_min")

            if est2 is not None:
                sp2 = s2.query(SetupProfile).filter(SetupProfile.estabelecimento_id == est2.id).first()
                if sp2 is not None and old_setup_payload is not None:
                    sp2.payload = old_setup_payload

            s2.commit()
        finally:
            s2.close()
