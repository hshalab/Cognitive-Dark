#!/usr/bin/env python3
"""
Coercion Files — Existing Content Performance Report (V2.9.9).

Teeno platforms par jo content PEHLE SE uploaded hai uska asli performance
report ek hi jagah:

  YouTube  — saari videos: views, likes, comments, status, duration
  Facebook — recent page posts: message, reactions, comments, shares
  Instagram— recent media: caption, likes, comments, permalink

Output: data/boost_report.md (human-readable) + console summary.
Koi mutation nahi — sirf READ.
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
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("boost-report")

import requests

GRAPH = "https://graph.facebook.com"
V = "v25.0"
REPORT_PATH = Path(__file__).resolve().parent.parent / "data" / "boost_report.md"


def first_env(*names):
    for n in names:
        v = os.environ.get(n, "").strip()
        if v:
            return v
    return ""


def resolve_yt_creds():
    cid = os.environ.get("GOOGLE_CLIENT_ID")
    csec = os.environ.get("GOOGLE_CLIENT_SECRET")
    rt = os.environ.get("REFRESH_TOKEN")
    if cid and csec and rt:
        return {"client_id": cid, "client_secret": csec, "refresh_token": rt,
                "token_uri": "https://oauth2.googleapis.com/token",
                "scopes": ["https://www.googleapis.com/auth/youtube.readonly"],
                "type": "authorized_user"}
    raw = os.environ.get("YOUTUBE_CREDENTIALS", "")
    if not raw:
        return None
    if os.path.exists(raw):
        return json.loads(Path(raw).read_text(encoding="utf-8"))
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def yt_report():
    info = resolve_yt_creds()
    if not info:
        return [("youtube", "no-yt-creds", "YouTube creds missing")]
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        creds = Credentials.from_authorized_user_info(info)
        if (creds.expired or not creds.valid) and creds.refresh_token:
            creds.refresh(Request())
        yt = build("youtube", "v3", credentials=creds)
        ch = yt.channels().list(part="contentDetails,statistics",
                                mine=True).execute()["items"][0]
        upl = ch["contentDetails"]["relatedPlaylists"]["uploads"]
        ids, token = [], None
        while True:
            r = yt.playlistItems().list(part="contentDetails", playlistId=upl,
                                        maxResults=50, pageToken=token).execute()
            ids += [i["contentDetails"]["videoId"] for i in r.get("items", [])]
            token = r.get("nextPageToken")
            if not token:
                break
        rows = []
        for s in range(0, len(ids), 50):
            vids = yt.videos().list(part="snippet,status,statistics,contentDetails",
                                    id=",".join(ids[s:s + 50])).execute()
            for it in vids.get("items", []):
                st = it.get("statistics", {})
                rows.append((it["id"], it["snippet"]["title"][:60],
                             int(st.get("viewCount", 0) or 0),
                             int(st.get("likeCount", 0) or 0),
                             int(st.get("commentCount", 0) or 0),
                             it["status"]["privacyStatus"]))
        rows.sort(key=lambda r: r[2], reverse=True)
        stat = ch.get("statistics", {})
        subs = stat.get("subscriberCount", "0")
        total_views = sum(r[2] for r in rows)
        lines = [f"**YouTube:** {len(rows)} videos | subs {subs} | total views {total_views:,}", ""]
        lines.append("| Views | Title | Likes | Comments | Status |")
        lines.append("|---|---|---|---|---|")
        for r in rows:
            lines.append(f"| {r[2]:,} | {r[1]} | {r[3]} | {r[4]} | {r[5]} |")
        return lines
    except Exception as exc:
        return [f"**YouTube:** error {exc}"]


def fb_report():
    tok = first_env("FB_ACCESS_TOKEN", "FACEBOOK_ACCESS_TOKEN")
    page = first_env("FB_PAGE_ID", "FACEBOOK_PAGE_ID")
    if not tok or not page:
        return ["**Facebook:** creds missing"]
    try:
        r = requests.get(f"{GRAPH}/{V}/{page}/posts",
                         params={"access_token": tok,
                                 "fields": "message,created_time,permalink_url,"
                                           "reactions.summary(true),comments.summary(true),shares",
                                 "limit": 20},
                         timeout=30)
        if r.status_code != 200:
            return [f"**Facebook:** API {r.status_code} {r.json().get('error', {}).get('message', '')[:80]}"]
        data = r.json().get("data", [])
        rows = []
        for p in data:
            msg = (p.get("message") or "")[:60].replace("\n", " ")
            react = (p.get("reactions", {}).get("summary", {}).get("total_count", 0))
            cmt = (p.get("comments", {}).get("summary", {}).get("total_count", 0))
            sh = (p.get("shares", {}) or {}).get("count", 0)
            rows.append((p.get("created_time", "")[:10], msg, react, cmt, sh))
        lines = [f"**Facebook:** {len(rows)} recent posts", ""]
        lines.append("| Date | Message | Reacts | Comments | Shares |")
        lines.append("|---|---|---|---|---|")
        for r in rows:
            lines.append(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} |")
        return lines
    except Exception as exc:
        return [f"**Facebook:** error {exc}"]


def ig_report():
    tok = first_env("IG_ACCESS_TOKEN", "INSTAGRAM_ACCESS_TOKEN", "FB_ACCESS_TOKEN",
                    "FACEBOOK_ACCESS_TOKEN")
    ig = first_env("IG_BUSINESS_ACCOUNT_ID", "INSTAGRAM_USER_ID")
    if not tok or not ig:
        return ["**Instagram:** creds missing"]
    try:
        r = requests.get(f"{GRAPH}/{V}/{ig}/media",
                         params={"access_token": tok,
                                 "fields": "id,caption,timestamp,permalink,like_count,"
                                           "comments_count,media_type",
                                 "limit": 15},
                         timeout=30)
        if r.status_code != 200:
            return [f"**Instagram:** API {r.status_code} {r.json().get('error', {}).get('message', '')[:80]}"]
        data = r.json().get("data", [])
        lines = [f"**Instagram:** {len(data)} recent media", ""]
        lines.append("| Date | Type | Caption | Likes | Comments |")
        lines.append("|---|---|---|---|---|")
        for m in data:
            cap = (m.get("caption") or "")[:45].replace("\n", " ")
            lines.append(f"| {m.get('timestamp', '')[:10]} | {m.get('media_type')} | "
                         f"{cap} | {m.get('like_count', 0)} | {m.get('comments_count', 0)} |")
        return lines
    except Exception as exc:
        return [f"**Instagram:** error {exc}"]


def main():
    print("Generating boost report...")
    now = datetime.now(timezone.utc).isoformat()
    out = ["# Existing Content Performance Report", "", f"*Generated: {now}*", ""]
    out += ["---", "", "## YouTube", "", *yt_report()]
    out += ["", "---", "", "## Facebook", "", *fb_report()]
    out += ["", "---", "", "## Instagram", "", *ig_report()]
    out += ["", "---", "", "*Auto-generated by scripts/boost_report.py (read-only).*"]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))
    print(f"\n-> Saved to {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
