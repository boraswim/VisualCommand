"""Motion gestures: built from a short history of hand positions.

The frame is mirrored before analysis, so "right" is your right.
Coordinates are normalised to the frame (0..1); y grows downwards.
"""
from __future__ import annotations

import math
from collections import deque

from visualcommand.features import FrameFeatures
from visualcommand.gestures.base import MotionGesture, register_gesture


class _History(MotionGesture):
    window = 0.6  # seconds of history kept

    def __init__(self) -> None:
        self.hist: deque = deque()

    def reset(self) -> None:
        self.hist.clear()

    def _push(self, t: float, value) -> None:
        self.hist.append((t, value))
        while self.hist and t - self.hist[0][0] > self.window:
            self.hist.popleft()


# --- swipes --------------------------------------------------------------------

class _Swipe(_History):
    direction = (1.0, 0.0)
    window = 0.6

    def update(self, f: FrameFeatures, settings: dict) -> bool:
        # Only an open hand swipes; anything else (or no hand) resets the stroke.
        if not f.hand or not f.open_hand:
            self.reset()
            return False
        self._push(f.t, f.palm_center)
        if len(self.hist) < 3:
            return False
        (x0, y0), (x1, y1) = self.hist[0][1], self.hist[-1][1]
        dx, dy = x1 - x0, y1 - y0
        ux, uy = self.direction
        along = dx * ux + dy * uy
        across = abs(dx * uy - dy * ux)
        if along >= settings.get("swipe_distance", 0.3) and across <= 0.5 * along:
            self.reset()
            return True
        return False


@register_gesture
class SwipeLeft(_Swipe):
    id, name, icon, order = "Swipe_Left", "Swipe left", "⬅️", 50
    description = "Open hand moved quickly to your left."
    direction = (-1.0, 0.0)


@register_gesture
class SwipeRight(_Swipe):
    id, name, icon, order = "Swipe_Right", "Swipe right", "➡️", 51
    description = "Open hand moved quickly to your right."
    direction = (1.0, 0.0)


@register_gesture
class SwipeUp(_Swipe):
    id, name, icon, order = "Swipe_Up", "Swipe up", "⬆️", 52
    description = "Open hand moved quickly upwards."
    direction = (0.0, -1.0)


@register_gesture
class SwipeDown(_Swipe):
    id, name, icon, order = "Swipe_Down", "Swipe down", "⬇️", 53
    description = "Open hand moved quickly downwards."
    direction = (0.0, 1.0)


# --- push ----------------------------------------------------------------------

@register_gesture
class Push(_History):
    id, name, icon, order = "Push", "Push", "🫸", 60
    description = "Open palm pushed quickly toward the camera."
    window = 0.5

    def update(self, f: FrameFeatures, settings: dict) -> bool:
        if not f.hand or not f.open_hand:
            self.reset()
            return False
        self._push(f.t, (f.palm_size, f.palm_center))
        if len(self.hist) < 3:
            return False
        sizes = [v[0] for _, v in self.hist]
        smallest = min(sizes)
        i = sizes.index(smallest)
        (cx0, cy0), (cx1, cy1) = self.hist[i][1][1], self.hist[-1][1][1]
        moved = math.hypot(cx1 - cx0, cy1 - cy0)
        if smallest > 0 and f.palm_size / smallest >= 1.35 and moved < 0.12:
            self.reset()
            return True
        return False


# --- wave ----------------------------------------------------------------------

@register_gesture
class Wave(_History):
    id, name, icon, order = "Wave", "Wave", "👋", 61
    description = "Open hand waved side to side (three changes of direction)."
    window = 1.6
    min_swing = 0.05

    def update(self, f: FrameFeatures, settings: dict) -> bool:
        if not f.hand or not f.open_hand:
            self.reset()
            return False
        self._push(f.t, f.palm_center[0])
        xs = [x for _, x in self.hist]
        if len(xs) < 5:
            return False
        reversals = 0
        direction = 0
        anchor = xs[0]
        for x in xs[1:]:
            delta = x - anchor
            if abs(delta) < self.min_swing:
                continue
            step = 1 if delta > 0 else -1
            if direction and step != direction:
                reversals += 1
            direction = step
            anchor = x
        if reversals >= 3:
            self.reset()
            return True
        return False


# --- circles -------------------------------------------------------------------

class _Circle(_History):
    window = 2.0
    sign = 1.0  # +1 clockwise on screen (y grows downwards)

    def update(self, f: FrameFeatures, settings: dict) -> bool:
        # Drawn with the index finger: index out, middle/ring/pinky folded.
        if not f.hand or not (f.extended[1] and not any(f.extended[2:])):
            self.reset()
            return False
        self._push(f.t, f.index_tip)
        if len(self.hist) < 8:
            return False
        pts = [p for _, p in self.hist]
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        radius = sum(math.hypot(p[0] - cx, p[1] - cy) for p in pts) / len(pts)
        if radius < 0.04:
            return False
        total = 0.0
        prev = math.atan2(pts[0][1] - cy, pts[0][0] - cx)
        for p in pts[1:]:
            a = math.atan2(p[1] - cy, p[0] - cx)
            d = a - prev
            if d > math.pi:
                d -= 2 * math.pi
            elif d < -math.pi:
                d += 2 * math.pi
            total += d
            prev = a
        if total * self.sign >= 2 * math.pi * 0.85:
            self.reset()
            return True
        return False


@register_gesture
class CircleCW(_Circle):
    id, name, icon, order = "Circle_CW", "Circle clockwise", "🔃", 70
    description = "Draw a circle clockwise in the air with your index finger."
    sign = 1.0


@register_gesture
class CircleCCW(_Circle):
    id, name, icon, order = "Circle_CCW", "Circle anticlockwise", "🔄", 71
    description = "Draw a circle anticlockwise in the air with your index finger."
    sign = -1.0


# --- pinch and drag ------------------------------------------------------------

class _PinchDrag(_History):
    window = 1.0
    sign = -1.0  # -1 = up (y decreases)

    def update(self, f: FrameFeatures, settings: dict) -> bool:
        if not f.hand or f.pinch > 0.35:
            self.reset()
            return False
        mid_y = f.index_tip[1]
        self._push(f.t, mid_y)
        dy = self.hist[-1][1] - self.hist[0][1]
        if dy * self.sign >= 0.15:
            self.reset()
            return True
        return False


@register_gesture
class PinchDragUp(_PinchDrag):
    id, name, icon, order = "Pinch_Drag_Up", "Pinch and drag up", "🤏⬆️", 80
    description = "Pinch thumb and index together, then move your hand up."
    sign = -1.0


@register_gesture
class PinchDragDown(_PinchDrag):
    id, name, icon, order = "Pinch_Drag_Down", "Pinch and drag down", "🤏⬇️", 81
    description = "Pinch thumb and index together, then move your hand down."
    sign = 1.0
