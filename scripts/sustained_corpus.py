"""Build a corpus whose target is the mean count over a future window (P94).

    python scripts/sustained_corpus.py --corpus data/corpus_bellevue_cal --future 30 --out data/corpus_bellevue_sus60

`rehorizon_corpus.py` moves a single instant further out. This replaces the
instant with a **sustained** quantity: the mean raw vehicle count over the K
samples after the window, classed with the source corpus's frozen thresholds.
P93 showed why. A 2 s count at a signalised junction is dominated by where in
a roughly 2-minute signal cycle it falls, and that phase noise is what kept
every model level with persistence.

**Fixed by `PREREGISTRATION_P94.md`:**

- inputs are `s … s+59`, and `e = s + 59`;
- the target is `mean(c[e+1 … e+K])` over **raw** counts, unsmoothed and
  unrounded;
- `label_index = e + K`, the last future sample, so the split's buffer covers
  the whole future window;
- the thresholds are frozen from the source manifest;
- the split is `assign_splits_temporal` with a buffer of `T + (T − 1 + K)`.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

from mfstnet.corpus.splits import assign_splits_temporal  # noqa: E402


def level(value: float, low_max: float, med_max: float) -> str:
    return "LOW" if value <= low_max else ("MEDIUM" if value <= med_max else "HIGH")


def build(source: Path, future: int) -> tuple[list[dict], dict]:
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("split_mode") != "temporal":
        raise SystemExit("only temporal-split corpora are supported")
    T, stride = manifest["T"], manifest["stride_s"] // manifest["step_s"]
    lanes = list(manifest["lanes"])
    series: dict[str, dict[str, list[int]]] = {}
    with (source / "counts.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            per = series.setdefault(row["clip_id"], {})
            for lane in lanes:
                per.setdefault(lane, []).append(int(row["count_" + lane]))
    by_clip = manifest.get("thresholds_by_clip") or {}

    rows = []
    offset = (T - 1) + future                 # start -> last future sample
    for clip_id, per in sorted(series.items()):
        n = len(next(iter(per.values())))
        starts = list(range(0, n - offset, stride))
        splits = assign_splits_temporal(starts, window_frames=T + offset)
        bounds = by_clip.get(clip_id, {"low_max": manifest["low_max"],
                                       "med_max": manifest["med_max"]})
        for start, split in zip(starts, splits):
            if split is None:
                continue
            e = start + T - 1
            entry = {"clip_id": clip_id, "split": split, "start_index": start,
                     "label_index": e + future}
            for lane in lanes:
                window = per[lane][e + 1:e + future + 1]
                entry["label_" + lane] = level(sum(window) / len(window),
                                               bounds["low_max"], bounds["med_max"])
            rows.append(entry)

    manifest = dict(manifest)
    manifest["target"] = f"mean raw vehicle count over the next {future} samples"
    manifest["future_samples"] = future
    manifest["target_note"] = ("P94: sustained-level target. Thresholds frozen "
                               "from the source; counts are raw vehicles, not PCU "
                               "(P93a). label_index is the last future sample.")
    manifest["rebuilt_from"] = str(source)
    return rows, manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--future", type=int, required=True,
                        help="K, samples in the future window (30 = 60 s)")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    rows, manifest = build(args.corpus, args.future)
    args.out.mkdir(parents=True, exist_ok=True)
    for name in ("counts.csv", "detections.csv"):
        if (args.corpus / name).exists():
            shutil.copyfile(args.corpus / name, args.out / name)
    with (args.out / "sequences.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"  K={args.future}: {len(rows)} windows {dict(Counter(r['split'] for r in rows))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
