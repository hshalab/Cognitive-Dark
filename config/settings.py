#!/usr/bin/env python3
"""
Cognitive Dark V2 — Global Configuration & Converted Niche Strategy.

Niche conversion (2026 trend-researched):
  OLD: "Dark Psychology & Manipulation Tactics"  →  monetization-risk framing
  NEW: "The Psychology of Influence — Dark Psychology for Self-Defense"

Why this conversion (verified 2026 trends):
  • "Dark psychology" raw-form is high-viewership but frequently flagged as
    harmful/reused content by YouTube & Meta → blocks monetization.
  • The trending, advertiser-friendly psychology sub-niches are: Stoicism,
    cognitive biases, red flags / gaslighting awareness, body language,
    influence & persuasion ethics, psychological self-defense.
  • "Protect yourself / spot manipulation" framing keeps the dark-psych DNA
    (hook power) while being Educational → safe for YPP / FB CMP / IG partner.
"""

import os
from pathlib import Path

# ─────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("CD_DATA_DIR", ROOT / "data"))
OUTPUT_DIR = Path(os.environ.get("CD_OUTPUT_DIR", ROOT / "output"))
CLIP_CACHE = DATA_DIR / "clips"
TMP_DIR = OUTPUT_DIR / "tmp"
DATA_DIR.mkdir(exist_ok=True)
TMP_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────
# Channel identity
# ─────────────────────────────────────────────────────────────
CHANNEL_NAME = "Cognitive Dark"
CHANNEL_TAGLINE = "The Psychology of Influence — and How to Protect Yourself"
TARGET_COUNTRY = "US"
TARGET_LANGUAGE = "en"
CHANNEL_URL = "https://youtube.com/@CognitiveDark"

NICHE = {
    "name": "Psychology of Influence & Self-Defense",
    "parent_niche": "Dark Psychology / Behavioral Psychology",
    "angle": ("Understand how the human mind is influenced, manipulated and "
              "persuaded — and learn to spot it, resist it, and master it."),
    "why_trending": (
        "2026's fastest-growing faceless psychology sub-niches: stoicism, "
        "cognitive biases, narcissist/gaslighting red flags, body language, "
        "influence ethics. Educational framing = monetization-safe."
    ),
    "safety": (
        "ALWAYS educational: 'learn to PROTECT yourself'. Never teach how to "
        "harm others. Include educational disclaimer in every description."
    ),
}

