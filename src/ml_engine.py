#!/usr/bin/env python3
"""
Cognitive Dark V2.1 — ML Learning Engine (advanced).

A lightweight online-learning system that makes the pipeline smarter over time:

  • Strategy selection  — UCB1 multi-armed bandit over
    (pillar x hook_style x day-part) arms, with recency decay so stale
    formulas get re-tested. Explores when uncertain, exploits winners.
  • Reward / penalty    — strong output ADDS reward to the EXACT arm that
    produced it; mistakes PENALIZE that same arm. V2.1 fixes the V2 bug
    where rewards/penalties landed on different arm keys than the one
    chosen — the bandit actually learns in production now.
  • Per-video attribution — every uploaded video_id is mapped to its arm,
    so real analytics (views/likes/comments) credit the exact formula.
  • Post-volume guards    — daily caps + minimum gap per platform
    (2026 algorithm: consistency beats bursts; bursts trigger spam signals).
  • Dedup & variation     — never re-post the same script/hook, and enforce
    minimum textual variation vs recent posts (native, human-like feed).
  • Platform health       — consecutive failures quarantine a platform;
    success heals it automatically.

Persistence: `data/learning_store.json` is committed back to the repo by the
CI workflow so learning survives across GitHub Actions runs. Every mutating
operation auto-saves (V2 lost end-of-run rewards because save() was skipped).
"""

import contextlib
import hashlib
import json
import logging
import math
import os
import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config.settings import HOOK_STYLES, LEARNING, ML_STORE_PATH, PILLARS

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


def current_day_part() -> str:
    """morning / afternoon / evening (timezone.utc) — shared by selection & fallback keys."""
    hour = datetime.now(timezone.utc).hour
    return "morning" if hour < 12 else ("afternoon" if hour < 17 else "evening")


