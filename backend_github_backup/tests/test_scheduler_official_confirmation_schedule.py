from datetime import datetime

import pytest

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None


@pytest.mark.skipif(ZoneInfo is None, reason="zoneinfo not available")
def test_official_confirmation_schedule_morning_appointment():
    from app.services.scheduler import _official_confirmation_schedule_local

    tz = ZoneInfo("Europe/Madrid")
    appt_local = datetime(2026, 2, 10, 10, 0, tzinfo=tz)

    send_local, deadline_local, window_h = _official_confirmation_schedule_local(appt_local, setup_payload={})

    assert send_local == datetime(2026, 2, 9, 14, 0, tzinfo=tz)
    assert deadline_local == datetime(2026, 2, 9, 17, 0, tzinfo=tz)
    assert window_h == pytest.approx(3.0)


@pytest.mark.skipif(ZoneInfo is None, reason="zoneinfo not available")
def test_official_confirmation_schedule_afternoon_appointment():
    from app.services.scheduler import _official_confirmation_schedule_local

    tz = ZoneInfo("Europe/Madrid")
    appt_local = datetime(2026, 2, 10, 16, 0, tzinfo=tz)

    send_local, deadline_local, window_h = _official_confirmation_schedule_local(appt_local, setup_payload={})

    assert send_local == datetime(2026, 2, 9, 17, 0, tzinfo=tz)
    assert deadline_local == datetime(2026, 2, 9, 20, 0, tzinfo=tz)
    assert window_h == pytest.approx(3.0)
