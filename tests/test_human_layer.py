"""Tests for the Human Layer (V3.0) — natural variation, intuition, brief."""

from human_layer import creator_intuition, generate_daily_brief, jitter_minutes, jitter_publish_at, maybe_emoji, vary_cta, vary_description, vary_hashtags, vary_title


def test_jitter_bounded():
    for _ in range(50):
        assert 0 <= jitter_minutes(8) <= 8


def test_jitter_publish_at_aware():
    from datetime import datetime, timezone
    dt = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
    out = jitter_publish_at(dt, 8)
    assert out.tzinfo is not None
    assert 0 <= (out - dt).total_seconds() <= 8 * 60


def test_vary_title_length():
    t = vary_title("Stop Letting Them Control You", seed=1)
    assert len(t) <= 100


def test_vary_description_keeps_content():
    d = "Line one\n\nRest of content here"
    out = vary_description(d, hook="Hook text", seed=2)
    assert "Rest of content" in out


def test_vary_cta_contains_follow():
    d = "Some description. Follow Coercion Files for more."
    out = vary_cta(d, seed=3)
    assert "Follow" in out


def test_vary_hashtags_bounded():
    tags = [f"tag{i}" for i in range(20)]
    for _ in range(20):
        out = vary_hashtags(tags, "instagram", seed=4)
        assert 1 <= len(out) <= 20


def test_emoji_never_crashes():
    assert isinstance(maybe_emoji(seed=5), str)


def test_creator_intuition_hot():
    ml = {"arms": {"cults::warning::morning": {"n": 5, "rewards": 7.5}},
          "reward_log": [{"reward": 2.0}, {"reward": 2.0}, {"reward": 2.0}]}
    notes = creator_intuition(ml)
    assert notes, "expected intuition notes"


def test_daily_brief_structure():
    brief = generate_daily_brief({}, {"history": []}, {})
    assert "Daily Brief" in brief
    assert "plan" in brief.lower() or "Plan" in brief


def test_reply_queue_roundtrip(tmp_path, monkeypatch):
    import human_layer
    monkeypatch.setattr(human_layer, "REPLY_QUEUE", tmp_path / "q.json")
    human_layer.save_reply_queue([{"id": "c1", "text": "hi"}])
    q = human_layer.load_reply_queue()
    assert q[0]["id"] == "c1"
