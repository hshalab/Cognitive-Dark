#!/usr/bin/env python3
"""
Cognitive Dark — mukammal Facebook Page metrics report.

Page-level (followers, category, about, published) + har video/reel ke
views, likes, comments, shares, reach, impressions aur created time.

GitHub Actions mein secrets (FB_PAGE_ID, FB_ACCESS_TOKEN) ke saath chalta hai.
Token commit/print nahi hota.
"""

import json
import os
import sys
from datetime import datetime, timezone

import requests

V = "v25.0"
GRAPH = "https://graph.facebook.com"


def get(url, params):
    r = requests.get(url, params=params, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    return r.json()


def page_info(tok, page):
    d = get(f"{GRAPH}/{V}/{page}", {
        "access_token": tok,
        "fields": ("id,name,username,category,about,description,followers_count,"
                   "fan_count,is_published,link,likes,"
                   "talking_about_count,verification_status,were_here_count"),
    })
    return d


def page_insights(tok, page):
    metrics = [
        "page_daily_follows", "page_follows", "page_impressions",
        "page_impressions_unique", "page_engaged_users", "page_post_engagements",
        "page_video_views", "page_video_view_time",
        "page_content_activity",
    ]
    out = {}
    for m in metrics:
        try:
            d = get(f"{GRAPH}/{V}/{page}/insights", {
                "access_token": tok, "metric": m, "period": "days_28",
            })
            vals = d.get("data", [])
            if vals:
                v = vals[0].get("values", [])
                out[m] = v[-1].get("value") if v else None
        except Exception:
            out[m] = None
    return out


def all_videos(tok, page):
    """Saare videos/reels with stats (pagination)."""
    out, url = [], f"{GRAPH}/{V}/{page}/videos"
    params = {
        "access_token": tok,
        "fields": ("id,title,description,created_time,updated_time,length,"
                   "views,likes.summary(true),comments.summary(true),"
                   "permalink_url,picture,status"),
        "limit": 100,
    }
    while url:
        d = get(url, params)
        for v in d.get("data", []):
            v["likes_count"] = (v.get("likes", {}) or {}).get("summary", {}).get("total_count", 0)
            v["comments_count"] = (v.get("comments", {}) or {}).get("summary", {}).get("total_count", 0)
            # shares is not a direct /videos field — fetch per video (best effort)
            v["shares_count"] = 0
            try:
                sd = get(f"{GRAPH}/{V}/{v['id']}",
                         {"access_token": tok, "fields": "shares"})
                v["shares_count"] = (sd.get("shares", {}) or {}).get("count", 0)
            except Exception:
                pass
            out.append(v)
        url = d.get("paging", {}).get("next")
        params = None  # next URL already has params
    return out


def main():
    tok = os.environ.get("FB_ACCESS_TOKEN", "")
    page = os.environ.get("FB_PAGE_ID", "")
    if not tok or not page:
        sys.exit("FB_PAGE_ID / FB_ACCESS_TOKEN env vars required")

    print("=" * 72)
    print("📘 FACEBOOK PAGE — FULL METRICS REPORT")
    print("=" * 72)

    try:
        info = page_info(tok, page)
    except Exception as e:
        print("Page info failed:", e)
        info = {}

    print("\n▸ PAGE")
    print(f"  name        : {info.get('name','?')}")
    print(f"  handle      : @{info.get('username','?')}")
    print(f"  category    : {info.get('category','?')}")
    print(f"  followers   : {info.get('followers_count', info.get('fan_count','?'))}")
    print(f"  likes       : {info.get('likes','?')}")
    print(f"  talking_about: {info.get('talking_about_count','?')}")
    print(f"  published   : {info.get('is_published','?')}")
    print(f"  link        : {info.get('link','?')}")
    about = (info.get("about") or "").strip()
    if about:
        print(f"  about       : {about[:120]}")

    print("\n▸ 28-DAY PAGE INSIGHTS")
    try:
        ins = page_insights(tok, page)
        for k, v in ins.items():
            print(f"  {k:28}: {v}")
    except Exception as e:
        print("  insights failed:", e)

    print("\n▸ VIDEOS / REELS")
    try:
        vids = all_videos(tok, page)
    except Exception as e:
        print("  videos fetch failed:", e)
        vids = []

    if not vids:
        print("  (koi video nahi mili — page par abhi tak upload nahi hui)")
        return

    total_views = total_likes = total_comments = total_shares = 0
    vids.sort(key=lambda v: v.get("created_time", ""), reverse=True)
    print(f"  {'created':<11} {'views':>7} {'likes':>6} {'cmts':>5} {'shrs':>5}  title")
    print("  " + "-" * 64)
    for v in vids:
        views = int(v.get("views", 0) or 0)
        likes = v.get("likes_count", 0)
        cmts = v.get("comments_count", 0)
        shrs = v.get("shares_count", 0)
        total_views += views
        total_likes += likes
        total_comments += cmts
        total_shares += shrs
        ct = (v.get("created_time", "")[:10])
        title = (v.get("title") or v.get("description") or "(no title)")[:42].replace("\n", " ")
        print(f"  {ct:<11} {views:>7} {likes:>6} {cmts:>5} {shrs:>5}  {title}")

    print("  " + "-" * 64)
    n = len(vids)
    print(f"  TOTAL ({n} videos): views={total_views}  likes={total_likes}  "
          f"comments={total_comments}  shares={total_shares}")
    if total_views:
        print(f"  AVERAGE per video: views={total_views//n}  "
              f"engagement={((total_likes+total_comments+total_shares)/max(total_views,1)*100):.2f}%")

    # JSON dump for ML/records
    report = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "page": info,
        "videos": [{k: x for k, x in v.items() if k != "video_insights"} for v in vids],
        "totals": {"videos": n, "views": total_views, "likes": total_likes,
                   "comments": total_comments, "shares": total_shares},
    }
    os.makedirs("data", exist_ok=True)
    with open("data/facebook_metrics.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("\n  ✅ data/facebook_metrics.json saved")


if __name__ == "__main__":
    main()
