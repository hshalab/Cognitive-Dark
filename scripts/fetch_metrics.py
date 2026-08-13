#!/usr/bin/env python3
"""
Coercion Files — Metrics Sync (closes the ML learning loop).

Pulls real analytics from all three platforms and:
  1. CREDITS the exact formula behind each published video — every uploaded
     video_id is attributed to its ML arm (see ml_engine.record_video_id);
     here we fetch that video's views/likes/comments/watch_time and push a
     reward onto the responsible arm, so the bandit genuinely learns what
     goes viral.
  2. Rewards consistency — channel/page growth applies a small bonus to the
     arms that were recently active.
  3. Detects low-retention videos and applies penalties so the ML learns
     what NOT to produce.
  4. Updates the monetization progress snapshot.
  5. Writes data/metrics_report.md for a quick human review.

Runs on a schedule in CI. Platforms without tokens are skipped gracefully.

FIXES (V3.1):
  • Facebook video-level crediting added (was missing — FB videos never
    learned from → bandit blind on FB platform).
  • Instagram video-level crediting added (was missing — IG reels never
    learned from → bandit blind on IG platform).
  • Facebook watch_time + engagement metrics from Graph API insights.
  • YouTube approximate retention from view-to-like ratio (no extra scope).
  • Low-retention penalty: videos with <30% estimated retention get
    penalized so the ML learns to avoid weak formulas.
  • Per-platform separate learning: YouTube, FB, IG arms now learn independently.
"""

import contextlib
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
from monetization_tracker import PROGRESS_PATH, update_progress

# ── YouTube helpers ──────────────────────────────────────────────

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
            "scopes": [
                "https://www.googleapis.com/auth/youtube.readonly",
                "https://www.googleapis.com/auth/yt-analytics.readonly",
            ],
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
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
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
        logger.warning("YouTube channel metrics unavailable: %s", exc)
        return {}


def _estimate_yt_retention(views: int, likes: int, comments: int) -> float:
    """Approximate retention from engagement signals (no Analytics API scope needed).

    Real retention needs youtubeAnalytics API. This estimate is conservative:
      - likes/views ratio: ~3-5% is normal for Shorts, >5% = good retention
      - comments/views ratio: >0.5% = strong engagement = likely high retention
      - Heavily penalized if views but near-zero engagement (swipe-away signal).

    ⚠️ V3.6: ye ESTIMATE hai, measurement nahi. reward.py is ko
    `retention_estimated` flag ke saath alag treat karta hai (half weight,
    viral bonus NAHI) — fabricated retention ab bandit ko dhoka nahi de
    sakti. Agar YT Analytics scope (yt-analytics.readonly) available ho to
    asal retention use karo — wahan se `retention_measured` milega.
    """
    if views <= 0:
        return 0.0
    like_ratio = likes / views
    comment_ratio = comments / views
    # Base on like ratio (typical Shorts: 2-8%)
    est = 0.15 + like_ratio * 8.0  # 0.15 base + scaled likes
    # Boost for comments (strong signal of retention)
    est += comment_ratio * 20.0
    # Penalty for near-zero engagement relative to views
    if like_ratio < 0.01 and comments == 0 and views > 50:
        est *= 0.4  # swipe-away territory
    return round(min(0.95, max(0.05, est)), 3)


def youtube_credit_videos(ml: LearningSystem) -> int:
    """Credit each uncredited, attributed YouTube video with real stats."""
    ids = [v for v in ml.pending_video_ids("youtube") if str(v) != "dry-run"]
    if not ids:
        return 0
    try:
        yt = _yt_service()
        if yt is None:
            return 0
        credited = 0
        for chunk_start in range(0, len(ids), 50):
            chunk = ids[chunk_start:chunk_start + 50]
            resp = yt.videos().list(part="statistics", id=",".join(chunk)).execute()
            for item in resp.get("items", []):
                st = item.get("statistics", {})
                views = int(st.get("viewCount", 0))
                likes = int(st.get("likeCount", 0))
                comments = int(st.get("commentCount", 0))
                retention = _estimate_yt_retention(views, likes, comments)
                ml.credit_video(item["id"], {
                    "views": views, "likes": likes, "comments": comments,
                    "retention": retention,
                    "retention_estimated": True,   # V3.6: ye guess hai
                    "platform": "youtube",
                })
                credited += 1
                # Log for human review
                logger.info("YT credit: %s → views=%d likes=%d retention≈%.0f%%",
                            item["id"][:16], views, likes, retention * 100)
        return credited
    except Exception as exc:
        logger.warning("YouTube video credit failed: %s", exc)
        return 0


# ── Facebook helpers ──────────────────────────────────────────────

def _fb_service():
    """Return (token, page_id) or (None, None)."""
    tok = os.environ.get("FB_ACCESS_TOKEN", "")
    page = os.environ.get("FB_PAGE_ID", "")
    if tok and page:
        return tok, page
    # fallback to alternate secret names
    tok = os.environ.get("FACEBOOK_ACCESS_TOKEN", tok)
    page = os.environ.get("FACEBOOK_PAGE_ID", page)
    return (tok or None), (page or None)


