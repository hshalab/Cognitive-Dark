#!/usr/bin/env python3
"""
Coercion Files — Mission Control (V2.8).

Weekly autonomous health + growth review. THE MANAGER of the operation.

  • Checks ML memory integrity (store + event log) and reports instantly if
    memory is at risk — with the exact repair command.
  • Audits platform health (quarantines), posting cadence (missed windows),
    publish-slot claims, momentum (hot/slump), and monetization progress.
  • Runs a GROWTH PLAYBOOK audit — every lever a 2026 creator needs to grow
    fast, marked ✅ (on) / ⚠️ (off) / ❌ (blocked), so the owner sees exactly
    which lever to pull next.
  • Produces `data/health_report.md` (human-readable) and prints a summary.

IMPORTANT: this script is READ-ONLY on the ML store (no race with the daily
pipeline — the store has exactly one writer). It only writes the report file.

Usage:
  python scripts/mission_control.py
"""

import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("mission_control")

from config.settings import DATA_DIR, USA_STYLE
from ml_engine import LearningSystem

REPORT_PATH = DATA_DIR / "health_report.md"


def _fmt_dt(iso: str) -> str:
    if not iso:
        return "-"
    try:
        dt = datetime.fromisoformat(str(iso))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return str(iso)


def audit(ml: LearningSystem) -> tuple[list[str], list[str]]:
    """Return (problems, ok_lines)."""
    problems, ok = [], []
    now = datetime.now(timezone.utc)

    # 1) ML memory integrity
    if not ml.store_ok:
        problems.append("❌ ML store BROKEN — memory at risk. Run: "
                        "python scripts/repair_data_files.py --apply")
    else:
        ok.append("✅ ML store healthy (arms=%d, videos=%d, attributed=%d)"
                  % (len(ml.data["arms"]), len(ml.data["videos"]),
                     len(ml.data["attribution"])))
        if ml.data.get("rebuilt_from_events"):
            problems.append("⚠️ ML store was REBUILT from event log — original file "
                            "was corrupt; watch the next CI run.")

    # 2) Event log (the diary) present?
    ep = ml.events_path
    if ep.exists():
        n = sum(1 for _ in ep.open(encoding="utf-8")) if ep.stat().st_size else 0
        ok.append(f"✅ Event diary present ({n} events) — memory is recoverable")
    else:
        problems.append("⚠️ No event diary found — memory has no rebuild fallback yet")

    # 3) Platform health / quarantines
    for plat in ("youtube", "facebook", "instagram"):
        h = ml.data.get("health", {}).get(plat, {})
        fails = h.get("failures", 0)
        healthy = h.get("healthy", True)
        if fails >= 3 or not healthy:
            problems.append(f"❌ {plat}: QUARANTINED ({fails} failures) — last: "
                            f"{h.get('last_reason', '-')[:120]}")
        elif fails:
            ok.append(f"⚠️ {plat}: {fails} recent failure(s) — still active")
        else:
            ok.append(f"✅ {plat}: healthy")

    # 4) Posting cadence (last 7 days) — consistency is THE 2026 growth lever
    log = ml.data.get("post_log", {})
    days = [(now.date() - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    for plat in ("youtube", "facebook", "instagram"):
        counts = [log.get(d, {}).get(plat, {}).get("count", 0) for d in days]
        total = sum(counts)
        if total == 0:
            problems.append(f"❌ {plat}: ZERO posts in the last 7 days — cadence broken")
        elif total < 7:
            problems.append(f"⚠️ {plat}: only {total} posts in 7 days — consistency "
                            "is the #1 growth lever, push daily")
        else:
            ok.append(f"✅ {plat}: {total} posts in 7 days (daily cadence on)")

    # 5) Publish-slot claims (double-post protection active?)
    claims = {p: len(c) for p, c in ml.data.get("publish_claims", {}).items() if c}
    if claims:
        ok.append(f"✅ Publish-slot ledger active: {claims}")
    else:
        ok.append("• No pending publish claims right now (normal)")

    # 6) Momentum
    series = []
    for r in ml.data.get("reward_log", [])[-15:]:
        series.append((r.get("ts", ""), r.get("reward", 0)))
    for p in ml.data.get("penalty_log", [])[-15:]:
        series.append((p.get("ts", ""), -abs(p.get("penalty", 0))))
    series.sort(key=lambda x: x[0])
    tail = [v for _, v in series[-4:]]
    wins = sum(1 for v in tail if v > 0.5)
    if wins >= 3:
        ok.append("🔥 Hot streak — keep the winning formulas, double down")
    elif sum(1 for v in tail if v <= 0.2) >= 3:
        problems.append("❄️ Slump — ML will explore fresh formulas; consider one "
                        "different pillar this week (variety)")
    else:
        ok.append("• Momentum steady — learning continues")

    # 7) Monetization progress
    try:
        prog = json.loads((DATA_DIR / "monetization_progress.json").read_text(encoding="utf-8"))
        for plat in ("youtube", "facebook", "instagram"):
            b = prog.get(plat, {})
            pct = b.get("pct", {})
            if not pct:
                problems.append(f"• {plat}: no monetization snapshot yet")
                continue
            pct_str = "; ".join(f"{k} {v}%" for k, v in pct.items())
            ok.append(f"• {plat} monetization: {pct_str}")
    except (OSError, json.JSONDecodeError) as exc:
        problems.append(f"⚠️ monetization_progress.json unreadable ({exc})")

    # 8) Growth playbook — the levers that actually grow a 2026 channel
    ok.append("")
    ok.append("**📈 GROWTH PLAYBOOK audit**")
    ok.append("- Hook in first 3s: " + ("✅ ON" if USA_STYLE.get("hook_seconds", 2.2) <= 3 else "⚠️ tune"))
    ok.append("- Fast cuts / USA style: ✅ ON (built-in)")
    ok.append("- SEO titles + power words: ✅ ON (seo.py)")
    ok.append("- Cross-platform reuse (1 video → YT/FB/IG): ✅ ON")
    ok.append("- Daily consistency: see cadence check above")
    ok.append("- Reply to comments (community signal): ⚠️ manual — reply daily")
    ok.append("- CTA 'follow/subscribe' inside video: ⚠️ verify last upload has it")
    if ml.data.get("health", {}).get("instagram", {}).get("failures", 0) >= 3:
        ok.append("- Instagram linked + permissioned: ❌ BLOCKED — fix Meta linking "
                  "(this kills 1/3 of growth)")
    return problems, ok


def main() -> int:
    ml = LearningSystem()
    problems, ok = audit(ml)

    lines = [
        "# 🛰️ Mission Control — Health & Growth Report",
        "",
        f"*Generated: {datetime.now(timezone.utc).isoformat()}*",
        "",
        "## Status",
        "",
    ]
    if problems:
        lines.append("**Problems found:**")
        for p in problems:
            lines.append(f"- {p}")
        lines.append("")
    if ok:
        lines.append("**Checks:**")
        for o in ok:
            lines.append(f"- {o}")
    lines += [
        "",
        "## What to do next (owner actions)",
        "",
    ]
    if any("QUARANTINED" in p for p in problems) or \
       any("instagram" in p and "BLOCKED" in p for p in problems):
        lines.append("1. **Fix the blocked platform** (usually Meta/IG account linking "
                     "or token permissions) — a dead platform is lost growth.")
    if any("cadence broken" in p for p in problems):
        lines.append("2. **Restore daily posting** — run the Daily Pipeline; consistency "
                     "is the strongest 2026 algorithm signal.")
    if any("store BROKEN" in p for p in problems):
        lines.append("3. **Repair ML memory** — `python scripts/repair_data_files.py --apply`.")
    if not any(("cadence broken" in p) or ("QUARANTINED" in p) or ("store BROKEN" in p)
               for p in problems):
        lines.append("1. **Keep the cadence** — Daily Pipeline already on schedule.")
        lines.append("2. **Reply to comments** daily (10 min) — it compounds reach.")
        lines.append("3. **Next milestone**: check monetization_progress.json targets.")
    lines += [
        "",
        "---",
        "_Auto-generated by scripts/mission_control.py. ML store is READ-ONLY here; "
        "no learning data is modified._",
    ]

    try:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = REPORT_PATH.with_suffix(".tmp")
        tmp.write_text("\n".join(lines), encoding="utf-8")
        import os
        os.replace(tmp, REPORT_PATH)
    except OSError as exc:
        print(f"Could not write {REPORT_PATH}: {exc}")
        return 1

    print("\n".join(lines))
    print(f"\n→ Report saved to {REPORT_PATH}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
