#!/usr/bin/env python3
"""
Cognitive Dark V2 — Video Builder (USA Viral Style, MoviePy 1.0.3 pinned).

USA-STYLE package:
  • FAST CUTS  — every scene is micro-cut into ~2.4s sub-clips with a zoom
                 punch on each cut (the relentless forward-motion look).
  • USA CAPTIONS — word-by-word karaoke captions: spoken words stay white,
                 the CURRENT word pops yellow (255,210,60), upcoming words
                 dimmed. This is the Alex-Hormozi / top USA faceless style.
  • HOOK OVERLAY — big red hook badge in the first 2.2s.
  • LOOP TRICK  — hook re-appears at the very end for seamless rewatch.
  • Memory-safe — one scene rendered at a time, ffmpeg concat at the end.
"""

import glob
import logging
import math
import os
import random
import re
import subprocess
import textwrap
from pathlib import Path

import compat  # patch PIL before moviepy import (Image.ANTIALIAS)
assert compat  # keep module loaded for its side-effect patch
import numpy as np
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("video_builder")

WIDTH, HEIGHT = 1080, 1920
FPS = 30
MUSIC_VOLUME = float(os.environ.get("MUSIC_VOLUME", "0.05"))

from config.settings import (USA_STYLE, VIDEO_THREADS, OUTPUT_DIR, TMP_DIR,
                             MUSIC_DIR)

# V2.1: anchor all working paths to config (V2 hardcoded "output/..." and
# "assets/music" relative to the CWD → broke when run from another folder).
OUT = str(OUTPUT_DIR)
TMP = str(TMP_DIR)

CUT_SECS = max(USA_STYLE["min_cut_seconds"], USA_STYLE["cut_seconds"])
WORDS_PER_GROUP = USA_STYLE["caption_words_per_group"]
CAP_Y = USA_STYLE["caption_y"]
CAP_H = USA_STYLE["caption_h"]
HL = USA_STYLE["highlight_color"]
DIM_A = USA_STYLE["dim_future_alpha"]
PAST = USA_STYLE["past_color"]
PUNCH = USA_STYLE["punch_zoom"]
PUNCH_DUR = USA_STYLE["punch_duration"]
HOOK_SECS = USA_STYLE["hook_seconds"]
LOOP_SECS = USA_STYLE["loop_seconds"]

FONT_CANDIDATES = [
    # V2.4 USA VIRAL: bundled condensed display faces (OFL) — the
    # MrBeast/Hormozi look. DejaVu only as last resort.
    "assets/fonts/Anton-Regular.ttf",
    "assets/fonts/BebasNeue-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "assets/fonts/DejaVuSans-Bold.ttf",
]


def _load_font(size: int):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


# ─────────────────────────────────────────────────────────────
# USA word-by-word captions
# ─────────────────────────────────────────────────────────────
def _split_words(text: str) -> list:
    return [w for w in re.split(r"\s+", text.strip()) if w]


def _word_chunks(text: str, group_size: int = None) -> list:
    """Group words into pop-chunks (default 2 words per chunk)."""
    group_size = group_size or WORDS_PER_GROUP
    words = _split_words(text)
    if not words:
        return []
    chunks = [words[i:i + group_size] for i in range(0, len(words), group_size)]
    return [" ".join(c) for c in chunks]


def _chunk_timing(text: str, narration_dur: float, group_size: int = None) -> list:
    """Estimate (start, end) per word-chunk, proportional to word length.

    (Kokoro-ONNX gives no word timestamps, so we distribute the narration
    duration by character weight — close enough for karaoke captions.)
    """
    words = _split_words(text)
    if not words:
        return []
    weights = [len(w) + 1 for w in words]
    times = []
    chunk_weights = []
    group_size = group_size or WORDS_PER_GROUP
    for i in range(0, len(words), group_size):
        chunk_weights.append(sum(weights[i:i + group_size]))
    ctotal = sum(chunk_weights) or 1
    start = 0.0
    for w in chunk_weights:
        frac = w / ctotal
        times.append((start, start + frac * narration_dur))
        start += frac * narration_dur
    return times


def _chunk_word_bounds(chunks: list) -> list:
    """Global word-index (start, end) for each caption chunk."""
    bounds, acc = [], 0
    for ch in chunks:
        n = len(_split_words(ch))
        bounds.append((acc, acc + n))
        acc += n
    return bounds


