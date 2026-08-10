#!/usr/bin/env python3
"""
Coercion Files — CTR & Virality Optimizer (V3.1).

Har platform ke 2026 algorithm signals ke hisaab se:
  1. TITLE CTR SCORE  — title ka predicted CTR score (0..1)
  2. HOOK RETENTION   — first-2-second hook retention potential
  3. CONTENT DENSITY  — per-second information value (retention driver)
  4. VIRAL SIGNALS    — emotional triggers, curiosity gaps, specificity
  5. PLATFORM TUNING  — YouTube vs FB vs IG ke liye alag optimization

Data sources (sab PUBLIC, documented patterns):
  - 2026 YouTube Shorts CTR benchmarks (public creator data)
  - Top psychology/true-crime faceless channel title analysis
  - First-3-second retention best practices
"""

from __future__ import annotations

import logging
import random
import re
from collections.abc import Callable  # noqa: F401
from dataclasses import dataclass, field

logger = logging.getLogger("ctr_optimizer")

# ─── CTR Score Components (YouTube Shorts 2026) ─────────────────────────────
# Documented patterns that consistently drive high CTR in the psychology niche:

CTR_SIGNALS = {
    # Pattern: (description, score_boost, example)
    "number_specificity": (
        "Specific numbers add credibility + clickable curiosity",
        0.12,
        r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b"
    ),
    "question_open_loop": (
        "Questions open a knowledge gap — viewer must click to close it",
        0.10,
        r"\b(why|how|what|who|when|would you|do you|can you)\b"
    ),
    "command_negative": (
        "'Stop/never/don't' = negative-space curiosity (what am I doing wrong?)",
        0.11,
        r"\b(stop|never|don'?t|quit|avoid|warning|watch out)\b"
    ),
    "reveal_exposure": (
        "'Secret/exposed/hidden/revealed' = high curiosity gap",
        0.10,
        r"\b(revealed?|secret|hidden|exposed|truth|inside|behind|real|finally)\b"
    ),
    "personal_stake": (
        "Content that threatens/promises something personal = high CTR",
        0.13,
        r"\b(you|your|yourself|everyone|everybody)\b"
    ),
    "authority_anchor": (
        "Named entities (FBI, CIA, Stanford, Milgram) add credibility",
        0.08,
        r"\b(fbi|cia|stanford|milgram|cialdini|nasa|project|declassified|mind control)\b"
    ),
    "ultra_specific": (
        "Ultra-specific details ($47k, 3 words, 1974) beat vague claims",
        0.12,
        r"\$\s?\d+|\d+\s?(dollars?|k|million|billion|people|signs|ways|reasons|days|weeks|minutes|seconds|years)"
    ),
    "urgency_scarcity": (
        "Urgency/limited-time framing drives immediate clicks",
        0.07,
        r"\b(urgent|now|instantly|today|currently|happening|breaking|alert)\b"
    ),
    "contrarian": (
        "Contrarian takes ('this is wrong', 'myth') get higher CTR in psychology",
        0.10,
        r"\b(think|believe|myth|wrong|don'?t believe|actually|truth|reality)\b"
    ),
    "emotional_charge": (
        "Fear/shock/curiosity emotion words boost CTR significantly",
        0.09,
        r"\b(dangerous|deadly|scary|shocking|brutal|cruel|evil|dark|trap|scam|hack)\b"
    ),
}


# ─── Retention Signals (first 5 seconds matter most) ────────────────────────
RETENTION_SIGNALS = {
    "immediate_action": (
        "Scene 1 starts in medias res — no intro, no 'welcome'",
        0.15,
        r"^(you're|she|he|they|i|we|in|on|at|the|this|that|it|here|there)"
    ),
    "concrete_anchor": (
        "First scene has a concrete number/date/name/place anchor",
        0.12,
        r"\$\s?\d+|\d+\s?(dollars?|k|people|signs|days|minutes|years|case|file|moment|second|word|text|phone|call|meeting|letter|email|memo|study|experiment|trial|court|wire|transfer)"
    ),
    "pattern_interrupt": (
        "First 3 words create pattern interrupt (unexpected start)",
        0.10,
        None  # checked via hook quality score
    ),
    "short_sentences": (
        "Short punchy sentences > long academic sentences (retention)",
        0.08,
        None  # structural check
    ),
    "emotion_word_density": (
        "Emotion-charged words per scene (dark/intense/revelatory)",
        0.07,
        r"\b(dark|deadly|shocking|brutal|cruel|evil|trap|scam|hack|warning|secret|hidden|truth|revealed|exposed|threat|danger|mind|control|manipulate|deceive|lie|trick)\b"
    ),
}


