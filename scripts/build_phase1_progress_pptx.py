"""Build the **Phase-I Progress Report – 1** presentation.

The spoken form of `scripts/build_phase1_progress_docx.py`, and scoped the same
way: the problem, the literature, the gap. No methodology slides, no results,
no architecture walkthrough — those belong to the documents that follow, and a
deck that shows them is answering a different brief than the one the report
answers.

The structure follows how the report has to be *defended* rather than how it is
printed. A reviewer of a Phase-I progress report asks three questions in order:
is the problem real, do you know the literature, and is there anything left to
do. The deck answers them in that order, and spends its middle third on the
literature because that is where the guideline puts its weight.

Identity, palette and the `Deck` helper come from the same places as the other
two decks, so all three read as one project. Citations are rendered from the
same verified record the report uses, so a number on a slide and a number in
the report cannot disagree.
"""

from __future__ import annotations

import argparse
import sys
from math import ceil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

from pptx.util import Inches, Pt  # noqa: E402

from scripts import phase1_progress_content as P  # noqa: E402
from scripts.build_review_pptx import (ACCENT, AMBER, BODY, BODY_ADVANCE,  # noqa: E402
                                       CONTENT_W, CREAM, Deck, DEEP,
                                       DIM_CREAM, FAINT, GOOD, INK, MARGIN,
                                       MONO, MONO_ADVANCE, MUTED, PANEL, W,
                                       WARN, export_pdf)
from scripts.build_synopsis_pptx import BODY_Y, panel_height  # noqa: E402

#: Slides before the reference list. The reference slides are counted from the
#: list itself, below, so TOTAL follows the bibliography rather than being
#: restated whenever a work is added.
BODY_SLIDES = 15

HALF = Inches(5.7)
RIGHT_X = Inches(7.1)

#: `Deck.table` draws each cell into a fixed-height box and does not grow it,
#: so a cell that needs a second line is drawn over the rule beneath it. These
#: are the per-point horizontal advances of the two typefaces, used to keep
#: every cell on one line.
#:
#: The divisor is 9.5 because that is the size `MONO_ADVANCE` and
#: `BODY_ADVANCE` were measured at. Dividing by 11 — which a sibling deck
#: does — understates the advance by about 16%, so a cell that was truncated to
#: "fit" still wrapped onto the row below. That is a defect only a rendered
#: slide shows.
MEASURED_AT_PT = 9.5
MONO_PER_PT = MONO_ADVANCE / MEASURED_AT_PT
BODY_PER_PT = BODY_ADVANCE / MEASURED_AT_PT



#: `Deck.table` insets each cell by this much before drawing its text box.
CELL_INSET = Inches(0.1)

#: And the text box itself carries python-pptx's default left and right
#: internal margin, 0.05 in each. Omitting this was why cells that the
#: arithmetic said fit still wrapped by a word.
TEXTBOX_INSET = Inches(0.1)

#: Measured advances are an average over the prose actually used, so a cell at
#: exactly the computed limit is a coin toss. Five per cent back from the edge
#: costs a word and removes the class of defect.
SAFETY = 0.95


#: Reference-slide layout, measured rather than chosen. `reference_pages`
#: packs the entries into as many slides as they need, so adding a work moves
#: the boundary instead of tripping the guard at the foot of
#: `slide_references`. The constants are the ones that guard checks against.
REF_SIZE = 8.5
REF_COLUMN_W = Inches(5.95)
REF_LINE_H = Inches(0.142)
REF_GAP = Inches(0.05)
REF_TOP_FIRST = Inches(2.52)
REF_TOP_CONT = Inches(2.12)
REF_BOTTOM = Inches(0.3)


def reference_lines(text: str) -> int:
    usable = (REF_COLUMN_W - TEXTBOX_INSET) / Inches(1) * SAFETY
    return max(1, ceil(len(text) * BODY_PER_PT * REF_SIZE / usable))


def reference_height(text: str) -> int:
    return reference_lines(text) * REF_LINE_H + REF_GAP


def reference_pages(entries):
    """Entries grouped into slides, each within one slide's two columns."""
    pages, page, used = [], [], 0
    for entry in entries:
        top = REF_TOP_FIRST if not pages else REF_TOP_CONT
        # Two columns, so a slide holds twice one column's height. Nine tenths
        # of it: the split between the columns is never exactly even, and the
        # guard measures the taller one.
        budget = (Inches(7.5) - top - REF_BOTTOM) * 2 * 0.9
        height = reference_height(f"[{entry[0]}]  {entry[1]}")
        if page and used + height > budget:
            pages.append(page)
            page, used = [], 0
        page.append(entry)
        used += height
    if page:
        pages.append(page)
    return pages


REFERENCE_PAGES = reference_pages(P.reference_list())
TOTAL = BODY_SLIDES + len(REFERENCE_PAGES)


