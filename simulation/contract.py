"""The observation contract, hashed, so a policy cannot silently read the wrong world.

`mfstnet/configs/spec.yaml` defines the PPO state layout once and the
environment raises if its own `STATE_DIM` disagrees. That catches a *length*
change. It does not catch the change that costs more: a **permutation or a
re-meaning**, where index 11 stops being `mfst_pred_N` and becomes something
else of the same size.

Nothing errors when that happens. The policy loads, the shapes match, and it
acts confidently on a feature that no longer means what it meant while it
learned to read it. Every checkpoint trained before the change and every
result derived from one become uncomparable, and no artifact says so.

So the contract gets a hash, the hash goes into each checkpoint's provenance
sidecar beside the timesteps P47 records, and loading a policy whose hash does
not match the current spec **refuses**.

**What is hashed, and why that exact set.** The index map, the dimension, the
normalisers, and the fallback index list -- everything that changes what a
number at a given position *means*:

* the **index map**, because a permutation is the silent case;
* the **normalisers**, because `count / 50` and `count / 200` are different
  features at the same index, and the divisors are tuning knobs (PRD §13.1
  marks them "revisit at W10");
* the **fallback list**, because which indices go to zero when the forecast is
  missing is part of what zero means;
* the **dimension**, which is redundant with the index map and included anyway
  -- it is the field a reader checks first.

The action space is deliberately **not** hashed here. ADR-015 is screening two
action spaces against each other, so two policies with different action spaces
are an intended comparison rather than an accident, and putting it in the digest
would make every arm-A checkpoint refuse to load in an arm-B run that legitimately
wanted to compare them.

**It is still checked.** Recording it without enforcing it would leave the exact
hole this module exists to close one level up: load an arm-A policy into an
arm-B environment and the digest passes, the observation length is right, and
the semantics are wrong. So `assert_compatible` checks both in one call --
observation contract *and* action space -- because two separate checks are one
that an evaluation path can forget.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

__all__ = ["contract_digest", "contract_fields", "assert_contract_matches",
           "assert_compatible", "load_sidecar"]

SPEC = Path("mfstnet/configs/spec.yaml")


def contract_fields(spec: dict) -> dict:
    """The parts of the spec that decide what a state number means."""
    state = spec["ppo_state"]
    return {
        "dim": state["dim"],
        "index_map": dict(sorted(state["index_map"].items())),
        "normalisers": dict(sorted(state["normalisers"].items())),
        "forecast_unavailable": dict(sorted(state["forecast_unavailable"].items())),
    }


def contract_digest(spec: dict | None = None) -> str:
    """A stable 16-hex digest of the observation contract.

    Sorted keys and a fixed separator, so the digest depends on the contract and
    not on how PyYAML happened to order a mapping (NFR-07).
    """
    if spec is None:
        import yaml

        spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    payload = json.dumps(contract_fields(spec), sort_keys=True,
                         separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def assert_contract_matches(recorded: str | None, *, what: str) -> None:
    """Raise unless `recorded` is the current contract digest.

    A `None` digest is refused rather than waved through. Every checkpoint
    written before this existed is in that state, and "no recorded contract" is
    exactly the condition that lets a policy be evaluated against a state it was
    not trained on -- the same argument P47 makes for an absent timesteps count.
    """
    current = contract_digest()
    if recorded == current:
        return
    if recorded is None:
        raise SystemExit(
            f"{what} records no observation contract, so it cannot be shown to "
            f"have been trained against the current one ({current}). Retrain "
            f"it, or move it aside."
        )
    raise SystemExit(
        f"{what} was trained against observation contract {recorded} and the "
        f"current contract is {current}. The shapes may still match: that is "
        f"the problem. A permuted or re-normalised index makes the policy act "
        f"on a feature that no longer means what it did while it learned to "
        f"read it, and nothing about that raises on its own. Retrain, or check "
        f"out the spec that digest belongs to."
    )


def load_sidecar(checkpoint: Path | str) -> dict:
    """Read a checkpoint's provenance sidecar, or `{}` if it has none."""
    path = Path(str(checkpoint) + ".provenance.json")
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def assert_compatible(checkpoint: Path | str, *, action_space: str) -> dict:
    """Refuse to use a policy that was not trained against this world.

    One entry point on purpose. The observation contract and the action space
    fail in the same way -- shapes match, meanings do not -- and an evaluation
    path that remembered to check one and forgot the other would be exactly as
    wrong as one that checked neither.

    Returns the sidecar so a caller can record what it evaluated.
    """
    checkpoint = Path(checkpoint)
    recorded = load_sidecar(checkpoint)
    what = checkpoint.name

    assert_contract_matches(recorded.get("observation_contract"), what=what)

    trained_on = recorded.get("action_space")
    if trained_on != action_space:
        raise SystemExit(
            f"{what} was trained on the {trained_on!r} action space and this "
            f"run uses {action_space!r}. ADR-015 screens the two against each "
            f"other, so this is not hashed into the observation contract -- "
            f"which means the digest passed and the observation length is "
            f"right. The policy would act, and its actions would mean "
            f"something else."
        )
    return recorded
