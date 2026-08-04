#!/usr/bin/env python3
"""
Cognitive Dark V2.1 — Metrics Sync (closes the ML learning loop).

Pulls real analytics from all three platforms and:
  1. CREDITS the exact formula behind each published video — every uploaded
     video_id is attributed to its ML arm (see ml_engine.record_video_id);
     here we fetch that video's views/likes/comments and push a reward onto
     the responsible arm, so the bandit genuinely learns what goes viral.
  2. Rewards consistency — channel/page growth applies a small bonus to the
     arms that were recently active.
  3. Updates the monetization progress snapshot.
  4. Writes data/metrics_report.md for a quick human review.

Runs on a schedule in CI. Platforms without tokens are skipped gracefully.

V2.1 fixes:
  • YouTube creds now resolve the SAME way as the uploader (path / raw JSON /
    split GOOGLE_CLIENT_ID+SECRET+REFRESH_TOKEN secrets) — V2 only read
    YOUTUBE_CREDENTIALS, so CI never pulled YT metrics.
  • apply_ml_updates() actually applies rewards (V2's loop body was `pass`).
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("fetch_metrics")

from ml_engine import LearningSystem
from monetization_tracker import update_progress, PROGRESS_PATH


def _resolve_yt_creds():
    """Same resolution rules as platforms/youtube.py (path | JSON | split env)."""
    raw = os.environ.get("YOUTUBE_CREDENTIALS", "")
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    refresh_token = os.environ.get("REFRESH_TOKEN")
    if client_id and client_secret and refresh_token:
        info = {
            "client_id": client_id, "client_secret": client_secret,
            "refresh_token": refresh_token,
            "token_uri": "https://oauth2.googleapis.com/token",
            "scopes": ["https://www.googleapis.com/auth/youtube.readonly"],
            "type": "authorized_user",
        }
        return info
    if not raw:
        return None
    if os.path.exists(raw):
        with open(raw, encoding="utf-8") as fh:
            return json.load(fh)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _yt_service():
    info = _resolve_yt_creds()
    if not info:
        return None
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    creds = Credentials.from_authorized_user_info(info)
    if (creds.expired or not creds.valid) and creds.refresh_token:
        creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)


def youtube_metrics() -> dict:
    """Channel-level subs/views via the Data API."""
    try:
        yt = _yt_service()
        if yt is None:
            return {}
        ch = yt.channels().list(part="statistics", mine=True).execute()["items"][0]
        stats = ch["statistics"]
        return {
            "subs": int(stats.get("subscriberCount", 0)),
            "views": int(stats.get("viewCount", 0)),
            "videos": int(stats.get("videoCount", 0)),
        }
    except Exception as exc:
        logger.warning("YouTube metrics unavailable: %s", exc)
        return {}


def youtube_credit_videos(ml: LearningSystem) -> int:
    """Credit each uncredited, attributed video with its real stats.

    Uses videos().list(part=statistics) which needs no extra scope. Returns
    the number of videos credited.
    """
    ids = [v for v in ml.pending_video_ids("youtube") if str(v) != "dry-run"]
    if not ids:
        return 0
    try:
        yt = _yt_service()
        if yt is None:
            return 0
        credited = 0
        for chunk_start in range(0, len(ids), 50):   # API max 50 ids/call
            chunk = ids[chunk_start:chunk_start + 50]
            resp = yt.videos().list(part="statistics", id=",".join(chunk)).execute()
            for item in resp.get("items", []):
                st = item.get("statistics", {})
                views = int(st.get("viewCount", 0))
                likes = int(st.get("likeCount", 0))
                comments = int(st.get("commentCount", 0))
                # Retention needs the Analytics API (extra scope); approximate
                # engagement with what the Data API gives us.
                ml.credit_video(item["id"], {
                    "views": views, "likes": likes, "comments": comments,
                    "retention": 0.0,
                })
                credited += 1
        return credited
    except Exception as exc:
        logger.warning("YouTube video credit failed: %s", exc)
        return 0


def facebook_metrics() -> dict:
    import requests
    tok, page = os.environ.get("FB_ACCESS_TOKEN", ""), os.environ.get("FB_PAGE_ID", "")
    if not tok or not page:
        return {}
    try:
        r = requests.get(f"https://graph.facebook.com/v25.0/{page}",
                         params={"access_token": tok,
                                 "fields": "fan_count,followers_count"}, timeout=30)
        r.raise_for_status()
        d = r.json()
        return {"followers": d.get("followers_count", d.get("fan_count", 0))}
    except Exception as exc:
        logger.warning("FB metrics unavailable: %s", exc)
        return {}


def instagram_metrics() -> dict:
    import requests
    tok, ig = os.environ.get("IG_ACCESS_TOKEN", ""), os.environ.get("IG_BUSINESS_ACCOUNT_ID", "")
    if not tok or not ig:
        return {}
    try:
        r = requests.get(f"https://graph.instagram.com/v22.0/{ig}",
                         params={"access_token": tok,
                                 "fields": "followers_count,media_count"}, timeout=30)
        r.raise_for_status()
        d = r.json()
        return {"followers": d.get("followers_count", 0)}
    except Exception as exc:
        logger.warning("IG metrics unavailable: %s", exc)
        return {}


def apply_growth_rewards(ml: LearningSystem, prog: dict) -> None:
    """V2.1: real growth now rewards the formulas that were recently active.

    V2's loop body was `pass` — nothing was learned from analytics. Here any
    positive follower/sub growth applies a small consistency bonus to the arms
    behind the most recent posts (best available attribution without paid
    analytics scopes).
    """
    grew = []
    for plat in ("youtube", "facebook", "instagram"):
        growth = prog.get(plat, {}).get("last_growth", 0) or 0
        if growth > 0:
            grew.append((plat, growth))
    if not grew:
        return
    recent = ml.recent_arm_keys(6)
    for plat, growth in grew:
        for arm in recent:
            ml.apply_reward(arm, f"{plat}_growth_{growth}",
                            ml.cfg.get("bonus_consistent", 1.0))
    logger.info("Growth rewards applied: %s → %d recent arms", grew, len(recent))


def main():
    yt = youtube_metrics()
    fb = facebook_metrics()
    ig = instagram_metrics()

    prev = {}
    try:
        prev = json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass

    overrides = {}
    for plat, cur, key in (("youtube", yt, "subs"),
                           ("facebook", fb, "followers"),
                           ("instagram", ig, "followers")):
        if cur:
            overrides[plat] = {
                **cur,
                "last_growth": cur[key] - prev.get(plat, {}).get(key, cur[key]),
            }

    prog = update_progress(overrides=overrides or None)
    ml = LearningSystem()

    # 1) credit individual videos (real views/likes/comments → arm reward)
    n_credited = youtube_credit_videos(ml)
    # 2) reward channel-level growth
    apply_growth_rewards(ml, prog)
    ml.save()

    summary = ml.summary()
    report = Path("data/metrics_report.md")
    report.parent.mkdir(exist_ok=True)
    report.write_text(
        f"# 📊 Cognitive Dark — Metrics Report\n\n"
        f"*Updated: {datetime.now(timezone.utc).isoformat()}*\n\n"
        f"**ML:** {summary['arms_tested']} arms · {summary['videos_tracked']} videos · "
        f"{summary['attributed_videos']} attributed · {summary['rewards']} rewards · "
        f"{summary['penalties']} penalties\n\n"
        f"**Best formulas:** " +
        (", ".join(f"{b['pillar']}/{b['hook_style']} ({b['mean']})"
                   for b in summary["best_formulas"]) or "none yet") + "\n\n"
        f"**Videos credited this run:** {n_credited}\n\n"
        f"```json\n{json.dumps(prog, indent=2, ensure_ascii=False)}\n```\n",
        encoding="utf-8")
    print("Metrics synced →", report)


if __name__ == "__main__":
    main()
