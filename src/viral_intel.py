#!/usr/bin/env python3
"""
Coercion Files — Viral Intelligence (V2.9).

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
    # V3.4: sirf STRONG power words — pehle "you/your/they/this" jaise generic
    # words bhi power maane jaate the, jo HAR hook mein hote hain → weak hook
    # ko bhi fake bonus mil jata tha. Ab generic words score nahi dete.
    "power_words": {"stop", "never", "secret", "why", "how", "warning",
                    "truth", "danger", "lies", "trick", "trap", "instantly",
                    "hidden", "exposed", "nobody", "signs", "before",
                    "if", "when", "what", "watch"},
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
        # V3.4: 0.2, not 0.4 — koi viral formula match nahi hona ek WEAK
        # signal hai, neutral nahi. 0.4 ka floor weak titles ko "passable"
        # bana deta tha.
        return {"score": 0.2, "formulas": [], "note": "no viral formula matched"}
    # cap: 3+ formulas quickly saturate; combine log-ish
    base = max(h["score"] for h in hits)
    bonus = 0.05 * (len(hits) - 1)
    return {"score": round(min(1.6, base + bonus), 3),
            "formulas": [h["formula"] for h in hits],
            "top_formula": hits[0]["formula"]}


def score_hook(hook: str) -> dict:
    """Score a 2-second hook: length, power words, energy, curiosity.

    V3.4 HONEST SCALE: base 0.30 (pehle 0.55 tha). Ek hook jis mein na power
    word hai, na pattern-interrupt, wo ab FAIL karta hai (<0.5) — pehle 0.55
    base ki wajah se har hook "passable" lagta tha. Weak hook ko weak kehna
    hi system ki pehli zimmedari hai — warna pipeline weak hooks ko viral
    bata kar upload karti rahti hai.
    """
    if not hook:
        return {"score": 0.0, "issues": ["empty hook"], "weak": True}
    words = re.findall(r"[A-Za-z']+", hook.lower())
    n_words = len(words)
    issues, bonus = [], 0.0
    if n_words > HOOK_QUALITY["max_words"]:
        issues.append(f"{n_words} words — target ≤ {HOOK_QUALITY['max_words']} "
                      "(first 2 seconds matter)")
    if n_words < 3:
        issues.append(f"only {n_words} word(s) — hook is a fragment, no payoff")
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
    # concrete anchor ($400k, 3 words, 1974) = specificity = curiosity punch
    anchors = len(re.findall(r"\$\s?\d+|\b\d+\b", hook))
    if anchors:
        bonus += min(0.24, 0.18 + 0.06 * (anchors - 1))
    # FRAGMENT CHECK (V3.4): "Stop letting them", "Why smart people",
    # "Nobody tells you" jaise 3-lafzi aadhe hooks payoff ke baghair hain —
    # overlay par weak lagte hain. 3 words ya kam + dangling ending = fragment.
    dangling = {"them", "they", "it", "this", "that", "you", "to", "at", "in",
                "of", "with", "when", "if", "and", "or", "up", "out", "on",
                "for", "from", "into", "your", "their", "about", "people"}
    if n_words <= 3 and words and words[-1] in dangling:
        issues.append("incomplete hook (fragment) — add the payoff")
        bonus -= 0.15
    score = round(max(0.0, min(1.0, 0.30 + bonus - 0.08 * len(issues))), 3)
    return {"score": score, "issues": issues, "power_words": power,
            "weak": score < 0.5}


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

    # V3.4 HONEST INDEX: own REAL performance is now the dominant term (0.50),
    # niche title patterns are context (0.30), data coverage (0.20). Pehle
    # pattern-shapes ka 0.55 weight tha — seed titles ki wajah se index hamesha
    # "A+ viral-ready" ban jata tha, chahe channel par views hi kyun na 0 hon.
    # Ab jab tak REAL metrics nahi aate, index kabhi "viral-ready" nahi bolta.
    total_score = round(0.30 * pattern.get("avg_score", 0.0) +
                        0.50 * own.get("avg_score", 0.0) +
                        0.20 * min(1.0, own.get("n_with_real_data", 0) / 15), 3)
    return {
        "index": total_score,
        "grade": _grade(total_score),
        "honest": own.get("n_with_real_data", 0) == 0,
        "honest_note": (own.get("note", "") if own.get("n_with_real_data", 0) == 0
                        else "index is driven by real performance data"),
        "patterns_learned": pattern.get("n", 0),
        "top_title_formulas": pattern.get("top_formulas", []),
        "own_fingerprint": own,
        "recommendations": _recommendations(pattern, own),
    }


def _own_fingerprint(ml_data: dict | None) -> dict:
    """Fingerprint from REAL performance, not from our own title-scorer.

    V3.4: pehle ye function apni hi videos ke titles ko title-scorer se score
    karta tha — matlab system apni khud ki tareef khud kar raha tha aur index
    "A+ viral-ready" dikhata tha jabke views 0 thay. Ab:
      • real = videos jin ke arms par REAL outcome data hai (n_real > 0)
      • har video ka performance score = arm ka posterior mean (0..5) → 0..1
      • jis video ka koi real data nahi, wo count HOTA hai lekin score 0
        ke saath — kyunki "koi data nahi" matlab "koi performance nahi"
    """
    if not ml_data:
        return {"n": 0, "avg_score": 0.0, "best_formula": None,
                "n_with_real_data": 0, "note": "no ML store"}
    videos = ml_data.get("videos", [])
    if not videos:
        return {"n": 0, "avg_score": 0.0, "best_formula": None,
                "n_with_real_data": 0, "note": "no videos yet"}
    arms = ml_data.get("arms", {})
    scored = []
    n_real = 0
    for v in videos[-40:]:
        arm = arms.get(v.get("arm_key"), {})
        n = int(arm.get("n", 0) or 0)
        rewards = float(arm.get("rewards", 0.0) or 0.0)
        if n > 0:
            n_real += 1
            mean = rewards / n           # REAL outcomes only — no prior credit
            perf = max(0.0, min(1.0, mean / 2.5))
        else:
            perf = 0.0                   # priors are belief, not performance
        title = v.get("title") or v.get("hook") or ""
        ts = score_title(title)
        scored.append({"perf": perf, "formulas": ts.get("formulas", []),
                       "title_score": ts.get("score", 0.0)})
    avg = round(sum(s["perf"] for s in scored) / len(scored), 3)
    formulas = [f for s in scored for f in s["formulas"]]
    top = None
    if formulas:
        counts = defaultdict(int)
        for f in formulas:
            counts[f] += 1
        top = max(counts.items(), key=lambda kv: kv[1])[0]
    return {"n": len(scored), "n_with_real_data": n_real, "avg_score": avg,
            "best_formula": top,
            "note": ("real-performance based" if n_real
                     else "NO real performance data yet — avg is 0 by design")}


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
    """A COMPLETE, high-pattern-interrupt hook (V3.4: pehle sirf fragments
    thay jaise "Stop letting them" — aadha hook overlay par weak lagta hai.
    Ab har option ek mukammal payoff wala hook hai)."""
    full_hooks = [
        "Stop letting them control your money",
        "Why smart people fall for cults",
        "Nobody tells you the first sign of control",
        "The trick they use to make you trust them",
        "How they get you to say yes before you think",
        "Never say this to a manipulator",
        "The warning sign everyone ignored",
        "Watch what they say when you say no",
    ]
    return random.choice(full_hooks)


# ─────────────────────────────────────────────────────────────
# V3.1 FULL SCRIPT QUALITY SCORE — sirf hook nahi, poora script
# ─────────────────────────────────────────────────────────────
PSYCH_CONCEPTS = ["milgram", "stanford", "cialdini", "cognitive dissonance",
                  "anchoring", "trauma bond", "bystander", "gaslighting",
                  "confirmation bias", "cognitive bias", "foot in the door",
                  "scarcity", "mirroring", "love bombing", "conditioning",
                  "deprogram", "psycholog", "behavioral stud", "research shows",
                  "studies show", "landmark study", "persuasion", "social proof"]
# V3.4: sirf REAL concrete anchors — pehle "day/week/minute/second/call/text/
# phone/email/meeting/date" bhi anchor maane jaate thay, jo har script mein
# hote hain → har script ko free "anchor ✅" milta tha. Ab specific evidence
# chahiye: raqam, case file, study, trial, transcript...
ANCHOR_HINTS = ["$", "3-word", "case", "file", "memo", "study", "experiment",
                "court", "trial", "wire", "transfer", "transcript",
                "declassified", "million", "thousand", "billion"]
ANCHOR_NUM_RE = re.compile(r"\d+\s?(k|%|percent|people|days|hours|years|times|words)", re.I)


def score_script(script: dict | None) -> dict:
    """Score a full script 0..1 — the 'human quality gate'.

    Components:
      hook        (0.25)  — viral_intel.score_hook
      cta         (0.20)  — like/comment/follow/save ask present
      anchor      (0.20)  — concrete detail ($ amount, 3-word text, case file...)
      psych       (0.15)  — real psychology concept/study named
      structure   (0.10)  — >=3 scenes, hook first
      duration    (0.10)  — 45-58s estimated from words
    """
    if not script:
        return {"score": 0.0, "issues": ["no script"], "components": {}}
    issues = []
    comp = {}

    # hook — V3.4 honest threshold (0.5 on the new honest scale; 0.85 was
    # tuned to the old inflated scale where weak hooks still scored 0.55+)
    try:
        h = score_hook(script.get("hook", ""))
        comp["hook"] = h["score"]
        if h["score"] < 0.5:
            issues.append(f"hook weak ({h['score']:.2f})")
    except Exception:
        comp["hook"] = 0.0

    # cta / engagement
    full = " ".join(str(s.get("caption", "")) for s in script.get("scenes", [])).lower()
    eng = any(w in full for w in ("like", "comment", "follow", "save", "share",
                                  "hit", "subscribe"))
    comp["cta"] = 1.0 if eng else 0.0
    if not eng:
        issues.append("no like/comment/follow ask")

    # concrete anchor — specific evidence only (raqam/case/study/trial)
    anchor = any(a in full for a in ANCHOR_HINTS) or bool(ANCHOR_NUM_RE.search(full))
    comp["anchor"] = 1.0 if anchor else 0.0
    if not anchor:
        issues.append("no concrete anchor (numbers/$/case/study)")

    # psychology concept
    psych = any(p in full for p in PSYCH_CONCEPTS)
    comp["psych"] = 1.0 if psych else 0.0
    if not psych:
        issues.append("no named psychology concept/study")

    # structure
    n_scenes = len(script.get("scenes", []))
    comp["structure"] = 1.0 if n_scenes >= 3 else 0.0
    if n_scenes < 3:
        issues.append(f"only {n_scenes} scenes")

    # duration (approx words -> seconds)
    words = len(full.split())
    est_s = words / 2.2  # ~2.2 words/sec narration
    comp["duration"] = 1.0 if 38 <= est_s <= 65 else 0.0
    if not (38 <= est_s <= 65):
        issues.append(f"duration est {est_s:.0f}s (target 38-65)")

    score = round(0.25 * comp["hook"] + 0.20 * comp["cta"] + 0.20 * comp["anchor"]
                  + 0.15 * comp["psych"] + 0.10 * comp["structure"]
                  + 0.10 * comp["duration"], 3)
    return {"score": score, "issues": issues, "components": comp,
            "est_s": round(est_s, 1), "scenes": n_scenes}


def score_script_grade(score: float) -> str:
    if score >= 0.8:
        return "A — strong script"
    if score >= 0.65:
        return "B — solid"
    if score >= 0.5:
        return "C — needs work"
    return "D — weak (regenerate)"
