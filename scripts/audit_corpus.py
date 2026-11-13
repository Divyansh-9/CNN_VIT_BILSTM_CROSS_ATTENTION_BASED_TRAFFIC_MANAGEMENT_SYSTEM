"""Re-derive a corpus from its own inputs and check it against itself (P40).

    python scripts/audit_corpus.py --corpus data/corpus

`build_corpus.py` writes `counts.csv`, `sequences.csv` and `manifest.json`, and
every downstream number rests on them being consistent. Nothing checked that
they were. The unit tests cover each component in isolation; this checks the
artifact they combined to produce, which is a different question and the one
that matters once a corpus is on disk.

**The checks that would catch a silent disaster**, in the order they would hurt:

1. **The label is where A15 says it is.** `label_index` must equal
   `start_index + (T-1) + horizon_s/step_s`, and must sit strictly after the
   last observed frame. An off-by-one here makes every label in the corpus
   wrong — the model would train on a target 2 s away while the paper claims
   60 s — and absolutely nothing else would look unusual.
2. **The labels follow from the counts.** Recomputed from `counts.csv` through
   the manifest's own thresholds, every label must match. This is what proves
   `sequences.csv` was derived rather than drifted.
3. **No camera in two splits.** Consecutive windows share most of their frames,
   so a clip on both sides of a split reports a validation score that means
   nothing.
4. **Every window fits its clip.** A window running past the end would be
   padded or truncated somewhere downstream; HLD §8 says drop it instead.
5. **Geometry for every clip.** P26: a window pooled through another camera's
   lanes measures the wrong region.

Exit code is 1 if any check fails, so this can gate a pipeline run.

**This trusts nothing the builder recorded about itself.** Where a value can be
recomputed from a more primitive file, it is.
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

from mfstnet.corpus.labels import (  # noqa: E402
    CongestionClass, label_from_count, smooth_counts,
)
from mfstnet.corpus.validation import (  # noqa: E402
    SequenceRecord, check_effective_sample_size, check_split_balance,
    check_transition_rate,
)

PASS, FAIL, WARN = "  ok  ", " FAIL ", " warn "


class Audit:
    def __init__(self) -> None:
        self.failures = 0
        self.warnings = 0

    def check(self, ok: bool, name: str, detail: str = "") -> bool:
        if ok:
            print(f"[{PASS}] {name}")
        else:
            self.failures += 1
            print(f"[{FAIL}] {name}")
            if detail:
                for line in detail.splitlines():
                    print(f"         {line}")
        return ok

    def warn(self, ok: bool, name: str, detail: str = "") -> None:
        if ok:
            print(f"[{PASS}] {name}")
        else:
            self.warnings += 1
            print(f"[{WARN}] {name}")
            if detail:
                for line in detail.splitlines():
                    print(f"         {line}")


def check_composition(audit, cameras: Path, rows: list[dict]) -> None:
    """Does the test split contain the domain the paper claims (P58)?

    A FAIL rather than a warning when it does not. A model tested only on
    cameras outside its claimed domain has not been evaluated on its claim, and
    nothing computed downstream repairs that.
    """
    from collections import Counter

    from mfstnet.corpus.composition import CameraRegistry, compose

    if not cameras.is_file():
        # Absent registry is a different situation from a camera missing FROM
        # one: the project has not adopted the check rather than failed it. It
        # warns loudly instead of passing quietly, because a silent skip is a
        # hole and a pass would be a lie.
        audit.warn(False, f"composition unchecked — no registry at {cameras}",
                   "P58: density and unassigned-rate gates select for "
                   "usability, not for representativeness. Nothing else "
                   "compares the test split against the claimed domain.")
        return
    registry = CameraRegistry.load(cameras)
    windows = Counter()
    for row in rows:
        if row.get("split") == "test":
            windows[row["clip_id"]] += 1
    if not windows:
        return

    undeclared = registry.missing(windows)
    if undeclared:
        detail = [f"{c[:60]} is not in data/cameras.json" for c in undeclared]
        detail.append("A camera nobody has characterised cannot be checked "
                      "against the claim.")
        audit.check(False, "every test camera declares what it is",
                    chr(10).join(detail))
        return


    composition = compose(registry, windows)
    country, share = composition.dominant_country()
    parts = ", ".join(f"{k} {v}" for k, v in
                      sorted(composition.by_country.items(), key=lambda kv: -kv[1]))
    audit.check(
        composition.matches_claim,
        f"the test split contains the claimed domain ({parts})",
        f"target is {registry.target.get('country')} / "
        f"{registry.target.get('traffic_type')}; the test split has "
        f"{len(composition.off_target)} off-target and "
        f"{len(composition.unknown)} undetermined camera(s), and none on "
        f"target. A paper cannot claim a domain its test set does not contain.")

    if share > 0.5 and country not in (registry.target.get("country") or []):
        audit.warn(False, f"dominant test country: {country} at {share:.0%} of "
                          f"windows",
                   "One off-target camera supplying most of the evaluation "
                   "makes it the result, whatever the other cameras show.")
    if composition.unknown:
        audit.warn(False,
                   f"{len(composition.unknown)} test camera(s) undetermined",
                   "Declared 'unknown' rather than guessed — but they count "
                   "toward neither side, so the claim rests on fewer cameras "
                   "than the fold count suggests.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--cameras", type=Path, default=Path("data/cameras.json"),
                        help="declared per-camera country, viewpoint and "
                             "traffic type (P58). The test split is checked "
                             "against the claimed domain")
    parser.add_argument("--smooth-window", type=int, default=3,
                        help="must match what built the corpus (build_corpus "
                             "uses the default)")
    args = parser.parse_args(argv)

    manifest = json.loads((args.corpus / "manifest.json").read_text(encoding="utf-8"))
    with (args.corpus / "counts.csv").open(encoding="utf-8", newline="") as handle:
        counts = list(csv.DictReader(handle))
    with (args.corpus / "sequences.csv").open(encoding="utf-8", newline="") as handle:
        sequences = list(csv.DictReader(handle))

    lanes = manifest["lanes"]
    T, step_s = manifest["T"], manifest["step_s"]
    horizon_s, stride_s = manifest["horizon_s"], manifest["stride_s"]
    audit = Audit()

    print(f"  {args.corpus}")
    print(f"  {len(sequences)} sequences · {len(counts)} count rows · "
          f"{len(lanes)} lanes · T={T} step={step_s}s horizon={horizon_s}s\n")

    # -- 1. the label sits where A15 says --------------------------------
    horizon_frames = horizon_s // step_s
    expected_offset = (T - 1) + horizon_frames
    wrong = [r for r in sequences
             if int(r["label_index"]) != int(r["start_index"]) + expected_offset]
    audit.check(
        not wrong,
        f"label_index == start_index + {T - 1} + {horizon_frames}",
        "" if not wrong else
        f"{len(wrong)} of {len(sequences)} disagree, e.g. start "
        f"{wrong[0]['start_index']} -> label {wrong[0]['label_index']}, "
        f"expected {int(wrong[0]['start_index']) + expected_offset}",
    )

    not_ahead = [r for r in sequences
                 if int(r["label_index"]) <= int(r["start_index"]) + T - 1]
    audit.check(
        not not_ahead,
        "the label frame is strictly after the last observed frame (A15)",
        "" if not not_ahead else
        f"{len(not_ahead)} window(s) label a frame the model has already seen",
    )

    gap_s = expected_offset * step_s - (T - 1) * step_s
    audit.check(
        gap_s == horizon_s,
        f"the observed-to-label gap is {horizon_s}s in wall clock",
        "" if gap_s == horizon_s else
        f"the arithmetic yields {gap_s}s, not the {horizon_s}s claimed",
    )

    # -- 2. the labels follow from the counts ------------------------------
    series: dict[str, dict[str, list[int]]] = {}
    for row in counts:
        clip = series.setdefault(row["clip_id"], {})
        for lane in lanes:
            clip.setdefault(lane, []).append(int(row["count_" + lane]))
    smoothed = {clip: {lane: smooth_counts(values, args.smooth_window)
                       for lane, values in per_lane.items()}
                for clip, per_lane in series.items()}

    by_clip_thresholds = manifest.get("thresholds_by_clip") or {}
    mismatched = []
    for row in sequences:
        clip = row["clip_id"]
        bound = by_clip_thresholds.get(clip)
        low = bound["low_max"] if bound else manifest["low_max"]
        med = bound["med_max"] if bound else manifest["med_max"]
        index = int(row["label_index"])
        for lane in lanes:
            values = smoothed.get(clip, {}).get(lane, [])
            count = int(round(values[index])) if index < len(values) else 0
            expected = label_from_count(count, low_max=low, med_max=med).name
            if row.get("label_" + lane) != expected:
                mismatched.append((clip, lane, index, count,
                                   row.get("label_" + lane), expected))
    audit.check(
        not mismatched,
        "every label re-derives from counts.csv through the recorded thresholds",
        "" if not mismatched else
        f"{len(mismatched)} of {len(sequences) * len(lanes)} disagree, e.g. "
        f"{mismatched[0][0][:34]} {mismatched[0][1]} at {mismatched[0][2]}: "
        f"count {mismatched[0][3]} labelled {mismatched[0][4]}, "
        f"expected {mismatched[0][5]}",
    )

    # -- 3. no clip on both sides of a split -------------------------------
    splits = collections.defaultdict(set)
    for row in sequences:
        splits[row["clip_id"]].add(row["split"])
    straddling = {clip: sorted(names) for clip, names in splits.items()
                  if len(names) > 1}
    audit.check(
        not straddling,
        "no clip appears in more than one split (ADR-002)",
        "" if not straddling else
        "\n".join(f"{clip[:44]} in {names}" for clip, names in straddling.items()),
    )

    # -- 4. every window fits inside its clip ------------------------------
    available = {clip: len(next(iter(per_lane.values())))
                 for clip, per_lane in series.items()}
    overrun = [r for r in sequences
               if int(r["label_index"]) >= available.get(r["clip_id"], 0)]
    audit.check(
        not overrun,
        "every window's label frame exists in counts.csv",
        "" if not overrun else
        f"{len(overrun)} window(s) label a frame past the end, e.g. "
        f"{overrun[0]['clip_id'][:34]} wants {overrun[0]['label_index']} of "
        f"{available.get(overrun[0]['clip_id'], 0)}",
    )

    # -- 5. geometry for every clip ----------------------------------------
    geometry = manifest.get("lane_centres_by_clip") or {}
    if geometry:
        missing = sorted(set(splits) - set(geometry))
        audit.check(
            not missing,
            "every clip has its own lane geometry (P26)",
            "" if not missing else
            f"{len(missing)} without geometry, e.g. {missing[0][:44]}",
        )
        widths = {len(entry["lanes"]) for entry in geometry.values()}
        audit.check(
            len(widths) <= 1,
            "every camera declares the same lane count",
            "" if len(widths) <= 1 else f"lane counts present: {sorted(widths)}",
        )
    else:
        audit.warn(False, "per-camera lane geometry recorded",
                   "manifest has no lane_centres_by_clip; a corpus built "
                   "before P26 pools every camera through one geometry")

    # -- 6. counts are a contiguous series ---------------------------------
    gaps = []
    for clip in sorted(series):
        indices = sorted(int(r["sample"]) for r in counts if r["clip_id"] == clip)
        if indices != list(range(len(indices))):
            gaps.append(clip)
    audit.check(
        not gaps,
        "counts.csv indices are contiguous from 0 for every clip",
        "" if not gaps else
        f"{len(gaps)} clip(s) have gaps, e.g. {gaps[0][:44]} — window "
        f"arithmetic assumes position equals index",
    )

    # -- 7. reporting, not correctness -------------------------------------
    for split in ("train", "val", "test"):
        rows = [r for r in sequences if r["split"] == split]
        if not rows:
            audit.warn(False, f"the {split} split is non-empty",
                       "an empty split cannot be trained or evaluated on")
            continue
        tally = collections.Counter(r["label_" + lane] for r in rows for lane in lanes)
        total = sum(tally.values())
        absent = [c for c in ("LOW", "MEDIUM", "HIGH") if tally[c] == 0]
        shares = "  ".join(f"{c} {tally[c] / total:5.1%}"
                           for c in ("LOW", "MEDIUM", "HIGH"))
        audit.warn(
            not absent,
            f"{split} carries all three classes    {shares}",
            "" if not absent else
            f"{', '.join(absent)} absent — macro F1 over a class with no "
            f"support is 0 by convention and drags the mean (P31)",
        )

    # -- 8. the corpus-level gates (P46) -----------------------------------
    # `validate_corpus` holds the gates that decide whether a corpus can carry
    # a *result* — split balance, effective sample size, transition rate — as
    # opposed to whether it is internally consistent, which is everything
    # above. Until P46 its only caller was `demo_pipeline.py`, running on
    # synthetic data. A real corpus built by `build_corpus.py` and checked here
    # never met them, so the corpus that actually trains the model got the
    # weaker of the two checks.
    records = []
    for row in sequences:
        clip = row["clip_id"]
        bound = by_clip_thresholds.get(clip)
        low = bound["low_max"] if bound else manifest["low_max"]
        med = bound["med_max"] if bound else manifest["med_max"]
        end = int(row["start_index"]) + T - 1
        records.append(SequenceRecord(
            seq_id=f"{clip}_{row['start_index']}",
            clip_id=clip,
            split=row["split"],
            labels=tuple(int(CongestionClass[row["label_" + lane]])
                         for lane in lanes),
            labels_now=tuple(int(label_from_count(smoothed[clip][lane][end],
                                                  low_max=low, med_max=med))
                             for lane in lanes),
            label_origin=row.get("label_origin", "auto"),
        ))

    print()
    # A leave-one-camera-out view is deliberately unbalanced: the test split is
    # one whole camera, so its share is whatever share that camera holds. The
    # 60/20/20 gate would fire on every fold and its advice -- "collect more
    # clips rather than reaching for a different splitter" -- is aimed at the
    # hash splitter, not at this. Reporting a warning that cannot be acted on
    # is how real warnings stop being read.
    protocol = manifest.get("split_protocol")
    gates = [check_effective_sample_size(records), check_transition_rate(records)]
    if protocol == "loco":
        print(f"[{PASS}] split_balance: not applicable — fold "
              f"{manifest.get('fold')} of {manifest.get('folds_total')}, "
              f"test is one whole camera by construction")
    else:
        gates.insert(0, check_split_balance(records))
    for gate in gates:
        audit.warn(gate.passed, f"{gate.name}: {gate.detail}")

    # P58. Density and unassigned-rate select for usability; neither asks what
    # the camera IS. This is the only check that compares the EVALUATION set
    # against what the paper claims to be about.
    check_composition(audit, args.cameras, rows)

    print()
    if audit.failures:
        print(f"  {audit.failures} CHECK(S) FAILED. This corpus should not be "
              f"trained on until they are understood.")
    else:
        print(f"  all correctness checks passed"
              + (f", {audit.warnings} warning(s)" if audit.warnings else ""))
    return 1 if audit.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
