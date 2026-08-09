#!/usr/bin/env python3
"""
Cognitive Dark — Viral Intelligence (V2.9).

Har 2026 viral channel jo karta hai uski PATTERN intelligence — formula se,
luck se nahi:

  • TITLE FORMULAS  — "Stop doing X", "Why smart people do Y", "The Z nobody
    sees", number-driven, question-driven, curiosity-gap. Scored against real
    top-channel titles.
  • HOOK SCORING    — 2-second pattern-interrupt quality check (length,
    power words, curiosity gap, personal stake).
  • VIRAL FINGERPRINT — aapki APNI best videos se seekhta hai: jo formula sab
    se zyada views/reward laya, usay classify karke aage use karta hai.
  • SUGGESTIONS     — script generator ke liye "abhi kya pattern use karo"
    ka chhota sa decision card, jo LLM prompt mein inject hota hai.

Data sources (sab PUBLIC, koi fake data nahi):
  1. data/competitor_seed.txt          — real top-channel titles (seeded)
  2. data/competitor_videos.json       — real competitor data (market_intel)
  3. ML reward history (aapki apni)    — kya actually chala
  4. YouTube API live search           — agar key ho to live top videos

Ye module READ-ONLY hai ML store par — koi race nahi.
"""

from __future__ import annotations

import json
import logging
import random
import re
from collections import defaultdict

from config.settings import DATA_DIR

logger = logging.getLogger("viral_intel")

COMPETITOR_FILE = DATA_DIR / "competitor_videos.json"
SEED_FILE = DATA_DIR / "competitor_seed.txt"

# ── documented 2026 viral title formulas (from top psychology/true-crime
# faceless channels — the recurring shapes, not fabricated view counts) ──
TITLE_FORMULAS = {
    "stop_command": {
        "pattern": re.compile(r"^(stop|never|don'?t|quit)\b", re.I),
        "why": "Direct command + negative space = curiosity gap (what am I doing wrong?)",
        "base": 1.25,
    },
    "question": {
        "pattern": re.compile(r"\b(why|how|what|who|when|do you|are you|would you|can you)\b", re.I),
        "why": "Questions open a knowledge gap the algorithm feeds on",
        "base": 1.10,
    },
    "number": {
        "pattern": re.compile(r"\b\d+\b"),
        "why": "Specific numbers = specificity signal (clickable, list-able)",
        "base": 1.05,
    },
    "reveal": {
        "pattern": re.compile(r"\b(revealed?|secret|hidden|exposed|truth|inside|behind|real)\b", re.I),
        "why": "Revelation framing = high CTR for psychology niches",
        "base": 1.15,
    },
    "curiosity_gap": {
        "pattern": re.compile(r"\b(nobody|everyone|they|never knew|didn'?t tell|won'?t say)\b", re.I),
        "why": "'Nobody tells you' = the classic faceless-shorts open loop",
        "base": 1.20,
    },
    "warning": {
        "pattern": re.compile(r"\b(warning|watch out|danger|red flag|signs|trap|scam)\b", re.I),
        "why": "Risk/self-protection framing is this niche's top performer",
        "base": 1.18,
    },
    "case_story": {
        "pattern": re.compile(r"\b(case|story|confession|experiment|files|files #)\b", re.I),
        "why": "True-crime story framing holds retention 2-3x longer than fact lists",
        "base": 1.12,
    },
}

HOOK_QUALITY = {
    "max_words": 9,
    "power_words": {"stop", "never", "secret", "why", "how", "you", "your",
                    "they", "this", "warning", "truth", "everyone", "nobody",
                    "danger", "lies", "trick", "trap", "instantly"},
    "low_energy": {"maybe", "sometimes", "perhaps", "kinda", "sorta", "some"},
}


