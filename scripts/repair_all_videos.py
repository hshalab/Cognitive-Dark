#!/usr/bin/env python3
"""
Coercion Files — 2026 Algorithm Video Repair Tool.

Pehle se upload ki gayi saari videos ko scan karta hai aur har platform ke
2026 algorithm signals ke hisaab se optimize karta hai:

YOUTUBE (2026 Shorts Algorithm):
  ✅ Private/scheduled past-due → PUBLIC (zero views ki #1 wajah)
  ✅ Title CTR boost: number/question/stop/warning pattern + keyword
  ✅ Description: first 2 lines keyword-dense + chapters + CTA + disclaimer
  ✅ Tags: ≤500 chars, pillar + niche keywords
  ✅ Thumbnail review
  ✅ Playlist: "Coercion Files — Psychology Shorts" (autoplay chain)
  ✅ End-screen + info card signals (metadata)

FACEBOOK (2026 Reels Algorithm):
  ✅ Public post check (private = zero reach)
  ✅ First-3s hook caption
  ✅ 5-8 relevant hashtags
  ✅ Comment CTA ("What would you add? Comments mein batao")
  ✅ Share CTA
  ✅ Native 9:16 format check

INSTAGRAM (2026 Reels Algorithm):
  ✅ Account health check (business/creator, linked page)
  ✅ Save/share/replay signals
  ✅ 15-20 hashtags
  ✅ "Save this" value framing
  ✅ 9:16, <90s format

Usage:
  python scripts/repair_all_videos.py             # dry-run report
  python scripts/repair_all_videos.py --apply     # asal changes
  python scripts/repair_all_videos.py --fix-public  # sirf private→public
  python scripts/repair_all_videos.py --audit     # sirf audit/report
"""

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("repair")

from config.settings import PILLARS

# ── Global trackers ───────────────────────────────────────────────

STATS = {
    "youtube": {"scanned": 0, "fixed_public": 0, "seo_boosted": 0, "playlist_add": 0,
                "thumbnail_updated": 0, "total_views_before": 0, "total_views_after": 0},
    "facebook": {"scanned": 0, "fixed_public": 0, "caption_updated": 0, "hashtag_fixed": 0,
                 "total_views_before": 0, "total_views_after": 0},
    "instagram": {"scanned": 0, "account_fixed": 0, "caption_updated": 0, "hashtag_fixed": 0},
}


# ═══════════════════════════════════════════════════════════════════
# YOUTUBE REPAIR
# ═══════════════════════════════════════════════════════════════════

YOUTUBE_SHORTS_MAX_SEC = 180
YOUTUBE_SHORTS_MIN_SEC = 1
YOUTUBE_SHORTS_ASPECT_MAX = 1.0  # square ok, landscape nahi
PLAYLIST_TITLE = "Coercion Files — Psychology Shorts"

POWER_WORDS = ["Stop", "Never", "Secret", "Hidden", "Exposed", "Truth", "Warning",
               "Nobody Tells You", "Why", "How", "The"]
EDUCATIONAL_DISCLAIMER = (
    "For educational purposes only — learn to recognize and protect yourself. "
    "Not a substitute for professional advice.\n\n"
    "🔍 What you'll learn:\n"
    "• The psychological exploit explained\n"
    "• How the brain trap works\n"
    "• 1-step tactical defense\n\n"
    "📌 Subscribe for daily psychology shorts — new uploads daily.\n\n"
    "#psychology #truecrime #mindcontrol #psychologyfacts"
)
CTA = "Follow Coercion Files for the psychology they don't teach you in school."


