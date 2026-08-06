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
    # uploads playlist → video ids (newest first), then full details
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
    items = []
    for s in range(0, len(ids), 50):
        r = yt.videos().list(part="snippet,status,statistics",
                             id=",".join(ids[s:s + 50])).execute()
        items += r.get("items", [])
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


def spread_schedule(yt):
    """V2.5.2: pending scheduled uploads ko alag-alag USA peak slots par
    phailao (same-time publishing impressions cannibalize karti hai)."""
    from datetime import datetime, timedelta, timezone as tz
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    from scheduler import PlatformScheduler

    items = [i for i in list_uploads(yt)
             if i["status"]["privacyStatus"] != "public"
             and i["status"].get("publishAt")]
    if not items:
        print("✅ Koi pending scheduled video nahi")
        return
    items.reverse()  # oldest first

    sched = PlatformScheduler("youtube")
    now = datetime.now(sched.tz)
    peaks = []
    for off in range(10):
        d = now + timedelta(days=off)
        for h in sched.peaks.get(d.strftime("%A").lower(), [12, 20]):
            t = d.replace(hour=h, minute=0, second=0, microsecond=0)
            if t > now + timedelta(minutes=10):
                peaks.append(t)

    for it, peak in zip(items, peaks):
        body = {"id": it["id"],
                "status": {"privacyStatus": "private",
                           "selfDeclaredMadeForKids": False,
                           "publishAt": peak.astimezone(tz.utc)
                           .strftime("%Y-%m-%dT%H:%M:%S.000Z")}}
        yt.videos().update(part="status", body=body).execute()
        print(f"  ⏰ {it['id']} → {peak.strftime('%a %I:00 %p ET')} "
              f"({peak.astimezone(tz.utc).strftime('%H:%M UTC')}) | "
              f"{it['snippet']['title'][:38]}")
    print(f"\n✅ {min(len(items), len(peaks))} videos alag peak times par set")


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "list"
    yt = _service()
    if action == "list":
        list_uploads(yt)
    elif action == "keep_latest":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
        include_public = "--include-public" in sys.argv
        keep_latest(yt, n, include_public)
    elif action == "spread":
        spread_schedule(yt)
    else:
        sys.exit(f"unknown action: {action}")


if __name__ == "__main__":
    main()