# ─────────────────────────────────────────────────────────────
# Title pattern analysis
# ─────────────────────────────────────────────────────────────
def analyze_titles(titles: list[str]) -> dict:
    """Score how viral the given titles are, per formula. Returns stats."""
    if not titles:
        return {"n": 0, "formula_scores": {}, "avg_score": 0.0}
    formula_hits = defaultdict(int)
    total = 0.0
    for t in titles:
        if not isinstance(t, str) or not t.strip():
            continue
        total += 1
        for name, f in TITLE_FORMULAS.items():
            if f["pattern"].search(t):
                formula_hits[name] += 1
    n = total or 1
    scores = {}
    for name, f in TITLE_FORMULAS.items():
        freq = formula_hits.get(name, 0) / n
        if freq > 0:
            scores[name] = {
                "share": round(freq, 3),
                "score": round(f["base"] * (0.7 + 0.6 * freq), 3),
                "why": f["why"],
            }
    ranked = sorted(scores.items(), key=lambda kv: kv[1]["score"], reverse=True)
    return {"n": int(total), "formula_scores": scores,
            "avg_score": round(sum(s["score"] for s in scores.values()) /
                               max(1, len(scores)), 3),
            "top_formulas": [k for k, _ in ranked[:4]]}


def score_title(title: str) -> dict:
    """Score ONE title against the viral formulas (0..~1.6)."""
    if not title:
        return {"score": 0.0, "formulas": []}
    hits = []
    for name, f in TITLE_FORMULAS.items():
        if f["pattern"].search(title):
            hits.append({"formula": name, "score": f["base"], "why": f["why"]})
    if not hits:
        return {"score": 0.4, "formulas": [], "note": "no viral formula matched"}
    # cap: 3+ formulas quickly saturate; combine log-ish
    base = max(h["score"] for h in hits)
    bonus = 0.05 * (len(hits) - 1)
    return {"score": round(min(1.6, base + bonus), 3),
            "formulas": [h["formula"] for h in hits],
            "top_formula": hits[0]["formula"]}


def score_hook(hook: str) -> dict:
    """Score a 2-second hook: length, power words, energy, curiosity."""
    if not hook:
        return {"score": 0.0, "issues": ["empty hook"]}
    words = re.findall(r"[A-Za-z']+", hook.lower())
    n_words = len(words)
    issues, bonus = [], 0.0
    if n_words > HOOK_QUALITY["max_words"]:
        issues.append(f"{n_words} words — target ≤ {HOOK_QUALITY['max_words']} "
                      "(first 2 seconds matter)")
    power = sum(1 for w in words if w in HOOK_QUALITY["power_words"])
    low = sum(1 for w in words if w in HOOK_QUALITY["low_energy"])
    bonus += min(0.5, 0.12 * power)
    if low:
        issues.append(f"low-energy words: {low} — kill 'maybe/sometimes'")
    if len(hook) > 90:
        issues.append(f"{len(hook)} chars — on-screen cap 90")
    # question or imperative = pattern interrupt
    if re.search(r"\b(why|how|stop|never|don'?t|watch|look)\b", hook, re.I):
        bonus += 0.2
    score = round(min(1.6, 0.55 + bonus - 0.08 * len(issues)), 3)
    return {"score": score, "issues": issues, "power_words": power}


