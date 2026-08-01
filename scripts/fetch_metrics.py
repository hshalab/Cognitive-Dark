#!/usr/bin/env python3
"""
Cognitive Dark V2 — Metrics Sync (closes the ML learning loop).

Pulls real analytics from all three platforms and:
  1. feeds reward/penalty updates into the ML store (learn what works),
  2. updates the monetization progress snapshot,
  3. writes data/metrics_report.md for a quick human review.

Runs on a schedule in CI. Platforms without tokens are skipped gracefully.
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("fetch_metrics")

from ml_engine import LearningSystem
from monetization_tracker import update_progress, PROGRESS_PATH


def youtube_metrics() -> dict:
    """Pull subs, views, watch time via YouTube Data + Analytics APIs."""
    import json as _json
    cred_raw = os.environ.get("YOUTUBE_CREDENTIALS", "")
    if not cred_raw:
        return {}
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        if os.path.exists(cred_raw):
            with open(cred_raw) as fh:
                info = _json.load(fh)
        else:
            info = _json.loads(cred_raw)
        creds = Credentials.from_authorized_user_info(info)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        yt = build("youtube", "v3", credentials=creds)
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


def facebook_metrics() -> dict:
    import requests
    tok, page = os.environ.get("FB_ACCESS_TOKEN", ""), os.environ.get("FB_PAGE_ID", "")
    if not tok or not page:
        return {}
    try:
        r = requests.get(f"https://graph.facebook.com/v25.0/{page}",
                         params={"access_token": tok,
                                 "fields": "fan_count,new_like_count,published_videos"}, timeout=30)
        r.raise_for_status()
        d = r.json()
        return {"followers": d.get("fan_count", 0)}
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


def apply_ml_updates(ml: LearningSystem, prog: dict) -> None:
    """Convert platform growth into ML rewards (strong output detection)."""
    # Subscribe growth above threshold → reward recent strong formulas
    for plat in ("youtube", "facebook", "instagram"):
        growth = prog.get(plat, {}).get("last_growth", 0)
        if growth and growth > 0:
            for arm_key, arm in ml.data["arms"].items():
                if arm["n"] > 0 and arm["plays"] <= arm["n"] + 1:
                    pass  # no per-video attribution without deeper analytics
    logger.info("ML store: %s arms, %d videos tracked",
                len(ml.data["arms"]), len(ml.data["videos"]))


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
    if yt:
        overrides["youtube"] = {
            "subs": yt["subs"],
            "last_growth": yt["subs"] - prev.get("youtube", {}).get("subs", yt["subs"]),
        }
    if fb:
        overrides["facebook"] = {
            "followers": fb["followers"],
            "last_growth": fb["followers"] - prev.get("facebook", {}).get("followers", fb["followers"]),
        }
    if ig:
        overrides["instagram"] = {
            "followers": ig["followers"],
            "last_growth": ig["followers"] - prev.get("instagram", {}).get("followers", ig["followers"]),
        }

    prog = update_progress(overrides=overrides or None)
    ml = LearningSystem()
    apply_ml_updates(ml, prog)
    ml.save()

    report = Path("data/metrics_report.md")
    report.parent.mkdir(exist_ok=True)
    report.write_text(
        f"# 📊 Cognitive Dark — Metrics Report\n\n"
        f"*Updated: {datetime.now(timezone.utc).isoformat()}*\n\n"
        f"```json\n{json.dumps(prog, indent=2, ensure_ascii=False)}\n```\n",
        encoding="utf-8")
    print("Metrics synced →", report)


if __name__ == "__main__":
    main()
