"""P98 — build the evaluation corpus from new hours of the P97 camera, frozen.

    python scripts/p98_build.py --clips data/_bellevue/p98_set --out data/corpus_p98

Implements the "building the evaluation windows" half of
`experiments/results/bellevue_pilot/PREREGISTRATION_P98.md`. Nothing here is a
choice: the detector, its operating point, the three reviewed lanes, the step
and the window geometry are P97's, read from P97's own corpus manifest and
lane file rather than retyped.

**Why per file.** Each hourly file is built on its own with `--split-mode
none` (P98 trains nothing and reads no split) and the parts are concatenated.
A part is the detector's expensive pass over one hour, so a failure later in
the run costs one file rather than all of them. Counting is per frame and per
file, so concatenating parts is exact; no window spans two files because
windows are cut per clip, in `p98_eval.py`.

**Same camera, checked rather than assumed.** A filename does not identify a
camera (the user's copies of these files sit in a folder named for another
one). Each file's mid-frame scene signature is compared with P97's footage and
the similarity is written to the provenance file. Lanes are frozen, so a file
from a moved camera would be counted through the wrong regions.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

P97_CORPUS = Path("data/corpus_bellevue_3lane")
P97_LANES = Path("data/_bellevue/lanes_reviewed_3lane/"
                 "Bellevue_NE8th_2017-09-11_15-08_to_17-08.json")
P97_VIDEO = Path("data/_bellevue/Bellevue_Bellevue_NE8th__2017-09-11_16-08-32.mp4")
WEIGHTS = Path("models/external/best_xl_ITD_v1.2.pt")


def mid_signature(path: Path):
    import cv2

    from mfstnet.corpus.identity import scene_signature

    capture = cv2.VideoCapture(str(path))
    capture.set(cv2.CAP_PROP_POS_FRAMES,
                int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) // 2)
    ok, frame = capture.read()
    capture.release()
    if not ok:
        raise SystemExit(f"{path}: could not read a mid-frame")
    return scene_signature(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--clips", type=Path, required=True,
                        help="directory holding exactly the P98 hourly files")
    parser.add_argument("--out", type=Path, default=Path("data/corpus_p98"))
    parser.add_argument("--parts", type=Path, default=Path("data/_bellevue/p98_parts"))
    parser.add_argument("--lanes-dir", type=Path, default=Path("data/_bellevue/lanes_p98"))
    args = parser.parse_args(argv)

    from mfstnet.corpus.identity import similarity
    from scripts import build_corpus
    from scripts.p98_eval import stratum

    frozen = json.loads((P97_CORPUS / "manifest.json").read_text(encoding="utf-8"))
    reference_lanes = json.loads(P97_LANES.read_text(encoding="utf-8"))
    clips = sorted(c for c in args.clips.glob("*.mp4") if stratum(c.stem) != "excluded")
    if not clips:
        raise SystemExit(f"no P98 clip under {args.clips}")

    # The P97 lanes, keyed to each file. Frozen by the protocol, so the only
    # change is the key build_corpus matches on.
    args.lanes_dir.mkdir(parents=True, exist_ok=True)
    for clip in clips:
        spec = dict(reference_lanes, clip=clip.name, surveyed_from=str(P97_VIDEO))
        spec["derived_from"] = (f"{P97_LANES.name}, unchanged: P98 freezes the "
                                f"three-lane geometry (PREREGISTRATION_P98.md)")
        (args.lanes_dir / f"{clip.stem}.json").write_text(
            json.dumps(spec, indent=2), encoding="utf-8")

    reference = mid_signature(P97_VIDEO)
    camera = {c.stem: round(similarity(reference, mid_signature(c)), 4) for c in clips}

    for clip in clips:
        part = args.parts / clip.stem
        if (part / "counts.csv").exists():
            print(f"  {clip.stem}: built")
            continue
        build_corpus.main([
            "--clips", str(clip), "--lanes-dir", str(args.lanes_dir),
            "--weights", str(WEIGHTS), "--conf", str(frozen["conf"]),
            "--imgsz", str(frozen["imgsz"]), "--step-s", str(frozen["step_s"]),
            "--timesteps", str(frozen["T"]), "--horizon-s", str(frozen["horizon_s"]),
            "--stride-s", str(frozen["stride_s"]), "--split-mode", "none",
            "--low-max", str(frozen["low_max"]), "--med-max", str(frozen["med_max"]),
            "--exclude", "--out", str(part)])

    counts, detections, sequences = [], [], []
    by_clip, samples = {}, {}
    for clip in clips:
        part = args.parts / clip.stem
        counts += read_csv(part / "counts.csv")
        detections += read_csv(part / "detections.csv")
        sequences += read_csv(part / "sequences.csv")
        manifest = json.loads((part / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["detector"] == WEIGHTS.name and manifest["conf"] == frozen["conf"]
        assert manifest["lane_centres"] == frozen["lane_centres"], clip
        by_clip.update(manifest["lane_centres_by_clip"])
        samples.update(manifest["samples_per_clip"])

    args.out.mkdir(parents=True, exist_ok=True)
    write_csv(args.out / "counts.csv", counts)
    write_csv(args.out / "detections.csv", detections)
    write_csv(args.out / "sequences.csv", sequences)
    manifest = {key: frozen[key] for key in (
        "lanes", "lane_centres", "max_radius", "T", "step_s", "horizon_s",
        "stride_s", "detector", "conf", "imgsz", "low_max", "med_max")}
    manifest.update({
        "clips": sorted(samples), "samples_per_clip": samples,
        "lane_centres_by_clip": by_clip, "splits": None,
        "split_mode": "none",
        "auto_labelled": True, "frozen_from": str(P97_CORPUS),
        "camera_similarity_to_p97": camera,
        "protocol": "experiments/results/bellevue_pilot/PREREGISTRATION_P98.md",
    })
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2),
                                            encoding="utf-8")
    print(f"\n  wrote {args.out}: {len(clips)} file(s), {len(counts)} samples")
    for name, value in camera.items():
        print(f"  {name:<48} similarity to P97 footage {value:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
