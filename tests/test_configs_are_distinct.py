"""Every ablation config must be a different computation (P56).

Configs B and E returned macro F1 and QWK equal to four decimal places on
fold 0. Two architectures agreeing to that precision is not what "similar
performance" looks like — floating-point noise alone should separate them — so
the obvious reading is a dead flag: `use_gate` or `mode` wired to nothing, or
to a module that is a no-op under the other settings. That is the P26 shape,
where shapes agree, loss falls, and nothing raises.

It is not what happened here: B and E produce **different logits** (max absolute
difference 0.055 at initialisation) from different parameter counts. What
coincides is the `argmax`, and metrics are computed from the argmax.

The distinction matters enough to pin. A dead flag would silently delete a row
from the ablation table — the reader would see eight configs and seven
experiments — and comparing metrics cannot detect it, because metrics are
exactly where a dead flag hides.
"""

from __future__ import annotations

import itertools

import pytest

torch = pytest.importorskip("torch")

from mfstnet.corpus.lanes import LaneCentres  # noqa: E402
from mfstnet.model import MFSTNet, ablation_config, iter_ablation_configs  # noqa: E402
from mfstnet.temporal import lane_masks_from_centres  # noqa: E402
from scripts.seed import set_seed  # noqa: E402

T = 6


def build(name):
    centres = LaneCentres(
        names=tuple(f"lane_{i}" for i in range(4)),
        centres=tuple((0.2 + 0.2 * i, 0.5) for i in range(4)),
        max_radius=0.25)
    set_seed(42)
    config = ablation_config(name)
    return config, MFSTNet(config, lane_masks_from_centres(centres, 7)).eval()


def logits_for(name, cnn, vit):
    config, model = build(name)
    with torch.no_grad():
        out = model(cnn if config.fusion.use_cnn else None,
                    vit if config.fusion.use_vit else None)
    return out.logits


@pytest.fixture(scope="module")
def inputs():
    torch.manual_seed(0)
    return (torch.randn(2, T, 2048, 7, 7), torch.randn(2, T, 384, 16, 16))


def test_no_two_configs_compute_the_same_function(inputs):
    """The guard. A pair that matched here would be a dead flag, and the
    ablation would be reporting one fewer experiment than it appears to."""
    cnn, vit = inputs
    names = [c.name for c in iter_ablation_configs()]
    computed = {name: logits_for(name, cnn, vit) for name in names}
    same = [(a, b) for a, b in itertools.combinations(names, 2)
            if torch.equal(computed[a], computed[b])]
    assert not same, f"configs computing an identical function: {same}"


def test_b_and_e_differ_in_their_logits(inputs):
    """The specific pair that raised the question, kept as a named case."""
    cnn, vit = inputs
    difference = float((logits_for("B", cnn, vit)
                        - logits_for("E", cnn, vit)).abs().max())
    assert difference > 1e-4, (
        "B (ViT only) and E (bidirectional, no gate) compute the same thing; "
        "E's fusion flag is not reaching the forward pass"
    )


def test_b_and_e_have_different_parameter_counts():
    counts = {name: sum(p.numel() for p in build(name)[1].parameters())
              for name in ("B", "E")}
    assert counts["B"] != counts["E"], counts


def test_matching_metrics_do_not_imply_matching_computation(inputs):
    """Why comparing metrics cannot substitute for this test.

    B and E agreed on every metric on fold 0 because metrics come from the
    argmax, and at initialisation both are near-uniform enough for the argmax to
    coincide while the logits do not.
    """
    cnn, vit = inputs
    b, e = logits_for("B", cnn, vit), logits_for("E", cnn, vit)
    assert torch.equal(b.argmax(-1), e.argmax(-1))
    assert not torch.equal(b, e)
