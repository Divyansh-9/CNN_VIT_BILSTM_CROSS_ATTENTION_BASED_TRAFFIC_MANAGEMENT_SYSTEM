"""A short run must not silently replace a long one's weights (P47).

`train_mfstnet.py` already refuses to let a verification run overwrite
`ablation.csv` when a longer run wrote it. Checkpoints had no such rule, and a
3,000-step `--smoke` run wrote to byte-identical path as a 500,000-step
training run — a `.zip` records weights, never how long they were trained for.

These test the guard directly rather than through `train()`, because the point
is the decision, not SUMO.
"""

from __future__ import annotations

import json

import pytest

from scripts.train_ppo import guard_checkpoint, sidecar_path


def write_checkpoint(tmp_path, name="ppo_surrogate_saturated_seed42.zip",
                     timesteps=None, smoke=False):
    path = tmp_path / name
    path.write_bytes(b"not really a model")
    if timesteps is not None:
        sidecar_path(path).write_text(
            json.dumps({"timesteps": timesteps, "smoke": smoke}),
            encoding="utf-8")
    return path


def test_absent_checkpoint_is_allowed(tmp_path):
    guard_checkpoint(tmp_path / "nothing.zip", 500_000)


def test_shorter_run_refuses_to_replace_longer(tmp_path):
    path = write_checkpoint(tmp_path, timesteps=500_000)
    with pytest.raises(SystemExit) as caught:
        guard_checkpoint(path, 3_000)
    message = str(caught.value)
    # The numbers have to be IN the message. "refused" alone sends the reader
    # looking for which run they just protected.
    assert "500,000" in message and "3,000" in message


def test_longer_run_supersedes_shorter(tmp_path):
    path = write_checkpoint(tmp_path, timesteps=3_000, smoke=True)
    guard_checkpoint(path, 500_000)


def test_equal_length_reruns_are_allowed(tmp_path):
    """Re-running the same length is a reproducibility check, not a mistake."""
    path = write_checkpoint(tmp_path, timesteps=500_000)
    guard_checkpoint(path, 500_000)


def test_checkpoint_without_a_sidecar_is_refused(tmp_path):
    """The case every pre-P47 checkpoint on disk is in.

    Unknown length cannot be compared, and an unknown-length checkpoint is
    exactly what let a 16-August file read as that day's output.
    """
    path = write_checkpoint(tmp_path)
    with pytest.raises(SystemExit) as caught:
        guard_checkpoint(path, 500_000)
    assert "no provenance sidecar" in str(caught.value)


def test_force_overrides_every_refusal(tmp_path):
    for kwargs in ({}, {"timesteps": 500_000}):
        path = write_checkpoint(tmp_path, name=f"c{len(kwargs)}.zip", **kwargs)
        guard_checkpoint(path, 3_000, force=True)


def test_smoke_flag_is_named_in_the_refusal(tmp_path):
    """A smoke checkpoint should say so, so the fix is obvious: delete it."""
    path = write_checkpoint(tmp_path, timesteps=500_000, smoke=True)
    with pytest.raises(SystemExit) as caught:
        guard_checkpoint(path, 3_000)
    assert "smoke" in str(caught.value)


def test_sidecar_sits_beside_the_zip_not_instead_of_it(tmp_path):
    """`.with_suffix` would turn `x.zip` into `x.provenance.json` and lose the
    association; the sidecar has to keep the full checkpoint name."""
    path = tmp_path / "ppo_surrogate_saturated_seed42.zip"
    assert sidecar_path(path).name.startswith(path.name)
