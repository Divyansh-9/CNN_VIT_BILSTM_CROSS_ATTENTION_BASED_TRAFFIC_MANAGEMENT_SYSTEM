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

from mfstnet.corpus.labels import label_from_count, smooth_counts  # noqa: E402

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--corpus", type=Path, required=True)
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
