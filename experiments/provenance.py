"""What the environment was when a result was written (P39).

Three defects in one day shared a shape: **a number whose meaning depended on a
fact the number did not carry.**

* [P32](../docs/00-planning/PRD-CHANGELOG.md) — the same config and seed gave
  `gate_mean` 0.53895 on CPU and 0.54268 on CUDA, and the results CSV did not
  say which ran.
* [P33](../docs/00-planning/PRD-CHANGELOG.md) — a CPU-built and a GPU-built
  feature cache carried the same `preprocessing_hash` and different values.
* [P38](../docs/00-planning/PRD-CHANGELOG.md) — PPO moved to the GPU the day
  the torch wheel changed, so a benchmark from before and one from after were
  measured on different devices, with neither CSV recording it.

Each was fixed where it happened. This closes the pattern: a result file gets a
sidecar naming the environment that produced it, so two results can be compared
by checking whether they are comparable at all.

**A sidecar, not new columns.** Existing result CSVs are committed graded
deliverables (NFR-09/10) and rewriting them to add columns would be transcribing
results rather than regenerating them — the exact thing NFR-09 forbids. A file
beside them costs nothing and breaks nothing.

    from experiments.provenance import write_sidecar
    write_sidecar(args.out)      # -> args.out.with_suffix(".provenance.json")

**What is deliberately not here.** No timestamp of convenience and no username:
the point is reproducibility, and a field that always differs between two runs
makes a diff useless for the question being asked.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from pathlib import Path

__all__ = ["environment", "write_sidecar", "sidecar_path"]


def _package_version(name: str) -> str | None:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version(name)
    except PackageNotFoundError:
        return None


def _git_commit() -> str | None:
    """The commit the code was at. `None` outside a repository, not an error."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10,
            cwd=Path(__file__).resolve().parent.parent,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None if result.returncode == 0 else None


def _torch_facts() -> dict:
    """Version, build and visible device.

    The **build** is separate from the version on purpose: `2.13.0+cpu` and
    `2.13.0+cu126` are the same version and cannot produce the same numbers.
    """
    try:
        import torch
    except ImportError:
        return {"torch": None}

    facts = {
        "torch": torch.__version__,
        "torch_build": torch.__version__.split("+")[1] if "+" in torch.__version__ else "default",
        "cuda_available": bool(torch.cuda.is_available()),
    }
    if torch.cuda.is_available():
        properties = torch.cuda.get_device_properties(0)
        facts["cuda_device"] = properties.name
        facts["cuda_capability"] = f"sm_{properties.major}{properties.minor}"
        # P33: TF32 silently changes convolution results by more than fp16
        # storage can hold, so it belongs in the record.
        facts["cudnn_tf32"] = bool(torch.backends.cudnn.allow_tf32)
        facts["matmul_tf32"] = bool(torch.backends.cuda.matmul.allow_tf32)
    return facts


def environment(**extra) -> dict:
    """The facts a result depends on and does not otherwise record.

    `extra` carries whatever the calling script knows and this cannot infer —
    the device it actually ran on, the corpus it read, the weights it used.
    """
    record = {
        "git_commit": _git_commit(),
        "python": platform.python_version(),
        "platform": platform.system(),
        **_torch_facts(),
    }
    for name in ("numpy", "ultralytics", "stable-baselines3", "gymnasium",
                 "eclipse-sumo", "scikit-learn", "scipy", "xgboost"):
        version = _package_version(name)
        if version is not None:
            record[name.replace("-", "_")] = version
    record.update(extra)
    return record


def sidecar_path(results_path: Path) -> Path:
    return Path(results_path).with_suffix(".provenance.json")


def write_sidecar(results_path: Path, **extra) -> Path:
    """Write the environment beside a result file, and return where it went."""
    path = sidecar_path(results_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(environment(**extra), indent=2) + "\n",
                    encoding="utf-8")
    return path


if __name__ == "__main__":
    json.dump(environment(), sys.stdout, indent=2)
    print()
