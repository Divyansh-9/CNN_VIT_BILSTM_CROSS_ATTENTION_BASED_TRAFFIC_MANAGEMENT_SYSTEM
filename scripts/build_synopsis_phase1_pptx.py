"""Build the **Phase I** synopsis presentation as a real PowerPoint file.

The companion deck to `scripts/build_synopsis_phase1_docx.py`, and the same
document in spoken form: what the team decided to build, what it was chosen
over, and how the twenty weeks are sequenced. Like the proposal report, it
quotes **no measured result** — it imports `synopsis_phase1_content`, which has
no access to `load_facts()`, so a result cannot reach a slide by accident.

Identity comes from `scripts/synopsis_content.py` so that the title, Project
Team ID, names, roll numbers and mentor are the same characters on every
artefact the project submits (guideline §1, verified again at §10).

Visual grammar, palette and the `Deck` helper are reused from
`scripts/build_review_pptx.py`, and the panel-geometry helpers from
`scripts/build_synopsis_pptx.py`, so the two decks read as one project.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

from pptx.dml.color import RGBColor  # noqa: E402
from pptx.enum.text import PP_ALIGN  # noqa: E402
from pptx.util import Inches, Pt  # noqa: E402

from scripts import synopsis_phase1_content as P  # noqa: E402
from scripts.build_review_pptx import (ACCENT, AMBER, BAD, BODY, CONTENT_W,  # noqa: E402
                                       CREAM, Deck, DEEP, DIM_CREAM, FAINT,
                                       GOOD, INK, MARGIN, MONO, MUTED, PANEL,
                                       RULE, W, WARN, export_pdf)
from scripts.build_synopsis_pptx import BODY_Y, panel_height  # noqa: E402

TOTAL = 19

HALF = Inches(5.7)
RIGHT_X = Inches(7.1)

#: Horizontal advance per character per point, measured off the two typefaces
#: this deck uses. `Deck.table` draws a cell as a fixed 0.26 in box and does not
#: grow it, so a cell that needs a second line is drawn over the rule beneath
#: it. These constants are what `_fits` uses to keep every cell on one line, and
#: they are the reason prose columns are handed `{"font": BODY}` — the monospace
#: default costs about a third more width for the same sentence.
MONO_PER_PT = 0.079 / 11
BODY_PER_PT = 0.060 / 11

#: `Deck.table` insets each cell by this much before drawing its text box.
CELL_INSET = Inches(0.1)


# ==========================================================================
#  slides
# ==========================================================================

def slide_title(deck: Deck) -> None:
    slide = deck._blank(DEEP)
    deck.slides.append(slide)

    deck.text(slide, MARGIN, Inches(0.52), Inches(11), Inches(0.3),
              size=10.5, font=MONO, colour=AMBER, bold=True)[3].text = (
        f"MAJOR PROJECT SYNOPSIS  ·  PHASE I PROPOSAL  ·  "
        f"B.TECH {P.BRANCH}  ·  PROJECT TEAM ID  {P.TEAM_ID}")

    _, _, para, run = deck.text(slide, MARGIN, Inches(0.98), Inches(11.4),
                                Inches(1.42), size=34, colour=CREAM, bold=True,
                                spacing=0.95)
    run.text = ("MFSTNet — Multimodal Spatio-Temporal\n"
                "Congestion Forecasting for\n")
    deck.rich(para, [("Adaptive Traffic Signal Control",
                      {"colour": AMBER, "bold": True, "size": 34})], size=34)

    # The title is three 34 pt lines at 0.95 spacing, which occupy about
    # 1.62 in — so the working name has to clear 2.65, not the 1.42 in the box
    # is nominally tall. And the lead paragraph is given the full content width
    # so it sets in two lines rather than three; at three it runs into the team
    # cards at 3.80.
    _, _, _, run = deck.text(slide, MARGIN, Inches(2.68), Inches(9.6),
                             Inches(0.34), size=11, font=MONO, colour=AMBER)
    run.text = f"working name:  {P.WORKING_NAME}"

    _, _, _, run = deck.text(slide, MARGIN, Inches(3.02), Inches(11.4),
                             Inches(0.7), size=13, colour=DIM_CREAM,
                             spacing=1.35)
    run.text = ("A proposal to forecast per-lane congestion 60 seconds ahead "
                "from an existing traffic camera alone, and to let a "
                "reinforcement-learning controller act on that forecast — no "
                "new roadside sensor, and no raw frame leaving the camera.")

    for index, member in enumerate(P.TEAM):
        x = MARGIN + index * Inches(2.95)
        deck.rect(slide, x, Inches(3.80), Inches(2.72), Inches(1.06),
                  fill=RGBColor(0x2A, 0x26, 0x63),
                  line=RGBColor(0x3D, 0x38, 0x82))
        deck.text(slide, x + Inches(0.22), Inches(3.94), Inches(2.3),
                  Inches(0.2), size=8.5, font=MONO,
                  colour=AMBER if member.lead else DIM_CREAM,
                  bold=True)[3].text = ("TEAM LEAD" if member.lead
                                        else f"SECTION {member.section}")
        deck.text(slide, x + Inches(0.22), Inches(4.18), Inches(2.34),
                  Inches(0.3), size=13.5, colour=CREAM,
                  bold=True)[3].text = member.name
        deck.text(slide, x + Inches(0.22), Inches(4.48), Inches(2.34),
                  Inches(0.3), size=9.5, font=MONO,
                  colour=DIM_CREAM)[3].text = (f"{member.roll}   ·   "
                                               f"{member.section}")

    deck.rule(slide, MARGIN, Inches(5.14), CONTENT_W,
              colour=RGBColor(0x3D, 0x38, 0x82))

    _, _, guide_para, guide_run = deck.text(
        slide, MARGIN, Inches(5.32), Inches(6.4), Inches(0.25),
        size=11, colour=DIM_CREAM)
    guide_run.text = "Under the guidance of   "
    deck.rich(guide_para, [(f"{P.MENTOR_NAME}, {P.MENTOR_DESIGNATION}",
                            {"colour": CREAM, "bold": True, "size": 11})],
              size=11)

    for offset, text, size, colour in (
            (0.50, P.DEPARTMENT, 11.5, CREAM),
            (0.76, P.INSTITUTE, 12.5, CREAM),
            (1.02, f"{P.PLACE}   ·   {P.SUBMISSION_MONTH}", 10.5, DIM_CREAM)):
        deck.text(slide, MARGIN, Inches(5.32 + offset), Inches(7.0),
                  Inches(0.3), size=size, colour=colour,
                  bold=colour is CREAM)[3].text = text

    emblem = P.ASSETS / "gehu-emblem.jpeg"
    if emblem.is_file():
        slide.shapes.add_picture(str(emblem), W - MARGIN - Inches(1.45),
                                 Inches(5.24), height=Inches(1.45))

    deck.notes(slide, """
