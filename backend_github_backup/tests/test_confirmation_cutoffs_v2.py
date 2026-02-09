from datetime import datetime

import pytest

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None


def _policy_payload_v2(**overrides):
    confirmation = {
        "minLeadHours": 0,
        "immediateHorizonHours": 36,
        "immediateWindowHours": 4,
        "quietHoursStart": "00:00",
        "quietHoursEnd": "00:00",
        "cutoffsEnabled": True,
        "morningEndTime": "12:00",
        "afternoonEndTime": "17:00",
        "morningCutoffPrevDay": "20:00",
        "afternoonCutoffSameDay": "12:00",
        "nightCutoffSameDay": "16:00",
        "minConfirmWindowHours": 2,
        "capBeforeStartHours": 2,
        "allowSameDay": True,
        "allowSameDayNightOnly": False,
    }
    confirmation.update(overrides)
    return {"business": {"confirmation": confirmation}}


@pytest.mark.skipif(ZoneInfo is None, reason="zoneinfo not available")
def test_cutoff_blocks_tomorrow_morning_after_20():
    from app.api.booking.routes import _extract_confirmation_policy, _slot_passes_confirmation_filter

    tz = ZoneInfo("Europe/Madrid")
    now_local = datetime(2026, 2, 1, 21, 0, tzinfo=tz)
    slot_start = datetime(2026, 2, 2, 9, 0, tzinfo=tz)

    policy = _extract_confirmation_policy(_policy_payload_v2())
    assert not _slot_passes_confirmation_filter(now_local=now_local, slot_start_local=slot_start, policy=policy)


@pytest.mark.skipif(ZoneInfo is None, reason="zoneinfo not available")
def test_cutoff_blocks_same_day_morning_after_previous_day_cutoff():
    from app.api.booking.routes import _extract_confirmation_policy, _slot_passes_confirmation_filter

    tz = ZoneInfo("Europe/Madrid")
    now_local = datetime(2026, 2, 2, 2, 0, tzinfo=tz)
    slot_start = datetime(2026, 2, 2, 9, 0, tzinfo=tz)

    policy = _extract_confirmation_policy(_policy_payload_v2())
    assert not _slot_passes_confirmation_filter(now_local=now_local, slot_start_local=slot_start, policy=policy)


@pytest.mark.skipif(ZoneInfo is None, reason="zoneinfo not available")
def test_cutoff_allows_tomorrow_afternoon_even_after_20():
    from app.api.booking.routes import _extract_confirmation_policy, _slot_passes_confirmation_filter

    tz = ZoneInfo("Europe/Madrid")
    now_local = datetime(2026, 2, 1, 21, 0, tzinfo=tz)
    slot_start = datetime(2026, 2, 2, 16, 0, tzinfo=tz)

    policy = _extract_confirmation_policy(_policy_payload_v2())
    assert _slot_passes_confirmation_filter(now_local=now_local, slot_start_local=slot_start, policy=policy)


@pytest.mark.skipif(ZoneInfo is None, reason="zoneinfo not available")
def test_min_confirm_window_blocks_short_window_due_to_start_minus_2h_cap():
    from app.api.booking.routes import _extract_confirmation_policy, _slot_passes_confirmation_filter

    tz = ZoneInfo("Europe/Madrid")
    now_local = datetime(2026, 2, 2, 10, 0, tzinfo=tz)
    slot_start = datetime(2026, 2, 2, 13, 0, tzinfo=tz)

    policy = _extract_confirmation_policy(_policy_payload_v2())
    assert not _slot_passes_confirmation_filter(now_local=now_local, slot_start_local=slot_start, policy=policy)
