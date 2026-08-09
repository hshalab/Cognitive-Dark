"""Tests for the 2026 Algorithm Playbook (V2.9)."""
from algorithm_playbook import audit_package, best_platform_for


def test_youtube_package_score():
    pkg = {"title": "Stop Letting Them Control You | Psychology Facts",
           "description": ("Psychology: how coercion works and how to protect "
                           "yourself. " * 8),
           "tags": ["psychology", "coercion", "mind control"],
           "duration_s": 48}
    a = audit_package(pkg, "youtube")
    assert a["platform"] == "youtube"
    assert a["score"] >= 0.5
    assert a["total"] > 0


def test_fb_package_cta():
    pkg = {"title": "Stop This Pattern", "description": "What would you add? "
           "Comment below. " * 5,
           "tags": ["a", "b", "c", "d", "e", "f", "g", "h"],
           "duration_s": 60}
    a = audit_package(pkg, "facebook")
    assert a["passed"] >= 2


def test_ig_save_framing():
    pkg = {"title": "5 Signs", "description": "Save this for later. " * 5,
           "tags": ["a"] * 15, "duration_s": 80}
    a = audit_package(pkg, "instagram")
    assert a["score"] > 0.3


def test_best_platform_hint():
    assert best_platform_for({"hook": "5 Signs You're Being Controlled"}) == "instagram"
    assert best_platform_for({"hook": "What would you do in this situation?"}) == "facebook"
    assert best_platform_for({"hook": "The truth about coercion"}) == "youtube"
