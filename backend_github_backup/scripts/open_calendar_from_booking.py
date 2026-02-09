import argparse
import os
import subprocess
import tempfile
import time
from datetime import date, timedelta

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

        # Ensure at least one professional exists for that establishment (availability depends on it).
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
    ap = argparse.ArgumentParser(
        description="Create a public appointment, download its .ics calendar file, and optionally open it (Windows)."
    )
    ap.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend base URL")
    ap.add_argument("--days-ahead", type=int, default=4, help="How many days ahead to book")
    ap.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout seconds")
    ap.add_argument(
        "--out",
        default="",
        help="Output .ics file path. If omitted, uses a temp file.",
    )
    ap.add_argument(
        "--open",
        action="store_true",
        help="Open the downloaded .ics file with the OS default calendar app.",
    )
    args = ap.parse_args()

    base = str(args.base_url).rstrip("/")

    # Quick reachability check
    r = requests.get(f"{base}/openapi.json", timeout=args.timeout)
    r.raise_for_status()

    slug, service_id = _pick_demo_booking_target()
    target_date = (date.today() + timedelta(days=int(args.days_ahead))).isoformat()

    # Find any bookable slot
    r = requests.get(
        f"{base}/availability",
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
        "customer_name": "Calendar PC Test",
        "customer_whatsapp": customer_whatsapp,
    }

    r = requests.post(
        f"{base}/appointments",
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

    cal_full = cal_url if not cal_url.startswith("/") else (base + cal_url)

    r = requests.get(cal_full, timeout=args.timeout)
    r.raise_for_status()
    ics_text = r.text or ""

    if "BEGIN:VCALENDAR" not in ics_text:
        raise RuntimeError("Downloaded file does not look like an .ics calendar")

    out_path = str(args.out or "").strip()
    if not out_path:
        fd, out_path = tempfile.mkstemp(prefix="easya-", suffix=".ics")
        os.close(fd)

    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(ics_text)

    print("[OK] .ics downloaded")
    print(f"- file: {out_path}")
    print(f"- url: {cal_full}")
    print(f"- slug: {slug}")
    print(f"- service_id: {service_id}")
    print(f"- professional_id: {chosen_prof_id}")
    print(f"- date: {target_date}")
    print(f"- start_time: {chosen_start_time}")

    if args.open:
        try:
            os.startfile(out_path)  # type: ignore[attr-defined]
            print("[OK] Opened .ics with default app")
            try:
                subprocess.run(["explorer", "/select,", out_path], check=False)
            except Exception:
                pass
            print("[NEXT] Novo Outlook: o jeito mais confiável é importar o arquivo no Calendário.")
            print("[NEXT] Calendário → Adicionar calendário → Carregar de arquivo → selecione o .ics")
            print("[NEXT] Depois disso, o evento aparece com lembrete configurado.")
            print("[NOTE] O lembrete não aparece na hora — ele vai tocar no horário do alarme configurado no evento.")
            print("[DOC] Veja também: Backend/scripts/README_CALENDAR_TEST.md")
        except Exception as e:
            print(f"[WARN] Could not auto-open file: {e}")
            print("You can open it manually by double-clicking the file path above.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
