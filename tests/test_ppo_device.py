"""PPO trains on the CPU, deliberately (P38).

Stable-Baselines3 selects CUDA whenever torch can see a GPU. For an MlpPolicy
that is the wrong call and SB3 says so itself in a warning — the observation is
a 16-dim vector (PRD §13.1) and the network is two small dense layers, so
per-step kernel launch and host transfer cost more than the arithmetic saves.

Measured on this machine, 8,192 timesteps: **8.0 s on CPU against 16.2 s on
CUDA.**

The trap is that this only started mattering the day torch became a CUDA
build. A benchmark taken before that ran on the CPU by accident and one taken
after would have run on the GPU by accident, and the two would not have been
comparable — with nothing in either result saying why.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TRAIN_PPO = Path(__file__).resolve().parent.parent / "scripts" / "train_ppo.py"


def test_ppo_is_constructed_with_an_explicit_device():
    """Pinned as source rather than behaviour, because reproducing it needs a
    GPU and the point is that the choice is written down, not inferred."""
    source = TRAIN_PPO.read_text(encoding="utf-8")
    constructor = source[source.index("model = PPO("):]
    constructor = constructor[: constructor.index("\n    )")]
    assert 'device="cpu"' in constructor, (
        "PPO must pin its device. Left to Stable-Baselines3 it picks CUDA "
        "whenever torch can see a GPU, which is 2x slower for an MlpPolicy "
        "and silently changes what a benchmark was measured on."
    )


def test_the_reason_is_recorded_next_to_the_choice():
    """A bare device='cpu' invites a later reader to 'fix' it."""
    source = TRAIN_PPO.read_text(encoding="utf-8")
    window = source[max(0, source.index('device="cpu"') - 1200):
                    source.index('device="cpu"')]
    assert "MlpPolicy" in window
    assert "slower" in window


def test_no_other_training_script_pins_the_device_away_from_auto():
    """MFSTNet is the opposite case — it is convolutional, it wants the GPU,
    and its `--device` defaults to auto. If that ever changed to a hardcoded
    cpu the 12.6x would quietly disappear."""
    train_mfstnet = (Path(__file__).resolve().parent.parent
                     / "scripts" / "train_mfstnet.py").read_text(encoding="utf-8")
    match = re.search(r'add_argument\(\s*"--device",\s*default="(\w+)"', train_mfstnet)
    assert match, "train_mfstnet must expose --device"
    assert match.group(1) == "auto"
