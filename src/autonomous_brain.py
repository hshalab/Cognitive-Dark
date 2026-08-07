#!/usr/bin/env python3
"""
Autonomous Brain for Cognitive-Dark V2.1.
Orchestrates ML learning results into real-world content decisions.

Fixed in V2.1:
  • niche_strategy module now exists (was ModuleNotFoundError → WAR_MODE dead)
  • pillar keywords mapped to the CURRENT 8 pillars (V1 keys removed)
  • topics pulled from a deep per-pillar bank (2026 viral angles)
"""

import logging
import random

try:
    from .ml_engine import LearningSystem
    from .niche_strategy import DARK_TOPICS, PILLAR_KEYWORDS, topics_for_pillar
except ImportError:
    from ml_engine import LearningSystem
    from niche_strategy import DARK_TOPICS, PILLAR_KEYWORDS, topics_for_pillar

logger = logging.getLogger("autonomous_brain")


class AutonomousBrain:
    def __init__(self):
        self.ls = LearningSystem()
        self.state = self.ls.data

    def decide_next_video(self, exclude_titles: list[str] = None) -> dict:
        """
        Decision Matrix:
        1. Choose the best arm (pillar/style/timing) via UCB1.
        2. Pick a topic from the winning pillar's bank (novelty-checked).
        """
        strategy = self.ls.choose_strategy()
        logger.info("🧠 Brain Strategy: %s (UCB: %s)",
                    strategy["arm_key"], strategy["ucb_score"])

        winning_pillar = strategy["pillar"]
        topic = self._get_smart_topic(winning_pillar, exclude_titles)

        return {
            "pillar": winning_pillar,
            "hook_style": strategy["hook_style"],
            "topic": topic,
            "day_part": strategy["day_part"],
            "arm_key": strategy["arm_key"],
        }

    def _get_smart_topic(self, pillar: str, exclude: list[str] = None) -> str:
        exclude = [e.lower() for e in (exclude or [])]
        # Prefer the winning pillar's own topic bank
        bank = [t for t in topics_for_pillar(pillar) if t.lower() not in exclude]
        if bank:
            return random.choice(bank)
        # Fallback: keyword-match the global pool
        keys = PILLAR_KEYWORDS.get(pillar, [])
        matched = [t for t in DARK_TOPICS
                   if any(k in t.lower() for k in keys) and t.lower() not in exclude]
        if matched:
            return random.choice(matched)
        candidates = [t for t in DARK_TOPICS if t.lower() not in exclude]
        return random.choice(candidates) if candidates else \
            "The truth about how influence really works"


def get_brain() -> AutonomousBrain:
    return AutonomousBrain()
