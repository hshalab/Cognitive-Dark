"""Tests for the ML learning engine — bandit, attribution, guards, health."""
from pathlib import Path

import pytest

from ml_engine import LearningSystem, current_day_part, text_sha, token_overlap


@pytest.fixture()
def ml(tmp_path: Path) -> LearningSystem:
    return LearningSystem(store_path=tmp_path / "store.json")


def test_new_store_has_schema(ml: LearningSystem):
    for key in ("arms", "videos", "attribution", "post_log", "health", "model_version"):
        assert key in ml.data


def test_choose_strategy_returns_arm(ml: LearningSystem):
    s = ml.choose_strategy()
    assert s["pillar"] and s["hook_style"] and s["arm_key"]
    assert s["day_part"] == current_day_part()


def test_reward_and_penalty_land_on_exact_arm(ml: LearningSystem):
    s = ml.choose_strategy()
    arm_key = s["arm_key"]
    ml.apply_reward(arm_key, "test_reward", 2.0)
    ml.apply_penalty(arm_key, "test_penalty", 1.0)
    arm = ml.data["arms"][arm_key]
    # apply_reward/apply_penalty each count as evidence; choose_strategy's
    # plays counter tracks selections separately from reward samples.
    assert arm["n"] == 2
    assert arm["plays"] == 1
    assert arm["rewards"] == pytest.approx(1.0)  # +2 -1


def test_persistence_roundtrip(ml: LearningSystem, tmp_path: Path):
    s = ml.choose_strategy()
    ml.apply_reward(s["arm_key"], "r", 1.5)
    # Reload from disk
    fresh = LearningSystem(store_path=tmp_path / "store.json")
    assert s["arm_key"] in fresh.data["arms"]
    assert fresh.data["arms"][s["arm_key"]]["rewards"] == pytest.approx(1.5)


def test_dedup_blocks_exact_duplicate(ml: LearningSystem):
    text = "This is unique video text about psychology"
    hook = "Stop doing this"
    ml.register_video({"text": text, "hook": hook, "text_sha": text_sha(f"{hook} | {text}")})
    verdict = ml.dedup_guard(text, hook)
    assert verdict["allowed"] is False


def test_dedup_allows_novel(ml: LearningSystem):
    ml.register_video({"text": "old content A", "hook": "old hook",
                       "text_sha": text_sha("old hook | old content A")})
    assert ml.dedup_guard("completely different narration", "new hook")["allowed"] is True


def test_can_post_enforces_daily_cap(ml: LearningSystem):
    for _ in range(3):
        assert ml.can_post("youtube", max_daily=3, min_gap_hours=0)[0] is True
        ml.record_post("youtube")
    allowed, reason = ml.can_post("youtube", max_daily=3, min_gap_hours=0)
    assert allowed is False
    assert "daily cap" in reason


def test_record_post_prunes_old_dates(ml: LearningSystem):
    # Inject an old date
    ml.data["post_log"]["2000-01-01"] = {"youtube": {"count": 5, "last_ts": "2000-01-01T00:00:00+00:00"}}
    ml.save()
    ml.record_post("youtube")
    assert "2000-01-01" not in ml.data["post_log"]


def test_platform_quarantine_and_recovery(ml: LearningSystem):
    for _ in range(3):
        ml.report_failure("youtube", "boom")
    assert ml.platform_healthy("youtube") is False
    ml.report_success("youtube")
    assert ml.platform_healthy("youtube") is True


def test_video_attribution_credits_arm(ml: LearningSystem):
    s = ml.choose_strategy()
    arm = s["arm_key"]
    ml.record_video_id("youtube", "abc123", arm, "Test Title")
    assert "abc123" in ml.data["attribution"]
    assert "abc123" in ml.pending_video_ids("youtube")
    reward = ml.credit_video("abc123", {"views": 5000, "likes": 200,
                                        "comments": 30, "retention": 0.6})
    assert reward > 0
    # After crediting, it's no longer pending
    assert "abc123" not in ml.pending_video_ids("youtube")


def test_sanitized_reason_hides_tokens():
    raw = "failed with access_token=EAABCabc123secretXYZ&foo=bar ghp_xxxxxxxxxxxxxxxxxxxx"
    clean = LearningSystem._sanitize_reason(raw)
    assert "EAABCabc" not in clean
    assert "ghp_" not in clean
    assert "***" in clean


def test_token_overlap():
    assert token_overlap("hello world", "hello world") == 1.0
    assert token_overlap("a b c", "d e f") == 0.0
    assert 0 < token_overlap("a b c", "b c d") < 1
