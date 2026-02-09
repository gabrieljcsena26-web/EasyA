"""Fix demo-est booking availability.

Goal: make it easy to test the public booking flow on any day/time.

What it does:
- Ensures demo-est has a SetupProfile
- Sets opening hours for all weekdays (09:00-18:00)
- Sets openDays to all true
- Adds per-professional workDays/work window for "Demo Prof" (if present)
- Sets confirmation.minLeadHours=0 so slots show up even for same-day tests

Run:
  cd Backend
  python -m scripts.fix_demo_est_setup
"""

from __future__ import annotations

import copy

from app.db.database import SessionLocal
from app.models.models import Estabelecimento, SetupProfile, Funcionario


WEEKDAYS = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


def _opening_hours_all_days(open_hhmm: str = "09:00", close_hhmm: str = "18:00") -> dict:
    return {
        day: {"active": True, "open": open_hhmm, "close": close_hhmm}
        for day in WEEKDAYS
    }


def _open_days_all_true() -> dict:
    return {day: True for day in WEEKDAYS}


def main() -> None:
    db = SessionLocal()
    try:
        est = db.query(Estabelecimento).filter_by(slug="demo-est").first()
        if not est:
            raise SystemExit("demo-est not found in DB")

        sp = db.query(SetupProfile).filter_by(estabelecimento_id=est.id).first()
        if not sp:
            sp = SetupProfile(estabelecimento_id=est.id, payload={})
            db.add(sp)
            db.flush()

        # IMPORTANT: JSON columns are not always change-tracked for in-place updates.
        # Work with a fresh dict so SQLAlchemy persists changes.
        payload = copy.deepcopy(sp.payload) if isinstance(sp.payload, dict) else {}
        business = payload.get("business") if isinstance(payload.get("business"), dict) else {}

        # Keep an existing timezone if present; otherwise set a reasonable default
        tz = business.get("timezone") or payload.get("timezone") or "Europe/Madrid"

        business.update(
            {
                "timezone": tz,
                "openDays": _open_days_all_true(),
                "openingHours": _opening_hours_all_days("09:00", "18:00"),
                "endOfShiftGraceMinutes": 10,
                "confirmation": {
                    "minLeadHours": 0,
                    "immediateHorizonHours": 36,
                    "immediateWindowHours": 4,
                    # Cutoffs + guardrails (V2) - used by booking availability filtering.
                    "cutoffsEnabled": True,
                    "morningEndTime": "12:00",
                    "afternoonEndTime": "17:00",
                    "morningCutoffPrevDay": "20:00",
                    "afternoonCutoffSameDay": "12:00",
                    "nightCutoffSameDay": "16:00",
                    # If there is less than 2h for the customer to confirm, the slot is not shown.
                    "minConfirmWindowHours": 2,
                    # Never allow confirmation deadline after (start - 2h).
                    "capBeforeStartHours": 2,
                    # Same-day booking policy (optional). Keep enabled for demo.
                    "allowSameDay": True,
                    "allowSameDayNightOnly": False,
                    # Disable quiet-hours restrictions for local/demo testing.
                    # In the booking policy implementation, quietHoursStart == quietHoursEnd means "no quiet hours".
                    "quietHoursStart": "00:00",
                    "quietHoursEnd": "00:00",
                    "tomorrowAfterQuietMinTime": "14:00",
                    "nightSendTime": "08:00",
                    "nightConfirmDeadline": "12:00",
                    "sendTimePrevDay": "17:00",
                    "capDeadlinePrevDay": "20:00",
                    "hysteresisStepMinutes": 15,
                },
            }
        )

        payload["business"] = business

        # Per-professional defaults (optional): make Demo Prof work every day, 09-18
        try:
            demo_prof = (
                db.query(Funcionario)
                .filter(Funcionario.estabelecimento_id == est.id)
                .order_by(Funcionario.id.asc())
                .first()
            )
            if demo_prof:
                team = payload.get("team") if isinstance(payload.get("team"), dict) else {}
                per = team.get("perProfessional") if isinstance(team.get("perProfessional"), dict) else {}
                key = str(getattr(demo_prof, "nome", "Demo Prof") or "Demo Prof")
                per[key] = {
                    **(per.get(key) if isinstance(per.get(key), dict) else {}),
                    "workDays": _open_days_all_true(),
                    "startTime": "09:00",
                    "endTime": "18:00",
                    "endOfShiftGraceMinutes": 10,
                }
                team["perProfessional"] = per
                payload["team"] = team
        except Exception:
            # If anything goes wrong here, still keep business-wide hours.
            pass

        sp.payload = payload
        db.commit()

        print("[ok] Updated demo-est SetupProfile")
        print("      timezone:", tz)
        print("      openingHours: all days 09:00-18:00")
        print("      confirmation.minLeadHours:", business.get("confirmation", {}).get("minLeadHours"))

    finally:
        db.close()


if __name__ == "__main__":
    main()
