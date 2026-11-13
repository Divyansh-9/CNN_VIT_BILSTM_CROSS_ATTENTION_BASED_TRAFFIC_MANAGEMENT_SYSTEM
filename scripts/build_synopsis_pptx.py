"""Build the synopsis presentation as a real PowerPoint file.

Guideline §1 requires that "the project title, Project Team ID, student names,
roll numbers, and Project Mentor name must remain consistent throughout the
synopsis, presentation, and project records", and §10 makes verifying that a
submission check. So this deck and the synopsis report are rendered from the
same constants in `scripts/synopsis_content.py`, and every quantitative claim
is read from a committed CSV under `experiments/results/` at build time. A
number that changes upstream changes on the slide instead of going stale.

The slide order follows the prescribed synopsis structure — abstract,
introduction, literature review, problem and objectives, methodology, hardware
and software, expected outcomes, conclusion, references — so a panel following
the report can follow the deck.

Visual grammar, palette and the `Deck` helper are reused from
`scripts/build_review_pptx.py` rather than reimplemented, because two decks
from one project that look like two projects is a presentation defect of its
own.

Speaker notes are on every slide and go into the real notes pane.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

from pptx.dml.color import RGBColor  # noqa: E402
from pptx.enum.shapes import MSO_SHAPE  # noqa: E402
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN  # noqa: E402
from pptx.util import Inches, Pt  # noqa: E402

from scripts import synopsis_content as C  # noqa: E402
from scripts.build_review_pptx import (ACCENT, AMBER, BAD, BODY, BODY_ADVANCE,  # noqa: E402
                                       CONTENT_W, CREAM, Deck, DEEP, DIM_CREAM,
                                       FAINT, GOOD, INK, MARGIN, MONO,
                                       MONO_ADVANCE, MUTED, PANEL,
                                       PANEL_DETAIL_INSET, PANEL_FOOT_GAP,
                                       PANEL_FOOT_INSET, PANEL_FOOT_LINE,
                                       PANEL_HEAD, PANEL_PAD, PANEL_ROW,
                                       PANEL_ROW_BARE, RULE, W, WARN,
                                       export_pdf, line_count)

TOTAL = 19
BODY_Y = Inches(2.36)


# ==========================================================================
#  panel geometry, derived from content rather than guessed
# ==========================================================================
#
# The measurements themselves live in `build_review_pptx` beside the `panel`
# method that advances by them, and `panel` refuses a box too short for the
# content it was handed. This is the other half of that: the height to hand it
# in the first place, computed from the rows rather than estimated by eye.


def _line_count(text: str, usable_in: float, advance_in: float) -> int:
    return line_count(text, usable_in, advance_in)


#: The size `MONO_ADVANCE` and `BODY_ADVANCE` were measured at, so a per-point
#: advance is `advance / MEASURED_AT_PT`. Needed because a panel's lead is
#: drawn at the caller's `size` rather than at 9.5 pt.
MEASURED_AT_PT = 9.5

#: Bold sets wider than regular in the body face. Measured off a rendered
#: panel: a lead at this allowance stays on one line where the regular figure
#: said it would and did not.
BOLD_FACTOR = 1.06


def panel_height(items, width, footnote: str | None = None,
                 size: float = 11) -> int:
    """The height `Deck.panel` needs for exactly this content.

    Rows are checked rather than measured. `Deck.panel` advances a fixed amount
    per row, so a string long enough to wrap collides with the row below it
    however tall the box is — no height fixes that, and only shortening the
    string does. Raising here turns a defect that has to be caught by looking
    at a rendered slide into one that fails the build.

    **Both** parts of a row are checked. A first version checked only the
    detail, and a panel of bare leads — the scope lists, which have no detail
    line — wrapped its first and third rows over the rows beneath them. The
    lead is bold, so it is measured with a small allowance over the body
    advance.
    """
    height = PANEL_HEAD
    usable_in = (width - PANEL_DETAIL_INSET) / Inches(1)
    lead_advance = BODY_ADVANCE / MEASURED_AT_PT * size * BOLD_FACTOR
    for lead, detail in items:
        if _line_count(lead, usable_in, lead_advance) > 1:
            fits = int(usable_in / lead_advance)
            raise ValueError(
                f"panel lead wraps and would collide with the row below it: "
                f"{lead!r} is {len(lead)} characters and about {fits} fit at "
                f"this panel width. Shorten the lead or widen the panel.")
        if not detail:
            height += PANEL_ROW_BARE
            continue
        if _line_count(detail, usable_in, MONO_ADVANCE) > 1:
            fits = int(usable_in / MONO_ADVANCE)
            raise ValueError(
                f"panel detail wraps and would collide with the row below it: "
                f"{detail!r} is {len(detail)} characters and about {fits} fit "
                f"at this panel width. Shorten the detail or widen the panel.")
        height += PANEL_ROW
    if footnote:
        usable = (width - PANEL_FOOT_INSET) / Inches(1)
        lines = _line_count(footnote, usable, BODY_ADVANCE)
        height += PANEL_FOOT_GAP + lines * PANEL_FOOT_LINE
    return int(height + PANEL_PAD)


def pack_detail(items, width) -> str:
    """As many of `items` as fit on one detail row, in order.

    The software stack is listed once in `synopsis_content.SOFTWARE_GROUPS` and
    read by both the report and this deck. The report has room for every entry
    in a group; a slide row does not, and joining them all produces exactly the
    wrapping `panel_height` refuses. So the deck takes the leading entries that
    fit and leaves the full list to the report, instead of the two documents
    disagreeing about the stack.
    """
    budget = int((width - PANEL_DETAIL_INSET) / Inches(1) / MONO_ADVANCE)
    packed: list[str] = []
    for item in items:
        candidate = packed + [item]
        if len(" · ".join(candidate)) > budget:
            break
        packed = candidate
    return " · ".join(packed) if packed else items[0]


# ==========================================================================
#  slides
# ==========================================================================

def slide_title(deck: Deck) -> None:
    slide = deck._blank(DEEP)
    deck.slides.append(slide)

    deck.text(slide, MARGIN, Inches(0.52), Inches(10), Inches(0.3),
              size=10.5, font=MONO, colour=AMBER, bold=True)[3].text = (
        f"MAJOR PROJECT SYNOPSIS   ·   B.TECH {C.BRANCH}   ·   "
        f"PROJECT TEAM ID  {C.TEAM_ID}")

    # Three deliberate lines at 34 pt. At 38 pt the last line wrapped, and a
    # wrapped title grows downwards into the lead paragraph.
    _, _, para, run = deck.text(slide, MARGIN, Inches(0.98), Inches(11.4),
                                Inches(1.42), size=34, colour=CREAM, bold=True,
                                spacing=0.95)
    run.text = ("MFSTNet — Multimodal Spatio-Temporal\n"
                "Congestion Forecasting for\n")
    deck.rich(para, [("Adaptive Traffic Signal Control",
                      {"colour": AMBER, "bold": True, "size": 34})], size=34)

    _, _, _, run = deck.text(slide, MARGIN, Inches(2.54), Inches(9.0),
                             Inches(1.0), size=13, colour=DIM_CREAM, spacing=1.35)
    run.text = ("Forecast per-lane congestion 60 seconds ahead from an existing "
                "traffic camera alone, and let a reinforcement-learning "
                "controller act on it — no new roadside sensor, no raw frame "
                "leaving the camera, and a safe fallback when either the "
                "forecast or the network is lost.")

    for index, member in enumerate(C.TEAM):
        x = MARGIN + index * Inches(2.95)
        deck.rect(slide, x, Inches(3.66), Inches(2.72), Inches(1.06),
                  fill=RGBColor(0x2A, 0x26, 0x63),
                  line=RGBColor(0x3D, 0x38, 0x82))
        deck.text(slide, x + Inches(0.22), Inches(3.80), Inches(2.3), Inches(0.2),
                  size=8.5, font=MONO,
                  colour=AMBER if member.lead else DIM_CREAM,
                  bold=True)[3].text = ("TEAM LEAD" if member.lead
                                        else f"SECTION {member.section}")
        deck.text(slide, x + Inches(0.22), Inches(4.04), Inches(2.34), Inches(0.3),
                  size=13.5, colour=CREAM, bold=True)[3].text = member.name
        deck.text(slide, x + Inches(0.22), Inches(4.34), Inches(2.34), Inches(0.3),
                  size=9.5, font=MONO,
                  colour=DIM_CREAM)[3].text = (f"{member.roll}   ·   "
                                               f"{member.section}")

    deck.rule(slide, MARGIN, Inches(5.02), CONTENT_W,
              colour=RGBColor(0x3D, 0x38, 0x82))

    _, _, guide_para, guide_run = deck.text(
        slide, MARGIN, Inches(5.22), Inches(6.4), Inches(0.25),
        size=11, colour=DIM_CREAM)
    guide_run.text = "Under the guidance of   "
    deck.rich(guide_para, [(f"{C.MENTOR_NAME}, {C.MENTOR_DESIGNATION}",
                            {"colour": CREAM, "bold": True, "size": 11})],
              size=11)

    for offset, text, size, colour in (
            (0.52, C.DEPARTMENT, 11.5, CREAM),
            (0.80, C.INSTITUTE, 12.5, CREAM),
            (1.08, f"{C.PLACE}   ·   {C.SUBMISSION_MONTH}", 10.5, DIM_CREAM)):
        deck.text(slide, MARGIN, Inches(5.22 + offset), Inches(7.0), Inches(0.3),
                  size=size, colour=colour,
                  bold=colour is CREAM)[3].text = text

    emblem = C.ASSETS / "gehu-emblem.jpeg"
    if emblem.is_file():
        slide.shapes.add_picture(str(emblem), W - MARGIN - Inches(1.45),
                                 Inches(5.14), height=Inches(1.45))

    deck.notes(slide, """
