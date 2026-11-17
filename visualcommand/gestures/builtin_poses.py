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


# Extra shape checks on top of MediaPipe's label, per pose.
SHAPE_CHECKS: dict[str, Callable[[FrameFeatures], bool]] = {"Open_Palm": open_palm_shape}

_BUILTIN = [
    # id (= MediaPipe label), name, icon, description
    ("Thumb_Up", "Thumbs up", "👍", "Fist with the thumb pointing up."),
    ("Thumb_Down", "Thumbs down", "👎", "Fist with the thumb pointing down."),
    ("Closed_Fist", "Fist", "✊", "All fingers curled into a fist."),
    ("Open_Palm", "Open palm", "✋",
     "Hand upright, all five fingers straight and spread, palm facing the camera."),
    ("Victory", "Peace sign", "✌️", "Index and middle finger up in a V."),
    ("Pointing_Up", "Point up", "☝️", "Only the index finger, pointing up."),
    ("ILoveYou", "I love you", "🤟", "Thumb, index and pinky out."),
]


def _make(label: str, name: str, icon: str, description: str, order: int) -> type[PoseGesture]:
    check = SHAPE_CHECKS.get(label)

    def score(self, f: FrameFeatures) -> float:
        if not f.hand or f.mp_label != label:
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
