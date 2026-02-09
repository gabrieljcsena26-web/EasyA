from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


TRIAL_DAYS_DEFAULT = 4


@dataclass(frozen=True)
class TrialStatus:
    active_plan: bool
    started: bool
    expired: bool
    start_utc: datetime | None
    end_utc: datetime | None


def _parse_dt(v: Any) -> datetime | None:
    if not v:
        return None
    s = str(v).strip()
    if not s:
        return None
    # Accept ISO strings with 'Z'
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _trial_block_is_disabled(setup_payload: dict | None) -> bool:
    payload = setup_payload if isinstance(setup_payload, dict) else {}
    trial = payload.get("trial") if isinstance(payload.get("trial"), dict) else {}
    # Manual override to unblock once the client has paid.
    # Can be set via /admin/setup or advanced JSON config.
    if bool(trial.get("active_plan")):
        return True
    if bool(trial.get("disabled")):
        return True
    return False


def compute_trial_status(setup_payload: dict | None, *, trial_days: int = TRIAL_DAYS_DEFAULT, now_utc: datetime | None = None) -> TrialStatus:
    payload = setup_payload if isinstance(setup_payload, dict) else {}

    if _trial_block_is_disabled(payload):
        return TrialStatus(active_plan=True, started=True, expired=False, start_utc=None, end_utc=None)

    trial = payload.get("trial") if isinstance(payload.get("trial"), dict) else {}
    start_utc = _parse_dt(trial.get("start_utc"))
    end_utc = _parse_dt(trial.get("end_utc"))

    started = start_utc is not None

    # Backfill end if missing.
    if started and end_utc is None:
        try:
            end_utc = start_utc + timedelta(days=int(trial_days))
        except Exception:
            end_utc = start_utc + timedelta(days=TRIAL_DAYS_DEFAULT)

    now = now_utc or _now_utc()
    expired = bool(end_utc and now > end_utc)

    return TrialStatus(active_plan=False, started=started, expired=expired, start_utc=start_utc, end_utc=end_utc)


def ensure_trial_started(setup_payload: dict | None, *, trial_days: int = TRIAL_DAYS_DEFAULT, now_utc: datetime | None = None) -> tuple[dict, TrialStatus]:
    payload = setup_payload if isinstance(setup_payload, dict) else {}

    # If plan active/disabled gating, don't mutate.
    if _trial_block_is_disabled(payload):
        status = compute_trial_status(payload, trial_days=trial_days, now_utc=now_utc)
        return payload, status

    trial = payload.get("trial") if isinstance(payload.get("trial"), dict) else {}
    start_utc = _parse_dt(trial.get("start_utc"))

    if start_utc is None:
        now = now_utc or _now_utc()
        start_utc = now
        end_utc = now + timedelta(days=int(trial_days))
        trial = dict(trial)
        trial["start_utc"] = start_utc.isoformat()
        trial["end_utc"] = end_utc.isoformat()
        payload = dict(payload)
        payload["trial"] = trial

    status = compute_trial_status(payload, trial_days=trial_days, now_utc=now_utc)
    return payload, status
