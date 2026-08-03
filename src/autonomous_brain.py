"""
Autonomous Brain for Cognitive-Dark V2.
Orchestrates ML learning results into real-world content decisions.
"""

import logging
import random
from pathlib import Path
from typing import Dict, List, Optional

# Relative imports for the src directory
try:
    from .ml_engine import LearningSystem
    from .niche_strategy import DARK_TOPICS
except ImportError:
    from ml_engine import LearningSystem
    from niche_strategy import DARK_TOPICS

logger = logging.getLogger("autonomous_brain")

class AutonomousBrain:
    def __init__(self):
        self.ls = LearningSystem()
        self.state = self.ls.data

    def decide_next_video(self, exclude_titles: List[str] = None) -> Dict:
        """
        Decision Matrix:
        1. Choose the best arm (pillar/style/timing) via UCB1.
        2. Pick/Generate a topic that matches the winning pillar.
        """
        strategy = self.ls.choose_strategy()
        logger.info(f"🧠 Brain Strategy: {strategy['arm_key']} (UCB: {strategy['ucb_score']})")
        
        winning_pillar = strategy["pillar"]
        topic = self._get_smart_topic(winning_pillar, exclude_titles)
        
        return {
            "pillar": winning_pillar,
            "hook_style": strategy["hook_style"],
            "topic": topic,
            "day_part": strategy["day_part"],
            "arm_key": strategy["arm_key"]
        }

    def _get_smart_topic(self, pillar: str, exclude: List[str] = None) -> str:
        exclude = exclude or []
        candidates = [t for t in DARK_TOPICS if t not in exclude]
        
        pillar_keywords = {
            "brain_glitch": ["brain", "memory", "mind", "think"],
            "dark_psych": ["manipulation", "dark", "secret", "toxic", "influence"],
            "body_language": ["body", "eye", "hand", "micro", "look"],
        }
        relevant = [t for t in candidates if any(k in t.lower() for k in pillar_keywords.get(pillar, []))]
        
        if relevant:
            return random.choice(relevant)
        return random.choice(candidates) if candidates else "The truth about human behavior"

def get_brain() -> AutonomousBrain:
    return AutonomousBrain()