def cell(text: str, width, *, size: float = 11, font: str = BODY) -> str:
    """`text`, refused if it cannot set on one line of a cell `width` wide.

    A guard, not a truncator. `Deck.table` draws each cell into a fixed box and
    does not grow it, so an over-long cell is drawn over the rule beneath it —
    and shortening it with an ellipsis, which an earlier version did, trades a
    collision for text that reads as a rendering fault. Raising instead means
    the fix is a shorter string in `phase1_progress_content`, which is where
    the wording belongs.

    The two insets are both real: `Deck.table` insets the cell before placing a
    text box, and the text box has its own left and right internal margin.
    """
    per_char = (MONO_PER_PT if font == MONO else BODY_PER_PT) * size
    usable = (width - CELL_INSET - TEXTBOX_INSET) / Inches(1) * SAFETY
    limit = int(usable / per_char)
    if len(text) > limit:
        raise ValueError(
            f"table cell {text!r} is {len(text)} characters and about {limit} "
            f"fit on one line at {size} pt in a {width / Inches(1):.2f} in "
            "column. Shorten the string or widen the column.")
    return text


# ==========================================================================
#  slides
# ==========================================================================

def slide_title(deck: Deck) -> None:
    slide = deck._blank(DEEP)
    deck.slides.append(slide)

    deck.text(slide, MARGIN, Inches(0.52), Inches(12), Inches(0.3),
              size=10.5, font=MONO, colour=AMBER, bold=True)[3].text = (
        f"MAJOR PROJECT  ·  PHASE-I PROGRESS REPORT – 1  ·  "
        f"B.TECH {P.BRANCH}  ·  PROJECT TEAM ID  {P.TEAM_ID}")

    _, frame, para, run = deck.text(slide, MARGIN, Inches(1.02), Inches(12.0),
                                    Inches(1.7), size=34, colour=CREAM,
                                    bold=True, spacing=0.95)
    run.text = "MFSTNet — Multimodal Spatio-Temporal\nCongestion Forecasting for "
    extra = para.add_run()
    extra.text = "Adaptive Traffic Signal Control"
    extra.font.bold = True
    extra.font.size = Pt(34)
    extra.font.color.rgb = AMBER
    extra.font.name = BODY

    _, _, _, run = deck.text(slide, MARGIN, Inches(2.68), Inches(9.6),
                             Inches(0.34), size=11, font=MONO, colour=AMBER)
    run.text = f"working name:  {P.WORKING_NAME}"

    _, _, _, run = deck.text(slide, MARGIN, Inches(3.02), Inches(11.4),
                             Inches(0.7), size=13, colour=DIM_CREAM,
                             spacing=1.35)
    run.text = ("Progress Report – 1 covers the problem, the literature and "
                "the research gap. It reports no measurement: none has been "
                "made yet, and a target stated as a result is the overclaim "
                "this project's reporting rules exist to prevent.")

    x = MARGIN
    card = Inches(2.86)
    for member in P.TEAM:
        deck.rect(slide, x, Inches(3.98), card, Inches(1.16),
                  fill=PANEL, line=None)
        deck.text(slide, x + Inches(0.22), Inches(4.14), card - Inches(0.4),
                  Inches(0.22), size=9, font=MONO, colour=ACCENT,
                  bold=True)[3].text = (
            "TEAM LEAD" if member.lead else f"SECTION {member.section}")
        deck.text(slide, x + Inches(0.22), Inches(4.42), card - Inches(0.4),
                  Inches(0.3), size=14, colour=INK, bold=True)[3].text = (
            member.name)
        deck.text(slide, x + Inches(0.22), Inches(4.76), card - Inches(0.4),
                  Inches(0.24), size=10, font=MONO, colour=MUTED)[3].text = (
            f"{member.roll}   ·   {member.section}")
        x += card + Inches(0.23)

    deck.rule(slide, MARGIN, Inches(5.44), CONTENT_W, colour=FAINT)
    _, _, para, run = deck.text(slide, MARGIN, Inches(5.62), Inches(9.0),
                                Inches(0.3), size=12, colour=DIM_CREAM)
    run.text = "Under the guidance of  "
    mentor = para.add_run()
    mentor.text = f"{P.MENTOR_NAME}, {P.MENTOR_DESIGNATION}"
    mentor.font.bold = True
    mentor.font.size = Pt(12)
    mentor.font.color.rgb = CREAM
    mentor.font.name = BODY

    for offset, text, size, colour in (
            (0.0, P.DEPARTMENT, 12.5, CREAM),
            (0.28, P.INSTITUTE, 12.5, CREAM),
            (0.58, f"{P.PLACE}   ·   {P.SUBMISSION_MONTH}", 11, DIM_CREAM)):
        deck.text(slide, MARGIN, Inches(6.14 + offset), Inches(9.0),
                  Inches(0.28), size=size, colour=colour,
                  bold=colour is CREAM)[3].text = text

    deck.notes(slide, (
        "Open by naming what this document is and is not. It is Progress "
        "Report – 1 for Phase I: problem, literature, gap. It is not a "
        "results report, and there is no measurement in it, because the "
        "measurements have not been taken. If asked why the deck has no "
        "accuracy figure, that is the answer, and it is the correct one."))


