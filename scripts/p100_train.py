"""P100 — the 6 pre-registered runs: 2 hour folds × seeds 42 1 7, G unweighted.

    python scripts/p100_train.py

Exactly P99's validation-selected recipe, trained with whole hours withheld,
on train/val-only corpora under `--no-test`. Nothing is selected afterwards:
each fold's model is the average of its three seeds (PREREGISTRATION_P100).
A run counts as done only when its CSV, sidecar and checkpoint all exist.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

CACHE = Path("data/cache_p99")
RESULTS = Path("experiments/results/bellevue_pilot/p100")
MODELS = Path("models/mfstnet/p100")
CONFIG, WEIGHTING = "G", "none"
FOLDS = ("A", "B")
SEEDS = (42, 1, 7)


def paths(fold: str, seed: int) -> tuple[Path, Path]:
    # train_mfstnet names a checkpoint with the manifest's fold.
    return (RESULTS / f"fold{fold}" / f"seed{seed}_{CONFIG}.csv",
            MODELS / f"fold{fold}" / f"mfstnet_{CONFIG}_seed{seed}_fold{fold}.pt")


def done(fold: str, seed: int) -> bool:
    out, checkpoint = paths(fold, seed)
    return out.exists() and out.with_suffix(".provenance.json").exists() and checkpoint.exists()


def main() -> int:
    runs = [(f, s) for f in FOLDS for s in SEEDS]
    for position, (fold, seed) in enumerate(runs, 1):
        tag = f"[{position}/{len(runs)}] fold {fold} seed {seed}"
        if done(fold, seed):
            print(f"  {tag}: done")
            continue
        out, checkpoint = paths(fold, seed)
        if checkpoint.exists():
            checkpoint.unlink()
        out.parent.mkdir(parents=True, exist_ok=True)
        print(f"  {tag}: training", flush=True)
        subprocess.run([
            sys.executable, "scripts/train_mfstnet.py",
            "--corpus", f"data/corpus_p100_{fold}_trainval", "--cache", str(CACHE),
            "--config", CONFIG, "--seed", str(seed), "--class-weights", WEIGHTING,
            "--no-test", "--device", "auto", "--out", str(out), "--force",
            "--save-checkpoint", str(checkpoint.parent)], check=True)
    missing = [r for r in runs if not done(*r)]
    if missing:
        raise SystemExit(f"{len(missing)} run(s) incomplete: {missing}")
    print(f"\n  all {len(runs)} runs complete. Next: scripts/p100_eval.py test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
