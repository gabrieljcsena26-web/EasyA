"""Set confirmation policy fields inside SetupProfile.payload.

Usage:
  cd Backend
  python -m scripts.set_confirmation_policy --slug barbeariaG --mode fixed14

Modes:
  fixed14:
    - >= immediateHorizonHours: véspera 14:00 -> 17:00
    - < immediateHorizonHours: confirmação imediata, janela 3h

Notes:
- Updates payload.confirmation (or payload.business.confirmation if you pass --target business).
- Creates SetupProfile row if missing.
"""

from __future__ import annotations

import argparse
from copy import deepcopy

from app.db.database import SessionLocal
from app.models.models import Estabelecimento, SetupProfile


def _ensure_dict(v):
    return v if isinstance(v, dict) else {}


def _get_container(payload: dict, target: str) -> dict:
    if target == "business":
        payload.setdefault("business", {})
        if not isinstance(payload.get("business"), dict):
            payload["business"] = {}
        return payload["business"]
    return payload


def _apply_mode_fixed14(container: dict) -> None:
    container.setdefault("confirmation", {})
    if not isinstance(container.get("confirmation"), dict):
        container["confirmation"] = {}

    c = container["confirmation"]

    # Recommended simple mode: slot visibility comes from cutoffs/lead time,
    # while send_at/confirm_by are computed for UI/reminders.
    c["simpleModeEnabled"] = True
    c["availabilityCutoffsOnly"] = True

    # Keep legacy behavior unless explicitly configured; this is opt-in at the payload level.
    c["minLeadHours"] = int(c.get("minLeadHours") or 4)
    c["immediateHorizonHours"] = int(c.get("immediateHorizonHours") or 36)

    # Always 3h confirmation window when booking is inside the horizon.
    c["immediateWindowHours"] = 3

    # For bookings beyond the horizon: fixed reminder at 14:00 on previous day, deadline 17:00.
    c["sendTimePrevDay"] = "14:00"
    c["capDeadlinePrevDay"] = "17:00"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--mode", default="fixed14", choices=["fixed14"])
    ap.add_argument("--target", default="root", choices=["root", "business"], help="Where to store confirmation config")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        est = db.query(Estabelecimento).filter_by(slug=str(args.slug)).first()
        if not est:
            raise SystemExit(f"estabelecimento not found for slug={args.slug}")

        sp = db.query(SetupProfile).filter_by(estabelecimento_id=est.id).first()
        if not sp:
            sp = SetupProfile(estabelecimento_id=est.id, payload={})
            db.add(sp)
            db.commit()
            db.refresh(sp)

        payload = deepcopy(_ensure_dict(sp.payload))
        container = _get_container(payload, target=str(args.target))

        if args.mode == "fixed14":
            _apply_mode_fixed14(container)

        sp.payload = payload
        db.add(sp)
        db.commit()

        print("OK")
        print("slug:", args.slug)
        print("setup_profile_id:", sp.id)
        print("target:", args.target)
        print("confirmation:", container.get("confirmation"))

    finally:
        db.close()


if __name__ == "__main__":
    main()