# ─────────────────────────────────────────────────────────────
# LearningSystem
# ─────────────────────────────────────────────────────────────
class LearningSystem:
    """Online learning core: UCB1 bandit + attribution + guards + health."""

    def __init__(self, store_path: Path = None, cfg: dict = None):
        self.store_path = Path(store_path or ML_STORE_PATH)
        self.cfg = dict(LEARNING)
        if cfg:
            self.cfg.update(cfg)
        # Live overrides from the Strategy Director (env-driven, auto-tuned)
        env_eps = os.environ.get("CD_EPSILON")
        if env_eps:
            with contextlib.suppress(ValueError):
                self.cfg["epsilon"] = float(env_eps)
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
        d.setdefault("attribution", {})     # video_id -> {arm_key, platform, ts, credited}
        d.setdefault("post_log", {})        # date -> {platform: {count, last_ts}}
        d.setdefault("penalty_log", [])
        d.setdefault("reward_log", [])
        d.setdefault("health", {})          # platform -> {failures, healthy, last_check}
        d.setdefault("model_version", 3)
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

    def recent_arm_keys(self, n: int = 6) -> list:
        """Arm keys of the last n registered videos (recency weighting input)."""
        keys = []
        for v in reversed(self.data["videos"][-n:]):
            k = v.get("arm_key")
            if k:
                keys.append(k)
        return keys

    def apply_seed_priors(self, priors: dict | None = None,
                          source: str = "seeded_priors") -> dict:
        """Warm-start the bandit with prior (pillar, hook) mean rewards.

        Priors are laid across ALL three day-parts for each (pillar, hook)
        pair so the UCB index has evidence everywhere on day one. Existing
        REAL evidence is never overwritten — priors only fill arms whose n==0.

        priors: {(pillar, hook): (mean, n_samples)}. Defaults to the
        curated set in seed_priors.SEED_PRIORS (documented, NOT fake
        "500 channel" data — see that module's docstring for the source).
        """
        if priors is None:
            from seed_priors import PRIOR_VERSION, SEED_PRIORS
            priors = SEED_PRIORS
            self.data["prior_version"] = PRIOR_VERSION
        seeded = 0
        for (pillar, hook), (mean, n) in priors.items():
            for day_part in ("morning", "afternoon", "evening"):
                key = self.arm_key(pillar, hook, day_part)
                arm = self._arm(key)
                if arm["n"] > 0:
                    continue  # never overwrite real evidence
                arm["rewards"] = round(float(mean) * int(n), 4)
                arm["sum_sq"] = round((float(mean) ** 2) * int(n), 4)
                arm["n"] = int(n)
                arm["plays"] = arm.get("plays", 0)
                arm["updated"] = _now_iso()
                arm["seeded"] = True
                seeded += 1
        self.data.setdefault("prior_log", []).append({
            "ts": _now_iso(), "source": source, "arms_seeded": seeded})
        self.save()
        logger.info("🌱 Seeded %d arms with warm-start priors (source=%s)", seeded, source)
        return {"arms_seeded": seeded, "source": source}

    # ── UCB1 selection ──
    def choose_strategy(self, recent_keys: list = None) -> dict:
        """Pick (pillar, hook_style, day_part) via UCB1 with epsilon exploration.

        Arms with no evidence are explored first; ties broken randomly;
        recently-used arms are down-weighted to keep the feed varied.
        """
        if recent_keys is None:
            recent_keys = self.recent_arm_keys()
        recent_keys = set(recent_keys)
        day_part = current_day_part()

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
        chosen = (random.choice(candidates) if random.random() < epsilon
                  else max(candidates, key=lambda c: c[0]))

        score, key, arm, pillar, style, dp = chosen
        arm["plays"] += 1
        arm["updated"] = _now_iso()
        self.save()

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
        # V2.1 recency decay: formulas silent for weeks get re-tested
        try:
            age_days = (datetime.now(timezone.utc) -
                        datetime.fromisoformat(arm["updated"])).total_seconds() / 86400
            decay = 0.97 ** max(0.0, age_days - 14)
        except (ValueError, KeyError):
            decay = 1.0
        return (mean + explore) * decay

    # ── reward / penalty (auto-persisted since V2.1) ──
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
        self.save()

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
        self.save()
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
        self.save()
        logger.info("REWARD applied %s → %s (%.1f)", reason, arm_key, w)
        return w

    @staticmethod
    def _trim(lst: list, keep: int = 500) -> None:
        if len(lst) > keep:
            del lst[:len(lst) - keep]

    # ── derived reward from platform metrics ──
    @staticmethod
    def reward_from_metrics(m: dict, cfg: dict = None) -> float:
        """Map raw platform metrics into a single reward scalar (0..~5).

        Delegates to reward.reward_from_dict so retention, completion,
        engagement, views, CTR and voice quality are ALL considered — not
        just views+likes. Kept here for backward compatibility.
        """
        try:
            from reward import reward_from_dict
            reward, _ = reward_from_dict(m)
            return reward
        except Exception:
            # Fallback (should not happen) — minimal legacy path
            views = float(m.get("views", 0) or 0)
            return round(min(5.0, math.log10(views + 1) / 6.0 * 3.0), 3)

    # ── per-video attribution (closes the learning loop) ──
    def record_video_id(self, platform: str, video_id: str, arm_key: str,
                        title: str = "") -> None:
        """Map a published video to its arm so analytics credit the formula."""
        if not video_id:
            return
        self.data["attribution"][str(video_id)] = {
            "arm_key": arm_key, "platform": platform, "title": title,
            "ts": _now_iso(), "credited": False,
        }
        # keep attribution bounded
        if len(self.data["attribution"]) > 500:
            oldest = sorted(self.data["attribution"].items(),
                            key=lambda kv: kv[1].get("ts", ""))[:-500]
            for k, _ in oldest:
                del self.data["attribution"][k]
        self.save()
        logger.info("🔗 Attributed %s:%s → %s", platform, video_id, arm_key)

    def pending_video_ids(self, platform: str | None = None) -> list:
        """Uncredited video ids (optionally filtered by platform)."""
        return [vid for vid, a in self.data["attribution"].items()
                if not a.get("credited") and (platform is None or a["platform"] == platform)]

    def credit_video(self, video_id: str, metrics: dict) -> float:
        """Convert real analytics for one video into a reward on its arm."""
        vid = str(video_id)
        a = self.data["attribution"].get(vid)
        if not a or a.get("credited"):
            return 0.0
        reward = self.reward_from_metrics(metrics)
        a["credited"] = True
        a["metrics"] = metrics
        a["credited_at"] = _now_iso()
        if reward > 0:
            self.apply_reward(a["arm_key"], f"metrics:{vid[:12]}", reward)
        else:
            self.apply_penalty(a["arm_key"], f"low_metrics:{vid[:12]}",
                               self.cfg["penalty_low_retention"])
        return reward

    # ── post-volume guards (2026: consistency > bursts) ──
    def can_post(self, platform: str, max_daily: int = 3,
                 min_gap_hours: float = 4.0) -> tuple:
        """Return (allowed, reason). Enforces daily cap + min gap between posts."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        day = self.data["post_log"].get(today, {})
        info = day.get(platform, {})
        count = info.get("count", 0)
        if count >= max_daily:
            return False, f"daily cap reached ({count}/{max_daily})"
        last = info.get("last_ts")
        if last and min_gap_hours > 0:
            try:
                elapsed = (datetime.now(timezone.utc) -
                           datetime.fromisoformat(last)).total_seconds() / 3600
                if elapsed < min_gap_hours:
                    return False, f"min gap not met ({elapsed:.1f}h < {min_gap_hours}h)"
            except ValueError:
                pass
        return True, "ok"

    def record_post(self, platform: str) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        day = self.data["post_log"].setdefault(today, {})
        info = day.setdefault(platform, {"count": 0, "last_ts": None})
        info["count"] += 1
        info["last_ts"] = _now_iso()
        # Keep a rolling 30-day post log. V2.1.6: the previous loop body was
        # `pass` (no-op) so stale dates were never pruned; the length cap below
        # only trimmed when >30 distinct keys. Do an explicit date prune now.
        cutoff = (datetime.now(timezone.utc).date() -
                  timedelta(days=30)).isoformat()
        for d in list(self.data["post_log"].keys()):
            if d < cutoff:
                del self.data["post_log"][d]
        self.save()

    # ── dedup & variation ──
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
    @staticmethod
    def _sanitize_reason(reason: str) -> str:
        """V2.1 SECURITY: never persist tokens/secrets inside error reasons.

        V2 stored raw exception URLs (including ?access_token=...) into the
        committed learning store — a live-token leak in a public repo.
        """
        import re as _re
        reason = _re.sub(r"access_token=[^&\s\"']+", "access_token=***", reason or "")
        reason = _re.sub(r"(EA[A-Za-z0-9]{20,})", "***", reason)
        reason = _re.sub(r"(ghp_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]+)", "***", reason)
        return reason[:400]

    def platform_healthy(self, platform: str) -> bool:
        h = self.data["health"].get(platform, {})
        # V2.1: quarantines AUTO-EXPIRE after 24h. V2 had a deadlock: old
        # failures quarantined a platform forever — uploads were skipped, so
        # no success could ever heal it. Now stale quarantines release and the
        # platform gets retried (failures re-quarantine it if still broken).
        if not h.get("healthy", True) or h.get("failures", 0) >= 3:
            try:
                last = datetime.fromisoformat(h.get("last_check", ""))
                age_h = (datetime.now(timezone.utc) - last).total_seconds() / 3600
            except (ValueError, TypeError):
                age_h = 999
            if age_h > 24:
                logger.info("🩹 %s quarantine expired (%.0fh old) — retrying", platform, age_h)
                h["healthy"] = True
                h["failures"] = 0
                self.data["health"][platform] = h
                self.save()
            else:
                return False
        return True

    def report_failure(self, platform: str, reason: str) -> None:
        h = self.data["health"].setdefault(platform, {"failures": 0, "healthy": True})
        h["failures"] = h.get("failures", 0) + 1
        h["last_reason"] = self._sanitize_reason(reason)
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
            pillar, style, _day_part = key.split("::")
            out.append({"pillar": pillar, "hook_style": style, "mean": round(mean, 3), "n": n})
        return out

    def summary(self) -> dict:
        return {
            "arms_tested": len(self.data["arms"]),
            "videos_tracked": len(self.data["videos"]),
            "attributed_videos": len(self.data["attribution"]),
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
        for _ in range(300):
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