def slide_agenda(deck: Deck) -> None:
    slide = deck.content(2, "AGENDA",
                         ("Three questions, ", "in the order they get asked"),
                         total=TOTAL)
    items = (
        ("Is the problem real?", "slides 3-6  ·  what a fixed-time signal "
                                "cannot do, and why the stream makes it worse"),
        ("Do we know the literature?", "slides 7-12  ·  four settled bodies of "
                                       f"work, {len(P.SURVEY_TABLE)} papers "
                                       "compared"),
        ("Is anything left to do?", "slides 13-15  ·  the gap, derived from "
                                    "the survey rather than asserted"),
    )
    deck.bullets(slide, MARGIN, BODY_Y, Inches(6.4), items, size=13,
                 gap=Inches(0.86))

    note = ("Every citation on every slide resolves to a record that was "
            "retrieved from a bibliographic index, not recalled.")
    height = panel_height((
        ("Five sections, no more", "the guideline prescribes exactly these"),
        ("1  Introduction", "nine named parts"),
        ("2  Literature Survey", "ten themed subsections"),
        ("3  Literature Survey Table",
         f"{len(P.SURVEY_TABLE)} papers, seven columns"),
        ("4  Research Gap", "five questions answered"),
        ("References", f"{len(P.reference_list())} entries, all cited"),
    ), HALF, note)
    deck.panel(slide, RIGHT_X, BODY_Y, HALF, height, "What this report is",
               (("Five sections, no more", "the guideline prescribes exactly these"),
                ("1  Introduction", "nine named parts"),
                ("2  Literature Survey", "ten themed subsections"),
                ("3  Literature Survey Table",
                 f"{len(P.SURVEY_TABLE)} papers, seven columns"),
                ("4  Research Gap", "five questions answered"),
                ("References", f"{len(P.reference_list())} entries, all cited")),
               footnote=note)

    deck.notes(slide, (
        "The agenda mirrors how the report is structured, and the panel is "
        "there so the examiner can see the report answers the guideline "
        "section by section. Point at the last row: every reference is cited "
        "in the text, both directions checked by a script."))


def slide_problem(deck: Deck) -> None:
    slide = deck.content(3, "INTRODUCTION",
                         ("A signal allocates green ",
                          "from a survey taken once"),
                         lead="Fixed-time control computes cycle length and "
                              "phase splits from a manual count, then holds "
                              "them for years.", total=TOTAL)
    items = (
        ("The plan is right on average",
         "and therefore wrong most of the time — green is held on an empty "
         "approach while a saturated one waits"),
        ("Re-timing needs a new survey",
         "so plans age; the method itself dates from 1958 and is still the "
         "basis of Indian practice"),
        ("The saturation flow it needs is not a constant",
         "published values for one intersection differ about two-fold with "
         "the PCU convention alone"),
    )
    deck.bullets(slide, MARGIN, BODY_Y, Inches(6.4), items, size=12.5,
                 gap=Inches(0.92))

    note = ("A camera that is already mounted, already powered and already "
            "pointed at the stop line is the one sensor that can be used "
            "without installing anything.")
    rows = (("Cameras already exist", "installed for enforcement, at most junctions"),
            ("Loops and probes do not", "and cost money the deployment does not have"),
            ("A decision acts on the future", "the next 30-90 s, not the present queue"),
            ("So forecast, do not measure", "one cycle ahead is the useful horizon"))
    deck.panel(slide, RIGHT_X, BODY_Y, HALF, panel_height(rows, HALF, note),
               "Why camera-only", rows, footnote=note)

    deck.notes(slide, (
        "Three facts, and the third is the one examiners find interesting: the "
        "baseline's own central parameter is uncertain under heterogeneous "
        "traffic. That is why the project sweeps the published range and takes "
        "the baseline's best configuration as the thing to beat, rather than "
        "picking one value and beating a badly-tuned plan."))


