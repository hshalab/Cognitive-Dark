#!/usr/bin/env python3
"""
Cognitive Dark V2 — Platform-Specific SEO Packaging.

Each platform gets NATIVE, distinct copy (different titles, captions, hashtag
sets, line breaks). Identical spammy text across platforms is a spam signal —
this module guarantees platform adaptation → supports the "0% spam detection" goal.

Platform algorithms (applied here):
  • YouTube : keyword in title first 60 chars, description keyword-dense in
              first 2 lines, ≤500 total tag chars, 2-3 hashtags in description.
  • Facebook: first line = hook, 3-8 relevant hashtags, CTA + engagement
              question to drive comments (FB's top signal).
  • Instagram: save-value caption, 15-20 hashtags, line breaks, "save this"
              CTA (IG rewards saves/shares).
"""

import random

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


def _title(script: dict, platform: str) -> str:
    title = script.get("title", "")[:70]
    if platform == "youtube":
        return title[:100]
    if platform == "facebook":
        # FB: punchy, curiosity, ≤60 chars shows fully in feed
        return (script.get("hook", title)[:58])
    if platform == "instagram":
        return (script.get("hook", title)[:55])
    return title[:100]


def _description(script: dict, platform: str) -> str:
    hook = script.get("hook", "")
    key_points = script.get("key_points", "")
    if platform == "youtube":
        desc = (f"{script.get('title','')} — {hook}\n\n"
                f"Learn the psychology behind influence & manipulation and how to "
                f"protect yourself. {EDUCATIONAL_DISCLAIMER}\n\n"
                f"🔍 What you'll learn:\n{key_points}\n\n"
                f"📌 Subscribe for daily psychology content\n\n"
                f"{' '.join(PLATFORM_HASHTAGS['youtube'])}")
        return desc[:4500]
    if platform == "facebook":
        first_line = random.choice([
            f"🚨 {hook}",
            f"🧠 {hook}",
            f"Most people never notice this pattern. {hook}",
        ])
        cta = random.choice(CTA_FB)
        desc = (f"{first_line}\n\n{script.get('key_points','')}\n\n"
                f"{cta}\n\n{EDUCATIONAL_DISCLAIMER}\n\n"
                f"{' '.join(PLATFORM_HASHTAGS['facebook'])}")
        return desc[:6300]  # FB 63,206 char limit — plenty
    if platform == "instagram":
        cta = random.choice(CTA_IG)
        tags = PLATFORM_HASHTAGS["instagram"]
        random.shuffle(tags)
        desc = (f"{hook}\n\n{script.get('key_points','')}\n\n"
                f"📌 {cta}\n\n"
                f"{EDUCATIONAL_DISCLAIMER}\n\n"
                f"{' '.join(tags[:20])}")
        return desc[:2200]
    return script.get("description", "")[:4500]


def _tags(script: dict, platform: str) -> list:
    base = [t.strip() for t in (script.get("tags") or []) if t.strip()][:15]
    if platform == "youtube":
        # ≤500 chars total for tags
        out, total = [], 0
        for t in base:
            if total + len(t) + 1 > 500:
                break
            out.append(t); total += len(t) + 1
        return out
    return base  # FB/IG use hashtags in caption instead


def build_platform_package(script: dict, platform: str) -> dict:
    """Return {title, description, tags, hashtags, publish_at_hint}."""
    return {
        "platform": platform,
        "title": _title(script, platform),
        "description": _description(script, platform),
        "tags": _tags(script, platform),
        "hashtags": PLATFORM_HASHTAGS.get(platform, []),
        "hook": script.get("hook", ""),
    }


if __name__ == "__main__":
    import json, sys
    sys.path.insert(0, "src")
    from script_generator import generate_script
    s = generate_script()
    for p in ("youtube", "facebook", "instagram"):
        pkg = build_platform_package(s, p)
        print(f"\n=== {p.upper()} ===")
        print("TITLE :", pkg["title"])
        print("DESC  :", pkg["description"][:140].replace("\n", " | "))
        print("TAGS  :", pkg["tags"][:5])