# ─────────────────────────────────────────────────────────────
# Content pillars (converted, trending-mapped)
# ─────────────────────────────────────────────────────────────
PILLARS = [
    {
        "key": "self_defense",
        "name": "Psychological Self-Defense",
        "trend": "high — manipulation awareness is the #1 viral angle",
        "hooks": [
            "How Manipulators Quietly Take Control of You",
            "7 Phrases Manipulators Use to Shut You Down",
            "The 30-Second Test That Reveals a Manipulator",
            "Why You Fall for Gaslighting (and How to Stop)",
            "The 'Love Bombing' Trap Nobody Tells You About",
            "How Narcissists Rewrite Your Reality",
            "3 Boundary Phrases That Stop Manipulators Cold",
            "The Silent Control Tactic You Accept Every Day",
        ],
        "search_terms": ["psychological manipulation", "gaslighting signs", "manipulation tactics",
                         "how to spot a manipulator", "emotional manipulation", "dark psychology"],
        "tags": ["psychological self defense", "manipulation tactics", "gaslighting",
                 "dark psychology", "emotional abuse", "boundaries", "psychology facts"],
    },
    {
        "key": "influence",
        "name": "Influence & Persuasion Psychology",
        "trend": "high — 'how persuasion works' is evergreen + advertiser-friendly",
        "hooks": [
            "The 6 Words That Make People Say Yes",
            "Why Your Brain Decides Before You Do",
            "The Psychology Behind Viral Content",
            "How Advertisers Program Your Choices",
            "The Anchoring Trick Used on You Every Day",
            "Why Scarcity Makes You Buy (Brain Science)",
            "The Framing Effect: Same Fact, Different Reality",
            "How 'Social Proof' Quietly Runs Your Life",
        ],
        "search_terms": ["persuasion psychology", "influence", "psychological tricks",
                         "how advertisers manipulate", "decision making psychology"],
        "tags": ["persuasion", "influence", "psychology tricks", "consumer psychology",
                 "decision making", "cognitive psychology", "brain hacks"],
    },
    {
        "key": "dark_triad",
        "name": "Dark Personality Awareness",
        "trend": "high — narcissist/psychopath content dominates shorts feeds",
        "hooks": [
            "10 Signs You're Dealing With a Narcissist",
            "The Dark Triad Explained in 60 Seconds",
            "Why Some People Feel No Remorse",
            "The Psychopath Next Door: 7 Red Flags",
            "How Machiavellians Manipulate Friendships",
            "The Empathy Switch: What Psychopaths Lack",
            "Narcissist or Confident? The 3-Second Difference",
            "Why Toxic People Love Your Kindness",
        ],
        "search_terms": ["narcissist signs", "dark triad", "psychopath traits",
                         "machiavellian", "dark personality test"],
        "tags": ["narcissist", "dark triad", "psychopath", "machiavellian",
                 "narcissism", "dark personality", "toxic people"],
    },
    {
        "key": "body_language",
        "name": "Body Language & Micro-Expressions",
        "trend": "high — 'read people' is a top psychology search cluster",
        "hooks": [
            "7 Body Language Signs Someone Is Lying",
            "How to Read Anyone in 3 Seconds",
            "The Micro-Expression That Exposes a Liar",
            "What Crossed Arms Really Mean (It's Not What You Think)",
            "FBI Agents Read These 5 Cues",
            "The Eye Contact Secret of Confident People",
            "Body Language That Makes People Respect You",
            "The Hand Gesture That Gives Away Anxiety",
        ],
        "search_terms": ["body language", "how to read people", "micro expressions",
                         "lying body language", "psychology of body language"],
        "tags": ["body language", "read people", "micro expressions", "nonverbal communication",
                 "lying signs", "psychology facts"],
    },
    {
        "key": "cognitive_biases",
        "name": "Cognitive Biases & Brain Traps",
        "trend": "high — bias explainers are the breakout 2026 format",
        "hooks": [
            "The Cognitive Bias Ruining Your Decisions",
            "Why Your Brain Lies to You Every Day",
            "The Sunk Cost Trap You're Stuck In",
            "How Confirmation Bias Controls Your Opinions",
            "The Anchoring Effect Everyone Falls For",
            "3 Mental Traps You Fall Into Daily",
            "Why Your Memory Rewrites the Past",
            "The Bias That Makes You Trust the Wrong People",
        ],
        "search_terms": ["cognitive biases", "cognitive bias examples", "brain tricks",
                         "thinking errors", "psychology of decision making"],
        "tags": ["cognitive biases", "brain tricks", "psychological biases", "thinking errors",
                 "anchoring effect", "confirmation bias", "decision making"],
    },
    {
        "key": "red_flags",
        "name": "Toxic Relationships & Red Flags",
        "trend": "very high — gaslighting/trauma-bond shorts are the biggest psychology sub-niche",
        "hooks": [
            "7 Red Flags You're Being Emotionally Manipulated",
            "How Gaslighting Destroys Your Self-Esteem",
            "The Trauma Bond That Keeps You Trapped",
            "5 Signs Your Partner Is Emotionally Abusing You",
            "Why You Can't Leave a Toxic Relationship",
            "The Cycle of Abuse You Keep Repeating",
            "How Love Bombing Turns Into Control",
            "The Silent Treatment: A Power Move Explained",
        ],
        "search_terms": ["gaslighting", "toxic relationship signs", "trauma bond",
                         "emotional abuse", "narcissist relationship"],
        "tags": ["gaslighting", "toxic relationship", "red flags", "emotional abuse",
                 "trauma bond", "love bombing", "narcissist"],
    },
    {
        "key": "stoic_mind",
        "name": "Stoicism × Modern Psychology",
        "trend": "very high — stoicism is the #1 trending philosophy/psychology fusion of 2025-26",
        "hooks": [
            "Stoic Rules That End Overthinking",
            "The Marcus Aurelius Trick for Emotional Control",
            "Why Stoics Never Get Manipulated",
            "4 Stoic Lessons for a Dark World",
            "The Ancient Psychology of Handling Criticism",
            "How Stoics Control What You Can't",
            "The 5-Second Stoic Pause That Changes Everything",
            "What Seneca Knew About Toxic People",
        ],
        "search_terms": ["stoicism", "stoic psychology", "stoic quotes", "emotional control",
                         "mindset psychology", "mental toughness"],
        "tags": ["stoicism", "stoic", "marcus aurelius", "seneca", "mental toughness",
                 "emotional control", "psychology", "mindset"],
    },
    {
        "key": "mind_control",
        "name": "Mind Control & Dark History",
        "trend": "medium-high — true-crime-psychology crossover, evergreen",
        "hooks": [
            "MKUltra: The CIA's Mind Control Program",
            "The Stanford Prison Experiment Explained",
            "How Cults Rewire Your Brain",
            "The Milgram Experiment: Would You Obey?",
            "How Jonestown Brainwashed 900 People",
            "The Asch Experiment: Why You Conform",
            "How Propaganda Programs the Public",
            "The Psychology of Brainwashing Revealed",
        ],
        "search_terms": ["MKUltra", "stanford prison experiment", "milgram experiment",
                         "cult psychology", "brainwashing", "psychology experiments"],
        "tags": ["mind control", "MKUltra", "stanford prison experiment", "milgram experiment",
                 "cult psychology", "dark history", "psychology experiments"],
    },
]