# ─── Platform-Specific Optimizations ─────────────────────────────────────────
PLATFORM_CTR_BOOSTS = {
    "youtube": {
        "title_max_optimal": 55,   # ≤55 chars for Shorts — mobile shows ~50
        "keyword_must_have": True,  # keyword in title = search + suggested hybrid
        "power_word_pos": "end",    # power word at END of title = highest CTR
        "case_number_boost": 0.15,  # "Case #12" style titles
    },
    "facebook": {
        "title_max_optimal": 58,   # FB feed shows ~58 chars
        "first_3_words": "critical", # first 3 words = the hook in news feed
        "emoji_use": "moderate",     # 1 emoji in title is OK for FB
        "question_boost": 0.08,      # FB loves discussion-starting questions
    },
    "instagram": {
        "title_max_optimal": 55,
        "save_value": "critical",    # must signal "save this"
        "hashtag_count_optimal": 15, # 15-20 sweet spot
        "aesthetic_hook": 0.10,      # IG rewards visually-hooks
    },
}


@dataclass
class CTRScore:
    title: str
    score: float = 0.0
    components: dict = field(default_factory=dict)
    issues: list = field(default_factory=list)
    recommendations: list = field(default_factory=list)
    platform: str = "youtube"

    def overall(self) -> float:
        return round(min(1.0, self.score), 3)


def score_title_ctr(title: str, platform: str = "youtube") -> CTRScore:
    """Score a title's predicted CTR (0..1) for the given platform.

    Based on documented 2026 patterns for psychology/true-crime Shorts.
    """
    if not title:
        return CTRScore(title=title, score=0.0,
                        issues=["empty title"], platform=platform)

    title_lower = title.lower()
    comp = {}
    issues = []
    total_boost = 0.50  # base score (everything passes minimum threshold)

    # ── Length check ──
    optimal = PLATFORM_CTR_BOOSTS.get(platform, {}).get("title_max_optimal", 55)
    if len(title) > optimal + 20:
        issues.append(f"title too long ({len(title)} chars, optimal ≤{optimal+20})")
    elif len(title) < 20:
        issues.append(f"title very short ({len(title)} chars) — may lack specificity")
    comp["length"] = 1.0 if 30 <= len(title) <= optimal + 10 else 0.7
    total_boost += 0.05 * comp["length"]

    # ── Signal detection ──
    signals_found = []
    for name, (_desc, boost, pattern) in CTR_SIGNALS.items():
        if pattern and re.search(pattern, title, re.I):
            signals_found.append(name)
            comp[name] = 1.0
            total_boost += boost
        else:
            comp[name] = 0.0

    # Deduplicate signal counting (don't double-count similar patterns)
    if "number_specificity" in signals_found and "ultra_specific" in signals_found:
        # Count once, but bonus for having both
        comp["specificity_combined"] = 1.0
        total_boost += 0.05
    else:
        comp["specificity_combined"] = 0.0

    # ── Platform-specific ──
    if platform == "youtube":
        # Case number format ("Case #123: ...") → strong CTR in true-crime
        if re.search(r"case\s*#\d+", title_lower):
            comp["case_number"] = 1.0
            total_boost += PLATFORM_CTR_BOOSTS["youtube"]["case_number_boost"]
        else:
            comp["case_number"] = 0.0

        # Keyword check — top psychology keywords
        keywords = ["psychology", "coercion", "cult", "con", "mind", "brainwash",
                    "scam", "manipulation", "dark", "behavioral", "truth", "lies",
                    "control", "gaslighting", "red flag", "stoic"]
        keyword_found = any(k in title_lower for k in keywords)
        comp["keyword"] = 1.0 if keyword_found else 0.5
        if not keyword_found:
            issues.append("no psychology/search keyword in title")

    elif platform == "facebook":
        # FB specific: question format gets engagement boost
        if re.search(r"\b(why|how|what|would you|do you)\b", title_lower):
            comp["question_format"] = 1.0
            total_boost += PLATFORM_CTR_BOOSTS["facebook"]["question_boost"]
        else:
            comp["question_format"] = 0.0

    elif platform == "instagram":
        # IG: "save this" value signal in title
        if any(w in title_lower for w in ["save", "checklist", "signs", "steps", "ways", "list"]):
            comp["save_worthy"] = 1.0
            total_boost += 0.10
        else:
            comp["save_worthy"] = 0.0

    # ── Power word count ──
    power_words = {"stop", "never", "secret", "why", "how", "you", "truth", "warning",
                   "exposed", "hidden", "shocking", "deadly", "danger", "trap", "hack",
                   "bomb", "instantly", "finally", "nobody", "everyone", "they"}
    pw_count = sum(1 for w in title_lower.split() if w.strip("?!.,") in power_words)
    comp["power_words"] = min(1.0, pw_count / 3.0)
    total_boost += 0.03 * min(3, pw_count)

    # ── Final score ──
    score = round(min(1.0, total_boost), 3)
    recs = []
    if len(signals_found) < 2:
        recs.append("add 1-2 viral CTR signals (number/question/command/reveal)")
    if not keyword_found and platform == "youtube":
        recs.append("add a search keyword (psychology/cult/scam/mind control...)")
    if not issues and score < 0.75:
        recs.append("add a specific number or case reference for credibility")

    return CTRScore(
        title=title, score=score, components=comp,
        issues=issues, recommendations=recs, platform=platform
    )


