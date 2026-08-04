#!/usr/bin/env python3
"""
Cognitive Dark V2.1 — Niche Strategy & Topic Bank.

Supplies the Autonomous Brain with a deep, monetization-safe topic pool
per content pillar (2026 trend-researched). Every topic keeps the dark
hook-power but stays in the educational "protect yourself" framing.
"""

from config.settings import PILLARS

# ─────────────────────────────────────────────────────────────
# Deep topic bank per pillar (2026 viral angles)
# ─────────────────────────────────────────────────────────────
TOPICS_BY_PILLAR = {
    "self_defense": [
        "How manipulators use silence as a weapon",
        "The gaslighting phrases that sound like love",
        "Why manipulators target empathetic people",
        "The guilt-trip loop and how to exit it",
        "How covert manipulation hides in compliments",
        "The DARVO tactic: deny, attack, reverse victim",
        "Why saying 'no' feels dangerous after manipulation",
        "The fog technique: confusing you to control you",
    ],
    "influence": [
        "How supermarkets engineer your buying decisions",
        "The decoy effect: why you pick the middle option",
        "How urgency timers hijack your judgment",
        "Why free trials quietly rewire commitment",
        "The foot-in-the-door pattern in everyday life",
        "How social proof is manufactured online",
        "The psychology of pricing: why 99 feels cheaper",
        "How reciprocity traps you into saying yes",
    ],
    "dark_triad": [
        "How narcissists use charm as camouflage",
        "The empathy gap: inside the dark triad mind",
        "Love bombing → devaluation → discard cycle",
        "How Machiavellians build alliances to betray them",
        "The mask of sanity: psychopathy up close",
        "Why dark triad people love power games at work",
        "How to spot covert narcissism in 5 minutes",
        "The discard phase: why it hurts so much",
    ],
    "body_language": [
        "Micro-expressions that leak true feelings",
        "How to detect discomfort in 3 seconds",
        "The feet don't lie: lower-body signals",
        "Pacifying behaviors: self-touch under stress",
        "How confidence is signaled before words",
        "Eye contact myths vs actual research",
        "The difference between shy and deceptive gaze",
        "Vocal tone shifts that reveal hidden emotion",
    ],
    "cognitive_biases": [
        "The sunk cost trap keeping you stuck",
        "Why your memory rewrites events",
        "The halo effect: beauty = trust illusion",
        "Confirmation bias in your daily feed",
        "The Dunning-Kruger effect explained",
        "Availability bias: why fear feels factual",
        "The anchoring trick in negotiations",
        "Why your brain loves patterns that aren't there",
    ],
    "red_flags": [
        "The trauma bond chemistry explained",
        "Why intermittent reinforcement is addictive",
        "Isolation: the first move of control",
        "The silent treatment as punishment",
        "Why leaving feels harder than staying",
        "The cycle of abuse: four phases mapped",
        "How 'you're too sensitive' erodes reality",
        "Breadcrumbing: crumbs instead of commitment",
    ],
    "stoic_mind": [
        "The Stoic pause between trigger and reaction",
        "Marcus Aurelius on handling difficult people",
        "Negative visualization: prehearsing adversity",
        "The dichotomy of control in toxic situations",
        "Epictetus: freedom starts with judgments",
        "How Stoics neutralize insults",
        "Amor fati: turning pain into fuel",
        "Seneca on the shortness of anxious lives",
    ],
    "mind_control": [
        "MKUltra: what the files actually show",
        "How cults use love bombing and isolation",
        "The Milgram experiment: obedience to authority",
        "Stanford Prison Experiment: power changes minds",
        "How propaganda exploits the mere-exposure effect",
        "Brainwashing myths vs real coercion research",
        "The Asch conformity experiments explained",
        "How information overload shuts down critical thought",
    ],
}

# Flat list for quick random picks
DARK_TOPICS = [t for topics in TOPICS_BY_PILLAR.values() for t in topics]

# Keyword signature per pillar (for topic ↔ pillar matching)
PILLAR_KEYWORDS = {
    "self_defense": ["manipulat", "gaslight", "guilt", "silence", "darvo", "fog", "empath", "covert"],
    "influence": ["buy", "price", "persuad", "market", "urgency", "reciprocity", "social proof", "decoy", "trial"],
    "dark_triad": ["narciss", "psychopath", "machiavell", "love bombing", "discard", "dark triad", "charm", "betray"],
    "body_language": ["body", "eye", "micro", "gesture", "posture", "vocal", "tone", "feet", "signal"],
    "cognitive_biases": ["bias", "memory", "anchor", "halo", "kruger", "sunk cost", "pattern", "availability"],
    "red_flags": ["trauma bond", "reinforcement", "isolation", "silent treatment", "abuse", "breadcrumb", "cycle", "too sensitive"],
    "stoic_mind": ["stoic", "marcus", "seneca", "epictetus", "control", "pause", "adversity", "fate", "insult"],
    "mind_control": ["mkultra", "cult", "milgram", "stanford", "propaganda", "brainwash", "asch", "obedience", "conform"],
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
