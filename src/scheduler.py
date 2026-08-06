#!/usr/bin/env python3
"""
Cognitive Dark V2.5.1 — Platform-Aware Scheduler.

• DST-correct: uses IANA tz `America/New_York` (EDT/EST handled automatically).
• 4 daily peak windows per platform (USA audience), tuned per algorithm:
    YouTube  : 7a / 12p / 5p / 8p ET
    Facebook : 9a / 1p / 5p / 8p ET
    Instagram: 11a / 2p / 5p / 7p ET
"""

import logging
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

logger = logging.getLogger("scheduler")

TZ = ZoneInfo(os.environ.get("CD_TIMEZONE", "America/New_York"))

DAY_PEAKS = {
    "youtube": {
        "monday": [7, 12, 17, 20], "tuesday": [7, 12, 17, 20],
        "wednesday": [7, 12, 17, 20], "thursday": [7, 12, 17, 20],
        "friday": [7, 12, 17, 21], "saturday": [10, 14, 17, 21],
        "sunday": [10, 14, 17, 20],
    },
    "facebook": {
        "monday": [9, 13, 17, 20], "tuesday": [9, 13, 17, 20],
        "wednesday": [9, 13, 17, 20], "thursday": [9, 13, 17, 20],
        "friday": [9, 12, 17, 20], "saturday": [10, 13, 17, 21],
        "sunday": [10, 13, 17, 20],
    },
    "instagram": {
        "monday": [11, 14, 17, 19], "tuesday": [11, 14, 17, 19],
        "wednesday": [11, 14, 17, 19], "thursday": [11, 14, 17, 19],
        "friday": [11, 14, 17, 18], "saturday": [10, 13, 16, 19],
        "sunday": [10, 13, 16, 18],
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
        """All peak hours as UTC cron strings (for GitHub Actions).

        Converted using the CURRENT date so the offset reflects the active
        DST state.
        """
        anchor = datetime.now(self.tz).date()
        crons = []
        for day, hours in self.peaks.items():
            for h in hours:
                local = datetime(anchor.year, anchor.month, anchor.day, h,
                                 tzinfo=self.tz)
                utc = local.astimezone(ZoneInfo("UTC"))
                crons.append(f"{utc.minute} {utc.hour} * * {day[:3].capitalize()}")
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