def _caption_window(full_text: str, chunks: list, current_idx: int) -> tuple:
    """Sliding 2-line window around the current chunk.

    V2 rendered the WHOLE caption but hard-truncated after 2 lines, so every
    word past ~line 2 never appeared on screen. V2.1 scrolls the window so the
    current word-chunk is ALWAYS visible (karaoke never disappears mid-scene).

    Returns (lines_to_render, first_global_word_index).
    """
    lines = textwrap.wrap(full_text, width=30) or [full_text]
    line_words = [ln.split(" ") for ln in lines]
    starts, acc = [], 0
    for lw in line_words:
        starts.append(acc)
        acc += len(lw)

    bounds = _chunk_word_bounds(chunks)
    if current_idx >= len(bounds):
        current_idx = len(bounds) - 1
    cw = bounds[current_idx][0] if bounds else 0

    line_of = 0
    for li, st in enumerate(starts):
        if st <= cw < st + len(line_words[li]):
            line_of = li
            break
    a = line_of if line_of + 1 < len(lines) else max(0, line_of - 1)
    b = min(len(lines), a + 2)
    return lines[a:b], starts[a]


def _caption_strip_usa(full_text: str, chunks: list, current_idx: int,
                       emotion: str = "dark") -> Image.Image:
    """V2.4 USA VIRAL caption style (bundled Anton face + effects):

    • ALL-CAPS condensed Anton — the MrBeast/Hormozi look
    • 1-2 word chunk, HUGE (110px), centered
    • EFFECTS: slight rotation jitter per chunk, heavy black stroke +
      drop shadow, emotion color pop (yellow default)
    • Motion pop-zoom is applied at clip level in build_short
    """
    strip = Image.new("RGBA", (WIDTH, CAP_H), (0, 0, 0, 0))
    if current_idx >= len(chunks):
        return strip
    text = chunks[current_idx].upper()

    accents = {"intense": (255, 90, 60), "revelatory": (255, 210, 60),
               "chilling": (110, 190, 255), "mysterious": (200, 170, 255)}
    color = accents.get(emotion, HL)

    size = 116 if len(text) <= 12 else (96 if len(text) <= 20 else 76)
    font = _load_font(size)
    lines = textwrap.wrap(text, width=16) or [text]

    draw = ImageDraw.Draw(strip)
    line_h = size + 30
    y = (CAP_H - line_h * len(lines)) // 2 + 4

    for li, line in enumerate(lines):
        w = draw.textlength(line, font=font)
        x = (WIDTH - w) / 2
        # drop shadow (offset black) + heavy stroke + color fill
        draw.text((x + 5, y + 6), line, font=font, fill=(0, 0, 0, 200))
        draw.text((x, y), line, font=font, fill=color + (255,),
                  stroke_width=5, stroke_fill=(0, 0, 0))
        y += line_h

    # rotation jitter per chunk (deterministic) — energy without chaos.
    # expand=False keeps the canvas fixed so on-screen position stays exact.
    angle = ((current_idx * 7) % 7) - 3
    if angle:
        strip = strip.rotate(angle, expand=False, resample=Image.BICUBIC)
    return strip


def _hook_overlay_usa(hook: str) -> Image.Image:
    """V2.4: condensed ALL-CAPS hook badge (Bebas/Anton) — USA viral look."""
    font = _load_font(92)
    ov = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(ov)
    lines = textwrap.wrap(hook.upper(), width=18) or [hook.upper()]
    if len(lines) > 3:
        lines = lines[:3] + ["..."]
    box_h = 122 * len(lines) + 80
    # layered badge: black offset + red main (depth effect)
    draw.rounded_rectangle([46, 128, WIDTH - 34, 128 + box_h], radius=26,
                           fill=(0, 0, 0, 200))
    draw.rounded_rectangle([40, 120, WIDTH - 40, 120 + box_h], radius=26,
                           fill=(150, 12, 12, 240))
    y = 150
    for line in lines:
        w = draw.textlength(line, font=font)
        x = (WIDTH - w) / 2
        draw.text((x + 4, y + 5), line, font=font, fill=(0, 0, 0, 210))
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255),
                  stroke_width=3, stroke_fill=(60, 5, 5))
        y += 122
    return ov


