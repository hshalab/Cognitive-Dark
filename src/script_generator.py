#!/usr/bin/env python3
"""
Cognitive Dark V2 — Script Generator.

  • Primary : Groq (Llama-3.3-70B, JSON mode)
  • Fallback: Gemini 2.0 Flash
  • Fallback: randomized template bank (offline-safe)
  • ML loop : the prompt is enriched with the ML engine's best-performing
    hook styles & pillars, so the system writes toward what already works.

Every script follows the viral retention structure:
  HOOK (0-3s pattern interrupt) → STAKES → PAYOFF/EVIDENCE → TWIST → CTA
And is framed educationally ("protect yourself") for monetization safety.
"""

import json
import logging
import os
import random
import re
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import PILLARS, HOOK_STYLES, NICHE
from ml_engine import LearningSystem

logger = logging.getLogger("script_generator")

GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")

SYSTEM_PROMPT = """You are the scriptwriter for "Cognitive Dark" — a faceless YouTube/Instagram/Facebook channel about THE PSYCHOLOGY OF INFLUENCE & SELF-DEFENSE.

AUDIENCE: USA adults (25-44), interested in psychology, self-improvement, toxic relationships, stoicism, human behavior.

HARD RULES:
1. Educational framing ONLY: teach viewers how manipulation WORKS so they can PROTECT themselves. NEVER instruct how to manipulate/harm others. (This keeps the channel monetization-safe.)
2. American English, dark-mysterious-authoritative tone, short punchy sentences.
3. Each scene = one spoken sentence block, 8-14 seconds of speech (~20-35 words).
4. Total narration 100-150 words; Short duration target 45-58 seconds.
5. Hook (scene 1) must be a pattern-interrupt: stop-scroll, curiosity/fear/knowledge-gap in the first 2 seconds.
6. Include at least one REAL psychology concept/study (e.g., Milgram, Stanford, Cialdini, anchoring, cognitive dissonance, trauma bond).
7. Final scene: CTA "Follow Cognitive Dark for more psychology they don't teach you in school."
8. Never diagnose or give medical advice. Add no emojis in captions.

OUTPUT — ONLY valid JSON, no markdown:
{
  "title": "Viral title, <=70 chars, includes a search keyword",
  "hook": "The exact 2-second hook text shown on screen (<=90 chars)",
  "scenes": [
    {"caption": "narration for this scene", "caption_roman": "same text",
     "visual": "short stock-video search query (2-4 words, e.g. 'dark city rain')",
     "emotion": "dark|mysterious|intense|chilling|revelatory"}
  ],
  "tags": ["up to 12", "youtube", "tags"],
  "description": "3-4 sentence description with keywords in the first sentence",
  "key_points": "3 bullet points of what the viewer learns"
}
Output ONLY the JSON object."""


def _groq(prompt: str) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.85,
        "max_tokens": 2200,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {GROQ_KEY}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read())["choices"][0]["message"]["content"]


def _gemini(prompt: str) -> str:
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{os.environ.get('GEMINI_MODEL', 'gemini-2.0-flash')}:generateContent")
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 2200, "temperature": 0.85,
                             "responseMimeType": "application/json"},
    }
    # key in header (x-goog-api-key) — safer than URL query string
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": GEMINI_KEY})
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read())
        return data["candidates"][0]["content"]["parts"][0]["text"]


