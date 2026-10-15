"""Shared facts for the synopsis report and the synopsis presentation.

The Department's guideline requires that "the project title, Project Team ID,
student names, roll numbers, and Project Mentor name must remain consistent
throughout the synopsis, presentation, and project records" (§1) and asks for
that consistency to be verified again before submission (§10). The only
mechanical way to honour that is for both documents to be rendered from one
set of constants, which is what this module is.

Every quantitative claim below is read from a committed CSV under
``experiments/results/`` at build time rather than typed in. Transcribing a
result into a document is the same defect NFR-09/NFR-10 forbid for paper
tables, and a synopsis is no more exempt than a paper is.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "experiments" / "results"
DATA = ROOT / "data"
ASSETS = ROOT / "docs" / "assets" / "gehu"

# ==========================================================================
#  Identity — the fields guideline §1 and §10 require to match everywhere
# ==========================================================================

#: The registered project title, as it appears on the cover, the Certificate
#: and the Candidate's Declaration. Recovered from a hand-edited copy of the
#: Phase-I progress report on 2026-10-14: the cover and the Certificate had been
#: changed to this and the Declaration had not, which is exactly the
#: inconsistency guideline §1 forbids and §10 makes a submission check. Setting
#: it once here is what makes all three places agree on the next build.
TITLE = ("CNN VIT BILSTM CROSS-ATTENTION BASED TRAFFIC MANAGEMENT SYSTEM")

#: The model inside the system, used in running prose. The project is the
#: system; MFSTNet is the network it is built around, so the two names are not
#: interchangeable and `TITLE_SHORT` is not an abbreviation of `TITLE`.
TITLE_SHORT = "MFSTNet"

#: Allotted by the Department, recovered from the hand-edited report on
#: 2026-10-14. §10 makes verifying it on every document a submission check,
#: which is now mechanical: all three documents read it from here.
TEAM_ID = "CSE27-293"

DEGREE = "BACHELOR OF TECHNOLOGY"
BRANCH = "COMPUTER SCIENCE & ENGINEERING"
SPECIALISATION = "Machine Learning & Artificial Intelligence"
DEPARTMENT = "Department of Computer Science and Engineering"
INSTITUTE = "Graphic Era Hill University"
PLACE = "Dehradun, Uttarakhand"
SUBMISSION_MONTH = "September-2026"

MENTOR_NAME = "Ms. Neha Pokhriyal"
MENTOR_DESIGNATION = "Assistant Professor"


@dataclass(frozen=True)
class Member:
    name: str
    roll: str
    section: str
    lead: bool = False

    @property
    def display(self) -> str:
        return f"{self.name} (Lead)" if self.lead else self.name


TEAM: tuple[Member, ...] = (
    Member("Divyansh Uniyal", "2318766", "ML2", lead=True),
    Member("Bhavya Gogia", "2318662", "C1"),
    Member("Km Shivani", "2318999", "ML2"),
    Member("Abhishek Negi", "2318178", "C1"),
)

AUTHORS = ", ".join(member.name for member in TEAM)


# ==========================================================================
#  Results, read from the committed CSVs
# ==========================================================================

def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def fmt(value: str | float, places: int = 4) -> str:
    return f"{float(value):.{places}f}"


def fmt_p(value: str | float, places: int = 4) -> str:
    """A p-value as prose, never as a literal zero.

    The benchmark CSV rounds, so a very small p arrives as ``0.0``. Printing
    "p = 0.0000" states something no test can conclude; the convention is a
    bound. The rest of the time the rounded value is reported as it stands.
    """
    p = float(value)
    floor = 10 ** -places
    if p < floor:
        return f"< {floor:.{places}f}"
    return f"= {p:.{places}f}"


@dataclass(frozen=True)
class Facts:
    """Everything either document quotes, resolved once from disk."""

    loco: dict[str, dict[str, str]]
    baselines: dict[str, dict[str, str]]
    gate: dict[str, str]
    control: dict[str, str]
    manifest: dict
    cameras: dict
    n_sequences: int

    # -- derived, so neither renderer computes its own version -----------
    @property
    def best_vision(self) -> tuple[str, float]:
        config = max(self.loco, key=lambda k: float(self.loco[k]["macro_f1_mean"]))
        return config, float(self.loco[config]["macro_f1_mean"])

    @property
    def best_counts(self) -> tuple[str, float]:
        model = max(self.baselines,
                    key=lambda k: float(self.baselines[k]["macro_f1_mean"]))
        return model, float(self.baselines[model]["macro_f1_mean"])

    @property
    def n_folds(self) -> int:
        return int(self.loco["G"]["n_folds"])

    @property
    def n_seeds(self) -> int:
        return int(self.loco["G"]["n_seeds"])

    def ci(self, config: str, metric: str = "macro_f1") -> str:
        row = self.loco[config]
        return (f"{fmt(row[f'{metric}_mean'])} "
                f"[{fmt(row[f'{metric}_lo'])}, {fmt(row[f'{metric}_hi'])}]")


#: The benchmark CSV holds every pairwise comparison in the regime, so the one
#: the documents quote has to be selected by name rather than by position. It
#: is the learned controller against the swept Webster baseline — the arm PRD
#: §14.3 nominates. `WEBSTER` is the ``method_b`` value; the learned arm is
#: whichever ``method_a`` names a PPO arm, and P52 is the reason that is
#: currently the forecast-free one.
WEBSTER = "webster"
PPO_ARMS = ("no-forecast", "surrogate", "mfstnet")

#: How the learned arm is described in prose. The CSV's own label carries the
#: regime and seed, which belong in provenance rather than in a slide heading.
CONTROL_ARM_LABEL = "PPO, forecast-free arm"


def select_control_row(rows: list[dict[str, str]]) -> dict[str, str]:
    """The learned-controller-versus-Webster row, chosen by name.

    Selecting the first row with a non-empty ``improvement_percent`` would
    silently return whichever comparison the writer happened to emit first,
    which is a different claim about a different pair of controllers. Raise
    rather than fall back: a document that quotes the wrong arm is worse than
    one that fails to build.
    """
    matches = [row for row in rows
               if row.get("method_b", "").strip() == WEBSTER
               and row.get("method_a", "").startswith(PPO_ARMS)
               and row.get("improvement_percent", "").strip()]
    if not matches:
        raise ValueError(
            "benchmark_stats.csv has no learned-arm-versus-Webster row; "
            f"expected method_b == {WEBSTER!r} and method_a starting with one "
            f"of {PPO_ARMS}. Run scripts/benchmark.py before building the "
            "synopsis.")
    if len(matches) > 1:
        raise ValueError(
            "benchmark_stats.csv has more than one learned-arm-versus-Webster "
            "row, so which result the synopsis quotes would be positional: "
            + ", ".join(row["method_a"] for row in matches))
    return matches[0]


def load_facts() -> Facts:
    loco = {row["config"]: row for row in read_csv(RESULTS / "loco_summary.csv")}
    baselines = {row["model"]: row
                 for row in read_csv(RESULTS / "baselines_summary.csv")}
    gate = read_csv(RESULTS / "gate_vs_probe.csv")[0]

    control_rows = read_csv(RESULTS / "benchmark_ppo" / "benchmark_stats.csv")
    control = select_control_row(control_rows)

    manifest = json.loads((DATA / "corpus" / "manifest.json").read_text("utf-8"))
    cameras = json.loads((DATA / "cameras.json").read_text("utf-8"))
    n_sequences = sum(1 for _ in read_csv(DATA / "corpus" / "sequences.csv"))

    return Facts(loco=loco, baselines=baselines, gate=gate, control=control,
                 manifest=manifest, cameras=cameras, n_sequences=n_sequences)


# ==========================================================================
#  Ablation configuration table — PRD §14.4 as amended by A22
# ==========================================================================

ABLATION_ROWS: tuple[tuple[str, str, str], ...] = (
    ("A", "CNN only", "ResNet-50 features alone; no ViT, no fusion."),
    ("B", "ViT only", "DINOv2 ViT-S/14 features alone; no CNN, no fusion."),
    ("C", "Concatenation", "Both backbones, channel concatenation instead of attention."),
    ("D", "One-way cross-attention", "CNN queries ViT only; the reverse path is disabled."),
    ("E", "Bidirectional, no gate", "Both directions, averaged rather than gated."),
    ("F", "Gated + temporal attention", "Adds temporal self-attention over the BiLSTM outputs."),
    ("G", "Full model", "Gated bidirectional fusion, temporal attention, attention pooling."),
    ("H", "Linear probe", "Frozen features, mean over time, linear classifier. The floor."),
)


# ==========================================================================
#  Static content shared by both renderers
# ==========================================================================

OBJECTIVES: tuple[tuple[str, str], ...] = (
    ("O1", "Assemble a licence-audited corpus of Indian and comparable "
           "unstructured-traffic camera footage, and fine-tune a YOLOv8s "
           "detector over eight vehicle classes that include the "
           "auto-rickshaw, e-rickshaw and cattle absent from COCO."),
    ("O2", "Derive per-lane congestion labels from detector counts using "
           "PCU-weighted occupancy with per-camera thresholds, so that a "
           "label means the same thing at a six-lane arterial and a "
           "two-lane approach."),
    ("O3", "Design MFSTNet: a gated bidirectional cross-attention fusion of "
           "frozen CNN and ViT features, followed by recurrent and "
           "attention-based temporal modelling, predicting per-lane "
           "congestion 60 s ahead."),
    ("O4", "Quantify the contribution of every architectural component "
           "through an eight-configuration ablation that includes a linear "
           "probe, evaluated leave-one-camera-out so that no reported score "
           "is a memorised camera."),
    ("O5", "Train a PPO signal controller on a SUMO intersection whose "
           "observation vector carries the forecast, and measure it against "
           "a swept, best-configuration Webster baseline over 30 paired "
           "seeds with a pre-registered disqualification rule."),
    ("O6", "Demonstrate an edge-to-server prototype in which no raw frame "
           "leaves the capture device, and in which both required fallback "
           "paths — forecast failure and network loss — are exercised."),
)

DELIVERABLES: tuple[tuple[str, str], ...] = (
    ("Curated dataset",
     "Part A curated from permissively licensed public sources plus Part B of "
     "1,500-3,000 annotated campus frames, with a per-camera provenance record."),
    ("Fine-tuned detector",
     "YOLOv8s weights over eight India-relevant classes, with the counting "
     "operating point calibrated against human-verified counts."),
    ("MFSTNet model",
     "Trained weights, an ONNX export for CPU inference, and the exposed gate "
     "value as a research artefact rather than an internal detail."),
    ("Ablation and evaluation results",
     "Per-run CSVs for all eight configurations across every fold and seed, "
     "with bootstrap confidence intervals generated by a committed script."),
    ("PPO controller",
     "A trained policy plus a 30-seed paired benchmark against Webster and "
     "fixed-time control across three demand regimes."),
    ("Working prototype",
     "Edge node, MQTT contract, FastAPI control server with safety clamping "
     "outside the transport layer, and a two-panel monitoring dashboard."),
    ("Reproducibility package",
     "Pinned requirements, fixed seeds, committed raw results and a public "
     "code release, so that every reported number can be regenerated."),
)

HARDWARE_ROWS: tuple[tuple[str, str, str], ...] = (
    ("Training workstation", "Laptop, 8-core x86-64 CPU, 16 GB RAM",
     "Feature caching, MFSTNet training, ablation sweeps."),
    ("GPU", "NVIDIA RTX 4050 Laptop, 6 GB VRAM, compute capability 8.9",
     "Frozen-backbone feature extraction and training; bf16/fp16 mixed precision."),
    ("Storage", "512 GB SSD, of which roughly 60 GB for video, cache and weights",
     "Source clips, the memory-mapped feature cache and model checkpoints."),
    ("Edge node", "Team laptop acting as the edge device (ADR-003)",
     "Detection, counting and the local fallback controller. Every latency "
     "figure states this host, because it is not a Jetson."),
    ("Camera", "Existing municipal or campus CCTV stream, 720p or better",
     "Frame source. Frames are processed in place and never transmitted."),
    ("Network", "Wi-Fi or Ethernet LAN; MQTT broker within 200 ms",
     "Carries counts, predictions and signal commands only."),
)

SOFTWARE_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Operating system and language",
     ("Windows 11 and Ubuntu 22.04 (both supported)",
      "Python 3.12+")),
    ("Deep learning",
     ("PyTorch 2.13.0 with CUDA 12.6", "torchvision 0.28.0",
      "timm 1.0.28 for the DINOv2 backbone", "Ultralytics YOLOv8 8.4.118")),
    ("Reinforcement learning and simulation",
     ("Stable-Baselines3 2.9.0", "Gymnasium 1.3.0",
      "Eclipse SUMO 1.27.1 with TraCI and sumolib")),
    ("Serving and deployment",
     ("ONNX 1.22.0 and ONNX Runtime 1.29.0", "FastAPI 0.141.1 with Pydantic 2.13.4",
      "Uvicorn 0.52.4", "Eclipse Mosquitto with Paho-MQTT")),
    ("Data, storage and analysis",
     ("SQLite (embedded; no separate database server)",
      "NumPy 2.5.2, pandas 3.0.5, SciPy 1.18.0",
      "scikit-learn 1.9.0, XGBoost 3.4.1", "OpenCV 5.0.0")),
    ("Interface",
     ("React 18 with Vite and Zustand", "Recharts and native WebSocket")),
    ("Engineering tooling",
     ("Git with Git LFS for model weights", "pytest 9.1.1 with GitHub Actions CI",
      "MLflow and TensorBoard for experiment tracking", "Docker Compose")),
)

REFERENCES: tuple[str, ...] = (
    'A. Vaswani et al., "Attention is all you need," in Proc. Adv. Neural Inf. '
    "Process. Syst. (NeurIPS), 2017, pp. 5998-6008.",

    'A. Dosovitskiy et al., "An image is worth 16x16 words: Transformers for '
    'image recognition at scale," in Proc. Int. Conf. Learn. Represent. (ICLR), 2021.',

    'M. Oquab et al., "DINOv2: Learning robust visual features without '
    'supervision," Trans. Mach. Learn. Res., 2024.',

    'K. He, X. Zhang, S. Ren, and J. Sun, "Deep residual learning for image '
    "recognition,\" in Proc. IEEE Conf. Comput. Vis. Pattern Recognit. (CVPR), "
    "2016, pp. 770-778.",

    'G. Jocher, A. Chaurasia, and J. Qiu, "Ultralytics YOLOv8," 2023. '
    "[Online]. Available: https://github.com/ultralytics/ultralytics",

    'G. Varma, A. Subramanian, A. Namboodiri, M. Chandraker, and C. V. Jawahar, '
    '"IDD: A dataset for exploring problems of autonomous navigation in '
    'unconstrained environments," in Proc. IEEE Winter Conf. Appl. Comput. Vis. '
    "(WACV), 2019, pp. 1743-1751.",

    'J. Schulman, F. Wolski, P. Dhariwal, A. Radford, and O. Klimov, "Proximal '
    'policy optimization algorithms," arXiv:1707.06347, 2017.',

    'A. Raffin, A. Hill, A. Gleave, A. Kanervisto, M. Ernestus, and N. Dormann, '
    '"Stable-Baselines3: Reliable reinforcement learning implementations," '
    "J. Mach. Learn. Res., vol. 22, no. 268, pp. 1-8, 2021.",

    'P. A. Lopez et al., "Microscopic traffic simulation using SUMO," in Proc. '
    "IEEE Int. Conf. Intell. Transp. Syst. (ITSC), 2018, pp. 2575-2582.",

    'F. V. Webster, "Traffic signal settings," Road Research Technical Paper '
    "No. 39, Road Research Laboratory, London, U.K., 1958.",

    "Indian Roads Congress, IRC:SP:41-1994, Guidelines for the Design of "
    "At-Grade Intersections in Rural and Urban Areas. New Delhi, India: IRC, 1994.",

    "Indo-HCM, Indian Highway Capacity Manual. New Delhi, India: CSIR-Central "
    "Road Research Institute, 2017.",

    'H. Wei, G. Zheng, V. Gayah, and Z. Li, "Recent advances in reinforcement '
    'learning for traffic signal control: A survey of models and evaluation," '
    "ACM SIGKDD Explorations Newsletter, vol. 22, no. 2, pp. 12-18, 2021.",

    'S. Hochreiter and J. Schmidhuber, "Long short-term memory," Neural '
    "Computation, vol. 9, no. 8, pp. 1735-1780, 1997.",

    'T. Chen and C. Guestrin, "XGBoost: A scalable tree boosting system," in '
    "Proc. ACM SIGKDD Int. Conf. Knowl. Discovery Data Mining, 2016, pp. 785-794.",

    'B. Efron and R. Tibshirani, An Introduction to the Bootstrap. New York, '
    "NY, USA: Chapman & Hall, 1993.",
)
