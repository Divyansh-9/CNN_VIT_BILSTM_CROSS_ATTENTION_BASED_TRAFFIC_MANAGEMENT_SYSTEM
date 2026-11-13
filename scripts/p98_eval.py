"""P98 — the frozen P97 model on new hours of the same camera, scored once.

    python scripts/p98_eval.py --corpus data/corpus_p98 --cache data/cache_p98

Implements `experiments/results/bellevue_pilot/PREREGISTRATION_P98.md`, written
before any P98 footage was on disk. **Nothing is trained or reselected.**

- **Windows:** per hourly clip, a start every 30 s, inputs `s … s+59`,
  `e = s + 59`. A window never spans two files. The Monday 14:08 file loses any
  window whose input or target reaches its last 149 samples, which keeps the
  evaluation clear of P97's training period starting at 15:08:32.
- **Targets:** the P94 sustained level, `mean(c[e+1 … e+K])`, with K = 30
  (60 s, primary) or K = 60 (120 s, secondary), and frozen thresholds
  LOW ≤ 2, MEDIUM ≤ 8.
- **Models, frozen:** P97's G seed 13 for 60 s and H seed 42 for 120 s, both
  three-lane, on the cached features. **Baseline:** the previous-window mean
  over the same K.
- **Primary:** Monday daylight, 07:08–15:08, 60 s, (G − baseline) macro-F1,
  with a **10-minute block bootstrap** (10,000 resamples of whole blocks).
  Replication means the interval excludes zero with a positive point estimate.
- **Secondaries,** Holm-corrected as one family at 0.05: per lane; 60 s on the
  dawn/dusk and Sunday-daylight strata; 120 s on the primary stratum; and the
  accuracy and QWK of the primary comparison.

Writes `experiments/results/bellevue_pilot/p98_results.json`, and the
per-window decisions beside it.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

ROOT = Path("experiments/results/bellevue_pilot")
CLASSES = ["LOW", "MEDIUM", "HIGH"]
LANES = {"lane_0": "west", "lane_1": "north", "lane_2": "east"}
T, STRIDE, BLOCK_SAMPLES, BUFFER = 60, 15, 300, 149
RESAMPLES = 10_000
CHECKPOINTS = {30: ("models/mfstnet/bellevue_3lane_sus60/mfstnet_G_seed13.pt", "G"),
               60: ("models/mfstnet/bellevue_3lane_sus120/mfstnet_H_seed42.pt", "H")}


def stratum(clip: str) -> str:
    """From the clip's own timestamp, never from a folder name."""
    stamp = clip.split("__")[1]                  # 2017-09-11_09-08-30
    day, hour = stamp[:10], int(stamp[11:13])
    if day == "2017-09-11" and 7 <= hour <= 14:
        return "primary"
    if (day, hour) in (("2017-09-11", 6), ("2017-09-10", 19)):
        return "dawn_dusk"
    if (day, hour) == ("2017-09-10", 18):
        return "sunday_daylight"
    return "excluded"


def level(x: float) -> int:
    return 0 if x <= 2 else (1 if x <= 8 else 2)


def build_windows(corpus: Path, K: int) -> list[dict]:
    counts: dict[str, dict[str, list[int]]] = {}
    with (corpus / "counts.csv").open(encoding="utf-8") as handle:
        for r in csv.DictReader(handle):
            per = counts.setdefault(r["clip_id"], {lane: [] for lane in LANES})
            for lane in LANES:
                per[lane].append(int(r["count_" + lane]))
    windows = []
    for clip, per in sorted(counts.items()):
        group = stratum(clip)
        if group == "excluded":
            continue
        n = len(per["lane_0"])
        limit = n - BUFFER if clip.endswith("14-08-31") else n
        for s in range(0, n, STRIDE):
            e = s + T - 1
            if e + K >= limit or e + K >= n or e - K + 1 < 0:
                continue
            windows.append({
                "clip": clip, "stratum": group, "start": s,
                "block": f"{clip}#{s // BLOCK_SAMPLES}",
                "true": [level(sum(per[l][e + 1:e + K + 1]) / K) for l in LANES],
                "base": [level(sum(per[l][e - K + 1:e + 1]) / K) for l in LANES]})
    return windows


def eligibility(corpus: Path) -> dict:
    """Windows and blocks per file, before any model is loaded.

    Targets only: the class support is the truth the model will be scored
    against, which the protocol reports regardless of outcome, and it says
    nothing about how the model does.
    """
    manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    out = {"samples_per_clip": manifest["samples_per_clip"], "by_K": {}}
    for K in (30, 60):
        windows = build_windows(corpus, K)
        per_file = {}
        for clip in manifest["samples_per_clip"]:
            mine = [w for w in windows if w["clip"] == clip]
            per_file[clip] = {"stratum": stratum(clip), "windows": len(mine),
                              "blocks": len({w["block"] for w in mine})}
        per_stratum = {}
        for group in ("primary", "dawn_dusk", "sunday_daylight"):
            mine = [w for w in windows if w["stratum"] == group]
            truth = [t for w in mine for t in w["true"]]
            per_stratum[group] = {
                "windows": len(mine), "blocks": len({w["block"] for w in mine}),
                "support": {c: truth.count(i) for i, c in enumerate(CLASSES)},
                "support_by_lane": {name: {c: [w["true"][j] for w in mine].count(i)
                                           for i, c in enumerate(CLASSES)}
                                    for j, name in enumerate(LANES.values())}}
        out["by_K"][K] = {"per_file": per_file, "per_stratum": per_stratum}
    return out