# ─────────────────────────────────────────────────────────────
# visual cut building
# ─────────────────────────────────────────────────────────────
def _build_scene_clip(clip_path: str, duration: float, punch: bool = False) -> object:
    """Cover-cropped 9:16 clip; images route to image path; optional zoom punch."""
    if clip_path.lower().endswith((".jpg", ".jpeg", ".png")):
        return _build_image_clip(clip_path, duration, punch=punch)
    from moviepy.editor import VideoFileClip
    clip = VideoFileClip(clip_path)
    if clip.duration is None or clip.duration < 0.5:
        clip.close()
        raise RuntimeError("clip too short")
    w, h = clip.w, clip.h
    s = max(WIDTH / w, HEIGHT / h)
    scaled = clip.resize(width=int(w * s + 0.5), height=int(h * s + 0.5))
    cropped = scaled.crop(x_center=scaled.w / 2, y_center=scaled.h / 2,
                          width=WIDTH, height=HEIGHT)
    out = cropped.subclip(0, min(duration, cropped.duration - 0.05)
                          if cropped.duration else duration)
    out = out.set_duration(duration)
    try:
        out = out.without_audio()
    except Exception:
        pass
    if punch:
        out = out.resize(lambda t: 1.0 + PUNCH * min(1.0, t / max(PUNCH_DUR, 0.01)))
    return out


def _build_image_clip(img_path: str, duration: float, punch: bool = False) -> object:
    """Static image cut — punch BAKED via PIL (zero per-frame resampling).

    Memory-safe: renders the zoomed-in start frame once, MoviePy only copies
    frames. The visual punch still reads because each fast cut starts slightly
    zoomed (and real stock clips get a true per-frame punch below).
    """
    from moviepy.editor import ImageClip
    try:
        im = Image.open(img_path).convert("RGB")
        # bake the punch: render the settled (slightly zoomed) frame as the
        # static cut — each fast cut starting tight still reads as a punch.
        zoom = 1.05
        w, h = im.size
        nw, nh = int(w * zoom), int(h * zoom)
        im2 = im.resize((nw, nh), Image.LANCZOS)
        left, top = (nw - w) // 2, (nh - h) // 2
        im2 = im2.crop((left, top, left + w, top + h)).resize((WIDTH, HEIGHT), Image.LANCZOS)
        fit_path = img_path + ".fit.jpg"
        im2.save(fit_path, quality=88)
        base = ImageClip(fit_path).set_duration(duration)
    except Exception:
        base = ImageClip(img_path).set_duration(duration)
    return base.set_position(("center", "center")).set_duration(duration)


# ── music ────────────────────────────────────────────────────
def _pick_music() -> str:
    exact = os.environ.get("MUSIC_TRACK", "").strip()
    tracks = glob.glob(str(MUSIC_DIR / "*.mp3")) + glob.glob(str(MUSIC_DIR / "*.wav"))
    tracks = [t for t in tracks if "ATTRIBUTION" not in t.upper()]
    if exact:
        m = [t for t in tracks if t.endswith(exact)]
        return m[0] if m else None
    dark = [t for t in tracks if any(v in t.lower() for v in
                                     ["dark", "ambient", "suspense", "ominous", "void"])]
    pool = dark or tracks
    return random.choice(pool) if pool else None


# ─────────────────────────────────────────────────────────────
# main build (memory-safe: one scene at a time)
# ─────────────────────────────────────────────────────────────
def _build_audio(audio_segments: list, total_duration: float,
                 scene_starts: list = None) -> str:
    from moviepy.editor import AudioFileClip, CompositeAudioClip
    tracks = []
    # V2.6 SYNC FIX: place each voice at its EXACT scene start time.
    # (V2 concatenated voices back-to-back while video scenes carry a +0.4s
    #  pad each → captions drifted ~0.4s later per scene; by scene 6 the
    #  voice led captions by ~2.4s.)
    if scene_starts:
        for seg, start in zip(audio_segments, scene_starts):
            if seg.get("path") and os.path.exists(seg["path"]):
                tracks.append(AudioFileClip(seg["path"]).set_start(start))
    else:
        for seg in audio_segments:
            if seg.get("path") and os.path.exists(seg["path"]):
                tracks.append(AudioFileClip(seg["path"]))
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
    os.makedirs(TMP, exist_ok=True)
    track_path = os.path.join(TMP, "narration.m4a")
    CompositeAudioClip(tracks).write_audiofile(track_path, fps=44100, codec="aac", logger=None)
    for t in tracks:
        try:
            t.close()
        except Exception:
            pass
    return track_path