def suggest_ctr_improved_title(hook: str, platform: str = "youtube",
                                pillar_keywords: list = None) -> list[str]:
    """Generate CTR-optimized title variants from a hook.

    Returns 3-5 title options, each targeting a different CTR pattern.
    """
    hook = hook.strip().rstrip("?.!")
    if not hook:
        return []

    variants = []
    _keywords = pillar_keywords or ["psychology", "truth", "mind", "control"]

    # Variant 1: Number + hook (specificity CTR boost)
    numbers = ["3", "7", "10", "11", "12", "50", "100", "21", "6"]
    num = random.choice(numbers)
    v1 = f"{num} {hook[0].lower() + hook[1:]}" if hook else hook
    variants.append(v1[:70])

    # Variant 2: Question format (curiosity gap)
    q_words = ["Why", "How", "What", "When", "Why do"]
    v2 = f"{random.choice(q_words)} {hook[0].lower() + hook[1:]}?"
    variants.append(v2[:70])

    # Variant 3: Command/negative (stop/never pattern)
    cmd_prefix = random.choice(["Stop", "Never", "Don't"])
    v3 = f"{cmd_prefix} {hook.lower()}"
    variants.append(v3[:70])

    # Variant 4: Reveal/exposure framing
    reveal_prefix = random.choice(["The Truth About", "What They Don't Tell You About",
                                   "Exposed: "])
    v4 = f"{reveal_prefix} {hook[0].lower() + hook[1:]}"
    variants.append(v4[:70])

    # Variant 5: Case format (true-crime style)
    case_num = random.randint(1, 999)
    v5 = f"Case #{case_num}: {hook}"
    variants.append(v5[:70])

    # Deduplicate
    seen, out = set(), []
    for v in variants:
        key = v.lower().strip()
        if key and key not in seen and len(v) > 15:
            seen.add(key)
            out.append(v)
    return out[:5]