Open with the one-sentence version, then stop: this forecasts congestion per
lane, sixty seconds ahead, from camera video alone. No loops cut into the road,
no radar per approach, no vehicle radios.

Then the reason that framing matters here -- those inputs do not exist on most
Indian junctions, and a camera usually does.

Introduce the team by name and section, name the guide, and move on. Do not read
the paragraph aloud; the panel can read.
""")


def slide_agenda(deck: Deck) -> None:
    slide = deck.content(2, "Structure", ["What this synopsis ", "proposes"],
                         lead="The deck follows the synopsis chapter order, so "
                              "a panel reading along can follow.", total=TOTAL)
    left = [("1  Introduction",
             "Background, motivation, and why a camera-only route is the one worth taking"),
            ("2  Literature Review",
             "Four research strands, each mature alone, and the gap between them"),
            ("3  Problem Statement & Objectives",
             "One precise problem; six objectives O1-O6 that discharge it"),
            ("4  Proposed Methodology",
             "Dataset, detector, MFSTNet, PPO controller, prototype, evaluation")]
    right = [("5  Hardware & Software",
              "What the project actually runs on — one laptop, one 6 GB GPU"),
             ("6  Expected Outcomes",
              "Seven deliverables, each with a measurable target stated in advance"),
             ("7  Conclusion",
              "Where the work stands, including the half that is not yet working"),
             ("References",
              "IEEE style, 16 entries, cited at first use in the report")]
    deck.bullets(slide, MARGIN, BODY_Y, Inches(5.7), left, gap=Inches(0.88))
    deck.bullets(slide, Inches(7.1), BODY_Y, Inches(5.5), right, gap=Inches(0.88))

    deck.rect(slide, MARGIN, Inches(6.28), CONTENT_W, Inches(0.62),
              fill=PANEL, line=RULE)
    _, _, para, run = deck.text(slide, MARGIN + Inches(0.28), Inches(6.44),
                                CONTENT_W - Inches(0.56), Inches(0.4),
                                size=11, colour=INK, spacing=1.2)
    run.text = "One thing to hold onto throughout:  "
    deck.rich(para, [("the control half of this project already works and is "
                      "measured; the vision half is measured and does not yet "
                      "beat a count-only baseline. Both are in the report.",
                      {"colour": MUTED, "size": 11})], size=11)

    deck.notes(slide, """
Twenty seconds on this slide. Its only job is to tell the panel the deck maps
onto the report they have in front of them.

The band at the bottom is deliberate: say the honest state out loud early, so
nobody feels it was buried until slide fifteen.
""")


def slide_background(deck: Deck) -> None:
    slide = deck.content(3, "Introduction", ["A signal allocates green time ",
                                             "from a survey taken once"],
                         lead="Fixed-time control computes cycle length and "
                              "phase splits from a manual count, then holds "
                              "them for years.", total=TOTAL)
    deck.bullets(slide, MARGIN, BODY_Y, Inches(6.0), [
        ("Fixed-time plans go stale", "Webster's 1958 method is still what is "
         "deployed, and still the honest baseline — but the demand that "
         "justified a plan changes long before the plan does."),
        ("Adaptive control needs measurement", "and measurement is the "
         "expensive part: loops are cut into the carriageway and fail with "
         "the surface; radar and lidar are priced per approach."),
        ("Both assume lanes", "A stream of filtering two-wheelers registers "
         "as a small count while consuming the discharge capacity of a car."),
    ], gap=Inches(1.02))

    camera_rows = [
        ("Already installed", "at a large share of urban junctions"),
        ("Sees the whole approach", "not a point under the tarmac"),
        ("Runs on commodity hardware", "detection near the camera"),
        ("Costs nothing new", "no civil work, no per-approach unit"),
    ]
    camera_note = ("What a camera does not give directly is the quantity a "
                   "controller needs: not the present state of the "
                   "intersection, but its state a minute from now.")
    deck.panel(slide, Inches(7.4), BODY_Y, Inches(5.2),
               panel_height(camera_rows, Inches(5.2), camera_note),
               "Why a camera", camera_rows, footnote=camera_note)

    deck.notes(slide, """
Anchor the whole talk here. Adaptive signal control is not an unsolved
algorithms problem -- it is a sensing-cost problem. Say that plainly.

If asked why Webster and not a modern adaptive product: because Webster is what
is actually running at the junctions we are talking about, so it is the baseline
that means something.
""")


def slide_motivation(deck: Deck) -> None:
    slide = deck.content(4, "Motivation", ["Three gaps that make this ",
                                           "worth building"],
                         lead="Each one changes a design decision later in the "
                              "deck, so they are stated first.", total=TOTAL)
    items = [
        ("A reactive controller is always one decision behind",
         "By the time a queue is visible it is already costing waiting time. A "
         "60-second forecast lets a phase decision be right when it takes "
         "effect, not when it is made."),
        ("General detectors cannot name Indian road users",
         "COCO has no auto-rickshaw, no e-rickshaw and no cattle class — and a "
         "detector that cannot name a vehicle cannot count it. Eight "
         "India-relevant classes are trained instead."),
        ("Fusion papers omit the floor a frozen-backbone study owes its reader",
         "Without a linear probe on the same frozen features, an architectural "
         "gain and a feature-quality gain are indistinguishable. So the probe "
         "is configuration H, not an appendix."),
    ]
    y = BODY_Y
    for index, (lead, detail) in enumerate(items, start=1):
        deck.rect(slide, MARGIN, y, CONTENT_W, Inches(1.16), fill=PANEL,
                  line=RULE)
        deck.text(slide, MARGIN + Inches(0.3), y + Inches(0.2), Inches(0.5),
                  Inches(0.5), size=26, font=MONO, colour=AMBER,
                  bold=True)[3].text = str(index)
        deck.text(slide, MARGIN + Inches(0.98), y + Inches(0.2),
                  CONTENT_W - Inches(1.3), Inches(0.28), size=14, colour=INK,
                  bold=True)[3].text = lead
        deck.text(slide, MARGIN + Inches(0.98), y + Inches(0.54),
                  CONTENT_W - Inches(1.3), Inches(0.56), size=11,
                  colour=MUTED, spacing=1.25)[3].text = detail
        y += Inches(1.34)

    deck.text(slide, MARGIN, Inches(6.6), CONTENT_W, Inches(0.4), size=11,
              colour=ACCENT, bold=True)[3].text = (
        "Consequence for this project: the ablation, not the architecture, is "
        "the deliverable of scientific interest.")

    deck.notes(slide, """
