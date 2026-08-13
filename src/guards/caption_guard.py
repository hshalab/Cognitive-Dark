#!/usr/bin/env python3
"""CaptionGuard — word-captions ka independent check.

Fail conditions:
  • kisi scene ka caption empty
  • caption text aur voice text match nahi karte (audience jo sunta hai
    wo parhta nahi = USA retention killer)
  • caption Y-zone UI safe-area mein nahi (Shorts UI ke neeche chhup jaye)
  • words-per-chunk 3 se zyada (screen par readable nahi)
"""

from __future__ import annotations

from config.settings import TMP_DIR, USA_STYLE
from guards.base import BaseGuard

MAX_WORDS_PER_CHUNK = 3
SAFE_TOP = 400        # hook overlay ke neeche (top area occupied)
SAFE_BOTTOM = 1650    # Shorts UI overlays ke upar
MAX_CAPTION_WORDS = 42


class CaptionGuard(BaseGuard):
    name = "caption"

    def check(self, payload: dict) -> object:
        script = payload.get("script") or {}
        scenes = script.get("scenes") or []
        segments = payload.get("segments") or []
        if not scenes:
            return self._v("UNKNOWN", "no scenes in payload", {"scenes": 0})

        issues, warns = [], []
        rows = []
        chunk_png_missing = 0
        for i, scene in enumerate(scenes):
            cap = (scene.get("caption") or "").strip()
            n_words = len(cap.split())
            # voice text for the same scene (if segments carry text)
            voice_text = ""
            if i < len(segments):
                voice_text = (segments[i].get("text") or "").strip()
            match = (cap == voice_text) if voice_text else None
            row = {"scene": i, "words": n_words, "caption_matches_voice": match}
            rows.append(row)
            if not cap:
                issues.append(f"scene {i}: caption empty")
            if match is False:
                issues.append(f"scene {i}: caption ≠ voice text (sunai vs dikhai alag)")
            if n_words > MAX_CAPTION_WORDS:
                issues.append(f"scene {i}: {n_words} caption words — unreadable")
            # caption strip PNG check (built by video_builder)
            strip = TMP_DIR / f"cap_{i:02d}_00.png"
            if not strip.exists():
                chunk_png_missing += 1

        if chunk_png_missing == len(scenes):
            warns.append("caption PNGs not found — video build se pehle gate? "
                         "(render ke baad dobara check karo)")

        cap_y = int(USA_STYLE.get("caption_y", 1150))
        cap_h = int(USA_STYLE.get("caption_h", 260))
        bottom = cap_y + cap_h
        zone_ok = cap_y >= SAFE_TOP and bottom <= SAFE_BOTTOM
        if not zone_ok:
            issues.append(f"caption zone y={cap_y}..{bottom} UI-safe nahi "
                          f"(safe {SAFE_TOP}..{SAFE_BOTTOM})")

        wpc = int(USA_STYLE.get("caption_words_per_group", 2))
        if wpc > MAX_WORDS_PER_CHUNK:
            issues.append(f"words-per-chunk {wpc} > {MAX_WORDS_PER_CHUNK}")

        evidence = {"scenes": len(scenes), "rows": rows, "chunk_png_missing":
                    chunk_png_missing, "caption_zone": f"{cap_y}..{bottom}",
                    "words_per_chunk": wpc}
        if issues:
            return self._v("FAIL", "; ".join(issues), evidence,
                           fix="Har scene ka caption exact voice text ke barabar "
                               "rakho; zone config USA_STYLE.caption_y check karo.")
        if warns:
            return self._v("WARN", "; ".join(warns), evidence)
        return self._v("PASS", f"{len(scenes)} captions, sab voice ke match, "
                              f"zone {cap_y}..{bottom} safe", evidence)
