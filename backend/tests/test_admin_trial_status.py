from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.database import SessionLocal
from app.models.models import Estabelecimento, SetupProfile

from main import app


def _iso_z(dt: datetime) -> str:
    """Return ISO string using 'Z' for UTC to match common payloads."""
    dt_utc = dt.astimezone(timezone.utc)
    # Keep seconds precision (no microseconds) for stability.
    return dt_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso(dt_s: str | None) -> datetime | None:
    if not dt_s:
        return None
    s = str(dt_s).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _auth_header_for_est(est: Estabelecimento) -> dict:
    token = create_access_token(
        {
            "username": est.slug,
            "slug": est.slug,
            "estabelecimento_id": est.id,
        },
        expires_in_minutes=30,
    )
    return {"Authorization": f"Bearer {token}"}


def _ensure_setup_payload(est_id: int, payload: dict) -> None:
    s = SessionLocal()
    try:
        sp = s.query(SetupProfile).filter(SetupProfile.estabelecimento_id == est_id).first()
        if not sp:
            sp = SetupProfile(estabelecimento_id=est_id, payload=payload)
            s.add(sp)
        else:
            sp.payload = payload
        s.commit()
    finally:
        s.close()


def test_admin_trial_status_not_started():
    client = TestClient(app)

    s = SessionLocal()
    try:
        est = s.query(Estabelecimento).first()
        assert est is not None
        headers = _auth_header_for_est(est)
        est_id = est.id
    finally:
        s.close()

    _ensure_setup_payload(est_id, {"business": {"timezone": "Europe/Madrid"}})

    r = client.get("/admin/trial-status", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    trial = body.get("trial") or {}

    assert trial.get("active_plan") is False
    assert trial.get("started") is False
    assert trial.get("expired") is False
    assert trial.get("start_utc") is None
    assert trial.get("end_utc") is None
    assert trial.get("seconds_left") is None
    assert trial.get("days_left") is None
    assert trial.get("hours_left") is None


def test_admin_trial_status_running_computes_countdown():
    client = TestClient(app)

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=1)
    end = now + timedelta(days=2, hours=3)

    s = SessionLocal()
    try:
        est = s.query(Estabelecimento).first()
        assert est is not None
        headers = _auth_header_for_est(est)
        est_id = est.id
    finally:
        s.close()

    _ensure_setup_payload(
        est_id,
        {
            "trial": {"start_utc": _iso_z(start), "end_utc": _iso_z(end)},
            "business": {"timezone": "Europe/Madrid"},
        },
    )

    r = client.get("/admin/trial-status", headers=headers)
    assert r.status_code == 200
    body = r.json()
    trial = body.get("trial") or {}

    assert trial.get("active_plan") is False
    assert trial.get("started") is True
    assert trial.get("expired") is False

    resp_now = _parse_iso(body.get("now_utc"))
    resp_end = _parse_iso(trial.get("end_utc"))
    assert resp_now is not None
    assert resp_end is not None

    seconds_left = trial.get("seconds_left")
    assert isinstance(seconds_left, int)

    expected = int(max(0, (resp_end - resp_now).total_seconds()))
    # Allow small drift between server/client timestamps.
    assert abs(seconds_left - expected) <= 5

    # Sanity: days/hours should exist and be >= 1.
    assert isinstance(trial.get("days_left"), int)
    assert isinstance(trial.get("hours_left"), int)
    assert trial.get("days_left") >= 1
    assert trial.get("hours_left") >= 1


def test_admin_trial_status_expired_no_countdown_fields():
    client = TestClient(app)

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=10)
    end = now - timedelta(days=1)

    s = SessionLocal()
    try:
        est = s.query(Estabelecimento).first()
        assert est is not None
        headers = _auth_header_for_est(est)
        est_id = est.id
    finally:
        s.close()

    _ensure_setup_payload(
        est_id,
        {
            "trial": {"start_utc": _iso_z(start), "end_utc": _iso_z(end)},
            "business": {"timezone": "Europe/Madrid"},
        },
    )

    r = client.get("/admin/trial-status", headers=headers)
    assert r.status_code == 200
    body = r.json()
    trial = body.get("trial") or {}

    assert trial.get("active_plan") is False
    assert trial.get("started") is True
    assert trial.get("expired") is True

    # Endpoint intentionally omits countdown when expired.
    assert trial.get("seconds_left") is None
    assert trial.get("days_left") is None
    assert trial.get("hours_left") is None


def test_admin_trial_status_active_plan_override_disables_countdown():
    client = TestClient(app)

    s = SessionLocal()
    try:
        est = s.query(Estabelecimento).first()
        assert est is not None
        headers = _auth_header_for_est(est)
        est_id = est.id
    finally:
        s.close()

    _ensure_setup_payload(
        est_id,
        {
            "trial": {"active_plan": True},
            "business": {"timezone": "Europe/Madrid"},
        },
    )

    r = client.get("/admin/trial-status", headers=headers)
    assert r.status_code == 200
    body = r.json()
    trial = body.get("trial") or {}

    assert trial.get("active_plan") is True
    assert trial.get("started") is True
    assert trial.get("expired") is False
    assert trial.get("start_utc") is None
    assert trial.get("end_utc") is None
    assert trial.get("seconds_left") is None
    assert trial.get("days_left") is None
    assert trial.get("hours_left") is None
