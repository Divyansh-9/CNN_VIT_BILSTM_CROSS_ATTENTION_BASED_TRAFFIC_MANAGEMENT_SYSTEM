"""Re-derive a corpus at a different forecast horizon, from its stored counts.

    python scripts/rehorizon_corpus.py --corpus data/corpus_bellevue_cal --horizon-s 180 --out data/corpus_bellevue_h180

P92 found that at a 60 s horizon neither the Bellevue pilot nor S61 beats
persistence. The first diagnostic is whether a longer horizon leaves room for a
model, and that question needs no detector run. The counts are already measured
(`counts.csv` is threshold- and horizon-independent). Only the windows, their
split and their labels depend on the horizon.

**Everything except the horizon is held fixed:**

- **Window geometry:** T, step and stride come from the source manifest, and
  windows come from the same `sequences_from_clip`.
- **Labels:** `smooth_counts` at the label sample, then `label_from_count`, as
  `relabel_corpus.py` does.
- **Thresholds are frozen from the source corpus** (`thresholds_by_clip`, or
  `low_max`/`med_max`). They are never recalibrated, so a horizon change cannot
  quietly move the class boundaries.
- **The split** is the same buffered chronological 60/20/20,
  `assign_splits_temporal`. Its buffer is a full window plus the new horizon,
  so a longer horizon costs more data at each boundary and still lets no input
  or target cross one.

Correctness check, run by `tests/test_rehorizon_corpus.py`: at the source's own
horizon this must reproduce the source corpus's windows, splits and labels
exactly.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

from mfstnet.corpus.labels import label_from_count, smooth_counts  # noqa: E402
from mfstnet.corpus.splits import assign_splits_temporal  # noqa: E402
from mfstnet.corpus.windows import WindowGeometry, sequences_from_clip  # noqa: E402

SMOOTH_WINDOW = 3          # relabel_corpus.py's default; the source used it


def rehorizon(source: Path, horizon_s: int) -> tuple[list[dict], dict]:
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("split_mode") != "temporal":
        raise SystemExit("only temporal-split corpora are supported: a clip "
                         "split is horizon-independent and needs no re-derivation")
    lanes = list(manifest["lanes"])
    geometry = WindowGeometry(T=manifest["T"], step_s=manifest["step_s"],
                              horizon_s=horizon_s, stride_s=manifest["stride_s"])

    series: dict[str, dict[str, list[int]]] = {}
    with (source / "counts.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            clip = series.setdefault(row["clip_id"], {})
            for lane in lanes:
                clip.setdefault(lane, []).append(int(row["count_" + lane]))

    by_clip = manifest.get("thresholds_by_clip") or {}
    rows = []
    for clip_id, per_lane in sorted(series.items()):
        smoothed = {lane: smooth_counts(v, SMOOTH_WINDOW) for lane, v in per_lane.items()}
        n_frames = len(next(iter(per_lane.values())))
        sequences = sequences_from_clip(clip_id, n_frames, geometry)
        if not sequences:
            raise SystemExit(f"{clip_id}: {n_frames} samples yield no window at "
                             f"a {horizon_s} s horizon")
        splits = assign_splits_temporal(
            [s.start_index for s in sequences],
            window_frames=geometry.T + geometry.label_offset_frames)
        bounds = by_clip.get(clip_id, {"low_max": manifest["low_max"],
                                       "med_max": manifest["med_max"]})
        for sequence, split in zip(sequences, splits):
            if split is None:
                continue
            entry = {"clip_id": clip_id, "split": split,
                     "start_index": sequence.start_index,
                     "label_index": sequence.label_index}
            for lane in lanes:
                count = int(round(smoothed[lane][sequence.label_index]))
                entry["label_" + lane] = label_from_count(
                    count, low_max=bounds["low_max"],
                    med_max=bounds["med_max"]).name
            rows.append(entry)

    manifest = dict(manifest)
    manifest["horizon_s"] = horizon_s
    manifest["rehorizoned_from"] = str(source)
    manifest["rehorizon_note"] = (
        "Windows, split and labels re-derived from counts.csv at this horizon "
        "by scripts/rehorizon_corpus.py. Thresholds frozen from the source; "
        "geometry, smoothing and split rule unchanged.")
    return rows, manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--horizon-s", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    rows, manifest = rehorizon(args.corpus, args.horizon_s)
    args.out.mkdir(parents=True, exist_ok=True)
    for name in ("counts.csv", "detections.csv"):
        if (args.corpus / name).exists():
            shutil.copyfile(args.corpus / name, args.out / name)
    with (args.out / "sequences.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2),
                                            encoding="utf-8")
    import collections
    print(f"  horizon {args.horizon_s} s: {len(rows)} windows "
          f"{dict(collections.Counter(r['split'] for r in rows))}")
    print(f"  wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
