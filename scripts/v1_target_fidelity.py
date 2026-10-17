"""V1-1 — can a human count a few frames per minute instead of all thirty? (detector data only)

    python scripts/v1_target_fidelity.py

V1 scores the deployed forecasters against a **human** next-minute target. The
true target is the mean count over the next minute: 30 samples, 2 s apart,
per lane. Counting all 30 frames by hand is too costly. A human can count *K*
frames spread evenly over the minute instead. This check measures, **on
detector series alone**, how far a *K*-frame mean is from the 30-sample mean.
It never touches a human label or any model-selection data.

**Data:** the P105 **test** hours of the three untouched cameras in
`data/corpus_p105` (Eastgate, Newport, SE38th). The calibration hours are
excluded, because they set the class thresholds.

**Fixed before it runs (P133 plan, V1-1).**

- **The target T(t):** the mean of samples t+1 … t+30, per lane.
- **The approximation A_K(t):** the mean of *K* samples spaced evenly over the
  same minute, the last one at t+30:
  - *K* = 6, every 5th sample (10 s);
  - *K* = 10, every 3rd sample (6 s);
  - *K* = 15, every 2nd sample (4 s).
- **Also reported, not chosen from:** the single count at t + 60 s.
- **Moments:** every sample t with a full next minute, every lane, every test
  hour.
- **Pass:**
  - MAE(A_K, T) ≤ **0.15** vehicles, V1's precision target;
  - **and** agreement of the per-camera class (P105's q33/q67, `level`) ≥
    **0.95**.
- **Choice:** the **smallest passing *K***. If none passes, V1's target cannot
  be made affordable at this fidelity. That is reported, and the owner
  decides cost against fidelity **before** any labelling. Nothing is chosen
  automatically.
"""

from __future__ import annotations

import csv
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

CORPUS = Path("data/corpus_p105")
THRESHOLDS = Path("experiments/results/bellevue_pilot/p105_thresholds.json")
OUT = Path("experiments/results/v1/v1_target_fidelity.json")
HORIZON = 30                                  # samples, 2 s apart
OPTIONS = {6: 5, 10: 3, 15: 2}                # K -> stride in samples
MAE_MAX, AGREE_MIN = 0.15, 0.95


def level(x: float, low: float, med: float) -> int:
    """P105's class rule, verbatim."""
    return 0 if x <= low else (1 if x <= med else 2)


def series_by_clip(camera_dir: Path) -> dict[str, dict[str, list[int]]]:
    manifest = json.loads((camera_dir / "manifest.json").read_text(encoding="utf-8"))
    roles = manifest["roles"]
    lanes = manifest["lanes"]
    out: dict[str, dict[str, list[int]]] = {}
    with (camera_dir / "counts.csv").open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if roles.get(row["clip_id"]) != "test":
                continue
            clip = out.setdefault(row["clip_id"], {lane: [] for lane in lanes})
            for lane in lanes:
                clip[lane].append(int(row[f"count_{lane}"]))
    return out


def main() -> int:
    thresholds = json.loads(THRESHOLDS.read_text(encoding="utf-8"))["cameras"]
    errors = {k: [] for k in OPTIONS} | {"single_t60": []}
    agree = {k: [] for k in errors}
    per_camera = {}
    for camera_dir in sorted(p for p in CORPUS.iterdir() if p.is_dir()):
        cam = camera_dir.name
        q = thresholds[cam]
        moments = 0
        for clip, lanes in series_by_clip(camera_dir).items():
            for values in lanes.values():
                for t in range(len(values) - HORIZON):
                    window = values[t + 1: t + 1 + HORIZON]
                    target = statistics.fmean(window)
                    target_cls = level(target, q["q33"], q["q67"])
                    for k, stride in OPTIONS.items():
                        picks = window[stride - 1::stride]
                        assert len(picks) == k, (k, len(picks))
                        approx = statistics.fmean(picks)
                        errors[k].append(abs(approx - target))
                        agree[k].append(level(approx, q["q33"], q["q67"]) == target_cls)
                    single = window[-1]
                    errors["single_t60"].append(abs(single - target))
                    agree["single_t60"].append(level(single, q["q33"], q["q67"]) == target_cls)
                    moments += 1
        per_camera[cam] = {"lane_moments": moments}
        print(f"  {cam}: {moments} lane-moments", flush=True)
    result = {}
    for k in errors:
        mae = statistics.fmean(errors[k])
        share = sum(agree[k]) / len(agree[k])
        result[str(k)] = {"mae_vehicles": mae, "class_agreement": share,
                          "passes": (mae <= MAE_MAX and share >= AGREE_MIN) if k in OPTIONS else None}
    passing = [k for k in OPTIONS if result[str(k)]["passes"]]
    chosen = min(passing) if passing else None
    body = {"what": "V1-1 target-fidelity check, detector series only (P133 plan)",
            "data": "data/corpus_p105, test hours of 3 cameras; calibration hours excluded",
            "criteria": {"mae_max_vehicles": MAE_MAX, "class_agreement_min": AGREE_MIN},
            "options": result, "chosen_K": chosen,
            "decision": (f"label {chosen} frames per lane per minute" if chosen else
                         "no option passes: the owner decides cost against fidelity before labelling"),
            "per_camera": per_camera}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes((json.dumps(body, indent=2) + "\n").encode("utf-8"))
    for k, v in result.items():
        print(f"  K={k:>10}: MAE {v['mae_vehicles']:.3f}, class agreement {v['class_agreement']:.3f}"
              f"{'' if v['passes'] is None else ('  PASS' if v['passes'] else '  fail')}")
    print(f"\n  {body['decision']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
