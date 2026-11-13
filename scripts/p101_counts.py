"""P101 — a count-only forecaster on P100's folds, against vision and both baselines.

    python scripts/p101_counts.py

Implements `experiments/results/bellevue_pilot/PREREGISTRATION_P101.md`,
committed before this ran. The count model sees exactly the 60-sample window
the vision model sees, has no clock feature, and is fitted per fold on that
fold's training windows only. Nothing is selected. The vision model's
decisions are read from P100's committed per-window file rather than
recomputed, so the comparison is paired on identical windows.

EXPLORATORY: P100's test windows have been read once already.
"""

from __future__ import annotations

import csv
import hashlib
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

from scripts.p99_eval import CLASSES, LANES, T, K, block_ci, confusion, diff, level, metric  # noqa: E402
from scripts.p100_eval import holm  # noqa: E402

ROOT = Path("experiments/results/bellevue_pilot")
CORPUS = Path("data/corpus_p99")
P100_WINDOWS = ROOT / "p100_test_windows.json"
VARIANTS = ("logreg", "logreg_balanced", "hgb")
LANE_KEYS = tuple(LANES)


def series() -> dict[str, list[list[int]]]:
    out: dict[str, list[list[int]]] = {}
    with (CORPUS / "counts.csv").open(encoding="utf-8") as handle:
        for r in csv.DictReader(handle):
            out.setdefault(r["clip_id"], []).append([int(r["count_" + l]) for l in LANE_KEYS])
    return out


def features(c: list[list[int]], s: int) -> list[float]:
    """8 per lane over inputs s … s+59, all three lanes: 24. No clock."""
    e = s + T - 1
    out = []
    xs = list(range(T))
    x_mean = statistics.fmean(xs)
    sxx = sum((x - x_mean) ** 2 for x in xs)
    for lane in range(3):
        v = [c[x][lane] for x in range(s, e + 1)]
        y_mean = statistics.fmean(v)
        slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, v)) / sxx
        out += [y_mean, statistics.fmean(v[-30:]), statistics.fmean(v[-15:]),
                statistics.fmean(v[-5:]), v[-1], statistics.pstdev(v), max(v), slope]
    return out


def make(variant: str):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression

    if variant == "logreg":
        return LogisticRegression(C=1.0, max_iter=5000)
    if variant == "logreg_balanced":
        return LogisticRegression(C=1.0, max_iter=5000, class_weight="balanced")
    return HistGradientBoostingClassifier(random_state=0)


def main() -> int:
    import numpy as np
    from sklearn.preprocessing import StandardScaler

    from scripts.p100_corpus import assign, load

    rows = json.loads(P100_WINDOWS.read_text(encoding="utf-8"))
    digest = hashlib.sha256(P100_WINDOWS.read_bytes()).hexdigest()
    counts = series()
    folds, _ = assign(load()[0])

    for w in rows:                     # the truth P100 scored, recomputed
        c, e = counts[w["clip"]], w["start"] + T - 1
        assert w["true"] == [level(sum(c[x][i] for x in range(e + 1, e + K + 1)) / K)
                             for i in range(3)], w

    fitted = {}
    for fold in ("A", "B"):
        train = folds[fold]["train"]
        test_hours = {r["hour"] for r in folds[fold]["test"]}
        assert not test_hours & {r["hour"] for r in train}
        X = np.array([features(counts[r["clip_id"]], int(r["start_index"])) for r in train])
        scaler = StandardScaler().fit(X)              # training windows only
        Xs = scaler.transform(X)
        mine = [w for w in rows if w["fold"] == fold]
        Xt = scaler.transform(np.array([features(counts[w["clip"]], w["start"]) for w in mine]))
        for variant in VARIANTS:
            for lane_index, lane in enumerate(LANE_KEYS):
                y = np.array([CLASSES.index(r[f"label_{lane}"]) for r in train])
                model = make(variant).fit(Xs, y)
                fitted[(fold, variant, lane)] = sorted(int(k) for k in model.classes_)
                predicted = model.predict(Xt)
                for w, p in zip(mine, predicted):
                    w.setdefault(variant, [0, 0, 0])[lane_index] = int(p)

    keys = {"counts (logreg)": "logreg", "counts (logreg, balanced)": "logreg_balanced",
            "counts (gradient boosting)": "hgb", "vision (P100)": "model",
            "clock prior": "clock", "persistence": "base"}
    report = {
        "protocol": "PREREGISTRATION_P101.md", "status": "exploratory: P100's test windows, already read",
        "p100_windows_sha256": digest, "windows": len(rows),
        "blocks": len({w["block"] for w in rows}),
        "support": {c: sum(w["true"][i] == k for w in rows for i in range(3))
                    for k, c in enumerate(CLASSES)},
        "classes_seen_in_training": {f"{f}/{v}/{l}": cl for (f, v, l), cl in fitted.items()
                                     if v == "logreg"},
        "macro_f1": {n: round(metric(rows, k, (0, 1, 2), "f1"), 4) for n, k in keys.items()},
        "recall": {n: {c: round(metric(rows, k, (0, 1, 2), c), 4) for c in CLASSES}
                   for n, k in keys.items()},
        "confusion": {n: confusion(rows, k) for n, k in keys.items()},
    }
    primary = {"vision - counts": block_ci(rows, "model", "logreg", seed=0),
               "counts - clock prior": block_ci(rows, "logreg", "clock", seed=1),
               "counts - persistence": block_ci(rows, "logreg", "base", seed=2)}
    holm(primary)
    report["family"] = primary
    report["variants_untested"] = {
        name: {"vision - counts": round(diff(rows, "model", v), 4),
               "counts - clock prior": round(diff(rows, v, "clock"), 4),
               "counts - persistence": round(diff(rows, v, "base"), 4)}
        for name, v in (("logreg_balanced", "logreg_balanced"), ("hgb", "hgb"))}

    # Complementarity: where counts and vision disagree, who is right, by class.
    comp = {c: {"disagree": 0, "counts_right": 0, "vision_right": 0, "neither": 0}
            for c in CLASSES}
    for w in rows:
        for i in range(3):
            a, b, t = w["logreg"][i], w["model"][i], w["true"][i]
            if a != b:
                e = comp[CLASSES[t]]
                e["disagree"] += 1
                e["counts_right" if a == t else "vision_right" if b == t else "neither"] += 1
    report["complementarity"] = comp
    (ROOT / "p101_results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("macro_f1", "recall", "family",
                                             "variants_untested", "complementarity",
                                             "support")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
