# Fixes Applied (2026-08-06)

## Critical
1. Resolved committed git merge conflicts in:
   - `data/learning_store.json` — kept the rich learning/history side instead of the wiped empty store.
   - `data/monetization_progress.json` — kept the newer timestamp and valid structure.
2. Fixed `NameError` in `src/video_builder.py` by importing `concatenate_audioclips` for short-music looping.
3. Added `onnxruntime` to `requirements.txt` for the documented Kokoro ONNX TTS path.

## Reliability
4. Replaced stream-copy scene concat with a normalized re-encode in `src/video_builder.py`; this avoids frozen/corrupt videos when per-scene x264 parameters differ.
5. Added `check=True` to ffprobe duration extraction and `check=False` where command success is intentionally inspected.
6. Fixed `scheduler.validate_gap()` to import/use `datetime.timezone` directly and safely handle naive datetimes.
7. Fixed `ml_engine.record_post()` stale-date pruning; the old loop contained only `pass`.

## Code quality
8. Added `ruff.toml` and fixed all lint issues across `src/`, `scripts/`, `config/`, and `tests/`.
9. Removed dead/confusing helper code, semicolon statement chains, and unsafe broad cleanup patterns where appropriate.
10. Normalized timezone usage to Python 3.11-compatible `datetime.timezone.utc` (GitHub Actions uses Python 3.11).

## Tests / CI
11. Added 36 tests covering:
    - ML bandit rewards/penalties, attribution, dedup, daily caps, quarantine recovery, token sanitization.
    - SEO titles/descriptions/tags/chapters.
    - DST-aware scheduler and cron generation.
    - YouTube/Facebook credential and publish-time conversion.
    - Procedural visuals and caption chunking.
12. Added `.github/workflows/ci.yml` to validate JSON, run Ruff, and run Pytest automatically.

## Additional fixes (second pass)
13. `scripts/manage_uploads.py`:
    - Removed Python-3.12-only `from datetime import UTC` (CI runs Python 3.11 → would crash).
    - Replaced eager `_service()` + raw `sys.argv` with proper `argparse`, so `--help` works without credentials and usage matches `video_manager.yml` inputs (`list | keep_latest | spread` + keep_count).
    - Made `zip(items, peaks)` length-safe (`strict=False`).
14. Swept the ENTIRE codebase (`src/`, `scripts/`, `tests/`) and converted every `datetime.UTC` / `from datetime import UTC` to `datetime.timezone.utc` for Python 3.11 compatibility (Ruff's `UP017` had auto-rewritten several; that rule is now ignored in `ruff.toml`).
15. Verified Kokoro-ONNX API matches the installed package (`Kokoro(model, voices)` + `create(text, voice, speed, lang)`), and confirmed TTS voice/speed defaults (am_fenrir @ 1.08x) are consistent between `tts_engine.py` and `config/settings.py`.
16. Confirmed every script (`channel_inventory`, `deep_repair`, `platform_audit`, `social_manager`, `generate_music`, `fetch_metrics`) imports and runs without credentials (graceful skip), and `deep_repair.py` actually heals the ML store.
17. All four GitHub workflow YAML files re-validated.

## Verification
- `python -m compileall src scripts config tests ready_scripts` ✅
- `python -m json.tool` on every `.json` (data + ready_scripts) ✅
- `ruff check src scripts config tests` → All checks passed ✅
- `PYTHONPATH=src pytest -q tests` → 36 passed ✅
- `PYTHONPATH=src python src/main.py --selftest` → all 5 stages pass + renders real MP4 ✅
- Kokoro-ONNX constructor / `create()` signature matches code ✅

## V2.7 — Double-Post & Data-Integrity Fix Pass (2026-08-10)

Observed production bug: **2 videos went public at the same time and the ML
"didn't know" about it.** Root causes found by live repro of the code:

**Root cause 1 — committed conflict markers corrupted the ML store.**
`data/learning_store.json` + `data/monetization_progress.json` contained
`<<<<<<< Updated upstream / ======= / >>>>>>> Stashed changes` markers
(committed by the old CI `git pull --rebase --autostash || true` +
`git add -f` pattern). `LearningSystem._load()` silently returned `{}` on
parse failure → every run started with ZERO memory → `can_post()` min-gap /
daily-cap and `dedup_guard()` had no history to check → double posts were
possible and the bandit never actually learned.

**Root cause 2 — two runs picked the same publish peak.**
`PlatformScheduler.next_peak()` is deterministic; a cron run + a manual
dispatch in the same window both compute the SAME next peak and schedule
`publishAt` for the same minute. The min-gap guard checks *upload* time, not
*publish* time, so it never caught this.

### Fixes applied
1. **`scripts/repair_data_files.py` (new)** — scans `data/*.json` for conflict
   markers / invalid JSON and restores the newest CLEAN version from git
   history (used it to recover both broken files; all 3 data files valid now).
2. **`src/ml_engine.py` — fail-safe store.** `_load()` never silently returns
   `{}`: corrupt main file → tries `.bak` snapshot → if both broken,
   `store_ok=False` and **every posting guard BLOCKS publishing** until the
   store is repaired. `save()` keeps a `.bak` and REFUSES to overwrite a
   corrupted store. Missing store (fresh install) still = fresh start.
3. **`src/ml_engine.py` — publish-slot claim ledger.** New `claim_publish() /
   release_claim() / claimed_peaks()` persist claimed `publish_at` slots in
   the store (25h TTL). Two runs can no longer claim the same minute.
4. **`src/scheduler.py` — `next_peak(now, reserved)`.** Skips already-claimed
   peaks (exact-hour match, 30-min tolerance), scanning up to 8 days.
5. **`src/main.py`** — claims the slot BEFORE upload, retries next-free peak
   on collision, releases the claim on failure, and sanitizes crash-journal
   errors (no raw exception strings that could embed access tokens).
6. **CI — single writer + conflict-safe commit.** `daily_pipeline.yml`: the
   separate `metrics-sync` job (the second writer that caused the race) is
   merged into the build job; the commit step refuses to push conflict
   markers / invalid JSON and turns the run RED instead of committing
   corruption. Same guard in `war_mode.yml`; `ci.yml` validation now also
   rejects conflict markers.
7. **`.gitignore`** — `data/*.bak` snapshots never committed.

### Verification
- `python scripts/repair_data_files.py --check` → all data files valid ✅
- `PYTHONPATH=src pytest -q tests` → 78 + 7 new = **85 passed** ✅
- `ruff check src scripts config tests` → All checks passed ✅
