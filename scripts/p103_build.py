"""P103 — count the transfer cameras with the frozen detector, one corpus per camera.

    python scripts/p103_build.py

Implements the data side of
`experiments/results/bellevue_pilot/PREREGISTRATION_P103.md` (Amendment 1
locks the lanes). For every enumerated file it writes that camera's reviewed
lanes keyed to the file, and runs `build_corpus.py` on the file alone with
P97's frozen detector settings and `--split-mode none` (P98). It then
concatenates each camera's files into `data/corpus_p103/<camera>/`. Windows
are cut per file later, so none spans two files.

The detector is exactly P97/P98's (ITD-xl, conf 0.45, imgsz 992, step 2 s),
read from the frozen P97 corpus manifest rather than retyped. A camera is
identified by the filename, never by the folder it sits in.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

FROZEN = Path("data/corpus_bellevue_3lane")
WEIGHTS = Path("models/external/best_xl_ITD_v1.2.pt")
LANES = Path("data/_bellevue/p103/lanes_reviewed")
FILES = Path("data/_bellevue/p103/files.txt")
PARTS = Path("data/_bellevue/p103/parts")
PER_FILE_LANES = Path("data/_bellevue/p103/lanes_per_file")
OUT = Path("data/corpus_p103")


def camera_of(path: Path) -> str:
    return re.search(r"Bellevue_(.+?)__", path.name).group(1)


def read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    from scripts import build_corpus

    frozen = json.loads((FROZEN / "manifest.json").read_text(encoding="utf-8"))
    files = [Path(p) for p in FILES.read_text(encoding="utf-8").split() if p]
    PER_FILE_LANES.mkdir(parents=True, exist_ok=True)
    for f in files:
        spec = json.loads((LANES / f"{camera_of(f)}.json").read_text(encoding="utf-8"))
        spec = dict(spec, clip=f.name,
                    derived_from=f"{camera_of(f)}.json, unchanged (P103 Amendment 1)")
        (PER_FILE_LANES / f"{f.stem}.json").write_text(json.dumps(spec, indent=2),
                                                      encoding="utf-8")

    for f in files:
        part = PARTS / f.stem
        if (part / "counts.csv").exists():
            print(f"  {f.stem}: built")
            continue
        try:
            build_corpus.main([
                "--clips", str(f), "--lanes-dir", str(PER_FILE_LANES),
                "--weights", str(WEIGHTS), "--conf", str(frozen["conf"]),
                "--imgsz", str(frozen["imgsz"]), "--step-s", str(frozen["step_s"]),
                "--timesteps", str(frozen["T"]), "--horizon-s", str(frozen["horizon_s"]),
                "--stride-s", str(frozen["stride_s"]), "--split-mode", "none",
                "--exclude", "--out", str(part)])
        except SystemExit as refusal:
            # A refused file is an exclusion, recorded below, not a crash.
            print(f"  {f.stem}: REFUSED by build_corpus: {refusal}")

    by_camera: dict[str, list[Path]] = {}
    for f in files:
        by_camera.setdefault(camera_of(f), []).append(f)
    for camera, members in sorted(by_camera.items()):
        counts, detections, samples, rejected = [], [], {}, []
        for f in members:
            part = PARTS / f.stem
            if not (part / "counts.csv").exists():
                rejected.append(f.stem)          # refused by build_corpus (e.g. P17)
                continue
            m = json.loads((part / "manifest.json").read_text(encoding="utf-8"))
            assert m["detector"] == WEIGHTS.name and m["conf"] == frozen["conf"]
            counts += read(part / "counts.csv")
            detections += read(part / "detections.csv")
            samples.update(m["samples_per_clip"])
        root = OUT / camera
        root.mkdir(parents=True, exist_ok=True)
        write(root / "counts.csv", counts)
        write(root / "detections.csv", detections)
        lanes = json.loads((LANES / f"{camera}.json").read_text(encoding="utf-8"))
        (root / "manifest.json").write_text(json.dumps({
            "camera": camera, "lanes": [l["name"] for l in lanes["lanes"]],
            "lane_centres": lanes["lanes"], "max_radius": lanes["max_radius"],
            "detector": WEIGHTS.name, "conf": frozen["conf"], "imgsz": frozen["imgsz"],
            "step_s": frozen["step_s"], "samples_per_clip": samples,
            "rejected_files": rejected,
            "protocol": "experiments/results/bellevue_pilot/PREREGISTRATION_P103.md",
        }, indent=2), encoding="utf-8")
        print(f"  {camera}: {len(samples)} file(s), {len(counts)} samples"
              + (f", REJECTED {rejected}" if rejected else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
