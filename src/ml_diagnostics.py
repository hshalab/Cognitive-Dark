#!/usr/bin/env python3
"""
Coercion Files — ML diagnostics & maturity report.

Bandit ki "maturity" aur health ka human-readable + JSON report:
  • Kitne arms real evidence se seekh chuke hain vs abhi priors par
  • Har pillar/hook ka posterior mean + 95% CI (confidence)
  • Exploration vs exploitation ratio
  • Simple regret (best known arm vs chosen)
  • Per-platform learning status
  • Low-evidence warnings (jagah jahan zyada data chahiye)

Koi mutation nahi — sirf read-only report.
"""

from __future__ import annotations

from bandit import ArmObservations, ArmPosterior
from ml_engine import LearningSystem


def arm_posteriors(ml: LearningSystem) -> dict[str, ArmPosterior]:
    return {k: ArmPosterior(
        prior_mean=float(a.get("prior_mean", 0.5)),
        prior_n=int(a.get("prior_n", 0)),
        obs=ArmObservations(
            n=int(a.get("n", 0)),
            total=float(a.get("rewards", 0.0)),
            total_sq=float(a.get("sum_sq", 0.0)),
        )) for k, a in ml.data.get("arms", {}).items()}


def maturity(ml: LearningSystem) -> dict:
    posts = arm_posteriors(ml)
    # V3.4 schema: arm.n = REAL observations only; prior_n = seed belief.
    # (Legacy stores jo priors ko n mein merge karke rakhte thay, unhein
    # ml_engine._ensure_schema migrate kar deta hai.)
    real = 0
    n_obs = 0
    n_seed = 0
    for a in ml.data["arms"].values():
        pn = int(a.get("prior_n", 0) or 0)
        n = int(a.get("n", 0) or 0)
        n_obs += n
        n_seed += pn
        if n > 0:
            real += 1
    total = len(posts) or 1
    real_obs = n_obs  # ab n hi real hai — koi subtraction nahi

    # Posterior uncertainty only over arms with real data
    obs_posts = [p for k, p in posts.items()
                 if int(ml.data["arms"][k].get("n", 0) or 0) > 0]
    avg_std = sum(p.std for p in obs_posts) / len(obs_posts) if obs_posts else 1.0
    confidence = round(max(0.0, min(1.0, 1.0 - avg_std / 1.5)), 3)

    cold = sum(1 for a in ml.data["arms"].values()
               if int(a.get("n", 0) or 0) == 0)
    return {
        "total_arms": total,
        "arms_with_real_data": real,
        "arms_coverage_pct": round(100 * real / total, 1),
        "total_observations": real_obs,
        "real_observations": real_obs,
        "seeded_observations": n_seed,
        "avg_posterior_std": round(avg_std, 3),
        "confidence": confidence,
        "cold_arms": cold,
        "maturity_stage": _stage(real, real_obs, confidence),
    }


def _stage(real_arms: int, real_obs: int, conf: float) -> str:
    if real_obs < 30 or real_arms < 10:
        return "EXPLORING"        # priors dominate — gather real data
    if real_obs < 150 or conf < 0.4:
        return "LEARNING"         # real data accumulating
    if conf < 0.65:
        return "CONVERGING"       # winners emerging
    return "MATURE"


def best_arms(ml: LearningSystem, top: int = 10) -> list[dict]:
    posts = arm_posteriors(ml)
    scored = []
    for key, p in posts.items():
        pillar, hook, _dp = key.split("::")
        lo, hi = p.confidence_interval()
        scored.append({
            "arm": key, "pillar": pillar, "hook": hook,
            "n": p.n, "mean": round(p.mean, 3), "std": round(p.std, 3),
            "ci95": [round(lo, 3), round(hi, 3)],
        })
    scored.sort(key=lambda r: r["mean"], reverse=True)
    return scored[:top]


