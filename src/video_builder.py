#!/usr/bin/env python3
"""
Cognitive Dark V2 — Video Builder (MoviePy 1.0.3 pinned).

Builds the 9:16 master short (1080×1920, 30fps) used by all three platforms:
  • real stock clips (Pexels/Pixabay) with cover-crop + subtle Ken Burns
  • burned-in captions (PIL), hook overlay in first 2s
  • loop trick (hook re-appears at the end → seamless rewatch)
  • Kokoro narration + dark ambient music bed

Platform variants (IG/FB/YT) are all 9:16 Reels/Shorts masters — no re-render
needed. A separate 16:9 long-form path can be added later.
"""

import glob
import logging
import os
import random
import textwrap
from pathlib import Path

import compat  # patch PIL before moviepy import (Image.ANTIALIAS)
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

logger = logging.getLogger("video_builder")

WIDTH, HEIGHT = 1080, 1920
FPS = 30
MUSIC_VOLUME = float(os.environ.get("MUSIC_VOLUME", "0.05"))

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "assets/fonts/DejaVuSans-Bold.ttf",
]


def _load_font(size: int):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


# ── caption / hook overlays ──────────────────────────────────
def _caption_strip(text: str, emotion: str = "dark") -> Image.Image:
    font = _load_font(54)
    strip = Image.new("RGBA", (WIDTH, 260), (0, 0, 0, 0))
    draw = ImageDraw.Draw(strip)
    lines = textwrap.wrap(text, width=28) or [text]
    if len(lines) > 3:
        lines = lines[:3] + ["..."]
    colors = {"dark": (255, 255, 255), "mysterious": (200, 180, 255),
              "intense": (255, 100, 80), "chilling": (150, 200, 255),
              "revelatory": (255, 220, 100)}
    fill = colors.get(emotion, (255, 255, 255))
    draw.rectangle([30, 0, WIDTH - 30, 260], fill=(0, 0, 0, 150))
    y = 18
    for line in lines:
        w = draw.textlength(line, font=font)
        draw.text(((WIDTH - w) / 2, y), line, font=font, fill=fill,
                  stroke_width=2, stroke_fill=(0, 0, 0))
        y += 68
    return strip


def _hook_overlay(hook: str) -> Image.Image:
    font = _load_font(70)
    ov = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(ov)
    lines = textwrap.wrap(hook, width=22) or [hook]
    if len(lines) > 3:
        lines = lines[:3] + ["..."]
    box_h = 100 * len(lines) + 70
    draw.rounded_rectangle([40, 140, WIDTH - 40, 140 + box_h], radius=24,
                           fill=(110, 8, 8, 215))
    y = 160
    for line in lines:
        w = draw.textlength(line, font=font)
        draw.text(((WIDTH - w) / 2, y), line, font=font, fill=(255, 255, 255, 255),
                  stroke_width=3, stroke_fill=(0, 0, 0))
        y += 104
    return ov


# ── scene clip building ──────────────────────────────────────
def _build_scene_clip(clip_path: str, duration: float) -> object:
    """Real stock video → cover-cropped 9:16 clip (audio dropped)."""
    # images route straight to the image path (no wasted VideoFileClip load)
    if clip_path.lower().endswith((".jpg", ".jpeg", ".png")):
        return _build_image_clip(clip_path, duration)
    from moviepy.editor import VideoFileClip
    clip = VideoFileClip(clip_path)
    if clip.duration is None or clip.duration < 0.5:
        clip.close()
        raise RuntimeError("clip too short")
    w, h = clip.w, clip.h
    s = max(WIDTH / w, HEIGHT / h)           # cover scale
    scaled = clip.resize(width=int(w * s + 0.5), height=int(h * s + 0.5))
    cropped = scaled.crop(x_center=scaled.w / 2, y_center=scaled.h / 2,
                          width=WIDTH, height=HEIGHT)
    # subtle Ken Burns drift
    zoomed = cropped.resize(lambda t: 1.0 + 0.05 * min(1.0, t / max(duration, 0.01)))
    out = zoomed.subclip(0, min(duration, zoomed.duration - 0.05)
                         if zoomed.duration else duration)
    out = out.set_duration(duration)
    try:
        out = out.without_audio()
    except Exception:
        pass
    return out


