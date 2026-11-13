"""Accumulating micro-batches must equal one batch, or it is a hyperparameter.

`--micro-batch` exists to bound peak memory: one batch of 32 windows at
`[60, 2048, 7, 7]` is 0.77 GB fp16 on the host, twice that once `torch.stack`
has copied it, and 1.5 GB fp32 on a 6 GB card before the model, its gradients
and AdamW's two moment buffers.

That is only legitimate if the optimiser step is unchanged. `batch_size` is
PRD §8.2 and how many windows are resident at once is an implementation detail
-- but the moment accumulation shifts the gradient, it stops being an
implementation detail and silently becomes a different training run.

The subtlety these pin is the **weighting**. Each micro-batch's loss is a mean
over its own windows, so summing the means over-weights a short final group.
`train_mfstnet` sums `loss * windows` and divides the accumulated gradient by
the windows actually seen, which is why an uneven split has to be tested rather
than assumed.
"""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")


def a_tiny_problem(seed: int = 0):
    torch.manual_seed(seed)
    model = torch.nn.Sequential(torch.nn.Linear(6, 5), torch.nn.Tanh(),
                                torch.nn.Linear(5, 3))
    inputs = torch.randn(20, 6)
    targets = torch.randint(0, 3, (20,))
    return model, inputs, targets


def single_batch_gradient(model, inputs, targets):
    criterion = torch.nn.CrossEntropyLoss()
    model.zero_grad(set_to_none=True)
    criterion(model(inputs), targets).backward()
    return [p.grad.clone() for p in model.parameters()]


def accumulated_gradient(model, inputs, targets, chunks):
    """The scheme `train_mfstnet` runs: sum `loss * n`, divide by total `n`."""
    criterion = torch.nn.CrossEntropyLoss()
    model.zero_grad(set_to_none=True)
    seen = 0
    start = 0
    for size in chunks:
        piece = slice(start, start + size)
        loss = criterion(model(inputs[piece]), targets[piece])
        (loss * size).backward()
        seen += size
        start += size
    for parameter in model.parameters():
        if parameter.grad is not None:
            parameter.grad /= seen
    return [p.grad.clone() for p in model.parameters()]


@pytest.mark.parametrize("chunks", [
    [20],                 # degenerate: one group, must be exact
    [10, 10],             # even split
    [8, 8, 4],            # the real shape: 32 = 8 + 8 + 8 + 8, last group short
    [5, 5, 5, 5],
    [7, 7, 6],            # uneven, the case naive averaging gets wrong
])
def test_accumulated_gradient_equals_one_batch(chunks):
    assert sum(chunks) == 20
    model, inputs, targets = a_tiny_problem()
    one = single_batch_gradient(model, inputs, targets)
    many = accumulated_gradient(model, inputs, targets, chunks)
    for a, b in zip(one, many):
        assert torch.allclose(a, b, atol=1e-6), (
            f"accumulation over {chunks} moved the gradient; the optimiser step "
            f"is not the one PRD §8.2's batch size specifies"
        )


def test_averaging_the_means_is_wrong_on_an_uneven_split():
    """The mistake this weighting avoids, demonstrated rather than asserted.

    If it were harmless, the guard above would be ceremony.
    """
    model, inputs, targets = a_tiny_problem()
    one = single_batch_gradient(model, inputs, targets)

    criterion = torch.nn.CrossEntropyLoss()
    model.zero_grad(set_to_none=True)
    chunks, start = [7, 7, 6], 0
    for size in chunks:
        piece = slice(start, start + size)
        (criterion(model(inputs[piece]), targets[piece]) / len(chunks)).backward()
        start += size
    naive = [p.grad.clone() for p in model.parameters()]

    assert not all(torch.allclose(a, b, atol=1e-6)
                   for a, b in zip(one, naive))


def test_micro_batch_never_exceeds_the_real_batch():
    """A micro-batch larger than the batch would raise the effective batch size,
    which IS a hyperparameter."""
    import inspect

    from scripts.train_mfstnet import train_one

    source = inspect.getsource(train_one)
    assert 'min(micro_batch or t["batch_size"], t["batch_size"])' in source
