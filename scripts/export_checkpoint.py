"""Export a TRAINED checkpoint to ONNX, and prove the graph is that model (S61).

    python scripts/export_checkpoint.py --checkpoint models/mfstnet/foreign/mfstnet_H_seed42_fold3.pt \\
        --cache data/cache_corpus

`export_onnx.py` builds a fresh `MFSTNet` and exports it. That is right for what
it measures — latency does not depend on the weights — and it is why P87 found
that no trained forecaster had ever been exported. A successful ONNX export is
not evidence of a trained model: an untrained one exports just as cleanly.

So this script does not stop at "the export worked". It runs the exported graph
over **the real cached windows of the checkpoint's own held-out test camera**
and compares its decisions with the per-window predictions that training
committed for that run (P59). A graph with trained weights reproduces them; a
graph with fresh weights does not, and the control row measures how far apart
the two are on the same windows.

**Pass criteria, fixed here rather than after looking:**

1. ONNX against PyTorch on CPU, same windows: identical argmax on every
   lane-window, and max absolute logit difference under `MAX_LOGIT_DRIFT`.
2. PyTorch on CPU against the committed predictions: at least
   `MIN_AGREEMENT` of lane-windows identical. Not 100%, on purpose — training
   ran on CUDA, and a near-tie can resolve differently on another device
   (P39); demanding exact equality would fail a correct export for a reason
   that has nothing to do with the weights.
3. The control — a fresh model of the same config — must agree **less** than
   the trained one. If it does not, the windows cannot tell the two apart and
   check 2 proves nothing.

The lane geometry baked into the graph is the test camera's own (P23, P26). A
graph is per camera; re-export for every deployment camera.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

MAX_LOGIT_DRIFT = 1e-3
MIN_AGREEMENT = 0.99
OUT_DIR = Path("models/onnx")


def committed_predictions(path: Path) -> dict[tuple[str, str, str], str]:
    with path.open(encoding="utf-8", newline="") as handle:
        return {(r["clip_id"], r["start_index"], r["lane"]): r["pred"]
                for r in csv.DictReader(handle)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--results", type=Path,
                        default=Path("experiments/results/loco_foreign"),
                        help="where the run's committed predictions live")
    parser.add_argument("--predictions", type=Path, default=None,
                        help="the run's predictions CSV, when it is not at "
                             "the standard name under --results")
    parser.add_argument("--source-id", default="corpus")
    parser.add_argument("--opset", type=int, default=18)
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)

    import dataclasses

    import numpy as np
    import onnxruntime
    import torch
    import yaml

    from experiments.provenance import write_sidecar
    from mfstnet.cache import FeatureCache
    from mfstnet.corpus.lanes import LaneCentres
    from mfstnet.model import MFSTNet, ablation_config
    from mfstnet.temporal import lane_masks_from_centres
    from scripts.export_onnx import build_wrapper
    from scripts.seed import set_seed
    from scripts.train_mfstnet import CLASSES, Windows, batches, load_corpus

    bundle = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    state, meta = bundle["state_dict"], bundle["meta"]
    name, seed, fold = meta["config"], meta["seed"], meta["fold"]
    print(f"  checkpoint {args.checkpoint}")
    print(f"    config {name}, seed {seed}, fold {fold}, domain {meta['domain']}, "
          f"{meta['mode']}")

    cache = FeatureCache(args.cache)
    if cache.spec.hash != meta["preprocessing_hash"]:
        raise SystemExit(
            f"the checkpoint was trained on preprocessing "
            f"{meta['preprocessing_hash']}; {args.cache} is {cache.spec.hash}. "
            f"Its windows are not the input this model was trained on.")

    rows, manifest = load_corpus(Path(meta["corpus"]))
    lanes = list(manifest["lanes"])
    if lanes != list(meta["lane_names"]):
        raise SystemExit(f"lane order differs: corpus {lanes}, checkpoint "
                         f"{meta['lane_names']}")
    test = [r for r in rows if r["split"] == "test"]
    spec = yaml.safe_load(Path("mfstnet/configs/spec.yaml")
                          .read_text(encoding="utf-8"))
    grid = spec.get("grid", 7)

    # One geometry is baked into the graph, so the test windows must share one.
    per_clip = manifest.get("lane_centres_by_clip") or {}
    geometries = set()
    for clip in {r["clip_id"] for r in test}:
        entry = per_clip[clip]
        geometries.add(tuple((e["name"], tuple(e["centre"]))
                             for e in entry["lanes"]) +
                       (float(entry.get("max_radius", 0.25)),))
    if len(geometries) != 1:
        raise SystemExit(f"the test camera's clips carry {len(geometries)} lane "
                         f"geometries; a graph bakes exactly one")
    entry = per_clip[test[0]["clip_id"]]
    masks = lane_masks_from_centres(
        LaneCentres(names=tuple(e["name"] for e in entry["lanes"]),
                    centres=tuple(tuple(e["centre"]) for e in entry["lanes"]),
                    max_radius=float(entry.get("max_radius", 0.25))), grid)

    config = dataclasses.replace(ablation_config(name), n_lanes=len(lanes))

    def build(weights: dict | None) -> torch.nn.Module:
        model = MFSTNet(config, masks)
        if weights is not None:
            result = model.load_state_dict(
                {k: v for k, v in weights.items() if not k.endswith("masks")},
                strict=False)
            extra = [k for k in result.missing_keys if not k.endswith("masks")]
            if extra or result.unexpected_keys:
                raise SystemExit(f"checkpoint does not fit config {name}: "
                                 f"missing {extra}, unexpected "
                                 f"{result.unexpected_keys}")
        return model.eval()

    trained = build(state)
    set_seed(seed)
    fresh = build(None)

    windows = Windows(test, cache, lanes, args.source_id, manifest["T"])
    inputs, logits_trained, logits_fresh = [], [], []
    with torch.no_grad():
        for cnn, vit, _, _ in batches(windows, 8, shuffle=False):
            cnn = None if cnn is None else cnn.float()
            vit = None if vit is None else vit.float()
            inputs.append((cnn, vit))
            for model, sink in ((trained, logits_trained), (fresh, logits_fresh)):
                out = model(cnn if config.fusion.use_cnn else None,
                            vit if config.fusion.use_vit else None)
                sink.append(out.logits)
    logits_trained = torch.cat(logits_trained)        # [N, L, C]
    logits_fresh = torch.cat(logits_fresh)

    # Check 2 and the control, against the committed per-window decisions.
    pattern = f"fold{fold}_seed{seed}_{name}_{name}.predictions.csv"
    predictions = args.predictions or args.results / pattern
    if not predictions.is_file():
        raise SystemExit(f"no committed predictions at {predictions}")
    committed = committed_predictions(predictions)

    def agreement(logits) -> float:
        hits = total = 0
        for i, row in enumerate(test):
            for j, lane in enumerate(lanes):
                key = (row["clip_id"], row["start_index"], lane)
                hits += CLASSES[int(logits[i, j].argmax())] == committed[key]
                total += 1
        return hits / total

    agree_trained = agreement(logits_trained)
    agree_fresh = agreement(logits_fresh)

    # Check 1: export, then run the graph over the same windows.
    wrapper = build_wrapper(trained, use_cnn=config.fusion.use_cnn,
                            use_vit=config.fusion.use_vit)
    names = (["cnn_maps"] if config.fusion.use_cnn else []) + \
            (["vit_maps"] if config.fusion.use_vit else [])
    first = tuple(t for t in inputs[0] if t is not None)
    with torch.no_grad():
        reference = wrapper(*first)
    outputs = ["logits"] + (["gate"] if len(reference) > 1 else [])

    args.out.mkdir(parents=True, exist_ok=True)
    graph = args.out / f"mfstnet_{meta['domain']}_{name}_seed{seed}_fold{fold}.onnx"
    torch.onnx.export(wrapper, first, str(graph), input_names=names,
                      output_names=outputs,
                      dynamic_axes={n: {0: "batch"} for n in names + outputs},
                      opset_version=args.opset, do_constant_folding=True)

    session = onnxruntime.InferenceSession(str(graph),
                                           providers=["CPUExecutionProvider"])
    onnx_logits = []
    for cnn, vit in inputs:
        feed = {}
        if config.fusion.use_cnn:
            feed["cnn_maps"] = cnn.numpy()
        if config.fusion.use_vit:
            feed["vit_maps"] = vit.numpy()
        onnx_logits.append(session.run(None, feed)[0])
    onnx_logits = np.concatenate(onnx_logits)
    drift = float(np.abs(onnx_logits - logits_trained.numpy()).max())
    same_argmax = float((onnx_logits.argmax(-1)
                         == logits_trained.numpy().argmax(-1)).mean())

    checks = {
        "onnx_vs_torch_max_abs_logit": drift,
        "onnx_vs_torch_argmax_agreement": same_argmax,
        "trained_vs_committed_agreement": agree_trained,
        "fresh_vs_committed_agreement": agree_fresh,
    }
    passed = (drift < MAX_LOGIT_DRIFT and same_argmax == 1.0
              and agree_trained >= MIN_AGREEMENT and agree_fresh < agree_trained)

    n = len(test) * len(lanes)
    print(f"\n  {len(test)} test windows x {len(lanes)} lanes = {n} decisions, "
          f"camera {meta['test_camera'][:40]}")
    print(f"    ONNX vs PyTorch     max |logit diff| {drift:.2e}   "
          f"argmax agreement {same_argmax:.4f}")
    print(f"    trained vs committed predictions   {agree_trained:.4f}")
    print(f"    fresh   vs committed predictions   {agree_fresh:.4f}   "
          f"(control)")

    write_sidecar(
        graph, device="cpu", checkpoint=str(args.checkpoint),
        checkpoint_sha256=hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
        config=name, seed=seed, fold=fold, domain=meta["domain"],
        baked_lane_geometry_from=meta["test_camera"], opset=args.opset,
        lane_names=lanes, timesteps=manifest["T"], step_s=manifest.get("step_s"),
        preprocessing_hash=meta["preprocessing_hash"],
        windows=len(test), decisions=n, passed=passed,
        graph_sha256=hashlib.sha256(graph.read_bytes()).hexdigest(), **checks)

    print(f"\n  {'PASS' if passed else 'FAIL'}  {graph}")
    if not passed:
        print("  The exported graph is not demonstrably the trained model. Do "
              "not deploy it.")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