def build_short(scene_visuals: list, audio_segments: list, scenes: list,
                out_path: str = None, hook: str = None) -> str:
    """scene_visuals: list (per scene) of lists (cuts) of clip paths."""
    import gc
    from moviepy.editor import CompositeVideoClip, ImageClip

    if out_path is None:
        out_path = os.path.join(OUT, "final_video.mp4")

    if len(scene_visuals) != len(audio_segments) or len(scene_visuals) != len(scenes):
        raise RuntimeError(
            f"length mismatch: scenes={len(scene_visuals)} audio={len(audio_segments)} "
            f"scenes={len(scenes)}")

    os.makedirs(TMP, exist_ok=True)
    # V2.1.4 FIX: the hook lives at SCRIPT level, not on scenes[0]. V2 read
    # scenes[0].get("hook") → always empty → the hook overlay & loop trick
    # NEVER rendered on any video (missing the critical first-2s hook).
    hook = hook or scenes[0].get("hook") or ""

    # 1) render each scene → temp mp4 (fast cuts + word captions baked in)
    scene_files = []
    scene_starts = []
    running = 0.0
    for i, (visuals, seg, scene) in enumerate(zip(scene_visuals, audio_segments, scenes)):
        duration = float(seg.get("duration", 4.0)) + 0.4
        scene_starts.append(running)
        running += duration
        narration_dur = float(seg.get("duration", 4.0))
        visuals = visuals or [os.path.join(TMP, "none.jpg")]
        caption_text = scene.get("caption_roman") or scene.get("caption", "")
        emotion = scene.get("emotion", "dark")

        layers = []

        # ── FAST CUTS: micro sub-clips with zoom punch ──
        n_cuts = max(1, math.ceil(duration / CUT_SECS))
        for c in range(n_cuts):
            start = c * CUT_SECS
            cdur = min(CUT_SECS, duration - start)
            if cdur < 0.35:
                break
            vpath = visuals[c % len(visuals)]
            cut = _build_scene_clip(vpath, cdur, punch=True).set_start(start)
            layers.append(cut)

        # ── USA WORD CAPTIONS ──
        chunks = _word_chunks(caption_text)
        times = _chunk_timing(caption_text, narration_dur)
        for idx, (grp, (t0, t1)) in enumerate(zip(chunks, times)):
            if t1 - t0 < 0.15:
                continue
            img = _caption_strip_usa(caption_text, chunks, idx, emotion)
            cap_path = os.path.join(TMP, f"cap_{i:02d}_{idx:02d}.png")
            img.save(cap_path)
            # V2.4.1: reliable pop — first 0.15s shows a PIL-prescaled (1.14x)
            # strip, then the normal one. (moviepy's resize-lambda proved
            # time-base fragile → text flew off-frame.)
            big = img.resize((int(WIDTH * 1.14), int(img.height * 1.14)),
                             Image.LANCZOS)
            big_path = cap_path.replace(".png", "_big.png")
            big.save(big_path)
            dy = (big.height - img.height) // 2
            pop = min(0.15, t1 - t0)
            layers.append(ImageClip(big_path)
                          .set_start(t0)
                          .set_duration(pop)
                          .set_position(("center", CAP_Y - dy)))
            if t1 - t0 > pop:
                layers.append(ImageClip(cap_path)
                              .set_start(t0 + pop)
                              .set_duration(t1 - t0 - pop)
                              .set_position(("center", CAP_Y)))

        # ── HOOK overlay (scene 0, first seconds) ──
        if i == 0 and hook:
            h_img = _hook_overlay_usa(hook)
            h_path = os.path.join(TMP, "hook_overlay.png")
            h_img.save(h_path)
            layers.append(ImageClip(h_path).set_duration(min(HOOK_SECS, duration))
                          .set_position(("center", 0)))

        # ── LOOP trick (hook re-appears at the very end) ──
        if i == len(scenes) - 1 and hook and duration >= 2.0:
            loop_dur = min(LOOP_SECS, duration * 0.3)
            if loop_dur >= 0.5:
                l_img = _hook_overlay_usa(hook)
                l_path = os.path.join(TMP, "loop_trick.png")
                l_img.save(l_path)
                layers.append(ImageClip(l_path).set_duration(loop_dur)
                              .set_position(("center", 0))
                              .set_start(duration - loop_dur))

        scene_clip = CompositeVideoClip(layers, size=(WIDTH, HEIGHT)).set_duration(duration)
        scene_file = os.path.join(TMP, f"scene_{i:02d}.mp4")
        scene_clip.write_videofile(
            scene_file, fps=FPS, codec="libx264", audio_codec="aac", bitrate="4000k",
            ffmpeg_params=["-pix_fmt", "yuv420p"], logger=None,
            threads=VIDEO_THREADS)
        scene_files.append(scene_file)
        scene_clip.close()
        for lyr in layers:
            try:
                lyr.close()
            except Exception:
                pass
        gc.collect()

    # 2) concat with ffmpeg demuxer
    list_file = os.path.join(TMP, "concat.txt")
    with open(list_file, "w") as fh:
        for f in scene_files:
            fh.write(f"file '{Path(f).resolve()}'\n")
    silent_video = os.path.join(TMP, "silent.mp4")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
         "-c", "copy", silent_video], check=True, capture_output=True)

    # 3) audio
    dur = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", silent_video],
        capture_output=True, text=True).stdout.strip())
    track = _build_audio(audio_segments, total_duration=dur,
                         scene_starts=scene_starts)

    # 4) mux
    os.makedirs(OUT, exist_ok=True)
    if track and os.path.exists(track):
        # V2.5: loudness-normalize to -14 LUFS (social-standard) so voice is
        # consistently punchy across videos — USA retention hygiene.
        subprocess.run(
            ["ffmpeg", "-y", "-i", silent_video, "-i", track,
             "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
             "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
             "-movflags", "+faststart", out_path],
            check=True, capture_output=True)
    else:
        subprocess.run(
            ["ffmpeg", "-y", "-i", silent_video, "-c:v", "copy",
             "-movflags", "+faststart", out_path], check=True, capture_output=True)

    logger.info("🎬 Video: %s (%.1fs, %d scenes, fast cuts %.1fs + word captions)",
                out_path, dur, len(scene_files), CUT_SECS)
    return out_path


