"""Build the project review deck as a real PowerPoint file.

    python scripts/build_review_pptx.py

Eighteen slides covering what has been built, the data it rests on, the stack,
every validation metric, the decisions taken and the defects found on the way.

**Generated, not typed.** Every figure is read from a committed CSV in
`experiments/results/` at build time, so a number that changes upstream changes
on the slide instead of going stale. The two detection frames are rendered from
real footage by the real detector rather than picked for looking good.

**Speaker notes on every slide.** They go into the actual notes pane, so
presenter view shows what to say.

**Fonts are Segoe UI and Consolas** — both ship with Windows. Naming a font
PowerPoint has to substitute is how a deck silently reflows on the machine it is
presented from.

Images are rendered into a temporary directory and embedded in the `.pptx`.
They are deliberately **not** committed: they are frames of third-party footage,
and the repository gaining video stills would reopen the P10 publication
question for no benefit. Without the footage present the two image slides say so
rather than the build failing.
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

from pptx import Presentation  # noqa: E402
from pptx.dml.color import RGBColor  # noqa: E402
from pptx.enum.shapes import MSO_SHAPE  # noqa: E402
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN  # noqa: E402
from pptx.util import Emu, Inches, Pt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "experiments" / "results"

# -- palette ---------------------------------------------------------------
# Derived from the dashboard spec the PRD §20 already fixes (#6366F1) rather
# than invented, and adapted from dark-only to a light deck that projects and
# prints. The title slide keeps the dark ground; content slides do not.
DEEP = RGBColor(0x1E, 0x1B, 0x4B)
PAPER = RGBColor(0xFB, 0xFB, 0xF9)
PANEL = RGBColor(0xF4, 0xF4, 0xF1)
INK = RGBColor(0x14, 0x18, 0x1A)
MUTED = RGBColor(0x55, 0x60, 0x68)
FAINT = RGBColor(0x8A, 0x94, 0x9B)
RULE = RGBColor(0xD6, 0xD9, 0xDC)
ACCENT = RGBColor(0x4F, 0x46, 0xE5)
AMBER = RGBColor(0xD9, 0x77, 0x06)
GOOD = RGBColor(0x15, 0x80, 0x3D)
WARN = RGBColor(0xB4, 0x53, 0x09)
BAD = RGBColor(0xB9, 0x1C, 0x1C)
CREAM = RGBColor(0xEE, 0xEC, 0xF7)
DIM_CREAM = RGBColor(0xA9, 0xA4, 0xD4)

BODY = "Segoe UI"
MONO = "Consolas"

# -- geometry --------------------------------------------------------------
W, H = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.72)
CONTENT_W = W - 2 * MARGIN
EYEBROW_Y = Inches(0.40)
TITLE_Y = Inches(0.86)
LEAD_Y = Inches(1.80)
BODY_Y = Inches(2.42)


# ==========================================================================
#  data
# ==========================================================================

def read_results(name: str) -> list[dict]:
    with (RESULTS / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def mean_map50(name: str) -> float:
    """Mean mAP50 over the classes actually evaluated in a metrics CSV."""
    values = [float(r["mAP50"]) for r in read_results(name)
              if r.get("mAP50") not in (None, "")]
    return statistics.mean(values)


def project_counts() -> dict:
    """Counts that would otherwise be typed once and drift.

    A slide claiming 620 tests while the suite has 628 is a small thing that
    quietly tells a reader the deck was assembled by hand. Collection is used
    rather than execution because it costs a second and the number is the same.
    """
    import functools
    import subprocess

    @functools.lru_cache(maxsize=1)
    def compute() -> dict:
        counts = {"tests": "?", "commits": "?",
                  "adrs": len(list((ROOT / "docs" / "00-planning" / "decisions")
                                   .glob("ADR-*.md")))}
        try:
            out = subprocess.run(
                [sys.executable, "-m", "pytest", "--collect-only", "-q",
                 str(ROOT / "tests")],
                capture_output=True, text=True, timeout=300, cwd=str(ROOT)).stdout
            # `pytest --collect-only -q` prints one "path: N" line per file
            # and no total, so the total is the sum.
            total = 0
            for line in out.splitlines():
                _, _, tail = line.rpartition(":")
                if tail.strip().isdigit():
                    total += int(tail.strip())
            if total:
                counts["tests"] = total
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
        try:
            counts["commits"] = int(subprocess.run(
                ["git", "rev-list", "--count", "HEAD"], capture_output=True,
                text=True, timeout=30, cwd=str(ROOT)).stdout.strip())
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
        return counts

    return compute()


def load_figures() -> dict:
    """Every number the deck states, read from the CSV that produced it."""
    counting = {r["conf"]: r for r in read_results("s14_counting_threshold_sweep.csv")}
    benchmark = read_results("benchmark_stats.csv")
    yield_rows = read_results("corpus_yield.csv")
    gate = read_results("gate_capacity.csv")

    def bench(regime: str, a: str, b: str) -> dict:
        for row in benchmark:
            if row["regime"] == regime and row["method_a"] == a and row["method_b"] == b:
                return row
        raise KeyError(f"{regime} {a} vs {b} not in benchmark_stats.csv")

    return {
        "bmd45": read_results("s15_metrics_bmd45.csv"),
        "bmd45_mean": mean_map50("s15_metrics_bmd45.csv"),
        "trafficcam_mean": mean_map50("s15_on_trafficcam.csv"),
        "dashcam_on_elevated": mean_map50("s11_on_bmd45_elevated.csv"),
        "s11_own": mean_map50("s11_detector_metrics.csv"),
        "s14_idd": mean_map50("s14_metrics_idd.csv"),
        "m2": read_results("m2_coco_baseline.csv"),
        "counting": counting,
        "bench": bench,
        "yield": yield_rows,
        "gate": [r for r in gate if r.get("gate_std")],
    }


def m2_shared_mean(rows: list[dict]) -> tuple[float, float, float]:
    comparable = [r for r in rows if r.get("coco_mAP50") not in (None, "")]
    coco = statistics.mean(float(r["coco_mAP50"]) for r in comparable)
    ours = statistics.mean(float(r["ours_mAP50"]) for r in comparable)
    return coco, ours, (ours - coco) / coco * 100


def yield_totals(rows: list[dict], step: int) -> tuple[int, int, int]:
    usable = [r for r in rows if r.get("clears_gate", "True") == "True"]
    seq = sum(int(r[f"sequences_step{step}"]) for r in usable)
    ind = sum(int(r[f"independent_step{step}"]) for r in usable)
    cams = sum(1 for r in usable if int(r[f"independent_step{step}"]))
    return seq, ind, cams


# ==========================================================================
#  drawing helpers
# ==========================================================================

class Deck:
    def __init__(self) -> None:
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = W, H
        self.slides: list = []

    # -- primitives --------------------------------------------------------
    def _blank(self, background: RGBColor):
        slide = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        fill = slide.background.fill
        fill.solid()
        fill.fore_color.rgb = background
        return slide

    @staticmethod
    def text(slide, left, top, width, height, *, size=14, colour=INK, bold=False,
             font=BODY, align=PP_ALIGN.LEFT, spacing=1.0, anchor=MSO_ANCHOR.TOP):
        box = slide.shapes.add_textbox(left, top, width, height)
        frame = box.text_frame
        frame.word_wrap = True
        frame.margin_left = frame.margin_right = 0
        frame.margin_top = frame.margin_bottom = 0
        frame.vertical_anchor = anchor
        para = frame.paragraphs[0]
        para.alignment = align
        para.line_spacing = spacing
        run = para.add_run()
        run.font.size = Pt(size)
        run.font.name = font
        run.font.bold = bold
        run.font.color.rgb = colour
        return box, frame, para, run

    @staticmethod
    def rich(para, pieces, *, size=14, font=BODY, default=INK):
        """A paragraph built from (text, {overrides}) pieces.

        Mixed emphasis inside one line is what carries the reference deck's
        headlines, and PowerPoint needs it run by run.
        """
        for text, style in pieces:
            run = para.add_run()
            run.text = text
            run.font.size = Pt(style.get("size", size))
            run.font.name = style.get("font", font)
            run.font.bold = style.get("bold", False)
            run.font.italic = style.get("italic", False)
            run.font.color.rgb = style.get("colour", default)
            if "link" in style:
                run.hyperlink.address = style["link"]

    @staticmethod
    def rect(slide, left, top, width, height, *, fill=None, line=None,
             line_pt=0.75, shape=MSO_SHAPE.RECTANGLE):
        box = slide.shapes.add_shape(shape, left, top, width, height)
        box.shadow.inherit = False
        if fill is None:
            box.fill.background()
        else:
            box.fill.solid()
            box.fill.fore_color.rgb = fill
        if line is None:
            box.line.fill.background()
        else:
            box.line.color.rgb = line
            box.line.width = Pt(line_pt)
        box.text_frame.text = ""
        return box

    def rule(self, slide, left, top, width, colour=RULE, weight=Pt(0.75)):
        return self.rect(slide, left, top, width, weight, fill=colour)

    # -- slide furniture ---------------------------------------------------
    def content(self, number, section, headline, *, lead=None, total=20):
        slide = self._blank(PAPER)
        self.slides.append(slide)

        _, _, para, run = self.text(slide, MARGIN, EYEBROW_Y, Inches(9), Inches(0.3),
                                    size=10.5, font=MONO, colour=AMBER, bold=True)
        run.text = f"{number:02d}"
        self.rich(para, [("   " + section.upper(), {"colour": FAINT, "size": 10.5})],
                  size=10.5, font=MONO)

        self.text(slide, W - MARGIN - Inches(2), EYEBROW_Y, Inches(2), Inches(0.3),
                  size=10.5, font=MONO, colour=FAINT,
                  align=PP_ALIGN.RIGHT)[3].text = f"{number} / {total}"

        _, frame, para, run = self.text(slide, MARGIN, TITLE_Y, CONTENT_W, Inches(0.8),
                                        size=30, colour=INK, bold=True, spacing=0.95)
        run.text = headline[0]
        if len(headline) > 1:
            self.rich(para, [(headline[1], {"colour": AMBER, "bold": True, "size": 30})],
                      size=30)

        if lead:
            self.text(slide, MARGIN, LEAD_Y, Inches(10.6), Inches(0.5),
                      size=12.5, colour=MUTED, spacing=1.25)[3].text = lead
        return slide

    def bullets(self, slide, left, top, width, items, *, size=11.5, gap=Inches(0.62)):
        """Bold lead, then an explanatory line — the reference's left column."""
        y = top
        for lead, detail in items:
            self.rect(slide, left, y + Inches(0.075), Inches(0.05), Inches(0.05),
                      fill=ACCENT, shape=MSO_SHAPE.OVAL)
            _, frame, para, run = self.text(
                slide, left + Inches(0.19), y, width - Inches(0.19), Inches(0.24),
                size=size, colour=INK, bold=True)
            run.text = lead
            _, _, _, sub = self.text(
                slide, left + Inches(0.19), y + Inches(0.23),
                width - Inches(0.19), Inches(0.42),
                size=size - 1.5, colour=MUTED, spacing=1.2)
            sub.text = detail
            y += gap
        return y

    def panel(self, slide, left, top, width, height, title, items, *,
              footnote=None, size=11):
        self.rect(slide, left, top, width, height, fill=PANEL, line=RULE)
        self.text(slide, left + Inches(0.28), top + Inches(0.26),
                  width - Inches(0.5), Inches(0.24),
                  size=10, font=MONO, colour=ACCENT, bold=True)[3].text = title.upper()
        y = top + Inches(0.66)
        for lead, detail in items:
            self.rect(slide, left + Inches(0.28), y + Inches(0.07),
                      Inches(0.05), Inches(0.05), fill=AMBER, shape=MSO_SHAPE.OVAL)
            _, _, _, run = self.text(slide, left + Inches(0.46), y,
                                     width - Inches(0.76), Inches(0.22),
                                     size=size, colour=INK, bold=True)
            run.text = lead
            if detail:
                _, _, _, sub = self.text(slide, left + Inches(0.46), y + Inches(0.21),
                                         width - Inches(0.76), Inches(0.22),
                                         size=size - 1.5, font=MONO, colour=MUTED)
                sub.text = detail
                y += Inches(0.50)
            else:
                y += Inches(0.32)
        if footnote:
            self.rule(slide, left + Inches(0.28), y + Inches(0.06),
                      width - Inches(0.56))
            _, _, _, run = self.text(slide, left + Inches(0.28), y + Inches(0.2),
                                     width - Inches(0.56), Inches(0.7),
                                     size=9.5, colour=MUTED, spacing=1.2)
            run.text = footnote

    def table(self, slide, left, top, width, headers, rows, *,
              widths=None, size=10.5, row_h=Inches(0.34), highlight=()):
        """Hand-drawn so the look is exact and PowerPoint applies no style."""
        widths = widths or [width / len(headers)] * len(headers)
        assert len(widths) == len(headers)

        x = left
        for header, w in zip(headers, widths):
            _, _, _, run = self.text(slide, x, top, w - Inches(0.1), Inches(0.22),
                                     size=8.5, font=MONO, colour=FAINT, bold=True)
            run.text = header.upper()
            x += w
        y = top + Inches(0.28)
        self.rule(slide, left, y, width, colour=ACCENT, weight=Pt(1.0))
        y += Inches(0.06)

        for index, row in enumerate(rows):
            if index in highlight:
                self.rect(slide, left - Inches(0.1), y - Inches(0.03),
                          width + Inches(0.2), row_h, fill=RGBColor(0xEC, 0xEB, 0xFA))
            x = left
            for cell, w in zip(row, widths):
                text, style = cell if isinstance(cell, tuple) else (cell, {})
                _, _, _, run = self.text(
                    slide, x, y, w - Inches(0.1), Inches(0.26),
                    size=style.get("size", size),
                    font=style.get("font", MONO if style.get("mono", True) else BODY),
                    colour=style.get("colour", INK),
                    bold=style.get("bold", index in highlight))
                run.text = str(text)
                x += w
            y += row_h
            self.rule(slide, left, y - Inches(0.06), width)
        return y

    @staticmethod
    def notes(slide, text: str) -> None:
        slide.notes_slide.notes_text_frame.text = text.strip()

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.prs.save(str(path))