def predict(windows, cache, corpus: Path, K: int) -> None:
    """The frozen checkpoint's decisions, on the cached features."""
    import dataclasses

    import torch

    from mfstnet.corpus.lanes import LaneCentres
    from mfstnet.model import MFSTNet, ablation_config
    from mfstnet.temporal import lane_masks_from_centres

    path, config_name = CHECKPOINTS[K]
    bundle = torch.load(path, map_location="cpu", weights_only=True)
    if bundle["meta"]["preprocessing_hash"] != cache.spec.hash:
        raise SystemExit("checkpoint and cache disagree on preprocessing (ADR-005)")
    manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    centres = manifest["lane_centres"]
    masks = lane_masks_from_centres(LaneCentres(
        names=tuple(c["name"] for c in centres),
        centres=tuple(tuple(c["centre"]) for c in centres),
        max_radius=float(manifest.get("max_radius", 0.25))), 7)
    config = dataclasses.replace(ablation_config(config_name), n_lanes=len(LANES))
    model = MFSTNet(config, masks)
    state = {k: v for k, v in bundle["state_dict"].items() if not k.endswith("masks")}
    missing = model.load_state_dict(state, strict=False)
    assert not [k for k in missing.missing_keys if not k.endswith("masks")], missing
    model.eval()
    with torch.no_grad():
        for w in windows:
            cnn, vit = cache.read_window("corpus", w["clip"], w["start"], T,
                                         dtype=torch.float32)
            out = model(cnn if config.fusion.use_cnn else None,
                        vit if config.fusion.use_vit else None)
            w["model"] = out.logits[0].argmax(-1).tolist()


def macro(t, p):
    from mfstnet.metrics import evaluate
    return evaluate(t, p, CLASSES)


def score(windows, lanes=None):
    idx = list(range(len(LANES))) if lanes is None else lanes
    t = [w["true"][i] for w in windows for i in idx]
    m = [w["model"][i] for w in windows for i in idx]
    b = [w["base"][i] for w in windows for i in idx]
    rm, rb = macro(t, m), macro(t, b)
    return {"f1": rm.macro_f1 - rb.macro_f1, "acc": rm.accuracy - rb.accuracy,
            "qwk": rm.qwk - rb.qwk, "model_f1": rm.macro_f1, "base_f1": rb.macro_f1,
            "support": {c: t.count(i) for i, c in enumerate(CLASSES)}}


def block_ci(windows, key="f1", lanes=None, seed=0):
    blocks: dict[str, list] = {}
    for w in windows:
        blocks.setdefault(w["block"], []).append(w)
    groups = list(blocks.values())
    rng = random.Random(seed)
    draws = []
    for _ in range(RESAMPLES):
        sample = [w for _ in groups for w in groups[rng.randrange(len(groups))]]
        draws.append(score(sample, lanes)[key])
    draws.sort()
    # Two-sided p from the bootstrap: share of draws on the other side of zero.
    point = score(windows, lanes)[key]
    p = 2 * min(sum(d <= 0 for d in draws), sum(d >= 0 for d in draws)) / RESAMPLES
    return {"point": round(point, 4), "ci95": [round(draws[250], 4), round(draws[9749], 4)],
            "p": min(1.0, round(p, 4)), "blocks": len(groups), "windows": len(windows)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--eligibility", action="store_true",
                        help="count windows, blocks and class support per file "
                             "and stop. Loads no model and scores nothing, so it "
                             "is safe to run before the one-time read")
    args = parser.parse_args(argv)

    if args.eligibility:
        report = eligibility(args.corpus)
        (ROOT / "p98_eligibility.json").write_text(json.dumps(report, indent=2),
                                                   encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0
    if args.cache is None:
        parser.error("--cache is required unless --eligibility")

    from mfstnet.cache import FeatureCache

    cache = FeatureCache(args.cache)
    out = {"protocol": "PREREGISTRATION_P98.md"}
    by_k = {}
    for K in (30, 60):
        windows = build_windows(args.corpus, K)
        predict(windows, cache, args.corpus, K)
        by_k[K] = windows
        (ROOT / f"p98_windows_K{K}.json").write_text(json.dumps(windows), encoding="utf-8")

    prim = [w for w in by_k[30] if w["stratum"] == "primary"]
    primary = block_ci(prim)
    primary.update({k: v for k, v in score(prim).items() if k in ("model_f1", "base_f1", "support")})
    primary["replicates"] = primary["ci95"][0] > 0 and primary["point"] > 0
    out["primary"] = primary

    secondary = {}
    for i, (lane, name) in enumerate(LANES.items()):
        secondary[f"lane {name}"] = block_ci(prim, lanes=[i], seed=i + 1)
    for group in ("dawn_dusk", "sunday_daylight"):
        sub = [w for w in by_k[30] if w["stratum"] == group]
        if sub:
            secondary[f"60 s {group}"] = block_ci(sub, seed=11)
    secondary["120 s primary stratum (H)"] = block_ci(
        [w for w in by_k[60] if w["stratum"] == "primary"], seed=21)
    secondary["primary accuracy"] = block_ci(prim, key="acc", seed=31)
    secondary["primary QWK"] = block_ci(prim, key="qwk", seed=41)

    # Holm, over the family, at 0.05.
    ordered = sorted(secondary.items(), key=lambda kv: kv[1]["p"])
    m = len(ordered)
    still = True
    for rank, (name, entry) in enumerate(ordered):
        threshold = 0.05 / (m - rank)
        entry["holm_threshold"] = round(threshold, 4)
        entry["holm_significant"] = still and entry["p"] <= threshold
        still = still and entry["holm_significant"]
    out["secondary"] = secondary
    out["windows_by_stratum"] = {g: sum(w["stratum"] == g for w in by_k[30])
                                 for g in ("primary", "dawn_dusk", "sunday_daylight")}
    (ROOT / "p98_results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
