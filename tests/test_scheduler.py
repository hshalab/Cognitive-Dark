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
