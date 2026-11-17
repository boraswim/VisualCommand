"""The 7 poses MediaPipe's gesture model recognises out of the box."""
from __future__ import annotations

from visualcommand.features import FrameFeatures
from visualcommand.gestures.base import PoseGesture, register_gesture

_BUILTIN = [
    # id (= MediaPipe label), name, icon, description
    ("Thumb_Up", "Thumbs up", "👍", "Fist with the thumb pointing up."),
    ("Thumb_Down", "Thumbs down", "👎", "Fist with the thumb pointing down."),
    ("Closed_Fist", "Fist", "✊", "All fingers curled into a fist."),
    ("Open_Palm", "Open palm", "✋", "Flat hand, all fingers spread, facing the camera."),
    ("Victory", "Peace sign", "✌️", "Index and middle finger up in a V."),
    ("Pointing_Up", "Point up", "☝️", "Only the index finger, pointing up."),
    ("ILoveYou", "I love you", "🤟", "Thumb, index and pinky out."),
]


def _make(label: str, name: str, icon: str, description: str, order: int) -> type[PoseGesture]:
    def score(self, f: FrameFeatures) -> float:
        return f.mp_score if f.hand and f.mp_label == label else 0.0

    cls = type(f"Builtin_{label}", (PoseGesture,), {
        "id": label, "name": name, "icon": icon, "description": description,
        "order": order, "score": score,
    })
    return register_gesture(cls)


for _i, (_label, _name, _icon, _desc) in enumerate(_BUILTIN):
    _make(_label, _name, _icon, _desc, order=_i)