# ─────────────────────────────────────────────────────────────
# Hook styles (ML learns which perform best)
# ─────────────────────────────────────────────────────────────
HOOK_STYLES = [
    "pattern_interrupt",   # "Stop scrolling — this affects you daily"
    "knowledge_gap",       # "Psychologists just discovered why..."
    "fear_based",          # "This is happening to you right now"
    "curiosity_trigger",   # "The word manipulators are terrified of"
    "counterintuitive",    # "Kindness is your biggest weakness"
    "dark_revelation",     # "You've been lied to about manipulation"
    "stoic_echo",          # "Marcus Aurelius would never allow this"
    "red_flag_checklist",  # "If they do these 3 things, run"
]

# ─────────────────────────────────────────────────────────────
# Video specs
# ─────────────────────────────────────────────────────────────
FPS = 30
SHORTS = {"width": 1080, "height": 1920, "min_s": 40, "max_s": 58}
LONG_FORM = {"width": 1280, "height": 720, "min_s": 480, "max_s": 900}
SQUARE = {"width": 1080, "height": 1080}  # optional IG feed variant

# ─────────────────────────────────────────────────────────────
# Platforms
# ─────────────────────────────────────────────────────────────
PLATFORMS = {
    "youtube": {
        "enabled": True,
        "format": "shorts",            # shorts | long
        "width": SHORTS["width"], "height": SHORTS["height"],
        "category": "27",              # Education
        "max_daily": 3,
        "timezone": "America/New_York",
        "peak_hours": [7, 12, 20],     # EST/EDT
        "hashtags": 3,
        "algorithm_notes": ("Retention first 5s + 100% watch-through drive the "
                            "Shorts feed; title keyword in first 100 chars; "
                            "description keyword-dense first 2 lines."),
    },
    "facebook": {
        "enabled": True,
        "format": "reels",             # reels | video
        "width": SHORTS["width"], "height": SHORTS["height"],
        "max_daily": 2,
        "timezone": "America/New_York",
        "peak_hours": [9, 13, 20],
        "hashtags": 8,
        "algorithm_notes": ("FB Reels: first-3s hook + comments in first hour "
                            "drive reach; 9:16 <90s posts to Reels tab; "
                            "engagement (shares, reactions) is the top signal."),
    },
    "instagram": {
        "enabled": True,
        "format": "reels",
        "width": SHORTS["width"], "height": SHORTS["height"],
        "max_daily": 2,
        "timezone": "America/New_York",
        "peak_hours": [11, 19],
        "hashtags": 20,                # IG allows 30; 15-20 sweet spot
        "algorithm_notes": ("IG Reels: watch-time %, replay, shares, saves; "
                            "post at 11am-2pm / 7-9pm EST; save-value content "
                            "('save this') boosts distribution."),
    },
}

