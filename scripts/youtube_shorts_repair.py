#!/usr/bin/env python3
"""
Coercion Files — YouTube Shorts Diagnostic & Repair.

Yeh script aapki channel ki saari videos (public/private/scheduled/unlisted)
ko scan karti hai aur batati hai:
  • kaun si video Shorts feed mein jane ki HALAT mein hai (vertical 1080x1920,
    <60s, square pixels) — yeh YouTube ke #1 technical requirement hain
  • kaun si videos PRIVATE/SCHEDULED phase mein atki hui hain (zero views ki
    sab se bari waja — private videos impressions nahi lete)
  • views, retention signals (agar available), privacy, publishAt
  • "Shorts" shelf kyun nahi mil raha — reason har video ke sath

Repair mode (`--fix-public`) un videos ko public kar deta hai jin ki
publishAt past mein hai lekin abhi tak private hain (schedule fire nahi hua).

Usage:
  python scripts/youtube_shorts_repair.py             # dry-run report
  python scripts/youtube_shorts_repair.py --fix-public # past-due private -> public

Credentials same as uploader: YOUTUBE_CREDENTIALS ya
GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET + REFRESH_TOKEN.
"""

import argparse
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
logger = logging.getLogger("shorts-repair")


# YouTube Shorts eligibility (2026 rules)
SHORTS_MAX_SECONDS = 180          # Shorts up to 3 min (verified accounts)
SHORTS_MIN_SECONDS = 1            # <1s not eligible
SHORTS_ASPECT_MIN = 0.55          # roughly 9:16 portrait tolerance
SHORTS_ASPECT_MAX = 1.0           # square is allowed; wider than square isn't a Short


def resolve_creds():
    """Same resolution as platforms/youtube.py: split OAuth > file > raw JSON."""
    cid = os.environ.get("GOOGLE_CLIENT_ID")
    csec = os.environ.get("GOOGLE_CLIENT_SECRET")
    rt = os.environ.get("REFRESH_TOKEN")
    if cid and csec and rt:
        info = {
            "client_id": cid, "client_secret": csec, "refresh_token": rt,
            "token_uri": "https://oauth2.googleapis.com/token",
            "scopes": ["https://www.googleapis.com/auth/youtube.upload",
                       "https://www.googleapis.com/auth/youtube.readonly",
                       "https://www.googleapis.com/auth/youtube"],
            "type": "authorized_user",
        }
        return info
    raw = os.environ.get("YOUTUBE_CREDENTIALS", "")
    if not raw:
        return None
    if os.path.exists(raw):
        return json.loads(Path(raw).read_text(encoding="utf-8"))
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def get_service():
    info = resolve_creds()
    if not info:
        sys.exit("❌ YouTube credentials nahi mile. .env mein daalo: "
                 "GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, REFRESH_TOKEN "
                 "(ya YOUTUBE_CREDENTIALS).")
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    creds = Credentials.from_authorized_user_info(info)
    if (creds.expired or not creds.valid) and creds.refresh_token:
        creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)


def all_upload_ids(yt):
    """Saari videos (including private/scheduled) via uploads playlist."""
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
    return ids


def fetch_videos(yt, ids):
    out = []
    for s in range(0, len(ids), 50):
        r = yt.videos().list(
            part="snippet,status,statistics,contentDetails,fileDetails,player",
            id=",".join(ids[s:s + 50])).execute()
        # NOTE: fileDetails needs owner + may be absent on some videos; we use it
        # only if returned.
        out += r.get("items", [])
    return out


def parse_iso8601_dur(s):
    """Parse ISO 8601 duration (e.g. PT57S) → seconds."""
    import re
    if not s:
        return None
    m = re.match(r"PT(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?", s)
    if not m:
        # hour form
        m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?", s)
        if not m:
            return None
        vals = m.groups()
        h = int(vals[0] or 0)
        mn = int(vals[1] or 0)
        sec = float(vals[2] or 0)
        return h * 3600 + mn * 60 + sec
    mn = int(m.group(1) or 0)
    sec = float(m.group(2) or 0)
    return mn * 60 + sec


def shorts_issues(item):
    """Technical reasons a video might not enter the Shorts feed."""
    issues = []
    cd = item.get("contentDetails", {})
    dur = parse_iso8601_dur(cd.get("duration", ""))
    if dur is not None:
        if dur < SHORTS_MIN_SECONDS:
            issues.append(f"duration {dur:.1f}s too short")
        elif dur > SHORTS_MAX_SECONDS:
            issues.append(f"duration {dur:.0f}s > {SHORTS_MAX_SECONDS}s (not a Short)")
    # dimension/ratio — fileDetails gives real width/height; may be absent
    fd = item.get("fileDetails", {})
    vstreams = fd.get("videoStreams", []) or []
    if vstreams:
        vs = vstreams[0]
        w, h = vs.get("widthPixels", 0), vs.get("heightPixels", 0)
        if w and h:
            ratio = w / h
            if ratio > SHORTS_ASPECT_MAX + 0.02:
                issues.append(f"landscape/square-wide {w}x{h} (ratio {ratio:.2f}) — not vertical")
            if h < 1080:
                issues.append(f"resolution {w}x{h} below 1080p (weak feed signal)")
            if vs.get("aspectRatio") and float(vs.get("aspectRatio", 1)) > 1.0:
                issues.append("pixel aspect ratio indicates non-portrait")
    else:
        issues.append("fileDetails missing (re-process or check upload)")
    st = item.get("status", {})
    if st.get("privacyStatus") != "public":
        issues.append(f"privacy={st.get('privacyStatus')} → no public impressions")
    if st.get("publishAt") and st.get("privacyStatus") == "private":
        pa = datetime.fromisoformat(st["publishAt"].replace("Z", "+00:00"))
        if pa > datetime.now(timezone.utc):
            issues.append(f"scheduled for future {pa.isoformat()}")
    if st.get("embeddable") is False:
        issues.append("embedding disabled (minor)")
    if st.get("selfDeclaredMadeForKids", False) is not True:
        pass  # adult educational — correct setting
    if item.get("snippet", {}).get("liveBroadcastContent") not in (None, "none"):
        issues.append("broadcast flag set (not a regular Short)")
    return dur, issues


