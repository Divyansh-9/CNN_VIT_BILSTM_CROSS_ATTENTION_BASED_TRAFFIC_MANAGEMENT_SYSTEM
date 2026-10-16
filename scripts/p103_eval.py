"""P103 — calibrate, check support, then score the frozen forecasters once.

    python scripts/p103_eval.py thresholds   # calibration hours only; support checks
    python scripts/p103_eval.py score        # refuses unless the thresholds are committed

Implements `experiments/results/bellevue_pilot/PREREGISTRATION_P103.md`.

**`thresholds`** reads each camera's Sunday 18:08 calibration hour and nothing
else, and computes q33/q67 of its 60 s future means, pooled over lanes. It
then counts the test hours' **targets** under both policies (no model is
loaded) and applies the protocol's stop rule: fewer than 30 pooled
lane-decisions of any class under the primary policy stops the run before
scoring.

**`score`** applies `c1L_v1.json`, unchanged, to every test window. It checks
the artifact's SHA-256 against the value committed with the protocol and
refuses unless `p103_thresholds.json` is committed and unchanged.

Cameras have four lanes here and NE 8th had three, so the 8 features are
computed from one lane's series directly. `self_check()` proves them identical
to the features the frozen model was trained on.
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

ROOT = Path("experiments/results/bellevue_pilot")
CORPUS = Path("data/corpus_p103")
ARTIFACT = ROOT / "c1L_v1.json"
ARTIFACT_SHA = "dbbd8df01b4de5882d9659c2789f36470b378f7b584162902ad8e2f0d464d007"
THRESHOLDS = ROOT / "p103_thresholds.json"
CAMERAS = ("150th_Eastgate", "150th_Newport", "150th_SE38th")
CLASSES = ["LOW", "MEDIUM", "HIGH"]
T, K, STRIDE, BLOCK = 60, 30, 15, 300
CALIBRATION = "2017-09-10_18"
ABSOLUTE = (2.0, 8.0)
RESAMPLES = 10_000
FLAG_CAMERA, STOP_POOLED = 10, 30


def lane_features(v: list[int], s: int) -> list[float]:
    """P101's 8 per-lane features from ONE lane's series, inputs s … s+59."""
    w = v[s:s + T]
    xs = range(T)
    x_mean = statistics.fmean(xs)
    sxx = sum((x - x_mean) ** 2 for x in xs)
    y_mean = statistics.fmean(w)
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, w)) / sxx
    return [y_mean, statistics.fmean(w[-30:]), statistics.fmean(w[-15:]),
            statistics.fmean(w[-5:]), w[-1], statistics.pstdev(w), max(w), slope]


def self_check() -> None:
    """The features must be exactly what c1L_v1 was trained on."""
    from scripts.c1L_freeze import own_lane
    from scripts.p101_counts import series

    counts = series()
    clip = sorted(counts)[0]
    c = counts[clip]
    for s in (0, 450, 900):
        for lane in range(3):
            assert lane_features([row[lane] for row in c], s) == own_lane(c, s, lane), (s, lane)


def level(x: float, low: float, med: float) -> int:
    return 0 if x <= low else (1 if x <= med else 2)


def load(camera: str) -> tuple[dict[str, list[list[int]]], list[str]]:
    root = CORPUS / camera
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    lanes = manifest["lanes"]
    out: dict[str, list[list[int]]] = {}
    with (root / "counts.csv").open(encoding="utf-8") as handle:
        for r in csv.DictReader(handle):
            out.setdefault(r["clip_id"], []).append([int(r["count_" + l]) for l in lanes])
    return out, lanes


def windows(camera: str) -> list[dict]:
    """Every eligible window of every file, with its future and past means."""
    counts, lanes = load(camera)
    rows = []
    for clip, c in sorted(counts.items()):
        n = len(c)
        role = "calibration" if CALIBRATION in clip else "test"
        for s in range(0, n, STRIDE):
            e = s + T - 1
            if e + K >= n or e - K + 1 < 0:
                continue
            series = [[row[j] for row in c] for j in range(len(lanes))]
            rows.append({
                "camera": camera, "clip": clip, "role": role, "start": s,
                "block": f"{clip}#{s // BLOCK}",
                "future": [sum(v[e + 1:e + K + 1]) / K for v in series],
                "past": [sum(v[e - K + 1:e + 1]) / K for v in series],
                "x": [lane_features(v, s) for v in series]})
    return rows


def calibrate(rows: list[dict]) -> tuple[float, float]:
    import numpy as np

    values = [m for w in rows if w["role"] == "calibration" for m in w["future"]]
    q33, q67 = np.percentile(values, [33, 67])
    return float(q33), float(q67)


# --------------------------------------------------------------- thresholds --

def thresholds() -> int:
    self_check()
    report = {"protocol": "PREREGISTRATION_P103.md", "calibration_hour": CALIBRATION,
              "rule": "q33/q67 of 60 s future means, calibration hour only, pooled over lanes",
              "cameras": {}}
    pooled = [0, 0, 0]
    for camera in CAMERAS:
        rows = windows(camera)
        cal = [w for w in rows if w["role"] == "calibration"]
        test = [w for w in rows if w["role"] == "test"]
        if not cal or not test:
            raise SystemExit(f"{camera}: calibration {len(cal)} / test {len(test)} windows — "
                             f"excluded by the protocol; amend before scoring")
        q33, q67 = calibrate(rows)
        support = {}
        for name, (low, med) in (("calibrated", (q33, q67)), ("absolute", ABSOLUTE)):
            got = [0, 0, 0]
            for w in test:
                for m in w["future"]:
                    got[level(m, low, med)] += 1
            support[name] = dict(zip(CLASSES, got))
            if name == "calibrated":
                pooled = [a + b for a, b in zip(pooled, got)]
        flags = [c for c, k in support["calibrated"].items() if k < FLAG_CAMERA]
        report["cameras"][camera] = {
            "q33": round(q33, 4), "q67": round(q67, 4),
            "calibration_windows": len(cal), "test_windows": len(test),
            "test_blocks": len({w["block"] for w in test}),
            "lanes": len(test[0]["future"]), "test_support": support,
            "flagged_classes_under_10": flags}
    report["pooled_calibrated_support"] = dict(zip(CLASSES, pooled))
    report["stop"] = min(pooled) < STOP_POOLED
    THRESHOLDS.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["stop"]:
        raise SystemExit(f"pooled support under {STOP_POOLED} for a class — STOP for an amendment")
    print(f"\n  commit {THRESHOLDS} before `score`")
    return 0


# -------------------------------------------------------------------- score --

def committed(path: Path) -> bool:
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", str(path)],
                             capture_output=True).returncode == 0
    clean = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", str(path)]).returncode == 0
    return tracked and clean


def predict(artifact: dict, x: list[float]) -> tuple[float, int]:
    z = [(v - m) / s for v, m, s in zip(x, artifact["scaler"]["mean"], artifact["scaler"]["scale"])]
    reg = artifact["regression"]
    mean = reg["intercept"] + sum(w * v for w, v in zip(reg["coef"], z))
    cls = artifact["classifier"]
    scores = [b + sum(w * v for w, v in zip(row, z)) for row, b in zip(cls["coef"], cls["intercept"])]
    return mean, cls["classes"][max(range(len(scores)), key=scores.__getitem__)]


def scores(rows, key) -> dict:
    from mfstnet.metrics import evaluate

    t = [x for w in rows for x in w["true"]]
    p = [x for w in rows for x in w[key]]
    r = evaluate(t, p, CLASSES)
    return {"f1": r.macro_f1, **{c: r.per_class[i].recall for i, c in enumerate(CLASSES)}}


def ci(rows, a, b, metric="f1", seed=0) -> dict:
    """Block bootstrap stratified by camera: blocks resampled within each camera."""
    strata: dict[str, dict[str, list]] = {}
    for w in rows:
        strata.setdefault(w["camera"], {}).setdefault(w["block"], []).append(w)
    groups = {cam: list(blocks.values()) for cam, blocks in strata.items()}
    rng = random.Random(seed)
    draws = []
    for _ in range(RESAMPLES):
        sample = [w for g in groups.values() for _ in g for w in g[rng.randrange(len(g))]]
        draws.append(scores(sample, a)[metric] - scores(sample, b)[metric])
    draws.sort()
    point = scores(rows, a)[metric] - scores(rows, b)[metric]
    p = 2 * min(sum(d <= 0 for d in draws), sum(d >= 0 for d in draws)) / RESAMPLES
    lo, hi = int(0.025 * RESAMPLES) - 1, int(0.975 * RESAMPLES) - 1   # 249, 9749 at 10,000
    return {"point": round(point, 4), "ci95": [round(draws[lo], 4), round(draws[hi], 4)],
            "p": min(1.0, round(p, 4)), "blocks": sum(len(g) for g in groups.values()),
            "windows": len(rows)}


def holm(family: dict) -> None:
    ordered = sorted(family.items(), key=lambda kv: kv[1]["p"])
    still = True
    for rank, (_, entry) in enumerate(ordered):
        entry["holm_threshold"] = round(0.05 / (len(ordered) - rank), 4)
        entry["holm_significant"] = still and entry["p"] <= entry["holm_threshold"]
        still = still and entry["holm_significant"]


def confusion(rows, key):
    m = [[0] * 3 for _ in range(3)]
    for w in rows:
        for t, p in zip(w["true"], w[key]):
            m[t][p] += 1
    return m


def score() -> int:
    self_check()
    if hashlib.sha256(ARTIFACT.read_bytes()).hexdigest() != ARTIFACT_SHA:
        raise SystemExit(f"{ARTIFACT} is not the artifact frozen with the protocol")
    if not committed(THRESHOLDS):
        raise SystemExit(f"{THRESHOLDS} must be committed, unchanged, before scoring")
    frozen = json.loads(THRESHOLDS.read_text(encoding="utf-8"))
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))

    arms = {"calibrated": [], "absolute": []}
    for camera in CAMERAS:
        rows = windows(camera)
        q = frozen["cameras"][camera]
        for arm, (low, med) in (("calibrated", (q["q33"], q["q67"])), ("absolute", ABSOLUTE)):
            cal = [w for w in rows if w["role"] == "calibration"]
            n_lanes = len(cal[0]["future"])
            prior = []
            for j in range(n_lanes):
                tally = [0, 0, 0]
                for w in cal:
                    tally[level(w["future"][j], low, med)] += 1
                prior.append(max(range(3), key=lambda i: (tally[i], -i)))
            for w in rows:
                if w["role"] != "test":
                    continue
                out = {"camera": camera, "clip": w["clip"], "start": w["start"],
                       "block": w["block"],
                       "future": [round(m, 4) for m in w["future"]],
                       "true": [level(m, low, med) for m in w["future"]],
                       "persistence": [level(m, low, med) for m in w["past"]],
                       "prior": prior}
                preds = [predict(artifact, x) for x in w["x"]]
                out["c1l"] = [level(m, low, med) for m, _ in preds]
                out["c1l_mean"] = [round(m, 4) for m, _ in preds]
                if arm == "absolute":
                    out["c1l_cls"] = [c for _, c in preds]
                arms[arm].append(out)

    cal_rows, abs_rows = arms["calibrated"], arms["absolute"]
    report = {"protocol": "PREREGISTRATION_P103.md", "artifact_sha256": ARTIFACT_SHA,
              "thresholds": {c: {k: frozen["cameras"][c][k] for k in ("q33", "q67")} for c in CAMERAS}}
    methods = {"C1-L": "c1l", "persistence": "persistence", "calibration prior": "prior"}
    for arm, rows in (("calibrated", cal_rows), ("absolute", abs_rows)):
        names = dict(methods, **({"C1-L-cls": "c1l_cls"} if arm == "absolute" else {}))
        report[arm] = {
            "pooled": {n: {k: round(v, 4) for k, v in scores(rows, key).items()}
                       for n, key in names.items()},
            "per_camera": {cam: {n: {k: round(v, 4) for k, v in
                                     scores([w for w in rows if w["camera"] == cam], key).items()}
                                 for n, key in names.items()} for cam in CAMERAS},
            "confusion": {n: confusion(rows, key) for n, key in names.items()},
            "support": {c: sum(t == i for w in rows for t in w["true"]) for i, c in enumerate(CLASSES)}}

    primary = {"C1-L - persistence": ci(cal_rows, "c1l", "persistence", seed=0),
               "C1-L - calibration prior": ci(cal_rows, "c1l", "prior", seed=1)}
    holm(primary)
    for entry in primary.values():
        entry["beats"] = entry["holm_significant"] and entry["point"] > 0
    report["primary"] = primary

    secondary = {f"{cam}: C1-L - persistence": ci([w for w in cal_rows if w["camera"] == cam],
                                                  "c1l", "persistence", seed=10 + i)
                 for i, cam in enumerate(CAMERAS)}
    secondary["LOW recall: C1-L - persistence"] = ci(cal_rows, "c1l", "persistence", "LOW", seed=20)
    secondary["absolute: C1-L-cls - persistence"] = ci(abs_rows, "c1l_cls", "persistence", seed=21)
    secondary["absolute: C1-L - persistence"] = ci(abs_rows, "c1l", "persistence", seed=22)
    holm(secondary)
    report["secondary"] = secondary

    # Amendment 2: limitation lanes, fixed before any count was read. The
    # thresholds stay as calibrated on all lanes; only the scored lanes change.
    def without(rows, drops):
        out = []
        for w in rows:
            keep = [j for j in range(len(w["true"])) if (w["camera"], j) not in drops]
            out.append({**w, **{k: [w[k][j] for j in keep]
                                for k in ("true", "c1l", "persistence", "prior")}})
        return out
    limits = {"Newport lane_2 (signal housing)": {("150th_Newport", 2)},
              "Eastgate lane_1 (roof and parking)": {("150th_Eastgate", 1)}}
    limits["both"] = set().union(*limits.values())
    report["sensitivity"] = {
        f"without {name}": {"C1-L - persistence": ci(without(cal_rows, drops), "c1l", "persistence", seed=30 + i),
                            "C1-L - calibration prior": ci(without(cal_rows, drops), "c1l", "prior", seed=40 + i)}
        for i, (name, drops) in enumerate(limits.items())}
    report["sensitivity_note"] = "reported, not tested; the pre-registered pooled primary stands"

    # Every lane, measured the same way: a near-constant background shows here.
    lanes = {}
    for cam in CAMERAS:
        mine = [w for w in cal_rows if w["camera"] == cam]
        for j in range(len(mine[0]["true"])):
            future = [w["true"][j] for w in mine]
            sub = [{**w, "true": [w["true"][j]], "c1l": [w["c1l"][j]],
                    "persistence": [w["persistence"][j]]} for w in mine]
            truth_means = [w["future"][j] for w in mine]
            lanes[f"{cam} lane_{j}"] = {
                "flag": next((n for n, d in limits.items() if n != "both" and (cam, j) in d), ""),
                "future_mean_avg": round(statistics.fmean(truth_means), 3),
                "future_mean_std": round(statistics.pstdev(truth_means), 3),
                "share_in_modal_class": round(max(future.count(c) for c in range(3)) / len(future), 3),
                "C1-L_minus_persistence_f1": round(scores(sub, "c1l")["f1"] - scores(sub, "persistence")["f1"], 4)}
    report["per_lane"] = lanes

    positive = sum(secondary[f"{cam}: C1-L - persistence"]["point"] > 0 for cam in CAMERAS)
    report["reading"] = (
        "transfers" if primary["C1-L - persistence"]["beats"] and positive >= 2 else
        "camera-dependent" if primary["C1-L - persistence"]["beats"] else
        "no improvement over persistence")
    report["cameras_with_positive_point"] = positive
    (ROOT / "p103_results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (ROOT / "p103_test_windows.json").write_text(json.dumps(cal_rows) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("thresholds", "primary", "secondary", "reading")}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("step", choices=("thresholds", "score"))
    args = parser.parse_args(argv)
    return thresholds() if args.step == "thresholds" else score()


if __name__ == "__main__":
    raise SystemExit(main())