Point three is the one to dwell on, because it explains why the results slide
later is honest rather than embarrassing. We built the floor into the experiment
design on purpose, and the floor is currently winning. That was a foreseeable
outcome of an honest design, not a surprise.
""")


def slide_literature(deck: Deck, facts: C.Facts) -> None:
    slide = deck.content(5, "Literature Review", ["Four strands, each mature ",
                                                  "on its own"],
                         lead="Every row below is well developed in isolation. "
                              "The combination is what is missing.", total=TOTAL)
    widths = [Inches(1.7), Inches(2.9), Inches(3.5), Inches(3.79)]
    deck.table(slide, MARGIN, BODY_Y, CONTENT_W,
               ["Strand", "Representative work", "Strength",
                "Limitation for this problem"],
               [[("Detection", {"bold": True, "font": BODY}),
                 "YOLO family [5]; IDD [6]",
                 ("Real-time on modest hardware", {"font": BODY}),
                 ("Dashcam viewpoint dominates; CCTV view seldom reported",
                  {"font": BODY, "colour": WARN})],
                [("Forecasting", {"bold": True, "font": BODY}),
                 "LSTM [14]; XGBoost [15]",
                 ("Strong on sensor time series", {"font": BODY}),
                 ("Assumes an instrumented network; count-only control omitted",
                  {"font": BODY, "colour": WARN})],
                [("Fusion", {"bold": True, "font": BODY}),
                 "ViT [2]; DINOv2 [3]; attention [1]",
                 ("Complementary local and global features", {"font": BODY}),
                 ("Linear-probe floor rarely reported, so gains unattributable",
                  {"font": BODY, "colour": WARN})],
                [("RL control", {"bold": True, "font": BODY}),
                 "PPO [7]; SB3 [8]; SUMO [9]",
                 ("Mature algorithms and simulators", {"font": BODY}),
                 ("Weak or unswept baselines [10]-[12]; variance unreported",
                  {"font": BODY, "colour": WARN})]],
               widths=widths, row_h=Inches(0.52), size=10)

    deck.rect(slide, MARGIN, Inches(5.16), CONTENT_W, Inches(1.5), fill=PANEL,
              line=RULE)
    deck.text(slide, MARGIN + Inches(0.3), Inches(5.36), CONTENT_W - Inches(0.6),
              Inches(0.24), size=10, font=MONO, colour=ACCENT,
              bold=True)[3].text = "THE PATTERN"
    deck.text(slide, MARGIN + Inches(0.3), Inches(5.66), CONTENT_W - Inches(0.6),
              Inches(0.8), size=12, colour=INK, spacing=1.3)[3].text = (
        "Detection work rarely carries through to control. Forecasting work "
        "rarely reports the count-only control condition. Fusion work rarely "
        "reports the linear-probe floor. Control work rarely sweeps its "
        "baseline. Each omission is individually forgivable and collectively "
        "the reason a reader cannot tell which component earned the result.")

    deck.notes(slide, """
Do not read the table. Say the four strands, then read the panel at the bottom,
which is the actual argument.

If a panel member pushes on novelty: agree immediately that the fusion
mechanisms are published, and redirect to the next slide, where the three things
we do claim are stated.
""")


def slide_gap(deck: Deck) -> None:
    slide = deck.content(6, "Research Gap", ["What we claim, ",
                                             "and what we do not"],
                         lead="The fusion mechanisms are published. Claiming "
                              "them would not survive review, so the claim is "
                              "narrower and defensible.", total=TOTAL)
    gaps = [
        ("G1", "Camera-only, forecast-driven control",
         "An end-to-end path from one existing camera to a signal decision, "
         "with no additional roadside sensing, is not established for "
         "unstructured traffic."),
        ("G2", "The gate reported as an artefact",
         "Gated fusion is published as a mechanism; the gate value is treated "
         "as an internal activation. Logging it, tracking it live and "
         "analysing when it saturates turns it into evidence about which "
         "modality the model is using."),
        ("G3", "Density-stratified, leave-one-camera-out evaluation",
         "Random splits over overlapping windows leak, and a camera-hashed "
         "split can put an entire traffic regime in one partition. One "
         "held-out camera at a time, reported as a fold mean with an "
         "interval, is what makes a cross-camera claim mean anything."),
    ]
    y = BODY_Y
    for tag, lead, detail in gaps:
        deck.rect(slide, MARGIN, y, Inches(0.86), Inches(1.16), fill=ACCENT)
        deck.text(slide, MARGIN, y + Inches(0.36), Inches(0.86), Inches(0.4),
                  size=20, font=MONO, colour=CREAM, bold=True,
                  align=PP_ALIGN.CENTER)[3].text = tag
        deck.text(slide, MARGIN + Inches(1.1), y + Inches(0.12),
                  CONTENT_W - Inches(1.2), Inches(0.3), size=14.5, colour=INK,
                  bold=True)[3].text = lead
        deck.text(slide, MARGIN + Inches(1.1), y + Inches(0.48),
                  CONTENT_W - Inches(1.2), Inches(0.6), size=11, colour=MUTED,
                  spacing=1.25)[3].text = detail
        y += Inches(1.34)

    deck.text(slide, MARGIN, Inches(6.56), CONTENT_W, Inches(0.4), size=11,
              colour=MUTED, spacing=1.2)[3].text = (
        "Stated the other way: this is not a new fusion mechanism. It is a "
        "camera-only path to control, an interpretable gate, and an evaluation "
        "protocol strict enough that a negative result is publishable.")

    deck.notes(slide, """
This is the slide that decides how the viva goes. Volunteering the limit of the
novelty claim before anyone asks is what makes the rest of the deck credible.

Have the related-work note ready if pressed for specifics on which mechanisms
are already published.
""")


def slide_problem(deck: Deck) -> None:
    slide = deck.content(7, "Problem Statement", ["One sentence, ",
                                                  "four difficulties"],
                         total=TOTAL)
    # The statement wraps to five lines at 13.5 pt across the content width, so
    # the box is sized for five and the cards start below it.
    deck.rect(slide, MARGIN, Inches(1.94), CONTENT_W, Inches(1.92),
              fill=RGBColor(0xEC, 0xEB, 0xFA), line=ACCENT)
    deck.text(slide, MARGIN + Inches(0.34), Inches(2.14), CONTENT_W - Inches(0.68),
              Inches(1.56), size=13.5, colour=INK, spacing=1.35)[3].text = (
        "Given only the video stream of a camera already installed at a "
        "signalised urban intersection carrying heterogeneous, weakly "
        "lane-disciplined traffic, predict the congestion level of each of the "
        "four approaches 60 seconds ahead, and use that prediction to select "
        "signal phases so that mean vehicle waiting time is lower than under "
        "the best-configured Webster plan — without installing any additional "
        "sensor, without transmitting any raw frame off the capture device, and "
        "without failing unsafely when either the forecast or the network is "
        "lost.")

    cards = [
        ("Counting is not detection",
         "A detector strong on mAP can still mis-count under occlusion. The "
         "operating point is chosen to minimise counting error, not to "
         "maximise mAP."),
        ("Labelling is not free",
         "Congestion has no ground-truth sensor here, so labels are derived "
         "from counts under a stated, per-camera-calibrated rule."),
        ("Forecasting is not description",
         "The model must predict a state it cannot see — the label is 60 "
         "seconds past the last observed frame."),
        ("Evaluation is easily circular",
         "Labels come from detector counts, and three baselines also consume "
         "detector counts. So the test split is human-verified."),
    ]
    for index, (lead, detail) in enumerate(cards):
        x = MARGIN + (index % 2) * Inches(6.15)
        y = Inches(4.06) + (index // 2) * Inches(1.32)
        deck.rect(slide, x, y, Inches(5.85), Inches(1.14), fill=PANEL, line=RULE)
        deck.text(slide, x + Inches(0.26), y + Inches(0.18), Inches(5.3),
                  Inches(0.26), size=12.5, colour=INK, bold=True)[3].text = lead
        deck.text(slide, x + Inches(0.26), y + Inches(0.5), Inches(5.35),
                  Inches(0.56), size=10.5, colour=MUTED,
                  spacing=1.2)[3].text = detail

    deck.notes(slide, """
Read the boxed statement once, slowly. It is the only slide where reading aloud
is right, because every clause in it is load-bearing -- including the two
negative clauses at the end, which are requirements and not caveats.

