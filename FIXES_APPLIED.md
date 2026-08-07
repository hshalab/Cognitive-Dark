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
