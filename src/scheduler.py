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
from datetime import datetime, timedelta, timezone
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

    def next_peak(self, now: datetime = None, reserved=None) -> datetime:
        """Next peak slot in the future (tz-aware, DST-correct).

        reserved: optional iterable of tz-aware datetimes already spoken for
        (e.g. publish slots claimed by another run in the shared ML store).
        Matching slots are skipped so two runs never target the same
        publish minute — the root cause of the observed double-post bug.
        """
        reserved = list(reserved or [])
        now = now or datetime.now(self.tz)
        # scan today + next 7 days until a free, future peak is found
        for days_ahead in range(0, 8):
            base = now + timedelta(days=days_ahead)
            day = base.strftime("%A").lower()
            hours = self.peaks.get(day, [12, 20])
            for h in sorted(hours):
                target = base.replace(hour=h, minute=0, second=0, microsecond=0)
                if days_ahead == 0 and target <= now:
                    continue
                if not self._claimed(target, reserved):
                    return target
        # unreachable in practice: 8 days x 4 peaks all reserved
        return (now + timedelta(days=1)).replace(hour=12, minute=0,
                                                 second=0, microsecond=0)

    @staticmethod
    def _claimed(target: datetime, reserved: list) -> bool:
        """True if `target` collides (within 30 min) with a reserved slot."""
        for r in reserved:
            if isinstance(r, str):
                try:
                    r = datetime.fromisoformat(r)
                except ValueError:
                    continue
            if r.tzinfo is None:
                r = r.replace(tzinfo=timezone.utc)
            if abs((target.astimezone(timezone.utc) -
                    r.astimezone(timezone.utc)).total_seconds()) < 1800:
                return True
        return False

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
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
        return elapsed >= min_hours


if __name__ == "__main__":
    for p in ("youtube", "facebook", "instagram"):
        s = PlatformScheduler(p)
        print(f"{p:10} next peak: {s.next_peak().isoformat()}  "
              f"({s.next_peak().strftime('%A %I:%M %p %Z')})")
