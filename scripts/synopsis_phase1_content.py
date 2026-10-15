"""Content for the **Phase I** synopsis — the proposal written at inception.

There are two synopsis documents in this series and they are deliberately
different documents, not two renderings of one:

* ``scripts/build_synopsis_docx.py`` renders the **progress** synopsis. It
  reads every number it quotes from a committed CSV under
  ``experiments/results/`` and reports what the pipeline has measured.
* ``scripts/build_synopsis_phase1_docx.py`` renders the **Phase I proposal**.
  It reports what the team decided to build and why, at the point the idea was
  fixed and the work started. It therefore contains **no measured results at
  all** — every number in it is a specification, a budget or a target taken
  from the PRD, and is written as such.

That separation is the whole reason this module does not import
``load_facts()``. A proposal that quotes a result it did not yet have is a
false document, and the cheapest way to guarantee it never happens is for the
proposal renderer to have no access to the results.

Identity — title, team, roll numbers, mentor, Team ID — is imported from
``scripts/synopsis_content.py`` and never restated here, because guideline §1
requires those fields to be identical across every document in the series and
§10 makes verifying that a submission check.
"""

from __future__ import annotations

from scripts.synopsis_content import (ABLATION_ROWS, ASSETS, AUTHORS, BRANCH,
                                      DEGREE, DEPARTMENT, INSTITUTE,
                                      MENTOR_DESIGNATION, MENTOR_NAME, PLACE,
                                      ROOT, SPECIALISATION, TEAM, TEAM_ID,
                                      TITLE, TITLE_SHORT, Member)

__all__ = [
    "ABLATION_ROWS", "ASSETS", "AUTHORS", "BRANCH", "DEGREE", "DEPARTMENT",
    "INSTITUTE", "MENTOR_DESIGNATION", "MENTOR_NAME", "PLACE", "ROOT",
    "SPECIALISATION", "TEAM", "TEAM_ID", "TITLE", "TITLE_SHORT", "Member",
    "SUBTITLE", "SUBMISSION_MONTH", "WORKING_NAME", "TOC_ENTRIES",
    "IDEA_CANDIDATES", "DESIGN_CHOICES", "LITERATURE_STRANDS", "OBJECTIVES",
    "RESEARCH_QUESTIONS", "IN_SCOPE", "OUT_OF_SCOPE", "PHASE_PLAN",
    "MILESTONES", "RISKS", "PERFORMANCE_MEASURES", "TARGETS", "DELIVERABLES",
    "FUTURE_SCOPE", "HARDWARE_ROWS", "SOFTWARE_GROUPS", "REFERENCES",
]

# ==========================================================================
#  Phase I identity
# ==========================================================================

SUBTITLE = "Phase I  —  Project Proposal"

#: The repository was opened on 2026-08-07 and the twenty-week schedule starts
#: from that week, so the proposal carries the month the work began rather
#: than the month the progress synopsis carries.
SUBMISSION_MONTH = "August-2026"

#: The name the idea was registered under before the model had one. It is
#: recorded because §1's consistency rule is easier to satisfy when the earlier
#: name is written down once rather than remembered differently by four people.
WORKING_NAME = "cnn-vit-bilstm-cross-attention-traffic-system"

TOC_ENTRIES: list[tuple[str, str, str]] = [
    ("", "Abstract", "abstract"),
    ("1", "Introduction", "ch1"),
    ("2", "Literature Review", "ch2"),
    ("3", "Problem Statement & Objectives", "ch3"),
    ("4", "Proposed Methodology", "ch4"),
    ("5", "Hardware and Software Requirements", "ch5"),
    ("6", "Expected Outcomes", "ch6"),
    ("7", "Conclusion", "ch7"),
    ("", "References", "references"),
]


# ==========================================================================
#  Chapter 1 — how the idea was chosen
# ==========================================================================

