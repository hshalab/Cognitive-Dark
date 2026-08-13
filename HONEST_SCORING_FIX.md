# 🩺 V3.4/V3.5/V3.6 — HONEST SCORING + INDEPENDENT GATE + REALITY SWEEP

## 🆕 V3.6 — Reality Sweep (2026-08-13): "ab kuch bhi fabricated nahi"

Owner ka sawal tha: *"Reality ki base par kuch rehta to nahi hai?"* Full sweep
mein 5 aur cheezein milin jo fabricated/assumed thin — sab fix:

1. **YT/FB/IG retention GUESS ko "measured" bataya ja raha tha** —
   `fetch_metrics.py` ne like-ratio se `0.15 + like*8 + comment*20` formula
   se retention BANA kar reward function ko diya (35% weight + viral bonus!)
   → bandit fabricated data se seekh raha tha. Ab har guess par
   `retention_estimated: True` flag hai, reward.py mein: half weight, 0.5
   cap, viral bonus band, quality gate "unknown". FB sirf REAL watch-time se
   retention bhejta hai (warna kuch nahi); IG fabricated retention poori
   tarah hata di (saves/shares real metrics hi bheje jate hain).

2. **Missing-data par penalty** — `credit_video` mein retention na ho to
   `low_metrics` ka -1.0 penalty lag jata tha → data ki kami formula ki
   ghalti nahi. Ab incomplete data = na reward na penalty (seekha hi nahi
   jata), sirf COMPLETE real metrics arm train karte hain.

3. **Fuzzy growth attribution** — channel ke subs/followers growth ko
   "recent arms" par bonus diya jata tha. Growth kis VIDEO se aayi koi nahi
   jaanta — ye reward reality par based nahi tha. `apply_growth_rewards`
   ab intentional no-op hai; sirf video-level EXACT attribution rehti hai.

4. **Playbook ke fake PASSes** — `algorithm_playbook.py` mein "reply top
   comment" aur "reply within 1h" hamesha `True` thay → playbook score
   hamesha inflated. Ab manual items `status=manual`, `ok=None` — score
   sirf machine-verifiable checks se banta hai. Mission Control ke static
   "✅ ON (built-in)" claims bhi honest banaye: ⚙️ config + gate verify.

5. **Committed store saaf kiya** — `data/learning_store.json` migrate ho
   gaya: 191 arms ke double-counted priors un-merge, 5 fake "published"
   rewards purge. Ab store mein sirf REAL outcomes hain (bache hue n=2
   wale arm ke dono outcomes event log mein real hain: IG upload fail +
   low_metrics). Migration ab ONE-TIME hai (`prior_dedup_migrated` marker) —
   dobara load par real data subtract nahi hota. Event-diary replay bhi
   legacy `<platform>_published` rewards skip karta hai — rebuild ke baad
   fake rewards wapas nahi aa sakte.

Naye tests: `tests/test_honesty.py` (V3.6 section) — estimated-vs-measured
retention discount, incomplete-data no-learning, manual playbook checks,
growth-rewards no-op, curated-prior flag, migration idempotency, replay
skip. **182 tests pass.**

---

# 🩺 V3.4 — HONEST SCORING FIX (2026-08-13)

**Masla:** system khud ko jhooti tareef deta tha. Hook kharab ho to bhi "strong"
score, data na ho to bhi "quality passed", views 0 hon to bhi "A+ viral-ready".
Natija: ML weak formulas ko repeat karta raha aur teeno platforms (YT/FB/IG)
ka nuqsan hota raha.

**Fix:** ab system sach bolta hai. Weak = weak, no-data = unknown, publish =
performance NAHI. Neeche har jhoot aur us ka ilaaj:

---

## 1. 🧮 Seed priors DOUBLE-COUNT ho rahe thay (sab se bara ML bug)

`apply_seed_priors()` priors ko `n/rewards/sum_sq` mein fake observations ki
tarah likhta tha, AUR `prior_n/prior_mean` alag se rakhta tha. `posterior_from_arm()`
dono ko jodta tha → **har prior 2x weight** ke saath chalta tha:

- Real outcome ka asar **aadha** reh jata tha (system asli data se seekhta hi nahi tha)
- Seeded arms `n≥7` dikhte thay → "cold arm" exploration branch **kabhi fire nahi hoti thi**
- Bandit apni hi ghalat assumptions par overconfident ho kar exploit karta rahta tha

