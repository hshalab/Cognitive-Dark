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

## V2.8 — Never-Lose-Memory + Human-Mind Strategy Layer (2026-08-10)

User asked: ML ko memory kabhi na khoyni chahiye, insaan jaisa sochna chahiye,
aur channel growth / sab kuch khud manage karna chahiye. Built & tested:

### 1. Memory can NEVER be lost (3-layer protection + a diary)
- **Append-only event log** (`data/events.jsonl`) — the ML's "diary". Every
  reward, penalty, post, video, attribution, credit, claim, health change and
  seed is appended as one immutable line BEFORE saving. A corrupt store file
  can't erase this — it's append-only.
- **3-layer recovery** in `ml_engine._load()`: main store → `.bak` snapshot →
  **rebuild from event log** (replay = full memory reconstruction). Only if ALL
  three are broken does posting get blocked (fail-safe).
- **Self-heal**: after a rebuild the store is immediately re-written, so the
  next process loads the real file.
- `.bak` snapshots added to `monetization_tracker` and `auto_repair` journal.
- CI validates `.jsonl` + conflict markers everywhere; commit step now persists
  `data/events.jsonl` + `strategy_state.json` + `strategy_notes.md` +
  `health_report.md`.

### 2. Human-mind decision layer (Strategy Director V2.8)
- **Momentum detection**: hot streak (3+ wins in last 4) → exploit winners
  (epsilon ≤ 0.08); slump (3+ losses) → fresh exploration (epsilon ≥ 0.25) +
  volume pulled back (caps −1, gap ≥ 4h) — exactly how a human creator reacts.
- **Variety guard**: same pillar 3x in a row → weight dampened (audience
  boredom protection).
- **Narrative memory** (`data/strategy_notes.md`): every decision written in
  plain language — "kyun kya kar raha hoon" — so the owner can read the ML's
  reasoning like a planner's diary.
- Pillar weights now pushed INTO the ML store so the bandit actually uses them.

### 3. Mission Control (`scripts/mission_control.py` + weekly workflow)
- Read-only weekly "doctor visit": checks ML memory integrity, platform health
  (quarantines), 7-day posting cadence, publish-slot ledger, momentum, and
  monetization progress.
- **GROWTH PLAYBOOK audit** — every 2026 growth lever marked ✅/⚠️/❌ so the
  owner sees exactly which lever to pull (hook 3s, cadence, SEO, cross-post,
  comments, IG linking).
- Outputs `data/health_report.md`; workflow `mission_control.yml` runs Monday
  weekly + manual. Store stays read-only → no CI race (single-writer rule).

### Verification
- 96/96 tests pass (78 + 7 V2.7 + 11 V2.8 new), Ruff clean, YAML valid.
- Live test: corrupt store + .bak, memory fully restored from event diary.

## V2.9 — Algorithm Playbook + Viral Intel (2026 platform optimization)

User wants: 2026 algorithms ke hisaab se har platform fully optimized + ML advance
(learn from viral channels) + fast monetization. Built & tested:

### Viral Intelligence (`src/viral_intel.py` — NEW)
- **8 viral title formulas** (stop_command, question, number, reveal,
  curiosity_gap, warning, case_story) scored from real top-channel titles
  (67+ in competitor_seed.txt) + live YouTube competitor data.
- **Hook scorer** — ≤9 words, pattern-interrupt, power-word check.
- **Virality index** (A+..D) combining niche patterns + own best-video
  fingerprint; **suggestion_card()** injected into the LLM prompt so scripts
  are written toward the strongest current patterns.
- **`pick_title_variant()`** — SEO titles are now scored and the strongest
  viral variant is chosen.

### 2026 Algorithm Playbook (`src/algorithm_playbook.py` — NEW)
- Per-platform 2026 signal checklists (YT: title kw first 100, ≤3 hashtags,
  <60s 9:16; FB: comments-first-hour, 5-8 hashtags, share CTA; IG: saves,
  15-20 hashtags, save-this framing). `audit_package()` scores every upload
  before publishing; `main.py` logs weak spots.

### Live competitor learning (`market_intel.sync_competitor_data`)
- Fetches real top videos for 8 niche queries via YouTube API/OAuth, merges
  into `data/competitor_videos.json` (bounded, deduped) — system learns from
  actual viral channels, not fabricated data. Runs once on first pipeline run.

### Monetization milestones (`monetization_tracker.milestones`)
- Per-platform milestone ladder (YT Tier-1 → YPP → 10M; FB Stars → CMP;
  IG Partner). `update_progress()` now stores `milestones` — always knows the
  NEXT realistic goal + % toward it.

### Wiring
- `script_generator.py`: viral intel card in prompt (never breaks generation).
- `seo.py`: viral-scored title selection.
- `main.py`: virality-index log, competitor sync once, playbook audit per upload.
- `tests/`: +12 (viral_intel, algorithm_playbook).

### Verification
- 108/108 tests pass, Ruff clean, YAML valid.
- Live: virality index B (0.633), top formulas [question, warning, stop_command,
  curiosity_gap]; monetization milestones: YT Tier-1 1.4%, FB CMP 0.0%, IG 0.0%.

### Honest notes
- "Cracking" algorithms isn't real — these are documented 2026 best practices
  + data-driven tuning. Consistency + these signals = fastest legitimate path.
- Monetization speed is bounded by content performance; the system now does
  everything in-code to maximize it. The BIGGEST lever outside code: fix
  Instagram linking (currently 0 posts in 7 days → 1/3 of growth dead) and
  keep daily posting on.

## V3.1 — Engagement Layer (97 views / 0 likes ka ilaaj) (2026-08-10)

User reported: 97 views but 0 likes — weak script/hook. Diagnosis from real
data: whole channel like-rate 0-2% (Shorts benchmark 4-6%) — scripts only
asked "Follow", never like/comment; some hooks weak/terse.

### Fixes
1. **ENGAGEMENT CTAs** — template + LLM (SYSTEM_PROMPT rule 9): natural
   like/comment asks, rotated 60/40 with follow/save CTAs (human mix, har
   video same nahi). Live proof: "If this warning just saved you from a false
   confession, hit like — it shows this to someone who needs it..."
2. **HOOK QUALITY GATE** — script generate hone ke baad `score_hook`; score
   < 0.85 → regenerate (max 3 attempts). 3 attempts ke baad bhi weak →
   documented strong hook override (LLM "case_file #3456" jaisa terse
   replacement). Live: "Why Innocent People Confess" override.
3. **CTA REPAIR** — last scene mein like/comment/follow word nahi → chhota
   engagement scene append (agar scenes < 6).
4. **ENGAGEMENT DOCTOR** (`scripts/analyze_engagement.py` + `engagement_audit`
   action) — YouTube stats fetch; ≥50 views + 0 likes → arm PENALTY; ≥5%
   like-rate → arm REWARD (bandit seekhta hai likes kahan se aate hain).
   Report `data/engagement_report.md`.

### Verification
- 121/121 tests pass, Ruff clean, CI green (`a257e1b`).
- Live audit: 16 public videos; Tinder Swindler 74v/1like (1.4%) — no
  zero-like alerts now; no strong (≥5%) yet — new CTAs need 2-3 weeks.
- Template CTA test: 30 runs → like/comment asks present + follow/save mix.
