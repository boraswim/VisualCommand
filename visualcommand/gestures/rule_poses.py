"""Extra poses defined by simple landmark rules (no training needed).

Each rule looks at FrameFeatures.extended = (thumb, index, middle, ring, pinky),
the pinch distance and the index direction.
"""
from __future__ import annotations

from visualcommand.features import FrameFeatures
from visualcommand.gestures.base import PoseGesture, register_gesture

MATCH = 0.9          # score reported when a rule matches
# Measured on real hands (both sides), in palm sizes:
#   thumb-index tip gap: OK sign 0.10-0.16, fist 0.30-0.38
#   index tip to middle-finger base: OK sign 0.56-0.63, fist 0.29-0.34
PINCH_CLOSE = 0.22   # thumb and index tips count as touching below this
INDEX_OUT = 0.45     # index tip is away from the palm (not curled into a fist) above this


def _pinching(f: FrameFeatures) -> bool:
    """Thumb and index tips together with the index held out, not a curled fist."""
    return f.hand and f.pinch <= PINCH_CLOSE and f.index_reach >= INDEX_OUT


@register_gesture
class Pinch(PoseGesture):
    id = "Pinch"
    name = "Pinch"
    icon = "🤏"
    description = "Thumb and index fingertips touching, other fingers relaxed."
    order = 20

    def score(self, f: FrameFeatures) -> float:
        if not _pinching(f) or f.mp_label == "Closed_Fist":
            return 0.0
        return MATCH if sum(f.extended[2:]) <= 1 else 0.0


@register_gesture
class OkSign(PoseGesture):
    id = "OK_Sign"
    name = "OK sign"
    icon = "👌"
    description = "Thumb and index make a circle, other three fingers up."
    order = 21

    def score(self, f: FrameFeatures) -> float:
        if not _pinching(f):
            return 0.0
        return MATCH if all(f.extended[2:]) else 0.0


def _pattern(f: FrameFeatures, want: tuple, ignore_thumb: bool = False) -> bool:
    got = f.extended
    if ignore_thumb:
        return got[1:] == want[1:]
    return got == want


@register_gesture
class ThreeFingers(PoseGesture):
    id = "Three_Fingers"
    name = "Three fingers"
    icon = "🖖"
    description = "Index, middle and ring finger up; thumb and pinky folded."
    order = 22

    def score(self, f: FrameFeatures) -> float:
        return MATCH if f.hand and f.pinch > PINCH_CLOSE and _pattern(
            f, (False, True, True, True, False), ignore_thumb=True) else 0.0


@register_gesture
class Rock(PoseGesture):
    id = "Rock"
    name = "Rock on"
    icon = "🤘"
    description = "Index and pinky up, middle and ring folded, thumb tucked in."
    order = 23

    def score(self, f: FrameFeatures) -> float:
        if not f.hand or f.mp_label == "ILoveYou":
            return 0.0
        return MATCH if _pattern(f, (False, True, False, False, True)) else 0.0


@register_gesture
class CallMe(PoseGesture):
    id = "Call_Me"
    name = "Call me"
    icon = "🤙"
    description = "Thumb and pinky out, other fingers folded."
    order = 24

    def score(self, f: FrameFeatures) -> float:
        return MATCH if f.hand and _pattern(f, (True, False, False, False, True)) else 0.0


# Finger gun, measured on real hands (both hands, palm or back to the camera):
#   fingers read thumb+index out, others curled in 86-98% of frames
#   thumb-to-index angle 45-83 deg (plain pointing with the thumb tucked: 11-20 deg)
#   index direction up to ~40 deg above horizontal
FINGER_GUN_MIN_THUMB_ANGLE = 35.0
POINT_MIN_HORIZONTAL = 0.7     # |dx| of the index direction: within ~45 deg of horizontal


def finger_gun(f: FrameFeatures) -> bool:
    """Thumb up, index out, middle/ring/pinky curled. Works with palm or back facing."""
    return (f.hand and _pattern(f, (True, True, False, False, False))
            and f.thumb_index_angle >= FINGER_GUN_MIN_THUMB_ANGLE)


class _PointSide(PoseGesture):
    sign = 1.0

    def score(self, f: FrameFeatures) -> float:
        if not finger_gun(f):
            return 0.0
        return MATCH if f.index_dir[0] * self.sign >= POINT_MIN_HORIZONTAL else 0.0


@register_gesture
class PointLeft(_PointSide):
    id = "Point_Left"
    name = "Point left"
    icon = "👈"
    description = ("Finger gun pointing to your left: thumb up, index out, other fingers "
                   "closed. Palm or back of the hand to the camera.")
    order = 25
    sign = -1.0


@register_gesture
class PointRight(_PointSide):
    id = "Point_Right"
    name = "Point right"
    icon = "👉"
    description = ("Finger gun pointing to your right: thumb up, index out, other fingers "
                   "closed. Palm or back of the hand to the camera.")
    order = 26
    sign = 1.0
