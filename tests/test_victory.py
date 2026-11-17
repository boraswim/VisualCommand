"""Peace sign: MediaPipe label (palm side) or hand-shape fallback (back of hand)."""
from visualcommand.features import FrameFeatures
from visualcommand.gestures import registry
from visualcommand.gestures.builtin_poses import VICTORY_SHAPE_SCORE, victory_shape

BACK_OF_HAND = dict(extended=(False, True, True, False, False), v_gap=0.63, v_angle=19.0,
                    straightness_index_middle=1.0, ring_pinky_curl=0.19, palm_facing=-0.95,
                    tilt=28.0)


def v(label="None", score=0.0, **over):
    kw = dict(BACK_OF_HAND)
    kw.update(over)
    return FrameFeatures(t=0, hand=True, mp_label=label, mp_score=score, **kw)


def test_back_of_hand_peace_sign_recognised_without_mediapipe_label():
    """MediaPipe's label was missing 91-100% of the time with the back of the hand."""
    assert victory_shape(v())
    assert registry()["Victory"]().score(v()) == VICTORY_SHAPE_SCORE


def test_palm_side_still_uses_mediapipe_score():
    assert registry()["Victory"]().score(v("Victory", 0.81, palm_facing=0.92)) == 0.81


def test_edge_on_resting_hand_is_not_a_peace_sign():
    """Regression: an everyday hand read as two fingers out, but edge-on and loose."""
    resting = v(v_gap=0.53, v_angle=29.0, ring_pinky_curl=0.35, palm_facing=-0.25, tilt=19.0)
    assert not victory_shape(resting)
    assert registry()["Victory"]().score(resting) == 0


def test_each_shape_limit():
    assert not victory_shape(v(v_gap=0.2))                    # fingers together
    assert not victory_shape(v(v_angle=5))                    # no V
    assert not victory_shape(v(straightness_index_middle=0.8))
    assert not victory_shape(v(ring_pinky_curl=0.4))          # ring/pinky not curled
    assert not victory_shape(v(palm_facing=-0.3))             # hand edge-on
    assert not victory_shape(v(tilt=60))                      # hand lying down
    assert not victory_shape(v(extended=(True, True, True, False, False)))  # thumb out
