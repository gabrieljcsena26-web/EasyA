import argparse
import time
import urllib.parse

import requests

from app.db.database import SessionLocal
from app.models.models import Estabelecimento, Funcionario, Service


def _pick_demo_booking_target() -> tuple[str, int]:
    s = SessionLocal()
    try:
        est = s.query(Estabelecimento).order_by(Estabelecimento.id.asc()).first()
        if not est or not est.slug:
            raise RuntimeError("No Estabelecimento with slug found in DB")

        svc = s.query(Service).filter(Service.estabelecimento_id == est.id).order_by(Service.id.asc()).first()
        if not svc:
            raise RuntimeError("No Service found for establishment")

        prof = (
            s.query(Funcionario)
            .filter(Funcionario.estabelecimento_id == est.id)
            .order_by(Funcionario.id.asc())
            .first()
        )
        if not prof:
            raise RuntimeError("No Funcionario found for establishment")

        return str(est.slug), int(svc.id)
    finally:
        s.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate a WhatsApp share link to open a booking calendar .ics on mobile.")
    ap.add_argument("--api-base-url", default="http://127.0.0.1:8000", help="Local backend base URL")
    ap.add_argument("--public-base-url", required=True, help="Public base URL (e.g. ngrok https URL)")
    ap.add_argument("--days-ahead", type=int, default=4)
    ap.add_argument("--timeout", type=float, default=10.0)
    args = ap.parse_args()

    api_base = str(args.api_base_url).rstrip("/")
    public_base = str(args.public_base_url).rstrip("/")

    # sanity
    r = requests.get(f"{api_base}/openapi.json", timeout=args.timeout)
    r.raise_for_status()

    slug, service_id = _pick_demo_booking_target()

    from datetime import date, timedelta

    target_date = (date.today() + timedelta(days=int(args.days_ahead))).isoformat()

    r = requests.get(
        f"{api_base}/availability",
        params={"date": target_date, "service_id": service_id, "slug": slug},
        timeout=args.timeout,
    )
    r.raise_for_status()
    body = r.json()
    if body.get("ok") is not True:
        raise RuntimeError(f"availability not ok: {body}")

    chosen_prof_id = None
    chosen_start_time = None
    for it in body.get("availability") or []:
        slots = it.get("slots") or []
        if slots:
            chosen_prof_id = int(it.get("professional_id"))
            chosen_start_time = str(slots[0])
            break
    if not chosen_prof_id or not chosen_start_time:
        raise RuntimeError("No bookable slot found")

    customer_whatsapp = f"+34999{int(time.time()) % 1000000:06d}"
    payload = {
        "service_id": service_id,
        "professional_id": chosen_prof_id,
        "date": target_date,
        "start_time": chosen_start_time,
        "channel": "booking_public",
        "customer_name": "WA Calendar Test",
        "customer_whatsapp": customer_whatsapp,
    }

    r = requests.post(
        f"{api_base}/appointments",
        params={"slug": slug},
        json=payload,
        timeout=args.timeout,
    )
    r.raise_for_status()
    body = r.json()
    if body.get("ok") is not True:
        raise RuntimeError(f"appointments not ok: {body}")

    cal_url = body.get("calendar_url")
    if not isinstance(cal_url, str) or "calendar.ics" not in cal_url:
        raise RuntimeError(f"Missing calendar_url in response: {body}")

    calendar_public = cal_url if not cal_url.startswith("/") else (public_base + cal_url)

    text = f"Adicionar ao calendário: {calendar_public}"
    wa_link = "https://wa.me/?text=" + urllib.parse.quote(text)

    print("[OK] WhatsApp calendar link generated")
    print(f"- public_base_url: {public_base}")
    print(f"- calendar_url: {calendar_public}")
    print(f"- whatsapp_link: {wa_link}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