def slide_stream(deck: Deck) -> None:
    slide = deck.content(4, "INTRODUCTION",
                         ("The stream is not ",
                          "the stream the method assumes"),
                         lead="Heterogeneous, non-lane-disciplined, and "
                              "Indian practice already says counting vehicles "
                              "measures the wrong thing.", total=TOTAL)
    rows = (
        ("Mixed modes on one approach",
         "two-wheelers, auto-rickshaws, e-rickshaws, cars, buses, trucks"),
        ("Different road space, different discharge",
         "a bus and a two-wheeler are not one vehicle each"),
        ("No lane discipline",
         "queue geometry does not follow the markings on the road"),
        ("Pedestrians and animals in the carriageway",
         "on many of the roads this targets"),
    )
    deck.panel(slide, MARGIN, BODY_Y, HALF, panel_height(rows, HALF),
               "What arrives at the junction", rows)

    items = (
        ("So congestion is defined on occupancy",
         "passenger-car-unit weighted, not a raw count — the Indian Highway "
         "Capacity Manual publishes the equivalences for this reason"),
        ("And thresholds are calibrated per camera",
         "a threshold correct at one viewpoint is arbitrary at another"),
        ("And whole cameras are held out",
         "a random split over overlapping windows lets a model recognise a "
         "camera it has already seen and call that generalisation"),
    )
    deck.bullets(slide, RIGHT_X, BODY_Y, Inches(5.9), items, size=12,
                 gap=Inches(1.0))

    deck.notes(slide, (
        "This slide is the bridge from a traffic-engineering problem to a "
        "machine-learning one. Each item on the right is a design decision "
        "forced by the item on the left — that is the connection worth making "
        "aloud, because it is what separates a considered design from an "
        "assembled one."))


def slide_statement(deck: Deck) -> None:
    slide = deck.content(5, "INTRODUCTION", ("The problem ", "statement"),
                         lead="Every clause is a constraint, not a "
                              "preference.", total=TOTAL)
    _, _, _, run = deck.text(slide, MARGIN, BODY_Y, CONTENT_W, Inches(1.2),
                             size=16, colour=INK, spacing=1.3)
    run.text = (
        "Given only the video of a single fixed camera already installed at a "
        "signalised urban intersection, predict the congestion level of each "
        "approach lane sixty seconds ahead — accurately enough for a "
        "controller to act on, under heterogeneous non-lane-disciplined "
        "traffic, without a raw frame ever leaving the device.")

    rows = (("A single camera", "several per junction is not deployable here"),
            ("Per-lane output", "a controller allocates green to an approach"),
            ("Sixty seconds ahead", "a forecast of the present is a measurement"),
            ("No raw frames off-device", "otherwise it is a surveillance system"))
    deck.panel(slide, MARGIN, Inches(4.05), HALF, panel_height(rows, HALF),
               "Why each clause is there", rows)

    objectives = tuple((f"O{i}  {label}", "") for i, label
                       in enumerate(P.OBJECTIVE_LABELS, start=1))
    deck.panel(slide, RIGHT_X, Inches(4.05), HALF,
               panel_height(objectives, HALF), "Six objectives", objectives)

    deck.notes(slide, (
        "Read the statement aloud; it is written to be read aloud. Then take "
        "the clauses one at a time — the point is that none of them is "
        "decoration. Drop any one and the problem becomes a different, easier "
        "problem that does not serve the junctions this targets."))


def slide_scope(deck: Deck) -> None:
    slide = deck.content(6, "INTRODUCTION",
                         ("Scope, and ", "what is outside it"),
                         lead="An unstated exclusion reads as an unmet "
                              "expectation at evaluation time.", total=TOTAL)
    inside = tuple((label, "") for label in P.IN_SCOPE_LABELS)
    deck.panel(slide, MARGIN, BODY_Y, HALF, panel_height(inside, HALF),
               "Within scope", inside)

    outside = tuple((label, "") for label in P.OUT_OF_SCOPE_LABELS)
    deck.panel(slide, RIGHT_X, BODY_Y, HALF, panel_height(outside, HALF),
               "Outside scope", outside)

    deck.notes(slide, (
        "The right-hand panel is the more useful one in a viva. Nothing "
        "actuates a real signal and no real-world wait-time reduction is "
        "claimed — every control number comes from simulation, and that is "
        "stated in the report rather than discovered by an examiner."))


def slide_survey_map(deck: Deck) -> None:
    slide = deck.content(7, "LITERATURE SURVEY",
                         ("Four settled bodies of work, ",
                          "and what each leaves"),
                         lead="Organised by what a strand settles, not by "
                              "date — the question is what is left, not what "
                              "exists.", total=TOTAL)
    rows = (
        ("Congestion from camera imagery",
         "settled: the signal is in the frame. Left: scene-level, present-tense"),
        ("Forecasting on sensor graphs",
         "settled: accurate on instrumented networks. Left: no loops here"),
        ("CNN-transformer fusion with a gate",
         "settled: published, some of it in 2019. Left: does it help this task"),
        ("RL signal control",
         "settled: benchmarked to city scale. Left: anticipatory state"),
    )
    deck.panel(slide, MARGIN, BODY_Y, Inches(6.5),
               panel_height(rows, Inches(6.5)), "The four strands", rows)

    items = (
        ("We claim none of the four",
         "each is cited as prior art; claiming one invites a citation we did "
         "not survey"),
        ("What survives is the conjunction",
         "per-lane, one phase ahead, one fixed camera, heterogeneous traffic, "
         "coupled to a controller"),
    )
    deck.bullets(slide, Inches(7.1), BODY_Y, Inches(5.5), items, size=12,
                 gap=Inches(1.1))

    deck.notes(slide, (
        "This is the most important slide in the deck. The honest position is "
        "that the mechanisms are prior art and the contribution is the "
        "conjunction plus the evidence. A team that states that is credible; a "
        "team that an examiner has to inform about Conformer or ViLBERT is not."))


