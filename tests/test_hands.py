"""Two-hand slot assignment, de-duplication and the false-hand filter."""
import numpy as np

from visualcommand.config import Config
from visualcommand.features import FrameFeatures, features_from_landmarks, plausible_hand
from visualcommand.hands import HandSlots

SENS = {"hold_time": 0.4, "cooldown": 2.0, "min_score": 0.7}
OPEN = (True,) * 5


def hand(t, center, label="None", score=0.0, extended=OPEN):
    return FrameFeatures(t=t, hand=True, palm_center=center, mp_label=label, mp_score=score,
                         extended=extended, palm_size=0.2)


def steps(t0, t1, fps=15):
    return [t0 + i / fps for i in range(int(round((t1 - t0) * fps)))]


def test_second_hand_gesture_detected_while_first_hand_is_tracked():
    """A false/idle 'hand' in one slot must not block the real hand in the other."""
    slots = HandSlots(2)
    fired = []
    for t in steps(0, 1.0):
        idle = hand(t, (0.5, 0.85))                         # e.g. a shadow on a shirt
        real = hand(t, (0.3, 0.4), "Thumb_Up", 0.9)
        # MediaPipe's output order flips around between frames
        hands = [idle, real] if int(t * 15) % 2 else [real, idle]
        fired += slots.process(t, hands, "good", {"Thumb_Up"}, SENS)
    assert fired == ["Thumb_Up"]


def test_hands_keep_their_slot_when_order_swaps():
    slots = HandSlots(2)
    a, b = hand(0, (0.2, 0.5)), hand(0, (0.8, 0.5))
    slots.process(0, [a, b], "good", set(), SENS)
    first = [s.current.palm_center for s in slots.slots]
    a2, b2 = hand(0.07, (0.22, 0.5)), hand(0.07, (0.78, 0.5))
    slots.process(0.07, [b2, a2], "good", set(), SENS)
    second = [s.current.palm_center for s in slots.slots]
    assert [round(x[0], 1) for x in first] == [round(x[0], 1) for x in second]


def test_same_pose_with_both_hands_fires_once():
    slots = HandSlots(2)
    fired = []
    for t in steps(0, 1.0):
        fired += slots.process(t, [hand(t, (0.2, 0.5), "Victory", 0.9),
                                   hand(t, (0.8, 0.5), "Victory", 0.9)], "good", {"Victory"}, SENS)
    assert fired == ["Victory"]


def test_suppress_blocks_poses_right_after_camera_start():
    slots = HandSlots(2)
    slots.suppress(0, 1.0)
    fired = []
    for t in steps(0, 1.6):
        fired += [(round(t, 2), g) for g in
                  slots.process(t, [hand(t, (0.5, 0.5), "Victory", 0.9)], "good", {"Victory"}, SENS)]
    assert len(fired) == 1 and fired[0][0] >= 1.0


def _real_hand_landmarks(scale=1.0, cx=0.5, cy=0.5):
    # rough open right hand, normalised coords
    base = np.array([
        [0, 0.20], [-0.06, 0.15], [-0.10, 0.10], [-0.13, 0.05], [-0.16, 0.0],
        [-0.05, 0.02], [-0.06, -0.06], [-0.065, -0.11], [-0.07, -0.15],
        [0, 0.0], [0, -0.09], [0, -0.14], [0, -0.18],
        [0.045, 0.01], [0.05, -0.07], [0.055, -0.12], [0.06, -0.16],
        [0.085, 0.03], [0.095, -0.03], [0.10, -0.07], [0.105, -0.10],
    ], dtype=np.float32)
    return base * scale + np.array([cx, cy], dtype=np.float32)


def test_plausible_hand_accepts_normal_hand():
    f = features_from_landmarks(0, _real_hand_landmarks(), 4 / 3)
    assert plausible_hand(f)
    assert sum(f.extended[1:]) == 4


def _tucked_thumb(lm):
    lm = lm.copy()
    # thumb folded across the palm, tip near the middle-finger base
    lm[2] = lm[0] + np.array([-0.04, -0.12])
    lm[3] = lm[0] + np.array([-0.03, -0.17])
    lm[4] = lm[0] + np.array([-0.01, -0.19])
    return lm


def _mirror(lm):
    out = lm.copy()
    out[:, 0] = 1.0 - out[:, 0]
    return out