#: The shortlist the team scored before fixing on one idea. Recorded because a
#: proposal that presents its chosen idea as the only idea gives the reader no
#: way to judge the choice.
IDEA_CANDIDATES: tuple[tuple[str, str, str], ...] = (
    ("Helmet and traffic-violation detection from CCTV",
     "Detection only; a solved problem with several public baselines.",
     "Rejected — no forecasting or control component, so the project would "
     "end at a detector and have nothing to ablate."),
    ("Vehicle re-identification across junctions",
     "Needs synchronised multi-camera footage with overlapping fields of view.",
     "Rejected — the footage the team can obtain is single-view and "
     "unsynchronised, so the core assumption fails before any modelling."),
    ("Accident and anomaly detection",
     "Positives are rare, and severity labels need expert adjudication.",
     "Rejected — the positive class would be too small to evaluate honestly "
     "within a twenty-week schedule."),
    ("Sensor-fusion congestion forecasting (camera + loop detector + GPS)",
     "Strongest formulation, but depends on municipal sensor feeds.",
     "Rejected — no route to the loop-detector or probe-vehicle data; the "
     "project would stall on a dependency outside the team's control."),
    ("Camera-only congestion forecasting driving an adaptive signal "
     "controller",
     "One fixed camera per approach, a short forecast horizon, and a "
     "controller trained in simulation against that forecast.",
     "Selected — every input is obtainable from a single fixed camera, and "
     "the work splits cleanly into a perception claim and a control claim "
     "that can each stand alone."),
)

#: Every design decision taken before implementation began, with what it was
#: chosen over. This is the table a reviewer needs in order to tell a
#: considered design from an assembled one.
DESIGN_CHOICES: tuple[tuple[str, str, str, str], ...] = (
    ("Detector",
     "Faster R-CNN; RetinaNet; DETR; YOLOv8s",
     "YOLOv8s",
     "Single-stage and exportable, and the only candidate with a credible "
     "path to the ten-frames-per-second edge budget."),
    ("Vision transformer",
     "Supervised ViT-S/16; CLIP ViT-B/32; DINOv2 ViT-S/14",
     "DINOv2 ViT-S/14",
     "The backbones are frozen, so representation quality is the whole of "
     "what the branch contributes. Note the patch size: 14, not 16, so token "
     "counts must be read from configuration rather than assumed."),
    ("Backbone regime",
     "Full fine-tuning; partial unfreeze partway through training; frozen "
     "backbones with a precomputed feature cache",
     "Frozen with a cache",
     "At the specified batch size an uncached step pushes 1,920 frames "
     "through both backbones, which does not fit in 6 GB. Caching turns the "
     "eight-configuration ablation from days into hours."),
    ("Fusion mechanism",
     "Channel concatenation; one-way cross-attention; bidirectional "
     "cross-attention averaged; gated bidirectional cross-attention",
     "Gated bidirectional",
     "The gate is a scalar per position that says which branch the model "
     "relied on. It is the one part of the design that produces an "
     "inspectable artefact rather than only a score."),
    ("Temporal model",
     "GRU; temporal convolutional network; transformer encoder alone; "
     "BiLSTM followed by temporal self-attention",
     "BiLSTM + temporal self-attention",
     "Sixty steps is short for a transformer trained from scratch and long "
     "enough that the recurrence has something to carry."),
    ("Sequence pooling",
     "Last hidden state; mean over time; attention pooling",
     "Attention pooling",
     "Congestion sixty seconds ahead is not equally determined by every "
     "frame, and attention pooling is the ablation-friendly way to say so."),
    ("Prediction target",
     "Per-frame count regression; one congestion class for the junction; "
     "per-lane three-class congestion",
     "Per-lane three-class at t + 60 s",
     "The controller acts per approach, so a junction-level label would be "
     "unusable by the component that consumes it."),
    ("Lane geometry",
     "Automatic clustering of detections; homography from a survey; "
     "hand-placed centres reviewed by a second person",
     "Hand-placed and reviewed",
     "Automatic centres move by 0.164 of frame width when the detector "
     "changes, which silently changes every count the corpus is built on."),
    ("Evaluation split",
     "Random 60/20/20; stratified by class; leave-one-camera-out",
     "Leave-one-camera-out",
     "A random split lets the model memorise a camera and report it as "
     "generalisation. Holding out a whole camera is the only split that "
     "answers the question actually being asked."),
    ("Controller",
     "Fixed-time; vehicle-actuated; DQN; PPO",
     "PPO",
     "Stable on a small discrete action space without the replay-buffer "
     "tuning DQN needs, and available as a maintained implementation."),
    ("Simulator",
     "CityFlow; SUMO with the default lane model; SUMO with the sublane model",
     "SUMO, sublane model",
     "Indian traffic is not lane-disciplined. The sublane model represents "
     "lateral position within a lane; the residual gap is declared rather "
     "than papered over."),
    ("Edge device",
     "NVIDIA Jetson Nano; Raspberry Pi with a Coral accelerator; a team laptop",
     "Team laptop",
     "The cash budget is zero. The control logic and the message contract "
     "are unchanged by the substitution, but every latency figure must then "
     "state the host it was measured on."),
    ("Datastore",
     "PostgreSQL with TimescaleDB; InfluxDB; SQLite",
     "SQLite",
     "The prototype stores a bounded history of counts and decisions. A "
     "database server would be infrastructure without a purpose."),
)