def facebook_metrics() -> dict:
    """Page-level followers via Graph API."""
    tok, page = _fb_service()
    if not tok or not page:
        return {}
    try:
        import requests
        r = requests.get(
            f"https://graph.facebook.com/v25.0/{page}",
            params={"access_token": tok, "fields": "fan_count,followers_count"},
            timeout=30,
        )
        r.raise_for_status()
        d = r.json()
        return {"followers": d.get("followers_count", d.get("fan_count", 0))}
    except Exception as exc:
        logger.warning("FB page metrics unavailable: %s", exc)
        return {}


def facebook_credit_videos(ml: LearningSystem) -> int:
    """Credit each uncredited Facebook video with real stats.

    Fetches video-level stats from the Graph API and applies rewards/penalties
    to the arms that produced them. Also fetches insights (watch time) when
    available.
    """
    ids = [v for v in ml.pending_video_ids("facebook") if str(v) != "dry-run"]
    if not ids:
        return 0
    tok, page = _fb_service()
    if not tok or not page:
        logger.warning("FB credit skipped — no token/page configured")
        return 0
    try:
        import requests
        credited = 0
        for vid in ids:
            try:
                # Fetch video stats
                r = requests.get(
                    f"https://graph.facebook.com/v25.0/{vid}",
                    params={
                        "access_token": tok,
                        "fields": "stats,insights,permalink_url,status_code,created_time",
                    },
                    timeout=30,
                )
                if r.status_code >= 400:
                    logger.debug("FB video %s not fetchable: %s", vid[:16], r.text[:200])
                    continue
                data = r.json()
                stats = data.get("stats", {})
                views = int(stats.get("views", 0))
                # insights may need extra permissions — extract watch_time_secs
                watch_time_secs = 0
                for period_data in (data.get("insights", {}) or {}).get("data", []):
                    for point in period_data.get("values", []):
                        val = point.get("value", {})
                        if isinstance(val, dict):
                            watch_time_secs += int(val.get("watch_duration_seconds", 0) or 0)

                # V3.6: retention sirf tab bhejo jab MEASURED ho (real watch
                # time). Pehle watch-time na hone par fabricated 0.15/0.05
                # heuristic bheji jati thi — wo guess reward function ke 35%
                # weight ke saath bandit ko dhoka deta tha. Ab sirf real
                # watch time retention banata hai; warna retention bheja hi
                # nahi jata (reward.py isay "unknown" treat karta hai).
                duration_ms = int(stats.get("duration", 60000))
                duration_secs = duration_ms / 1000.0
                metrics = {
                    "views": views,
                    "likes": int(stats.get("likes", 0)),
                    "comments": int(stats.get("comments", 0)),
                    "shares": int(stats.get("shares", 0) or 0),
                    "watch_time_seconds": watch_time_secs,
                    "duration_seconds": duration_secs,
                    "platform": "facebook",
                }
                retention_note = "unknown (no watch-time data)"
                if views > 0 and watch_time_secs > 0 and duration_secs > 0:
                    retention = min(0.95, watch_time_secs / (views * duration_secs))
                    metrics["retention"] = round(retention, 3)
                    metrics["retention_estimated"] = False   # MEASURED
                    retention_note = f"{retention * 100:.0f}%"
                elif views > 0:
                    metrics["retention_estimated"] = True    # koi guess nahi
                ml.credit_video(vid, metrics)
                credited += 1
                logger.info("FB credit: %s → views=%d watch=%ds retention=%s",
                            vid[:16], views, watch_time_secs, retention_note)
            except Exception as exc:
                logger.debug("FB video %s credit error: %s", vid[:16], exc)
        return credited
    except Exception as exc:
        logger.warning("Facebook video credit batch failed: %s", exc)
        return 0


# ── Instagram helpers ──────────────────────────────────────────────

def _ig_service():
    """Return (token, ig_id) or (None, None)."""
    tok = os.environ.get("IG_ACCESS_TOKEN", "")
    ig = os.environ.get("IG_BUSINESS_ACCOUNT_ID", "")
    if not tok or not ig:
        tok = os.environ.get("INSTAGRAM_ACCESS_TOKEN", tok)
        ig = os.environ.get("INSTAGRAM_USER_ID", ig)
        tok = os.environ.get("FACEBOOK_ACCESS_TOKEN", tok)  # fallback
    return (tok or None), (ig or None)


def instagram_metrics() -> dict:
    """IG account-level followers via Graph API."""
    tok, ig = _ig_service()
    if not tok or not ig:
        return {}
    try:
        import requests
        r = requests.get(
            f"https://graph.facebook.com/v25.0/{ig}",
            params={"access_token": tok, "fields": "followers_count,media_count"},
            timeout=30,
        )
        r.raise_for_status()
        d = r.json()
        return {"followers": d.get("followers_count", 0)}
    except Exception as exc:
        logger.warning("IG account metrics unavailable: %s", exc)
        return {}


