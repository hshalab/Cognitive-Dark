#!/usr/bin/env python3
"""VideoGuard — RENDERED mp4 ki ffprobe reality measurement.

Producer ke claim par bharosa nahi — actual file probe hoti hai:
  • 1080x1920 (9:16) — koi aur resolution = Reels/Shorts feed ke liye galat
  • duration 35-60s (40-58 target)
  • fps >= 24
  • video bitrate >= 1000k (blurry upload nahi)
  • AUDIO stream present (silent video releasable nahi)
  • file size sane
  • scene cuts: har scene ki avg duration <= 9s (fast-cut USA style)
"""

from __future__ import annotations

import glob
import os

from config.settings import TMP_DIR
from guards.base import BaseGuard

W, H = 1080, 1920
MIN_S, MAX_S = 35.0, 60.0
TARGET_MIN_S, TARGET_MAX_S = 40.0, 58.0
MIN_FPS = 24.0
MIN_BITRATE = 1_000_000
MIN_SIZE_MB = 1.0
MAX_SCENE_AVG_S = 9.0


class VideoGuard(BaseGuard):
    name = "video"

    def check(self, payload: dict) -> object:
        path = payload.get("video_path") or ""
        if not path or not os.path.exists(path):
            return self._v("UNKNOWN", "video file not built", {"path": path},
                           fix="Video render karo pehle (build_short).")
        try:
            st = self.observer.video_stats(path)
        except Exception as exc:
            return self._v("UNKNOWN", f"cannot probe video: {exc}",
                           {"path": path, "error": str(exc)[:200]},
                           fix="ffprobe install/check karo, video dobara render.")

        issues, warns = [], []
        dur = st["duration_s"]
        if st["width"] != W or st["height"] != H:
            issues.append(f"resolution {st['width']}x{st['height']} "
                          f"(chahiye {W}x{H} 9:16)")
        if dur < MIN_S:
            issues.append(f"duration {dur}s < {MIN_S}s")
        elif dur > MAX_S:
            issues.append(f"duration {dur}s > {MAX_S}s")
        elif dur < TARGET_MIN_S or dur > TARGET_MAX_S:
            warns.append(f"duration {dur}s outside 40-58s sweet spot")
        if st["fps"] and st["fps"] < MIN_FPS:
            issues.append(f"fps {st['fps']} < {MIN_FPS}")
        if st["video_bitrate"] and st["video_bitrate"] < MIN_BITRATE:
            issues.append(f"bitrate {st['video_bitrate'] // 1000}k < 1000k")
        if not st["has_audio"]:
            issues.append("NO audio stream — silent upload (releasable nahi)")
        if st["size_bytes"] and st["size_bytes"] < MIN_SIZE_MB * 1e6:
            issues.append(f"file too small ({st['size_bytes'] / 1e6:.1f}MB)")
        if not st["has_video"]:
            issues.append("no video stream")

        # fast-cut check via rendered scene files
        scene_files = sorted(glob.glob(str(TMP_DIR / "scene_*.mp4")))
        n_scenes = len(scene_files)
        avg_scene = round(dur / n_scenes, 2) if n_scenes else 0.0
        if n_scenes and avg_scene > MAX_SCENE_AVG_S:
            warns.append(f"avg scene {avg_scene}s > {MAX_SCENE_AVG_S}s "
                         "(fast cuts missing)")

        evidence = {"path": path, **{k: v for k, v in st.items()
                                     if k != "path"},
                    "scene_files": n_scenes, "avg_scene_s": avg_scene}
        if issues:
            return self._v("FAIL", "; ".join(issues), evidence,
                           fix="Video dobara render karo — 1080x1920, 40-58s, "
                               "audio ke saath, bitrate >= 4000k.")
        if warns:
            return self._v("WARN", "; ".join(warns), evidence)
        return self._v("PASS", f"{st['width']}x{st['height']} {dur}s "
                              f"{st['fps']}fps audio={'yes' if st['has_audio'] else 'no'}",
                       evidence)