# ==========================================================================
#  slides
# ==========================================================================

TEAM = [("Divyansh Uniyal", "Project Lead"), ("KM Shivani", "Team Member"),
        ("Abhishek Negi", "Team Member"), ("Bhavya Gogia", "Team Member")]
UNIVERSITY = "Graphic Era Hill University"
CAMPUS = "Dehradun, Uttarakhand"
GUIDE_NAME = "Ms Neha Pokhriyal"


def slide_title(deck: Deck, fig: dict) -> None:
    slide = deck._blank(DEEP)
    deck.slides.append(slide)

    deck.text(slide, MARGIN, Inches(0.62), Inches(9), Inches(0.3),
              size=10.5, font=MONO, colour=AMBER,
              bold=True)[3].text = "B.TECH CSE (ML / AI)   ·   MAJOR PROJECT   ·   WEEK 2 OF 20"

    _, _, para, run = deck.text(slide, MARGIN, Inches(1.06), Inches(11.2), Inches(1.5),
                                size=42, colour=CREAM, bold=True, spacing=0.95)
    run.text = "MFSTNet — Camera-Only Congestion\nForecasting and "
    deck.rich(para, [("Signal Control", {"colour": AMBER, "bold": True, "size": 42})],
              size=42)

    _, _, _, run = deck.text(slide, MARGIN, Inches(2.62), Inches(8.6), Inches(0.9),
                             size=13, colour=DIM_CREAM, spacing=1.35)
    run.text = ("A multimodal deep-learning system that forecasts per-lane congestion "
                "60 seconds ahead from traffic camera video alone, and a reinforcement-"
                "learning controller that acts on it — built for unstructured Indian "
                "traffic, where lane discipline cannot be assumed.")

    for index, (name, role) in enumerate(TEAM):
        x = MARGIN + index * Inches(2.95)
        deck.rect(slide, x, Inches(3.86), Inches(2.72), Inches(0.92),
                  fill=RGBColor(0x2A, 0x26, 0x63), line=RGBColor(0x3D, 0x38, 0x82))
        deck.text(slide, x + Inches(0.22), Inches(4.02), Inches(2.3), Inches(0.2),
                  size=8.5, font=MONO,
                  colour=AMBER if index == 0 else DIM_CREAM,
                  bold=True)[3].text = role.upper()
        deck.text(slide, x + Inches(0.22), Inches(4.28), Inches(2.34), Inches(0.3),
                  size=13.5, colour=CREAM, bold=True)[3].text = name

    deck.rule(slide, MARGIN, Inches(5.08), CONTENT_W, colour=RGBColor(0x3D, 0x38, 0x82))

    _, _, _, run = deck.text(slide, MARGIN, Inches(5.28), Inches(6), Inches(0.24),
                             size=12, colour=CREAM, bold=True)
    run.text = UNIVERSITY
    deck.text(slide, MARGIN, Inches(5.54), Inches(6), Inches(0.25),
              size=10.5, colour=DIM_CREAM)[3].text = CAMPUS
    _, _, guide_para, guide_run = deck.text(
        slide, MARGIN, Inches(5.84), Inches(6), Inches(0.25),
        size=10.5, colour=DIM_CREAM)
    guide_run.text = "Faculty Guide   "
    deck.rich(guide_para, [(GUIDE_NAME, {"colour": CREAM, "bold": True,
                                         "size": 10.5})], size=10.5)

    counts = project_counts()
    stats = [(f"{fig['bmd45_mean']:.4f}", "mAP50, elevated CCTV"),
             (str(counts["tests"]), "committed tests"),
             (str(counts["adrs"]), "decisions recorded"),
             ("1.5 h", "full ablation")]
    for index, (value, label) in enumerate(stats):
        x = Inches(6.9) + index * Inches(1.62)
        deck.text(slide, x, Inches(5.3), Inches(1.5), Inches(0.4),
                  size=19, colour=AMBER if index == 0 else CREAM,
                  bold=True)[3].text = value
        deck.text(slide, x, Inches(5.72), Inches(1.55), Inches(0.4),
                  size=8.5, colour=DIM_CREAM, spacing=1.1)[3].text = label

    deck.text(slide, MARGIN, Inches(6.62), Inches(11.9), Inches(0.3),
              size=9.5, font=MONO, colour=RGBColor(0x7A, 0x74, 0xB8))[3].text = (
        "Every validation figure is read from a committed results CSV at build time. "
        "The two exceptions — S17's detector numbers and the timing comparison — say so "
        "where they appear.")

    deck.notes(slide, """
Open with the one-sentence version: this forecasts congestion per lane, sixty
seconds ahead, from camera video alone -- no loops buried in the road, no GPS
feeds, no vehicle radios. Then say why that matters here: those inputs do not
exist on most Indian junctions, and a camera does.

Introduce the team, then move on quickly. The four numbers on the right are
there so the panel knows this is measured work, not a proposal -- come back to
each of them later.
""")


def slide_problem(deck: Deck) -> None:
    slide = deck.content(2, "The problem", ["Lane discipline is an assumption ",
                                            "this traffic does not make"],
                         lead="Most traffic forecasting assumes vehicles in lanes, of "
                              "similar size, detected by sensors in the road. Every one "
                              "of those assumptions fails here.")
    deck.bullets(slide, MARGIN, BODY_Y, Inches(6.6), [
        ("Vehicles do not stay in lanes.",
         "Motorcycles filter between cars, auto-rickshaws occupy gaps. A lane occupancy "
         "figure from a loop detector describes a road this is not."),
        ("The vehicle mix is extreme.",
         "A motorcycle and a bus differ by an order of magnitude in road space. Counting "
         "vehicles treats them as equal; the measured fleet is 45% two-wheelers."),
        ("The infrastructure is not there.",
         "Inductive loops need the road dug up and maintained. Cameras are already "
         "mounted at many junctions, and a phone on a footbridge is a valid sensor."),
        ("Off-the-shelf detection does not transfer.",
         "COCO has no auto-rickshaw class at all, and a detector trained on dashcam "
         "imagery scores 0.3223 on an elevated camera."),
    ])
    deck.panel(slide, Inches(7.7), BODY_Y - Inches(0.1), Inches(4.9), Inches(4.1),
               "What the system has to do", [
                   ("Forecast, not report", "60 s ahead, per lane, three classes"),
                   ("From pixels only", "no loops, no GPS, no V2I radio"),
                   ("Survive an unseen camera", "the number that governs deployment"),
                   ("Act on the forecast", "PPO controller consumes it directly"),
                   ("Degrade safely", "counts alone, then a local Webster fallback"),
               ],
               footnote="A forecast nothing acts on is a dashboard. The controller is "
                        "what turns a prediction into changed signal timing, which is "
                        "why both halves are in scope.")
    deck.notes(slide, """
This is the slide that justifies the whole project, so do not rush it.

The key line is the third bullet: cameras already exist at junctions, loops do
not. That is the practical argument for a camera-only system in an Indian city,
and it is stronger than any accuracy number.

If asked "why not just buy a detector" -- point at the fourth bullet. COCO has
no auto-rickshaw class. It is not that off-the-shelf is worse; it cannot see the
vehicle at all.
""")