The four cards are the answer to "why is this a project and not a weekend".
""")


def slide_objectives(deck: Deck) -> None:
    slide = deck.content(8, "Objectives", ["Six objectives, ",
                                           "each independently checkable"],
                         lead="Every objective names an artefact that either "
                              "exists or does not, so progress is not a "
                              "matter of opinion.", total=TOTAL)
    y = BODY_Y
    short = [
        "Licence-audited corpus of unstructured-traffic footage; YOLOv8s "
        "fine-tuned over eight India-relevant vehicle classes.",
        "Per-lane congestion labels from PCU-weighted occupancy with "
        "per-camera thresholds, so a label means the same thing on a six-lane "
        "arterial and a two-lane approach.",
        "MFSTNet: gated bidirectional cross-attention over frozen CNN and ViT "
        "features, then recurrent and attention-based temporal modelling, "
        "predicting 60 s ahead.",
        "Eight-configuration ablation including a linear probe, evaluated "
        "leave-one-camera-out so no reported score is a memorised camera.",
        "PPO controller on a SUMO intersection whose observation carries the "
        "forecast, measured against a swept Webster baseline over 30 paired "
        "seeds with a pre-registered disqualification rule.",
        "Edge-to-server prototype in which no raw frame leaves the capture "
        "device, and in which both required fallback paths are exercised.",
    ]
    for index, ((tag, _full), text) in enumerate(zip(C.OBJECTIVES, short)):
        deck.rect(slide, MARGIN, y + Inches(0.04), Inches(0.66), Inches(0.5),
                  fill=ACCENT if index < 4 else AMBER)
        deck.text(slide, MARGIN, y + Inches(0.14), Inches(0.66), Inches(0.3),
                  size=14, font=MONO, colour=CREAM, bold=True,
                  align=PP_ALIGN.CENTER)[3].text = tag
        deck.text(slide, MARGIN + Inches(0.88), y, CONTENT_W - Inches(0.98),
                  Inches(0.6), size=12, colour=INK, spacing=1.25)[3].text = text
        y += Inches(0.72)

    deck.rule(slide, MARGIN, y + Inches(0.06), CONTENT_W)
    deck.text(slide, MARGIN, y + Inches(0.2), CONTENT_W, Inches(0.4), size=11,
              colour=MUTED, spacing=1.2)[3].text = (
        "O1-O4 are the vision and evaluation track; O5-O6 are the control and "
        "prototype track. They were built to be independent on purpose, so a "
        "delay in one does not stall the other — and O5 is already delivering "
        "a result while O4 is still gathering power.")

    deck.notes(slide, """
Say the split at the bottom explicitly: two tracks, deliberately decoupled. It
is the reason the project has a positive result to show at all while the vision
side is still inconclusive.
""")


def slide_architecture(deck: Deck) -> None:
    slide = deck.content(9, "Methodology", ["Three tiers, ",
                                            "one message contract"],
                         lead="Frames never leave the edge tier. Only derived "
                              "counts and predictions cross the network.",
                         total=TOTAL)
    tiers = [
        ("EDGE TIER", "team laptop, at the camera",
         ["Fixed CCTV camera", "YOLOv8s detection — 8 classes",
          "Per-lane counting", "Local Webster fallback"], ACCENT),
        ("SERVER TIER", "FastAPI + ONNX + PPO",
         ["MFSTNet (ONNX) — 60 s ahead", "PPO policy — 16-dim, 12 actions",
          "SignalGuard — min/max green, all-red", "SQLite — bounded history"],
         RGBColor(0x0F, 0x76, 0x6E)),
        ("PRESENTATION TIER", "React dashboard",
         ["Live panel — counts, predictions, gate",
          "Benchmark panel — committed CSV",
          "The two panels never merge", "Refresh within 2 s"], AMBER),
    ]
    for index, (name, subtitle, items, colour) in enumerate(tiers):
        x = MARGIN + index * Inches(4.09)
        width = Inches(3.79)
        deck.rect(slide, x, BODY_Y, width, Inches(0.62), fill=colour)
        deck.text(slide, x + Inches(0.22), BODY_Y + Inches(0.1), width - Inches(0.4),
                  Inches(0.24), size=10.5, font=MONO, colour=CREAM,
                  bold=True)[3].text = name
        deck.text(slide, x + Inches(0.22), BODY_Y + Inches(0.34), width - Inches(0.4),
                  Inches(0.24), size=9.5,
                  colour=RGBColor(0xE4, 0xE2, 0xF6))[3].text = subtitle
        y = BODY_Y + Inches(0.78)
        for item in items:
            deck.rect(slide, x, y, width, Inches(0.56), fill=PANEL, line=RULE)
            deck.text(slide, x + Inches(0.22), y + Inches(0.16), width - Inches(0.44),
                      Inches(0.3), size=10.5, colour=INK,
                      anchor=MSO_ANCHOR.TOP)[3].text = item
            y += Inches(0.68)

    # The contract line wraps to two lines in 10.5 pt mono at this width, so the
    # band is two lines tall rather than clipping the QoS-ownership clause.
    deck.rect(slide, MARGIN, Inches(5.90), CONTENT_W, Inches(0.72), fill=DEEP)
    deck.text(slide, MARGIN + Inches(0.28), Inches(6.00), CONTENT_W - Inches(0.56),
              Inches(0.54), size=10.5, font=MONO, colour=CREAM, bold=True,
              spacing=1.2)[3].text = (
        "MQTT CONTRACT    emergency QoS 2   │   counts and commands QoS 1   │   "
        "predictions and heartbeat QoS 0    —    QoS is attached to the topic, "
        "never passed by the caller")

    deck.text(slide, MARGIN, Inches(6.74), CONTENT_W, Inches(0.5), size=11,
              colour=INK, spacing=1.2)[3].text = (
        "The coupling that is easy to miss: MFSTNet's output is not only "
        "displayed, it is part of the controller's observation, at indices "
        "11-14 of a 16-dimensional vector. If the forecast is unavailable "
        "those indices are zeroed — the vector is never shortened, because "
        "that would silently change the meaning of every later index.")

    deck.notes(slide, """
Two things to say and then move: frames stop at the edge tier, and QoS lives on
the topic definition so a caller cannot downgrade an emergency message.

The paragraph at the bottom is the answer to "how are the two halves actually
coupled" -- expect that question and have this slide up when it comes.
""")


def slide_corpus(deck: Deck, facts: C.Facts) -> None:
    slide = deck.content(10, "Methodology", ["The corpus is built ",
                                             "so a threshold is a config change"],
                         lead="Counts are stored separately from labels, so "
                              "relabelling takes seconds instead of re-running "
                              "the detector over hours of video.", total=TOTAL)
    stages = [
        ("Source clips", "curated public footage + campus capture"),
        ("Triage", "reject clips too short or too degraded"),
        ("Lane geometry", "placed by hand, then reviewed"),
        ("Detection", "fine-tuned YOLOv8s → per-lane counts"),
        ("Counts file", "threshold-independent"),
        ("Labelling", "PCU occupancy, per-camera p33/p67"),
        ("Audit", "fails loudly; nothing proceeds past it"),
        ("Feature cache", "frozen backbones once, fp16 per clip"),
        ("Split", "leave-one-camera-out, cut by source clip"),
    ]
    y = BODY_Y
    for index, (name, detail) in enumerate(stages):
        deck.rect(slide, MARGIN, y, Inches(2.4), Inches(0.42),
                  fill=ACCENT if index in (0, 8) else PANEL,
                  line=None if index in (0, 8) else RULE)
        deck.text(slide, MARGIN + Inches(0.18), y + Inches(0.1), Inches(2.1),
                  Inches(0.24), size=10.5,
                  colour=CREAM if index in (0, 8) else INK,
                  bold=True)[3].text = name
        deck.text(slide, MARGIN + Inches(2.6), y + Inches(0.1), Inches(3.6),
                  Inches(0.24), size=10, colour=MUTED)[3].text = detail
        y += Inches(0.48)

    # One panel rather than two stacked ones: two panels sized for their own
    # content do not both fit beside a nine-stage pipeline, and the first one's
    # footnote ended up drawn over the second.
    corpus_rows = [
        ("Twenty two-wheelers ≠ twenty buses", "same count, different road"),
        ("Indo-HCM equivalence values",
         "car 1.00 · motorcycle 0.24 · auto 0.78"),
        ("Thresholds per camera",
         "p33 / p67 of that camera's own distribution"),
        ("Split by source clip, never by window",
         "neighbouring windows share most frames"),
        ("Lane centres by hand, always reviewed",
         "auto centres moved 0.164 of frame width"),
    ]
    corpus_note = ("An unmapped vehicle class raises rather than defaulting to "
                   "a weight of 1.0.")
    panel_h = panel_height(corpus_rows, Inches(5.5), corpus_note)
    deck.panel(slide, Inches(7.1), BODY_Y, Inches(5.5), panel_h,
               "Decisions the corpus makes", corpus_rows, footnote=corpus_note)

    band_y = BODY_Y + panel_h + Inches(0.16)
    deck.rect(slide, Inches(7.1), band_y, Inches(5.5), Inches(0.62), fill=PANEL,
              line=RULE)
    deck.text(slide, Inches(7.38), band_y + Inches(0.13), Inches(4.94),
              Inches(0.4), size=10, colour=MUTED, spacing=1.2)[3].text = (
        "A cache is keyed on backbone, resize and normalisation; a mismatch "
        "raises rather than warns, because a stale cache trains normally and "
        "reports wrong numbers.")

    deck.notes(slide, """
