"""V1 — draw the lane-moments humans will count (ids only; no footage, no labels).

    python scripts/v1_sample.py

**The source: P105's test hours** for its three untouched cameras (Eastgate,
Newport, SE38th).
- **Why these hours:** no model was fitted or selected on them. P105 scored
  them with detector labels, so V1 becomes a **paired label-source
  comparison**: the same forecasts on the same moments, scored once against
  detector labels and once against human ones.
- **No new footage is needed.**
- **Calibration hours are excluded:** they set the class thresholds.

**A lane-moment** is a (clip, lane, t) triple, with t a sample index 2 s apart.

| element | samples | used for |
|---|---|---|
| history | t − 59 … t | ridge's two minutes; persistence uses the last 30 |
| future | t + 1 … t + 30 | the next-minute target |
| **labelled frames** | **t + 2, t + 4, …, t + 30 (15 frames)** | the human target. V1-1 found *K* = 15 the smallest faithful option |

**Non-overlap.** Moments of one lane sit on a 90-sample grid
(t = 59, 149, 239, …), so their history-plus-future windows never overlap.

**Strata:** camera × the detector class of the next-minute mean, using P105's
per-camera q33 and q67. Each stratum is shuffled once, with a fixed seed.

**The draw:**
- **the pilot** takes 40 lane-moments, round-robin across the strata;
- **the rest** stays an ordered reserve;
- the main sample later takes the first *n* of each stratum, with *n* set at
  the V1 freeze from the pilot's measured rate and spread. **Nothing is
  re-drawn.**

The manifest holds ids, sample indices and strata. It holds **no counts,
labels or frames.**
"""

from __future__ import annotations

import csv
import json
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

from scripts.v1_target_fidelity import CORPUS, THRESHOLDS, level  # noqa: E402

OUT = Path("experiments/results/v1/v1_sample_manifest.json")
SEED = 20261017
HISTORY, HORIZON, GRID, PILOT = 60, 30, 90, 40
LABEL_OFFSETS = tuple(range(2, HORIZON + 1, 2))          # t+2 ... t+30: 15 frames
CLASSES = ("LOW", "MEDIUM", "HIGH")


def moment_id(clip: str, lane: str, t: int) -> str:
    return f"{clip}|{lane}|{t}"


def candidates() -> dict[str, list[dict]]:
    """Every eligible lane-moment, grouped by stratum (camera:class)."""
    thresholds = json.loads(THRESHOLDS.read_text(encoding="utf-8"))["cameras"]
    strata: dict[str, list[dict]] = {}
    for camera_dir in sorted(p for p in CORPUS.iterdir() if p.is_dir()):
        cam = camera_dir.name
        q = thresholds[cam]
        manifest = json.loads((camera_dir / "manifest.json").read_text(encoding="utf-8"))
        series: dict[str, dict[str, list[int]]] = {}
        with (camera_dir / "counts.csv").open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if manifest["roles"].get(row["clip_id"]) != "test":
                    continue
                clip = series.setdefault(row["clip_id"], {lane: [] for lane in manifest["lanes"]})
                for lane in manifest["lanes"]:
                    clip[lane].append(int(row[f"count_{lane}"]))
        for clip, lanes in sorted(series.items()):
            for lane, values in sorted(lanes.items()):
                for t in range(HISTORY - 1, len(values) - HORIZON, GRID):
                    future = statistics.fmean(values[t + 1: t + 1 + HORIZON])
                    cls = CLASSES[level(future, q["q33"], q["q67"])]
                    strata.setdefault(f"{cam}:{cls}", []).append(
                        {"id": moment_id(clip, lane, t), "camera": cam, "clip": clip,
                         "lane": lane, "t": t,
                         "labelled_samples": [t + k for k in LABEL_OFFSETS]})
    return strata


def draw(strata: dict[str, list[dict]]) -> dict:
    ordered = {}
    for name in sorted(strata):
        items = list(strata[name])
        random.Random(f"{SEED}:{name}").shuffle(items)
        ordered[name] = items
    pilot, cursor = [], {name: 0 for name in ordered}
    while len(pilot) < PILOT and any(cursor[n] < len(ordered[n]) for n in ordered):
        for name in sorted(ordered):
            if len(pilot) < PILOT and cursor[name] < len(ordered[name]):
                pilot.append(ordered[name][cursor[name]])
                cursor[name] += 1
    reserve = {name: ordered[name][cursor[name]:] for name in ordered}
    return {"pilot": pilot, "reserve": reserve}


def main() -> int:
    strata = candidates()
    drawn = draw(strata)
    body = {"what": "V1 sample manifest: ids and sample indices only (no counts, labels or frames)",
            "source": "data/corpus_p105, P105 test hours; calibration excluded",
            "seed": SEED, "grid_samples": GRID, "history_samples": HISTORY,
            "labelled_offsets": list(LABEL_OFFSETS), "pilot_size": len(drawn["pilot"]),
            "strata_sizes": {k: len(v) for k, v in strata.items()},
            "pilot": drawn["pilot"], "reserve": drawn["reserve"]}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes((json.dumps(body, indent=1) + "\n").encode("utf-8"))
    print(f"  {sum(map(len, strata.values()))} eligible lane-moments in {len(strata)} strata: "
          f"{body['strata_sizes']}")
    print(f"  pilot {len(drawn['pilot'])}; reserve {sum(map(len, drawn['reserve'].values()))} -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
