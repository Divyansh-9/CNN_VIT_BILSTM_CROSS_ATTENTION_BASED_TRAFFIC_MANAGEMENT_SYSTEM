"""Re-cut an existing corpus's splits without re-running the detector (P49).

    python scripts/resplit_corpus.py --corpus data/corpus --clips data/_corpus_clips \
        --protocol loco --fold 0 --out data/corpus_fold0

`build_corpus.py` assigns splits by hashing each camera id. That is
reproducible, and with enough cameras it is fine. The corpus built on
2026-08-21 has seven, and the draw put a UK motorway alone in `test` and a
camera with no HIGH window alone in `val` -- see `mfstnet/corpus/folds.py` for
why both are disqualifying.

Re-cutting a split is a re-derivation, not a rebuild: the split depends on the
camera each window came from and on nothing the detector produced. `counts.csv`
and `detections.csv` are carried over untouched (hardlinked where the filesystem
allows), so a fold view costs a few kilobytes and a second, and every downstream
tool -- `audit_corpus.py` included -- reads it exactly as it reads a corpus.
This is the same argument `relabel_corpus.py` makes for thresholds and P28 makes
for lane centres: **the expensive artifact is the detections, and everything
downstream of them should re-derive in seconds.**

Camera identity is recomputed here rather than read from the corpus, because a
corpus built before this script existed does not record it. It uses the same
mid-frame scene signature `build_corpus.py` uses, so the grouping is identical.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

from mfstnet.corpus.composition import CameraRegistry  # noqa: E402
from mfstnet.corpus.folds import (  # noqa: E402
    MINIMUM_TEST_SEQUENCES,
    eligible_for_test,
    leave_one_camera_out,
)

CARRIED = ("counts.csv", "detections.csv")

#: Which cameras a fold view may contain, by partition (ADR-025, P86).
#: `mixed` is every camera, partitioned or not: it reproduces the folds every
#: committed result was produced on, and is the default for that reason.
#: `foreign` and `india` are disjoint, so a model trained on one has never seen
#: the other — which is what lets fine-tuning on India be compared against
#: training on India from scratch without the comparison being contaminated.
#: `unknown` cameras belong to no domain and enter only `mixed`.
DOMAINS = {
    "mixed": None,
    "foreign": {"real_external"},
    "india": {"real_india"},
}


def camera_ids(clip_ids, clips_dir: Path) -> dict[str, str]:
    """clip stem -> camera id, by the same signature build_corpus.py uses."""
    import cv2

    from mfstnet.corpus.identity import group_cameras
    from scripts.build_corpus import scene_signature

    signatures = {}
    for path in sorted(clips_dir.glob("*.mp4")):
        if path.stem not in clip_ids:
            continue
        capture = cv2.VideoCapture(str(path))
        capture.set(cv2.CAP_PROP_POS_FRAMES,
                    int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) // 2)
        ok, mid = capture.read()
        capture.release()
        if ok:
            signatures[path.stem] = scene_signature(
                cv2.cvtColor(mid, cv2.COLOR_BGR2GRAY))

    missing = set(clip_ids) - set(signatures)
    if missing:
        raise SystemExit(
            "no video found for " + ", ".join(sorted(missing)[:3])
            + ". Camera identity is read from the footage, so --clips must be "
            "the directory the corpus was built from."
        )
    groups = group_cameras(signatures)
    for clip_id in clip_ids:
        groups.setdefault(clip_id, clip_id)
    return groups


def carry_over(source: Path, destination: Path) -> None:
    """Hardlink if the filesystem allows it, copy if not. Never leave it out."""
    if destination.exists():
        destination.unlink()
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--clips", type=Path, required=True,
                        help="the directory the corpus was built from")
    parser.add_argument("--protocol", choices=("loco",), default="loco")
    parser.add_argument("--domain", choices=sorted(DOMAINS), default="mixed",
                        help="which partition the fold view draws on (ADR-025). "
                             "mixed reproduces every committed result; foreign "
                             "and india are disjoint")
    parser.add_argument("--cameras", type=Path,
                        default=Path("data/cameras.json"))
    parser.add_argument("--fold", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--min-test-sequences", type=int,
                        default=MINIMUM_TEST_SEQUENCES,
                        help="a camera contributing fewer windows than this "
                             "stays in train in every fold. Rotating over all "
                             "seven cameras of the 2026-08-21 corpus produced a "
                             "fold whose test split held ONE sequence")
    parser.add_argument("--list", action="store_true",
                        help="print the fold table and exit, changing nothing")
    args = parser.parse_args(argv)

    with (args.corpus / "sequences.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit(f"{args.corpus}/sequences.csv is empty")

    clip_ids = {row["clip_id"] for row in rows}
    groups = camera_ids(clip_ids, args.clips)

    registry = CameraRegistry.load(args.cameras)
    allowed = DOMAINS[args.domain]
    excluded = sorted({c for c in groups.values()
                       if allowed is not None
                       and registry.partition(c) not in allowed})
    if excluded:
        # Out of the fold view entirely, not parked in a fourth split: a row
        # that is in the file is a row something can count.
        rows = [r for r in rows if groups[r["clip_id"]] not in excluded]
        clip_ids = {row["clip_id"] for row in rows}
        groups = {k: v for k, v in groups.items() if v not in excluded}
        print(f"  domain {args.domain}: {len(excluded)} camera(s) outside it "
              f"are excluded — " + ", ".join(c[:24] for c in excluded))
    if not rows:
        raise SystemExit(
            f"domain {args.domain!r} contains no camera in this corpus. "
            f"Partitions come from {args.cameras}; scripts/check_sources.py "
            f"lists them. Nothing is trained on an empty domain.")
    cameras = sorted(set(groups.values()))

    per_camera: dict[str, int] = {c: 0 for c in cameras}
    for row in rows:
        per_camera[groups[row["clip_id"]]] += 1
    eligible, always_train = eligible_for_test(
        per_camera, minimum=args.min_test_sequences)
    folds = leave_one_camera_out(cameras, always_train=always_train)

    merged = {c: [k for k, v in groups.items() if v == c] for c in cameras}
    print(f"  {len(clip_ids)} clip(s) -> {len(cameras)} camera(s), "
          f"{len(folds)} fold(s)")
    for camera, members in merged.items():
        if len(members) > 1:
            print(f"    {camera[:44]} == " + ", ".join(m[:30] for m in members[1:]))
    if always_train:
        print(f"  always train (under {args.min_test_sequences} windows): "
              + ", ".join(f"{c[:26]} ({per_camera[c]})" for c in always_train))
    if args.list:
        print()
        print("  {:<6}{:<30}{:>6}   {:<30}{:>6}{:>8}".format(
            "fold", "test camera", "n", "val camera", "n", "train"))
        for f in folds:
            print("  {:<6}{:<30}{:>6}   {:<30}{:>6}{:>8}".format(
                f.index, f.test[:28], per_camera[f.test],
                f.val[:28], per_camera[f.val],
                sum(per_camera[c] for c in f.train)))
        return 0

    if not 0 <= args.fold < len(folds):
        raise SystemExit(
            f"--fold {args.fold} is out of range: {len(eligible)} eligible "
            f"camera(s) give folds 0..{len(folds) - 1}. --list shows them."
        )
    fold = folds[args.fold]
    print(f"  fold {fold.index} of {len(folds)}: test={fold.test[:34]}")
    print(f"  {'':>18}val ={fold.val[:34]}")

    for row in rows:
        row["camera_id"] = groups[row["clip_id"]]
        row["split"] = fold.split_of(row["camera_id"])

    args.out.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    with (args.out / "sequences.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    manifest = json.loads((args.corpus / "manifest.json").read_text(encoding="utf-8"))
    manifest["splits"] = {clip: groups and fold.split_of(groups[clip])
                          for clip in sorted(clip_ids)}
    manifest["cameras"] = groups
    # A fold view must never be mistaken for the corpus it came from, or a
    # result carrying fold 3's numbers reads as the whole corpus's.
    manifest["split_protocol"] = args.protocol
    manifest["fold"] = fold.index
    manifest["folds_total"] = len(folds)
    manifest["fold_test_camera"] = fold.test
    manifest["fold_val_camera"] = fold.val
    manifest["fold_always_train"] = always_train
    manifest["min_test_sequences"] = args.min_test_sequences
    manifest["domain"] = args.domain
    manifest["domain_excluded"] = excluded
    manifest["camera_partitions"] = {c: registry.partition(c) for c in cameras}
    manifest["resplit_from"] = str(args.corpus)
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2),
                                            encoding="utf-8")

    for name in CARRIED:
        source = args.corpus / name
        if source.exists():
            carry_over(source, args.out / name)

    tally = {}
    for row in rows:
        tally[row["split"]] = tally.get(row["split"], 0) + 1
    print("  " + "  ".join(f"{k} {v}" for k, v in sorted(tally.items())))
    print(f"  wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