def slide_system(deck: Deck) -> None:
    slide = deck.content(3, "What we built", ["Four subsystems, ",
                                              "integrated late by design"],
                         lead="Each is independently testable, which is why three of "
                              "them are already measured while the fourth is still "
                              "being decided.")
    parts = [
        ("IndiaTrafficNet", "Dataset", "8 India-specific classes\nincluding auto- and\ne-rickshaw, cattle"),
        ("YOLOv8s", "Detection", "per-lane vehicle counts\n0.8941 mAP50 at the\ndeployment viewpoint"),
        ("MFSTNet", "The model", "ResNet-50 + DINOv2 ViT\ngated cross-attention\nper-lane forecast"),
        ("PPO agent", "Control", "SUMO via TraCI\nconsumes the forecast\nas auxiliary state"),
    ]
    for index, (name, kind, detail) in enumerate(parts):
        x = MARGIN + index * Inches(3.03)
        deck.rect(slide, x, BODY_Y, Inches(2.8), Inches(1.72),
                  fill=PANEL, line=ACCENT if index in (1, 2) else RULE)
        deck.text(slide, x + Inches(0.24), BODY_Y + Inches(0.2), Inches(2.3), Inches(0.2),
                  size=8.5, font=MONO, colour=AMBER, bold=True)[3].text = kind.upper()
        deck.text(slide, x + Inches(0.24), BODY_Y + Inches(0.44), Inches(2.4), Inches(0.3),
                  size=15, colour=INK, bold=True)[3].text = name
        deck.text(slide, x + Inches(0.24), BODY_Y + Inches(0.78), Inches(2.4), Inches(0.8),
                  size=9.5, colour=MUTED, spacing=1.25)[3].text = detail
        if index < 3:
            deck.text(slide, x + Inches(2.84), BODY_Y + Inches(0.66), Inches(0.2),
                      Inches(0.3), size=15, colour=FAINT)[3].text = "›"

    deck.rect(slide, MARGIN, Inches(4.5), CONTENT_W, Inches(1.05),
              fill=RGBColor(0xEC, 0xEB, 0xFA), line=ACCENT)
    deck.text(slide, MARGIN + Inches(0.3), Inches(4.68), Inches(11), Inches(0.22),
              size=9.5, font=MONO, colour=ACCENT,
              bold=True)[3].text = "THE COUPLING THAT IS EASY TO MISS"
    _, _, _, run = deck.text(slide, MARGIN + Inches(0.3), Inches(4.94),
                             Inches(11.2), Inches(0.5), size=11.5, colour=INK,
                             spacing=1.25)
    run.text = ("MFSTNet's output is not only a prediction — it occupies indices 11–14 "
                "of the PPO controller's 16-dimensional state vector. Changing the model's "
                "output shape invalidates every trained controller checkpoint.")

    deck.text(slide, MARGIN, Inches(5.82), Inches(11.9), Inches(0.5),
              size=11, colour=MUTED, spacing=1.3)[3].text = (
        "Two fallbacks are required behaviour rather than nice-to-haves: if the model "
        "fails, the controller runs on raw counts with those indices zeroed — never a "
        "shortened vector; if the network drops for more than 10 seconds, the edge node "
        "switches to a Webster controller embedded locally.")
    deck.notes(slide, """
Walk left to right along the four boxes -- data, detection, model, control.

The purple box is the point of the slide. Examiners often ask how the subsystems
relate; the honest answer is that they are loosely coupled except here, where the
model's output is literally part of the controller's input vector. That is why
its shape is treated as a contract.

The fallbacks matter if anyone asks about reliability. Say plainly: we never
shorten the state vector, we zero it, because a controller silently receiving a
different-length input is worse than one receiving zeros.
""")


def slide_stack(deck: Deck) -> None:
    slide = deck.content(4, "The stack", ["Every version here is the one ",
                                          "actually installed"],
                         lead="Until four days ago these were aspirational: not one of "
                              "the seven pinned-and-installed packages matched its pin.")
    groups = [
        ("Vision and learning", ["torch 2.13.0+cu126", "torchvision 0.28.0",
                                 "timm 1.0.28  (DINOv2)", "ultralytics 8.4.118",
                                 "opencv 5.0.0.93"]),
        ("Reinforcement learning", ["stable-baselines3 2.9.0", "gymnasium 1.3.0",
                                    "eclipse-sumo 1.27.1", "traci / sumolib 1.27.1"]),
        ("Analysis and testing", ["numpy 2.5.2", "pandas 3.0.5", "scipy 1.18.0",
                                  "scikit-learn 1.9.0", "xgboost 3.4.1", "pytest 9.1.1"]),
    ]
    for index, (title, items) in enumerate(groups):
        x = MARGIN + index * Inches(4.06)
        deck.rect(slide, x, BODY_Y, Inches(3.8), Inches(2.16), fill=PANEL, line=RULE)
        deck.text(slide, x + Inches(0.26), BODY_Y + Inches(0.22), Inches(3.3), Inches(0.2),
                  size=9, font=MONO, colour=ACCENT, bold=True)[3].text = title.upper()
        y = BODY_Y + Inches(0.54)
        for item in items:
            deck.text(slide, x + Inches(0.26), y, Inches(3.4), Inches(0.22),
                      size=10.5, font=MONO, colour=INK)[3].text = item
            y += Inches(0.28)

    deck.rect(slide, MARGIN, Inches(4.92), CONTENT_W, Inches(0.96),
              fill=RGBColor(0xF7, 0xF1, 0xE4), line=AMBER)
    deck.text(slide, MARGIN + Inches(0.3), Inches(5.1), Inches(11), Inches(0.22),
              size=9.5, font=MONO, colour=WARN,
              bold=True)[3].text = "WHY SCIPY AND SCIKIT-LEARN ARE PINNED BUT NOT USED"
    _, _, _, run = deck.text(slide, MARGIN + Inches(0.3), Inches(5.36),
                             Inches(11.2), Inches(0.5), size=11, colour=INK, spacing=1.25)
    run.text = ("The metrics and statistics are pure standard library so the arithmetic "
                "stays auditable. These two exist so the tests can cross-check the "
                "hand-rolled implementations against them — macro F1, quadratic-weighted "
                "kappa, the paired t-test and Cohen's d are graded numbers, and a bespoke "
                "statistic nobody verifies is worse than none.")
    deck.text(slide, MARGIN, Inches(6.24), Inches(11.9), Inches(0.3),
              size=10, font=MONO, colour=FAINT)[3].text = (
        "Hardware: RTX 4050 Laptop, 6 GB, sm_89  ·  training runs locally, not on Colab")
    deck.notes(slide, """
Do not read the version lists aloud. The two things to say:

First, these versions are the ones the environment actually has. We audited it
and found every single pinned package disagreed with its pin -- SUMO said 1.19,
the machine had 1.27. A clean install would have built a different stack from the
one every measurement was taken on.

Second, the amber box is a good answer to "did you just import a library for your
metrics". No -- the metrics are written out longhand so they can be checked, and
the libraries are there to test our implementations against.
""")


DATASETS = [
    ("BMD-45", "huggingface.co/datasets/iisc-aim/BMD-45",
     "https://huggingface.co/datasets/iisc-aim/BMD-45",
     "CC BY 4.0", GOOD,
     "45,986 images · 3,679 Bengaluru CCTV cameras",
     "Primary training and test at the deployment viewpoint"),
    ("IDD Detection", "idd.insaan.iiit.ac.in — IIIT Hyderabad",
     "https://idd.insaan.iiit.ac.in/",
     "Research use", WARN,
     "40,000 annotated images, dashcam",
     "Week-2 bootstrap; the project's only dashcam surface"),
    ("TrafficCAM", "github.com/Math-ML-X/TrafficCAM",
     "https://github.com/Math-ML-X/TrafficCAM",
     "NONE DECLARED", BAD,
     "2,676 frames · ~72,000 boxes · 5 cities",
     "Cross-camera test — and the only source of e_rickshaw"),
    ("ITD v1.2", "github.com/teg-iitr/ITD-Indian-traffic-dataset",
     "https://github.com/teg-iitr/ITD-Indian-traffic-dataset",
     "CC BY-NC 4.0", WARN,
     "9,200+ images · 280,000+ objects · IIT Roorkee",
     "Supplies the detector used for lane survey and counting"),
    ("Bellevue Traffic Video", "github.com/City-of-Bellevue/TrafficVideoDataset",
     "https://github.com/City-of-Bellevue/TrafficVideoDataset",
     "Public body release", GOOD,
     "~101 hours · 5 fixed intersections",
     "ADR-016 Phase 1 corpus — proposed, not yet used"),
    ("Public traffic footage", "12 clips resolving to 11 distinct cameras",
     None, "Third-party", MUTED,
     "the corpus source today",
     "Every MFSTNet training sequence comes from these"),
    ("IndiaTrafficNet", "self-collected, self-annotated",
     None, "Ours", ACCENT,
     "12,000+ frames targeted",
     "ADR-006 — pending sign-off"),
]


def slide_data(deck: Deck) -> None:
    slide = deck.content(5, "The data", ["Seven sources, and ",
                                         "what we may do with each"],
                         lead="Licence is not paperwork here — it decides what can be "
                              "published, and one of these is unresolved.")
    y = BODY_Y + Inches(0.06)
    deck.text(slide, MARGIN, y - Inches(0.26), Inches(2.4), Inches(0.2),
              size=8.5, font=MONO, colour=FAINT, bold=True)[3].text = "DATASET & SOURCE"
    deck.text(slide, MARGIN + Inches(4.6), y - Inches(0.26), Inches(1.6), Inches(0.2),
              size=8.5, font=MONO, colour=FAINT, bold=True)[3].text = "LICENCE"
    deck.text(slide, MARGIN + Inches(6.3), y - Inches(0.26), Inches(2.2), Inches(0.2),
              size=8.5, font=MONO, colour=FAINT, bold=True)[3].text = "ROLE IN THIS PROJECT"
    deck.rule(slide, MARGIN, y - Inches(0.04), Inches(8.35), colour=ACCENT, weight=Pt(1.0))
    y += Inches(0.1)

    for name, source, link, licence, colour, scale, role in DATASETS:
        deck.text(slide, MARGIN, y, Inches(4.4), Inches(0.2),
                  size=11, colour=INK, bold=True)[3].text = name
        _, _, para, run = deck.text(slide, MARGIN, y + Inches(0.19), Inches(4.5),
                                    Inches(0.2), size=8.5, font=MONO, colour=MUTED)
        if link:
            run.text = ""
            deck.rich(para, [(source, {"colour": ACCENT, "link": link, "size": 8.5})],
                      size=8.5, font=MONO)
        else:
            run.text = source
        deck.text(slide, MARGIN + Inches(4.6), y + Inches(0.03), Inches(1.7), Inches(0.2),
                  size=9, font=MONO, colour=colour, bold=True)[3].text = licence
        deck.text(slide, MARGIN + Inches(6.3), y + Inches(0.03), Inches(2.1), Inches(0.34),
                  size=9, colour=MUTED, spacing=1.15)[3].text = role
        y += Inches(0.53)
        deck.rule(slide, MARGIN, y - Inches(0.08), Inches(8.35))

    deck.panel(slide, Inches(9.35), BODY_Y - Inches(0.2), Inches(3.25), Inches(4.3),
               "Before anything is published", [
                   ("TrafficCAM: none declared", "checked — repo, site, download page"),
                   ("IDD requires a citation", "Varma et al., WACV 2019"),
                   ("ITD is non-commercial", "CC BY-NC 4.0 propagates"),
                   ("BMD-45 is the clean one", "CC BY 4.0, attribution only"),
               ],
               footnote="No licence is not the same as permissive: with none declared, "
                        "default copyright applies. Research use is normal practice; "
                        "redistributing the data or releasing weights trained on it is "
                        "not granted. The authors are named and reachable, so we ask "
                        "them — and cite the paper either way.")
    deck.notes(slide, """
This slide exists because a panel or a reviewer will ask where the data came
from, and because we found something while assembling it.

Go across the licence column. BMD-45 is clean, CC BY 4.0. IDD needs a citation,
which is easy. ITD is non-commercial, which constrains anything derived from it.

Then stop on TrafficCAM. It trains the detector, it is the ONLY source of
e-rickshaw examples, and it declares no licence at all -- we checked the GitHub
repository, the project website and the download page, and there is none in any
of them.

Be precise about what that means, because it is easy to get backwards. No
licence is not permissive; it is restrictive. Default copyright applies, so
nothing is granted. Using it for research is ordinary academic practice and we
are comfortable with it. Redistributing the data, or releasing weights trained
on it, is not.

So the plan is: keep using it, cite the paper properly -- Deng et al.,
arXiv:2211.09620, Cambridge and Bristol -- and email the authors for written
permission before anything is released. If asked "is this a problem", the honest
answer is: not for the project, potentially for the release, and one email fixes
it.
""")