def _parse_script(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    script = json.loads(text)
    assert "title" in script and "scenes" in script, "missing title/scenes"
    assert len(script["scenes"]) >= 3, "need >=3 scenes"
    for i, s in enumerate(script["scenes"]):
        s.setdefault("caption", "")
        s.setdefault("caption_roman", s["caption"])
        s.setdefault("visual", "dark moody city night cinematic")
        s.setdefault("emotion", "dark")
    script.setdefault("hook", script["scenes"][0].get("caption", "")[:80])
    script.setdefault("tags", ["psychology", "dark psychology", "manipulation"])
    return script


def _template_script(pillar: dict, hook_style: str) -> dict:
    """Offline template bank — randomized per call, per pillar, per style."""
    hook = random.choice(pillar["hooks"])
    style_line = {
        "pattern_interrupt": "You need to hear this before your next conversation.",
        "knowledge_gap": "Psychologists just confirmed what most people refuse to believe.",
        "fear_based": "This is happening to you more often than you realize.",
        "curiosity_trigger": "There's a word manipulators are terrified you'll learn.",
        "counterintuitive": "The trait you think is kindness is actually your weakness.",
        "dark_revelation": "You've been lied to about how influence really works.",
        "stoic_echo": "Even Marcus Aurelius warned against what you accept daily.",
        "red_flag_checklist": "If you notice these three signs, the answer is simple.",
    }[hook_style]

    # large variety bank → keeps 0% spam even without the LLM
    setups = [
        "Here's how it actually works. Your brain takes a mental shortcut every single "
        "time — and that shortcut is exactly what gets exploited.",
        "Most people miss it because it looks completely normal. That's the point. "
        "The most effective tactics hide in plain sight.",
        "Psychologists have studied this pattern for decades. Here's what they found.",
        "You've felt it before — that quiet discomfort you couldn't explain. Here's what it was.",
        "There's a reason this works on nearly everyone. It's wired into how we think.",
        "The research is clear on this one. Your instincts were right to be suspicious.",
        "This isn't a theory. It's a documented pattern of human behavior.",
        "Before you dismiss this, consider how often it's already happened to you.",
    ]
    proofs = [
        "Psychologists call this a cognitive bias. Once you see it, you can't unsee it. "
        "Studies show it shapes decisions you make every hour.",
        "Research into human behavior confirms it: familiarity breeds acceptance. "
        "The more you hear something, the more true it feels.",
        "A landmark study on this pattern found it works in under ten seconds. "
        "That's faster than you can catch yourself.",
        "The data from behavioral studies is striking: most people can't spot it "
        "until it's pointed out to them directly.",
        "Cognitive research shows your brain prefers the easy answer — and that "
        "preference is exactly what gets used against you.",
        "Studies on persuasion show this one factor explains more outcomes than "
        "any other — and it's the one nobody checks.",
    ]
    twists = [
        "The scariest part? It works silently. No raised voice, no threats — just a "
        "pattern repeated until it feels normal. That's the real danger.",
        "Once you recognize the pattern, you take your power back. Awareness is the "
        "only defense that actually works.",
        "And that's the part nobody tells you: it doesn't need your permission. "
        "It just needs your attention.",
        "Here's the twist — the people who use it often don't know they're doing it. "
        "It's learned behavior, passed down and repeated.",
        "The moment you name it, it loses its power over you. That's why awareness "
        "is the single strongest defense.",
        "What makes it dangerous is how ordinary it looks. But now that you've seen "
        "it, you'll start noticing it everywhere.",
    ]
    cta = random.choice([
        "Follow Cognitive Dark for the psychology they don't teach you in school.",
        "Follow for more psychology that protects you.",
        "Follow Cognitive Dark — the dark side of the human mind, decoded daily.",
        "Follow Cognitive Dark to see through the patterns before they see you.",
    ])

    body = (random.choice(setups), random.choice(proofs),
            random.choice(twists), cta)

    visuals = ["dark city night rain", "shadowed figure corridor", "black smoke abstract",
               "empty street fog", "close up eye dark", "storm clouds timelapse",
               "silhouette under streetlight", "foggy forest at night", "dark office empty",
               "rain on window night", "crowd of people city night", "old clock tower dark"]
    emotions = ["dark", "intense", "chilling", "mysterious", "revelatory"]

    scenes = [
        {"caption": hook, "caption_roman": hook,
         "visual": random.choice(visuals), "emotion": emotions[0]},
        {"caption": style_line, "caption_roman": style_line,
         "visual": random.choice(visuals), "emotion": emotions[1]},
    ]
    for i, c in enumerate(body[:-1]):
        scenes.append({"caption": c, "caption_roman": c,
                       "visual": random.choice(visuals), "emotion": emotions[(i + 2) % 5]})
    scenes.append({"caption": body[-1], "caption_roman": body[-1],
                   "visual": "glowing brain abstract dark", "emotion": "revelatory"})

    return {
        "title": f"{hook} | Dark Psychology Facts",
        "hook": hook,
        "scenes": scenes,
        "tags": pillar["tags"][:10],
        "description": (f"{hook} — understand the psychology behind it and protect "
                        f"yourself. {NICHE['angle']} #psychology #darkpsychology"),
        "key_points": "• How the tactic works\n• Why it works on you\n• How to protect yourself",
        "pillar": pillar["key"],
        "pillar_name": pillar["name"],
    }


def generate_script(pillar_key: str = None, hook_style: str = None,
                    ml: LearningSystem = None, topic: str = None) -> dict:
    """Generate one short-form script (45-58s)."""
    # ── strategy selection (ML-informed) ──
    if ml is not None and not pillar_key:
        chosen = ml.choose_strategy()
        pillar = next(p for p in PILLARS if p["key"] == chosen["pillar"])
        hook_style = hook_style or chosen["hook_style"]
    else:
        pillar = next((p for p in PILLARS if p["key"] == pillar_key), None)
        if pillar is None:
            pillar = random.choice(PILLARS)
        hook_style = hook_style or random.choice(HOOK_STYLES)

    # ── ML insights fed back into the prompt (closing the learning loop) ──
    learned_hint = ""
    if ml is not None:
        best = ml.best_formulas(3)
        if best:
            learned_hint = ("\n\nPERFORMANCE DATA (learn what works): recent top "
                            "formulas were pillars/styles: "
                            + ", ".join(f"{b['pillar']}/{b['hook_style']}"
                                        f"(score {b['mean']})" for b in best)
                            + ". Weight your choice toward these when relevant.")

    prompt = f"""Create a YouTube Short script (45-58 seconds) for the pillar "{pillar['name']}".
Hook style: {hook_style}.
Topic: {topic or pillar['name']}.
Pillar hooks for inspiration: {', '.join(pillar['hooks'][:5])}.
{learned_hint}
Write it now — valid JSON only."""

    # ── LLM chain ──
    script = None
    source = None
    if GROQ_KEY:
        try:
            script = _parse_script(_groq(prompt)); source = "groq"
        except Exception as exc:
            logger.warning("Groq failed: %s", exc)
    if script is None and GEMINI_KEY:
        try:
            script = _parse_script(_gemini(prompt)); source = "gemini"
        except Exception as exc:
            logger.warning("Gemini failed: %s", exc)
    if script is None:
        script = _template_script(pillar, hook_style); source = "template"
        logger.info("Using template fallback (no LLM key or LLM failed)")

    script["source"] = source
    script["pillar"] = pillar["key"]
    script["pillar_name"] = pillar["name"]
    script["hook_style"] = hook_style
    script.setdefault("tags", pillar["tags"][:10])
    return script


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    s = generate_script()
    print(json.dumps(s, indent=2, ensure_ascii=False))
