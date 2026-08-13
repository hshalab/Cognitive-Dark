"""2026 Algorithm Video Repair — unit tests (V3.6).

Pure functions ke liye: title/description boost idempotent hona chahiye,
pipe-stuffing na ho, aur FB/IG caption builders honest hon.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from repair_all_videos import (
    fb_update_post_text,
    yt_boost_description,
    yt_boost_title,
    yt_keyword_for_title,
)


def test_yt_title_boost_adds_keyword_naturally():
    title = "Why Innocent People Confess"
    new, changed = yt_boost_title(title, "lie detection")
    assert changed is True
    assert "lie detection" in new.lower()
    # V3.6: pipe-stuffing ("| Keyword") nahi — natural colon merge
    assert "|" not in new
    assert len(new) <= 100


def test_yt_title_boost_idempotent():
    title = "Why Innocent People Confess"
    once, _ = yt_boost_title(title, "lie detection")
    twice, changed2 = yt_boost_title(once, "lie detection")
    assert changed2 is False          # dobara kuch nahi badalta
    assert twice == once
    assert twice.lower().count("lie detection") == 1


def test_yt_title_boost_no_pipe_stuffing():
    title = "The Cult That Banned These 3 Questions"
    new, _ = yt_boost_title(title, "cult psychology")
    assert "|" not in new


def test_yt_description_idempotent_no_duplicate_chapters():
    desc = "Some existing description about psychology."
    once, changed1 = yt_boost_description(desc, "cult psychology")
    assert changed1 is True
    twice, changed2 = yt_boost_description(once, "cult psychology")
    assert changed2 is False          # dobara chalane par duplicate nahi
    assert once.lower().count("chapters") == 1
    assert twice == once


def test_yt_description_keeps_existing_content():
    desc = "Original creator description with subscribe and like CTA. Educational content."
    new, _changed = yt_boost_description(desc, None)
    # existing content intact hona chahiye, duplicate CTA/disclaimer nahi
    assert "Original creator description" in new
    assert new.lower().count("subscribe for daily") <= 1


def test_yt_keyword_detection():
    assert yt_keyword_for_title("How Scams Work Psychology") is not None
    assert yt_keyword_for_title("Gaslighting red flags explained") is not None
    assert yt_keyword_for_title("Random unrelated words") is None


def test_fb_update_helper_signature():
    # ladder helper mojood hai (network call test se bahar — sirf contract)
    assert callable(fb_update_post_text)
