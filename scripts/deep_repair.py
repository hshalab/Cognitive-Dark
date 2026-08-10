#!/usr/bin/env python3
"""
Deep SEO & Metadata Repair for Coercion Files (V2.1).

Scans the learning store and channel state, then heals inconsistencies:
  • re-validates the ML store schema (upgrades older versions in place)
  • clears platform quarantines that have gone stale (>48h with no new errors)
  • removes stale temp artifacts the runtime journal may have missed
  • prints a compact health report for the operator

V2.1: fixed the `sys` import-order crash (V2 used `sys.path` before importing
sys) and replaced the empty stub with real repair logic.
"""

import logging
import sys
from pathlib import Path
from datetime import timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("deep-repair")


def heal_ml_store() -> dict:
    """Load + resave the ML store so its schema is upgraded & consistent."""
    from ml_engine import LearningSystem
    ml = LearningSystem()
    healed = {
        "arms": len(ml.data.get("arms", {})),
        "videos": len(ml.data.get("videos", {})),
        "attribution": len(ml.data.get("attribution", {})),
    }
    # Clear stale quarantines (healthy=True again after 48h without failures)
    from datetime import datetime
    now = datetime.now(timezone.utc)
    cleared = []
    for plat, h in ml.data.get("health", {}).items():
        if not h.get("healthy", True):
            try:
                last = datetime.fromisoformat(h.get("last_check"))
                if (now - last).total_seconds() > 48 * 3600:
                    h["healthy"] = True
                    h["failures"] = 0
                    cleared.append(plat)
            except (ValueError, TypeError):
                h["healthy"] = True
                h["failures"] = 0
                cleared.append(plat)
    if cleared:
        logger.info("🩹 Cleared stale quarantines: %s", ", ".join(cleared))
    ml.save()
    healed["cleared_quarantines"] = cleared
    return healed


def clean_stale_tmp(older_hours: float = 24) -> None:
    from auto_repair import cleanup
    cleanup(older_than_hours=older_hours)


def run_deep_repair():
    logger.info("🧠 Brain Scan: analyzing channel + ML state...")
    healed = heal_ml_store()
    logger.info("📦 ML store: %d arms, %d videos, %d attributed",
                healed["arms"], healed["videos"], healed["attribution"])
    clean_stale_tmp()
    logger.info("✅ Deep repair complete.")
    print("Repair complete:", healed)


if __name__ == "__main__":
    run_deep_repair()
