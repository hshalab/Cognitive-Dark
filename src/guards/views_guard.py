#!/usr/bin/env python3
"""ViewsGuard — REAL platform performance se video ko judge karta hai.

Ye woh guard hai jo system ko dead formulas repeat karne se rokta hai:

  • Formula (arm) ke 3+ REAL outcomes hain aur real mean < 0.4
    → FAIL: "ye formula real data mein fail ho chuka hai — pivot karo"
  • Formula ki recent credited videos mein 0 views + 0 likes streak
    (metrics fetch ho chuke) → FAIL
  • 3 se kam real outcomes → PASS with honest note ("monitoring")
  • Platform quarantined (ML store health) → FAIL
  • Metrics pipeline configured nahi → WARN (reward source hai)

Prior ko "performance" nahi maana jaata — sirf real outcomes count hote
hain. Is guard ki wajah se bandit ke seeded beliefs kabhi publish ki ijazat
nahi dete jab reality un ke khilaf ho.
"""

from __future__ import annotations

import os

from guards.base import BaseGuard

MIN_REAL_N = 3
FAIL_MEAN = 0.4


class ViewsGuard(BaseGuard):
    name = "views"

    def check(self, payload: dict) -> object:
        ml = payload.get("ml")
        arm_key = (payload.get("script") or {}).get("arm_key") or ""
        platform = payload.get("platform") or ""

        if ml is not None and not getattr(ml, "store_ok", True):
            return self._v("FAIL", "ML store broken — posting blocked",
                           {"store_ok": False},
                           fix="python scripts/repair_data_files.py --apply")

        stats = self.observer.arm_real_stats(ml, arm_key)
        recent = self.observer.attributed_recent(ml, arm_key, limit=3)
        quarantined = bool(ml and not ml.platform_healthy(platform))

        # metrics pipeline check (reward ka SOLE source ab ye hi hai)
        metrics_configured = bool(
            os.environ.get("YOUTUBE_CREDENTIALS") or
            os.environ.get("REFRESH_TOKEN") or
            os.environ.get("FB_ACCESS_TOKEN") or
            os.environ.get("IG_ACCESS_TOKEN") or
            os.environ.get("YOUTUBE_API_KEY"))

        issues, warns = [], []
        if quarantined:
            issues.append(f"{platform} quarantined (3+ real failures) — "
                          "upload block")

        n_real = stats["n_real"]
        real_mean = stats["real_mean"]
        if n_real >= MIN_REAL_N and real_mean < FAIL_MEAN:
            issues.append(
                f"formula PROVEN weak: {n_real} real outcomes, mean {real_mean} "
                f"(< {FAIL_MEAN}) — ye formula pivot karo, repeat mat karo")

        zero_streak = 0
        credited = [r for r in recent if r.get("credited")]
        for r in credited:
            m = r.get("metrics") or {}
            if float(m.get("views", 0) or 0) <= 0 and \
                    float(m.get("likes", 0) or 0) <= 0:
                zero_streak += 1
        if credited and zero_streak >= len(credited):
            issues.append(f"last {zero_streak} credited videos = 0 views + 0 likes "
                          "— formula dead, pivot")

        if not metrics_configured:
            warns.append("metrics pipeline (fetch_metrics) ke liye koi token "
                         "configured nahi — rewards ka source band hai")

        evidence = {"platform": platform, **stats,
                    "recent_credited": len(credited),
                    "zero_view_streak": zero_streak,
                    "quarantined": quarantined,
                    "metrics_configured": metrics_configured}

        if issues:
            return self._v("FAIL", "; ".join(issues), evidence,
                           fix="Pillar/hook pivot karo — naya formula test karo. "
                               "Dead formula repeat karna har platform par nuqsan hai.")
        if warns:
            return self._v("WARN", "; ".join(warns), evidence)
        if n_real == 0:
            return self._v("PASS",
                           "no real data yet (n_real=0) — monitoring mein "
                           "jayegi, metrics hi is ka fate decide karenge", evidence)
        return self._v("PASS", f"{n_real} real outcomes, mean {real_mean} "
                               f"(>= {FAIL_MEAN}) — formula working", evidence)
