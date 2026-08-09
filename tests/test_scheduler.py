"""Tests for the DST-aware platform scheduler."""
from datetime import datetime, timedelta, timezone

from scheduler import TZ, PlatformScheduler


def test_next_peak_is_future_and_tz_aware():
    for p in ("youtube", "facebook", "instagram"):
        nxt = PlatformScheduler(p).next_peak()
        assert nxt.tzinfo is not None
        assert nxt > datetime.now(nxt.tzinfo)


def test_next_peak_uses_tomorrow_when_all_passed():
    # 23:59 on a day whose last peak already passed → tomorrow
    late = datetime(2026, 8, 3, 23, 59, tzinfo=TZ)  # Monday
    nxt = PlatformScheduler("youtube").next_peak(now=late)
    assert nxt.day == 4  # Tuesday
    assert nxt.hour == 7


def test_validate_gap_with_none():
    s = PlatformScheduler()
    assert s.validate_gap(None) is True


def test_validate_gap_naive_datetime_treated_utc():
    s = PlatformScheduler()
    old = datetime.now(timezone.utc) - timedelta(hours=10)
    assert s.validate_gap(old, min_hours=6) is True
    recent = datetime.now(timezone.utc) - timedelta(hours=1)
    assert s.validate_gap(recent, min_hours=6) is False


def test_cron_utc_times_produces_entries():
    s = PlatformScheduler("youtube")
    crons = s.cron_utc_times()
    # 7 days x 4 peaks = 28
    assert len(crons) == 28
    for c in crons:
        parts = c.split()
        assert len(parts) == 5
        assert parts[2] == "*" and parts[3] == "*"  # day/month always


def test_next_peak_skips_reserved_slot():
    """V2.7: a peak already claimed by another run must be skipped — this is
    the direct fix for two runs scheduling the same publish minute."""
    tz = TZ
    now = datetime(2026, 8, 3, 9, 0, tzinfo=tz)  # Monday 9:00
    # Monday peaks for youtube: [7, 12, 17, 20] → next is 12:00
    s = PlatformScheduler("youtube")
    assert s.next_peak(now=now).hour == 12
    # ...but if 12:00 is already claimed, we must get 17:00 instead
    reserved = [datetime(2026, 8, 3, 12, 0, tzinfo=tz)]
    nxt = s.next_peak(now=now, reserved=reserved)
    assert nxt.hour == 17

    # reserved can also arrive as ISO strings (what the ML store persists)
    reserved_iso = ["2026-08-03T12:00:00-04:00"]
    assert s.next_peak(now=now, reserved=reserved_iso).hour == 17

    # with both 12:00 and 17:00 taken → 20:00, then tomorrow 7:00
    reserved3 = [datetime(2026, 8, 3, h, tzinfo=tz) for h in (12, 17)]
    assert s.next_peak(now=now, reserved=reserved3).hour == 20
    reserved4 = [datetime(2026, 8, 3, h, tzinfo=tz) for h in (12, 17, 20)]
    assert s.next_peak(now=now, reserved=reserved4).day == 4  # Tuesday
    assert s.next_peak(now=now, reserved=reserved4).hour == 7
