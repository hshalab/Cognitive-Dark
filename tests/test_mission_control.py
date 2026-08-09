"""Tests for Mission Control (read-only health/growth audit)."""
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ml_engine import LearningSystem


def test_mission_control_writes_report(tmp_path: Path):
    store_dir = tmp_path / "data"
    store_dir.mkdir()
    ml = LearningSystem(store_path=store_dir / "learning_store.json")
    ml.apply_reward("cults::question_hook::morning", "r", 2.0)
    # seed 7 days of youtube posts so cadence is healthy
    now = datetime.now(timezone.utc)
    for i in range(7):
        d = (now.date() - timedelta(days=i)).isoformat()
        ml.data["post_log"][d] = {"youtube": {"count": 1,
                                              "last_ts": (now - timedelta(days=i)).isoformat()}}
    ml.save()

    env = {k: v for k, v in os.environ.items()}
    env["CD_DATA_DIR"] = str(store_dir)
    r = subprocess.run(
        [sys.executable, "scripts/mission_control.py"],
        cwd=Path(__file__).resolve().parent.parent,
        capture_output=True, text=True, env=env, timeout=120)
    report = store_dir / "health_report.md"
    assert report.exists(), f"report missing; stderr={r.stderr[:500]}"
    text = report.read_text(encoding="utf-8")
    assert "Mission Control" in text
    assert "GROWTH PLAYBOOK" in text
    assert "youtube" in text


def test_mission_control_flags_broken_store(tmp_path: Path):
    store_dir = tmp_path / "data"
    store_dir.mkdir()
    path = store_dir / "learning_store.json"
    path.write_text("<<<<<<< corrupted", encoding="utf-8")  # no events either
    env = {k: v for k, v in os.environ.items()}
    env["CD_DATA_DIR"] = str(store_dir)
    r = subprocess.run(
        [sys.executable, "scripts/mission_control.py"],
        cwd=Path(__file__).resolve().parent.parent,
        capture_output=True, text=True, env=env, timeout=120)
    assert r.returncode == 1  # broken store = problems found
    report = store_dir / "health_report.md"
    assert report.exists()
    assert "store" in report.read_text(encoding="utf-8").lower()