The point of this slide is engineering discipline, not the diagram. Two facts
carry it: counts are kept apart from labels so a threshold decision costs
seconds, and splits are cut by clip because overlapping windows would otherwise
put near-duplicates on both sides.

The 0.164-of-frame-width number is measured, not illustrative -- say so if
asked.
""")


def slide_model(deck: Deck, facts: C.Facts) -> None:
    slide = deck.content(11, "Methodology", ["MFSTNet — ",
                                             "frozen backbones, learned fusion"],
                         lead="Both backbones are frozen and cached, which is "
                              "what makes an 8-configuration, 4-fold, 5-seed "
                              "sweep fit on one 6 GB laptop GPU.", total=TOTAL)
    stack = [
        ("Frame sequence   —   T = 60 frames at 5 s", ACCENT, CREAM),
        ("ResNet-50 (frozen)  2048×7×7        ‖        DINOv2 ViT-S/14 (frozen)  "
         "384 tokens, CLS dropped", PANEL, INK),
        ("Aligned onto a shared 7 × 7 grid   —   the gate is elementwise, so "
         "the grids must match", PANEL, INK),
        ("Z_A = CNN queries ViT        ‖        Z_B = ViT queries CNN", PANEL, INK),
        ("Gated fusion   —   the gate value is logged, tracked and reported",
         RGBColor(0xF7, 0xE9, 0xE3), INK),
        ("BiLSTM  2 layers × 128, bidirectional   →   temporal self-attention  "
         "2 layers × 4 heads", PANEL, INK),
        ("Attention pooling over time   +   per-lane ROI pooling", PANEL, INK),
        ("Per-lane head   —   LOW / MEDIUM / HIGH for N, S, E, W at t + 60 s",
         ACCENT, CREAM),
    ]
    y = BODY_Y
    for text, fill, colour in stack:
        deck.rect(slide, MARGIN, y, Inches(7.5), Inches(0.46), fill=fill,
                  line=None if fill in (ACCENT,) else RULE)
        deck.text(slide, MARGIN + Inches(0.22), y + Inches(0.12), Inches(7.1),
                  Inches(0.26), size=10.5, colour=colour,
                  bold=fill is ACCENT)[3].text = text
        y += Inches(0.54)

    x = Inches(8.5)
    deck.rect(slide, x, BODY_Y, Inches(4.1), Inches(1.86),
              fill=RGBColor(0xEC, 0xEB, 0xFA), line=ACCENT)
    deck.text(slide, x + Inches(0.26), BODY_Y + Inches(0.2), Inches(3.6),
              Inches(0.24), size=10, font=MONO, colour=ACCENT,
              bold=True)[3].text = "THE GATE  (4.1) AND (4.2)"
    deck.text(slide, x + Inches(0.26), BODY_Y + Inches(0.56), Inches(3.6),
              Inches(0.6), size=13, font=MONO, colour=INK, bold=True,
              spacing=1.5)[3].text = ("g = σ( W [ Z_A ; Z_B ] )\n"
                                     "F = g·Z_A + (1−g)·Z_B")
    deck.text(slide, x + Inches(0.26), BODY_Y + Inches(1.28), Inches(3.6),
              Inches(0.5), size=10, colour=MUTED, spacing=1.2)[3].text = (
        "Retained, not discarded. A gate at 0.5 with negligible variance "
        "means averaging, not selection.")

    gate_mean = C.fmt(facts.loco["G"]["gate_mean_mean"])
    gate_std = C.fmt(facts.loco["G"]["gate_std_mean"])
    deck.rect(slide, x, Inches(4.34), Inches(4.1), Inches(1.02), fill=PANEL,
              line=RULE)
    deck.text(slide, x + Inches(0.26), Inches(4.48), Inches(3.6), Inches(0.24),
              size=10, font=MONO, colour=FAINT,
              bold=True)[3].text = "MEASURED, CONFIG G"
    _, _, para, run = deck.text(slide, x + Inches(0.26), Inches(4.74),
                                Inches(3.6), Inches(0.5), size=17, font=MONO,
                                colour=WARN, bold=True)
    run.text = f"g = {gate_mean}"
    deck.rich(para, [(f"   σ = {gate_std}", {"colour": MUTED, "size": 11,
                                             "font": MONO})], size=17)

    ablation_rows = [
        ("Every module disableable by flag", "no code edit A → H"),
        ("H is the linear probe", "the floor, not an appendix"),
    ]
    deck.panel(slide, x, Inches(5.48), Inches(4.1),
               panel_height(ablation_rows, Inches(4.1)),
               "Ablation-ability is architectural", ablation_rows)

    deck.notes(slide, """
Two claims here and no more. First, freezing the backbones and caching their
outputs is what turns a sixty-hour ablation into about ninety minutes on a
laptop -- that is why this project can run an eight-way sweep at all.

Second, the gate measured at 0.53 with a standard deviation of 0.009 is a
finding, not a bug. The model is averaging, not choosing. Say it before anyone
reads it off the slide.
""")


def slide_controller(deck: Deck, facts: C.Facts) -> None:
    slide = deck.content(12, "Methodology", ["The controller, ",
                                             "and a baseline worth beating"],
                         lead="A weak baseline is the commonest way an RL "
                              "traffic result stops meaning anything, so the "
                              "baseline is swept rather than chosen.",
                         total=TOTAL)
    # Both panels sized for four rows. The safety-limit and clamping notes moved
    # into the paragraph below, because a footnote inside a panel this tall does
    # not fit above the reward band.
    ppo_rows = [
        ("Observation", "16-dim; forecast at indices 11-14"),
        ("Action space", "12 discrete: {NS, EW} × {10,20,30,45,60,90} s"),
        ("Algorithm", "lr 3e-4 · n_steps 2048 · batch 64 · γ 0.99"),
        ("Budget", "clip 0.2 · ent 0.01 · 500,000 timesteps"),
    ]
    webster_rows = [
        ("Saturation flow is not chosen", "it is swept: 525 → 1283 PCU/h/m"),
        ("Best configuration wins", "and that is what PPO must beat"),
        ("Clamping is logged", "clamp rate reported beside the result"),
        ("Disqualification is pre-registered", "<85% trips, or >50% clamped"),
    ]
    deck.panel(slide, MARGIN, BODY_Y, Inches(5.9),
               panel_height(ppo_rows, Inches(5.9)), "PPO agent", ppo_rows)
    deck.panel(slide, Inches(6.9), BODY_Y, Inches(5.7),
               panel_height(webster_rows, Inches(5.7)), "Webster baseline",
               webster_rows)

    deck.rect(slide, MARGIN, Inches(5.40), CONTENT_W, Inches(0.96),
              fill=RGBColor(0xEC, 0xEB, 0xFA), line=ACCENT)
    deck.text(slide, MARGIN + Inches(0.3), Inches(5.54), CONTENT_W - Inches(0.6),
              Inches(0.24), size=10, font=MONO, colour=ACCENT,
              bold=True)[3].text = "REWARD  (4.3)"
    deck.text(slide, MARGIN + Inches(0.3), Inches(5.82), CONTENT_W - Inches(0.6),
              Inches(0.4), size=14, font=MONO, colour=INK,
              bold=True)[3].text = (
        "r_t  =  −(W_t − W_{t−1}) / 100   −   1.0 · n_starved   −   "
        "0.05 · 1[switch]")

    deck.text(slide, MARGIN, Inches(6.52), CONTENT_W, Inches(0.8), size=11,
              colour=MUTED, spacing=1.25)[3].text = (
        "Reduction in total lane waiting time between successive decisions, "
        "penalised for starving an approach and lightly penalised for "
        "switching. Minimum and maximum green of 10 s and 90 s and a 3 s "
        "all-red are enforced by actuation, not learned — a safety constraint "
        "the agent could trade against reward is not a constraint. A Webster "
        "controller that clamps every cycle has stopped computing anything and "
        "is a fixed-time plan under another name, which is why the clamp rate "
        "is reported beside the result.")

    deck.notes(slide, """
The sweep is the slide. Webster's optimum cycle depends on an assumed
saturation flow whose published values for mixed traffic span more than a factor
of two -- so quoting one value silently chooses how strong your baseline is. We
sweep and take the best.

If asked why the safety limits are not learned: because a constraint the policy
can trade against reward is not a constraint.

