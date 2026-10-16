"""P105 — calibrate, check support, then score the frozen change forecaster once.

    python scripts/p105_eval.py thresholds   # calibration hours only; stop rules
    python scripts/p105_eval.py score        # refuses unless the thresholds are committed

Implements `experiments/results/bellevue_pilot/PREREGISTRATION_P105.md`.

**Methods**, all predicting Δ, the next 60 s mean minus the last 60 s mean:

- persistence (Δ̂ = 0);
- trend (the last minute-over-minute change, continued);
- ridge (`p105_ridge_v1.json`, applied unchanged, its SHA-256 checked).

The forecast count is `max(0, last 60 s mean + Δ̂)`. Its class comes from the
test camera's own calibration-hour thresholds, at full precision.

**Primary family (Holm):** ridge − persistence on macro-F1, and persistence −
ridge on forecast-count MAE. Positive means ridge is better on both. The
bootstrap is stratified by camera over 10-minute blocks.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import statistics
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

from scripts.p105_freeze import T, K, STRIDE, change_features, future_mean, recent_mean, trend  # noqa: E402

ROOT = Path("experiments/results/bellevue_pilot")
CORPUS = Path("data/corpus_p105")
RIDGE = ROOT / "p105_ridge_v1.json"
RIDGE_SHA = "73532968dcf24b2533089687530ca435d2f09bc8cebcb159b44d97dd55c7c74c"
THRESHOLDS = ROOT / "p105_thresholds.json"
CAMERAS = ("116th_NE12th", "150th_Eastgate", "150th_Newport", "150th_SE38th")
CLASSES = ["LOW", "MEDIUM", "HIGH"]
BLOCK, RESAMPLES = 300, 10_000
STOP_POOLED, FLAG_CAMERA, MIN_BLOCKS, EMPTY_LANE = 30, 10, 6, 0.5
METHODS = ("persistence", "trend", "ridge")


def level(x: float, low: float, med: float) -> int:
    return 0 if x <= low else (1 if x <= med else 2)


def windows(camera: str, ridge: dict | None = None) -> list[dict]:
    root = CORPUS / camera
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    lanes, roles = manifest["lanes"], manifest["roles"]
    clips: dict[str, list[list[int]]] = {}
    with (root / "counts.csv").open(encoding="utf-8") as handle:
        for r in csv.DictReader(handle):
            clips.setdefault(r["clip_id"], []).append([int(r["count_" + l]) for l in lanes])
    rows = []
    for clip, c in sorted(clips.items()):
        series = [[row[j] for row in c] for j in range(len(lanes))]
        for s in range(0, len(c), STRIDE):
            e = s + T - 1
            if e + K >= len(c):
                continue
            w = {"camera": camera, "clip": clip, "role": roles[clip], "start": s,
                 "block": f"{clip}#{s // BLOCK}",
                 "recent": [recent_mean(v, e) for v in series],
                 "future": [future_mean(v, e) for v in series]}
            if ridge is not None:
                w["delta"] = {
                    "persistence": [0.0] * len(series),
                    "trend": [trend(v, s) for v in series],
                    "ridge": [sum(a * b for a, b in zip(ridge["coef"], change_features(v, s)))
                              for v in series]}
            rows.append(w)
    return rows


def calibrate(rows: list[dict]) -> tuple[float, float]:
    import numpy as np

    values = [m for w in rows if w["role"] == "calibration" for m in w["future"]]
    q33, q67 = np.percentile(values, [33, 67])
    return float(q33), float(q67)       # full precision (P103's rounding defect)


def thresholds() -> int:
    report = {"protocol": "PREREGISTRATION_P105.md", "rule": "q33/q67 of the calibration "
              "hour's 60 s means, pooled over lanes, full precision", "cameras": {}}
    pooled, blocks = [0, 0, 0], 0
    for camera in CAMERAS:
        rows = windows(camera)
        cal = [w for w in rows if w["role"] == "calibration"]
        test = [w for w in rows if w["role"] == "test"]
        if not cal or not test:
            report["cameras"][camera] = {"excluded": f"calibration {len(cal)} / test {len(test)} windows"}
            continue
        q33, q67 = calibrate(rows)
        got = [0, 0, 0]
        for w in test:
            for m in w["future"]:
                got[level(m, q33, q67)] += 1
        pooled = [a + b for a, b in zip(pooled, got)]
        n_blocks = len({w["block"] for w in test})
        blocks += n_blocks
        report["cameras"][camera] = {
            "q33": q33, "q67": q67, "calibration_windows": len(cal), "test_windows": len(test),
            "test_blocks": n_blocks, "lanes": len(test[0]["future"]),
            "test_support": dict(zip(CLASSES, got)),
            "flagged_classes_under_10": [c for c, k in zip(CLASSES, got) if k < FLAG_CAMERA]}
    report["pooled_support"] = dict(zip(CLASSES, pooled))
    report["pooled_test_blocks"] = blocks
    report["stop"] = min(pooled) < STOP_POOLED or blocks < MIN_BLOCKS
    THRESHOLDS.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["stop"]:
        raise SystemExit("support or volume below the protocol's floor — STOP for an amendment")
    print(f"\n  commit {THRESHOLDS} before `score`")
    return 0


def committed(path: Path) -> bool:
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", str(path)],
                             capture_output=True).returncode == 0
    clean = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", str(path)]).returncode == 0
    return tracked and clean


def metrics(rows: list[dict], method: str) -> dict:
    from mfstnet.metrics import evaluate

    t = [x for w in rows for x in w["true"]]
    p = [x for w in rows for x in w["cls"][method]]
    r = evaluate(t, p, CLASSES)
    err = [f - c for w in rows for f, c in zip(w["count"][method], w["future"])]
    return {"f1": r.macro_f1, "mae": statistics.fmean(abs(x) for x in err),
            "bias": statistics.fmean(err),
            **{c: r.per_class[i].recall for i, c in enumerate(CLASSES)}}


def ci(rows, a, b, key, seed, flip=False) -> dict:
    """a − b on `key` (b − a if flip), stratified block bootstrap by camera."""
    strata: dict[str, dict[str, list]] = {}
    for w in rows:
        strata.setdefault(w["camera"], {}).setdefault(w["block"], []).append(w)
    groups = [list(blocks.values()) for blocks in strata.values()]

    def d(sample):
        x, y = metrics(sample, a)[key], metrics(sample, b)[key]
        return (y - x) if flip else (x - y)
    rng = random.Random(seed)
    draws = sorted(d([w for g in groups for _ in g for w in g[rng.randrange(len(g))]])
                   for _ in range(RESAMPLES))
    point = d(rows)
    p = 2 * min(sum(v <= 0 for v in draws), sum(v >= 0 for v in draws)) / RESAMPLES
    lo, hi = int(0.025 * RESAMPLES) - 1, int(0.975 * RESAMPLES) - 1
    return {"point": round(point, 4), "ci95": [round(draws[lo], 4), round(draws[hi], 4)],
            "p": min(1.0, round(p, 4)), "blocks": sum(len(g) for g in groups), "windows": len(rows)}


def holm(family: dict) -> None:
    ordered = sorted(family.items(), key=lambda kv: kv[1]["p"])
    still = True
    for rank, (_, entry) in enumerate(ordered):
        entry["holm_threshold"] = round(0.05 / (len(ordered) - rank), 4)
        entry["holm_significant"] = still and entry["p"] <= entry["holm_threshold"]
        still = still and entry["holm_significant"]


def score() -> int:
    if hashlib.sha256(RIDGE.read_bytes()).hexdigest() != RIDGE_SHA:
        raise SystemExit(f"{RIDGE} is not the model frozen before P105 footage was counted")
    if not committed(THRESHOLDS):
        raise SystemExit(f"{THRESHOLDS} must be committed, unchanged, before scoring")
    ridge = json.loads(RIDGE.read_text(encoding="utf-8"))
    frozen = json.loads(THRESHOLDS.read_text(encoding="utf-8"))
    rows = []
    for camera in CAMERAS:
        q = frozen["cameras"].get(camera, {})
        if "q33" not in q:
            continue
        for w in windows(camera, ridge):
            if w["role"] != "test":
                continue
            w["true"] = [level(m, q["q33"], q["q67"]) for m in w["future"]]
            w["count"] = {m: [max(0.0, r + d) for r, d in zip(w["recent"], w["delta"][m])]
                          for m in METHODS}
            w["cls"] = {m: [level(x, q["q33"], q["q67"]) for x in w["count"][m]] for m in METHODS}
            rows.append(w)

    cams = sorted({w["camera"] for w in rows})
    report = {"protocol": "PREREGISTRATION_P105.md", "ridge_sha256": RIDGE_SHA,
              "windows": len(rows), "blocks": len({w["block"] for w in rows}),
              "pooled": {m: {k: round(v, 4) for k, v in metrics(rows, m).items()} for m in METHODS},
              "per_camera": {c: {m: {k: round(v, 4) for k, v in
                                     metrics([w for w in rows if w["camera"] == c], m).items()}
                                 for m in METHODS} for c in cams}}
    primary = {"ridge - persistence, macro-F1": ci(rows, "ridge", "persistence", "f1", seed=0),
               "persistence - ridge, count MAE": ci(rows, "ridge", "persistence", "mae", seed=1, flip=True)}
    holm(primary)
    report["primary"] = primary
    secondary = {"trend - persistence, macro-F1": ci(rows, "trend", "persistence", "f1", seed=2),
                 "persistence - trend, count MAE": ci(rows, "trend", "persistence", "mae", seed=3, flip=True),
                 "ridge - persistence, LOW recall": ci(rows, "ridge", "persistence", "LOW", seed=4)}
    for i, c in enumerate(cams):
        secondary[f"{c}: ridge - persistence, macro-F1"] = ci(
            [w for w in rows if w["camera"] == c], "ridge", "persistence", "f1", seed=10 + i)
    holm(secondary)
    report["secondary"] = secondary

    lanes = {}
    for c in cams:
        mine = [w for w in rows if w["camera"] == c]
        for j in range(len(mine[0]["future"])):
            avg = statistics.fmean(w["future"][j] for w in mine)
            lanes[f"{c} lane_{j}"] = {"future_mean_avg": round(avg, 3),
                                      "near_empty": avg < EMPTY_LANE}
    report["lanes"] = lanes
    f1_ok = primary["ridge - persistence, macro-F1"]
    mae_ok = primary["persistence - ridge, count MAE"]
    win = lambda e: e["holm_significant"] and e["point"] > 0  # noqa: E731
    report["reading"] = ("change-forecasting transfers" if win(f1_ok) and win(mae_ok) else
                         "better counts, classes unchanged" if win(mae_ok) else
                         "no transferable improvement over persistence")
    (ROOT / "p105_results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    slim = [{k: w[k] for k in ("camera", "clip", "start", "block", "true", "future", "recent")}
            | {"count": w["count"], "cls": w["cls"]} for w in rows]
    (ROOT / "p105_test_windows.json").write_text(json.dumps(slim) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("pooled", "primary", "secondary", "reading")}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("step", choices=("thresholds", "score"))
    args = parser.parse_args(argv)
    return thresholds() if args.step == "thresholds" else score()


if __name__ == "__main__":
    raise SystemExit(main())
