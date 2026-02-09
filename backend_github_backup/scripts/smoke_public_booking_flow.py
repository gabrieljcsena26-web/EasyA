import argparse
import sys
import time
from datetime import date, datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

import requests

from app.db.database import SessionLocal
from app.models.models import Estabelecimento, Funcionario, Service


def _fail(msg: str, code: int) -> int:
    print(f"[SMOKE][FAIL] {msg}")
    return code


def main() -> int:
    ap = argparse.ArgumentParser(description="Smoke test: public booking flow (availability -> appointment -> calendar .ics).")
    ap.add_argument("--base-url", default="http://127.0.0.1:8001", help="Backend base URL")
    ap.add_argument("--slug", default="", help="Optional establishment slug override")
    ap.add_argument("--days-ahead", type=int, default=4, help="First day offset to try (today + N)")
    ap.add_argument(
        "--max-tries",
        type=int,
        default=14,
        help="How many consecutive days to try until finding a bookable slot",
    )
    ap.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout seconds")
    args = ap.parse_args()

    base = str(args.base_url).rstrip("/")

    # 1) Basic reachability
    try:
        r = requests.get(f"{base}/openapi.json", timeout=args.timeout)
    except Exception as e:
        return _fail(f"Cannot reach backend at {base}: {e}", 10)
    if r.status_code != 200:
        return _fail(f"/openapi.json returned {r.status_code}: {r.text[:400]}", 11)

    # 2) Read public config first (anchors today/now in establishment timezone)
    try:
        r = requests.get(
            f"{base}/config",
            params={"slug": str(args.slug).strip() or None},
            timeout=args.timeout,
        )
    except Exception as e:
        return _fail(f"GET /config failed: {e}", 12)

    if r.status_code != 200:
        return _fail(f"GET /config returned {r.status_code}: {r.text[:600]}", 13)

    config_body = r.json() or {}
    business = (config_body.get("business") or {}) if isinstance(config_body.get("business"), dict) else {}
    cfg_slug = str(business.get("slug") or "").strip()
    cfg_tz = str(business.get("timezone") or "").strip()
    cfg_today_local = str(business.get("today_local") or "").strip()
    cfg_now_local_iso = str(business.get("now_local_iso") or "").strip()
    cfg_h_inicio = business.get("horario_inicio")
    cfg_h_fim = business.get("horario_fim")

    if str(args.slug or "").strip() and cfg_slug and cfg_slug != str(args.slug).strip():
        return _fail(f"/config returned unexpected slug={cfg_slug!r} (requested {args.slug!r})", 14)

    if not cfg_today_local or not cfg_now_local_iso:
        return _fail(f"/config missing today_local/now_local_iso: {business}", 15)

    try:
        now_local = datetime.fromisoformat(cfg_now_local_iso)
    except Exception as e:
        return _fail(f"Cannot parse business.now_local_iso={cfg_now_local_iso!r}: {e}", 16)

    # 3) Select demo entities from DB (ensures we test the public endpoints, but without relying on auth-only listing routes)
    s = SessionLocal()
    try:
        est_q = s.query(Estabelecimento)
        if str(args.slug or "").strip():
            est_q = est_q.filter(Estabelecimento.slug == str(args.slug).strip())
        est = est_q.order_by(Estabelecimento.id.asc()).first()
        if not est:
            return _fail(
                f"No Estabelecimento found in DB" + (f" for slug={args.slug!r}" if args.slug else ""),
                20,
            )

        svc = s.query(Service).filter(Service.estabelecimento_id == est.id).order_by(Service.id.asc()).first()
        if not svc:
            return _fail("No Service found for establishment", 21)

        # Ensure we have at least one professional under this establishment
        prof_any = (
            s.query(Funcionario)
            .filter(Funcionario.estabelecimento_id == est.id)
            .order_by(Funcionario.id.asc())
            .first()
        )
        if not prof_any:
            return _fail("No Funcionario found for establishment", 22)

        slug = str(est.slug)
        service_id = int(svc.id)
        service_duration_min = int(svc.duration_min or 0)
        service_buffer_min = int(svc.buffer_min or 0)
    finally:
        s.close()

    # 4) Availability (scan a range of days until we find a slot)
    chosen_prof_id = None
    chosen_start_time = None
    target_date = None

    tries = max(1, int(args.max_tries or 1))
    start_offset = int(args.days_ahead or 0)

    last_avail_body = None
    base_date = None
    try:
        base_date = date.fromisoformat(cfg_today_local)
    except Exception:
        base_date = date.today()

    for i in range(tries):
        d = (base_date + timedelta(days=start_offset + i)).isoformat()
        try:
            r = requests.get(
                f"{base}/availability",
                params={"date": d, "service_id": service_id, "slug": slug},
                timeout=args.timeout,
            )
        except Exception as e:
            return _fail(f"GET /availability failed: {e}", 30)

        if r.status_code != 200:
            return _fail(f"GET /availability returned {r.status_code}: {r.text[:600]}", 31)

        body = r.json()
        last_avail_body = body
        if body.get("ok") is not True:
            return _fail(f"GET /availability returned ok!=true: {body}", 32)

        for it in body.get("availability") or []:
            slots = it.get("slots") or []
            if slots:
                chosen_prof_id = int(it.get("professional_id"))
                chosen_start_time = str(slots[0])
                target_date = d
                break

        if chosen_prof_id and chosen_start_time and target_date:
            break

    if not chosen_prof_id or not chosen_start_time or not target_date:
        return _fail(
            f"No bookable slot found for slug={slug} service_id={service_id} in {tries} tries starting at today+{start_offset}. "
            f"Last availability response: {str(last_avail_body)[:800]}",
            33,
        )

    # Validate the chosen slot is sane: within business hours and not in the past vs now_local.
    try:
        slot_dt_naive = datetime.strptime(f"{target_date} {chosen_start_time}", "%Y-%m-%d %H:%M")

        # Basic opening-hours check (if present on /config)
        if isinstance(cfg_h_inicio, int) and isinstance(cfg_h_fim, int):
            start_minutes = slot_dt_naive.hour * 60 + slot_dt_naive.minute
            open_minutes = int(cfg_h_inicio) * 60
            close_minutes = int(cfg_h_fim) * 60

            duration_total = (service_duration_min + service_buffer_min) * 60
            end_minutes = start_minutes * 60 + duration_total
            if start_minutes < open_minutes:
                return _fail(
                    f"Chosen slot is before business opens: {chosen_start_time} < {cfg_h_inicio:02d}:00",
                    34,
                )
            if end_minutes > close_minutes * 60:
                return _fail(
                    f"Chosen slot exceeds business closing time: start={chosen_start_time} duration+buffer={service_duration_min}+{service_buffer_min}min closing={cfg_h_fim:02d}:00",
                    35,
                )

        # If timezone is available, compare in that tz. If not, compare naive dates.
        if ZoneInfo is not None and cfg_tz:
            tzinfo = ZoneInfo(cfg_tz)
            slot_local = slot_dt_naive.replace(tzinfo=tzinfo)
            if slot_local <= now_local.astimezone(tzinfo):
                return _fail(
                    f"Chosen slot is not in the future (business tz): now={now_local.isoformat()} slot={slot_local.isoformat()} tz={cfg_tz}",
                    36,
                )
        else:
            if slot_dt_naive <= now_local.replace(tzinfo=None):
                return _fail(
                    f"Chosen slot is not in the future: now={now_local.isoformat()} slot={slot_dt_naive.isoformat()}",
                    37,
                )
    except Exception as e:
        return _fail(f"Slot sanity validation failed: {e}", 38)

    # 5) Create appointment
    customer_whatsapp = f"+34999{int(time.time()) % 1000000:06d}"
    payload = {
        "service_id": service_id,
        "professional_id": chosen_prof_id,
        "date": target_date,
        "start_time": chosen_start_time,
        "channel": "booking_public",
        "customer_name": "Smoke Test",
        "customer_whatsapp": customer_whatsapp,
    }

    try:
        r = requests.post(
            f"{base}/appointments",
            params={"slug": slug},
            json=payload,
            timeout=args.timeout,
        )
    except Exception as e:
        return _fail(f"POST /appointments failed: {e}", 40)

    if r.status_code != 200:
        return _fail(f"POST /appointments returned {r.status_code}: {r.text[:800]}", 41)

    body = r.json()
    if body.get("ok") is not True:
        return _fail(f"POST /appointments returned ok!=true: {body}", 42)

    appt = body.get("appointment") or {}
    appt_id = appt.get("id")
    cal_url = body.get("calendar_url")
    if not appt_id or not isinstance(cal_url, str) or "calendar.ics" not in cal_url:
        return _fail(f"Missing appointment id or calendar_url: {body}", 43)

    if cal_url.startswith("/"):
        cal_full = base + cal_url
    else:
        cal_full = cal_url

    # 6) Download calendar
    try:
        r = requests.get(cal_full, timeout=args.timeout)
    except Exception as e:
        return _fail(f"GET calendar.ics failed: {e}", 50)

    if r.status_code != 200:
        return _fail(f"GET calendar.ics returned {r.status_code}: {r.text[:400]}", 51)

    txt = r.text or ""
    if "BEGIN:VCALENDAR" not in txt or "BEGIN:VEVENT" not in txt:
        return _fail("calendar.ics content does not look like an iCalendar file", 52)

    # Reminder/alarm presence (calendar should include a VALARM trigger for confirmation/reminder)
    if "BEGIN:VALARM" not in txt or "TRIGGER" not in txt:
        return _fail("calendar.ics missing VALARM/TRIGGER (reminder/alarm)", 56)

    # Basic field validation for timezone correctness (DTSTART/DTEND may be UTC or TZID-based)
    dtstart_line = None
    dtend_line = None
    summary_line = None
    for line in txt.splitlines():
        if dtstart_line is None and line.startswith("DTSTART"):
            dtstart_line = line
        if dtend_line is None and line.startswith("DTEND"):
            dtend_line = line
        if summary_line is None and line.startswith("SUMMARY"):
            summary_line = line
        if dtstart_line and dtend_line and summary_line:
            break

    if not dtstart_line or not dtend_line or not summary_line:
        return _fail(
            f"calendar.ics missing required fields (DTSTART/DTEND/SUMMARY). "
            f"Found DTSTART={bool(dtstart_line)} DTEND={bool(dtend_line)} SUMMARY={bool(summary_line)}",
            53,
        )

    # If DTSTART is UTC (ends with Z), verify the conversion matches the chosen local slot.
    # This catches regressions where the backend timezone is wrong (e.g. defaulting to BR).
    try:
        if ZoneInfo is not None and dtstart_line.endswith("Z"):
            # Example: DTSTART:20260206T143000Z
            dtstart_raw = dtstart_line.split(":", 1)[1].strip()
            if dtstart_raw.endswith("Z"):
                dtstart_raw = dtstart_raw[:-1]
            ics_utc = datetime.strptime(dtstart_raw, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)

            # Establishment timezone from SetupProfile payload
            s = SessionLocal()
            try:
                est = s.query(Estabelecimento).filter(Estabelecimento.slug == slug).first()
                sp = None
                if est:
                    from app.models.models import SetupProfile
                    sp = s.query(SetupProfile).filter(SetupProfile.estabelecimento_id == est.id).first()
                payload = sp.payload if sp and isinstance(sp.payload, dict) else {}
            finally:
                s.close()

            business = payload.get("business") if isinstance(payload.get("business"), dict) else {}
            tz_name = str(business.get("timezone") or payload.get("timezone") or "UTC")
            tzinfo = ZoneInfo(tz_name)

            local_dt = datetime.strptime(f"{target_date} {chosen_start_time}", "%Y-%m-%d %H:%M").replace(tzinfo=tzinfo)
            expected_utc = local_dt.astimezone(timezone.utc)

            delta = abs((ics_utc - expected_utc).total_seconds())
            if delta > 60:
                return _fail(
                    f"ICS DTSTART UTC mismatch. tz={tz_name} local={local_dt.isoformat()} expected_utc={expected_utc.isoformat()} got_ics_utc={ics_utc.isoformat()} delta_s={int(delta)}",
                    54,
                )
    except Exception as e:
        return _fail(f"ICS timezone assertion failed: {e}", 55)

    print("[SMOKE][OK] Public booking flow works")
    print(f"- base_url: {base}")
    print(f"- slug: {slug}")
    print(f"- service_id: {service_id}")
    print(f"- professional_id: {chosen_prof_id}")
    print(f"- date: {target_date}")
    print(f"- start_time: {chosen_start_time}")
    print(f"- appointment_id: {appt_id}")
    print(f"- calendar_url: {cal_url}")
    print(f"- ics_dtstart: {dtstart_line}")
    print(f"- ics_dtend: {dtend_line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
