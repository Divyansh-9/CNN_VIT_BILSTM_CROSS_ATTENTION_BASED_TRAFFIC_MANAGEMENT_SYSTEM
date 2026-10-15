"""Verify every reference against OpenAlex and commit the records.

`docs/00-planning/BIBLIOGRAPHY.md` marks most of its entries ⚠️ — "named from
general knowledge, **not retrieved**" — and states the rule this script exists
to satisfy: *nothing enters the paper's reference list while still marked ⚠️*.
The Phase-I Progress Report guideline raises the stakes: it requires a
comparative table of 25-30 papers, and a table of plausible-looking citations
nobody retrieved is exactly the failure the bibliography's own rule anticipates.

So the reference list is **fetched, not typed**. Each entry below declares the
title and year it expects; the script queries OpenAlex, picks the best candidate,
and **refuses to record it** unless the returned title and year match what was
expected. A mismatch is reported with the candidate it found so the expectation
can be corrected against reality — never the reverse.

    python scripts/verify_references.py            # refresh data/references.json
    python scripts/verify_references.py --check    # fail if the file is stale

Output is deterministic: no timestamps, no run identifiers, sorted keys. A
re-run after a successful run produces a byte-identical file, so a diff means a
record actually changed upstream. That is the same discipline as
`experiments/provenance.py` — record what identifies the thing, never when it
was looked at.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "data" / "references.json"

API = "https://api.openalex.org/works"
SELECT = ("display_name,publication_year,doi,authorships,primary_location,"
          "type,ids")

#: OpenAlex asks for a contact address in the query string rather than an API
#: key, and answers faster when it gets one. The project has no shared mailbox,
#: so the polite-pool identifier is the repository itself.
MAILTO = "https://github.com/mfstnet"

#: A year may legitimately differ from the expectation by one: OpenAlex dates a
#: work by its earliest record, which for a conference paper is often the
#: preprint posted the year before. Two years apart is a different paper.
YEAR_SLACK = 1

#: How much of the expected title must appear in the returned one. Set by the
#: failure it has to catch: the expected DCRNN title shares 6 of its 9
#: significant words with a *different* 2018 traffic-forecasting paper, and the
#: words it does not share — "diffusion", "data", "driven" — are the ones that
#: identify it. A threshold low enough to tolerate a reworded title is low
#: enough to accept the wrong paper, so the threshold is high and the
#: short-form case below is handled explicitly instead.
TITLE_OVERLAP = 0.75

#: A record whose title is at most this many significant words is treated as a
#: short form — OpenAlex holds some conference papers under only their name,
#: `PressLight`, `CoLight` — and matches when every word of it appears in the
#: expectation. Longer than this and a title has enough content to be checked
#: in the normal direction.
SHORT_FORM_WORDS = 3

STOPWORDS = frozenset("a an the of for and in on to with without by at is are "
                      "from as all its it this that".split())


# ==========================================================================
#  what to verify
# ==========================================================================
#
# `key` is the citation key the content module uses. `query` is what goes to
# OpenAlex. `title` and `year` are the expectation the result is checked
# against — they are the assertion, not a hint, and a failure here means the
# expectation was wrong and must be corrected from the record.
#
# `theme` groups the entry in the literature survey and in the comparative
# table, so the table's ordering is a property of this file rather than of the
# document that renders it.

WORKS: tuple[dict, ...] = (
    # -- the task: congestion from camera imagery ---------------------------
    dict(key="chakraborty2018", theme="vision-congestion",
         query="Traffic Congestion Detection from Camera Images using Deep "
               "Convolution Neural Networks",
         title="Traffic Congestion Detection from Camera Images using Deep "
               "Convolution Neural Networks", year=2018),
    dict(key="kumar2021", theme="vision-congestion",
         query="Applications of deep learning in congestion detection "
               "prediction and alleviation a survey",
         title="Applications of deep learning in congestion detection, "
               "prediction and alleviation: A survey", year=2021),
    dict(key="feng2024", theme="vision-congestion",
         query="Predicting spatio-temporal traffic flow comprehensive "
               "end-to-end approach from surveillance cameras",
         title="Predicting spatio-temporal traffic flow: a comprehensive "
               "end-to-end approach from surveillance cameras", year=2024),

    # -- the mainstream forecasting paradigm, and what it assumes -----------
    dict(key="yu2018", theme="graph-forecasting",
         query="Spatio-Temporal Graph Convolutional Networks A Deep Learning "
               "Framework for Traffic Forecasting",
         title="Spatio-Temporal Graph Convolutional Networks: A Deep Learning "
               "Framework for Traffic Forecasting", year=2018),
    dict(key="li2018", theme="graph-forecasting",
         query="Diffusion Convolutional Recurrent Neural Network Data-Driven "
               "Traffic Forecasting",
         title="Diffusion Convolutional Recurrent Neural Network: "
               "Data-Driven Traffic Forecasting", year=2018),
    dict(key="wu2019", theme="graph-forecasting",
         query="Graph WaveNet for Deep Spatial-Temporal Graph Modeling",
         title="Graph WaveNet for Deep Spatial-Temporal Graph Modeling",
         year=2019),
    dict(key="guo2019", theme="graph-forecasting",
         query="Attention Based Spatial-Temporal Graph Convolutional Networks "
               "for Traffic Flow Forecasting",
         title="Attention Based Spatial-Temporal Graph Convolutional Networks "
               "for Traffic Flow Forecasting", year=2019),

    # -- the backbones ------------------------------------------------------
    dict(key="he2016", theme="backbone",
         query="Deep Residual Learning for Image Recognition",
         title="Deep Residual Learning for Image Recognition", year=2016),
    dict(key="dosovitskiy2021", theme="backbone",
         query="An Image is Worth 16x16 Words Transformers for Image "
               "Recognition at Scale",
         title="An Image is Worth 16x16 Words: Transformers for Image "
               "Recognition at Scale", year=2020),
    dict(key="oquab2024", theme="backbone",
         query="DINOv2 Learning Robust Visual Features without Supervision",
         title="DINOv2: Learning Robust Visual Features without Supervision",
         year=2023),
    dict(key="liu2022", theme="backbone",
         query="A ConvNet for the 2020s",
         title="A ConvNet for the 2020s", year=2022),

    # -- hybrid CNN-transformer: the nearest architectural neighbours ------
    dict(key="peng2021", theme="hybrid",
         query="Conformer Local Features Coupling Global Representations for "
               "Visual Recognition",
         title="Conformer: Local Features Coupling Global Representations for "
               "Visual Recognition", year=2021),
    dict(key="chen2021", theme="hybrid",
         query="CrossViT Cross-Attention Multi-Scale Vision Transformer for "
               "Image Classification",
         title="CrossViT: Cross-Attention Multi-Scale Vision Transformer for "
               "Image Classification", year=2021),
    dict(key="dai2021", theme="hybrid",
         query="CoAtNet Marrying Convolution and Attention for All Data Sizes",
         title="CoAtNet: Marrying Convolution and Attention for All Data "
               "Sizes", year=2021),
    dict(key="mehta2022", theme="hybrid",
         query="MobileViT Light-weight General-purpose and Mobile-friendly "
               "Vision Transformer",
         title="MobileViT: Light-weight, General-purpose, and Mobile-friendly "
               "Vision Transformer", year=2021),

    # -- cross-attention and gating: the mechanisms we must not claim ------
    dict(key="vaswani2017", theme="attention",
         query="Attention Is All You Need",
         title="Attention Is All You Need", year=2017),
    dict(key="lu2019", theme="attention",
         query="ViLBERT Pretraining Task-Agnostic Visiolinguistic "
               "Representations for Vision-and-Language Tasks",
         title="ViLBERT: Pretraining Task-Agnostic Visiolinguistic "
               "Representations for Vision-and-Language Tasks", year=2019),
    dict(key="tan2019", theme="attention",
         query="LXMERT Learning Cross-Modality Encoder Representations from "
               "Transformers",
         title="LXMERT: Learning Cross-Modality Encoder Representations from "
               "Transformers", year=2019),
    dict(key="alayrac2022", theme="attention",
         query="Flamingo a Visual Language Model for Few-Shot Learning",
         title="Flamingo: a Visual Language Model for Few-Shot Learning",
         year=2022),

    # -- temporal models ----------------------------------------------------
    dict(key="hochreiter1997", theme="temporal",
         query="Long Short-Term Memory",
         title="Long Short-Term Memory", year=1997),
    dict(key="chen2016", theme="temporal",
         query="XGBoost A Scalable Tree Boosting System",
         title="XGBoost: A Scalable Tree Boosting System", year=2016),

    # -- reinforcement learning for signal control -------------------------
    dict(key="wei2018", theme="rl-control",
         query="IntelliLight Reinforcement Learning Intelligent Traffic Light "
               "Control",
         title="IntelliLight: A Reinforcement Learning Approach for "
               "Intelligent Traffic Light Control", year=2018),
    dict(key="wei2019a", theme="rl-control",
         query="PressLight Learning Max Pressure Control to Coordinate "
               "Traffic Signals in Arterial Network",
         title="PressLight: Learning Max Pressure Control to Coordinate "
               "Traffic Signals in Arterial Network", year=2019),
    dict(key="wei2019b", theme="rl-control",
         query="CoLight Learning Network-level Cooperation for Traffic Signal "
               "Control",
         title="CoLight: Learning Network-level Cooperation for Traffic "
               "Signal Control", year=2019),
    dict(key="zheng2019", theme="rl-control",
         query="Learning Phase Competition for Traffic Signal Control",
         title="Learning Phase Competition for Traffic Signal Control",
         year=2019),
    dict(key="chen2020", theme="rl-control",
         query="Toward A Thousand Lights Decentralized Deep Reinforcement "
               "Learning for Large-Scale Traffic Signal Control",
         title="Toward A Thousand Lights: Decentralized Deep Reinforcement "
               "Learning for Large-Scale Traffic Signal Control", year=2020),
    dict(key="wei2021", theme="rl-control",
         query="Recent Advances in Reinforcement Learning for Traffic Signal "
               "Control A Survey of Models and Evaluation",
         title="Recent Advances in Reinforcement Learning for Traffic Signal "
               "Control: A Survey of Models and Evaluation", year=2021),
    dict(key="schulman2017", theme="rl-control",
         query="Proximal Policy Optimization Algorithms",
         title="Proximal Policy Optimization Algorithms", year=2017),

    # -- data: viewpoint is the gap -----------------------------------------
    dict(key="varma2019", theme="datasets",
         query="IDD A Dataset for Exploring Problems of Autonomous "
               "Navigation in Unconstrained Environments",
         title="IDD: A Dataset for Exploring Problems of Autonomous "
               "Navigation in Unconstrained Environments", year=2019),
    dict(key="wen2020", theme="datasets",
         query="UA-DETRAC A new benchmark and protocol for multi-object "
               "detection and tracking",
         title="UA-DETRAC: A new benchmark and protocol for multi-object "
               "detection and tracking", year=2020),
    dict(key="tang2019", theme="datasets",
         query="CityFlow A City-Scale Benchmark for Multi-Target Multi-Camera "
               "Vehicle Tracking and Re-Identification",
         title="CityFlow: A City-Scale Benchmark for Multi-Target "
               "Multi-Camera Vehicle Tracking and Re-Identification",
         year=2019),

    # -- the Indian signal-timing ground this stands on ---------------------
    dict(key="sugiarto2024", theme="indian-traffic",
         query="Base saturation flow rate and its effect on performance of "
               "pretimed signalized intersection with non-lane based urban "
               "heterogeneous traffic",
         title="Base saturation flow rate (BSFR) and its effect on "
               "performance of pretimed signalized intersection with "
               "non-lane based urban heterogeneous traffic", year=2024),

    # -- tooling that is cited as a method, not as a convenience -----------
    dict(key="lopez2018", theme="tooling",
         query="Microscopic Traffic Simulation using SUMO",
         title="Microscopic Traffic Simulation using SUMO", year=2018),
    # -- the pipeline's first stage, which the survey cited only as a URL -----
    dict(key="redmon2016", theme="detection",
         query="You Only Look Once Unified Real-Time Object Detection",
         title="You Only Look Once: Unified, Real-Time Object Detection",
         year=2016),
    dict(key="lin2017", theme="detection",
         query="Focal Loss for Dense Object Detection",
         title="Focal Loss for Dense Object Detection", year=2017),

    # -- density estimation: the nearest neighbour the first survey missed ----
    dict(key="zhang2016", theme="density",
         query="Single-Image Crowd Counting via Multi-Column Convolutional "
               "Neural Network",
         title="Single-Image Crowd Counting via Multi-Column Convolutional "
               "Neural Network", year=2016),
    dict(key="li2018csr", theme="density",
         query="CSRNet Dilated Convolutional Neural Networks for "
               "Understanding the Highly Congested Scenes",
         title="CSRNet: Dilated Convolutional Neural Networks for "
               "Understanding the Highly Congested Scenes", year=2018),

    # -- synthetic data and domain transfer ----------------------------------
    dict(key="richter2016", theme="synthetic",
         query="Playing for Data Ground Truth from Computer Games",
         title="Playing for Data: Ground Truth from Computer Games",
         year=2016),
    dict(key="ros2016", theme="synthetic",
         query="The SYNTHIA Dataset A Large Collection of Synthetic Images "
               "for Semantic Segmentation of Urban Scenes",
         title="The SYNTHIA Dataset: A Large Collection of Synthetic Images "
               "for Semantic Segmentation of Urban Scenes", year=2016),
    dict(key="gaidon2016", theme="synthetic",
         query="Virtual Worlds as Proxy for Multi-Object Tracking Analysis",
         title="Virtual Worlds as Proxy for Multi-Object Tracking Analysis",
         year=2016),
    dict(key="dosovitskiy2017", theme="synthetic",
         query="CARLA An Open Urban Driving Simulator",
         title="CARLA: An Open Urban Driving Simulator", year=2017),
    dict(key="tobin2017", theme="synthetic",
         query="Domain Randomization for Transferring Deep Neural Networks "
               "from Simulation to the Real World",
         title="Domain Randomization for Transferring Deep Neural Networks "
               "from Simulation to the Real World", year=2017),
    dict(key="ganin2016", theme="synthetic",
         query="Domain-Adversarial Training of Neural Networks",
         title="Domain-Adversarial Training of Neural Networks", year=2016),
    dict(key="hoffman2018", theme="synthetic",
         query="CyCADA Cycle-Consistent Adversarial Domain Adaptation",
         title="CyCADA: Cycle-Consistent Adversarial Domain Adaptation",
         year=2018),

    # -- how generalisation and imbalance are measured -----------------------
    dict(key="gulrajani2021", theme="generalisation",
         query="In Search of Lost Domain Generalization",
         title="In Search of Lost Domain Generalization", year=2020),
    dict(key="zhou2022", theme="generalisation",
         query="Domain Generalization A Survey",
         title="Domain Generalization: A Survey", year=2022),
    dict(key="cui2019", theme="generalisation",
         query="Class-Balanced Loss Based on Effective Number of Samples",
         title="Class-Balanced Loss Based on Effective Number of Samples",
         year=2019),

    dict(key="raffin2021", theme="tooling",
         query="Stable-Baselines3 Reliable Reinforcement Learning "
               "Implementations",
         title="Stable-Baselines3: Reliable Reinforcement Learning "
               "Implementations", year=2021),
)


# ==========================================================================
#  matching
# ==========================================================================

def significant(title: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", title.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 1}


def title_matches(expected: str, found: str) -> bool:
    """Whether `found` is a record of the work `expected` names.

    Two cases, kept separate on purpose. Normally most of the expected title's
    significant words must appear in the record, *and* its first significant
    word must — that word carries the identity ("Diffusion", "Conformer",
    "IntelliLight"), and requiring it is what rejects a different paper on the
    same topic that happens to share the generic remainder.

    The exception is a record stored under only a short name, where there is no
    title to measure: then every word of the record must appear in the
    expectation instead.
    """
    want, got = significant(expected), significant(found)
    if not want or not got:
        return False
    if len(got) <= SHORT_FORM_WORDS:
        return got <= want
    first = significant_order(expected)
    if first and first[0] not in got:
        return False
    return len(want & got) / len(want) >= TITLE_OVERLAP


def significant_order(title: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", title.lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 1]


def pick(candidates: list[dict], work: dict) -> tuple[dict | None, str]:
    """The best candidate, or None and why nothing qualified.

    Prefers a published venue over the preprint of the same work: OpenAlex
    returns both, and a reference list should point at the record of
    publication. Falls back to the preprint when that is all there is, which is
    the honest outcome for a work that only ever appeared on arXiv.
    """
    scored: list[tuple[float, int, int, dict]] = []
    for item in candidates:
        found = item.get("display_name") or ""
        if not title_matches(work["title"], found):
            continue
        year = item.get("publication_year")
        if year is None or abs(year - work["year"]) > YEAR_SLACK:
            continue
        location = item.get("primary_location") or {}
        source = location.get("source") or {}
        repository = (source.get("type") == "repository"
                      or "arxiv" in (source.get("display_name") or "").lower())
        # Exact year outranks a year inside the slack. OpenAlex holds some
        # duplicate records dated by a later re-publication — "Attention Is All
        # You Need" appears as 2025 — and preferring the expected year is what
        # keeps the canonical record ahead of them.
        want = significant(work["title"])
        overlap = len(want & significant(found)) / len(want) if want else 0.0
        scored.append((overlap, 1 if year == work["year"] else 0,
                       0 if repository else 1, item))

    if not scored:
        names = [f"{c.get('display_name')!r} ({c.get('publication_year')})"
                 for c in candidates[:3]]
        return None, ("no candidate matched the expected title and year; "
                      f"OpenAlex returned {names or 'nothing'}")
    scored.sort(key=lambda row: (row[1], row[2], row[0]), reverse=True)
    return scored[0][3], ""


def fetch(query: str, rows: int = 10) -> list[dict]:
    params = urllib.parse.urlencode({
        "search": query, "per-page": rows, "select": SELECT, "mailto": MAILTO})
    url = f"{API}?{params}"
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=45) as response:
                return json.load(response).get("results", [])
        except urllib.error.HTTPError as error:
            # 429 is a rate limit, not a failure: wait long enough to matter.
            # The short exponential backoff that suits a dropped connection
            # just burns the remaining attempts against a quota.
            if error.code != 429 or attempt == 4:
                raise RuntimeError(f"OpenAlex unreachable: {error}") from error
            time.sleep(15 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            if attempt == 4:
                raise RuntimeError(f"OpenAlex unreachable: {error}") from error
            time.sleep(1.5 * (attempt + 1))
    return []


# ==========================================================================
#  arXiv, for the works OpenAlex cannot serve
# ==========================================================================
#
# OpenAlex's index is wrong about two of the most-cited papers in this
# bibliography: it holds "Attention Is All You Need" dated 2025 and has no 2017
# record of it at all, and nothing for "Proximal Policy Optimization
# Algorithms". Both are arXiv preprints, and arXiv's own API is the authority
# for an arXiv preprint — so those entries are verified there instead, and the
# record says which authority answered. Falling back to typing the DOI from
# memory is the one thing this script exists to prevent.

ARXIV_API = "http://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"


def fetch_arxiv(query: str, rows: int = 8) -> list[dict]:
    from xml.etree import ElementTree

    terms = " AND ".join(f'ti:"{word}"' for word in [query])
    params = urllib.parse.urlencode({"search_query": terms,
                                     "max_results": rows})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(f"{ARXIV_API}?{params}",
                                        timeout=45) as response:
                feed = ElementTree.fromstring(response.read())
            break
        except (urllib.error.URLError, TimeoutError,
                ElementTree.ParseError) as error:
            if attempt == 3:
                raise RuntimeError(f"arXiv unreachable: {error}") from error
            time.sleep(1.5 * (attempt + 1))
    else:                                          # pragma: no cover
        return []

    results: list[dict] = []
    for entry in feed.iter(ATOM + "entry"):
        identifier = (entry.findtext(ATOM + "id") or "")
        # `abs/1706.03762v7` — the version suffix is an edition of the same
        # work, and a reference list cites the work.
        arxiv_id = identifier.rsplit("/", 1)[-1].split("v")[0]
        published = entry.findtext(ATOM + "published") or ""
        results.append({
            "display_name": " ".join(
                (entry.findtext(ATOM + "title") or "").split()),
            "publication_year": int(published[:4]) if published[:4].isdigit()
                                else None,
            "doi": f"https://doi.org/10.48550/arXiv.{arxiv_id}",
            "authorships": [
                {"author": {"display_name": author.findtext(ATOM + "name")}}
                for author in entry.iter(ATOM + "author")],
            "primary_location": {"source": {"display_name": "arXiv",
                                            "type": "repository"}},
            "type": "preprint",
            "ids": {"arxiv": arxiv_id},
        })
    return results


def record(work: dict, item: dict, authority: str) -> dict:
    """The committed form: identity only, nothing about the lookup itself."""
    location = item.get("primary_location") or {}
    source = location.get("source") or {}
    authors = [(a.get("author") or {}).get("display_name") or "?"
               for a in item.get("authorships", [])]
    doi = (item.get("doi") or "").replace("https://doi.org/", "")
    return {
        "key": work["key"],
        "theme": work["theme"],
        "title": item.get("display_name"),
        "authors": authors,
        "year": item.get("publication_year"),
        "venue": source.get("display_name"),
        "doi": doi or None,
        "openalex": (item.get("ids") or {}).get("openalex"),
        "arxiv": (item.get("ids") or {}).get("arxiv"),
        "type": item.get("type"),
        "verified_against": authority,
    }


def load_existing(path: Path) -> dict[str, dict]:
    if not path.is_file():
        return {}
    works = json.loads(path.read_text(encoding="utf-8")).get("works", [])
    return {work["key"]: work for work in works}


def build(known: dict[str, dict], refresh: frozenset[str]) -> tuple[list[dict],
                                                                    list[str]]:
    """Records for every entry in `WORKS`, querying only what is not known.

    Incremental on purpose. A full re-query is 35 requests against a free API
    that answers 429 when leaned on, and a record that is already correct does
    not become more correct by being fetched again. `--refresh` is how a record
    gets re-checked when there is a reason to doubt it; `--check` is how the
    whole file gets re-checked when the cost is acceptable.
    """
    records: list[dict] = []
    problems: list[str] = []
    for work in WORKS:
        key = work["key"]
        if key in known and key not in refresh:
            cached = dict(known[key])
            # These records predate the fields; they were verified against
            # OpenAlex, which is what the field says. Filling it in is
            # recording what happened, not asserting something new.
            cached.setdefault("verified_against", "openalex")
            cached.setdefault("arxiv", None)
            cached["theme"] = work["theme"]
            records.append(cached)
            continue

        try:
            item, why = pick(fetch(work["query"]), work)
        except RuntimeError as error:
            # One authority being unreachable is not a reason to lose the run.
            # The other authority is a different host, and the records already
            # recorded are unaffected — the entry is simply reported as
            # unverified, which is the honest state.
            item, why = None, str(error)
        authority = "openalex"
        if item is None:
            # Second authority, not a second guess: arXiv's own record of an
            # arXiv preprint, checked against the same expectation.
            try:
                fallback, _ = pick(fetch_arxiv(work["title"]), work)
            except RuntimeError:
                fallback = None
            if fallback is not None:
                item, authority = fallback, "arxiv"
        if item is None:
            problems.append(f"{key}: {why}")
            continue
        records.append(record(work, item, authority))
        # One request per second. OpenAlex's published limit is higher, but the
        # whole run is a handful of queries and finishing a minute sooner is
        # worth nothing against being rate-limited halfway through.
        time.sleep(1.0)
    return records, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true",
                        help="verify the committed file matches the "
                             "authorities today, and change nothing")
    parser.add_argument("--refresh", nargs="*", metavar="KEY", default=[],
                        help="re-query these keys even though they are already "
                             "recorded; pass with no keys to re-query all")
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    args = parser.parse_args(argv)

    known = load_existing(args.out)
    if args.refresh == [] and "--refresh" in (argv or sys.argv[1:]):
        refresh = frozenset(work["key"] for work in WORKS)
    else:
        refresh = frozenset(args.refresh)
    if args.check:
        refresh = frozenset(work["key"] for work in WORKS)

    pending = sum(1 for work in WORKS
                  if work["key"] not in known or work["key"] in refresh)
    print(f"\n  {len(WORKS)} works, {len(known)} already recorded, "
          f"{pending} to query\n")

    records, problems = build(known, refresh)

    for problem in problems:
        print(f"  UNVERIFIED  {problem}")

    payload = json.dumps({"works": records},
                         indent=2, ensure_ascii=False) + "\n"

    if args.check:
        if not args.out.is_file():
            print(f"\n  FAIL  {args.out} does not exist")
            return 1
        current = args.out.read_text(encoding="utf-8")
        if current != payload:
            print(f"\n  FAIL  {args.out.name} is stale — re-run without "
                  "--check and review the diff")
            return 1
        print(f"\n  PASS  {len(records)} records match their authorities")
        return 0 if not problems else 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(payload, encoding="utf-8")
    arxiv = sum(1 for r in records if r["verified_against"] == "arxiv")
    print(f"\n  wrote {args.out.relative_to(ROOT)}  "
          f"({len(records)} verified, {arxiv} of them against arXiv, "
          f"{len(problems)} unverified)")
    if problems:
        print("  Correct the expectation from the record, never the record "
              "from the expectation.")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