This is the Phase I proposal, not a progress report. Say that in the first
sentence, because it sets what the panel should expect: a plan, its
justification, and the schedule -- no results yet.

One-line version of the idea: forecast congestion per lane, sixty seconds
ahead, from camera video alone, and let the controller act on the forecast.

Name the working name on the slide once. It is how the idea appears in our
early records, and it says what the pipeline is.
""")


def slide_agenda(deck: Deck) -> None:
    slide = deck.content(2, "Structure", ["What this proposal ", "covers"],
                         lead="The deck follows the synopsis chapter order, "
                              "so a panel reading along can follow.",
                         total=TOTAL)
    left = [("1  Introduction",
             "Background, motivation, and how the idea was selected from five"),
            ("2  Literature Review",
             "Four strands, each mature on its own, and the gap between them"),
            ("3  Problem Statement & Objectives",
             "One problem, three research questions, six objectives O1-O6"),
            ("4  Proposed Methodology",
             "Design decisions, architecture, corpus, model, control, plan")]
    right = [("5  Hardware & Software",
              "What the project needs — one laptop and one 6 GB GPU"),
             ("6  Expected Outcomes",
              "Seven deliverables and the targets set in advance for each"),
             ("7  Conclusion",
              "What is committed to, and what is deliberately left out"),
             ("References",
              "IEEE style, 16 entries, each cited in the report")]
    deck.bullets(slide, MARGIN, BODY_Y, HALF, left, gap=Inches(0.88))
    deck.bullets(slide, RIGHT_X, BODY_Y, Inches(5.5), right, gap=Inches(0.88))

    deck.rect(slide, MARGIN, Inches(6.28), CONTENT_W, Inches(0.62),
              fill=PANEL, line=RULE)
    _, _, para, run = deck.text(slide, MARGIN + Inches(0.28), Inches(6.44),
                                CONTENT_W - Inches(0.56), Inches(0.4),
                                size=11, colour=INK, spacing=1.2)
    run.text = "One thing to hold onto throughout:  "
    deck.rich(para, [("this is a proposal. Every number in it is a target set "
                      "in advance, not a measurement. Nothing here reports a "
                      "result, because the work starts now.",
                      {"colour": MUTED, "size": 11})], size=11)

    deck.notes(slide, """
Twenty seconds. The only job of this slide is to tell the panel that the deck
maps onto the report in front of them.

Read the band at the bottom out loud. It is the difference between a proposal
and a progress report, and stating it early stops a panel from asking for
results we have not claimed to have.
""")


def slide_background(deck: Deck) -> None:
    slide = deck.content(3, "Introduction",
                         ["A signal allocates green ", "from a survey taken once"],
                         lead="Fixed-time control computes cycle length and "
                              "phase splits from a manual count, then holds "
                              "them for years.", total=TOTAL)
    deck.bullets(slide, MARGIN, BODY_Y, Inches(6.0), [
        ("The plan is right on average",
         "and therefore wrong most of the time — green is held on an empty "
         "approach while a saturated one waits."),
        ("The stream is heterogeneous",
         "A two-wheeler, an auto-rickshaw and a bus occupy different road "
         "space and discharge at different rates."),
        ("The stream is not lane disciplined",
         "Vehicles sit between nominal lanes, so queue geometry does not "
         "follow the markings on the road."),
        ("Counting vehicles measures the wrong thing",
         "Indian practice already says so: the capacity manual publishes "
         "passenger-car equivalents for exactly this reason."),
    ], gap=Inches(0.92))

    items = [("Cameras already exist", "installed for enforcement, at most junctions"),
             ("Loops and probes do not", "and cost money the deployment does not have"),
             ("A decision acts on the future", "the next 30-90 s, not the present queue"),
             ("So forecast, do not measure", "one cycle ahead is the useful horizon")]
    footnote = ("Camera-only is a harder problem than sensor-fusion. "
                "It is chosen because it is the one that can actually "
                "be deployed on the junctions this targets.")
    # The footnote has to be declared to `panel_height` as well as to `panel`:
    # the height is what reserves room for it, and a panel sized without it
    # draws its own footnote below the box.
    height = panel_height(items, Inches(5.2), footnote)
    deck.panel(slide, Inches(7.4), BODY_Y, Inches(5.2), height,
               "Why this framing", items, footnote=footnote)

    deck.notes(slide, """
