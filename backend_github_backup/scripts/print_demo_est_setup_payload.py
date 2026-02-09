"""Print SetupProfile payload for demo-est (truncated).

Run:
  cd Backend
  python -m scripts.print_demo_est_setup_payload
"""

from __future__ import annotations

import json

from app.db.database import SessionLocal
from app.models.models import Estabelecimento, SetupProfile


def main() -> None:
    db = SessionLocal()
    try:
        est = db.query(Estabelecimento).filter_by(slug="demo-est").first()
        if not est:
            raise SystemExit("demo-est not found")
        sp = db.query(SetupProfile).filter_by(estabelecimento_id=est.id).first()
        if not sp:
            print("no SetupProfile")
            return
        payload = sp.payload if isinstance(sp.payload, dict) else {}
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        print(text[:4000])
    finally:
        db.close()


if __name__ == "__main__":
    main()
