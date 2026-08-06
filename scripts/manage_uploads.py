#!/usr/bin/env python3
"""
Cognitive Dark — YouTube Upload Manager (runs in CI where secrets live).

Actions:
  list        — print every uploaded video (id, status, publishAt, views, title)
  keep_latest — keep the N most recent uploads; DELETE older NON-PUBLIC
                (private/scheduled) uploads. Public videos are NEVER touched
                unless --include-public is passed.

Usage (CI):  python scripts/manage_uploads.py list
             python scripts/manage_uploads.py keep_latest 3
"""

import json
import logging
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("manage")


def _creds():
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


def _service():
    info = _creds()
    if not info:
        sys.exit("❌ No YouTube credentials in environment")
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    creds = Credentials.from_authorized_user_info(info)
    if (creds.expired or not creds.valid) and creds.refresh_token:
        creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)


def list_uploads(yt):
    items, token = [], None
    while True:
        r = yt.videos().list(part="snippet,status,statistics", myRating="upload",
                             maxResults=50, pageToken=token).execute()
        items += r.get("items", [])
        token = r.get("nextPageToken")
        if not token:
            break
    items.sort(key=lambda i: i["snippet"]["publishedAt"], reverse=True)
    print(f"\n📺 TOTAL UPLOADS: {len(items)}")
    for it in items:
        st = it["status"]["privacyStatus"]
        pub = it["status"].get("publishAt", "")[:16]
        views = it.get("statistics", {}).get("viewCount", "0")
        print(f"  {it['id']}  {st:8} views={views:>5} "
              f"pub={pub or '-':16} | {it['snippet']['title'][:48]}")
    return items


def keep_latest(yt, n: int, include_public: bool = False):
    items = list_uploads(yt)
    keep = items[:n]
    doomed = items[n:]
    deleted = []
    for it in doomed:
        st = it["status"]["privacyStatus"]
        if st == "public" and not include_public:
            print(f"  ⏭️  SKIP public: {it['id']} {it['snippet']['title'][:40]}")
            continue
        yt.videos().delete(id=it["id"]).execute()
        deleted.append(it["id"])
        print(f"  🗑️  DELETED ({st}): {it['id']} {it['snippet']['title'][:40]}")
    print(f"\n✅ Kept {len(keep)} latest · deleted {len(deleted)} faulty uploads")
    for k in keep:
        print(f"   KEPT: {k['id']} [{k['status']['privacyStatus']}] "
              f"{k['snippet']['title'][:45]}")


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "list"
    yt = _service()
    if action == "list":
        list_uploads(yt)
    elif action == "keep_latest":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
        include_public = "--include-public" in sys.argv
        keep_latest(yt, n, include_public)
    else:
        sys.exit(f"unknown action: {action}")


if __name__ == "__main__":
    main()
