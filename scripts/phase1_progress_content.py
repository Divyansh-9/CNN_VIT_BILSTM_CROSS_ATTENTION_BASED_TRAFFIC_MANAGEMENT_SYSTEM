"""Content for the **Phase-I Progress Report – 1**.

A third deliverable, not a mode of the other two. The Department's
*Guidelines for Major Project Phase-I Progress Report – 1* prescribe five
sections and no others — Introduction, Literature Survey, Literature Survey
Table, Research Gap, References — with the Introduction broken into nine named
parts and the table carrying **25 to 30 papers**. There is no methodology
chapter, no requirements chapter, and no results chapter, so this report says
what the project is for and what the literature already settles, and stops.

Two rules make it structurally impossible to overstate:

**No measured result can reach it.** Like `synopsis_phase1_content`, this module
never imports `synopsis_content.load_facts()`, and `build_synopsis.py` does not
load the facts for this document. A number produced by a run cannot appear here
by accident.

**No unverified citation can reach it.** Every reference is read from
`data/references.json`, which `scripts/verify_references.py` fills from OpenAlex
and arXiv and refuses to fill from memory. That exists because
`docs/00-planning/BIBLIOGRAPHY.md` marks most of its own entries ⚠️ "named from
general knowledge, not retrieved", and states the rule: nothing ⚠️ enters a
reference list. A 30-row comparative table is where that rule would otherwise
break first.

A third rule is a matter of care rather than structure, and belongs here as an
instruction to whoever edits next. **The verified record covers bibliographic
identity — title, authors, year, venue, DOI — not full text.** So the
`Key findings` and `Limitations` cells below describe each work's *method and
the assumption it makes*, which is what this project's own
`docs/00-planning/RELATED-WORK.md` establishes and can defend. Numeric findings
appear only where `BIBLIOGRAPHY.md` marks the figure ✅ verified. Do not add a
number to this table because it sounds right.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from scripts.synopsis_content import (AUTHORS, BRANCH, DEGREE, DEPARTMENT,
                                      INSTITUTE, MENTOR_DESIGNATION,
                                      MENTOR_NAME, PLACE, ROOT,
                                      SPECIALISATION, TEAM, TEAM_ID, TITLE,
                                      TITLE_SHORT, Member)

__all__ = [
    "AUTHORS", "BRANCH", "DEGREE", "DEPARTMENT", "INSTITUTE",
    "MENTOR_DESIGNATION", "MENTOR_NAME", "PLACE", "SPECIALISATION", "TEAM",
    "TEAM_ID", "TITLE", "TITLE_SHORT", "Member",
    "SUBTITLE", "SUBMISSION_MONTH", "WORKING_NAME", "TOC_ENTRIES",
    "BACKGROUND", "PROBLEM_STATEMENT", "MOTIVATION", "EXISTING_SCENARIO",
    "EXISTING_LIMITS", "NEED", "OBJECTIVES", "OBJECTIVE_LABELS",
    "IN_SCOPE", "IN_SCOPE_LABELS", "OUT_OF_SCOPE", "OUT_OF_SCOPE_LABELS",
    "APPROACH_STAGES", "APPROACH_CLOSING", "EXPECTED_OUTCOME",
    "SURVEY_SECTIONS", "SURVEY_TABLE", "SURVEY_TABLE_SLIDE", "THEME_LABELS",
    "TABLE_MIN", "TABLE_MAX",
    "GAP_WHAT_IS_DONE", "GAP_LIMITS",
    "GAP_UNRESOLVED", "GAP_UNADDRESSED", "GAP_HOW_WE_ADDRESS", "GAP_CLOSING",
    "REFERENCES_PATH", "EXTRA_REFERENCES", "WORKS", "Work",
    "cite", "render", "cited_keys", "reference_list",
]

SUBTITLE = "Phase-I  —  Progress Report – 1"

#: The month this report is prepared, not the month the project began. The
#: synopsis carries its own month for the same reason: the two documents are
#: submitted at different points and dating them identically would be false.
SUBMISSION_MONTH = "October-2026"

#: The name the idea was registered under before the model had one, carried
#: through every document so §1's consistency rule has one spelling to check.
WORKING_NAME = "cnn-vit-bilstm-cross-attention-traffic-system"

#: The five sections the guideline prescribes, in its order. Nothing is added:
#: a progress report that silently grows a methodology chapter is answering a
#: different brief.
TOC_ENTRIES: list[tuple[str, str, str]] = [
    ("1", "Introduction", "intro"),
    ("2", "Literature Survey", "survey"),
    ("3", "Literature Survey Table", "table"),
    ("4", "Research Gap", "gap"),
    ("", "References", "refs"),
]


# ==========================================================================
#  references, read from the verified record
# ==========================================================================

REFERENCES_PATH = ROOT / "data" / "references.json"


@dataclass(frozen=True)
class Work:
    key: str
    theme: str
    title: str
    authors: tuple[str, ...]
    year: int
    venue: str | None
    doi: str | None
    arxiv: str | None
    verified_against: str

    @property
    def first_author(self) -> str:
        """Family name of the first author, for an `[n]`-style narrative cue.

        OpenAlex is inconsistent about name order — it returns
        `"Dai, Zihang"` for one record and `"Hanxiao Liu"` for the next — so the
        comma form is detected rather than assumed away. Guessing wrong puts a
        given name where a reader expects a surname, in a document whose whole
        point is that its citations were checked.
        """
        if not self.authors:
            return "Anon."
        name = self.authors[0]
        if "," in name:
            return name.split(",")[0].strip()
        return name.split()[-1]

    @property
    def narrative(self) -> str:
        """`Peng et al. (2021)` — how the work is named in running prose."""
        suffix = " et al." if len(self.authors) > 1 else ""
        return f"{self.first_author}{suffix} ({self.year})"

    @property
    def authors_ieee(self) -> str:
        """`A. Vaswani et al.` — IEEE abbreviates past three authors."""
        shown = [_initialise(name) for name in self.authors[:3]]
        if len(self.authors) > 3:
            return shown[0] + " et al."
        if len(shown) == 1:
            return shown[0]
        return ", ".join(shown[:-1]) + ", and " + shown[-1]

    @property
    def locator(self) -> str:
        if self.doi:
            return f"doi: {self.doi}"
        if self.arxiv:
            return f"arXiv:{self.arxiv}"
        return ""

    @property
    def venue_clean(self) -> str:
        """The venue with OpenAlex's duplicated halves collapsed.

        OpenAlex returns some venues as the same name written twice either side
        of a dash — "IEEE Computer Society Conference on Computer Vision and
        Pattern Recognition/Proceedings - IEEE Computer Society Conference on
        Computer Vision and Pattern Recognition/Proceedings". That is one venue
        stated twice, and collapsing it discards nothing.

        Only exactly-repeated dash-separated segments are collapsed. A first
        version also split on "/" and kept the first surviving segment, which
        turned "IEEE/CVF International Conference on Computer Vision (ICCV)"
        into "IEEE" — a slash is part of that venue's real name. Nothing is
        abbreviated and nothing is substituted: inventing a short form would be
        asserting a venue name that no record states.
        """
        venue = self.venue or "preprint"
        parts = [part.strip() for part in venue.split(" - ") if part.strip()]
        seen: list[str] = []
        for part in parts:
            if part.casefold() not in {other.casefold() for other in seen}:
                seen.append(part)
        return " - ".join(seen) if seen else venue

    @property
    def ieee(self) -> str:
        parts = [self.authors_ieee, f'"{self.title},"',
                 f"{self.venue_clean}, {self.year}."]
        if self.locator:
            parts.append(self.locator + ".")
        return " ".join(parts)


def _initialise(name: str) -> str:
    """`Yaguang Li` and `Dai, Zihang` both become `Z. Dai` form."""
    if "," in name:
        family, _, given = name.partition(",")
        given_parts = given.split()
    else:
        parts = name.split()
        family, given_parts = parts[-1], parts[:-1]
    initials = " ".join(f"{p[0]}." for p in given_parts if p and p[0].isalpha())
    return f"{initials} {family.strip()}".strip()


def _load_works() -> dict[str, Work]:
    payload = json.loads(REFERENCES_PATH.read_text(encoding="utf-8"))
    works: dict[str, Work] = {}
    for row in payload["works"]:
        works[row["key"]] = Work(
            key=row["key"], theme=row["theme"], title=row["title"],
            authors=tuple(row["authors"]), year=row["year"],
            venue=row["venue"], doi=row["doi"], arxiv=row.get("arxiv"),
            verified_against=row["verified_against"])
    return works


WORKS: dict[str, Work] = _load_works()

#: Works that are standards, manuals or software rather than indexed papers, so
#: no bibliographic API holds a record of them. They are cited in the narrative
#: and listed in References, and deliberately **not** placed in the comparative
#: table, which the guideline asks to be research papers and prior projects.
EXTRA_REFERENCES: tuple[tuple[str, str], ...] = (
    ("webster1958",
     'F. V. Webster, "Traffic signal settings," Road Research Technical Paper '
     "No. 39, Road Research Laboratory, London, U.K., 1958."),
    ("irc1994",
     "Indian Roads Congress, IRC:SP:41-1994, Guidelines for the Design of "
     "At-Grade Intersections in Rural and Urban Areas. New Delhi, India: "
     "IRC, 1994."),
    ("indohcm2017",
     "Indo-HCM, Indian Highway Capacity Manual. New Delhi, India: "
     "CSIR-Central Road Research Institute, 2017."),
    ("yolov8",
     'G. Jocher, A. Chaurasia, and J. Qiu, "Ultralytics YOLOv8," 2023. '
     "[Online]. Available: https://github.com/ultralytics/ultralytics"),
    ("sutton2018",
     "R. S. Sutton and A. G. Barto, Reinforcement Learning: An Introduction, "
     "2nd ed. Cambridge, MA, USA: MIT Press, 2018."),
)


def _reference_order() -> list[str]:
    """Citation keys in the order they are numbered in References.

    Theme order, then year, then key. A reference list ordered by first
    appearance would renumber every entry whenever a sentence moves, and the
    comparative table is generated from the same order, so a stable order is
    what keeps the table's row numbers and the reference numbers aligned.
    """
    theme_order = [theme for theme, _title, _lead in SURVEY_SECTIONS]
    ordered = sorted(
        WORKS.values(),
        key=lambda work: (theme_order.index(work.theme), work.year, work.key))
    return [work.key for work in ordered] + [key for key, _ in EXTRA_REFERENCES]


def cite(*keys: str) -> str:
    """`[4]`, `[4], [7]` — the bracketed number a sentence carries.

    Raises on an unknown key. A citation that silently renders as `[?]` is the
    defect this whole arrangement exists to prevent, so it fails the build
    instead.
    """
    order = _reference_order()
    numbers = []
    for key in keys:
        if key not in order:
            raise KeyError(
                f"cited key {key!r} is in no reference list. Add it to "
                f"scripts/verify_references.py and re-run that script, or to "
                f"EXTRA_REFERENCES if no bibliographic API indexes it.")
        numbers.append(order.index(key) + 1)
    return ", ".join(f"[{n}]" for n in sorted(numbers))


def reference_list() -> list[tuple[int, str]]:
    """The numbered References section, in `_reference_order()`."""
    extras = dict(EXTRA_REFERENCES)
    out: list[tuple[int, str]] = []
    for index, key in enumerate(_reference_order(), start=1):
        out.append((index, WORKS[key].ieee if key in WORKS else extras[key]))
    return out


_CITE_RE = re.compile(r"\{([a-z0-9]+)\}")


def render(text: str) -> str:
    """Replace every `{key}` in prose with its bracketed reference number.

    Narrative prose names a work by key rather than by number so that the
    numbering stays a property of the reference list. An unknown key raises
    through `cite()`, which is the point: the alternative is a document that
    ships with a citation pointing at nothing.
    """
    return _CITE_RE.sub(lambda match: cite(match.group(1)), text)


def cited_keys() -> set[str]:
    """Every key the narrative actually cites.

    Used by `scripts/check_progress_report.py` to enforce the guideline's
    requirement in both directions: every paper in the comparative table
    appears in References, and every reference is cited somewhere in the text.
    An uncited reference is padding, and a checker that only looks one way
    cannot tell.
    """
    found: set[str] = set()
    for block in _NARRATIVE_BLOCKS():
        found.update(_CITE_RE.findall(block))
    found.update(key for key, *_ in SURVEY_TABLE)
    return found


# ==========================================================================
#  Section 1 — Introduction
# ==========================================================================

#: 1.1 Background. Written to establish the domain for a reader who does not
#: already hold it, which is what the guideline's "sufficient background and
#: context" asks for, and kept specific to signalised urban intersections in
#: India rather than to traffic in general.
BACKGROUND: tuple[str, ...] = (
    "Urban road traffic in India is governed at its intersections. A "
    "signalised junction decides, several times a minute, which approach is "
    "allowed to discharge and for how long, and that decision determines the "
    "delay experienced by every vehicle upstream of it. The great majority of "
    "signalised junctions in Indian cities run a fixed-time plan: the cycle "
    "length and the green split are computed once from a manual turning-"
    "movement count, encoded into the controller, and then held for months or "
    "years. The method behind those plans is Webster's, published in 1958, "
    "and it remains the practical basis of signal timing in Indian design "
    "practice.",

    "A fixed-time plan is correct on average and wrong most of the time. "
    "Demand at an urban junction varies across the day, across the week and "
    "with weather, events and incidents, while the plan does not. The visible "
    "consequence is green time held on an empty approach while a saturated "
    "approach waits, and it is not a failure of the arithmetic — it is the "
    "cost of a plan that cannot see the junction it is controlling.",

    "The traffic the plan must serve is also not the traffic the method "
    "assumes. Indian urban streams are heterogeneous and non-lane-"
    "disciplined. A single approach carries two-wheelers, auto-rickshaws, "
    "e-rickshaws, cars, light commercial vehicles, buses, trucks and, on many "
    "roads, pedestrians and animals in the carriageway. These modes occupy "
    "different road space and discharge at different rates, and they do not "
    "queue in the lanes that are painted on the road. Indian practice already "
    "recognises this: the Indian Highway Capacity Manual publishes "
    "passenger-car-unit equivalences precisely because counting vehicles is "
    "not the same as measuring how much road is occupied.",

    "What has changed, and what makes this project possible, is sensing. "
    "Surveillance cameras are already installed at a large and growing number "
    "of Indian junctions for enforcement and monitoring. They are a sensor "
    "the signal does not currently use. Inductive loops, radar and magnetic "
    "probes — the instrumentation that the mainstream traffic-forecasting "
    "literature assumes — require trenching, calibration and maintenance "
    "budgets that most of these junctions do not have. A camera that is "
    "already mounted, already powered and already pointed at the stop line is "
    "the one sensor that can be used without installing anything.",
)

#: 1.2 Problem statement. One paragraph, stated so that it is falsifiable: it
#: names the input, the output, the horizon and the deployment constraint.
PROBLEM_STATEMENT: tuple[str, ...] = (
    "Given only the video stream of a single fixed camera already installed at "
    "a signalised urban intersection, predict the congestion level of each "
    "approach lane sixty seconds into the future, accurately enough for a "
    "signal controller to act on the prediction rather than on a measurement "
    "of the present — and do so under heterogeneous, non-lane-disciplined "
    "traffic, on hardware a municipal body could afford, without transmitting "
    "or storing a single raw video frame.",

    "Each clause of that statement is a constraint rather than a preference. "
    "A single camera, because a method that needs several cameras per junction "
    "cannot be deployed at the junctions this targets. Per-lane output, "
    "because a controller allocates green to an approach and a scene-level "
    "congestion score gives it nothing to act on. Sixty seconds, because a "
    "signal decision takes effect over the next phase and a forecast of the "
    "present is a measurement, not a forecast. No raw frames leaving the "
    "device, because a system that moves footage of a public road off the "
    "camera is a surveillance system regardless of what it is used for.",
)

#: 1.3 Motivation.
MOTIVATION: tuple[str, ...] = (
    "The cost of the current arrangement is paid in delay, fuel and emissions "
    "at every junction, every day, and it is paid most heavily by the modes "
    "that are least able to absorb it. A two-wheeler or an auto-rickshaw "
    "waiting out a green phase allocated to an empty approach is not an "
    "abstraction; it is the ordinary experience of an Indian commute.",

    "The reason this has not already been solved is not that adaptive control "
    "is unknown. It is that adaptive control has been built for a road "
    "environment that is instrumented, lane-disciplined and homogeneous, and "
    "the published methods inherit those assumptions through their inputs. A "
    "controller that expects loop-detector occupancy cannot be installed where "
    "there are no loops. A forecaster trained on lane-disciplined motorway "
    "flow does not transfer to a junction where vehicles straddle the "
    "markings. The gap is not in the control theory; it is between the sensing "
    "the methods assume and the sensing that exists.",

    "The second motivation is methodological, and it is why this is a research "
    "project and not an integration exercise. The architecture this project "
    "proposes fuses a convolutional and a transformer view of the same frame "
    "through a learned gate. Whether that gate learns anything interpretable — "
    "whether it shifts toward one branch as the scene becomes dense — is a "
    "question that can be answered with evidence, and answering it is worth "
    "more than another percentage point on a benchmark.",
)

#: 1.4 Existing scenario, as prose, followed by its limitations as a list so
#: the limitation is attached to the approach rather than left implied.
EXISTING_SCENARIO: tuple[str, ...] = (
    "Four approaches are in use or in the literature, and each addresses part "
    "of the problem.",

    "Fixed-time control, computed by Webster's method from a periodic manual "
    "count, is the deployed baseline at the junctions this project targets. "
    "Vehicle-actuated control, where a detector extends a green phase while "
    "vehicles are still arriving, is deployed where detectors exist. "
    "Sensor-based forecasting — the spatio-temporal graph literature — "
    "predicts flow or speed across a road network from loop-detector and probe "
    "time series. Vision-based congestion estimation classifies congestion "
    "directly from camera imagery, and is an active field rather than an "
    "opening.",
)

EXISTING_LIMITS: tuple[tuple[str, str], ...] = (
    ("Fixed-time control",
     "The plan cannot respond to the demand it is serving. Re-timing requires "
     "a fresh manual survey, so plans age; and the method's saturation-flow "
     "parameter is itself uncertain under heterogeneous traffic, where "
     "published values for a single intersection differ by a factor of two "
     "depending only on which passenger-car-unit convention is used."),

    ("Vehicle-actuated control",
     "It requires the detector infrastructure that is absent at the target "
     "junctions, and it reacts to arrivals that have already happened rather "
     "than anticipating the next phase."),

    ("Sensor-based graph forecasting",
     "It is accurate and well developed, and it assumes an instrumented "
     "network with a known road graph. Its inputs do not exist at an "
     "un-instrumented Indian junction, so its accuracy is not available there "
     "at any price."),

    ("Vision-based congestion estimation",
     "It uses the sensor that does exist, and most published work classifies "
     "the scene as a whole, estimates present conditions rather than "
     "forecasting, and is evaluated on lane-disciplined traffic. None of those "
     "three gives a signal controller a per-lane forecast it can act on."),

    ("Reinforcement-learning signal control",
     "It is a mature and heavily benchmarked literature, and its state vectors "
     "are built from instantaneous measurements. Whether an anticipatory input "
     "helps a controller, and how good that anticipation must be before it "
     "helps, is largely untested."),
)

#: 1.5 Need for the proposed work.
NEED: tuple[str, ...] = (
    "The four approaches above do not compose into a solution, because the "
    "accurate ones need sensors that are absent and the deployable one does "
    "not produce what a controller needs. What is missing is a method that "
    "takes the sensor that is already installed and produces the quantity a "
    "controller can act on: a per-lane congestion level, one phase ahead, "
    "under traffic that does not respect lanes.",

    "That is the gap this project is built for, and the engineering it implies "
    "is specific. Congestion must be defined on occupancy weighted by "
    "passenger-car units rather than on a raw vehicle count, because a count "
    "that treats a bus and a two-wheeler alike measures the wrong thing. The "
    "thresholds separating congestion levels must be calibrated per camera, "
    "because a threshold that is correct for one viewpoint is arbitrary at "
    "another. Evaluation must hold out whole cameras rather than shuffling "
    "windows, because a model that has seen a camera in training will report "
    "recognition as generalisation. And the detector the pipeline depends on "
    "must be fine-tuned for the vehicle classes Indian streams actually "
    "contain, because an off-the-shelf detector has never been trained to see "
    "an auto-rickshaw.",
)

#: 1.6 Objectives, numbered. These are the objectives of the project, stated as
#: things that will be built or established rather than as aspirations.
OBJECTIVES: tuple[tuple[str, str], ...] = (
    ("Assemble a fixed-camera corpus of heterogeneous traffic with per-lane "
     "congestion labels",
     "Curate footage from permissively-licensed public sources, place lane "
     "regions by hand for each camera, derive per-lane passenger-car-unit "
     "weighted occupancy from detector counts, and label each lane's "
     "congestion level sixty seconds ahead. Splits are cut by source camera "
     "so that no camera appears in both training and test."),

    ("Fine-tune a vehicle detector for the classes Indian streams contain",
     "Train a single-stage detector on an eight-class Indian taxonomy "
     "including auto-rickshaw and e-rickshaw, and report per-class accuracy "
     "with support counts rather than a single averaged figure."),

    ("Design and train a multimodal spatio-temporal forecaster",
     "Combine a convolutional and a self-supervised transformer view of each "
     "frame through bidirectional cross-attention and a learned gate, model "
     "the sequence with a bidirectional recurrent encoder, and predict a "
     "congestion class per lane at a sixty-second horizon."),

    ("Establish whether each component earns its place",
     "Run an ablation in which every module can be disabled by configuration "
     "alone, including a linear-probe floor, and compare against count-based "
     "forecasters that consume only detector counts. Report the comparison "
     "whichever way it goes."),

    ("Couple the forecast to a signal controller and measure the coupling",
     "Train a reinforcement-learning controller on a simulated heterogeneous "
     "intersection with the forecast as part of its state, and measure "
     "against the best configuration of the fixed-time baseline rather than "
     "an arbitrary one."),

    ("Keep the whole pipeline reproducible and privacy-preserving",
     "Fix seeds across every library, commit raw per-run results rather than "
     "summary tables, generate every reported table from those results by a "
     "committed script, and ensure no raw video frame is ever written to disk "
     "or transmitted."),
)

#: The same six objectives in the few words a slide row has space for. Kept
#: here rather than in the deck so the report and the deck cannot name a
#: different six, and ordered identically so `O3` means the same thing in both.
OBJECTIVE_LABELS: tuple[str, ...] = (
    "Build the labelled fixed-camera corpus",
    "Fine-tune a detector for Indian classes",
    "Train the multimodal forecaster",
    "Show whether each component earns its place",
    "Couple the forecast to a controller",
    "Keep it reproducible and privacy-preserving",
)

if len(OBJECTIVE_LABELS) != len(OBJECTIVES):
    raise AssertionError(
        f"{len(OBJECTIVE_LABELS)} short labels for {len(OBJECTIVES)} "
        "objectives; the deck and the report would disagree about how many "
        "there are.")


IN_SCOPE: tuple[str, ...] = (
    "Per-lane congestion forecasting at a sixty-second horizon from a single "
    "fixed camera, for a four-approach signalised intersection.",
    "A curated fixed-camera corpus of heterogeneous traffic, with per-lane "
    "labels derived from passenger-car-unit weighted occupancy.",
    "A vehicle detector fine-tuned for an eight-class Indian taxonomy.",
    "An ablation over the architecture, and a comparison against count-based "
    "forecasters that use no appearance information at all.",
    "A reinforcement-learning signal controller evaluated in simulation, with "
    "the forecast as an input to its state.",
    "An edge-to-server prototype in which only derived counts and predictions "
    "cross the network.",
)

OUT_OF_SCOPE: tuple[str, ...] = (
    "Field deployment on a live signal. Nothing in this project actuates a "
    "real traffic light, and no wait-time reduction is claimed for the real "
    "world.",
    "Multi-intersection coordination. The controller is single-junction; "
    "network-level cooperation is established work and is not attempted.",
    "Vehicle re-identification, tracking across cameras, number-plate "
    "recognition, or any identification of individuals or vehicles.",
    "Trajectory prediction for individual vehicles. The output is a per-lane "
    "congestion class, not a path.",
    "A production data platform. Storage is a single embedded database and the "
    "dashboard is a diagnostic surface, not an operations product.",
)

#: The scope lists in the few words a slide panel row has space for, paired one
#: to one with the full statements above. Kept here for the same reason as
#: `OBJECTIVE_LABELS`: the report and the deck must not describe a different
#: scope, and `panel_height` refuses a row that wraps, so the short form has to
#: exist somewhere. Here is where the wording belongs.
IN_SCOPE_LABELS: tuple[str, ...] = (
    "Per-lane congestion forecast, 60 s ahead, one fixed camera",
    "A curated fixed-camera corpus of heterogeneous traffic",
    "A detector fine-tuned for eight Indian vehicle classes",
    "An ablation, and count-only baselines to beat",
    "An RL signal controller, evaluated in simulation",
    "An edge-to-server prototype that moves no raw frame",
)

OUT_OF_SCOPE_LABELS: tuple[str, ...] = (
    "Field deployment on a live signal",
    "Multi-intersection coordination",
    "Re-identification, tracking, number-plate recognition",
    "Trajectory prediction for individual vehicles",
    "A production data platform",
)

for _name, _labels, _full in (("IN_SCOPE", IN_SCOPE_LABELS, IN_SCOPE),
                              ("OUT_OF_SCOPE", OUT_OF_SCOPE_LABELS,
                               OUT_OF_SCOPE)):
    if len(_labels) != len(_full):
        raise AssertionError(
            f"{len(_labels)} short labels for {len(_full)} {_name} entries; "
            "the deck and the report would state a different scope.")


#: 1.8 Proposed approach — the stages, each with what it produces. Brief by
#: design: the guideline asks for "a brief overview of the methodology", and
#: the detailed design belongs to the documents that follow this one.
APPROACH_STAGES: tuple[tuple[str, str], ...] = (
    ("Stage 1 — Corpus",
     "Triage candidate footage, place per-camera lane regions by hand, detect "
     "and count vehicles per lane per step, convert counts to "
     "passenger-car-unit weighted occupancy, and label each lane's congestion "
     "level at the forecast horizon. Thresholds are calibrated per camera at "
     "the 33rd and 67th percentiles of that camera's own occupancy "
     "distribution."),

    ("Stage 2 — Detection",
     "Fine-tune a single-stage detector on an eight-class Indian taxonomy, "
     "bootstrapping from a public Indian dataset so that corpus construction "
     "is not blocked on collecting new footage."),

    ("Stage 3 — Representation",
     "Extract two views of each frame with frozen backbones — one "
     "convolutional, one self-supervised transformer — and cache the features, "
     "so that an ablation over the layers above them does not re-run the "
     "backbones."),

    ("Stage 4 — Fusion",
     "Let each view attend to the other in both directions, and combine the "
     "two results with a learned gate whose value is logged and analysed "
     "rather than hidden inside the network."),

    ("Stage 5 — Temporal model and head",
     "Encode the fused sequence with a bidirectional recurrent network and "
     "temporal self-attention, pool by attention rather than by taking the "
     "last state, and pool per-lane regions separately so the four lanes can "
     "receive four different predictions."),

    ("Stage 6 — Control",
     "Train a policy-gradient controller on a simulated heterogeneous "
     "four-way intersection whose state includes the per-lane forecast, and "
     "compare it against the best-tuned fixed-time plan."),

    ("Stage 7 — Prototype",
     "Run detection on an edge device, publish only derived counts over a "
     "message broker to a server that holds the forecaster and the "
     "controller, and fall back to a locally-embedded fixed-time plan if the "
     "link drops."),
)

APPROACH_CLOSING: tuple[str, ...] = (
    "The order is a constraint and not a convenience. A standard "
    "cross-attention model is brought to convergence before the gate replaces "
    "it, and the gate before temporal attention is added, because the known "
    "failure mode of a project shaped like this one is an elaborate "
    "architecture with no experiments behind it. Every module is therefore "
    "disableable by configuration alone, which is what makes the ablation "
    "possible without editing code between runs.",
)

#: 1.9 Expected outcome. Stated as what will exist and what will be known —
#: never as a number, because this report is written before the measurements.
EXPECTED_OUTCOME: tuple[tuple[str, str], ...] = (
    ("A labelled fixed-camera corpus",
     "Per-lane congestion labels at a sixty-second horizon, with the "
     "threshold calibration recorded per camera and splits cut so that no "
     "camera is shared between training and test."),

    ("A detector tuned for Indian vehicle classes",
     "Per-class accuracy reported with support counts, so that a strong "
     "average over common classes cannot hide a failure on the rare ones the "
     "taxonomy exists to add."),

    ("An answer on whether visual fusion earns its cost",
     "The ablation and the count-only baselines answer this directly. A "
     "finding that appearance does not beat counts in this regime is a "
     "reportable result and will be reported as one."),

    ("Evidence about what the gate learns",
     "The gate value is logged and analysed against scene density. A gate "
     "that collapses or tracks nothing is an informative negative result."),

    ("A controller result with its uncertainty",
     "The control comparison is reported as a mean with a bootstrap "
     "confidence interval over repeated seeds against the best-tuned "
     "fixed-time baseline, with a paired test and an effect size, rather than "
     "as a single headline figure."),

    ("A reproducible package",
     "Fixed seeds, committed raw per-run results, and every reported table "
     "generated from those results by a committed script."),
)


# ==========================================================================
#  Section 2 — Literature Survey
# ==========================================================================
#
# One subsection per theme in `data/references.json`, in the order a reader
# needs them: the task first, then the paradigm this project departs from, then
# the mechanisms it assembles, then the control literature, then the data.
# `cite()` resolves the numbers, so a sentence can never cite a reference that
# is not in the list.

SURVEY_SECTIONS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("vision-congestion", "Congestion estimation from camera imagery", (
        "The task-level prior art is a camera and a congestion label, and it "
        "is an active field rather than an opening. Chakraborty et al. "
        "{chakraborty2018} classify congestion directly from traffic-camera "
        "still images with deep convolutional networks, establishing that the "
        "signal is present in a single frame from a fixed viewpoint. Kumar and "
        "Raubal {kumar2021} survey the use of deep learning across congestion "
        "detection, prediction and alleviation; the survey's existence is "
        "itself the finding that matters here, because it means a project "
        "claiming camera-based congestion estimation as novel would be "
        "claiming something the field settled years ago.",

        "The closest work at the task level is Feng et al. {feng2024}, which "
        "assembles detection, tracking and prediction into one end-to-end "
        "pipeline driven by fixed low-resolution surveillance cameras. It "
        "shows the pipeline is buildable from the sensor this project assumes. "
        "What it does not do — and what none of this strand does — is produce "
        "a per-lane forecast under non-lane-disciplined traffic and hand it to "
        "a controller. The scene-level output and the lane-disciplined "
        "evaluation setting are where the opening is.",
    )),

    ("graph-forecasting", "Spatio-temporal forecasting from sensor networks", (
        "The dominant traffic-forecasting paradigm treats the road network as "
        "a graph and the sensors on it as a multivariate time series. Yu et "
        "al. {yu2018} apply graph convolution jointly over the spatial graph "
        "and the temporal axis; Li et al. {li2018} model propagation as a "
        "diffusion process on a directed graph with a recurrent sequence-to-"
        "sequence decoder; Wu et al. {wu2019} learn the adjacency matrix "
        "rather than taking it from the road geometry, removing the need for "
        "a correct hand-built graph; and Guo et al. {guo2019} add attention "
        "over both axes so the model can weight periods and locations "
        "differently.",

        "This strand is mature, well benchmarked, and consistently strong on "
        "its own datasets. Its relevance here is in what it assumes rather "
        "than what it achieves. Every method above consumes loop-detector or "
        "probe-vehicle readings from an instrumented network whose topology is "
        "known. At an Indian junction with a camera and no loops, those inputs "
        "do not exist, so the accuracy these methods report is not available "
        "at any price. That is the assumption this project departs from, and "
        "stating it that way is more defensible than claiming to outperform "
        "methods evaluated on different inputs.",
    )),

    ("density", "Density estimation, and counting what cannot be separated", (
        "A strand the first version of this survey missed, and the nearest "
        "neighbour to what this project actually measures. Congestion here is "
        "passenger-car-unit weighted occupancy — a density, not a count — and "
        "estimating density directly from an image is a solved problem in "
        "another domain. Zhang et al. {zhang2016} regress a continuous "
        "density map with a multi-column network at several receptive-field "
        "scales, so that objects at different apparent sizes are handled by "
        "different columns. Li et al. {li2018csr} replace the multi-column "
        "design with dilated convolutions behind a truncated classification "
        "backbone, and report that density can be recovered where individual "
        "objects are no longer separable at all.",

        "That last property is the one that matters at a saturated Indian "
        "approach. When vehicles overlap to the point where a detector cannot "
        "put a box on each, a counting pipeline degrades and a density "
        "estimator does not. This project counts rather than regresses "
        "density, because a count is what converts to passenger-car units and "
        "a density map does not carry vehicle class. That is a deliberate "
        "trade, recorded here as one: the detector's behaviour under "
        "saturation is a known risk, and this literature is where the "
        "alternative lives if that risk materialises."),
    ),

    ("detection", "Object detection as the pipeline's first stage", (
        "Every count in this project comes from a detector, so detection "
        "accuracy bounds everything downstream. Redmon et al. {redmon2016} "
        "reframe detection as a single regression over a grid, which is what "
        "makes per-frame inference on a live stream affordable; the "
        "single-stage family this project uses descends directly from it. Lin "
        "et al. {lin2017} identify why single-stage detectors had lagged — "
        "the loss is dominated by easy background — and show that reshaping "
        "it to down-weight easy negatives closes most of the gap.",

        "Both results bear on a measured property of this project's detector "
        "rather than on a design choice. Accuracy on small, crowded objects "
        "is the known weakness of the single-stage family, and an "
        "obliquely-viewed junction at saturation is precisely that case. The "
        "imbalance Lin et al. correct is between object and background; the "
        "imbalance this project carries is between common and rare vehicle "
        "classes, which {cui2019} addresses and which Section 2.12 returns "
        "to."),
    ),

    ("backbone", "Frozen visual representations", (
        "Two families of frozen feature extractor are relevant. Residual "
        "convolutional networks {he2016} remain a strong local-texture "
        "encoder and are cheap enough to run per frame. Vision transformers "
        "{dosovitskiy2021} treat an image as a sequence of patches and model "
        "long-range relations directly, which is the property a congested "
        "scene needs: occupancy is a relation between distant parts of the "
        "frame, not a local texture.",

        "Two later results shape the choice. Oquab et al. {oquab2024} show "
        "that self-supervised pre-training yields transformer features that "
        "transfer without labels, which matters when the backbone will be "
        "frozen and the downstream corpus is small — a frozen backbone makes "
        "representation quality the whole ceiling. Against that, Liu et al. "
        "{liu2022} show a modernised pure convolutional network matching "
        "transformer performance, which is the adversarial citation this "
        "project must answer: if the transformer branch cannot be shown to "
        "contribute, it should not be in the model. That is precisely what an "
        "ablation with a convolution-only configuration is for.",
    )),

    ("hybrid", "Hybrid convolutional-transformer architectures", (
        "Combining the two families is established work, and the nearest "
        "neighbour is explicit about it. Peng et al. {peng2021} run parallel "
        "convolutional and transformer branches and exchange information "
        "between them through a coupling unit at every stage. Chen et al. "
        "{chen2021} fuse two transformer branches operating at different "
        "token scales using cross-attention on their classification tokens, "
        "establishing cross-attention as a dual-branch fusion mechanism. Dai "
        "et al. {dai2021} stack convolution and attention within one network, "
        "and Mehta and Rastegari {mehta2022} interleave them for efficiency "
        "on mobile hardware.",

        "The consequence for this project is a disclaimer that has to be made "
        "rather than avoided: a dual convolutional-transformer design fused by "
        "cross-attention is not a contribution in 2026, and a report that "
        "presented it as one would be contradicted by the first reviewer who "
        "knows this strand. What the architecture can contribute is evidence — "
        "an ablation that isolates whether the fusion does anything at all on "
        "this task, which these works do not answer for per-lane congestion "
        "forecasting.",
    )),

    ("attention", "Cross-attention and gated fusion", (
        "The mechanisms this project assembles are each published. Scaled "
        "dot-product attention and the multi-head transformer block "
        "{vaswani2017} are the substrate. Lu et al. {lu2019} introduce "
        "co-attentional layers in which each stream's queries attend to the "
        "other stream's keys and values, in both directions — which is "
        "exactly the bidirectional cross-attention this project uses, "
        "published in 2019 for vision and language. Tan and Bansal "
        "{tan2019} build a cross-modality encoder on the same principle.",

        "Gating the result is also established. Alayrac et al. {alayrac2022} "
        "place learned gates on cross-attention layers to control how much "
        "cross-modal information flows into the main stream. The gate in this "
        "project is a convex combination of the two cross-attended streams, "
        "and as a mechanism it is standard.",

        "What is not standard is the use made of it. In the works above a gate "
        "is an optimisation device, reported only through its effect on "
        "accuracy. Here the gate's value is treated as an output: it is "
        "logged per window, analysed against scene density, and reported "
        "whether or not it behaves as predicted. That reframing — mechanism as "
        "measurement — is the defensible contribution, and it survives the "
        "fact that every component of the mechanism is prior art.",
    )),

    ("temporal", "Sequence models and the baselines that must be beaten", (
        "The temporal half of the problem has a long-settled default. Long "
        "short-term memory {hochreiter1997} remains the standard recurrent "
        "encoder for a sixty-step sequence of this length, and a bidirectional "
        "pair of such layers is the project's temporal encoder.",

        "The more important citation in this strand is a baseline rather than "
        "a component. Gradient-boosted decision trees {chen2016} are "
        "extremely strong on small tabular problems, and a per-lane vehicle "
        "count sequence is a small tabular problem. If a boosted-tree model "
        "reading detector counts matches a dual-backbone attention "
        "architecture reading pixels, the complexity of the latter is not "
        "justified, and the honest course is to report that. This is why "
        "count-only baselines are built in parallel with the model rather "
        "than afterwards.",
    )),

    ("rl-control", "Reinforcement learning for signal control", (
        "Learned signal control is a mature literature. Wei et al. "
        "{wei2018} apply deep reinforcement learning to signal control on "
        "real-world data; Wei et al. {wei2019a} shape the reward with "
        "max-pressure theory so the learned policy inherits a known "
        "stability argument; Wei et al. {wei2019b} coordinate many "
        "intersections through graph attention; Zheng et al. {zheng2019} "
        "exploit the phase-competition symmetry so a policy generalises "
        "across intersection geometries; and Chen et al. {chen2020} scale "
        "decentralised pressure-based control to city size. Wei et al. "
        "{wei2021} survey the field and its evaluation practices.",

        "The method this project uses for the controller itself is proximal "
        "policy optimisation {schulman2017}, a standard on-policy algorithm, "
        "applied through a standard implementation. None of this is a "
        "contribution, and the report says so: single-intersection control "
        "with a policy-gradient method on a microscopic simulator is a "
        "well-solved problem.",

        "The open question this strand leaves is about the state, not the "
        "algorithm. The works above build state vectors from instantaneous "
        "measurements — queue lengths, pressures, occupancies of the present. "
        "Whether a controller benefits from an *anticipatory* input, and how "
        "accurate that anticipation must be before the benefit appears, is "
        "largely untested. That question is answerable with a sensitivity "
        "curve over forecast quality, and it is the project's contribution on "
        "the control side.",
    )),

    ("datasets", "Datasets, and why viewpoint is the real gap", (
        "The data situation is specific and it is the project's hardest "
        "constraint. Varma et al. {varma2019} provide the reference Indian "
        "driving dataset, with the heterogeneous classes this project needs — "
        "including auto-rickshaw and animals — but captured from an "
        "ego-vehicle dashcam, because its agenda is autonomous navigation. A "
        "moving viewpoint cannot support per-lane regions that stay valid "
        "across a sixty-step window.",

        "Conversely, the fixed-camera benchmarks have the right viewpoint and "
        "the wrong traffic. Wen et al. {wen2020} provide a fixed elevated "
        "multi-object detection and tracking benchmark on Chinese traffic, and "
        "Tang et al. {tang2019} a city-scale fixed multi-camera benchmark on "
        "United States traffic. Both are lane-disciplined and neither contains "
        "the vehicle modes an Indian stream does.",

        "The intersection of the two properties — heterogeneous Indian traffic "
        "*and* a fixed elevated viewpoint, as continuous video rather than "
        "still frames — is genuinely under-served, and that is a dataset gap "
        "rather than a modelling one. It is also the reason this project "
        "curates its corpus from licensed public sources instead of assuming a "
        "benchmark exists.",
    )),

    ("synthetic", "Synthetic data, and how far a foreign domain transfers", (
        "When the data a project needs does not exist, the literature offers "
        "two answers, and they are not the same answer. The first is to "
        "generate it. Richter et al. {richter2016} extract pixel-accurate "
        "labels from a commercial game engine at no annotation cost; Ros et "
        "al. {ros2016} build a synthetic urban corpus for the same purpose, "
        "and Gaidon et al. {gaidon2016} clone real sequences into a virtual "
        "world so that the same scene exists in both. Dosovitskiy et al. "
        "{dosovitskiy2017} provide an open urban driving simulator with "
        "sensors and a control interface attached. Tobin et al. {tobin2017} "
        "show that deliberately randomising a simulator's appearance, rather "
        "than making it realistic, is often what makes a model transfer.",

        "The second answer is to adapt rather than generate. Ganin et al. "
        "{ganin2016} train a feature extractor adversarially so that a "
        "classifier cannot tell which domain a sample came from, and Hoffman "
        "et al. {hoffman2018} translate images between domains while "
        "enforcing cycle consistency and semantic preservation.",

        "The finding common to both answers is that the synthetic-to-real gap "
        "is real and must be measured rather than assumed away: synthetic "
        "data substitutes for a large fraction of real annotation, and a "
        "small amount of real in-domain data recovers most of what remains. "
        "For this project the implication is specific, and it points away "
        "from generating frames. The deployment viewpoint and the deployment "
        "country are both available in real, openly-licensed data, so "
        "synthetic imagery would substitute for something already held. Where "
        "generation has no substitute is in producing a *controlled* "
        "variable — traffic at a chosen degree of lane discipline, which no "
        "observational dataset can contain, because a real road has whatever "
        "discipline it has and offers no counterfactual."),
    ),

    ("generalisation", "How transfer and imbalance are measured", (
        "Two of this project's methodological commitments are stated in "
        "Section 1.5 as though they were self-evident, and this literature is "
        "what makes them defensible. Holding out whole cameras rather than "
        "shuffling windows is a leave-one-domain-out protocol, and Gulrajani "
        "and Lopez-Paz {gulrajani2021} show why the protocol matters more "
        "than the method: under a careful and consistent evaluation, no "
        "domain-generalisation algorithm reliably beat plain empirical risk "
        "minimisation, and much of the reported progress came from "
        "differences in model selection rather than from the methods "
        "themselves. Zhou et al. {zhou2022} survey the field and its "
        "evaluation practice. The lesson taken here is not that "
        "generalisation is hopeless, but that the split and the "
        "model-selection rule have to be fixed before any number is produced "
        "— which is why both are declared in advance.",

        "The second commitment is reporting per-class accuracy with support "
        "counts rather than a single average. Cui et al. {cui2019} re-weight "
        "a loss by the effective number of samples per class instead of by "
        "raw frequency, and show the advantage grows with imbalance. The "
        "limit of that method is the condition this project is actually in: a "
        "weighting scheme assumes every class is present to be weighted, and "
        "it cannot help a class that has no test instances at all."),
    ),

    ("indian-traffic", "Signal timing under heterogeneous traffic", (
        "The baseline this project must beat has to be constructed carefully, "
        "because its central parameter is uncertain. Webster's method "
        "{webster1958} needs a saturation-flow value, and under non-lane-"
        "disciplined heterogeneous traffic that value is not a constant. "
        "Sugiarto et al. {sugiarto2024} measure base saturation flow on "
        "non-lane-based urban traffic and fit it to approach width, reporting "
        "passenger-car equivalents of 0.24 for a motorcycle and 0.78 for an "
        "auto-rickshaw, with start and end lost times of four to five seconds "
        "and about three seconds. Indian practice itself supplies two "
        "different conventions for the same quantity: the Indian Roads "
        "Congress geometric guidance {irc1994} and the Indian Highway "
        "Capacity Manual {indohcm2017} do not agree, and published "
        "measurements at a single intersection differ by roughly a factor of "
        "two depending on which is used.",

        "The methodological consequence is that the fixed-time baseline cannot "
        "be built from one chosen saturation-flow figure. The published range "
        "has to be swept and the *best* configuration of the baseline taken as "
        "the thing to beat, because beating a badly-tuned baseline measures "
        "the tuning rather than the method.",
    )),

    ("tooling", "Simulation and implementation substrate", (
        "Control cannot be evaluated on a live signal, so it is evaluated in "
        "microscopic simulation. SUMO {lopez2018} supports sub-lane lateral "
        "movement, which is what allows a simulated stream to be "
        "non-lane-disciplined rather than a homogeneous queue, and the "
        "residual gap between the simulated stream and a real Indian one is "
        "declared rather than ignored. The controller is implemented with "
        "Stable-Baselines3 {raffin2021}, a reference implementation whose "
        "behaviour is documented and reproducible, and the detector with a "
        "current single-stage detection framework {yolov8}. Reinforcement "
        "learning terminology throughout follows the standard treatment "
        "{sutton2018}.",
    )),
)


# ==========================================================================
#  Section 3 — the comparative table
# ==========================================================================
#
# Thirty rows, which is the guideline's maximum, ordered by the same theme
# order as the survey and the reference list so a reader can move between the
# three. `Methodology`, `Dataset / Setup`, `Key findings` and `Limitations` are
# written at the level of method and assumption — see this module's docstring
# for why a numeric finding appears only where the project's own bibliography
# records it as verified.
#
# `key` indexes `data/references.json`; the author, year and title columns are
# rendered from that record, never typed here. That is what makes a wrong
# citation impossible to introduce by editing this table.

SURVEY_TABLE: tuple[tuple[str, str, str, str, str], ...] = (
    # (key, methodology, dataset/setup, key findings, limitations)
    ("chakraborty2018",
     "Deep convolutional classifiers (and a comparison against shallow "
     "features) applied to single still images from traffic cameras",
     "Still images from a deployed highway traffic-camera network, "
     "labelled congested or uncongested",
     "Congestion is recoverable from one frame of a fixed camera, "
     "without tracking or a calibrated scene model",
     "Scene-level binary label, present-tense detection rather than a "
     "forecast, and no per-lane output a controller could act on"),

    ("kumar2021",
     "Survey of deep-learning methods across congestion detection, "
     "prediction and alleviation, organised by task and input modality",
     "Survey of published work; no single experimental setup",
     "The field is large and active, and camera-based congestion "
     "estimation is established rather than open",
     "A survey fixes the state of the art but answers no question; it is "
     "cited to bound the novelty claim, not to borrow a method"),

    ("feng2024",
     "End-to-end pipeline chaining vehicle detection, multi-object "
     "tracking and short-horizon flow prediction",
     "Fixed low-resolution urban surveillance camera video",
     "Detection, tracking and prediction compose into one deployable "
     "pipeline driven only by an existing camera",
     "Link- or scene-level flow rather than per-lane congestion, lane- "
     "disciplined setting, and the forecast is not consumed by a "
     "controller"),

    ("yu2018",
     "Graph convolution over the sensor graph combined with gated "
     "temporal convolution, in a fully convolutional spatio-temporal "
     "block",
     "Loop-detector speed and flow time series on instrumented road "
     "networks",
     "Spatial structure and temporal dynamics can be modelled jointly "
     "without recurrence, at low cost",
     "Requires an instrumented network and a known road graph; neither "
     "exists at the target junctions, and no visual input is used"),

    ("li2018",
     "Traffic as a diffusion process on a directed graph, with diffusion "
     "convolution inside a recurrent encoder-decoder trained by "
     "scheduled sampling",
     "Loop-detector speed series from instrumented freeway and arterial "
     "networks",
     "Directed, asymmetric spatial propagation matters, and multi-step "
     "forecasting benefits from modelling it explicitly",
     "Same infrastructure assumption; the directed graph must be "
     "supplied, and the method has no access to appearance"),

    ("wu2019",
     "Learned adaptive adjacency matrix combined with dilated causal "
     "convolution over the temporal axis",
     "Loop-detector series on instrumented networks",
     "The spatial graph can be learned from data rather than taken from "
     "road geometry, removing the hand-built-graph requirement",
     "Removes the need for a *correct* graph but not for the sensors; "
     "still sensor-only and lane-disciplined"),

    ("guo2019",
     "Spatial and temporal attention over a graph convolutional "
     "backbone, with separate components for recent, daily and weekly "
     "periodicity",
     "Loop-detector flow series on instrumented networks",
     "Attention over both axes lets the model weight locations and "
     "periods differently, improving multi-horizon accuracy",
     "Sensor-dependent; the periodicity components presume stable "
     "recurring demand patterns and a long observation history"),

    ("he2016",
     "Residual connections allowing very deep convolutional networks to "
     "be trained by learning residual functions",
     "Large-scale image classification and detection benchmarks",
     "Depth becomes trainable, and the resulting features transfer "
     "broadly as a general-purpose local encoder",
     "Convolutional inductive bias is local; relations between distant "
     "parts of a frame are reached only through depth"),

    ("dosovitskiy2021",
     "Image as a sequence of flattened patches fed to a standard "
     "transformer encoder, with no convolutional prior",
     "Large-scale supervised image classification pre-training, "
     "transferred to smaller benchmarks",
     "Global relations can be modelled directly, and attention-based "
     "vision matches convolutional networks given enough pre-training "
     "data",
     "Data-hungry without a convolutional prior; patch count fixes the "
     "token budget and therefore the spatial granularity"),

    ("oquab2024",
     "Self-supervised pre-training of vision transformers by self- "
     "distillation, producing features used without fine-tuning",
     "Large curated unlabelled image corpus; evaluated by frozen-feature "
     "transfer",
     "Frozen self-supervised features transfer strongly without any "
     "labels, which is what makes a frozen backbone viable on a small "
     "corpus",
     "Features are general rather than task-specific; a frozen backbone "
     "caps achievable accuracy at whatever its representation already "
     "contains"),

    ("liu2022",
     "Pure convolutional network modernised with transformer-era design "
     "choices — large kernels, inverted bottlenecks, revised "
     "normalisation",
     "Large-scale image classification, detection and segmentation "
     "benchmarks",
     "A well-designed convolutional network matches transformers of "
     "comparable scale, so attention is not automatically the better "
     "choice",
     "The adversarial citation for this project: it implies a "
     "transformer branch must be shown to contribute, which only an "
     "ablation can do"),

    ("peng2021",
     "Parallel convolutional and transformer branches with a feature- "
     "coupling unit exchanging information between them at every stage",
     "Image classification, detection and segmentation benchmarks",
     "Local and global representations are complementary, and coupling "
     "them bidirectionally beats either branch alone",
     "Nearest architectural neighbour to this project; couples at every "
     "stage with no learned gate, and has no temporal component or "
     "forecasting task"),

    ("chen2021",
     "Dual transformer branches at different patch scales, fused by "
     "cross-attention between their classification tokens",
     "Image classification benchmarks",
     "Cross-attention is an effective dual-branch fusion operator, and "
     "multi-scale tokens carry complementary information",
     "Both branches are transformers, fusion is single-directional per "
     "exchange, and the task is single-image classification"),

    ("lu2019",
     "Co-attentional transformer layers in which each stream's queries "
     "attend to the other stream's keys and values, in both directions",
     "Large paired image-text corpus, transferred to vision-and-language "
     "tasks",
     "Bidirectional cross-attention between two streams is an effective "
     "fusion mechanism — published in 2019, which is why this project "
     "does not claim it",
     "Fuses two *modalities*; applying it across two visual encoders of "
     "the same frame is a different application, not a new mechanism"),

    ("alayrac2022",
     "Gated cross-attention layers inserted into a frozen language "
     "model, with learned gates controlling how much cross-modal signal "
     "flows",
     "Large interleaved image-text corpus; few-shot evaluation",
     "A learned gate on cross-attention is effective and stable — the "
     "gating mechanism this project uses is therefore prior art",
     "The gate is an optimisation device reported only through "
     "downstream accuracy; its learned value is not analysed as a "
     "finding"),

    ("chen2016",
     "Regularised gradient-boosted decision-tree ensemble with a "
     "sparsity-aware split finder and second-order objective",
     "Tabular machine-learning benchmarks and competition datasets",
     "Boosted trees are extremely strong on small tabular problems — and "
     "a per-lane vehicle count sequence is a small tabular problem",
     "No appearance information, so it cannot act when detection fails; "
     "included here as the baseline the proposed model must justify "
     "itself against"),

    ("wei2018",
     "Deep Q-learning over a phase-gated network, with a reward "
     "combining queue length, delay and phase-change penalties",
     "Microscopic simulation calibrated against real signal and camera "
     "data from a deployed intersection",
     "Learned control beats fixed-time control on real-world-derived "
     "demand, and the evaluation protocol matters as much as the "
     "algorithm",
     "Single intersection, reactive state built from present "
     "measurements, and no anticipatory input"),

    ("wei2019a",
     "Reinforcement learning with a reward derived from max-pressure "
     "theory, coordinating signals along an arterial",
     "Microscopic simulation on synthetic and real arterial networks",
     "Grounding the reward in a known stability result makes the learned "
     "policy coordinate without explicit communication",
     "Pressure is computed from current queue state; the method presumes "
     "reliable per-lane vehicle counts and forecasts nothing"),

    ("chen2020",
     "Decentralised deep reinforcement learning with pressure-based "
     "state and parameter sharing across thousands of intersections",
     "Microscopic simulation at city scale on real road networks",
     "Learned signal control scales to city size — which is why single- "
     "intersection control cannot be claimed as a contribution",
     "Scale rather than sensing: still requires per-lane counts, and "
     "still acts on the present"),

    ("wei2021",
     "Survey of models, state and reward designs, and evaluation "
     "practice in reinforcement-learning signal control",
     "Survey of published work and benchmarks",
     "Fixes what the field has settled, and documents how unevenly "
     "results are reported — which is the argument for seeded runs with "
     "confidence intervals",
     "Surveys the state designs in use; the question of anticipatory "
     "state is left largely open, which is the opening this project uses"),

    ("schulman2017",
     "On-policy policy-gradient optimisation with a clipped surrogate "
     "objective, trading exact trust-region enforcement for simplicity",
     "Continuous-control and Atari benchmark suites",
     "A simple clipped objective matches or beats more complex trust- "
     "region methods and is stable enough to be a default",
     "A general algorithm, not a traffic method; it contributes nothing "
     "to the domain and is used here as a standard tool"),

    ("varma2019",
     "Dataset construction and benchmarking for detection and "
     "segmentation in unconstrained traffic, with a hierarchical label "
     "set",
     "Ego-vehicle dashcam footage from Indian roads, including auto- "
     "rickshaw and animal classes",
     "Unconstrained Indian road scenes are measurably harder than "
     "structured-traffic benchmarks, and the class taxonomy must be "
     "extended to describe them",
     "Ego-vehicle viewpoint: a moving camera cannot support fixed per- "
     "lane regions that stay valid across a window, so it bootstraps "
     "detection but cannot supply the corpus"),

    ("wen2020",
     "Benchmark and evaluation protocol for multi-object detection and "
     "tracking, with detection and tracking scored jointly",
     "Fixed elevated traffic-camera video, predominantly Chinese urban "
     "and highway traffic",
     "Fixed elevated surveillance video is the right viewpoint for lane- "
     "level work, and joint detection-tracking evaluation is necessary "
     "for it",
     "Lane-disciplined traffic without Indian vehicle modes, so a model "
     "trained on it does not transfer to the target stream"),

    ("tang2019",
     "City-scale benchmark for multi-target multi-camera vehicle "
     "tracking and re-identification, with calibrated camera geometry",
     "Fixed multi-camera video across road intersections in the United "
     "States",
     "Multi-camera fixed-viewpoint data at city scale is collectable and "
     "annotatable, and viewpoint calibration is what makes it usable",
     "United States traffic, lane-disciplined, and oriented to re- "
     "identification — a task this project explicitly excludes on "
     "privacy grounds"),

    ("sugiarto2024",
     "Field measurement of base saturation flow at pre-timed signalised "
     "intersections, regressed against effective approach width, with "
     "passenger-car equivalents estimated per mode",
     "Field survey of non-lane-based urban heterogeneous traffic at "
     "signalised intersections",
     "Base saturation flow scales nearly linearly with approach width; "
     "passenger-car equivalents of 0.24 for a motorcycle and 0.78 for an "
     "auto-rickshaw; start lost time four to five seconds and end lost "
     "time about three seconds",
     "Measured at specific sites, so the coefficients are not portable "
     "unaltered; it quantifies the baseline's uncertainty rather than "
     "removing it"),

    ("redmon2016",
     "Detection reframed as a single regression over a grid, predicting "
     "boxes and class probabilities in one forward pass",
     "Standard object-detection benchmarks, evaluated at real-time frame "
     "rates",
     "Detection becomes fast enough to run per frame on a live stream, "
     "which is what makes a detector usable inside a per-step counting "
     "pipeline",
     "Accuracy on small and crowded objects lags two-stage detectors, "
     "and an obliquely-viewed saturated junction is exactly that case"),

    ("lin2017",
     "A reshaped cross-entropy that down-weights easy negatives so "
     "training is not dominated by background, inside a single-stage "
     "detector",
     "Standard detection benchmarks under extreme foreground-background "
     "imbalance",
     "Class imbalance rather than architecture was what held single- "
     "stage detectors back; correcting the loss closes most of the gap",
     "Corrects imbalance between object and background, not between rare "
     "and common vehicle classes, which is the imbalance this project "
     "carries"),

    ("li2018csr",
     "Dilated convolutions behind a truncated classification backbone, "
     "regressing a continuous density map rather than counting objects",
     "Dense crowd-counting benchmarks, including highly congested scenes",
     "Density is recoverable where individual objects are no longer "
     "separable, and the map integrates to a count without detecting "
     "anything",
     "Counts people rather than weighting heterogeneous vehicle classes, "
     "and yields a scene density rather than a per-lane one"),

    ("richter2016",
     "Pixel-accurate labels extracted from a commercial game engine by "
     "intercepting its rendering calls, at no annotation cost",
     "Synthetic urban driving frames, transferred to real segmentation "
     "benchmarks",
     "Synthetic data substitutes for a large fraction of real "
     "annotation, and a small amount of real in-domain data recovers "
     "most of the remainder",
     "The synthetic-to-real gap is real and must be measured; a model "
     "trained on synthetic alone does not match one trained in domain"),

    ("cui2019",
     "A loss re-weighted by the effective number of samples per class "
     "rather than by raw frequency, derived from expected sample "
     "coverage",
     "Long-tailed image classification benchmarks at controlled "
     "imbalance factors",
     "Re-weighting by effective number beats inverse-frequency weighting "
     "as imbalance grows, which is the regime a rare-class taxonomy sits "
     "in",
     "Assumes every class is present to be weighted, so it cannot help a "
     "class that has no test instances at all"),
)


#: The guideline's bound, checked here rather than in the renderer. A table
#: that drifts to 24 or 31 rows is a submission defect, and the cheapest place
#: to catch it is the module that holds the rows. The four works that are cited
#: in Section 2 but deliberately absent from the table — a mobile hybrid
#: backbone, a second cross-modal encoder, the simulator and the
#: reinforcement-learning library — are tools or near-duplicates of a row that
#: is already present, and the guideline asks the table to hold research papers
#: and prior projects rather than everything cited.
TABLE_MIN, TABLE_MAX = 25, 30

if not TABLE_MIN <= len(SURVEY_TABLE) <= TABLE_MAX:
    raise AssertionError(
        f"the literature survey table has {len(SURVEY_TABLE)} rows; the "
        f"guideline requires between {TABLE_MIN} and {TABLE_MAX}.")


# ==========================================================================
#  Section 4 — Research Gap
# ==========================================================================
#
# The guideline asks five specific questions and expects the answers to be
# derived from the survey rather than written as generalities. Each list below
# answers one of them, and every entry traces to a subsection of Section 2.

GAP_WHAT_IS_DONE: tuple[str, str] = (
    "What has already been done",
    "The survey establishes four settled bodies of work. Congestion can be "
    "estimated from a fixed camera's imagery, and this is an active field "
    "rather than an opening {chakraborty2018}, {kumar2021}, {feng2024}. "
    "Spatio-temporal forecasting over an instrumented sensor network is "
    "mature and accurate {yu2018}, {li2018}, {wu2019}, {guo2019}. Fusing "
    "convolutional and transformer representations by bidirectional "
    "cross-attention with a learned gate is published, in some cases years "
    "ago {peng2021}, {chen2021}, {lu2019}, {alayrac2022}. And "
    "reinforcement-learning signal control is heavily benchmarked, including "
    "at city scale {wei2018}, {wei2019a}, {chen2020}, {wei2021}. This "
    "project claims none of these four as its contribution.",
)

GAP_LIMITS: tuple[tuple[str, str], ...] = (
    ("The accurate forecasters assume sensing that the target junctions do "
     "not have",
     "Every method in the graph-forecasting strand consumes loop-detector or "
     "probe readings over a known road graph {yu2018}, {li2018}, {wu2019}, "
     "{guo2019}. At an Indian junction with a camera and no loops those "
     "inputs do not exist, so the reported accuracy is unavailable rather "
     "than merely harder to reach."),

    ("The camera-based work produces the wrong granularity",
     "Published vision-based congestion work classifies the scene as a whole "
     "or predicts link-level flow {chakraborty2018}, {feng2024}. A signal "
     "controller allocates green to an approach, so a scene-level score "
     "gives it nothing to act on."),

    ("Most of it estimates the present rather than the future",
     "Detection of current congestion {chakraborty2018} is a measurement. A "
     "signal decision takes effect over the next phase, so a controller needs "
     "a forecast at roughly one phase's horizon."),

    ("Evaluation settings are lane-disciplined",
     "The fixed-camera benchmarks that have the right viewpoint carry "
     "structured traffic {wen2020}, {tang2019}, and the Indian dataset with "
     "the right traffic has a moving ego-vehicle viewpoint {varma2019}. "
     "Neither combination matches the deployment target."),

    ("The gate is reported only through its effect",
     "Gated fusion is evaluated by downstream accuracy {alayrac2022}. What "
     "the gate learns is not itself examined, so the interpretability the "
     "mechanism could offer is left unclaimed."),

    ("Controller state is built from the present",
     "The reinforcement-learning literature composes state from instantaneous "
     "measurements {wei2019a}, {zheng2019}, {chen2020}. Whether an "
     "anticipatory input helps, and how accurate it must be before it does, "
     "is not systematically tested."),
)

GAP_UNRESOLVED: tuple[str, ...] = (
    "No published method produces a per-lane congestion forecast, at a "
    "one-phase horizon, from a single fixed camera, under non-lane-"
    "disciplined heterogeneous traffic, and feeds it to a controller. Each "
    "element exists separately; the conjunction does not.",

    "It is not established whether appearance information beats vehicle "
    "counts for this task. The count-based alternative is cheap and strong "
    "{chen2016}, and the comparison is rarely made on verified labels with "
    "whole cameras held out.",

    "It is not known whether a fusion gate learns anything that corresponds "
    "to a physical property of the scene, because the works that use gates "
    "do not report their values {alayrac2022}.",

    "The sensitivity of a learned controller to forecast quality is "
    "unmeasured. Without it, a positive control result cannot be attributed "
    "to anticipation rather than to the controller itself.",

    "There is no public corpus of continuous fixed-camera video of "
    "heterogeneous Indian junction traffic with per-lane labels. The datasets "
    "that exist have either the viewpoint or the traffic, not both "
    "{varma2019}, {wen2020}, {tang2019}.",
)

GAP_UNADDRESSED: tuple[tuple[str, str], ...] = (
    ("Congestion defined on occupancy rather than count",
     "A count treats a bus and a two-wheeler alike. Under heterogeneous "
     "traffic the quantity a controller needs is occupancy weighted by "
     "passenger-car units, and the published equivalences differ enough "
     "between conventions to change the answer {sugiarto2024}, {irc1994}, "
     "{indohcm2017}."),

    ("Per-camera threshold calibration",
     "A congestion threshold that is correct at one viewpoint is arbitrary at "
     "another, yet thresholds are commonly fixed globally."),

    ("Camera-level generalisation",
     "Splitting overlapping windows at random lets a model recognise a camera "
     "it has already seen and report that as generalisation. Holding out "
     "whole cameras is the only split that measures what deployment "
     "requires."),

    ("Labels that do not derive from the baseline's own inputs",
     "If congestion labels are derived from detector counts and the baseline "
     "also consumes detector counts, the comparison is circular. A "
     "human-verified test split is what breaks it."),

    ("Privacy as a design constraint rather than a policy",
     "Work in this area generally assumes footage can be moved and stored. "
     "Keeping raw frames on the device and transmitting only derived counts "
     "is a constraint on the architecture, not a statement added afterwards."),
)

GAP_HOW_WE_ADDRESS: tuple[tuple[str, str], ...] = (
    ("Claim the conjunction, not the components",
     "The contribution is stated as per-lane congestion forecasting from a "
     "single fixed camera under non-lane-disciplined heterogeneous traffic, "
     "coupled to a controller. Every component mechanism is cited as prior "
     "art rather than presented as new."),

    ("Build the corpus the gap implies",
     "Curate continuous fixed-camera footage of heterogeneous traffic from "
     "permissively-licensed sources, place lane regions per camera by hand, "
     "and label per-lane congestion from passenger-car-unit weighted "
     "occupancy with per-camera thresholds."),

    ("Make the comparison that decides the question",
     "Evaluate against count-only forecasters including a boosted-tree model "
     "{chen2016} and a linear probe, on a human-verified test split, with "
     "whole cameras held out — and report the result whichever way it goes."),

    ("Treat the gate as a measurement",
     "Log the gate value per window and analyse it against scene density, "
     "reporting a gate that collapses or tracks nothing as the negative "
     "result it is."),

    ("Answer the control question with a curve, not a comparison",
     "Sweep forecast quality from none through a noise-calibrated surrogate "
     "to an oracle, so the result says how good the forecast must be before "
     "anticipation pays, and compare against the best-tuned fixed-time "
     "baseline {webster1958} rather than an arbitrary one."),

    ("Design for the privacy constraint",
     "Run detection at the edge and transmit only derived counts and "
     "predictions, so that no raw frame is written to disk or crosses the "
     "network at any point in the pipeline."),
)

GAP_CLOSING: tuple[str, ...] = (
    "Stated plainly, the gap this project occupies is not a missing "
    "mechanism. The mechanisms exist and are cited. It is the absence of a "
    "method that works from the sensing an Indian junction actually has, "
    "produces the quantity a signal controller actually consumes, is "
    "evaluated under the traffic that actually arrives, and is honest about "
    "which of its parts earn their cost.",
)


#: Six rows of the comparative table, rewritten short enough to set on one
#: line of a slide. Purpose-written rather than truncated: an ellipsis in the
#: middle of a cell reads as a rendering fault, and a slide that samples the
#: table should look deliberate. The report's table is the full one — this is
#: the shape of it, and the keys are a subset of `SURVEY_TABLE`'s so the two
#: cannot describe different papers.
SURVEY_TABLE_SLIDE: tuple[tuple[str, str, str], ...] = (
    ("chakraborty2018", "Deep CNN on single traffic-camera frames",
     "Scene-level and present-tense, not per-lane"),
    ("li2018", "Diffusion on a directed sensor graph",
     "Needs loops and a known road graph"),
    ("peng2021", "Parallel CNN and transformer, coupled",
     "Nearest neighbour; no gate, no temporal axis"),
    ("lu2019", "Co-attention in both directions, 2019",
     "So our fusion mechanism is prior art"),
    ("chen2020", "Decentralised RL at city scale",
     "State is the present; no anticipation"),
    ("varma2019", "Indian dataset, heterogeneous classes",
     "Ego-vehicle view cannot hold per-lane regions"),
)

_table_keys = {key for key, *_ in SURVEY_TABLE}
_stray = [key for key, *_ in SURVEY_TABLE_SLIDE if key not in _table_keys]
if _stray:
    raise AssertionError(
        f"the slide sampler cites {_stray}, which are not rows of the "
        "report's comparative table; the deck and the report would describe "
        "different papers.")


#: Theme slugs shortened for a slide column. The slugs themselves are the
#: grouping key shared by `data/references.json`, the survey sections and the
#: table order, so they stay descriptive; this is only how they are displayed
#: where there is room for one word.
THEME_LABELS: dict[str, str] = {
    "vision-congestion": "vision",
    "graph-forecasting": "graph",
    "backbone": "backbone",
    "hybrid": "hybrid",
    "attention": "attention",
    "temporal": "temporal",
    "detection": "detect",
    "density": "density",
    "synthetic": "synthetic",
    "generalisation": "transfer",
    "rl-control": "control",
    "datasets": "data",
    "indian-traffic": "timing",
    "tooling": "tools",
}

_unlabelled = sorted({work.theme for work in WORKS.values()}
                     - set(THEME_LABELS))
if _unlabelled:
    raise AssertionError(
        f"themes without a short label: {_unlabelled}. Add them to "
        "THEME_LABELS, or a slide column will render a raw slug.")


def _NARRATIVE_BLOCKS() -> list[str]:
    """Every piece of prose that may carry a `{key}`.

    Listed explicitly rather than discovered by scanning the module, so that
    adding a new prose block and forgetting to render it is a missing-citation
    failure in the checker rather than a `{key}` printed literally into a
    submitted document.
    """
    blocks: list[str] = []
    for _theme, _title, paragraphs in SURVEY_SECTIONS:
        blocks.extend(paragraphs)
    blocks.append(GAP_WHAT_IS_DONE[1])
    blocks.extend(detail for _lead, detail in GAP_LIMITS)
    blocks.extend(GAP_UNRESOLVED)
    blocks.extend(detail for _lead, detail in GAP_UNADDRESSED)
    blocks.extend(detail for _lead, detail in GAP_HOW_WE_ADDRESS)
    blocks.extend(GAP_CLOSING)
    return blocks
