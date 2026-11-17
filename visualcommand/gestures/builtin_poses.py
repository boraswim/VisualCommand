"""The 7 poses MediaPipe's gesture model recognises out of the box."""
from __future__ import annotations

from typing import Callable

from visualcommand.features import FrameFeatures
from visualcommand.gestures.base import PoseGesture, register_gesture

# Open palm: MediaPipe's label alone fired on casually raised hands. A deliberate
# open palm was measured (both hands) at: palm facing 0.97-0.98, straightness
# 0.99-1.00, spread 1.09-1.25, palm width 0.68-0.73, tilt within 16 degrees, all five
# fingers out. Accidental ones: facing 0.74-0.81, straightness 0.85-0.89, spread
# 0.61-0.81, width 0.50-0.56. Limits sit between the two, with margin.
OPEN_PALM = {
    "palm_facing": 0.90,     # ~25 degrees from facing the camera; rejects back of hand
    "straightness": 0.93,    # fingers fully stretched
    "spread": 0.95,          # fingers spread apart
    "palm_width": 0.60,      # palm not turned sideways
    "max_tilt": 35.0,        # hand roughly upright
}


def open_palm_shape(f: FrameFeatures) -> bool:
    c = OPEN_PALM
    return (all(f.extended)
            and f.palm_facing >= c["palm_facing"]
            and f.straightness >= c["straightness"]
            and f.spread >= c["spread"]
            and f.palm_width >= c["palm_width"]
            and f.tilt <= c["max_tilt"])


# Thumbs up: MediaPipe's label also fired on a hand resting on the face with the
# thumb along the cheek. Measured (palm lengths / degrees):
#   deliberate: thumb tip 0.56-0.87 above the index knuckle (median 0.75), fingertips
#               0.12-0.32 from their knuckles, thumb up to 43 deg from vertical
#   hand on face: thumb -0.20-0.66 above (median 0.46), fingertips 0.23-0.58, up to 71 deg
# Replay with these limits: all deliberate frames pass, no hand-on-face trigger.
THUMB_UP = {
    "min_lift": 0.55,        # thumb clearly sticking up above the fist
    "max_fist": 0.35,        # other fingers curled tightly into a fist
    "max_angle": 45.0,       # thumb pointing roughly straight up
}


def thumb_up_shape(f: FrameFeatures) -> bool:
    c = THUMB_UP
    return (f.extended[0]
            and f.thumb_lift >= c["min_lift"]
            and f.fist_tightness <= c["max_fist"]
            and f.thumb_angle <= c["max_angle"])


# Peace sign with the back of the hand to the camera: MediaPipe's label is missing
# 91-100% of the time, but the hand shape is clear. Measured (back of hand, both
# hands): index+middle out 96-98%, tip gap 0.55-0.71, V 14-21 deg, ring/pinky curl
# 0.16-0.28, |palm facing| 0.91-0.97, tilt 25-30 deg. Everyday hands that also read
# as two fingers out were narrower, edge-on (|facing| 0.17-0.40) or looser (0.30-0.37).
VICTORY_SHAPE = {
    "min_gap": 0.45,
    "min_v_angle": 10.0,
    "min_straight": 0.93,
    "max_ring_pinky": 0.32,
    "min_flat": 0.7,         # |palm facing|: palm OR back toward the camera, not edge-on
    "max_tilt": 40.0,
}
VICTORY_SHAPE_SCORE = 0.8


def victory_shape(f: FrameFeatures) -> bool:
    c = VICTORY_SHAPE
    return (f.extended == (False, True, True, False, False)
            and f.v_gap >= c["min_gap"]
            and f.v_angle >= c["min_v_angle"]
            and f.straightness_index_middle >= c["min_straight"]
            and f.ring_pinky_curl <= c["max_ring_pinky"]
            and abs(f.palm_facing) >= c["min_flat"]
            and f.tilt <= c["max_tilt"])


# Shape-only fallbacks: poses MediaPipe often misses, recognised from the hand
# outline instead (score returned when MediaPipe's label is absent).
SHAPE_FALLBACKS: dict[str, tuple[Callable[[FrameFeatures], bool], float]] = {
    "Victory": (victory_shape, VICTORY_SHAPE_SCORE),
}

# Extra shape checks on top of MediaPipe's label, per pose.
SHAPE_CHECKS: dict[str, Callable[[FrameFeatures], bool]] = {
    "Open_Palm": open_palm_shape,
    "Thumb_Up": thumb_up_shape,
}

_BUILTIN = [
    # id (= MediaPipe label), name, icon, description
    ("Thumb_Up", "Thumbs up", "👍",
     "Tight fist with the thumb sticking straight up, well above the fist."),
    ("Thumb_Down", "Thumbs down", "👎", "Fist with the thumb pointing down."),
    ("Closed_Fist", "Fist", "✊", "All fingers curled into a fist."),
    ("Open_Palm", "Open palm", "✋",
     "Hand upright, all five fingers straight and spread, palm facing the camera."),
    ("Victory", "Peace sign", "✌️",
     "Index and middle finger up in a V. Palm or back of the hand toward the camera."),
    ("Pointing_Up", "Point up", "☝️", "Only the index finger, pointing up."),
    ("ILoveYou", "I love you", "🤟", "Thumb, index and pinky out."),
]


def _make(label: str, name: str, icon: str, description: str, order: int) -> type[PoseGesture]:
    check = SHAPE_CHECKS.get(label)
    fallback = SHAPE_FALLBACKS.get(label)

    def score(self, f: FrameFeatures) -> float:
        if not f.hand:
            return 0.0
        if f.mp_label != label:
            if fallback is not None and fallback[0](f):
                return fallback[1]
            return 0.0
        if check is not None and not check(f):
            return 0.0
        return f.mp_score

    cls = type(f"Builtin_{label}", (PoseGesture,), {
        "id": label, "name": name, "icon": icon, "description": description,
        "order": order, "score": score,
    })
    return register_gesture(cls)


for _i, (_label, _name, _icon, _desc) in enumerate(_BUILTIN):
    _make(_label, _name, _icon, _desc, order=_i)
