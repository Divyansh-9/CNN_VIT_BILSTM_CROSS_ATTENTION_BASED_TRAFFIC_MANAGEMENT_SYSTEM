"""P99 — build the block-split corpus, and refuse if any pre-training check fails.

    python scripts/p99_corpus.py

Implements the split in `experiments/results/bellevue_pilot/PREREGISTRATION_P99.md`
from counts that already exist (ITD-xl, three lanes), and writes:

- `data/corpus_p99/`: every window, with its split. **Only the frozen
  evaluator reads it.**
- `data/corpus_p99_trainval/`: the same, with **every test window removed**.
  This is the only corpus training sees (`train_mfstnet.py --no-test`), so no
  run can score, select on, or even load a test label.
- `data/cache_p99/`: the two existing feature caches, hard-linked under one
  manifest. Nothing is re-encoded, and both must carry the same
  preprocessing hash.

**Stops** unless all of these hold, before anything is written:

1. the class support per split equals the pre-registered table exactly;
2. every window's span, inputs and target together, lies inside its block;
3. no sample index is spanned by windows of two different splits;
4. the train/val corpus holds no test window.
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

P98 = Path("data/corpus_p98")
P97 = Path("data/corpus_bellevue_3lane")
CACHES = (Path("data/cache_bellevue"), Path("data/cache_p98"))
OUT, TRAINVAL, CACHE = (Path("data/corpus_p99"), Path("data/corpus_p99_trainval"),
                        Path("data/cache_p99"))
LANES = ("lane_0", "lane_1", "lane_2")
CLASSES = ("LOW", "MEDIUM", "HIGH")
T, K, STRIDE, BLOCK, BLOCKS, HOUR = 60, 30, 15, 300, 6, 1800
SPAN = T + K                       # inputs s … s+59 and target e+1 … e+30
EXPECTED = {"train": (165, 1139, 412), "val": (27, 416, 142), "test": (83, 824, 263)}


def level(x: float) -> str:
    return CLASSES[0 if x <= 2 else (1 if x <= 8 else 2)]


def read_counts(corpus: Path) -> dict[str, list[list[int]]]:
    out: dict[str, list[list[int]]] = {}
    with (corpus / "counts.csv").open(encoding="utf-8") as handle:
        for r in csv.DictReader(handle):
            out.setdefault(r["clip_id"], []).append([int(r["count_" + l]) for l in LANES])
    return out


def hours() -> list[tuple[str, str, int, int]]:
    """(label, clip_id, offset, length), in chronological order."""
    p98, p97 = read_counts(P98), read_counts(P97)
    out = [(c.split("__")[1], c, 0, len(v))
           for c, v in sorted(p98.items(), key=lambda kv: kv[0].split("__")[1])]
    (joined, series), = p97.items()
    assert len(series) == 2 * HOUR, len(series)
    out += [("2017-09-11_15-08-32", joined, 0, HOUR),
            ("2017-09-11_16-08-32", joined, HOUR, HOUR)]
    return out


def build():
    counts = {**read_counts(P98), **read_counts(P97)}
    windows, spans = [], {}
    for h, (label, clip, offset, length) in enumerate(hours()):
        role = {h % BLOCKS: "test", (h + 3) % BLOCKS: "test", (h + 1) % BLOCKS: "val"}
        series = counts[clip]
        for b in range(BLOCKS):
            lo = offset + BLOCK * b
            hi = min(lo + BLOCK, offset + length)
            split = role.get(b, "train")
            for s in range(lo, hi, STRIDE):
                e = s + T - 1
                if s + SPAN - 1 >= hi:
                    continue
                assert lo <= s and e + K < hi, (clip, s)                      # check 2
                w = {"clip_id": clip, "split": split, "start_index": s,
                     "label_index": e + K, "hour": label, "block": f"{label}#{b}"}
                for i, lane in enumerate(LANES):
                    w[f"label_{lane}"] = level(sum(series[x][i] for x in range(e + 1, e + K + 1)) / K)
                windows.append(w)
                for x in range(s, s + SPAN):
                    spans.setdefault((clip, x), set()).add(split)
    return windows, spans


def main() -> int:
    windows, spans = build()

    support = {split: Counter(w[f"label_{l}"] for w in windows if w["split"] == split
                              for l in LANES) for split in EXPECTED}
    table = {split: tuple(support[split][c] for c in CLASSES) for split in EXPECTED}
    for split, expected in EXPECTED.items():                                   # check 1
        print(f"  {split:<5} LOW/MEDIUM/HIGH {table[split]}  pre-registered {expected}")
    if table != EXPECTED:
        raise SystemExit("support differs from PREREGISTRATION_P99.md — STOP, nothing written")

    shared = sum(1 for splits in spans.values() if len(splits) > 1)           # check 3
    if shared:
        raise SystemExit(f"{shared} sample(s) are spanned by two splits — STOP")
    print(f"  every window lies inside its block; 0 of {len(spans)} spanned samples "
          f"are shared between splits")

    trainval = [w for w in windows if w["split"] != "test"]
    assert not any(w["split"] == "test" for w in trainval)                     # check 4

    manifest_p98 = json.loads((P98 / "manifest.json").read_text(encoding="utf-8"))
    manifest_p97 = json.loads((P97 / "manifest.json").read_text(encoding="utf-8"))
    assert manifest_p97["lane_centres"] == manifest_p98["lane_centres"]
    manifest = {key: manifest_p98[key] for key in (
        "lanes", "lane_centres", "max_radius", "T", "step_s", "horizon_s",
        "stride_s", "detector", "conf", "imgsz", "low_max", "med_max")}
    manifest.update({
        "clips": sorted({w["clip_id"] for w in windows}),
        "samples_per_clip": {**manifest_p98["samples_per_clip"],
                             **manifest_p97["samples_per_clip"]},
        "lane_centres_by_clip": {**manifest_p98["lane_centres_by_clip"],
                                 **manifest_p97["lane_centres_by_clip"]},
        "auto_labelled": True, "splits": None, "split_mode": "p99_blocks",
        "split_protocol": "PREREGISTRATION_P99.md: six 10-minute blocks per hour; "
                          "test h%6 and (h+3)%6, val (h+1)%6, train the rest; "
                          "windows wholly inside a block",
        "target": "mean raw vehicle count over the next 30 samples",
        "future_samples": K,
        "support": {split: dict(zip(CLASSES, table[split])) for split in EXPECTED},
        "built_from": [str(P98), str(P97)],
    })

    fields = ["clip_id", "split", "start_index", "label_index",
              *[f"label_{l}" for l in LANES], "hour", "block"]
    for root, rows, note in ((OUT, windows, "all splits; read only by scripts/p99_eval.py"),
                             (TRAINVAL, trainval, "train and val only; test windows removed")):
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True)
        with (root / "sequences.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        with (root / "counts.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = None
            for source in (P98, P97):
                with (source / "counts.csv").open(encoding="utf-8") as src:
                    for r in csv.DictReader(src):
                        if writer is None:
                            writer = csv.DictWriter(handle, fieldnames=list(r))
                            writer.writeheader()
                        writer.writerow(r)
        (root / "manifest.json").write_text(json.dumps({**manifest, "contents": note},
                                                       indent=2), encoding="utf-8")
        print(f"  wrote {root}: {len(rows)} windows")

    merged = None
    if CACHE.exists():
        shutil.rmtree(CACHE)
    CACHE.mkdir(parents=True)
    for source in CACHES:
        m = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
        if merged is None:
            merged, sources = {**m, "clips": {}}, []
        if m["preprocessing_hash"] != merged["preprocessing_hash"]:
            raise SystemExit(f"{source} has preprocessing hash {m['preprocessing_hash']}, "
                             f"not {merged['preprocessing_hash']} (ADR-005) — STOP")
        for key, entry in m["clips"].items():
            os.link(source / entry["file"], CACHE / entry["file"])
            merged["clips"][key] = entry
        sources.append(str(source))
    missing = [c for c in manifest["clips"] if f"corpus/{c}" not in merged["clips"]]
    if missing:
        raise SystemExit(f"no cached features for {missing} — STOP")
    (CACHE / "manifest.json").write_text(json.dumps(merged, indent=2, sort_keys=True),
                                         encoding="utf-8")
    # Beside the manifest, not in it: CacheManifest is strict about its keys.
    (CACHE / "merged_from.json").write_text(json.dumps(sources, indent=2),
                                            encoding="utf-8")
    print(f"  wrote {CACHE}: {len(merged['clips'])} clip(s), hash "
          f"{merged['preprocessing_hash']}, hard-linked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