Do not read the four bullets. Say the one sentence that carries them: a
fixed-time plan is computed once from a count taken once, and then applied at
every hour of every day.

The panel on the right is the argument for the whole project. Cameras exist;
loops and probes do not. And a phase decision takes effect over the next
half-minute to minute and a half, so the controller needs the near future, not
the present.
""")


def slide_selection(deck: Deck) -> None:
    slide = deck.content(4, "Introduction",
                         ["How the idea ", "was chosen"],
                         lead="Five candidates were scored on four criteria "
                              "before one was fixed. The shortlist is recorded "
                              "rather than discarded.", total=TOTAL)

    name_w = Inches(3.5)
    decision_w = CONTENT_W - name_w
    rows = [[cell(name, name_w, bold=True), cell(decision, decision_w)]
            for name, _needs, decision in P.IDEA_CANDIDATES]
    deck.table(slide, MARGIN, BODY_Y, CONTENT_W,
               ["Candidate idea", "Decision"], rows,
               widths=[name_w, decision_w],
               size=10, row_h=Inches(0.52), highlight=(len(rows) - 1,))

    deck.rect(slide, MARGIN, Inches(5.52), CONTENT_W, Inches(0.80),
              fill=PANEL, line=RULE)
    _, _, para, run = deck.text(slide, MARGIN + Inches(0.28), Inches(5.66),
                                CONTENT_W - Inches(0.56), Inches(0.56),
                                size=11, colour=INK, spacing=1.2)
    run.text = "The four criteria:  "
    deck.rich(para, [("every input obtainable without a dependency outside the "
                      "team; a component that can be ablated and therefore "
                      "defended; a fit inside twenty weeks at a zero-rupee cash "
                      "budget; and a negative result that is still a reportable "
                      "finding rather than a failed project.",
                      {"colour": MUTED, "size": 11})], size=11)

    deck.notes(slide, """
This is the slide a panel remembers, so spend time on it. It shows the choice
was made rather than assumed.

Name one rejected idea and why -- the pothole detector needed a moving camera
and had no team-owned route to labels. Then the fourth criterion, which is the
one that matters most: we wanted a project where a negative result is still a
result. That is why the count-only baseline is in the experiment from week one.
""")


def slide_literature(deck: Deck) -> None:
    slide = deck.content(5, "Literature Review",
                         ["Four strands, each mature ", "on its own"],
                         lead="Every mechanism this project uses is published. "
                              "What is not published is the combination, for "
                              "this setting, reported this way.", total=TOTAL)

    left = [("Visual representation  [2] [3] [4]",
             "Residual networks are strong locally; a queue is a global "
             "quantity. Self-supervised ViT features transfer without "
             "fine-tuning — which is what makes a frozen branch affordable."),
            ("Fusion  [1]",
             "Cross-attention and gated combination are standard. What is "
             "never reported is the gate itself — the quantity that says "
             "which branch the model actually relied on.")]
    right = [("Temporal modelling  [14] [15]",
              "Sixty steps is short: long enough for a recurrence to carry "
              "something, too short to train a transformer from scratch on a "
              "corpus this size."),
             ("Signal control  [7] [9] [10] [13]",
              "PPO on a SUMO intersection is established. The recurring "
              "methodological problem in the surveys is weak baselines and "
              "single-seed reporting.")]
    deck.bullets(slide, MARGIN, BODY_Y, HALF, left, gap=Inches(1.42))
    deck.bullets(slide, RIGHT_X, BODY_Y, Inches(5.5), right, gap=Inches(1.42))

    deck.rect(slide, MARGIN, Inches(5.60), CONTENT_W, Inches(1.06),
              fill=PANEL, line=RULE)
    deck.text(slide, MARGIN + Inches(0.28), Inches(5.76),
              CONTENT_W - Inches(0.56), Inches(0.24), size=10, font=MONO,
              colour=ACCENT, bold=True)[3].text = "THE GAP, IN ONE SENTENCE"
    deck.text(slide, MARGIN + Inches(0.28), Inches(6.02),
              CONTENT_W - Inches(0.56), Inches(0.5), size=11.5, colour=INK,
              spacing=1.2)[3].text = (
        "No fixed-camera junction dataset for unstructured traffic carries "
        "per-lane congestion labels; no published work reports what a "
        "CNN-to-ViT fusion gate learns on traffic imagery; and learned "
        "controllers are rarely measured against a baseline that was itself "
        "tuned first.")

    deck.notes(slide, """
Be explicit that we are not claiming the mechanisms. Cross-attention, gating,
frozen backbones and PPO control are all published, and saying so is what makes
the rest of the claim credible.

