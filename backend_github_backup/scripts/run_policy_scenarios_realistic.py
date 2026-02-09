"""Run realistic booking/availability scenarios in the terminal.

This script is meant for product/policy validation. It uses the same core logic
as /availability, but lets you simulate different 'now' times deterministically.

What it covers:
- Cutoffs (morning prev-day 20:00, afternoon same-day 12:00, night same-day 16:00)
- Confirmation window rules (immediate window hours, minConfirmWindowHours, capBeforeStartHours)
- Business lunch break (breakStart/breakEnd)
- Professional-specific break (team.perProfessional[*].breakStart/breakEnd)
- Professional work window and work days (team.perProfessional[*].startTime/endTime/workDays)

Usage:
  cd Backend
  C:/dev/easya-agenda_clean_2026-01-20/.venv/Scripts/python.exe -m scripts.run_policy_scenarios_realistic --slug demo-est --date 2026-02-02

Optional:
  --now 2026-02-01T19:00 --now 2026-02-01T21:00 --now 2026-02-02T10:00

Notes:
- This script does not call the HTTP endpoint; it runs the same logic directly.
- The policy is read from SetupProfile.payload; the script can optionally inject
  a temporary scenario payload (no DB write) for testing.
"""

from __future__ import annotations

import argparse
import copy
import os
import sys
from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

# Allow running as: python scripts/run_policy_scenarios_realistic.py
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.db.database import SessionLocal
from app.models.models import Estabelecimento, SetupProfile, Service, Funcionario, Agendamento

from app.api.booking import routes as booking_routes


def _parse_dt_local(v: str) -> datetime:
    s = (v or "").strip()
    if not s:
        raise ValueError("empty datetime")
    if len(s) == 16 and "T" in s:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M")
    return datetime.fromisoformat(s)


