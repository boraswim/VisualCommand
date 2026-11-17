"""Gesture plugin base class and the catalogue registry.

To add a gesture: subclass PoseGesture, return a 0..1 score per frame from
score(), decorate it with @register_gesture, and put it in any module inside
visualcommand/gestures/. The settings window lists it automatically.
"""
from __future__ import annotations

from typing import ClassVar

from visualcommand.features import FrameFeatures

_REGISTRY: dict[str, type["PoseGesture"]] = {}


class PoseGesture:
    id: ClassVar[str] = ""
    name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    icon: ClassVar[str] = "✋"
    order: ClassVar[int] = 100          # position in the catalogue

    def score(self, f: FrameFeatures) -> float:
        """Confidence 0..1 that the hand is in this pose right now."""
        raise NotImplementedError


def register_gesture(cls: type[PoseGesture]) -> type[PoseGesture]:
    if not cls.id:
        raise ValueError(f"{cls.__name__} has no id")
    if cls.id in _REGISTRY and _REGISTRY[cls.id] is not cls:
        raise ValueError(f"Duplicate gesture id {cls.id!r}")
    _REGISTRY[cls.id] = cls
    return cls


def registry() -> dict[str, type[PoseGesture]]:
    return dict(_REGISTRY)
