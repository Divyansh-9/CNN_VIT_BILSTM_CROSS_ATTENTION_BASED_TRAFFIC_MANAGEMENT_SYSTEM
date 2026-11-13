"""Audit every fold-eligible camera, and measure what each contributes.

Authorised as the next work package after ADR-024 withdrew the graded
lane-discipline sweep. It answers three questions from committed data, with no
training run:

1. **What is each camera?** Location, viewpoint, traffic type, how that was
   determined, licence, window count, and its congestion-label distribution.
2. **What does each contribute to the evaluation?** Share of windows, share of
   HIGH labels, and which leave-one-camera-out fold holds it out.
3. **What happens to the headline if one is excluded?** Recomputed from
   `loco_summary.csv`'s per-fold scores, so the ablation costs nothing and
   cannot disagree with the committed results.

    python scripts/camera_audit.py

**This is not a licence to drop a camera that scores badly.** PRD §2.5.5
forbids quietly dropping an inconvenient result, and a mean computed over the
folds that flatter a model is the definition of cherry-picking. The exclusion
column exists so that the *composition* of the headline is visible — a mean
over three in-regime cameras and one declared out-of-regime one is not a
generalisation estimate, it is a blend of two different quantities, and a
reader is entitled to see both.

`data/cameras.json` declares `target_domain`, so in-regime and out-of-regime
are read from the record rather than decided here.
"""

from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "data" / "corpus"
LOCO = ROOT / "data" / "corpus_loco"
SUMMARY = ROOT / "experiments" / "results" / "loco_summary.csv"
CAMERAS = ROOT / "data" / "cameras.json"

LABELS = ("LOW", "MEDIUM", "HIGH")

#: A source is accepted into the corpus only when every one of these is
#: recorded. Written down here because "we will check" is not a gate, and
#: because the project already has one camera (`video1`) whose every property
#: is unknown.
COLLECTION_GATE = (
    ("provenance", "where the footage came from, and the uploader"),
    ("licence", "resolved and permissive enough to redistribute derived data"),
    ("viewpoint", "fixed and elevated, confirmed by looking at a frame"),
    ("country / traffic type", "declared, and determined_by = frame"),
    ("usable duration", "continuous enough for at least 10 windows, so the "
                        "camera can be a fold under ADR-019"),
    ("label distribution", "contains at least one HIGH window, or is declared "
                           "as a camera that cannot score the HIGH class"),
)


def load_cameras() -> dict:
    payload = json.loads(CAMERAS.read_text(encoding="utf-8"))
    return payload.get("cameras", payload), payload.get("target_domain", {})


def fold_of_camera() -> dict[str, int]:
    """Which leave-one-camera-out fold holds each camera out."""
    mapping: dict[str, int] = {}
    for directory in sorted(LOCO.glob("fold*")):
        path = directory / "sequences.csv"
        if not path.is_file():
            continue
        with path.open(encoding="utf-8", newline="") as handle:
            held = {row["clip_id"] for row in csv.DictReader(handle)
                    if row["split"] == "test"}
        for clip in held:
            mapping[clip] = int(directory.name.removeprefix("fold"))
    return mapping


