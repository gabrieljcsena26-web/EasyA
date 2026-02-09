"""Debug confirmation window for demo-est.

Run:
  cd Backend
  python -m scripts.debug_confirmation_demo_est
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.db.database import SessionLocal
from app.models.models import Estabelecimento, SetupProfile
from app.api.booking.routes import _extract_confirmation_policy, _confirmation_times_for_slot

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore


def main() -> None:
    db = SessionLocal()
    try:
        est = db.query(Estabelecimento).filter_by(slug="demo-est").first()
        if not est:
            raise SystemExit("demo-est not found")
        sp = db.query(SetupProfile).filter_by(estabelecimento_id=est.id).first()
        payload = sp.payload if sp and isinstance(sp.payload, dict) else None

        tz = None
        if ZoneInfo is not None and isinstance(payload, dict):
            business = payload.get("business") if isinstance(payload.get("business"), dict) else {}
            tz_name = business.get("timezone") or payload.get("timezone") or "America/Sao_Paulo"
            tz = ZoneInfo(str(tz_name))

        now_local = datetime.now(tz) if tz else datetime.now()
        pol = _extract_confirmation_policy(payload)

        slot_start_local = (now_local + timedelta(days=1)).replace(hour=11, minute=0, second=0, microsecond=0)

        send_at, confirm_by = _confirmation_times_for_slot(
            now_local=now_local,
            slot_start_local=slot_start_local,
            policy=pol,
        )

        print("now_local:", now_local.isoformat())
        print("slot_start_local:", slot_start_local.isoformat())
        print("policy:", {k: (str(v) if hasattr(v, 'isoformat') else v) for k, v in pol.items()})
        print("send_at:", send_at.isoformat() if send_at else None)
        print("confirm_by:", confirm_by.isoformat() if confirm_by else None)
    finally:
        db.close()


if __name__ == "__main__":
    main()
