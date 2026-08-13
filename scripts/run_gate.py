#!/usr/bin/env python3
"""Standalone Gate Runner — aakhri build ko dobara judge karta hai.

Pipeline har run ke baad output/gate_payload.json likhti hai (script,
segments, video, packages). Ye script us payload ko dobara gate se
guzarta hai — aap khud dekh sakte hain ke konsa guard kyun pass/fail
hua, aur supervisor ne kya faisla diya.

Usage:
  python scripts/run_gate.py                 # last payload, sab platforms
  python scripts/run_gate.py --mode warn     # sirf report, block nahi
  python scripts/run_gate.py --json          # machine-readable output
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from guards.gate import ReleaseGate

PAYLOAD_PATH = ROOT / "output" / "gate_payload.json"


def main() -> int:
    ap = argparse.ArgumentParser(description="Independent Release Gate runner")
    ap.add_argument("--payload", default=str(PAYLOAD_PATH))
    ap.add_argument("--mode", default=None,
                    help="strict | warn | off (default: env GATE_MODE ya strict)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not Path(args.payload).exists():
        print(f"❌ payload nahi mili: {args.payload}")
        print("   Pehle pipeline chalao (python src/main.py --dry-run) — "
              "wo output/gate_payload.json likhti hai.")
        return 1

    gate = ReleaseGate(mode=args.mode)
    reports = gate.evaluate_from_file(args.payload)

    if args.json:
        print(json.dumps([
            {"platform": r.platform, "released": r.released, "grade": r.grade,
             "verdicts": [v.to_dict() for v in r.verdicts],
             "supervisor": r.supervisor}
            for r in reports], indent=2, ensure_ascii=False))
    else:
        for r in reports:
            print(f"\n═══ {r.platform.upper()} — "
                  f"{'🟢 RELEASED' if r.released else '🔴 HELD'} "
                  f"(grade {r.grade}) ═══")
            for v in r.verdicts:
                icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌",
                        "UNKNOWN": "❓"}.get(v.status, "?")
                print(f"  {icon} {v.guard:<8} {v.status:<7} {v.reason[:110]}")
                if v.fix:
                    print(f"      ↳ fix: {v.fix[:110]}")
            if not r.released:
                print("  SUPERVISOR violations:")
                for viol in r.supervisor.get("violations", []):
                    print(f"     ❌ {viol}")
        print("\nReports: data/gate_report.json + data/gate_report.md")

    return 0 if all(r.released for r in reports) else 2


if __name__ == "__main__":
    sys.exit(main())
