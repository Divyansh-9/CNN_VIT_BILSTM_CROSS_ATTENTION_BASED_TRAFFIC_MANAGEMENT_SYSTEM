"""A result must carry the facts its meaning depends on (P39).

Three defects in one session shared a shape — a number whose meaning depended
on something the number did not record:

* P32: the same config and seed gave gate_mean 0.53895 on CPU and 0.54268 on
  CUDA, and the CSV did not say which ran.
* P33: a CPU-built and a GPU-built feature cache carried the same
  preprocessing_hash and different values.
* P38: PPO moved to the GPU the day the torch wheel changed, so a benchmark
  from before and one from after were measured on different devices.

Each was fixed where it happened. The sidecar closes the pattern.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from experiments.provenance import environment, sidecar_path, write_sidecar

ROOT = Path(__file__).resolve().parent.parent


def test_the_environment_names_the_torch_build_not_only_the_version():
    """`2.13.0+cpu` and `2.13.0+cu126` are the same version and cannot produce
    the same numbers. P32 is exactly that distinction going unrecorded."""
    record = environment()
    if record.get("torch") is None:
        pytest.skip("torch not installed")
    assert "torch_build" in record
    assert record["torch_build"] in record["torch"] or record["torch_build"] == "default"


def test_tf32_is_recorded_when_a_gpu_is_present():
    """P33: TF32 changes convolution results by more than fp16 storage holds,
    so a cache built with it on is different data."""
    record = environment()
    if not record.get("cuda_available"):
        pytest.skip("no CUDA device here")
    assert "cudnn_tf32" in record
    assert "matmul_tf32" in record


def test_the_sidecar_sits_beside_the_result_and_does_not_replace_it(tmp_path):
    """Existing result CSVs are committed graded deliverables. Adding columns
    would mean rewriting them, which NFR-09 forbids."""
    results = tmp_path / "ablation.csv"
    results.write_text("config,macro_f1\nG,0.71\n", encoding="utf-8")

    written = write_sidecar(results, device="cuda")

    assert written == sidecar_path(results) == tmp_path / "ablation.provenance.json"
    assert results.read_text(encoding="utf-8") == "config,macro_f1\nG,0.71\n"


def test_extra_facts_from_the_caller_are_kept(tmp_path):
    written = write_sidecar(tmp_path / "r.csv", device="cpu", corpus="data/corpus")
    record = json.loads(written.read_text(encoding="utf-8"))
    assert record["device"] == "cpu"
    assert record["corpus"] == "data/corpus"


def test_the_record_carries_no_field_that_always_differs(tmp_path):
    """A timestamp or a username makes a diff between two runs useless for the
    question it is being asked — whether the two are comparable."""
    first = json.loads(write_sidecar(tmp_path / "a.csv").read_text(encoding="utf-8"))
    second = json.loads(write_sidecar(tmp_path / "b.csv").read_text(encoding="utf-8"))
    assert first == second


def test_the_record_is_json_serialisable():
    """It is written with json.dumps, so a stray Path or torch dtype would
    fail at the end of a long run rather than at the start."""
    json.dumps(environment())


@pytest.mark.parametrize("script,writes", [
    ("train_mfstnet.py", "the ablation table (NFR-09/10)"),
    ("train_baselines.py", "the count-sequence baselines"),
    ("benchmark.py", "the 30-seed RL comparison"),
    ("webster_sweep.py", "the ADR-012 saturation sweep"),
])
def test_every_graded_result_writer_writes_a_sidecar(script, writes):
    source = (ROOT / "scripts" / script).read_text(encoding="utf-8")
    assert "write_sidecar" in source, (
        f"{script} writes {writes} and must record the environment beside it"
    )
