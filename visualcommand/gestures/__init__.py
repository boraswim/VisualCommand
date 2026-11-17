"""Gesture catalogue (hand poses). Every module in this package is imported so its
@register_gesture classes show up in the settings window."""
from __future__ import annotations

import importlib
import pkgutil

from visualcommand.gestures.base import (  # noqa: F401  (re-exported)
    PoseGesture, register_gesture, registry,
)

# Listed explicitly so frozen builds always include them; pkgutil picks up any extra modules.
_BUILTIN_MODULES = ("builtin_poses", "rule_poses")
_loaded = False


def load_all() -> None:
    global _loaded
    if _loaded:
        return
    names = list(_BUILTIN_MODULES)
    for info in pkgutil.iter_modules(__path__):
        if info.name not in names and info.name != "base":
            names.append(info.name)
    for name in names:
        importlib.import_module(f"{__name__}.{name}")
    _loaded = True


def catalogue() -> list[type[PoseGesture]]:
    """All gestures in display order."""
    load_all()
    return sorted(registry().values(), key=lambda g: (g.order, g.name))