The three-part gap at the bottom is the slide. Read it, do not paraphrase it,
and then move on -- the methodology chapter is where it gets discharged.
""")


def slide_problem(deck: Deck) -> None:
    slide = deck.content(6, "Problem Statement",
                         ["One problem, ", "stated precisely"],
                         lead="Every clause below is load-bearing; each one "
                              "excludes an easier problem we are choosing not "
                              "to solve.", total=TOTAL)

    deck.rect(slide, MARGIN, BODY_Y, CONTENT_W, Inches(1.30),
              fill=PANEL, line=RULE)
    deck.text(slide, MARGIN + Inches(0.32), BODY_Y + Inches(0.22),
              CONTENT_W - Inches(0.64), Inches(0.9), size=13, colour=INK,
              spacing=1.28)[3].text = (
        "Given only the video streams of fixed cameras at a signalised "
        "junction carrying heterogeneous, non-lane-disciplined traffic, "
        "predict the congestion level of each approach 60 seconds ahead, and "
        "use that prediction to select the next phase and its duration so that "
        "mean waiting time is lower than under a tuned fixed-time plan — with "
        "no raw frame transmitted off the capture device.")

    y = Inches(4.06)
    deck.bullets(slide, MARGIN, y, HALF, [
        (tag, text) for tag, text in P.RESEARCH_QUESTIONS[:2]
    ], gap=Inches(1.30))
    deck.bullets(slide, RIGHT_X, y, Inches(5.5), [
        P.RESEARCH_QUESTIONS[2],
        ("Why each is stated this way",
         "A negative answer to any of the three is a reportable finding, not "
         "a failed project. That is deliberate."),
    ], gap=Inches(1.30))

    deck.notes(slide, """
Read the boxed statement verbatim. It is the one paragraph in the deck worth
reading aloud word for word, because every clause was argued over.

Then the three research questions. Stress the last line: each question is
written so that "no" is publishable. RQ1 answered "no" would mean the
appearance branch does not earn its place, and we would report that.
""")


def slide_objectives(deck: Deck) -> None:
    slide = deck.content(7, "Objectives", ["Six objectives, ", "in dependency order"],
                         lead="O1-O3 are Phase I and mandatory. O4-O5 are "
                              "Phase II. O6 is Phase III and optional.",
                         total=TOTAL)
    left = [(tag, text) for tag, text in P.OBJECTIVES[:3]]
    right = [(tag, text) for tag, text in P.OBJECTIVES[3:]]
    deck.bullets(slide, MARGIN, BODY_Y, HALF, left, gap=Inches(1.34))
    deck.bullets(slide, RIGHT_X, BODY_Y, Inches(5.5), right, gap=Inches(1.34))

    deck.notes(slide, """
Do not read all six. Say that they are ordered by dependency -- each needs the
one before it -- and that the first three are the mandatory core.

If asked why O6 is optional: because a live runtime integration that is not
reached does not invalidate anything measured in O4 and O5, and pretending
otherwise is how projects end up with nothing finished.
""")


def slide_decisions(deck: Deck) -> None:
    slide = deck.content(8, "Methodology",
                         ["What we chose, ", "and what we changed"],
                         lead="Thirteen decisions were taken from a shortlist. "
                              "Six of them are where the design moved most.",
                         total=TOTAL)

    picks = ["Vision transformer", "Backbone regime", "Fusion mechanism",
             "Evaluation split", "Edge device", "Datastore"]
    chosen = {row[0]: row for row in P.DESIGN_CHOICES}
    widths = [Inches(2.6), Inches(6.0), CONTENT_W - Inches(8.6)]
    rows = []
    for name in picks:
        component, alternatives, selected, _reason = chosen[name]
        rows.append([cell(component, widths[0], bold=True),
                     cell(alternatives, widths[1]),
                     cell(selected, widths[2], colour=ACCENT)])

    deck.table(slide, MARGIN, BODY_Y, CONTENT_W,
               ["Component", "Considered", "Selected"], rows,
               widths=widths, size=10, row_h=Inches(0.46))

    deck.rect(slide, MARGIN, Inches(5.90), CONTENT_W, Inches(1.00),
              fill=PANEL, line=RULE)
    deck.text(slide, MARGIN + Inches(0.28), Inches(6.06),
              CONTENT_W - Inches(0.56), Inches(0.24), size=10, font=MONO,
              colour=ACCENT, bold=True)[3].text = (
        "TWO OF THESE ARE FORCED, NOT PREFERRED")
    deck.text(slide, MARGIN + Inches(0.28), Inches(6.32),
              CONTENT_W - Inches(0.56), Inches(0.5), size=11, colour=MUTED,
              spacing=1.2)[3].text = (
        "Frozen backbones are forced by 6 GB of video memory — an uncached "
        "step at the specified batch size pushes 1,920 frames through both "
        "backbones and does not fit. The edge device is a team laptop because "
        "the cash budget is zero, which is why every latency figure this "
        "project reports must name the host it was measured on.")

    deck.notes(slide, """
This is the second slide worth dwelling on. It answers "what did you try and
change", which is the question a proposal review actually asks.

Pick two to narrate. The ViT went from supervised ViT-S/16 to DINOv2 ViT-S/14,
because with frozen backbones the representation is the whole contribution --
and note the patch size changed from 16 to 14, so token counts get read from
config rather than assumed. The split went from a random 60/20/20 to
leave-one-camera-out, because a random split lets the model recognise a camera
it has already seen and reports that as generalisation.

