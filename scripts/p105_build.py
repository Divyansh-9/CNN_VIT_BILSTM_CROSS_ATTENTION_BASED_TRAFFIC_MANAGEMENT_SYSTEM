"""P105 — count the 16 Option B files with the frozen detector, one corpus per camera.

    python scripts/p105_build.py

Implements the data side of `PREREGISTRATION_P105.md` (Amendments 1–2). The
P103 lanes are frozen for Eastgate, Newport and SE38th; 116th NE12th uses the
lanes locked by Amendment 2. Each file is built alone with P97's frozen
detector settings and `--split-mode none`. A file `build_corpus` refuses is
recorded as an exclusion, never substituted.
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
FILES = Path("experiments/results/bellevue_pilot/p105_files.json")
FOOTAGE = Path("data/_bellevue/p105")
LANES = {"116th_NE12th": Path("data/_bellevue/p105/lanes_reviewed/116th_NE12th.json"),
         **{c: Path(f"data/_bellevue/p103/lanes_reviewed/{c}.json")
            for c in ("150th_Eastgate", "150th_Newport", "150th_SE38th")}}
PARTS = Path("data/_bellevue/p105/parts")
PER_FILE_LANES = Path("data/_bellevue/p105/lanes_per_file")
OUT = Path("data/corpus_p105")


def camera_of(name: str) -> str:
    return re.search(r"Bellevue_(.+?)__", name).group(1)


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
    files = json.loads(FILES.read_text(encoding="utf-8"))["files"]
    PER_FILE_LANES.mkdir(parents=True, exist_ok=True)
    for f in files:
        spec = json.loads(LANES[f["camera"]].read_text(encoding="utf-8"))
        spec = dict(spec, clip=f["name"], derived_from=f"{LANES[f['camera']]}, unchanged")
        (PER_FILE_LANES / f"{Path(f['name']).stem}.json").write_text(
            json.dumps(spec, indent=2), encoding="utf-8")

    for f in files:
        part = PARTS / Path(f["name"]).stem
        if (part / "counts.csv").exists():
            print(f"  {f['name']}: built")
            continue
        try:
            build_corpus.main([
                "--clips", str(FOOTAGE / f["name"]), "--lanes-dir", str(PER_FILE_LANES),
                "--weights", str(WEIGHTS), "--conf", str(frozen["conf"]),
                "--imgsz", str(frozen["imgsz"]), "--step-s", str(frozen["step_s"]),
                "--timesteps", str(frozen["T"]), "--horizon-s", str(frozen["horizon_s"]),
                "--stride-s", str(frozen["stride_s"]), "--split-mode", "none",
                "--exclude", "--out", str(part)])
        except SystemExit as refusal:
            print(f"  {f['name']}: REFUSED by build_corpus: {refusal}")

    for camera, lane_file in sorted(LANES.items()):
        members = [f for f in files if f["camera"] == camera]
        counts, detections, samples, rejected = [], [], {}, []
        for f in members:
            part = PARTS / Path(f["name"]).stem
            if not (part / "counts.csv").exists():
                rejected.append(f["name"])
                continue
            m = json.loads((part / "manifest.json").read_text(encoding="utf-8"))
            assert m["detector"] == WEIGHTS.name and m["conf"] == frozen["conf"]
            counts += read(part / "counts.csv")
            detections += read(part / "detections.csv")
            samples.update(m["samples_per_clip"])
        root = OUT / camera
        root.mkdir(parents=True, exist_ok=True)
        if counts:
            write(root / "counts.csv", counts)
            write(root / "detections.csv", detections)
        lanes = json.loads(lane_file.read_text(encoding="utf-8"))
        (root / "manifest.json").write_text(json.dumps({
            "camera": camera, "lanes": [l["name"] for l in lanes["lanes"]],
            "lane_centres": lanes["lanes"], "max_radius": lanes["max_radius"],
            "detector": WEIGHTS.name, "conf": frozen["conf"], "imgsz": frozen["imgsz"],
            "step_s": frozen["step_s"], "samples_per_clip": samples,
            "roles": {f["name"].removesuffix(".mp4"): f["role"] for f in members},
            "rejected_files": rejected,
            "protocol": "experiments/results/bellevue_pilot/PREREGISTRATION_P105.md",
        }, indent=2), encoding="utf-8")
        print(f"  {camera}: {len(samples)} file(s), {len(counts)} samples"
              + (f", REJECTED {rejected}" if rejected else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
