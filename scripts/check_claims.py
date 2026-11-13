"""Every scope claim the paper makes, checked against the corpus (P64).

    python scripts/check_claims.py

[P58](../docs/00-planning/PRD-CHANGELOG.md) found a British motorway supplying
41% of the evaluation corpus for a project about unstructured Indian traffic. It
was found by *looking at the footage*, after that check had been skipped four
times. [P61](../docs/00-planning/PRD-CHANGELOG.md) turned that one question into
a gate.

The question generalises, and that is the point of this script:

> the paper claims X — does the corpus contain X?

Viewpoint, traffic type, class coverage, camera count, licence releasability:
each is a sentence a reviewer can check, each is a place the project can be
caught, and each is machine-checkable against artifacts already on disk. They
live in `docs/00-planning/CLAIMS.yaml` written **as the sentences they would
appear as in the paper**, so what is being asserted is legible without reading
any code.

**`asserted` claims block. `aspirational` ones report.** The distinction is
deliberate and the promotion is a diff: a claim cannot drift from intended to
stated without someone editing the file.

Exit 1 on any failing `asserted` claim, so the paper cannot be built over one.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

from mfstnet.corpus.composition import CameraRegistry, compose  # noqa: E402

CLAIMS = Path("docs/00-planning/CLAIMS.yaml")
FOLDS = Path("data/corpus_loco")
CLASSES = ("LOW", "MEDIUM", "HIGH")


def fold_rows(folds: Path) -> list[tuple[str, list[dict]]]:
    """(fold name, sequence rows) for every fold view on disk."""
    found = []
    for directory in sorted(folds.glob("fold*")):
        path = directory / "sequences.csv"
        if not path.is_file():
            continue
        with path.open(encoding="utf-8", newline="") as handle:
            found.append((directory.name, list(csv.DictReader(handle))))
    return found


def windows_in_test_split(rows: list[dict]) -> Counter:
    """Named to avoid the `test_` prefix on purpose: pytest collects any
    imported callable starting with it, and a helper hijacking the collector is
    a defect that only shows up once someone imports the module."""
    return Counter(row["clip_id"] for row in rows if row["split"] == "test")


def lane_labels(rows: list[dict], split: str) -> Counter:
    lanes = [k for k in rows[0] if k.startswith("label_lane_")]
    return Counter(row[lane] for row in rows if row["split"] == split
                   for lane in lanes)


# --------------------------------------------------------------- checks --
# Each returns (passed, detail). Detail is printed whether it passed or not,
# because a claim that passes for a reason worth knowing is still worth stating.


def evaluation_contains_target_domain(claim, registry, folds):
    off, on = [], []
    for name, rows in folds:
        composition = compose(registry, windows_in_test_split(rows))
        (on if composition.matches_claim else off).append(name)
    target = f"{registry.target.get('country')} / {registry.target.get('traffic_type')}"
    if off:
        return False, (f"{len(off)} of {len(folds)} fold(s) have no on-target "
                       f"camera in test: {', '.join(off)}. Target is {target}.")
    return True, f"every fold's test camera is on target ({target})"


def every_camera_is_elevated(claim, registry, folds):
    wrong = sorted(name for name, entry in registry.cameras.items()
                   if entry.get("viewpoint") not in ("elevated", "unknown"))
    unknown = sorted(name for name, entry in registry.cameras.items()
                     if entry.get("viewpoint") == "unknown")
    if wrong:
        return False, f"not elevated: {', '.join(c[:40] for c in wrong)}"
    if unknown:
        return True, (f"no camera is known to be non-elevated, but "
                      f"{len(unknown)} has an undetermined viewpoint — "
                      f"the claim rests on fewer cameras than it appears to")
    return True, "every camera declared elevated"


def every_class_has_test_support(claim, registry, folds):
    minimum = claim.get("minimum_support", 1)
    thin = []
    for name, rows in folds:
        counts = lane_labels(rows, "test")
        for label in CLASSES:
            if counts[label] < minimum:
                thin.append(f"{name}:{label}={counts[label]}")
    if thin:
        return False, (f"below {minimum} support in test: {', '.join(thin)}. "
                       f"A class the paper reports must be estimable on the "
                       f"split it is reported from.")
    return True, f"every class has at least {minimum} test windows in every fold"


def enough_eligible_cameras(claim, registry, folds):
    wanted = claim.get("minimum_cameras", 1)
    cameras = {name for _, rows in folds for name in windows_in_test_split(rows)}
    if len(cameras) < wanted:
        return False, (f"{len(cameras)} camera(s) serve as a test fold, against "
                       f"{wanted} claimed")
    return True, f"{len(cameras)} camera(s) serve as a test fold"


def every_camera_licence_permits_release(claim, registry, folds):
    allowed = set(claim.get("allowed_licences", []))
    blocked = sorted((name, entry.get("licence", "undeclared"))
                     for name, entry in registry.cameras.items()
                     if entry.get("licence") not in allowed)
    if blocked:
        return False, (f"{len(blocked)} of {len(registry.cameras)} camera(s) "
                       f"carry a licence that does not permit release, e.g. "
                       f"{blocked[0][1]}")
    return True, "every camera's licence permits release"


CHECKS = {fn.__name__: fn for fn in (
    evaluation_contains_target_domain,
    every_camera_is_elevated,
    every_class_has_test_support,
    enough_eligible_cameras,
    every_camera_licence_permits_release,
)}


#: Claims about what the *evaluation* shows. Under the headline protocol
#: (P86, ADR-025) all three are scoped together: moving only `domain` to the
#: Indian folds would leave `camera_count` passing on three Bangladeshi cameras
#: and a British motorway, under a headline that contains none of them.
EVALUATION_CHECKS = (
    "evaluation_contains_target_domain",
    "every_class_has_test_support",
    "enough_eligible_cameras",
)

HEADLINE = "headline"


def headline_folds(registry: CameraRegistry, folds):
    """Folds whose every test camera is declared on target.

    `is_on_target` returning None — undeclared or unknown — keeps a fold out:
    a camera nobody has inspected is not evidence for the Indian headline.
    """
    kept = []
    for name, rows in folds:
        cameras = windows_in_test_split(rows)
        if cameras and all(registry.is_on_target(c) is True for c in cameras):
            kept.append((name, rows))
    return kept


def run(claims: list[dict], registry: CameraRegistry, folds) -> list[dict]:
    results = []
    for claim in claims:
        check = CHECKS.get(claim["check"])
        if check is None:
            results.append({**claim, "passed": False,
                            "detail": f"no checker named {claim['check']!r}"})
            continue
        scoped = folds
        if claim.get("scope") == HEADLINE:
            scoped = headline_folds(registry, folds)
            if not scoped:
                # The vacuity guard. "Every fold's test camera is on target"
                # is TRUE over zero folds, and that is exactly the state the
                # corpus is in today. A claim over an empty set is not
                # evidence, so it fails rather than passing by default.
                target = (f"{registry.target.get('country')} / "
                          f"{registry.target.get('traffic_type')}")
                results.append({**claim, "passed": False, "detail": (
                    f"no fold is in the headline scope: none of "
                    f"{len(folds)} fold(s) has a test camera on target "
                    f"({target}). A claim over an empty set is not evidence.")})
                continue
        passed, detail = check(claim, registry, scoped)
        if claim.get("scope") == HEADLINE:
            detail = f"[headline: {len(scoped)} of {len(folds)} folds] {detail}"
        results.append({**claim, "passed": passed, "detail": detail})
    return results


def with_protocol(claims: list[dict], protocol: str | None) -> list[dict]:
    """Preview a protocol without editing CLAIMS.yaml.

    `--protocol headline` scopes every evaluation claim to the headline folds,
    which is what ADR-025 proposes. It changes what is *printed*, never the
    file, so the claims of record stay what was signed.
    """
    if protocol != HEADLINE:
        return claims
    return [{**c, "scope": HEADLINE} if c["check"] in EVALUATION_CHECKS else c
            for c in claims]


def main(argv: list[str] | None = None) -> int:
    import yaml

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--claims", type=Path, default=CLAIMS)
    parser.add_argument("--folds", type=Path, default=FOLDS)
    parser.add_argument("--cameras", type=Path, default=Path("data/cameras.json"))
    parser.add_argument("--protocol", choices=[HEADLINE], default=None,
                        help="preview the claims under a proposed evaluation "
                             "protocol without editing CLAIMS.yaml (ADR-025)")
    args = parser.parse_args(argv)

    claims = yaml.safe_load(args.claims.read_text(encoding="utf-8"))["claims"]
    registry = CameraRegistry.load(args.cameras)
    folds = fold_rows(args.folds)
    if not folds:
        raise SystemExit(
            f"no fold views under {args.folds}. Build them with "
            f"scripts/resplit_corpus.py — a claim about the evaluation cannot "
            f"be checked without one."
        )

    claims = with_protocol(claims, args.protocol)
    if args.protocol:
        print(f"  PREVIEW under protocol {args.protocol!r} — CLAIMS.yaml is "
              f"unchanged and this is not the claim of record.\n")
    results = run(claims, registry, folds)
    blocking = [r for r in results if r["status"] == "asserted" and not r["passed"]]

    print(f"  {len(claims)} claim(s) against {len(folds)} fold(s)\n")
    for result in results:
        mark = ("  ok  " if result["passed"]
                else " FAIL " if result["status"] == "asserted" else " note ")
        print(f"[{mark}] {result['id']}: {result['sentence'].strip()}")
        print(f"         {result['detail']}")
        if not result["passed"] and result["status"] == "aspirational":
            print("         aspirational — reported, not blocking. Promoting it "
                  "is a diff.")
        print()

    if blocking:
        print(f"  {len(blocking)} ASSERTED CLAIM(S) FAIL. The paper cannot be "
              f"built over these:")
        for result in blocking:
            print(f"    {result['id']} — {result['sentence'].strip()}")
        return 1
    print("  every asserted claim holds against the corpus on disk")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
