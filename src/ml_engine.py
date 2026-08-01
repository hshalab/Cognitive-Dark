#!/usr/bin/env python3
"""
Cognitive Dark V2 — ML Learning Engine.

A lightweight online-learning system that makes the pipeline smarter over time:

  • Strategy selection  — UCB1 multi-armed bandit over
    (pillar × hook_style × day-part) arms. Explores when uncertain,
    exploits the best-performing content formulas once evidence exists.
  • Reward / penalty    — strong output (high retention, engagement, views)
    ADDS reward to the arm that produced it; mistakes (upload failures,
    spam flags, very low retention) PENALIZE the responsible arm. The system
    literally learns from its mistakes.
  • Dedup & variation   — 0% spam-detection goal: never re-post the same
    script/hook, and enforce a minimum textual variation against recent
    posts so the feed looks human & native.
  • Platform health     — consecutive failures quarantine a platform until
    it recovers; ML consults health before scheduling.

Persistence: `data/learning_store.json` is committed back to the repo by the
CI workflow so learning survives across GitHub Actions runs.
"""

import hashlib
import json
import logging
import math
import os
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from config.settings import LEARNING, ML_STORE_PATH, DATA_DIR, PILLARS, HOOK_STYLES

logger = logging.getLogger("ml_engine")


# ─────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_text(text: str) -> str:
    """Lowercase, strip punctuation/spaces — for dedup hashing."""
    text = re.sub(r"[^a-z0-9 ]", "", (text or "").lower())
    return re.sub(r"\s+", " ", text).strip()


def text_sha(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode()).hexdigest()


