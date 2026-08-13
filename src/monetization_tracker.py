#!/usr/bin/env python3
"""
Coercion Files — Monetization Tracker.

Tracks progress toward platform monetization thresholds (2026 rules) and
computes daily targets for the 30-day plan.

  YouTube  : YPP full = 1,000 subs + 4,000 watch-hrs OR 10M Shorts views/90d
             Tier-1 (fan funding) = 500 subs + 3,000 hrs OR 3M Shorts views/90d
  Facebook : Content Monetization = 5,000 followers + 60k min viewed/60d + 5 uploads/30d
             Stars (first money) = 500 followers
  Instagram: Partner/bonus invites ≈ 500 followers + 60 active days + strong plays

Output: data/monetization_progress.json + prints a daily plan.
"""

import contextlib
import json
import logging
import shutil
from datetime import datetime, timezone

from config.settings import DATA_DIR, MONETIZATION

logger = logging.getLogger("monetization")

PROGRESS_PATH = DATA_DIR / "monetization_progress.json"

# V3.4 HONESTY: pehle hardcoded "subs=7, followers=523" defaults thay — wo
# bina kisi measurement ke asli data ban kar progress % calculate karte thay.
# Ab default 0 hai aur real values sirf fetch_metrics.py se aati hain. Jab
# tak fetch nahi hota, tracker saaf kehta hai ke data missing hai.
DEFAULTS = {
    "youtube": {"subs": 0, "watch_hours": 0, "shorts_views_90d": 0},
    "facebook": {"followers": 0, "minutes_60d": 0, "uploads_30d": 0},
    "instagram": {"followers": 0, "plays_60d": 0, "days_active": 0},
}


def _load_progress() -> dict:
    # V2.8: try main file, then .bak snapshot — never silently lose history.
    for path in (PROGRESS_PATH, PROGRESS_PATH.with_suffix(PROGRESS_PATH.suffix + ".bak")):
        if not path.exists():
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
    return {}


def update_progress(overrides: dict = None) -> dict:
    """Merge latest known metrics (from fetch_metrics.py) and compute plan."""
    prog = _load_progress()
    # V2.1 FIX: fill only MISSING keys with defaults. V2 did
    #   prog[plat].update(DEFAULTS)  which OVERWROTE real fetched values
    #   (e.g. 150 subs → back to 7) on every pipeline run.
    for plat, defs in DEFAULTS.items():
        bucket = prog.setdefault(plat, {})
        for k, v in defs.items():
            bucket.setdefault(k, v)
    for plat, vals in (overrides or {}).items():
        if plat in prog:
            prog[plat].update(vals)
    prog["last_updated"] = datetime.now(timezone.utc).isoformat()

    plan = MONETIZATION
    days = plan["plan_days"]

    yt = prog["youtube"]
    yt_target = plan["youtube"]["full_ytp"]
    yt["pct"] = {
        "subs": min(100, round(yt["subs"] / yt_target["subs"] * 100, 1)),
        "watch_hours": min(100, round(yt["watch_hours"] / yt_target["watch_hours"] * 100, 1)),
        "shorts_views": min(100, round(yt["shorts_views_90d"] / yt_target["shorts_views_90d"] * 100, 1)),
    }
    yt["daily_targets"] = {
        "subs": max(0, int((yt_target["subs"] - yt["subs"]) / days)),
        "shorts_views": max(0, int((yt_target["shorts_views_90d"] - yt["shorts_views_90d"]) / days)),
    }

    fb = prog["facebook"]
    fb_t = plan["facebook"]["cmp"]
    fb["pct"] = {
        "followers": min(100, round(fb["followers"] / fb_t["followers"] * 100, 1)),
        "minutes": min(100, round(fb["minutes_60d"] / fb_t["minutes_60d"] * 100, 1)),
    }
    fb["daily_targets"] = {
        "followers": max(0, int((fb_t["followers"] - fb["followers"]) / days)),
        "minutes": max(0, int((fb_t["minutes_60d"] - fb["minutes_60d"]) / days)),
    }

    ig = prog["instagram"]
    ig_t = plan["instagram"]["partner"]
    ig["pct"] = {"followers": min(100, round(ig["followers"] / ig_t["followers"] * 100, 1))}
    ig["daily_targets"] = {"followers": max(0, int((ig_t["followers"] - ig["followers"]) / days))}

    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        shutil.copy2(PROGRESS_PATH,
                     PROGRESS_PATH.with_suffix(PROGRESS_PATH.suffix + ".bak"))
    # V2.9: milestone roadmap — the NEXT realistic goal per platform, so the
    # system always has a near-term target (not just the far 30-day one).
    prog["milestones"] = milestones(prog)
    with open(PROGRESS_PATH, "w", encoding="utf-8") as fh:
        json.dump(prog, fh, ensure_ascii=False, indent=2)
    return prog


