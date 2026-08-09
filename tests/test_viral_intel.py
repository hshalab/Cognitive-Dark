"""Tests for Viral Intelligence (V2.9)."""
from viral_intel import analyze_titles, pick_title_variant, score_hook, score_title, suggestion_card, virality_index


def test_score_title_detects_stop_command():
    s = score_title("Stop Letting Them Do This To You")
    assert s["score"] > 0.8
    assert "stop_command" in s["formulas"] or "curiosity_gap" in s["formulas"] or \
        "warning" in s["formulas"]


def test_score_title_weak_without_pattern():
    s = score_title("A Video About Things")
    assert s["score"] < 0.8


def test_score_hook_length_rule():
    good = score_hook("Stop letting them control you.")
    bad = score_hook("So basically maybe sometimes you could perhaps think about "
                     "some things that might be interesting to consider")
    assert good["score"] > bad["score"]
    assert any("words" in i for i in bad["issues"])


def test_analyze_titles_empty_safe():
    a = analyze_titles([])
    assert a["n"] == 0
    assert a["avg_score"] == 0.0


def test_analyze_titles_ranks_formulas():
    titles = [
        "Stop Doing This One Thing",
        "Never Trust These 3 Signs",
        "Why Smart People Fall For This",
        "The Secret Nobody Tells You",
        "Warning: 5 Red Flags Of A Cult",
    ]
    a = analyze_titles(titles)
    assert a["n"] == 5
    assert a["top_formulas"], "expected at least one top formula"


def test_pick_title_variant_chooses_strongest():
    weak = "A Video About Some Things"
    strong = "Stop Letting Them Control You: The Truth"
    picked = pick_title_variant("hook", [weak, strong])
    assert picked == strong


def test_virality_index_returns_grade():
    idx = virality_index({})
    assert "grade" in idx
    assert "recommendations" in idx
    assert "index" in idx


def test_suggestion_card_has_formulas():
    card = suggestion_card({})
    assert card["title_formulas_to_use"]
    assert "hook_rule" in card
