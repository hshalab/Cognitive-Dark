#!/usr/bin/env python3
"""
Cognitive Dark - Strategy Director.

Rolling performance (last N videos) dekh khud ba khud in cheezon ko tune karta
hai taake owner ko manually settings na badalni parein:

  • epsilon (exploration rate) - agar rewards barh rahe to exploit zyada,
    warna explore zyada
  • voice speed - USA retention ke liye 1.05-1.12 ke darmyan re-tune
  • per-pillar preference - top pillars ko zyada weight, dead pillars ko kam
  • daily cadence cap - agar quality gir rahi hai to volume kam; agar har
    video achhi to cap barhao
  • minimum post gap - agar same-burst se reach gir rahi hai to gap barhao

Decisions data/strategy_state.json mein save hote hain, aur pipeline inhein
env/ML config override ki tarah istemal karta hai. Har adjustment chhota
(damping) hai taake ek kharab din poori strategy na bigaar de.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from config.settings import DATA_DIR

logger = logging.getLogger("director")

STATE_PATH = DATA_DIR / "strategy_state.json"


@dataclass
class StrategyState:
    epsilon: float = 0.15
    kokoro_speed: float = 1.08
    pillar_weights: dict = None
    daily_caps: dict = None
    min_gap_hours: float = 3.0
    updated_at: str = ""
    last_mean_reward: float = 0.0
    last_engagement: float = 0.0
    decision_log: list = None

    def __post_init__(self):
        if self.pillar_weights is None:
            self.pillar_weights = {}
        if self.daily_caps is None:
            self.daily_caps = {"youtube": 4, "facebook": 4, "instagram": 3}
        if self.decision_log is None:
            self.decision_log = []


class StrategyDirector:
    def __init__(self, ml=None, state_path: Path = STATE_PATH):
        self.ml = ml
        self.state_path = Path(state_path)
        self.state = self._load()

    # ── persistence ──
    def _load(self) -> StrategyState:
        try:
            d = json.loads(self.state_path.read_text(encoding="utf-8"))
            return StrategyState(**d)
        except (OSError, json.JSONDecodeError, TypeError):
            return StrategyState()

    def save(self) -> None:
        self.state.updated_at = datetime.now(timezone.utc).isoformat()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self.state), indent=2, ensure_ascii=False),
                       encoding="utf-8")
        os.replace(tmp, self.state_path)

    # ── compute rolling stats from ML reward_log ──
    def _rolling(self, n: int = 20) -> dict:
        if not self.ml:
            return {"mean": 0.0, "engagement": 0.0, "n": 0}
        rewards = self.ml.data.get("reward_log", [])[-n:]
        if not rewards:
            return {"mean": 0.0, "engagement": 0.0, "n": 0}
        vals = [r.get("reward", 0) for r in rewards]
        mean = sum(vals) / len(vals)
        # Engagement approximated from how many penalty-free rewards > 0.5
        positive = sum(1 for v in vals if v > 0.5) / len(vals)
        return {"mean": mean, "engagement": positive, "n": len(vals)}

    # ── pillar performance → weights ──
    def _pillar_scores(self) -> dict:
        if not self.ml:
            return {}
        scores = {}
        for key, arm in self.ml.data.get("arms", {}).items():
            if arm.get("n", 0) < 3:
                continue
            pillar = key.split("::", 1)[0]
            scores.setdefault(pillar, []).append(arm["rewards"] / max(1, arm["n"]))
        out = {}
        for pillar, means in scores.items():
            out[pillar] = round(sum(means) / len(means), 3)
        return out

    def decide(self) -> StrategyState:
        """Run one tuning pass and persist the new state."""
        stats = self._rolling(20)
        s = self.state
        log = []

        # 1) epsilon - exploit more as rewards improve
        old_eps = s.epsilon
        if stats["n"] >= 8:
            target_eps = 0.10 if stats["mean"] > 1.0 else (0.20 if stats["mean"] < 0.4 else 0.15)
            s.epsilon = round(old_eps + 0.4 * (target_eps - old_eps), 3)
            if abs(s.epsilon - old_eps) > 0.005:
                log.append(f"epsilon {old_eps}→{s.epsilon} (mean_reward={stats['mean']:.2f})")

        # 2) voice speed - nudge within safe USA-cadence band based on engagement
        old_speed = s.kokoro_speed
        if stats["n"] >= 10:
            if stats["engagement"] < 0.4 and s.kokoro_speed < 1.12:
                s.kokoro_speed = round(min(1.12, s.kokoro_speed + 0.01), 3)
            elif stats["engagement"] > 0.7 and s.kokoro_speed > 1.05:
                s.kokoro_speed = round(max(1.05, s.kokoro_speed - 0.01), 3)
            if abs(s.kokoro_speed - old_speed) > 0.002:
                log.append(f"voice_speed {old_speed}→{s.kokoro_speed}")

        # 3) pillar weights from real per-pillar rewards
        pscores = self._pillar_scores()
        if pscores:
            for pillar, score in pscores.items():
                prev = s.pillar_weights.get(pillar, 1.0)
                # 0.3 (bad) → 0.7 weight; 1.5+ (great) → 1.25 weight
                target = max(0.6, min(1.25, 0.8 + score * 0.35))
                s.pillar_weights[pillar] = round(prev + 0.5 * (target - prev), 3)
            log.append("pillar weights updated from real performance")

        # 4) cadence & gap - if mean reward < 0.4, reduce burst (more gap)
        old_gap = s.min_gap_hours
        if stats["n"] >= 8:
            target_gap = 4.0 if stats["mean"] < 0.4 else (2.0 if stats["mean"] > 1.2 else 3.0)
            s.min_gap_hours = round(old_gap + 0.5 * (target_gap - old_gap), 2)
            if abs(s.min_gap_hours - old_gap) > 0.1:
                log.append(f"min_gap_hours {old_gap}→{s.min_gap_hours}")

        s.last_mean_reward = round(stats["mean"], 3)
        s.last_engagement = round(stats["engagement"], 3)
        if log:
            s.decision_log.append({"ts": datetime.now(timezone.utc).isoformat(),
                                   "changes": log})
            s.decision_log = s.decision_log[-20:]
            for entry in log:
                logger.info("🎛 %s", entry)
        self.save()
        return s

    def apply_to_env(self) -> None:
        """Push decided values into the process environment so TTS/scheduler/ml pick them up."""
        s = self.state
        os.environ["KOKORO_SPEED"] = str(s.kokoro_speed)
        os.environ["MIN_POST_GAP_HOURS"] = str(s.min_gap_hours)
        # epsilon/weights consumed by ML via override helper below
        os.environ["CD_EPSILON"] = str(s.epsilon)

    def pillar_weight(self, pillar_key: str) -> float:
        return float(self.state.pillar_weights.get(pillar_key, 1.0))


def current_director(ml=None) -> StrategyDirector:
    return StrategyDirector(ml=ml)
