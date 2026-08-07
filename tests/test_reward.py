"""Tests for the multi-signal reward function."""
from reward import VideoMetrics, compute_reward, reward_from_dict


def test_zero_metrics_low_reward():
    m = VideoMetrics(views=0)
    r, b = compute_reward(m)
    assert 0 <= r <= 5
    assert b["retention"] == 0.0


def test_high_retention_dominates():
    # A video with 500 views but 70% retention should beat one with 5000
    # views and 10% retention (retention is the #1 signal in 2026).
    strong = VideoMetrics(views=500, likes=20, comments=5,
                          duration_seconds=50, avg_view_seconds=35)
    weak = VideoMetrics(views=5000, likes=10, comments=2,
                        duration_seconds=50, avg_view_seconds=5)
    r1, _ = compute_reward(strong)
    r2, _ = compute_reward(weak)
    assert r1 > r2


def test_engagement_rate_counts():
    base = dict(views=1000, duration_seconds=50, avg_view_seconds=30)
    low_eng = VideoMetrics(**base, likes=1, comments=0, shares=0)
    hi_eng = VideoMetrics(**base, likes=50, comments=20, shares=10)
    assert compute_reward(hi_eng)[0] > compute_reward(low_eng)[0]


def test_viral_bonus_requires_views_and_retention():
    viral = VideoMetrics(views=2000, retention=0.6, duration_seconds=40)
    _, b = compute_reward(viral)
    assert b["reward"] >= 2.0  # strong base + viral bonus applied


def test_voice_quality_matters():
    base = dict(views=1000, retention=0.5, duration_seconds=40)
    good = VideoMetrics(**base, voice_rating=1.0)
    bad = VideoMetrics(**base, voice_rating=0.2)
    assert compute_reward(good)[0] > compute_reward(bad)[0]


def test_reward_from_dict_accepts_subset():
    r, b = reward_from_dict({"views": 100, "likes": 5, "retention": 0.5})
    assert r > 0
    assert "reward" in b


def test_retention_from_avg_view_seconds():
    m = VideoMetrics(duration_seconds=50, avg_view_seconds=30)
    assert abs(m.effective_retention() - 0.6) < 0.01


def test_reward_capped_at_5():
    m = VideoMetrics(views=10_000_000, likes=1_000_000, comments=100_000,
                     shares=50_000, retention=1.0, ctr=0.2, duration_seconds=40)
    r, _ = compute_reward(m)
    assert r <= 5.0
