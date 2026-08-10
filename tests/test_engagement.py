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
