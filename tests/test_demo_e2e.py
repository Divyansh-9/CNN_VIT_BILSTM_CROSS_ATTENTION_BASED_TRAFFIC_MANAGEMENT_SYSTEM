"""scripts/demo_e2e.py: refuses what it cannot run, before starting anything (D17)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.demo_e2e import APPROACHES, CHECKS, main  # noqa: E402


def test_a_missing_mosquitto_is_refused(tmp_path, capsys):
    with pytest.raises(SystemExit) as stop:
        main(["--mosquitto", str(tmp_path / "absent.exe"), "--clips-root", str(tmp_path)])
    assert stop.value.code == 2
    assert "--mosquitto is not a file" in capsys.readouterr().err


def test_a_missing_clip_is_refused(tmp_path, capsys):
    exe = tmp_path / "mosquitto.exe"
    exe.write_bytes(b"")
    with pytest.raises(SystemExit) as stop:
        main(["--mosquitto", str(exe), "--clips-root", str(tmp_path)])
    assert stop.value.code == 2
    assert "not found under --clips-root" in capsys.readouterr().err


def test_every_lane_maps_to_a_distinct_approach_and_all_nine_checks_are_named():
    lanes = dict(a.split("=") for a in APPROACHES)
    assert sorted(lanes.values()) == ["E", "N", "S", "W"]
    assert CHECKS == tuple(f"E{i}" for i in range(1, 10))
