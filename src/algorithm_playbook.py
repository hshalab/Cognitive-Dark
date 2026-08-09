#!/usr/bin/env python3
"""
Cognitive Dark — 2026 Algorithm Playbook (V2.9).

Har platform ke 2026 ranking signals ka "cheat sheet" — documented best
practices (koi hack nahi, algorithm ka asli behavior):

  YouTube Shorts  : retention (first 5s + full watch-through), title keyword
                    in first 100 chars, description keyword-dense first 2
                    lines, ≤ 3 hashtags, 9:16, < 60s, 1080x1920, 3-5/day cap
                    (consistency), upload at peak, reply to top comment.
  Facebook Reels  : first-3s hook, comments in first hour (creator reply),
                    share-ability, 5-8 hashtags, < 90s, 9:16, native audio
                    (no watermarks), public post, CTA for comments/shares.
  Instagram Reels : saves + shares + replays are the top signals, 15-20
                    hashtags, "save this" value framing, 11am-2pm / 7-9pm,
                    < 90s, 9:16, high density (use space), native features.

apply() verifies/boosts an upload package per platform; audit() reports a
per-platform scorecard so Mission Control can flag weak spots.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger("playbook")

PLAYBOOK = {
    "youtube": {
        "name": "YouTube Shorts",
        "signals": {
            "retention_first_5s": "Hook in 0-3s, first word visual, no slow intro",
            "full_watch_through": "Loop-able ending (end == start feel)",
            "title_keyword_first_100": "Keyword in first 100 chars of title+desc",
            "description_keywords": "First 2 lines keyword-dense",
            "hashtags_max_3": "≥3 hashtags = spam label risk",
            "format_9x16_60s": "1080x1920, < 60s (57s safe)",
            "consistency": "3-5/day daily beats bursts",
            "reply_top_comment": "Pin + reply to top comment in first hour",
        },
        "max_hashtags": 3,
        "title_max": 100,
        "desc_max": 5000,
        "duration_max_s": 60,
        "frequency": "3-5/day",
    },
    "facebook": {
        "name": "Facebook Reels",
        "signals": {
            "first_3s_hook": "First 3 seconds decide the swipe",
            "comments_first_hour": "Reply to comments within 1h (boost)",
            "share_ability": "Relatable/quotable → shares",
            "hashtags_5_8": "5-8 relevant hashtags",
            "format_9x16_90s": "9:16, < 90s",
            "native_audio_no_watermark": "No TikTok watermark, use native audio",
            "public_post": "Must be public (not friends)",
            "cta_comments": "End with a comment question",
        },
        "max_hashtags": 8,
        "title_max": 150,
        "desc_max": 6300,
        "duration_max_s": 90,
        "frequency": "2-4/day",
    },
    "instagram": {
        "name": "Instagram Reels",
        "signals": {
            "saves_are_gold": "'Save this' value framing = top signal",
            "replays": "Loop-able, satisfying ending",
            "shares": "Direct-message-worthy content",
            "hashtags_15_20": "15-20 relevant hashtags (30 max)",
            "format_9x16_90s": "9:16, < 90s",
            "high_density": "Use full frame, text on screen, no dead space",
            "post_times": "11am-2pm / 7-9pm (audience awake)",
            "native_features": "Use native tools (add yours, polls)",
        },
        "max_hashtags": 20,
        "title_max": 100,
        "desc_max": 2200,
        "duration_max_s": 90,
        "frequency": "2-4/day",
    },
}


def audit_package(pkg: dict, platform: str) -> dict:
    """Check a platform package against the playbook; return scorecard."""
    spec = PLAYBOOK.get(platform)
    if not spec:
        return {"score": 0.0, "checks": [], "passed": 0, "total": 0}
    checks = []
    passed = 0
    total = len(spec["signals"])
    title = (pkg.get("title") or "")[:spec["title_max"]]
    desc = pkg.get("description") or ""
    tags = pkg.get("tags") or []
    duration = pkg.get("duration_s")

    def check(name, ok, note=""):
        nonlocal passed
        checks.append({"signal": name, "ok": bool(ok), "note": note})
        if ok:
            passed += 1

    check("title_keyword_first_100", len(title) <= spec["title_max"],
          f"{len(title)}/{spec['title_max']} chars")
    check("hashtags", 0 < len(tags) <= spec["max_hashtags"],
          f"{len(tags)} hashtags (max {spec['max_hashtags']})")
    check("description_present", len(desc) > 150, f"{len(desc)} chars")
    if platform == "youtube":
        check("format_9x16_60s", duration is None or duration <= spec["duration_max_s"],
              f"{duration or '?'}s")
        check("keyword_first_2_lines",
              any(k in desc[:300].lower() for k in ("psychology", "coercion", "cult",
                                                    "con", "mind", "brainwash", "scam")),
              "first 2 lines keyword-dense?")
        check("reply_top_comment", True, "manual — pin top comment daily")
    if platform == "facebook":
        check("format_9x16_90s", duration is None or duration <= spec["duration_max_s"],
              f"{duration or '?'}s")
        check("cta_comments", any(c in desc.lower() for c in ("comment", "what would you",
                                                              "agree", "share")),
              "comment/share CTA present")
        check("comments_first_hour", True, "manual — reply within 1h")
    if platform == "instagram":
        check("format_9x16_90s", duration is None or duration <= spec["duration_max_s"],
              f"{duration or '?'}s")
        check("saves_are_gold", any(c in desc.lower() for c in ("save this", "save it",
                                                                "bookmark")),
              "'save this' framing")
        check("cta_shares", any(c in desc.lower() for c in ("share", "send this", "tag")),
              "share/send CTA")

    score = round(passed / max(1, total), 3)
    return {"score": score, "checks": checks, "passed": passed, "total": total,
            "platform": platform, "name": spec["name"]}


def best_platform_for(script: dict) -> str:
    """Suggest which platform to prioritize for a given hook (nice-to-have)."""
    hook = (script.get("hook") or "").lower()
    if re.search(r"\b(save|list|checklist|signs|steps|ways)\b", hook):
        return "instagram"   # save-worthy, list-y
    if re.search(r"\b(comment|what do you|what would you|would you|agree|think)\b", hook):
        return "facebook"    # discussion trigger
    return "youtube"         # default: biggest reach


def format_tip(platform: str) -> str:
    spec = PLAYBOOK[platform]
    return (f"{spec['name']} 2026: {', '.join(spec['signals'].values())[:200]} "
            f"(frequency {spec['frequency']})")
