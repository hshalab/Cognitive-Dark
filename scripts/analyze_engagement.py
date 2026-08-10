#!/usr/bin/env python3
"""
Coercion Files — Engagement Doctor (V3.1).

97 views / 0 likes jaise videos ka asal ilaaj:

  1. YouTube ki saari videos fetch karta hai (views, likes, comments).
  2. LIKE-RATE calculate karta hai (likes/views) — Shorts benchmark 4-6%.
  3. "ZERO-LIKE ALERTS": views >= 50 par 0 likes → us video ka ARM penalize
     (bandit seekhta hai ye formula likes nahi laata) — apply_penalty.
  4. STRONG LIKE-RATE (>=5% aur views>=50) → arm ko reward (formula prove).
  5. Report likhta hai: data/engagement_report.md — kaunsa pillar/hook likes
     laata hai, kaunsa nahi.

READ on ML store se zyada kuch nahi — sirf apply_penalty/reward (bounded).
Usage:
  python scripts/analyze_engagement.py            # report + ML feedback
  python scripts/analyze_engagement.py --dry     # sirf report, koi penalty nahi
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("engage-audit")

from ml_engine import LearningSystem

REPORT_PATH = Path(__file__).resolve().parent.parent / "data" / "engagement_report.md"

# benchmarks
ZERO_LIKE_VIEWS = 50     # 50+ views par 0 likes = red flag
GOOD_LIKE_RATE = 0.05    # 5%+ = strong
PENALTY = -0.6
REWARD = 1.0


def resolve_yt_creds():
    cid = os.environ.get("GOOGLE_CLIENT_ID", "")
    csec = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    rt = os.environ.get("REFRESH_TOKEN", "")
    if cid and csec and rt:
        return {"client_id": cid, "client_secret": csec, "refresh_token": rt,
                "token_uri": "https://oauth2.googleapis.com/token",
                "scopes": ["https://www.googleapis.com/auth/youtube.readonly"],
                "type": "authorized_user"}
    return None


def fetch_yt_videos():
    info = resolve_yt_creds()
    if not info:
        logger.warning("YT creds missing")
        return []
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        creds = Credentials.from_authorized_user_info(info)
        if (creds.expired or not creds.valid) and creds.refresh_token:
            creds.refresh(Request())
        yt = build("youtube", "v3", credentials=creds)
        ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
        upl = ch["contentDetails"]["relatedPlaylists"]["uploads"]
        ids, token = [], None
        while True:
            r = yt.playlistItems().list(part="contentDetails", playlistId=upl,
                                        maxResults=50, pageToken=token).execute()
            ids += [i["contentDetails"]["videoId"] for i in r.get("items", [])]
            token = r.get("nextPageToken")
            if not token:
                break
        out = []
        for s in range(0, len(ids), 50):
            vids = yt.videos().list(part="snippet,statistics,status",
                                    id=",".join(ids[s:s + 50])).execute()
            for it in vids.get("items", []):
                st = it.get("statistics", {})
                out.append({"id": it["id"],
                            "title": it["snippet"]["title"],
                            "status": it["status"]["privacyStatus"],
                            "views": int(st.get("viewCount", 0) or 0),
                            "likes": int(st.get("likeCount", 0) or 0),
                            "comments": int(st.get("commentCount", 0) or 0)})
        return out
    except Exception as exc:
        logger.warning("YT fetch failed: %s", exc)
        return []


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry", action="store_true", help="sirf report, koi penalty nahi")
    args = ap.parse_args()

    videos = fetch_yt_videos()
    if not videos:
        print("Koi video nahi mili (creds?)")
        return 1
    public = [v for v in videos if v["status"] == "public"]
    print(f"Videos: {len(videos)} total, {len(public)} public")

    ml = LearningSystem()
    attribution = ml.data.get("attribution", {})
    zero_like = []
    strong = []
    rows = []
    for v in sorted(public, key=lambda x: x["views"], reverse=True):
        views = v["views"]
        likes = v["likes"]
        rate = likes / views if views else 0.0
        arm = None
        att = attribution.get(v["id"])
        if att:
            arm = att.get("arm_key")
        flag = ""
        if views >= ZERO_LIKE_VIEWS and likes == 0:
            flag = "ZERO-LIKE"
            zero_like.append(v)
            if arm and not args.dry:
                ml.apply_penalty(arm, f"zero_like:{v['id'][:8]}", PENALTY,
                                 platform="youtube")
                logger.info("PENALTY zero-like -> %s", arm)
        elif views >= ZERO_LIKE_VIEWS and rate >= GOOD_LIKE_RATE:
            flag = "STRONG"
            strong.append(v)
            if arm and not args.dry:
                ml.apply_reward(arm, f"good_like_rate:{v['id'][:8]}", REWARD,
                                platform="youtube")
                logger.info("REWARD good like-rate -> %s", arm)
        rows.append((views, likes, round(rate * 100, 1), flag,
                     v["title"][:45], arm or "-"))

    now = datetime.now(timezone.utc).isoformat()
    lines = ["# Engagement Report (V3.1)", "", f"*{now}*", "",
             f"**Videos:** {len(public)} public | "
             f"**Zero-like alerts (≥{ZERO_LIKE_VIEWS}v, 0 likes):** {len(zero_like)} | "
             f"**Strong (≥{GOOD_LIKE_RATE*100:.0f}% like-rate):** {len(strong)}", "",
             "| Views | Likes | Like% | Flag | Title | Arm |",
             "|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} |")
    lines += ["", "## Zero-like wale (ilaaj: hook + like-CTA + naya formula)", ""]
    if zero_like:
        for v in zero_like[:10]:
            lines.append(f"- **{v['title'][:50]}** — {v['views']} views, 0 likes")
    else:
        lines.append("- Koi zero-like alert nahi — achhi bat!")
    lines += ["", "## Strong wale (doble down karo)", ""]
    if strong:
        for v in strong[:10]:
            lines.append(f"- **{v['title'][:50]}** — {v['views']} views, "
                         f"{v['likes']} likes")
    else:
        lines.append("- Abhi koi 5%+ like-rate nahi — engagement CTAs abhi "
                     "naye scripts mein hain, agle 2-3 hafte mein asar dikhega.")
    lines += ["", "---", "_Auto-generated by scripts/analyze_engagement.py. "
              "Zero-like arms ko penalty, strong arms ko reward milta hai (bandit "
              "seekhta hai likes kahan se aate hain)._"]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\n-> {REPORT_PATH}")
    return 0 if not zero_like else 1


if __name__ == "__main__":
    sys.exit(main())