def token_overlap(a: str, b: str) -> float:
    """Jaccard-like overlap of word sets (0..1)."""
    ta = set(normalize_text(a).split())
    tb = set(normalize_text(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1.0, len(ta | tb))


# ─────────────────────────────────────────────────────────────
# LearningSystem
# ─────────────────────────────────────────────────────────────
class LearningSystem:
    """Online learning core: UCB1 bandit + reward/penalty + dedup + health."""

    def __init__(self, store_path: Path = None, cfg: dict = None):
        self.store_path = Path(store_path or ML_STORE_PATH)
        self.cfg = cfg or LEARNING
        self.data = self._load()
        self._ensure_schema()

    # ── persistence ──
    def _load(self) -> dict:
        try:
            with open(self.store_path, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            return {}

    def save(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.store_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, self.store_path)

    def _ensure_schema(self) -> None:
        d = self.data
        d.setdefault("arms", {})            # arm_key -> stats
        d.setdefault("videos", [])          # history of generated posts
        d.setdefault("penalty_log", [])
        d.setdefault("reward_log", [])
        d.setdefault("health", {})          # platform -> {failures, healthy, last_check}
        d.setdefault("model_version", 2)
        d.setdefault("created_at", _now_iso())

    # ── arm management ──
    @staticmethod
    def arm_key(pillar: str, hook_style: str, day_part: str) -> str:
        return f"{pillar}::{hook_style}::{day_part}"

    def _arm(self, key: str) -> dict:
        arm = self.data["arms"].setdefault(key, {
            "plays": 0, "rewards": 0.0, "sum_sq": 0.0, "n": 0, "updated": _now_iso(),
        })
        return arm

    # ── UCB1 selection ──
    def choose_strategy(self, recent_keys: list = None) -> dict:
        """Pick (pillar, hook_style, day_part) via UCB1 with epsilon exploration.

        Arms with no evidence are explored first; ties broken randomly;
        recently-used arms are down-weighted to keep the feed varied.
        """
        recent_keys = set(recent_keys or [])
        now = datetime.now(timezone.utc)
        hour = now.hour
        day_part = "morning" if hour < 12 else ("afternoon" if hour < 17 else "evening")

        total_plays = sum(a["plays"] for a in self.data["arms"].values()) or 1
        epsilon = self.cfg["epsilon"]

        candidates = []
        for pillar in PILLARS:
            for style in HOOK_STYLES:
                key = self.arm_key(pillar["key"], style, day_part)
                arm = self._arm(key)
                score = self._ucb_score(arm, total_plays)
                if key in recent_keys:
                    score *= 0.5  # avoid instant repeat of same formula
                candidates.append((score, key, arm, pillar["key"], style, day_part))

        # Explore random arm with prob epsilon
        if random.random() < epsilon:
            chosen = random.choice(candidates)
        else:
            chosen = max(candidates, key=lambda c: c[0])

        score, key, arm, pillar, style, dp = chosen
        arm["plays"] += 1
        arm["updated"] = _now_iso()

        return {
            "arm_key": key, "pillar": pillar, "hook_style": style,
            "day_part": dp, "ucb_score": round(score, 4),
            "arm_evidence": arm["n"],
        }

    @staticmethod
    def _ucb_score(arm: dict, total_plays: int) -> float:
        n = arm["n"]
        if n == 0:
            return 1e9 + random.random()  # unexplored arms first
        mean = arm["rewards"] / n
        # Upper Confidence Bound (UCB1)
        explore = math.sqrt(2.0 * math.log(max(2, total_plays)) / n)
        return mean + explore

    # ── reward / penalty ──
    def record_outcome(self, arm_key: str, reward: float) -> None:
        """Push a real outcome into the arm's distribution (UCB update)."""
        arm = self._arm(arm_key)
        arm["rewards"] += max(0.0, reward)
        arm["sum_sq"] += max(0.0, reward) ** 2
        arm["n"] += 1
        arm["updated"] = _now_iso()
        self.data["reward_log"].append({
            "ts": _now_iso(), "arm": arm_key, "reward": round(reward, 4),
        })
        self._trim("reward_log")

    def apply_penalty(self, arm_key: str, reason: str, weight: float = None) -> float:
        """Penalize the arm behind a mistake (failure / low retention / spam flag)."""
        w = weight if weight is not None else self.cfg["penalty_failure"]
        arm = self._arm(arm_key)
        arm["rewards"] = max(0.0, arm["rewards"] - abs(w))
        arm["n"] += 1  # counts as evidence (negative signal)
        arm["updated"] = _now_iso()
        self.data["penalty_log"].append({
            "ts": _now_iso(), "arm": arm_key, "reason": reason, "penalty": w,
        })
        self._trim("penalty_log")
        logger.info("PENALTY applied %s → %s (%.1f)", reason, arm_key, w)
        return w

    def apply_reward(self, arm_key: str, reason: str, weight: float = None) -> float:
        """Reward the arm behind a strong output."""
        w = weight if weight is not None else self.cfg["bonus_viral"]
        arm = self._arm(arm_key)
        arm["rewards"] += abs(w)
        arm["n"] += 1
        arm["updated"] = _now_iso()
        self.data["reward_log"].append({
            "ts": _now_iso(), "arm": arm_key, "reason": reason, "reward": w,
        })
        self._trim("reward_log")
        logger.info("REWARD applied %s → %s (%.1f)", reason, arm_key, w)
        return w

    @staticmethod
    def _trim(lst: list, keep: int = 500) -> None:
        if len(lst) > keep:
            del lst[:len(lst) - keep]

    # ── derived reward from platform metrics ──
    @staticmethod
    def reward_from_metrics(m: dict, cfg: dict = None) -> float:
        """Map raw platform metrics into a single reward scalar (0..~5)."""
        cfg = cfg or LEARNING
        retention = m.get("retention", 0.0)         # 0..1 avg view duration
        views = float(m.get("views", 0) or 0)
        likes = float(m.get("likes", 0) or 0)
        comments = float(m.get("comments", 0) or 0)
        shares = float(m.get("shares", 0) or 0)
        subs = float(m.get("subs_gained", 0) or 0)

        eng = likes + 2 * comments + 3 * shares + 5 * subs
        view_score = min(1.0, math.log10(views + 1) / 6.0)
        ret_score = min(1.0, retention / 0.55)      # >55% avg retention = excellent
        eng_score = min(1.0, eng / 200.0)

        r = (cfg["reward_retention"] * ret_score +
             cfg["reward_engagement"] * eng_score +
             cfg["reward_views"] * view_score)
        if retention >= 0.55 and views >= 1000:
            r += cfg["bonus_viral"] / 3.0
        return round(min(5.0, r * 3.0), 3)

    # ── dedup & variation (0% spam-detection goal) ──
    def dedup_guard(self, script_text: str, hook: str = "") -> dict:
        """Return verdict: {'allowed': bool, 'reason': str}.

        Blocks exact re-posts and enforces minimum variation vs recent videos.
        """
        combined = f"{hook} | {script_text}"
        h = text_sha(combined)
        for v in self.data["videos"][-self.cfg["dedup_window"]:]:
            if v.get("text_sha") == h:
                return {"allowed": False, "reason": "exact duplicate of previous post"}
            if token_overlap(v.get("hook", ""), hook) > 0.75:
                return {"allowed": False, "reason": "hook too similar to recent post"}

        recent = [v.get("text", "") for v in self.data["videos"][-5:]]
        if recent:
            max_overlap = max(token_overlap(combined, r) for r in recent)
            if max_overlap > self.cfg["min_variation"] + 0.35:
                return {"allowed": False,
                        "reason": f"too similar to recent post (overlap {max_overlap:.2f})"}
        return {"allowed": True, "reason": "ok"}

    def register_video(self, rec: dict) -> None:
        """Record a produced/queued video for future dedup + learning."""
        rec.setdefault("ts", _now_iso())
        self.data["videos"].append(rec)
        if len(self.data["videos"]) > 2000:
            self.data["videos"] = self.data["videos"][-2000:]
        self.save()

    # ── platform health (auto-repair integration) ──
    def platform_healthy(self, platform: str) -> bool:
        h = self.data["health"].get(platform, {})
        return h.get("healthy", True) and h.get("failures", 0) < 3

    def report_failure(self, platform: str, reason: str) -> None:
        h = self.data["health"].setdefault(platform, {"failures": 0, "healthy": True})
        h["failures"] = h.get("failures", 0) + 1
        h["last_reason"] = reason
        h["last_check"] = _now_iso()
        if h["failures"] >= 3:
            h["healthy"] = False
            logger.warning("⚠️ Platform %s quarantined after %d failures", platform, h["failures"])
        self.save()

    def report_success(self, platform: str) -> None:
        h = self.data["health"].setdefault(platform, {"failures": 0, "healthy": True})
        h["failures"] = 0
        h["healthy"] = True
        h["last_check"] = _now_iso()
        self.save()

    # ── insight feed for script prompt (closes the learning loop) ──
    def best_formulas(self, top: int = 3) -> list:
        """Return the top-performing arm formulas (pillar/style pairs)."""
        scored = []
        for key, arm in self.data["arms"].items():
            if arm["n"] == 0:
                continue
            scored.append((arm["rewards"] / arm["n"], key, arm["n"]))
        scored.sort(reverse=True)
        out = []
        for mean, key, n in scored[:top]:
            pillar, style, dp = key.split("::")
            out.append({"pillar": pillar, "hook_style": style, "mean": round(mean, 3), "n": n})
        return out

    def summary(self) -> dict:
        return {
            "arms_tested": len(self.data["arms"]),
            "videos_tracked": len(self.data["videos"]),
            "rewards": len(self.data["reward_log"]),
            "penalties": len(self.data["penalty_log"]),
            "best_formulas": self.best_formulas(5),
            "health": self.data["health"],
        }


# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys

    if "--simulate" in sys.argv:
        # 300-round simulation: arms with high retention should rise to top
        ls = LearningSystem(store_path=Path("/tmp/ml_sim.json"))
        ls.data["arms"] = {}
        for i in range(300):
            s = ls.choose_strategy()
            # arm quality depends on pillar & style (synthetic)
            quality = {"pattern_interrupt": 0.8, "knowledge_gap": 0.7,
                       "fear_based": 0.55, "curiosity_trigger": 0.65,
                       "counterintuitive": 0.6, "dark_revelation": 0.5,
                       "stoic_echo": 0.75, "red_flag_checklist": 0.85}.get(
                s["hook_style"], 0.5)
            reward = quality + random.uniform(-0.15, 0.15)
            ls.record_outcome(s["arm_key"], reward)
        top = ls.best_formulas(5)
        print("Top 5 arms after 300 simulated rounds:")
        for t in top:
            print(f"  {t['pillar']:>18} / {t['hook_style']:<22} mean={t['mean']:.3f} n={t['n']}")
        print("Expected: red_flag_checklist & pattern_interrupt & stoic_echo on top")
