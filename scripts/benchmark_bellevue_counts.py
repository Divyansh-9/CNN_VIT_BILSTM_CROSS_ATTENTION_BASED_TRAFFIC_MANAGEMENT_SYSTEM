"""Score detector profiles on visually counted frames from the two Bellevue recordings."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.benchmark_video_counts import infer, score

REFERENCE = Path(__file__).resolve().parents[1] / "experiments/results/bellevue_frame_count_reference.json"


def export_frames(recordings, counts, dimensions, output):
    import cv2

    for label, recording in zip(("morning", "afternoon"), recordings):
        capture = cv2.VideoCapture(str(recording))
        try:
            for name in counts:
                part, seconds = name.split("-")
                if part != label:
                    continue
                capture.set(cv2.CAP_PROP_POS_MSEC, int(seconds) * 1000)
                ok, frame = capture.read()
                if not ok or list(frame.shape[1::-1]) != dimensions:
                    raise ValueError(f"Could not read the expected Bellevue frame at {seconds}s in {recording.name}")
                if not cv2.imwrite(str(output / f"{name}.png"), frame):
                    raise OSError(f"Could not write the frame for {name}")
        finally:
            capture.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--morning", type=Path, required=True)
    parser.add_argument("--afternoon", type=Path, required=True)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--cctv-weights", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    counts = reference["counts"]
    profiles = ((args.weights, 640, .30), (args.weights, 960, .30),
                (args.weights, 1280, .30), (args.cctv_weights, 960, .40))
    results = []
    with TemporaryDirectory(prefix="stms-bellevue-counts-") as directory:
        frames = Path(directory)
        export_frames((args.morning, args.afternoon), counts, reference["frame_size"], frames)
        examples = [(frames / f"{name}.png", count) for name, count in counts.items()]
        for weights, size, confidence in profiles:
            rows, ms = infer(weights, examples, size, region=reference["region_xyxy"])
            results.append({"model": weights.name, "size": size, "confidence": confidence,
                            "milliseconds_per_image": ms, **score(rows, confidence),
                            "predicted_by_frame": {
                                name: sum(value >= confidence for value in confidences)
                                for name, (_, confidences) in zip(counts, rows)
                            }})
    report = {"source": reference["source"], "method": reference["method"],
              "region_xyxy": reference["region_xyxy"], "baseline": results[0], "tuned": results[1],
              "alternatives": results[2:]}
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"baseline": results[0], "tuned": results[1]}), flush=True)


if __name__ == "__main__":
    main()
