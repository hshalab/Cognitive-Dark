# 🛂 Independent Release Gate (V3.5) — Architecture

> **Owner ki requirement:** "Ek independent observer banao jo system par rely
> na kare balke reality observe kare. Ek gate banao jis par har department ka
> alag alag guard ho — script, hook, video quality, voice, caption, FB/YT/IG
> 2026 algorithm ke mutabiq SEO, CTR, views. Video tab tak gate se nahi
> guzregi jab tak SAB guards use pass na karein. Aakhir mein ek supervisor
> jo verify kare ke sab guards ne USA audience ke mutabiq INDEPENDENTLY pass
> kiya."

Yahi banaya gaya hai. Poora system `src/guards/` mein hai.

---

## 1. Architecture

```
                 ┌─────────────────────────────────────────────┐
  producer       │            🛂 RELEASE GATE                   │
  (pipeline) ───►│                                             │      ┌────────┐
                 │  producer self-scores STRIP ho jate hain     │      │ YT/FB/IG│
                 │  (script_quality/hook_score guards tak      │──────►│ upload │
                 │   pahunch hi nahi sakte)                    │      └────────┘
                 │                                             │        sirf jab
                 │  ┌───────────────────────────────────────┐  │        RELEASED
                 │  │  INDEPENDENT GUARDS (raw reality)      │  │
                 │  │  ├─ script   (text, fluff/anchors/CTA) │  │
                 │  │  ├─ hook     (overlay, pattern-interrupt)  │
                 │  │  ├─ voice    (WAV files, silence, pace)│  │
                 │  │  ├─ caption  (text match, safe zone)   │  │
                 │  │  ├─ video    (ffprobe 1080x1920/audio) │  │
                 │  │  ├─ seo      (YT/FB/IG 2026 rules)     │  │
                 │  │  ├─ ctr      (title first-3/keyword)   │  │
                 │  │  └─ views    (REAL performance, pivot) │  │
                 │  └───────────────────────────────────────┘  │
                 │                    │                        │
                 │              ┌─────▼────────┐               │
                 │              │ USASupervisor │  fail-CLOSED  │
                 │              └──────────────┘               │
                 └─────────────────────────────────────────────┘
```

**Fail-closed principle:** koi guard agar measure hi nahi kar saka (UNKNOWN)
to video block hoti hai. "Pata nahi" kabhi "pass" nahi hota.

## 2. Guard kya measure karta hai (reality, opinion nahi)

| Guard | Kya measure karta hai | Fail conditions (examples) |
|---|---|---|
| **ScriptGuard** | RAW text — apni fluff/anchor/concept lists | AI-fluff ("in this video"), <4 scenes, <90 words, koi concrete anchor nahi, koi psych concept nahi, CTA nahi, hook↔scene-1 ka koi link nahi (clickbait gap), ALL-CAPS shouting |
| **HookGuard** | 2-sec overlay text — apne rules | <3 ya >9 words, >85 chars, weak opener ("welcome"), dangling fragment ("Stop letting them"), cliché, na strong word na pattern-interrupt |
| **VoiceGuard** | ASAL WAV files (wave/RMS/silence ratio) | audio file missing (TTS silence fallback = silent video), 50%+ silence, speaking rate 1.6–3.2 wps se bahar, total 35–60s se bahar |
| **CaptionGuard** | captions vs voice text + UI zone | caption ≠ voice text (jo sunta hai wo nahi padhta), caption zone Shorts UI ke neeche, words-per-chunk >3 |
| **VideoGuard** | RENDERED mp4 ki ffprobe measurement | 1080x1920 nahi, duration <35s ya >60s, fps <24, bitrate <1000k, NO audio stream, file too small, scene avg >9s (fast cuts missing) |
| **SEOGuard** | Banaya hua package — YT/FB/IG 2026 rules | YT: title 20-100 + keyword + disclaimer + tags ≤500 chars + ≤3 hashtags; FB: 200-6300 chars + comment CTA + 4-8 hashtags; IG: ≤2200 + save/share CTA + 10-20 hashtags |
| **CTRGuard** | title — apni independent scoring | pehle 3 words mein na power na keyword, "|" stuffing, ALL-CAPS spam, "!!", title↔hook disconnected, score < platform threshold |
| **ViewsGuard** | ML store ke REAL outcomes (priors nahi) | formula ke 3+ real outcomes ka mean <0.4 → "PROVEN weak — pivot"; credited videos ki 0-view streak; platform quarantined |

**Independence ka guarantee:** `ReleaseGate._sanitize()` payload se
producer ke saare self-scores (`script_quality`, `hook_score`, `ctr_score`...)
strip kar deta hai. Guards unhein **dekh hi nahi sakte**. Supervisor dobara
assert karta hai ke koi leak na ho.

## 3. USASupervisor — aakhri judge

1. **Independence audit** — har verdict ka evidence non-empty ho, koi guard
   UNKNOWN na ho, koi producer-score leak na ho.
2. **USA calibration** — content English (ASCII ≥92%), koi roman-Urdu token
   nahi, koi British spelling nahi (colour/behaviour), sirf $/dollars,
   publish window 6am–11pm ET (raat 2 baje = dead post).
3. **Cross-platform nativness** — teeno platforms ki copy 90%+ identical na ho
   (spam signal).
4. **Grade** — A (sab PASS), B (1-2 WARN), C (2+ WARN), F (koi FAIL) →
   F par video **HELD**.

Supervisor ne ab tak 3 real bugs pakre: template CTAs Roman Urdu mein thay
(USA channel ki narration Urdu bol rahi thi), hook-override ke baad scene-1
purana hook bolta tha (clickbait gap), aur "rs." currency regex ka false
positive. Teeno fix ho gaye.

## 4. Pipeline integration (`src/main.py`)

```
build (script→clips→voice→video) ──► GATE evaluate (har platform) ──┐
      ▲                                                              │
      │  core guard fail + repairs baki                            ▼
      └────── naya script generate (GATE_MAX_REPAIRS=2)      released? ──no──► HELD
                                                                    │ (upload nahi,
                                                                    │  gate_blocked
                                                                    │  result)
                                                                   yes
                                                                    ▼
                                                              upload (YT/FB/IG)
```

- **GATE_MODE**: `strict` (default) | `warn` (report only, emergency) | `off`
- **GATE_MAX_REPAIRS**: core guard (script/hook/voice/caption/video) fail hone
  par kitni baar naya script banaye (default 2)
- Gate ke HELD hone par platform par **ML penalty nahi** lagti (ye quality
  control hai, platform ka fault nahi) aur publish-slot claim nahi hota
- Har run ke baad:
  - `data/gate_report.json` + `data/gate_report.md` — har guard ka verdict +
    evidence + supervisor ka faisla (CI commit karta hai = audit trail)
  - `output/gate_payload.json` — aakhri build ka raw payload

## 5. Standalone use

```bash
python scripts/run_gate.py            # aakhri build ko dobara judge karo
python scripts/run_gate.py --json     # machine-readable
python scripts/run_gate.py --mode warn
```

## 6. Tests

`tests/test_guards.py` — 27 tests:
- har guard ka pass/fail behavior (weak vs strong payload)
- fail-closed: missing audio / silent WAV / missing video / UNKNOWN probe
- independence: producer scores strip ho jate hain
- supervisor: Urdu token, British spelling, currency false-positive, unknown
  measurement → HOLD
- **full-release integration**: real WAVs + real ffmpeg video + strong
  script/packages → SAB guards pass → RELEASED (grade A/B)

Selftest (`python src/main.py --selftest`) ab gate ko bhi verify karta hai.
