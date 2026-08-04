#!/usr/bin/env python3
"""
Cognitive Dark V2 — USA-STYLE Platform SEO Packaging.

USA viral-channel conventions applied:
  • TITLES — hook first, KEYWORD in the first 40 chars, power words, Title
    Case, numbers when possible, ≤70 chars for Shorts (best CTR).
  • DESCRIPTIONS — first 2 lines keyword-dense, "What you'll learn" bullets,
    a "chapter" timestamp block, hashtags, CTA, educational disclaimer.
  • TAGS (YouTube) — broad + specific + branded mix, ≤500 chars total.
  • Platform-native copy — every platform gets distinct text (spam signal if
    identical), tuned to each algorithm (FB = comments, IG = saves/shares).
"""

import random

POWER_WORDS = ["Secret", "Instantly", "Never", "Shocking", "Hidden", "Exposed",
               "Deadly", "Silently", "Brutal", "Finally", "Nobody Tells You",
               "They Don't Want You to Know", "Revealed", "Stop", "Master"]

PLATFORM_HASHTAGS = {
    "youtube": ["#psychology", "#darkpsychology", "#psychologyfacts"],
    "facebook": ["#psychology", "#darkpsychology", "#manipulation", "#selfimprovement",
                 "#gaslighting", "#stoicism", "#mindset", "#psychologyfacts"],
    "instagram": ["#psychology", "#darkpsychology", "#psychologyfacts", "#manipulation",
                  "#gaslighting", "#narcissist", "#stoicism", "#mindset", "#mentalhealth",
                  "#selfimprovement", "#bodylanguage", "#emotionalintelligence",
                  "#toxicrelationships", "#psychologytips", "#humanbehavior",
                  "#influence", "#brainhacks", "#factsvideo", "#foryou", "#viral"],
}

CTA_IG = ["Save this for your next conversation.", "Save this — you'll need it.",
          "Tag someone who needs to see this.", "Send this to a friend who settles too easily."]
CTA_FB = ["What would you add? Drop it in the comments.",
          "Agree or disagree? Let's talk in the comments.",
          "Share this with someone who needs to hear it.",
          "Which sign surprised you most? Comment below."]

EDUCATIONAL_DISCLAIMER = (
    "⚠️ For educational purposes only — learn to recognize and protect yourself. "
    "Not a substitute for professional advice.")

CHAPTER_TEMPLATE = """⏱ CHAPTERS:
00:00 The Hook
00:05 What's Really Happening
00:12 The Pattern Nobody Sees
00:20 Why It Works On You
00:28 How To Protect Yourself"""


def _title_case_word(w: str, first: bool, stop: set) -> str:
    # Preserve acronyms (FBI, CIA, MKUltra) — all-caps tokens stay as-is
    if w.isupper() and len(w) >= 2:
        return w
    if first or w.lower() not in stop:
        return w.capitalize()
    return w.lower()


def _power_title(hook: str, max_len: int = 70) -> str:
    """USA-style title: hook-first, Title Case, keyword density, ≤ max_len."""
    t = hook.strip()
    # strip trailing punctuation for cleaner titles
    t = t.rstrip("?!.").strip()
    if len(t.split()) <= 4 and random.random() < 0.5:
        t = f"{t}: {random.choice(POWER_WORDS)}"
    # V2.1 FIX: rebuild words AFTER the power-word append (V2 used the stale
    # pre-append list, so the power word silently never appeared).
    words = t.split()
    stop = {"a", "an", "the", "and", "or", "but", "of", "to", "in", "on", "for",
            "with", "at", "by", "is", "are", "you", "your", "it", "its"}
    tt = " ".join(_title_case_word(w, i == 0, stop) for i, w in enumerate(words))
    return tt[:max_len]


def _title(script: dict, platform: str) -> str:
    hook = script.get("hook", "") or script.get("title", "")
    if platform == "youtube":
        t = _power_title(hook, 70)
        # ensure a keyword appears in the first 40 chars
        keyword = script.get("pillar_name", "")[:18] or "Psychology"
        if keyword.lower() not in t.lower() and len(t) < 55:
            t = f"{t} | {keyword}"
        return t[:100]
    if platform == "facebook":
        return hook[:58]  # FB feed shows ~58 chars fully
    if platform == "instagram":
        return hook[:55]
    return _power_title(hook, 70)[:100]


def _description(script: dict, platform: str) -> str:
    hook = script.get("hook", "")
    key_points = script.get("key_points", "")
    if platform == "youtube":
        keyword = script.get("pillar_name", "psychology")
        desc = (f"{script.get('title','')} — {hook}\n"
                f"{keyword}: how manipulation works, why it works on you, and "
                f"exactly how to protect yourself.\n\n"
                f"{CHAPTER_TEMPLATE}\n\n"
                f"🔍 WHAT YOU'LL LEARN:\n{key_points}\n\n"
                f"📌 SUBSCRIBE for daily psychology shorts — new uploads daily.\n"
                f"{EDUCATIONAL_DISCLAIMER}\n\n"
                f"{' '.join(PLATFORM_HASHTAGS['youtube'])}")
        return desc[:4500]
    if platform == "facebook":
        first = random.choice([
            f"🚨 {hook}",
            f"🧠 {hook}",
            f"Most people never notice this pattern. {hook}",
        ])
        cta = random.choice(CTA_FB)
        desc = (f"{first}\n\n{key_points}\n\n"
                f"{cta}\n\n{EDUCATIONAL_DISCLAIMER}\n\n"
                f"{' '.join(PLATFORM_HASHTAGS['facebook'])}")
        return desc[:6300]
    if platform == "instagram":
        cta = random.choice(CTA_IG)
        tags = PLATFORM_HASHTAGS["instagram"][:]
        random.shuffle(tags)
        desc = (f"{hook}\n\n{key_points}\n\n"
                f"📌 {cta}\n\n{EDUCATIONAL_DISCLAIMER}\n\n"
                f"{' '.join(tags[:20])}")
        return desc[:2200]
    return script.get("description", "")[:4500]


def _tags(script: dict, platform: str) -> list:
    if platform != "youtube":
        return []  # FB/IG use hashtags in caption
    base = [t.strip() for t in (script.get("tags") or []) if t.strip()]
    pillar = script.get("pillar_name", "")
    if pillar:
        base += [pillar, f"{pillar} psychology", f"{pillar} examples"]
    base += ["psychology facts", "dark psychology", "manipulation",
             "self improvement", "mindset"]
    # dedupe, keep order
    seen, out = set(), []
    for t in base:
        k = t.lower()
        if k not in seen:
            seen.add(k); out.append(t)
    # ≤500 chars total
    final, total = [], 0
    for t in out:
        if total + len(t) + 1 > 500:
            break
        final.append(t); total += len(t) + 1
    return final


def build_platform_package(script: dict, platform: str) -> dict:
    """Return {title, description, tags, hashtags, hook} for a platform."""
    return {
        "platform": platform,
        "title": _title(script, platform),
        "description": _description(script, platform),
        "tags": _tags(script, platform),
        "hashtags": PLATFORM_HASHTAGS.get(platform, []),
        "hook": script.get("hook", ""),
    }


if __name__ == "__main__":
    import sys
    sys.path.insert(0, "src")
    from script_generator import generate_script
    s = generate_script()
    for p in ("youtube", "facebook", "instagram"):
        pkg = build_platform_package(s, p)
        print(f"\n=== {p.upper()} ===")
        print("TITLE :", pkg["title"])
        print("DESC  :", pkg["description"][:150].replace("\n", " | "))
        print("TAGS  :", pkg["tags"][:6])
