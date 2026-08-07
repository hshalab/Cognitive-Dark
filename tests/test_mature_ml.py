"""Tests for mature ML features: Thompson policy, per-platform, diagnostics."""
from pathlib import Path

import pytest

from ml_diagnostics import maturity, report, report_json
from ml_engine import LearningSystem


@pytest.fixture()
def ml(tmp_path: Path) -> LearningSystem:
    return LearningSystem(store_path=tmp_path / "store.json")


def test_choose_strategy_returns_thompson_metadata(ml: LearningSystem):
    s = ml.choose_strategy()
    assert s["policy"] == "thompson"
    assert "posterior_mean" in s
    assert "posterior_std" in s
    assert len(s["ci_95"]) == 2


def test_per_platform_records_separately(ml: LearningSystem):
    s = ml.choose_strategy(platform="youtube")
    ml.record_outcome(s["arm_key"], 3.0, platform="youtube")
    ml.record_outcome(s["arm_key"], 0.5, platform="facebook")
    yt = ml.data["platform_arms"]["youtube"][s["arm_key"]]
    fb = ml.data["platform_arms"]["facebook"][s["arm_key"]]
    assert yt["n"] == 1
    assert fb["n"] == 1
    assert yt["rewards"] > fb["rewards"]


def test_per_platform_affects_selection(ml: LearningSystem):
    # Train one arm high on youtube but low on facebook
    for _ in range(15):
        ml.apply_reward("coercive_control::warning::morning", "win", 3.0, platform="youtube")
        ml.apply_penalty("coercive_control::warning::morning", "lose", 2.0, platform="facebook")
    s = ml.choose_strategy(platform="youtube")
    assert "arm_key" in s


def test_maturity_exploring_without_data(ml: LearningSystem):
    m = maturity(ml)
    assert m["maturity_stage"] == "EXPLORING"
    assert report(ml)
    assert report_json(ml)["maturity"]


def test_maturity_progresses_with_observations(ml: LearningSystem):
    for _ in range(40):
        s = ml.choose_strategy()
        ml.record_outcome(s["arm_key"], 2.5)
    m = maturity(ml)
    assert m["maturity_stage"] in ("LEARNING", "CONVERGING", "MATURE")
    assert m["total_observations"] >= 40


def test_credit_video_uses_multi_signal_reward(ml: LearningSystem):
    s = ml.choose_strategy()
    ml.record_video_id("youtube", "abc123", s["arm_key"], "T")
    reward = ml.credit_video("abc123", {
        "views": 5000, "likes": 200, "comments": 30,
        "retention": 0.65, "duration_seconds": 40,
    })
    assert reward > 1.0
    attr = ml.data["attribution"]["abc123"]
    assert attr["credited"] is True
    assert "breakdown" in attr
