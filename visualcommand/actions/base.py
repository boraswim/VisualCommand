"""Action registry. To add an action, decorate a function in any module of
visualcommand/actions/ with @register_action; it appears in every gesture's dropdown.

An action function receives (ctx, params) and may return a short message for
the notification. `ctx` is the running App (gives access to pause_tracking etc.).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

NONE_ID = "none"


@dataclass(frozen=True)
class Param:
    key: str
    label: str
    placeholder: str = ""


@dataclass(frozen=True)
class ActionSpec:
    id: str
    name: str
    func: Callable
    description: str = ""
    group: str = "General"
    params: tuple[Param, ...] = field(default_factory=tuple)
    order: int = 100
    # > 0: the action waits for confirmation. A popup counts down this many seconds
    # with Execute / Cancel buttons and runs the action when the countdown ends.
    confirm_seconds: int = 0


# Order of the categories in the action dropdown.
GROUP_ORDER = ("System", "Media", "Audio", "Power", "VisualCommand", "General")

_REGISTRY: dict[str, ActionSpec] = {}


def register_action(id: str, name: str, description: str = "", group: str = "General",
                    params: tuple[Param, ...] = (), order: int = 100, confirm_seconds: int = 0):
    def deco(func: Callable) -> Callable:
        if id in _REGISTRY:
            raise ValueError(f"Duplicate action id {id!r}")
        _REGISTRY[id] = ActionSpec(id, name, func, description, group, tuple(params), order,
                                   confirm_seconds)
        return func
    return deco


def registry() -> dict[str, ActionSpec]:
    return dict(_REGISTRY)