def _build_image_clip(img_path: str, duration: float) -> object:
    """Static image fallback — ZERO per-frame resampling (memory-light).

    The zoom is baked once via PIL (1080→1134 cover crop), so MoviePy only
    copies frames — no resize lambda recomputation per frame.
    """
    from moviepy.editor import ImageClip
    try:
        im = Image.open(img_path).convert("RGB")
        # bake a mild 5% zoom once: crop center of a slightly-zoomed copy
        zoom = 1.05
        w, h = im.size
        nw, nh = int(w * zoom), int(h * zoom)
        im2 = im.resize((nw, nh), Image.LANCZOS)
        left, top = (nw - w) // 2, (nh - h) // 2
        im2 = im2.crop((left, top, left + w, top + h))
        # then fit canvas (procedural images are already 9:16; be safe anyway)
        im2 = im2.resize((WIDTH, HEIGHT), Image.LANCZOS)
        fit_path = img_path + ".fit.jpg"
        im2.save(fit_path, quality=88)
        base = ImageClip(fit_path).set_duration(duration)
    except Exception:
        base = ImageClip(img_path).set_duration(duration)
    return base.set_position(("center", "center")).set_duration(duration)


# ── music ────────────────────────────────────────────────────
def _pick_music() -> str:
    exact = os.environ.get("MUSIC_TRACK", "").strip()
    tracks = glob.glob("assets/music/*.mp3") + glob.glob("assets/music/*.wav")
    tracks = [t for t in tracks if "ATTRIBUTION" not in t.upper()]
    if exact:
        m = [t for t in tracks if t.endswith(exact)]
        return m[0] if m else None
    dark = [t for t in tracks if any(v in t.lower() for v in
                                     ["dark", "ambient", "suspense", "ominous", "void"])]
    pool = dark or tracks
    return random.choice(pool) if pool else None


# ── main build (memory-safe: one scene in RAM at a time) ─────
def _build_audio(audio_segments: list, total_duration: float) -> str:
    """Render narration+music to an m4a track (audio-only, low memory)."""
    from moviepy.editor import AudioFileClip, CompositeAudioClip, concatenate_audioclips
    tracks = []
    voices = [AudioFileClip(s["path"]) for s in audio_segments
              if s.get("path") and os.path.exists(s["path"])]
    if voices:
        tracks.append(concatenate_audioclips(voices))
    music_path = _pick_music()
    if music_path and os.path.exists(music_path):
        try:
            music = AudioFileClip(music_path).volumex(MUSIC_VOLUME)
            if music.duration < total_duration:
                loops = int(np.ceil(total_duration / music.duration))
                music = concatenate_audioclips([music] * loops).subclip(0, total_duration)
            else:
                music = music.subclip(0, total_duration)
            music = music.fx(lambda c: c.audio_fadein(0.5))
            music = music.fx(lambda c: c.audio_fadeout(min(2.5, total_duration * 0.15)))
            tracks.append(music)
        except Exception as exc:
            logger.warning("music failed: %s", exc)
    if not tracks:
        return None
    os.makedirs("output/tmp", exist_ok=True)
    track_path = "output/tmp/narration.m4a"
    CompositeAudioClip(tracks).write_audiofile(
        track_path, fps=44100, codec="aac", logger=None)
    for t in tracks:
        try:
            t.close()
        except Exception:
            pass
    return track_path


