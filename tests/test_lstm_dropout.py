"""The BiLSTM must not use nn.LSTM's built-in dropout (P42).

`nn.LSTM(..., dropout>0)` on CUDA in training mode aborts the process at
teardown on this stack — torch 2.13.0+cu126, Python 3.14, Windows, sm_89 —
with STATUS_STACK_BUFFER_OVERRUN (0xC0000409). cuDNN allocates a dropout-state
descriptor that is not torn down cleanly.

The failure is nastier than a crash normally is, because **everything succeeds
first**. Training completes, the results CSV is written and correct, the summary
prints — and then the process dies. What is left is a non-zero exit code on a
run whose output is perfectly good, which is exactly the shape that gets
dismissed as noise. It was: the first time this appeared in the session it was
written off as a shell artifact.

`TemporalEncoder` therefore stacks single-layer LSTMs and applies dropout
between them explicitly. That is what PyTorch's built-in dropout does anyway —
output of every layer except the last — so the model is unchanged, and
`test_the_stacked_form_matches_the_builtin_exactly` holds it to that.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

torch = pytest.importorskip("torch")

from mfstnet.temporal import TemporalConfig, TemporalEncoder


def test_no_lstm_is_built_with_builtin_dropout():
    """The guard. Any nn.LSTM anywhere in the encoder must have dropout 0."""
    encoder = TemporalEncoder(TemporalConfig(use_bilstm=True))
    lstms = [m for m in encoder.modules() if isinstance(m, torch.nn.LSTM)]

    assert lstms, "the encoder should contain LSTMs when use_bilstm is on"
    for lstm in lstms:
        assert lstm.dropout == 0, (
            "nn.LSTM built-in dropout aborts the process at teardown on CUDA. "
            "Apply dropout between stacked single-layer LSTMs instead."
        )


def test_each_lstm_is_a_single_layer():
    """Built-in dropout only engages with num_layers > 1, so single layers are
    also what keeps the descriptor from being allocated."""
    encoder = TemporalEncoder(TemporalConfig(use_bilstm=True, layers=2))
    for lstm in (m for m in encoder.modules() if isinstance(m, torch.nn.LSTM)):
        assert lstm.num_layers == 1


def test_there_is_one_lstm_per_configured_layer():
    for layers in (1, 2, 3):
        encoder = TemporalEncoder(TemporalConfig(use_bilstm=True, layers=layers))
        found = [m for m in encoder.modules() if isinstance(m, torch.nn.LSTM)]
        assert len(found) == layers


def test_the_stacked_form_matches_the_builtin_exactly():
    """The change is a workaround for a platform defect and must not be a
    modelling change. Given the same weights and dropout inactive, the two
    forms have to agree bitwise."""
    torch.manual_seed(0)
    cfg = TemporalConfig(use_bilstm=True, use_temporal_attn=False, pooling="last")
    encoder = TemporalEncoder(cfg).eval()

    builtin = torch.nn.LSTM(cfg.d_model, cfg.hidden, cfg.layers, batch_first=True,
                            bidirectional=True, dropout=cfg.dropout).eval()
    for index, layer in enumerate(encoder.rnn_layers):
        for name, param in layer.named_parameters():
            getattr(builtin, name.replace("l0", f"l{index}")).data.copy_(param.data)

    x = torch.randn(3, 7, cfg.d_model)
    with torch.no_grad():
        _, (h_n, _) = builtin(x)
        reference = torch.cat([h_n[-2], h_n[-1]], dim=-1)
        ours = encoder(x)

    assert torch.equal(ours, reference)


def test_the_parameter_count_is_unchanged():
    cfg = TemporalConfig(use_bilstm=True)
    encoder = TemporalEncoder(cfg)
    builtin = torch.nn.LSTM(cfg.d_model, cfg.hidden, cfg.layers, batch_first=True,
                            bidirectional=True, dropout=cfg.dropout)

    ours = sum(p.numel() for p in encoder.rnn_layers.parameters())
    assert ours == sum(p.numel() for p in builtin.parameters())


def test_dropout_still_happens_in_training_mode():
    """A workaround that quietly removed the regularisation would be worse than
    the crash."""
    torch.manual_seed(0)
    encoder = TemporalEncoder(TemporalConfig(use_bilstm=True, layers=2,
                                             dropout=0.5)).train()
    x = torch.randn(4, 6, 256)
    assert not torch.equal(encoder(x), encoder(x))


def test_dropout_is_off_in_eval_mode():
    torch.manual_seed(0)
    encoder = TemporalEncoder(TemporalConfig(use_bilstm=True, layers=2,
                                             dropout=0.5)).eval()
    x = torch.randn(4, 6, 256)
    assert torch.equal(encoder(x), encoder(x))


def test_a_single_layer_configuration_applies_no_dropout():
    """PyTorch ignores built-in dropout for one layer and warns about it; the
    stacked form has to make the same choice rather than silently adding it."""
    encoder = TemporalEncoder(TemporalConfig(use_bilstm=True, layers=1,
                                             dropout=0.5)).train()
    x = torch.randn(4, 6, 256)
    assert torch.equal(encoder(x), encoder(x))
