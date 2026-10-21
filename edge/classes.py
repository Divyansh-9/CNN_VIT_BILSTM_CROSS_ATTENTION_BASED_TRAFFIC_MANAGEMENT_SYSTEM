"""Detector class names to the contract's vehicle classes, on the edge (D1).

The deployed detector (ITD-xl) names its classes 'two wheeler', 'autorickshaw',
'LCV', 'bicycle' and 'pedestrain'. The contract's `VehicleCount` accepts only
PRD §12.2's eight, so before this the first two-wheeler raised a ContractError
inside `EdgeNode.tick` and ended the edge loop (Phase C).

The mapping is read from `indiatrafficnet/class_mapping.yaml` (`itd_mapping`),
the project's single authority for class names, and is the one already
decided there: `LCV` merges into `truck`, `bicycle` is dropped. `normalise` is
total. A name with no mapping is reported as unknown, never guessed at and
never raised on, so a new or misspelled class cannot take the node down; the
node then withholds that lane's count rather than understate it.

**Two counts, kept apart on purpose.** This mapping shapes only the
contract-facing `vehicle_count` breakdown. The forecasters
(`edge.persistence`, `edge.count_forecast`) take the detector's raw lane
totals, bicycles included, because that is what the corpus counted and what
their frozen specs were calibrated on. Never feed them the filtered count from
here: it would shift their input away from the calibration without any sign
in their output.
"""

from __future__ import annotations

from pathlib import Path

from contracts.mqtt import VEHICLE_CLASSES

__all__ = ["MAPPING_FILE", "load_itd_mapping", "normalise"]

MAPPING_FILE = Path(__file__).resolve().parent.parent / "indiatrafficnet" / "class_mapping.yaml"

#: The dataset files spell two classes with underscores; the wire spells them
#: with hyphens (contracts/mqtt.py, TRIAGE-001 D1).
_WIRE = {"auto_rickshaw": "auto-rickshaw", "e_rickshaw": "e-rickshaw"}


def load_itd_mapping(path: Path = MAPPING_FILE, *, spelling: str = "wire") -> dict[str, str | None]:
    """Detector name -> contract class, or None where the class is dropped."""
    import yaml

    mapping = yaml.safe_load(path.read_text(encoding="utf-8"))["itd_mapping"]
    if spelling == "dataset":
        return dict(mapping)
    out = {name: (_WIRE.get(ours, ours) if ours is not None else None)
           for name, ours in mapping.items()}
    stray = {v for v in out.values() if v is not None} - set(VEHICLE_CLASSES)
    if stray:
        raise ValueError(f"itd_mapping names classes the contract does not have: {sorted(stray)}")
    return out


def normalise(types: dict[str, int], mapping: dict[str, str | None] | None = None
              ) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    """`(kept by contract class, dropped by decision, unknown)`.

    - **Kept:** a contract class passes through; a detector name is mapped,
      and merged classes are summed.
    - **Dropped:** a name the mapping sends to null (`bicycle`). Leaving it out
      of the count is the recorded decision.
    - **Unknown:** a name with no decision at all. The caller must not publish
      a count without it: the vehicles were seen, and leaving them out would
      report fewer than were there, which is the "missing read as zero" error
      P97a forbids.
    """
    mapping = {} if mapping is None else mapping
    kept: dict[str, int] = {}
    dropped: dict[str, int] = {}
    unknown: dict[str, int] = {}
    for name, n in types.items():
        if name in VEHICLE_CLASSES:
            kept[name] = kept.get(name, 0) + n
        elif name in mapping and mapping[name] is None:
            dropped[name] = dropped.get(name, 0) + n
        elif name in mapping:
            kept[mapping[name]] = kept.get(mapping[name], 0) + n
        else:
            unknown[name] = unknown.get(name, 0) + n
    return kept, dropped, unknown
