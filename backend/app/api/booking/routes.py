import math
import os
from datetime import datetime, timedelta, time as dt_time, timezone

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_access_token
from app.core.locale import resolve_lang, resolve_timezone
from app.core.trial import compute_trial_status, ensure_trial_started
from app.db.database import get_db
from app.models.models import Estabelecimento, Funcionario, Cliente, Agendamento, Service, SetupProfile
from app.schemas.schemas import (
    ConfigOut,
    ServiceOut,
    ProfessionalOut,
    BookingDepositRuleOut,
    AppointmentOut,
    AppointmentCreate,
    EstabelecimentoOut,
)

router = APIRouter(tags=["booking"])


def _trial_raise_expired(*, status) -> None:
    end_iso = None
    try:
        end_iso = status.end_utc.isoformat() if status and status.end_utc else None
    except Exception:
        end_iso = None
    raise HTTPException(
        status_code=402,
        detail={
            "code": "TRIAL_EXPIRED",
            "message": "Trial expired. Choose a plan to continue.",
            "trial_end_utc": end_iso,
        },
    )


def _public_api_base_url() -> str:
    base = (
        os.getenv("API_PUBLIC_BASE_URL")
        or os.getenv("BACKEND_PUBLIC_BASE_URL")
        or os.getenv("PUBLIC_BASE_URL")
        or ""
    )
    base = str(base).strip().rstrip("/")
    return base


def _booking_base_url() -> str:
    base = (
        os.getenv("BOOKING_PUBLIC_BASE_URL")
        or os.getenv("FRONTEND_BASE_URL")
        or os.getenv("PUBLIC_BASE_URL")
        or "http://localhost:3002"
    )
    base = str(base).strip().rstrip("/")
    return base or "http://localhost:3002"


def _booking_link_for_slug(slug: str) -> str:
    s = str(slug or "").strip()
    if not s:
        return _booking_base_url()
    return f"{_booking_base_url()}/booking/{s}"


def _normalize_name_key(name: str) -> str:
    return " ".join(str(name or "").strip().lower().split())


def _is_counted_appointment_status(status: Optional[str]) -> bool:
    if not status:
        return True
    s = str(status).strip().lower()
    # excluir cancelados e no-show
    if "cancel" in s:
        return False
    if "no-show" in s or "noshow" in s:
        return False
    if "nao compare" in s or "não compare" in s:
        return False
    return True


def _extract_capacity(payload: Optional[dict]) -> tuple[Optional[int], dict]:
    """Extrai capacidade (clientes/dia) do SetupProfile JSON.

    Retorna (default_capacity, per_prof_by_normalized_name).
    """
    if not payload or not isinstance(payload, dict):
        return None, {}
    cap = payload.get("capacity")
    if not isinstance(cap, dict):
        return None, {}

    default_raw = cap.get("appointmentsPerDayDefault")
    default_val: Optional[int]
    try:
        default_val = int(default_raw)
        if default_val < 0:
            default_val = 0
    except Exception:
        default_val = None

    per = cap.get("perProfessional")
    out = {}
    if isinstance(per, dict):
        for k, v in per.items():
            nk = _normalize_name_key(k)
            if not nk:
                continue
            try:
                iv = int(v)
                if iv < 0:
                    iv = 0
                out[nk] = iv
            except Exception:
                continue

    return default_val, out


def _extract_open_days_and_holidays(payload: Optional[dict]) -> tuple[Optional[dict], set[str]]:
    if not payload or not isinstance(payload, dict):
        return None, set()
    biz = payload.get("business")
    if not isinstance(biz, dict):
        return None, set()
    open_days = biz.get("openDays")
    if not isinstance(open_days, dict):
        open_days = None
    holidays_raw = biz.get("holidays")
    holidays: set[str] = set()
    if isinstance(holidays_raw, list):
        for h in holidays_raw:
            hs = str(h).strip()
            if hs:
                holidays.add(hs)
    return open_days, holidays


def _extract_opening_hours(payload: Optional[dict]) -> Optional[dict]:
    if not payload or not isinstance(payload, dict):
        return None
    biz = payload.get("business")
    if not isinstance(biz, dict):
        return None
    oh = biz.get("openingHours") or biz.get("opening_hours")
    return oh if isinstance(oh, dict) else None


def _windows_from_list(
    windows,
    *,
    start_key: str,
    end_key: str,
    alt_start_key: Optional[str] = None,
    alt_end_key: Optional[str] = None,
) -> list[tuple[dt_time, dt_time]]:
    if not isinstance(windows, list):
        return []
    out: list[tuple[dt_time, dt_time]] = []
    for w in windows:
        if not isinstance(w, dict):
            continue
        st = _parse_hhmm(w.get(start_key))
        et = _parse_hhmm(w.get(end_key))
        if (st is None or et is None) and alt_start_key and alt_end_key:
            st = st or _parse_hhmm(w.get(alt_start_key))
            et = et or _parse_hhmm(w.get(alt_end_key))
        if not st or not et:
            continue
        if datetime.combine(datetime.today().date(), st) >= datetime.combine(datetime.today().date(), et):
            continue
        out.append((st, et))
    out.sort(key=lambda x: (x[0].hour, x[0].minute, x[1].hour, x[1].minute))
    return out


