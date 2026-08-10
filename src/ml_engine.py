#!/usr/bin/env python3
"""
Coercion Files — ML Learning Engine (advanced).

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
import shutil
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
        # V2.7 fail-safe: store_ok=False means the ML memory could not be
        # loaded — every posting guard then BLOCKS publishing. A run with no
        # memory must never be allowed to double-post.
        self.store_ok = True
        self._rebuilt = False
        self.data = self._load()
        self._ensure_schema()
        # If we rebuilt from the event log, persist the healed store NOW so
        # the next process loads the real file (no repeated replay).
        if self._rebuilt and self.store_ok:
            try:
                self.save()
                logger.warning("Healed ML store written to %s", self.store_path)
            except Exception as exc:
                logger.warning("Could not persist healed store: %s", exc)

    # ── persistence ──
    def _load(self) -> dict:
        """Load the store; never silently return a broken state.

        Order: main file → .bak snapshot → rebuild from the append-only event
        log. Only if ALL are unusable do we set store_ok=False so that
        can_post()/dedup_guard() refuse to publish until
        scripts/repair_data_files.py restores the store. A missing store
        (fresh install) is fine — there is simply nothing to guard yet.
        """
        bak = self.store_path.with_suffix(self.store_path.suffix + ".bak")
        if not self.store_path.exists() and not bak.exists() \
                and not self.events_path.exists():
            return {}  # fresh start — no memory yet

        for path in (self.store_path, bak):
            if not path.exists():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("store root must be a JSON object")
                if path is bak:
                    logger.warning(
                        "ML store corrupt at %s — recovered from backup %s. "
                        "Run scripts/repair_data_files.py to restore the real store.",
                        self.store_path, bak)
                return data
            except (json.JSONDecodeError, ValueError, OSError) as exc:
                logger.critical("ML store unreadable at %s (%s)", path, exc)

        # LAST LINE OF DEFENSE: rebuild memory from the append-only event log
        # (the "diary"). This is what guarantees the ML NEVER loses its
        # learning — even if both store copies get corrupted by CI conflicts.
        rebuilt = self._rebuild_from_events()
        if rebuilt is not None:
            self._rebuilt = True
            self.store_ok = True
            logger.warning(
                "ML store missing/corrupt — rebuilt from event log "
                "(%d events replayed, %d arms, %d videos)",
                rebuilt.get("events_replayed", 0),
                len(rebuilt.get("arms", {})),
                len(rebuilt.get("videos", [])))
            return rebuilt

        self.store_ok = False
        logger.critical(
            "No usable ML store (main + backup + event log all broken). "
            "All posting is BLOCKED until scripts/repair_data_files.py succeeds.")
        return {}

    def save(self) -> None:
        """Persist atomically, keeping a last-known-good .bak first.

        If the store is broken we REFUSE to overwrite it (that would destroy
        the only evidence + recoverable memory) and post no data at all.
        """
        if not self.store_ok:
            logger.critical(
                "Refusing to overwrite a corrupted ML store — run "
                "scripts/repair_data_files.py first. Nothing was written.")
            return
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        if self.store_path.exists():
            try:
                shutil.copy2(self.store_path,
                             self.store_path.with_suffix(self.store_path.suffix + ".bak"))
            except OSError as exc:
                logger.warning("Could not write .bak backup: %s", exc)
        tmp = self.store_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, self.store_path)

    # ── append-only event log (the "diary" — memory survives any crash) ──
    @property
    def events_path(self) -> Path:
        """Events live next to the store: store.json → store.events.jsonl."""
        return self.store_path.with_suffix(self.store_path.suffix + ".events.jsonl")

    def _append_event(self, etype: str, **payload) -> None:
        """Append one immutable event line. Never raises (memory is best-effort)."""
        try:
            line = {"ts": _now_iso(), "type": etype, **payload}
            with open(self.events_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(line, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning("Could not append event %s: %s", etype, exc)

    @staticmethod
    def _arm_in(data: dict, key: str) -> dict:
        """Create/get an arm dict inside an arbitrary data root (for replay)."""
        return data["arms"].setdefault(key, {
            "plays": 0, "rewards": 0.0, "sum_sq": 0.0, "n": 0,
            "updated": _now_iso(),
        })

    def _rebuild_from_events(self) -> dict | None:
        """Replay the event log into a fresh, valid store. None if unusable."""
        ep = self.events_path
        if not ep.exists():
            return None
        events = []
        try:
            for line in ep.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                events.append(json.loads(line))
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Event log unreadable (%s) — cannot rebuild", exc)
            return None
        if not events:
            return None

        data = {
            "arms": {}, "videos": [], "attribution": {}, "post_log": {},
            "publish_claims": {}, "penalty_log": [], "reward_log": [],
            "health": {}, "model_version": 3,
            "created_at": events[0].get("ts", _now_iso()),
            "rebuilt_from_events": True,
            "rebuilt_ts": _now_iso(),
            "events_replayed": len(events),
        }
        for ev in events:
            t = ev.get("type")
            ts = ev.get("ts", _now_iso())
            try:
                if t == "reward":
                    arm = self._arm_in(data, ev["arm"])
                    w = float(ev["w"])
                    arm["rewards"] += w
                    arm["sum_sq"] += w * w
                    arm["n"] += 1
                    arm["updated"] = ts
                    data["reward_log"].append({"ts": ts, "arm": ev["arm"],
                                               "reward": round(w, 4),
                                               "platform": ev.get("platform")})
                elif t == "penalty":
                    arm = self._arm_in(data, ev["arm"])
                    w = -abs(float(ev["w"]))
                    arm["rewards"] += w
                    arm["sum_sq"] += w * w
                    arm["n"] += 1
                    arm["updated"] = ts
                    data["penalty_log"].append({"ts": ts, "arm": ev["arm"],
                                                "reason": ev.get("reason", ""),
                                                "penalty": ev.get("w"),
                                                "platform": ev.get("platform")})
                elif t == "post":
                    date, plat = ev["date"], ev["platform"]
                    info = data["post_log"].setdefault(date, {}).setdefault(
                        plat, {"count": 0, "last_ts": None})
                    info["count"] += 1
                    info["last_ts"] = ev.get("ts")
                elif t == "video":
                    rec = dict(ev.get("rec", {}))
                    rec.setdefault("ts", ts)
                    data["videos"].append(rec)
                elif t == "attribution":
                    data["attribution"][str(ev["video_id"])] = {
                        "arm_key": ev.get("arm_key"), "platform": ev.get("platform"),
                        "title": ev.get("title", ""), "ts": ts, "credited": False,
                    }
                elif t == "credit":
                    a = data["attribution"].get(str(ev.get("video_id")))
                    if a:
                        a["credited"] = True
                        a["credited_at"] = ts
                        a["reward"] = ev.get("reward", 0)
                elif t == "claim":
                    data["publish_claims"].setdefault(ev["platform"], {})[ev["iso"]] = {
                        "run_id": ev.get("run_id"), "ts": ts}
                elif t == "health_failure":
                    h = data["health"].setdefault(ev["platform"],
                                                  {"failures": 0, "healthy": True})
                    h["failures"] = h.get("failures", 0) + 1
                    h["last_reason"] = ev.get("reason", "")
                    h["last_check"] = ts
                    if h["failures"] >= 3:
                        h["healthy"] = False
                elif t == "health_success":
                    data["health"][ev["platform"]] = {"failures": 0, "healthy": True,
                                                      "last_check": ts}
                elif t == "seed":
                    for key, (mean, n) in (ev.get("priors") or {}).items():
                        arm = self._arm_in(data, key)
                        if arm.get("n", 0) == 0:
                            arm.update({
                                "rewards": round(float(mean) * int(n), 4),
                                "sum_sq": round((float(mean) ** 2) * int(n), 4),
                                "n": int(n), "prior_n": int(n),
                                "prior_mean": round(float(mean), 4),
                                "seeded": True, "updated": ts})
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("Skipping unparseable event %s: %s", t, exc)

        data["reward_log"] = data["reward_log"][-500:]
        data["penalty_log"] = data["penalty_log"][-500:]
        if len(data["videos"]) > 2000:
            data["videos"] = data["videos"][-2000:]
        return data

    def _ensure_schema(self) -> None:
        d = self.data
        d.setdefault("arms", {})            # arm_key -> stats
        d.setdefault("videos", [])          # history of generated posts
        d.setdefault("attribution", {})     # video_id -> {arm_key, platform, ts, credited}
        d.setdefault("post_log", {})        # date -> {platform: {count, last_ts}}
        d.setdefault("publish_claims", {})   # platform -> {publish_at_iso: {run_id, ts}}
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
                # Seed only if not already seeded and no real evidence exists.
                # prior_n>0 means a prior is already written; n>prior_n means
                # real outcomes were added on top of the prior. Either way skip.
                if arm.get("n", 0) > 0:
                    continue
                arm["rewards"] = round(float(mean) * int(n), 4)
                arm["sum_sq"] = round((float(mean) ** 2) * int(n), 4)
                arm["n"] = int(n)
                arm["prior_n"] = int(n)
                arm["prior_mean"] = round(float(mean), 4)
                arm["plays"] = arm.get("plays", 0)
                arm["updated"] = _now_iso()
                arm["seeded"] = True
                seeded += 1
        self.data.setdefault("prior_log", []).append({
            "ts": _now_iso(), "source": source, "arms_seeded": seeded})
        if seeded:
            priors_for_log = {}
            for key, arm in self.data["arms"].items():
                if arm.get("seeded") and arm.get("prior_n"):
                    priors_for_log[key] = [arm.get("prior_mean", 0.0), arm.get("prior_n")]
            self._append_event("seed", source=source,
                               arms_seeded=seeded, priors=priors_for_log)
        self.save()
        logger.info("🌱 Seeded %d arms with warm-start priors (source=%s)", seeded, source)
        return {"arms_seeded": seeded, "source": source}

    # ── UCB1 selection ──
    def choose_strategy(self, recent_keys: list = None,
                        platform: str | None = None) -> dict:
        """Pick (pillar, hook_style, day_part) using a mature bandit policy.

        Default is Thompson sampling (Bayesian posterior sampling), which
        naturally balances explore/exploit using each arm's uncertainty.
        UCB1 is available as fallback (cfg['policy']='ucb'). A small residual
        epsilon still picks a fully random arm to guarantee coverage.

        If cfg['per_platform'] is on and `platform` is given, the score is
        blended with that platform's specific arm history so YouTube vs Reels
        learn separately.
        """
        from bandit import posterior_from_arm, score_arms, should_force_exploration
        if recent_keys is None:
            recent_keys = self.recent_arm_keys()
        recent_keys = set(recent_keys)
        day_part = current_day_part()
        policy = os.environ.get("CD_POLICY", self.cfg.get("policy", "thompson"))
        epsilon = self.cfg.get("epsilon", 0.10)

        total_plays = sum(a["plays"] for a in self.data["arms"].values()) or 1
        c = self.cfg.get("ucb_c", 2.0)

        candidates = []
        for pillar in PILLARS:
            for style in HOOK_STYLES:
                key = self.arm_key(pillar["key"], style, day_part)
                arm = self._arm(key)
                # baseline score (0.0 placeholder; real score added below)
                candidates.append((0.0, key, arm, pillar["key"], style, day_part))

        candidates = score_arms(candidates, policy=policy,
                                total_plays=total_plays, c=c)

        # Cold-start guarantee: with some probability, force a genuinely
        # under-observed arm (UCB's "infinite bonus" generalized).
        force = [c for c in candidates if should_force_exploration(c[2])]
        if force and random.random() < 0.25:
            chosen = random.choice(force)
        # Residual epsilon-random over all candidates
        elif random.random() < epsilon:
            chosen = random.choice(candidates)
        else:
            chosen = max(candidates, key=lambda c: c[0])

        # Recency / variety penalty (don't instantly repeat same formula),
        # plus pillar-weight adjustment from the Strategy Director.
        score, key, arm, pillar, style, dp = chosen
        if key in recent_keys:
            score *= 0.5
        weight = float(self.data.get("pillar_weights", {}).get(pillar, 1.0))
        score *= weight

        # Per-platform blend (optional)
        if platform and self.cfg.get("per_platform", True):
            plat = self._platform_arm(platform, key)
            if plat.get("n", 0) >= 3:
                p_post = posterior_from_arm(plat)
                score = 0.6 * score + 0.4 * p_post.mean

        arm["plays"] += 1
        arm["updated"] = _now_iso()
        self.save()

        post = posterior_from_arm(arm)
        ci_lo, ci_hi = post.confidence_interval()
        return {
            "arm_key": key, "pillar": pillar, "hook_style": style,
            "day_part": dp, "policy": policy,
            "score": round(score, 4),
            "posterior_mean": round(post.mean, 3),
            "posterior_std": round(post.std, 3),
            "ci_95": [round(ci_lo, 3), round(ci_hi, 3)],
            "arm_evidence": arm["n"],
        }

    def _platform_arm(self, platform: str, base_key: str) -> dict:
        """Per-platform arm stats bucket (separate learning per platform)."""
        d = self.data.setdefault("platform_arms", {}).setdefault(platform, {})
        return d.setdefault(base_key, {"n": 0, "rewards": 0.0, "sum_sq": 0.0})

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
    def _update_arm(self, arm_key: str, reward: float) -> None:
        """Store a signed reward observation (allows negative penalties)."""
        arm = self._arm(arm_key)
        arm["rewards"] += float(reward)
        arm["sum_sq"] += float(reward) * float(reward)
        arm["n"] += 1
        arm["updated"] = _now_iso()

    def _record_platform(self, arm_key: str, platform: str | None, reward: float) -> None:
        if not (platform and self.cfg.get("per_platform", True)):
            return
        pa = self._platform_arm(platform, arm_key)
        pa["rewards"] += float(reward)
        pa["sum_sq"] += float(reward) * float(reward)
        pa["n"] += 1

    def record_outcome(self, arm_key: str, reward: float,
                        platform: str | None = None) -> None:
        """Push a real outcome into the arm's distribution."""
        reward = float(reward)
        self._update_arm(arm_key, reward)
        self._record_platform(arm_key, platform, reward)
        self.data["reward_log"].append({
            "ts": _now_iso(), "arm": arm_key, "reward": round(reward, 4),
            "platform": platform,
        })
        self._trim("reward_log")
        self._append_event("reward", arm=arm_key, w=round(reward, 4),
                           platform=platform)
        self.save()

    def apply_penalty(self, arm_key: str, reason: str, weight: float = None,
                       platform: str | None = None) -> float:
        """Penalize the arm behind a mistake (failure / low retention / spam)."""
        w = float(weight if weight is not None else self.cfg["penalty_failure"])
        self._update_arm(arm_key, -abs(w))
        self._record_platform(arm_key, platform, -abs(w))
        self.data["penalty_log"].append({
            "ts": _now_iso(), "arm": arm_key, "reason": reason, "penalty": w,
            "platform": platform,
        })
        self._trim("penalty_log")
        self._append_event("penalty", arm=arm_key, reason=self._sanitize_reason(reason),
                           w=abs(w), platform=platform)
        self.save()
        logger.info("PENALTY applied %s → %s (%.1f) platform=%s",
                    reason, arm_key, w, platform or "-")
        return w

    def apply_reward(self, arm_key: str, reason: str, weight: float = None,
                      platform: str | None = None,
                      content_quality: float = 0.0) -> float:
        """Reward the arm behind a strong output.

        Args:
            content_quality: 0..1 score from script quality gate (viral_intel.score_script).
                             Arms that produce high-quality scripts get a bonus so the
                             bandit learns to favor formulas that consistently produce
                             strong content — not just lucky uploads.
        """
        w = float(weight if weight is not None else self.cfg["bonus_viral"])
        # Quality bonus: scripts scoring >=0.7 get a 15% reward boost so the
        # bandit learns to favor formulas that consistently produce strong content.
        quality_bonus = w * 0.15 if content_quality >= 0.7 else 0.0
        total = abs(w) + quality_bonus
        self._update_arm(arm_key, total)
        self._record_platform(arm_key, platform, total)
        self.data["reward_log"].append({
            "ts": _now_iso(), "arm": arm_key, "reason": reason, "reward": total,
            "platform": platform, "quality_bonus": quality_bonus,
        })
        self._trim("reward_log")
        self._append_event("reward", arm=arm_key, reason=self._sanitize_reason(reason),
                           w=abs(w), platform=platform)
        self.save()
        if quality_bonus > 0:
            logger.info("REWARD(+quality) %s → %s (%.1f + %.2f bonus) platform=%s",
                        reason, arm_key, w, quality_bonus, platform or "-")
        else:
            logger.info("REWARD applied %s → %s (%.1f) platform=%s",
                        reason, arm_key, w, platform or "-")
        return total

    @staticmethod
    def _trim(lst: list, keep: int = 500) -> None:
        if len(lst) > keep:
            del lst[:len(lst) - keep]

    # ── derived reward from platform metrics ──
    @staticmethod
    def reward_from_metrics(m: dict, cfg: dict = None) -> tuple[float, dict]:
        """Map raw platform metrics into (reward, breakdown).

        Delegates to reward.reward_from_dict so retention, completion,
        engagement, views, CTR and voice quality are ALL considered — not
        just views+likes.
        """
        try:
            from reward import reward_from_dict
            return reward_from_dict(m)
        except Exception:
            views = float(m.get("views", 0) or 0)
            r = round(min(5.0, math.log10(views + 1) / 6.0 * 3.0), 3)
            return r, {"fallback": True, "reward": r}

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
        self._append_event("attribution", video_id=str(video_id),
                           arm_key=arm_key, platform=platform, title=title)
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
        reward, breakdown = self.reward_from_metrics(metrics)
        platform = a.get("platform")
        a["credited"] = True
        a["metrics"] = metrics
        a["reward"] = reward
        a["breakdown"] = breakdown
        a["credited_at"] = _now_iso()
        self._append_event("credit", video_id=vid, reward=round(reward, 4))
        if reward > 0.5:
            self.apply_reward(a["arm_key"], f"metrics:{vid[:12]}", reward, platform=platform)
        else:
            self.apply_penalty(a["arm_key"], f"low_metrics:{vid[:12]}",
                               self.cfg["penalty_low_retention"], platform=platform)
        return reward

    # ── post-volume guards (2026: consistency > bursts) ──
    def can_post(self, platform: str, max_daily: int = 3,
                 min_gap_hours: float = 4.0) -> tuple:
        """Return (allowed, reason). Enforces daily cap + min gap between posts.

        V2.7 fail-safe: with a broken/unusable store there is no memory of
        recent posts — posting is BLOCKED rather than risking double posts.
        """
        if not self.store_ok:
            return (False,
                    "ML store broken — posting blocked (run scripts/repair_data_files.py)")
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
        self._append_event("post", platform=platform, date=today)
        self.save()

    # ── publish-slot claims (prevents two runs targeting the same peak) ──
    # The double-post bug: two runs (cron + manual dispatch) both compute the
    # SAME next peak and both schedule publishAt there → 2 videos go public at
    # the same minute. The ledger below makes each run CLAIM its slot in the
    # shared store BEFORE uploading, and next_peak() skips already-claimed
    # times. Claims older than 25h are pruned (publishAt window is <24h).
    CLAIM_TTL_HOURS = 25

    def _prune_claims(self) -> None:
        now = datetime.now(timezone.utc)
        claims = self.data.get("publish_claims", {})
        for plat in list(claims):
            for iso in list(claims[plat]):
                try:
                    dt = datetime.fromisoformat(iso)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    stale = (now - dt).total_seconds() > self.CLAIM_TTL_HOURS * 3600
                except ValueError:
                    stale = True
                if stale:
                    del claims[plat][iso]
            if not claims[plat]:
                del claims[plat]

    def claimed_peaks(self, platform: str) -> list:
        """Future publish slots already claimed for a platform (tz-aware)."""
        self._prune_claims()
        now = datetime.now(timezone.utc)
        out = []
        for iso in self.data.get("publish_claims", {}).get(platform, {}):
            try:
                dt = datetime.fromisoformat(iso)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt > now:
                    out.append(dt)
            except ValueError:
                continue
        return out

    def claim_publish(self, platform: str, publish_at, run_id: str = None) -> tuple:
        """Reserve a publish slot BEFORE uploading. Returns (ok, reason).

        A slot already claimed by a DIFFERENT run_id is refused, so two runs
        can never schedule the same publish minute.
        """
        if not self.store_ok:
            return False, "ML store broken — cannot claim publish slot"
        if isinstance(publish_at, str):
            try:
                publish_at = datetime.fromisoformat(publish_at)
            except ValueError:
                return False, f"bad publish_at: {publish_at}"
        if publish_at.tzinfo is None:
            publish_at = publish_at.replace(tzinfo=timezone.utc)
        iso = publish_at.astimezone(timezone.utc).isoformat()
        self._prune_claims()
        claims = self.data.setdefault("publish_claims",
                                      {}).setdefault(platform, {})
        other = claims.get(iso)
        if other and other.get("run_id") != run_id:
            return False, (f"slot {iso} already claimed by run "
                           f"{other.get('run_id')}")
        claims[iso] = {"run_id": run_id, "ts": _now_iso()}
        self._append_event("claim", platform=platform, iso=iso, run_id=run_id)
        self.save()
        return True, "claimed"

    def release_claim(self, platform: str, publish_at) -> None:
        """Free a claim when the upload failed (don't hold a slot we didn't use)."""
        if isinstance(publish_at, str):
            try:
                publish_at = datetime.fromisoformat(publish_at)
            except ValueError:
                return
        if publish_at.tzinfo is None:
            publish_at = publish_at.replace(tzinfo=timezone.utc)
        iso = publish_at.astimezone(timezone.utc).isoformat()
        self.data.get("publish_claims", {}).get(platform, {}).pop(iso, None)
        self.save()

    # ── dedup & variation ──
    def dedup_guard(self, script_text: str, hook: str = "") -> dict:
        """Return verdict: {'allowed': bool, 'reason': str}.

        Blocks exact re-posts and enforces minimum variation vs recent videos.
        V2.7 fail-safe: with a broken store there is no dedup history — we
        BLOCK rather than risk re-posting the same content.
        """
        if not self.store_ok:
            return {"allowed": False,
                    "reason": "ML store broken — dedup unavailable, blocking to avoid re-posts"}
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
        self._append_event("video", rec=rec)
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
        self._append_event("health_failure", platform=platform,
                           reason=self._sanitize_reason(reason))
        self.save()

    def report_success(self, platform: str) -> None:
        h = self.data["health"].setdefault(platform, {"failures": 0, "healthy": True})
        h["failures"] = 0
        h["healthy"] = True
        h["last_check"] = _now_iso()
        self._append_event("health_success", platform=platform)
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