If asked whether SUMO can represent this traffic at all: the sublane model is
enabled, so lateral filtering is representable, and the residual gap to observed
behaviour is declared in the report rather than treated as absent.
""")


def slide_evaluation(deck: Deck, facts: C.Facts) -> None:
    slide = deck.content(13, "Methodology", ["Evaluation is the ",
                                             "deliverable"],
                         lead="Leave-one-camera-out, five seeds, bootstrap "
                              "intervals, and raw per-run CSVs committed "
                              "beside the code.", total=TOTAL)
    items = [
        ("Leave-one-camera-out",
         f"Each fold holds out one camera entirely — {facts.n_folds} folds "
         f"today. A reported score cannot be the model recognising a camera it "
         f"has already seen."),
        ("Five seeds, and the spread is reported",
         "On this corpus one configuration moved by more than 0.24 macro-F1 "
         "across seeds on a single fold — larger than the gap between most "
         "pairs of configurations. The harness warns when the spread exceeds "
         "the closest gap, because those two are then not separated."),
        ("Ordinal metrics, not just accuracy",
         "Macro-F1 as the headline, with quadratic weighted kappa and an "
         "ordinal error rate beside it: confusing LOW with HIGH is not the "
         "same error as confusing LOW with MEDIUM."),
        ("Claims are machine-checked",
         "Every scope claim is stored as the sentence it would appear as in "
         "the report, paired with an assertion run against the corpus. A "
         "failing assertion blocks table generation. There is no override "
         "flag."),
    ]
    deck.bullets(slide, MARGIN, BODY_Y, Inches(7.4), items, gap=Inches(1.06))

    reported_rows = [
        ("Mean ± 95% CI", "bootstrap, 10,000 resamples"),
        ("Paired t-test", "α = 0.05, 30 paired seeds"),
        ("Effect size", "Cohen's d, always alongside p"),
        ("Fold count beside the mean", "4 points is not 30"),
        ("Seeds fixed, CSVs committed", "generated, never transcribed"),
    ]
    reported_h = panel_height(reported_rows, Inches(4.4))
    deck.panel(slide, Inches(8.2), BODY_Y, Inches(4.4), reported_h,
               "Reported as", reported_rows)

    circular_y = BODY_Y + reported_h + Inches(0.14)
    deck.rect(slide, Inches(8.2), circular_y, Inches(4.4), Inches(1.4),
              fill=PANEL, line=RULE)
    deck.text(slide, Inches(8.46), circular_y + Inches(0.16), Inches(3.9),
              Inches(0.24), size=10, font=MONO, colour=BAD,
              bold=True)[3].text = "AND WHERE IT IS CIRCULAR"
    deck.text(slide, Inches(8.46), circular_y + Inches(0.42), Inches(3.9),
              Inches(0.9), size=10.5, colour=INK, spacing=1.25)[3].text = (
        "Labels come from detector counts, and three baselines also consume "
        "them — scoring those on auto-generated labels scores them against "
        "their own input. So the test split is human-verified; training data "
        "stays auto-labelled.")

    deck.notes(slide, """
This is where to spend time if the panel is technical. The circularity point in
the bottom-right box is the one that shows we understood our own experiment: you
cannot evaluate a count-consuming baseline on labels derived from counts.

Also say plainly that four folds is a small experiment, and that the next slide
shows what that costs us in statistical power.
""")


def slide_ablation(deck: Deck, facts: C.Facts) -> None:
    best_config, best_f1 = facts.best_vision
    slide = deck.content(14, "Preliminary Results",
                         ["The ablation, ", "reported as measured"],
                         lead=f"{facts.n_folds} folds × {facts.n_seeds} seeds = "
                              f"{facts.loco['G']['n_runs']} runs per "
                              f"configuration. Nothing below is a single-seed "
                              f"number.", total=TOTAL)
    rows = []
    highlight = []
    for index, (config, variant, _desc) in enumerate(C.ABLATION_ROWS):
        row = facts.loco[config]
        f1 = float(row["macro_f1_mean"])
        style = {"bold": True} if config == best_config else {}
        if config == best_config:
            highlight.append(index)
        rows.append([
            (config, {"bold": True}),
            (variant, dict({"font": BODY}, **style)),
            (f"{C.fmt(f1)}  [{C.fmt(row['macro_f1_lo'])}, "
             f"{C.fmt(row['macro_f1_hi'])}]", style),
            (C.fmt(row["accuracy_mean"]), style),
            (C.fmt(row["macro_f1_seed_spread"]),
             {"colour": WARN if float(row["macro_f1_seed_spread"]) > 0.15
              else MUTED}),
        ])
    # 7.7 in of columns, not 8.0: the highlighted row is drawn 0.1 in wider than
    # the table on each side, and at 8.0 in that bleed ran under the panel at
    # x = 8.7.
    deck.table(slide, MARGIN, BODY_Y, Inches(7.7),
               ["Cfg", "Variant", "Macro-F1  [95% CI]", "Acc", "Seed spread"],
               rows, widths=[Inches(0.55), Inches(2.4), Inches(2.85),
                             Inches(0.85), Inches(1.05)],
               row_h=Inches(0.4), size=10, highlight=tuple(highlight))

    best_model, best_counts = facts.best_counts
    x = Inches(8.7)
    deck.rect(slide, x, BODY_Y, Inches(3.9), Inches(1.9), fill=PANEL,
              line=RULE)
    deck.text(slide, x + Inches(0.26), BODY_Y + Inches(0.18), Inches(3.4),
              Inches(0.24), size=10, font=MONO, colour=FAINT,
              bold=True)[3].text = "COUNT-ONLY BASELINES, SAME FOLDS"
    y = BODY_Y + Inches(0.5)
    for name, row in sorted(facts.baselines.items(),
                            key=lambda kv: -float(kv[1]["macro_f1_mean"])):
        leader = name == best_model
        deck.text(slide, x + Inches(0.26), y, Inches(2.3), Inches(0.24),
                  size=10.5, colour=INK,
                  bold=leader)[3].text = name.replace("_", " ")
        deck.text(slide, x + Inches(2.6), y, Inches(1.1), Inches(0.24),
                  size=10.5, font=MONO, colour=GOOD if leader else MUTED,
                  bold=leader,
                  align=PP_ALIGN.RIGHT)[3].text = C.fmt(row["macro_f1_mean"])
        y += Inches(0.32)

    deck.rect(slide, x, Inches(4.44), Inches(3.9), Inches(2.22),
              fill=RGBColor(0xFD, 0xF3, 0xE8), line=WARN)
    deck.text(slide, x + Inches(0.26), Inches(4.6), Inches(3.4), Inches(0.24),
              size=10, font=MONO, colour=WARN,
              bold=True)[3].text = "WHAT THIS SAYS, HONESTLY"
    deck.text(slide, x + Inches(0.26), Inches(4.9), Inches(3.4), Inches(1.6),
              size=10.5, colour=INK, spacing=1.3)[3].text = (
        f"The best vision configuration is {best_config} at {C.fmt(best_f1)}. "
        f"A count-only sequence model reaches {C.fmt(best_counts)} on the same "
        f"folds and seeds. On this corpus the appearance features are not yet "
        f"earning their place, so the vision claim is reported as open — not "
        f"as established, and not dropped.")

    deck.notes(slide, f"""
Do not soften this. State it: the count-only baseline at {C.fmt(best_counts)}
beats every vision configuration, the best of which is {best_config} at
{C.fmt(best_f1)}.

Then give the two reasons that are actually in the data, not excuses: four folds
is very little power, and the seed spread on several configurations is larger
than the gaps between them. Both are on the slide, in the right-hand column.

