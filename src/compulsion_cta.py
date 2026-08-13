#!/usr/bin/env python3
"""
Coercion Files — Compulsion CTA Engine (V3.3).

Audience ko "like karna majboor" karne ke liye — 8 documented psychology
principles jo Shorts mein likes/comments/saves chalaate hain:

  1. RECIPROCITY   — "is case file ko research karne mein 9 ghante lage...
                      agar isne aapko bachaya to ek like toh banta hai"
  2. ALGORITHM     — "like karo warna algorithm isay kisi aur ko nahi
                      dikhayega jo isay zaroorat hai" (protection altruism)
  3. IDENTITY      — "agar aap woh insaan hain jo aankhein kholta hai,
                      like karo" (self-image commitment)
  4. CLIFFHANGER   — "is trick ka part 2 agle video mein... agar 10k likes
                      aaye" (continuation reward)
  5. CHALLENGE     — "comment karo aap kya karte" (interaction bait)
  6. VALIDATION    — "like agar aapko pehle se pata tha" (ego stroke)
  7. SAVE-VALUE    — "save karo — ye checklist kaam aayegi" (utility)
  8. LOOP-END      — loop-able ending (rewatch = completion + replay signal)

Har script ko 1-2 CTAs milte hain (like + comment/save combo), rotated —
insaan jaisa, spam nahi. Template + LLM dono use karte hain.
"""

from __future__ import annotations

import logging
import random

logger = logging.getLogger("cta")

# ── CTA templates per principle (V3.5: ENGLISH — USA audience ke liye.
# Pehle Roman Urdu mein thay — English TTS Urdu bolta tha aur supervisor
# inhein USA-calibration fail karta tha. Psychology principles same hain.)
CTA_BANK = {
    "reciprocity": [
        "This case file took nine hours to decode. If it taught you "
        "something, one like is earned.",
        "This pattern took weeks to research. A like makes the work worth "
        "it — and I keep bringing real cases like this.",
        "If this video saved or taught you anything — one like. The rest "
        "is on me.",
    ],
    "algorithm": [
        "Hit like — otherwise the algorithm won't show this to someone "
        "who needs to see it before it's too late.",
        "Like this. Every like pushes this video to someone who still "
        "hasn't escaped this pattern.",
        "One like equals one person protected. It tells the algorithm "
        "this matters.",
    ],
    "identity": [
        "If you're the kind of person who keeps their eyes open — hit "
        "like. We recognize each other.",
        "Like if you're one of the people who spots manipulators early. "
        "This is the group that stays safe.",
        "If you're the 'never fold' type — like. These are your people.",
    ],
    "cliffhanger": [
        "Part 2 of this trick drops next week — if this video crosses "
        "10,000 likes. Like it to get it there.",
        "The next case — even darker than this one — comes when this "
        "hits 5,000 likes. You know what to do.",
    ],
    "challenge": [
        "Comment: what would you do in this position? I read every "
        "single comment.",
        "Now tell me — which of these 3 signs have you seen yourself? "
        "Comment below, we're counting.",
        "Comment 'SAFE' if you're sending this to someone. And like so "
        "it actually reaches them.",
    ],
    "validation": [
        "Like if you already knew this pattern was real. Experts spot it "
        "early.",
        "If you've felt this before — like. Your instincts were right.",
    ],
    "save_value": [
        "Save this — the checklist will protect you next year when "
        "someone tries this on you.",
        "Save it. By the time you watch this again, the pattern may "
        "already be working against you. Protect yourself now.",
    ],
    "loop_end": [
        "And this pattern is still running... right now. (Loop-able "
        "ending — rewatch is the signal)",
    ],
}

# Like/comment/save keywords — quality gate inke bina CTA count nahi karta
ENGAGE_WORDS = ("like", "comment", "follow", "save", "share", "hit", "subscribe")


def cta_pair(seed: int | None = None) -> list[str]:
    """1-2 CTAs (like + comment/save combo), rotated — bilkul insaan jaisa.

    Returns 1..2 strings. Kabhi sirf like, kabhi like+comment, kabhi
    like+save — human variety, spam nahi.
    """
    rng = random.Random(seed) if seed is not None else random
    # 1) choose primary principle (algorithm/reciprocity strongest for likes)
    primary = rng.choices(
        ["algorithm", "reciprocity", "identity", "cliffhanger", "validation",
         "challenge", "save_value"],
        weights=[0.22, 0.20, 0.12, 0.10, 0.10, 0.14, 0.12])[0]
    primary_text = rng.choice(CTA_BANK[primary])

    # 2) ~50% chance add a second (comment or save) — combo boosts interaction
    second = None
    if rng.random() < 0.5:
        secondary_pool = ["challenge", "save_value"]
        # don't double the same principle
        pool = [p for p in secondary_pool if p != primary] or secondary_pool
        second = rng.choice(CTA_BANK[rng.choice(pool)])

    out = [primary_text]
    if second:
        out.append(second)
    return out


def has_engagement(text: str) -> bool:
    """True agar text mein like/comment/follow/save ka koi trigger hai."""
    t = (text or "").lower()
    return any(w in t for w in ENGAGE_WORDS)


def build_engaging_last_scene(pillar_key: str | None = None,
                              seed: int | None = None) -> dict:
    """Ek complete final scene — hook + compulsion CTA + comment bait.

    Isay script ke scenes mein append karo (agar CTA missing ho).
    """
    pair = cta_pair(seed)
    # combine into one flowing narration block (voiced)
    lines = " ".join(pair)
    if pillar_key:
        pass  # pillar-specific flavour future
    return {
        "caption": lines,
        "caption_roman": lines,
        "visual": "dark city night rain reflection",
        "emotion": "revelatory",
    }


def llm_cta_instructions() -> str:
    """SYSTEM_PROMPT ke liye — LLM ko compulsion CTA likhne ke rules."""
    return (
        "9. ENGAGEMENT COMPULSION (critical): Beat 4 ends with a NATURAL but "
        "compelling like ask using ONE of these psychology hooks (varied, never "
        "robotic, never 'please like and subscribe'): "
        "(a) reciprocity — 'this took 9 hours to research, one like is earned'; "
        "(b) algorithm-altruism — 'hit like or the algorithm won't show this to "
        "someone who needs it'; "
        "(c) identity — 'if you're the kind of person who opens their eyes, "
        "like this'; "
        "(d) cliffhanger — 'part 2 drops if this hits 10k likes'; "
        "(e) challenge — 'comment what you'd do in this position'. "
        "Add a short comment question 50% of the time. Keep it 1-2 punchy "
        "sentences, authentic documentary voice."
    )