def _deep_merge(base: dict, patch: dict) -> dict:
    out = dict(base)
    for k, v in (patch or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _get_tz(payload: dict) -> ZoneInfo | None:
    if ZoneInfo is None:
        return None
    business = payload.get("business") if isinstance(payload.get("business"), dict) else {}
    tz_name = str(business.get("timezone") or payload.get("timezone") or "America/Sao_Paulo")
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("America/Sao_Paulo")


def _build_temp_scenario_payload(existing: dict, prof: Funcionario) -> dict:
    """Inject a realistic day setup without writing to DB."""
    existing = existing if isinstance(existing, dict) else {}

    prof_name = str(getattr(prof, "nome", "") or "Prof")

    confirmation = {
        # Cutoffs+guardrails v2
        "cutoffsEnabled": True,
        "morningEndTime": "12:00",
        "afternoonEndTime": "17:00",
        "morningCutoffPrevDay": "20:00",
        "afternoonCutoffSameDay": "12:00",
        "nightCutoffSameDay": "16:00",
        # Confirmation window
        "minLeadHours": 0,
        "immediateHorizonHours": 36,
        "immediateWindowHours": 4,
        "minConfirmWindowHours": 2,
        "capBeforeStartHours": 2,
        # Quiet hours ON for realism
        "quietHoursStart": "21:00",
        "quietHoursEnd": "08:00",
        "tomorrowAfterQuietMinTime": "14:00",
        "nightSendTime": "08:00",
        "nightConfirmDeadline": "12:00",
        "sendTimePrevDay": "17:00",
        "capDeadlinePrevDay": "20:00",
        "hysteresisStepMinutes": 15,
    }

    patch = {
        "business": {
            # A normal day with a lunch break
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
            # broken hours represented via break
            "breakStart": "12:00",
            "breakEnd": "14:00",
            "endOfShiftGraceMinutes": 10,
            "confirmation": confirmation,
        },
        "team": {
            "perProfessional": {
                prof_name: {
                    # Professional works the whole day but has a short break
                    "workDays": {
                        "monday": True,
                        "tuesday": True,
                        "wednesday": True,
                        "thursday": True,
                        "friday": True,
                        "saturday": True,
                        "sunday": True,
                    },
                    "startTime": "09:00",
                    "endTime": "18:00",
                    "breakStart": "15:30",
                    "breakEnd": "16:00",
                    "endOfShiftGraceMinutes": 10,
                }
            }
        },
    }

    return _deep_merge(existing, patch)


def _apply_scenario(payload: dict, *, scenario: str, prof: Funcionario) -> dict:
    """Apply additional scenario tweaks on top of the base injected payload."""
    payload = payload if isinstance(payload, dict) else {}
    biz = payload.get("business") if isinstance(payload.get("business"), dict) else {}
    opening_hours = biz.get("openingHours") if isinstance(biz.get("openingHours"), dict) else {}

    team = payload.get("team") if isinstance(payload.get("team"), dict) else {}
    per = team.get("perProfessional") if isinstance(team.get("perProfessional"), dict) else {}
    prof_name = str(getattr(prof, "nome", "") or "Prof")
    pentry = per.get(prof_name) if isinstance(per.get(prof_name), dict) else {}

    scenario = str(scenario or "").strip().lower()
    if scenario in ["lunch", "lunch-break", "default", ""]:
        return payload

    if scenario in ["broken-hours", "broken", "quebrado", "horario-quebrado"]:
        # Business: multiple windows in the day
        opening_hours["monday"] = {
            "active": True,
            "windows": [
                {"open": "09:00", "close": "11:40"},
                {"open": "13:10", "close": "16:20"},
                {"open": "17:20", "close": "19:00"},
            ],
        }

        # Tiny business break inside the gap to also exercise break parsing
        biz["breakStart"] = "11:40"
        biz["breakEnd"] = "12:10"

        # Professional: also broken, but slightly different inside business windows
        pentry["windows"] = [
            {"startTime": "09:10", "endTime": "11:40"},
            {"startTime": "13:30", "endTime": "16:00"},
            {"startTime": "17:20", "endTime": "18:40"},
        ]
        pentry["breakStart"] = "15:05"
        pentry["breakEnd"] = "15:25"

        per[prof_name] = pentry
        team["perProfessional"] = per
        payload["team"] = team

        biz["openingHours"] = opening_hours
        payload["business"] = biz
        return payload

    return payload


def _compute_slots_for_prof(
    *,
    db,
    est: Estabelecimento,
    prof: Funcionario,
    service: Service,
    setup_payload: dict,
    target_date: str,
    now_local: datetime,
    tz: ZoneInfo | None,
) -> tuple[list[str], dict]:
    confirmation_policy = booking_routes._extract_confirmation_policy(setup_payload)

    target_date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
    biz_windows, closed_reason = booking_routes._business_day_windows(est, target_date_obj, setup_payload)
    if closed_reason is not None or not biz_windows:
        return [], {"closed_reason": closed_reason}

    weekday_key = booking_routes._weekday_key_monday_first(target_date_obj)

    prof_workdays = booking_routes._extract_prof_workdays(setup_payload)
    prof_windows_multi = booking_routes._extract_prof_day_windows_multi(setup_payload)

    # Respect professional workday config
    try:
        pname_key = booking_routes._normalize_name_key(getattr(prof, "nome", ""))
        wd = prof_workdays.get(pname_key)
        if isinstance(wd, dict) and weekday_key in wd and not bool(wd.get(weekday_key)):
            return []
    except Exception:
        pass

    # Work windows (business windows default)
    windows = biz_windows
    try:
        pname = booking_routes._normalize_name_key(getattr(prof, "nome", ""))
        pw = prof_windows_multi.get(pname)
        if pw:
            windows = booking_routes._intersect_windows(pw, biz_windows)
    except Exception:
        windows = biz_windows

    interval = service.display_interval_min or 30
    duration_total = int(service.duration_min + (service.buffer_min or 0))
    grace_min = booking_routes._extract_end_of_shift_grace_minutes(setup_payload, prof=prof)

    base_slots = booking_routes._generate_time_slots_for_windows(windows, interval)

    # breaks
    break_start_t, break_end_t = booking_routes._extract_break_window(setup_payload)
    break_start_dt = datetime.combine(target_date_obj, break_start_t) if break_start_t and break_end_t else None
    break_end_dt = datetime.combine(target_date_obj, break_end_t) if break_start_t and break_end_t else None

    biz_break_start_dt = break_start_dt
    biz_break_end_dt = break_end_dt

    prof_break_start_dt = None
    prof_break_end_dt = None
    pbs_t, pbe_t = booking_routes._extract_break_window_for_prof(setup_payload, prof)
    if pbs_t and pbe_t:
        prof_break_start_dt = datetime.combine(target_date_obj, pbs_t)
        prof_break_end_dt = datetime.combine(target_date_obj, pbe_t)

    # existing appointments (real DB)
    day_start = datetime.combine(target_date_obj, booking_routes.dt_time.min)
    day_end = datetime.combine(target_date_obj, booking_routes.dt_time.max)
    ags = (
        db.query(Agendamento)
        .filter(
            Agendamento.funcionario_id == prof.id,
            Agendamento.data_hora >= day_start,
            Agendamento.data_hora <= day_end,
        )
        .all()
    )

    stats = {
        "candidate_count": len(base_slots),
        "excluded": {},
        "excluded_samples": {},
    }

    def _exclude(reason: str, slot: str) -> None:
        stats["excluded"][reason] = int(stats["excluded"].get(reason, 0)) + 1
        smp = stats["excluded_samples"].get(reason) or []
        if len(smp) < 4:
            smp.append(slot)
        stats["excluded_samples"][reason] = smp

    free_slots: list[str] = []
    last_added: datetime | None = None

    for s in base_slots:
        start_dt = datetime.strptime(f"{target_date} {s}", "%Y-%m-%d %H:%M")
        end_dt = start_dt + timedelta(minutes=duration_total)

        start_local = start_dt.replace(tzinfo=tz) if tz else start_dt

        # Confirmation/cutoff filter
        if not booking_routes._slot_passes_confirmation_filter(
            now_local=now_local,
            slot_start_local=start_local,
            policy=confirmation_policy,
        ):
            _exclude("confirmation", s)
            continue

        # shift end limit (per window; grace applies only to last window)
        end_limit = booking_routes._slot_end_limit_for_windows(
            day=target_date_obj,
            windows=windows,
            start_dt=start_dt,
            grace_min=grace_min,
        )
        if end_limit is None or end_dt > end_limit:
            _exclude("end_limit", s)
            continue

        # breaks overlap
        if biz_break_start_dt and biz_break_end_dt and biz_break_start_dt < biz_break_end_dt:
            if not (end_dt <= biz_break_start_dt or start_dt >= biz_break_end_dt):
                _exclude("biz_break", s)
                continue
        if prof_break_start_dt and prof_break_end_dt and prof_break_start_dt < prof_break_end_dt:
            if not (end_dt <= prof_break_start_dt or start_dt >= prof_break_end_dt):
                _exclude("prof_break", s)
                continue

        # spacing
        if last_added and start_dt < (last_added + timedelta(minutes=duration_total)):
            _exclude("spacing", s)
            continue

        conflict = False
        for ag in ags:
            if ag.service:
                dur = int(ag.service.duration_min + (ag.service.buffer_min or 0))
            else:
                dur = 60
            ex_start = ag.data_hora
            ex_end = ex_start + timedelta(minutes=dur)
            if not (end_dt <= ex_start or start_dt >= ex_end):
                conflict = True
                break

        if not conflict:
            free_slots.append(s)
            last_added = start_dt
        else:
            _exclude("conflict", s)

    return free_slots, stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", default="demo-est")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--now", action="append", default=[], help="Local datetime, e.g. 2026-02-01T19:00")
    ap.add_argument("--no-inject", action="store_true", help="Use DB payload as-is (do not inject scenario patch)")
    ap.add_argument("--scenario", default="lunch", choices=["lunch", "broken-hours"], help="Scenario preset")
    ap.add_argument("--explain", action="store_true", help="Print why slots were excluded (filters)")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        est = db.query(Estabelecimento).filter_by(slug=str(args.slug)).first()
        if not est:
            raise SystemExit(f"estabelecimento not found for slug={args.slug}")

        svc = db.query(Service).filter(Service.estabelecimento_id == est.id).order_by(Service.id.asc()).first()
        if not svc:
            raise SystemExit("no service found")

        prof = db.query(Funcionario).filter(Funcionario.estabelecimento_id == est.id).order_by(Funcionario.id.asc()).first()
        if not prof:
            raise SystemExit("no professional found")

        sp = db.query(SetupProfile).filter_by(estabelecimento_id=est.id).first()
        payload_db = copy.deepcopy(sp.payload) if sp and isinstance(sp.payload, dict) else {}

        payload = payload_db if args.no_inject else _build_temp_scenario_payload(payload_db, prof)
        if not args.no_inject:
            payload = _apply_scenario(payload, scenario=str(args.scenario), prof=prof)
        tz = _get_tz(payload)

        if not args.now:
            # Default timeline around the cutoffs
            args.now = [
                # previous day (messy times)
                "2026-02-01T19:07",
                "2026-02-01T20:03",
                "2026-02-01T21:11",
                # same day (off-grid times)
                "2026-02-02T02:13",
                "2026-02-02T10:07",
                "2026-02-02T11:37",
                "2026-02-02T13:12",
                "2026-02-02T15:53",
            ]

        if args.scenario == "broken-hours":
            print("Scenario: broken business hours (multi windows) + prof broken windows + small breaks")
        else:
            print("Scenario: lunch break 12:00-14:00 + prof break 15:30-16:00")
        print("Policy: cutoffsEnabled=True, minConfirmWindowHours=2, capBeforeStartHours=2")
        print("Cutoffs: morning(prev day)=20:00, afternoon(same day)=12:00, night(same day)=16:00")
        print("Date:", args.date, "Slug:", args.slug)
        print("Service:", f"{svc.id} ({svc.duration_min}+{svc.buffer_min or 0}min)")
        print("Professional:", f"{prof.id} ({prof.nome})")
        print("TZ:", str(tz) if tz else None)
        print("---")

        for now_s in args.now:
            now_local = _parse_dt_local(now_s)
            if tz and now_local.tzinfo is None:
                now_local = now_local.replace(tzinfo=tz)

            slots, stats = _compute_slots_for_prof(
                db=db,
                est=est,
                prof=prof,
                service=svc,
                setup_payload=payload,
                target_date=args.date,
                now_local=now_local,
                tz=tz,
            )

            head = slots[:10]
            tail = slots[-5:] if len(slots) > 10 else []
            print(f"now={now_local.isoformat()} -> {len(slots)} slots")
            if head:
                print("  first:", ", ".join(head))
            if tail:
                print("  last:", ", ".join(tail))

            if args.explain and isinstance(stats, dict):
                excluded = stats.get("excluded") or {}
                if excluded:
                    order = ["confirmation", "end_limit", "biz_break", "prof_break", "spacing", "conflict"]
                    parts = []
                    for k in order:
                        if k in excluded:
                            parts.append(f"{k}={excluded[k]}")
                    if parts:
                        print("  excluded:", "; ".join(parts))
                    samples = stats.get("excluded_samples") or {}
                    for k in order:
                        smp = samples.get(k)
                        if smp:
                            print(f"    {k} samples: {', '.join(smp)}")

        print("---")
        print("Tip: try a specific slot with detailed output:")
        print("  C:/dev/easya-agenda_clean_2026-01-20/.venv/Scripts/python.exe -m scripts.simulate_booking_policy --slug", args.slug, "--now 2026-02-02T10:00 --slot 2026-02-02T13:00")

    finally:
        db.close()


if __name__ == "__main__":
    main()