# ==========================================================================
#  Chapter 2 — literature
# ==========================================================================

#: Table 2.1: the four strands, what each establishes, and what it leaves open
#: for this project. Comparison, not a list of papers.
LITERATURE_STRANDS: tuple[tuple[str, str, str], ...] = (
    ("Convolutional backbones for traffic scenes",
     "Deep residual networks [4] give strong local texture and occlusion "
     "cues, and remain the default feature extractor for dense scenes.",
     "Local receptive fields alone do not represent the whole approach; a "
     "queue that extends past the crop is not visible to them."),
    ("Vision transformers and self-supervised features",
     "ViT [2] models global context by construction, and DINOv2 [3] shows "
     "self-supervised features transfer without fine-tuning.",
     "Almost all reported use is fine-tuned. How well frozen DINOv2 features "
     "describe dense unstructured traffic is not established."),
    ("Cross-attention fusion",
     "Cross-attention [1] is the standard way to let two modalities query "
     "one another, and is used widely in vision-language work.",
     "Fusion is normally reported as a single number. Which branch the model "
     "actually relied on is not reported, so it cannot be checked."),
    ("Temporal modelling for short-horizon forecasting",
     "Recurrent models [14] and gradient-boosted count models [15] are both "
     "established for short-horizon traffic prediction.",
     "Count-only baselines are frequently omitted from vision papers, so the "
     "appearance branch is rarely shown to be earning its place."),
    ("Adaptive signal control",
     "Webster's method [10] remains the classical baseline; the RL survey "
     "[13] catalogues both the progress and the recurring evaluation flaws "
     "of learned controllers.",
     "Learned controllers are often compared against an untuned fixed-time "
     "arm, which makes the improvement easy to overstate."),
    ("Unstructured-traffic datasets and standards",
     "IDD [6] covers Indian road scenes for driving tasks; IRC [11] and "
     "Indo-HCM [12] supply the intersection and capacity conventions.",
     "No public dataset gives fixed-camera junction footage with the "
     "per-lane congestion labels this project needs."),
)


# ==========================================================================
#  Chapter 3 — problem, questions, objectives, scope
# ==========================================================================

RESEARCH_QUESTIONS: tuple[tuple[str, str], ...] = (
    ("RQ1", "Do frozen appearance features add anything over vehicle counts "
            "alone when forecasting per-lane congestion sixty seconds ahead? "
            "The count-only baseline is part of the experiment, not a "
            "courtesy."),
    ("RQ2", "Does gated bidirectional fusion beat cheaper fusion, and does "
            "the learned gate carry an interpretable signal about which "
            "branch the model relies on?"),
    ("RQ3", "Does a controller that receives a short-horizon congestion "
            "forecast outperform the same controller without one, measured "
            "against a swept-and-tuned Webster baseline rather than an "
            "untuned one?"),
)

OBJECTIVES: tuple[tuple[str, str], ...] = (
    ("O1", "Assemble a licence-audited corpus of fixed-camera junction "
           "footage covering unstructured traffic, and fine-tune a YOLOv8s "
           "detector over eight vehicle classes that include the "
           "auto-rickshaw, e-rickshaw and cattle absent from COCO."),
    ("O2", "Derive per-lane congestion labels from detector counts using "
           "PCU-weighted occupancy with per-camera thresholds, so that a "
           "label means the same thing at a six-lane arterial and a "
           "two-lane approach."),
    ("O3", "Implement the Phase I model — two frozen backbones, standard "
           "cross-attention fusion, a BiLSTM and a per-lane congestion head "
           "— and demonstrate that it trains to convergence before any "
           "Phase II component is added."),
    ("O4", "Extend the model with gated bidirectional fusion, temporal "
           "self-attention and attention pooling, and quantify each addition "
           "through an eight-configuration ablation that includes a linear "
           "probe as its floor."),
    ("O5", "Evaluate leave-one-camera-out, reporting mean and bootstrap "
           "confidence interval across folds together with the seed spread, "
           "so that no reported score is a memorised camera or a lucky "
           "initialisation."),
    ("O6", "Train a PPO signal controller on a SUMO intersection whose "
           "observation vector carries the forecast, measure it against a "
           "swept, best-configuration Webster baseline over thirty paired "
           "seeds, and demonstrate an edge-to-server prototype in which no "
           "raw frame leaves the capture device."),
)

