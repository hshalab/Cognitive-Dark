#!/usr/bin/env python3
"""
Coercion Files — Niche Strategy & Topic Bank (Coercion Files).

Supplies the Autonomous Brain with a deep, monetization-safe topic pool
per content pillar. True-crime x psychology positioning: story-driven,
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
        "Synanon: the rehab that turned into an armed cult",
        "How coercive groups enforce financial surrender",
    ],
    "con_artists": [
        "The AI voice-clone scam draining American bank accounts",
        "How a 3-word text message bypassed two-factor banking security",
        "The psychology behind the Tinder Swindler's script",
        "Why victims of romance scams wire money twice",
        "Anatomy of the $100M pig-butchering crypto syndicate",
        "Urgency framing: how scammers trigger amygdala hijack",
        "The fake CEO wire transfer script exposed",
        "The 'Urgent Fraud Alert' phone script decoded word by word",
        "The confidence trick that sold the Eiffel Tower twice",
        "Verbal leakage: 3 phrases financial fraudsters always overuse",
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
        "Operation Midnight Climax: the declassified truth",
    ],
    "interrogation": [
        "The 3-second silence FBI interrogators use to break alibis",
        "Why innocent people confess under psychological fatigue",
        "Statement analysis: 2 words that betray guilty suspects",
        "Baseline calibration: how detectives spot the exact shift",
        "The Reid technique's psychological pressure points",
        "Micro-expressions: what body language experts get wrong",
        "The cognitive load trick that forces liars to slip up",
        "How to answer a manipulative corporate question safely",
    ],
    "coercive_control": [
        "Quiet firing: 3 psychological signs your boss is managing you out",
        "How covert workplace narcissists sabotage promotions",
        "Coercive control: the abuse with no physical evidence",
        "The daily rules toxic manipulators quietly enforce",
        "Financial abuse: subtle control through shared accounts",
        "Why leaving is statistically the danger peak in toxic bonds",
        "The 3-stage abuse cycle: tension, incident, love bomb",
        "Blame-shifting language: how manipulators rewrite reality",
        "The DARVO technique used by covert manipulators",
    ],
    "mass_psychology": [
        "How dark UX patterns manipulate millions into spending",
        "The outrage loop: algorithms engineered for emotional addiction",
        "Why false stories spread 6x faster than factual corrections",
        "Astroturfing: fake grassroots campaigns funding viral panic",
        "Fear headlines and your attention budget",
        "The bandwagon effect inside your comment section",
        "Manufactured consent in modern media",
        "How normal gets redefined one headline at a time",
    ],
    "brainwashing_myths": [
        "Brainwashing myths vs the real behavioral science",
        "The Manchurian Candidate: Hollywood fiction vs CIA reality",
        "Why one video can't brainwash you — but repetition does",
        "The six conditions real thought reform requires",
        "Korean War POW controversy, explained calmly",
        "Did deprogramming ever actually work?",
        "Coercive persuasion: what the research actually says",
        "Your phone isn't brainwashing you — it's micro-nudging",
    ],
    "stoic_defense": [
        "Stoic mental immunity against modern social engineering",
        "Marcus Aurelius on dealing with deceivers daily",
        "The 5-second stoic pause before reacting to urgency",
        "Epictetus: guard only what is under your control",
        "Premeditation of evils as a fraud defense drill",
        "How stoics defuse manipulative insults in one line",
        "Amor fati: the unshakeable mindset con artists can't crack",
        "The stoic rule high-pressure salesmen can't break",
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
