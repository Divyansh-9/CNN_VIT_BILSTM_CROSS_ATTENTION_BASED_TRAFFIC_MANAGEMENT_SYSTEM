"""Render the **Phase I** synopsis report to `.docx`.

This is the proposal document: what the team decided to build, what it was
chosen over, and how the work is sequenced. It reports **no measured results**
— see the module docstring of `scripts/synopsis_phase1_content.py` for why the
separation is enforced by construction rather than by care.

Every formatting constant, paragraph helper, table helper and piece of front
matter is imported from `scripts.build_synopsis_docx` rather than copied. The
Department's guideline is one rule set; two copies of it would drift, and the
drift would be invisible until submission.

Run through `scripts/build_synopsis.py --which phase1`; this module exposes
`build()`.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8

use_utf8()

from scripts import build_synopsis_docx as D
from scripts import synopsis_phase1_content as P
from scripts.docx_writer import (Document, LINE_ONE_HALF, Para, Run, Table,
                                 inches)

BODY = D.BODY
WIDTH = D.WIDTH

body = D.body
chapter = D.chapter
section = D.section
subsection = D.subsection
caption = D.caption
bullets = D.bullets
labelled = D.labelled
equation = D.equation
data_table = D.data_table
node = D.node
arrow = D.arrow
blank = D.blank


def widths_for(*fractions: float) -> list[int]:
    """Column widths that sum to exactly the usable text width.

    The last column absorbs the rounding, because a table whose columns sum to
    one twip less than the text width is visibly narrow on the page.
    """
    out = [int(WIDTH * fraction) for fraction in fractions[:-1]]
    out.append(WIDTH - sum(out))
    return out


# ==========================================================================
#  Abstract
# ==========================================================================

def abstract(doc: Document) -> None:
    D.front_heading(doc, "ABSTRACT")
    body(doc,
         "Urban traffic in Indian cities is heterogeneous and not lane "
         "disciplined: two-wheelers, auto-rickshaws, e-rickshaws, cars, buses "
         "and occasionally cattle share the same carriageway and occupy "
         "lateral positions that a lane model does not describe. Signals at "
         "such junctions are still overwhelmingly fixed-time, so green is "
         "allocated to an approach that may be empty while a saturated "
         "approach waits. The information needed to do better is already "
         "present in the CCTV cameras that most junctions already carry; what "
         "is missing is a method that turns those frames into a forecast a "
         "controller can act on.")
    body(doc,
         f"This project proposes {P.TITLE_SHORT}: a camera-only pipeline that "
         f"predicts per-lane congestion sixty seconds ahead and hands that "
         f"prediction to a reinforcement-learning signal controller. A "
         f"fine-tuned YOLOv8s detector produces per-lane vehicle counts over "
         f"eight India-relevant classes; those counts are converted into "
         f"ordered congestion labels using passenger-car-unit-weighted "
         f"occupancy with per-camera thresholds. A frozen convolutional "
         f"backbone and a frozen self-supervised vision transformer are fused "
         f"by gated bidirectional cross-attention, modelled over time by a "
         f"bidirectional LSTM with temporal self-attention, and read out per "
         f"lane. A PPO agent trained in the SUMO microsimulator consumes the "
         f"forecast as part of its observation and selects the next phase and "
         f"its duration.")
    body(doc,
         "The methodology is deliberately staged. Phase I delivers the "
         "corpus, the detector and a model with standard cross-attention "
         "only, and nothing from Phase II begins until that converges. Phase "
         "II adds gating, temporal attention and attention pooling, each "
         "behind a configuration flag so that an eight-configuration "
         "ablation — including a linear probe as its floor — runs without a "
         "code edit. Evaluation is leave-one-camera-out at five seeds, and "
         "the controller is measured against a swept, best-configuration "
         "Webster baseline over thirty paired seeds.")
    body(doc,
         "The expected outcome is a curated dataset, a fine-tuned detector, a "
         "trained forecasting model with its fusion gate exposed as an "
         "inspectable artefact, a signal controller benchmarked with "
         "confidence intervals and an effect size, and a working "
         "edge-to-server prototype in which no raw frame ever leaves the "
         "capture device. Every table in the final report is to be generated "
         "from committed per-run result files by a committed script.")
    body(doc,
         f"Keywords: traffic congestion forecasting; cross-attention fusion; "
         f"vision transformer; reinforcement learning; adaptive signal "
         f"control; unstructured traffic. Working name: {P.WORKING_NAME}.")


# ==========================================================================
#  Chapter 1 — Introduction
# ==========================================================================

def introduction(doc: Document) -> None:
    chapter(doc, "1", "INTRODUCTION")

    section(doc, "1.1", "Background")
    body(doc,
         "A signalised junction allocates a scarce resource — green time — "
         "among competing approaches. A fixed-time signal allocates it from a "
         "plan computed once, from counts taken once, and then applies that "
         "plan identically at every hour of every day. When demand is stable "
         "this is adequate. When demand varies, it is not: the plan is right "
         "on average and wrong most of the time, and the cost is paid in "
         "waiting vehicles, in fuel, and in emissions.")
    body(doc,
         "The Indian case is harder than the textbook case in two specific "
         "ways. First, the traffic stream is heterogeneous: a two-wheeler, an "
         "auto-rickshaw and a bus occupy very different amounts of road and "
         "discharge at very different rates, so counting vehicles without "
         "weighting them measures the wrong quantity. Second, the stream is "
         "not lane disciplined; vehicles occupy lateral positions between "
         "nominal lanes, and queue geometry does not follow lane markings. "
         "Both facts are recognised in Indian practice — the Indian Highway "
         "Capacity Manual [12] supplies passenger-car-unit equivalents "
         "precisely because vehicle counts are not comparable across classes "
         "— and both are ignored by most published traffic-vision work.")

    section(doc, "1.2", "Motivation")
    body(doc,
         "Two observations motivate this project. The first is that the "
         "sensing problem is largely already solved by existing "
         "infrastructure: a large number of Indian junctions already carry "
         "fixed CCTV cameras, installed for enforcement and monitoring, "
         "whose frames are sufficient to count and classify vehicles per "
         "approach. Adding inductive loops or probe-vehicle feeds would "
         "improve the input, but it would also make the method deployable "
         "only where a municipality has already invested in them.")
    body(doc,
         "The second is that a controller does not need to know the present; "
         "it needs to know the near future. A phase decision taken now takes "
         "effect over the next thirty to ninety seconds, so a controller "
         "acting on the current queue is always acting on stale information. "
         "A forecast one signal cycle ahead is therefore not a refinement of "
         "the sensing problem but a different problem, and it is the one this "
         "project takes as central.")

    section(doc, "1.3", "Selection of the Project Idea")
    body(doc,
         "The team shortlisted five candidate problems before fixing on one. "
         "They were scored against four criteria: whether every required "
         "input could be obtained without a dependency outside the team's "
         "control; whether the work contained a component that could be "
         "ablated and therefore defended; whether it fitted a twenty-week "
         "schedule with a zero-rupee cash budget; and whether a negative "
         "result would still be a reportable finding rather than a failed "
         "project. Table 1.1 records the shortlist and the decision on each.")

    data_table(doc, ["Candidate idea", "What it would have required",
                     "Decision and reason"],
               [list(row) for row in P.IDEA_CANDIDATES],
               widths_for(0.26, 0.31, 0.43), "1.1",
               "Candidate project ideas considered before selection")

    body(doc,
         f"The selected idea was registered under the working name "
         f"{P.WORKING_NAME}, which names the pipeline rather than the "
         f"contribution: a convolutional branch, a vision-transformer branch, "
         f"cross-attention between them and a recurrent temporal model. That "
         f"name is retained here because it is how the idea appears in the "
         f"team's early records, and guideline §1 asks for identity fields to "
         f"be traceable across documents. The title carried forward to every "
         f"later document is \"{P.TITLE}\".")
    body(doc,
         "It is worth being explicit about what is claimed. The individual "
         "mechanisms in this pipeline are published: cross-attention, gated "
         "fusion, frozen self-supervised backbones and PPO signal control all "
         "exist in the literature. The contribution claimed is their "
         "combination for this specific setting, and three things that are "
         "usually left out of it — the fusion gate reported as an artefact "
         "rather than an internal detail, a strictly camera-only input, and "
         "an evaluation that holds out whole cameras. Overstating novelty in "
         "a proposal only creates a claim that has to be retracted later.")

    section(doc, "1.4", "Scope of Phase I")
    body(doc,
         "This synopsis proposes the whole project, but the work is gated. "
         "Phase I is the mandatory core: the corpus pipeline, the detector, "
         "and a forecasting model built from a convolutional branch, a "
         "transformer branch, standard cross-attention, a bidirectional LSTM "
         "and a per-lane head. The architectural refinements that make the "
         "work publishable are Phase II, and they are not begun until the "
         "Phase I model trains to convergence. This ordering is a deliberate "
         "guard against a known failure mode in student projects — an "
         "elaborate architecture with no experiments attached to it — and it "
         "is treated here as a constraint rather than a preference.")

    section(doc, "1.5", "Organisation of this Synopsis")
    body(doc,
         "Chapter 2 reviews the relevant literature in four strands and "
         "states the gap. Chapter 3 states the problem, the research "
         "questions, the numbered objectives and the scope boundaries. "
         "Chapter 4 gives the proposed methodology: the design decisions and "
         "what they were chosen over, the system architecture, the corpus, "
         "the model, the controller, the evaluation protocol, the phase plan "
         "and the risk register. Chapter 5 lists the hardware and software "
         "the project actually requires. Chapter 6 states the expected "
         "outcomes, the measurable targets and the future scope. Chapter 7 "
         "concludes.")


# ==========================================================================
#  Chapter 2 — Literature Review
# ==========================================================================

def literature_review(doc: Document) -> None:
    chapter(doc, "2", "LITERATURE REVIEW")
    body(doc,
         "The work this project builds on falls into four strands: visual "
         "representation for traffic scenes, multimodal fusion, temporal "
         "modelling for short-horizon forecasting, and adaptive signal "
         "control. Each is summarised below in terms of what it establishes "
         "and what it leaves unresolved for the present setting.")

    section(doc, "2.1", "Visual Representation for Traffic Scenes")
    body(doc,
         "Deep residual networks [4] remain the default feature extractor for "
         "dense scenes, and their inductive bias suits the problem: local "
         "texture, partial occlusion and small objects are exactly what a "
         "convolutional stack is good at. The limitation is equally "
         "structural. A convolutional receptive field is local, and the "
         "quantity of interest — how far a queue extends along an approach — "
         "is global. A network that sees the head of a queue clearly and the "
         "tail not at all will underestimate it consistently.")
    body(doc,
         "Vision transformers [2] model global relationships by construction, "
         "and DINOv2 [3] shows that self-supervised pre-training produces "
         "features that transfer without fine-tuning. That last property is "
         "what makes a transformer branch affordable here: if the backbone is "
         "never updated, its features can be computed once and cached, and "
         "the training cost collapses. What is not established is how well "
         "frozen self-supervised features describe dense, unstructured "
         "traffic specifically, since almost all reported transfer results "
         "fine-tune. Treating that as an open question rather than an "
         "assumption is why the count-only baseline is part of this "
         "experiment.")

    section(doc, "2.2", "Multimodal and Multi-Branch Fusion")
    body(doc,
         "Cross-attention [1] is the standard mechanism for letting one "
         "representation query another, and gated combinations of two "
         "branches are common in multimodal work. The mechanisms are "
         "therefore not novel, and this proposal does not claim them as "
         "such. What is unusual is the reporting: fusion is normally "
         "evaluated by whether the fused model scores higher, and the "
         "internal quantity that decides how much of each branch was used is "
         "not published. A gate that is logged, tracked and analysed turns "
         "that quantity into evidence, and makes it possible to say which "
         "branch the model relied on under which conditions rather than "
         "merely that fusion helped.")

    section(doc, "2.3", "Temporal Modelling for Short-Horizon Forecasting")
    body(doc,
         "Long short-term memory networks [14] are long established for "
         "sequence modelling, and gradient-boosted trees [15] remain strong "
         "on tabular count sequences. Sixty timesteps is a short sequence: "
         "long enough that a recurrence has something to accumulate, short "
         "enough that a transformer trained from scratch on a small corpus "
         "would be a poor use of the available data. The combination adopted "
         "here — a bidirectional recurrence followed by a small self-"
         "attention block over its outputs — is chosen on those grounds and "
         "is itself part of the ablation rather than an assumption.")

    section(doc, "2.4", "Adaptive Signal Control")
    body(doc,
         "Webster's method [10] computes cycle length and green splits from "
         "flow ratios and remains the classical baseline. Its two parameters "
         "matter more than its formula: the saturation flow rate, for which "
         "the published range for Indian conditions spans more than a factor "
         "of two [11], [12], and the cycle-length clamp. A learned controller "
         "compared against one arbitrary point in that range is being "
         "compared against a straw baseline.")
    body(doc,
         "Reinforcement learning for signal control is a mature subfield; the "
         "survey of Wei et al. [13] catalogues both its progress and its "
         "recurring methodological problems, of which weak baselines and "
         "single-seed reporting are the two most common. PPO [7], for which a "
         "maintained implementation is available [8], is stable on small "
         "discrete action spaces without the replay tuning that value-based "
         "methods require; the underlying formulation follows standard "
         "treatment [16]. Training requires a microsimulator, and SUMO [9] is "
         "the established open one.")

    section(doc, "2.5", "Comparative Summary")
    body(doc,
         "Table 2.1 places the strands beside one another, stating for each "
         "what it establishes and what it leaves open for this project.")
    data_table(doc, ["Strand", "What it establishes",
                     "What it leaves open here"],
               [list(row) for row in P.LITERATURE_STRANDS],
               widths_for(0.22, 0.39, 0.39), "2.1",
               "Comparative summary of the four literature strands")

    section(doc, "2.6", "Research Gap")
    body(doc,
         "Three gaps follow from the above and together define this project. "
         "There is no published fixed-camera junction dataset for "
         "unstructured traffic carrying per-lane congestion labels; the "
         "closest Indian resource [6] is built for driving tasks from a "
         "moving platform, not for a fixed junction view. There is no "
         "reported analysis of what a fusion gate between a convolutional "
         "and a transformer branch actually learns on traffic imagery. And "
         "learned signal controllers are seldom evaluated against a "
         "baseline that has itself been tuned, which makes the reported "
         "improvement difficult to interpret.")


# ==========================================================================
#  Chapter 3 — Problem Statement and Objectives
# ==========================================================================

def problem_and_objectives(doc: Document) -> None:
    chapter(doc, "3", "PROBLEM STATEMENT & OBJECTIVES")

    section(doc, "3.1", "Problem Statement")
    body(doc,
         "Given only the video streams of fixed cameras at a signalised "
         "junction carrying heterogeneous, non-lane-disciplined traffic, "
         "predict the congestion level of each approach sixty seconds ahead, "
         "and use that prediction to select the next signal phase and its "
         "duration so that mean vehicle waiting time is lower than under a "
         "tuned fixed-time plan — subject to the constraint that no raw video "
         "frame is transmitted off the capture device or written to disk.")
    body(doc,
         "Three parts of that statement are load-bearing. \"Only the video "
         "streams\" excludes loop detectors and probe-vehicle data, which "
         "makes the method deployable on existing infrastructure and also "
         "makes it harder. \"Sixty seconds ahead\" is one signal cycle, which "
         "is the horizon over which a phase decision has effect. And the "
         "privacy constraint is a design constraint rather than a policy "
         "note: it determines that inference runs at the edge and that only "
         "derived counts and predictions cross the network.")

    section(doc, "3.2", "Research Questions")
    body(doc,
         "The project is organised around three questions, each stated so "
         "that a negative answer is a reportable result rather than a "
         "failure.")
    for tag, text in P.RESEARCH_QUESTIONS:
        labelled(doc, tag, text)

    section(doc, "3.3", "Objectives")
    body(doc,
         "The objectives below are ordered by dependency: each requires the "
         "one before it. Objectives O1 to O3 constitute Phase I and are "
         "mandatory; O4 and O5 are Phase II; O6 is Phase III.")
    for tag, text in P.OBJECTIVES:
        labelled(doc, tag, text)

    section(doc, "3.4", "Scope")
    body(doc,
         "The following are within scope and are what the project undertakes "
         "to deliver.")
    bullets(doc, P.IN_SCOPE)

    section(doc, "3.5", "Out of Scope")
    body(doc,
         "The following are explicitly excluded. They are listed rather than "
         "omitted, because an unstated exclusion reads as an unfulfilled "
         "promise at assessment.")
    bullets(doc, P.OUT_OF_SCOPE)


# ==========================================================================
#  Chapter 4 — Proposed Methodology
# ==========================================================================

def methodology(doc: Document) -> None:
    chapter(doc, "4", "PROPOSED METHODOLOGY")

    # -- 4.1 design decisions ---------------------------------------------
    section(doc, "4.1", "Design Decisions and the Alternatives Rejected")
    body(doc,
         "Every component below was chosen from a shortlist, and the "
         "shortlist is recorded rather than discarded. Table 4.1 gives, for "
         "each decision, what was considered, what was selected and the "
         "reason. Two of the entries are forced by the operating envelope "
         "rather than by preference — the frozen backbones by 6 GB of "
         "available video memory, and the edge device by a zero-rupee cash "
         "budget — and are marked as such rather than presented as "
         "principled choices they are not.")
    data_table(doc, ["Component", "Alternatives considered", "Selected",
                     "Reason"],
               [list(row) for row in P.DESIGN_CHOICES],
               widths_for(0.15, 0.27, 0.16, 0.42), "4.1",
               "Design decisions taken at project inception, with the "
               "alternatives rejected")

    # -- 4.2 architecture --------------------------------------------------
    section(doc, "4.2", "Proposed System Architecture")
    body(doc,
         "The system is three tiers, shown in Figure 4.1. The edge tier reads "
         "frames, detects and counts vehicles per lane, and publishes counts "
         "only. The server tier runs the forecasting model and the "
         "controller, applies safety limits, and stores a bounded history. "
         "The presentation tier displays live values and benchmark values in "
         "separate panels that never merge, so that a number measured on a "
         "held-out split is never shown as though it were a live reading.")
    body(doc,
         "The tier boundary carries the project's privacy constraint. Frames "
         "are read, processed and discarded inside the edge tier; what "
         "crosses the network is a count vector, a prediction and a signal "
         "command. Two fallback paths are required behaviour rather than "
         "robustness extras: if the forecasting model is unavailable the "
         "controller runs on counts alone, and if the message broker is "
         "silent for more than ten seconds the edge node arms a locally "
         "embedded fixed-time controller.")
    D.architecture_figure(doc)
    caption(doc, "Fig. 4.1  Proposed three-tier system architecture")

    # -- 4.3 corpus --------------------------------------------------------
    section(doc, "4.3", "Dataset and Corpus Construction")
    body(doc,
         "No public dataset supplies fixed-camera junction footage with "
         "per-lane congestion labels, so the corpus is constructed. The "
         "dataset is two-track by design. A detector is bootstrapped from "
         "public unstructured-traffic imagery [6] so that the pipeline is "
         "never blocked waiting on in-house annotation, and an in-house set "
         "is curated and captured in parallel and swapped in when ready. Any "
         "experiment run in the interval records which detector weights "
         "produced it, because two sets exist during that window.")
    body(doc,
         "Figure 4.2 gives the pipeline. Two stages deserve comment. Lane "
         "geometry is placed by hand and reviewed rather than derived "
         "automatically, because automatically derived lane centres shift by "
         "roughly one sixth of the frame width when the detector changes, "
         "which would silently alter every count the corpus rests on. And the "
         "split is cut by source clip, never by window: overlapping temporal "
         "windows from one clip placed on both sides of a split would leak "
         "the answer.")
    D.corpus_figure(doc)
    caption(doc, "Fig. 4.2  Proposed corpus construction pipeline")

    subsection(doc, "4.3.1", "Labelling by PCU-Weighted Occupancy")
    body(doc,
         "A congestion label derived from a raw vehicle count would treat a "
         "lane holding ten two-wheelers and a lane holding ten buses as "
         "equally congested. Labels are therefore defined on "
         "passenger-car-unit-weighted occupancy, using the equivalences "
         "published in the Indian Highway Capacity Manual [12]. For lane l at "
         "time t, with n_{c,l}(t) detections of class c and pcu_c the "
         "equivalence factor for that class, equation (4.1) defines the "
         "occupancy that thresholds are applied to.")
    equation(doc, "occ_l(t)  =  ( SUM_c  n_{c,l}(t) . pcu_c )  /  cap_l",
             "4.1")
    body(doc,
         "Here cap_l normalises by the capacity of the lane, so that the "
         "quantity is comparable between a six-lane arterial approach and a "
         "two-lane one. Thresholds separating LOW from MEDIUM and MEDIUM from "
         "HIGH are calibrated per camera at the 33rd and 67th percentiles of "
         "that camera's own occupancy distribution and are recorded in the "
         "corpus manifest. A vehicle class with no published equivalence "
         "raises an error rather than defaulting to a factor of one, since a "
         "silent default would corrupt every label containing that class.")

    # -- 4.4 detection -----------------------------------------------------
    section(doc, "4.4", "Vehicle Detection and Counting")
    body(doc,
         "Detection uses YOLOv8s [5], fine-tuned over eight classes chosen "
         "for the Indian street: two-wheeler, auto-rickshaw, e-rickshaw, car, "
         "light commercial vehicle, bus, truck and cattle. The last three of "
         "those are either absent from or unreliable in general-purpose "
         "object-detection training sets, which is the reason fine-tuning is "
         "necessary rather than optional. The detection split is stratified "
         "70/15/15, which is a different split from the model evaluation "
         "described in Section 4.7 and serves a different purpose.")
    body(doc,
         "Detection quality and counting quality are reported separately. A "
         "detector can score well on mean average precision while "
         "systematically miscounting a class that is small in the frame, and "
         "since every congestion label in the corpus is derived from counts, "
         "it is the counting error that propagates. The counting operating "
         "point is therefore calibrated against human-verified counts on a "
         "held-out set, and never against the detector's own output.")

    # -- 4.5 the model -----------------------------------------------------
    section(doc, "4.5", "The Proposed Forecasting Model")
    body(doc,
         "The model takes a sixty-frame window sampled at five-second "
         "intervals and predicts, for each of the four approaches, one of "
         "three ordered congestion classes at sixty seconds after the end of "
         "the window. Its structure is given in Figure 4.3.")
    D.model_figure(doc)
    caption(doc, "Fig. 4.3  Proposed model structure")

    subsection(doc, "4.5.1", "Frozen Backbones")
    body(doc,
         "Both backbones — a residual convolutional network [4] and a "
         "self-supervised vision transformer [3] — are frozen. This is not a "
         "regularisation choice; it is what makes the project fit the "
         "hardware. With both backbones trainable, a single step at the "
         "specified batch size would push 1,920 frames through them, which "
         "does not fit in 6 GB. Frozen, their outputs are a deterministic "
         "function of the input, so they are computed once and cached, and "
         "the eight-configuration ablation becomes a matter of hours rather "
         "than days. The cache is keyed on the preprocessing configuration "
         "and refuses to load against a mismatched key, because silently "
         "reusing features computed under different normalisation would "
         "produce results that are wrong rather than merely stale.")

    subsection(doc, "4.5.2", "Gated Bidirectional Cross-Attention")
    body(doc,
         "Two cross-attention passes [1] are computed: Z_A, in which the "
         "convolutional features query the transformer features, and Z_B, in "
         "which the transformer features query the convolutional features. "
         "A learned gate then combines them, as in equations (4.2) and (4.3), "
         "where sigma is the logistic function and W and b are learned.")
    equation(doc, "g  =  sigma( W [ Z_A ; Z_B ] + b )", "4.2")
    equation(doc, "F_fused  =  g . Z_A  +  ( 1 - g ) . Z_B", "4.3")
    body(doc,
         "The gate value g is treated as an output of the system rather than "
         "an internal detail. It is returned from the forward pass, logged "
         "during training, displayed on the dashboard and analysed in the "
         "final report, because it is the quantity that answers which branch "
         "the model relied on. A gate that is computed and discarded would "
         "make the fusion claim untestable.")

    subsection(doc, "4.5.3", "Temporal Modelling and Read-Out")
    body(doc,
         "The fused per-timestep features pass through a two-layer "
         "bidirectional LSTM [14], then through a small temporal "
         "self-attention block, and are pooled over time by attention rather "
         "than by taking the last hidden state — congestion sixty seconds "
         "ahead is not equally determined by every frame in the window. "
         "Read-out is per lane, using region-of-interest pooling over the "
         "spatial grid at each lane's reviewed geometry. Pooling globally and "
         "then applying one shared head four times cannot produce four "
         "different predictions, which is why the feature cache preserves "
         "spatial structure rather than storing a pooled vector.")

    subsection(doc, "4.5.4", "Planned Ablation")
    body(doc,
         "Every component above is required to be disableable by "
         "configuration, giving the eight configurations in Table 4.2. "
         "Configuration H, a linear probe over mean-pooled frozen features, "
         "is the floor: any frozen-backbone architecture that cannot beat it "
         "has not justified itself, and it is reported whatever it shows.")
    data_table(doc, ["Config", "Variant", "What it isolates"],
               [list(row) for row in P.ABLATION_ROWS],
               widths_for(0.09, 0.26, 0.65), "4.2",
               "The eight planned ablation configurations")

    # -- 4.6 control -------------------------------------------------------
    section(doc, "4.6", "Adaptive Signal Control")
    body(doc,
         "The controller is a PPO agent [7], [16] implemented with a "
         "maintained library [8], acting on a four-way intersection modelled "
         "in the SUMO microsimulator [9] and driven through its online "
         "interface. Geometry and phase structure follow Indian intersection "
         "design practice [11]. Because the traffic being modelled is not "
         "lane disciplined, the simulator's sublane model is enabled so that "
         "vehicles may occupy lateral positions within a lane; the residual "
         "difference between the simulation and observed behaviour is to be "
         "declared as a limitation rather than left implicit.")
    body(doc,
         "The observation vector is sixteen-dimensional and its layout is a "
         "contract: per-lane queue lengths, current phase and elapsed green, "
         "time of day, an emergency flag, and four entries carrying the "
         "forecast for the four approaches. If the forecast is unavailable "
         "those four entries are zeroed and the vector keeps its length, "
         "because a shortened vector silently invalidates every trained "
         "checkpoint. The action space is twelve discrete actions: two phase "
         "groups by six green durations. The reward, equation (4.4), is the "
         "negative mean waiting time across lanes at each decision step.")
    equation(doc, "r_t  =  -  ( 1 / |L| )  SUM_{l in L}  w_l(t)", "4.4")
    body(doc,
         "The baseline is Webster's method [10], and it is swept rather than "
         "configured once: the published saturation-flow range for Indian "
         "conditions is wide enough that a single arbitrary value would "
         "produce whichever result the author preferred. The best Webster "
         "configuration found by that sweep is the baseline the learned "
         "controller must beat.")

    # -- 4.7 evaluation ----------------------------------------------------
    section(doc, "4.7", "Evaluation Plan and Performance Measures")
    body(doc,
         "The forecasting model is to be evaluated leave-one-camera-out: each "
         "fold holds out one camera entirely, with the remainder used for "
         "training and validation. A random split over windows would let the "
         "model recognise a camera it has already seen and report that as "
         "generalisation. The headline figure is the mean across folds with a "
         "bootstrap 95% confidence interval, quoted together with the number "
         "of folds, because an interval over a handful of folds is not an "
         "interval over thirty runs.")
    body(doc,
         "Every configuration is to be run at five seeds. A single-seed table "
         "ranks initialisations rather than architectures, and on a corpus of "
         "this size the movement between seeds can exceed the gap between two "
         "architectures. The evaluation harness therefore reports the seed "
         "spread beside every mean, and two configurations separated by less "
         "than that spread are to be reported as not separated by the "
         "experiment.")
    body(doc,
         "Count-only baselines are part of the experiment rather than a "
         "courtesy. A recurrent model and a gradient-boosted model [15] over "
         "the same count sequences, on the same folds and seeds, answer "
         "RQ1 directly: if the appearance branch does not beat them, that is "
         "the finding and it will be reported as such. Table 4.3 lists the "
         "measures to be reported and why each is included.")
    data_table(doc, ["Measure", "Why it is reported"],
               [list(row) for row in P.PERFORMANCE_MEASURES],
               widths_for(0.30, 0.70), "4.3",
               "Performance measures and the reason for each")
    body(doc,
         "Three reproducibility rules apply throughout. Seeds are fixed "
         "across the numerical, deep-learning and reinforcement-learning "
         "libraries and recorded with every result. Raw per-run results are "
         "committed, not only summary tables. And every table in the final "
         "report is generated from those committed files by a committed "
         "script, so that a number in the report and a number in the data "
         "cannot disagree.")

    # -- 4.8 phase plan ----------------------------------------------------
    section(doc, "4.8", "Phase-Wise Development Plan")
    body(doc,
         "The build order is a constraint. Table 4.4 states the three phases, "
         "what each contains and the condition that must hold before the next "
         "begins. The rule that matters is the gate between Phase I and Phase "
         "II: no gating, no temporal attention and no attention pooling is "
         "implemented until the Phase I model trains cleanly to convergence. "
         "Figure 4.4 shows the same sequence as a flow, with the gate "
         "conditions on the transitions.")
    data_table(doc, ["Phase", "Weeks", "Contents", "Exit condition"],
               [list(row) for row in P.PHASE_PLAN],
               widths_for(0.13, 0.11, 0.40, 0.36), "4.4",
               "Phase-wise development plan and exit conditions")
    phase_figure(doc)
    caption(doc, "Fig. 4.4  Build order, with the condition on each gate")

    body(doc,
         "Table 4.5 places those phases on the twenty-week calendar as dated "
         "milestones, each of which is a checkable state of the repository "
         "rather than an activity.")
    data_table(doc, ["Milestone", "State to be reached"],
               [list(row) for row in P.MILESTONES],
               widths_for(0.16, 0.84), "4.5",
               "Twenty-week milestone schedule")

    # -- 4.9 risk ----------------------------------------------------------
    section(doc, "4.9", "Risk Register")
    body(doc,
         "Table 4.6 is the risk register. Each entry names a risk, its "
         "likelihood and impact, and the response — not a hope. Two entries "
         "are worth reading together: the possibility that the appearance "
         "features do not beat a count-only baseline, and the possibility "
         "that the forecast does not help the controller. Both are treated "
         "as outcomes to be measured rather than as failure modes to be "
         "avoided, which is why the two claims are kept separate and why the "
         "count-only baseline is in the experiment from the first week.")
    data_table(doc, ["Risk", "Likelihood", "Impact", "Response"],
               [list(row) for row in P.RISKS],
               widths_for(0.22, 0.11, 0.10, 0.57), "4.6",
               "Risk register with likelihood, impact and planned response",
               aligns=["left", "center", "center", "left"])


# ==========================================================================
#  Chapter 5 — Requirements
# ==========================================================================

def requirements(doc: Document) -> None:
    chapter(doc, "5", "HARDWARE AND SOFTWARE REQUIREMENTS")
    body(doc,
         "The requirements below are the ones this project actually needs; "
         "nothing is listed because it is conventional. Table 5.1 gives the "
         "hardware and Table 5.2 the software, each entry stated with the "
         "purpose it serves rather than as a specification in isolation.")

    section(doc, "5.1", "Hardware Requirements")
    body(doc,
         "Two entries determine the shape of the whole project. The 6 GB of "
         "video memory on the training GPU is why both backbones are frozen "
         "and their features cached, and the substitution of a team laptop "
         "for dedicated edge hardware is why every latency figure in this "
         "project must state the host it was measured on.")
    data_table(doc, ["Component", "Specification", "Purpose in this project"],
               [list(row) for row in P.HARDWARE_ROWS],
               widths_for(0.20, 0.34, 0.46), "5.1",
               "Hardware requirements")

    section(doc, "5.2", "Software Requirements")
    body(doc,
         "Exact versions are to be pinned in a committed requirements file, "
         "which is the authority; the groups in Table 5.2 state what is "
         "required and why. One installation detail is recorded here because "
         "it has a failure mode that is silent: the CUDA-enabled build of the "
         "deep-learning framework must be installed from its own package "
         "index before the remaining packages, since the default index "
         "resolves to a CPU-only build that then fails at run time rather "
         "than at install time.")
    data_table(doc, ["Category", "Software"],
               [[group, "; ".join(items)] for group, items in P.SOFTWARE_GROUPS],
               widths_for(0.30, 0.70), "5.2", "Software requirements")


# ==========================================================================
#  Chapter 6 — Expected Outcomes
# ==========================================================================

def expected_outcomes(doc: Document) -> None:
    chapter(doc, "6", "EXPECTED OUTCOMES")

    section(doc, "6.1", "Deliverables")
    body(doc,
         "The project is expected to produce seven artefacts, listed in "
         "Table 6.1. Each is stated so that its completion is checkable: an "
         "artefact that exists on disk, in a repository or in a release, "
         "rather than a description of work done.")
    data_table(doc, ["Deliverable", "Description"],
               [list(row) for row in P.DELIVERABLES],
               widths_for(0.24, 0.76), "6.1", "Expected deliverables")

    section(doc, "6.2", "Measurable Targets")
    body(doc,
         "Table 6.2 states the criteria the finished work is to be judged "
         "against. They are targets set in advance, not predictions of the "
         "result: a target that is missed is to be reported as missed, with "
         "the measured value and an analysis, rather than quietly restated "
         "afterwards to match whatever was obtained.")
    data_table(doc, ["Aspect", "Target", "How it is to be measured"],
               [list(row) for row in P.TARGETS],
               widths_for(0.19, 0.36, 0.45), "6.2",
               "Measurable targets for the completed project")

    section(doc, "6.3", "Future Scope")
    body(doc,
         "The following extensions are outside the twenty-week schedule and "
         "are recorded so that the boundary of this project is explicit "
         "rather than implied.")
    for heading, text in P.FUTURE_SCOPE:
        labelled(doc, heading + " —", text)


# ==========================================================================
#  Chapter 7 — Conclusion
# ==========================================================================

def conclusion(doc: Document) -> None:
    chapter(doc, "7", "CONCLUSION")
    body(doc,
         f"This synopsis proposes {P.TITLE_SHORT}: a camera-only system that "
         f"forecasts per-lane congestion one signal cycle ahead at a "
         f"junction carrying heterogeneous, non-lane-disciplined traffic, and "
         f"a reinforcement-learning controller that acts on that forecast. "
         f"The perception component fuses a frozen convolutional branch and a "
         f"frozen self-supervised transformer branch through gated "
         f"bidirectional cross-attention, models sixty timesteps with a "
         f"bidirectional recurrence and temporal attention, and reads out per "
         f"lane. The control component is a PPO agent trained in "
         f"microsimulation against a swept classical baseline.")
    body(doc,
         "Three commitments distinguish the proposal from a description of an "
         "architecture. The first is order: Phase I is a mandatory core that "
         "must converge before any refinement is written, which is a "
         "deliberate guard against an elaborate model with no experiments "
         "attached. The second is falsifiability: a count-only baseline and a "
         "linear probe are in the experiment from the beginning, the "
         "evaluation holds out whole cameras, every configuration is run at "
         "five seeds, and the classical control baseline is tuned before it "
         "is beaten. The third is that the fusion gate is reported as an "
         "artefact rather than kept as an internal detail, which is what "
         "makes the fusion claim checkable at all.")
    body(doc,
         "The risks are known and stated in Section 4.9 with responses "
         "attached, and the two most consequential — that appearance "
         "features may not beat vehicle counts, and that the forecast may "
         "not help the controller — are treated as measurements to be taken "
         "rather than outcomes to be avoided. The two claims are therefore "
         "kept separate, so that a null result on the perception question "
         "does not invalidate the control result or the prototype.")
    body(doc,
         "On completion the project is expected to deliver a curated "
         "dataset, a fine-tuned detector, a trained and exported forecasting "
         "model, a benchmarked controller, a working edge-to-server "
         "prototype in which no raw frame leaves the capture device, and a "
         "reproducibility package from which every reported number can be "
         "regenerated. Whether each component earns its place is a question "
         "the experiments are designed to answer honestly, in either "
         "direction.")


# ==========================================================================
#  Figures particular to this document
# ==========================================================================

def phase_figure(doc: Document) -> None:
    """Fig 4.4 — the build order, with the gate condition on each transition."""
    label_w = int(WIDTH * 0.22)
    widths = [label_w, WIDTH - label_w]
    rows = [
        [node("PHASE I\nmandatory", label_w, fill="DDE3F0", bold=True),
         node("Corpus + detector + labels  ->  CNN + ViT + standard "
              "cross-attention + BiLSTM  ->  per-lane head",
              widths[1])],
        [arrow(label_w),
         node("GATE:  the Phase I model trains to convergence and beats the "
              "linear probe on a held-out camera", widths[1], fill="F7E9E3")],
        [node("PHASE II\nstretch", label_w, fill="DDE3F0", bold=True),
         node("Gating replaces standard cross-attention  ->  temporal "
              "self-attention  ->  attention pooling  ->  ablation A-H, "
              "leave-one-camera-out at five seeds", widths[1])],
        [arrow(label_w),
         node("GATE:  every configuration runs from a flag, and the ablation "
              "table is generated from committed per-run results",
              widths[1], fill="F7E9E3")],
        [node("PHASE III\noptional", label_w, fill="DDE3F0", bold=True),
         node("SUMO + PPO arms  ->  thirty-seed benchmark against a swept "
              "Webster baseline  ->  ONNX export, edge node, control server, "
              "dashboard", widths[1])],
    ]
    doc.add(Table(rows, widths, borders=False, header_rows=0))


# ==========================================================================
#  entry point
# ==========================================================================

def build(out_path: Path) -> Path:
    doc = Document(
        font="Times New Roman", size=BODY, line=LINE_ONE_HALF,
        margin_left=inches(1.25), margin_right=inches(1.0),
        margin_top=inches(0.75), margin_bottom=inches(0.75),
        title=f"{P.TITLE} — {P.SUBTITLE}", authors=P.AUTHORS,
    )

    D.title_page(doc, subtitle=P.SUBTITLE, month=P.SUBMISSION_MONTH)
    D.certificate(doc)
    D.declaration(doc)
    D.table_of_contents(doc, P.TOC_ENTRIES)
    abstract(doc)
    introduction(doc)
    literature_review(doc)
    problem_and_objectives(doc)
    methodology(doc)
    requirements(doc)
    expected_outcomes(doc)
    conclusion(doc)
    D.references(doc, P.REFERENCES)

    doc.save(out_path)
    return out_path