def score_hook_retention(hook: str, first_scene_text: str = "") -> dict:
    """Score a hook's potential for first-5-second retention (0..1).

    The first 5 seconds determine whether viewers swipe away or stay.
    """
    if not hook:
        return {"score": 0.0, "issues": ["empty hook"]}

    issues = []
    score = 0.50  # base

    # Length: ideal 4-8 words for 2-second overlay
    words = hook.split()
    if len(words) > 9:
        issues.append(f"too many words ({len(words)}) — 2-second cap")
        score -= 0.10
    elif len(words) < 3:
        issues.append("hook too short — add specificity")

    # Power word presence
    power = {"stop", "never", "why", "how", "warning", "truth", "secret",
             "exposed", "hidden", "shocking", "danger", "trap", "you"}
    pw = sum(1 for w in words if w.lower().strip("?!.,") in power)
    score += min(0.20, pw * 0.05)
    if pw == 0:
        issues.append("no power words in hook")

    # Question or command = pattern interrupt
    if re.search(r"\b(why|how|stop|never|don'?t|warning|look|watch)\b", hook, re.I):
        score += 0.15

    # First-scene text continuity (hook → scene 1 should flow naturally)
    if first_scene_text:
        # Check that first scene picks up the hook's thread
        first_words = set(first_scene_text.lower().split()[:10])
        hook_words = set(w.lower().strip("?!.,") for w in words)
        overlap = len(hook_words & first_words) / max(1, len(hook_words))
        if overlap < 0.2 and len(hook_words) > 2:
            issues.append("hook doesn't connect to scene 1 — abrupt transition")
            score -= 0.08

    # Emotional charge
    emotion_words = {"dangerous", "deadly", "scary", "shocking", "brutal",
                     "evil", "dark", "trap", "scam", "hack", "warning",
                     "secret", "hidden", "truth", "revealed", "exposed"}
    emotion_count = sum(1 for w in words if w.lower() in emotion_words)
    score += min(0.10, emotion_count * 0.04)

    return {
        "score": round(min(1.0, max(0.0, score)), 3),
        "issues": issues,
        "word_count": len(words),
        "power_words": pw,
    }


def pick_best_title(hook: str, variants: list[str], platform: str = "youtube"
                    ) -> str:
    """Pick the highest-CTR variant from a list of title options."""
    if not variants:
        return hook[:70]
    scored = [(score_title_ctr(v, platform).score, v) for v in variants]
    scored.sort(reverse=True)
    return scored[0][1]


def describe_ctr_grade(score: float) -> str:
    """Human-readable CTR grade."""
    if score >= 0.85:
        return "S — elite CTR potential"
    if score >= 0.75:
        return "A — strong CTR"
    if score >= 0.65:
        return "B — good, room to improve"
    if score >= 0.50:
        return "C — average, needs optimization"
    return "D — weak CTR, rewrite recommended"


