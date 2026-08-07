"""Tests for warm-start priors (seed_priors) — must never overwrite real data."""
from pathlib import Path

import pytest

from ml_engine import LearningSystem
from seed_priors import SEED_PRIORS


@pytest.fixture()
def ml(tmp_path: Path) -> LearningSystem:
    return LearningSystem(store_path=tmp_path / "store.json")


def test_seed_creates_expected_arms(ml: LearningSystem):
    result = ml.apply_seed_priors()
    # 8 pillars x 8 hooks x 3 day_parts = 192
    assert result["arms_seeded"] == 8 * 8 * 3
    assert len(ml.data["arms"]) == 8 * 8 * 3
    assert ml.data["prior_version"]


def test_seed_sets_mean_consistent(ml: LearningSystem):
    ml.apply_seed_priors()
    arm = ml.data["arms"]["coercive_control::warning::morning"]
    mean, n = SEED_PRIORS[("coercive_control", "warning")]
    assert arm["n"] == n
    assert arm["rewards"] == pytest.approx(mean * n)
    assert arm["seeded"] is True


def test_seed_is_idempotent(ml: LearningSystem):
    r1 = ml.apply_seed_priors()
    assert r1["arms_seeded"] > 0
    # Second run: every arm's n already equals its prior_n, so nothing new seeded.
    r2 = ml.apply_seed_priors()
    assert r2["arms_seeded"] == 0


def test_seed_never_overwrites_real_evidence(ml: LearningSystem):
    # Pre-populate an arm with real outcome
    s = ml.choose_strategy()
    ml.record_outcome(s["arm_key"], 3.0)
    before = ml.data["arms"][s["arm_key"]]["rewards"]
    ml.apply_seed_priors()
    after = ml.data["arms"][s["arm_key"]]["rewards"]
    assert before == after  # real evidence untouched
    assert ml.data["arms"][s["arm_key"]].get("seeded") is not True


def test_high_prior_arms_rank_first(ml: LearningSystem):
    # UCB adds a big explore bonus to all seeded arms (equal n), so on a
    # fresh seed the deterministic ranking is by prior mean. Verify the
    # top formulas come from our highest-prior (pillar, hook) pairs.
    ml.apply_seed_priors()
    top = ml.best_formulas(5)
    top_pairs = {(t["pillar"], t["hook_style"]) for t in top}
    expected = {("coercive_control", "warning"), ("con_artists", "warning"),
                ("coercive_control", "red_flag"), ("con_artists", "red_flag")}
    # At least 2 of the top 5 should be high-prior winners.
    assert len(top_pairs & expected) >= 2
    assert top[0]["pillar"] in ("coercive_control", "con_artists")
