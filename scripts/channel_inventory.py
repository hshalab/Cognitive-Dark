#!/usr/bin/env python3
"""
Coercion Files — Channel Inventory & Status Diagnostic.

The pipeline uploads YouTube videos as PRIVATE with a publishAt schedule. If the
publish step ever failed, videos sit in Studio as Private forever — invisible to
viewers, earning nothing. This script lists EVERY video on all three platforms
with its true status, so you can see exactly what is public vs stuck.

Usage:
    python scripts/channel_inventory.py

Needs the same credentials as the pipeline (.env or GH secrets):
    YOUTUBE_CREDENTIALS | GOOGLE_CLIENT_ID+GOOGLE_CLIENT_SECRET+REFRESH_TOKEN
    FB_PAGE_ID + FB_ACCESS_TOKEN
    IG_BUSINESS_ACCOUNT_ID + IG_ACCESS_TOKEN
Platforms without credentials are skipped gracefully.
"""

import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("inventory")


def _yt_creds():
    raw = os.environ.get("YOUTUBE_CREDENTIALS", "")
    cid = os.environ.get("GOOGLE_CLIENT_ID")
    csec = os.environ.get("GOOGLE_CLIENT_SECRET")
    rt = os.environ.get("REFRESH_TOKEN")
    if cid and csec and rt:
        return {"client_id": cid, "client_secret": csec, "refresh_token": rt,
                "token_uri": "https://oauth2.googleapis.com/token",
                "type": "authorized_user"}
    if not raw:
        return None
    if os.path.exists(raw):
        return json.load(open(raw, encoding="utf-8"))
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def youtube_inventory() -> dict:
    info = _yt_creds()
    if not info:
        return {"available": False, "reason": "no YouTube credentials"}
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        creds = Credentials.from_authorized_user_info(info)
        if (creds.expired or not creds.valid) and creds.refresh_token:
            creds.refresh(Request())
        yt = build("youtube", "v3", credentials=creds)
        videos, page_token = [], None
        while True:
            r = yt.videos().list(part="snippet,status,statistics",
                                 myRating="upload", maxResults=50,
                                 pageToken=page_token).execute()
            for it in r.get("items", []):
                videos.append({
                    "id": it["id"],
                    "title": it["snippet"]["title"][:60],
                    "published": it["snippet"]["publishedAt"][:10],
                    "status": it["status"]["privacyStatus"],
                    "views": int(it.get("statistics", {}).get("viewCount", 0)),
                })
            page_token = r.get("nextPageToken")
            if not page_token:
                break
        return {"available": True, "videos": videos}
    except Exception as exc:
        return {"available": False, "reason": str(exc)}


def facebook_inventory() -> dict:
    tok, page = os.environ.get("FB_ACCESS_TOKEN", ""), os.environ.get("FB_PAGE_ID", "")
    if not tok or not page:
        return {"available": False, "reason": "no FB credentials"}
    try:
        import requests
        vids, url = [], f"https://graph.facebook.com/v25.0/{page}/videos"
        while url:
            r = requests.get(url, params={"access_token": tok,
                                          "fields": "title,status,created_time,permalink_url"},
                             timeout=30)
            r.raise_for_status()
            d = r.json()
            for it in d.get("data", []):
                vids.append({
                    "id": it.get("id"),
                    "title": (it.get("title") or "(no title)")[:60],
                    "created": (it.get("created_time") or "")[:10],
                    "status": it.get("status", "?"),
                    "url": it.get("permalink_url", ""),
                })
            url = d.get("paging", {}).get("next")
        return {"available": True, "videos": vids}
    except Exception as exc:
        return {"available": False, "reason": str(exc)}


def instagram_inventory() -> dict:
    tok, ig = os.environ.get("IG_ACCESS_TOKEN", ""), os.environ.get("IG_BUSINESS_ACCOUNT_ID", "")
    if not tok or not ig:
        return {"available": False, "reason": "no IG credentials"}
    try:
        import requests
        vids, url = [], f"https://graph.instagram.com/v22.0/{ig}/media"
        while url:
            r = requests.get(url, params={"access_token": tok,
                                          "fields": "media_type,timestamp,permalink"},
                             timeout=30)
            r.raise_for_status()
            d = r.json()
            for it in d.get("data", []):
                vids.append({
                    "id": it.get("id"),
                    "type": it.get("media_type", "?"),
                    "created": (it.get("timestamp") or "")[:10],
                    "url": it.get("permalink", ""),
                })
            url = d.get("paging", {}).get("next")
        return {"available": True, "videos": vids}
    except Exception as exc:
        return {"available": False, "reason": str(exc)}


def main():
    print("═" * 62)
    print("📦 COGNITIVE DARK — CHANNEL INVENTORY & STATUS")
    print("═" * 62)

    yt = youtube_inventory()
    print("\n▶ YOUTUBE")
    if yt["available"]:
        vids = yt["videos"]
        by_status = {}
        for v in vids:
            by_status.setdefault(v["status"], []).append(v)
        print(f"  Total uploads: {len(vids)}")
        for status in ("public", "private", "unlisted"):
            lst = by_status.get(status, [])
            if lst:
                views = sum(v["views"] for v in lst)
                print(f"  • {status.upper():8}: {len(lst):3} videos  ({views:,} total views)")
        # V2.1 flags the real blocker: videos stuck private
        stuck = by_status.get("private", [])
        if stuck:
            print(f"\n  ⚠️  {len(stuck)} videos are PRIVATE — invisible to viewers.")
            print("     These were uploaded but never published. Fix: publish them")
            print("     (V2.1 pipeline now publishes correctly at peak hours).")
            for v in stuck[:5]:
                print(f"       - [{v['published']}] {v['title']}")
            if len(stuck) > 5:
                print(f"       ... and {len(stuck) - 5} more")
    else:
        print("  skipped —", yt["reason"])

    fb = facebook_inventory()
    print("\n▶ FACEBOOK")
    if fb["available"]:
        print(f"  Total videos: {len(fb['videos'])}")
        for v in fb["videos"][:5]:
            print(f"    - [{v['created']}] {v['status']:10} {v['title']}")
    else:
        print("  skipped —", fb["reason"])

    ig = instagram_inventory()
    print("\n▶ INSTAGRAM")
    if ig["available"]:
        reels = [v for v in ig["videos"] if v["type"] in ("REELS", "VIDEO")]
        print(f"  Total media: {len(ig['videos'])}  (reels/videos: {len(reels)})")
    else:
        print("  skipped —", ig["reason"])

    print("\n" + "═" * 62)


if __name__ == "__main__":
    main()
