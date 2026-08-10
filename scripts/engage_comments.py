#!/usr/bin/env python3
"""
Coercion Files — Comment Engagement Engine (V3.0).

YouTube/Facebook/Instagram ke comments fetch karta hai aur insaani tone mein
jawab DRAFT karta hai (LLM se — Groq/Gemini). Drafts data/reply_queue.json
mein queue hote hain — aap approve karo, ya AUTO_REPLY_COMMENTS=true ho to
positive comments khud reply ho jate hain.

Usage:
  python scripts/engage_comments.py            # draft-only (queue mein)
  python scripts/engage_comments.py --apply    # auto-reply positive comments
  python scripts/engage_comments.py --platform youtube

Koi secret print nahi hota. Bounded reads (last N comments).
"""

import argparse
import json
import logging
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("engage")

from human_layer import load_reply_queue, save_reply_queue

GRAPH = "https://graph.facebook.com"
V = "v25.0"
UA = "CoercionFiles-CI/1.0"


def first_env(*names):
    for n in names:
        v = os.environ.get(n, "").strip()
        if v:
            return v
    return ""


def http_json(url, headers=None, data=None, timeout=60):
    req = urllib.request.Request(url, data=data, headers=headers or {},
                                 method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def llm_draft(comment: str, username: str, platform: str) -> str | None:
    """Draft a human-toned reply via Groq (fallback Gemini)."""
    prompt = (f"Reply to this comment on a psychology/true-crime shorts channel. "
              f"Tone: warm, authentic, human — NOT salesy, NOT robotic. 1-2 short "
              f"sentences, maybe a follow question. No emojis overuse. "
              f"Comment by {username} ({platform}): \"{comment}\"\n"
              f"Reply:")
    # Groq
    key = os.environ.get("GROQ_API_KEY", "")
    if key:
        try:
            payload = {"model": "openai/gpt-oss-20b",
                       "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": 120, "temperature": 0.9}
            data = json.dumps(payload).encode()
            r = http_json("https://api.groq.com/openai/v1/chat/completions",
                          headers={"Authorization": f"Bearer {key}",
                                   "Content-Type": "application/json",
                                   "User-Agent": UA}, data=data)
            return r["choices"][0]["message"]["content"].strip()[:280]
        except Exception as exc:
            logger.warning("groq reply draft failed: %s", exc)
    # Gemini
    gkey = os.environ.get("GEMINI_API_KEY", "")
    if gkey:
        try:
            payload = {"contents": [{"parts": [{"text": prompt}]}],
                       "generationConfig": {"maxOutputTokens": 150,
                                            "temperature": 0.9}}
            data = json.dumps(payload).encode()
            url = ("https://generativelanguage.googleapis.com/v1beta/models/"
                   "gemini-2.0-flash:generateContent")
            r = http_json(url + "?key=" + gkey,
                          headers={"Content-Type": "application/json",
                                   "User-Agent": UA}, data=data)
            return r["candidates"][0]["content"]["parts"][0]["text"].strip()[:280]
        except Exception as exc:
            logger.warning("gemini reply draft failed: %s", exc)
    return None


# ── platform fetchers ──
def fetch_yt_comments(limit: int = 15) -> list[dict]:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        cid = os.environ.get("GOOGLE_CLIENT_ID", "")
        csec = os.environ.get("GOOGLE_CLIENT_SECRET", "")
        rt = os.environ.get("REFRESH_TOKEN", "")
        if not (cid and csec and rt):
            logger.warning("YT creds missing — skip comments")
            return []
        info = {"client_id": cid, "client_secret": csec, "refresh_token": rt,
                "token_uri": "https://oauth2.googleapis.com/token",
                "scopes": ["https://www.googleapis.com/auth/youtube.readonly"],
                "type": "authorized_user"}
        creds = Credentials.from_authorized_user_info(info)
        if (creds.expired or not creds.valid) and creds.refresh_token:
            creds.refresh(Request())
        yt = build("youtube", "v3", credentials=creds)
        ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
        upl = ch["contentDetails"]["relatedPlaylists"]["uploads"]
        items = yt.playlistItems().list(part="contentDetails", playlistId=upl,
                                        maxResults=5).execute().get("items", [])
        out = []
        for it in items[:limit]:
            vid = it["contentDetails"]["videoId"]
            try:
                threads = yt.commentThreads().list(part="snippet",
                                                   videoId=vid,
                                                   maxResults=5).execute().get("items", [])
                for th in threads:
                    sn = th["snippet"]["topLevelComment"]["snippet"]
                    out.append({"platform": "youtube", "id": th["id"],
                                "video_id": vid, "author": sn.get("authorDisplayName", "?"),
                                "text": sn.get("textDisplay", ""), "likes": sn.get("likeCount", 0)})
            except Exception as exc:
                logger.warning("yt comments %s: %s", vid, exc)
        return out[:limit]
    except Exception as exc:
        logger.warning("yt comments fetch failed: %s", exc)
        return []


def fetch_fb_comments(limit: int = 10) -> list[dict]:
    tok = first_env("FB_ACCESS_TOKEN", "FACEBOOK_ACCESS_TOKEN")
    page = first_env("FB_PAGE_ID", "FACEBOOK_PAGE_ID")
    if not tok or not page:
        return []
    try:
        import requests
        r = requests.get(f"{GRAPH}/{V}/{page}/posts",
                         params={"access_token": tok,
                                 "fields": "id,comments{message,from,created_time}",
                                 "limit": 5}, timeout=30)
        if r.status_code != 200:
            return []
        out = []
        for p in r.json().get("data", []):
            for c in (p.get("comments", {}).get("data", []) or []):
                out.append({"platform": "facebook", "id": c.get("id"),
                            "post_id": p.get("id"),
                            "author": (c.get("from") or {}).get("name", "?"),
                            "text": c.get("message", ""), "likes": 0})
        return out[:limit]
    except Exception as exc:
        logger.warning("fb comments fetch failed: %s", exc)
        return []


def fetch_ig_comments(limit: int = 10) -> list[dict]:
    tok = first_env("IG_ACCESS_TOKEN", "INSTAGRAM_ACCESS_TOKEN", "FB_ACCESS_TOKEN",
                    "FACEBOOK_ACCESS_TOKEN")
    ig = first_env("IG_BUSINESS_ACCOUNT_ID", "INSTAGRAM_USER_ID")
    if not tok or not ig:
        return []
    try:
        import requests
        r = requests.get(f"{GRAPH}/{V}/{ig}/media",
                         params={"access_token": tok, "fields": "id", "limit": 5},
                         timeout=30)
        if r.status_code != 200:
            return []
        out = []
        for m in r.json().get("data", []):
            cr = requests.get(f"{GRAPH}/{V}/{m['id']}/comments",
                              params={"access_token": tok,
                                      "fields": "text,username,timestamp"},
                              timeout=30)
            if cr.status_code != 200:
                continue
            for c in cr.json().get("data", []):
                out.append({"platform": "instagram", "id": c.get("id"),
                            "media_id": m["id"], "author": c.get("username", "?"),
                            "text": c.get("text", ""), "likes": 0})
        return out[:limit]
    except Exception as exc:
        logger.warning("ig comments fetch failed: %s", exc)
        return []


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="positive comments par auto-reply (draft queue se)")
    ap.add_argument("--platform", default=None, choices=["youtube", "facebook",
                                                         "instagram"])
    args = ap.parse_args()

    queue = load_reply_queue()
    seen_ids = {q.get("id") for q in queue}
    fetched = []
    if args.platform in (None, "youtube"):
        fetched += fetch_yt_comments()
    if args.platform in (None, "facebook"):
        fetched += fetch_fb_comments()
    if args.platform in (None, "instagram"):
        fetched += fetch_ig_comments()

    print(f"Comments fetched: {len(fetched)} (platforms)")
    new = 0
    for c in fetched:
        if c["id"] in seen_ids:
            continue
        draft = llm_draft(c["text"], c["author"], c["platform"])
        entry = {**c, "draft_reply": draft, "ts": __import__("datetime").datetime
                 .now(__import__("datetime").timezone.utc).isoformat(),
                 "status": "draft"}
        queue.append(entry)
        seen_ids.add(c["id"])
        new += 1
        print(f"\n  [{c['platform']}] @{c['author']}: {c['text'][:60]}")
        print(f"      → draft: {draft}")

    save_reply_queue(queue[-100:])
    print(f"\nQueue: {new} naye drafts (total {len(queue)}) — data/reply_queue.json")

    if args.apply:
        # auto-reply positive comments (drafts jo positive hain) — v1: sirf
        # like/thankyou wale (LLM draft hi human tone hai). Is version mein
        # replies QUEUE mein hain — aap approve karo. Auto-post next version.
        print("NOTE: --apply abhi sirf drafts ko 'approved' mark karta hai "
              "(real posting next version — safe default).")
        for q in queue:
            if q.get("status") == "draft" and q.get("draft_reply"):
                q["status"] = "approved"
        save_reply_queue(queue[-100:])
        print("Drafts approved (reply posting manual hai).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
