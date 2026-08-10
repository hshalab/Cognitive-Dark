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

# ── CTA templates per principle ─────────────────────────────
CTA_BANK = {
    "reciprocity": [
        "Is case file ko decode karne mein 9 ghante lage. Agar isne aapko "
        "kuch sikhaya, ek like toh banta hai.",
        "Is pattern ko research karne mein hafte lage. Like karo — yeh meri "
        "mehnat ko worth-it banata hai, aur main aise aur cases laata hoon.",
        "Agar is video ne aapka kuch bacha ya sikhlaya — ek like. Baqi "
        "meri taraf se.",
    ],
    "algorithm": [
        "Hit like — warna algorithm isay kisi aur ko nahi dikhayega jo "
        "isay bachne ke liye zaroorat rakhta hai.",
        "Like karo. Har like is video ko us insaan tak pahunchata hai jo "
        "is pattern se abhi kabhi nikla hi nahi.",
        "Ek like = ek insaan protected. Ye algorithm ko batata hai ke ye "
        "matter karta hai.",
    ],
    "identity": [
        "Agar aap woh insaan hain jo apni aankhein kholta hai — like karo. "
        "Hum pehchan lete hain ek doosre ko.",
        "Like karo agar aap manipulator ko pehchanne wale logon mein se hain. "
        "Ye woh group hai jo bachta hai.",
        "Agar aap 'kabhi mat jhuko' wale hain — like. Yeh aapke log hain.",
    ],
    "cliffhanger": [
        "Is trick ka part 2 agle hafte — agar ye video 10,000 likes cross "
        "kare. Like karo isay wahan pahunchane ke liye.",
        "Aage ka case — jo isse bhi zyada dark hai — tab aayega jab ye "
        "5,000 likes tak pahunche. Like karo.",
    ],
    "challenge": [
        "Comment karo: agar aap is position mein hote to kya karte? Main "
        "har comment padhta hoon.",
        "Ab batao — in 3 signs mein se kaunsa aapne khud dekha hai? "
        "Comment karo, hum count karte hain.",
        "Comment 'SAFE' agar aap yeh kisi ko bhej rahe ho. Like bhi karo "
        "taake ye reach kare.",
    ],
    "validation": [
        "Like karo agar aapko pehle se pata tha ke ye pattern chalta hai. "
        "Experts hi isay pehchante hain.",
        "Agar aapne yeh pehle feel kiya tha — like. Aapki instincts theek "
        "thin.",
    ],
    "save_value": [
        "Isay save karo — ye checklist agle saal kaam aayegi jab kabhi "
        "koi isay try kare.",
        "Save karo. Jab tak aap isay dobara dekho, ye pattern aapke "
        "khilaf kaam kar raha hai. Abhi protect karo.",
    ],
    "loop_end": [
        "Aur yeh pattern abhi bhi chalta hai... isi waqt. (Loop-able end — "
        "rewatch = signal)",
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
