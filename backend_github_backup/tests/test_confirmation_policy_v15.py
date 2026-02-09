from datetime import datetime

import pytest

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None


@pytest.mark.skipif(ZoneInfo is None, reason="zoneinfo not available")
def test_confirmation_quiet_hours_allows_tomorrow_afternoon():
    from app.api.booking.routes import _extract_confirmation_policy, _slot_passes_confirmation_filter

    tz = ZoneInfo("Europe/Madrid")
    now_local = datetime(2026, 1, 29, 21, 30, tzinfo=tz)
    slot_start = datetime(2026, 1, 30, 18, 0, tzinfo=tz)

    policy = _extract_confirmation_policy({"confirmation": {}})
    assert _slot_passes_confirmation_filter(now_local=now_local, slot_start_local=slot_start, policy=policy)


@pytest.mark.skipif(ZoneInfo is None, reason="zoneinfo not available")
def test_confirmation_quiet_hours_blocks_tomorrow_morning():
    from app.api.booking.routes import _extract_confirmation_policy, _slot_passes_confirmation_filter

    tz = ZoneInfo("Europe/Madrid")
    now_local = datetime(2026, 1, 29, 21, 30, tzinfo=tz)
    slot_start = datetime(2026, 1, 30, 9, 0, tzinfo=tz)

    policy = _extract_confirmation_policy({"confirmation": {}})
    assert not _slot_passes_confirmation_filter(now_local=now_local, slot_start_local=slot_start, policy=policy)


@pytest.mark.skipif(ZoneInfo is None, reason="zoneinfo not available")
def test_confirmation_before_21_caps_deadline_to_21():
    from app.api.booking.routes import _confirmation_deadline_for_slot, _extract_confirmation_policy, _slot_passes_confirmation_filter

    tz = ZoneInfo("Europe/Madrid")
    now_local = datetime(2026, 1, 29, 19, 30, tzinfo=tz)
    slot_start = datetime(2026, 1, 30, 9, 0, tzinfo=tz)

    policy = _extract_confirmation_policy({"confirmation": {}})
    assert _slot_passes_confirmation_filter(now_local=now_local, slot_start_local=slot_start, policy=policy)

    deadline = _confirmation_deadline_for_slot(now_local=now_local, slot_start_local=slot_start, policy=policy)
    assert deadline is not None
    assert deadline.date().isoformat() == "2026-01-29"
    assert deadline.strftime("%H:%M") == "21:00"


@pytest.mark.skipif(ZoneInfo is None, reason="zoneinfo not available")
def test_confirmation_batch_mode_for_farther_than_36h():
    from app.api.booking.routes import _confirmation_deadline_for_slot, _extract_confirmation_policy, _slot_passes_confirmation_filter

    tz = ZoneInfo("Europe/Madrid")
    now_local = datetime(2026, 1, 29, 10, 0, tzinfo=tz)
    slot_start = datetime(2026, 1, 31, 16, 0, tzinfo=tz)

    policy = _extract_confirmation_policy({"confirmation": {}})
    assert _slot_passes_confirmation_filter(now_local=now_local, slot_start_local=slot_start, policy=policy)

    deadline = _confirmation_deadline_for_slot(now_local=now_local, slot_start_local=slot_start, policy=policy)
    assert deadline is not None
    assert deadline.date().isoformat() == "2026-01-30"
    assert deadline.strftime("%H:%M") == "20:00"


@pytest.mark.skipif(ZoneInfo is None, reason="zoneinfo not available")
def test_confirmation_blocks_slots_under_min_lead():
    from app.api.booking.routes import _extract_confirmation_policy, _slot_passes_confirmation_filter

    tz = ZoneInfo("Europe/Madrid")
    now_local = datetime(2026, 1, 29, 10, 0, tzinfo=tz)
    slot_start = datetime(2026, 1, 29, 13, 30, tzinfo=tz)

    policy = _extract_confirmation_policy({"confirmation": {}})
    assert not _slot_passes_confirmation_filter(now_local=now_local, slot_start_local=slot_start, policy=policy)
