"""Gesture plugin base classes and the catalogue registry.

To add a gesture: subclass PoseGesture (return a 0..1 score per frame) or
MotionGesture (return True when the motion completes), decorate it with
@register_gesture, and put it in any module inside visualcommand/gestures/.
The settings window lists it automatically.
"""
from __future__ import annotations

from typing import ClassVar

from visualcommand.features import FrameFeatures

POSE = "pose"
MOTION = "motion"

_REGISTRY: dict[str, type["Gesture"]] = {}


class Gesture:
    id: ClassVar[str] = ""
    name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    kind: ClassVar[str] = POSE
    icon: ClassVar[str] = "✋"
    order: ClassVar[int] = 100          # position in the catalogue

    def reset(self) -> None:
        """Forget any history (called after a gesture fires or the hand is lost)."""


class PoseGesture(Gesture):
    kind = POSE

    def score(self, f: FrameFeatures) -> float:
        """Confidence 0..1 that the hand is in this pose right now."""
        raise NotImplementedError


class MotionGesture(Gesture):
    kind = MOTION

    def update(self, f: FrameFeatures, settings: dict) -> bool:
        """Feed one frame (hand may be absent). Return True when the motion completes."""
        raise NotImplementedError


def register_gesture(cls: type[Gesture]) -> type[Gesture]:
    if not cls.id:
        raise ValueError(f"{cls.__name__} has no id")
    if cls.id in _REGISTRY and _REGISTRY[cls.id] is not cls:
        raise ValueError(f"Duplicate gesture id {cls.id!r}")
    _REGISTRY[cls.id] = cls
    return cls


def registry() -> dict[str, type[Gesture]]:
    return dict(_REGISTRY)