Be honest about the bottom band. Two of these are constraints wearing the
clothes of decisions.
""")


def slide_architecture(deck: Deck) -> None:
    slide = deck.content(9, "Methodology", ["Three tiers, ", "one privacy boundary"],
                         lead="Frames are read, processed and discarded inside "
                              "the edge tier. Only counts, predictions and "
                              "commands cross the network.", total=TOTAL)

    tiers = [
        ("EDGE  ·  team laptop at the camera",
         ["Fixed CCTV frames — never transmitted, never written to disk",
          "YOLOv8s detection over 8 India-relevant classes",
          "Per-lane counting on hand-placed, reviewed lane centres",
          "Local Webster fallback, armed if the broker is silent > 10 s"]),
        ("SERVER  ·  FastAPI + ONNX + PPO",
         ["MFSTNet (ONNX) — per-lane congestion, 60 s ahead",
          "PPO policy — 16-dim observation, 12 discrete actions",
          "SignalGuard — min/max green, all-red, clamping outside HTTP",
          "SQLite — bounded history of counts and decisions"]),
        ("DASHBOARD  ·  React",
         ["Live panel — counts, predictions, gate value",
          "Benchmark panel — from the committed CSV",
          "The two panels never merge",
          "Refresh budget 2 s"]),
    ]
    width = Inches(3.86)
    for index, (title, lines) in enumerate(tiers):
        x = MARGIN + index * Inches(4.06)
        deck.rect(slide, x, BODY_Y, width, Inches(2.62), fill=PANEL, line=RULE)
        deck.text(slide, x + Inches(0.24), BODY_Y + Inches(0.20),
                  width - Inches(0.48), Inches(0.24), size=9.5, font=MONO,
                  colour=ACCENT, bold=True)[3].text = title.upper()
        y = BODY_Y + Inches(0.58)
        for line in lines:
            deck.text(slide, x + Inches(0.24), y, width - Inches(0.48),
                      Inches(0.46), size=10.5, colour=INK,
                      spacing=1.15)[3].text = "·  " + line
            y += Inches(0.50)

    deck.rect(slide, MARGIN, Inches(5.28), CONTENT_W, Inches(0.56),
              fill=RGBColor(0xEC, 0xEB, 0xFA), line=RULE)
    deck.text(slide, MARGIN + Inches(0.28), Inches(5.42),
              CONTENT_W - Inches(0.56), Inches(0.3), size=10.5, font=MONO,
              colour=INK, bold=True)[3].text = (
        "MQTT CONTRACT   —   EMERGENCY QoS 2   |   COUNTS AND COMMANDS QoS 1  "
        " |   PREDICTIONS AND HEARTBEAT QoS 0")

    deck.text(slide, MARGIN, Inches(6.08), CONTENT_W, Inches(0.7),
              size=11.5, colour=MUTED, spacing=1.2)[3].text = (
        "Two fallback paths are required behaviour rather than robustness "
        "extras: if the forecast is unavailable the controller runs on counts "
        "alone with the four forecast entries zeroed — never with a shortened "
        "observation vector — and if the broker is silent for more than ten "
        "seconds the edge node arms its own fixed-time controller.")

    deck.notes(slide, """
Walk left to right once. The line that matters is the first one in the edge
column: frames never leave the host. That is a design constraint, not a policy
note, and it is why inference is at the edge at all.

The two fallbacks are requirements. Say "required behaviour", not "we also
plan to handle failures".
""")


def slide_corpus(deck: Deck) -> None:
    slide = deck.content(10, "Methodology", ["The corpus has to ", "be built"],
                         lead="No public dataset gives fixed-camera junction "
                              "footage with per-lane congestion labels, so the "
                              "pipeline is part of the work.", total=TOTAL)

    stages = [("Source and triage", "curated public footage + campus capture"),
              ("Lane geometry", "placed by hand, then reviewed — never derived"),
              ("Detection", "fine-tuned YOLOv8s, per-frame per-lane counts"),
              ("Counts file", "threshold-free, so relabelling costs seconds"),
              ("Labelling", "PCU-weighted occupancy, per-camera p33/p67"),
              ("Audit", "fails loudly; nothing proceeds past it"),
              ("Split", "leave-one-camera-out, cut by clip — never by window")]
    height = panel_height(stages, HALF)
    deck.panel(slide, MARGIN, BODY_Y, HALF, height, "Pipeline, in order", stages)

    deck.bullets(slide, RIGHT_X, BODY_Y, Inches(5.5), [
        ("Labels are PCU-weighted, not counts",
         "Ten two-wheelers and ten buses are not the same congestion. The "
         "capacity manual publishes the equivalences; an unmapped class raises "
         "rather than defaulting to 1.0."),
        ("Lane centres are placed by hand",
         "Automatically derived centres move by 0.164 of frame width when the "
         "detector changes — silently altering every count the corpus rests on."),
        ("The split is cut by source clip",
         "Overlapping temporal windows from one clip on both sides of a split "
         "would leak the answer across it."),
        ("Two detector tracks run in parallel",
         "A public dataset bootstraps week 2 so nothing waits on annotation; "
         "every experiment records which weights produced it."),
    ], gap=Inches(1.10))

    deck.notes(slide, """
The point of this slide is that the dataset is a deliverable, not a
prerequisite we assume away.

