"""Forecast quality from persistence (q = 0) to the oracle (q = 1) (P115 §3, D3).

ADR-021 sweeps forecast quality. Raw macro-F1 cannot be the axis on this
simulator: persistence already scores what the low grid points ask for, and a
rare class caps what the high ones can reach (P114). So quality is defined
**relative to persistence**, which the policy could compute for itself:

- one binary "informed" process `I_t`, shared by all four approaches, is a
  two-state chain over decision steps. At each step it is redrawn as
  Bernoulli(q) with probability 1 - rho, and kept otherwise, with
  rho = exp(-step_s / tau_s). Its stationary share is q;
- the forecast is the oracle class where `I_t` holds, and the persistence class
  (the current count's class) where it does not.

A wrong forecast is therefore a lagging one, "the future is like now". That
makes it adjacent-class, lane-correlated and persistent in time: ADR-021 §4's
three properties, with no further parameters.

**A nominal q is not trusted to be the delivered quality.** `skill` measures it
against targets from a separate simulation run.
"""

from __future__ import annotations

import math

import numpy as np

__all__ = ["informed_mask", "construct", "skill", "corruption_rng", "GRID"]

GRID = (0.0, 0.25, 0.5, 0.75, 1.0)


def corruption_rng(seed: int, q: float) -> np.random.Generator:
    """The recorded corruption RNG (P115 §3)."""
    return np.random.default_rng([int(seed), int(round(1000 * q)), 52])


def informed_mask(n_steps: int, q: float, rng: np.random.Generator, *,
                  step_s: float = 5.0, tau_s: float = 60.0) -> np.ndarray:
    if not 0.0 <= q <= 1.0:
        raise ValueError(f"quality q must lie in [0, 1], got {q}")
    keep = math.exp(-step_s / tau_s)
    mask = np.empty(n_steps, dtype=bool)
    state = bool(rng.random() < q)
    for t in range(n_steps):
        if t > 0 and rng.random() >= keep:
            state = bool(rng.random() < q)
        mask[t] = state
    return mask


def construct(oracle: np.ndarray, persistence: np.ndarray, q: float,
              rng: np.random.Generator, **chain) -> np.ndarray:
    """Forecast classes, shape (steps, approaches), from the two endpoints."""
    oracle, persistence = np.asarray(oracle), np.asarray(persistence)
    if oracle.shape != persistence.shape or oracle.ndim != 2:
        raise ValueError(f"oracle {oracle.shape} and persistence {persistence.shape} "
                         f"must both be (steps, approaches)")
    mask = informed_mask(oracle.shape[0], q, rng, **chain)
    return np.where(mask[:, None], oracle, persistence)


def skill(forecast: np.ndarray, persistence: np.ndarray, oracle: np.ndarray,
          targets: np.ndarray) -> float:
    """(acc(F) - acc(P)) / (acc(O) - acc(P)), every accuracy against `targets`."""
    def acc(x):
        return float((np.asarray(x) == np.asarray(targets)).mean())

    span = acc(oracle) - acc(persistence)
    if span <= 0:
        raise ValueError("the oracle is no better than persistence on these targets; "
                         "skill is undefined")
    return (acc(forecast) - acc(persistence)) / span
