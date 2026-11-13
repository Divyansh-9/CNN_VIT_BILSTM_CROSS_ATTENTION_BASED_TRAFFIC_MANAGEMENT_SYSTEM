"""MFSTNet on the edge: frames in, a `CongestionPrediction` out (ADR-026).

**Why here and not on the server.** MFSTNet's inputs are ResNet-50 and DINOv2
feature maps computed from frames, and NFR-13 lets only counts and predictions
leave the edge. So the model runs where the frames are, and the server receives
its output on `stms/{id}/congestion/prediction` like any other payload.

**Only a verified graph is served.** `export_checkpoint.py` proves a graph is
the trained model by reproducing that run's committed predictions on its own
held-out camera, and records the result in a sidecar. This module refuses a
graph whose sidecar does not say it passed, and refuses one whose bytes no
longer hash to what was verified. An untrained export runs just as cleanly as
a trained one (P87); the sidecar is the only thing that tells them apart.

**Streaming, not batch.** A window is T frames at `step_s` apart. Recomputing
both backbones over all T frames for every prediction is what the deployed
latency figure in `export_onnx.py` charges, and it is the cold-start cost only.
In steady state each step adds ONE frame: two backbone passes, then the head
over a ring of the last T feature frames. That is the number the edge budget is
about.

**The input is the cache's input, exactly.** Frames go through
`mfstnet.preprocess.preprocess_frame` — the function the cache builder uses —
and features are rounded through fp16 before the head, because the cache stored
fp16 and the model never saw anything else (P35, P88).
"""

from __future__ import annotations

import hashlib
import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from contracts.mqtt import CongestionClass, CongestionPrediction

__all__ = ["DeploymentError", "VerifiedGraph", "EdgeForecaster"]

CLASSES = (CongestionClass.LOW, CongestionClass.MEDIUM, CongestionClass.HIGH)
APPROACHES = ("N", "S", "E", "W")


class DeploymentError(RuntimeError):
    """A graph or a mapping that must not be served."""


@dataclass(frozen=True)
class VerifiedGraph:
    """An exported graph plus the record that proves it is the trained model."""

    path: Path
    sidecar: dict

    @classmethod
    def load(cls, path: Path) -> "VerifiedGraph":
        path = Path(path)
        record = path.with_suffix(".provenance.json")
        if not record.is_file():
            raise DeploymentError(
                f"{path} has no provenance sidecar. Export it with "
                f"scripts/export_checkpoint.py, which verifies it first.")
        sidecar = json.loads(record.read_text(encoding="utf-8"))
        if sidecar.get("passed") is not True:
            raise DeploymentError(
                f"{path} did not pass verification against its committed "
                f"predictions; it is not demonstrably the trained model.")
        recorded = sidecar.get("files_sha256")
        if not recorded:
            raise DeploymentError(
                f"{path}'s sidecar records no per-file hashes. Its weights may "
                f"sit in an external .onnx.data file that was never covered "
                f"(P90); re-export it with scripts/export_checkpoint.py.")
        from mfstnet.onnx_files import file_hashes

        # The graph's own bytes first, before anything parses them: a
        # replaced graph is reported as replaced, not as a parser crash.
        graph_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if graph_digest != recorded.get(path.name):
            raise DeploymentError(
                f"{path.name} hashes to {graph_digest[:12]}, not the "
                f"{str(recorded.get(path.name))[:12]} that was verified. The "
                f"file was replaced after verification.")
        try:
            actual = file_hashes(path)
        except FileNotFoundError as error:
            raise DeploymentError(
                f"{path} references a file that is missing: {error}") from error
        except Exception as error:     # any parse failure is a refusal
            raise DeploymentError(f"{path} cannot be read as ONNX: "
                                  f"{type(error).__name__}") from error
        if set(actual) != set(recorded):
            raise DeploymentError(
                f"{path} consists of {sorted(actual)} but "
                f"{sorted(recorded)} were verified")
        for name, digest in actual.items():
            if digest != recorded[name]:
                raise DeploymentError(
                    f"{name} hashes to {digest[:12]}, not the "
                    f"{recorded[name][:12]} that was verified. The file was "
                    f"replaced after verification.")
        return cls(path=path, sidecar=sidecar)

    @property
    def model_id(self) -> str:
        """`config@graph-hash`, short enough for the payload and unambiguous."""
        return f"{self.sidecar['config']}@{self.sidecar['graph_sha256'][:12]}"