If time is short, keep two things: labels are PCU-weighted because counting
vehicles measures the wrong quantity, and the split is cut by clip because
windows overlap.
""")


def slide_model(deck: Deck) -> None:
    slide = deck.content(11, "Methodology", ["The model, and ", "the gate"],
                         lead="Two frozen branches, fused by a learned gate, "
                              "over a 60-step window at 5 s intervals.",
                         total=TOTAL)

    stack = [("Frozen backbones", "ResNet-50  +  DINOv2 ViT-S/14, cached once"),
             ("Two cross-attention passes", "Z_A = CNN queries ViT ; Z_B = ViT queries CNN"),
             ("Gated fusion", "g = sigma(W[Z_A ; Z_B]) ; F = g Z_A + (1-g) Z_B"),
             ("BiLSTM", "2 layers, hidden 128, bidirectional"),
             ("Temporal self-attention", "2 layers, 4 heads, over the BiLSTM outputs"),
             ("Attention pooling", "over time, then per-lane ROI pooling"),
             ("Per-lane head", "LOW / MEDIUM / HIGH for N, S, E, W at t + 60 s")]
    height = panel_height(stack, HALF)
    deck.panel(slide, MARGIN, BODY_Y, HALF, height, "Proposed structure", stack)

    deck.bullets(slide, RIGHT_X, BODY_Y, Inches(5.5), [
        ("The gate is an output, not a detail",
         "It is returned from the forward pass, logged, shown on the dashboard "
         "and analysed. A gate that is computed and discarded makes the fusion "
         "claim untestable."),
        ("Frozen is forced, then exploited",
         "6 GB cannot hold an uncached step. Frozen features are deterministic, "
         "so they are computed once and cached — and the ablation drops from "
         "days to hours."),
        ("Every block is disableable by flag",
         "Eight configurations A-H run from configuration alone, with no code "
         "edit between them. Config H is a linear probe — the floor."),
        ("Per-lane read-out, not global pooling",
         "Pooling globally and applying one head four times cannot produce "
         "four different predictions."),
    ], gap=Inches(1.10))

    deck.notes(slide, """
Do not walk the whole stack. Point at the gate row and explain it: g is a
learned scalar that says how much of each branch was used, and we report it.

Then the honest framing of "frozen": it started as a hardware constraint and
turned into the thing that makes the ablation affordable. Both are true and the
order matters.

Config H is the floor. If the full model cannot beat a linear probe on frozen
features, the architecture has not justified itself, and we report that.
""")


def slide_control(deck: Deck) -> None:
    slide = deck.content(12, "Methodology", ["The controller, and ",
                                             "the baseline it must beat"],
                         lead="PPO on a SUMO four-way intersection, with the "
                              "forecast inside the observation vector.",
                         total=TOTAL)

    left = [("Observation is 16-dim and a contract",
             "Queues, phase, elapsed green, time of day, emergency flag, and "
             "four forecast entries. If the forecast is missing those four are "
             "zeroed — the vector is never shortened."),
            ("Twelve discrete actions",
             "Two phase groups by six green durations. Reward is the negative "
             "mean waiting time across lanes at each decision step."),
            ("The simulator models the real stream",
             "The sublane model is enabled so vehicles occupy lateral positions "
             "within a lane; the residual gap is declared, not papered over.")]
    right = [("Webster is swept, not configured once",
              "The published saturation-flow range for Indian conditions spans "
              "more than a factor of two. A single arbitrary value produces "
              "whichever result the author preferred."),
             ("The best Webster is the baseline",
              "PPO must beat the strongest configuration the sweep finds, over "
              "30 paired seeds across three demand regimes."),
             ("The forecast has to earn its place",
              "A perfect-forecast ceiling run comes first, because it can "
              "falsify the whole idea cheaply.")]
    deck.bullets(slide, MARGIN, BODY_Y, HALF, left, gap=Inches(1.34))
    deck.bullets(slide, RIGHT_X, BODY_Y, Inches(5.5), right, gap=Inches(1.34))

    deck.notes(slide, """
The line to land: we are tuning the baseline before we try to beat it. That is
the single most common weakness in RL-for-signals papers, and saying it out
loud is worth more than any architecture detail on this slide.

If asked about the 16-dim vector: it is a contract because a permuted index
keeps the shape and changes the meaning, so the layout is hashed into every
checkpoint sidecar.
""")


def slide_evaluation(deck: Deck) -> None:
    slide = deck.content(13, "Methodology", ["How it will ", "be evaluated"],
                         lead="The protocol is fixed now, before any number "
                              "exists, so that it cannot be chosen afterwards "
                              "to suit the result.", total=TOTAL)

    items = [("Leave-one-camera-out", "each fold holds out one camera entirely"),
             ("Five seeds per config", "a one-seed table ranks initialisations"),
             ("Bootstrap 95% CI", "percentile method, 10,000 resamples"),
             ("Paired t-test, alpha 0.05", "with Cohen's d beside it"),
             ("Seed spread reported", "two configs inside it are not separated"),
             ("Count-only baselines", "LSTM and XGBoost on the same folds")]
    footnote = ("Raw per-run results are committed, and every table in "
                "the final report is generated from them by a committed "
                "script — never transcribed.")
    height = panel_height(items, HALF, footnote)
    deck.panel(slide, MARGIN, BODY_Y, HALF, height, "Protocol, fixed in advance",
               items, footnote=footnote)

    deck.bullets(slide, RIGHT_X, BODY_Y, Inches(5.5), [
        ("Why hold out whole cameras",
         "A random split over windows lets the model recognise a camera it has "
         "already seen, and reports that as generalisation."),
        ("Why five seeds",
         "On a corpus this size the movement between seeds can exceed the gap "
         "between two architectures. One seed would rank noise."),
        ("Why count-only baselines are in from week one",
         "They answer RQ1 directly. If appearance does not beat counts, that "
         "is the finding, and it will be reported as the finding."),
    ], gap=Inches(1.44))

    deck.notes(slide, """
Say "fixed in advance" and mean it. The value of pre-registering the protocol
is that we cannot pick the evaluation that flatters the result later.

