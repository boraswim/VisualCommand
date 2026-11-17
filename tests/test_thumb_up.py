"""Stricter Thumbs up: tight fist, thumb sticking straight up above it."""
import numpy as np

from visualcommand.features import FrameFeatures, features_from_landmarks
from visualcommand.gestures import registry
from visualcommand.gestures.builtin_poses import thumb_up_shape

DELIBERATE = dict(extended=(True, False, False, False, False), thumb_lift=0.75,
                  fist_tightness=0.20, thumb_angle=18.0)


def thumb(**over):
    kw = dict(DELIBERATE)
    kw.update(over)
    return FrameFeatures(t=0, hand=True, mp_label="Thumb_Up", mp_score=0.63, **kw)


def test_deliberate_thumbs_up_passes():
    assert thumb_up_shape(thumb())
    assert registry()["Thumb_Up"]().score(thumb()) == 0.63


def test_hand_on_face_with_thumb_on_cheek_is_rejected():
    """Regression: median values measured with the hand resting on the face."""
    face = thumb(thumb_lift=0.46, fist_tightness=0.36, thumb_angle=15)
    assert not thumb_up_shape(face)
    assert registry()["Thumb_Up"]().score(face) == 0


def test_each_restriction_on_its_own():
    assert not thumb_up_shape(thumb(thumb_lift=0.4))                 # thumb not above the fist
    assert not thumb_up_shape(thumb(fist_tightness=0.45))            # fingers loose
    assert not thumb_up_shape(thumb(thumb_angle=60))                 # thumb leaning sideways
    assert not thumb_up_shape(thumb(extended=(False,) * 5))          # thumb not out


def test_measures_from_a_drawn_thumbs_up():
    # fist (fingertips curled onto their knuckles) with the thumb straight up
    lm = np.zeros((21, 2), np.float32)
    lm[0] = (0.50, 0.70)                              # wrist
    for i, (mcp, x) in enumerate(((5, 0.46), (9, 0.50), (13, 0.54), (17, 0.58))):
        lm[mcp] = (x, 0.55)
        lm[mcp + 1] = (x, 0.53)
        lm[mcp + 2] = (x + 0.01, 0.56)
        lm[mcp + 3] = (x + 0.01, 0.58)
    lm[1], lm[2], lm[3], lm[4] = (0.45, 0.62), (0.44, 0.55), (0.44, 0.47), (0.44, 0.39)
    f = features_from_landmarks(0, lm, 4 / 3)
    assert f.thumb_lift > 0.55 and f.fist_tightness < 0.35 and f.thumb_angle < 10