class EdgeForecaster:
    """One camera's forecaster. `step(frame)` once per `step_s`."""

    def __init__(self, graph: VerifiedGraph, lane_to_approach: dict[str, str],
                 *, timesteps: int, device: str = "cpu",
                 image_size: int = 224) -> None:
        import onnxruntime
        import torch

        from mfstnet.encoders import CNNBranch, EncoderConfig, ViTBranch

        lanes = list(graph.sidecar["lane_names"])
        if set(lane_to_approach) != set(lanes):
            raise DeploymentError(
                f"lane_to_approach covers {sorted(lane_to_approach)}, the graph "
                f"predicts {lanes}. Every lane needs an approach (PPO indices "
                f"11-14 are N, S, E, W), and none may be guessed.")
        bad = set(lane_to_approach.values()) - set(APPROACHES)
        if bad or len(set(lane_to_approach.values())) != len(lanes):
            raise DeploymentError(
                f"lane_to_approach must map each lane to a distinct one of "
                f"{APPROACHES}; got {lane_to_approach}")

        self.graph, self.lanes = graph, lanes
        self.lane_to_approach = dict(lane_to_approach)
        self.timesteps, self.device, self.image_size = timesteps, device, image_size
        self.session = onnxruntime.InferenceSession(
            str(graph.path), providers=["CPUExecutionProvider"])
        self.inputs = [i.name for i in self.session.get_inputs()]
        self.outputs = [o.name for o in self.session.get_outputs()]

        encoder = EncoderConfig()
        self.cnn = (CNNBranch(encoder).to(device).eval()
                    if "cnn_maps" in self.inputs else None)
        self.vit = (ViTBranch(encoder).to(device).eval()
                    if "vit_maps" in self.inputs else None)
        self.rings = {name: deque(maxlen=timesteps) for name in self.inputs}
        self._torch = torch

    @property
    def ready(self) -> bool:
        return all(len(r) == self.timesteps for r in self.rings.values())

    def features(self, frame_bgr) -> dict:
        """Both backbones over one frame, rounded through fp16 as cached."""
        from mfstnet.preprocess import preprocess_frame

        torch = self._torch
        image = preprocess_frame(frame_bgr, self.image_size).unsqueeze(0)
        out = {}
        with torch.no_grad():
            image = image.to(self.device)
            for name, branch in (("cnn_maps", self.cnn), ("vit_maps", self.vit)):
                if branch is not None:
                    out[name] = (branch(image).to(torch.float16)
                                 .to(torch.float32).cpu().numpy()[0])
        return out

    def push(self, features: dict) -> None:
        for name, value in features.items():
            self.rings[name].append(value)

    def predict(self) -> CongestionPrediction:
        import numpy as np

        if not self.ready:
            raise DeploymentError(
                f"{min(len(r) for r in self.rings.values())} of "
                f"{self.timesteps} frames buffered; a shorter window would put "
                f"the label at the wrong horizon (A15)")
        feed = {name: np.stack(self.rings[name])[None] for name in self.inputs}
        results = dict(zip(self.outputs, self.session.run(None, feed)))
        logits = results["logits"][0]                       # [L, C]
        exp = np.exp(logits - logits.max(-1, keepdims=True))
        probs = exp / exp.sum(-1, keepdims=True)
        predictions, confidences = {}, {}
        for i, lane in enumerate(self.lanes):
            approach = self.lane_to_approach[lane]
            predictions[approach] = CLASSES[int(probs[i].argmax())]
            confidences[approach] = round(float(probs[i].max()), 4)
        # A config without a gate (A, B, H) sends None, not a neutral 0.5:
        # contract v2 lets the dashboard tell an absent gate from a real one.
        gate = (round(float(np.clip(results["gate"].mean(), 0.0, 1.0)), 4)
                if "gate" in results else None)
        return CongestionPrediction(
            predictions=predictions, confidences=confidences,
            gate_value=gate, model=self.graph.model_id)

    def step(self, frame_bgr) -> CongestionPrediction | None:
        """Add one frame; return a prediction once a full window is buffered."""
        self.push(self.features(frame_bgr))
        return self.predict() if self.ready else None
