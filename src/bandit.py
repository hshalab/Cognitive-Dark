#!/usr/bin/env python3
"""
Coercion Files — Mature bandit core.

Yeh module LearningSystem ke liye do production-grade policies deta hai:

  1. Thompson sampling (default) — har arm ka Bayesian posterior
     N(mu, sigma^2) bana kar us se ek sample leta hai. Jis arm ka sample
     buland usay choose karta hai. High-uncertainty (kam-seen) arms naturally
     explore hoti hain; proven arms exploit hoti hain.

  2. UCB1 — classical upper-confidence bound (purana behavior, fallback).

Har arm ka prior market_intel / seed_priors se aata hai. Real observations aate
hi posterior update hota hai aur priors dheere dheere patle padte jate hain.

Koi fake "500 channels" data nahi — priors sirf documented public patterns hain,
aur un ki n (pseudo-observations) kam rakhi gayi hai taake aapka asli data jaldi
override kar de.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

# Reward scale used across the system (see reward.py: 0..5).
REWARD_MIN = 0.0
REWARD_MAX = 5.0
DEFAULT_PRIOR_MEAN = 0.5      # neutral prior on 0..5 scale
DEFAULT_PRIOR_NOISE = 0.5     # prior variance for an arm with no data


@dataclass
class ArmObservations:
    """Running raw observations for one arm."""
    n: int = 0
    total: float = 0.0
    total_sq: float = 0.0

    def add(self, reward: float) -> None:
        self.n += 1
        self.total += reward
        self.total_sq += reward * reward

    def merge(self, other: ArmObservations) -> None:
        self.n += other.n
        self.total += other.total
        self.total_sq += other.total_sq

    @property
    def mean(self) -> float:
        return self.total / self.n if self.n else 0.0

    @property
    def sample_var(self) -> float:
        if self.n < 2:
            return 1.0
        var = (self.total_sq - (self.total * self.total) / self.n) / (self.n - 1)
        return max(0.0, var)


class ArmPosterior:
    """Bayesian posterior for one arm with a Normal prior.

    prior_mean/prior_n express the market/seeded belief as `prior_n`
    pseudo-observations averaging `prior_mean`. Observations update the
    posterior analytically (conjugate Normal with known observation variance).
    """

    def __init__(self, prior_mean: float = DEFAULT_PRIOR_MEAN,
                 prior_n: int = 3, obs: ArmObservations | None = None,
                 prior_noise: float = DEFAULT_PRIOR_NOISE):
        self.prior_mean = float(prior_mean)
        self.prior_n = max(0, int(prior_n))
        self.prior_noise = float(prior_noise)
        self.obs = obs or ArmObservations()

    # ── updates ──
    def add(self, reward: float) -> None:
        self.obs.add(max(REWARD_MIN, min(REWARD_MAX, float(reward))))

    # ── derived stats ──
    @property
    def n(self) -> int:
        return self.obs.n

    @property
    def effective_n(self) -> float:
        return float(self.prior_n + self.obs.n)

    @property
    def mean(self) -> float:
        if self.effective_n <= 0:
            return self.prior_mean
        return (self.prior_n * self.prior_mean + self.obs.total) / self.effective_n

    @property
    def variance(self) -> float:
        """Posterior variance (uncertainty). Shrinks with more observations.

        For a genuinely unseen arm (no prior pseudo-count and no observations)
        we return a large base uncertainty so Thompson sampling still explores
        it, rather than collapsing to the prior mean deterministically.
        """
        if self.effective_n <= 0:
            return (self.prior_noise * 2.0) ** 2
        obs_var = self.obs.sample_var if self.obs.n else self.prior_noise ** 2
        return obs_var / self.effective_n + (self.prior_noise / self.effective_n) ** 2

    @property
    def std(self) -> float:
        return math.sqrt(max(1e-6, self.variance))

    # ── policies ──
    def thompson_sample(self) -> float:
        """Draw one sample from the posterior — the core of Thompson sampling."""
        return random.gauss(self.mean, self.std)

    def ucb(self, total_arm_plays: int, c: float = 2.0) -> float:
        bonus = c * math.sqrt(math.log(max(2, total_arm_plays)) / max(1.0, self.effective_n))
        return self.mean + bonus

    def confidence_interval(self, z: float = 1.96) -> tuple[float, float]:
        half = z * self.std
        return self.mean - half, self.mean + half


def posterior_from_arm(arm: dict) -> ArmPosterior:
    """Build an ArmPosterior from the ML engine's stored arm dict.

    Arm dict shape:
      {n, rewards (=sum), sum_sq, prior_mean?, prior_n?, seeded?}
    """
    obs = ArmObservations(
        n=int(arm.get("n", 0)),
        total=float(arm.get("rewards", 0.0)),
        total_sq=float(arm.get("sum_sq", 0.0)),
    )
    return ArmPosterior(
        prior_mean=float(arm.get("prior_mean", DEFAULT_PRIOR_MEAN)),
        prior_n=int(arm.get("prior_n", 0)),
        obs=obs,
    )


def write_posterior_to_arm(arm: dict, post: ArmPosterior) -> None:
    """Persist prior metadata back onto an arm dict (n/rewards/sum_sq already set)."""
    arm["prior_mean"] = round(post.prior_mean, 4)
    arm["prior_n"] = post.prior_n


def score_arms(candidates: list[tuple[float, str, dict, str, str, str]],
               policy: str = "thompson", total_plays: int = 0,
               c: float = 2.0) -> list:
    """Score candidate arms in place with the selected policy.

    Each candidate tuple: (score, key, arm, pillar, hook_style, day_part).
    Returns the same list (caller then applies recency penalty and picks max).
    """
    out = []
    for _score, key, arm, pillar, style, day_part in candidates:
        post = posterior_from_arm(arm)
        s = post.ucb(total_plays, c=c) if policy == "ucb" else post.thompson_sample()
        out.append((s, key, arm, pillar, style, day_part))
    return out


def should_force_exploration(arm: dict, min_obs: int = 1) -> bool:
    """Cold-arm guarantee: arms with no real observations get a strong boost."""
    return int(arm.get("n", 0)) < max(1, min_obs)


# ─────────────────────────────────────────────────────────────
# Reward normalization — keeps priors and real rewards comparable
# across platforms/view scales.
# ─────────────────────────────────────────────────────────────
class RunningStats:
    """Welford online mean/std, used for reward standardization."""

    def __init__(self):
        self.n = 0
        self.mean = 0.0
        self._m2 = 0.0

    def add(self, x: float) -> None:
        self.n += 1
        delta = x - self.mean
        self.mean += delta / self.n
        self._m2 += delta * (x - self.mean)

    @property
    def variance(self) -> float:
        return self._m2 / (self.n - 1) if self.n > 1 else 1.0

    @property
    def std(self) -> float:
        return math.sqrt(max(1e-6, self.variance))

    def standardize(self, x: float) -> float:
        """Z-score, then sigmoid → (0,1). Stable even with few samples."""
        if self.n < 5:
            # Not enough history: deterministic linear map from [0,5] → [0,1]
            return max(0.01, min(0.99, x / REWARD_MAX))
        z = (x - self.mean) / max(0.5, self.std)
        return max(0.01, min(0.99, 1.0 / (1.0 + math.exp(-z))))