The right column is three answers to "why so careful". Give the first and the
third; skip the middle one unless asked.
""")


def slide_plan(deck: Deck) -> None:
    slide = deck.content(14, "Plan", ["Three phases, ", "with gates between them"],
                         lead="Nothing from Phase II is written until the "
                              "Phase I model trains cleanly. This is a "
                              "constraint, not a preference.", total=TOTAL)

    widths = [Inches(1.5), Inches(1.1), Inches(5.2), CONTENT_W - Inches(7.8)]
    # Three lines rather than two in the prose columns: the Phase II row is the
    # longest in the deck, and a 0.62 in row holds three 10 pt lines.
    rows = [[cell(phase, widths[0], bold=True), cell(weeks, widths[1]),
             cell(contents, widths[2], lines=3),
             cell(exit_, widths[3], lines=3, colour=MUTED)]
            for phase, weeks, contents, exit_ in P.PHASE_PLAN]
    deck.table(slide, MARGIN, BODY_Y, CONTENT_W,
               ["Phase", "Weeks", "Contents", "Exit condition"], rows,
               widths=widths, size=10, row_h=Inches(0.62))

    y = Inches(4.74)
    deck.text(slide, MARGIN, y, CONTENT_W, Inches(0.24), size=10, font=MONO,
              colour=ACCENT, bold=True)[3].text = "MILESTONES"
    y += Inches(0.32)
    for index, (when, what) in enumerate(P.MILESTONES):
        column = index % 2
        row = index // 2
        x = MARGIN + column * Inches(6.06)
        _, _, para, run = deck.text(slide, x, y + row * Inches(0.52),
                                    Inches(5.8), Inches(0.44), size=10.5,
                                    colour=MUTED, spacing=1.15)
        run.text = f"{when}   "
        deck.rich(para, [(what, {"colour": INK, "size": 10.5})],
                  size=10.5, font=None)

    deck.notes(slide, """
The gate between Phase I and Phase II is the point of this slide. Read the exit
condition for Phase I out loud.

The known failure mode in projects like this is an elaborate architecture with
no experiments attached to it. The gate exists specifically to prevent that, and
saying so is more convincing than the schedule itself.
""")


def slide_risks(deck: Deck) -> None:
    slide = deck.content(15, "Plan", ["What could go wrong, ", "and the response"],
                         lead="Eight risks, each with a response rather than a "
                              "hope. Two of them are outcomes we intend to "
                              "measure, not avoid.", total=TOTAL)

    widths = [Inches(2.9), Inches(1.2), Inches(1.0), CONTENT_W - Inches(5.1)]
    rows = [[cell(risk, widths[0], 9.5, bold=True),
             cell(likelihood, widths[1], 9.5),
             cell(impact, widths[2], 9.5,
                  colour=BAD if impact == "High" else MUTED),
             cell(response, widths[3], 9.5)]
            for risk, likelihood, impact, response in P.RISKS]
    deck.table(slide, MARGIN, BODY_Y, CONTENT_W,
               ["Risk", "Likelihood", "Impact", "Response"], rows,
               widths=widths, size=9.5, row_h=Inches(0.46))

    deck.notes(slide, """
Do not read the table. Pick the two rows that are not really risks in the usual
sense: appearance features may not beat counts, and the forecast may not help
the controller.

Those are measurements we plan to take. That is why the two claims are kept
separate -- a null result on the vision question does not invalidate the
control result or the prototype.
""")


def slide_outcomes(deck: Deck) -> None:
    slide = deck.content(16, "Expected Outcomes",
                         ["Seven deliverables, ", "with targets set in advance"],
                         lead="A target that is missed will be reported as "
                              "missed, with the measured value — not restated "
                              "afterwards to match what was obtained.",
                         total=TOTAL)

    widths = [Inches(2.8), Inches(4.4), CONTENT_W - Inches(7.2)]
    rows = [[cell(aspect, widths[0], bold=True),
             cell(target, widths[1], colour=ACCENT),
             cell(how, widths[2], colour=MUTED)]
            for aspect, target, how in P.TARGETS]
    deck.table(slide, MARGIN, BODY_Y, CONTENT_W,
               ["Aspect", "Target", "How it is measured"], rows,
               widths=widths, size=10, row_h=Inches(0.44))

    y = Inches(5.98)
    deck.text(slide, MARGIN, y, CONTENT_W, Inches(0.24), size=10, font=MONO,
              colour=ACCENT, bold=True)[3].text = "DELIVERABLES"
    y += Inches(0.30)
    names = " · ".join(name for name, _detail in P.DELIVERABLES)
    deck.text(slide, MARGIN, y, CONTENT_W, Inches(0.6), size=11.5,
              colour=INK, spacing=1.2)[3].text = names

    deck.notes(slide, """
The framing sentence in the lead is the one to say aloud. Targets are set now,
before any measurement, and a missed target gets reported with its number.

If asked which target is least certain: the vision macro-F1. It depends on how
well frozen self-supervised features describe dense unstructured traffic, and
that is genuinely an open question rather than a safe assumption.
""")


def slide_conclusion(deck: Deck) -> None:
    slide = deck.content(17, "Conclusion", ["What this proposal ", "commits to"],
                         lead="Three commitments distinguish this from a "
                              "description of an architecture.", total=TOTAL)

    deck.bullets(slide, MARGIN, BODY_Y, HALF, [
        ("Order",
         "Phase I is a mandatory core that must converge before any refinement "
         "is written. The gate is a guard against an elaborate model with no "
         "experiments attached to it."),
        ("Falsifiability",
         "A count-only baseline and a linear probe are in the experiment from "
         "the start; the evaluation holds out whole cameras; every config runs "
         "at five seeds; the classical baseline is tuned before it is beaten."),
    ], gap=Inches(1.70))

    deck.bullets(slide, RIGHT_X, BODY_Y, Inches(5.5), [
        ("Reporting the gate",
         "The fusion gate is an artefact we publish, not an internal detail. "
         "It is what makes the fusion claim checkable at all."),
        ("And what is deliberately excluded",
         "Multi-junction coordination, trajectory prediction, deployment on "
         "live signal hardware, night and adverse weather, and any claim that "
         "requires data we do not have."),
    ], gap=Inches(1.70))

    deck.rect(slide, MARGIN, Inches(6.02), CONTENT_W, Inches(0.86),
              fill=PANEL, line=RULE)
    deck.text(slide, MARGIN + Inches(0.28), Inches(6.20),
              CONTENT_W - Inches(0.56), Inches(0.5), size=11.5, colour=MUTED,
              spacing=1.2)[3].text = (
        "Whether each component earns its place is a question the experiments "
        "are designed to answer honestly, in either direction. The two claims "
        "— the count-based forecaster with its controller, and the vision "
        "claim — are stated separately so that a null result on one does not "
        "take the other down with it.")

    deck.notes(slide, """