def build_short(clip_paths: list, audio_segments: list, scenes: list,
                out_path: str = "output/final_video.mp4") -> str:
    import gc
    import subprocess
    from moviepy.editor import (CompositeVideoClip, ImageClip)

    if len(clip_paths) != len(audio_segments) or len(clip_paths) != len(scenes):
        raise RuntimeError(
            f"length mismatch: clips={len(clip_paths)} audio={len(audio_segments)} "
            f"scenes={len(scenes)}")

    os.makedirs("output/tmp", exist_ok=True)
    hook = scenes[0].get("hook") or ""

    # 1) render each scene to its own temp MP4 (bounded memory)
    scene_files = []
    for i, (clip_path, seg, scene) in enumerate(zip(clip_paths, audio_segments, scenes)):
        duration = float(seg.get("duration", 4.0)) + 0.4
        base = _build_scene_clip(clip_path, duration)

        cap_img = _caption_strip(scene.get("caption_roman") or scene.get("caption", ""),
                                 scene.get("emotion", "dark"))
        cap_tmp = f"output/tmp/caption_{i}.png"
        cap_img.save(cap_tmp)
        cap_clip = (ImageClip(cap_tmp).set_duration(duration)
                    .set_position(("center", HEIGHT - 430)))
        layers = [base, cap_clip]

        # hook overlay on scene 0 (first 2.2s)
        if i == 0 and hook:
            hook_img = _hook_overlay(hook)
            hook_tmp = "output/tmp/hook_overlay.png"
            hook_img.save(hook_tmp)
            layers.append(ImageClip(hook_tmp).set_duration(min(2.2, duration))
                          .set_position(("center", 0)))

        # loop trick: hook re-appears at the END of the last scene
        is_last = i == len(scenes) - 1
        if is_last and hook and duration >= 2.0:
            loop_dur = min(1.4, duration * 0.3)
            if loop_dur >= 0.5:
                loop_img = _hook_overlay(hook)
                loop_tmp = "output/tmp/loop_trick.png"
                loop_img.save(loop_tmp)
                layers.append(ImageClip(loop_tmp).set_duration(loop_dur)
                              .set_position(("center", 0))
                              .set_start(duration - loop_dur))
                logger.info("Loop trick baked into scene %d (%.1fs)", i, loop_dur)

        scene_clip = CompositeVideoClip(layers, size=(WIDTH, HEIGHT)).set_duration(duration)
        scene_file = f"output/tmp/scene_{i:02d}.mp4"
        scene_clip.write_videofile(
            scene_file, fps=FPS, codec="libx264", audio_codec="aac", bitrate="4000k",
            ffmpeg_params=["-pix_fmt", "yuv420p"], logger=None,
            threads=max(1, (os.cpu_count() or 2) - 1))
        scene_files.append(scene_file)
        scene_clip.close()
        base.close()
        try:
            cap_clip.close()
        except Exception:
            pass
        gc.collect()

    # 2) concat scene files with ffmpeg demuxer (no MoviePy memory)
    list_file = "output/tmp/concat.txt"
    with open(list_file, "w") as fh:
        for f in scene_files:
            fh.write(f"file '{Path(f).resolve()}'\n")
    silent_video = "output/tmp/silent.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
         "-c", "copy", silent_video], check=True, capture_output=True)

    # 3) audio track (length = silent video duration)
    dur = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", silent_video],
        capture_output=True, text=True).stdout.strip())
    track = _build_audio(audio_segments, total_duration=dur)

    # 4) mux
    os.makedirs("output", exist_ok=True)
    if track and os.path.exists(track):
        subprocess.run(
            ["ffmpeg", "-y", "-i", silent_video, "-i", track,
             "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
             "-movflags", "+faststart", out_path],
            check=True, capture_output=True)
    else:
        subprocess.run(
            ["ffmpeg", "-y", "-i", silent_video, "-c:v", "copy",
             "-movflags", "+faststart", out_path], check=True, capture_output=True)

    logger.info("🎬 Video: %s (%.1fs)", out_path, dur)
    return out_path


def generate_thumbnail(first_visual: str, hook: str = "") -> str:
    img = Image.open(first_visual).convert("RGB").resize((WIDTH, HEIGHT))
    arr = np.asarray(img).astype(np.float32)
    arr *= 0.7
    arr = (arr - 128.0) * 1.2 + 118.0
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    if hook:
        ov = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        font = _load_font(56)
        lines = textwrap.wrap(hook, 22)
        box_h = 70 * len(lines) + 40
        d.rounded_rectangle([50, 160, WIDTH - 50, 160 + box_h], radius=22,
                            fill=(140, 10, 10, 210))
        y = 175
        for line in lines:
            w = d.textlength(line, font=font)
            d.text(((WIDTH - w) / 2, y), line, font=font, fill=(255, 255, 255, 255),
                   stroke_width=2, stroke_fill=(0, 0, 0))
            y += 72
        img = img.convert("RGBA"); img.alpha_composite(ov); img = img.convert("RGB")

    os.makedirs("output", exist_ok=True)
    p = "output/thumbnail.jpg"
    img.save(p, quality=90)
    return p


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # offline demo: procedural visuals + silent segments
    from visuals import generate_procedural_scene
    scenes = [{"caption": f"Scene {i} — test narration for the build.", 
               "caption_roman": f"Scene {i} — test narration for the build.",
               "emotion": "dark"} for i in range(4)]
    clips = [{"path": generate_procedural_scene(i, "dark"), "source": "proc"} for i in range(4)]
    segs = [{"path": None, "duration": 3.0, "text": s["caption"]} for s in scenes]
    build_short([c["path"] for c in clips], segs, scenes)
