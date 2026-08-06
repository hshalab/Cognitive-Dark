#!/usr/bin/env python3
"""
Cognitive Dark V2.2 — Niche Strategy & Topic Bank (Coercion Files).

Supplies the Autonomous Brain with a deep, monetization-safe topic pool
per content pillar. True-crime × psychology positioning: story-driven,
educational, "how it worked + how to defend" framing.
"""

from config.settings import PILLARS

# ─────────────────────────────────────────────────────────────
# Deep topic bank per pillar (2026 viral true-crime angles)
# ─────────────────────────────────────────────────────────────
TOPICS_BY_PILLAR = {
    "cults": [
        "How NXIVM hid a cult inside self-help branding",
        "The 3 questions cults forbid members to ask",
        "Why high-achievers fall for cult recruitment",
        "Love bombing: week one inside a cult",
        "How Jonestown's obedience was engineered step by step",
        "The cult exit interview that went viral",
        "Isolation tactics: cutting the lifelines",
        "The leader's script for killing doubt",
    ],
    "con_artists": [
        "The psychology behind the Tinder Swindler's script",
        "Why victims of romance scams wire money twice",
        "Anatomy of the pig-butchering crypto scam",
        "The confidence trick that sold the Eiffel Tower",
        "Urgency framing: how scammers stop you thinking",
        "How a con artist reads your first reply",
        "The pigeon drop con, still working today",
        "Verbal leakage: phrases scammers overuse",
    ],
    "mind_control_history": [
        "What the declassified MKUltra files actually show",
        "The CIA experiments that crossed every line",
        "Project Stargate and the psychic spy budget",
        "Radio Rwanda: broadcasts that manufactured hate",
        "How WWII propaganda posters hijacked emotion",
        "The overton window shift of a single ad campaign",
        "Cold War hypnosis programs: fact vs myth",
        "The ethics fallout that changed research rules",
    ],
    "interrogation": [
        "Why innocent people confess under pressure",
        "The question sequence that exposes liars",
        "Baseline behavior: how detectives calibrate truth",
        "Silence as a weapon in interrogation rooms",
        "Statement analysis: the words that betray you",
        "The Reid technique's psychological pressure points",
        "Micro-expressions that leak during interviews",
        "How to answer a manipulative question safely",
    ],
    "coercive_control": [
        "Coercive control: the abuse with no bruises",
        "The daily rules abusers quietly enforce",
        "How abusers isolate you from your own family",
        "Financial abuse: control through the wallet",
        "Why leaving is statistically the danger peak",
        "The abuse cycle: tension, incident, reconciliation",
        "Blame-shifting language decoded",
        "Safety planning: document everything",
    ],
    "mass_psychology": [
        "How crowds rewire individual judgment in minutes",
        "The outrage loop: feeds engineered for anger",
        "Why false stories spread 6x faster than truth",
        "Astroturfing: fake movements, real money",
        "Fear headlines and your attention budget",
        "The bandwagon effect inside your comment section",
        "Manufactured consent in modern media",
        "How normal gets redefined one headline at a time",
    ],
    "brainwashing_myths": [
        "Brainwashing myths vs the real science",
        "The Manchurian Candidate: Hollywood vs reality",
        "Why one video can't brainwash you",
        "The six conditions real thought reform requires",
        "Korean War POW controversy, explained calmly",
        "Did deprogramming ever actually work?",
        "Coercive persuasion: what the research says",
        "Your phone isn't brainwashing you — it's nudging",
    ],
    "stoic_defense": [
        "Stoic mental immunity against manipulation",
        "Marcus Aurelius on dealing with liars daily",
        "The 5-second stoic pause before reacting",
        "Epictetus: guard only your judgments",
        "Premeditation of evils as a defense drill",
        "How stoics defuse insults in one line",
        "Amor fati: the mindset scammers can't crack",
        "The stoic rule cult recruiters can't break",
    ],
}

# Flat list for quick random picks
DARK_TOPICS = [t for topics in TOPICS_BY_PILLAR.values() for t in topics]

# Keyword signature per pillar (for topic ↔ pillar matching)
PILLAR_KEYWORDS = {
    "cults": ["cult", "jonestown", "nxivm", "recruit", "love bombing", "isolation", "leader", "exit"],
    "con_artists": ["con", "scam", "swindler", "confidence", "crypto", "pigeon", "urgency", "verbal leakage"],
    "mind_control_history": ["mkultra", "cia", "stargate", "propaganda", "radio rwanda", "declassified", "hypnosis", "overton"],
    "interrogation": ["interrogat", "lie", "confess", "detective", "baseline", "reid", "micro-expression", "statement analysis"],
    "coercive_control": ["abuse", "coercive", "isolat", "financial", "leaving", "cycle", "blame", "safety"],
    "mass_psychology": ["crowd", "outrage", "misinformation", "astroturf", "headlines", "bandwagon", "consent", "feed"],
    "brainwashing_myths": ["brainwash", "manchurian", "thought reform", "deprogramming", "myth", "coercive persuasion", "nudging"],
    "stoic_defense": ["stoic", "marcus", "epictetus", "pause", "judgments", "insult", "amor fati", "immunity"],
}


def topics_for_pillar(pillar_key: str) -> list:
    """Return the topic bank for a pillar (falls back to the full pool)."""
    return TOPICS_BY_PILLAR.get(pillar_key) or DARK_TOPICS


def pillar_for_topic(topic: str) -> str:
    """Best-effort pillar detection for a free-form topic."""
    t = (topic or "").lower()
    best, best_hits = None, 0
    for pillar, keys in PILLAR_KEYWORDS.items():
        hits = sum(1 for k in keys if k in t)
        if hits > best_hits:
            best, best_hits = pillar, hits
    return best or PILLARS[0]["key"]