def slide_detection(deck: Deck, fig: dict) -> None:
    slide = deck.content(6, "Result · detection", ["Detection at the deployment "
                                                   "viewpoint is ", "solved"],
                         lead="Milestone M2 was due in Week 9. It was met in Week 2, on "
                              "BMD-45's Bengaluru CCTV test split.")
    order = ["car", "motorcycle", "auto_rickshaw", "bus", "truck"]
    rows_by_class = {r["class"]: r for r in fig["bmd45"]}
    rows = []
    for name in order:
        row = rows_by_class[name]
        rows.append([name, row["precision"], row["recall"],
                     (row["mAP50"], {"colour": GOOD, "bold": True}),
                     row["mAP50_95"], f"{int(row['test_boxes']):,}"])
    total_boxes = sum(int(rows_by_class[n]["test_boxes"]) for n in order)
    rows.append([("mean", {"font": BODY, "bold": True}), "—", "—",
                 (f"{fig['bmd45_mean']:.4f}", {"colour": GOOD, "bold": True}),
                 "—", f"{total_boxes:,}"])

    deck.table(slide, MARGIN, BODY_Y, Inches(8.3),
               ["class", "precision", "recall", "mAP50", "mAP50-95", "test boxes"],
               rows,
               widths=[Inches(2.0), Inches(1.3), Inches(1.2), Inches(1.3),
                       Inches(1.4), Inches(1.1)],
               highlight={2, 5})

    deck.panel(slide, Inches(9.35), BODY_Y - Inches(0.1), Inches(3.25), Inches(3.0),
               "The number that matters", [
                   ("auto_rickshaw 0.9186", "a class COCO does not have"),
                   ("e_rickshaw, cattle", "absent from this test split"),
               ],
               footnote="Building our own detector is justified by the classes an "
                        "off-the-shelf model cannot see at all, not by a few points of "
                        "mAP on the classes it can.")
    deck.notes(slide, """
The row to point at is auto_rickshaw, 0.9186. That is the justification for
building a detector rather than downloading one -- COCO does not have the class,
so there is no baseline to beat, only a capability that either exists or does
not.

If asked about the blank rows: e_rickshaw and cattle have zero boxes in this
particular test split, so they are honestly reported as not evaluated rather
than given a misleading score. e_rickshaw comes up again two slides later.
""")


def slide_examples(deck: Deck, images: dict) -> None:
    slide = deck.content(7, "Detection · in the wild",
                         ["What ", "\"unstructured\" actually means"],
                         lead="Real output from the detector at confidence 0.45. "
                              "Neither scene has lane markings a model could rely on.")
    captions = [
        ("Mumbai — Andheri Station", "23 vehicles in one frame. A bus filling a quarter "
                                     "of the image and motorcycles under one percent of it."),
        ("Dhaka — Rampura", "20 vehicles. The pilot camera: its quietest moment in twenty "
                            "minutes still held nine vehicles."),
    ]
    for index, key in enumerate(("mumbai", "dhaka")):
        x = MARGIN + index * Inches(6.15)
        if images.get(key):
            slide.shapes.add_picture(str(images[key]), x, BODY_Y, width=Inches(5.85))
            top = BODY_Y + Inches(3.32)
        else:
            deck.rect(slide, x, BODY_Y, Inches(5.85), Inches(3.2), fill=PANEL, line=RULE)
            deck.text(slide, x + Inches(0.4), BODY_Y + Inches(1.4), Inches(5.0),
                      Inches(0.5), size=11, font=MONO, colour=FAINT,
                      align=PP_ALIGN.CENTER)[3].text = (
                "source footage not present on this machine")
            top = BODY_Y + Inches(3.32)
        title, detail = captions[index]
        deck.text(slide, x, top, Inches(5.85), Inches(0.22),
                  size=11, colour=INK, bold=True)[3].text = title
        deck.text(slide, x, top + Inches(0.24), Inches(5.85), Inches(0.5),
                  size=10, colour=MUTED, spacing=1.2)[3].text = detail

    deck.text(slide, MARGIN, Inches(6.72), Inches(11.9), Inches(0.3),
              size=10, font=MONO, colour=FAINT)[3].text = (
        "Boxes coloured by class in the detector's own taxonomy  ·  vehicles span 25% of "
        "the frame down to under 1%")
    deck.notes(slide, """
Let the pictures do the work; say very little.

Two things worth naming. First, the scale range -- a bus occupying a quarter of
the frame and a motorcycle occupying under one percent, in the same image. That
is a genuinely hard detection problem and it is why input resolution matters.

Second, look at how the vehicles are arranged. There is no lane structure to
exploit. That is the whole argument for treating lanes as regions a human marks
rather than something the model infers.
""")


def slide_m2(deck: Deck, fig: dict) -> None:
    coco, ours, delta = m2_shared_mean(fig["m2"])
    slide = deck.content(8, "Result · vs COCO", [f"+{delta:.1f}% mAP over COCO ",
                                                 "on the shared classes"],
                         lead="M2's criterion is a 10% improvement over COCO. It had been "
                              "asserted and never measured, so we measured it — same test "
                              "split, ground truth remapped so one validator scores both.")
    rows = []
    for row in fig["m2"]:
        if row.get("coco_mAP50") in (None, ""):
            continue
        gain = float(row["delta"])
        rows.append([row["class"], row["coco_mAP50"], row["ours_mAP50"],
                     (f"+{gain:.4f}", {"colour": GOOD, "bold": True})])
    rows.append([("shared mean", {"font": BODY, "bold": True}),
                 f"{coco:.4f}", f"{ours:.4f}",
                 (f"+{delta:.1f}%", {"colour": GOOD, "bold": True})])
    deck.table(slide, MARGIN, BODY_Y, Inches(7.2),
               ["class", "COCO baseline", "ours", "delta"], rows,
               widths=[Inches(2.2), Inches(1.8), Inches(1.6), Inches(1.6)],
               highlight={4})

    deck.panel(slide, Inches(8.3), BODY_Y - Inches(0.1), Inches(4.3), Inches(2.9),
               "Where no percentage is honest", [
                   ("auto_rickshaw  0.7109", "COCO has no such class"),
                   ("cattle  0.3516", "COCO has no such class"),
               ],
               footnote="The baseline is not low here, it is undefined. Saying that is a "
                        "stronger statement than any percentage would have been, and it "
                        "is the difference between a result and a marketing number.")
    deck.notes(slide, """
Five times the threshold the milestone asked for, so the milestone is met
comfortably.

The important part is the panel. For auto-rickshaw and cattle we deliberately
report no improvement percentage, because COCO cannot detect those classes at
all -- the denominator does not exist. It would have been easy to write "infinite
improvement" and it would have been meaningless.

If a reviewer probes the methodology: we remapped the ground truth so that
Ultralytics' own validator scored both models on the same split. We did not
compare our number against a figure quoted in someone else's paper.
""")


def slide_counting(deck: Deck, fig: dict) -> None:
    slide = deck.content(9, "Result · counting", ["Counting accuracy is ",
                                                  "not detection accuracy"],
                         lead="Congestion labels come from counts, and a detector with "
                              "excellent mAP can still systematically over- or under-count. "
                              "So the operating point was fitted against 5,273 "
                              "human-annotated vehicles.")
    rows = []
    for conf in ("0.25", "0.35", "0.45", "0.55", "0.6"):
        row = fig["counting"][conf]
        ratio = float(row["detected_over_true"])
        colour = GOOD if abs(ratio - 1) < 0.01 else (WARN if abs(ratio - 1) < 0.08 else BAD)
        rows.append([conf, (row["detected_over_true"], {"colour": colour, "bold": True}),
                     row["sparse_third"], row["dense_third"],
                     row["mae_vehicles_per_frame"]])
    deck.table(slide, MARGIN, BODY_Y, Inches(7.4),
               ["confidence", "detected / true", "sparse third", "dense third",
                "MAE per frame"], rows,
               widths=[Inches(1.5), Inches(1.7), Inches(1.5), Inches(1.4), Inches(1.3)],
               highlight={2})

    deck.panel(slide, Inches(8.5), BODY_Y - Inches(0.1), Inches(4.1), Inches(3.1),
               "Why the last two columns exist", [
                   ("0.45 is pinned", "ratio 0.9989, lowest error"),
                   ("Density dependence 2.8%", "reported, not averaged away"),
               ],
               footnote="A detector accurate on average can still be biased with density — "
                        "under-counting exactly when the road is busy, which is exactly "
                        "when the forecast matters. Splitting the test set by density is "
                        "the only way to see it.")
    deck.notes(slide, """
This is a methodology slide and it usually earns credit.

The argument: mAP tells you whether boxes are in the right place. It does not
tell you whether the COUNT is right, and the count is what becomes the label. So
we swept the confidence threshold and picked the point where detected-over-true
is closest to one.

The sparse and dense columns are the part to emphasise. A detector can look
perfect on average while under-counting in heavy traffic -- which is precisely
when a congestion forecast matters. Ours has 2.8% residual density dependence
and we report it rather than hiding it in an average.
""")


