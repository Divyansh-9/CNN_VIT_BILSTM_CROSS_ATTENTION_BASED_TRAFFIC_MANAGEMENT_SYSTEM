"""P100 — the content control and the unseen-hour test. Frozen before any run.

    python scripts/p100_eval.py partA     # P99 checkpoint, within-hour input swap
    python scripts/p100_eval.py test      # the 6 fold runs on their unseen hours

Implements `experiments/results/bellevue_pilot/PREREGISTRATION_P100.md`.

**The swap needs no extra inference.** Window i given window j's inputs (j from
the same hour) produces exactly the model's real-input output for j. So the
swapped prediction for i is the real prediction for its partner, scored
against i's labels. The pairing is a seeded derangement within each hour.

**No selection.** A fold's model is the mean of its three seeds' class
probabilities. Validation was used only for early stopping inside the trainer.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

from scripts.p99_eval import (CLASSES, LANES, T, K, block_ci, confusion,  # noqa: E402
                              diff, level, metric)

ROOT = Path("experiments/results/bellevue_pilot")
CORPUS = Path("data/corpus_p99")
CACHE = Path("data/cache_p99")
P99_SELECTION = ROOT / "selection_P99.json"
PERIODS = {
    "sunday evening": ("2017-09-10_18", "2017-09-10_19"),
    "morning": ("2017-09-11_06", "2017-09-11_07", "2017-09-11_08", "2017-09-11_09"),
    "midday": ("2017-09-11_10", "2017-09-11_11", "2017-09-11_12", "2017-09-11_13"),
    "afternoon": ("2017-09-11_14", "2017-09-11_15", "2017-09-11_16"),
}


def stamp(hour: str) -> datetime:
    return datetime.strptime(hour, "%Y-%m-%d_%H-%M-%S")


def rows_with_truth(keep) -> list[dict]:
    """Windows of `corpus_p99` chosen by `keep(row)`, with truth and persistence."""
    counts: dict[str, list[list[int]]] = {}
    with (CORPUS / "counts.csv").open(encoding="utf-8") as handle:
        for r in csv.DictReader(handle):
            counts.setdefault(r["clip_id"], []).append([int(r["count_" + l]) for l in LANES])
    with (CORPUS / "sequences.csv").open(encoding="utf-8") as handle:
        source = list(csv.DictReader(handle))
    out = []
    for r in source:
        if not keep(r):
            continue
        c, s = counts[r["clip_id"]], int(r["start_index"])
        e = s + T - 1
        true = [CLASSES.index(r[f"label_{l}"]) for l in LANES]
        assert true == [level(sum(c[x][i] for x in range(e + 1, e + K + 1)) / K)
                        for i in range(3)], r
        out.append({"clip": r["clip_id"], "start": s, "hour": r["hour"], "block": r["block"],
                    "true": true,
                    "base": [level(sum(c[x][i] for x in range(e - K + 1, e + 1)) / K)
                             for i in range(3)]})
    return out


def probabilities(rows: list[dict], checkpoint: str) -> list[list[list[float]]]:
    import dataclasses

    import torch

    from mfstnet.cache import FeatureCache
    from mfstnet.corpus.lanes import LaneCentres
    from mfstnet.model import MFSTNet, ablation_config
    from mfstnet.temporal import lane_masks_from_centres

    cache = FeatureCache(CACHE)
    cache.load_manifest()
    bundle = torch.load(checkpoint, map_location="cpu", weights_only=True)
    if bundle["meta"]["preprocessing_hash"] != cache.spec.hash:
        raise SystemExit(f"{checkpoint}: preprocessing hash differs (ADR-005)")
    manifest = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))
    masks = lane_masks_from_centres(LaneCentres(
        names=tuple(c["name"] for c in manifest["lane_centres"]),
        centres=tuple(tuple(c["centre"]) for c in manifest["lane_centres"]),
        max_radius=float(manifest["max_radius"])), 7)
    config = dataclasses.replace(ablation_config(bundle["meta"]["config"]), n_lanes=len(LANES))
    model = MFSTNet(config, masks)
    state = {k: v for k, v in bundle["state_dict"].items() if not k.endswith("masks")}
    result = model.load_state_dict(state, strict=False)
    assert not [k for k in result.missing_keys if not k.endswith("masks")], result
    model.eval()
    out = []
    with torch.no_grad():
        for w in rows:
            cnn, vit = cache.read_window("corpus", w["clip"], w["start"], T, dtype=torch.float32)
            logits = model(cnn if config.fusion.use_cnn else None,
                           vit if config.fusion.use_vit else None).logits[0]
            out.append(torch.softmax(logits, -1).tolist())
    return out


def argmax(p: list[float]) -> int:
    return max(range(len(p)), key=p.__getitem__)


SPAN = T + K        # one window's inputs and target, in samples


def partners(rows: list[dict]) -> list[int]:
    """Amendment 2: within each hour, windows sorted by start, each paired with
    the one half the list away (a cyclic shift by n // 2). Deterministic, a
    derangement, and checked: a partner is never the window itself and never
    shares a sample with it, so the swap removes the window's own traffic."""
    by_hour: dict[str, list[int]] = {}
    for i, w in enumerate(rows):
        by_hour.setdefault(w["hour"], []).append(i)
    out = [-1] * len(rows)
    for hour, members in by_hour.items():
        members = sorted(members, key=lambda i: rows[i]["start"])
        n = len(members)
        if n < 2:
            raise SystemExit(f"hour {hour} has {n} window(s); a swap needs a partner")
        for a, i in enumerate(members):
            j = members[(a + n // 2) % n]
            if j == i or rows[i]["clip"] != rows[j]["clip"] or                     abs(rows[i]["start"] - rows[j]["start"]) < SPAN:
                raise SystemExit(f"{hour}: window {rows[i]['start']} would be paired "
                                 f"with overlapping window {rows[j]['start']} — STOP")
            out[i] = j
    return out


def add_swap(rows: list[dict], key: str) -> None:
    """`key + "_swap"`: each window gets its partner's real-input prediction,
    which is exactly what the model outputs when given the partner's inputs."""
    for i, j in enumerate(partners(rows)):
        rows[i][key + "_swap"] = rows[j][key]


def recall_table(rows, keys) -> dict:
    return {name: {c: round(metric(rows, k, (0, 1, 2), c), 4) for c in CLASSES}
            for name, k in keys.items()}


def holm(family: dict) -> None:
    ordered = sorted(family.items(), key=lambda kv: kv[1]["p"])
    still = True
    for rank, (_, entry) in enumerate(ordered):
        entry["holm_threshold"] = round(0.05 / (len(ordered) - rank), 4)
        entry["holm_significant"] = still and entry["p"] <= entry["holm_threshold"]
        still = still and entry["holm_significant"]


# ------------------------------------------------------------------- part A --

def part_a() -> int:
    selection = json.loads(P99_SELECTION.read_text(encoding="utf-8"))
    rows = rows_with_truth(lambda r: r["split"] == "test")
    for w, p in zip(rows, probabilities(rows, selection["selected"]["checkpoint"])):
        w["model"] = [argmax(q) for q in p]
    add_swap(rows, "model")
    report = {
        "protocol": "PREREGISTRATION_P100.md, Part A",
        "note": "re-analysis of P99's already-read test windows; changes no P99 result",
        "checkpoint": selection["selected"]["checkpoint"], "windows": len(rows),
        "real_macro_f1": round(metric(rows, "model", (0, 1, 2), "f1"), 4),
        "swapped_macro_f1": round(metric(rows, "model_swap", (0, 1, 2), "f1"), 4),
        "real_minus_swapped": block_ci(rows, "model", "model_swap"),
        "recall": recall_table(rows, {"real": "model", "swapped": "model_swap"}),
    }
    (ROOT / "p100_partA.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


# --------------------------------------------------------------------- test --

def clock_prior(train_rows: list[dict], hour: str) -> list[int]:
    """Nearest training hour(s) in absolute time; ties pooled; then fold-wide
    frequency; then the lower ordinal. Never sees the test hour's labels."""
    hours = sorted({r["hour"] for r in train_rows})
    # Whole hours (Amendment 1): file starts jitter by seconds (06:08:29,
    # 07:08:31, 08:08:31), which would otherwise break every equidistant tie.
    gaps = {h: round(abs((stamp(h) - stamp(hour)).total_seconds()) / 3600) for h in hours}
    nearest = {h for h in hours if gaps[h] == min(gaps.values())}
    out = []
    for lane in LANES:
        overall = Counter(r[f"label_{lane}"] for r in train_rows)
        here = Counter(r[f"label_{lane}"] for r in train_rows if r["hour"] in nearest)
        out.append(min(range(3), key=lambda i: (-here[CLASSES[i]], -overall[CLASSES[i]], i)))
    return out


def test() -> int:
    from scripts.p100_corpus import assign, load
    from scripts.p100_train import FOLDS, SEEDS, done, paths

    missing = [(f, s) for f in FOLDS for s in SEEDS if not done(f, s)]
    if missing:
        raise SystemExit(f"runs incomplete: {missing}")
    folds, _ = assign(load()[0])
    rows: list[dict] = []
    for fold in FOLDS:
        test_hours = {r["hour"] for r in folds[fold]["test"]}
        train_rows = folds[fold]["train"]
        mine = rows_with_truth(lambda r: r["hour"] in test_hours)
        per_seed = [probabilities(mine, str(paths(fold, s)[1])) for s in SEEDS]
        for i, w in enumerate(mine):
            w["fold"] = fold
            w["clock"] = clock_prior(train_rows, w["hour"])
            mean = [[sum(p[i][lane][c] for p in per_seed) / len(SEEDS) for c in range(3)]
                    for lane in range(3)]
            w["model"] = [argmax(q) for q in mean]
            for s, p in zip(SEEDS, per_seed):
                w[f"seed{s}"] = [argmax(q) for q in p[i]]
        rows += mine
    add_swap(rows, "model")

    report = {"protocol": "PREREGISTRATION_P100.md, Part B", "windows": len(rows),
              "blocks": len({w["block"] for w in rows}),
              "support": {c: sum(w["true"][i] == k for w in rows for i in range(3))
                          for k, c in enumerate(CLASSES)},
              "macro_f1": {who: round(metric(rows, k, (0, 1, 2), "f1"), 4)
                           for who, k in (("model", "model"), ("clock prior", "clock"),
                                          ("persistence", "base"),
                                          ("model, swapped input", "model_swap"))},
              "recall": recall_table(rows, {"model": "model", "clock prior": "clock",
                                            "persistence": "base"}),
              "confusion": {k: confusion(rows, k) for k in ("model", "clock", "base")}}

    primary = {"model - clock prior": block_ci(rows, "model", "clock", seed=0),
               "model - persistence": block_ci(rows, "model", "base", seed=1)}
    holm(primary)
    for entry in primary.values():
        entry["beats"] = entry["holm_significant"] and entry["point"] > 0
    report["primary"] = primary

    secondary = {
        "content: real - swapped": block_ci(rows, "model", "model_swap", seed=2),
        "LOW recall: model - clock": block_ci(rows, "model", "clock", "LOW", seed=3),
        "LOW recall: model - persistence": block_ci(rows, "model", "base", "LOW", seed=4)}
    for fold in FOLDS:
        secondary[f"fold {fold}: model - clock"] = block_ci(
            [w for w in rows if w["fold"] == fold], "model", "clock", seed=5 + ord(fold))
    holm(secondary)
    report["secondary"] = secondary

    report["reported_not_tested"] = {
        "each seed": {f"seed{s}": {"macro_f1": round(metric(rows, f"seed{s}", (0, 1, 2), "f1"), 4),
                                   "minus_clock": round(diff(rows, f"seed{s}", "clock"), 4),
                                   "minus_persistence": round(diff(rows, f"seed{s}", "base"), 4)}
                      for s in SEEDS},
        "each lane": {name: {"minus_clock": round(diff(rows, "model", "clock", lanes=(i,)), 4),
                             "minus_persistence": round(diff(rows, "model", "base", lanes=(i,)), 4)}
                      for i, name in enumerate(LANES.values())},
        "each period": {p: {"minus_clock": round(diff(sub, "model", "clock"), 4),
                            "minus_persistence": round(diff(sub, "model", "base"), 4),
                            "windows": len(sub)}
                        for p, prefixes in PERIODS.items()
                        for sub in [[w for w in rows if w["hour"].startswith(prefixes)]]},
        "LOW recall against the 0.50 bar (information only)": report["recall"]["model"]["LOW"],
    }
    (ROOT / "p100_results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (ROOT / "p100_test_windows.json").write_text(json.dumps(rows), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("step", choices=("partA", "test"))
    args = parser.parse_args(argv)
    return part_a() if args.step == "partA" else test()


if __name__ == "__main__":
    raise SystemExit(main())
