#!/usr/bin/env python3
"""
Cognitive Dark V2 — Multi-Platform Pipeline Orchestrator.

  Script(Groq) → Clips(Pexels/Pixabay) → Voice(Kokoro) → Video(MoviePy)
  → Upload(YouTube + Facebook + Instagram) → ML feedback → Monetization tracker

Every stage runs inside the auto-repair StageRunner (retries + fallbacks).
The ML engine picks the content strategy and is updated with outcomes
(rewards for strong output, penalties for mistakes) — learning from errors.
"""

import argparse
import json
import logging
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("main")

from config.settings import PLATFORMS
from auto_repair import (Preflight, RepairJournal, StageRunner, cleanup, selftest)
from ml_engine import LearningSystem
from scheduler import PlatformScheduler
from script_generator import generate_script
from clips_downloader import prepare_clips
from tts_engine import generate_voice_segments, release_tts
from video_builder import build_short, generate_thumbnail
from seo import build_platform_package
from monetization_tracker import update_progress


def _platform_uploaders(dry_run: bool) -> dict:
    from platforms.youtube import YouTubeUploader
    from platforms.facebook import FacebookUploader
    from platforms.instagram import InstagramUploader
    return {
        "youtube": YouTubeUploader(dry_run=dry_run),
        "facebook": FacebookUploader(dry_run=dry_run),
        "instagram": InstagramUploader(dry_run=dry_run),
    }


def run_pipeline(platforms: list = None, dry_run: bool = False,
                 pillar: str = None, topic: str = None) -> dict:
    start = time.time()
    platforms = platforms or [p for p, c in PLATFORMS.items() if c["enabled"]]

    # ── auto-repair: journal + stale-state repair ──
    journal = RepairJournal()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    journal.start_run(run_id, "short_pipeline")
    journal.repair_if_crashed()
    cleanup(older_than_hours=24)

    # ── preflight ──
    Preflight().run(check_deps=True)
    logger.info("🚀 COGNITIVE DARK V2 — platforms=%s dry_run=%s",
                ",".join(platforms), dry_run)

    # ── ML engine ──
    ml = LearningSystem()

    # ── 1. Script (ML-chosen strategy) ──
    runner = StageRunner(max_retries=2)
    script = runner.run(generate_script, "script", [], pillar_key=pillar,
                        topic=topic, ml=ml)
    logger.info("📝 %s [%s/%s] (%s)", script["title"], script["pillar"],
                script["hook_style"], script["source"])

    # ── 0% spam-detection: dedup & variation guard (retry w/ new strategy) ──
    guard = ml.dedup_guard(" ".join(s["caption"] for s in script["scenes"]),
                           script.get("hook", ""))
    retries = 0
    while not guard["allowed"] and retries < 4:
        logger.warning("⛔ Too-similar content (%s) → retrying with fresh strategy (%d)",
                       guard["reason"], retries + 1)
        ml.apply_penalty(ml.arm_key(script["pillar"], script["hook_style"], "any"),
                         "dedup_blocked", 0.3)
        script = generate_script(ml=ml, topic=topic)
        guard = ml.dedup_guard(" ".join(s["caption"] for s in script["scenes"]),
                               script.get("hook", ""))
        retries += 1
    if not guard["allowed"]:
        logger.error("⛔ Could not produce unique content after 4 attempts")
        journal.finish_run(run_id, "blocked", guard["reason"])
        return {"success": False, "reason": guard["reason"]}

    # ── 2. Clips (Pexels → Pixabay → procedural) ──
    clips = prepare_clips(script["scenes"])
    clip_paths = [c["path"] for c in clips]
    logger.info("🎞️  Clips: %s", ", ".join(sorted({c["source"] for c in clips})))

    # ── 3. Voice (Kokoro → edge → elevenlabs → silence) ──
    segments = generate_voice_segments(script["scenes"])
    narration_s = sum(s["duration"] for s in segments)
    logger.info("🎙️  Narration: %.1fs", narration_s)
    release_tts()  # free the ~300MB Kokoro model before video render

    # ── 4. Video ──
    final_video = build_short(clip_paths, segments, script["scenes"])
    thumb = generate_thumbnail(clip_paths[0], script.get("hook", ""))
    logger.info("🎬 Built %s + thumbnail", final_video)

    # ── 5. Upload per platform (algorithm-adapted, ML-scheduled) ──
    uploaders = _platform_uploaders(dry_run)
    results = {}
    ml.register_video({
        "title": script["title"], "hook": script.get("hook", ""),
        "pillar": script["pillar"], "hook_style": script["hook_style"],
        "text_sha": __import__("ml_engine", fromlist=["text_sha"]).text_sha(
            " ".join(s["caption"] for s in script["scenes"])),
        "text": " ".join(s["caption"] for s in script["scenes"]),
        "source": script["source"], "run_id": run_id,
    })

    for p in platforms:
        cfg = PLATFORMS.get(p)
        if not cfg or not cfg.get("enabled"):
            logger.info("⏭️  %s disabled in config", p)
            continue
        if not ml.platform_healthy(p):
            logger.warning("⛔ %s quarantined (3+ failures) — skipping", p)
            continue
        pkg = build_platform_package(script, p)
        sched = PlatformScheduler(p)
        publish_at = sched.next_peak().isoformat()
        try:
            res = uploaders[p].upload(final_video, thumb, pkg, publish_at=publish_at)
            results[p] = res
            arm = ml.arm_key(script["pillar"], script["hook_style"],
                             sched.next_peak().strftime("%A").lower())
            if res.get("ok"):
                ml.report_success(p)
            elif res.get("skipped"):
                # not a real mistake — just missing config; don't penalize the ML
                logger.info("ℹ️  %s: skipped (config) — no ML penalty", p.upper())
            else:
                ml.report_failure(p, res.get("error") or res.get("reason", "unknown"))
                ml.apply_penalty(arm, f"{p}_upload_failed", ml.cfg["penalty_failure"])
        except Exception as exc:
            logger.error("Platform %s raised: %s", p, exc)
            ml.report_failure(p, str(exc))
            results[p] = uploaders[p].result(False, error=str(exc))

    # ── 6. ML feedback for strong output (rewards) ──
    for p, res in results.items():
        if res.get("ok") and not res.get("dry_run"):
            arm = ml.arm_key(script["pillar"], script["hook_style"], "any")
            ml.apply_reward(arm, f"{p}_published")
            # A/B hint: freshly-published strong formula keeps its score high;
            # actual metrics arrive via scripts/fetch_metrics.py.

    # ── 7. Monetization progress snapshot ──
    update_progress()

    journal.finish_run(run_id, "success",
                       "; ".join(f"{p}:{'OK' if r.get('ok') else 'FAIL'}"
                                 for p, r in results.items()))
    elapsed = time.time() - start
    logger.info("✅ DONE in %.0fs — %s", elapsed, script["title"])
    return {"success": True, "run_id": run_id, "results": results,
            "title": script["title"], "elapsed_s": round(elapsed, 1)}