# ─────────────────────────────────────────────────────────────
# Virality index — combined, from ALL data
# ─────────────────────────────────────────────────────────────
def virality_index(ml_data: dict = None) -> dict:
    """One number + breakdown: how viral-ready is the system right now.

    Combines: seed-title patterns, our own best-video fingerprint, and
    (if present) live competitor data.
    """
    seed_titles = []
    if SEED_FILE.exists():
        seed_titles = [ln.strip() for ln in SEED_FILE.read_text(encoding="utf-8").splitlines()
                       if ln.strip() and not ln.startswith("#")]
    comp = []
    if COMPETITOR_FILE.exists():
        try:
            comp = json.loads(COMPETITOR_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            comp = []
    titles = seed_titles + [v.get("title", "") for v in comp if isinstance(v, dict)]

    pattern = analyze_titles(titles)

    # own best-video fingerprint (from ML reward history + videos)
    own = _own_fingerprint(ml_data)

    total_score = round(0.55 * pattern.get("avg_score", 0.0) +
                        0.30 * own.get("avg_score", 0.0) +
                        0.15 * min(1.0, pattern.get("n", 0) / 60), 3)
    return {
        "index": total_score,
        "grade": _grade(total_score),
        "patterns_learned": pattern.get("n", 0),
        "top_title_formulas": pattern.get("top_formulas", []),
        "own_fingerprint": own,
        "recommendations": _recommendations(pattern, own),
    }


def _own_fingerprint(ml_data: dict | None) -> dict:
    if not ml_data:
        return {"n": 0, "avg_score": 0.0, "best_formula": None}
    videos = ml_data.get("videos", [])
    if not videos:
        return {"n": 0, "avg_score": 0.0, "best_formula": None}
    scored = []
    for v in videos[-40:]:
        title = v.get("title") or v.get("hook") or ""
        s = score_title(title)
        # crude performance proxy: hooks from high-n arms are 'proven'
        arm_key = v.get("arm_key")
        arm = ml_data.get("arms", {}).get(arm_key, {})
        if arm.get("n", 0) > 2:
            mean = arm["rewards"] / max(1, arm["n"])
            s = dict(s, score=s["score"] * (0.7 + 0.3 * min(2.0, mean)))
        scored.append(s)
    avg = round(sum(s["score"] for s in scored) / len(scored), 3)
    formulas = [f for s in scored for f in s.get("formulas", [])]
    top = None
    if formulas:
        counts = defaultdict(int)
        for f in formulas:
            counts[f] += 1
        top = max(counts.items(), key=lambda kv: kv[1])[0]
    return {"n": len(scored), "avg_score": avg, "best_formula": top}


def _grade(score: float) -> str:
    if score >= 0.9:
        return "A+ — viral-ready"
    if score >= 0.75:
        return "A — strong"
    if score >= 0.6:
        return "B — solid, keep tuning"
    if score >= 0.45:
        return "C — needs work"
    return "D — early stage"


def _recommendations(pattern: dict, own: dict) -> list[str]:
    recs = []
    if not pattern.get("top_formulas"):
        recs.append("Add 20+ real competitor titles to data/competitor_seed.txt "
                    "so the pattern engine has data to learn from.")
        return recs
    top = pattern["top_formulas"][0]
    recs.append(f"Write titles with the '{top}' formula — it's the strongest "
                "pattern in the niche right now.")
    if own.get("best_formula") and own["best_formula"] != top:
        recs.append(f"Your own best formula is '{own['best_formula']}' — keep "
                    f"using it, but test '{top}' variants too.")
    elif own.get("best_formula"):
        recs.append(f"Your proven formula '{own['best_formula']}' matches the "
                    "niche — double down.")
    recs.append("Hook ≤ 9 words, pattern-interrupt in the first 2 seconds "
                "(command/question).")
    return recs[:3]


def suggestion_card(ml_data: dict = None) -> dict:
    """Short decision card injected into the script-generator prompt."""
    idx = virality_index(ml_data)
    formulas = idx["top_title_formulas"] or ["question"]
    return {
        "title_formulas_to_use": formulas[:3],
        "hook_rule": ("Pattern-interrupt, ≤ 9 words, command or question in "
                      "the first 2 seconds."),
        "index_grade": idx["grade"],
        "recommendations": idx["recommendations"],
    }


def pick_title_variant(hook: str, candidates: list[str]) -> str:
    """Pick the highest-scoring title variant against viral formulas."""
    if not candidates:
        return hook[:70]
    scored = [(score_title(c)["score"], c) for c in candidates]
    scored.sort(reverse=True)
    return scored[0][1]


def random_boosted_hook() -> str:
    """Occasionally suggest a hook style tuned to the top pattern (randomized)."""
    starters = [
        "Stop letting them", "Why smart people", "Nobody tells you",
        "The trick they", "How they get you", "Never say this",
        "The warning they ignored", "Watch what they say",
    ]
    return random.choice(starters)
