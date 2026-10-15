"""Render the synopsis report to `.docx`.

Formatting is taken from two authorities and neither is paraphrased here:

* the Department's **synopsis format** file supplies the front matter — the
  title page sequence, the certificate and declaration wording, and the table
  of contents; and
* the Department's **synopsis guideline** supplies the measurable rules — A4
  single-sided, 1.25 in left margin and 1 in right, 0.75 in top and bottom,
  Times New Roman throughout, 12 pt justified body at 1.5-line spacing,
  16 pt bold left-justified chapter numbers, 18 pt bold centred chapter
  titles, 14 pt bold section headings, 12 pt bold subsection headings, 10 pt
  bold captions, chapter-wise figure/table/equation numbering, and IEEE
  references.

Those constants live in one block below so a rule change is a one-line edit
rather than a search through the prose.

Run through `scripts/build_synopsis.py`; this module exposes `build()`.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8

use_utf8()

from scripts import synopsis_content as C
from scripts.docx_writer import (Cell, Document, Image, LINE_ONE_HALF,
                                 LINE_SINGLE, Para, Run, Table, inches)

# -- the guideline's numbers, in Word's own units --------------------------
BODY = 24            # 12 pt
CHAPTER_NUM = 32     # 16 pt bold, left
CHAPTER_TITLE = 36   # 18 pt bold, centred
SECTION = 28         # 14 pt bold, left
SUBSECTION = 24      # 12 pt bold, left
CAPTION = 20         # 10 pt bold
TITLE_FONT = "Bookman Old Style"   # title page only, per the format file

WIDTH = 11906 - inches(1.25) - inches(1.0)   # usable text width, twips


# ==========================================================================
#  paragraph helpers
# ==========================================================================

def body(doc: Document, text: str, *, first_indent: int = 0,
         after: int = 160) -> None:
    doc.add(Para([Run(text, size=BODY)], align="both", after=after,
                 indent_first=first_indent))


def chapter(doc: Document, number: str, title: str) -> None:
    doc.add(Para([Run(f"CHAPTER {number}", size=CHAPTER_NUM, bold=True)],
                 align="left", before=0, after=120, keep_next=True,
                 page_break_before=True, outline_level=0,
                 bookmark=f"ch{number}"))
    doc.add(Para([Run(title, size=CHAPTER_TITLE, bold=True)],
                 align="center", after=280, keep_next=True))


def front_heading(doc: Document, title: str, *, page_break: bool = True) -> None:
    """An unnumbered front-matter or back-matter heading."""
    doc.add(Para([Run(title, size=CHAPTER_TITLE, bold=True)], align="center",
                 after=280, keep_next=True, page_break_before=page_break,
                 outline_level=0, bookmark=title.split()[0].lower()))


def section(doc: Document, number: str, title: str) -> None:
    doc.add(Para([Run(f"{number}  {title}", size=SECTION, bold=True)],
                 align="left", before=200, after=120, keep_next=True,
                 outline_level=1))


def subsection(doc: Document, number: str, title: str) -> None:
    doc.add(Para([Run(f"{number}  {title}", size=SUBSECTION, bold=True)],
                 align="left", before=160, after=100, keep_next=True,
                 outline_level=2))


def caption(doc: Document, text: str, *, above: bool = False) -> None:
    doc.add(Para([Run(text, size=CAPTION, bold=True)], align="center",
                 line=LINE_SINGLE, before=80 if not above else 160,
                 after=200 if not above else 80))


def bullets(doc: Document, items, *, numbered: bool = False) -> None:
    num_id = 2 if numbered else 1
    for item in items:
        doc.add(Para([Run(item, size=BODY)], align="both", after=80,
                     numbering=(num_id, 0)))


def labelled(doc: Document, label: str, text: str) -> None:
    doc.add(Para([Run(label + "  ", size=BODY, bold=True), Run(text, size=BODY)],
                 align="both", after=100, indent_left=360, indent_hanging=360))


def equation(doc: Document, text: str, number: str) -> None:
    """An equation with a right-aligned, chapter-wise decimal number."""
    doc.add(Para(
        [Run(f"{text}\t({number})", size=BODY, italic=False)],
        align="left", line=LINE_SINGLE, before=120, after=160,
        indent_left=720, tabs=((WIDTH, "right", "dot"),)))


# ==========================================================================
#  table helpers
# ==========================================================================

def cell_para(text: str, *, bold: bool = False, size: int = 22,
              align: str = "left") -> Para:
    return Para([Run(text, size=size, bold=bold)], align=align,
                line=LINE_SINGLE, before=20, after=20)


def data_table(doc: Document, header: list[str], rows: list[list[str]],
               widths: list[int], number: str, title: str,
               *, aligns: list[str] | None = None) -> None:
    """A bordered data table with its caption above it, numbered chapter-wise."""
    caption(doc, f"Table {number}  {title}", above=True)
    aligns = aligns or ["left"] * len(header)
    head = [Cell([cell_para(text, bold=True, align="center")], width,
                 shaded=True)
            for text, width in zip(header, widths)]
    grid = [head]
    for row in rows:
        grid.append([Cell([cell_para(text, align=align)], width)
                     for text, width, align in zip(row, widths, aligns)])
    doc.add(Table(grid, widths))
    doc.add(Para([Run("", size=BODY)], line=LINE_SINGLE, after=180))


def node(text: str, width: int, *, fill: str = "F2F2F2", span: int = 1,
         bold: bool = False) -> Cell:
    return Cell([cell_para(text, bold=bold, size=20, align="center")], width,
                boxed=True, fill=fill, span=span)


def arrow(width: int, glyph: str = "▼", span: int = 1) -> Cell:
    return Cell([cell_para(glyph, size=20, align="center")], width, span=span)


def blank(width: int, span: int = 1) -> Cell:
    return Cell([cell_para("", size=16, align="center")], width, span=span)


# ==========================================================================
#  front matter
# ==========================================================================

def title_page(doc: Document, *, subtitle: str | None = None,
               month: str | None = None, kind: str = "A Synopsis") -> None:
    """The prescribed title page.

    `subtitle`, `month` and `kind` exist so the other documents in the same
    series — the Phase I proposal, and the Phase-I Progress Report whose
    guideline is a different document entirely — reuse this page rather than
    fork copies of the Department's front matter that would then drift from it.
    `kind` defaults to the format file's own wording, so a caller that does not
    pass it gets exactly the page the format file specifies.
    """

    def line(text: str, size: int, *, bold: bool = True, after: int = 100,
             font: str = TITLE_FONT) -> None:
        doc.add(Para([Run(text, size=size, bold=bold, font=font)],
                     align="center", line=LINE_SINGLE, after=after))

    emblem = C.ASSETS / "gehu-emblem.jpeg"
    wordmark = C.ASSETS / "gehu-wordmark.png"

    doc.add(Para([Run("", size=BODY)], line=LINE_SINGLE, after=0))
    line(kind, 32, after=60)
    line("On", 28, after=120)
    line(C.TITLE, 32, after=60 if subtitle else 200)
    if subtitle:
        line(subtitle, 24, after=200)
    line("Submitted in partial fulfilment of the requirement for the award of "
         "the degree of", 22, bold=False, after=140)
    line(C.DEGREE, 32, after=40)
    line("IN", 24, after=40)
    line(C.BRANCH, 28, after=20)
    line(f"({C.SPECIALISATION})", 22, bold=False, after=180)

    if emblem.exists():
        doc.add_image(emblem.read_bytes(), "jpeg", 1.4, 1.4,
                      name="Graphic Era Hill University emblem")

    line("Submitted by:", 24, after=100)
    for member in C.TEAM:
        line(f"{member.display}    {member.roll}    Section {member.section}",
             22, bold=False, after=50)

    line("Under the Guidance of", 24, after=60)
    line(C.MENTOR_NAME, 26, after=40)
    line(C.MENTOR_DESIGNATION, 22, bold=False, after=140)
    line(f"Project Team ID:  {C.TEAM_ID}", 24, after=180)

    if wordmark.exists():
        doc.add_image(wordmark.read_bytes(), "png", 4.6, 1.0,
                      name="Graphic Era Hill University wordmark")

    line(C.DEPARTMENT, 24, after=40)
    line(C.INSTITUTE, 26, after=40)
    line(C.PLACE, 24, after=40)
    line(month or C.SUBMISSION_MONTH, 24, after=0)


def certificate(doc: Document, *, kind: str = "project synopsis") -> None:
    front_heading(doc, "CERTIFICATE")
    names = ", ".join(f"{m.name} ({m.roll})" for m in C.TEAM)
    body(doc,
         f'This is to certify that the {kind} entitled "{C.TITLE}" '
         f"is being submitted by {names} for the partial fulfillment of the "
         f"requirement for the award of the degree of B.Tech C.S.E. "
         f"({C.SPECIALISATION}) in {C.DEPARTMENT}, {C.INSTITUTE}, Dehradun, "
         f"and is a record of their own work carried out under my supervision. "
         f"The matter embodied in the {kind} has not been submitted in any "
         f"other university or institution for the award of any degree.")
    doc.add(Para([Run("", size=BODY)], after=900))
    for text, size, bold in ((C.MENTOR_NAME, BODY, True),
                             (C.MENTOR_DESIGNATION, BODY, False),
                             (C.DEPARTMENT + ",", BODY, False),
                             (f"{C.INSTITUTE}, Dehradun, India.", BODY, False)):
        doc.add(Para([Run(text, size=size, bold=bold)], align="left",
                     line=LINE_SINGLE, after=40))


def declaration(doc: Document, *, kind: str = "project synopsis") -> None:
    front_heading(doc, "CANDIDATE'S DECLARATION")
    body(doc,
         f'We hereby certify that the work which is being presented in the '
         f'{kind} entitled "{C.TITLE}" is being submitted for the '
         f"partial fulfillment of the requirement for the award of the degree "
         f"of B.Tech C.S.E. ({C.SPECIALISATION}) in {C.DEPARTMENT}, "
         f"{C.INSTITUTE}, Dehradun, is our original work and has not been "
         f"submitted to any other university or institution for the award of "
         f"any degree or diploma.")
    doc.add(Para([Run("", size=BODY)], after=300))

    widths = [int(WIDTH * 0.42), int(WIDTH * 0.22), WIDTH - int(WIDTH * 0.42)
              - int(WIDTH * 0.22)]
    grid = [[Cell([cell_para(text, bold=True, align="center")], width, shaded=True)
             for text, width in zip(("Name of Student", "Roll Number",
                                     "Signature"), widths)]]
    for member in C.TEAM:
        grid.append([
            Cell([cell_para(member.display)], widths[0]),
            Cell([cell_para(member.roll, align="center")], widths[1]),
            Cell([cell_para(""), cell_para("")], widths[2]),
        ])
    doc.add(Table(grid, widths))


def table_of_contents(doc: Document,
                      entries: list[tuple[str, str, str]] | None = None) -> None:
    front_heading(doc, "TABLE OF CONTENTS")
    widths = [int(WIDTH * 0.14), int(WIDTH * 0.66),
              WIDTH - int(WIDTH * 0.14) - int(WIDTH * 0.66)]
    entries = entries or [
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
    grid = [[Cell([cell_para(text, bold=True, align="center")], width, shaded=True)
             for text, width in zip(("Sr. No.", "Description", "Page No."),
                                    widths)]]
    for number, description, anchor in entries:
        page = Para([Run("", size=22, field=f"PAGEREF {anchor} \\h")],
                    align="center", line=LINE_SINGLE, before=20, after=20)
        grid.append([
            Cell([cell_para(number, align="center")], widths[0]),
            Cell([cell_para(description)], widths[1]),
            Cell([page], widths[2]),
        ])
    doc.add(Table(grid, widths))
    doc.add(Para([Run("", size=BODY)], after=200))
    doc.add(Para([Run("Note: page numbers are field codes. Press Ctrl+A then "
                      "F9 in Word to refresh them after any edit.",
                      size=20, italic=True)], align="left", line=LINE_SINGLE))


# ==========================================================================
#  chapters
# ==========================================================================

def abstract(doc: Document, facts: C.Facts) -> None:
    best_config, best_f1 = facts.best_vision
    best_model, best_counts = facts.best_counts
    improvement = float(facts.control["improvement_percent"])

    front_heading(doc, "ABSTRACT")
    body(doc,
         "Urban traffic in India is heterogeneous and only weakly lane "
         "disciplined: two-wheelers filter between larger vehicles, "
         "auto-rickshaws and e-rickshaws occupy a lane share that no "
         "vehicle-count threshold captures, and fixed-time signal plans "
         "commissioned from a historical survey continue to run long after "
         "the demand that justified them has changed. Loop detectors and "
         "radar are the conventional remedy, and their per-intersection cost "
         "keeps them out of reach for most municipal deployments. Cameras, "
         "by contrast, are already installed.")
    body(doc,
         "This project proposes MFSTNet, a camera-only system that forecasts "
         "per-lane congestion 60 seconds ahead and hands that forecast to a "
         "reinforcement-learning signal controller. A fine-tuned YOLOv8s "
         "detector, trained over eight vehicle classes that include the "
         "auto-rickshaw, e-rickshaw and cattle absent from general-purpose "
         "datasets, produces per-lane counts. Frozen ResNet-50 and DINOv2 "
         "ViT-S/14 backbones supply complementary appearance features, which "
         "a gated bidirectional cross-attention module fuses into a single "
         "representation; the gate value is retained and reported as a "
         "research artefact rather than discarded as an internal detail. A "
         "BiLSTM with temporal self-attention models the 60-step observation "
         "window, and a per-lane head classifies each approach as LOW, "
         "MEDIUM or HIGH. A Proximal Policy Optimization agent then consumes "
         "these predictions inside a 16-dimensional observation vector and "
         "selects signal phases in a SUMO microsimulation of a four-way "
         "intersection.")
    body(doc,
         "The methodology is deliberately falsifiable. Every architectural "
         "component is disableable by configuration, giving an "
         "eight-configuration ablation that includes a linear probe as its "
         "floor; evaluation is leave-one-camera-out, so no reported score "
         "can be a memorised camera; and all results are reported as means "
         "with bootstrap 95% confidence intervals across folds and seeds. "
         f"On the {facts.n_folds}-fold, {facts.n_seeds}-seed pilot corpus the "
         f"strongest vision configuration reaches a macro-F1 of "
         f"{C.fmt(best_f1)}, while a count-sequence baseline "
         f"({best_model.replace('_', ' ')}) reaches {C.fmt(best_counts)}; the "
         "vision claim is therefore reported as open rather than "
         "established. On the control side, the trained policy reduces mean "
         f"vehicle waiting time by {improvement:.2f}% against a swept, "
         "best-configuration Webster baseline over 30 paired seeds "
         f"(p {C.fmt_p(facts.control['p'])}, Cohen's "
         f"d = {float(facts.control['cohens_d']):.2f}).")
    body(doc,
         "The expected outcome is a reproducible, licence-audited dataset, a "
         "trained and exported model, a complete ablation and control "
         "benchmark with raw per-run results committed alongside the code, "
         "and an edge-to-server prototype in which no raw video frame ever "
         "leaves the capture device.")
    doc.add(Para([Run("Keywords:  ", size=BODY, bold=True),
                  Run("traffic congestion forecasting, multimodal fusion, "
                      "vision transformer, cross-attention, reinforcement "
                      "learning, adaptive signal control, SUMO, edge "
                      "inference.", size=BODY)], align="both", before=120))


def introduction(doc: Document, facts: C.Facts) -> None:
    chapter(doc, "1", "INTRODUCTION")

    section(doc, "1.1", "Background")
    body(doc,
         "A signalised intersection allocates a scarce resource — green time "
         "— among competing approaches. The allocation rule in near-universal "
         "use in Indian cities is fixed-time control, in which cycle length "
         "and phase splits are computed once from a manual survey and then "
         "held constant. Webster's 1958 formulation remains the reference "
         "method for that computation and is still the honest baseline any "
         "adaptive scheme must beat, because it is what is actually deployed.")
    body(doc,
         "Adaptive control instead measures demand and reallocates green "
         "time in response to it. The measurement is the difficulty. "
         "Inductive loops must be cut into the carriageway and fail with the "
         "road surface; radar and lidar units are priced per approach. Both "
         "assume that vehicles arrive in lanes, which in unstructured "
         "traffic they do not: a stream of filtering two-wheelers registers "
         "as a small count while occupying the discharge capacity of a car.")
    body(doc,
         "Cameras avoid both problems. They are already mounted at a large "
         "fraction of Indian urban intersections for enforcement and "
         "surveillance, they observe the whole approach rather than a point, "
         "and modern detectors can be run on commodity hardware near the "
         "camera. What a camera does not provide directly is the quantity a "
         "controller needs, which is not the present state of the "
         "intersection but its state a minute from now — long enough for a "
         "phase decision made now to still be the right one when it takes "
         "effect.")

    section(doc, "1.2", "Motivation")
    body(doc,
         "Three observations motivate this work. First, a controller that "
         "reacts to present queues is always one decision behind the "
         "traffic; a controller supplied with a short-horizon forecast can "
         "act before a queue forms. Second, general-purpose detectors and "
         "datasets do not represent Indian road users — COCO contains no "
         "auto-rickshaw and no e-rickshaw class, and a detector that cannot "
         "name a vehicle cannot count it. Third, the published literature on "
         "multimodal fusion for traffic prediction reports architecture "
         "comparisons without the floor that a frozen-backbone study owes "
         "its reader: a linear probe on the same features. Where that floor "
         "is missing, an architectural gain and a feature-quality gain are "
         "indistinguishable.")
    body(doc,
         "This project therefore treats the ablation, not the architecture, "
         "as the deliverable of scientific interest. Every module is "
         "disableable by a configuration flag, the linear probe is a "
         "first-class configuration rather than an afterthought, and a "
         "negative or inconclusive result is reported and analysed rather "
         "than dropped.")

    section(doc, "1.3", "Significance and Need")
    body(doc,
         "The direct beneficiary is the municipal traffic authority that "
         "already owns camera infrastructure and cannot fund a sensor "
         "retrofit. The system requires no new roadside hardware, produces a "
         "control decision in under 50 ms, and degrades safely: if the "
         "forecast is unavailable the controller runs on raw counts, and if "
         "the network is lost for more than 10 seconds the edge device falls "
         "back to a locally embedded Webster controller. Neither fallback is "
         "an optional extra; both are specified behaviour and both are "
         "tested.")
    body(doc,
         "The design also takes privacy seriously as a constraint rather "
         "than a disclaimer. Frames are processed where they are captured "
         "and are never transmitted over the network or written to disk; "
         "only derived counts and predictions leave the edge device. A "
         "deployment therefore cannot become a video archive by accident.")

    section(doc, "1.4", "Organisation of the Synopsis")
    body(doc,
         "Chapter 2 reviews vehicle detection in unstructured traffic, "
         "spatio-temporal congestion prediction, multimodal fusion and "
         "reinforcement-learning signal control, and identifies the gap this "
         "work addresses. Chapter 3 states the problem precisely and lists "
         "the objectives. Chapter 4 describes the proposed methodology, "
         "including the system architecture, the corpus construction "
         "pipeline, the model, the controller, the evaluation protocol and "
         "the preliminary results obtained so far. Chapter 5 lists the "
         "hardware and software requirements, Chapter 6 the expected "
         "outcomes, and Chapter 7 concludes.")


def literature_review(doc: Document, facts: C.Facts) -> None:
    chapter(doc, "2", "LITERATURE REVIEW")

    section(doc, "2.1", "Vehicle Detection in Unstructured Traffic")
    body(doc,
         "Single-stage detectors dominate deployed traffic sensing because "
         "they meet real-time budgets on modest hardware. The YOLO family "
         "[5] is the usual choice, and its accuracy on Western traffic "
         "imagery is well established. The limitation is categorical rather "
         "than architectural: models pre-trained on COCO recognise car, "
         "motorcycle, bus and truck, and have no label for the "
         "auto-rickshaw, e-rickshaw, or cattle that occupy Indian "
         "carriageways. The India Driving Dataset [6] was assembled "
         "specifically to expose this, and demonstrates that models trained "
         "on structured-traffic imagery degrade sharply on unconstrained "
         "Indian roads. Most such datasets are nonetheless captured from a "
         "dashcam viewpoint, whereas an intersection controller sees an "
         "elevated, fixed CCTV view — a domain shift that the literature "
         "reports but rarely quantifies.")

    section(doc, "2.2", "Spatio-Temporal Congestion Prediction")
    body(doc,
         "Congestion forecasting is conventionally posed over sensor time "
         "series. Recurrent models [14] capture the temporal dependency, and "
         "gradient-boosted trees [15] remain a strong tabular baseline. Both "
         "consume counts or occupancies, which presupposes an instrumented "
         "network. Vision-based forecasting instead reads congestion from "
         "the image, which removes that presupposition but introduces "
         "another: appearance features must carry information about the "
         "*future* state, and whether they do is an empirical question that "
         "much of the literature assumes rather than tests. A count-only "
         "sequence model on the same footage is the control condition that "
         "settles it, and it is reported far less often than it should be.")

    section(doc, "2.3", "Multimodal Fusion of Convolutional and Transformer Features")
    body(doc,
         "Convolutional backbones [4] encode local texture with strong "
         "inductive bias; vision transformers [2] encode long-range "
         "relationships through self-attention [1]. Because the two are "
         "complementary, fusing them is a natural design, and the mechanisms "
         "for doing so — concatenation, one-directional cross-attention, "
         "bidirectional cross-attention, and gated combination — are all "
         "individually published. Self-supervised pre-training [3] has since "
         "changed the calculus: DINOv2 features transfer well enough that "
         "freezing both backbones and training only the fusion layers is a "
         "defensible design, which in turn makes the linear probe the "
         "mandatory floor. If a linear classifier on the same frozen "
         "features matches the fusion network, the fusion network is "
         "unjustified, and that is a result rather than a failure.")

    section(doc, "2.4", "Reinforcement Learning for Signal Control")
    body(doc,
         "Reinforcement learning for traffic signal control is a mature "
         "subfield; the survey of Wei et al. [13] catalogues both its "
         "progress and its recurring methodological weaknesses, chief among "
         "them baselines that are weaker than what is deployed and "
         "evaluations reported without variance. Proximal Policy "
         "Optimization [7] is the standard on-policy algorithm and is "
         "available in a maintained reference implementation [8]. SUMO [9] "
         "is the usual simulator; modelling non-lane-disciplined traffic "
         "requires its sublane extension, since the default model forbids "
         "the lateral filtering that defines the regime. On the baseline "
         "side, Webster's method [10] is sensitive to an assumed saturation "
         "flow whose published values for heterogeneous traffic span more "
         "than a factor of two [11], [12] — so quoting a single value "
         "silently chooses how strong the baseline will be.")

    section(doc, "2.5", "Comparative Summary")
    body(doc,
         "Table 2.1 places the four strands beside one another. The pattern "
         "is that each strand is individually well developed and the "
         "combination is not: detection work rarely carries through to "
         "control, forecasting work rarely reports the count-only control "
         "condition, fusion work rarely reports the linear-probe floor, and "
         "control work rarely sweeps its baseline.")

    widths = [int(WIDTH * 0.20), int(WIDTH * 0.30), int(WIDTH * 0.28)]
    widths.append(WIDTH - sum(widths))
    data_table(
        doc,
        ["Strand", "Representative work", "Strength", "Limitation for this problem"],
        [
            ["Detection", "YOLO family [5]; IDD [6]",
             "Real-time on modest hardware; India-specific classes exist",
             "Dashcam viewpoint dominates; CCTV-view performance seldom reported"],
            ["Forecasting", "LSTM [14]; XGBoost [15]",
             "Strong on sensor time series",
             "Assumes instrumented network; count-only control condition often omitted"],
            ["Fusion", "ViT [2]; DINOv2 [3]; cross-attention [1]",
             "Complementary local and global features; frozen backbones viable",
             "Linear-probe floor rarely reported, so gains are unattributable"],
            ["RL control", "PPO [7]; SB3 [8]; SUMO [9]",
             "Mature algorithms and simulators",
             "Weak or unswept baselines [10]-[12]; variance often unreported"],
        ],
        widths, "2.1", "Comparison of the four relevant research strands")

    section(doc, "2.6", "Research Gap")
    body(doc,
         "Three gaps follow, and the project is scoped to them rather than "
         "to a claim of architectural novelty, which the fusion literature "
         "would not support.")
    labelled(doc, "G1.",
             "Camera-only, forecast-driven control. Detection, forecasting "
             "and control are studied separately; an end-to-end path from a "
             "single existing camera to a signal decision, with no "
             "additional roadside sensing, is not established for "
             "unstructured traffic.")
    labelled(doc, "G2.",
             "The gate as a reported artefact. Gated fusion is published as "
             "a mechanism, but the gate value is treated as an internal "
             "activation. Exposing it — logging it per run, tracking it "
             "live, and analysing when it saturates — turns it into "
             "evidence about which modality the model is actually using.")
    labelled(doc, "G3.",
             "Density-stratified, leave-one-camera-out evaluation. Random "
             "splits over overlapping temporal windows leak, and a "
             "camera-hashed split can place an entire traffic regime in a "
             "single partition. Evaluating one held-out camera at a time, "
             "and reporting the fold mean with an interval, is the "
             "protocol that makes a cross-camera claim meaningful.")


def problem_and_objectives(doc: Document, facts: C.Facts) -> None:
    chapter(doc, "3", "PROBLEM STATEMENT & OBJECTIVES")

    section(doc, "3.1", "Problem Statement")
    body(doc,
         "Given only the video stream of a camera already installed at a "
         "signalised urban intersection carrying heterogeneous, weakly "
         "lane-disciplined traffic, predict the congestion level of each of "
         "the four approaches 60 seconds ahead, and use that prediction to "
         "select signal phases so that mean vehicle waiting time is lower "
         "than under the best-configured Webster plan — without installing "
         "any additional sensor, without transmitting any raw frame off the "
         "capture device, and without the system failing unsafely when "
         "either the forecast or the network becomes unavailable.")
    body(doc,
         "The problem decomposes into four coupled difficulties. Counting is "
         "not detection: a detector that scores well on mAP can still "
         "mis-count under occlusion, and the operating point that maximises "
         "detection accuracy is not the one that minimises counting error. "
         "Labelling is not free: congestion has no ground-truth sensor here, "
         "so labels must be derived from counts under a stated, "
         "per-camera-calibrated rule. Forecasting is not description: the "
         "model must predict a state it cannot see. And evaluation is easily "
         "circular: labels derived from detector counts cannot be used to "
         "judge baselines that also consume detector counts, which is why "
         "the test split must be human-verified while training data may "
         "remain automatically labelled.")

    section(doc, "3.2", "Objectives")
    body(doc, "The project pursues six objectives.")
    for tag, text in C.OBJECTIVES:
        labelled(doc, tag + ".", text)

    section(doc, "3.3", "Scope, Assumptions and Delimitations")
    body(doc,
         "The scope is a single four-way intersection observed by a single "
         "fixed camera, with four approaches and a two-phase signal plan. "
         "Lane geometry is placed by hand once per camera and reviewed, "
         "because automatically derived lane centres were measured to move "
         "by 0.164 of the frame width when the detector changed, which is "
         "large enough to reassign vehicles between approaches. The control "
         "policy is trained and evaluated in microsimulation; deployment on "
         "live signal hardware is explicitly out of scope for an academic "
         "project and would require authority approval and a safety case.")
    body(doc,
         "Two assumptions are stated rather than buried. The camera is "
         "assumed to be static, since the lane geometry is fixed at "
         "calibration. And the simulator is assumed to approximate "
         "heterogeneous traffic adequately once its sublane model is "
         "enabled; the residual gap between simulated and observed "
         "behaviour is declared in the results rather than treated as "
         "absent.")


def methodology(doc: Document, facts: C.Facts) -> None:
    chapter(doc, "4", "PROPOSED METHODOLOGY")

    # -- 4.1 architecture -------------------------------------------------
    section(doc, "4.1", "System Architecture")
    body(doc,
         "The system is organised into four subsystems that are developed "
         "independently and integrated late: a dataset and detection "
         "pipeline, the MFSTNet forecasting model, a reinforcement-learning "
         "signal controller, and an edge-to-server prototype that carries "
         "the first three into operation. Figure 4.1 shows the block "
         "diagram. The three tiers communicate only over the message "
         "contract shown; no tier reaches into another's internals, and the "
         "safety limits that clamp a signal command live outside the "
         "transport that carries it, so a command cannot become unsafe by "
         "arriving through a different path.")

    architecture_figure(doc)
    caption(doc, "Fig. 4.1  Block diagram of the proposed system")

    body(doc,
         "The coupling that is easy to miss is that MFSTNet's output is not "
         "only a prediction to be displayed; it is part of the controller's "
         "observation. The observation vector is 16-dimensional and carries "
         "the four per-lane congestion predictions at indices 11 to 14. When "
         "the forecast is unavailable those four indices are zeroed and the "
         "vector keeps its length — shortening it would silently change the "
         "meaning of every later index and invalidate the trained policy.")

    # -- 4.2 dataset ------------------------------------------------------
    section(doc, "4.2", "Dataset and Corpus Construction")
    body(doc,
         "The dataset is built in two parts. Part A is curated from "
         "permissively licensed public sources; Part B contributes 1,500 to "
         "3,000 annotated campus frames captured by the team. Every camera "
         "is declared in a manifest that records its location, viewpoint and "
         "how each property was determined — whether the footage was "
         "actually inspected or the property was inferred from a filename — "
         "so that a claim about coverage can be checked rather than "
         "asserted. Annotation covers eight classes: car, motorcycle, "
         "auto-rickshaw, e-rickshaw, bus, truck, bicycle and cattle.")
    body(doc,
         "The training corpus for the forecasting model is then constructed "
         "automatically from real footage. Figure 4.2 gives the pipeline. "
         "Clips are triaged for usability, lane centres are placed by hand "
         "and reviewed, the fine-tuned detector produces per-frame per-lane "
         "counts, and those counts are converted to congestion labels. The "
         "count file is retained separately from the label file, which "
         "means a threshold decision is a configuration change that "
         "re-derives labels in seconds rather than a reason to re-run the "
         "detector over hours of video.")

    corpus_figure(doc)
    caption(doc, "Fig. 4.2  Corpus construction pipeline")

    manifest = facts.manifest
    body(doc,
         f"Each training sample is a window of T = {manifest.get('T', 60)} "
         f"frames sampled every {manifest.get('step_s', 2)} s, labelled with "
         f"the congestion state {manifest.get('horizon_s', 60)} s beyond the "
         f"last observed frame, with successive windows starting "
         f"{manifest.get('stride_s', 30)} s apart. Because neighbouring "
         "windows share most of their frames, splits are cut by source clip "
         "and never by window; cutting by window would place near-duplicate "
         "samples on both sides of the split and inflate every score.")
    subsection(doc, "4.2.1", "Congestion Labelling")
    body(doc,
         "A raw vehicle count is a poor congestion signal in mixed traffic, "
         "because a count of twenty two-wheelers and a count of twenty "
         "buses describe different roads. Labels are therefore defined on "
         "passenger-car-unit weighted occupancy using published Indian "
         "equivalence values, and the LOW/MEDIUM/HIGH thresholds are "
         "calibrated per camera at the 33rd and 67th percentiles of that "
         "camera's own distribution and recorded in the corpus manifest. An "
         "unmapped vehicle class raises an error rather than defaulting to "
         "a weight of one, so a silently mis-weighted class cannot reach "
         "the labels.")

    # -- 4.3 detection ----------------------------------------------------
    section(doc, "4.3", "Vehicle Detection and Counting")
    body(doc,
         "YOLOv8s is fine-tuned on the joint dataset with a stratified "
         "70/15/15 split. Two facts govern how it is used. First, detection "
         "accuracy and counting accuracy are separate quantities and are "
         "verified separately: the operating confidence threshold is chosen "
         "by minimising counting error against human-annotated frames, not "
         "by maximising mAP. Second, cross-camera generalisation is far "
         "weaker than within-camera performance, and it is the cross-camera "
         "number that governs deployment; both are reported.")
    body(doc,
         "Counts are attributed to approaches through hand-placed lane "
         "centres. Points that fall too far from every centre are left "
         "unassigned rather than snapped to the nearest one, because "
         "snapping fabricates a count in a lane that had none.")

    # -- 4.4 model --------------------------------------------------------
    section(doc, "4.4", "MFSTNet: Model Design")
    body(doc,
         "Figure 4.3 shows the model. Both backbones are frozen, so their "
         "outputs are computed once per clip and cached to disk as "
         "half-precision arrays; only the fusion, temporal and head "
         "parameters are trained. This is what makes an eight-configuration, "
         "four-fold, five-seed sweep tractable on a single 6 GB laptop GPU: "
         "the cache reduces the full ablation from an estimated 12.3 hours "
         "on CPU to roughly 1.5 hours. The cache is keyed by a hash covering "
         "backbone identity, input resize and normalisation, and a mismatch "
         "raises rather than warns, because a stale cache trains perfectly "
         "normally and reports wrong numbers.")

    model_figure(doc)
    caption(doc, "Fig. 4.3  MFSTNet architecture")

    subsection(doc, "4.4.1", "Feature Extraction")
    body(doc,
         "ResNet-50 supplies a 2048-channel convolutional map and DINOv2 "
         "ViT-S/14 supplies 384-dimensional patch tokens. The two grids "
         "differ in size, and since the gate operates elementwise they must "
         "be aligned before fusion; both branches are therefore resampled "
         "onto a shared 7x7 grid, with the transformer's classification "
         "token dropped before reshaping.")

    subsection(doc, "4.4.2", "Gated Bidirectional Cross-Attention")
    body(doc,
         "Two cross-attention passes are computed: Z_A, in which the "
         "convolutional features query the transformer features, and Z_B, "
         "in which the transformer features query the convolutional "
         "features. A learned gate then combines them, as in equations (4.1) "
         "and (4.2), where sigma is the logistic function, W is a learned "
         "projection and the semicolon denotes concatenation along the "
         "feature axis.")
    equation(doc, "g = sigma( W [ Z_A ; Z_B ] )", "4.1")
    equation(doc, "F_fused = g . Z_A + (1 - g) . Z_B", "4.2")
    body(doc,
         "The gate g is retained and reported. A gate that sits at 0.5 with "
         "negligible variance is telling the reader that the model is "
         "averaging the two branches rather than selecting between them, "
         "which is an interpretable finding about the data and not a bug to "
         "be tuned away. Because it is a research artefact, the forward pass "
         "always returns it and no code path discards it.")

    subsection(doc, "4.4.3", "Temporal Modelling")
    body(doc,
         "The fused per-frame representations form a sequence of length T, "
         "which a two-layer bidirectional LSTM with 128 hidden units per "
         "direction encodes into a 256-dimensional sequence. Two layers of "
         "four-head temporal self-attention then relate distant timesteps "
         "directly, and attention pooling collapses the sequence to a single "
         "vector — a learned weighting over time, in place of taking the "
         "last hidden state and discarding the rest of the window.")

    subsection(doc, "4.4.4", "Per-Lane Prediction Head")
    body(doc,
         "A single globally pooled representation cannot produce four "
         "different per-lane answers, so pooling is per-lane: each "
         "approach's Voronoi region around its hand-placed centre defines a "
         "region of interest over the shared grid, and the head is applied "
         "to each region's pooled feature. This is why the feature cache "
         "must preserve spatial structure rather than store a single pooled "
         "vector per frame.")
    body(doc,
         "Training uses AdamW at a learning rate of 1e-4 with weight decay "
         "1e-4, cosine annealing, a batch size of 32, up to 100 epochs with "
         "early stopping at patience 15, and cross-entropy weighted by "
         "inverse class frequency. Residency is managed by accumulating "
         "micro-batches to the specified batch size rather than by reducing "
         "it, since the batch size is a specified hyperparameter and "
         "available memory is not a reason to change one.")

    subsection(doc, "4.4.5", "Ablation Design")
    body(doc,
         "Every component above is disableable by a configuration flag, "
         "giving the eight configurations in Table 4.1. No code is edited "
         "between configurations. Configuration H is the floor: frozen "
         "features, per-lane pooling, a mean over time, and a linear "
         "classifier. If H matches G, the architecture is unjustified on "
         "this data, and reporting that is the point of including it.")
    widths = [int(WIDTH * 0.09), int(WIDTH * 0.26)]
    widths.append(WIDTH - sum(widths))
    data_table(doc, ["Config", "Variant", "What it enables or removes"],
               [list(row) for row in C.ABLATION_ROWS], widths,
               "4.1", "Ablation configurations",
               aligns=["center", "left", "left"])

    # -- 4.5 controller ---------------------------------------------------
    section(doc, "4.5", "Reinforcement-Learning Signal Controller")
    body(doc,
         "The controller is a PPO agent acting on a four-way intersection "
         "modelled in SUMO and driven through TraCI, with the sublane model "
         "enabled so that lateral filtering is representable. The action "
         "space is 12 discrete actions, being the choice of phase "
         "(north-south or east-west) crossed with six green durations of "
         "10, 20, 30, 45, 60 and 90 seconds. The observation is the "
         "16-dimensional vector described in Section 4.1. The reward, "
         "equation (4.3), is the reduction in total lane waiting time "
         "between successive decisions, penalised for starving an approach "
         "and lightly penalised for switching, so that the agent is "
         "discouraged from churning without being forbidden to adapt.")
    equation(doc,
             "r_t = - (W_t - W_{t-1}) / 100  -  1.0 * n_starved  -  0.05 * 1[switch]",
             "4.3")
    body(doc,
         "Training uses a learning rate of 3e-4, 2048 steps per update, a "
         "minibatch of 64, a discount of 0.99, GAE lambda 0.95, a clip range "
         "of 0.2, an entropy coefficient of 0.01, and 500,000 timesteps. "
         "Minimum and maximum green times of 10 and 90 seconds and a 3-second "
         "all-red interval are enforced by actuation rather than learned, "
         "because a safety constraint that the agent could trade away is not "
         "a safety constraint.")
    body(doc,
         "The baseline deserves as much care as the policy. Webster's "
         "optimum cycle is sensitive to an assumed saturation flow whose "
         "published values for heterogeneous traffic span from 525 to 1283 "
         "PCU per hour per metre of approach width. Rather than choose one, "
         "the baseline sweeps the published range and the best-performing "
         "configuration becomes the baseline the learned policy must beat. "
         "Cycle clamping is logged and the clamp rate reported alongside "
         "the result: a Webster controller that clamps in every cycle has "
         "stopped computing anything and is a fixed-time plan under another "
         "name, and comparing against it would be misleading.")

    # -- 4.6 prototype ----------------------------------------------------
    section(doc, "4.6", "Edge-to-Server Prototype")
    body(doc,
         "The edge node runs detection and counting beside the camera and "
         "publishes only counts and predictions over MQTT; the control "
         "server hosts the policy and the exported model and returns signal "
         "commands. Quality of service differs by topic and is attached to "
         "the topic definition rather than accepted from the caller, so a "
         "caller cannot downgrade an emergency message: emergency traffic is "
         "QoS 2, counts and commands QoS 1, and predictions and heartbeats "
         "QoS 0. Two fallback paths are required behaviour. If model "
         "inference fails, the controller continues on raw counts with the "
         "forecast indices zeroed; if the broker is unreachable for more "
         "than 10 seconds, the edge node switches to a locally embedded "
         "Webster controller whose parameters were embedded at deployment "
         "time, since a fallback that activates because the network is down "
         "cannot fetch its own configuration.")
    body(doc,
         "The edge device for this project is a team laptop rather than an "
         "embedded accelerator, which is a budget decision and not a design "
         "one: the control logic and the message contract are unchanged. "
         "Every latency figure therefore states the host it was measured "
         "on, and laptop figures are labelled as proxy measurements.")

    # -- 4.7 evaluation ---------------------------------------------------
    section(doc, "4.7", "Evaluation Protocol")
    body(doc,
         "The forecasting model is evaluated leave-one-camera-out over the "
         "cameras contributing at least ten windows. Each fold holds out one "
         "camera entirely for testing, with the remainder in training and "
         "validation, so a reported score cannot be the model recognising a "
         "camera it has already seen. The headline figure is the mean across "
         "folds with a bootstrap 95% confidence interval computed by the "
         "percentile method over 10,000 resamples [16], quoted together "
         "with the number of folds, because an interval over four points is "
         "not an interval over thirty.")
    body(doc,
         "Every configuration is run at five seeds. A single-seed table "
         "ranks initialisations rather than architectures: on this corpus "
         "one configuration moved by more than 0.24 macro-F1 across seeds on "
         "a single fold, which is larger than the gap between most pairs of "
         "configurations. The evaluation harness therefore reports the "
         "seed spread beside every mean and warns when the spread exceeds "
         "the closest gap between two configurations, since those two are "
         "then not separated by the experiment.")
    body(doc,
         "Metrics are macro-F1 as the headline, with accuracy, weighted F1, "
         "quadratic weighted kappa and an ordinal error rate reported "
         "alongside, because congestion classes are ordered and confusing "
         "LOW with HIGH is not the same error as confusing LOW with MEDIUM. "
         "Control results are reported as mean vehicle waiting time over 30 "
         "paired evaluation seeds per method, with a bootstrap 95% "
         "confidence interval, a paired t-test at alpha = 0.05 and Cohen's "
         "d. Pre-registered disqualification rules apply: a method that "
         "completes fewer than 85% of trips, or a Webster arm that clamps in "
         "more than half of its cycles, is disqualified from the comparison "
         "and reported as such rather than quietly quoted.")
    body(doc,
         "All raw per-run results are committed as CSV, not only summary "
         "tables, and every table is generated from those CSVs by a "
         "committed script. Seeds are fixed across PyTorch, NumPy and the "
         "RL library, and a machine-checked claims file holds each scope "
         "claim as the sentence it would appear as in the report, paired "
         "with an assertion that is run against the corpus. A claim whose "
         "assertion fails blocks table generation; there is no override.")

    # -- 4.8 preliminary results ------------------------------------------
    section(doc, "4.8", "Preliminary Results")
    body(doc,
         "The pipeline is implemented end to end and has produced its first "
         "measurements on a pilot corpus. They are reported here in full, "
         "including the ones that do not support the vision hypothesis, "
         "because a synopsis that reports only the favourable half would "
         "misrepresent the state of the work. Table 4.2 gives the ablation "
         "across the eight configurations, and Table 4.3 gives the count-only "
         "baselines evaluated on the identical folds and seeds.")

    widths = [int(WIDTH * 0.12), int(WIDTH * 0.30), int(WIDTH * 0.30)]
    widths.append(WIDTH - sum(widths))
    rows = []
    for config, _variant, _desc in C.ABLATION_ROWS:
        row = facts.loco[config]
        rows.append([config,
                     f"{C.fmt(row['macro_f1_mean'])} "
                     f"[{C.fmt(row['macro_f1_lo'])}, {C.fmt(row['macro_f1_hi'])}]",
                     f"{C.fmt(row['accuracy_mean'])} "
                     f"[{C.fmt(row['accuracy_lo'])}, {C.fmt(row['accuracy_hi'])}]",
                     C.fmt(row["macro_f1_seed_spread"])])
    data_table(doc, ["Config", "Macro-F1  [95% CI]", "Accuracy  [95% CI]",
                     "Seed spread"],
               rows, widths, "4.2",
               f"Leave-one-camera-out ablation results "
               f"({facts.n_folds} folds x {facts.n_seeds} seeds, "
               f"{facts.loco['G']['n_runs']} runs per configuration)",
               aligns=["center", "center", "center", "center"])

    best_config, best_f1 = facts.best_vision
    best_model, best_counts = facts.best_counts
    widths = [int(WIDTH * 0.34), int(WIDTH * 0.33)]
    widths.append(WIDTH - sum(widths))
    baseline_rows = [[name.replace("_", " "),
                      C.fmt(row["macro_f1_mean"]),
                      C.fmt(row["accuracy_mean"])]
                     for name, row in sorted(
                         facts.baselines.items(),
                         key=lambda kv: -float(kv[1]["macro_f1_mean"]))]
    data_table(doc, ["Count-sequence baseline", "Macro-F1", "Accuracy"],
               baseline_rows, widths, "4.3",
               "Count-only baselines on the same folds and seeds",
               aligns=["left", "center", "center"])

    body(doc,
         f"Three readings follow, and each is stated as the evidence "
         f"supports it. First, the strongest vision configuration is "
         f"{best_config} at a macro-F1 of {facts.ci(best_config)}, while the "
         f"strongest count-only baseline "
         f"({best_model.replace('_', ' ')}) reaches "
         f"{C.fmt(best_counts)} on the same folds and seeds. On this corpus "
         f"the appearance features are therefore not yet earning their "
         f"place, and the vision claim is reported as open.")
    body(doc,
         f"Second, the full model and the linear probe cannot be separated. "
         f"Across {facts.gate['n_folds']} folds the mean difference between "
         f"them is {C.fmt(facts.gate['mean_difference'])} with a 95% "
         f"interval of [{C.fmt(facts.gate['ci_low'])}, "
         f"{C.fmt(facts.gate['ci_high'])}], against a minimum detectable "
         f"difference of {C.fmt(facts.gate['minimum_detectable_difference'])} "
         f"at this fold count. The verdict recorded by the analysis script is "
         f"“{facts.gate['verdict'].lower()}”, which is a statement "
         f"about the power of a four-fold experiment as much as about the "
         f"architecture.")
    body(doc,
         f"That mean requires its composition stated, because it is not "
         f"evenly made. Fold by fold the difference is "
         f"{facts.gate['difference_per_fold']}: the full model is ahead on "
         f"three of the four folds and loses the fourth by a margin larger "
         f"than the other three gains combined. That fourth fold holds out "
         f"the M6 Motorway, the one camera declared "
         f"“structured” against a target of "
         f"“mixed”, and it contributes 41.2% of the corpus "
         f"windows and 52.6% of every HIGH label. Averaged over the three "
         f"in-regime folds alone the sign reverses and the full model leads "
         f"by 0.0449; the reversal survives scoring only the classes present "
         f"in each fold, so it is a property of which camera is held out "
         f"rather than of which classes were evaluable. Neither aggregate "
         f"corrects the other — one measures transfer to an out-of-regime "
         f"camera and one measures generalisation within the target regime — "
         f"and this report quotes the four-fold figure as its headline "
         f"because that is the protocol registered in advance. The gate "
         f"itself sits at "
         f"{C.fmt(facts.loco['G']['gate_mean_mean'])} with a standard "
         f"deviation of {C.fmt(facts.loco['G']['gate_std_mean'])}: the model "
         f"is averaging its two branches, not selecting between them.")

    control = facts.control
    body(doc,
         f"Third, the control result is positive and holds up. Against the "
         f"swept, best-configuration Webster baseline at "
         f"{C.fmt(control['mean_b'], 3)} s mean waiting time, the learned "
         f"policy achieves {C.fmt(control['mean_a'], 3)} s over "
         f"{control['n_pairs']} paired seeds — an improvement of "
         f"{float(control['improvement_percent']):.2f}% with "
         f"p {C.fmt_p(control['p'])} and Cohen's "
         f"d = {float(control['cohens_d']):.2f}. This arm carries no "
         f"forecast, so it measures the value of learned phase selection "
         f"alone; the contribution of the forecast is a separate experiment "
         f"and is not claimed here.")
    body(doc,
         "The corpus is also honest about what it does not yet contain. No "
         "camera currently eligible for a fold is Indian, and the HIGH class "
         "is scarce in three of the four folds. Both conditions are encoded "
         "as failing assertions in the machine-checked claims file, which is "
         "why report-table generation is currently blocked; expanding the "
         "corpus with Part B campus footage is the work that clears them, "
         "and no claim about the Indian domain is made until it does.")
    body(doc,
         "One limitation is sharp enough to state on its own, because it "
         "bounds every number in this report. None of the four "
         "fold-eligible cameras is Indian. Three are Bangladeshi and one is "
         "a British motorway; the two Indian sources in the corpus contribute "
         "six and three windows, which is below the ten-window threshold a "
         "camera needs to be scored as a fold. Every result here is therefore "
         "evidence about generalisation across cameras in heterogeneous "
         "South Asian traffic, and is not evidence about generalisation to an "
         "Indian camera. That is a limitation of the evidence and not a "
         "reason to withhold it: the out-of-regime fold is the only "
         "external-domain test the project has, and removing it to improve "
         "an average would be the selective reporting this project's own "
         "rules forbid. A further consequence follows for one class in "
         "particular — the camera held out in fold 0 contains no HIGH "
         "windows at all, so that fold cannot evaluate the HIGH class, and "
         "its score must not be read as evidence either for or against "
         "performance on it.")


def requirements(doc: Document, facts: C.Facts) -> None:
    chapter(doc, "5", "HARDWARE AND SOFTWARE REQUIREMENTS")
    body(doc,
         "The requirements below are the ones this project actually uses; "
         "nothing is listed because it is conventional. Two entries are "
         "worth their explanation. Training runs locally on a 6 GB laptop "
         "GPU rather than on a cloud instance, which is possible only "
         "because the frozen backbones are evaluated once and cached — an "
         "uncached step at the specified batch size would push 1,920 frames "
         "through both backbones and would not fit. And the database is "
         "SQLite rather than a separate server, because the prototype stores "
         "a bounded history of counts and decisions and a database server "
         "would be infrastructure without a purpose. Table 5.1 lists the "
         "hardware and Table 5.2 the software.")

    section(doc, "5.1", "Hardware Requirements")
    widths = [int(WIDTH * 0.22), int(WIDTH * 0.36)]
    widths.append(WIDTH - sum(widths))
    data_table(doc, ["Component", "Specification", "Purpose in this project"],
               [list(row) for row in C.HARDWARE_ROWS], widths,
               "5.1", "Hardware requirements")

    section(doc, "5.2", "Software Requirements")
    widths = [int(WIDTH * 0.32)]
    widths.append(WIDTH - sum(widths))
    rows = [[group, "; ".join(items)] for group, items in C.SOFTWARE_GROUPS]
    data_table(doc, ["Category", "Software and pinned versions"], rows, widths,
               "5.2", "Software requirements")
    body(doc,
         "Versions are pinned in a committed requirements file, which is the "
         "authority; any version written in prose is a summary of it. The "
         "CUDA-enabled build of the deep-learning framework must be "
         "installed from its own package index before the remaining "
         "packages, because the default index resolves to a CPU-only wheel "
         "that then fails at run time rather than at install time.")


def expected_outcomes(doc: Document, facts: C.Facts) -> None:
    chapter(doc, "6", "EXPECTED OUTCOMES")
    body(doc,
         "The project is expected to deliver seven artefacts, each of which "
         "is measurable rather than descriptive. Table 6.1 lists them with "
         "the form each one takes on delivery.")
    widths = [int(WIDTH * 0.28)]
    widths.append(WIDTH - sum(widths))
    data_table(doc, ["Deliverable", "Description"],
               [list(row) for row in C.DELIVERABLES], widths,
               "6.1", "Expected deliverables")

    section(doc, "6.1", "Measurable Targets")
    body(doc,
         "The following targets are the criteria against which the finished "
         "work will be judged. They are stated in advance so that a result "
         "that misses them is visible as a miss rather than reframed after "
         "the fact.")
    targets = [
        "Detection: at least 0.85 mAP@0.5 on a held-out test split of the "
        "curated dataset, with cross-camera performance reported separately "
        "and without averaging the two.",
        "Counting: mean absolute per-frame counting error below 1.5 vehicles "
        "at the chosen operating point, verified against human-annotated "
        "frames rather than against detector output.",
        "Forecasting: the full model to exceed the linear probe by a margin "
        "larger than the seed spread, on a corpus large enough for that "
        "margin to be detectable. Where it does not, the finding is reported "
        "as an inconclusive comparison with its minimum detectable "
        "difference stated.",
        "Control: a statistically significant reduction in mean vehicle "
        "waiting time against the best-configured Webster baseline over 30 "
        "paired seeds, with the baseline's clamp rate disclosed. The "
        "preliminary benchmark already meets this at "
        f"{float(facts.control['improvement_percent']):.2f}%.",
        "Latency: model inference within 150 ms on server CPU through the "
        "exported graph, a control decision within 50 ms, and message "
        "delivery within 200 ms, each figure labelled with the host it was "
        "measured on.",
        "Reproducibility: every reported number regenerable from committed "
        "code, committed raw results and pinned dependencies on a clean "
        "machine, with seeds fixed and documented.",
    ]
    bullets(doc, targets, numbered=True)

    section(doc, "6.2", "Academic Outcome")
    body(doc,
         "The intended academic output is a conference submission. The "
         "defensible contribution is not a new fusion mechanism — those are "
         "published — but the combination of a camera-only forecast-to-control "
         "path, the gate reported as an artefact rather than hidden as an "
         "activation, and a leave-one-camera-out evaluation reported with "
         "the linear-probe floor beside it. A negative or inconclusive "
         "vision result, reported with its statistical power, remains a "
         "publishable contribution under that framing.")


def conclusion(doc: Document, facts: C.Facts) -> None:
    chapter(doc, "7", "CONCLUSION")
    body(doc,
         "This synopsis has proposed MFSTNet, a camera-only system that "
         "forecasts per-lane congestion 60 seconds ahead at a signalised "
         "urban intersection and uses that forecast to drive a "
         "reinforcement-learning signal controller. The proposal is built "
         "around infrastructure that Indian cities already own — fixed "
         "cameras — and requires no additional roadside sensing, no raw "
         "video to leave the point of capture, and no unsafe behaviour when "
         "either the forecast or the network fails.")
    body(doc,
         "The methodology has been described in full: a licence-audited "
         "two-part dataset with eight India-relevant vehicle classes; "
         "PCU-weighted, per-camera-calibrated congestion labels derived from "
         "detector counts; a gated bidirectional fusion of frozen "
         "convolutional and self-supervised transformer features with "
         "per-lane region pooling and temporal attention; a PPO controller "
         "whose observation carries the forecast in a fixed 16-dimensional "
         "contract; and an edge-to-server prototype with two required "
         "fallback paths.")
    body(doc,
         "What distinguishes the plan is the evaluation rather than the "
         "architecture. Every module is disableable by configuration so that "
         "an eight-way ablation runs without a code edit; the linear probe "
         "is included as the floor that a frozen-backbone study owes its "
         "reader; evaluation is leave-one-camera-out so that no score is a "
         "memorised camera; and all results are reported as means with "
         "bootstrap confidence intervals across folds and seeds, with raw "
         "per-run data committed alongside the code.")
    control = facts.control
    best_config, best_f1 = facts.best_vision
    body(doc,
         f"Preliminary results are consistent with that discipline. The "
         f"control half is already positive: a "
         f"{float(control['improvement_percent']):.2f}% reduction in mean "
         f"waiting time against a swept Webster baseline over "
         f"{control['n_pairs']} paired seeds, at "
         f"p {C.fmt_p(control['p'])}. The vision half is not yet: "
         f"the best configuration reaches {C.fmt(best_f1)} macro-F1 against "
         f"{C.fmt(facts.best_counts[1])} for a count-only sequence model, "
         f"and the full model cannot presently be separated from the linear "
         f"probe at four folds. Those findings are reported rather than "
         f"deferred, and they set the remaining work: expand the corpus with "
         f"Indian campus footage so that the domain claim can be made "
         f"honestly, raise the number of evaluable cameras so that the "
         f"architecture comparison has the power to resolve, and complete "
         f"the forecast-carrying control arm so that the value of the "
         f"forecast is measured rather than assumed.")
    body(doc,
         "The expected significance is a low-cost, privacy-preserving "
         "adaptive signal control path for unstructured urban traffic, "
         "delivered together with the evidence needed to judge whether each "
         "of its parts is earning its place.")


def references(doc: Document, entries: tuple[str, ...] | None = None) -> None:
    front_heading(doc, "REFERENCES")
    for index, text in enumerate(entries or C.REFERENCES, start=1):
        doc.add(Para([Run(f"[{index}]\t{text}", size=BODY)], align="both",
                     after=100, indent_left=560, indent_hanging=560,
                     tabs=(560,)))


# ==========================================================================
#  figures
# ==========================================================================

def architecture_figure(doc: Document) -> None:
    """Fig 4.1 — three tiers, drawn as boxed cells in a borderless table."""
    third = WIDTH // 3
    widths = [third, third, WIDTH - 2 * third]
    rows = [
        [node("EDGE TIER  (team laptop, at the camera)", third, fill="DDE3F0",
              bold=True),
         node("SERVER TIER  (FastAPI + ONNX + PPO)", third, fill="DDE3F0",
              bold=True),
         node("PRESENTATION TIER  (React dashboard)", widths[2], fill="DDE3F0",
              bold=True)],
        [arrow(third), arrow(third), arrow(widths[2])],
        [node("Fixed CCTV camera\nframes never leave this host", third),
         node("MFSTNet (ONNX)\nper-lane congestion, 60 s ahead", third),
         node("Live panel\ncounts, predictions, gate value", widths[2])],
        [arrow(third), arrow(third), arrow(widths[2])],
        [node("YOLOv8s detection\n8 India-relevant classes", third),
         node("PPO policy\n16-dim observation, 12 actions", third),
         node("Benchmark panel\ncommitted CSV: split, n, date, commit",
              widths[2])],
        [arrow(third), arrow(third), blank(widths[2])],
        [node("Per-lane counting\nhand-placed lane centres", third),
         node("SignalGuard\nmin/max green, all-red, clamping", third),
         blank(widths[2])],
        [arrow(third), arrow(third, "▲"), blank(widths[2])],
        [node("Local Webster fallback\narms if the broker is silent > 10 s",
              third, fill="F7E9E3"),
         node("SQLite\nbounded history of counts and decisions", third),
         blank(widths[2])],
    ]
    doc.add(Table(rows, widths, borders=False, header_rows=0))
    doc.add(Table(
        [[node("MQTT contract   —   emergency QoS 2  │  counts and "
               "commands QoS 1  │  predictions and heartbeat QoS 0",
               WIDTH, fill="EFEFEF", bold=True)]],
        [WIDTH], borders=False, header_rows=0))


def corpus_figure(doc: Document) -> None:
    """Fig 4.2 — the corpus pipeline, one stage per row."""
    stages = [
        ("Source clips", "public curated footage (Part A) + campus capture (Part B)"),
        ("Triage", "reject clips shorter than the window span or too degraded"),
        ("Lane geometry", "centres placed by hand, then reviewed — never auto-derived"),
        ("Detection", "fine-tuned YOLOv8s → per-frame, per-lane counts"),
        ("Counts file", "threshold-independent, so relabelling costs seconds"),
        ("Labelling", "PCU-weighted occupancy, per-camera p33/p67 thresholds"),
        ("Audit", "fails loudly on any inconsistency; nothing proceeds past it"),
        ("Feature cache", "frozen backbones evaluated once, stored fp16 per clip"),
        ("Split", "leave-one-camera-out, cut by source clip — never by window"),
    ]
    label_w = int(WIDTH * 0.30)
    widths = [label_w, WIDTH - label_w]
    rows = []
    for index, (name, detail) in enumerate(stages):
        rows.append([node(name, label_w, fill="DDE3F0", bold=True),
                     node(detail, widths[1])])
        if index < len(stages) - 1:
            rows.append([arrow(label_w), blank(widths[1])])
    doc.add(Table(rows, widths, borders=False, header_rows=0))


def model_figure(doc: Document) -> None:
    """Fig 4.3 — MFSTNet, with the two frozen branches shown side by side."""
    half = WIDTH // 2
    widths = [half, WIDTH - half]
    rows = [
        [node("Frame sequence   —   T = 60 frames", WIDTH, fill="DDE3F0",
              bold=True, span=2), blank(0)],
        [arrow(half), arrow(widths[1])],
        [node("ResNet-50  (frozen)\n2048 x 7 x 7", half, fill="EAF2EA"),
         node("DINOv2 ViT-S/14  (frozen)\n384 x 16 x 16, CLS dropped",
              widths[1], fill="EAF2EA")],
        [arrow(half), arrow(widths[1])],
        [node("Aligned onto a shared 7 x 7 grid   —   the gate is "
              "elementwise, so the grids must match", WIDTH, span=2), blank(0)],
        [arrow(half), arrow(widths[1])],
        [node("Z_A  =  CNN queries ViT", half),
         node("Z_B  =  ViT queries CNN", widths[1])],
        [arrow(half), arrow(widths[1])],
        [node("Gated fusion:   g = sigma(W[Z_A ; Z_B]),   "
              "F = g·Z_A + (1-g)·Z_B\nthe gate value is logged, "
              "tracked and reported", WIDTH, fill="F7E9E3", span=2), blank(0)],
        [arrow(half), arrow(widths[1])],
        [node("BiLSTM   —   2 layers, hidden 128, bidirectional", WIDTH,
              span=2), blank(0)],
        [arrow(half), arrow(widths[1])],
        [node("Temporal self-attention   —   2 layers, 4 heads", WIDTH,
              span=2), blank(0)],
        [arrow(half), arrow(widths[1])],
        [node("Attention pooling over time  +  per-lane ROI pooling", WIDTH,
              span=2), blank(0)],
        [arrow(half), arrow(widths[1])],
        [node("Per-lane head   —   LOW / MEDIUM / HIGH for N, S, E, W at "
              "t + 60 s", WIDTH, fill="DDE3F0", bold=True, span=2), blank(0)],
    ]
    doc.add(Table(rows, widths, borders=False, header_rows=0))


# ==========================================================================
#  entry point
# ==========================================================================

def build(out_path: Path) -> Path:
    facts = C.load_facts()
    doc = Document(
        font="Times New Roman", size=BODY, line=LINE_ONE_HALF,
        margin_left=inches(1.25), margin_right=inches(1.0),
        margin_top=inches(0.75), margin_bottom=inches(0.75),
        title=C.TITLE, authors=C.AUTHORS,
    )

    title_page(doc)
    certificate(doc)
    declaration(doc)
    table_of_contents(doc)
    abstract(doc, facts)
    introduction(doc, facts)
    literature_review(doc, facts)
    problem_and_objectives(doc, facts)
    methodology(doc, facts)
    requirements(doc, facts)
    expected_outcomes(doc, facts)
    conclusion(doc, facts)
    references(doc)

    doc.save(out_path)
    return out_path
