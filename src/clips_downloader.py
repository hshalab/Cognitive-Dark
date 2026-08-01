#!/usr/bin/env python3
"""
Cognitive Dark V2 — Stock Clip Downloader.

Sources (free, royalty-free, monetization-safe):
  • Pexels  — api.pexels.com/videos/search   (Authorization header)
  • Pixabay — pixabay.com/api/videos/        (key query param)

Each scene's `visual` field is a short search query. We fetch a pool of
clips per scene, pick the best (portrait > landscape, resolution, size),
download & cache them, and return paths. If both providers fail or no key
is configured, the pipeline falls back to procedural visuals (visuals.py).
"""

import logging
import os
import random
import time
from pathlib import Path

import requests

from config.settings import CLIP_CACHE, CLIP_CACHE_TTL_DAYS, MIN_CLIP_BYTES, CLIP_PROVIDER_ORDER
from visuals import generate_procedural_scene  # fallback

logger = logging.getLogger("clips_downloader")

PEXELS_KEY = os.environ.get("PEXELS_API_KEY", "")
PIXABAY_KEY = os.environ.get("PIXABAY_API_KEY", "")

UA = {"User-Agent": "CognitiveDarkV2/1.0 (+https://github.com/CognitiveDark)"}


# ── Pexels ───────────────────────────────────────────────────
def _pexels_search(query: str, per_page: int = 12) -> list:
    """Return list of candidate clips [{url, width, height, quality, provider}]."""
    if not PEXELS_KEY:
        return []
    resp = requests.get(
        "https://api.pexels.com/videos/search",
        params={"query": query, "per_page": per_page, "orientation": "portrait"},
        headers={"Authorization": PEXELS_KEY, **UA}, timeout=30)
    resp.raise_for_status()
    out = []
    for v in resp.json().get("videos", []):
        for f in v.get("video_files", []):
            if not f.get("link"):
                continue
            out.append({
                "url": f["link"],
                "width": f.get("width", 0), "height": f.get("height", 0),
                "quality": f.get("quality", ""),
                "provider": "pexels", "id": v.get("id"),
                "duration": v.get("duration", 0),
            })
    return out


# ── Pixabay ──────────────────────────────────────────────────
def _pixabay_search(query: str, per_page: int = 12) -> list:
    if not PIXABAY_KEY:
        return []
    resp = requests.get(
        "https://pixabay.com/api/videos/",
        params={"key": PIXABAY_KEY, "q": query, "per_page": per_page,
                "video_type": "film", "min_width": 640, "min_height": 360},
        headers=UA, timeout=30)
    resp.raise_for_status()
    out = []
    for h in resp.json().get("hits", []):
        for size_key in ("medium", "large", "small"):
            f = h.get("videos", {}).get(size_key)
            if not f or not f.get("url"):
                continue
            out.append({
                "url": f["url"],
                "width": f.get("width", 0), "height": f.get("height", 0),
                "quality": size_key,
                "provider": "pixabay", "id": h.get("id"),
                "duration": h.get("duration", 0),
            })
    return out


# ── selection & download ─────────────────────────────────────
def _score(clip: dict) -> float:
    """Prefer portrait 1080p+ (reels-native), penalize tiny/low files."""
    w, h = clip["width"], clip["height"]
    s = 0.0
    if h >= 1920 and 0 < w <= 1080:
        s += 4.0                      # perfect portrait HD
    elif h >= 1080:
        s += 2.0
    elif h >= 720:
        s += 1.0
    s += min(1.0, (h * w) / (1920 * 1080))
    if clip["quality"] in ("hd", "uhd", "large"):
        s += 0.5
    return s


def _download(url: str, dest: Path) -> Path:
    if dest.exists() and dest.stat().st_size > MIN_CLIP_BYTES:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    with requests.get(url, headers=UA, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(tmp, "wb") as fh:
            for chunk in r.iter_content(chunk_size=1 << 16):
                fh.write(chunk)
    if tmp.stat().st_size < MIN_CLIP_BYTES:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"clip too small: {tmp.stat().st_size} bytes")
    os.replace(tmp, dest)
    return dest


def get_clip_for_scene(scene_idx: int, scene: dict, max_retries: int = 2) -> dict:
    """Fetch the best clip for a scene. Returns {'path': str, 'source': str}
    or raises if all providers fail."""
    query = (scene.get("visual") or "dark city night").strip()[:80]
    candidates = []
    for provider in CLIP_PROVIDER_ORDER:
        try:
            if provider == "pexels":
                candidates += _pexels_search(query)
            elif provider == "pixabay":
                candidates += _pixabay_search(query)
        except Exception as exc:
            logger.warning("Provider %s search failed: %s", provider, exc)
    if not candidates:
        raise RuntimeError("no clips found for query: " + query)

    candidates.sort(key=_score, reverse=True)
    seen = set()
    for clip in candidates:
        url = clip["url"]
        ext = Path(url.split("?")[0]).suffix or ".mp4"
        key = f"{clip['provider']}_{clip['id']}_{clip['width']}x{clip['height']}{ext}"
        if key in seen:
            continue
        seen.add(key)
        dest = CLIP_CACHE / key
        try:
            path = _download(url, dest)
            return {"path": str(path), "source": clip["provider"],
                    "width": clip["width"], "height": clip["height"],
                    "query": query}
        except Exception as exc:
            logger.warning("clip download failed (%s): %s", url[:70], exc)
            time.sleep(0.5)
    raise RuntimeError(f"could not download any clip for: {query}")


def prepare_clips(scenes: list) -> list:
    """Fetch clips for all scenes. Falls back to procedural visuals per scene."""
    results = []
    for i, scene in enumerate(scenes):
        try:
            results.append(get_clip_for_scene(i, scene))
        except Exception as exc:
            logger.warning("Clips unavailable for scene %d → procedural visual (%s)", i, exc)
            results.append({
                "path": generate_procedural_scene(i, scene.get("emotion", "dark")),
                "source": "procedural", "query": scene.get("visual", ""),
            })
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_scenes = [
        {"visual": "dark city rain", "emotion": "dark"},
        {"visual": "storm clouds", "emotion": "intense"},
    ]
    for r in prepare_clips(test_scenes):
        print(r["source"], r["path"])
