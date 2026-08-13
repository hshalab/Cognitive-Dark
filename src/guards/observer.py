#!/usr/bin/env python3
"""IndependentObserver — RAW reality, sirf measurements, koi opinion nahi.

Ye layer producer ke score/cache/opinion se bilkul alag hai. Sirf artifacts
ki measurement karta hai:
  • ffprobe (video ka asal resolution/duration/bitrate/streams)
  • WAV analysis (duration, RMS loudness, silence ratio — pure stdlib)
  • file sizes
  • ML store se REAL outcome stats (read-only, priors excluded)

Guards in functions par bharosa karte hain. Agar koi measurement fail ho
jaye to exception propagate hoti hai — guard use FAIL/UNKNOWN mein convert
karta hai (fail-closed). Kabhi bhi "guess" nahi karte.
"""

from __future__ import annotations

import json
import logging
import math
import struct
import subprocess
import wave
from pathlib import Path

logger = logging.getLogger("guards.observer")


class IndependentObserver:
    """Measures artifacts; never reads producer self-scores."""

    def ffprobe(self, path) -> dict:
        """Full ffprobe JSON. Raises if the file can't be probed."""
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", str(path)],
            capture_output=True, text=True, timeout=90, check=False)
        if r.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {r.stderr.strip()[:300]}")
        return json.loads(r.stdout)

    def video_stats(self, path) -> dict:
        """Flat measurement dict of the ACTUAL video file."""
        p = Path(path)
        data = self.ffprobe(p)
        fmt = data.get("format", {})
        v_stream = next((s for s in data.get("streams", [])
                         if s.get("codec_type") == "video"), None)
        a_stream = next((s for s in data.get("streams", [])
                         if s.get("codec_type") == "audio"), None)

        def _fps(stream: dict | None) -> float:
            if not stream:
                return 0.0
            for key in ("avg_frame_rate", "r_frame_rate"):
                try:
                    num, _, den = stream.get(key, "0/0").partition("/")
                    if int(den):
                        return round(int(num) / int(den), 3)
                except (ValueError, ZeroDivisionError):
                    continue
            return 0.0

        return {
            "path": str(p),
            "exists": p.exists(),
            "size_bytes": p.stat().st_size if p.exists() else 0,
            "duration_s": round(float(fmt.get("duration", 0) or 0), 3),
            "width": int(v_stream.get("width", 0)) if v_stream else 0,
            "height": int(v_stream.get("height", 0)) if v_stream else 0,
            "fps": _fps(v_stream),
            "has_video": v_stream is not None,
            "has_audio": a_stream is not None,
            "video_bitrate": int(v_stream.get("bit_rate", 0) or 0) if v_stream else 0,
            "codec": v_stream.get("codec_name", "") if v_stream else "",
        }

    # ── WAV analysis (pure stdlib — 16-bit PCM) ─────────────────────
    def wav_stats(self, path) -> dict:
        """Measure a voice segment WAV: duration, RMS, silence ratio, peak."""
        p = Path(path)
        with wave.open(str(p), "rb") as w:
            n_frames = w.getnframes()
            rate = w.getframerate() or 1
            channels = w.getnchannels() or 1
            sampwidth = w.getsampwidth()
            dur = n_frames / rate
            if sampwidth != 2:
                raise RuntimeError(f"unsupported sample width {sampwidth}")
            # cap analysis at 60s to stay memory-safe
            frames = w.readframes(min(n_frames, int(rate * 60)))
        raw = frames[: (len(frames) // 2) * 2]
        if not raw:
            return {"path": str(p), "duration_s": round(dur, 3), "rms": 0.0,
                    "peak": 0.0, "silence_ratio": 1.0, "sample_rate": rate}
        samples = struct.unpack(f"<{len(raw) // 2}h", raw)
        # stride to keep analysis fast on long files
        step = max(1, len(samples) // 400_000)
        picked = samples[::step]
        squares = [s * s for s in picked]
        rms = math.sqrt(sum(squares) / len(picked))
        peak = max(abs(s) for s in picked)
        # silence ratio over 50ms windows
        win = max(1, int(rate * 0.05 / step))
        silent_win = 0
        total_win = 0
        for i in range(0, len(picked), win):
            chunk = squares[i:i + win]
            if not chunk:
                continue
            total_win += 1
            if math.sqrt(sum(chunk) / len(chunk)) < 500:
                silent_win += 1
        return {"path": str(p), "duration_s": round(dur, 3),
                "rms": round(rms, 1), "peak": round(float(peak), 1),
                "silence_ratio": round(silent_win / max(1, total_win), 3),
                "sample_rate": rate, "channels": channels}

    # ── ML store REAL outcomes (read-only; priors NOT included) ────
    def arm_real_stats(self, ml, arm_key: str) -> dict:
        """Arm ke REAL outcomes (n_real, real_mean) — belief nahi, data."""
        if ml is None or not arm_key:
            return {"n_real": 0, "real_mean": 0.0, "arm_key": arm_key}
        arm = ml.data.get("arms", {}).get(arm_key, {})
        n_real = int(arm.get("n", 0) or 0)
        rewards = float(arm.get("rewards", 0.0) or 0.0)
        return {"n_real": n_real,
                "real_mean": round(rewards / n_real, 3) if n_real else 0.0,
                "arm_key": arm_key,
                "prior_n": int(arm.get("prior_n", 0) or 0),
                "prior_mean": float(arm.get("prior_mean", 0.0) or 0.0)}

    def attributed_recent(self, ml, arm_key: str, limit: int = 3) -> list:
        """Is arm ki recent credited videos — unke real metrics."""
        if ml is None:
            return []
        out = []
        for vid, a in reversed(list(ml.data.get("attribution", {}).items())):
            if a.get("arm_key") != arm_key:
                continue
            out.append({"video_id": vid, "credited": a.get("credited", False),
                        "metrics": a.get("metrics", {})})
            if len(out) >= limit:
                break
        return out