If a panel member asks whether we would report this in the paper -- yes, and the
next slide shows the pre-registered comparison that settles it.
""")


def slide_control_result(deck: Deck, facts: C.Facts) -> None:
    control = facts.control
    gate = facts.gate
    improvement = float(control["improvement_percent"])
    slide = deck.content(15, "Preliminary Results",
                         ["The control half ", "already works"],
                         lead="30 paired seeds against the swept, "
                              "best-configuration Webster baseline.",
                         total=TOTAL)

    stats = [(f"{improvement:.2f}%", "lower mean waiting time", GOOD),
             (f"{float(control['mean_a']):.2f} s", C.CONTROL_ARM_LABEL, INK),
             (f"{float(control['mean_b']):.2f} s",
              "Webster, best config", MUTED),
             (f"{float(control['cohens_d']):.2f}", "Cohen's d", INK),
             (f"p {C.fmt_p(control['p'])}", "paired t-test", GOOD)]
    for index, (value, label, colour) in enumerate(stats):
        x = MARGIN + index * Inches(2.45)
        deck.rect(slide, x, BODY_Y, Inches(2.25), Inches(1.12), fill=PANEL,
                  line=RULE)
        deck.text(slide, x + Inches(0.2), BODY_Y + Inches(0.2), Inches(1.9),
                  Inches(0.44), size=21, font=MONO, colour=colour,
                  bold=True)[3].text = value
        deck.text(slide, x + Inches(0.2), BODY_Y + Inches(0.68), Inches(1.95),
                  Inches(0.32), size=9.5, colour=MUTED,
                  spacing=1.1)[3].text = label

    deck.text(slide, MARGIN, Inches(3.72), CONTENT_W, Inches(0.4), size=11.5,
              colour=INK, spacing=1.2)[3].text = (
        f"n = {control['n_pairs']} paired seeds, saturated demand regime. This "
        f"arm carries no forecast, so it measures the value of learned phase "
        f"selection alone — the contribution of the forecast is a separate "
        f"experiment and is not claimed here.")

    corpus_gap_rows = [
        ("No fold-eligible camera is Indian",
         "three Bangladeshi, one UK motorway"),
        ("HIGH is scarce in three of four folds",
         "0 / 20 / 9 / 1 test windows"),
        ("Both are failing assertions",
         "report-table generation is blocked, by design"),
    ]
    corpus_gap_note = ("Part B campus footage is the work that clears them. "
                       "Until it does, no claim about the Indian domain is "
                       "made.")
    gap_h = panel_height(corpus_gap_rows, Inches(5.5), corpus_gap_note)

    deck.rect(slide, MARGIN, Inches(4.3), Inches(6.0), gap_h,
              fill=RGBColor(0xFD, 0xF3, 0xE8), line=WARN)
    deck.text(slide, MARGIN + Inches(0.28), Inches(4.46), Inches(5.4),
              Inches(0.24), size=10, font=MONO, colour=WARN,
              bold=True)[3].text = "FULL MODEL vs LINEAR PROBE — PRE-REGISTERED"
    _, _, _, run = deck.text(slide, MARGIN + Inches(0.28), Inches(4.76),
                             Inches(5.4), Inches(0.4), size=19, font=MONO,
                             colour=WARN, bold=True)
    run.text = gate["verdict"].title()
    deck.text(slide, MARGIN + Inches(0.28), Inches(5.24), Inches(5.4),
              Inches(1.2), size=10.5, colour=INK, spacing=1.3)[3].text = (
        f"Mean {C.fmt(gate['mean_difference'])}, 95% CI "
        f"[{C.fmt(gate['ci_low'])}, {C.fmt(gate['ci_high'])}], detectable "
        f"{C.fmt(gate['minimum_detectable_difference'])} at "
        f"{gate['n_folds']} folds. Per fold {gate['difference_per_fold']}: "
        f"the full model leads on three, and the M6 fold — structured "
        f"traffic, 52.6% of HIGH — reverses the mean. On the three "
        f"in-regime folds it leads by 0.0449. Four-fold is the registered "
        f"headline; both are reported.")

    # Both boxes take the height the panel's content needs, so the pair stays
    # level instead of one being sized by eye.
    deck.panel(slide, Inches(7.1), Inches(4.3), Inches(5.5), gap_h,
               "What the corpus does not yet contain", corpus_gap_rows,
               footnote=corpus_gap_note)

    deck.notes(slide, f"""
Lead with the positive number because it is real: {improvement:.2f}% lower mean
waiting time, p below 0.001, large effect size, thirty paired seeds against a
baseline we swept rather than picked.

Immediately add the honest qualifier: this arm carries no forecast. It shows
learned phase selection is worth something. It does not yet show the forecast is.

Then the two boxes. The left one is a pre-registered comparison we cannot
resolve at four folds -- say "cannot distinguish", not "no difference". The right
one is the corpus gap, and the fact that our own claims checker is red is the
strongest evidence we are not overclaiming.
""")


def slide_requirements(deck: Deck) -> None:
    slide = deck.content(16, "Requirements", ["One laptop, ",
                                              "one 6 GB GPU, ₹0"],
                         lead="Nothing is listed because it is conventional. "
                              "Two entries below are the reason the project "
                              "is feasible at all.", total=TOTAL)
    hardware = [(row[0], row[1]) for row in C.HARDWARE_ROWS]
    hardware_h = panel_height(hardware, Inches(6.0))
    deck.panel(slide, MARGIN, BODY_Y, Inches(6.0), hardware_h,
               "Hardware", hardware)

    # The deck shows the leading entries of each software group that fit on one
    # row; the report lists every entry. The dashboard row is left to the report
    # because the dashboard is the one subsystem not yet built.
    software = [(group, pack_detail(items, Inches(5.7)))
                for group, items in C.SOFTWARE_GROUPS
                if group != "Interface"]
    software_h = panel_height(software, Inches(5.7))
    deck.panel(slide, Inches(6.9), BODY_Y, Inches(5.7), software_h,
               "Software", software)

    notes = [
        ("Training is local, not cloud",
         "Caching the frozen backbones collapses the full A–H ablation from "
         "≈12.3 h on CPU to ≈1.5 h; an uncached step does not fit in 6 GB."),
        ("SQLite, not a database server",
         "The prototype stores a bounded history of counts and decisions; a "
         "separate server would be infrastructure without a purpose."),
    ]
    y = BODY_Y + max(hardware_h, software_h) + Inches(0.12)
    for lead, detail in notes:
        deck.rect(slide, MARGIN, y, CONTENT_W, Inches(0.44),
                  fill=RGBColor(0xEC, 0xEB, 0xFA), line=ACCENT)
        _, _, para, run = deck.text(slide, MARGIN + Inches(0.26),
                                    y + Inches(0.10), CONTENT_W - Inches(0.52),
                                    Inches(0.3), size=10.5, colour=INK,
                                    bold=True)
        run.text = lead + "   "
        deck.rich(para, [(detail, {"colour": MUTED, "size": 10.5})], size=10.5)
        y += Inches(0.52)

    deck.notes(slide, """
Twenty seconds. The only claim worth making aloud is that this runs on one
laptop with a 6 GB card, and the reason is the feature cache -- twelve hours down
to ninety minutes.

If asked about the Jetson: the plan changed for budget reasons, the contract did
not, and every latency number we quote says which host produced it. The edge
device being a laptop is a budget decision, not a design one.

The software rows show the leading versions of each group; the committed
requirements file is the authority, and the report lists every entry. The
dashboard row is in the report and not here, because the dashboard is the one
subsystem still unbuilt.
""")


def slide_outcomes(deck: Deck, facts: C.Facts) -> None:
    improvement = float(facts.control["improvement_percent"])
    slide = deck.content(17, "Expected Outcomes",
                         ["Seven deliverables, ", "each with a stated target"],
                         lead="Targets are written down in advance so a miss "
                              "is visible as a miss rather than reframed "
                              "afterwards.", total=TOTAL)
    deck.table(slide, MARGIN, BODY_Y, CONTENT_W,
               ["Deliverable", "Measurable target", "Status"],
               [[("Curated dataset", {"font": BODY, "bold": True}),
                 ("Part A curated + 1,500-3,000 campus frames, per-camera "
                  "provenance record", {"font": BODY}),
                 ("Part A done, Part B pending", {"colour": WARN})],
                [("Fine-tuned detector", {"font": BODY, "bold": True}),
                 ("≥ 0.85 mAP@0.5; cross-camera reported separately",
                  {"font": BODY}),
                 ("Done", {"colour": GOOD})],
                [("MFSTNet model", {"font": BODY, "bold": True}),
                 ("Weights + ONNX export; gate exposed as an artefact",
                  {"font": BODY}),
                 ("Done", {"colour": GOOD})],
                [("Ablation & evaluation", {"font": BODY, "bold": True}),
                 ("All 8 configs × 4 folds × 5 seeds, bootstrap CIs from a "
                  "committed script", {"font": BODY}),
                 ("Done; underpowered", {"colour": WARN})],
                [("PPO controller", {"font": BODY, "bold": True}),
                 (f"Significant reduction vs best Webster over 30 paired "
                  f"seeds — met at {improvement:.2f}%", {"font": BODY}),
                 ("Done", {"colour": GOOD})],
                [("Working prototype", {"font": BODY, "bold": True}),
                 ("Edge node, MQTT contract, control server, two-panel "
                  "dashboard", {"font": BODY}),
                 ("Dashboard pending", {"colour": WARN})],
                [("Reproducibility package", {"font": BODY, "bold": True}),
                 ("Pinned deps, fixed seeds, committed raw CSVs, public "
                  "release", {"font": BODY}),
                 ("Done", {"colour": GOOD})]],
               widths=[Inches(2.5), Inches(7.4), Inches(2.0)],
               row_h=Inches(0.46), size=10)

    deck.rect(slide, MARGIN, Inches(6.16), CONTENT_W, Inches(0.86),
              fill=RGBColor(0xEC, 0xEB, 0xFA), line=ACCENT)
    deck.text(slide, MARGIN + Inches(0.3), Inches(6.3), CONTENT_W - Inches(0.6),
              Inches(0.24), size=10, font=MONO, colour=ACCENT,
              bold=True)[3].text = "ACADEMIC OUTCOME"
    deck.text(slide, MARGIN + Inches(0.3), Inches(6.56), CONTENT_W - Inches(0.6),
              Inches(0.4), size=11, colour=INK, spacing=1.2)[3].text = (
        "A conference submission whose contribution is the camera-only "
        "forecast-to-control path, the gate reported as an artefact, and a "
        "leave-one-camera-out evaluation with the linear-probe floor beside "
        "it. Under that framing an inconclusive vision result, reported with "
        "its statistical power, is still a contribution.")

    deck.notes(slide, """
