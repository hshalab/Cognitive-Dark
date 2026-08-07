#!/usr/bin/env python3
"""
Warm-start the ML bandit with curated priors (idempotent; never overwrites
real per-video evidence already collected).

Run:
  PYTHONPATH=src python scripts/seed_ml_priors.py            # apply
  PYTHONPATH=src python scripts/seed_ml_priors.py --check    # just report
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from ml_engine import LearningSystem
from seed_priors import SEED_PRIORS, PRIOR_VERSION


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report only, don't write")
    args = ap.parse_args()

    ml = LearningSystem()

    # Count arms with real (non-seed) evidence
    real = [k for k, a in ml.data["arms"].items() if a.get("n", 0) > 0]
    seeded = [k for k, a in ml.data["arms"].items() if a.get("seeded")]

    print("=" * 60)
    print(f"ML store: {ml.store_path}")
    print(f"Prior version (available): {PRIOR_VERSION}")
    print(f"Prior applied (store):     {ml.data.get('prior_version', '—')}")
    print(f"Arms total:                {len(ml.data['arms'])}")
    print(f"Arms with any n:           {len(real)}")
    print(f"Arms already seeded:       {len(seeded)}")
    print("=" * 60)

    if args.check:
        # Show top-10 arms by prior mean (from our curated set, day-agnostic)
        print("\nPrior strength by (pillar, hook) — top 12:")
        ranked = sorted(SEED_PRIORS.items(), key=lambda kv: kv[1][0], reverse=True)[:12]
        for (pillar, hook), (mean, n) in ranked:
            print(f"  {mean:.2f}  n={n}  {pillar:22} / {hook}")
        return

    result = ml.apply_seed_priors()
    print(f"\n✅ {result['arms_seeded']} arms seeded.")
    print("   (Arms with real video evidence were NOT touched.)")
    print("\nTop 10 arms the bandit will lean toward first:")
    for t in ml.best_formulas(10):
        print(f"  mean={t['mean']:.2f} n={t['n']:>2}  {t['pillar']:22} / {t['hook_style']}")


if __name__ == "__main__":
    main()