def report(yt, fix_public=False):
    ids = all_upload_ids(yt)
    if not ids:
        print("Koi video nahi mili channel par.")
        return
    items = fetch_videos(yt, ids)
    print(f"\n{'='*78}\n📺 TOTAL VIDEOS ON CHANNEL: {len(items)}\n{'='*78}")

    total_views = 0
    zero_view = []
    private_past_due = []
    shorts_ok = 0
    not_shorts = 0

    for it in items:
        sn = it["snippet"]
        st = it["status"]
        stats = it.get("statistics", {})
        views = int(stats.get("viewCount", 0))
        total_views += views
        dur, issues = shorts_issues(it)
        is_short = dur is not None and dur <= SHORTS_MAX_SECONDS
        if is_short and not any("vertical" in x or "not a Short" in x for x in issues):
            shorts_ok += 1
        else:
            not_shorts += 1
        pub = st.get("publishAt", "")[:16].replace("T", " ")
        print(f"\n▸ {it['id']}  [{st['privacyStatus']:8}]  views={views:<6} "
              f"dur={f'{dur:.0f}s' if dur else '?':5}  pub={pub or 'now/-'}")
        print(f"  title: {sn['title'][:70]}")
        if issues:
            for x in issues:
                print(f"    ⚠️  {x}")
        if views == 0:
            zero_view.append(it)
        # past-due private (scheduled time passed but still private — needs repair)
        if st.get("publishAt") and st["privacyStatus"] == "private":
            pa = datetime.fromisoformat(st["publishAt"].replace("Z", "+00:00"))
            if pa <= datetime.now(timezone.utc):
                private_past_due.append((it, pa))

    print(f"\n{'='*78}\n📊 SUMMARY\n{'='*78}")
    print(f"  Total videos       : {len(items)}")
    print(f"  Shorts-shaped      : {shorts_ok}")
    print(f"  Non-Shorts shape   : {not_shorts}")
    print(f"  Zero-views         : {len(zero_view)}")
    print(f"  Past-due PRIVATE   : {len(private_past_due)} (schedule fire nahi hua)")
    print(f"  Total channel views: {total_views}")

    if private_past_due:
        print("\n🔧 PAST-DUE PRIVATE VIDEOS (yeh zero-views ki sab se bari waja hain):")
        for it, pa in private_past_due:
            print(f"   - {it['id']}  scheduled {pa.isoformat()[:16]}  → {it['snippet']['title'][:50]}")

    if fix_public and private_past_due:
        print("\n🔧 Repair: past-due private videos ko PUBLIC kiya ja raha hai...")
        for it, _pa in private_past_due:
            try:
                yt.videos().update(
                    part="status",
                    body={"id": it["id"],
                          "status": {"privacyStatus": "public",
                                     "selfDeclaredMadeForKids": False}}).execute()
                print(f"   ✅ {it['id']} → PUBLIC")
            except Exception as exc:
                print(f"   ❌ {it['id']}: {exc}")
    elif private_past_due:
        print("\n💡 Inhein public karne ke liye:  python scripts/youtube_shorts_repair.py --fix-public")

    # Zero-view diagnosis (non-private)
    stuck = [v for v in zero_view
             if v["status"]["privacyStatus"] == "public"
             and not v["status"].get("publishAt")]
    if stuck:
        print("\n🔍 PUBLIC MAGAR ZERO-VIEWS — yeh algorithm/content issues hain (technical nahi):")
        for it in stuck:
            print(f"   - {it['id']}: {it['snippet']['title'][:55]}")
        print("   Wajuhat: pehle 24-72h test impressions mein kam CTR ya kam 3s "
              "retention → YouTube ne push karna band kar diya. Hook + thumbnail "
              "improve karein (USA_GROWTH_PLAN.md dekho).")
    print()


def main():
    ap = argparse.ArgumentParser(description="YouTube Shorts diagnostic & repair")
    ap.add_argument("--fix-public", action="store_true",
                    help="past-due private/scheduled videos ko public kar do")
    args = ap.parse_args()
    yt = get_service()
    report(yt, fix_public=args.fix_public)


if __name__ == "__main__":
    main()
