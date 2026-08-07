"""Tests for platform credential resolution and FB epoch conversion."""
import json
from pathlib import Path

import platforms.youtube as yt
from platforms.facebook import _to_epoch


def test_youtube_resolve_none_without_env(monkeypatch):
    for k in ("YOUTUBE_CREDENTIALS", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "REFRESH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    assert yt._resolve_credentials() == (None, False)


def test_youtube_resolve_split_oauth(monkeypatch, tmp_path):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "csec")
    monkeypatch.setenv("REFRESH_TOKEN", "rtok")
    monkeypatch.delenv("YOUTUBE_CREDENTIALS", raising=False)
    path, is_path = yt._resolve_credentials()
    assert is_path is False
    data = json.loads(Path(path).read_text())
    assert data["client_id"] == "cid"
    assert data["refresh_token"] == "rtok"
    assert data["token_uri"] == "https://oauth2.googleapis.com/token"
    assert "youtube.upload" in " ".join(data["scopes"])


def test_youtube_resolve_raw_json(monkeypatch, tmp_path):
    raw = json.dumps({"type": "authorized_user", "client_id": "x"})
    monkeypatch.setenv("YOUTUBE_CREDENTIALS", raw)
    for k in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "REFRESH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    path, is_path = yt._resolve_credentials()
    assert is_path is False
    assert json.loads(Path(path).read_text())["client_id"] == "x"


def test_fb_epoch_handles_none_str_and_naive():
    assert _to_epoch(None) == ""
    assert _to_epoch("not-a-date") == ""
    epoch = _to_epoch("2026-08-07T12:00:00+00:00")
    assert epoch.isdigit()
    assert int(epoch) > 1_700_000_000
    # Naive datetime must be treated as UTC rather than crash
    from datetime import datetime
    assert _to_epoch(datetime(2026, 8, 7, 12, 0, 0)).isdigit()


def test_instagram_duration_ms_fallback(monkeypatch):
    import platforms.instagram as ig
    # Force ffprobe failure path -> safe default without raising
    monkeypatch.setattr(ig.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError()))
    assert ig._duration_ms("missing.mp4") == 60_000
