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


@dataclass
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
    index_tip: tuple[float, float] = (0.0, 0.0)
    index_dir: tuple[float, float] = (0.0, 0.0)  # unit vector index MCP -> tip
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
    # Thumb: tip well away from the index base and further from the pinky base than its IP joint.
    tip, ip = pts[THUMB[3]], pts[THUMB[2]]
    thumb = _dist(tip, pts[5]) > 0.55 * palm and _dist(tip, pts[17]) > _dist(ip, pts[17]) * 1.05
    states.append(thumb)
    for mcp, pip, _dip, tip_i in FINGERS.values():
        # Curled fingers bring the tip back toward the wrist, closer than the PIP joint.
        states.append(_dist(wrist, pts[tip_i]) > _dist(wrist, pts[pip]) * 1.12
                      and _dist(pts[mcp], pts[tip_i]) > 0.45 * palm)
    return tuple(states)  # type: ignore[return-value]


def build_features(t: float, result, aspect: float, lighting: str) -> FrameFeatures:
    """Turn a MediaPipe GestureRecognizerResult into FrameFeatures."""
    f = FrameFeatures(t=t, lighting=lighting)
    if result is None or not result.hand_landmarks:
        return f
    lm = result.hand_landmarks[0]
    norm = np.array([[p.x, p.y] for p in lm], dtype=np.float32)
    return features_from_landmarks(
        t, norm, aspect, lighting,
        mp_label=(result.gestures[0][0].category_name if result.gestures and result.gestures[0] else "None"),
        mp_score=(result.gestures[0][0].score if result.gestures and result.gestures[0] else 0.0),
        handedness=(result.handedness[0][0].category_name if result.handedness and result.handedness[0] else ""),
    )


def features_from_landmarks(t: float, norm: np.ndarray, aspect: float, lighting: str = "good",
                            mp_label: str = "None", mp_score: float = 0.0,
                            handedness: str = "") -> FrameFeatures:
    pts = norm.copy()
    pts[:, 0] *= aspect                     # make x and y the same scale for distances
    palm = _dist(pts[WRIST], pts[9]) or 1e-6
    centre = norm[[0, 5, 9, 13, 17]].mean(axis=0)
    d = pts[8] - pts[5]
    n = float(np.linalg.norm(d)) or 1e-6
    return FrameFeatures(
        t=t, hand=True, landmarks=norm, handedness=handedness,
        mp_label=mp_label or "None", mp_score=float(mp_score),
        extended=finger_states(pts),
        palm_center=(float(centre[0]), float(centre[1])),
        palm_size=palm,
        pinch=_dist(pts[4], pts[8]) / palm,
        index_tip=(float(norm[8][0]), float(norm[8][1])),
        index_dir=(float(d[0] / n), float(d[1] / n)),
        lighting=lighting,
    )