def main():
    ap = argparse.ArgumentParser(description="Cognitive Dark V2 pipeline")
    ap.add_argument("--platforms", default=None,
                    help="comma list: youtube,facebook,instagram (default: all enabled)")
    ap.add_argument("--dry-run", action="store_true",
                    help="build everything, never call upload APIs")
    ap.add_argument("--pillar", default=None, help="force a content pillar key")
    ap.add_argument("--topic", default=None, help="force a topic")
    ap.add_argument("--selftest", action="store_true",
                    help="run offline smoke tests and exit")
    ap.add_argument("--simulate", action="store_true",
                    help="simulate ML learning (UCB convergence) and exit")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(0 if selftest() else 1)
    if args.simulate:
        sys.path.insert(0, "src")
        from ml_engine import LearningSystem
        import random as _r
        ls = LearningSystem(store_path=Path("/tmp/ml_sim.json"))
        ls.data["arms"] = {}
        qual = {"pattern_interrupt": .8, "knowledge_gap": .7, "fear_based": .55,
                "curiosity_trigger": .65, "counterintuitive": .6, "dark_revelation": .5,
                "stoic_echo": .75, "red_flag_checklist": .85}
        for _ in range(300):
            s = ls.choose_strategy()
            ls.record_outcome(s["arm_key"], qual[s["hook_style"]] + _r.uniform(-.15, .15))
        print("Top formulas after simulation:")
        for t in ls.best_formulas(6):
            print(f"  {t['pillar']:>16} / {t['hook_style']:<22} mean={t['mean']:.3f} n={t['n']}")
        sys.exit(0)

    platforms = [p.strip() for p in args.platforms.split(",")] if args.platforms else None
    try:
        res = run_pipeline(platforms=platforms, dry_run=args.dry_run,
                           pillar=args.pillar, topic=args.topic)
        if not res.get("success"):
            sys.exit(2)
    except Exception as exc:
        logger.error("Pipeline crashed:\n%s", traceback.format_exc())
        journal = RepairJournal()
        journal.data.setdefault("current", {}).update(
            {"status": "crashed", "error": str(exc)})
        journal._write()
        sys.exit(1)


if __name__ == "__main__":
    main()