def generate_thumbnail(first_visual: str, hook: str = "") -> str:
    if first_visual.lower().endswith((".mp4", ".mov", ".avi")):
        from moviepy.editor import VideoFileClip
        clip = VideoFileClip(first_visual)
        frame = clip.get_frame(0)
        img = Image.fromarray(frame).convert("RGB").resize((WIDTH, HEIGHT))
        clip.close()
    else:
        img = Image.open(first_visual).convert("RGB").resize((WIDTH, HEIGHT))

    arr = np.asarray(img).astype(np.float32)
    arr *= 0.7
    arr = (arr - 128.0) * 1.2 + 118.0
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    if hook:
        ov = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        font = _load_font(60)
        lines = textwrap.wrap(hook, 20)
        box_h = 76 * len(lines) + 40
        d.rounded_rectangle([50, 150, WIDTH - 50, 150 + box_h], radius=22,
                            fill=(150, 10, 10, 215))
        y = 168
        for line in lines:
            w = d.textlength(line, font=font)
            d.text(((WIDTH - w) / 2, y), line, font=font, fill=(255, 255, 255, 255),
                   stroke_width=2, stroke_fill=(0, 0, 0))
            y += 78
        img = img.convert("RGBA"); img.alpha_composite(ov); img = img.convert("RGB")

    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, "thumbnail.jpg")
    img.save(p, quality=90)
    return p


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from visuals import generate_procedural_scene
    scenes = [{"caption": f"Scene {i} — fast cut test narration for the build.",
               "caption_roman": f"Scene {i} — fast cut test narration for the build.",
               "emotion": "dark"} for i in range(3)]
    visuals = [[generate_procedural_scene(i * 10 + k, "dark") for k in range(3)]
               for i in range(3)]
    segs = [{"path": None, "duration": 4.0, "text": s["caption"]} for s in scenes]
    build_short(visuals, segs, scenes)