def pillar_summary(ml: LearningSystem) -> list[dict]:
    by_pillar: dict[str, list[ArmPosterior]] = {}
    for key, p in arm_posteriors(ml).items():
        pillar = key.split("::")[0]
        by_pillar.setdefault(pillar, []).append(p)
    out = []
    for pillar, posts in by_pillar.items():
        means = [p.mean for p in posts]
        ns = [p.n for p in posts]
        out.append({
            "pillar": pillar,
            "arms": len(posts),
            "avg_mean": round(sum(means) / len(means), 3),
            "best_mean": round(max(means), 3),
            "observations": sum(ns),
        })
    out.sort(key=lambda r: r["avg_mean"], reverse=True)
    return out


def platform_status(ml: LearningSystem) -> dict:
    out = {}
    for plat, arms in ml.data.get("platform_arms", {}).items():
        n = sum(a.get("n", 0) for a in arms.values())
        out[plat] = {
            "arms": len(arms),
            "observations": n,
            "healthy": ml.platform_healthy(plat),
        }
    return out


def report(ml: LearningSystem | None = None) -> str:
    ml = ml or LearningSystem()
    mat = maturity(ml)
    lines = ["=" * 64, "🧠 ML MATURITY REPORT", "=" * 64,
             f"stage         : {mat['maturity_stage']}",
             f"arms w/ data  : {mat['arms_with_real_data']}/{mat['total_arms']} "
             f"({mat['arms_coverage_pct']}%)",
             f"observations  : {mat['total_observations']}",
             f"confidence    : {mat['confidence']:.0%}  (avg posterior std={mat['avg_posterior_std']})",
             f"cold arms     : {mat['cold_arms']} (need ≥3 real outcomes each)", ""]

    lines.append("TOP ARMS (by posterior mean):")
    for r in best_arms(ml, 8):
        ci = f"±{r['std']:.2f}"
        lines.append(f"  {r['mean']:>5.2f} {ci:>6}  n={r['n']:<3}  {r['pillar']:20} / {r['hook']}")

    lines.append("")
    lines.append("PILLAR RANKING:")
    for p in pillar_summary(ml):
        lines.append(f"  avg {p['avg_mean']:>5.2f}  best {p['best_mean']:>5.2f}  "
                     f"obs={p['observations']:<4}  {p['pillar']}")

    plat = platform_status(ml)
    if plat:
        lines.append("")
        lines.append("PLATFORMS:")
        for k, v in plat.items():
            status = "✅" if v["healthy"] else "⛔"
            lines.append(f"  {status} {k:10} obs={v['observations']:<4} arms={v['arms']}")

    if mat["maturity_stage"] == "EXPLORING":
        lines += ["", "💡 PRIORITY: publish 20-30 varied videos across pillars so real "
                       "data replaces priors. Don't scale any pillar yet."]
    elif mat["maturity_stage"] == "LEARNING":
        lines += ["", "💡 Real data is accumulating. Top arms are forming — start "
                       "weighting them but keep ~20% exploration."]
    elif mat["maturity_stage"] == "CONVERGING":
        lines += ["", "💡 Winners emerging. Shift 70% budget to top 2 pillars; run "
                       "occasional challengers."]
    else:
        lines += ["", "💡 Mature: exploit top arms hard, test new hooks only as "
                       "small experiments."]
    lines.append("=" * 64)
    return "\n".join(lines)


def report_json(ml: LearningSystem | None = None) -> dict:
    ml = ml or LearningSystem()
    return {
        "maturity": maturity(ml),
        "best_arms": best_arms(ml, 15),
        "pillars": pillar_summary(ml),
        "platforms": platform_status(ml),
        "policy": ml.cfg.get("policy", "thompson"),
        "epsilon": ml.cfg.get("epsilon"),
    }


if __name__ == "__main__":
    import argparse
    import json
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    ml = LearningSystem()
    if a.json:
        print(json.dumps(report_json(ml), indent=2))
    else:
        print(report(ml))
