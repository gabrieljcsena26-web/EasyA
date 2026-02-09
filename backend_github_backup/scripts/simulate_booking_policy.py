"""Simulate booking confirmation policy decisions.

Usage:
  cd Backend
  C:/dev/easya-agenda_clean_2026-01-20/.venv/Scripts/python.exe -m scripts.simulate_booking_policy --slug demo-est --slot 2026-02-02T09:00
  C:/dev/easya-agenda_clean_2026-01-20/.venv/Scripts/python.exe -m scripts.simulate_booking_policy --slot 2026-02-01T18:00 --now 2026-02-01T14:00

Notes:
- Uses SetupProfile.payload.business.timezone if present.
- Prints whether the slot is bookable and the computed send_at/confirm_by (local).
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

from app.db.database import SessionLocal
from app.models.models import Estabelecimento, SetupProfile

from app.api.booking.routes import (
    _cutoff_allows_slot,
    _extract_confirmation_policy,
    _confirmation_times_for_slot,
)


def _parse_dt(v: str) -> datetime:
    s = (v or "").strip()
    if not s:
        raise ValueError("empty datetime")
    # Accept YYYY-MM-DDTHH:MM or ISO with seconds.
    if len(s) == 16 and "T" in s:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M")
    return datetime.fromisoformat(s)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", default="demo-est")
    ap.add_argument("--now", default=None, help="Local datetime, e.g. 2026-02-01T14:00")
    ap.add_argument("--slot", required=True, help="Slot start local datetime, e.g. 2026-02-02T09:00")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        est = db.query(Estabelecimento).filter_by(slug=str(args.slug)).first()
        if not est:
            raise SystemExit(f"estabelecimento not found for slug={args.slug}")

        sp = db.query(SetupProfile).filter_by(estabelecimento_id=est.id).first()
        payload = sp.payload if sp and isinstance(sp.payload, dict) else {}

        tz = None
        if ZoneInfo is not None:
            business = payload.get("business") if isinstance(payload.get("business"), dict) else {}
            tz_name = str(business.get("timezone") or payload.get("timezone") or "America/Sao_Paulo")
            tz = ZoneInfo(tz_name)

        now_local = _parse_dt(args.now) if args.now else datetime.now(tz) if tz else datetime.now()
        slot_start_local = _parse_dt(args.slot)
        if tz and slot_start_local.tzinfo is None:
            slot_start_local = slot_start_local.replace(tzinfo=tz)
        if tz and now_local.tzinfo is None:
            now_local = now_local.replace(tzinfo=tz)

        policy = _extract_confirmation_policy(payload)

        allowed, reason = _cutoff_allows_slot(now_local=now_local, slot_start_local=slot_start_local, policy=policy)
        print("slug:", args.slug)
        print("tz:", str(tz) if tz else None)
        print("now_local:", now_local.isoformat())
        print("slot_start_local:", slot_start_local.isoformat())
        print("cutoff_allowed:", allowed, "reason:", reason)

        send_at, confirm_by = _confirmation_times_for_slot(now_local=now_local, slot_start_local=slot_start_local, policy=policy)
        if send_at is None or confirm_by is None:
            print("bookable:", False)
            print("reason_hint:", reason or "blocked_by_policy")
            return

        print("bookable:", True)
        print("send_at:", send_at.isoformat())
        print("confirm_by:", confirm_by.isoformat())
        print("time_to_confirm:", str(confirm_by - now_local))
        print("lead_time:", str(slot_start_local - now_local))
        print("start_minus_2h:", (slot_start_local - timedelta(hours=2)).isoformat())

    finally:
        db.close()


if __name__ == "__main__":
    main()