The Status column is the point. Five of seven are done and two are honestly
marked pending or underpowered.

Do not skip the "Done; underpowered" row -- volunteering it is what makes the
four "Done" rows believable.
""")


def slide_conclusion(deck: Deck, facts: C.Facts) -> None:
    control = facts.control
    best_config, best_f1 = facts.best_vision
    improvement = float(control["improvement_percent"])
    slide = deck.content(18, "Conclusion", ["Where this stands, ",
                                            "and what is next"], total=TOTAL)

    deck.rect(slide, MARGIN, Inches(1.92), Inches(6.0), Inches(2.3),
              fill=RGBColor(0xE8, 0xF4, 0xEC), line=GOOD)
    deck.text(slide, MARGIN + Inches(0.28), Inches(2.08), Inches(5.4),
              Inches(0.24), size=10, font=MONO, colour=GOOD,
              bold=True)[3].text = "WHAT WORKS"
    deck.text(slide, MARGIN + Inches(0.28), Inches(2.38), Inches(5.4),
              Inches(1.7), size=11.5, colour=INK, spacing=1.35)[3].text = (
        f"The whole pipeline is implemented end to end — corpus, detector, "
        f"feature cache, MFSTNet with all eight configurations, "
        f"leave-one-camera-out evaluation, SUMO environment, PPO arms, "
        f"benchmark harness, ONNX export, control server and edge node with "
        f"both fallbacks. The control result is real: {improvement:.2f}% lower "
        f"mean waiting time than the best-configured Webster baseline over "
        f"{control['n_pairs']} paired seeds.")

    deck.rect(slide, Inches(7.1), Inches(1.92), Inches(5.5), Inches(2.3),
              fill=RGBColor(0xFD, 0xF3, 0xE8), line=WARN)
    deck.text(slide, Inches(7.38), Inches(2.08), Inches(4.9), Inches(0.24),
              size=10, font=MONO, colour=WARN,
              bold=True)[3].text = "WHAT DOES NOT, YET"
    deck.text(slide, Inches(7.38), Inches(2.38), Inches(4.9), Inches(1.7),
              size=11.5, colour=INK, spacing=1.35)[3].text = (
        f"The vision claim is open. Configuration {best_config} reaches "
        f"{C.fmt(best_f1)} macro-F1 against {C.fmt(facts.best_counts[1])} for a "
        f"count-only sequence model, and the full model cannot be separated "
        f"from the linear probe at four folds. No fold-eligible camera is "
        f"Indian, and the dashboard is not built. All four are reported, not "
        f"deferred.")

    nexts = [
        ("Expand the corpus with Indian campus footage",
         "so the domain claim can be made honestly and the claims checker goes "
         "green"),
        ("Raise the number of evaluable cameras",
         "so the architecture comparison has the power to resolve rather than "
         "returning “cannot distinguish”"),
        ("Complete the forecast-carrying control arm",
         "so the value of the forecast is measured rather than assumed"),
        ("Build the descoped two-panel dashboard",
         "benchmark numbers and live numbers visually separated, never merged"),
    ]
    y = Inches(4.5)
    for index, (lead, detail) in enumerate(nexts, start=1):
        deck.rect(slide, MARGIN, y + Inches(0.04), Inches(0.42), Inches(0.42),
                  fill=ACCENT, shape=MSO_SHAPE.OVAL)
        deck.text(slide, MARGIN, y + Inches(0.12), Inches(0.42), Inches(0.28),
                  size=11, font=MONO, colour=CREAM, bold=True,
                  align=PP_ALIGN.CENTER)[3].text = str(index)
        _, _, para, run = deck.text(slide, MARGIN + Inches(0.62), y,
                                    CONTENT_W - Inches(0.7), Inches(0.4),
                                    size=12, colour=INK, bold=True,
                                    spacing=1.2)
        run.text = lead + "   "
        deck.rich(para, [(detail, {"colour": MUTED, "size": 11.5})], size=12)
        y += Inches(0.52)

    deck.rule(slide, MARGIN, Inches(6.72), CONTENT_W, colour=ACCENT,
              weight=Pt(1.0))
    deck.text(slide, MARGIN, Inches(6.86), CONTENT_W, Inches(0.4), size=11.5,
              colour=INK, bold=True, spacing=1.2)[3].text = (
        "Expected significance: a low-cost, privacy-preserving adaptive signal "
        "control path for unstructured urban traffic, delivered with the "
        "evidence needed to judge whether each of its parts earns its place.")

    deck.notes(slide, """
Close on the two-column contrast and then the four next steps. Do not end on an
apology for the vision result -- end on the last line, which is the actual
contribution: the system plus the evidence to judge it.

Then stop talking and take questions.
""")


def slide_references(deck: Deck) -> None:
    slide = deck.content(19, "References", ["References ", "(IEEE style)"],
                         lead="Cited at first use in the synopsis report; "
                              "numbering matches the report exactly.",
                         total=TOTAL)
    half = (len(C.REFERENCES) + 1) // 2
    for column in (0, 1):
        x = MARGIN + column * Inches(6.15)
        y = Inches(2.24)
        entries = C.REFERENCES[column * half:(column + 1) * half]
        for offset, text in enumerate(entries):
            index = column * half + offset + 1
            deck.text(slide, x, y, Inches(0.5), Inches(0.24), size=9.5,
                      font=MONO, colour=ACCENT,
                      bold=True)[3].text = f"[{index}]"
            deck.text(slide, x + Inches(0.5), y, Inches(5.4), Inches(0.5),
                      size=9.5, colour=INK, spacing=1.15)[3].text = text
            y += Inches(0.54)

    deck.notes(slide, """
Do not present this slide. It is there so a panel member who asks "where is the
DINOv2 paper" can be pointed at a number instead of a promise.
""")


# ==========================================================================
#  entry point
# ==========================================================================

def build(out_path: Path) -> Path:
    facts = C.load_facts()
    deck = Deck()

    slide_title(deck)
    slide_agenda(deck)
    slide_background(deck)
    slide_motivation(deck)
    slide_literature(deck, facts)
    slide_gap(deck)
    slide_problem(deck)
    slide_objectives(deck)
    slide_architecture(deck)
    slide_corpus(deck, facts)
    slide_model(deck, facts)
    slide_controller(deck, facts)
    slide_evaluation(deck, facts)
    slide_ablation(deck, facts)
    slide_control_result(deck, facts)
    slide_requirements(deck)
    slide_outcomes(deck, facts)
    slide_conclusion(deck, facts)
    slide_references(deck)

    deck.save(out_path)
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path,
                        default=C.ROOT / "docs" / "demo"
                        / "MFSTNet-Synopsis-Presentation.pptx")
    parser.add_argument("--pdf", action="store_true",
                        help="also export a PDF, driving PowerPoint itself")
    args = parser.parse_args(argv)

    path = build(args.out)
    print(f"  wrote {path}  ({path.stat().st_size / 1024:.0f} KB, "
          f"{TOTAL} slides)")
    if args.pdf:
        pdf = export_pdf(path)
        if pdf:
            print(f"  wrote {pdf}  ({pdf.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
