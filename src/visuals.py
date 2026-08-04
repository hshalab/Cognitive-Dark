#!/usr/bin/env python3
"""
Cognitive Dark V2 — Procedural Visual Fallback.

Used when stock clips are unavailable (no API keys, offline, rate-limited).
Dark cinematic stills (1080×1920) generated with numpy/PIL — the same
approach as V1 but tuned for the converted niche.
"""

import logging
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

logger = logging.getLogger("visuals")

WIDTH, HEIGHT = 1080, 1920

PALETTES = {
    "dark": ((5, 5, 12), (15, 20, 40)),
    "mysterious": ((8, 4, 16), (25, 15, 50)),
    "intense": ((18, 4, 4), (55, 15, 10)),
    "chilling": ((4, 8, 16), (10, 25, 55)),
    "revelatory": ((3, 3, 3), (8, 8, 12)),
}
BOKEH = {
    "dark": [(40, 60, 120), (80, 40, 40), (30, 30, 60)],
    "mysterious": [(80, 40, 120), (40, 30, 100), (60, 20, 80)],
    "intense": [(120, 30, 20), (100, 40, 10), (80, 20, 20)],
    "chilling": [(20, 40, 100), (30, 50, 80), (15, 30, 70)],
    "revelatory": [(200, 180, 100), (150, 140, 80), (100, 90, 50)],
}


def generate_procedural_scene(scene_idx: int, emotion: str = "dark",
                              out_dir: str = "output/visuals") -> str:
    rng = np.random.RandomState(1000 + scene_idx * 37)
    top, bottom = PALETTES.get(emotion, PALETTES["dark"])
    # V2.1: vectorized gradient (V2 filled 2M pixels in a Python loop → slow).
    t = np.linspace(0.0, 1.0, HEIGHT, dtype=np.float32)[:, None]
    top_a = np.asarray(top, dtype=np.float32)[None, :]
    bot_a = np.asarray(bottom, dtype=np.float32)[None, :]
    col = (top_a + (bot_a - top_a) * t)                      # (H,3)
    grad = np.repeat(col[:, None, :], WIDTH, axis=1)         # (H,W,3)
    img = Image.fromarray(grad.astype(np.uint8))

    # noise texture
    arr = np.asarray(img).astype(np.float32)
    arr = np.clip(arr + rng.standard_normal(arr.shape) * 3, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr)

    # bokeh
    overlay = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
    dr = ImageDraw.Draw(overlay)
    colors = BOKEH.get(emotion, BOKEH["dark"])
    for _ in range(15):
        r = rng.randint(20, 100)
        x, y = rng.randint(0, WIDTH), rng.randint(0, HEIGHT)
        col = colors[rng.randint(0, len(colors))]   # V2.1: randint high is exclusive
        dr.ellipse([x - r, y - r, x + r, y + r],
                   fill=tuple(int(v * 0.2) for v in col))
    overlay = overlay.filter(ImageFilter.GaussianBlur(50))
    img = Image.blend(img, overlay, 0.4)

    # light source for revelatory
    if emotion == "revelatory":
        light = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
        lr = ImageDraw.Draw(light)
        lx, ly = WIDTH // 2, HEIGHT // 3
        for r in range(200, 0, -2):
            alpha = int(30 * (1 - r / 200))
            lr.ellipse([lx - r, ly - r, lx + r, ly + r],
                       fill=(200 + alpha, 180 + alpha, 100 + alpha))
        light = light.filter(ImageFilter.GaussianBlur(80))
        img = Image.blend(img, light, 0.3)

    # vignette
    vign = Image.new("L", (WIDTH, HEIGHT), 0)
    dv = ImageDraw.Draw(vign)
    dv.ellipse([-WIDTH * 0.3, -HEIGHT * 0.25, WIDTH * 1.3, HEIGHT * 1.2], fill=255)
    vign = vign.filter(ImageFilter.GaussianBlur(250))
    arr = np.asarray(img).astype(np.float32)
    arr *= np.asarray(vign)[..., None] / 255.0
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"proc_{scene_idx:02d}.jpg")
    img.save(path, quality=92)
    return path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    p = generate_procedural_scene(0, "chilling")
    print("wrote", p)
