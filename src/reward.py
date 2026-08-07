#!/usr/bin/env python3
"""
Cognitive Dark — multi-signal reward function.

Sirf views dekh ke bandit ko reward dena 2026 mein galat hai — algorithm
ab retention, completion aur engagement ko zyada weight deta hai. Yeh module
raw metrics ko ek hi 0..~3 score mein map karta hai, jis tarah
ml_engine.record_outcome expect karta hai.

Inputs (sab optional, jitna mile utna behtar):
  views, likes, comments, shares, saves, watch_time_seconds, duration_seconds,
  retention (0..1 average viewed), avg_view_seconds, ctr (0..1), subs_gained,
  voice_rating (0..1 TTS quality, optional), completion (0..1)
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Weights (sum = 1.0). Retention/completion ko sab se zyada wazan kyun ke
# Shorts/Reels feed mein 2026 ka sab se bara ranking signal yahi hai.
WEIGHTS = {
    "retention": 0.34,
    "completion": 0.16,
    "engagement": 0.22,
    "views": 0.14,
    "ctr": 0.09,
    "quality": 0.05,
}


@dataclass
class VideoMetrics:
    views: float = 0
    likes: float = 0
    comments: float = 0
    shares: float = 0
    saves: float = 0
    subs_gained: float = 0
    watch_time_seconds: float = 0
    duration_seconds: float = 0
    retention: float | None = None
    avg_view_seconds: float | None = None
    completion: float | None = None
    ctr: float | None = None
    voice_rating: float = 1.0  # 0..1, TTS quality / no static / correct speed

    def effective_retention(self) -> float:
        """Return 0..1 retention estimate from whichever data we have."""
        if self.retention is not None:
            return max(0.0, min(1.0, self.retention))
        if self.avg_view_seconds and self.duration_seconds:
            return max(0.0, min(1.0, self.avg_view_seconds / self.duration_seconds))
        if self.watch_time_seconds and self.views and self.duration_seconds:
            return max(0.0, min(1.0,
                               (self.watch_time_seconds / max(1, self.views)) /
                               self.duration_seconds))
        return 0.0

    def effective_completion(self) -> float:
        if self.completion is not None:
            return max(0.0, min(1.0, self.completion))
        # For Shorts, completion ≈ viewers reaching the end. We approximate from
        # retention shape but without per-second data use half the retention
        # above 0.5 as a conservative completion proxy.
        r = self.effective_retention()
        return max(0.0, min(1.0, (r - 0.4) / 0.6)) if r > 0.4 else 0.0


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def compute_reward(m: VideoMetrics) -> tuple[float, dict]:
    """Return (reward 0..~3, breakdown dict for logging)."""
    retention = m.effective_retention()
    completion = m.effective_completion()

    # Engagement rate (interactions per view). 6%+ is excellent for Shorts.
    interactions = m.likes + 2 * m.comments + 3 * m.shares + 2 * m.saves + 5 * m.subs_gained
    eng_rate = interactions / max(1.0, m.views)
    eng_score = _clamp01(eng_rate / 0.06)

    # Views via log scale: 0 views=0, 100≈0.33, 10k≈0.67, 1M≈1.0
    view_score = _clamp01(math.log10(max(1.0, m.views)) / 6.0)

    ctr_score = _clamp01((m.ctr or 0.0) / 0.10)            # 10% CTR → full
    quality_score = _clamp01(m.voice_rating)

    raw = (WEIGHTS["retention"] * _clamp01(retention / 0.60) +    # 60%+ ret = full
           WEIGHTS["completion"] * completion +
           WEIGHTS["engagement"] * eng_score +
           WEIGHTS["views"] * view_score +
           WEIGHTS["ctr"] * ctr_score +
           WEIGHTS["quality"] * quality_score)

    # Viral bonus (as in ml_engine.LEARNING) for the rare breakout — lifts cap
    reward = raw * 3.0
    if retention >= 0.55 and m.views >= 1000:
        reward += 1.0
    reward = round(min(5.0, reward), 3)

    breakdown = {
        "retention": round(retention, 3),
        "completion": round(completion, 3),
        "engagement_rate": round(eng_rate, 4),
        "view_score": round(view_score, 3),
        "ctr": round(m.ctr or 0.0, 4),
        "voice_rating": round(m.voice_rating, 2),
        "reward": reward,
    }
    return reward, breakdown


def reward_from_dict(metrics: dict) -> tuple[float, dict]:
    return compute_reward(VideoMetrics(**{
        k: metrics[k] for k in metrics if k in VideoMetrics.__dataclass_fields__
    }))