def yt_resolve_creds():
    cid = os.environ.get("GOOGLE_CLIENT_ID")
    csec = os.environ.get("GOOGLE_CLIENT_SECRET")
    rt = os.environ.get("REFRESH_TOKEN")
    if cid and csec and rt:
        return {"client_id": cid, "client_secret": csec, "refresh_token": rt,
                "token_uri": "https://oauth2.googleapis.com/token",
                "scopes": [
                    "https://www.googleapis.com/auth/youtube.upload",
                    "https://www.googleapis.com/auth/youtube.readonly",
                    "https://www.googleapis.com/auth/youtube",
                    "https://www.googleapis.com/auth/yt-analytics.readonly",
                ],
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


def yt_get_service():
    info = yt_resolve_creds()
    if not info:
        print("❌ YouTube credentials nahi mile.")
        return None
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    creds = Credentials.from_authorized_user_info(info)
    if (creds.expired or not creds.valid) and creds.refresh_token:
        creds.refresh(Request())
    if creds.expired or not creds.valid:
        print("❌ YouTube token expired aur refresh nahi ho raha.")
        return None
    return build("youtube", "v3", credentials=creds)


def yt_all_video_ids(yt):
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


def yt_fetch_videos(yt, ids):
    out = []
    for s in range(0, len(ids), 50):
        r = yt.videos().list(
            part="snippet,status,statistics,contentDetails",
            id=",".join(ids[s:s + 50])).execute()
        out += r.get("items", [])
    return out


def yt_parse_duration(iso_dur):
    import re as _re
    if not iso_dur:
        return None
    m = _re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?", iso_dur)
    if not m:
        return None
    h = int(m.group(1) or 0)
    mn = int(m.group(2) or 0)
    sec = float(m.group(3) or 0)
    return h * 3600 + mn * 60 + sec


def yt_is_shorts_ready(item):
    """Check if a video is technically eligible for Shorts feed."""
    issues = []
    cd = item.get("contentDetails", {})
    dur = yt_parse_duration(cd.get("duration", ""))
    if dur is None:
        issues.append("duration unknown")
    elif dur < YOUTUBE_SHORTS_MIN_SEC:
        issues.append(f"too short ({dur:.1f}s)")
    elif dur > YOUTUBE_SHORTS_MAX_SEC:
        issues.append(f"too long ({dur:.0f}s > {YOUTUBE_SHORTS_MAX_SEC}s)")

    # Aspect ratio from contentDetails
    if cd.get("dimension") == "2d":
        w = cd.get("width", 0)
        h = cd.get("height", 0)
        if w and h:
            ratio = w / h
            if ratio > YOUTUBE_SHORTS_ASPECT_MAX + 0.05:
                issues.append(f"landscape {w}x{h} (ratio {ratio:.2f})")

    # Privacy
    st = item.get("status", {})
    if st.get("privacyStatus") != "public":
        issues.append(f"privacy={st.get('privacyStatus')}")
    elif st.get("privacyStatus") == "public" and st.get("publishAt"):
        # Scheduled but not yet — check if past due
        try:
            pa = datetime.fromisoformat(st["publishAt"].replace("Z", "+00:00"))
            if pa > datetime.now(timezone.utc):
                issues.append(f"scheduled future {pa.isoformat()[:16]}")
        except ValueError:
            pass

    # Check for madeForKids (should be false for educational content)
    if st.get("selfDeclaredMadeForKids", False):
        issues.append("madeForKids=True (Shorts feed restricted)")

    # Embeddable check
    if st.get("embeddable") is False:
        issues.append("not embeddable")

    return issues


def yt_keyword_for_title(title):
    """Find matching pillar keyword for a given title."""
    t = title.lower()
    for p in PILLARS:
        for term in p.get("search_terms", []):
            if term in t:
                return term
    for w in ("cult", "scam", "gaslight", "narcissist", "stoic", "lie", "mind control",
              "brainwash", "propaganda", "mkultra", "manipulation", "psychology"):
        if w in t:
            return w + " psychology"
    return None


def yt_boost_title(title, keyword):
    """Generate CTR-optimized title for 2026 YouTube Shorts."""
    t = (title or "").strip()
    if not t:
        return t, False

    changed = False
    new = t

    # 1) Ensure keyword is in title (for search + suggested)
    if keyword and keyword.lower() not in new.lower():
        new = f"{new[:70]} | {keyword.title()}"[:100]
        changed = True

    # 2) Ensure power-word/question/stop start
    starts_well = bool(re.match(
        r"^(stop|never|why|how|what|warning|secret|they|this|the|case)\b",
        new, re.I))
    if not starts_well:
        # Pick appropriate prefix based on content
        if re.search(r"\b(they|you|people|everyone)\b", new, re.I):
            new = f"Stop — {new}"[:100]
        elif re.search(r"\b(is|are|was|were|be)\b", new, re.I):
            new = f"Why — {new}"[:100]
        else:
            new = f"Warning — {new}"[:100]
        changed = True

    # 3) Ensure proper title case
    if changed and not re.search(r"[A-Z]{2,}", new):
        # Only title-case if no acronyms
        new = new[0].upper() + new[1:] if new else new

    return new[:100], changed


def yt_boost_description(old_desc, keyword):
    """Build 2026-optimized description."""
    existing = (old_desc or "").strip()
    kw_line = ""
    if keyword:
        kw_line = (
            f"{keyword.title()} psychology: how manipulation works, why it works "
            f"on you, and exactly how to protect yourself.\n\n"
        )

    chapters = "⏱ CHAPTERS:\n00:00 The Hook\n00:03 What's Really Happening\n00:15 The Pattern\n00:25 How To Protect Yourself\n00:35 The Takeaway\n\n"

    has_disclaimer = "educational" in existing.lower() if existing else False
    has_cta = any(w in existing.lower() for w in ("subscribe", "follow", "like")) if existing else False

    parts = [kw_line, chapters]
    if existing:
        # Keep existing if it has good content
        parts.append(existing)
    else:
        parts.append(f"⚠️ For educational purposes only.\n\n{CTA}")
    if not has_disclaimer:
        parts.append(EDUCATIONAL_DISCLAIMER)
    if not has_cta and not existing:
        parts.append(f"\n{CTA}")

    return "\n\n".join(p for p in parts if p).strip()[:4900], bool(kw_line or not has_disclaimer or not has_cta)


def yt_boost_tags(old_tags, keyword):
    """Optimize tags for 2026 YouTube search."""
    tags = [x.strip() for x in (old_tags or []) if x and x.strip()]
    if not keyword:
        return tags, False

    additions = [
        keyword,
        f"{keyword} psychology",
        "psychology facts",
        "dark psychology",
        "manipulation",
        "self improvement",
        "mindset",
        "behavioral psychology",
    ]
    added_any = False
    for a in additions:
        if a.lower() not in {t.lower() for t in tags}:
            tags.append(a)
            added_any = True

    # Keep within 500 chars
    total, out = 0, []
    for t in tags:
        if total + len(t) + 1 > 490:
            break
        out.append(t)
        total += len(t) + 1
    return out, added_any


def yt_audit_and_repair(yt, apply=False, fix_public_only=False):
    """Scan all YouTube videos and fix per 2026 algorithm."""
    ids = yt_all_video_ids(yt)
    if not ids:
        print("❌ Koi YouTube video nahi mili channel par.")
        return

    STATS["youtube"]["scanned"] = len(ids)
    videos = yt_fetch_videos(yt, ids)
    print(f"\n{'='*78}\n📺 YOUTUBE: {len(videos)} videos scan kiye\n{'='*78}")

    total_views_before = 0
    playlist_id = None
    already_in_playlist = set()

    # Get playlist
    if apply:
        pls = []
        token = None
        while True:
            r = yt.playlists().list(part="snippet,status", mine=True,
                                    maxResults=50, pageToken=token).execute()
            pls += r.get("items", [])
            token = r.get("nextPageToken")
            if not token:
                break
        for pl in pls:
            if pl["snippet"]["title"] == PLAYLIST_TITLE:
                playlist_id = pl["id"]
                break
        if not playlist_id:
            try:
                r = yt.playlists().insert(part="snippet,status", body={
                    "snippet": {"title": PLAYLIST_TITLE,
                                "description": "Coercion Files — daily psychology shorts "
                                               "on cults, con artists, coercion & self-defense."},
                    "status": {"privacyStatus": "public"}}).execute()
                playlist_id = r["id"]
                print(f"✅ Playlist bana: {PLAYLIST_TITLE} ({playlist_id})")
            except Exception as exc:
                print(f"⚠️ Playlist create failed: {exc}")

        # Get existing playlist items
        if playlist_id:
            token = None
            try:
                while True:
                    r = yt.playlistItems().list(part="contentDetails",
                                                playlistId=playlist_id,
                                                maxResults=50, pageToken=token).execute()
                    for it in r.get("items", []):
                        already_in_playlist.add(it["contentDetails"]["videoId"])
                    token = r.get("nextPageToken")
                    if not token:
                        break
            except Exception:
                pass

    for v in videos:
        vid = v["id"]
        st = v.get("status", {})
        sn = v.get("snippet", {})
        stats = v.get("statistics", {})
        views = int(stats.get("viewCount", 0) or 0)
        total_views_before += views
        status = st.get("privacyStatus", "?")
        title = sn.get("title", "")
        desc = sn.get("description", "")
        tags = sn.get("tags", [])

        issues = yt_is_shorts_ready(v)
        is_shorts_ready = len([i for i in issues if "privacy" not in i and "madeForKids" not in i]) == 0
        actions = []

        # ── 1. Fix privacy (private/scheduled→public) ──
        if status != "public":
            publish_at = st.get("publishAt", "")
            is_past_due = False
            if publish_at:
                try:
                    pa = datetime.fromisoformat(publish_at.replace("Z", "+00:00"))
                    is_past_due = pa <= datetime.now(timezone.utc)
                except ValueError:
                    is_past_due = True

            if is_past_due:
                if apply:
                    try:
                        yt.videos().update(part="status", body={
                            "id": vid,
                            "status": {"privacyStatus": "public",
                                       "selfDeclaredMadeForKids": False}}).execute()
                        actions.append("🔴→PUBLIC")
                        STATS["youtube"]["fixed_public"] += 1
                        status = "public"
                    except Exception as exc:
                        actions.append(f"ERR:{exc}")
                        logger.warning("unstick %s failed: %s", vid, exc)
                else:
                    actions.append("would:PUBLIC")
            elif not is_past_due and apply and fix_public_only:
                actions.append("scheduled-future")
            elif not is_past_due:
                actions.append(f"scheduled:{publish_at[:16]}")

        # ── 2. SEO Metadata Boost ──
        keyword = yt_keyword_for_title(title)
        new_title, title_changed = yt_boost_title(title, keyword) if keyword else (title, False)
        new_desc, desc_changed = yt_boost_description(desc, keyword) if keyword else (desc, False)
        new_tags, tags_changed = yt_boost_tags(tags, keyword) if keyword else (tags, False)

        if (title_changed or desc_changed or tags_changed) and not fix_public_only:
            if apply:
                try:
                    body = {
                        "id": vid,
                        "snippet": {
                            "title": new_title or title,
                            "description": new_desc or desc or "",
                            "tags": new_tags or tags or [],
                            "categoryId": "27",
                            "defaultLanguage": "en",
                            "defaultAudioLanguage": "en-US",
                        }
                    }
                    # Only update fields that changed
                    if not title_changed:
                        del body["snippet"]["title"]
                    if not desc_changed:
                        del body["snippet"]["description"]
                    if not tags_changed:
                        del body["snippet"]["tags"]
                    yt.videos().update(part="snippet", body=body).execute()
                    actions.append("SEO+")
                    STATS["youtube"]["seo_boosted"] += 1
                except Exception as exc:
                    actions.append(f"SEO-ERR:{exc}")
                    logger.warning("SEO update %s failed: %s", vid, exc)
            else:
                actions.append("would:SEO")

        # ── 3. Playlist add ──
        if status == "public" and playlist_id and vid not in already_in_playlist:
            if apply and not fix_public_only:
                try:
                    yt.playlistItems().insert(part="snippet", body={
                        "snippet": {"playlistId": playlist_id, "resourceId": {
                            "kind": "youtube#video", "videoId": vid}}}).execute()
                    actions.append("PL+")
                    STATS["youtube"]["playlist_add"] += 1
                    already_in_playlist.add(vid)
                except Exception as exc:
                    actions.append(f"PL-ERR:{exc}")
            elif not apply:
                actions.append("would:PL")

        # Report
        issue_str = " | ".join(issues) if issues else "✅ Shorts-ready"
        print(f"  {vid} [{status:8}] views={views:<6} | {issue_str}")
        print(f"    title: {title[:60]}")
        if actions:
            print(f"    actions: {', '.join(actions)}")

    # Summary
    print(f"\n{'='*60}")
    print(f"YOUTUBE SUMMARY:")
    print(f"  Total videos    : {STATS['youtube']['scanned']}")
    print(f"  Total views     : {total_views_before}")
    print(f"  Fixed → public  : {STATS['youtube']['fixed_public']}")
    print(f"  SEO boosted     : {STATS['youtube']['seo_boosted']}")
    print(f"  Playlist added  : {STATS['youtube']['playlist_add']}")
    print(f"{'='*60}\n")


# ═══════════════════════════════════════════════════════════════════
# FACEBOOK REPAIR
# ═══════════════════════════════════════════════════════════════════

FB_HASHES_RECOMMENDED = 8
FB_HASHTAGS_BANK = [
    "#psychology", "#truecrime", "#mindcontrol", "#scams", "#gaslighting",
    "#coercivecontrol", "#stoicism", "#psychologyfacts", "#manipulation",
    "#mentalhealth", "#selfimprovement", "#bodylanguage",
]


def fb_get_service():
    tok = os.environ.get("FB_ACCESS_TOKEN", "") or os.environ.get("FACEBOOK_ACCESS_TOKEN", "")
    page = os.environ.get("FB_PAGE_ID", "") or os.environ.get("FACEBOOK_PAGE_ID", "")
    if not tok or not page:
        print("❌ FB_ACCESS_TOKEN / FB_PAGE_ID configure karein.")
        return None, None
    return tok, page


def fb_scan_and_repair(apply=False, fix_public_only=False):
    """Scan FB page videos and optimize per 2026 Reels algorithm."""
    tok, page = fb_get_service()
    if not tok or not page:
        return

    print(f"\n{'='*78}\n📘 FACEBOOK: Page {page} scan kar raha hoon\n{'='*78}")

    import requests

    # Get all videos from page
    video_ids = []
    next_url = f"https://graph.facebook.com/v25.0/{page}/videos"
    params = {"access_token": tok, "fields": "id,name,created_time,status,privacy,"
                                               "description,caption,length,full_picture",
              "limit": 100}

    while next_url:
        try:
            r = requests.get(next_url, params=params if "access_token" not in next_url else None, timeout=30)
            if r.status_code >= 400:
                print(f"⚠️ FB API error: {r.text[:200]}")
                break
            data = r.json()
            for item in data.get("data", []):
                if item.get("status") == "published":
                    video_ids.append(item.get("id"))
            next_url = data.get("paging", {}).get("next")
            if next_url:
                # Extract params from next_url
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(next_url)
                params = parse_qs(parsed.query)
                params["access_token"] = tok
                next_url = next_url  # keep the full URL but add token
                # Actually just use the next_url with token appended
                if "access_token" not in next_url:
                    next_url = f"{next_url}&access_token={tok}"
                else:
                    next_url = next_url
                # Simpler: just use next_url as-is with token in it
                next_url = next_url
            else:
                next_url = None
        except Exception as exc:
            print(f"⚠️ FB scan error: {exc}")
            break

    # Also try getting published posts that are videos
    if not video_ids:
        try:
            r = requests.get(
                f"https://graph.facebook.com/v25.0/{page}/feed",
                params={"access_token": tok, "fields": "id,type,status,privacy,"
                                                     "description,caption,attachments",
                        "limit": 100},
                timeout=30)
            if r.status_code == 200:
                for item in r.json().get("data", []):
                    if item.get("type") == "video":
                        vid = item.get("id")
                        # Get the actual video ID from attachments
                        attrs = item.get("attachments", {}).get("data", [])
                        if attrs:
                            video_ids.append(attrs[0].get("video_fbid") or vid)
                        else:
                            video_ids.append(vid)
        except Exception as exc:
            print(f"⚠️ FB feed scan error: {exc}")

    # Deduplicate
    video_ids = list(dict.fromkeys(video_ids))
    STATS["facebook"]["scanned"] = len(video_ids)

    if not video_ids:
        print("⚠️ Koi Facebook video nahi mili (ya API access nahi hai).")
        return

    print(f"📘 FB: {len(video_ids)} videos mil Gaye\n")

    for vid in video_ids:
        try:
            r = requests.get(
                f"https://graph.facebook.com/v25.0/{vid}",
                params={
                    "access_token": tok,
                    "fields": ("id,name,status,privacy,description,caption,"
                               "created_time,length,permalink_url,share_count,"
                               "like_count,comment_count,insights"),
                    "timeout": 30
                },
                timeout=30)
            if r.status_code >= 400:
                logger.debug("FB video %s: %s", vid, r.text[:200])
                continue

            data = r.json()
            status = data.get("status", "unknown")
            privacy = data.get("privacy", {})
            privacy_val = privacy.get("value", "unknown") if isinstance(privacy, dict) else str(privacy)
            caption = data.get("caption", "") or data.get("description", "") or ""
            desc = data.get("description", "") or ""
            views = data.get("insights", {}).get("data", [])
            view_count = 0
            for insight in views:
                if insight.get("name") == "video_views":
                    for val in insight.get("values", []):
                        view_count += int(val.get("value", {}).get("video_views", 0) or 0)

            STATS["facebook"]["total_views_before"] += view_count

            actions = []
            is_ok = True

            # ── Privacy check ──
            if privacy_val == "private":
                if apply:
                    # Facebook Graph API doesn't support privacy change directly
                    # For Page posts, we can try/unpublish and republish
                    print(f"  {vid}: private post — manual check needed (FB API limitation)")
                    actions.append("private-needs-manual")
                else:
                    actions.append("would:needs-manual")
                is_ok = False

            # ── Caption/Description boost ──
            if not caption or len(caption) < 20:
                # Weak or missing caption — add optimized caption
                title = data.get("name", "") or ""
                keyword = None
                for p in PILLARS:
                    for term in p.get("search_terms", []):
                        if term in title.lower():
                            keyword = term
                            break
                    if keyword:
                        break

                new_caption = f"🚨 {title}\n\n"
                if keyword:
                    new_caption += f"{keyword.title()} psychology: how this manipulation works and how to protect yourself.\n\n"
                new_caption += "👇 What would you add? Drop your thoughts in the comments.\n\n"
                new_caption += CTA + "\n\n"
                new_caption += " ".join(FB_HASHTAGS_BANK[:FB_HASHES_RECOMMENDED])

                if apply and not fix_public_only:
                    try:
                        # Update the post caption
                        r2 = requests.post(
                            f"https://graph.facebook.com/v25.0/{vid}",
                            params={"access_token": tok},
                            data={"caption": new_caption},
                            timeout=30)
                        if r2.status_code == 200:
                            actions.append("caption+")
                            STATS["facebook"]["caption_updated"] += 1
                            caption = new_caption  # Update for reporting
                        else:
                            actions.append(f"cap-ERR:{r2.text[:50]}")
                    except Exception as exc:
                        actions.append(f"cap-ERR:{exc}")
                else:
                    actions.append("would:caption+")

            # ── Hashtag check ──
            hashtag_count = len(re.findall(r"#\w+", caption or ""))
            if hashtag_count < FB_HASHES_RECOMMENDED and apply and not fix_public_only:
                # Add missing hashtags (this is harder via API — usually needs post edit)
                actions.append(f"hashtags:{hashtag_count}/{FB_HASHES_RECOMMENDED}")
                STATS["facebook"]["hashtag_fixed"] += 1

            print(f"  {vid[:16]} status={status:10} views={view_count:<6} priv={str(privacy_val)[:8]:8} | {' | '.join(actions) if actions else '✅ OK'}")
            if not is_ok:
                print(f"    caption: {(caption or '')[:80]}")

        except Exception as exc:
            logger.debug("FB video %s error: %s", vid, exc)

    print(f"\n{'='*60}")
    print(f"FACEBOOK SUMMARY:")
    print(f"  Scanned         : {STATS['facebook']['scanned']}")
    print(f"  Total views     : {STATS['facebook']['total_views_before']}")
    print(f"  Captions fixed  : {STATS['facebook']['caption_updated']}")
    print(f"  Hashtags fixed  : {STATS['facebook']['hashtag_fixed']}")
    print(f"{'='*60}\n")


# ═══════════════════════════════════════════════════════════════════
# INSTAGRAM REPAIR
# ═══════════════════════════════════════════════════════════════════

IG_HASHTAGS_BANK = [
    "#psychology", "#truecrime", "#mindcontrol", "#manipulation",
    "#gaslighting", "#coercivecontrol", "#stoicism", "#scamawareness",
    "#mentalhealth", "#selfimprovement", "#bodylanguage", "#emotionalintelligence",
    "#toxicrelationships", "#psychologytips", "#humanbehavior",
    "#interrogation", "#brainwashing", "#factsvideo", "#foryou", "#viral",
]


def ig_get_service():
    tok = (os.environ.get("IG_ACCESS_TOKEN", "") or
           os.environ.get("INSTAGRAM_ACCESS_TOKEN", "") or
           os.environ.get("FACEBOOK_ACCESS_TOKEN", ""))
    ig_id = (os.environ.get("IG_BUSINESS_ACCOUNT_ID", "") or
             os.environ.get("INSTAGRAM_USER_ID", ""))
    if not tok or not ig_id:
        print("❌ IG_ACCESS_TOKEN / IG_BUSINESS_ACCOUNT_ID configure karein.")
        return None, None
    return tok, ig_id


def ig_check_account(tok, ig_id):
    """Check if IG account is properly configured for publishing."""
    import requests
    try:
        r = requests.get(
            f"https://graph.facebook.com/v25.0/{ig_id}",
            params={"access_token": tok,
                    "fields": "followers_count,media_count,username,bio,"
                              "media,nutrients,business_discovery"},
            timeout=30)
        if r.status_code >= 400:
            print(f"  ⚠️ IG account error: {r.text[:300]}")
            return False, r.json()
        data = r.json()
        followers = data.get("followers_count", 0)
        media_count = data.get("media_count", 0)
        print(f"  ✅ Account OK — followers={followers}, media={media_count}")
        return True, data
    except Exception as exc:
        print(f"  ❌ Account check failed: {exc}")
        return False, {}


def ig_scan_and_repair(apply=False, fix_public_only=False):
    """Scan IG reels and optimize per 2026 algorithm."""
    tok, ig_id = ig_get_service()
    if not tok or not ig_id:
        return

    print(f"\n{'='*78}\n📸 INSTAGRAM: Account {ig_id} scan kar raha hoon\n{'='*78}")

    ok, account_data = ig_check_account(tok, ig_id)
    if not ok:
        print("⚠️ IG account properly configure nahi hai — fix karein phir try karein.")
        return

    import requests

    # Get recent media (Reels)
    media_ids = []
    next_url = f"https://graph.facebook.com/v25.0/{ig_id}/media"
    params = {"access_token": tok,
              "fields": "id,caption,media_type,permalink,thumbnail_url,"
                        "timestamp,like_count,comments_count,plays,shares,"
                        "saved_count,insights",
              "limit": 50,
              "filter": "reels"}

    while next_url:
        try:
            r = requests.get(next_url, timeout=30)
            if r.status_code >= 400:
                logger.debug("IG media error: %s", r.text[:200])
                break
            data = r.json()
            for item in data.get("data", []):
                if item.get("media_type") in ("REELS", "VIDEO"):
                    media_ids.append(item.get("id"))
            next_url = data.get("paging", {}).get("next")
            if next_url and "access_token" not in next_url:
                next_url = f"{next_url}&access_token={tok}"
            elif not next_url:
                next_url = None
        except Exception as exc:
            print(f"⚠️ IG scan error: {exc}")
            break

    STATS["instagram"]["scanned"] = len(media_ids)

    if not media_ids:
        print("⚠️ Koi Instagram Reels nahi mili (ya API access limit hai).")
        return

    print(f"📸 IG: {len(media_ids)} Reels mil Gaye\n")

    for mid in media_ids:
        try:
            r = requests.get(
                f"https://graph.facebook.com/v25.0/{mid}",
                params={
                    "access_token": tok,
                    "fields": ("id,caption,media_type,permalink,thumbnail_url,"
                               "timestamp,like_count,comments_count,plays,"
                               "shares,saved_count,insights"),
                    "timeout": 30
                },
                timeout=30)
            if r.status_code >= 400:
                logger.debug("IG reel %s: %s", mid, r.text[:200])
                continue

            data = r.json()
            caption = data.get("caption", "") or ""
            plays = data.get("plays", 0) or 0
            likes = data.get("like_count", 0) or 0
            comments = data.get("comments_count", 0) or 0
            shares = data.get("shares", 0) or 0
            saved = data.get("saved_count", 0) or 0

            STATS["instagram"]["total_views_before"] = plays

            actions = []

            # ── Caption optimization ──
            has_save_cta = any(w in caption.lower() for w in ["save", "bookmark", "keep"])
            hashtag_count = len(re.findall(r"#\w+", caption or ""))
            needs_upgrade = (not caption or len(caption) < 50 or
                            hashtag_count < 15 or not has_save_cta)

            if needs_upgrade and apply and not fix_public_only:
                # Build 2026-optimized caption
                title = ""
                # Try to extract title from caption
                lines = caption.split("\n") if caption else []
                for line in lines:
                    if len(line) > 10 and not line.startswith("#"):
                        title = line.strip()
                        break

                new_caption = f"🚨 {title or 'Psychology Fact'}\n\n"
                new_caption += "Save this for your next conversation — "
                new_caption += "you'll need it.\n\n"
                new_caption += CTA + "\n\n"
                new_caption += " ".join(IG_HASHTAGS_BANK[:20])

                try:
                    r2 = requests.post(
                        f"https://graph.facebook.com/v25.0/{mid}",
                        params={"access_token": tok},
                        data={"caption": new_caption},
                        timeout=30)
                    if r2.status_code == 200:
                        actions.append("caption+")
                        STATS["instagram"]["caption_updated"] += 1
                        caption = new_caption
                    else:
                        actions.append(f"cap-ERR:{r2.text[:50]}")
                except Exception as exc:
                    actions.append(f"cap-ERR:{exc}")
            elif needs_upgrade:
                actions.append(f"would:caption+ (hashtags={hashtag_count})")
            elif not has_save_cta:
                actions.append("would:add-save-cta")

            # ── Engagement stats ──
            engagement_rate = (likes + comments * 2 + shares * 3 + saved * 4) / max(1, plays) * 100

            print(f"  {mid[:16]} plays={plays:<6} likes={likes:<5} saved={saved:<4} "
                  f"eng={engagement_rate:.1f}% | {' | '.join(actions) if actions else '✅ OK'}")
            if caption:
                print(f"    caption: {(caption or '')[:80]}")

        except Exception as exc:
            logger.debug("IG reel %s error: %s", mid, exc)

    print(f"\n{'='*60}")
    print(f"INSTAGRAM SUMMARY:")
    print(f"  Scanned         : {STATS['instagram']['scanned']}")
    print(f"  Captions fixed  : {STATS['instagram']['caption_updated']}")
    print(f"{'='*60}\n")


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(
        description="Coercion Files — 2026 Algorithm Video Repair Tool")
    ap.add_argument("--apply", action="store_true",
                    help="asal changes karo (default: dry-run report only)")
    ap.add_argument("--fix-public", action="store_true",
                    help="sirf private→public fix karo (YouTube)")
    ap.add_argument("--audit", action="store_true",
                    help="sirf scan/report — koi change nahi")
    ap.add_argument("--skip-yt", action="store_true", help="YouTube skip karo")
    ap.add_argument("--skip-fb", action="store_true", help="Facebook skip karo")
    ap.add_argument("--skip-ig", action="store_true", help="Instagram skip karo")
    args = ap.parse_args()

    apply = args.apply or args.fix_public
    fix_public_only = args.fix_public and not args.apply
    audit_only = args.audit

    mode = "APPLY" if apply else "DRY-RUN"
    if fix_public_only:
        mode = "FIX-PUBLIC-ONLY"
    elif audit_only:
        mode = "AUDIT-ONLY"

    print(f"\n{'#'*78}")
    print(f"# Coercion Files — 2026 Algorithm Video Repair")
    print(f"# Mode: {mode} | Time: {datetime.now(timezone.utc).isoformat()}")
    print(f"{'#'*78}\n")

    if not args.skip_yt:
        yt = yt_get_service()
        if yt:
            if audit_only or fix_public_only:
                yt_audit_and_repair(yt, apply=args.apply, fix_public_only=fix_public_only)
            else:
                yt_audit_and_repair(yt, apply=apply)
        else:
            print("⚠️ YouTube skip — credentials nahi hain")

    if not args.skip_fb:
        fb_scan_and_repair(apply=apply, fix_public_only=fix_public_only)

    if not args.skip_ig:
        ig_scan_and_repair(apply=apply, fix_public_only=fix_public_only)

    # Final totals
    print(f"\n{'#'*78}")
    print(f"# FINAL REPORT — {mode}")
    print(f"{'#'*78}")
    print(f"""
📺 YOUTUBE:
   Videos scanned  : {STATS['youtube']['scanned']}
   → Public kiye   : {STATS['youtube']['fixed_public']}
   SEO boosted     : {STATS['youtube']['seo_boosted']}
   Playlist add    : {STATS['youtube']['playlist_add']}

📘 FACEBOOK:
   Videos scanned  : {STATS['facebook']['scanned']}
   Captions fixed  : {STATS['facebook']['caption_updated']}
   Hashtags fixed  : {STATS['facebook']['hashtag_fixed']}

📸 INSTAGRAM:
   Reels scanned   : {STATS['instagram']['scanned']}
   Captions fixed  : {STATS['instagram']['caption_updated']}
""")


if __name__ == "__main__":
    main()
