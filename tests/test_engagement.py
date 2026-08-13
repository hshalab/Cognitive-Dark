"""Tests for engagement layer (V3.1) — like-CTA in scripts, hook gate, audit."""
import subprocess
import sys
from pathlib import Path

from script_generator import _template_script
from viral_intel import score_hook


def _pillar():
    return {"key": "con_artists", "name": "Con Artists", "hooks": ["The hook"],
            "tags": ["a"], "search_terms": ["scam psychology"]}


def test_template_script_cta_mentions_engagement():
    """Har template script mein ya to like/comment ask ya follow CTA hona chahiye."""
    hits = {"like": 0, "comment": 0, "follow": 0, "save": 0, "share": 0}
    for _ in range(30):
        s = _template_script(_pillar(), "warning")
        text = " ".join(sc["caption"] for sc in s["scenes"]).lower()
        for word in hits:
            if word in text:
                hits[word] += 1
    # kuch scripts mein like/comment ask hona chahiye (60% engagement mix)
    assert hits["like"] > 0 or hits["comment"] > 0, f"no engagement CTA: {hits}"
    assert hits["follow"] + hits["save"] + hits["share"] > 0  # mix bhi hai


def test_hook_gate_scores():
    good = score_hook("Stop letting them control you.")["score"]
    weak = score_hook("Here is a video about some things")["score"]
    assert good > weak


def test_analyze_engagement_dry_runs(tmp_path):
    """--dry mode: bina YT creds bhi crash nahi — report file na bane (koi vids)."""
    try:
        import dotenv  # noqa: F401
    except ImportError:
        import pytest
        pytest.skip("python-dotenv not installed in sandbox")
    r = subprocess.run(
        [sys.executable, "scripts/analyze_engagement.py", "--dry"],
        cwd=Path(__file__).resolve().parent.parent,
        capture_output=True, text=True, timeout=60)
    # bina creds ke gracefully exit (0 ya 1 dono chalega, crash nahi)
    assert r.returncode in (0, 1)
    assert "Koi video" in r.stdout or "Videos:" in r.stdout


def test_score_script_strong_script():
    """Achhi script (hook + cta + anchor + psych) ko A/B grade milna chahiye."""
    from viral_intel import score_script, score_script_grade
    good = {
        "hook": "Stop letting them control you.",
        "scenes": [
            {"caption": "Stop letting them control you."},
            {"caption": "The $400k wire transfer happened in 3 days. Cognitive "
                         "dissonance made her send it."},
            {"caption": "Cialdini's scarcity principle explains the urgency. "
                         "If this helped, hit like and comment below."},
        ],
    }
    q = score_script(good)
    assert q["score"] >= 0.7, q
    assert score_script_grade(q["score"]) in ("A — strong script", "B — solid")


def test_score_script_weak_script():
    from viral_intel import score_script
    weak = {"hook": "Hello everyone", "scenes": [
        {"caption": "Welcome back to my channel"}]}
    q = score_script(weak)
    assert q["score"] < 0.5, q


def test_cta_pair_always_engaging():
    """cta_pair hamesha like/comment/save trigger de (compulsion engine)."""
    from compulsion_cta import cta_pair, has_engagement
    seen = set()
    for _ in range(60):
        pair = cta_pair()
        text = " ".join(pair)
        assert has_engagement(text), f"no engage word: {text}"
        # variation — har baar same na ho
        seen.add(text[:30])
    assert len(seen) >= 8, f"too repetitive: {len(seen)} unique"


def test_build_engaging_last_scene():
    from compulsion_cta import build_engaging_last_scene, has_engagement
    scene = build_engaging_last_scene("cults")
    assert has_engagement(scene["caption"])
    assert scene["caption_roman"] == scene["caption"]
    assert scene["emotion"] == "revelatory"


def test_llm_cta_instructions_present():
    from compulsion_cta import llm_cta_instructions
    txt = llm_cta_instructions()
    assert "reciprocity" in txt and "algorithm-altruism" in txt
    assert "please like and subscribe" in txt  # explicitly forbidden


def test_yt_package_always_has_keyword():
    """V3.6.3: SEOGuard keyword requirement — YT package title mein keyword
    HAMESHA hona chahiye, chahe CTR boost/title picker kuch bhi chune."""
    import random

    from config.settings import PILLARS
    from seo import build_platform_package
    random.seed(7)
    for _ in range(10):
        script = {
            "hook": "How One Ad Manipulated a Country",
            "title": "How One Ad Manipulated a Country",
            "pillar": "mind_control_history",
            "pillar_name": "Declassified Mind Control",
            "key_points": "• x",
            "tags": ["psychology"],
            "scenes": [{"caption": "How one ad manipulated a country with repeated messaging."},
                       {"caption": "The declassified files show the propaganda campaign ran for months."},
                       {"caption": "Milgram proved obedience rises under authority pressure."},
                       {"caption": "Hit like if this helps you spot manufactured consent. Comment below."}],
        }
        pkg = build_platform_package(script, "youtube", durations=[4.0] * 4)
        kw = next(p["search_terms"][0] for p in PILLARS
                  if p["key"] == "mind_control_history")
        assert kw.lower() in pkg["title"].lower(), pkg["title"]
        assert pkg["title"].count("|") <= 0  # pipe-stuffing wapas nahi
