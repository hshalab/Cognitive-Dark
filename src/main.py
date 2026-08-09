#!/usr/bin/env python3
"""
Cognitive Dark V2.1 — Multi-Platform Pipeline Orchestrator.

  Script(Groq) → Clips(Pexels/Pixabay) → Voice(Kokoro) → Video(MoviePy)
  → Upload(YouTube + Facebook + Instagram) → ML feedback → Monetization tracker

Every stage runs inside the auto-repair StageRunner (retries + fallbacks).
The ML engine picks the content strategy and is updated with outcomes —
V2.1: rewards/penalties land on the EXACT arm that produced the video,
daily caps + min-gap guards protect platform health, and every published
video_id is attributed back to its formula so real analytics train the bandit.
"""

import argparse
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from auto_repair import Preflight, RepairJournal, StageRunner, cleanup, selftest
from clips_downloader import prepare_clips
from config.settings import MIN_POST_GAP_HOURS, PLATFORMS
from ml_engine import LearningSystem, text_sha
from monetization_tracker import update_progress
from scheduler import PlatformScheduler
from script_generator import generate_script
from seo import build_platform_package
from tts_engine import generate_voice_segments, release_tts
from video_builder import build_short, generate_thumbnail


def _platform_uploaders(dry_run: bool) -> dict:
    from platforms.facebook import FacebookUploader
    from platforms.instagram import InstagramUploader
    from platforms.youtube import YouTubeUploader
    return {
        "youtube": YouTubeUploader(dry_run=dry_run),
        "facebook": FacebookUploader(dry_run=dry_run),
        "instagram": InstagramUploader(dry_run=dry_run),
    }


