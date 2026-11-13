"""V1-2 — the inter-rater gate: do two blind labellers agree enough to freeze the protocol?

    python scripts/v1_pilot_agreement.py --a data/v1/v1_pilot_<A>.json --b data/v1/v1_pilot_<B>.json

**Fixed before any pilot label exists.** The plan and P135 set these:

- **The measure, ICC(2,1):** two-way random effects, absolute agreement,
  single rater (Shrout and Fleiss). It is computed on the per-frame counts of
  all pilot frames both labellers counted.
- **The gate:** ICC(2,1) ≥ **0.80**.
- **On failure:**
  - the counting instructions are revised **once**, and the pilot is repeated
    with `--attempt 2`;
  - a second failure stops V1 for the owner's decision;
  - there is no third attempt.
- **Unusable frames (-1):** excluded pairwise. The share is reported, and
  above 5% it is flagged.
- **Reported, not gating:**
  - Cohen's κ on each moment's class (the mean of its 15 frames, under P105's
    per-camera thresholds);
  - the mean absolute difference;
  - the mean signed difference (A − B);
  - the ICC per camera.

**The counts are human labels of licence-unresolved footage.** They stay in
`data/v1/`, which is gitignored. Only the agreement statistics are written to
`experiments/results/v1/`.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

KEY = Path("data/v1/v1_pilot_key.json")
OUT = Path("experiments/results/v1")
ICC_MIN, UNUSABLE_FLAG = 0.80, 0.05


def icc_2_1(rows: list[tuple[float, ...]]) -> float:
    """ICC(2,1), absolute agreement, two-way random, single rater (Shrout and Fleiss 1979)."""
    n, k = len(rows), len(rows[0])
    if n < 2 or k < 2:
        raise ValueError("ICC needs at least two subjects and two raters")
    grand = statistics.fmean(v for r in rows for v in r)
    row_means = [statistics.fmean(r) for r in rows]
    col_means = [statistics.fmean(r[j] for r in rows) for j in range(k)]
    ssr = k * sum((m - grand) ** 2 for m in row_means)
    ssc = n * sum((m - grand) ** 2 for m in col_means)
    sst = sum((v - grand) ** 2 for r in rows for v in r)
    sse = sst - ssr - ssc
    msr, msc, mse = ssr / (n - 1), ssc / (k - 1), sse / ((n - 1) * (k - 1))
    denominator = msr + (k - 1) * mse + k * (msc - mse) / n
    return (msr - mse) / denominator if denominator else 1.0


def cohen_kappa(a: list[int], b: list[int]) -> float:
    labels = sorted(set(a) | set(b))
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b)) / n
    expected = sum((a.count(c) / n) * (b.count(c) / n) for c in labels)
    return (observed - expected) / (1 - expected) if expected < 1 else 1.0


def agreement(key_items: list[dict], counts_a: dict, counts_b: dict,
              thresholds: dict) -> dict:
    from scripts.v1_target_fidelity import level

    pairs, unusable, per_camera, moments = [], 0, {}, {}
    for item in key_items:
        a, b = counts_a.get(item["id"]), counts_b.get(item["id"])
        if a is None or b is None:
            raise ValueError(f"item {item['id']} is missing from a labeller's export")
        if a < 0 or b < 0:
            unusable += 1
            continue
        pairs.append((float(a), float(b)))
        camera = item["clip"].split("__")[0].removeprefix("Bellevue_")
        per_camera.setdefault(camera, []).append((float(a), float(b)))
        moments.setdefault(item["moment"], {"camera": camera, "a": [], "b": []})
        moments[item["moment"]]["a"].append(a)
        moments[item["moment"]]["b"].append(b)
    icc = icc_2_1(pairs)
    cls_a, cls_b = [], []
    for m in moments.values():
        q = thresholds[m["camera"]]
        cls_a.append(level(statistics.fmean(m["a"]), q["q33"], q["q67"]))
        cls_b.append(level(statistics.fmean(m["b"]), q["q33"], q["q67"]))
    share = unusable / len(key_items)
    return {"frames": len(key_items), "frames_scored": len(pairs), "unusable": unusable,
            "unusable_share": round(share, 4), "unusable_flagged": share > UNUSABLE_FLAG,
            "icc_2_1": round(icc, 4), "gate": ICC_MIN, "passed": icc >= ICC_MIN,
            "kappa_moment_class": round(cohen_kappa(cls_a, cls_b), 4),
            "mean_abs_diff": round(statistics.fmean(abs(a - b) for a, b in pairs), 4),
            "mean_signed_diff_a_minus_b": round(statistics.fmean(a - b for a, b in pairs), 4),
            "icc_per_camera": {c: round(icc_2_1(p), 4) for c, p in per_camera.items() if len(p) >= 2}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--a", type=Path, required=True)
    parser.add_argument("--b", type=Path, required=True)
    parser.add_argument("--attempt", type=int, choices=(1, 2), default=1)
    args = parser.parse_args(argv)
    out = OUT / f"v1_pilot_agreement_attempt{args.attempt}.json"
    if out.exists():
        raise SystemExit(f"{out} exists: each pilot attempt is scored once")
    if args.attempt == 2 and not (OUT / "v1_pilot_agreement_attempt1.json").exists():
        raise SystemExit("attempt 2 only follows a scored attempt 1")
    a, b = (json.loads(p.read_text(encoding="utf-8")) for p in (args.a, args.b))
    if a["labeller"] == b["labeller"]:
        raise SystemExit("the two exports name the same labeller")
    thresholds = json.loads(Path("experiments/results/bellevue_pilot/p105_thresholds.json")
                            .read_text(encoding="utf-8"))["cameras"]
    items = json.loads(KEY.read_text(encoding="utf-8"))["items"]
    result = agreement(items, a["counts"], b["counts"], thresholds)
    result.update({"attempt": args.attempt, "labellers": 2,
                   "next": ("freeze the instructions and the V1 protocol" if result["passed"] else
                            "revise the instructions once and re-pilot (attempt 2)"
                            if args.attempt == 1 else "stop: V1 goes to the owner")})
    OUT.mkdir(parents=True, exist_ok=True)
    out.write_bytes((json.dumps(result, indent=2) + "\n").encode("utf-8"))
    print(f"  ICC(2,1) {result['icc_2_1']} (gate {ICC_MIN}): "
          f"{'PASS' if result['passed'] else 'FAIL'}; kappa {result['kappa_moment_class']}; "
          f"unusable {result['unusable_share']:.1%} -> {result['next']}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
