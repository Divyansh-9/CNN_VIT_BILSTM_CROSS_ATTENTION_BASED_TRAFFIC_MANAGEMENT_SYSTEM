"""Train/serve count parity: the deployed edge against the offline corpus (P143).

    python scripts/count_parity.py --clips-root D:/bellevue
    python scripts/count_parity.py --clips-root D:/bellevue --camera 150th_Eastgate --samples 150

The persistence and ridge forecasters were calibrated and trained on
`data/corpus_p103/<camera>/counts.csv` (P103, P105). The deployed edge must feed
them the same numbers from the same footage, or every forecast it publishes is
made on inputs the forecasters never saw.

**Online** is the edge's own code, not a re-implementation of it:
- `edge.run.file_frames`, the edge's frame sampler;
- `edge.run.YoloDetector`;
- `count_frame`, at the settings the edge reads from `class_mapping.yaml`.

**Offline** is the committed corpus counts.

A clip passes only if every lane value and every timestamp is identical, and
both sides hold the same number of samples. "Close" is not parity.

Frames are decoded, counted and dropped in memory. Nothing but counts is
written (NFR-13). The footage path is an argument and is never recorded:
results name clips by id.

`--mutate-conf` counts at a different confidence on purpose. It exists to show
that this comparison detects a real configuration skew, and it never writes
over the real results.
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

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "data" / "corpus_p103"
CAMERAS = ("150th_Eastgate", "150th_Newport", "150th_SE38th")
OUT = ROOT / "experiments" / "results" / "bellevue_pilot" / "count_parity"


def compare(online: list[tuple[float, list[int]]],
            offline: list[tuple[float, list[int]]]) -> dict:
    """Sample by sample: equal counts, equal timestamps, equal length."""
    paired = list(zip(online, offline))
    values = [(a, b) for (_, on), (_, off) in paired for a, b in zip(on, off)]
    exact_values = sum(a == b for a, b in values)
    return {
        "samples_online": len(online),
        "samples_offline": len(offline),
        "lane_values": len(values),
        "exact_lane_values": exact_values,
        "exact_samples": sum(on == off for (_, on), (_, off) in paired),
        "timestamps_match": all(t_on == t_off for (t_on, _), (t_off, _) in paired),
        "mae_per_lane_value": round(sum(abs(a - b) for a, b in values) / len(values), 6)
        if values else None,
        "parity": bool(values) and exact_values == len(values) and len(online) == len(offline)
        and all(t_on == t_off for (t_on, _), (t_off, _) in paired),
    }


def offline_counts(camera: str, lanes: tuple[str, ...]) -> dict[str, list[tuple[float, list[int]]]]:
    clips: dict[str, list[tuple[int, float, list[int]]]] = {}
    with (CORPUS / camera / "counts.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            clips.setdefault(row["clip_id"], []).append(
                (int(row["sample"]), float(row["t_s"]), [int(row[f"count_{n}"]) for n in lanes]))
    return {c: [(t, v) for _, t, v in sorted(rows)] for c, rows in clips.items()}


def main(argv: list[str] | None = None) -> int:
    from edge.run import YoloDetector, file_frames, load_counting, load_lanes
    from experiments.provenance import write_sidecar
    from mfstnet.corpus.counting import count_frame

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--clips-root", type=Path, required=True,
                    help="folder searched recursively for <clip_id>.mp4; never recorded")
    ap.add_argument("--camera", action="append", choices=CAMERAS,
                    help="repeatable; default every P103 camera")
    ap.add_argument("--samples", type=int, help="stop each clip after this many samples")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--mutate-conf", type=float,
                    help="VERIFICATION ONLY: count at this confidence, to show skew is detected")
    args = ap.parse_args(argv)
    if args.mutate_conf is not None and args.out.resolve() == OUT.resolve():
        ap.error("--mutate-conf must write elsewhere: pass --out")

    weights, conf, imgsz = load_counting(ROOT / "indiatrafficnet" / "class_mapping.yaml")
    detector = YoloDetector(weights, conf, imgsz)
    count_conf = conf if args.mutate_conf is None else args.mutate_conf
    args.out.mkdir(parents=True, exist_ok=True)
    footage = {p.stem: p for p in args.clips_root.rglob("*.mp4")}
    summary, failed = [], 0
    for camera in args.camera or CAMERAS:
        manifest = json.loads((CORPUS / camera / "manifest.json").read_text(encoding="utf-8"))
        if (manifest["detector"], manifest["conf"], manifest["imgsz"]) != (weights.name, conf, imgsz):
            print(f"{camera}: the edge's counting settings differ from the corpus manifest's")
            return 1
        lanes = load_lanes(CORPUS / camera / "manifest.json")
        for clip_id, offline in offline_counts(camera, lanes.names).items():
            if clip_id not in footage:
                print(f"{clip_id}: footage not found under --clips-root")
                summary.append({"camera": camera, "clip_id": clip_id, "parity": False,
                                "note": "footage not found"})
                failed += 1
                continue
            if args.samples:
                offline = offline[:args.samples]
            online = []
            for k, (ts, frame) in enumerate(file_frames(str(footage[clip_id]))):
                if args.samples and k >= args.samples:
                    break
                counts = count_frame(detector(frame), lanes, min_confidence=count_conf)
                del frame                                    # NFR-13
                online.append((float(ts), [int(counts.per_lane.get(n, 0)) for n in lanes.names]))
            result = compare(online, offline)
            failed += not result["parity"]
            summary.append({"camera": camera, "clip_id": clip_id, **result, "note": ""})
            with (args.out / f"{clip_id}.csv").open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["sample", "t_online", "t_offline",
                            *[f"online_{n}" for n in lanes.names], *[f"offline_{n}" for n in lanes.names]])
                for k in range(max(len(online), len(offline))):
                    t_on, on = online[k] if k < len(online) else ("", [""] * len(lanes.names))
                    t_off, off = offline[k] if k < len(offline) else ("", [""] * len(lanes.names))
                    w.writerow([k, t_on, t_off, *on, *off])
            print(f"{clip_id}: {result['exact_lane_values']}/{result['lane_values']} lane values exact, "
                  f"samples {result['samples_online']}/{result['samples_offline']}, "
                  f"parity {result['parity']}")
    fields = ["camera", "clip_id", "samples_online", "samples_offline", "lane_values",
              "exact_lane_values", "exact_samples", "timestamps_match", "mae_per_lane_value",
              "parity", "note"]
    summary_path = args.out / "summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(summary)
    write_sidecar(summary_path, script="scripts/count_parity.py", weights=weights.name,
                  conf=conf, count_conf=count_conf, imgsz=imgsz, samples_limit=args.samples,
                  mutated=args.mutate_conf is not None)
    print(f"{len(summary) - failed} of {len(summary)} clips at exact parity; {summary_path}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
