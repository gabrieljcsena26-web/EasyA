import copy

from app.db.database import SessionLocal
from app.models.models import Estabelecimento, Funcionario, Service, SetupProfile


def test_availability_supports_broken_hours_windows(client):
    s = SessionLocal()

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

        # Deterministic grid
        svc.duration_min = 60
        svc.buffer_min = 0
        svc.display_interval_min = 30

        prof_key = str(getattr(prof, "nome", "") or str(getattr(prof, "id", "")))

        # Use a far-future date so confirmation filtering won't block due to 'now'.
        # 2099-02-02 is fine regardless of weekday because we set all weekdays.
        windows = [
            {"open": "09:00", "close": "11:00"},
            {"open": "14:00", "close": "16:00"},
        ]

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
                    "monday": {"active": True, "windows": windows},
                    "tuesday": {"active": True, "windows": windows},
                    "wednesday": {"active": True, "windows": windows},
                    "thursday": {"active": True, "windows": windows},
                    "friday": {"active": True, "windows": windows},
                    "saturday": {"active": True, "windows": windows},
                    "sunday": {"active": True, "windows": windows},
                },
                # Keep a confirmation container (even empty) for admin-driven behavior.
                "confirmation": {},
            },
            "team": {
                "perProfessional": {
                    prof_key: {
                        "windows": [
                            {"startTime": "09:30", "endTime": "11:00"},
                            {"startTime": "14:30", "endTime": "16:00"},
                        ]
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

        # Must only offer slots inside the configured professional windows.
        # Note: /availability intentionally enforces spacing by duration_total (non-overlapping starts),
        # so with a 60min service and 30min interval we expect only one slot per 90min block.
        assert "09:30" in slots
        assert "14:30" in slots

        # Outside the windows or crossing window ends should be excluded.
        assert "09:00" not in slots
        assert "10:00" not in slots  # excluded by spacing after 09:30
        assert "10:30" not in slots  # would end after 11:00
        assert "14:00" not in slots
        assert "15:00" not in slots  # excluded by spacing after 14:30
        assert "15:30" not in slots  # would end after 16:00
        assert "13:30" not in slots
    finally:
        # Restore prior state to avoid test order coupling.
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
