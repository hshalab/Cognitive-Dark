"""Tests for the mature Bayesian/Thompson bandit core."""
import random

from bandit import ArmObservations, ArmPosterior, RunningStats, score_arms


def test_arm_observations_running():
    o = ArmObservations()
    for x in [1.0, 2.0, 3.0]:
        o.add(x)
    assert o.n == 3
    assert abs(o.mean - 2.0) < 1e-9
    assert o.sample_var > 0


def test_posterior_shrinks_to_data():
    random.seed(1)
    p = ArmPosterior(prior_mean=2.0, prior_n=2)
    # many observations near 4.0 should pull posterior up and reduce std
    for _ in range(200):
        p.add(4.0)
    assert p.mean > 3.5
    assert p.std < 0.2


def test_posterior_uses_prior_when_no_data():
    p = ArmPosterior(prior_mean=1.5, prior_n=4)
    assert abs(p.mean - 1.5) < 1e-9
    assert p.std > 0


def test_thompson_sample_uses_uncertainty():
    random.seed(2)
    unknown = ArmPosterior(prior_mean=1.0, prior_n=0)   # high variance
    known = ArmPosterior(prior_mean=3.0, prior_n=2)
    known.obs = ArmObservations(n=100, total=300.0, total_sq=900.0)
    # High-mean low-uncertainty should mostly win but unknown occasionally
    wins_unknown = sum(1 for _ in range(500) if unknown.thompson_sample() > known.thompson_sample())
    assert 0 < wins_unknown < 400  # exploration exists but not dominant


def test_ucb_bonus_for_underobserved():
    known = ArmPosterior(prior_mean=2.0, prior_n=2)
    known.obs = ArmObservations(n=100, total=200.0, total_sq=400.0)
    unknown = ArmPosterior(prior_mean=2.0, prior_n=0)
    assert unknown.ucb(1000) > known.ucb(1000)


def test_confidence_interval_widens_with_uncertainty():
    p_certain = ArmPosterior(prior_mean=2.0, prior_n=2)
    p_certain.obs = ArmObservations(n=100, total=200.0, total_sq=400.0)
    p_uncertain = ArmPosterior(prior_mean=2.0, prior_n=0)
    lo1, hi1 = p_certain.confidence_interval()
    lo2, hi2 = p_uncertain.confidence_interval()
    assert (hi1 - lo1) < (hi2 - lo2)


def test_score_arms_returns_same_count():
    cands = [(0.0, f"k{i}", {"n": i, "rewards": float(i), "sum_sq": float(i),
                             "plays": 1}, "p", "h", "morning") for i in range(5)]
    out = score_arms(cands, policy="thompson")
    assert len(out) == len(cands)
    out2 = score_arms(cands, policy="ucb", total_plays=50)
    assert len(out2) == len(cands)


def test_running_stats_standardize_bounded():
    rs = RunningStats()
    for x in [1.0, 2.0, 2.0, 3.0]:
        rs.add(x)
    for x in [0.0, 2.5, 5.0]:
        z = rs.standardize(x)
        assert 0.0 < z < 1.0