def slide_vision_and_graph(deck: Deck) -> None:
    slide = deck.content(8, "LITERATURE SURVEY",
                         ("The task exists; ",
                          "the sensing assumption is the gap"),
                         total=TOTAL)
    rows = (
        (f"Chakraborty et al. (2018) {P.cite('chakraborty2018')}",
         "congestion from one still frame of a fixed camera"),
        (f"Kumar & Raubal (2021) {P.cite('kumar2021')}",
         "a whole survey of this space — so it is not an opening"),
        (f"Feng et al. (2024) {P.cite('feng2024')}",
         "detect, track and predict in one pipeline from fixed cameras"),
    )
    note = ("None of this gives a controller a per-lane forecast under "
            "non-lane-disciplined traffic. That is where the opening is.")
    deck.panel(slide, MARGIN, BODY_Y, HALF, panel_height(rows, HALF, note),
               "Camera-based congestion", rows, footnote=note)

    graph = (
        (f"Yu et al. (2018) {P.cite('yu2018')}", "graph convolution over space and time"),
        (f"Li et al. (2018) {P.cite('li2018')}", "diffusion on a directed sensor graph"),
        (f"Wu et al. (2019) {P.cite('wu2019')}", "learns the adjacency instead of taking it"),
        (f"Guo et al. (2019) {P.cite('guo2019')}", "attention over both axes"),
    )
    graph_note = ("All four consume loop-detector or probe readings on a known "
                  "graph. At a camera-only junction those inputs do not exist, "
                  "so the accuracy is unavailable at any price.")
    deck.panel(slide, RIGHT_X, BODY_Y, HALF,
               panel_height(graph, HALF, graph_note),
               "Sensor-graph forecasting", graph, footnote=graph_note)

    deck.notes(slide, (
        "Cite what a strand *assumes*, not only what it does. The graph "
        "literature is excellent and irrelevant here, and saying precisely "
        "why is stronger than claiming to outperform methods evaluated on "
        "inputs we do not have."))


def slide_mechanisms(deck: Deck) -> None:
    slide = deck.content(9, "LITERATURE SURVEY",
                         ("Every mechanism we use is ", "already published"),
                         lead="This is stated, not avoided. A reviewer who "
                              "knows this strand will know it either way.",
                         total=TOTAL)
    rows = (
        (f"Peng et al. (2021) {P.cite('peng2021')}",
         "parallel CNN and transformer branches, coupled at every stage"),
        (f"Chen et al. (2021) {P.cite('chen2021')}",
         "dual branches fused by cross-attention on class tokens"),
        (f"Lu et al. (2019) {P.cite('lu2019')}",
         "co-attention — bidirectional cross-attention, in 2019"),
        (f"Alayrac et al. (2022) {P.cite('alayrac2022')}",
         "learned gates on cross-attention layers"),
        (f"Liu et al. (2022) {P.cite('liu2022')}",
         "a modern pure CNN matches transformers — the adversarial citation"),
    )
    deck.panel(slide, MARGIN, BODY_Y, Inches(6.5),
               panel_height(rows, Inches(6.5)), "The nearest neighbours", rows)

    items = (
        ("So the architecture is not the contribution",
         "the ablation is: does the fusion do anything on this task"),
        ("The gate is treated as an output",
         "logged per window and analysed against density — in the works above "
         "a gate is an optimisation device reported only through accuracy"),
        ("A gate that learns nothing is reportable",
         "and it will be reported"),
    )
    deck.bullets(slide, Inches(7.1), BODY_Y, Inches(5.5), items, size=11.5,
                 gap=Inches(1.08))

    deck.notes(slide, (
        "Mechanism as measurement is the defensible reframing, and it survives "
        "the fact that every component is prior art. Also flag the ConvNeXt "
        "citation deliberately: it argues the transformer branch must earn its "
        "place, and the convolution-only ablation configuration is the answer."))