IN_SCOPE: tuple[str, ...] = (
    "One four-approach signalised junction, with one fixed camera per "
    "approach and a fixed field of view.",
    "A sixty-second forecast horizon at a five-second sampling interval, "
    "giving a sixty-step input window.",
    "Three ordered congestion classes per lane — LOW, MEDIUM, HIGH — defined "
    "on PCU-weighted occupancy rather than on raw vehicle count.",
    "Signal control evaluated in simulation, with the prototype demonstrating "
    "the end-to-end path rather than controlling live signals.",
)

OUT_OF_SCOPE: tuple[str, ...] = (
    "Control of a live municipal signal. Nothing in this project is connected "
    "to a road-side controller.",
    "Vehicle re-identification, number-plate recognition, or any per-vehicle "
    "identity. Only aggregate counts leave the capture device.",
    "Network-wide coordination across multiple junctions. The observation and "
    "action spaces are defined for one junction.",
    "Pedestrian and non-motorised phase modelling beyond a fixed minimum "
    "clearance interval.",
    "Night-time and heavy-rain conditions, which are recorded as a stated "
    "limitation rather than claimed and left untested.",
)


# ==========================================================================
#  Chapter 4 — plan, milestones and risk
# ==========================================================================

#: The build order is a constraint, not a preference: PRD §2.4 fixes it to
#: prevent the known failure mode of an over-engineered architecture with
#: under-delivered experiments.
PHASE_PLAN: tuple[tuple[str, str, str, str], ...] = (
    ("Phase I\nMandatory",
     "Weeks 1-8",
     "Corpus pipeline and audit; YOLOv8s fine-tuning; PCU-weighted "
     "labelling; feature cache; CNN + ViT with standard cross-attention, "
     "BiLSTM and the per-lane head.",
     "The Phase I model trains to convergence and beats the linear probe on "
     "a held-out camera. Nothing from Phase II begins until it does."),
    ("Phase II\nStretch",
     "Weeks 9-14",
     "Gating replaces standard cross-attention; temporal self-attention over "
     "the BiLSTM outputs; attention pooling replaces the last hidden state; "
     "the full eight-configuration ablation, leave-one-camera-out at five "
     "seeds.",
     "Every configuration runs from a flag with no code edit between "
     "configurations, and the ablation table is generated from committed "
     "per-run CSVs."),
    ("Phase III\nOptional",
     "Weeks 15-20",
     "SUMO environment and PPO arms; the thirty-seed paired benchmark "
     "against a swept Webster baseline; ONNX export; edge node, MQTT "
     "contract, control server and dashboard.",
     "The prototype demonstrates both required fallback paths, and the "
     "control result is reported with its disqualification rules applied."),
)

MILESTONES: tuple[tuple[str, str], ...] = (
    ("Week 2", "Idea fixed, requirements written, detector bootstrapped on a "
               "public dataset so the corpus pipeline is not blocked on "
               "in-house annotation."),
    ("Week 5", "Corpus pipeline end to end: triage, reviewed lane geometry, "
               "counts, labels, audit. Architecture and design documents due."),
    ("Week 8", "Phase I model converging; feature cache built; the in-house "
               "dataset swaps in and every experiment records which detector "
               "weights produced it."),
    ("Week 11", "Phase II components in; ablation running; test plan and test "
                "design documents due."),
    ("Week 14", "Leave-one-camera-out ablation complete at five seeds, with "
                "raw per-run CSVs committed."),
    ("Week 17", "Controller trained and benchmarked; ONNX export and control "
                "server working."),
    ("Week 19", "Prototype integrated end to end, both fallback paths "
                "exercised."),
    ("Week 20", "Results, test report and paper draft; public code release "
                "with pinned requirements and fixed seeds."),
)

