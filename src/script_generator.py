#!/usr/bin/env python3
"""
Coercion Files — Script Generator.

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
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import HOOK_STYLES, NICHE, PILLARS
from ml_engine import LearningSystem

logger = logging.getLogger("script_generator")

GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")

SYSTEM_PROMPT = """You are the lead investigative writer for "Coercion Files" — a premium, high-retention documentary channel analyzing FORENSIC SOCIAL ENGINEERING, HIGH-STAKES PSYCHOLOGICAL DECEPTION, and SELF-DEFENSE for a smart USA audience.

AUDIENCE: USA adults (25-50), skeptical, analytical, interested in true-crime psychology, financial deception, workplace power dynamics, and self-defense.

TONE & STYLE (HUMAN DOCUMENTARY FEEL):
1. NO GENERIC AI FLUFF: Never say "In this video", "Welcome back", "Have you ever wondered", "It is important to remember", or list boring generic bullet points.
2. IN MEDIAS RES HOOK: Start scene 1 immediately in the middle of a high-stakes, shocking, or concrete situation (a specific scenario, real date/number, or dangerous psychological trap). Max 8 words for the hook overlay.
3. CONCRETE ANCHORS: Use tangible details (e.g., "$400k wire transfer", "3-word text message", "1-on-1 meeting", "police interrogation transcript", "declassified memo").
4. HUMAN PACING: Write in short, rhythmic, punchy sentences with natural breath pauses (use '—' and '...' where natural). Avoid long academic run-on sentences.
5. 4-BEAT RETENTION ARC:
   - Beat 1 (0-3s): The Disruptor Hook (curiosity/danger gap).
   - Beat 2 (3-15s): The Psychological Exploit (how the brain glitch is triggered).
   - Beat 3 (15-38s): The Forensic Case Breakdown / Concrete Real Example.
   - Beat 4 (38-55s): The Tactical Immunity (the 1 phrase or action to disarm it) + Loop CTA.
6. MONETIZATION SAFETY: Strictly educational/documentary framing. We decode deception to PROTECT viewers, never to teach malicious harm.
7. TARGET DURATION: 48-58 seconds (approx 110-145 spoken words total across scenes).
8. CINEMATIC VISUAL PROMPTS: Generate specific, moody, documentary b-roll search terms (e.g., "bank vault cctv dark", "redacted fbi document desk", "shadowed interrogation room", "smartphone notification late night", "rain reflection city neon dark") NOT generic smiling stock models.
9. ENGAGEMENT COMPULSION (critical): Beat 4 ends with a NATURAL but compelling like ask using ONE of these psychology hooks (varied, never robotic, never "please like and subscribe"): (a) reciprocity — "this took 9 hours to research, one like is earned"; (b) algorithm-altruism — "hit like or the algorithm won't show this to someone who needs it"; (c) identity — "if you're the kind of person who opens their eyes, like this"; (d) cliffhanger — "part 2 drops if this hits 10k likes"; (e) challenge — "comment what you'd do in this position". Add a short comment question 50% of the time. Keep it 1-2 punchy sentences, authentic documentary voice.