def slide_control_lit(deck: Deck) -> None:
    slide = deck.content(10, "LITERATURE SURVEY",
                         ("Signal control is solved; ",
                          "anticipation is not tested"),
                         total=TOTAL)
    rows = (
        (f"Wei et al. (2018) {P.cite('wei2018')}", "deep RL on real signal data"),
        (f"Wei et al. (2019) {P.cite('wei2019a')}", "max-pressure reward"),
        (f"Wei et al. (2019) {P.cite('wei2019b')}", "network-level cooperation"),
        (f"Zheng et al. (2019) {P.cite('zheng2019')}", "phase-competition invariance"),
        (f"Chen et al. (2020) {P.cite('chen2020')}", "decentralised, city scale"),
    )
    note = ("Single-intersection control with a policy-gradient method on a "
            "simulator is well solved. We claim none of it.")
    deck.panel(slide, MARGIN, BODY_Y, HALF, panel_height(rows, HALF, note),
               "What is settled", rows, footnote=note)

    items = (
        ("Every state vector above is built from the present",
         "queue lengths, pressures, occupancies as measured now"),
        ("Whether anticipation helps is open",
         "and so is how accurate it must be before it helps"),
        ("That is answerable with a curve",
         "no forecast, a noise-calibrated surrogate, an oracle — the "
         "sensitivity curve is the contribution on the control side"),
    )
    deck.bullets(slide, RIGHT_X, BODY_Y, Inches(5.9), items, size=12,
                 gap=Inches(1.04))

    deck.notes(slide, (
        "The ceiling run comes first because it can falsify the whole control "
        "track: if a controller with a perfect forecast does not beat one with "
        "no forecast, the forecast is not worth carrying, and we would rather "
        "find that out in week nine than in week nineteen."))


def slide_data_lit(deck: Deck) -> None:
    slide = deck.content(11, "LITERATURE SURVEY",
                         ("Viewpoint, not country, ", "is the dataset gap"),
                         total=TOTAL)
    rows = (
        (f"IDD {P.cite('varma2019')}", "Indian, heterogeneous — ego-vehicle dashcam"),
        (f"UA-DETRAC {P.cite('wen2020')}", "fixed elevated camera — Chinese traffic"),
        (f"CityFlow {P.cite('tang2019')}", "fixed multi-camera — US traffic"),
    )
    note = ("Heterogeneous Indian traffic AND a fixed elevated viewpoint, as "
            "continuous video rather than stills, is genuinely under-served. "
            "That is a dataset gap, not a modelling one.")
    deck.panel(slide, MARGIN, BODY_Y, HALF, panel_height(rows, HALF, note),
               "What exists", rows, footnote=note)

    items = (
        ("A moving camera cannot carry per-lane regions",
         "they must stay valid across a sixty-step window, so dashcam "
         "footage bootstraps detection but cannot supply the corpus"),
        ("So the corpus is curated, not assumed",
         "licensed public fixed-camera footage, lane regions placed by hand "
         "per camera, labels from PCU-weighted occupancy"),
        ("And this is the project's hardest constraint",
         "stated here rather than discovered later"),
    )
    deck.bullets(slide, RIGHT_X, BODY_Y, Inches(5.9), items, size=12,
                 gap=Inches(1.04))

    deck.notes(slide, (
        "If one question comes back on this deck it will be about data. The "
        "answer is that the gap is the *conjunction* of viewpoint and traffic "
        "regime, that it is real, and that the corpus is curated from licensed "
        "sources rather than waiting on a benchmark that does not exist."))


def slide_table(deck: Deck) -> None:
    slide = deck.content(12, "LITERATURE SURVEY TABLE",
                         (f"{len(P.SURVEY_TABLE)} papers, ",
                          "compared on the same seven columns"),
                         lead="The full table is in the report, on landscape "
                              "pages. Six rows here show the shape of it.",
                         total=TOTAL)
    widths = [Inches(2.55), Inches(1.25), Inches(4.0), Inches(4.093)]
    headers = ("Author(s) & Year", "Theme", "Methodology",
               "Limitation / research gap")

    rows = []
    for key, method, limit in P.SURVEY_TABLE_SLIDE:
        work = P.WORKS[key]
        rows.append([
            (cell(f"{work.narrative}  {P.cite(key)}", widths[0]),
             {"font": BODY}),
            (cell(P.THEME_LABELS[work.theme], widths[1], size=9.5,
                  font=MONO), {"font": MONO}),
            (cell(method, widths[2]), {"font": BODY}),
            (cell(limit, widths[3]), {"font": BODY}),
        ])

    deck.table(slide, MARGIN, BODY_Y, CONTENT_W, headers, rows, widths=widths,
               size=11)

    y = Inches(5.5)
    deck.text(slide, MARGIN, y, CONTENT_W, Inches(0.24), size=10, font=MONO,
              colour=ACCENT, bold=True)[3].text = "WHAT THE LAST COLUMN SAYS"
    deck.text(slide, MARGIN, y + Inches(0.3), CONTENT_W, Inches(0.8), size=12,
              colour=MUTED, spacing=1.25)[3].text = (
        "The limitations are not scattered. They concentrate on four "
        "assumptions: that sensing infrastructure exists, that a scene-level "
        "output is enough, that the present can stand in for the near future, "
        "and that traffic is lane-disciplined. Those four are the gap.")

    deck.notes(slide, (
        f"The report's table has all {len(P.SURVEY_TABLE)} rows and seven "
        "columns, set landscape so it is legible. Author, year and title are "
        "generated from the verified record, so a wrong citation cannot be "
        "introduced by editing the table. Say that if asked how the citations "
        "were checked."))