def test_finger_states_identical_for_left_and_right_hand():
    """Regression: a pose must read the same with either hand (mirror image)."""
    for lm in (_real_hand_landmarks(), _tucked_thumb(_real_hand_landmarks())):
        right = features_from_landmarks(0, lm, 4 / 3)
        left = features_from_landmarks(0, _mirror(lm), 4 / 3)
        assert right.extended == left.extended


def test_thumb_out_and_tucked_are_told_apart():
    out = features_from_landmarks(0, _real_hand_landmarks(), 4 / 3)
    tucked = features_from_landmarks(0, _tucked_thumb(_real_hand_landmarks()), 4 / 3)
    assert out.extended[0] is True
    assert tucked.extended[0] is False


def _sided(t, center, size, side, label="None", score=0.9, hs=0.99):
    f = hand(t, center, label, score)
    f.palm_size, f.handedness = size, side
    f.extra["handedness_score"] = hs
    return f


def test_phantom_same_side_hand_dropped():
    """Regression: a sleeve below the real right hand was detected as a second,
    smaller *right* hand making a fist, firing Closed_Fist during an open palm."""
    from visualcommand.features import drop_phantom_hands
    real = _sided(0, (0.44, 0.45), 0.20, "Right", "Open_Palm", 0.72)
    phantom = _sided(0, (0.43, 0.84), 0.12, "Right", "Closed_Fist", 0.82)
    assert drop_phantom_hands([phantom, real]) == [real]


def test_much_smaller_second_hand_dropped():
    from visualcommand.features import drop_phantom_hands
    real = _sided(0, (0.3, 0.4), 0.20, "Right")
    tiny = _sided(0, (0.7, 0.8), 0.08, "Left")
    assert drop_phantom_hands([real, tiny]) == [real]


def test_real_two_hands_kept():
    from visualcommand.features import drop_phantom_hands
    right = _sided(0, (0.3, 0.4), 0.20, "Right")
    left = _sided(0, (0.7, 0.4), 0.17, "Left")
    assert drop_phantom_hands([right, left]) == [right, left]


def test_fist_is_not_a_pinch_or_ok_sign():
    """Regression: in a fist the thumb rests on the index (gap ~0.3 palm), which the
    old pinch threshold (0.32) accepted."""
    from visualcommand.gestures import registry
    fist = FrameFeatures(t=0, hand=True, mp_label="Closed_Fist", extended=(False,) * 5,
                         pinch=0.30, index_reach=0.32, palm_size=0.2)
    ok = FrameFeatures(t=0, hand=True, extended=(False, False, True, True, True),
                       pinch=0.14, index_reach=0.6, palm_size=0.2)
    pinch = FrameFeatures(t=0, hand=True, extended=(True, False, False, False, False),
                          pinch=0.12, index_reach=0.6, palm_size=0.2)
    reg = registry()
    assert reg["Pinch"]().score(fist) == 0 and reg["OK_Sign"]().score(fist) == 0
    assert reg["OK_Sign"]().score(ok) > 0
    assert reg["Pinch"]().score(pinch) > 0


def _fake_result(norm_landmarks, label="None", side="Right"):
    from types import SimpleNamespace as NS
    pts = [NS(x=float(x), y=float(y)) for x, y in norm_landmarks]
    return NS(hand_landmarks=[pts], gestures=[[NS(category_name=label, score=0.0)]],
              handedness=[[NS(category_name=side, score=0.99)]])


def _pointing_hand(direction):
    """Finger gun: index out along +x or -x in the image, thumb up, others curled."""
    lm = _real_hand_landmarks()
    # index out to image-left (-x), the side the thumb is on in this template
    lm[5:9] = lm[5] + np.array([[0, 0], [-0.06, 0], [-0.11, 0], [-0.15, 0]])
    for mcp, pip, dip, tip in ((9, 10, 11, 12), (13, 14, 15, 16), (17, 18, 19, 20)):
        lm[pip] = lm[mcp] + np.array([0, -0.03])
        lm[dip] = lm[mcp] + np.array([0, -0.01])
        lm[tip] = lm[mcp] + np.array([0, 0.02])
    # thumb sticking up, away from the palm
    lm[2] = lm[0] + np.array([-0.07, -0.09])
    lm[3] = lm[0] + np.array([-0.10, -0.17])
    lm[4] = lm[0] + np.array([-0.12, -0.25])
    if direction > 0:                  # the mirror-image hand points to image-right
        lm = _mirror(lm)
    return lm


