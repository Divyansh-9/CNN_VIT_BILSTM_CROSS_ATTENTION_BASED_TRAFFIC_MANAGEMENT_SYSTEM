"""Write a camera profile, and record evidence in one (ADR-028, D31).

    python scripts/camera_profile.py make --lanes-file data/_bellevue/p103/lanes_reviewed/150th_Eastgate.json \\
        --camera 150th_Eastgate --lane-map lane_0=N lane_1=S lane_2=E lane_3=W \\
        --placed-by "project owner" --how "calibration-hour frames" --record "PREREGISTRATION_P103.md, Amendment 1"
    python scripts/camera_profile.py record cameras/150th_Eastgate.json --kind direction --how frame \\
        --by "<name>" --date 2026-11-01 --note "lane_0 is ..."

`make` takes a reviewed lane file or a corpus manifest, as the edge does, and never
marks a direction verified: a new profile says `declared`. `record` is the one way to
add evidence. It computes what the evidence binds, so nobody writes a hash by hand,
and direction evidence is what moves a camera to `verified`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from edge.profile import BINDS, PROFILES, SCHEMA_VERSION, ProfileError, binding, load_profile  # noqa: E402
from scripts.console import use_utf8  # noqa: E402

use_utf8()

__all__ = ["main", "make_profile", "record_evidence"]

DEFAULT_SPEC = "experiments/results/bellevue_pilot/persistence_v1.json"


def lanes_from(path: Path) -> tuple[list[dict], float]:
    """The same two shapes `edge.run.load_lanes` accepts."""
    spec = json.loads(path.read_text(encoding="utf-8"))
    if "lane_centres" in spec:
        entries = spec["lane_centres"]
    elif spec.get("reviewed"):
        entries = spec["lanes"]
    else:
        raise ProfileError(f"{path} is not a reviewed lane file or a corpus manifest (P23)")
    return ([{"name": e["name"], "centre": list(e["centre"])} for e in entries], float(spec.get("max_radius", 0.25)))


def make_profile(args, root: Path = ROOT) -> dict:
    lanes, radius = lanes_from(args.lanes_file)
    lane_map = dict(item.split("=", 1) for item in args.lane_map)
    return {
        "schema_version": SCHEMA_VERSION,
        "camera_id": args.camera,
        "geometry": {"coordinates": "normalised_image", "max_radius": radius, "lanes": lanes},
        "lane_map": lane_map,
        "calibration": {"persistence_spec": args.spec,
                        "spec_sha256": hashlib.sha256((root / args.spec).read_bytes()).hexdigest(),
                        "key": args.key or args.camera},
        "limitations": list(args.limitation or []),
        "provenance": {"placed_by": args.placed_by, "how": args.how, "record": args.record},
        "direction": {"status": "declared"},
        "evidence": [],
    }


def write(path: Path, profile: dict, root: Path = ROOT) -> None:
    """Refuses to leave an invalid profile behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    before = path.read_bytes() if path.exists() else None
    path.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        load_profile(path, root)
    except ProfileError:
        if before is None:
            path.unlink()
        else:
            path.write_bytes(before)
        raise


def record_evidence(path: Path, kind: str, *, how: str, by: str, date: str, note: str, ref: str = "",
                    root: Path = ROOT) -> dict:
    """Append evidence bound to the configuration as it stands now."""
    profile = load_profile(path, root)
    raw = json.loads(json.dumps(profile.raw))
    if kind == "live" and not ref:
        raise ProfileError("live evidence must name its S65 report: only S65 qualifies a stream")
    entry = {"kind": kind, "binds": binding(raw, kind), "how": how, "by": by, "date": date, "note": note}
    if ref:
        entry["ref"] = ref
    raw["evidence"].append(entry)
    if kind == "direction":
        raw["direction"]["status"] = "verified"
    write(path, raw, root)
    return entry


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    mk = sub.add_parser("make", help="write a new profile")
    mk.add_argument("--camera", required=True)
    mk.add_argument("--lanes-file", type=Path, required=True)
    mk.add_argument("--lane-map", nargs="+", required=True, metavar="LANE=DIR")
    mk.add_argument("--spec", default=DEFAULT_SPEC, help="the persistence spec holding this camera's thresholds")
    mk.add_argument("--key", help="this camera's key in that spec; default --camera")
    mk.add_argument("--limitation", action="append", help="a known weakness; repeat for several")
    mk.add_argument("--placed-by", required=True)
    mk.add_argument("--how", required=True)
    mk.add_argument("--record", required=True, help="where the placement is recorded")
    mk.add_argument("--out", type=Path, default=PROFILES)
    rec = sub.add_parser("record", help="record evidence against a profile")
    rec.add_argument("profile", type=Path)
    rec.add_argument("--kind", choices=sorted(BINDS), required=True)
    rec.add_argument("--how", required=True, help="frame means the footage was looked at")
    rec.add_argument("--by", required=True)
    rec.add_argument("--date", required=True)
    rec.add_argument("--note", required=True)
    rec.add_argument("--ref", default="", help="the report or run this rests on")
    args = ap.parse_args(argv)
    try:
        if args.command == "make":
            path = args.out / f"{args.camera}.json"
            if path.exists():
                ap.error(f"{path} exists: a profile is not silently replaced")
            write(path, make_profile(args))
            print(f"wrote {path}: direction declared, no evidence yet")
        else:
            entry = record_evidence(args.profile, args.kind, how=args.how, by=args.by, date=args.date,
                                    note=args.note, ref=args.ref)
            print(f"recorded {entry['kind']} evidence in {args.profile}, bound to {entry['binds'][:12]}")
    except ProfileError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