def slide_gap(deck: Deck) -> None:
    slide = deck.content(13, "RESEARCH GAP",
                         ("The gap, ", "derived rather than asserted"),
                         lead="Each claim about what is missing carries the "
                              "citation of the work that establishes what is "
                              "present.", total=TOTAL)
    rows = tuple((lead, "") for lead, _detail in P.GAP_LIMITS)
    deck.panel(slide, MARGIN, BODY_Y, Inches(6.5),
               panel_height(rows, Inches(6.5)),
               "Six limitations in existing work", rows)

    items = (
        ("No method produces the conjunction",
         "per-lane, one phase ahead, one fixed camera, heterogeneous traffic, "
         "feeding a controller"),
        ("Appearance versus counts is untested here",
         "on verified labels with whole cameras held out"),
        ("Nobody reports what a fusion gate learns",
         "so its interpretability is unclaimed"),
        ("Forecast-quality sensitivity is unmeasured",
         "so a positive control result cannot be attributed to anticipation"),
    )
    deck.bullets(slide, Inches(7.1), BODY_Y, Inches(5.5), items, size=11.5,
                 gap=Inches(1.08))

    deck.notes(slide, (
        "The left panel comes straight out of the final column of the "
        "comparative table. The right panel is what those limitations leave "
        "unresolved. Keep the two visibly connected — that connection is what "
        "the guideline means by a gap derived from the survey."))


def slide_response(deck: Deck) -> None:
    slide = deck.content(14, "RESEARCH GAP",
                         ("What the project ", "does about it"), total=TOTAL)
    rows = tuple((lead, "") for lead, _detail in P.GAP_HOW_WE_ADDRESS)
    note = ("Each response answers a specific limitation from the previous "
            "slide. None of them is a general statement of intent.")
    deck.panel(slide, MARGIN, BODY_Y, Inches(6.5),
               panel_height(rows, Inches(6.5), note), "Six responses", rows,
               footnote=note)

    unaddressed = tuple((lead, "") for lead, _detail in P.GAP_UNADDRESSED)
    deck.panel(slide, Inches(7.1), BODY_Y, Inches(5.5),
               panel_height(unaddressed, Inches(5.5)),
               "What has not been adequately addressed", unaddressed)

    deck.notes(slide, (
        "Pair the two panels item by item if there is time. The one to "
        "emphasise is making the comparison that decides the question — "
        "count-only baselines on verified labels — because that is the result "
        "a reviewer will look for and the one most projects quietly omit."))


def slide_close(deck: Deck) -> None:
    slide = deck.content(15, "CLOSING", ("Where Phase I ", "stands"),
                         total=TOTAL)
    rows = (
        ("Problem established",
         "camera-only, per-lane, one phase ahead, heterogeneous traffic"),
        (f"Literature surveyed: {len(P.SURVEY_TABLE)} papers compared",
         f"{len(P.reference_list())} references, every one retrieved and cited"),
        ("Gap named and traced to the survey",
         "six limitations, five unresolved problems, six responses"),
        ("No measurement reported",
         "because none has been made — by construction, not by omission"),
    )
    deck.panel(slide, MARGIN, BODY_Y, Inches(6.5),
               panel_height(rows, Inches(6.5)), "Delivered in this report",
               rows)

    items = (
        ("Next: the corpus",
         "triage footage, place lane regions per camera, derive PCU-weighted "
         "occupancy, label at the sixty-second horizon"),
        ("Then: detection",
         "fine-tune for the eight-class Indian taxonomy, per-class accuracy "
         "with support counts"),
        ("Then: Phase 1 of the model",
         "standard cross-attention to convergence before the gate replaces it "
         "— the build order is a constraint, not a preference"),
    )
    deck.bullets(slide, Inches(7.1), BODY_Y, Inches(5.5), items, size=11.5,
                 gap=Inches(1.16))

    deck.notes(slide, (
        "Close on the last row of the panel. A Phase-I progress report with no "
        "numbers in it is correct, and the reason is structural: the content "
        "module behind this document has no import path to the results files "
        "at all, so a measurement cannot reach these slides by accident."))


