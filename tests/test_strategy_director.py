"""Tests for Strategy Director — auto-tuning of epsilon/speed/cadence/weights."""
from pathlib import Path

from ml_engine import LearningSystem
from strategy_director import StrategyDirector


def fresh_ml(tmp_path: Path) -> LearningSystem:
    return LearningSystem(store_path=tmp_path / "ml.json")


def test_init_defaults(tmp_path):
    d = StrategyDirector(ml=fresh_ml(tmp_path), state_path=tmp_path / "s.json")
    assert d.state.epsilon == 0.15
    assert 1.05 <= d.state.kokoro_speed <= 1.10


def test_low_reward_increases_epsilon(tmp_path):
    ml = fresh_ml(tmp_path)
    # Seed a run of poor rewards
    for _i in range(12):
        arm = ml.choose_strategy()["arm_key"]
        ml.record_outcome(arm, 0.2)
    d = StrategyDirector(ml=ml, state_path=tmp_path / "s.json")
    d.decide()
    assert d.state.epsilon > 0.15  # explore more when losing


def test_high_reward_decreases_epsilon(tmp_path):
    ml = fresh_ml(tmp_path)
    for _i in range(12):
        arm = ml.choose_strategy()["arm_key"]
        ml.record_outcome(arm, 1.8)
    d = StrategyDirector(ml=ml, state_path=tmp_path / "s.json")
    d.decide()
    assert d.state.epsilon < 0.15  # exploit more when winning


def test_pillar_weights_track_performance(tmp_path):
    ml = fresh_ml(tmp_path)
    # Reward one pillar's arms, penalize another's
    for _ in range(6):
        ml.apply_reward("coercive_control::warning::morning", "win", 2.0)
        ml.apply_penalty("stoic_defense::case_file::morning", "lose", 1.0)
    d = StrategyDirector(ml=ml, state_path=tmp_path / "s.json")
    d.decide()
    assert d.state.pillar_weights["coercive_control"] > 1.0
    assert d.state.pillar_weights["stoic_defense"] < 1.0


def test_apply_to_env_sets_kokoro_speed(tmp_path, monkeypatch):
    d = StrategyDirector(ml=fresh_ml(tmp_path), state_path=tmp_path / "s.json")
    d.state.kokoro_speed = 1.10
    d.apply_to_env()
    import os
    assert os.environ["KOKORO_SPEED"] == "1.1"


def test_state_persists(tmp_path):
    d1 = StrategyDirector(ml=fresh_ml(tmp_path), state_path=tmp_path / "s.json")
    d1.state.kokoro_speed = 1.12
    d1.save()
    d2 = StrategyDirector(state_path=tmp_path / "s.json")
    assert d2.state.kokoro_speed == 1.12
