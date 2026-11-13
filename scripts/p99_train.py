"""P99 — the 20 pre-registered training runs, one per process, resumable.

    python scripts/p99_train.py

G and H × class weights {inverse, none} × seeds 42 1 7 13 21, each trained on
`data/corpus_p99_trainval` with `--no-test`: that corpus holds no test window,
so no run can score or select on test. One config per process, because a fresh
interpreter is what reliably returns a 6 GB card's memory (run_loco.py, P55).

A run counts as done only when its metrics CSV, its sidecar and its checkpoint
all exist, so an interrupted run is retrained from the start rather than half
counted (P97).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

CORPUS = Path("data/corpus_p99_trainval")
CACHE = Path("data/cache_p99")
RESULTS = Path("experiments/results/bellevue_pilot/p99")
MODELS = Path("models/mfstnet/p99")
CONFIGS = ("G", "H")
WEIGHTS = ("inverse", "none")
SEEDS = (42, 1, 7, 13, 21)


def paths(config: str, weighting: str, seed: int) -> tuple[Path, Path]:
    out = RESULTS / weighting / f"seed{seed}_{config}.csv"
    checkpoint = MODELS / weighting / f"mfstnet_{config}_seed{seed}.pt"
    return out, checkpoint


def done(config: str, weighting: str, seed: int) -> bool:
    out, checkpoint = paths(config, weighting, seed)
    sidecar = out.with_suffix(".provenance.json")
    return out.exists() and sidecar.exists() and checkpoint.exists()


def main() -> int:
    runs = [(c, w, s) for w in WEIGHTS for c in CONFIGS for s in SEEDS]
    for position, (config, weighting, seed) in enumerate(runs, 1):
        tag = f"[{position}/{len(runs)}] {config} {weighting} seed {seed}"
        if done(config, weighting, seed):
            print(f"  {tag}: done")
            continue
        out, checkpoint = paths(config, weighting, seed)
        if checkpoint.exists():          # a checkpoint without its record is not a run
            checkpoint.unlink()
        out.parent.mkdir(parents=True, exist_ok=True)
        print(f"  {tag}: training", flush=True)
        subprocess.run([
            sys.executable, "scripts/train_mfstnet.py",
            "--corpus", str(CORPUS), "--cache", str(CACHE), "--config", config,
            "--seed", str(seed), "--class-weights", weighting, "--no-test",
            "--device", "auto", "--out", str(out), "--force",
            "--save-checkpoint", str(checkpoint.parent)], check=True)
    missing = [r for r in runs if not done(*r)]
    if missing:
        raise SystemExit(f"{len(missing)} run(s) incomplete: {missing}")
    print(f"\n  all {len(runs)} runs complete. Next: scripts/p99_eval.py select")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