# ─────────────────────────────────────────────────────────────
# Monetization targets (2026 thresholds — research-verified)
# ─────────────────────────────────────────────────────────────
MONETIZATION = {
    "youtube": {
        "full_ytp": {"subs": 1000, "watch_hours": 4000, "shorts_views_90d": 10_000_000},
        "tier1": {"subs": 500, "watch_hours": 3000, "shorts_views_90d": 3_000_000},
        "strategy": "Daily Shorts (Shorts-views path) + weekly 10-15min long-form (watch-hours path)",
    },
    "facebook": {
        "cmp": {"followers": 5000, "minutes_60d": 60_000, "uploads_30d": 5},
        "stars": {"followers": 500},
        "strategy": "Daily Reels (60-90s, qualifies for in-stream ads) + long-form weekly",
    },
    "instagram": {
        "partner": {"followers": 500, "days_active": 60, "plays_60d": 3_000_000},
        "strategy": "Daily Reels; bonuses/partner are invite-driven — prioritize saves & shares",
    },
    "plan_days": 30,
    "daily_posts_per_platform": {"youtube": 2, "facebook": 2, "instagram": 2},
    "weekly_long_form": 1,
}

# ─────────────────────────────────────────────────────────────
# Music
# ─────────────────────────────────────────────────────────────
MUSIC_VOLUME = float(os.environ.get("MUSIC_VOLUME", "0.05"))
MUSIC_DIR = ROOT / "assets" / "music"

# ─────────────────────────────────────────────────────────────
# TTS
# ─────────────────────────────────────────────────────────────
TTS_PRIMARY = os.environ.get("TTS_PRIMARY", "kokoro")   # kokoro | edge | elevenlabs
KOKORO_VOICE = os.environ.get("KOKORO_VOICE", "am_fenrir")  # deep authoritative male
KOKORO_SPEED = float(os.environ.get("KOKORO_SPEED", "0.98"))
KOKORO_LANG = "a"  # American English

# ─────────────────────────────────────────────────────────────
# Clip providers
# ─────────────────────────────────────────────────────────────
CLIP_PROVIDER_ORDER = ["pexels", "pixabay"]  # fallback chain
CLIP_CACHE_TTL_DAYS = 30
MIN_CLIP_BYTES = 100_000

# ─────────────────────────────────────────────────────────────
# ML engine
# ─────────────────────────────────────────────────────────────
ML_STORE_PATH = DATA_DIR / "learning_store.json"
LEARNING = {
    "epsilon": 0.15,          # exploration rate
    "min_plays_before_greedy": 6,
    "dedup_window": 60,       # videos to compare against for variation
    "min_variation": 0.35,    # min 1 - token-overlap vs recent posts
    "reward_retention": 0.6,  # weight of retention on reward
    "reward_engagement": 0.3,
    "reward_views": 0.1,
    "penalty_failure": -2.0,  # upload/API failure
    "penalty_low_retention": -1.0,
    "bonus_viral": 3.0,       # reward for strong output
    "bonus_consistent": 1.0,
}
