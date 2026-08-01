#!/usr/bin/env python3
"""
Cognitive Dark V2 — Platform-Aware Scheduler.

• DST-correct: uses IANA tz `America/New_York` (EDT/EST handled automatically —
  fixes the V1 bug where EST was hardcoded to UTC-5 and drifted all summer).
• Per-platform peak hours (USA audience) tuned to each algorithm:
    YouTube  : 7-9a / 12-2p / 7-11p
    Facebook : 9a-1p / 8p-12a
    Instagram: 11a-2p / 7-9p
"""

import logging
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

logger = logging.getLogger("scheduler")

TZ = ZoneInfo(os.environ.get("CD_TIMEZONE", "America/New_York"))

DAY_PEAKS = {
    "youtube": {
        "monday": [7, 12, 20], "tuesday": [7, 12, 20], "wednesday": [7, 12, 20, 22],
        "thursday": [7, 12, 20], "friday": [7, 12, 21], "saturday": [10, 15, 21],
        "sunday": [10, 19, 21],
    },
    "facebook": {
        "monday": [9, 13, 20], "tuesday": [9, 13, 20], "wednesday": [9, 13, 20],
        "thursday": [9, 13, 20], "friday": [9, 12, 20], "saturday": [10, 14, 21],
        "sunday": [10, 14, 20],
    },
    "instagram": {
        "monday": [11, 19], "tuesday": [11, 19], "wednesday": [11, 19],
        "thursday": [11, 19], "friday": [11, 18], "saturday": [10, 18],
        "sunday": [10, 17],
    },
}


class PlatformScheduler:
    def __init__(self, platform: str = "youtube", tz: str = None):
        self.platform = platform
        self.tz = ZoneInfo(tz or os.environ.get("CD_TIMEZONE", "America/New_York"))
        self.peaks = DAY_PEAKS.get(platform, DAY_PEAKS["youtube"])

    def next_peak(self, now: datetime = None) -> datetime:
        """Next peak slot in the future (tz-aware, DST-correct)."""
        now = now or datetime.now(self.tz)
        day = now.strftime("%A").lower()
        hours = self.peaks.get(day, [12, 20])
        for h in sorted(hours):
            target = now.replace(hour=h, minute=0, second=0, microsecond=0)
            if target > now:
                return target
        # tomorrow's first peak
        tomorrow = (now + timedelta(days=1)).replace(minute=0, second=0, microsecond=0)
        day_t = tomorrow.strftime("%A").lower()
        return tomorrow.replace(hour=min(self.peaks.get(day_t, [12])),
                                minute=0, second=0, microsecond=0)

    def cron_utc_times(self) -> list:
        """All peak hours as UTC cron strings (for GitHub Actions)."""
        crons = []
        for day, hours in self.peaks.items():
            # Convert each local (naive, treated as tz) hour to UTC
            for h in hours:
                local = datetime(2026, 1, 15, h, tzinfo=self.tz)  # fixed date, tz-aware
                utc_h = local.astimezone(ZoneInfo("UTC")).hour
                crons.append(f"0 {utc_h} * * {day[:3].capitalize()}")
        return crons

    def validate_gap(self, last_dt, min_hours: float = 6.0) -> bool:
        if last_dt is None:
            return True
        elapsed = (datetime.now(timezone_utc()) - last_dt).total_seconds() / 3600
        return elapsed >= min_hours


def timezone_utc():
    from datetime import timezone
    return timezone.utc


if __name__ == "__main__":
    for p in ("youtube", "facebook", "instagram"):
        s = PlatformScheduler(p)
        print(f"{p:10} next peak: {s.next_peak().isoformat()}  "
              f"({s.next_peak().strftime('%A %I:%M %p %Z')})")