def slide_references(deck: Deck, number: int, entries, *,
                     continued: bool = False) -> None:
    """One reference slide, flowing `entries` down two columns.

    Called once per page of `REFERENCE_PAGES`. IEEE entries do not all fit on
    one slide at a size anyone can read — thirty-nine of them needed 6.37 in
    against the 5.08 in a slide has — and the guard at the end of this
    function is what established that rather than a judgement call. Splitting
    is the honest fix; shrinking the type until it fits would have produced a
    slide that technically contains the references and practically does not.
    """
    first, last = entries[0][0], entries[-1][0]
    slide = deck.content(
        number, "REFERENCES",
        (f"References {first}–{last}, " if continued
         else f"{len(P.reference_list())} references, ",
         "every one retrieved"),
        lead=None if continued else
        ("Titles, authors, years, venues and DOIs come from OpenAlex and "
         "arXiv, recorded in a committed file. None is reproduced from "
         "memory."), total=TOTAL)

    size = REF_SIZE
    column_w = REF_COLUMN_W
    line_h = REF_LINE_H
    gap = REF_GAP

    # Flow the entries, advancing by each one's own height. Laying them out at
    # a fixed pitch — which an earlier version did — overlaps every entry that
    # wraps to three lines onto the one below it, and the long venue names make
    # that several of them.
    def lines(text: str) -> int:
        usable = (column_w - TEXTBOX_INSET) / Inches(1) * SAFETY
        return max(1, ceil(len(text) * BODY_PER_PT * size / usable))

    rendered = [f"[{index}]  {text}" for index, text in entries]
    heights = [lines(text) * line_h + gap for text in rendered]

    top = REF_TOP_CONT if continued else REF_TOP_FIRST
    available = Inches(7.5) - top - REF_BOTTOM

    # Break where the two columns come out closest to equal height, rather than
    # at the midpoint of the count: the entries differ by a factor of three in
    # how many lines they take.
    total_height = sum(heights)
    running = 0
    column_break = len(rendered)
    for index, height in enumerate(heights):
        running += height
        if running >= total_height / 2:
            column_break = index + 1
            break

    for column, slice_ in enumerate((rendered[:column_break],
                                     rendered[column_break:])):
        y = top
        offset = 0 if column == 0 else column_break
        for index, text in enumerate(slice_):
            height = heights[offset + index]
            deck.text(slide, MARGIN if column == 0 else Inches(6.95), y,
                      column_w, height, size=size, colour=MUTED,
                      spacing=1.08)[3].text = text
            y += height
        if y - top > available:
            raise ValueError(
                f"reference column {column + 1} of slide {number} needs "
                f"{(y - top) / Inches(1):.2f} in and the slide has "
                f"{available / Inches(1):.2f} in. Move entries to the next "
                "reference slide.")

    if not continued:
        deck.notes(slide, (
            "If asked how the references were checked: a committed script "
            "queries OpenAlex for each work and refuses to record a result "
            "whose title or year does not match what was expected. Two "
            "preprints that OpenAlex does not hold at their publication year "
            "were verified against arXiv instead, and the record says which "
            "authority answered for each entry."))
    else:
        deck.notes(slide, (
            "The continuation. Nothing on either reference slide is "
            "uncited — a committed checker fails the build if a reference is "
            "listed and never referred to in the text, and if a citation in "
            "the text points at an entry that does not exist."))


# ==========================================================================
#  build
# ==========================================================================

def build(out_path: Path) -> Path:
    deck = Deck()
    slide_title(deck)
    slide_agenda(deck)
    slide_problem(deck)
    slide_stream(deck)
    slide_statement(deck)
    slide_scope(deck)
    slide_survey_map(deck)
    slide_vision_and_graph(deck)
    slide_mechanisms(deck)
    slide_control_lit(deck)
    slide_data_lit(deck)
    slide_table(deck)
    slide_gap(deck)
    slide_response(deck)
    slide_close(deck)
    for index, page in enumerate(REFERENCE_PAGES):
        slide_references(deck, BODY_SLIDES + 1 + index, page,
                         continued=index > 0)

    if len(deck.slides) != TOTAL:
        raise AssertionError(
            f"TOTAL says {TOTAL} slides and the deck has {len(deck.slides)}; "
            "the per-slide counter would lie.")

    deck.save(out_path)
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, default=(
        Path(__file__).resolve().parent.parent / "docs" / "demo"
        / "MFSTNet-Phase1-Progress-Report-1-Presentation.pptx"))
    parser.add_argument("--pdf", action="store_true")
    args = parser.parse_args(argv)

    path = build(args.out)
    print(f"  wrote {path}  ({path.stat().st_size / 1024:.0f} KB, "
          f"{TOTAL} slides)")
    if args.pdf:
        pdf = export_pdf(path)
        if pdf:
            print(f"  wrote {pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
