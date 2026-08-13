"""2026 Algorithm Video Repair — unit tests (V3.6).

Pure functions ke liye: title/description boost idempotent hona chahiye,
pipe-stuffing na ho, aur FB/IG caption builders honest hon.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from repair_all_videos import (
    _clean_legacy_title,
    fb_update_post_text,
    yt_boost_description,
    yt_boost_title,
    yt_keyword_for_title,
)


def test_cleanup_only_change_marks_changed():
    """V3.6-repair-7 ka bug: jab sirf cleanup title badle (keyword pehle se
    satisfied) to changed=False reh kar update SKIP ho jati thi — 2 live
    videos is liye kabhi fix nahi hue. Ab cleanup ka change bhi count hota."""
    from repair_all_videos import yt_boost_title
    new, changed = yt_boost_title(
        "Stop: Mkultra: the Cia's Mind-Control Program: Nobody Tells You",
        "mkultra psychology")
    assert changed is True
    assert new == "Mkultra: the Cia's Mind-Control Program"


def test_clean_legacy_title_removes_old_artifacts():
    # purane repair code ke "Why — " prefix + pipe keyword
    assert _clean_legacy_title(
        "Why — Financial Abuse: Control Through Money | Coercive Control Signs") \
        == "Financial Abuse: Control Through Money"
    # purane seo ke random power-word suffix
    assert _clean_legacy_title("How Crowds Change Your Brain in Minutes: Never") \
        == "How Crowds Change Your Brain in Minutes"
    # ": Nobody Tells You" suffix
    assert _clean_legacy_title("The Feed That Outrages You: Nobody Tells You") \
        == "The Feed That Outrages You"
    # natural titles untouched
    assert _clean_legacy_title("Why Smart People Join Cults") \
        == "Why Smart People Join Cults"


def test_boost_repairs_legacy_stuffed_title():
    # legacy "| Keyword" pipe wala title → clean "Hook: Keyword" form
    new, changed = yt_boost_title(
        "Why Innocent People Confess | Lie Detection", "lie detection")
    assert changed is True
    assert "|" not in new
    assert "Lie Detection" in new
    assert len(new) <= 100


def test_repair_never_injects_new_prefixes():
    """Repair sirf junk REMOVE karta hai — "The Truth:" jaise naye prefix
    kabhi ADD nahi karta (purana bug: cleaner strip karta, boost wapas
    jod deta tha — circular junk)."""
    new, _ = yt_boost_title(
        "Love Bombing: the Cult Recruitment Pipeline", "cult psychology")
    assert not new.startswith("The Truth:")
    assert not new.startswith("Stop:")
    assert not new.startswith("Why:")
    assert "cult" in new.lower()   # keyword token satisfaction — no double merge


def test_clean_full_legacy_chains():
    # live channel ke 8 asli junk titles — sab clean hone chahiye
    cases = [
        ("The Truth: Love Bombing: the Cult Recruitment Pipeline: Cult Psychology",
         "cult psychology", "Love Bombing: the Cult Recruitment Pipeline"),
        ("Stop: Mkultra: the Cia's Mind-Control Program: Nobody Tells You",
         "mind control psychology", "Mkultra: the Cia's Mind-Control Program"),
        ("How Crowds Change your Brain in Minutes: Never: Mass Psychology",
         "mass psychology", "How Crowds Change your Brain in Minutes: Mass Psychology"),
        ("How One Ad Manipulated a Country | Mkultra Explained | Mkultra Psychology",
         "MKUltra explained", "How One Ad Manipulated a Country: Mkultra Explained"),
    ]
    for title, kw, expected in cases:
        new, _ = yt_boost_title(title, kw)
        assert new == expected, f"{new!r} != {expected!r}"
        assert "|" not in new
        assert "The Truth:" not in new


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
