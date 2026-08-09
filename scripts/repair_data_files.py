#!/usr/bin/env python3
"""
Cognitive Dark — Data File Repair Tool (V2.7).

Fixes committed data corruption in `data/*.json` caused by CI bot conflicts:

  • git conflict markers (<<<<<<< Updated upstream / ======= / >>>>>>>)
    that get auto-committed by the workflow's `git pull --rebase --autostash`
    + `git add -f` pattern — this is exactly what broke learning_store.json
    and monetization_progress.json on 2026-08-09.
  • Any other invalid JSON (truncated file, bad escaping, ...).

How it repairs (safest order):
  1. For each broken file, walk GIT HISTORY (newest → oldest) and restore
     the most recent version that is VALID JSON — your ML memory comes back
     without hand-editing.
  2. If no clean version exists in history, the file is left untouched and
     reported — never half-repaired.

Usage:
  python scripts/repair_data_files.py          # dry-run: report only, no writes
  python scripts/repair_data_files.py --apply  # restore broken files in place
  python scripts/repair_data_files.py --check  # validate only; exit 1 if broken
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

MARKER_RE = re.compile(r"^(<<<<<<<|=======|>>>>>>>)", re.MULTILINE)


def is_clean(text: str) -> bool:
    """True if the text is valid JSON AND has no conflict markers."""
    if MARKER_RE.search(text):
        return False
    try:
        json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return False
    return True


def git_clean_version(rel_path: str) -> str | None:
    """Return the newest clean content for rel_path from git history, or None."""
    try:
        commits = subprocess.run(
            ["git", "log", "--format=%H", "--", rel_path],
            cwd=ROOT, capture_output=True, text=True, timeout=60, check=False)
    except Exception:
        return None
    for commit in commits.stdout.split():
        commit = commit.strip()
        if not commit:
            continue
        try:
            out = subprocess.run(
                ["git", "show", f"{commit}:{rel_path}"],
                cwd=ROOT, capture_output=True, text=True, timeout=60, check=False)
        except Exception:
            continue
        if out.returncode == 0 and is_clean(out.stdout):
            return out.stdout
    return None


def repair(apply: bool) -> tuple[int, int, list[str]]:
    """Scan + optionally fix. Returns (broken, fixed, notes)."""
    broken, fixed, notes = 0, 0, []
    for path in sorted(DATA_DIR.glob("*.json")):
        rel = path.relative_to(ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            notes.append(f"{rel}: unreadable ({exc})")
            continue
        if is_clean(text):
            continue
        broken += 1
        why = "conflict markers" if MARKER_RE.search(text) else "invalid JSON"
        clean = git_clean_version(rel)
        if clean is None:
            notes.append(f"❌ {rel}: {why} — NO clean version in git history; manual fix needed")
            continue
        if apply:
            path.write_text(clean, encoding="utf-8")
            # fresh-validate what we wrote
            if is_clean(path.read_text(encoding="utf-8")):
                fixed += 1
                notes.append(f"✅ {rel}: {why} → restored from git history "
                             f"({len(clean)} bytes, valid JSON)")
            else:
                notes.append(f"⚠️  {rel}: restore did not validate — inspect manually")
        else:
            notes.append(f"🔎 {rel}: {why} — clean version found in history "
                         f"(run with --apply to restore)")
    return broken, fixed, notes


def check() -> tuple[int, list[str]]:
    broken, notes = 0, []
    for path in sorted(DATA_DIR.glob("*.json")):
        rel = path.relative_to(ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            broken += 1
            notes.append(f"❌ {rel}: unreadable ({exc})")
            continue
        if not is_clean(text):
            broken += 1
            why = "conflict markers" if MARKER_RE.search(text) else "invalid JSON"
            notes.append(f"❌ {rel}: {why}")
        else:
            notes.append(f"✓ {rel}: valid")
    return broken, notes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="restore broken files from git history (default: report only)")
    ap.add_argument("--check", action="store_true",
                    help="validate only; exit 1 if any file is broken")
    args = ap.parse_args()

    if args.check:
        broken, notes = check()
        for n in notes:
            print(n)
        print(f"\n{broken} broken file(s)" if broken else "\nAll data files valid ✓")
        return 1 if broken else 0

    broken, fixed, notes = repair(apply=args.apply)
    for n in notes:
        print(n)
    print(f"\nSummary: {broken} broken, {fixed} fixed"
          + ("" if args.apply else " (dry-run — rerun with --apply to write)"))
    return 1 if broken and not fixed else 0


if __name__ == "__main__":
    sys.exit(main())