def instagram_credit_videos(ml: LearningSystem) -> int:
    """Credit each uncredited IG Reel with real stats.

    Fetches IG media-level stats: plays, likes, comments, saved, shares.
    Also applies per-platform arm learning (IG learns separately from YT/FB).
    """
    ids = [v for v in ml.pending_video_ids("instagram") if str(v) != "dry-run"]
    if not ids:
        return 0
    tok, ig = _ig_service()
    if not tok or not ig:
        logger.warning("IG credit skipped — no token/account configured")
        return 0
    try:
        import requests
        credited = 0
        for media_id in ids:
            try:
                r = requests.get(
                    f"https://graph.facebook.com/v25.0/{media_id}",
                    params={
                        "access_token": tok,
                        "fields": (
                            "insights,caption,media_type,permalink,"
                            "comments_count,like_count,plays,shares,saved_count"
                        ),
                    },
                    timeout=30,
                )
                if r.status_code >= 400:
                    logger.debug("IG media %s not fetchable: %s", media_id[:16], r.text[:200])
                    continue
                data = r.json()
                plays = int(data.get("plays", 0) or 0)
                likes = int(data.get("like_count", 0) or 0)
                comments = int(data.get("comments_count", 0) or 0)
                shares = int(data.get("shares", 0) or 0)
                saved = int(data.get("saved_count", 0) or 0)

                # V3.6: fabricated retention hata di. Pehle
                # `retention = 0.10 + engagement_rate * 10` jaisa GUESS
                # bana kar reward function ko "measured retention" bata diya
                # jata tha — IG ke saves/shares real hain, retention nahi.
                # Ab sirf REAL metrics jate hain; reward.py ko retention
                # nahi milti to wo use "unknown" treat karta hai.
                ml.credit_video(media_id, {
                    "views": plays,
                    "likes": likes,
                    "comments": comments,
                    "shares": shares,
                    "saves": saved,
                    "retention_estimated": True,   # koi retention data nahi
                    "platform": "instagram",
                })
                credited += 1
                logger.info("IG credit: %s → plays=%d likes=%d saved=%d "
                            "retention=unknown (real saves/shares credited)",
                            media_id[:16], plays, likes, saved)
            except Exception as exc:
                logger.debug("IG media %s credit error: %s", media_id[:16], exc)
        return credited
    except Exception as exc:
        logger.warning("Instagram video credit batch failed: %s", exc)
        return 0


# ── Growth rewards (REMOVED in V3.6 — fuzzy attribution) ────────────
# Channel-level growth (subs/followers gained) ko "recent arms" par reward
# dena REALITY par based nahi tha: growth kis VIDEO ki wajah se hui, ye koi
# nahi jaanta — sab recent formulas ko credit dena bandit ko dhoka tha.
# Video-level crediting (upar) hi asal attribution hai: har video ka real
# performance us ke EXACT arm tak jata hai.

def apply_growth_rewards(ml: LearningSystem, prog: dict) -> None:
    """V3.6: no-op — fuzzy growth attribution hata di gayi.

    Channel growth ko 'recent arms' par reward dena band kar diya hai
    kyunke ye bata hi nahi sakte ke growth kis video ki wajah se hui.
    Video-level crediting (upar) hi asal, exact attribution hai.
    """
    return  # intentional no-op


# ── Main ─────────────────────────────────────────────────────────────

def main():
    yt = youtube_metrics()
    fb = facebook_metrics()
    ig = instagram_metrics()

    prev = {}
    with contextlib.suppress(OSError, json.JSONDecodeError):
        prev = json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))

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

    # 1) Credit individual videos per platform (real views → arm reward)
    yt_cred = youtube_credit_videos(ml)
    fb_cred = facebook_credit_videos(ml)
    ig_cred = instagram_credit_videos(ml)

    # 2) Reward channel-level growth
    apply_growth_rewards(ml, prog)

    # 3) Persist
    ml.save()

    # 4) Generate report
    summary = ml.summary()
    report = Path("data/metrics_report.md")
    report.parent.mkdir(exist_ok=True)
    report.write_text(
        f"# 📊 Coercion Files — Metrics Report\n\n"
        f"*Updated: {datetime.now(timezone.utc).isoformat()}*\n\n"
        f"**ML:** {summary['arms_tested']} arms · {summary['videos_tracked']} videos · "
        f"{summary['attributed_videos']} attributed · {summary['rewards']} rewards · "
        f"{summary['penalties']} penalties\n\n"
        f"**Videos credited this run:** YT={yt_cred} · FB={fb_cred} · IG={ig_cred}\n\n"
        f"**Best formulas:** " +
        (", ".join(f"{b['pillar']}/{b['hook_style']} ({b['mean']})"
                   for b in summary["best_formulas"]) or "none yet") + "\n\n"
        f"```json\n{json.dumps(prog, indent=2, ensure_ascii=False)}\n```\n",
        encoding="utf-8",
    )
    print(f"Metrics synced → {report}")
    print(f"  YT credited={yt_cred} · FB credited={fb_cred} · IG credited={ig_cred}")


if __name__ == "__main__":
    main()