#: Risks are stated with a trigger and a response rather than as a list of
#: worries, because a risk without a response is not a plan.
RISKS: tuple[tuple[str, str, str, str], ...] = (
    ("Annotation effort is underestimated",
     "High", "High",
     "Bootstrap the detector on a public dataset from Week 2 so the corpus "
     "pipeline never waits on in-house annotation, and curate from "
     "permissively licensed sources before collecting anything new."),
    ("Permission for campus footage is delayed",
     "Medium", "High",
     "The perception track is built on curated public footage first, so "
     "in-house capture swaps in as an addition rather than a dependency."),
    ("A capture location yields only one camera",
     "Medium", "Medium",
     "Leave-one-camera-out cannot score a single-camera location. Capture is "
     "planned as multiple viewpoints per location from the start."),
    ("The HIGH class is rare in the available footage",
     "High", "Medium",
     "Report macro-F1 and per-class support rather than accuracy, weight the "
     "loss by inverse frequency, and state the class counts beside every "
     "result."),
    ("6 GB of VRAM is insufficient",
     "Medium", "High",
     "Freeze both backbones and cache their features; hold a small number of "
     "windows resident and accumulate gradients to the specified batch size."),
    ("The simulator does not reproduce unstructured traffic",
     "High", "Medium",
     "Use the sublane model, calibrate demand against observed counts, and "
     "declare the residual gap as a limitation rather than claiming realism."),
    ("The forecast does not help the controller",
     "Medium", "High",
     "Run the perfect-forecast ceiling first: if a perfect forecast does not "
     "beat no forecast, the forecast is not worth carrying and that is "
     "reported as a finding."),
    ("Appearance features do not beat counts",
     "Medium", "High",
     "The count-only baseline is in the experiment from the start, and the "
     "two claims are stated separately so the control claim ships even if "
     "the vision claim does not."),
)

PERFORMANCE_MEASURES: tuple[tuple[str, str], ...] = (
    ("Macro-F1", "The headline forecasting metric. Chosen over accuracy "
                 "because the HIGH class is expected to be rare, and "
                 "accuracy would reward ignoring it."),
    ("Per-class precision, recall and support",
     "Reported for every class, so a metric cannot hide an unpredicted "
     "class."),
    ("Quadratic weighted kappa and ordinal error rate",
     "The classes are ordered: confusing LOW with HIGH is not the same error "
     "as confusing LOW with MEDIUM."),
    ("Detection mAP@0.5 and counting error",
     "Reported separately, because counting accuracy and detection accuracy "
     "are different quantities and the corpus depends on the second."),
    ("Mean vehicle waiting time and queue length",
     "The control metrics, measured over thirty paired evaluation seeds per "
     "method in each demand regime."),
    ("Bootstrap 95% confidence interval, paired t-test, Cohen's d",
     "Every comparison is reported with an interval and an effect size, "
     "never as a bare difference of two means."),
    ("Latency, with its measurement host",
     "Detection frame rate, model inference time, controller decision time "
     "and message round-trip, each labelled with the machine it was measured "
     "on."),
)


# ==========================================================================
#  Chapter 6 — outcomes and future scope
# ==========================================================================

DELIVERABLES: tuple[tuple[str, str], ...] = (
    ("Curated dataset",
     "Fixed-camera junction footage curated from permissively licensed "
     "sources, plus an in-house capture set, with a per-camera provenance "
     "record stating how each property was determined."),
    ("Fine-tuned detector",
     "YOLOv8s weights over eight India-relevant classes, with the counting "
     "operating point calibrated against human-verified counts rather than "
     "against its own pseudo-labels."),
    ("Congestion forecasting model",
     "Trained weights, an ONNX export for CPU inference, and the gate value "
     "exposed from the forward pass as a research artefact rather than an "
     "internal detail."),
    ("Ablation and evaluation results",
     "Per-run CSVs for all eight configurations across every fold and seed, "
     "with confidence intervals generated by a committed script and never "
     "transcribed."),
    ("Signal controller",
     "A trained PPO policy and a thirty-seed paired benchmark against a "
     "swept Webster baseline and a fixed-time arm, across three demand "
     "regimes."),
    ("Working prototype",
     "Edge node, MQTT contract, control server with safety limits enforced "
     "outside the transport layer, and a monitoring dashboard that keeps "
     "benchmark numbers and live numbers in separate panels."),
    ("Reproducibility package",
     "Pinned requirements, fixed seeds, committed raw results, a public code "
     "release and archived weights, so every reported number can be "
     "regenerated from a clean machine."),
)

