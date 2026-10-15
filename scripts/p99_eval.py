"""P99 — selection on validation, then the one-time test read. Frozen before training.

    python scripts/p99_eval.py select      # validation only; writes selection_P99.json
    python scripts/p99_eval.py test        # refuses unless that selection is committed

Implements `experiments/results/bellevue_pilot/PREREGISTRATION_P99.md` and its
Amendment 1. This file was committed **before any P99 run trained**, so every
rule below was fixed without knowledge of any P99 score.

**`select`** reads only the runs' validation scores. Under `--no-test` the
training corpus holds no test window, so nothing else exists to read.

**`test`** refuses unless `selection_P99.json` is tracked by git and unchanged
since it was committed. It then predicts the test windows with the four
selected checkpoints and the frozen P97 control, and reports everything the
protocol lists: the primary, every secondary under Holm, the shortcut
diagnostic, both objectives, every lane and period ablation, and Phase 2
conditions 1 to 3. Condition 4 (ONNX parity and the test suite) is a separate
step and is recorded as pending here.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

ROOT = Path("experiments/results/bellevue_pilot")
SELECTION = ROOT / "selection_P99.json"
CORPUS = Path("data/corpus_p99")
CACHE = Path("data/cache_p99")
CLASSES = ["LOW", "MEDIUM", "HIGH"]
LANES = {"lane_0": "west", "lane_1": "north", "lane_2": "east"}
T, K = 60, 30
SEEDS = (42, 1, 7, 13, 21)
CONFIGS = ("G", "H")
WEIGHTS = ("inverse", "none")
RESAMPLES = 10_000
CONTROL = "models/mfstnet/bellevue_3lane_sus60/mfstnet_G_seed13.pt"
P97_HOURS = ("2017-09-11_15-08-32", "2017-09-11_16-08-32")
PERIODS = {
    "sunday evening (18:08, 19:08)": ("2017-09-10_18", "2017-09-10_19"),
    "morning (06:08-09:08)": ("2017-09-11_06", "2017-09-11_07", "2017-09-11_08", "2017-09-11_09"),
    "midday (10:08-13:08)": ("2017-09-11_10", "2017-09-11_11", "2017-09-11_12", "2017-09-11_13"),
    "afternoon (14:08-16:08)": ("2017-09-11_14", "2017-09-11_15", "2017-09-11_16"),
}
LOW_RECALL_FLOOR, LOW_SUPPORT_FLOOR = 0.50, 30


def level(x: float) -> int:
    return 0 if x <= 2 else (1 if x <= 8 else 2)


# ------------------------------------------------------------------ select --

def run_score(config: str, weighting: str, seed: int) -> float:
    from scripts.p99_train import paths

    out, _ = paths(config, weighting, seed)
    sidecar = json.loads(out.with_suffix(".provenance.json").read_text(encoding="utf-8"))
    if sidecar.get("evaluated_on") != "val" or sidecar.get("class_weights") != weighting:
        raise SystemExit(f"{out}: not a --no-test {weighting} run (sidecar {sidecar})")
    with out.open(encoding="utf-8") as handle:
        (row,) = list(csv.DictReader(handle))
    return float(row["val_macro_f1"])


def select() -> int:
    from scripts.p99_train import paths

    scores = {(c, w, s): run_score(c, w, s) for c in CONFIGS for w in WEIGHTS for s in SEEDS}
    pairs = {(c, w): sum(scores[(c, w, s)] for s in SEEDS) / len(SEEDS)
             for c in CONFIGS for w in WEIGHTS}
    # Exact tie: H before G, then inverse before none (PREREGISTRATION_P99).
    rank = {("H", "inverse"): 0, ("H", "none"): 1, ("G", "inverse"): 2, ("G", "none"): 3}
    best = max(pairs.values())
    chosen = min((p for p, v in pairs.items() if v == best), key=rank.get)
    seeds = {}
    for pair in pairs:
        top = max(scores[(*pair, s)] for s in SEEDS)
        seed = next(s for s in SEEDS if scores[(*pair, s)] == top)
        _, checkpoint = paths(pair[0], pair[1], seed)
        seeds[f"{pair[0]}/{pair[1]}"] = {
            "seed": seed, "val_macro_f1": top, "checkpoint": str(checkpoint),
            "sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest()}
    selection = {
        "protocol": "PREREGISTRATION_P99.md", "read": "validation only",
        "val_macro_f1": {f"{c}/{w}/seed{s}": v for (c, w, s), v in scores.items()},
        "pair_means": {f"{c}/{w}": round(v, 4) for (c, w), v in pairs.items()},
        "selected_pair": f"{chosen[0]}/{chosen[1]}",
        "selected": seeds[f"{chosen[0]}/{chosen[1]}"],
        "per_pair": seeds}
    SELECTION.write_text(json.dumps(selection, indent=2), encoding="utf-8")
    print(json.dumps(selection, indent=2))
    print(f"\n  commit {SELECTION} before running `test`")
    return 0


# -------------------------------------------------------------------- test --

def assert_committed() -> None:
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", str(SELECTION)],
                             capture_output=True).returncode == 0
    clean = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", str(SELECTION)]).returncode == 0
    if not (tracked and clean):
        raise SystemExit(f"{SELECTION} must be committed, unchanged, before the test "
                         f"is read (PREREGISTRATION_P99, lock 3)")


def windows() -> list[dict]:
    """Every test window, with its truth, the baseline and the hour prior."""
    counts: dict[str, list[list[int]]] = {}
    with (CORPUS / "counts.csv").open(encoding="utf-8") as handle:
        for r in csv.DictReader(handle):
            counts.setdefault(r["clip_id"], []).append([int(r["count_" + l]) for l in LANES])
    with (CORPUS / "sequences.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    prior = hour_prior([r for r in rows if r["split"] == "train"])
    out = []
    for r in rows:
        if r["split"] != "test":
            continue
        c, s = counts[r["clip_id"]], int(r["start_index"])
        e = s + T - 1
        true = [CLASSES.index(r[f"label_{l}"]) for l in LANES]
        # The stored label must be the definition, recomputed: a silent
        # mismatch here would score every model against the wrong truth.
        assert true == [level(sum(c[x][i] for x in range(e + 1, e + K + 1)) / K)
                        for i in range(3)], r
        out.append({"clip": r["clip_id"], "start": s, "hour": r["hour"], "block": r["block"],
                    "true": true,
                    "base": [level(sum(c[x][i] for x in range(e - K + 1, e + 1)) / K)
                             for i in range(3)],
                    "prior": [prior[(r["hour"], l)] for l in LANES]})
    return out


def hour_prior(train: list[dict]) -> dict:
    """Amendment 1, frozen: per hour and lane, the most frequent class among that
    hour's TRAINING windows. A tie goes to the class more frequent in the whole
    training split for that lane, then to the lower ordinal."""
    overall = {l: Counter(r[f"label_{l}"] for r in train) for l in LANES}
    prior = {}
    for hour in sorted({r["hour"] for r in train}):
        for l in LANES:
            here = Counter(r[f"label_{l}"] for r in train if r["hour"] == hour)
            prior[(hour, l)] = min(range(3), key=lambda i: (-here[CLASSES[i]],
                                                           -overall[l][CLASSES[i]], i))
    return prior


def predict(rows: list[dict], checkpoint: str, key: str) -> None:
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
        raise SystemExit(f"{checkpoint}: preprocessing hash differs from the cache (ADR-005)")
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
    with torch.no_grad():
        for w in rows:
            cnn, vit = cache.read_window("corpus", w["clip"], w["start"], T, dtype=torch.float32)
            out = model(cnn if config.fusion.use_cnn else None,
                        vit if config.fusion.use_vit else None)
            w[key] = out.logits[0].argmax(-1).tolist()


def metric(rows, key, lanes, name):
    from mfstnet.metrics import evaluate

    t = [w["true"][i] for w in rows for i in lanes]
    p = [w[key][i] for w in rows for i in lanes]
    r = evaluate(t, p, CLASSES)
    if name == "f1":
        return r.macro_f1
    if name == "acc":
        return r.accuracy
    if name == "qwk":
        return r.qwk
    return r.per_class[CLASSES.index(name)].recall          # "LOW" / "MEDIUM" / "HIGH"


def diff(rows, a, b, name="f1", lanes=(0, 1, 2)):
    return metric(rows, a, lanes, name) - metric(rows, b, lanes, name)


def block_ci(rows, a, b, name="f1", lanes=(0, 1, 2), seed=0):
    blocks: dict[str, list] = {}
    for w in rows:
        blocks.setdefault(w["block"], []).append(w)
    groups = list(blocks.values())
    rng = random.Random(seed)
    draws = sorted(diff([w for _ in groups for w in groups[rng.randrange(len(groups))]],
                        a, b, name, lanes) for _ in range(RESAMPLES))
    point = diff(rows, a, b, name, lanes)
    p = 2 * min(sum(d <= 0 for d in draws), sum(d >= 0 for d in draws)) / RESAMPLES
    return {"point": round(point, 4), "ci95": [round(draws[249], 4), round(draws[9749], 4)],
            "p": min(1.0, round(p, 4)), "blocks": len(groups), "windows": len(rows)}


def confusion(rows, key):
    m = [[0] * 3 for _ in range(3)]
    for w in rows:
        for i in range(3):
            m[w["true"][i]][w[key][i]] += 1
    return m


def test() -> int:
    assert_committed()
    selection = json.loads(SELECTION.read_text(encoding="utf-8"))
    rows = windows()
    keys = {}
    for pair, entry in selection["per_pair"].items():
        path = Path(entry["checkpoint"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise SystemExit(f"{path} changed since selection")
        keys[pair] = f"model:{pair}"
        predict(rows, str(path), keys[pair])
    control_rows = [w for w in rows if w["hour"] not in P97_HOURS]
    predict(control_rows, CONTROL, "control")

    chosen = keys[selection["selected_pair"]]
    report = {"protocol": "PREREGISTRATION_P99.md", "selected_pair": selection["selected_pair"],
              "selected": selection["selected"],
              "support": {c: sum(w["true"][i] == k for w in rows for i in range(3))
                          for k, c in enumerate(CLASSES)}}

    primary = block_ci(rows, chosen, "base")
    primary["beats"] = primary["ci95"][0] > 0 and primary["point"] > 0
    primary["model_f1"] = round(metric(rows, chosen, (0, 1, 2), "f1"), 4)
    primary["base_f1"] = round(metric(rows, "base", (0, 1, 2), "f1"), 4)
    primary["recall"] = {who: {c: round(metric(rows, k, (0, 1, 2), c), 4) for c in CLASSES}
                         for who, k in (("model", chosen), ("baseline", "base"))}
    primary["confusion"] = {"model": confusion(rows, chosen), "baseline": confusion(rows, "base")}
    report["primary"] = primary

    config = selection["selected_pair"].split("/")[0]
    secondary = {}
    for i, name in enumerate(LANES.values()):
        secondary[f"lane {name}"] = block_ci(rows, chosen, "base", lanes=(i,), seed=1 + i)
    secondary["accuracy"] = block_ci(rows, chosen, "base", "acc", seed=11)
    secondary["QWK"] = block_ci(rows, chosen, "base", "qwk", seed=12)
    for j, c in enumerate(CLASSES):
        secondary[f"recall {c}"] = block_ci(rows, chosen, "base", c, seed=21 + j)
    secondary[f"objective: {config} inverse - none"] = block_ci(
        rows, keys[f"{config}/inverse"], keys[f"{config}/none"], seed=31)
    secondary["shortcut: model - hour prior"] = block_ci(rows, chosen, "prior", seed=41)
    ordered = sorted(secondary.items(), key=lambda kv: kv[1]["p"])
    still = True
    for rank, (_, entry) in enumerate(ordered):
        entry["holm_threshold"] = round(0.05 / (len(ordered) - rank), 4)
        entry["holm_significant"] = still and entry["p"] <= entry["holm_threshold"]
        still = still and entry["holm_significant"]
    report["secondary"] = secondary

    # Every selected model, both objectives, on the same windows: reported, not tested.
    report["all_selected_models"] = {
        pair: {"macro_f1": round(metric(rows, k, (0, 1, 2), "f1"), 4),
               "minus_baseline": round(diff(rows, k, "base"), 4),
               "minus_hour_prior": round(diff(rows, k, "prior"), 4),
               "recall": {c: round(metric(rows, k, (0, 1, 2), c), 4) for c in CLASSES}}
        for pair, k in keys.items()}
    report["hour_prior"] = {"macro_f1": round(metric(rows, "prior", (0, 1, 2), "f1"), 4),
                            "minus_baseline": round(diff(rows, "prior", "base"), 4)}
    report["control_p97"] = {
        "checkpoint": CONTROL, "windows": len(control_rows),
        "note": "test blocks of the 11 P98 hours only; 15:08 and 16:08 were its own data",
        "macro_f1": round(metric(control_rows, "control", (0, 1, 2), "f1"), 4),
        "minus_baseline": block_ci(control_rows, "control", "base", seed=51),
        "recall": {c: round(metric(control_rows, "control", (0, 1, 2), c), 4) for c in CLASSES},
        "selected_model_same_windows": round(metric(control_rows, chosen, (0, 1, 2), "f1"), 4)}

    # Phase 2 conditions 1-3 (condition 4 is a separate step).
    ablations = {f"without lane {n}": round(diff(rows, chosen, "base",
                                                 lanes=tuple(j for j in range(3) if j != i)), 4)
                 for i, n in enumerate(LANES.values())}
    for period, prefixes in PERIODS.items():
        kept = [w for w in rows if not w["hour"].startswith(prefixes)]
        ablations[f"without {period}"] = round(diff(kept, chosen, "base"), 4)
    low_support = report["support"]["LOW"]
    low_recall = primary["recall"]["model"]["LOW"]
    gates = {
        "1 LOW recall >= 0.50 (support >= 30)": low_support >= LOW_SUPPORT_FLOOR
                                                 and low_recall >= LOW_RECALL_FLOOR,
        "2 primary interval above zero": primary["beats"],
        "3 positive without any one lane or period": all(v > 0 for v in ablations.values()),
        "4 ONNX parity and test suite": "pending (export_checkpoint.py, pytest)",
    }
    report["ablations"] = ablations
    report["phase2_conditions"] = gates
    report["phase2_conditions_1_to_3_pass"] = all(v is True for k, v in gates.items()
                                                  if not k.startswith("4"))

    (ROOT / "p99_results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (ROOT / "p99_test_windows.json").write_text(json.dumps(rows), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("step", choices=("select", "test"))
    args = parser.parse_args(argv)
    return select() if args.step == "select" else test()


if __name__ == "__main__":
    raise SystemExit(main())
