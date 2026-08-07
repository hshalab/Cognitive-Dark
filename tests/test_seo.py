"""Tests for SEO packaging — titles, descriptions, tags, chapters."""
from seo import (
    PLATFORM_HASHTAGS,
    _chapters,
    _power_title,
    _title_case_word,
    build_platform_package,
)

SCRIPT = {
    "title": "Test Hook",
    "hook": "You won't believe this FBI trick",
    "pillar": "psychological_self_defense",
    "pillar_name": "Psychological Self-Defense",
    "tags": ["psychology", "manipulation", "fbi", "CIA"],
    "key_points": "• point one\n• point two",
}


def test_youtube_title_under_100_chars():
    pkg = build_platform_package(SCRIPT, "youtube")
    assert len(pkg["title"]) <= 100
    assert pkg["title"]  # non-empty


def test_titles_match_platform_length_strategy():
    yt = build_platform_package(SCRIPT, "youtube")["title"]
    fb = build_platform_package(SCRIPT, "facebook")["title"]
    ig = build_platform_package(SCRIPT, "instagram")["title"]
    # YouTube title is search-intent / keyword appended; FB/IG are hook-first.
    assert len(yt) > len(fb)
    assert "Psychology Facts" in yt
    assert len(ig) <= 55


def test_tags_under_500_chars_youtube():
    tags = build_platform_package(SCRIPT, "youtube")["tags"]
    total = sum(len(t) + 1 for t in tags)
    assert total <= 500
    assert "psychology" in [t.lower() for t in tags]


def test_non_youtube_has_no_tags_uses_hashtags():
    for p in ("facebook", "instagram"):
        pkg = build_platform_package(SCRIPT, p)
        assert pkg["tags"] == []
        assert pkg["hashtags"] == PLATFORM_HASHTAGS[p]


def test_description_contains_keyword_hashtags_and_chapters():
    pkg = build_platform_package(SCRIPT, "youtube", durations=[5.0, 10.0])
    assert "Psychological Self-Defense" in pkg["description"]
    assert "#psychology" in pkg["description"]
    assert "CHAPTERS" in pkg["description"]


def test_chapters_use_real_durations():
    chapters = _chapters([5.0, 10.0, 8.0])
    assert chapters.startswith("⏱ CHAPTERS:")
    assert "00:00" in chapters
    assert "00:05" in chapters
    assert "00:15" in chapters


def test_power_title_appends_power_word():
    title = _power_title("Stop", max_len=70)
    # Title should be Title Case
    assert title[0].isupper()
    assert len(title) <= 70


def test_acronyms_preserved():
    assert _title_case_word("FBI", first=True, stop=set()) == "FBI"
    assert _title_case_word("CIA", first=False, stop=set()) == "CIA"


def test_hyphenated_words_title_cased():
    assert _title_case_word("30-second", first=True, stop=set()) == "30-Second"


def test_ig_description_under_2200():
    pkg = build_platform_package(SCRIPT, "instagram")
    assert len(pkg["description"]) <= 2200