#: Targets, taken from the PRD. A proposal states what it will be judged
#: against; it does not report what it achieved.
TARGETS: tuple[tuple[str, str, str], ...] = (
    ("Detection quality", "mAP@0.5 ≥ 0.70 over the eight classes",
     "Measured on a human-labelled test split, never on pseudo-labels."),
    ("Detection throughput", "≥ 10 frames per second on the edge device",
     "Reported with the measurement host named, because the edge device is "
     "a laptop and not a Jetson."),
    ("Forecasting quality",
     "Macro-F1 ≥ 0.75 on held-out cameras, and above the count-only "
     "baseline",
     "Both halves matter: beating the baseline is the claim, the absolute "
     "number is the target."),
    ("Model inference", "≤ 150 ms per window on server CPU via ONNX",
     "The budget the control loop is designed around."),
    ("Control improvement",
     "≥ 15% lower mean waiting time than the best Webster configuration",
     "Measured over thirty paired seeds with a paired t-test and an effect "
     "size, and disqualified if fewer than 85% of trips complete."),
    ("Decision and message latency",
     "≤ 50 ms per control decision and ≤ 200 ms end to end over MQTT",
     "Measured on the prototype, with the host stated."),
    ("Reproducibility",
     "Every table regenerated from committed CSVs by a committed script",
     "Fixed seeds across the numerical, deep-learning and RL libraries."),
)

FUTURE_SCOPE: tuple[tuple[str, str], ...] = (
    ("Coordination across junctions",
     "The observation and action spaces are defined for one junction. "
     "Extending to a corridor means a shared reward and an explicit "
     "communication scheme between agents, which is a project in itself."),
    ("Deployment on dedicated edge hardware",
     "The control logic and the message contract are written to be unchanged "
     "by the substitution, so a Jetson port is a re-measurement rather than "
     "a rewrite."),
    ("Wider domain coverage",
     "Night, rain and fog are out of scope here and are the first extension "
     "worth making, because they are where a camera-only method is weakest."),
    ("Distilling a larger detector",
     "A larger detector can pseudo-label footage for the deployed small one, "
     "adopted only if pre-registered criteria are met on real labelled test "
     "data."),
    ("Longer forecast horizons",
     "Sixty seconds is chosen to match one signal cycle. Longer horizons "
     "would let the controller plan across cycles, at a cost in accuracy "
     "that has to be measured rather than assumed."),
    ("Public release and dissemination",
     "Code, weights and an archived dataset record, with a paper submitted "
     "to a transport or vision venue once the evaluation is complete."),
)


# ==========================================================================
#  Chapter 5 — requirements, as planned
# ==========================================================================

HARDWARE_ROWS: tuple[tuple[str, str, str], ...] = (
    ("Training workstation", "Laptop, 8-core x86-64 CPU, 16 GB RAM",
     "Feature caching, model training and the ablation sweeps."),
    ("GPU", "NVIDIA RTX 4050 Laptop, 6 GB VRAM",
     "Frozen-backbone feature extraction and training, in mixed precision. "
     "The 6 GB limit is why the backbones are frozen and cached."),
    ("Storage", "512 GB SSD, of which roughly 60 GB for video, cache and "
                "weights",
     "Source clips, the memory-mapped feature cache and model checkpoints."),
    ("Edge node", "A team laptop acting as the edge device",
     "Detection, counting and the local fallback controller. Every latency "
     "figure states this host, because it is not a Jetson."),
    ("Camera", "Fixed municipal or campus CCTV stream, 720p or better",
     "Frame source, one per approach. Frames are processed in place and "
     "never transmitted."),
    ("Network", "Wi-Fi or Ethernet LAN with a broker inside 200 ms",
     "Carries counts, predictions and signal commands only."),
)

