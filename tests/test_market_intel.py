"""Tests for market intelligence — competitor analysis & priors."""
from market_intel import (
    analyze,
    classify_hook,
    classify_pillar,
    load_competitor_videos,
    market_report,
    priors_for_bandit,
    save_competitor_videos,
)

SAMPLE = [
    {"video_id": "a", "title": "5 Signs Someone Is MANIPULATING You", "channel": "X",
     "view_count": 500000, "like_count": 20000, "comment_count": 1500,
     "duration_seconds": 42, "published_at": "2026-06-01T12:00:00Z", "query": "manipulation"},
    {"video_id": "b", "title": "Why You Feel Like You're Going Crazy (Gaslighting)",
     "channel": "Y", "view_count": 300000, "like_count": 10000, "comment_count": 800,
     "duration_seconds": 38, "published_at": "2026-06-02T18:00:00Z", "query": "gaslighting"},
    {"video_id": "c", "title": "The Scam That Stole $2M (Romance Fraud Explained)",
     "channel": "Z", "view_count": 1200000, "like_count": 50000, "comment_count": 3000,
     "duration_seconds": 55, "published_at": "2026-06-03T09:00:00Z", "query": "scam"},
    {"video_id": "d", "title": "Marcus Aurelius - How To Stay Calm", "channel": "W",
     "view_count": 8000, "like_count": 100, "comment_count": 10,
     "duration_seconds": 58, "published_at": "2026-06-04T20:00:00Z", "query": "stoic"},
]


def test_classify_hook():
    assert classify_hook("5 Signs Someone Is Manipulating You") == "red_flag"
    assert classify_hook("Why do people fall for cults?") == "question_hook"
    assert classify_hook("If they say this, run") == "warning"


def test_classify_pillar():
    assert classify_pillar("gaslighting signs in relationships") == "coercive_control"
    assert classify_pillar("romance scam stole millions") == "con_artists"
    assert classify_pillar("inside the cult brainwashing") == "cults"


def test_analyze_empty_returns_curated():
    a = analyze([])
    assert a["source"] == "curated_patterns"
    assert len(a["pair_means"]) > 0
    assert a["duration_best_s"] == 42


def test_analyze_sample_ranks_high_performers():
    a = analyze(SAMPLE)
    assert a["source"] == "youtube_public_data"
    assert a["video_count"] == 4
    top = a["pair_means"][0]
    # The scam video (1.2M views) should rank high
    assert top["mean"] > 0.5


def test_priors_for_bandit_shape():
    a = analyze(SAMPLE)
    priors = priors_for_bandit(a)
    assert priors
    for (_pillar, _hook), (mean, n) in priors.items():
        assert 0.1 <= mean <= 2.0
        assert n >= 1


def test_market_report_runs():
    r = market_report(analyze(SAMPLE))
    assert "MARKET INTELLIGENCE" in r
    assert "Top" in r


def test_save_and_load(tmp_path, monkeypatch):
    import market_intel
    monkeypatch.setattr(market_intel, "COMPETITOR_FILE", tmp_path / "c.json")
    save_competitor_videos(SAMPLE)
    loaded = load_competitor_videos()
    assert len(loaded) == 4