# ─── Content Density Analyzer (retention driver) ─────────────────────────────
def analyze_content_density(scenes: list[dict]) -> dict:
    """Analyze per-scene information density — key retention driver.

    High-density content (concrete details, named concepts) holds viewers.
    Low-density = generic AI fluff = swipe-away.
    """
    if not scenes:
        return {"score": 0.0, "per_scene": []}

    per_scene = []
    total_score = 0.0

    concrete_markers = [
        "$", "3-word", "text", "phone", "call", "date", "case", "file",
        "meeting", "letter", "memo", "minute", "second", "day", "week",
        "study", "experiment", "court", "trial", "wire", "email",
        "fbi", "cia", "stanford", "milgram", "cialdini", "project",
        "declassified", "document", "transcript", "record", "report",
        "number", "amount", "thousand", "million", "billion",
    ]

    psych_concepts = [
        "milgram", "stanford", "cialdini", "cognitive dissonance",
        "anchoring", "trauma bond", "bystander", "gaslighting",
        "confirmation bias", "cognitive bias", "foot in the door",
        "scarcity", "mirroring", "love bombing", "conditioning",
        "deprogram", "persuasion", "social proof", "neuro", "brain",
        "prefrontal", "amygdala", "psycholog", "behavioral", "studies",
        "research", "study shows", "found that", "demonstrated",
    ]

    for i, scene in enumerate(scenes):
        text = (scene.get("caption") or "").lower()
        words = text.split()
        score = 0.30  # base per-scene

        # Concrete anchor presence
        has_concrete = any(m in text for m in concrete_markers)
        score += 0.20 if has_concrete else 0.0
        if not has_concrete:
            per_scene.append({"scene": i, "score": round(score, 3),
                              "issue": "no concrete anchor"})

        # Psychology concept named
        has_psych = any(p in text for p in psych_concepts)
        score += 0.15 if has_psych else 0.0
        if not has_psych:
            per_scene.append({"scene": i, "score": round(score, 3),
                              "issue": "no named psych concept"})

        # Sentence length (shorter = better retention pacing)
        sent_len = len(words)
        if 15 <= sent_len <= 40:
            score += 0.10
        elif sent_len > 50:
            score -= 0.05
            per_scene.append({"scene": i, "score": round(score, 3),
                              "issue": f"too long ({sent_len} words)"})

        # Action verbs (active voice = better pacing)
        action_verbs = {"stole", "lied", "confessed", "wired", "called",
                        "texted", "met", "found", "discovered", "exposed",
                        "caught", "tricked", "manipulated", "demanded",
                        "threatened", "promised", "claimed", "denied",
                        "admitted", "agreed", "fell", "lost", "gained",
                        "ran", "left", "joined", "escaped", "-faced",
                        "triggered", "broke", "cried", "screamed"}
        has_action = any(v in text for v in action_verbs)
        score += 0.10 if has_action else 0.0
        if not has_action:
            per_scene.append({"scene": i, "score": round(score, 3),
                              "issue": "no action verb"})

        per_scene.append({"scene": i, "score": round(min(1.0, score), 3),
                          "action": has_action, "concrete": has_concrete,
                          "psych": has_psych})
        total_score += min(1.0, score)

    avg = round(total_score / len(scenes), 3) if scenes else 0.0
    return {
        "score": avg,
        "per_scene": per_scene,
        "n_scenes": len(scenes),
        "grade": describe_ctr_grade(avg),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Demo: score a few titles
    test_titles = [
        "Why Smart People Join Cults",
        "Stop Doing This Immediately",
        "The Cult That Banned These 3 Questions",
        "MKUltra: The CIA Mind Control Files",
        "Case #47: The Salesman Who Wasn't",
        "Coercive Control: The Invisible Abuse",
    ]
    print("=== TITLE CTR SCORES (YouTube Shorts) ===")
    for t in test_titles:
        s = score_title_ctr(t, "youtube")
        print(f"  [{describe_ctr_grade(s.score)}] {t[:55]}")
        print(f"    score={s.score} components={ {k:v for k,v in s.components.items() if v>0} }")

    print("\n=== SUGGESTED VARIANTS ===")
    for variant in suggest_ctr_improved_title("Smart people join dangerous cults"):
        s = score_title_ctr(variant, "youtube")
        print(f"  [{describe_ctr_grade(s.score)}] {variant[:65]} (score={s.score})")

    print("\n=== HOOK RETENTION SCORES ===")
    for hook in ["Why Smart People Join Cults", "Stop letting them", "Case #12"]:
        r = score_hook_retention(hook)
        print(f"  {hook[:40]:40s} → {describe_ctr_grade(r['score'])} ({r['score']})")

    print("\n=== CONTENT DENSITY (sample scenes) ===")
    scenes = [
        {"caption": "She wired $47,000 in three minutes. No hesitation."},
        {"caption": "The psychologists call this the compliance cascade."},
        {"caption": "Her husband had been planning the transfer for weeks."},
    ]
    d = analyze_content_density(scenes)
    print(f"  Overall density: {d['grade']} ({d['score']})")
    for ps in d["per_scene"]:
        flags = []
        if not ps.get("action"):
            flags.append("no-action")
        if not ps.get("concrete"):
            flags.append("no-concrete")
        if not ps.get("psych"):
            flags.append("no-psych")
        print(f"  Scene {ps['scene']}: {ps['score']} {' '.join(flags)}")
