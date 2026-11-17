"""Per-frame hand features, computed once and shared by every gesture.

Only numbers live here (landmark coordinates, scores); never pixels.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# MediaPipe hand landmark indices
WRIST = 0
THUMB = (1, 2, 3, 4)          # cmc, mcp, ip, tip
FINGERS = {                   # mcp, pip, dip, tip
    "index": (5, 6, 7, 8),
    "middle": (9, 10, 11, 12),
    "ring": (13, 14, 15, 16),
    "pinky": (17, 18, 19, 20),
}

HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (0, 17), (17, 18), (18, 19), (19, 20),
)


@dataclass(eq=False)   # identity equality: generated __eq__ would compare numpy arrays and raise
class FrameFeatures:
    t: float                                  # seconds (monotonic)
    hand: bool = False
    # 21x2 landmarks normalised to the frame (0..1), frame already mirrored (selfie view)
    landmarks: np.ndarray | None = None
    handedness: str = ""
    mp_label: str = "None"                    # MediaPipe's built-in gesture label
    mp_score: float = 0.0
    # (thumb, index, middle, ring, pinky)
    extended: tuple[bool, bool, bool, bool, bool] = (False,) * 5
    palm_center: tuple[float, float] = (0.0, 0.0)   # normalised frame coords
    palm_size: float = 0.0                    # wrist to middle-MCP, aspect-corrected
    pinch: float = 9.9                        # thumb-tip to index-tip / palm_size
    index_reach: float = 1.0                  # index-tip to middle-finger base / palm_size
    index_tip: tuple[float, float] = (0.0, 0.0)
    index_dir: tuple[float, float] = (0.0, 0.0)  # unit vector index MCP -> tip
    # Hand shape (all relative to palm_size where a distance):
    straightness: float = 1.0     # least-straight of the 4 fingers (1 = perfectly straight)
    spread: float = 1.0           # index tip to pinky tip
    palm_width: float = 0.7       # index base to pinky base; shrinks as the hand turns sideways
    tilt: float = 0.0             # degrees the hand leans from upright (0 = fingers straight up)
    # +1 palm straight at the camera, -1 back of the hand, ~0 edge-on. Needs MediaPipe's
    # depth values and handedness; 1.0 when unknown.
    palm_facing: float = 1.0
    lighting: str = "good"
    extra: dict = field(default_factory=dict)

    @property
    def open_hand(self) -> bool:
        """Four fingers out (thumb ignored: it is the least reliable)."""
        return sum(self.extended[1:]) >= 4

    @property
    def fingers_up(self) -> int:
        return sum(self.extended)


def _dist(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b))


def finger_states(pts: np.ndarray) -> tuple[bool, bool, bool, bool, bool]:
    """Which fingers are extended. `pts` is 21x2 in aspect-corrected units."""
    wrist = pts[WRIST]
    palm = _dist(wrist, pts[9]) or 1e-6
    states = []
    # Thumb: the tip is further from the pinky base than its own IP joint is, and
    # well away from the middle-finger base. Measured on real left and right hands:
    # thumb out gives >= 1.13 and >= 0.73, thumb tucked gives <= 0.86 and <= 0.47.
    # (The old "distance from the index base" test overlapped between the two.)
    tip, ip = pts[THUMB[3]], pts[THUMB[2]]
    thumb = (_dist(tip, pts[17]) > _dist(ip, pts[17]) * 1.0
             and _dist(tip, pts[9]) > 0.6 * palm)
    states.append(thumb)
    for mcp, pip, _dip, tip_i in FINGERS.values():
        # Curled fingers bring the tip back toward the wrist, closer than the PIP joint.
        states.append(_dist(wrist, pts[tip_i]) > _dist(wrist, pts[pip]) * 1.12
                      and _dist(pts[mcp], pts[tip_i]) > 0.45 * palm)
    return tuple(states)  # type: ignore[return-value]


def _top(categories_per_hand, i):
    if categories_per_hand and len(categories_per_hand) > i and categories_per_hand[i]:
        return categories_per_hand[i][0]
    return None


def build_hands(t: float, result, aspect: float, lighting: str,
                to_user_view: bool = False) -> list[FrameFeatures]:
    """One FrameFeatures per hand in a MediaPipe GestureRecognizerResult (0, 1 or 2).

    MediaPipe is fed the camera's natural (unmirrored) view, where *your* right is
    the image's left. With `to_user_view`, x coordinates are mirrored so everything
    downstream (pointing direction, preview) is from your point of view: x grows to
    your right. Finger states don't depend on this; handedness comes from MediaPipe.
    """
    hands = []
    if result is None or not result.hand_landmarks:
        return hands
    for i, lm in enumerate(result.hand_landmarks):
        raw = np.array([[p.x, p.y, getattr(p, "z", 0.0)] for p in lm], dtype=np.float32)
        norm = raw[:, :2].copy()
        if to_user_view:
            norm[:, 0] = 1.0 - norm[:, 0]
        g, h = _top(result.gestures, i), _top(result.handedness, i)
        side = h.category_name if h else ""
        f = features_from_landmarks(
            t, norm, aspect, lighting,
            mp_label=g.category_name if g else "None",
            mp_score=g.score if g else 0.0,
            handedness=side,
        )
        f.palm_facing = palm_facing(raw, aspect, side)
        f.extra["handedness_score"] = float(h.score) if h else 0.0
        hands.append(f)
    return hands


def palm_facing(raw: np.ndarray, aspect: float, handedness: str) -> float:
    """How directly the palm faces the camera: +1 palm, -1 back of hand, ~0 edge-on.

    Uses the palm plane (wrist, index base, pinky base) in 3D from MediaPipe's
    natural-view landmarks (x, y, z). Which side of that plane is the palm depends
    on left/right hand. Measured: deliberate open palms 0.97-0.98 with either hand,
    a casually raised hand 0.74-0.81.
    """
    if handedness not in ("Left", "Right") or raw.shape[1] < 3 or not np.any(raw[:, 2]):
        return 1.0
    p = raw.astype(np.float64).copy()
    p[:, 0] *= aspect
    n = np.cross(p[5] - p[0], p[17] - p[0])
    norm = float(np.linalg.norm(n)) or 1e-9
    sign = 1.0 if handedness == "Right" else -1.0
    return float(-n[2] / norm * sign)


def plausible_hand(f: FrameFeatures) -> bool:
    """Reject detections that can't be a real hand in front of a webcam.

    Shadows and folds in clothing sometimes get picked up as tiny or huge "hands",
    or as hands whose landmarks collapse onto each other.
    """
    if not f.hand or f.landmarks is None:
        return False
    if not 0.04 <= f.palm_size <= 0.8:            # too small / too big for a hand
        return False
    lm = f.landmarks
    span = float(np.ptp(lm[:, 0]) + np.ptp(lm[:, 1]))
    if span < 0.06:                               # landmarks collapsed into a blob
        return False
    return True


SIZE_RATIO_MIN = 0.5      # a person's two hands are at a similar distance from the camera
SAME_SIDE_CONFIDENCE = 0.9


def drop_phantom_hands(hands: list[FrameFeatures]) -> list[FrameFeatures]:
    """Remove a second detection that can't be a real second hand.

    Seen on real recordings: a sleeve or forearm below the real hand detected as a
    small "fist", labelled the same side (two right hands at once). Keep the larger
    detection when both claim the same side, and drop one less than half the size
    of the other.
    """
    if len(hands) < 2:
        return hands
    a, b = sorted(hands[:2], key=lambda h: h.palm_size, reverse=True)
    same_side = (a.handedness and a.handedness == b.handedness
                 and min(a.extra.get("handedness_score", 0), b.extra.get("handedness_score", 0))
                 >= SAME_SIDE_CONFIDENCE)
    if same_side or b.palm_size < SIZE_RATIO_MIN * a.palm_size:
        return [a]
    return [a, b]


def build_features(t: float, result, aspect: float, lighting: str) -> FrameFeatures:
    """First hand only (kept for simple callers and tests)."""
    hands = build_hands(t, result, aspect, lighting)
    return hands[0] if hands else FrameFeatures(t=t, lighting=lighting)


def features_from_landmarks(t: float, norm: np.ndarray, aspect: float, lighting: str = "good",
                            mp_label: str = "None", mp_score: float = 0.0,
                            handedness: str = "") -> FrameFeatures:
    pts = norm.copy()
    pts[:, 0] *= aspect                     # make x and y the same scale for distances
    palm = _dist(pts[WRIST], pts[9]) or 1e-6
    centre = norm[[0, 5, 9, 13, 17]].mean(axis=0)
    d = pts[8] - pts[5]
    n = float(np.linalg.norm(d)) or 1e-6
    straight = []
    for mcp, pip, dip, tip in FINGERS.values():
        bones = _dist(pts[pip], pts[mcp]) + _dist(pts[dip], pts[pip]) + _dist(pts[tip], pts[dip])
        straight.append(_dist(pts[tip], pts[mcp]) / (bones or 1e-6))
    up = pts[9] - pts[WRIST]
    return FrameFeatures(
        t=t, hand=True, landmarks=norm, handedness=handedness,
        mp_label=mp_label or "None", mp_score=float(mp_score),
        extended=finger_states(pts),
        palm_center=(float(centre[0]), float(centre[1])),
        palm_size=palm,
        pinch=_dist(pts[4], pts[8]) / palm,
        index_reach=_dist(pts[8], pts[9]) / palm,
        index_tip=(float(norm[8][0]), float(norm[8][1])),
        index_dir=(float(d[0] / n), float(d[1] / n)),
        straightness=float(min(straight)),
        spread=_dist(pts[8], pts[20]) / palm,
        palm_width=_dist(pts[5], pts[17]) / palm,
        tilt=float(np.degrees(np.arctan2(abs(up[0]), -up[1]))),
        lighting=lighting,
    )
