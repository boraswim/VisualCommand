"""Two-hand slot assignment, de-duplication and the false-hand filter."""
import numpy as np

from visualcommand.config import Config
from visualcommand.features import FrameFeatures, features_from_landmarks, plausible_hand
from visualcommand.hands import HandSlots

SENS = {"hold_time": 0.4, "cooldown": 2.0, "min_score": 0.7, "swipe_distance": 0.25}
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


def test_swipe_with_one_hand_while_other_hand_is_still():
    slots = HandSlots(2)
    fired = []
    ts = steps(0, 0.5)
    for i, t in enumerate(ts):
        still = hand(t, (0.8, 0.8), extended=(False,) * 5)
        moving = hand(t, (0.15 + 0.5 * i / (len(ts) - 1), 0.4))
        fired += slots.process(t, [still, moving], "good", {"Swipe_Right"}, SENS)
    assert fired == ["Swipe_Right"]


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


def test_old_config_swipe_distance_migrated(tmp_path):
    p = tmp_path / "config.json"
    p.write_text('{"version": 1, "sensitivity": {"swipe_distance": 0.3}}', encoding="utf-8")
    cfg = Config(p)
    assert cfg.sensitivity()["swipe_distance"] == 0.25
    assert cfg.get("hand_strictness") == 0.7


def test_custom_swipe_distance_kept(tmp_path):
    p = tmp_path / "config.json"
    p.write_text('{"version": 1, "sensitivity": {"swipe_distance": 0.4}}', encoding="utf-8")
    assert Config(p).sensitivity()["swipe_distance"] == 0.4