# ── V2.9: milestone roadmap (next achievable target per platform) ──
MILESTONE_LADDER = {
    "youtube": [
        ("YT Tier-1 (fan funding)", {"subs": 500}),
        ("YT YPP (full)", {"subs": 1000, "watch_hours": 4000}),
        ("YT 10M Shorts views (90d)", {"shorts_views_90d": 10_000_000}),
    ],
    "facebook": [
        ("FB Stars (first money)", {"followers": 500}),
        ("FB CMP (in-stream ads)", {"followers": 5000, "minutes_60d": 60_000,
                                    "uploads_30d": 5}),
    ],
    "instagram": [
        ("IG Partner (invite-track)", {"followers": 500, "plays_60d": 3_000_000}),
    ],
}


def milestones(prog: dict) -> dict:
    """Pick the next incomplete milestone per platform + % toward it."""
    out = {}
    for plat, ladder in MILESTONE_LADDER.items():
        bucket = prog.get(plat, {})
        for name, target in ladder:
            # % = min over the required metrics
            pcts = []
            for k, need in target.items():
                have = float(bucket.get(k, 0) or 0)
                pcts.append(min(100.0, have / need * 100))
            pct = round(min(pcts), 1)
            if pct < 100.0:
                out[plat] = {"milestone": name, "pct": pct,
                             "needs": target, "have": {k: bucket.get(k, 0)
                                                       for k in target}}
                break
        else:
            out[plat] = {"milestone": "COMPLETE 🎉", "pct": 100.0, "needs": {},
                         "have": {}}
    return out


def print_plan(prog: dict) -> str:
    lines = []
    lines.append("═" * 60)
    lines.append("🧠 COGNITIVE DARK — 30-DAY MONETIZATION PLAN")
    lines.append("═" * 60)

    yt = prog["youtube"]
    lines.append("\n▶ YOUTUBE  (YPP: 1,000 subs + 4,000 hrs OR 10M Shorts views/90d)")
    lines.append(f"   subs {yt['subs']}/1,000 ({yt['pct']['subs']}%) → need "
                 f"{yt['daily_targets']['subs']}/day")
    lines.append(f"   Shorts views {yt['shorts_views_90d']:,}/10M ({yt['pct']['shorts_views']}%) "
                 f"→ {yt['daily_targets']['shorts_views']:,}/day")
    lines.append(f"   watch hrs {yt['watch_hours']}/4,000 ({yt['pct']['watch_hours']}%)")

    fb = prog["facebook"]
    lines.append("\n▶ FACEBOOK (CMP: 5,000 followers + 60,000 min/60d + 5 uploads/30d)")
    lines.append("   followers %s/5,000 (%s%%) → %s/day"
                 % (fb["followers"], fb["pct"]["followers"], fb["daily_targets"]["followers"]))
    lines.append(f"   minutes {fb['minutes_60d']:,}/60,000 ({fb['pct']['minutes']}%) → "
                 f"{fb['daily_targets']['minutes']}/day")
    lines.append(f"   uploads_30d {fb['uploads_30d']}/5  (Stars need only 500 followers 🎯)")

    ig = prog["instagram"]
    lines.append("\n▶ INSTAGRAM (partner: 500 followers + 60d + strong plays)")
    lines.append("   followers %s/500 (%s%%) → %s/day"
                 % (ig["followers"], ig["pct"]["followers"], ig["daily_targets"]["followers"]))

    lines.append("\n📅 DAILY CADENCE:")
    lines.append("   • 2 Shorts/day x YouTube + 2 Reels/day x FB + 2 Reels/day x IG")
    lines.append("   • 1 long-form (10-15 min) per week on YouTube for watch-hours")
    lines.append("   • Post at platform peak hours (ML schedules these)")
    lines.append("   • Reuse 1 master video across all 3 platforms (native captions)")
    lines.append("\n⚠️ Honest note: going 7 → 1,000 subs + 4,000 hrs in 30 days from a")
    lines.append("   fresh channel is a stretch goal; the realistic 30-day wins are:")
    lines.append("   YouTube Tier-1 (500 subs), FB Stars (500 followers), IG follower base.")
    lines.append("═" * 60)
    return "\n".join(lines)


if __name__ == "__main__":
    prog = update_progress()
    print(print_plan(prog))
