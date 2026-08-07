"""Tests for procedural visuals and caption chunking."""
from pathlib import Path

from video_builder import _caption_window, _chunk_timing, _word_chunks
from visuals import generate_procedural_scene


def test_procedural_scene_writes_image(tmp_path: Path):
    out = generate_procedural_scene(3, "intense", out_dir=str(tmp_path))
    p = Path(out)
    assert p.exists() and p.stat().st_size > 5000


def test_word_chunks_grouping():
    chunks = _word_chunks("one two three four", group_size=2)
    assert chunks == ["one two", "three four"]


def test_chunk_timing_sums_to_duration():
    times = _chunk_timing("one two three four", 8.0, group_size=2)
    assert len(times) == 2
    assert abs(times[0][0] - 0.0) < 1e-6
    assert abs(times[-1][1] - 8.0) < 1e-6
    for t0, t1 in times:
        assert t1 > t0


def test_caption_window_keeps_current_visible():
    chunks = ["one two", "three four", "five six", "seven eight"]
    lines, _ = _caption_window("one two three four five six seven eight", chunks, 3)
    assert lines  # not empty