**Fix (`ml_engine.py`, `bandit.py`):**
- Priors ab sirf `prior_n/prior_mean` mein rehte hain; `n/rewards/sum_sq` = sirf REAL outcomes
- Legacy stores ke liye one-time migration: merged prior exact subtract ho kar real observations recover ho jate hain (`prior_dedup_migrated`)
- `best_formulas()` ab `n_real` (asli data) aur `n_eff` (prior+data) alag batata hai
- Event-log replay (diary) bhi naye schema mein rebuild karta hai

**Test:** `test_prior_never_double_counted`, `test_posterior_counts_prior_once`,
`test_legacy_merged_prior_is_unmerged_on_load`, `test_seeded_arms_are_not_experienced`

---

## 2. 🎁 Publish par SELF-REWARD (bandit ki jhooti tareef)

Har successful upload ko `+1.0 bonus_consistent` + self-scored quality bonus milta
tha. Matlab: **upload karo = reward**, chahe views 0 hon. 30 uploads = 30 rewards →
har formula "top performer" ban jata tha. Real analytics (fetch_metrics) ke penalties
is jhoot ke samne be-asar thay.

**Fix:**
- `config/settings.py`: `bonus_consistent = 0.0` — publish karna performance nahi hai
- `main.py`: publish par log sirf "📊 NO reward yet — real metrics decide"
- `ml_engine.apply_reward()`: weight 0 ho to observation record hi nahi hota (n inflate nahi hota)
- **One-time self-praise purge:** legacy store ke saare `*_published` reward entries
  arm stats se exact subtract (`self_praise_purged`). Event diary intact rehti hai.

**Test:** `test_zero_weight_reward_does_not_inflate_n`, `test_self_praise_rewards_are_purged_on_load`

---

## 3. 🔇 Recency penalty & pillar weights SILENT NO-OP thin

`choose_strategy()` mein recency penalty (variety guard) aur Strategy Director ke
pillar weights **argmax ke BAAD** lagte thay → wo sirf DISPLAY score ko badalte thay,
**selection par zero asar**. Matlab "aik pillar 3 baar repeat mat karo" ka guard
production mein kabhi kaam nahi karta tha, aur per-platform learning bhi blend
hoti thi chunao ke baad.

**Fix (`ml_engine.choose_strategy`):** penalties/weights/blend ab HAR candidate par
argmax se PEHLE lagte hain. Variety guard ab asal mein kaam karta hai.

**Test:** `test_recency_penalty_actually_steers_choice`

---

## 4. 📊 Reward gate: "missing data = PASSED" wala jhoot

`reward.py` mein `quality_gate_passed = retention >= 0.70 or retention == 0.0` —
matlab jab retention ka **koi data hi nahi** tha (0.0), gate "PASSED" bol deta tha.
Is ke ilawa `voice_rating` default **1.0** tha — har video ko bina kisi measurement
ke FREE perfect TTS score milta tha (7% weight hamesha full marks).

**Fix (`reward.py`):**
- Missing retention → `quality_gate_status = "unknown"`, `passed = False`
- `data_complete` flag batata hai ke asli measurement hui bhi thi ya nahi
- `voice_rating = None` → neutral 0.5 (koi evidence nahi = na perfect, na zero)

**Test:** `test_missing_retention_does_not_pass_gate`, `test_voice_rating_missing_is_neutral_not_perfect`

---

## 5. 🎯 Scorers inflated bases — weak content "passable" dikhta tha

| Scorer | Pehle (jhoot) | Ab (sach) |
|---|---|---|
| `score_hook` | base 0.55 + trivial power words ("you/your/they/this" har hook mein hote hain) | base 0.30 + sirf STRONG power words + fragment detection + concrete-anchor bonus |
| `score_title_ctr` | base 0.50 — koi bhi title "C — average" se neeche ja hi nahi sakta tha | base 0.25; keyword ab REAL boost deta hai; D-grade ab genuine weak titles ko milta hai |
| `score_script` | anchors mein "day/week/call/text/phone" — har script free "anchor ✅" | sirf real evidence ($, case, study, trial, transcript, digits) |
| `analyze_content_density` | base 0.30 + generic markers | base 0.10 + strict markers, per-scene issues clean |
| `score_title` (viral formulas) | no-match floor 0.4 | floor 0.2 — "koi formula nahi" weak hai, neutral nahi |
| `virality_index` | own videos ko APNE HI scorer se score karta tha → hamesha "A+ viral-ready" | own performance ab REAL arm rewards se aati hai; bina data ke index **D — early stage** kehta hai |
| `score_hook_retention` | base 0.50 | base 0.25 |