Close on the last band. It is the sentence that tells a panel this is a
research plan rather than a demo plan.

Then stop talking. The next slide is references and needs no narration.
""")


def slide_references(deck: Deck) -> None:
    slide = deck.content(18, "References", ["Sources, ", "IEEE style"],
                         lead=f"{len(P.REFERENCES)} entries, each cited at "
                              f"first use in the synopsis report.", total=TOTAL)
    half = (len(P.REFERENCES) + 1) // 2
    for column, entries in enumerate((P.REFERENCES[:half], P.REFERENCES[half:])):
        x = MARGIN + column * Inches(6.06)
        for index, entry in enumerate(entries):
            number = column * half + index + 1
            _, _, para, run = deck.text(slide, x, BODY_Y + index * Inches(0.52),
                                        Inches(5.8), Inches(0.46), size=9.5,
                                        colour=MUTED, spacing=1.15)
            run.text = f"[{number}]  "
            deck.rich(para, [(_shorten(entry, 132), {"colour": INK, "size": 9.5})],
                      size=9.5)

    deck.notes(slide, """
No narration. Leave it up while questions start.
""")


def slide_close(deck: Deck) -> None:
    slide = deck._blank(DEEP)
    deck.slides.append(slide)

    deck.text(slide, MARGIN, Inches(2.30), Inches(11), Inches(0.34),
              size=11, font=MONO, colour=AMBER,
              bold=True)[3].text = "PHASE I  ·  PROJECT PROPOSAL"
    deck.text(slide, MARGIN, Inches(2.70), Inches(11.2), Inches(1.1),
              size=32, colour=CREAM, bold=True, spacing=1.0)[3].text = (
        "Thank you.\nQuestions welcome.")
    deck.text(slide, MARGIN, Inches(4.10), Inches(9.6), Inches(0.8),
              size=13, colour=DIM_CREAM, spacing=1.3)[3].text = (
        f"{P.TITLE}\nProject Team ID {P.TEAM_ID}  ·  "
        f"guided by {P.MENTOR_NAME}, {P.MENTOR_DESIGNATION}")
    deck.text(slide, MARGIN, Inches(5.30), Inches(9.6), Inches(0.4),
              size=11, font=MONO, colour=AMBER)[3].text = (
        f"working name:  {P.WORKING_NAME}")

    deck.notes(slide, """
Expect three questions: why not fine-tune the backbones (6 GB), why not a
public dataset (none has per-lane congestion labels on fixed cameras), and what
happens if the vision branch does not beat counts (we report it, and the
control claim stands on its own).
""")


# ==========================================================================

def _shorten(text: str, limit: int) -> str:
    """Trim to `limit` characters on a word boundary, with an ellipsis."""
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(",;:.") + " …"


def cell(text: str, width, size: float = 10, *, bold: bool = False,
         colour=INK, lines: int = 2) -> tuple[str, dict]:
    """A table cell trimmed to what its own column can actually show.

    `Deck.table` draws every cell into a fixed 0.26 in box, so a long string
    wraps *downwards* out of that box. Two wrapped lines still sit inside the
    row height every table here uses, and a third does not — it crosses the
    rule below and lands on the next row. So the budget is two lines' worth of
    characters, derived from the column width rather than guessed, and anything
    past it is cut on a word boundary. Deriving it means changing a column
    width cannot silently start truncating.
    """
    usable = (width - CELL_INSET) / 914400
    limit = int(lines * usable / (BODY_PER_PT * size))
    return _shorten(text, limit), {"font": BODY, "bold": bold, "colour": colour}


def build(out_path: Path) -> Path:
    deck = Deck()
    slide_title(deck)
    slide_agenda(deck)
    slide_background(deck)
    slide_selection(deck)
    slide_literature(deck)
    slide_problem(deck)
    slide_objectives(deck)
    slide_decisions(deck)
    slide_architecture(deck)
    slide_corpus(deck)
    slide_model(deck)
    slide_control(deck)
    slide_evaluation(deck)
    slide_plan(deck)
    slide_risks(deck)
    slide_outcomes(deck)
    slide_conclusion(deck)
    slide_references(deck)
    slide_close(deck)

    if len(deck.slides) != TOTAL:
        raise AssertionError(
            f"TOTAL says {TOTAL} slides and the deck has {len(deck.slides)}; "
            "the per-slide counter would lie.")
    deck.save(out_path)
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path,
                        default=P.ROOT / "docs" / "demo"
                        / "MFSTNet-Synopsis-Phase1-Presentation.pptx")
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