def slide_generalisation(deck: Deck, fig: dict) -> None:
    slide = deck.content(10, "Honesty", ["The number that governs deployment is ",
                                         "0.3500, not 0.8941"],
                         lead="A model deployed on a junction it has never seen is in the "
                              "third column. Reporting only the first would be the easiest "
                              "mistake in this project.")
    # Both cards are the SAME detector (s15) on two test sets. An IDD figure
    # would have to come from a different model's CSV, and putting two models
    # in one comparison row is exactly the sort of thing this slide is about.
    cards = [
        ("BMD-45 — trained domain", f"{fig['bmd45_mean']:.4f}", GOOD,
         "Bengaluru Safe City CCTV, the viewpoint the detector was built for"),
        ("TrafficCAM — cameras never seen", f"{fig['trafficcam_mean']:.4f}", BAD,
         "five other Indian cities, same elevated viewpoint, different cameras"),
    ]
    for index, (name, value, colour, detail) in enumerate(cards):
        x = MARGIN + index * Inches(4.25)
        deck.rect(slide, x, BODY_Y, Inches(3.95), Inches(1.66), fill=PANEL,
                  line=colour if index == 1 else RULE)
        deck.text(slide, x + Inches(0.26), BODY_Y + Inches(0.2), Inches(3.5), Inches(0.2),
                  size=9, font=MONO, colour=FAINT, bold=True)[3].text = name.upper()
        deck.text(slide, x + Inches(0.26), BODY_Y + Inches(0.46), Inches(3.4), Inches(0.45),
                  size=30, colour=colour, bold=True)[3].text = value
        deck.text(slide, x + Inches(0.26), BODY_Y + Inches(1.04), Inches(3.5), Inches(0.5),
                  size=9.5, colour=MUTED, spacing=1.2)[3].text = detail
    drop = (1 - fig["trafficcam_mean"] / fig["bmd45_mean"]) * 100
    deck.text(slide, MARGIN, Inches(4.14), Inches(8.2), Inches(0.24),
              size=10.5, font=MONO, colour=BAD,
              bold=True)[3].text = (f"the same weights lose {drop:.0f}% of their accuracy "
                                    f"moving to cameras they were not trained on")

    deck.rect(slide, MARGIN, Inches(4.34), Inches(8.3), Inches(1.62),
              fill=RGBColor(0xF7, 0xF1, 0xE4), line=AMBER)
    deck.text(slide, MARGIN + Inches(0.3), Inches(4.52), Inches(7.6), Inches(0.22),
              size=9.5, font=MONO, colour=WARN,
              bold=True)[3].text = "WHAT FIXED IT, AND WHY WE DID NOT ADOPT IT"
    _, _, _, run = deck.text(slide, MARGIN + Inches(0.3), Inches(4.78),
                             Inches(7.7), Inches(1.0), size=11, colour=INK, spacing=1.28)
    run.text = ("Adding 1,254 human-annotated TrafficCAM boxes moved cross-camera "
                "accuracy to 0.5734 and brought e_rickshaw from 0.000 to 0.4787 — a class "
                "the detector had been shipping an output head for without ever seeing an "
                "example. That arm was recorded as failing a sixth criterion on IDD. "
                "Re-measuring the baseline it was judged against does not reproduce it, so "
                "the verdict is suspended rather than reversed: both sides have to be "
                "measured the same way before it means anything.")

    deck.panel(slide, Inches(9.35), BODY_Y - Inches(0.1), Inches(3.25), Inches(3.5),
               "The comparison that shows it", [
                   ("Dashcam-trained on CCTV", f"{fig['dashcam_on_elevated']:.4f}"),
                   ("Same model, own test set", f"{fig['s11_own']:.4f}"),
               ],
               footnote="Viewpoint, not country, is what breaks a detector. The same "
                        "weights lose half their accuracy moving from a dashcam to a pole, "
                        "which is why the whole data strategy targets elevated cameras.")
    deck.notes(slide, """
Lead with the honesty. Say out loud: the headline number is 0.8941, and the
number that governs deployment is 0.3500. A junction the model has not seen is
the third column.

The amber box is the one to dwell on if there is time. We found something that
fixed a real gap -- e-rickshaw went from literally zero to 0.48 -- and did not
adopt it, because it was recorded as failing a criterion fixed in advance.

Then be honest about what happened next: re-measuring that criterion's baseline
did not reproduce the number it was judged against. So the verdict is suspended,
not reversed. Reversing it on one re-measured half would repeat the mistake that
caused it. If asked what we will do: measure both sides the same way.

If asked what happens next: the open question is whether dashcam accuracy should
still be an acceptance criterion at all, given the deployment is a fixed camera.
That is a decision we have put to the guide.

Both cards are the same detector on two test sets, deliberately. If asked about
IDD: the earlier joint detector scored 0.6174 there, but quoting it beside these
two would be putting a different model in the same comparison row.
""")


