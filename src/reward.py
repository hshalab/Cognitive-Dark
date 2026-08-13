#!/usr/bin/env python3
"""
Coercion Files — Multi-signal High-Quality Reward Function.

Calibrated strictly for >70% Retention & High-CTR Quality Standards:
  • Retention weight: 35% (Target: 70%+ Average View Duration)
  • Completion rate: 16% (Shorts/Reels finish rate)
  • Engagement & Shares: 20% (FB shares & IG saves weighted highest)
  • Click-Through-Rate (CTR): 10% (10%+ CTR target)
  • Views scale: 12%
  • Quality / Voice / Production: 7%
"""

from __future__ import annotations

import math
from dataclasses import dataclass

WEIGHTS = {
    "retention": 0.35,
    "completion": 0.16,
    "engagement": 0.20,
    "views": 0.12,
    "ctr": 0.10,
    "quality": 0.07,
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
    # V3.6: retention_estimated=True matlab retention GUESS hai (like-ratio
    # se banaya hua), measurement nahi. Estimated retention ko reward mein
    # half weight milta hai, viral bonus NAHI milta, aur quality gate usay
    # "unknown" batata hai — fabricated data bandit ko dhoka nahi de sakta.
    retention_estimated: bool = False
    # V3.4: None = "koi evidence nahi" (neutral 0.5). Pehle default 1.0 tha —
    # matlab har video ko FREE mein perfect TTS score milta tha, bina kisi
    # measurement ke. Ye 7% weight hamesha 100% score karta tha = jhoot.
    voice_rating: float | None = None

    def effective_voice_rating(self) -> float:
        """0..1 — None (koi data nahi) neutral 0.5 deta hai, 1.0 nahi."""
        if self.voice_rating is None:
            return 0.5
        return max(0.0, min(1.0, self.voice_rating))

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
        r = self.effective_retention()
        return max(0.0, min(1.0, (r - 0.4) / 0.6)) if r > 0.4 else 0.0


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def compute_reward(m: VideoMetrics) -> tuple[float, dict]:
    """Return (reward 0..~3, breakdown dict for logging)."""
    retention = m.effective_retention()
    completion = m.effective_completion()

    # Engagement rate: shares & saves weighted heavily for viral distribution
    interactions = m.likes + 2 * m.comments + 3 * m.shares + 2 * m.saves + 5 * m.subs_gained
    eng_rate = interactions / max(1.0, m.views)
    eng_score = _clamp01(eng_rate / 0.06)

    # Views via log scale
    view_score = _clamp01(math.log10(max(1.0, m.views)) / 6.0)

    # CTR score (Target 8-12% CTR for viral tier)
    ctr_score = _clamp01((m.ctr or 0.0) / 0.10)
    quality_score = _clamp01(m.effective_voice_rating())

    # Retention score: 60-70%+ is the gold standard benchmark.
    # V3.6: agar retention GUESS hai (retention_estimated), to contribution
    # aadhi karo aur 0.5 par cap karo — estimate kabhi "gold retention" ka
    # credit nahi le sakta. Measured retention ka pura weight rehta hai.
    retention_score = _clamp01(retention / 0.60)
    if m.retention_estimated:
        retention_score = min(0.5, retention_score * 0.5)

    raw = (WEIGHTS["retention"] * retention_score +
           WEIGHTS["completion"] * completion +
           WEIGHTS["engagement"] * eng_score +
           WEIGHTS["views"] * view_score +
           WEIGHTS["ctr"] * ctr_score +
           WEIGHTS["quality"] * quality_score)

    reward = raw * 3.0

    # Viral bonus for breakout retention — sirf MEASURED retention ke liye.
    # V3.6: estimate ke liye viral bonus band (guess "viral" nahi bana sakta).
    if not m.retention_estimated:
        if retention >= 0.55 and m.views >= 1000:
            reward += 1.0
        if retention >= 0.70:
            reward += 0.5  # Extra bonus for hitting elite 70%+ retention

    reward = round(max(0.0, min(5.0, reward)), 3)

    # V3.4 HONEST GATE: pehle `retention >= 0.70 or retention == 0.0` tha —
    # matlab jab koi retention DATA hi nahi tha (0.0) to gate "PASS" keh deta
    # tha. No-data video ko "quality passed" batana system ka khud ko dhoka
    # dena tha. Ab data na ho to gate pass NAHI hota — explicitly UNKNOWN.
    # V3.6: ESTIMATED retention bhi "measured" nahi maani jaati —
    # quality gate usay bhi UNKNOWN kehta hai.
    has_retention_data = (m.retention is not None
                          or (m.avg_view_seconds or 0) > 0
                          or (m.watch_time_seconds or 0) > 0)
    retention_measured = has_retention_data and not m.retention_estimated
    has_views = m.views > 0
    data_complete = has_views and retention_measured
    breakdown = {
        "retention": round(retention, 3),
        "retention_measured": bool(retention_measured),
        "retention_estimated": bool(m.retention_estimated),
        "completion": round(completion, 3),
        "engagement_rate": round(eng_rate, 4),
        "view_score": round(view_score, 3),
        "ctr": round(m.ctr or 0.0, 4),
        "voice_rating": round(m.effective_voice_rating(), 2),
        "reward": reward,
        "quality_gate_passed": bool(retention_measured and retention >= 0.70),
        "quality_gate_status": ("passed" if (retention_measured and retention >= 0.70)
                                else ("unknown" if not data_complete else "failed")),
        "data_complete": bool(data_complete),
    }
    return reward, breakdown


def reward_from_dict(metrics: dict) -> tuple[float, dict]:
    return compute_reward(VideoMetrics(**{
        k: metrics[k] for k in metrics if k in VideoMetrics.__dataclass_fields__
    }))