Naye rules:
- **Hook gate** (script_generator): 0.60 honest scale (pehle 0.85 inflated scale par)
- **Fragment detection:** "Stop letting them" jaisa 3-lafzi adhoora hook ab FAIL hota hai
- **Hook fallback:** curated pillar hooks pehle, complete boosted hooks baad mein —
  aur replacement tabhi jab naya hook GENUINELY zyada score kare
- **CTR title boost:** sirf <0.55 par trigger, sirf tab replace jab variant sach mein behtar ho
- `keyword_found` ab FB/IG branches mein defined hai (pehle NameError hota tha)

**Tests:** `test_weak_hook_scores_low`, `test_fragment_hook_is_not_strong`,
`test_weak_title_scores_low_ctr`, `test_ctr_score_works_for_all_platforms`,
`test_fluff_script_fails_gate`, `test_concrete_script_passes_gate`,
`test_virality_index_honest_without_performance`

---

## 6. 🎬 Video render bugs (har video mein dikhte thay)

1. **CTA end-card ka text INVISIBLE tha** — text y=1780 par draw hota tha jabke
   overlay canvas sirf 180px lamba hai → har video ke end par sirf **khali dark box**
   dikhta tha. Fix: text ab overlay ke andar local coordinates par draw hota hai
   (verified: 5019 yellow text pixels). Wording bhi "Follow" hai (sirf "Subscribe"
   FB/IG par ghalat lagta tha).
2. **Thumbnail squish** — landscape frame seedha `1080x1920` resize ho kar bheenga
   ho jata tha. Fix: center cover-crop (`_cover_resize`).

**Verification:** `python src/main.py --selftest` (real MP4 render) + overlay
pixel-check pass.

---

## 7. 📝 Titles — keyword stuffing aur toota grammar

- `"Hook | Psychology Facts"` pipe-append hata diya (bot-pattern, CTR giraata tha)
- Random power-word append (`": Truth"`) hata diya — double-colon titles ("Hook: Truth: Keyword") khatam
- CTR variants ab grammatical hain (`_cap`, `_trunc_words` word-boundary par) —
  "3 why Smart People..." aur "12 Signs of micro-Expressions Interviewe" jaise
  toote titles ab possible nahi
- Keyword duplication guard ("Lie Detection: Lie Detection" nahi banega)

---

## 8. 🧾 Monetization tracker ke fabricated defaults

`youtube: subs=7, facebook: followers=523` hardcoded "asli data" ban kar % 
calculate karte thay. Ab default 0 hai aur real values sirf `fetch_metrics.py`
se aati hain.

---

## 9. 🔧 Aur bhi

- `autonomous_brain` WAR_MODE par `KeyError: ucb_score` crash — fix (`score` key)
- 9 Ruff lint errors (dead vars, pointless comparisons) — clean
- `scripts/repair_all_videos.py` ka dead `is_shorts_ready` check ab summary mein
  "Not Shorts-ready" counter ban gaya
- `ml_diagnostics` / `strategy_director` / `human_layer` ab priors ko "experience"
  nahi maante — sirf real outcomes se maturity/intuition banti hai

---

## ✅ Verification

```bash
PYTHONPATH=src python -m pytest tests -q      # 143 passed
ruff check src scripts config tests            # All checks passed
python src/main.py --selftest                  # real MP4 render ✅
python src/main.py --dry-run                   # full pipeline ✅
```

Naya suite: **`tests/test_honesty.py`** — ye 15 tests har jhoot ko lock karte hain.
Agar koi future change inhein tore to samjho system dobara khud ko dhoka dene laga hai.

## 🔄 Aage kya hoga (owner ke liye)

1. **Agla pipeline run** migrate karega: legacy store ke merged priors un-merge
   honge aur fake publish-rewards purge honge (one-time, automatic, idempotent).
2. **`fetch_metrics.py` daily chalna zaroori hai** — ab ye hi reward ka SOLE source
   hai. Us ke bagair bandit kisi ko reward nahi dega (jo sahi hai — par is ka matlab
   hai metrics workflow on hona chahiye).
3. Pehle kuch din index **"D — early stage"** dikhayega — ye kharab nahi, **sach** hai.
   Jaise real views/retention aate jayenge, index aur grades asli data par uthte hain.
4. Mission Control (`scripts/mission_control.py`) ab real-data vs belief ka farq
   bhi report karega (`n_real` / `cold_arms`).