def test_pointing_hand_template_is_a_finger_gun():
    from visualcommand.gestures.rule_poses import finger_gun
    for d in (-1, 1):
        f = features_from_landmarks(0, _pointing_hand(d), 4 / 3)
        assert f.extended == (True, True, False, False, False), f.extended
        assert finger_gun(f)


def test_pointing_right_in_your_view_is_point_right():
    """Regression: the camera's natural view is not a mirror, so pointing to *your*
    right points to the image's LEFT. Positions must be converted to your view."""
    from visualcommand.features import build_hands
    from visualcommand.gestures import registry
    natural = _pointing_hand(direction=-1)          # image-left = your right
    f = build_hands(0, _fake_result(natural), 4 / 3, "good", to_user_view=True)[0]
    reg = registry()
    assert reg["Point_Right"]().score(f) > 0
    assert reg["Point_Left"]().score(f) == 0
    g = build_hands(0, _fake_result(_pointing_hand(direction=+1)), 4 / 3, "good",
                    to_user_view=True)[0]
    assert reg["Point_Left"]().score(g) > 0 and reg["Point_Right"]().score(g) == 0


def test_user_view_keeps_finger_states_and_handedness():
    from visualcommand.features import build_hands
    lm = _real_hand_landmarks()
    a = build_hands(0, _fake_result(lm, side="Right"), 4 / 3, "good", to_user_view=False)[0]
    b = build_hands(0, _fake_result(lm, side="Right"), 4 / 3, "good", to_user_view=True)[0]
    assert a.extended == b.extended and b.handedness == "Right"
    assert abs(a.palm_center[0] - (1 - b.palm_center[0])) < 1e-6


def test_old_flip_default_is_turned_off(tmp_path):
    import json
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"version": 5, "mirror_image": True}), encoding="utf-8")
    assert Config(p).get("mirror_image") is False


def test_plausible_hand_rejects_tiny_blob():
    f = features_from_landmarks(0, _real_hand_landmarks(scale=0.1), 4 / 3)
    assert not plausible_hand(f)


def test_two_real_hands_with_landmarks_do_not_crash():
    """Regression: 0.1.1 crashed when a second hand appeared, because comparing two
    FrameFeatures compared their numpy landmark arrays."""
    slots = HandSlots(2)
    fired = []
    for i, t in enumerate(steps(0, 1.0)):
        left = features_from_landmarks(t, _real_hand_landmarks(cx=0.3), 4 / 3,
                                       mp_label="Thumb_Up", mp_score=0.9)
        right = features_from_landmarks(t, _real_hand_landmarks(cx=0.7), 4 / 3)
        hands = [left, right] if i % 2 else [right, left]
        fired += slots.process(t, hands, "good", {"Thumb_Up"}, SENS)
        kept = {id(h) for h in hands}
        assert [h for h in hands if id(h) not in kept] == []
    assert fired == ["Thumb_Up"]


def test_frame_features_compare_by_identity():
    a = features_from_landmarks(0, _real_hand_landmarks(), 4 / 3)
    b = features_from_landmarks(0, _real_hand_landmarks(), 4 / 3)
    assert a == a and a != b and a in [a] and b not in [a]


def test_old_config_loses_motion_mappings_and_swipe_setting(tmp_path):
    """0.1.3 removed motion gestures: their mappings and settings are dropped and saved."""
    import json
    p = tmp_path / "config.json"
    p.write_text(json.dumps({
        "version": 2,
        "sensitivity": {"swipe_distance": 0.3, "hold_time": 0.5},
        "mappings": {"Thumb_Up": {"action": "screenshot"}, "Swipe_Down": {"action": "screenshot"},
                     "Swipe_Left": {"action": "media_prev"}, "Wave": {"action": "lock_pc"}},
    }), encoding="utf-8")
    cfg = Config(p)
    assert cfg.mappings() == {"Thumb_Up": {"action": "screenshot"}}
    assert "swipe_distance" not in cfg.sensitivity()
    assert cfg.sensitivity()["hold_time"] == 0.5
    on_disk = json.loads(p.read_text(encoding="utf-8"))
    assert on_disk["version"] >= 3 and "Swipe_Down" not in on_disk["mappings"]
