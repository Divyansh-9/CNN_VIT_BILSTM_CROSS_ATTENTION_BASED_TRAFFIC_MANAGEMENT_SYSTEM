"""One camera's configuration, and the evidence bound to it (ADR-028, D31).

A profile, `cameras/<camera_id>.json`, holds a camera's lanes and lane map, and points
at its thresholds by path and hash rather than copying them. It holds no stream URL
and no source: a camera and what feeds it are separate choices.

**Status is derived, never stored.** Evidence records the hash of what it depends on,
so changing a lane voids it with nobody having to remember. A lane map's letters are
labels until direction evidence matches the active configuration.

This is the one loader: the edge, the preflight and the demonstration tools all use
it, so there is one set of rules. It needs only the standard library. What the edge
needs beyond this (the spec's lane count, the forecasters) stays in `edge.run`.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

__all__ = ["CameraProfile", "ProfileError", "binding", "canonical_hash", "load_profile", "load_profiles"]

ROOT = Path(__file__).resolve().parent.parent
PROFILES = ROOT / "cameras"
SCHEMA_VERSION = 1
KEYS = {"schema_version", "camera_id", "geometry", "lane_map", "calibration", "limitations",
        "provenance", "direction", "evidence"}
NAME = re.compile(r"[A-Za-z0-9_-]{1,32}")
APPROACHES = ("N", "S", "E", "W")
DIRECTION_STATUSES = ("declared", "verified", "does_not_apply")
#: What each kind of evidence depends on. A lane map's letters do not change what was
#: counted, so changing them voids direction evidence and leaves the others standing.
BINDS = {"direction": ("geometry", "lane_map"), "replay": ("geometry", "calibration"),
         "live": ("geometry", "calibration")}


class ProfileError(ValueError):
    """A profile that cannot be used, and why."""


def canonical_hash(*sections) -> str:
    """SHA-256 of canonical JSON: sorted keys, no whitespace, UTF-8. So reordering or
    reformatting a file changes nothing."""
    text = json.dumps(list(sections), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def binding(raw: dict, kind: str) -> str:
    return canonical_hash(*(raw[section] for section in BINDS[kind]))


@dataclass(frozen=True)
class CameraProfile:
    path: Path
    camera_id: str
    lanes: tuple[tuple[str, tuple[float, float]], ...]
    max_radius: float
    lane_map: dict[str, str]
    spec_path: Path
    spec_key: str
    limitations: tuple[str, ...]
    direction_status: str
    raw: dict

    def evidence(self, kind: str) -> list[dict]:
        """Only what still matches this configuration."""
        current = binding(self.raw, kind)
        return [e for e in self.raw["evidence"] if e["kind"] == kind and e["binds"] == current]

    def stale_evidence(self, kind: str) -> list[dict]:
        current = binding(self.raw, kind)
        return [e for e in self.raw["evidence"] if e["kind"] == kind and e["binds"] != current]

    @property
    def directions_verified(self) -> bool:
        return self.direction_status == "verified" and bool(self.evidence("direction"))

    @property
    def calibrated_on(self) -> str | None:
        """The hour the thresholds came from, as a clip's name writes it."""
        entry = json.loads(self.spec_path.read_text(encoding="utf-8"))["cameras"][self.spec_key]
        hour = re.search(r"(\d{4}-\d{2}-\d{2}) (\d{2}):(\d{2})", entry.get("source", ""))
        return f"{hour[1]}_{hour[2]}-{hour[3]}" if hour else None


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def load_profile(path, root: Path = ROOT) -> CameraProfile:
    """A valid profile, or ProfileError naming what is wrong."""
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ProfileError(f"no profile at {path}") from None
    except (OSError, ValueError) as error:
        raise ProfileError(f"{path.name} is not readable JSON ({type(error).__name__})") from None
    if not isinstance(raw, dict):
        raise ProfileError(f"{path.name} is not a JSON object")
    if raw.get("schema_version") != SCHEMA_VERSION:
        raise ProfileError(f"{path.name}: schema_version must be {SCHEMA_VERSION}")
    if set(raw) != KEYS:
        # Unknown keys are refused, so a stream URL has nowhere to go.
        raise ProfileError(f"{path.name}: its fields must be exactly {sorted(KEYS)}")
    camera = raw["camera_id"]
    if not isinstance(camera, str) or not NAME.fullmatch(camera) or camera != path.stem:
        raise ProfileError(f"{path.name}: camera_id must be a short code equal to the file's name")

    geometry = raw["geometry"]
    entries = geometry.get("lanes") if isinstance(geometry, dict) else None
    if not isinstance(entries, list) or not entries or geometry.get("coordinates") != "normalised_image" \
            or not _number(geometry.get("max_radius")) or not 0 < geometry["max_radius"] <= 1:
        raise ProfileError(f"{path.name}: geometry needs normalised_image coordinates, max_radius and lanes")
    lanes = []
    for entry in entries:
        centre = entry.get("centre") if isinstance(entry, dict) else None
        name = entry.get("name") if isinstance(entry, dict) else None
        if not isinstance(name, str) or not NAME.fullmatch(name) or not isinstance(centre, list) or len(centre) != 2 \
                or not all(_number(v) and 0 <= v <= 1 for v in centre):
            raise ProfileError(f"{path.name}: each lane needs a name and a centre within the image")
        lanes.append((name, (float(centre[0]), float(centre[1]))))

    lane_map = raw["lane_map"]
    if not isinstance(lane_map, dict) or set(lane_map) != {name for name, _ in lanes}:
        raise ProfileError(f"{path.name}: lane_map must cover exactly the lanes in geometry")
    if any(v not in APPROACHES for v in lane_map.values()) or len(set(lane_map.values())) != len(lane_map):
        raise ProfileError(f"{path.name}: each lane must map to a distinct one of {list(APPROACHES)}")

    calibration = raw["calibration"]
    if not isinstance(calibration, dict) or set(calibration) != {"persistence_spec", "spec_sha256", "key"}:
        raise ProfileError(f"{path.name}: calibration needs persistence_spec, spec_sha256 and key")
    spec_path = Path(root) / calibration["persistence_spec"]
    if not spec_path.is_file():
        raise ProfileError(f"{path.name}: persistence spec not found: {calibration['persistence_spec']}")
    spec_bytes = spec_path.read_bytes()
    if hashlib.sha256(spec_bytes).hexdigest() != calibration["spec_sha256"]:
        raise ProfileError(f"{path.name}: persistence spec {spec_path.name} does not match its recorded hash")
    try:
        known = calibration["key"] in json.loads(spec_bytes)["cameras"]
    except (ValueError, KeyError, TypeError):
        raise ProfileError(f"{path.name}: persistence spec {spec_path.name} is not readable") from None
    if not known:
        raise ProfileError(f"{path.name}: {spec_path.name} has no thresholds for {calibration['key']}")

    direction = raw["direction"]
    if not isinstance(direction, dict) or direction.get("status") not in DIRECTION_STATUSES:
        raise ProfileError(f"{path.name}: direction.status must be one of {list(DIRECTION_STATUSES)}")
    if not isinstance(raw["limitations"], list) or not all(isinstance(t, str) for t in raw["limitations"]):
        raise ProfileError(f"{path.name}: limitations must be a list of sentences")
    if not isinstance(raw["provenance"], dict):
        raise ProfileError(f"{path.name}: provenance must say where the lanes came from")
    evidence = raw["evidence"]
    if not isinstance(evidence, list) or not all(
            isinstance(e, dict) and e.get("kind") in BINDS and isinstance(e.get("binds"), str) for e in evidence):
        raise ProfileError(f"{path.name}: each piece of evidence needs a kind and what it binds")
    return CameraProfile(path=path, camera_id=camera, lanes=tuple(lanes), max_radius=float(geometry["max_radius"]),
                         lane_map=dict(lane_map), spec_path=spec_path, spec_key=calibration["key"],
                         limitations=tuple(raw["limitations"]), direction_status=direction["status"], raw=raw)


def load_profiles(directory: Path = PROFILES, root: Path = ROOT) -> tuple[list[CameraProfile], list[tuple[Path, str]]]:
    """(the valid profiles, each invalid file with its reason)."""
    good, bad = [], []
    for path in sorted(Path(directory).glob("*.json")):
        try:
            good.append(load_profile(path, root))
        except ProfileError as error:
            bad.append((path, str(error)))
    return good, bad