def run_pipeline(platforms: list = None, dry_run: bool = False,
                 pillar: str = None, topic: str = None) -> dict:
    start = time.time()
    platforms = platforms or [p for p, c in PLATFORMS.items() if c["enabled"]]

    # ── auto-repair: journal + stale-state repair (V2.1: repair BEFORE start) ──
    journal = RepairJournal()
    journal.repair_if_crashed()          # detect a crashed PREVIOUS run first
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    journal.start_run(run_id, "short_pipeline")
    cleanup(older_than_hours=24)

    # ── preflight ──
    Preflight().run(check_deps=True)
    logger.info("🚀 COGNITIVE DARK V2.1 — platforms=%s dry_run=%s",
                ",".join(platforms), dry_run)

    # ── ML engine ──
    ml = LearningSystem()

    # Warm-start the bandit with market intelligence once (idempotent: real
    # per-video evidence is never overwritten). Falls back to curated patterns.
    try:
        from market_intel import analyze, priors_for_bandit
        _analysis = analyze()
        _priors = priors_for_bandit(_analysis)
        existing = sum(1 for a in ml.data["arms"].values() if a.get("n", 0) > 0)
        if existing < len(_priors) * 3:
            ml.apply_seed_priors(priors=_priors, source=_analysis["source"])
            logger.info("🌡 Market intel: %d patterns from %s",
                        len(_priors), _analysis["source"])
    except Exception as exc:
        logger.warning("Market intel warm-start skipped: %s", exc)

    # Strategy director — auto-tune epsilon, voice speed, cadence from results
    try:
        from strategy_director import StrategyDirector
        director = StrategyDirector(ml=ml)
        director.decide()
        director.apply_to_env()
        # Reload cfg overrides (epsilon may have changed from env)
        env_eps = os.environ.get("CD_EPSILON")
        if env_eps:
            ml.cfg["epsilon"] = float(env_eps)
    except Exception as exc:
        logger.warning("Strategy director skipped: %s", exc)
        director = None

    # ── BRAIN ADAPTATION (War Mode) ──
    if os.environ.get("WAR_MODE", "false").lower() == "true" and not pillar and not topic:
        try:
            from autonomous_brain import get_brain
            brain = get_brain()
            decision = brain.decide_next_video()
            pillar = decision["pillar"]
            topic = decision["topic"]
            logger.info("🧠 Autonomous Brain decided: %s (%s)", topic, pillar)
        except Exception as e:
            logger.warning("Brain decision failed: %s", e)

    # ── 1. Script (ML-chosen strategy) ──
    runner = StageRunner(max_retries=2)
    script = runner.run(generate_script, "script", [], pillar_key=pillar,
                        topic=topic, ml=ml)
    logger.info("📝 %s [%s/%s] (%s)", script["title"], script["pillar"],
                script["hook_style"], script["source"])
    arm = script.get("arm_key")  # V2.1: the EXACT arm travels with the script

    # ── dedup & variation guard (retry w/ new strategy) ──
    guard = ml.dedup_guard(" ".join(s["caption"] for s in script["scenes"]),
                           script.get("hook", ""))
    retries = 0
    while not guard["allowed"] and retries < 4:
        logger.warning("⛔ Too-similar content (%s) → retrying with fresh strategy (%d)",
                       guard["reason"], retries + 1)
        if arm:
            ml.apply_penalty(arm, "dedup_blocked", 0.3)
        script = generate_script(ml=ml, topic=topic)
        arm = script.get("arm_key")
        guard = ml.dedup_guard(" ".join(s["caption"] for s in script["scenes"]),
                               script.get("hook", ""))
        retries += 1
    if not guard["allowed"]:
        logger.error("⛔ Could not produce unique content after 4 attempts")
        journal.finish_run(run_id, "blocked", guard["reason"])
        return {"success": False, "reason": guard["reason"]}

    # ── 2. Clips (Pexels → Pixabay → procedural) — 3 DISTINCT cuts per scene ──
    clip_sets = prepare_clips(script["scenes"], per_scene=3)
    scene_visuals = [[c["path"] for c in s] for s in clip_sets]
    logger.info("🎞️  Clips: %s (%d scenes x %d cuts)",
                ", ".join(sorted({c["source"] for s in clip_sets for c in s})),
                len(scene_visuals), len(scene_visuals[0]) if scene_visuals else 0)

    # ── 3. Voice (Kokoro → edge → elevenlabs → silence) ──
    segments = generate_voice_segments(script["scenes"])
    narration_s = sum(s["duration"] for s in segments)
    logger.info("🎙️  Narration: %.1fs", narration_s)

    # V2.5 SHORTS CAP GUARD: >60s = NOT a Short on YouTube; IG/FB Reels also
    # favor <60s. Trim trailing scenes (clips+audio together) to stay 40-58s.
    while narration_s > 57 and len(script["scenes"]) > 3:
        script["scenes"].pop()
        narration_s -= segments.pop()["duration"]
        scene_visuals.pop()
    logger.info("✂️  Final scenes: %d (%.1fs narration — Shorts-safe)",
                len(script["scenes"]), narration_s)
    release_tts()  # free the ~300MB Kokoro model before video render

    # ── 4. Video (USA style: fast cuts + word captions + hook overlay) ──
    final_video = build_short(scene_visuals, segments, script["scenes"],
                              hook=script.get("hook", ""))
    thumb = generate_thumbnail(scene_visuals[0][0], script.get("hook", ""))
    logger.info("🎬 Built %s + thumbnail", final_video)

    # ── 5. Upload per platform (algorithm-adapted, volume-guarded) ──
    uploaders = _platform_uploaders(dry_run)
    results = {}
    packs = {}
    caption_text = " ".join(s["caption"] for s in script["scenes"])
    ml.register_video({
        "title": script["title"], "hook": script.get("hook", ""),
        "pillar": script["pillar"], "hook_style": script["hook_style"],
        "arm_key": arm,
        "text_sha": text_sha(caption_text),
        "text": caption_text,
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
        # V2.1: daily cap + min-gap guards (consistency beats bursts)
        allowed, why = ml.can_post(p, cfg.get("max_daily", 3), MIN_POST_GAP_HOURS)
        if not allowed and not dry_run:
            logger.info("⏭️  %s skipped: %s", p, why)
            results[p] = {"platform": p, "ok": False, "skipped": True, "reason": why}
            continue

        pkg = build_platform_package(script, p,
                                     durations=[s["duration"] for s in segments])
        packs[p] = pkg
        sched = PlatformScheduler(p)
        # V2.7: CLAIM the publish slot BEFORE uploading. If another run (e.g.
        # cron + manual dispatch in the same window) already claimed this
        # peak, next_peak() is asked for the next free one. This closes the
        # "two videos go public at the same minute" double-post bug.
        claimed = False
        publish_at = sched.next_peak(reserved=ml.claimed_peaks(p))
        if not dry_run:
            for _ in range(6):
                ok_claim, why = ml.claim_publish(p, publish_at, run_id)
                if ok_claim:
                    claimed = True
                    break
                logger.warning("⛔ %s: %s → trying next free peak", p, why)
                publish_at = sched.next_peak(
                    reserved=[*ml.claimed_peaks(p), publish_at])
        try:
            res = uploaders[p].upload(final_video, thumb, pkg,
                                      publish_at=publish_at.isoformat())
            results[p] = res
            if res.get("ok"):
                ml.report_success(p)
                if not res.get("dry_run"):
                    ml.record_post(p)
                    # V2.1: attribute the published id back to the formula
                    vid = res.get("video_id") or res.get("post_id") or res.get("media_id")
                    if vid and arm:
                        ml.record_video_id(p, vid, arm, script["title"])
            elif res.get("skipped"):
                # not a real mistake — just missing config; don't penalize the ML
                logger.info("ℹ️  %s: skipped (config) — no ML penalty", p.upper())
            else:
                if claimed:
                    ml.release_claim(p, publish_at)  # failed — free the slot
                ml.report_failure(p, res.get("error") or res.get("reason", "unknown"))
                if arm:
                    ml.apply_penalty(arm, f"{p}_upload_failed",
                                     ml.cfg["penalty_failure"], platform=p)
        except Exception as exc:
            if claimed:
                ml.release_claim(p, publish_at)
            logger.error("Platform %s raised: %s", p, exc)
            ml.report_failure(p, str(exc))
            if arm:
                ml.apply_penalty(arm, f"{p}_raised",
                                 ml.cfg["penalty_failure"], platform=p)
            results[p] = uploaders[p].result(False, error=str(exc))

    # ── 5b. Content pack for manual posting (CI artifact) ──
    # V2.6: while the IG API link propagates, the runner exposes video +
    # thumbnail + per-platform captions as a downloadable artifact so the
    # owner can post manually in ~1 minute.
    try:
        import json as _json
        with open(os.path.join("output", "seo_packages.json"), "w",
                  encoding="utf-8") as fh:
            _json.dump({"title": script["title"], "hook": script.get("hook", ""),
                        "packages": packs}, fh, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.warning("content pack write failed: %s", exc)

    # ── 6. ML feedback for strong output (rewards on the EXACT arm) ──
    for p, res in results.items():
        if res.get("ok") and not res.get("dry_run") and arm:
            ml.apply_reward(arm, f"{p}_published",
                            ml.cfg["bonus_consistent"], platform=p)
            # Real performance metrics arrive via scripts/fetch_metrics.py,
            # which credits this video's arm through the attribution map.
    ml.save()

    # ── 7. Monetization progress snapshot (non-destructive merge) ──
    update_progress()

    journal.finish_run(run_id, "success",
                       "; ".join(f"{p}:{'OK' if r.get('ok') else 'FAIL'}"
                                 for p, r in results.items()))
    elapsed = time.time() - start
    logger.info("✅ DONE in %.0fs — %s", elapsed, script["title"])
    return {"success": True, "run_id": run_id, "results": results,
            "title": script["title"], "elapsed_s": round(elapsed, 1)}


def main():
    ap = argparse.ArgumentParser(description="Cognitive Dark V2.1 pipeline")
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
        # V2.7 SECURITY: never persist raw exceptions — platform API errors can
        # embed access tokens in the URL (same sanitizer the ML engine uses).
        journal.data.setdefault("current", {}).update(
            {"status": "crashed",
             "error": LearningSystem._sanitize_reason(str(exc))})
        journal._write()
        sys.exit(1)


if __name__ == "__main__":
    main()
