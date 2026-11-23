"""Whole-frame mode for footage without a calibrated camera."""

from pathlib import Path

from edge.profile import CameraProfile, ROOT, load_profile

WHOLE_FRAME = "whole-frame"
WHOLE_FRAME_PATH = ROOT / "scripts" / "whole-frame.json"


def load_recording_profile(path):
    if Path(path).resolve() == WHOLE_FRAME_PATH:
        return CameraProfile(path=WHOLE_FRAME_PATH, camera_id=WHOLE_FRAME, lanes=(("frame", (.5, .5)),),
                             max_radius=1., lane_map={"frame": "N"}, spec_path=WHOLE_FRAME_PATH, spec_key=WHOLE_FRAME,
                             limitations=("Whole-frame counts estimate visible traffic. Track IDs can change under occlusion.",
                                          "Lane crossings, lane forecasts and approach signal advice need a camera profile."),
                             direction_status="does_not_apply", raw={"scope": WHOLE_FRAME})
    return load_profile(path)