def _intersect_windows(
    a: list[tuple[dt_time, dt_time]],
    b: list[tuple[dt_time, dt_time]],
) -> list[tuple[dt_time, dt_time]]:
    if not a or not b:
        return []

    def _to_min(t: dt_time) -> int:
        return int(t.hour) * 60 + int(t.minute)

    out: list[tuple[dt_time, dt_time]] = []
    for a_start, a_end in a:
        a0 = _to_min(a_start)
        a1 = _to_min(a_end)
        for b_start, b_end in b:
            b0 = _to_min(b_start)
            b1 = _to_min(b_end)
            s0 = max(a0, b0)
            e0 = min(a1, b1)
            if s0 < e0:
                out.append((dt_time(hour=s0 // 60, minute=s0 % 60), dt_time(hour=e0 // 60, minute=e0 % 60)))
    out.sort(key=lambda x: (x[0].hour, x[0].minute, x[1].hour, x[1].minute))
    return out


def _slot_end_limit_for_windows(
    *,
    day,
    windows: list[tuple[dt_time, dt_time]],
    start_dt: datetime,
    grace_min: int,
) -> Optional[datetime]:
    """Return the window end datetime (plus grace if last window) for the window containing start_dt."""
    if not windows:
        return None
    for idx, (ws, we) in enumerate(windows):
        win_start = datetime.combine(day, ws)
        win_end = datetime.combine(day, we)
        if win_start <= start_dt < win_end:
            extra = int(grace_min or 0) if idx == (len(windows) - 1) else 0
            return win_end + timedelta(minutes=extra)
    return None


def _generate_time_slots_for_windows(
    windows: list[tuple[dt_time, dt_time]],
    interval_min: int,
) -> List[str]:
    out: List[str] = []
    for ws, we in windows:
        out.extend(_generate_time_slots(ws, we, interval_min))
    return out


def _parse_hhmm(v) -> Optional[dt_time]:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        if ":" in s:
            hh, mm = s.split(":", 1)
            h = int(hh)
            m = int(mm)
            if h < 0 or h > 23 or m < 0 or m > 59:
                return None
            return dt_time(hour=h, minute=m)
    except Exception:
        return None
    return None


def _extract_break_window(payload: Optional[dict]) -> tuple[Optional[dt_time], Optional[dt_time]]:
    """Return (break_start, break_end) or (None,None). Supports legacy breakStartHour/breakEndHour."""
    if not payload or not isinstance(payload, dict):
        return None, None
    biz = payload.get("business")
    if not isinstance(biz, dict):
        return None, None
    bs = biz.get("breakStart") or biz.get("break_start")
    be = biz.get("breakEnd") or biz.get("break_end")
    if bs is None and be is None:
        bs_h = biz.get("breakStartHour")
        be_h = biz.get("breakEndHour")
        try:
            bs_h = int(bs_h) if bs_h is not None else None
            be_h = int(be_h) if be_h is not None else None
        except Exception:
            bs_h = None
            be_h = None
        if bs_h is None or be_h is None:
            return None, None
        if bs_h == 0 and be_h == 0:
            return None, None
        if bs_h < 0 or bs_h > 23 or be_h < 0 or be_h > 23:
            return None, None
        return dt_time(hour=bs_h), dt_time(hour=be_h)

    start_t = _parse_hhmm(bs)
    end_t = _parse_hhmm(be)
    if not start_t or not end_t:
        return None, None
    return start_t, end_t


def _extract_break_window_for_prof(setup_payload: Optional[dict], prof) -> tuple[Optional[dt_time], Optional[dt_time]]:
    """Return (break_start, break_end) for a given professional.

    Reads from setup_payload.team.perProfessional keyed by professional name or id.
    Supports breakStart/breakEnd (HH:MM) and legacy breakStartHour/breakEndHour.
    """
    if not setup_payload or not isinstance(setup_payload, dict):
        return None, None

    team = setup_payload.get("team")
    if not isinstance(team, dict):
        return None, None

    per = team.get("perProfessional")
    if not isinstance(per, dict):
        return None, None

    keys: list[str] = []
    try:
        nm = getattr(prof, "nome", None)
        if nm is not None and str(nm).strip():
            keys.append(str(nm).strip())
    except Exception:
        pass
    try:
        pid = getattr(prof, "id", None)
        if pid is not None:
            keys.append(str(pid))
    except Exception:
        pass

    for k in keys:
        entry = per.get(k)
        if not isinstance(entry, dict):
            continue

        bs = entry.get("breakStart") or entry.get("break_start")
        be = entry.get("breakEnd") or entry.get("break_end")

        if bs is None and be is None:
            bs_h = entry.get("breakStartHour")
            be_h = entry.get("breakEndHour")
            try:
                bs_h = int(bs_h) if bs_h is not None else None
                be_h = int(be_h) if be_h is not None else None
            except Exception:
                bs_h = None
                be_h = None
            if bs_h is None or be_h is None:
                continue
            if bs_h == 0 and be_h == 0:
                continue
            if bs_h < 0 or bs_h > 23 or be_h < 0 or be_h > 23:
                continue
            return dt_time(hour=bs_h), dt_time(hour=be_h)

        start_t = _parse_hhmm(bs)
        end_t = _parse_hhmm(be)
        if not start_t or not end_t:
            continue
        return start_t, end_t

    return None, None


def _business_day_window(
    est: Estabelecimento,
    day,
    setup_payload: Optional[dict],
) -> tuple[Optional[dt_time], Optional[dt_time], Optional[str]]:
    """Return (start_time, end_time, closed_reason). If closed_reason is not None, day is closed."""

    windows, closed_reason = _business_day_windows(est, day, setup_payload)
    if closed_reason is not None or not windows:
        return None, None, closed_reason
    return windows[0][0], windows[-1][1], None


def _business_day_windows(
    est: Estabelecimento,
    day,
    setup_payload: Optional[dict],
) -> tuple[list[tuple[dt_time, dt_time]], Optional[str]]:
    """Return (windows, closed_reason).

    Supports either a single window (open/close) or multiple windows via:
      setup_payload.business.openingHours[weekday].windows = [{open, close}, ...]
    """
    weekday_key = _weekday_key_monday_first(day)
    open_days, holidays = _extract_open_days_and_holidays(setup_payload)
    opening_hours = _extract_opening_hours(setup_payload)

    if day.isoformat() in holidays:
        return [], "holiday"

    if open_days is not None and not bool(open_days.get(weekday_key, False)):
        return [], "weekday_closed"

    if opening_hours is not None:
        entry = opening_hours.get(weekday_key)
        if isinstance(entry, dict):
            if entry.get("active") is False:
                return [], "weekday_closed"

            # Multi-window (broken hours)
            windows = _windows_from_list(
                entry.get("windows"),
                start_key="open",
                end_key="close",
                alt_start_key="start",
                alt_end_key="end",
            )
            if windows:
                return windows, None

            # Single window
            start_t = _parse_hhmm(entry.get("open"))
            end_t = _parse_hhmm(entry.get("close"))
            if start_t and end_t:
                if datetime.combine(day, start_t) >= datetime.combine(day, end_t):
                    return [], "weekday_closed"
                return [(start_t, end_t)], None

    start_hour = getattr(est, "horario_inicio", 9)
    end_hour = getattr(est, "horario_fim", 18)
    try:
        start_hour = int(start_hour)
        end_hour = int(end_hour)
    except Exception:
        start_hour = 9
        end_hour = 18
    if start_hour < 0 or start_hour > 23 or end_hour < 0 or end_hour > 23:
        start_hour, end_hour = 9, 18
    if start_hour >= end_hour:
        return [], "weekday_closed"
    return [(dt_time(hour=start_hour), dt_time(hour=end_hour))], None


def _extract_prof_workdays(payload: Optional[dict]) -> dict:
    """Retorna map normalized_name -> workDays dict (monday..sunday -> bool)."""
    if not payload or not isinstance(payload, dict):
        return {}
    team = payload.get("team")
    if not isinstance(team, dict):
        return {}
    per = team.get("perProfessional")
    if not isinstance(per, dict):
        return {}
    out = {}
    for name, obj in per.items():
        nk = _normalize_name_key(name)
        if not nk or not isinstance(obj, dict):
            continue
        wd = obj.get("workDays")
        if isinstance(wd, dict):
            out[nk] = wd
    return out


def _extract_prof_day_windows(payload: Optional[dict]) -> dict:
    """Retorna map normalized_name -> (start_time, end_time) para cada profissional.

    Suporta:
    - startTime/endTime (HH:MM)
    - startHour/endHour (int)
    """
    if not payload or not isinstance(payload, dict):
        return {}
    team = payload.get("team")
    if not isinstance(team, dict):
        return {}
    per = team.get("perProfessional")
    if not isinstance(per, dict):
        return {}

    out: dict[str, tuple[dt_time, dt_time]] = {}
    for name, obj in per.items():
        nk = _normalize_name_key(name)
        if not nk or not isinstance(obj, dict):
            continue

        st = None
        et = None

        # Preferred HH:MM
        st_s = obj.get("startTime")
        et_s = obj.get("endTime")
        if st_s and et_s:
            st = _parse_hhmm(st_s)
            et = _parse_hhmm(et_s)

        # Legacy integer hours
        if (st is None or et is None):
            try:
                sh = obj.get("startHour")
                eh = obj.get("endHour")
                if sh is not None and eh is not None:
                    sh_i = int(sh)
                    eh_i = int(eh)
                    if 0 <= sh_i <= 23 and 0 <= eh_i <= 23:
                        st = st or dt_time(hour=sh_i)
                        et = et or dt_time(hour=eh_i)
            except Exception:
                pass

        if st and et:
            # guard against inverted windows
            if datetime.combine(datetime.today().date(), st) < datetime.combine(datetime.today().date(), et):
                out[nk] = (st, et)

    return out


def _extract_prof_day_windows_multi(payload: Optional[dict]) -> dict[str, list[tuple[dt_time, dt_time]]]:
    """Retorna map normalized_name -> [ (start_time, end_time), ... ]

    Suporta:
    - windows: [{startTime,endTime}] ou [{open,close}] (broken hours)
    - startTime/endTime (HH:MM)
    - startHour/endHour (int)
    """
    if not payload or not isinstance(payload, dict):
        return {}
    team = payload.get("team")
    if not isinstance(team, dict):
        return {}
    per = team.get("perProfessional")
    if not isinstance(per, dict):
        return {}

    out: dict[str, list[tuple[dt_time, dt_time]]] = {}
    for name, obj in per.items():
        nk = _normalize_name_key(name)
        if not nk or not isinstance(obj, dict):
            continue

        windows = _windows_from_list(
            obj.get("windows"),
            start_key="startTime",
            end_key="endTime",
            alt_start_key="open",
            alt_end_key="close",
        )
        if windows:
            out[nk] = windows
            continue

        # Fall back to legacy single window
        st = None
        et = None
        st_s = obj.get("startTime")
        et_s = obj.get("endTime")
        if st_s and et_s:
            st = _parse_hhmm(st_s)
            et = _parse_hhmm(et_s)

        if (st is None or et is None):
            try:
                sh = obj.get("startHour")
                eh = obj.get("endHour")
                if sh is not None and eh is not None:
                    sh_i = int(sh)
                    eh_i = int(eh)
                    if 0 <= sh_i <= 23 and 0 <= eh_i <= 23:
                        st = st or dt_time(hour=sh_i)
                        et = et or dt_time(hour=eh_i)
            except Exception:
                pass

        if st and et:
            if datetime.combine(datetime.today().date(), st) < datetime.combine(datetime.today().date(), et):
                out[nk] = [(st, et)]

    return out


def _per_professional_entry(setup_payload: Optional[dict], prof) -> Optional[dict]:
    if not setup_payload or not isinstance(setup_payload, dict):
        return None

    team = setup_payload.get("team")
    if not isinstance(team, dict):
        return None

    per = team.get("perProfessional")
    if not isinstance(per, dict):
        return None

    keys: list[str] = []
    try:
        nm = getattr(prof, "nome", None)
        if nm is not None and str(nm).strip():
            keys.append(str(nm).strip())
    except Exception:
        pass
    try:
        pid = getattr(prof, "id", None)
        if pid is not None:
            keys.append(str(pid))
    except Exception:
        pass

    for k in keys:
        entry = per.get(k)
        if isinstance(entry, dict):
            return entry
    return None


def _service_key_matches(service: Service, key) -> bool:
    if key is None:
        return False
    s = str(key).strip()
    if not s:
        return False

    # by id
    try:
        if int(s) == int(service.id):
            return True
    except Exception:
        pass

    # by name (normalized)
    try:
        return _normalize_name_key(s) == _normalize_name_key(getattr(service, "name", ""))
    except Exception:
        return False


def _prof_allows_service(setup_payload: Optional[dict], prof, service: Service) -> bool:
    """Return True if professional is allowed to perform the given service.

    Backwards compatible: if no config is present, allow.

    Supported shapes (under setup_payload.team.perProfessional[<name or id>]):
    - servicesAllowed: [1, 2, "Corte", ...]
    - serviceIds: [1, 2, ...]
    - services: {
         "1": true,
         "Corte": {"enabled": true},
      }
      or list with items like {"id": 1, "enabled": true}.
    """

    entry = _per_professional_entry(setup_payload, prof)
    if not isinstance(entry, dict):
        return True

    configured = False

    allowed_list = entry.get("servicesAllowed")
    if isinstance(allowed_list, list):
        configured = True
        for it in allowed_list:
            if isinstance(it, dict):
                if _service_key_matches(service, it.get("id") or it.get("service_id") or it.get("name")):
                    return bool(it.get("enabled", True))
            else:
                if _service_key_matches(service, it):
                    return True

    ids_list = entry.get("serviceIds")
    if isinstance(ids_list, list):
        configured = True
        for it in ids_list:
            if _service_key_matches(service, it):
                return True

    services_map = entry.get("services")
    if isinstance(services_map, dict):
        configured = True
        for k, v in services_map.items():
            if not _service_key_matches(service, k):
                continue
            if isinstance(v, bool):
                return bool(v)
            if isinstance(v, dict):
                return bool(v.get("enabled", True))
            return True
    elif isinstance(services_map, list):
        configured = True
        for it in services_map:
            if isinstance(it, dict):
                if _service_key_matches(service, it.get("id") or it.get("service_id") or it.get("name")):
                    return bool(it.get("enabled", True))
            else:
                if _service_key_matches(service, it):
                    return True

    # If the professional has an explicit config container but doesn't list this service, deny.
    if configured:
        return False
    return True


def _extract_end_of_shift_grace_minutes(setup_payload: Optional[dict], prof=None) -> int:
    """Retorna tolerância (minutos) permitida para ultrapassar o fim do turno.

    Importante: essa tolerância NÃO afeta pausas/almoço (essas continuam bloqueando por sobreposição).

    Suporta:
    - setup_payload.business.endOfShiftGraceMinutes (ou endOfDayGraceMinutes)
    - setup_payload.team.perProfessional[<name or id>].endOfShiftGraceMinutes
    """
    default_val = 0
    if isinstance(setup_payload, dict) and isinstance(setup_payload.get("business"), dict):
        biz = setup_payload.get("business")
        raw = biz.get("endOfShiftGraceMinutes")
        if raw is None:
            raw = biz.get("endOfDayGraceMinutes")
        try:
            default_val = int(raw) if raw is not None else 0
        except Exception:
            default_val = 0

    # per-professional override
    if prof is not None and isinstance(setup_payload, dict):
        team = setup_payload.get("team")
        if isinstance(team, dict):
            per = team.get("perProfessional")
            if isinstance(per, dict):
                keys: list[str] = []
                try:
                    nm = getattr(prof, "nome", None)
                    if nm is not None and str(nm).strip():
                        keys.append(str(nm).strip())
                except Exception:
                    pass
                try:
                    pid = getattr(prof, "id", None)
                    if pid is not None:
                        keys.append(str(pid))
                except Exception:
                    pass
                for k in keys:
                    entry = per.get(k)
                    if not isinstance(entry, dict):
                        continue
                    raw = entry.get("endOfShiftGraceMinutes")
                    if raw is None:
                        continue
                    try:
                        default_val = int(raw)
                    except Exception:
                        pass
                    break

    if default_val < 0:
        default_val = 0
    if default_val > 30:
        # guardrail: não queremos tolerâncias absurdas por acidente
        default_val = 30
    return default_val


def _weekday_key_monday_first(d) -> str:
    # python weekday(): Monday=0..Sunday=6
    mapping = {
        0: "monday",
        1: "tuesday",
        2: "wednesday",
        3: "thursday",
        4: "friday",
        5: "saturday",
        6: "sunday",
    }
    return mapping.get(d.weekday(), "monday")


def _extract_confirmation_policy(payload: Optional[dict]) -> dict:
    """Extrai política de confirmação (SMS) do SetupProfile.

    V1.5 (defaults):
    - Só mostrar slots com antecedência >= 4h
    - Quiet hours (não enviar SMS): 21:00–08:00
    - Se faltarem < 36h e não estiver em quiet hours: SMS imediato; confirmar em 4h, cap em 21:00
    - Se faltarem >= 36h: fluxo véspera 17:00 -> deadline 20:00
    - Se o booking for feito depois das 21:00 e o slot for amanhã >= 14:00:
        SMS amanhã 08:00; confirmar até amanhã 12:00

        Optional (opt-in) modes:
        - prevDayWindowsEnabled: força a confirmação sempre na véspera (para slots futuros),
            com janelas separadas por horário (ex.: manhã 14:00->17:00; tarde/noite 17:00->20:00).
    """

    def _read_container(p: Optional[dict]) -> Optional[dict]:
        if not isinstance(p, dict):
            return None
        c = p.get("confirmation")
        return c if isinstance(c, dict) else None

    root = _read_container(payload)
    biz = None
    if isinstance(payload, dict) and isinstance(payload.get("business"), dict):
        biz = _read_container(payload.get("business"))

    src = root or biz or {}
    has_confirmation_config = (root is not None) or (biz is not None)

    def _parse_bool(v, default: bool = False) -> bool:
        if isinstance(v, bool):
            return v
        if v is None:
            return default
        s = str(v).strip().lower()
        if s in ["1", "true", "yes", "y", "on"]:
            return True
        if s in ["0", "false", "no", "n", "off", ""]:
            return False
        return default

    # hard rules
    try:
        min_lead_hours = int(src.get("minLeadHours", 4))
    except Exception:
        min_lead_hours = 4
    if min_lead_hours < 0:
        min_lead_hours = 0

    try:
        immediate_horizon_hours = int(src.get("immediateHorizonHours", 36))
    except Exception:
        immediate_horizon_hours = 36
    if immediate_horizon_hours <= 0:
        immediate_horizon_hours = 36

    try:
        immediate_window_hours = int(src.get("immediateWindowHours", 4))
    except Exception:
        immediate_window_hours = 4
    if immediate_window_hours <= 0:
        immediate_window_hours = 4

    quiet_start = _parse_hhmm(src.get("quietHoursStart")) or dt_time(hour=21, minute=0)
    quiet_end = _parse_hhmm(src.get("quietHoursEnd")) or dt_time(hour=8, minute=0)

    # tomorrow-after-quiet-hours mode
    tomorrow_min_time = _parse_hhmm(src.get("tomorrowAfterQuietMinTime")) or dt_time(hour=14, minute=0)
    night_send_time = _parse_hhmm(src.get("nightSendTime")) or dt_time(hour=8, minute=0)
    night_confirm_deadline = _parse_hhmm(src.get("nightConfirmDeadline")) or dt_time(hour=12, minute=0)

    # batch (day-before)
    batch_send_time = _parse_hhmm(src.get("sendTimePrevDay")) or dt_time(hour=17, minute=0)
    batch_deadline_time = _parse_hhmm(src.get("capDeadlinePrevDay")) or dt_time(hour=20, minute=0)

    # prev-day windows (V3) - opt-in to preserve legacy behavior.
    prev_day_windows_enabled = _parse_bool(src.get("prevDayWindowsEnabled"), False)
    prev_day_split_time = _parse_hhmm(src.get("prevDaySplitTime")) or dt_time(hour=14, minute=0)
    prev_day_morning_send_time = _parse_hhmm(src.get("prevDayMorningSendTime")) or dt_time(hour=14, minute=0)
    prev_day_morning_deadline_time = _parse_hhmm(src.get("prevDayMorningDeadline")) or dt_time(hour=17, minute=0)
    prev_day_afternoon_send_time = _parse_hhmm(src.get("prevDayAfternoonSendTime")) or dt_time(hour=17, minute=0)
    prev_day_afternoon_deadline_time = _parse_hhmm(src.get("prevDayAfternoonDeadline")) or dt_time(hour=20, minute=0)

    # Cutoffs (V2)
    # If the establishment has no explicit confirmation config yet, default to
    # recommended deterministic visibility rules (cutoffs + lead time).
    if not has_confirmation_config:
        cutoffs_enabled = True
    else:
        cutoffs_enabled = _parse_bool(src.get("cutoffsEnabled"), False)
    morning_end_time = _parse_hhmm(src.get("morningEndTime")) or dt_time(hour=12, minute=0)
    afternoon_end_time = _parse_hhmm(src.get("afternoonEndTime")) or dt_time(hour=17, minute=0)
    morning_cutoff_prev_day = _parse_hhmm(src.get("morningCutoffPrevDay")) or dt_time(hour=20, minute=0)
    afternoon_cutoff_same_day = _parse_hhmm(src.get("afternoonCutoffSameDay")) or dt_time(hour=12, minute=0)
    night_cutoff_same_day = _parse_hhmm(src.get("nightCutoffSameDay")) or dt_time(hour=16, minute=0)

    # Optional: prev-day cutoffs for afternoon/night (useful when hiding availability based on véspera window).
    afternoon_cutoff_prev_day = _parse_hhmm(src.get("afternoonCutoffPrevDay"))
    night_cutoff_prev_day = _parse_hhmm(src.get("nightCutoffPrevDay"))

    # Simple mode (V4)
    # If confirmation isn't configured, default to simple mode.
    if not has_confirmation_config:
        simple_mode_enabled = True
        availability_cutoffs_only = True
    else:
        simple_mode_enabled = _parse_bool(src.get("simpleModeEnabled"), False)
        availability_cutoffs_only = _parse_bool(src.get("availabilityCutoffsOnly"), False)

    # Guardrails applied after computing confirm_by.
    try:
        min_confirm_window_hours = int(src.get("minConfirmWindowHours", 0))
    except Exception:
        min_confirm_window_hours = 0
    if min_confirm_window_hours < 0:
        min_confirm_window_hours = 0
    if min_confirm_window_hours > 24:
        min_confirm_window_hours = 24

    try:
        cap_before_start_hours = int(src.get("capBeforeStartHours", 0))
    except Exception:
        cap_before_start_hours = 0
    if cap_before_start_hours < 0:
        cap_before_start_hours = 0
    if cap_before_start_hours > 24:
        cap_before_start_hours = 24

    allow_same_day = _parse_bool(src.get("allowSameDay"), True)
    allow_same_day_night_only = _parse_bool(src.get("allowSameDayNightOnly"), False)

    # anti-piscada (histerese)
    try:
        step_minutes = int(src.get("hysteresisStepMinutes", 15))
    except Exception:
        step_minutes = 15
    if step_minutes <= 0:
        step_minutes = 15
    if step_minutes > 60:
        step_minutes = 60

    return {
        "has_confirmation_config": has_confirmation_config,
        "min_lead_hours": min_lead_hours,
        "immediate_horizon_hours": immediate_horizon_hours,
        "immediate_window_hours": immediate_window_hours,
        "quiet_start": quiet_start,
        "quiet_end": quiet_end,
        "tomorrow_after_quiet_min_time": tomorrow_min_time,
        "night_send_time": night_send_time,
        "night_confirm_deadline": night_confirm_deadline,
        "batch_send_time_prev_day": batch_send_time,
        "batch_deadline_prev_day": batch_deadline_time,
        "prev_day_windows_enabled": prev_day_windows_enabled,
        "prev_day_split_time": prev_day_split_time,
        "prev_day_morning_send_time": prev_day_morning_send_time,
        "prev_day_morning_deadline": prev_day_morning_deadline_time,
        "prev_day_afternoon_send_time": prev_day_afternoon_send_time,
        "prev_day_afternoon_deadline": prev_day_afternoon_deadline_time,
        "simple_mode_enabled": simple_mode_enabled,
        "availability_cutoffs_only": availability_cutoffs_only,
        "hysteresis_step_minutes": step_minutes,
        "cutoffs_enabled": cutoffs_enabled,
        "morning_end_time": morning_end_time,
        "afternoon_end_time": afternoon_end_time,
        "morning_cutoff_prev_day": morning_cutoff_prev_day,
        "afternoon_cutoff_same_day": afternoon_cutoff_same_day,
        "night_cutoff_same_day": night_cutoff_same_day,
        "afternoon_cutoff_prev_day": afternoon_cutoff_prev_day,
        "night_cutoff_prev_day": night_cutoff_prev_day,
        "min_confirm_window_hours": min_confirm_window_hours,
        "cap_before_start_hours": cap_before_start_hours,
        "allow_same_day": allow_same_day,
        "allow_same_day_night_only": allow_same_day_night_only,
    }


def _slot_passes_basic_availability_filter(
    *,
    now_local: datetime,
    slot_start_local: datetime,
    policy: dict,
) -> bool:
    """Basic deterministic availability rules.

    Intended for the simple mode where slot visibility depends only on:
    - not in the past
    - cutoffs (same-day / prev-day)
    - min lead time (with hysteresis)
    """
    if slot_start_local <= now_local:
        return False

    allowed, _reason = _cutoff_allows_slot(now_local=now_local, slot_start_local=slot_start_local, policy=policy)
    if not allowed:
        return False

    min_lead_hours = int(policy.get("min_lead_hours") or 0)
    lead_minutes = (slot_start_local - now_local).total_seconds() / 60.0
    step_minutes = int(policy.get("hysteresis_step_minutes") or 15)
    stable_lead_minutes = _ceil_minutes(lead_minutes, step_minutes)
    if stable_lead_minutes < (min_lead_hours * 60):
        return False

    return True


def _slot_period_for_time(*, t: dt_time, policy: dict) -> str:
    morning_end: dt_time = policy.get("morning_end_time") or dt_time(hour=12, minute=0)
    afternoon_end: dt_time = policy.get("afternoon_end_time") or dt_time(hour=17, minute=0)
    if t < morning_end:
        return "morning"
    if t < afternoon_end:
        return "afternoon"
    return "night"


def _cutoff_time_for_period(*, period: str, policy: dict) -> Optional[dt_time]:
    if period == "afternoon":
        return policy.get("afternoon_cutoff_same_day")
    if period == "night":
        return policy.get("night_cutoff_same_day")
    # morning same-day cutoff is intentionally not defined here; morning is governed by other rules.
    return None


def _cutoff_allows_slot(*, now_local: datetime, slot_start_local: datetime, policy: dict) -> tuple[bool, Optional[str]]:
    """Return (allowed, reason).

    Cutoffs are intentionally simple, deterministic, and timezone-safe (based on now_local.tzinfo).
    Only active when policy['cutoffs_enabled'] is True.
    """

    if not policy.get("cutoffs_enabled"):
        return True, None

    slot_date = slot_start_local.date()
    now_date = now_local.date()

    if slot_date < now_date:
        return False, "past_date"

    allow_same_day = bool(policy.get("allow_same_day", True))
    allow_same_day_night_only = bool(policy.get("allow_same_day_night_only", False))
    period = _slot_period_for_time(t=slot_start_local.time(), policy=policy)

    # Morning cutoff is defined as an absolute moment: (slot_date - 1) at configured time.
    # If now_local is after that moment, any morning slot for slot_date is blocked (including after midnight).
    if period == "morning":
        cutoff_prev: dt_time = policy.get("morning_cutoff_prev_day") or dt_time(hour=20, minute=0)
        cutoff_dt = datetime.combine(slot_date - timedelta(days=1), cutoff_prev)
        if now_local.tzinfo and cutoff_dt.tzinfo is None:
            cutoff_dt = cutoff_dt.replace(tzinfo=now_local.tzinfo)
        if now_local > cutoff_dt:
            return False, "cutoff_prev_day_morning"

    # Optional: prev-day cutoff for afternoon/night
    if period in ["afternoon", "night"]:
        key = "afternoon_cutoff_prev_day" if period == "afternoon" else "night_cutoff_prev_day"
        cutoff_prev = policy.get(key)
        if isinstance(cutoff_prev, dt_time):
            cutoff_dt = datetime.combine(slot_date - timedelta(days=1), cutoff_prev)
            if now_local.tzinfo and cutoff_dt.tzinfo is None:
                cutoff_dt = cutoff_dt.replace(tzinfo=now_local.tzinfo)
            if now_local > cutoff_dt:
                return False, f"cutoff_prev_day_{period}"

    # Same-day cutoffs
    if slot_date == now_date:
        if not allow_same_day:
            return False, "same_day_disabled"
        if allow_same_day_night_only and period != "night":
            return False, "same_day_night_only"

        cutoff_t = _cutoff_time_for_period(period=period, policy=policy)
        if cutoff_t is not None and now_local.time() > cutoff_t:
            return False, f"cutoff_same_day_{period}"
        return True, None

    return True, None


def _apply_confirmation_guardrails(
    *,
    now_local: datetime,
    slot_start_local: datetime,
    send_at: Optional[datetime],
    confirm_by: Optional[datetime],
    policy: dict,
) -> tuple[Optional[datetime], Optional[datetime]]:
    if send_at is None or confirm_by is None:
        return None, None

    # Cap deadline to be before the appointment starts (operational safety)
    cap_hours = int(policy.get("cap_before_start_hours") or 0)
    if cap_hours > 0:
        cap_dt = slot_start_local - timedelta(hours=cap_hours)
        if now_local.tzinfo and cap_dt.tzinfo is None:
            cap_dt = cap_dt.replace(tzinfo=now_local.tzinfo)
        confirm_by = min(confirm_by, cap_dt)

    # Minimum time window for the customer to respond
    min_window_hours = int(policy.get("min_confirm_window_hours") or 0)
    if min_window_hours > 0:
        if (confirm_by - now_local) < timedelta(hours=min_window_hours):
            return None, None

    if confirm_by <= now_local:
        return None, None
    return send_at, confirm_by


def _is_in_quiet_hours(now_local: datetime, quiet_start: dt_time, quiet_end: dt_time) -> bool:
    """Retorna True se o horário local estiver dentro de quiet hours.

    Suporta janelas que cruzam meia-noite (ex.: 21:00 -> 08:00).
    """
    t = now_local.time()
    if quiet_start == quiet_end:
        return False
    if quiet_start < quiet_end:
        return quiet_start <= t < quiet_end
    return t >= quiet_start or t < quiet_end


def _ceil_minutes(value_minutes: float, step_minutes: int) -> int:
    if step_minutes <= 1:
        return int(value_minutes)
    try:
        v = float(value_minutes)
    except Exception:
        v = 0.0
    if v <= 0:
        return 0
    return int(math.ceil(v / float(step_minutes)) * float(step_minutes))


def _confirmation_times_for_slot(
    *,
    now_local: datetime,
    slot_start_local: datetime,
    policy: dict,
) -> tuple[Optional[datetime], Optional[datetime]]:
    """Calcula (send_at, confirm_by) para o slot, ou (None,None) se não for bookável."""
    if slot_start_local <= now_local:
        return None, None

    prev_day_mode = bool(policy.get("prev_day_windows_enabled", False)) and slot_start_local.date() > now_local.date()
    simple_mode = bool(policy.get("simple_mode_enabled", False))

    allowed, _reason = _cutoff_allows_slot(now_local=now_local, slot_start_local=slot_start_local, policy=policy)
    if not allowed:
        return None, None

    # antecedência mínima
    min_lead_hours = int(policy.get("min_lead_hours") or 0)
    lead_minutes = (slot_start_local - now_local).total_seconds() / 60.0
    step_minutes = int(policy.get("hysteresis_step_minutes") or 15)
    stable_lead_minutes = _ceil_minutes(lead_minutes, step_minutes)
    if stable_lead_minutes < (min_lead_hours * 60):
        return None, None

    quiet_start: dt_time = policy.get("quiet_start")
    quiet_end: dt_time = policy.get("quiet_end")
    has_confirmation_config = bool(policy.get("has_confirmation_config", False))
    in_quiet = _is_in_quiet_hours(now_local, quiet_start, quiet_end) if has_confirmation_config else False

    # If prev-day windows are enabled for future-day slots, do not apply the quiet-hours special mode.
    # The "véspera" schedule is deterministic and should stay consistent regardless of when the user books.
    if prev_day_mode:
        in_quiet = False

    # Simple mode also avoids quiet-hours branching: it should behave consistently.
    if simple_mode:
        in_quiet = False

    # Mode: booking feito durante quiet hours (ex.: 21:00-08:00)
    if in_quiet:
        # Permitimos somente "amanhã à tarde/noite" (>= 14:00) com envio 08:00 e deadline 12:00.
        tomorrow_min_t: dt_time = policy.get("tomorrow_after_quiet_min_time")
        night_send_t: dt_time = policy.get("night_send_time")
        night_deadline_t: dt_time = policy.get("night_confirm_deadline")

        if slot_start_local.date() == (now_local.date() + timedelta(days=1)) and slot_start_local.time() >= tomorrow_min_t:
            send_at = datetime.combine(slot_start_local.date(), night_send_t)
            confirm_by = datetime.combine(slot_start_local.date(), night_deadline_t)
            if now_local.tzinfo:
                send_at = send_at.replace(tzinfo=now_local.tzinfo)
                confirm_by = confirm_by.replace(tzinfo=now_local.tzinfo)
            return _apply_confirmation_guardrails(
                now_local=now_local,
                slot_start_local=slot_start_local,
                send_at=send_at,
                confirm_by=confirm_by,
                policy=policy,
            )

        # Slots "curto prazo" durante quiet hours: não mostramos.
        # Slots mais distantes (>= horizon) seguem fluxo batch; isso permite marcar datas futuras.
        immediate_horizon_hours = int(policy.get("immediate_horizon_hours") or 36)
        if stable_lead_minutes < (immediate_horizon_hours * 60):
            return None, None

    # Fora de quiet hours: decidir entre imediato vs batch
    immediate_horizon_hours = int(policy.get("immediate_horizon_hours") or 36)
    immediate_window_hours = int(policy.get("immediate_window_hours") or 4)

    # Mode: force prev-day confirmation windows for future-day slots (opt-in).
    if bool(policy.get("prev_day_windows_enabled", False)) and slot_start_local.date() > now_local.date():
        split_t: dt_time = policy.get("prev_day_split_time") or dt_time(hour=14, minute=0)
        is_morning_window = slot_start_local.time() <= split_t
        if is_morning_window:
            send_t: dt_time = policy.get("prev_day_morning_send_time") or dt_time(hour=14, minute=0)
            deadline_t: dt_time = policy.get("prev_day_morning_deadline") or dt_time(hour=17, minute=0)
        else:
            send_t = policy.get("prev_day_afternoon_send_time") or dt_time(hour=17, minute=0)
            deadline_t = policy.get("prev_day_afternoon_deadline") or dt_time(hour=20, minute=0)
        day_before = slot_start_local.date() - timedelta(days=1)
        send_at = datetime.combine(day_before, send_t)
        confirm_by = datetime.combine(day_before, deadline_t)
        if now_local.tzinfo:
            send_at = send_at.replace(tzinfo=now_local.tzinfo)
            confirm_by = confirm_by.replace(tzinfo=now_local.tzinfo)

        # If the prev-day window already expired, allow a last-chance immediate confirmation
        # for afternoon/night slots (so "amanhã 16:00" can still be bookable after 20:00).
        # Morning slots remain strict to prevent last-minute morning bookings.
        if confirm_by <= now_local:
            if is_morning_window:
                return None, None
            send_at = now_local
            confirm_by = now_local + timedelta(hours=immediate_window_hours)

        return _apply_confirmation_guardrails(
            now_local=now_local,
            slot_start_local=slot_start_local,
            send_at=send_at,
            confirm_by=confirm_by,
            policy=policy,
        )

    if stable_lead_minutes < (immediate_horizon_hours * 60):
        send_at = now_local
        confirm_by = now_local + timedelta(hours=immediate_window_hours)
        # cap: não queremos confirmações depois do início de quiet hours (apenas quando configurado)
        if has_confirmation_config:
            cap_dt = datetime.combine(now_local.date(), quiet_start)
            if now_local.tzinfo:
                cap_dt = cap_dt.replace(tzinfo=now_local.tzinfo)
            if cap_dt > now_local:
                confirm_by = min(confirm_by, cap_dt)
        return _apply_confirmation_guardrails(
            now_local=now_local,
            slot_start_local=slot_start_local,
            send_at=send_at,
            confirm_by=confirm_by,
            policy=policy,
        )

    # Batch (>= horizon): dia anterior 17:00 -> deadline 20:00
    send_t: dt_time = policy.get("batch_send_time_prev_day")
    deadline_t: dt_time = policy.get("batch_deadline_prev_day")
    day_before = slot_start_local.date() - timedelta(days=1)
    send_at = datetime.combine(day_before, send_t)
    confirm_by = datetime.combine(day_before, deadline_t)
    if now_local.tzinfo:
        send_at = send_at.replace(tzinfo=now_local.tzinfo)
        confirm_by = confirm_by.replace(tzinfo=now_local.tzinfo)
    return _apply_confirmation_guardrails(
        now_local=now_local,
        slot_start_local=slot_start_local,
        send_at=send_at,
        confirm_by=confirm_by,
        policy=policy,
    )


def _confirmation_deadline_for_slot(
    *,
    now_local: datetime,
    slot_start_local: datetime,
    policy: dict,
) -> Optional[datetime]:
    """Compat: retorna apenas o deadline (confirm_by) para o slot.

    A implementação principal agora está em _confirmation_times_for_slot.
    """
    _, confirm_by = _confirmation_times_for_slot(now_local=now_local, slot_start_local=slot_start_local, policy=policy)
    return confirm_by


def _slot_passes_confirmation_filter(
    *,
    now_local: datetime,
    slot_start_local: datetime,
    policy: dict,
) -> bool:
    # In simple availability mode, slot visibility is governed by cutoffs + min lead time,
    # not by confirmation window deadlines.
    if bool(policy.get("availability_cutoffs_only", False)) or bool(policy.get("simple_mode_enabled", False)):
        return _slot_passes_basic_availability_filter(now_local=now_local, slot_start_local=slot_start_local, policy=policy)

    send_at, confirm_by = _confirmation_times_for_slot(now_local=now_local, slot_start_local=slot_start_local, policy=policy)
    if send_at is None or confirm_by is None:
        return False
    if now_local >= confirm_by:
        return False
    return True


def _get_single_estabelecimento(db: Session, slug: Optional[str] = None) -> Estabelecimento:
    """Retorna o estabelecimento "principal" para fins de booking.

    Preferimos o estabelecimento demo criado pelo seed (slug
    "ana-beleza-madrid"), que é o que tem profissionais e serviços
    configurados. Se não existir, caímos para:
    - o primeiro estabelecimento que tiver ao menos um serviço; ou
    - qualquer estabelecimento existente.
    """

    # 1) Tentar slug passado explicitamente
    est = None
    if slug:
        est = db.query(Estabelecimento).filter(Estabelecimento.slug == slug).first()

    # 2) Tentar o slug conhecido do seed se não passou slug
    if not est and not slug:
        est = (
            db.query(Estabelecimento)
            .filter(Estabelecimento.slug == "ana-beleza-madrid")
            .first()
        )

    # 2) Caso não exista, tentar um estabelecimento que tenha serviços
    if not est:
        est = (
            db.query(Estabelecimento)
            .join(Service, Service.estabelecimento_id == Estabelecimento.id)
            .first()
        )

    # 3) Fallback final: qualquer estabelecimento
    if not est:
        est = db.query(Estabelecimento).first()

    if not est:
        raise HTTPException(status_code=400, detail="Nenhum estabelecimento configurado")

    return est


@router.get("/config", response_model=ConfigOut)
def get_config(
    slug: Optional[str] = Query(None, description="Slug do estabelecimento (opcional)"),
    db: Session = Depends(get_db),
) -> ConfigOut:
    """Retorna serviços e profissionais para landing e dashboard.

    Por enquanto, usamos o primeiro estabelecimento encontrado.
    """
    est = _get_single_estabelecimento(db, slug=slug)

    services: List[Service] = (
        db.query(Service)
        .filter(Service.estabelecimento_id == est.id)
        .order_by(Service.id.asc())
        .all()
    )

    professionals: List[Funcionario] = (
        db.query(Funcionario)
        .filter(Funcionario.estabelecimento_id == est.id)
        .order_by(Funcionario.id.asc())
        .all()
    )

    # customer-facing booking rules (used by booking UI popup)
    setup_row = db.query(SetupProfile).filter(SetupProfile.estabelecimento_id == est.id).first()
    setup_payload = setup_row.payload if setup_row else None

    # Regras de confirmação (<24h): só oferecer horários com no mínimo 6h de antecedência.
    tz, tz_name = resolve_timezone(setup_payload if isinstance(setup_payload, dict) else None)
    now_local = datetime.now(tz) if tz else datetime.now()
    pol = setup_payload.get("policies") if isinstance(setup_payload, dict) else None
    if not isinstance(pol, dict):
        pol = {}

    deposit_enabled = bool(pol.get("depositEnabled"))
    retain_pct = int(pol.get("noShowRetainPercentOfService") or 15)
    refund_pct = int(pol.get("noShowRefundPercentOfService") or 35)

    lang = (est.idioma_padrao or "pt-BR")
    if str(lang).lower().startswith("en"):
        popup_text = (
            f"No-show policy: you pay 50% to reserve. If you don't show up, we keep {retain_pct}% and refund {refund_pct}% of the service price."
            if deposit_enabled else None
        )
    elif str(lang).lower().startswith("es"):
        popup_text = (
            f"Regla de no-show: pagas 50% para reservar. Si no asistes, retenemos {retain_pct}% y reembolsamos {refund_pct}% del valor del servicio."
            if deposit_enabled else None
        )
    elif str(lang).lower().startswith("fr"):
        popup_text = (
            f"Règle no-show : vous payez 50% pour réserver. En cas d'absence, nous retenons {retain_pct}% et remboursons {refund_pct}% du prix du service."
            if deposit_enabled else None
        )
    elif str(lang).lower().startswith("ca"):
        popup_text = (
            f"Regla de no-show: pagues el 50% per reservar. Si no vens, retenim {retain_pct}% i retornem {refund_pct}% del preu del servei."
            if deposit_enabled else None
        )
    else:
        popup_text = (
            f"Regra de no-show: você paga 50% para reservar. Em caso de não comparecimento, será retido {retain_pct}% e reembolsado {refund_pct}% do valor do serviço."
            if deposit_enabled else None
        )

    deposit_rule = BookingDepositRuleOut(
        enabled=deposit_enabled,
        deposit_percent_of_service=50,
        no_show_retain_percent_of_service=retain_pct,
        no_show_refund_percent_of_service=refund_pct,
        popup_text=popup_text,
    )

    return ConfigOut(
        services=[
            ServiceOut(
                id=s.id,
                name=s.name,
                duration_min=s.duration_min,
                buffer_min=s.buffer_min,
                price_cents=s.price_cents,
                display_interval_min=s.display_interval_min,
            )
            for s in services
        ],
        professionals=[
            ProfessionalOut(id=p.id, name=p.nome) for p in professionals
        ],
        business=EstabelecimentoOut(
            id=est.id,
            nome=est.nome,
            telefone=est.telefone,
            slug=est.slug,
            lembrete_horas_antes=est.lembrete_horas_antes or [],
            email=est.email,
            idioma_padrao=est.idioma_padrao,
            horario_inicio=getattr(est, 'horario_inicio', 9),
            horario_fim=getattr(est, 'horario_fim', 18),
            timezone=str(tz_name) if tz_name else None,
            today_local=now_local.strftime('%Y-%m-%d') if isinstance(now_local, datetime) else None,
            now_local_iso=now_local.isoformat() if isinstance(now_local, datetime) else None,
            photos=est.photos or [],
            reviews=est.reviews or [],
        ),
        deposit_rule=deposit_rule,
    )


def _to_appointment_out(ag: Agendamento) -> AppointmentOut:
    if not ag.service:
        # Fallback seguro se service estiver ausente em registros antigos
        base_duration = 60
        base_buffer = 0
        service_id = 0
    else:
        base_duration = ag.service.duration_min
        base_buffer = ag.service.buffer_min or 0
        service_id = ag.service.id

    date_str = ag.data_hora.date().isoformat()
    start_time = ag.data_hora.strftime("%H:%M")

    return AppointmentOut(
        id=ag.id,
        service_id=service_id,
        professional_id=ag.funcionario_id,
        date=date_str,
        start_time=start_time,
        duration_min=base_duration,
        buffer_min=base_buffer,
        status=ag.status or "pendente",
        customer_name=ag.cliente.nome if ag.cliente else "",
        customer_whatsapp=ag.cliente.telefone if ag.cliente else "",
    )


def _escape_ics_text(value: str) -> str:
    s = str(value or "")
    # RFC5545 escaping: backslash, semicolon, comma, newline
    s = s.replace("\\", "\\\\")
    s = s.replace(";", "\\;")
    s = s.replace(",", "\\,")
    s = s.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")
    return s


def _dt_to_ics_utc(dt: datetime) -> str:
    aware = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    utc_dt = aware.astimezone(timezone.utc).replace(microsecond=0)
    return utc_dt.strftime("%Y%m%dT%H%M%SZ")


def _td_to_ics_duration(td: timedelta) -> str:
    """Format a timedelta as an RFC5545 duration (PnDTnHnMnS) without sign."""
    total = int(abs(td.total_seconds()))
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)

    parts = []
    if days:
        parts.append(f"{days}D")

    time_parts = []
    if hours:
        time_parts.append(f"{hours}H")
    if minutes:
        time_parts.append(f"{minutes}M")
    if seconds or not (parts or time_parts):
        time_parts.append(f"{seconds}S")

    if time_parts:
        return "P" + "".join(parts) + "T" + "".join(time_parts)
    return "P" + "".join(parts)


def _build_ics_event(
    *,
    uid: str,
    summary: str,
    description: str,
    dtstart: datetime,
    dtend: datetime,
    url: Optional[str] = None,
    alarm_trigger_at: Optional[datetime] = None,
    alarm_description: Optional[str] = None,
) -> str:

    now_utc = datetime.now(timezone.utc)

    tz_name = None
    try:
        if getattr(dtstart, "tzinfo", None) is not None and hasattr(dtstart.tzinfo, "key"):
            tz_name = str(dtstart.tzinfo.key)
    except Exception:
        tz_name = None

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//EasyAgenda//Booking//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:EasyAgenda",
    ]

    if tz_name:
        lines.append(f"X-WR-TIMEZONE:{_escape_ics_text(tz_name)}")

    lines.extend(
        [
            "BEGIN:VEVENT",
            f"UID:{_escape_ics_text(uid)}",
            f"DTSTAMP:{_dt_to_ics_utc(now_utc)}",
            f"DTSTART:{_dt_to_ics_utc(dtstart)}",
            f"DTEND:{_dt_to_ics_utc(dtend)}",
            "STATUS:CONFIRMED",
            "TRANSP:OPAQUE",
            f"SUMMARY:{_escape_ics_text(summary)}",
            f"DESCRIPTION:{_escape_ics_text(description)}",
        ]
    )

    if url:
        lines.append(f"URL:{_escape_ics_text(url)}")

    if alarm_trigger_at is not None:
        desc = str(alarm_description or "Lembrete")
        trigger_line = None
        try:
            if alarm_trigger_at < dtstart:
                # More compatible with Outlook: relative trigger before DTSTART
                delta = dtstart - alarm_trigger_at
                trigger_line = f"TRIGGER:-{_td_to_ics_duration(delta)}"
        except Exception:
            trigger_line = None
        if not trigger_line:
            trigger_line = f"TRIGGER;VALUE=DATE-TIME:{_dt_to_ics_utc(alarm_trigger_at)}"

        lines.extend(
            [
                "BEGIN:VALARM",
                "ACTION:DISPLAY",
                f"DESCRIPTION:{_escape_ics_text(desc)}",
                trigger_line,
                "END:VALARM",
            ]
        )

    lines.extend(
        [
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )
    return "\r\n".join(lines)


@router.get("/appointments", response_model=List[AppointmentOut])
def list_appointments(
    professional_id: int = Query(..., description="ID do profissional"),
    date: str = Query(..., description="Data no formato YYYY-MM-DD"),
    db: Session = Depends(get_db),
) -> List[AppointmentOut]:
    """Lista agendamentos para um profissional em um dia, no formato esperado pelo dashboard."""
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Data inválida, use YYYY-MM-DD")

    start_dt = datetime.combine(target_date, dt_time.min)
    end_dt = datetime.combine(target_date, dt_time.max)

    ags = (
        db.query(Agendamento)
        .filter(
            Agendamento.funcionario_id == professional_id,
            Agendamento.data_hora >= start_dt,
            Agendamento.data_hora <= end_dt,
        )
        .order_by(Agendamento.data_hora.asc())
        .all()
    )

    return [_to_appointment_out(ag) for ag in ags]


@router.post("/appointments", response_model=dict)
def create_appointment(
    payload: AppointmentCreate,
    slug: Optional[str] = Query(None, description="Slug do estabelecimento (opcional)"),
    db: Session = Depends(get_db),
):
    """Cria um agendamento a partir do payload da landing/dashboard.

    Valida conflito com base em duration+buffer do serviço.
    """
    service = db.query(Service).filter(Service.id == payload.service_id).first()
    if not service:
        raise HTTPException(status_code=400, detail="Serviço não encontrado")

    profissional = (
        db.query(Funcionario)
        .filter(Funcionario.id == payload.professional_id)
        .first()
    )
    if not profissional:
        raise HTTPException(status_code=400, detail="Profissional não encontrado")

    try:
        start_dt = datetime.strptime(
            f"{payload.date} {payload.start_time}", "%Y-%m-%d %H:%M"
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Data ou hora inválidas")

    # Determinar establishment de forma determinística.
    if slug:
        est = _get_single_estabelecimento(db, slug=slug)
        if profissional.estabelecimento_id != est.id:
            raise HTTPException(status_code=400, detail="Profissional não pertence a este estabelecimento")
    else:
        est = db.query(Estabelecimento).filter(Estabelecimento.id == profissional.estabelecimento_id).first()
        if not est:
            raise HTTPException(status_code=400, detail="Estabelecimento do profissional não encontrado")

    # Carregar setup (para regras de horário/pausa/confirmação)
    setup_row = db.query(SetupProfile).filter(SetupProfile.estabelecimento_id == est.id).first()
    setup_payload = setup_row.payload if setup_row else None

    # Trial gating: trial starts on first successful appointment creation.
    # After expiry, block new bookings.
    setup_payload_next, trial_status = ensure_trial_started(setup_payload)
    if trial_status.expired:
        _trial_raise_expired(status=trial_status)

    # Persist trial start/end if we just created them.
    try:
        if setup_payload_next is not setup_payload:
            if setup_row:
                setup_row.payload = setup_payload_next
            else:
                setup_row = SetupProfile(estabelecimento_id=est.id, payload=setup_payload_next)
                db.add(setup_row)
            db.commit()
            db.refresh(setup_row)
            setup_payload = setup_payload_next
    except Exception:
        # Never block booking due to trial metadata persistence issues.
        setup_payload = setup_payload_next

    # Especialidade: profissional pode não oferecer este serviço
    if not _prof_allows_service(setup_payload, profissional, service):
        raise HTTPException(status_code=400, detail="Profissional não oferece este serviço")

    tz, _tz_name = resolve_timezone(setup_payload if isinstance(setup_payload, dict) else None)
    now_local = datetime.now(tz) if tz else datetime.now()
    now_naive = now_local.replace(tzinfo=None) if now_local.tzinfo else now_local

    # Não permitir agendamento no passado
    if start_dt < now_naive:
        raise HTTPException(status_code=400, detail="Não é possível agendar no passado")

    confirmation_policy = _extract_confirmation_policy(setup_payload)
    start_local = start_dt.replace(tzinfo=tz) if tz else start_dt
    if not _slot_passes_confirmation_filter(now_local=now_local, slot_start_local=start_local, policy=confirmation_policy):
        raise HTTPException(status_code=400, detail="Horário não pode ser confirmado dentro da janela")

    send_at_local, confirm_by_local = _confirmation_times_for_slot(
        now_local=now_local,
        slot_start_local=start_local,
        policy=confirmation_policy,
    )

    # Respeitar horários/pausas conforme configuração
    target_date = start_dt.date()
    biz_windows, closed_reason = _business_day_windows(est, target_date, setup_payload)
    if closed_reason is not None or not biz_windows:
        raise HTTPException(status_code=400, detail="Estabelecimento fechado nesta data")

    # dias de trabalho do profissional
    prof_workdays = _extract_prof_workdays(setup_payload)
    weekday_key = _weekday_key_monday_first(target_date)
    pname_key = _normalize_name_key(getattr(profissional, "nome", ""))
    wd = prof_workdays.get(pname_key)
    if isinstance(wd, dict) and weekday_key in wd and not bool(wd.get(weekday_key)):
        raise HTTPException(status_code=400, detail="Profissional não atende neste dia")

    # janela do profissional (se configurada) — pode ser multi-window
    prof_windows_multi = _extract_prof_day_windows_multi(setup_payload)
    prof_windows = prof_windows_multi.get(pname_key) if pname_key else None
    if not prof_windows:
        prof_windows = biz_windows
    else:
        prof_windows = _intersect_windows(prof_windows, biz_windows)

    duration_total = service.duration_min + (service.buffer_min or 0)
    new_end = start_dt + timedelta(minutes=duration_total)
    grace_min = _extract_end_of_shift_grace_minutes(setup_payload, prof=profissional)
    end_limit = _slot_end_limit_for_windows(day=target_date, windows=prof_windows, start_dt=start_dt, grace_min=grace_min)
    if end_limit is None or new_end > end_limit:
        raise HTTPException(status_code=400, detail="Fora do horário de atendimento do profissional")

    # pausas (negócio + profissional): ambas devem ser respeitadas
    biz_bs_t, biz_be_t = _extract_break_window(setup_payload)
    if biz_bs_t and biz_be_t:
        bstart = datetime.combine(target_date, biz_bs_t)
        bend = datetime.combine(target_date, biz_be_t)
        if bstart < bend and not (new_end <= bstart or start_dt >= bend):
            raise HTTPException(status_code=400, detail="Horário cai na pausa/almoço")

    pbs_t, pbe_t = _extract_break_window_for_prof(setup_payload, profissional)
    if pbs_t and pbe_t:
        pbstart = datetime.combine(target_date, pbs_t)
        pbend = datetime.combine(target_date, pbe_t)
        if pbstart < pbend and not (new_end <= pbstart or start_dt >= pbend):
            raise HTTPException(status_code=400, detail="Horário cai na pausa/almoço")

    # Garantir que o serviço pertence a este estabelecimento
    if service.estabelecimento_id != est.id:
        raise HTTPException(status_code=400, detail="Serviço não pertence a este estabelecimento")

    # Cliente: reusar telefone como chave dentro do estabelecimento determinado
    cliente = (
        db.query(Cliente)
        .filter(
            Cliente.telefone == payload.customer_whatsapp,
            Cliente.estabelecimento_id == est.id,
        )
        .first()
    )
    if not cliente:
        cliente = Cliente(
            nome=payload.customer_name,
            telefone=payload.customer_whatsapp,
            observacoes="",
            tipo_servico=service.name,
            estabelecimento_id=est.id,
        )
        if getattr(payload, "customer_lang", None):
            try:
                cliente.idioma = str(payload.customer_lang).strip() or cliente.idioma
            except Exception:
                pass
        db.add(cliente)
        db.flush()
    else:
        # Update language when provided so future reminders/ICS match the customer's booking language.
        if getattr(payload, "customer_lang", None):
            try:
                next_lang = str(payload.customer_lang).strip()
                if next_lang and str(getattr(cliente, "idioma", "") or "").strip() != next_lang:
                    cliente.idioma = next_lang
            except Exception:
                pass

    # Verificar conflitos para o mesmo profissional no dia
    new_start = start_dt

    same_day_start = datetime.combine(start_dt.date(), dt_time.min)
    same_day_end = datetime.combine(start_dt.date(), dt_time.max)

    existing = (
        db.query(Agendamento)
        .filter(
            Agendamento.funcionario_id == profissional.id,
            Agendamento.data_hora >= same_day_start,
            Agendamento.data_hora <= same_day_end,
        )
        .all()
    )

    for ag in existing:
        # Determinar duration+buffer do agendamento existente
        if ag.service:
            dur = ag.service.duration_min + (ag.service.buffer_min or 0)
        else:
            dur = 60  # fallback para registros antigos
        existing_start = ag.data_hora
        existing_end = existing_start + timedelta(minutes=dur)

        # Checar sobreposição de intervalos
        if not (new_end <= existing_start or new_start >= existing_end):
            raise HTTPException(
                status_code=409,
                detail="Este horário acabou de ser reservado. Escolha outro horário.",
            )

    novo = Agendamento(
        cliente_id=cliente.id,
        funcionario_id=profissional.id,
        service_id=service.id,
        descricao=service.name,
        data_hora=start_dt,
        status="pendente",
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)

    # Poderíamos aqui reutilizar o scheduler/notificações, similar ao dashboard,
    # mas mantemos simples por enquanto.

    ics_token = create_access_token(
        {"purpose": "ics", "appointment_id": int(novo.id), "est_id": int(est.id)},
        expires_in_hours=24 * 365,
    )
    calendar_path = f"/appointments/{novo.id}/calendar.ics?token={ics_token}"
    api_base = _public_api_base_url()
    calendar_url = f"{api_base}{calendar_path}" if api_base else calendar_path

    def _dt_to_iso(dt: Optional[datetime]) -> Optional[str]:
        if dt is None:
            return None
        try:
            return dt.isoformat()
        except Exception:
            return None

    return {
        "ok": True,
        "appointment": _to_appointment_out(novo),
        "calendar_url": calendar_url,
        "send_at": _dt_to_iso(send_at_local),
        "confirm_by": _dt_to_iso(confirm_by_local),
    }


@router.get("/appointments/{appointment_id}/calendar.ics")
def get_appointment_calendar_ics(
    appointment_id: int,
    token: str = Query(..., description="Token assinado para download do .ics"),
    db: Session = Depends(get_db),
):
    """Gera um arquivo .ics (Add to Calendar) de forma pública e segura.

    Requer um token assinado (JWT) com purpose=ics e appointment_id/est_id.
    """
    payload = verify_access_token(token)
    if str(payload.get("purpose") or "").strip().lower() != "ics":
        raise HTTPException(status_code=403, detail="Token inválido")

    tok_appt_id = payload.get("appointment_id")
    tok_est_id = payload.get("est_id")
    try:
        tok_appt_id_int = int(tok_appt_id)
        tok_est_id_int = int(tok_est_id)
    except Exception:
        raise HTTPException(status_code=403, detail="Token inválido")

    if tok_appt_id_int != int(appointment_id):
        raise HTTPException(status_code=403, detail="Token inválido")

    ag = db.query(Agendamento).filter(Agendamento.id == appointment_id).first()
    if not ag:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")

    profissional = db.query(Funcionario).filter(Funcionario.id == ag.funcionario_id).first()
    if not profissional:
        raise HTTPException(status_code=404, detail="Profissional não encontrado")

    est = db.query(Estabelecimento).filter(Estabelecimento.id == profissional.estabelecimento_id).first()
    if not est:
        raise HTTPException(status_code=404, detail="Estabelecimento não encontrado")

    if int(est.id) != tok_est_id_int:
        raise HTTPException(status_code=403, detail="Token inválido")

    setup_row = db.query(SetupProfile).filter(SetupProfile.estabelecimento_id == est.id).first()
    setup_payload = setup_row.payload if setup_row else None

    tz, _tz_name = resolve_timezone(setup_payload if isinstance(setup_payload, dict) else None)

    start_local = ag.data_hora.replace(tzinfo=tz)
    duration_min = ag.service.duration_min if getattr(ag, "service", None) else 60
    end_local = start_local + timedelta(minutes=int(duration_min))

    now_local = datetime.now(tz)
    confirmation_policy = _extract_confirmation_policy(setup_payload)

    # For already-created appointments we still want to show a confirmation window,
    # even if the slot is now inside the min lead time.
    try:
        policy_for_display = dict(confirmation_policy)
        policy_for_display["min_lead_hours"] = 0
    except Exception:
        policy_for_display = confirmation_policy

    send_at_local, confirm_by_local = _confirmation_times_for_slot(
        now_local=now_local,
        slot_start_local=start_local,
        policy=policy_for_display,
    )

    service_name = "Serviço" if not getattr(ag, "service", None) else (ag.service.name or "Serviço")
    business_name = getattr(est, "nome", None) or "Estabelecimento"
    professional_name = getattr(profissional, "nome", None) or ""

    lang = resolve_lang(
        cliente_lang=getattr(getattr(ag, "cliente", None), "idioma", None),
        estabelecimento_lang=getattr(est, "idioma_padrao", None),
    )

    def _i18n(label_key: str) -> str:
        # Minimal, deterministic strings for ICS fields.
        # Keep it simple: this is displayed in the customer's calendar.
        l = str(lang or "").lower()
        if l.startswith("en"):
            table = {
                "created": "Appointment created via EasyAgenda.",
                "code": "Code",
                "pro": "Professional",
                "manage": "Manage/confirm",
                "reminder": "Confirmation reminder",
                "confirm_by": "Confirm by",
                "alarm": "Confirm appointment",
            }
        elif l.startswith("fr"):
            table = {
                "created": "Rendez-vous créé via EasyAgenda.",
                "code": "Code",
                "pro": "Professionnel",
                "manage": "Gérer/confirmer",
                "reminder": "Rappel de confirmation",
                "confirm_by": "Confirmer avant",
                "alarm": "Confirmer le rendez-vous",
            }
        elif l.startswith("ca"):
            table = {
                "created": "Cita creada amb EasyAgenda.",
                "code": "Codi",
                "pro": "Professional",
                "manage": "Gestionar/confirmar",
                "reminder": "Recordatori de confirmació",
                "confirm_by": "Confirmar abans de",
                "alarm": "Confirmar cita",
            }
        elif l.startswith("pt"):
            table = {
                "created": "Agendamento criado via EasyAgenda.",
                "code": "Código",
                "pro": "Profissional",
                "manage": "Gerir/confirmar",
                "reminder": "Lembrete de confirmação",
                "confirm_by": "Confirmar até",
                "alarm": "Confirmar agendamento",
            }
        else:  # es default
            table = {
                "created": "Cita creada con EasyAgenda.",
                "code": "Código",
                "pro": "Profesional",
                "manage": "Gestionar/confirmar",
                "reminder": "Recordatorio de confirmación",
                "confirm_by": "Confirmar antes de",
                "alarm": "Confirmar cita",
            }
        return table.get(label_key, label_key)

    uid = f"easya-{int(est.id)}-{int(appointment_id)}@easyaagenda"
    summary = f"{service_name} · {business_name}".strip()
    booking_code = f"EA-{int(appointment_id)}"
    booking_link = _booking_link_for_slug(getattr(est, "slug", ""))

    description_parts = ["Agendamento criado via EasyAgenda."]
    description_parts = [_i18n("created")]
    description_parts.append(f"{_i18n('code')}: {booking_code}.")
    if professional_name:
        description_parts.append(f"{_i18n('pro')}: {professional_name}.")
    description_parts.append(f"{_i18n('manage')}: {booking_link}.")
    if send_at_local is not None:
        try:
            description_parts.append(
                _i18n("reminder") + ": "
                + send_at_local.strftime("%Y-%m-%d %H:%M")
                + "."
            )
        except Exception:
            pass
    if confirm_by_local is not None:
        try:
            description_parts.append(
                _i18n("confirm_by") + ": "
                + confirm_by_local.strftime("%Y-%m-%d %H:%M")
                + "."
            )
        except Exception:
            pass
    description = " ".join(description_parts)

    def _choose_confirmation_alarm_trigger(
        *,
        now_local: datetime,
        start_local: datetime,
        send_at_local: Optional[datetime],
    ) -> Optional[datetime]:
        """Pick an alarm time to remind the customer to confirm.

        Goal: always include a VALARM for future appointments.
        - Prefer the computed send_at_local when it is in the future.
        - Otherwise, use a conservative fallback: 36h, 4h, 1h or 15m before.
        """

        # 1) Prefer the policy-driven reminder time.
        if send_at_local is not None:
            try:
                if send_at_local > now_local:
                    return send_at_local
            except Exception:
                pass

        # 2) Fallback: relative reminders before the appointment.
        try:
            delta = start_local - now_local
            if delta.total_seconds() <= 0:
                return None

            if delta >= timedelta(hours=36, minutes=10):
                offset = timedelta(hours=36)
            elif delta >= timedelta(hours=4, minutes=10):
                offset = timedelta(hours=4)
            elif delta >= timedelta(hours=1, minutes=10):
                offset = timedelta(hours=1)
            elif delta >= timedelta(minutes=25):
                offset = timedelta(minutes=15)
            else:
                # If the appointment is very soon, still create a near-immediate alarm.
                offset_minutes = max(1, int(delta.total_seconds() // 60) - 1)
                offset = timedelta(minutes=offset_minutes)

            trigger_at = start_local - offset

            # Ensure it's not in the past.
            if trigger_at <= now_local:
                trigger_at = now_local + timedelta(minutes=1)

            # Keep it before the event start.
            if trigger_at >= start_local:
                trigger_at = start_local - timedelta(minutes=1)

            return trigger_at
        except Exception:
            return None

    alarm_trigger_at = _choose_confirmation_alarm_trigger(
        now_local=now_local,
        start_local=start_local,
        send_at_local=send_at_local,
    )

    ics_text = _build_ics_event(
        uid=uid,
        summary=summary,
        description=description,
        dtstart=start_local,
        dtend=end_local,
        url=booking_link,
        alarm_trigger_at=alarm_trigger_at,
        alarm_description=_i18n("alarm"),
    )
    filename = f"agendamento-{ag.data_hora.strftime('%Y%m%d-%H%M')}.ics"

    return Response(
        content=ics_text,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
    )


def _generate_time_slots(
    start_time: dt_time,
    end_time: dt_time,
    interval_min: int,
) -> List[str]:
    slots: List[str] = []
    current = datetime.combine(datetime.today().date(), start_time)
    end_dt = datetime.combine(datetime.today().date(), end_time)
    while current < end_dt:
        slots.append(current.strftime("%H:%M"))
        current += timedelta(minutes=interval_min)
    return slots


@router.get("/availability")
def get_availability(
    date: str = Query(..., description="Data YYYY-MM-DD"),
    service_id: int = Query(...),
    professional_id: Optional[int] = Query(None),
    slug: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Calcula horários livres para um serviço em um dia.

    Implementação simples: janela 09:00-18:00, passo = display_interval_min.
    """
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Data inválida, use YYYY-MM-DD")

    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=400, detail="Serviço não encontrado")

    est = _get_single_estabelecimento(db, slug=slug)

    setup_row = db.query(SetupProfile).filter(SetupProfile.estabelecimento_id == est.id).first()
    setup_payload = setup_row.payload if setup_row else None

    trial_status = compute_trial_status(setup_payload)
    if trial_status.expired:
        _trial_raise_expired(status=trial_status)

    tz, _tz_name = resolve_timezone(setup_payload if isinstance(setup_payload, dict) else None)
    now_local = datetime.now(tz)

    confirmation_policy = _extract_confirmation_policy(setup_payload)

    day_start_time, day_end_time, closed_reason = _business_day_window(est, target_date, setup_payload)

    prof_windows_multi = _extract_prof_day_windows_multi(setup_payload)
    prof_workdays = _extract_prof_workdays(setup_payload)
    weekday_key = _weekday_key_monday_first(target_date)

    if professional_id is not None:
        profissionais = db.query(Funcionario).filter(
            Funcionario.id == professional_id,
            Funcionario.estabelecimento_id == est.id,
        ).all()
    else:
        profissionais = db.query(Funcionario).filter(
            Funcionario.estabelecimento_id == est.id
        ).all()

    interval = service.display_interval_min or 30

    if closed_reason is not None or day_start_time is None or day_end_time is None:
        availability_items = [
            {
                "professional_id": str(p.id),
                "professional_name": p.nome,
                "slots": [],
            }
            for p in profissionais
        ]
        return {
            "ok": True,
            "date": date,
            "service_id": str(service_id),
            "availability": availability_items,
            "closed": True,
            "closed_reason": closed_reason,
        }

    # Multi-window business hours (horário quebrado)
    biz_windows, _ = _business_day_windows(est, target_date, setup_payload)

    duration_total = service.duration_min + (service.buffer_min or 0)

    break_start_t, break_end_t = _extract_break_window(setup_payload)
    break_start_dt = datetime.combine(target_date, break_start_t) if break_start_t and break_end_t else None
    break_end_dt = datetime.combine(target_date, break_end_t) if break_start_t and break_end_t else None

    availability_items = []

    for prof in profissionais:
        # Respeitar especialidade: profissional pode não oferecer este serviço
        try:
            if not _prof_allows_service(setup_payload, prof, service):
                availability_items.append(
                    {
                        "professional_id": str(prof.id),
                        "professional_name": prof.nome,
                        "slots": [],
                    }
                )
                continue
        except Exception:
            pass

        # Respeitar dias de trabalho do profissional (se configurado)
        try:
            pname_key = _normalize_name_key(getattr(prof, "nome", ""))
            wd = prof_workdays.get(pname_key)
            if isinstance(wd, dict) and weekday_key in wd and not bool(wd.get(weekday_key)):
                availability_items.append(
                    {
                        "professional_id": str(prof.id),
                        "professional_name": prof.nome,
                        "slots": [],
                    }
                )
                continue
        except Exception:
            pass

        # Aplicar janela de trabalho do profissional (se configurada) — suporta broken hours
        grace_min = _extract_end_of_shift_grace_minutes(setup_payload, prof=prof)

        windows = biz_windows
        try:
            pname = _normalize_name_key(getattr(prof, "nome", ""))
            pw = prof_windows_multi.get(pname)
            if pw:
                windows = _intersect_windows(pw, biz_windows)
        except Exception:
            windows = biz_windows

        base_slots = _generate_time_slots_for_windows(windows, interval)

        biz_break_start_dt = break_start_dt
        biz_break_end_dt = break_end_dt

        prof_break_start_dt = None
        prof_break_end_dt = None
        pbs_t, pbe_t = _extract_break_window_for_prof(setup_payload, prof)
        if pbs_t and pbe_t:
            prof_break_start_dt = datetime.combine(target_date, pbs_t)
            prof_break_end_dt = datetime.combine(target_date, pbe_t)

        # Buscar agendamentos do dia para este profissional
        day_start = datetime.combine(target_date, dt_time.min)
        day_end = datetime.combine(target_date, dt_time.max)
        ags = (
            db.query(Agendamento)
            .filter(
                Agendamento.funcionario_id == prof.id,
                Agendamento.data_hora >= day_start,
                Agendamento.data_hora <= day_end,
            )
            .all()
        )
        free_slots: List[str] = []
        # Gerar slots candidatos no passo display_interval_min e aceitar
        # somente se não houver conflito (service.duration + buffer) com agendamentos existentes.
        # Além disso, garantir espaçamento por profissional entre slots aceitos
        # usando duration_total (duration + buffer) para evitar apresentar
        # inícios que se sobrepõem no mesmo profissional.
        last_added: datetime | None = None
        for s in base_slots:
            start_dt = datetime.strptime(f"{date} {s}", "%Y-%m-%d %H:%M")
            end_dt = start_dt + timedelta(minutes=duration_total)

            # Filtro de confirmação (SMS): só oferecer horários que ainda conseguem ser confirmados.
            if tz:
                start_local = start_dt.replace(tzinfo=tz)
            else:
                start_local = start_dt
            if not _slot_passes_confirmation_filter(now_local=now_local, slot_start_local=start_local, policy=confirmation_policy):
                continue

            # Não permitir horários que estendam o atendimento para além do fim da janela
            end_limit = _slot_end_limit_for_windows(day=target_date, windows=windows, start_dt=start_dt, grace_min=grace_min)
            if end_limit is None or end_dt > end_limit:
                continue

            # Respeitar pausas (negócio + profissional) bloqueando qualquer sobreposição
            if biz_break_start_dt and biz_break_end_dt and biz_break_start_dt < biz_break_end_dt:
                if not (end_dt <= biz_break_start_dt or start_dt >= biz_break_end_dt):
                    continue
            if prof_break_start_dt and prof_break_end_dt and prof_break_start_dt < prof_break_end_dt:
                if not (end_dt <= prof_break_start_dt or start_dt >= prof_break_end_dt):
                    continue

            # Respeitar espaçamento entre os slots aceitos para este profissional
            if last_added and start_dt < (last_added + timedelta(minutes=duration_total)):
                continue

            conflict = False
            for ag in ags:
                if ag.service:
                    dur = ag.service.duration_min + (ag.service.buffer_min or 0)
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

        availability_items.append(
            {
                "professional_id": str(prof.id),
                "professional_name": prof.nome,
                "slots": free_slots,
            }
        )

    return {
        "ok": True,
        "date": date,
        "service_id": str(service_id),
        "availability": availability_items,
    }


@router.get("/occupancy")
def get_occupancy(
    from_: str = Query("from", alias="from"),
    to: str = Query(...),
    service_id: int = Query(...),
    professional_id: Optional[int] = Query(None),
    slug: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Retorna vagas por dia (free_slots + estado free/mid/busy).

    Usa a mesma lógica básica de availability para contar quantos slots livres existem.
    """
    try:
        start_date = datetime.strptime(from_, "%Y-%m-%d").date()
        end_date = datetime.strptime(to, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Datas inválidas, use YYYY-MM-DD")

    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=400, detail="Serviço não encontrado")

    est = _get_single_estabelecimento(db, slug=slug)

    if professional_id is not None:
        profissionais = db.query(Funcionario).filter(
            Funcionario.id == professional_id,
            Funcionario.estabelecimento_id == est.id,
        ).all()
    else:
        profissionais = db.query(Funcionario).filter(
            Funcionario.estabelecimento_id == est.id
        ).all()

    interval = service.display_interval_min or 30
    duration_total = service.duration_min + (service.buffer_min or 0)

    # capacidade baseada no setup (clientes/dia) — se existir, preferimos isso
    setup_row = db.query(SetupProfile).filter(SetupProfile.estabelecimento_id == est.id).first()
    setup_payload = setup_row.payload if setup_row else None
    # timezone + política de confirmação (para refletir corretamente o que é "bookável")
    tz, _tz_name = resolve_timezone(setup_payload if isinstance(setup_payload, dict) else None)
    now_local = datetime.now(tz)
    confirmation_policy = _extract_confirmation_policy(setup_payload)

    cap_default, cap_per_prof = _extract_capacity(setup_payload)
    open_days, holidays = _extract_open_days_and_holidays(setup_payload)
    prof_workdays = _extract_prof_workdays(setup_payload)
    prof_windows_multi = _extract_prof_day_windows_multi(setup_payload)

    days = []
    current = start_date
    while current <= end_date:
        # também fechar por feriado/dia da semana no modo slots
        biz_windows, closed_reason = _business_day_windows(est, current, setup_payload)
        if closed_reason is not None or not biz_windows:
            days.append(
                {
                    "date": current.isoformat(),
                    "free_slots": 0,
                    "total_slots": 0,
                    "occupancy_percent": 100.0,
                    "state": "closed",
                    "closed_reason": closed_reason,
                }
            )
            current += timedelta(days=1)
            continue

        # CAPACITY MODE: usa "clientes/dia" ao invés de slots por horário
        if cap_default is not None or cap_per_prof:
            # fechar por feriado ou dia da semana (estabelecimento)
            weekday_key = _weekday_key_monday_first(current)
            is_holiday = current.isoformat() in holidays
            is_open_day = True
            if open_days is not None:
                is_open_day = bool(open_days.get(weekday_key, False))

            if is_holiday or not is_open_day:
                days.append(
                    {
                        "date": current.isoformat(),
                        "free_slots": 0,
                        "total_slots": 0,
                        "booked_count": 0,
                        "occupancy_percent": 100.0,
                        "state": "closed",
                        "closed_reason": "holiday" if is_holiday else "weekday_closed",
                    }
                )
                current += timedelta(days=1)
                continue

            # capacidade total depende do(s) profissional(is) selecionado(s)
            total_slots = 0
            for prof in profissionais:
                # especialidade: ignorar profissionais que não fazem este serviço
                try:
                    if not _prof_allows_service(setup_payload, prof, service):
                        continue
                except Exception:
                    pass
                pname = _normalize_name_key(getattr(prof, "nome", ""))
                # respeitar dias de trabalho do profissional (se configurado)
                wd = prof_workdays.get(pname)
                if isinstance(wd, dict) and weekday_key in wd and not bool(wd.get(weekday_key)):
                    continue
                total_slots += cap_per_prof.get(pname, cap_default if cap_default is not None else 0)

            day_start = datetime.combine(current, dt_time.min)
            day_end = datetime.combine(current, dt_time.max)
            prof_ids = [p.id for p in profissionais]

            ags = (
                db.query(Agendamento)
                .filter(
                    Agendamento.funcionario_id.in_(prof_ids),
                    Agendamento.data_hora >= day_start,
                    Agendamento.data_hora <= day_end,
                )
                .all()
            )
            booked_count = sum(1 for a in ags if _is_counted_appointment_status(getattr(a, "status", None)))

            if total_slots <= 0:
                free_slots = 0
                occupancy_percent = 100.0
                state = "busy"
            else:
                booked_ratio = min(1.0, booked_count / float(total_slots))
                occupancy_percent = round(100.0 * booked_ratio, 1)
                free_slots = max(total_slots - booked_count, 0)

                if free_slots == 0 or booked_ratio >= 0.95:
                    state = "busy"
                elif booked_ratio >= 0.70:
                    state = "mid"
                else:
                    state = "free"

            days.append(
                {
                    "date": current.isoformat(),
                    "free_slots": int(free_slots),
                    "total_slots": int(total_slots),
                    "booked_count": int(booked_count),
                    "occupancy_percent": float(occupancy_percent),
                    "state": state,
                }
            )
            current += timedelta(days=1)
            continue

        base_slots = _generate_time_slots_for_windows(biz_windows, interval)

        # Para occupancy queremos contar quantos "horários de início" diferentes
        # ainda têm pelo menos um profissional disponível, e não todas as
        # combinações profissional x horário. Isso evita números como 54 para
        # um dia (18 horários x 3 profissionais) e reflete melhor a percepção
        # do cliente final.
        total_free = 0
        total_slots = 0

        # Limite por janela (não contar horários que extrapolam o fim da janela)
        break_start_t, break_end_t = _extract_break_window(setup_payload)
        break_start_dt = datetime.combine(current, break_start_t) if break_start_t and break_end_t else None
        break_end_dt = datetime.combine(current, break_end_t) if break_start_t and break_end_t else None

        break_dt_by_prof: dict[int, tuple[datetime, datetime]] = {}
        # janelas de trabalho por profissional (horário) para este dia
        prof_windows_by_id: dict[int, list[tuple[dt_time, dt_time]]] = {}
        prof_grace_by_id: dict[int, int] = {}
        weekday_key = _weekday_key_monday_first(current)

        active_profs: list[Funcionario] = []
        for prof in profissionais:
            # especialidade: ignorar profissionais que não fazem este serviço
            try:
                if not _prof_allows_service(setup_payload, prof, service):
                    continue
            except Exception:
                pass
            # respeitar dias de trabalho do profissional (se configurado)
            pname = _normalize_name_key(getattr(prof, "nome", ""))
            wd = prof_workdays.get(pname)
            if isinstance(wd, dict) and weekday_key in wd and not bool(wd.get(weekday_key)):
                continue

            # janela padrão é a do estabelecimento (pode ser multi-window);
            # pode ser sobrescrita pelo setup do profissional.
            p_windows = biz_windows
            try:
                if pname and pname in prof_windows_multi:
                    p_windows = _intersect_windows(prof_windows_multi[pname], biz_windows)
            except Exception:
                p_windows = biz_windows
            prof_windows_by_id[int(prof.id)] = p_windows
            prof_grace_by_id[int(prof.id)] = _extract_end_of_shift_grace_minutes(setup_payload, prof=prof)
            active_profs.append(prof)

            pbs_t, pbe_t = _extract_break_window_for_prof(setup_payload, prof)
            if pbs_t and pbe_t:
                try:
                    break_dt_by_prof[int(prof.id)] = (datetime.combine(current, pbs_t), datetime.combine(current, pbe_t))
                except Exception:
                    continue

        # Pré-carregar agendamentos do dia para todos os profissionais
        ags_by_prof = {}
        day_start = datetime.combine(current, dt_time.min)
        day_end = datetime.combine(current, dt_time.max)
        for prof in active_profs:
            ags = (
                db.query(Agendamento)
                .filter(
                    Agendamento.funcionario_id == prof.id,
                    Agendamento.data_hora >= day_start,
                    Agendamento.data_hora <= day_end,
                )
                .all()
            )
            ags_by_prof[prof.id] = ags

        for s in base_slots:
            start_dt = datetime.combine(current, datetime.strptime(s, "%H:%M").time())
            end_dt = start_dt + timedelta(minutes=duration_total)

            # Filtro de confirmação (mesma lógica de /availability)
            if tz:
                start_local = start_dt.replace(tzinfo=tz)
            else:
                start_local = start_dt
            if not _slot_passes_confirmation_filter(now_local=now_local, slot_start_local=start_local, policy=confirmation_policy):
                continue

            # Ignorar horários cujo atendimento serviço+buffer passaria além do fim da janela do estabelecimento
            biz_end_limit = _slot_end_limit_for_windows(day=current, windows=biz_windows, start_dt=start_dt, grace_min=0)
            if biz_end_limit is None or end_dt > biz_end_limit:
                continue

            if break_start_dt and break_end_dt and break_start_dt < break_end_dt:
                if not (end_dt <= break_start_dt or start_dt >= break_end_dt):
                    continue

            total_slots += 1

            slot_free_for_someone = False
            for prof in active_profs:
                # respeitar janelas do profissional (horário)
                p_windows = prof_windows_by_id.get(int(prof.id)) or []
                p_end_limit = _slot_end_limit_for_windows(
                    day=current,
                    windows=p_windows,
                    start_dt=start_dt,
                    grace_min=int(prof_grace_by_id.get(int(prof.id), 0) or 0),
                )
                if p_end_limit is None or end_dt > p_end_limit:
                    continue

                ags = ags_by_prof.get(prof.id, [])

                # pausa do profissional (não bloqueia o slot inteiro, só este profissional)
                bwin = break_dt_by_prof.get(int(prof.id))
                if bwin and bwin[0] < bwin[1]:
                    if not (end_dt <= bwin[0] or start_dt >= bwin[1]):
                        continue

                conflict = False
                for ag in ags:
                    if ag.service:
                        dur = ag.service.duration_min + (ag.service.buffer_min or 0)
                    else:
                        dur = 60
                    ex_start = ag.data_hora
                    ex_end = ex_start + timedelta(minutes=dur)
                    if not (end_dt <= ex_start or start_dt >= ex_end):
                        conflict = True
                        break

                if not conflict:
                    slot_free_for_someone = True
                    break

            if slot_free_for_someone:
                total_free += 1

        if total_slots <= 0:
            state = "busy"
            occupancy_percent = 100.0
        else:
            free_ratio = total_free / float(total_slots)
            occupancy_percent = round(100.0 * (1.0 - free_ratio), 1)

            # faixas simples e previsíveis para UI
            if total_free == 0 or free_ratio <= 0.10:
                state = "busy"
            elif free_ratio <= 0.40:
                state = "mid"
            else:
                state = "free"

        days.append(
            {
                "date": current.isoformat(),
                "free_slots": total_free,
                "total_slots": total_slots,
                "occupancy_percent": occupancy_percent,
                "state": state,
            }
        )
        current += timedelta(days=1)

    return {
        "ok": True,
        "from_date": start_date.isoformat(),
        "to_date": end_date.isoformat(),
        "service_id": str(service_id),
        "professional_id": str(professional_id) if professional_id is not None else "",
        "days": days,
    }
