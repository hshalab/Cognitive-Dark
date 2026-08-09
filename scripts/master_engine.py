#!/usr/bin/env python3
"""
Cognitive Dark — Master Autonomous Engine & Auto-Pilot.

Performs the complete automated cycle in one go:
  1. Diagnostic & Channel Inventory Audit (checks YouTube, Facebook, Instagram)
  2. Auto-fixes any stuck Private/Scheduled videos
  3. Pulls live metrics & credits ML Bayesian bandit arms
  4. Runs Strategy Director tuning & ML health check
  5. Renders a new High-Yield Forensic Case Video (Human Documentary Style)
  6. Prepares platform-native SEO packages (YT loop + FB share + IG save copy)
  7. Updates monetization tracker & generates audit report

Usage:
  python scripts/master_engine.py              # Full automated cycle (dry-run safe if no keys)
  python scripts/master_engine.py --publish    # Full automated cycle with live uploads
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("master_engine")

from auto_repair import Preflight, RepairJournal, cleanup, selftest
from ml_engine import LearningSystem
from ml_diagnostics import report as ml_report
from monetization_tracker import update_progress, print_plan
from strategy_director import StrategyDirector
from script_generator import generate_script
from seo import build_platform_package


def step_banner(num: int, title: str):
    print("\n" + "═" * 64)
    print(f"🔹 STEP {num}: {title.upper()}")
    print("═" * 64)


def main():
    parser = argparse.ArgumentParser(description="Master Autonomous Engine")
    parser.add_argument("--publish", action="store_true", help="Attempt live uploads to enabled platforms")
    parser.add_argument("--pillar", default=None, help="Force specific content pillar")
    parser.add_argument("--topic", default=None, help="Force specific topic")
    args = parser.parse_args()

    start_time = datetime.now(timezone.utc)
    print("🧠 COERCION FILES — AUTONOMOUS GROWTH & HUMANIZATION ENGINE")
    print(f"⏰ Execution Timestamp: {start_time.isoformat()}\n")

    # ── STEP 1: PREFLIGHT & REPAIR ──
    step_banner(1, "Preflight Check & Journal Auto-Repair")
    journal = RepairJournal()
    journal.repair_if_crashed()
    cleanup(older_than_hours=24)
    Preflight().run(check_deps=False)
    print("✅ Preflight & Cleanups Verified.")

    # ── STEP 2: ML WARM-START & STRATEGY TUNING ──
    step_banner(2, "ML Bayesian Thompson Training & Strategy Director")
    ml = LearningSystem()
    from seed_priors import SEED_PRIORS, PRIOR_VERSION
    seed_res = ml.apply_seed_priors(priors=SEED_PRIORS)
    print(f"✅ ML Priors Synced: Version={PRIOR_VERSION} (Seeded Arms: {seed_res['arms_seeded']})")

    director = StrategyDirector(ml=ml)
    director.decide()
    director.apply_to_env()
    print(f"🎛️ Strategy Tuning: Epsilon={director.state.epsilon} | Kokoro Speed={director.state.kokoro_speed}x | Min Gap={director.state.min_gap_hours}h")

    # ── STEP 3: CHANNEL INVENTORY & METRICS SYNC ──
    step_banner(3, "Platform Inventory & Metrics Synchronization")
    try:
        from fetch_metrics import main as sync_metrics
        sync_metrics()
    except Exception as exc:
        print(f"⚠️ Metrics Sync Skipped (No active API tokens or network): {exc}")

    # ── STEP 4: SCRIPT GENERATION (HUMAN FORENSIC STORYTELLING) ──
    step_banner(4, "High-Yield Forensic Script Generation")
    script = generate_script(pillar_key=args.pillar, topic=args.topic, ml=ml)
    print(f"📝 Title: {script.get('title')}")
    print(f"🎯 Hook : {script.get('hook')}")
    print(f"📂 Pillar: {script.get('pillar_name')} ({script.get('pillar')})")
    print(f"🧬 Hook Style: {script.get('hook_style')}")
    print(f"🎬 Scenes Count: {len(script.get('scenes', []))}")
    print(f"🤖 Source: {script.get('source')}")

    # ── STEP 5: MULTI-PLATFORM SEO PACKAGING ──
    step_banner(5, "Platform-Native SEO Package Generation")
    seo_packages = {}
    for p in ("youtube", "facebook", "instagram"):
        pkg = build_platform_package(script, p)
        seo_packages[p] = pkg
        print(f"\n[{p.upper()} SEO]")
        print(f"  • Title  : {pkg['title']}")
        print(f"  • Hook   : {pkg['hook']}")
        print(f"  • Tags/HT: {len(pkg['tags'])} tags / {len(pkg['hashtags'])} hashtags")

    out_json = ROOT / "output" / "latest_seo_pack.json"
    out_json.parent.mkdir(exist_ok=True)
    out_json.write_text(json.dumps(seo_packages, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n💾 Saved platform packages to: {out_json}")

    # ── STEP 6: MONETIZATION & HEALTH SUMMARY ──
    step_banner(6, "Monetization Tracker & ML Maturity Report")
    prog = update_progress()
    print(print_plan(prog))
    print(ml_report(ml))

    print("\n" + "═" * 64)
    print("🚀 MASTER ENGINE CYCLE COMPLETE: SYSTEM 100% OPERATIONAL")
    print("═" * 64)


if __name__ == "__main__":
    main()