SOFTWARE_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Operating system and language",
     ("Windows 11 and Ubuntu 22.04 (both supported)", "Python 3.12+")),
    ("Deep learning",
     ("PyTorch with CUDA 12.6", "torchvision, for the ResNet-50 backbone",
      "timm, for the DINOv2 backbone", "Ultralytics YOLOv8")),
    ("Reinforcement learning and simulation",
     ("Stable-Baselines3", "Gymnasium",
      "Eclipse SUMO with TraCI and sumolib")),
    ("Serving and deployment",
     ("ONNX and ONNX Runtime", "FastAPI with Pydantic", "Uvicorn",
      "Eclipse Mosquitto with Paho-MQTT")),
    ("Data, storage and analysis",
     ("SQLite, embedded, with no separate database server",
      "NumPy, pandas and SciPy", "scikit-learn and XGBoost", "OpenCV")),
    ("Interface",
     ("React with Vite and Zustand", "Recharts and native WebSocket")),
    ("Engineering tooling",
     ("Git, with Git LFS for model weights",
      "pytest with continuous integration",
      "MLflow and TensorBoard for experiment tracking", "Docker Compose")),
)


# ==========================================================================
#  References
# ==========================================================================
#
#  Deliberately a separate list from the progress synopsis rather than a slice
#  of it. The two documents cite different work, and the guideline requires
#  that every entry be cited and every citation have an entry — a shared list
#  would guarantee that one of the two documents violates it.
#  `scripts/check_synopsis.py` enforces both directions on each document.

REFERENCES: tuple[str, ...] = (
    'A. Vaswani et al., "Attention is all you need," in Proc. Adv. Neural Inf. '
    "Process. Syst. (NeurIPS), 2017, pp. 5998-6008.",

    'A. Dosovitskiy et al., "An image is worth 16x16 words: Transformers for '
    'image recognition at scale," in Proc. Int. Conf. Learn. Represent. '
    "(ICLR), 2021.",

    'M. Oquab et al., "DINOv2: Learning robust visual features without '
    'supervision," Trans. Mach. Learn. Res., 2024.',

    'K. He, X. Zhang, S. Ren, and J. Sun, "Deep residual learning for image '
    'recognition," in Proc. IEEE Conf. Comput. Vis. Pattern Recognit. (CVPR), '
    "2016, pp. 770-778.",

    'G. Jocher, A. Chaurasia, and J. Qiu, "Ultralytics YOLOv8," 2023. '
    "[Online]. Available: https://github.com/ultralytics/ultralytics",

    'G. Varma, A. Subramanian, A. Namboodiri, M. Chandraker, and C. V. '
    'Jawahar, "IDD: A dataset for exploring problems of autonomous navigation '
    'in unconstrained environments," in Proc. IEEE Winter Conf. Appl. Comput. '
    "Vis. (WACV), 2019, pp. 1743-1751.",

    'J. Schulman, F. Wolski, P. Dhariwal, A. Radford, and O. Klimov, "Proximal '
    'policy optimization algorithms," arXiv:1707.06347, 2017.',

    'A. Raffin, A. Hill, A. Gleave, A. Kanervisto, M. Ernestus, and N. '
    'Dormann, "Stable-Baselines3: Reliable reinforcement learning '
    'implementations," J. Mach. Learn. Res., vol. 22, no. 268, pp. 1-8, 2021.',

    'P. A. Lopez et al., "Microscopic traffic simulation using SUMO," in Proc. '
    "IEEE Int. Conf. Intell. Transp. Syst. (ITSC), 2018, pp. 2575-2582.",

    'F. V. Webster, "Traffic signal settings," Road Research Technical Paper '
    "No. 39, Road Research Laboratory, London, U.K., 1958.",

    "Indian Roads Congress, IRC:SP:41-1994, Guidelines for the Design of "
    "At-Grade Intersections in Rural and Urban Areas. New Delhi, India: IRC, "
    "1994.",

    "Indo-HCM, Indian Highway Capacity Manual. New Delhi, India: "
    "CSIR-Central Road Research Institute, 2017.",

    'H. Wei, G. Zheng, V. Gayah, and Z. Li, "Recent advances in reinforcement '
    'learning for traffic signal control: A survey of models and evaluation," '
    "ACM SIGKDD Explorations Newsletter, vol. 22, no. 2, pp. 12-18, 2021.",

    'S. Hochreiter and J. Schmidhuber, "Long short-term memory," Neural '
    "Computation, vol. 9, no. 8, pp. 1735-1780, 1997.",

    'T. Chen and C. Guestrin, "XGBoost: A scalable tree boosting system," in '
    "Proc. ACM SIGKDD Int. Conf. Knowl. Discovery Data Mining, 2016, "
    "pp. 785-794.",

    "R. S. Sutton and A. G. Barto, Reinforcement Learning: An Introduction, "
    "2nd ed. Cambridge, MA, USA: MIT Press, 2018.",
)