OUTPUT — ONLY valid JSON, no markdown formatting:
{
  "title": "High CTR Viral Title (<=70 chars, search keyword included)",
  "hook": "Exact 2-second hook text shown on screen (<=85 chars)",
  "scenes": [
    {
      "caption": "Punchy human narration for this scene",
      "caption_roman": "Same text",
      "visual": "Specific moody cinematic b-roll query (2-4 words)",
      "emotion": "dark|mysterious|intense|chilling|revelatory"
    }
  ],
  "tags": ["up to 10", "targeted", "usa", "tags"],
  "description": "Engaging 3-sentence description with search keywords and educational disclaimer",
  "key_points": "• Point 1\\n• Point 2\\n• Point 3"
}
Output ONLY the raw JSON object."""


def _groq_with(model: str, prompt: str) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": model,
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
                 "Content-Type": "application/json",
                 # V2.9.14: Cloudflare (error 1010) blocks Python-urllib's
                 # default UA → 403 on valid keys. Send a real UA.
                 "User-Agent": "CoercionFiles-CI/1.0"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read())["choices"][0]["message"]["content"]


def _groq(prompt: str) -> str:
    """V2.2.1: Groq DEPRECATED the Llama chat models (403 on
    llama-3.3-70b-versatile). Walk a model ladder: gpt-oss-120b → 20b → legacy.
    Override via GROQ_MODELS env (comma list) or GROQ_MODEL (single)."""
    single = os.environ.get("GROQ_MODEL", "").strip()
    models = ([single] if single else
              [m.strip() for m in os.environ.get(
                  "GROQ_MODELS",
                  "openai/gpt-oss-120b,openai/gpt-oss-20b,llama-3.3-70b-versatile"
              ).split(",") if m.strip()])
    last_exc = None
    for model in models:
        try:
            return _groq_with(model, prompt)
        except Exception as exc:
            last_exc = exc
            logger.warning("Groq model %s failed: %s", model, exc)
    raise last_exc


def _gemini_with(model: str, prompt: str) -> str:
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent")
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 2200, "temperature": 0.85,
                             "responseMimeType": "application/json"},
    }
    # key in header (x-goog-api-key) — safer than URL query string
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": GEMINI_KEY,
                 # V2.9.14: same Cloudflare/UA guard as Groq
                 "User-Agent": "CoercionFiles-CI/1.0"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read())
        return data["candidates"][0]["content"]["parts"][0]["text"]


def _gemini(prompt: str) -> str:
    """V2.2.2: model ladder — older flash models get deprecated over time."""
    models = [m.strip() for m in os.environ.get(
        "GEMINI_MODELS", "gemini-2.5-flash,gemini-2.0-flash").split(",") if m.strip()]
    last_exc = None
    for model in models:
        try:
            return _gemini_with(model, prompt)
        except Exception as exc:
            last_exc = exc
            logger.warning("Gemini model %s failed: %s", model, exc)
    raise last_exc


def _replace_hook_everywhere(script: dict, old_hook: str) -> None:
    """V3.5: hook override ke saath scene-1 aur title bhi update karo.

    Pehle sirf script["hook"] badla jata tha — scene 1 mein PURANA hook
    reh jata tha. Independent ScriptGuard ne isay pakra: overlay kuch aur
    kehta hai, narration kuch aur = clickbait gap = retention killer.
    """
    new_hook = script.get("hook", "")
    if not new_hook or not script.get("scenes"):
        return
    old_low = (old_hook or "").strip().lower()
    s0 = script["scenes"][0]
    cap = s0.get("caption", "")
    idx = cap.lower().find(old_low) if old_low else -1
    if idx >= 0:
        new_cap = (cap[:idx] + new_hook + cap[idx + len(old_hook):]).strip()
        s0["caption"] = new_cap
        s0["caption_roman"] = new_cap
    title = script.get("title", "")
    if old_low and old_low in title.lower():
        script["title"] = re.sub(re.escape(old_hook), new_hook, title,
                                 flags=re.I)


def _parse_script(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    script = json.loads(text)
    assert "title" in script and "scenes" in script, "missing title/scenes"
    assert len(script["scenes"]) >= 3, "need >=3 scenes"
    for s in script["scenes"]:
        s.setdefault("caption", "")
        s.setdefault("caption_roman", s["caption"])
        s.setdefault("visual", "dark moody city night cinematic")
        s.setdefault("emotion", "dark")
    script.setdefault("hook", script["scenes"][0].get("caption", "")[:80])
    script.setdefault("tags", ["psychology", "dark psychology", "manipulation"])
    return script


def _template_script(pillar: dict, hook_style: str) -> dict:
    """Offline template bank — randomized forensic human storytelling per pillar."""
    hook = random.choice(pillar["hooks"])

    # Forensic narrative setups (Concrete human case anchors)
    narrative_setups = {
        "cults": [
            "In documented case files, high-control groups never recruit with ideology — they recruit with belonging. The moment your life hits turbulence, their script begins.",
            "Declassified exit interviews reveal the exact same pattern: strangers flood you with warmth, validate your hidden pain, and make you feel finally understood.",
            "Psychologists call it the 'belonging trap'. You don't join because you are gullible — you join because you are human and exhausted.",
        ],
        "con_artists": [
            "Federal fraud analysts found that 92% of wire scams rely on a single psychological trigger: manufactured urgency that shuts down analytical thinking.",
            "In 2024, an American executive wired $380,000 in under ten minutes. The scammer didn't hack a computer — they hacked human fear.",
            "The script is always identical: a sudden crisis, a closing window, and an authoritative voice demanding immediate secrecy.",
        ],
        "interrogation": [
            "FBI behavioral analysts know that guilty suspects rarely break from aggressive shouting — they break from deliberate, strategic silence.",
            "When an investigator stays silent for four seconds after a statement, the suspect's anxiety forces them to fill the void with unnecessary details.",
            "Statement analysis shows that innocent people answer directly, while deceptive answers include extra justifications and narrative padding.",
        ],
        "coercive_control": [
            "In workplace and relationship psychology, covert control never starts with overt aggression — it begins with subtle boundary erosion.",
            "First, your judgment is questioned. Then, your external support network is quietly undermined until you doubt your own perception.",
            "Behavioral scientists call this cognitive erosion. When someone repeatedly says 'you are overreacting', it is a control mechanism.",
        ],
        "mind_control_history": [
            "Declassified government archives show that decades of behavioral research converged on one truth: isolation is the prerequisite for mental control.",
            "Project files confirm that when external reference points are removed, the human mind rapidly adapts to whatever reality the authority provides.",
            "Historical transcripts demonstrate how language reframing can gradually normalize ideas that once seemed completely unthinkable.",
        ],
        "mass_psychology": [
            "Modern engagement algorithms are engineered around evolutionary threat detection: outrage and fear circulate six times faster than calm facts.",
            "When a feed repeatedly exposes you to artificial conflict, your nervous system adopts a defensive baseline without your conscious awareness.",
            "Data scientists call it the outrage loop: keep the user agitated, and their attention remains captive for advertisers.",
        ],
        "brainwashing_myths": [
            "Contrary to Hollywood spy films, thought reform is not a mysterious chemical process — it is systematic, high-pressure repetition.",
            "Behavioral research confirms that beliefs do not change overnight; they shift through hundreds of micro-commitments over time.",
            "The real danger is not sudden brainwashing, but gradual normalization of subtle boundary violations.",
        ],
        "stoic_defense": [
            "Stoic philosophy provided the earliest psychological shield: the five-second gap between an external stimulus and your internal reaction.",
            "Marcus Aurelius documented daily mental preparation against deceivers: recognize that urgency is almost always an artificial manipulation.",
            "When you refuse to react on someone else's timeline, their entire high-pressure script immediately collapses.",
        ],
    }

    forensic_proofs = [
        "Neuroimaging shows that high-urgency language triggers the amygdala, effectively disabling the prefrontal cortex's ability to evaluate risk.",
        "Behavioral data proves that once you agree to three small, insignificant requests, your likelihood of agreeing to a major concession triples.",
        "Cognitive psychologists call this the compliance cascade: small surrenders quietly condition you for total capitulation.",
        "Clinical analysis demonstrates that manipulators always rush the timeline because logic and sleep are their greatest enemies.",
    ]

    # V3.5: second concrete detail — template scripts 86-94 words ki thin
    # (ScriptGuard 90+ chahta hai) aur ek hi proof thin. Ye scene script ko
    # ~105+ words tak le jata hai + retention ke liye ek aur forensic detail.
    second_details = [
        "In the declassified case file, the victim described the same loop: trust first, then isolation, then urgency.",
        "Investigators found the same script in fourteen separate cases, word for word.",
        "The transcript shows the suspect never once raised their voice. Control is quiet.",
        "Court records confirm the manipulation started three weeks before any money moved.",
    ]

    tactical_shields = [
        "The universal defense is simple: the second you feel pressured to act instantly, force a 24-hour pause. Real opportunities survive sleep; scams don't.",
        "Your tactical shield is to name the tactic aloud: 'Why is this urgent?' The moment urgency is questioned, the manipulator loses leverage.",
        "The psychological antidote is unwavering boundary clarity: never make a financial or emotional commitment under manufactured time pressure.",
        "Remember: legitimate authorities will never demand instant secrecy or immediate wire transfers. Pause, breathe, and verify independently.",
    ]

    # V3.3: COMPULSION CTA — audience ko like karna majboor (psychology).
    # Template CTAs ab compulsion_cta.cta_pair() se aate hain — har video
    # alag principle (algorithm-altruism, reciprocity, identity, challenge).
    try:
        from compulsion_cta import cta_pair
        _cta_lines = cta_pair()
        cta = " ".join(_cta_lines)
    except Exception:
        cta = ("If this pattern just clicked for you, hit like — it shows "
               "this to someone who needs it. And comment: have you seen "
               "this play out? I read everything.")

    setup = random.choice(narrative_setups.get(pillar.get("key"), narrative_setups["con_artists"]))
    proof = random.choice(forensic_proofs)
    detail = random.choice(second_details)
    shield = random.choice(tactical_shields)

    visuals = [
        "bank cctv footage dark",
        "redacted fbi dossier desk",
        "shadowed figure corridor night",
        "smartphone screen notification dark",
        "rain on window city neon",
        "interrogation room mirror dark",
        "financial chart red drop",
        "cyber security glitch screen dark",
    ]


    scenes = [
        {
            "caption": f"{hook}. Here is the exact case breakdown.",
            "caption_roman": f"{hook}. Here is the exact case breakdown.",
            "visual": visuals[0],
            "emotion": "intense",
        },
        {
            "caption": setup,
            "caption_roman": setup,
            "visual": visuals[1],
            "emotion": "mysterious",
        },
        {
            "caption": proof,
            "caption_roman": proof,
            "visual": visuals[2],
            "emotion": "dark",
        },
        {
            "caption": detail,
            "caption_roman": detail,
            "visual": visuals[3],
            "emotion": "chilling",
        },
        {
            "caption": shield,
            "caption_roman": shield,
            "visual": visuals[4],
            "emotion": "revelatory",
        },
        {
            "caption": cta,
            "caption_roman": cta,
            "visual": visuals[5],
            "emotion": "revelatory",
        },
    ]

    # V3.5: title ke pehle 3 words mein keyword/power hona chahiye (CTRGuard
    # rule). Agar hook khud keyword se shuru nahi hota to keyword prefix karo.
    title = f"{hook} | Forensic Psychology"
    kw = (pillar.get("search_terms") or ["psychology"])[0]
    first3 = " ".join(title.split()[:3]).lower()
    if kw.lower() not in first3 and "psychology" not in first3:
        title = f"{kw.title()}: {hook}"[:100]

    return {
        "title": title,
        "hook": hook,
        "scenes": scenes,
        "tags": pillar["tags"][:10],
        "description": (f"{hook} — Forensic case breakdown: how high-stakes deception works "
                        f"and the exact psychological defense to protect yourself. "
                        f"{NICHE['angle']} #psychology #truecrime #scams"),
        "key_points": "• The psychological exploit explained\n• How the brain trap works\n• 1-step tactical defense",
        "pillar": pillar["key"],
        "pillar_name": pillar["name"],
    }


def generate_script(pillar_key: str = None, hook_style: str = None,
                    ml: LearningSystem = None, topic: str = None) -> dict:
    """Generate one short-form script (45-58s)."""
    # ── strategy selection (ML-informed) ──
    arm_key = None
    if ml is not None and not pillar_key:
        chosen = ml.choose_strategy()
        pillar = next(p for p in PILLARS if p["key"] == chosen["pillar"])
        hook_style = hook_style or chosen["hook_style"]
        arm_key = chosen["arm_key"]   # V2.1: exact arm travels with the script
    else:
        pillar = next((p for p in PILLARS if p["key"] == pillar_key), None)
        if pillar is None:
            pillar = random.choice(PILLARS)
        hook_style = hook_style or random.choice(HOOK_STYLES)
        if ml is not None:
            # forced pillar — still attribute to a consistent arm key
            from ml_engine import current_day_part
            arm_key = ml.arm_key(pillar["key"], hook_style, current_day_part())

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

    # ── LLM chain (V2.9.13: provider preference — self-healing) ──
    # V3.1: HOOK QUALITY GATE — weak hook (score < 1.0) = weak engagement
    # (97 views / 0 likes ka sabab). Weak hook par naya script regenerate
    # karte hain (max 3 attempts) taake first-2-second pattern-interrupt
    # strong ho.
    _state_path = Path(__file__).resolve().parent.parent / "data" / "llm_state.json"
    preferred = None
    try:
        if _state_path.exists():
            preferred = json.loads(_state_path.read_text(encoding="utf-8")).get("provider")
    except (OSError, json.JSONDecodeError):
        preferred = None

    script = None
    source = None
    hook_score = 0.0
    for _attempt in range(4):
        script = None
        source = None
        providers = {"groq": (_groq, GROQ_KEY), "gemini": (_gemini, GEMINI_KEY)}
        order = [pp for pp in (preferred, "gemini", "groq") if pp in providers]
        for name in order:
            fn, key = providers[name]
            if not key:
                continue
            try:
                script = _parse_script(fn(prompt))
                source = name
                break
            except Exception as exc:
                logger.warning("%s failed: %s", name, exc)
        if script is None:
            script = _template_script(pillar, hook_style)
            source = "template"
            logger.info("Using template fallback (no LLM key or LLM failed)")
        try:
            from viral_intel import score_hook
            hook_score = score_hook(script.get("hook", ""))["score"]
        except Exception:
            hook_score = 1.0
        # V3.1: DURATION CHECK — LLM scripts 34s par aa rahi thin (target 45-58s).
        # Choti script = weak retention + Shorts shelf par nuksan.
        _words = len(" ".join(str(sc.get("caption", ""))
                              for sc in script.get("scenes", [])).split())
        _est = _words / 2.2
        too_short = _est < 38 and source in ("groq", "gemini")
        # V3.4: gate ab 0.60 hai (honest scale) — 0.85 purane inflated scale
        # ka tha jahan base hi 0.55 tha. Ab weak hook genuinely regenerate
        # hota hai, sirf praise nahi milti.
        if hook_score >= 0.60 and not too_short:
            break
        if too_short and _attempt < 3:
            prompt += ("\n\nIMPORTANT: The previous script was too short "
                       f"(~{_est:.0f}s, target 48-58s). Make it LONGER: "
                       "extend to ~120-140 spoken words with one more concrete "
                       "forensic detail, a second real example, and a named "
                       "psychology concept/study (e.g. Milgram, Stanford, "
                       "Cialdini, cognitive dissonance).")
            logger.warning("Script too short (~%ds) — retrying with 'make longer' hint",
                           round(_est))
        else:
            logger.warning("Hook weak (score %.2f) — regenerating script (attempt %d/4)",
                           hook_score, _attempt + 2)
    # V3.1 + V3.4: hook fallback — regen ke baad bhi weak ho to documented
    # strong hook se override. V3.4: (1) threshold 0.60 honest scale,
    # (2) CURATED pillar hooks ko priority (pehle fragment-generator pehle
    # chalta tha — "Stop letting them" jaise aadhe hooks overlay par chale
    # jaate thay), (3) replacement tabhi jab wo GENUINELY behtar score kare.
    if hook_score < 0.60:
        candidates = ([h for h in pillar.get("hooks", []) if h]
                      if pillar.get("hooks") else [])
        try:
            from viral_intel import random_boosted_hook as _rbh
            candidates += [_rbh(), _rbh()]
        except Exception:
            pass
        best, best_score = None, hook_score
        for cand in candidates:
            cand = cand[:85]
            try:
                from viral_intel import score_hook as _sh
                cs = _sh(cand)["score"]
            except Exception:
                cs = 0.0
            if cs > best_score:
                best, best_score = cand, cs
        if best:
            _old_hook = script.get("hook", "")
            script["hook"] = best
            _replace_hook_everywhere(script, _old_hook)   # V3.5: scene1+title sync
            hook_score = best_score
            logger.info("Hook overridden with strong documented hook (score %.2f)",
                        hook_score)
    # V3.3: CTA repair — compulsion CTA (psychology like-bait) append agar
    # script mein like/comment/save trigger nahi hai.
    _eng_words = ("like", "comment", "follow", "save", "share", "subscribe", "hit")
    _full = " ".join(sc.get("caption", "") for sc in script.get("scenes", [])).lower()
    if not any(w in _full for w in _eng_words) and len(script.get("scenes", [])) < 6:
        try:
            from compulsion_cta import build_engaging_last_scene
            script["scenes"].append(build_engaging_last_scene(pillar.get("key")))
            logger.info("CTA repair: compulsion engagement scene appended")
        except Exception:
            pass

    # ── V3.1: FULL SCRIPT QUALITY GATE — sirf hook nahi, poora script ──
    # score_script: hook(0.25) + cta(0.20) + anchor(0.20) + psych(0.15) +
    # structure(0.10) + duration(0.10). Weak (C/D) → documented pillar hook
    # + repair list store. Ye score script ke saath travels karta hai taake
    # ML engagement doctor isay use kar sake.
    _quality = {"score": 0.5, "issues": ["unknown"], "components": {}}
    try:
        from viral_intel import score_script as _score_script
        from viral_intel import score_script_grade
        _quality = _score_script(script)
        if _quality["score"] < 0.65:
            # repair: documented strong hook override (human creator ki
            # swipe file — pillar hooks settings mein already curated hain)
            pillar_hooks = ([h for h in pillar["hooks"] if h]
                            if pillar.get("hooks") else [])
            if pillar_hooks:
                _old_hook = script.get("hook", "")
                script["hook"] = random.choice(pillar_hooks)[:85]
                _replace_hook_everywhere(script, _old_hook)   # V3.5 sync
                logger.info("SCRIPT quality gate: weak score %.2f → hook replaced "
                            "with proven pillar hook", _quality["score"])
                try:
                    hook_score = score_hook(script.get("hook", ""))["score"]
                except Exception:
                    hook_score = 1.0
                _quality = _score_script(script)  # re-score
        logger.info("SCRIPT quality: %.2f (%s) issues=%s",
                    _quality["score"], score_script_grade(_quality["score"]),
                    _quality.get("issues", []))
    except Exception as exc:
        logger.warning("script quality gate skipped: %s", exc)

    # remember which provider worked (self-healing order)
    if source in ("groq", "gemini"):
        try:
            _state_path.parent.mkdir(parents=True, exist_ok=True)
            _state_path.write_text(json.dumps({"provider": source}), encoding="utf-8")
        except OSError:
            pass

    script["source"] = source
    script["hook_score"] = round(hook_score, 3)
    script["script_quality"] = _quality
    script["pillar"] = pillar["key"]
    script["pillar_name"] = pillar["name"]
    script["hook_style"] = hook_style
    script["arm_key"] = arm_key or LearningSystem.arm_key(
        pillar["key"], hook_style, "any")
    script.setdefault("tags", pillar["tags"][:10])

    # ── V3.1: CTR-OPTIMIZED TITLE — generate high-CTR title variants ──
    # V3.4: threshold 0.55 (honest scale) + sirf tab replace karo jab naya
    # title GENUINELY behtar score kare (pehle blind replace hota tha).
    try:
        from ctr_optimizer import describe_ctr_grade, pick_best_title, score_title_ctr, suggest_ctr_improved_title
        _title_score = score_title_ctr(script.get("title", ""), "youtube")
        if _title_score.score < 0.55:
            _variants = suggest_ctr_improved_title(
                script.get("hook", script.get("title", "")),
                "youtube",
                pillar_keywords=[p["key"] for p in PILLARS]
            )
            if _variants:
                _best = pick_best_title(script.get("hook", ""), _variants, "youtube")
                if score_title_ctr(_best, "youtube").score > _title_score.score:
                    script["title"] = _best
                    logger.info("CTR title boost: %s → %s (%s)",
                                _title_score.title[:40], script["title"][:40],
                                describe_ctr_grade(
                                    score_title_ctr(script["title"], "youtube").score))
    except Exception as exc:
        logger.warning("CTR title optimization skipped: %s", exc)

    return script


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    s = generate_script()
    print(json.dumps(s, indent=2, ensure_ascii=False))