def label_counts() -> dict[str, Counter]:
    with (CORPUS / "sequences.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    counts: dict[str, Counter] = {}
    lane_columns = [c for c in rows[0] if c.startswith("label_lane_")]
    for row in rows:
        bucket = counts.setdefault(row["clip_id"], Counter())
        bucket["windows"] += 1
        for column in lane_columns:
            value = row[column]
            if value in LABELS:
                bucket[value] += 1
            elif value.isdigit():
                bucket[LABELS[int(value)]] += 1
    return counts


def per_fold_scores() -> dict[str, dict[int, float]]:
    with SUMMARY.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    out = {}
    for row in rows:
        out[row["config"]] = {
            int(part.split(":")[0]): float(part.split(":")[1])
            for part in row["macro_f1_per_fold"].split()}
    return out


def main() -> int:
    cameras, target = load_cameras()
    folds = fold_of_camera()
    counts = label_counts()
    total_windows = sum(c["windows"] for c in counts.values())
    total_high = sum(c[LABELS[2]] for c in counts.values())

    print(f"\n  target domain declared in data/cameras.json: "
          f"{target.get('country', ['?'])} · "
          f"{target.get('traffic_type', ['?'])} · "
          f"{target.get('viewpoint', ['?'])}\n")

    print(f"  {'camera':<34} {'fold':>4} {'win':>5} {'%win':>6} "
          f"{'HIGH':>5} {'%HIGH':>6}  {'country':<11} {'by':<9} licence")
    rows_out = []
    for clip, bucket in sorted(counts.items(), key=lambda kv: -kv[1]["windows"]):
        declared = cameras.get(clip, {})
        fold = folds.get(clip)
        high = bucket[LABELS[2]]
        rows_out.append((clip, fold, bucket["windows"], high, declared))
        print(f"  {clip[:33]:<34} "
              f"{('-' if fold is None else fold):>4} "
              f"{bucket['windows']:>5} "
              f"{bucket['windows'] / total_windows:>6.1%} "
              f"{high:>5} "
              f"{(high / total_high if total_high else 0):>6.1%}  "
              f"{str(declared.get('country', '?'))[:10]:<11} "
              f"{str(declared.get('determined_by', '?'))[:8]:<9} "
              f"{str(declared.get('licence', '?'))[:28]}")

    # Split on traffic TYPE, not country. Every fold-eligible camera is
    # out-of-country — three Bangladeshi and one British — which is precisely
    # why the `domain` claim is red, and splitting on country would leave no
    # folds on either side. The scientifically meaningful axis is the traffic
    # regime the project is about: `mixed` is the non-lane-disciplined,
    # heterogeneous stream this targets, and `structured` is its counterexample.
    out_of_regime = [
        (clip, fold) for clip, fold, _w, _h, declared in rows_out
        if fold is not None
        and declared.get("traffic_type") not in target.get("traffic_type", [])]

    off_country = [
        clip for clip, fold, _w, _h, declared in rows_out
        if fold is not None
        and declared.get("country") not in target.get("country", [])]
    if off_country:
        eligible = len([r for r in rows_out if r[1] is not None])
        print(f"\n  NOTE  {len(off_country)} of {eligible} fold-eligible "
              f"cameras are outside the declared country.")
        print("        That is the `domain` claim in CLAIMS.yaml, and it is "
              "red for exactly this reason.")

    print(f"\n  fold-eligible cameras: {len([r for r in rows_out if r[1] is not None])}"
          f" — the effective sample size under ADR-019, and what more hours "
          f"from\n  the same cameras does NOT increase.")

    if not out_of_regime:
        print("\n  Every fold-eligible camera matches the declared target "
              "domain.")
        return 0

    scores = per_fold_scores()
    print(f"\n  Out-of-regime by the declared target domain: "
          + ", ".join(f"{c[:28]} (fold {f})" for c, f in out_of_regime))
    excluded = {fold for _clip, fold in out_of_regime}

    print(f"\n  macro-F1 with and without those folds, from the committed "
          f"per-fold scores:\n")
    print(f"    {'cfg':>4} {'all folds':>10} {'in-regime':>10} {'delta':>8}")
    deltas = {}
    for config, folds_scores in sorted(scores.items()):
        every = statistics.mean(folds_scores.values())
        inside = statistics.mean([v for k, v in folds_scores.items()
                                  if k not in excluded])
        deltas[config] = (every, inside)
        print(f"    {config:>4} {every:>10.4f} {inside:>10.4f} "
              f"{inside - every:>+8.4f}")

    if "G" in deltas and "H" in deltas:
        g, h = deltas["G"], deltas["H"]
        print(f"\n  ADR-022's pre-registered comparison, both ways:")
        print(f"    all folds   full model G {g[0]:.4f}  linear probe H "
              f"{h[0]:.4f}   G-H {g[0] - h[0]:+.4f}")
        print(f"    in-regime   full model G {g[1]:.4f}  linear probe H "
              f"{h[1]:.4f}   G-H {g[1] - h[1]:+.4f}")
        if (g[0] - h[0]) * (g[1] - h[1]) < 0:
            print("\n    The SIGN FLIPS. Which cameras are in the mean decides "
                  "whether the\n    full model or the linear probe wins, so "
                  "neither number may be quoted\n    without stating its fold "
                  "composition.")

    print(f"\n  Collection gate — a new source is accepted only when all of "
          f"these are recorded:")
    for name, requirement in COLLECTION_GATE:
        print(f"    {name:<24} {requirement}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