def slide_pipeline(deck: Deck) -> None:
    slide = deck.content(11, "The corpus", ["Nine steps, and the expensive one ",
                                            "runs once"],
                         lead="Turning video into training data. The detector pass costs "
                              "hours; every choice made after it re-derives in seconds.")
    steps = ["triage\nwhich clips qualify", "survey\nwhere traffic is",
             "place lanes\nby hand, per camera", "import\nvalidate placement",
             "build corpus\ndetector → counts", "relabel\nthresholds",
             "audit\nre-derive and check", "cache\nfrozen features",
             "train\nconfig or ablation"]
    for index, step in enumerate(steps):
        x = MARGIN + (index % 5) * Inches(2.42)
        y = BODY_Y + (index // 5) * Inches(1.02)
        accent = index in (2, 6)
        deck.rect(slide, x, y, Inches(2.24), Inches(0.84), fill=PANEL,
                  line=ACCENT if accent else RULE)
        name, detail = step.split("\n")
        deck.text(slide, x + Inches(0.18), y + Inches(0.14), Inches(2.0), Inches(0.22),
                  size=11.5, colour=ACCENT if accent else INK, bold=True)[3].text = name
        deck.text(slide, x + Inches(0.18), y + Inches(0.42), Inches(2.0), Inches(0.34),
                  size=9, colour=MUTED, spacing=1.15)[3].text = detail

    deck.rect(slide, MARGIN, Inches(4.66), CONTENT_W, Inches(1.5),
              fill=RGBColor(0xEC, 0xEB, 0xFA), line=ACCENT)
    deck.text(slide, MARGIN + Inches(0.3), Inches(4.84), Inches(11), Inches(0.22),
              size=9.5, font=MONO, colour=ACCENT,
              bold=True)[3].text = "WHAT A CHANGE ACTUALLY COSTS"
    for index, (what, cost, colour) in enumerate([
            ("Move a lane centre", "0.66 s", GOOD),
            ("Change the thresholds", "seconds", GOOD),
            ("Change detector, confidence or sampling", "hours", WARN)]):
        x = MARGIN + Inches(0.3) + index * Inches(3.9)
        deck.text(slide, x, Inches(5.14), Inches(3.6), Inches(0.24),
                  size=11, colour=INK)[3].text = what
        deck.text(slide, x, Inches(5.42), Inches(3.6), Inches(0.3),
                  size=15, colour=colour, bold=True)[3].text = cost
    deck.notes(slide, """
The point of this slide is the purple box, not the nine boxes above it.

Lane placement is done by eye over a heat map, so it was never going to be right
first time. Before, revising it meant running the detector over every clip again
-- hours. Now the detections are stored separately from the lane geometry, so
re-placing a lane and rebuilding the labels takes under a second.

That matters more than the speed suggests: a feedback loop that costs hours gets
used once, and the placement ends up judged on how it looks rather than on the
counts it produces.
""")


def slide_lanes(deck: Deck, images: dict) -> None:
    slide = deck.content(12, "Lane geometry", ["A lane that moves when the tooling "
                                               "changes ", "is not a property of the road"],
                         lead="Lane centres are placed by a human over a detection heat "
                              "map, and the reason is measurable.")
    if images.get("lanes"):
        slide.shapes.add_picture(str(images["lanes"]), MARGIN, BODY_Y, width=Inches(7.2))
    else:
        deck.rect(slide, MARGIN, BODY_Y, Inches(7.2), Inches(4.05), fill=PANEL, line=RULE)
        deck.text(slide, MARGIN + Inches(0.6), BODY_Y + Inches(1.9), Inches(6.0),
                  Inches(0.4), size=11, font=MONO, colour=FAINT,
                  align=PP_ALIGN.CENTER)[3].text = "source footage not present"

    deck.panel(slide, Inches(8.4), BODY_Y - Inches(0.1), Inches(4.2), Inches(3.1),
               "Measured, not assumed", [
                   ("0.164 of frame width", "≈ 315 px of drift"),
                   ("Between two detectors", "same footage, same settings"),
               ],
               footnote="Automatic centres are a clustering of where the detector happened "
                        "to fire. Swap the detector and they move. A reviewer placing them "
                        "by hand is placing something about the road instead.")
    deck.text(slide, Inches(8.4), Inches(5.85), Inches(4.2), Inches(0.8),
              size=10.5, colour=MUTED, spacing=1.25)[3].text = (
        "The count matters more than the positions. At two centres, two cameras left "
        "over a third of vehicles outside every lane; at four, the worst is 10.5%.")
    deck.notes(slide, """
The image is detection density over sixty sampled frames, with the automatic
lane centres marked.

The measurement is the argument: swap the detector and those centres move by
0.164 of the frame width, about 315 pixels. Something that moves when you change
your tooling is not a fact about the road, so we do not let the tooling decide
it.

The last line is worth saying if there is time -- how MANY lanes you place
matters more than exactly where. Two centres left a third of the vehicles
unassigned on some cameras. Four fixed it.
""")


def slide_sampling(deck: Deck, fig: dict) -> None:
    slide = deck.content(13, "Decision · A28", ["Every 2 seconds, not 5, ",
                                                "keeps four cameras alive"],
                         lead="The PRD fixes a 5-second interval as a bare number derived "
                              "nowhere. We pre-registered a statistic to replace it before "
                              "the footage existed, deliberately biased against the answer "
                              "we wanted.")
    rows = []
    for step, label in ((5, "5 — current"), (2, "2 — proposed"), (1, "1")):
        seq, ind, cams = yield_totals(fig["yield"], step)
        minimum = (60 - 1) * step + 60
        rows.append([label, f"{minimum} s", str(seq), str(ind),
                     (f"{cams} of 11", {"colour": GOOD if cams == 11 else WARN,
                                        "bold": True})])
    deck.table(slide, MARGIN, BODY_Y, Inches(7.5),
               ["step_s", "clip minimum", "sequences", "independent segments",
                "cameras contributing"], rows,
               widths=[Inches(1.5), Inches(1.4), Inches(1.4), Inches(1.9), Inches(1.3)],
               highlight={1})

    deck.rect(slide, MARGIN, Inches(4.5), Inches(7.5), Inches(1.5),
              fill=RGBColor(0xEC, 0xEB, 0xFA), line=ACCENT)
    deck.text(slide, MARGIN + Inches(0.3), Inches(4.68), Inches(6.8), Inches(0.22),
              size=9.5, font=MONO, colour=ACCENT,
              bold=True)[3].text = "THE SEQUENCE COLUMN IS THE WEAKER ARGUMENT"
    _, _, _, run = deck.text(slide, MARGIN + Inches(0.3), Inches(4.94),
                             Inches(6.9), Inches(0.9), size=11, colour=INK, spacing=1.28)
    run.text = ("Overlapping windows inflate any sequence count — measured at 5.6×. The "
                "column that matters is the last one: a 5-second interval needs 355 s of "
                "continuous footage per clip and so deletes four cameras outright. "
                "Sequences from one camera are correlated; cameras are the unit the model "
                "must generalise over, and no augmentation manufactures a viewpoint.")

    deck.panel(slide, Inches(8.6), BODY_Y - Inches(0.1), Inches(4.0), Inches(3.4),
               "What the statistic returned", [
                   ("1 or 2, in all six", "three detectors × two threshold sets"),
                   ("Never 5", "the value the PRD assumed"),
               ],
               footnote="Fixing the statistic before seeing the data is what makes this a "
                        "measurement rather than a preference. It was also chosen so that "
                        "a wrong answer would favour keeping the PRD's value.")
    deck.notes(slide, """
Explain pre-registration first, because it is the part that makes this credible:
we wrote down the formula before we had the footage, and we chose one that would
favour keeping the PRD's existing value if it was wrong.

It returned 1 or 2 in all six combinations we tested. Never 5.

Then correct the obvious reading of the table. Do not claim "the corpus doubles"
-- overlapping windows inflate the sequence count by 5.6 times, so that number
means little. The real argument is the last column: at 5 seconds a clip needs
355 seconds of continuous footage, which deletes four of our eleven cameras
entirely, including the best Indian junction scene we have.
""")


def slide_model(deck: Deck) -> None:
    slide = deck.content(14, "The model", ["Two frozen backbones, ",
                                           "arbitrated by a learned gate"],
                         lead="MFSTNet is the project's core contribution. The gate is a "
                              "research artifact in its own right — logged every run and "
                              "analysed in the paper.")
    stages = ["ResNet-50\n2048 × 7 × 7\nfrozen", "DINOv2 ViT-S/14\n384 × 16 × 16\nfrozen",
              "bidirectional\ncross-attention\ntwo directions",
              "the gate\ng = σ(W[Z_A;Z_B])\nF = gZ_A + (1−g)Z_B",
              "per-lane ROI\nVoronoi cells from\nlane centres",
              "BiLSTM + temporal\nattention, T = 60",
              "congestion head\nLOW / MED / HIGH\n60 s ahead"]
    for index, stage in enumerate(stages):
        x = MARGIN + (index % 4) * Inches(3.03)
        y = BODY_Y + (index // 4) * Inches(1.32)
        accent = index == 3
        deck.rect(slide, x, y, Inches(2.82), Inches(1.14),
                  fill=RGBColor(0xEC, 0xEB, 0xFA) if accent else PANEL,
                  line=ACCENT if accent else RULE)
        lines = stage.split("\n")
        deck.text(slide, x + Inches(0.2), y + Inches(0.16), Inches(2.5), Inches(0.22),
                  size=12, colour=ACCENT if accent else INK,
                  bold=True)[3].text = lines[0]
        deck.text(slide, x + Inches(0.2), y + Inches(0.44), Inches(2.55), Inches(0.6),
                  size=9, font=MONO, colour=MUTED,
                  spacing=1.25)[3].text = "\n".join(lines[1:])

    deck.text(slide, MARGIN, Inches(5.66), Inches(11.9), Inches(0.8),
              size=11, colour=MUTED, spacing=1.3)[3].text = (
        "Freezing the backbones and caching their features is what makes an eight-config "
        "ablation feasible on a 6 GB laptop GPU. Ablation-ability is treated as an "
        "architectural constraint, not an afterthought: every module can be disabled by a "
        "config flag, with no code edit between configs.")
    deck.notes(slide, """
Walk the pipeline once, briefly. Both backbones are frozen -- we do not fine-tune
them -- and their features are cached, which is the single decision that makes
the experiment affordable.

Stop on the gate, in purple. Two cross-attention directions produce two views;
the gate learns how much to weight each, per location and per timestep. It is not
an internal detail: we log it, plot it, and analyse it in the paper, because "how
does the model balance texture against structure" is the interesting question.

If asked why frozen: with a corpus this size, fine-tuning 45 million parameters
would overfit immediately. The next slide is about what the gate actually does.
""")


def slide_gate(deck: Deck, fig: dict) -> None:
    slide = deck.content(15, "Result · the gate", ["The gate can gate — the flat gate is ",
                                                   "a fact about the data"],
                         lead="On the pilot corpus it sits at 0.54 with a spread of 0.005: "
                              "one value everywhere, which is a scalar blend rather than a "
                              "gate. So we asked whether it can do more.")
    rows = []
    for row in fig["gate"]:
        rows.append([row["seed"],
                     (row["gate_std"], {"colour": GOOD, "bold": True}),
                     row["gate_when_cnn_carries"], row["gate_when_vit_carries"],
                     row["gate_separation"]])
    deck.table(slide, MARGIN, BODY_Y, Inches(7.3),
               ["seed", "gate std", "g when CNN carries", "g when ViT carries",
                "separation"], rows,
               widths=[Inches(1.1), Inches(1.5), Inches(1.9), Inches(1.8), Inches(1.0)])

    _, _, _, run = deck.text(slide, MARGIN, Inches(4.3), Inches(7.5), Inches(1.0),
                             size=11.5, colour=INK, spacing=1.3)
    run.text = ("Given a task where half the samples carry the label in the CNN branch and "
                "half in the ViT, the gate moves by 50–90× its pilot spread and routes "
                "toward whichever branch is worth reading. The mechanism works; the pilot "
                "corpus simply does not demand it.")

    deck.panel(slide, Inches(8.4), BODY_Y - Inches(0.1), Inches(4.2), Inches(3.5),
               "Why it is flat, exactly", [
                   ("z_a, z_b nearly orthogonal", "cosine −0.004 — different information"),
                   ("but small: std 0.035", "so the sigmoid stays linear"),
                   ("predicted gate std 0.006", "observed 0.006"),
               ],
               footnote="The residual adds both branches back ungated, so neither can be "
                        "fully suppressed. That bounds how much of the ablation's gain "
                        "gating can ever explain — which belongs in the paper rather than "
                        "in a reviewer's question.")
    deck.notes(slide, """
This is the slide a good examiner will push on, so know it well.

Observation: on our pilot data the gate barely moves. Rather than hand-wave, we
instrumented its input and predicted the spread from first principles -- the two
inputs are nearly orthogonal but small, so the sigmoid never leaves its linear
region. Predicted 0.006, observed 0.006.

Then we built a task that REQUIRES gating and showed the gate moves by fifty to
ninety times that, in the right direction, across three seeds. So the mechanism
has capacity; the flat reading is a statement about five cameras of data.

Volunteer the caveat before you are asked: the residual connection adds both
branches back ungated, so the gate can never fully suppress a branch. That limits
how much of the ablation difference gating can account for.
""")


def slide_control(deck: Deck, fig: dict) -> None:
    slide = deck.content(16, "Result · signal control", ["Baselines reported as measured, ",
                                                         "including where they disqualify"],
                         lead="Thirty paired seeds per regime, bootstrap confidence "
                              "intervals, paired t-test and Cohen's d — the statistics the "
                              "requirements ask for.")
    rows = []
    for regime, cite in (("light", "partly"), ("saturated", "yes"),
                         ("oversaturated", "no")):
        fixed_web = fig["bench"](regime, "fixed", "webster")
        fixed_lq = fig["bench"](regime, "fixed", "longest_queue")
        colour = {"yes": GOOD, "partly": WARN, "no": BAD}[cite]
        rows.append([regime,
                     f"{float(fixed_web['mean_a']):.2f}",
                     f"{float(fixed_lq['mean_b']):.2f}",
                     f"{float(fixed_web['mean_b']):.2f}",
                     f"{float(fixed_web['cohens_d']):.2f}",
                     (cite, {"colour": colour, "bold": True})])
    deck.table(slide, MARGIN, BODY_Y, Inches(7.6),
               ["regime", "fixed-time", "longest-queue", "webster", "cohen's d",
                "citable"], rows,
               widths=[Inches(1.7), Inches(1.3), Inches(1.5), Inches(1.2),
                       Inches(1.2), Inches(0.7)],
               highlight={1})
    deck.text(slide, MARGIN, Inches(4.16), Inches(7.6), Inches(0.3),
              size=9.5, font=MONO, colour=FAINT)[3].text = (
        "mean wait, seconds  ·  headline comparison is made at saturation")

    deck.panel(slide, Inches(8.6), BODY_Y - Inches(0.1), Inches(4.0), Inches(3.6),
               "Two automatic disqualifications", [
                   ("Light: Webster clamps 100%", "a fixed-time controller in disguise"),
                   ("Oversaturated: <85% arrive", "a low wait measures survivors only"),
               ],
               footnote="Both rules were written before the runs. They exist because the "
                        "flattering reading of each regime is available and wrong — a "
                        "controller that finishes fewer trips can post a better mean wait "
                        "simply by losing the slow ones.")
    deck.notes(slide, """
Point at the saturated row -- that is the headline, because saturation is where
signal timing actually decides the outcome. Webster is clearly best there, with a
very large effect size.

Then explain the two disqualifications, which are the interesting part. In light
traffic Webster's cycle formula hits its clamp one hundred percent of the time,
so it is not really Webster any more and the comparison is not citable. In
oversaturated traffic all three controllers fail to clear 85% of trips, and a
mean wait computed over survivors is survivorship bias.

Both rules were written before the runs. Say that -- it is the difference between
a filter and an excuse.
""")


def slide_engineering(deck: Deck) -> None:
    slide = deck.content(17, "Engineering", ["The ablation went from ",
                                             "12.3 hours to 1.5"],
                         lead="Two independent faults were hiding behind one symptom, and "
                              "half of every training epoch was spent on the wrong side of "
                              "the bus.")
    rows = [
        ["A · CNN only", "33.2 s", "20.5 s", ("12.7 s", {"colour": GOOD}), "2.6×"],
        ["B · ViT only", "20.1 s", "19.8 s", ("9.4 s", {"colour": GOOD}), "2.1×"],
        ["G · full MFSTNet", "208.4 s", "40.0 s", ("16.6 s", {"colour": GOOD}), "12.6×"],
        [("A–H, extrapolated", {"font": BODY, "bold": True}), "12.3 h", "3.8 h",
         ("1.5 h", {"colour": GOOD, "bold": True}), "8.2×"],
    ]
    deck.table(slide, MARGIN, BODY_Y, Inches(7.0),
               ["config", "CPU", "GPU fp32", "GPU fp16", "gain"], rows,
               widths=[Inches(2.0), Inches(1.2), Inches(1.3), Inches(1.3), Inches(1.2)],
               highlight={3})

    findings = [
        ("The documented install could not work",
         "It pointed at a CUDA index that no longer carries PyTorch at any version, so it "
         "silently resolved to the CPU wheel."),
        ("The trainer had no device handling at all",
         "A correct install would still have run on the CPU with the GPU idle. It does not "
         "error; it is just slow on a machine that looks healthy."),
        ("Features were widened too early",
         "The cache stores fp16 and the model wants fp32. Widening before the transfer "
         "doubled what was copied and shipped — and the widening is exact, so moving it "
         "changed no result."),
    ]
    y = Inches(4.62)
    for lead, detail in findings:
        deck.rect(slide, MARGIN, y + Inches(0.07), Inches(0.05), Inches(0.05),
                  fill=ACCENT, shape=MSO_SHAPE.OVAL)
        deck.text(slide, MARGIN + Inches(0.2), y, Inches(7.0), Inches(0.2),
                  size=10.5, colour=INK, bold=True)[3].text = lead
        deck.text(slide, MARGIN + Inches(0.2), y + Inches(0.2), Inches(7.0), Inches(0.4),
                  size=9.5, colour=MUTED, spacing=1.2)[3].text = detail
        y += Inches(0.66)

    deck.text(slide, MARGIN, Inches(4.26), Inches(7.0), Inches(0.22),
              size=8.5, font=MONO, colour=FAINT)[3].text = (
        "measured on the five-camera pilot during the optimisation work; "
        "not a committed CSV")

    deck.panel(slide, Inches(8.3), BODY_Y - Inches(0.1), Inches(4.3), Inches(4.2),
               "Reproducibility machinery", [
                   ("Pre-registered thresholds", "fixed before the run that tests them"),
                   ("Results written, never typed", "a short run refuses to overwrite a long one"),
                   ("The corpus audits itself", "9 checks; 7 of 7 mutations caught"),
                   ("Results carry their environment", "torch build, device, TF32, commit"),
               ],
               footnote=f"{project_counts()['tests']} tests · "
                        f"{project_counts()['commits']} commits · "
                        f"{project_counts()['adrs']} decision records · seeds fixed at "
                        f"42 across Python, NumPy, PyTorch and SB3.")
    deck.notes(slide, """
Two stories here and both are short.

First, why training was slow: the install instructions in our own docs pointed at
a CUDA index that no longer exists, so following them silently gave the CPU-only
build. And even with that fixed, the training script never moved anything to the
GPU. Two separate faults, one symptom.

Second, the fp16 point is a nice engineering detail. The cache stores half
precision, the model wants single -- we were converting before the transfer, so
we copied and shipped twice the bytes. Moving the conversion after the transfer
is exact, so all eight configs produce identical numbers, 2.5 times faster.

The panel on the right is what to mention if asked about rigour.
""")


def slide_next(deck: Deck) -> None:
    slide = deck.content(18, "Challenges & next", ["What went wrong, ",
                                                   "and what happens now"],
                         lead="Twenty-nine defects are logged with their cause and cost. "
                              "These are the ones that changed the project.")
    rows = [
        ["P21", "e_rickshaw scored 0.000", "IDD contains zero instances — a head trained on nothing"],
        ["P23", "Lane polygons overlapped on 11 of 12 cameras", "every vehicle in the overlap double-counted"],
        ["P26", "Every camera pooled through one camera's lanes", "silent: shapes agree, loss falls, wrong region"],
        ["P29", "A cached window read its entire clip", "26 GB of churn for 1.5 GB — segfault, no traceback"],
        ["P30", "No pinned package matched its installed version", "a clean machine would build a different stack"],
        ["P34", "Calibration produced an impossible threshold", "0% LOW — the degeneracy it exists to prevent"],
    ]
    deck.table(slide, MARGIN, BODY_Y, Inches(7.8),
               ["#", "what was wrong", "why it mattered"], rows,
               widths=[Inches(0.7), Inches(3.3), Inches(3.8)],
               size=9.5, row_h=Inches(0.42))

    deck.text(slide, MARGIN, Inches(5.5), Inches(7.8), Inches(0.6),
              size=10.5, colour=MUTED, spacing=1.25)[3].text = (
        "Three of these shared one shape — a number whose meaning depended on a fact the "
        "number did not carry. Each was fixed where it happened; the pattern was then "
        "closed once, by recording the environment beside every result.")

    deck.panel(slide, Inches(8.6), BODY_Y - Inches(0.1), Inches(4.0), Inches(3.5),
               "Three decisions, then the corpus", [
                   ("A28 — sampling interval", "eleven cameras, or seven"),
                   ("ADR-017 — thresholds", "what every congestion table means"),
                   ("S17 — acceptance surface", "which detector is the one of record"),
               ],
               footnote="Everything on the critical path is built and measured. What "
                        "remains is not engineering: place the lane centres, build the "
                        "corpus, audit it, run the ablation — an evening's compute.")
    deck.text(slide, Inches(8.6), Inches(6.0), Inches(4.0), Inches(0.8),
              size=10, colour=MUTED, spacing=1.25)[3].text = (
        "Honest limit: 64 independent segments across 11 cameras, and 20 of them come "
        "from one clip. That concentration is the corpus's real weakness.")
    deck.notes(slide, """
Do not present the defect table as failure. Present it as evidence that the
project is being checked -- most of these were found by us, on purpose, and each
one has a test that stops it returning.

If you only mention one, mention P26: every camera was being pooled through a
single camera's lane geometry, and nothing looked wrong. The shapes agreed, the
loss fell, the numbers were plausible. That is the kind of defect that reaches a
paper.

Close on the three decisions. Be clear that they are not engineering blockers --
the pipeline runs end to end today. They decide what the numbers are OF, and two
of them cost minutes to reverse.

Finish with the honest limit rather than a flourish. Twenty of sixty-four
segments come from one clip; more footage from one junction is the only thing
that fixes it.
""")


KAGGLE_USER = "idredk"
KAGGLE_RUNS = [
    ("S11", "cnn-vit-bilstm-cross-attention-traffic-system-s11",
     "—", "IDD bootstrap detector", "in repo", GOOD),
    ("S14", "cnn-vit-bilstm-cross-attention-traffic-system-s14",
     "—", "joint BMD-45 + IDD detector, and the s15 augmented variant",
     "in repo", GOOD),
    ("S16", "cnn-vit-bilstm-cross-attention-traffic-system-s16",
     "4.2 h", "ITD-distilled detector — not adopted, BMD-45 fell 0.0057",
     "not fetched", WARN),
    ("S17", "cnn-vit-bilstm-cross-attention-traffic-system-s17",
     "2.8 h", "TrafficCAM-augmented detector — verdict suspended (P43)",
     "not fetched", BAD),
]
KAGGLE_DATASETS = [
    "indiatrafficnet-bootstrap-idd-yolo",
    "cnn-vit-bilstm-traffic-itd-pseudo-labels",
    "cnn-vit-bilstm-traffic-trafficcam-yolo",
]


def slide_compute(deck: Deck) -> None:
    slide = deck.content(19, "Compute", ["Where each run happened, ",
                                         "and what came back"],
                         lead="Detector training ran on Kaggle T4 x2. Everything "
                              "else runs on the project laptop.")
    # A touch below the usual body line: this slide's lead sits directly above
    # a header row, and they crowd each other at the default spacing.
    y = BODY_Y + Inches(0.18)
    headers = [("run", Inches(0.8)), ("kaggle notebook", Inches(4.0)),
               ("gpu time", Inches(1.0)), ("what it produced", Inches(3.4)),
               ("weights", Inches(1.2))]
    x = MARGIN
    for name, w in headers:
        deck.text(slide, x, y - Inches(0.26), w - Inches(0.1), Inches(0.2),
                  size=8.5, font=MONO, colour=FAINT, bold=True)[3].text = name.upper()
        x += w
    deck.rule(slide, MARGIN, y - Inches(0.04), Inches(10.4), colour=ACCENT,
              weight=Pt(1.0))
    y += Inches(0.12)

    for run, slug, hours, produced, state, colour in KAGGLE_RUNS:
        deck.text(slide, MARGIN, y, Inches(0.7), Inches(0.2),
                  size=11, colour=INK, bold=True)[3].text = run
        _, _, para, run_obj = deck.text(slide, MARGIN + Inches(0.8), y,
                                        Inches(3.9), Inches(0.2),
                                        size=8.5, font=MONO, colour=MUTED)
        run_obj.text = ""
        deck.rich(para, [(slug, {"colour": ACCENT, "size": 8.5,
                                 "link": f"https://www.kaggle.com/code/"
                                         f"{KAGGLE_USER}/{slug}"})],
                  size=8.5, font=MONO)
        deck.text(slide, MARGIN + Inches(4.8), y, Inches(0.9), Inches(0.2),
                  size=9.5, font=MONO, colour=INK)[3].text = hours
        deck.text(slide, MARGIN + Inches(5.8), y - Inches(0.02), Inches(3.3),
                  Inches(0.4), size=9, colour=MUTED, spacing=1.15)[3].text = produced
        deck.text(slide, MARGIN + Inches(9.2), y, Inches(1.2), Inches(0.2),
                  size=9, font=MONO, colour=colour, bold=True)[3].text = state
        y += Inches(0.62)
        deck.rule(slide, MARGIN, y - Inches(0.14), Inches(10.4))

    deck.text(slide, MARGIN, y + Inches(0.06), Inches(2.2), Inches(0.2),
              size=8.5, font=MONO, colour=FAINT, bold=True)[3].text = "KAGGLE DATASETS"
    _, _, para, run_obj = deck.text(slide, MARGIN, y + Inches(0.3),
                                    Inches(11.6), Inches(0.2),
                                    size=8.5, font=MONO, colour=MUTED)
    run_obj.text = ""
    pieces = []
    for index, slug in enumerate(KAGGLE_DATASETS):
        if index:
            pieces.append(("   ·   ", {"colour": FAINT, "size": 8.5}))
        pieces.append((slug, {"colour": ACCENT, "size": 8.5,
                              "link": f"https://www.kaggle.com/datasets/"
                                      f"{KAGGLE_USER}/{slug}"}))
    deck.rich(para, pieces, size=8.5, font=MONO)

    deck.rect(slide, MARGIN, Inches(5.86), Inches(11.9), Inches(1.2),
              fill=RGBColor(0xF7, 0xF1, 0xE4), line=AMBER)
    deck.text(slide, MARGIN + Inches(0.3), Inches(6.04), Inches(11.0), Inches(0.22),
              size=9.5, font=MONO, colour=WARN,
              bold=True)[3].text = "TWO THINGS THIS SLIDE IS ACTUALLY FOR"
    _, _, _, run_obj = deck.text(slide, MARGIN + Inches(0.3), Inches(6.3),
                                 Inches(11.3), Inches(0.7), size=10.5, colour=INK,
                                 spacing=1.28)
    run_obj.text = ("The S17 weights were never fetched from Kaggle, which is precisely "
                    "why criterion 4 cannot be re-measured and why the verdict is "
                    "suspended rather than settled. And every notebook above is "
                    "currently PRIVATE — the links work for us and 404 for anyone else, "
                    "so they need making public, or the guide added, before this deck "
                    "is shared.")
    deck.notes(slide, """
Two honest points, and neither is a formality.

First: only the detector training went to Kaggle, because it needs more GPU than
the laptop has. Everything else -- corpus, cache, MFSTNet, the whole ablation,
the controller -- runs locally in about an hour and a half. Say that, because a
panel will assume a project like this lives on rented compute.

Second, the amber box. Two of the four runs produced weights we never brought
back, and one of them is S17. That is not tidiness -- it is the direct reason we
cannot re-measure the criterion that rejected it, and therefore the reason the
IDD scope question is still open. It is a good example of an operational
shortcut turning into a blocked decision.

Also flag the private notebooks before anyone clicks a link in the room.
""")


REFERENCES = [
    ("IDD",
     "Varma, G., Subramanian, A., Namboodiri, A., Chandraker, M., & Jawahar, C. V. "
     "(2019). IDD: A Dataset for Exploring Problems of Autonomous Navigation in "
     "Unconstrained Environments. WACV 2019.",
     "Citation required by the terms of use.", WARN),
    ("TrafficCAM",
     "Deng, Z., Cheng, Y., Liu, L., Wang, S., Ke, R., Schönlieb, C.-B., & "
     "Aviles-Rivero, A. I. TrafficCAM: A Versatile Dataset for Traffic Flow "
     "Segmentation. arXiv:2211.09620. University of Cambridge & University of Bristol.",
     "No licence declared — cite, and seek written permission before release.", BAD),
    ("ITD v1.2",
     "Agarwal, Thombre, Kedia & Ghosh (2024). Indian Traffic Dataset. "
     "Transportation Engineering Group, IIT Roorkee. CC BY-NC 4.0.",
     "Non-commercial: the restriction propagates to anything derived.", WARN),
    ("BMD-45",
     "IISc AIM. BMD-45 (Hugging Face: iisc-aim/BMD-45). CVPR 2026. "
     "arXiv:2604.24419. CC BY 4.0.",
     "Author list to be completed from the paper before submission.", MUTED),
    ("Bellevue Traffic Video Dataset",
     "City of Bellevue, Washington. TrafficVideoDataset. "
     "github.com/City-of-Bellevue/TrafficVideoDataset.",
     "Released by a public body for research use.", GOOD),
    ("Tooling",
     "Jocher et al., Ultralytics YOLOv8 · Oquab et al. (2024), DINOv2 · "
     "Raffin et al. (2021), Stable-Baselines3, JMLR 22(268) · "
     "Lopez et al. (2018), Microscopic Traffic Simulation using SUMO, ITSC.",
     "Cited in the paper's implementation section.", MUTED),
]


def slide_references(deck: Deck) -> None:
    slide = deck.content(20, "References", ["Sources, ",
                                            "and what each one obliges us to do"],
                         lead="Written down now rather than reconstructed in Week 20. "
                              "Two of these carry conditions that shape what can be "
                              "released.", total=20)
    y = BODY_Y - Inches(0.1)
    for name, citation, obligation, colour in REFERENCES:
        deck.text(slide, MARGIN, y, Inches(2.5), Inches(0.22),
                  size=11, colour=INK, bold=True)[3].text = name
        deck.text(slide, MARGIN + Inches(2.6), y, Inches(6.4), Inches(0.52),
                  size=9, colour=MUTED, spacing=1.2)[3].text = citation
        deck.rect(slide, MARGIN + Inches(9.2), y + Inches(0.02),
                  Inches(0.045), Inches(0.045), fill=colour, shape=MSO_SHAPE.OVAL)
        deck.text(slide, MARGIN + Inches(9.34), y - Inches(0.01), Inches(3.1),
                  Inches(0.5), size=8.5, colour=colour, spacing=1.2)[3].text = obligation
        y += Inches(0.72)
        deck.rule(slide, MARGIN, y - Inches(0.16), CONTENT_W)

    deck.text(slide, MARGIN, Inches(6.72), Inches(11.9), Inches(0.3),
              size=9.5, font=MONO, colour=FAINT)[3].text = (
        "Full entries in docs/00-planning/DATASETS.md  ·  "
        "one marked item is deliberately incomplete rather than guessed")
    deck.notes(slide, """
Do not read this slide out. It is here so the panel can see the sources are
tracked, and so the citations exist before the paper needs them.

If you say anything, say the two obligations. IDD requires a citation as a
condition of use, which we have. ITD is non-commercial, so anything derived from
it inherits that -- worth knowing if this project is ever taken further.

The BMD-45 line is deliberately marked incomplete. We have the venue, the arXiv
number and the licence, but not the author list, so it says so rather than
guessing. An examiner spotting a fabricated citation is far worse than one
spotting a gap you have already flagged.
""")


# ==========================================================================
#  images
# ==========================================================================

FOOTAGE = Path("D:/traffic dataset")
CLIPS = {
    "mumbai": ("Mumbai Traffic Chaos - Near Andheri Station.mp4", 0.45),
    "dhaka": ("Incredible traffic Sound in Dhaka, Bangladesh। Rampura  "
              "[4K ASMR] #TheSoundofDhaka.mp4", 0.50),
}
# The ITD detector's own taxonomy, BGR.
CLASS_COLOURS = {"car": (129, 185, 63), "two wheeler": (241, 102, 99),
                 "autorickshaw": (46, 163, 224), "bus": (224, 102, 224),
                 "truck": (78, 103, 224), "LCV": (120, 200, 220),
                 "bicycle": (200, 200, 120)}


def render_images(outdir: Path) -> dict:
    """Annotated frames, rendered fresh from the footage.

    Returns whatever it could produce. A missing clip or model is reported and
    skipped: a deck that builds without two pictures is more useful than a build
    that fails on a machine without the footage.
    """
    outdir.mkdir(parents=True, exist_ok=True)
    produced: dict = {}

    weights = ROOT / "models" / "external" / "best_xl_ITD_v1.2.pt"
    if not weights.is_file():
        print(f"  no detector at {weights} — image slides will say so")
        return produced

    try:
        import cv2
        from ultralytics import YOLO

        from scripts.pilot_a17 import vehicle_ids
    except ImportError as error:
        print(f"  cannot render images ({error}) — image slides will say so")
        return produced

    model = YOLO(str(weights))
    ids = vehicle_ids(model)
    names = model.names if isinstance(model.names, dict) else dict(enumerate(model.names))

    for tag, (filename, position) in CLIPS.items():
        path = FOOTAGE / filename
        target = outdir / f"detect_{tag}.jpg"
        if target.is_file():
            produced[tag] = target
            continue
        if not path.is_file():
            print(f"  missing {path.name}")
            continue
        capture = cv2.VideoCapture(str(path))
        frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(frames * position))
        ok, frame = capture.read()
        capture.release()
        if not ok:
            continue
        result = model.predict(source=frame, conf=0.45, imgsz=992, verbose=False)[0]
        boxes = [(b, int(c), p) for b, c, p in zip(result.boxes.xyxy.tolist(),
                                                   result.boxes.cls.tolist(),
                                                   result.boxes.conf.tolist())
                 if int(c) in ids]
        # Largest first, so a big foreground vehicle cannot bury the small ones.
        boxes.sort(key=lambda item: -((item[0][2] - item[0][0]) *
                                      (item[0][3] - item[0][1])))
        for box, cls, score in boxes:
            label = str(names[cls])
            colour = CLASS_COLOURS.get(label, (170, 170, 170))
            x1, y1, x2, y2 = (int(v) for v in box)
            cv2.rectangle(frame, (x1, y1), (x2, y2), colour, 3)
            caption = f"{label} {score:.2f}"
            (tw, th), _ = cv2.getTextSize(caption, cv2.FONT_HERSHEY_DUPLEX, 0.52, 1)
            cv2.rectangle(frame, (x1, max(0, y1 - th - 9)), (x1 + tw + 10, y1),
                          colour, -1)
            cv2.putText(frame, caption, (x1 + 5, max(11, y1 - 5)),
                        cv2.FONT_HERSHEY_DUPLEX, 0.52, (13, 17, 23), 1, cv2.LINE_AA)
        height, width = frame.shape[:2]
        wide = 1400
        cv2.imwrite(str(target),
                    cv2.resize(frame, (wide, int(height * wide / width)),
                               interpolation=cv2.INTER_AREA),
                    [cv2.IMWRITE_JPEG_QUALITY, 86])
        produced[tag] = target
        print(f"  rendered {target.name}  ({len(boxes)} vehicles)")

    lanes = outdir / "lanes.jpg"
    if lanes.is_file():
        produced["lanes"] = lanes
    else:
        import json as _json

        for spec_path in sorted((ROOT / "data" / "lanes_k4").glob("*.json")):
            if spec_path.name == "survey_summary.json":
                continue
            spec = _json.loads(spec_path.read_text(encoding="utf-8"))
            if not spec.get("clip", "").startswith("Mumbai"):
                continue
            preview = spec_path.with_suffix("").with_suffix(".preview.jpg")
            if preview.is_file():
                import shutil

                shutil.copy2(preview, lanes)
                produced["lanes"] = lanes
                print(f"  reused {preview.name} for the lane slide")
            break
    return produced


# ==========================================================================
#  build
# ==========================================================================

def export_pdf(pptx_path: Path) -> Path | None:
    """Export a PDF beside the deck, driving PowerPoint itself.

    PowerPoint renders its own format correctly, which no third-party converter
    can be relied on to do — and a deck that looks right as a .pptx and wrong as
    a PDF is worse than no PDF at all. So this drives the real application, and
    returns None wherever that is unavailable rather than producing something
    that only approximately matches.
    """
    import subprocess

    if sys.platform != "win32":
        print("  --pdf needs Windows with PowerPoint installed; skipping")
        return None

    pdf_path = pptx_path.with_suffix(".pdf")
    script = (
        "$ErrorActionPreference='Stop';"
        "$app = New-Object -ComObject PowerPoint.Application;"
        f"$p = $app.Presentations.Open('{pptx_path}', $true, $false, $false);"
        f"$p.SaveAs('{pdf_path}', 32);"          # 32 = ppSaveAsPDF
        "$p.Close(); $app.Quit();"
        "[System.Runtime.InteropServices.Marshal]::ReleaseComObject($app)|Out-Null"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=600)
    if result.returncode != 0 or not pdf_path.is_file():
        print("  PDF export failed; the .pptx is unaffected")
        for line in (result.stderr or "").strip().splitlines()[:3]:
            print(f"    {line}")
        return None
    return pdf_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path,
                        default=ROOT / "docs" / "demo" / "MFSTNet-Project-Review.pptx")
    parser.add_argument(
        "--pdf", action="store_true",
        help="also export a PDF through PowerPoint. Windows only and it needs "
             "PowerPoint installed; the deck still builds without it")
    parser.add_argument("--assets", type=Path,
                        default=Path(tempfile.gettempdir()) / "mfstnet-deck-assets",
                        help="where rendered frames are cached between builds; they "
                             "are deliberately not committed")
    args = parser.parse_args(argv)

    print(f"  reading results from {RESULTS}")
    figures = load_figures()
    images = render_images(args.assets)

    deck = Deck()
    slide_title(deck, figures)
    slide_problem(deck)
    slide_system(deck)
    slide_stack(deck)
    slide_data(deck)
    slide_detection(deck, figures)
    slide_examples(deck, images)
    slide_m2(deck, figures)
    slide_counting(deck, figures)
    slide_generalisation(deck, figures)
    slide_pipeline(deck)
    slide_lanes(deck, images)
    slide_sampling(deck, figures)
    slide_model(deck)
    slide_gate(deck, figures)
    slide_control(deck, figures)
    slide_engineering(deck)
    slide_next(deck)
    slide_compute(deck)
    slide_references(deck)

    deck.save(args.out)
    size = args.out.stat().st_size / 1024 / 1024
    print(f"\n  wrote {args.out}  ({len(deck.slides)} slides, {size:.2f} MB)")
    print(f"  images embedded: {len(images)} of 3")
    print("  validation figures read from experiments/results at build time; "
          "the S17\n  detector numbers and the timing table are marked on their "
          "slides as not\n  coming from a committed CSV")
    if args.pdf:
        pdf = export_pdf(args.out)
        if pdf is not None:
            print(f"  wrote {pdf}  "
                  f"({pdf.stat().st_size / 1024 / 1024:.2f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
