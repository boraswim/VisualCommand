"""Is the hand being *shown* to the camera, or just resting / holding something?

Applied to every pose before it can count. Derived from trigger-log records that
were all false triggers (hand resting low near the desk, tiny and cut off at the
bottom edge, or pointed toward the camera while holding something), checked
against a recording of all 11 mapped gestures made deliberately with each hand
plus 25 s of hands resting / typing / holding things.

Height is measured at the middle of the hand's outline (not the palm centre: a
thumbs up's palm sits low under the raised thumb). Lines from 0.58 to 0.62 kept
21/22 deliberate gestures with 0 resting-hand triggers; 0.60 is in the middle.
"""
from __future__ import annotations

from visualcommand.features import FrameFeatures

DEFAULT_ZONE = 0.60      # middle of the hand must be above this fraction of the frame height
MIN_PALM_SIZE = 0.08     # smaller = far away or mostly out of view (false one: 0.04)
EDGE = 0.01              # landmarks outside the frame by more than this = cut off
MAX_PALM_WIDTH = 0.95    # larger = hand pointed toward/away from the camera
                         # (false ones 1.02-1.08; a hand shown to the camera ~0.7)
MIN_STEADY = 0.8         # share of frames during the hold that must show the pose


def hand_height(f: FrameFeatures) -> float:
    """Vertical middle of the hand's outline (0 = top of the view, 1 = bottom)."""
    if f.landmarks is None:
        return f.palm_center[1]
    ys = f.landmarks[:, 1]
    return float((ys.min() + ys.max()) / 2)


def presentation_problem(f: FrameFeatures, zone: float = DEFAULT_ZONE) -> str | None:
    """None if the hand is clearly shown to the camera, else a short reason."""
    if not f.hand:
        return "no hand"
    if hand_height(f) > zone:
        return "hand too low (raise it into the gesture zone)"
    if f.palm_size < MIN_PALM_SIZE:
        return "hand too small or too far"
    lm = f.landmarks
    if lm is not None and (lm.min() < -EDGE or lm.max() > 1 + EDGE):
        return "hand partly out of view"
    if f.palm_width > MAX_PALM_WIDTH:
        return "hand pointed toward/away from the camera"
    return None
