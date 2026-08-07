#!/usr/bin/env python3
"""
Cognitive Dark V2 — Compact Dark Ambient Music Generator.

Generates 2 short dark-ambient beds (~90s, mono 22.05kHz → ~4MB each) so the
repo stays small. Run once during setup
CI regenerates if missing.
"""

import os
import wave

import numpy as np

SR = 22050
DUR = 90.0
OUT = os.path.join("assets", "music")


def hz(midi):
    return 440.0 * 2.0 ** ((midi - 69.0) / 12.0)


def _write(name, sig):
    os.makedirs(OUT, exist_ok=True)
    peak = np.abs(sig).max() or 1.0
    pcm = (sig / peak * 0.72 * 32767).astype(np.int16)
    path = os.path.join(OUT, name)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(f"  ✅ {name} ({os.path.getsize(path)//1024}KB)")


def build(name, root=36, bpm=55, pad_chords=(36, 39, 43), seed=7):
    rng = np.random.default_rng(seed)
    n = int(SR * DUR)
    t = np.arange(n) / SR
    f = hz(root)

    # drone
    drone = (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * 2 * f * t)) * 0.14
    drone *= 0.7 + 0.3 * np.sin(2 * np.pi * t / 18.0)

    # heartbeat
    hb = np.zeros(n)
    period = 60.0 / bpm
    tt = 0.0
    while tt < DUR:
        pos = int(tt * SR)
        if pos + int(0.14 * SR) < n:
            tl = np.arange(int(0.14 * SR)) / SR
            hb[pos:pos + len(tl)] += np.sin(2 * np.pi * 55 * tl) * np.exp(-tl * 16) * 0.09
            dp = pos + int(0.22 * SR)
            if dp + int(0.09 * SR) < n:
                td = np.arange(int(0.09 * SR)) / SR
                hb[dp:dp + len(td)] += np.sin(2 * np.pi * 70 * td) * np.exp(-td * 20) * 0.05
        tt += period

    # ambient pad (dissonant chord cluster)
    pad = np.zeros(n)
    for k, m in enumerate(pad_chords):
        fk = hz(m)
        env = np.exp(-((t - (k + 0.5) * DUR / len(pad_chords)) ** 2) / (2 * (DUR / 8) ** 2))
        pad += np.sin(2 * np.pi * fk * t) * env * 0.06

    # noise texture
    noise = rng.standard_normal(n) * 0.004
    k = np.hanning(101)
    k /= k.sum()
    noise = np.convolve(noise, k, mode="same")

    mix = drone + hb + pad + noise
    _write(name, mix)


if __name__ == "__main__":
    build("dark_drone.wav", root=36, bpm=55, pad_chords=(36, 39, 43, 46), seed=1)
    build("suspense_thrum.wav", root=33, bpm=60, pad_chords=(33, 36, 39, 42), seed=2)
    print("Done — 2 tracks in assets/music/")
