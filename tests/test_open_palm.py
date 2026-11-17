"""Stricter Open Palm: upright, fingers straight and spread, palm facing the camera."""
import numpy as np

from visualcommand.features import FrameFeatures, palm_facing
from visualcommand.gestures import registry
from visualcommand.gestures.builtin_poses import open_palm_shape

DELIBERATE = dict(extended=(True,) * 5, palm_facing=0.97, straightness=0.99, spread=1.15,
                  palm_width=0.70, tilt=9.0)


def palm(**over):
    kw = dict(DELIBERATE)
    kw.update(over)
    return FrameFeatures(t=0, hand=True, mp_label="Open_Palm", mp_score=0.7, **kw)


def test_deliberate_open_palm_passes():
    assert open_palm_shape(palm())
    assert registry()["Open_Palm"]().score(palm()) == 0.7


def test_casual_raised_hand_is_rejected():
    """Values measured on accidental open-palm detections."""
    casual = palm(palm_facing=0.77, straightness=0.87, spread=0.70, palm_width=0.52)
    assert not open_palm_shape(casual)
    assert registry()["Open_Palm"]().score(casual) == 0


def test_each_restriction_on_its_own():
    assert not open_palm_shape(palm(palm_facing=-0.97))        # back of the hand
    assert not open_palm_shape(palm(palm_facing=0.8))          # turned away
    assert not open_palm_shape(palm(straightness=0.88))        # fingers bent
    assert not open_palm_shape(palm(spread=0.8))               # fingers together
    assert not open_palm_shape(palm(palm_width=0.5))           # hand sideways
    assert not open_palm_shape(palm(tilt=50))                  # hand lying down
    assert not open_palm_shape(palm(extended=(False, True, True, True, True)))  # thumb in


def test_other_builtin_poses_unchanged():
    f = FrameFeatures(t=0, hand=True, mp_label="Victory", mp_score=0.66,
                      extended=(False, True, True, False, False), straightness=0.5, spread=0.3)
    assert registry()["Victory"]().score(f) == 0.66


def test_palm_facing_same_for_both_hands_and_flips_for_back():
    # a flat hand in the image plane, tilted slightly so the palm normal has depth
    right = np.array([[0.5, 0.7, 0.0]] + [[0.5, 0.5, 0.0]] * 4 +
                     [[0.45, 0.5, -0.02]] + [[0.5, 0.45, 0.0]] * 11 +
                     [[0.56, 0.52, 0.02]] + [[0.5, 0.45, 0.0]] * 3, dtype=np.float32)
    left = right.copy()
    left[:, 0] = 1 - left[:, 0]                 # the mirror-image hand
    r = palm_facing(right, 4 / 3, "Right")
    l_val = palm_facing(left, 4 / 3, "Left")
    assert abs(r - l_val) < 1e-6
    assert abs(palm_facing(right, 4 / 3, "Left") + r) < 1e-6   # other side = back of hand


def test_palm_facing_unknown_without_depth():
    flat = np.zeros((21, 3), np.float32)
    assert palm_facing(flat, 4 / 3, "Right") == 1.0
