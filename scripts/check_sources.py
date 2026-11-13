"""Check every data source against the collection gate, per role.

    python scripts/check_sources.py

Reads `data/sources.json`, `data/cameras.json`, the corpus manifest and
`docs/00-planning/CLAIMS.yaml`; writes nothing; exits 1 when a source is marked
`accepted` for a role it does not pass, a `rejected` source gives no reason, or
synthetic data is given a role that reaches an evaluation split.

**Why roles are gated separately.** One source can be exactly right for one job
and useless for another. BMD-45 is CC BY 4.0, Indian, fixed and elevated, which
makes it the best detector data the project has; it is also stills, about 12.5
frames per camera, so it cannot supply a single forecasting window. A single
pass/fail per source would either admit it to the forecaster or bar it from the
detector, and both are wrong.

**Where the thresholds come from.** Nothing here is chosen. The window span and
stride are read from the corpus manifest; ten windows per camera is ADR-019's
fold-eligibility rule; ten instances per class is `minimum_support` on the
`class_coverage` claim; four cameras is `minimum_cameras` on `camera_count`.
Changing any of them is a change to those records, not to this file.

**Partitions are derived, not asserted, for cameras already in the corpus.** A
camera is `real_india` only when every declared field in `target_domain` —
country, traffic type, viewpoint — matches; an undeclared field makes it
`unknown`; everything else that is real is `real_external`. The definition is
`CameraRegistry.partition`, shared with `resplit_corpus.py --domain`, so the
data a model trains on and the scope a claim is checked over cannot drift
apart. That keeps the British motorway and the Dhaka footbridges as
what the project has decided they are — an external-domain test — rather than
letting them count toward the Indian claim.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

import yaml  # noqa: E402

from mfstnet.corpus.composition import CameraRegistry  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "data" / "sources.json"
CAMERAS = ROOT / "data" / "cameras.json"
MANIFEST = ROOT / "data" / "corpus" / "manifest.json"
CLAIMS = ROOT / "docs" / "00-planning" / "CLAIMS.yaml"

#: ADR-019: a camera is fold-eligible at this many windows.
MIN_WINDOWS = 10

PARTITIONS = ("real_india", "real_external", "synthetic_sumo")

#: Roles whose data can reach an evaluation split. Synthetic data may never
#: hold one of these (ADR-024 decision 4).
EVALUATED_ROLES = ("forecaster", "detector")


def claim(claims: list[dict], claim_id: str) -> dict:
    return next(c for c in claims if c["id"] == claim_id)


def thresholds() -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    claims = yaml.safe_load(CLAIMS.read_text(encoding="utf-8"))["claims"]
    span = manifest["T"] * manifest["step_s"]
    return {
        "span_s": span,
        "stride_s": manifest["stride_s"],
        # The shortest continuous recording that yields MIN_WINDOWS windows.
        "min_continuous_s": span + (MIN_WINDOWS - 1) * manifest["stride_s"],
        "min_support": claim(claims, "class_coverage")["minimum_support"],
        "min_cameras": claim(claims, "camera_count")["minimum_cameras"],
    }


def forecaster_gate(entry: dict, t: dict) -> list[str]:
    """What this source still lacks to serve the forecaster. Empty means pass."""
    if entry.get("partition") == "synthetic_sumo":
        return ["synthetic data cannot enter a forecasting evaluation split"]
    missing = []
    if not entry.get("licence_resolved"):
        missing.append(f"licence unresolved ({entry.get('licence', '?')})")
    if entry.get("viewpoint") != "elevated":
        missing.append(f"viewpoint is {entry.get('viewpoint', 'unknown')}, "
                       "not elevated")
    if not entry.get("fixed_camera"):
        missing.append("not a fixed camera")
    if entry.get("determined_by") != "frame":
        missing.append(f"properties determined by "
                       f"{entry.get('determined_by', 'nothing')}, not by "
                       "looking at a frame")
    continuous = entry.get("continuous_s")
    if continuous is None:
        missing.append("continuous duration unknown")
    elif continuous < t["min_continuous_s"]:
        missing.append(f"{continuous} s continuous, needs "
                       f"{t['min_continuous_s']} s for {MIN_WINDOWS} windows")
    high = entry.get("high_support")
    if high is None:
        missing.append("HIGH support unknown until labelled")
    elif high < t["min_support"]:
        missing.append(f"{high} HIGH lane-windows, needs {t['min_support']} "
                       "to score the class")
    return missing


def detector_gate(entry: dict, t: dict) -> list[str]:
    if entry.get("partition") == "synthetic_sumo":
        return ["synthetic data cannot enter a detector evaluation split"]
    missing = []
    if not entry.get("licence_resolved"):
        missing.append(f"licence unresolved ({entry.get('licence', '?')})")
    if entry.get("determined_by") != "frame":
        missing.append("properties not confirmed from a frame")
    return missing


def count_pretraining_gate(entry: dict, t: dict) -> list[str]:
    return [] if entry.get("licence_resolved") else ["licence unresolved"]


GATES = {"forecaster": forecaster_gate, "detector": detector_gate,
         "count_pretraining": count_pretraining_gate}


def camera_partition(registry, camera: str) -> str:
    """One definition, shared with the fold builder: `CameraRegistry.partition`."""
    return registry.partition(camera)


def violations(sources: dict, t: dict) -> list[str]:
    """Every rule breach in the register. Separate from printing so it can be
    tested without capturing output."""
    found = []
    for key, entry in sources.items():
        partition = entry.get("partition")
        if partition not in PARTITIONS + ("per-camera",):
            found.append(f"{key}: unknown partition {partition!r}")
        roles = entry.get("roles", {})
        if partition == "synthetic_sumo":
            bad = [role for role in roles if role in EVALUATED_ROLES]
            if bad:
                found.append(f"{key}: synthetic data given evaluated "
                             f"role(s) {bad}")
        for role, status in roles.items():
            if role not in GATES:
                found.append(f"{key}: unknown role {role!r}")
                continue
            if status == "rejected" and not entry.get("reason"):
                found.append(f"{key}: rejected for {role} with no reason")
            if partition == "per-camera":
                continue
            missing = GATES[role](entry, t)
            if status == "accepted" and missing:
                found.append(f"{key}: accepted for {role} but "
                             f"{'; '.join(missing)}")
    return found


def main() -> int:
    t = thresholds()
    sources = json.loads(SOURCES.read_text(encoding="utf-8"))["sources"]
    payload = json.loads(CAMERAS.read_text(encoding="utf-8"))
    cameras = payload["cameras"]
    registry = CameraRegistry(payload)

    print(f"\n  thresholds, read from their records: window {t['span_s']} s, "
          f"stride {t['stride_s']} s, so {MIN_WINDOWS} windows need "
          f"{t['min_continuous_s']} s continuous;")
    print(f"  {t['min_support']} instances per class; "
          f"{t['min_cameras']} fold-eligible cameras\n")

    for key, entry in sources.items():
        partition = entry.get("partition")
        print(f"  {key}  [{partition}]")
        print(f"    {entry.get('name', '')}")
        for role, status in entry.get("roles", {}).items():
            if partition == "per-camera":
                print(f"    {role:<18} {status:<9} per camera, below")
                continue
            missing = GATES[role](entry, t)
            verdict = "passes" if not missing else "; ".join(missing)
            print(f"    {role:<18} {status:<9} {verdict}")
        print()

    print("  cameras already in the corpus, partition derived from "
          "cameras.json:\n")
    import csv
    from collections import Counter
    with (ROOT / "data" / "corpus" / "sequences.csv").open(
            encoding="utf-8", newline="") as handle:
        windows = Counter(row["clip_id"] for row in csv.DictReader(handle))

    india = []
    for name, camera in cameras.items():
        part = camera_partition(registry, name)
        if part == "real_india":
            india.append(name)
        owes = []
        if not str(camera.get("licence", "")).startswith("resolved"):
            owes.append("licence")
        if camera.get("determined_by") != "frame":
            owes.append(f"inspection (determined by "
                        f"{camera.get('determined_by')})")
        print(f"    {part:<14} {windows.get(name, 0):>3} win  {name[:40]:<41} owes: "
              f"{', '.join(owes) or 'nothing'}")

    eligible = [n for n in india if windows.get(n, 0) >= MIN_WINDOWS]
    print(f"\n  real_india cameras in the corpus: {len(india)}, of which "
          f"{len(eligible)} fold-eligible at {MIN_WINDOWS} windows. "
          f"`camera_count` needs {t['min_cameras']}.")
    print("  NOTE  `domain` is checked on EVERY fold's test camera. While "
          "real_external\n        cameras stay leave-one-camera-out folds it "
          "cannot pass however many\n        Indian cameras are added. Scoring "
          "real_external as a separate named\n        arm is a change to the "
          "claim's protocol: the project owner's decision.")

    found = violations(sources, t)
    if found:
        print(f"\n  {len(found)} GATE VIOLATION(S):")
        for item in found:
            print(f"    {item}")
        return 1
    print("\n  no source is accepted for a role it fails, and every rejection "
          "gives its reason\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
