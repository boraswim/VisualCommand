"""Action catalogue: everything a gesture can trigger."""
from __future__ import annotations

import importlib
import logging
import pkgutil

from visualcommand.actions.base import (  # noqa: F401  (re-exported)
    GROUP_ORDER, NONE_ID, ActionResult, ActionSpec, Param, register_action, registry,
)

log = logging.getLogger(__name__)

_BUILTIN_MODULES = ("system", "media", "audio", "power")
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


def _group_rank(group: str) -> int:
    return GROUP_ORDER.index(group) if group in GROUP_ORDER else len(GROUP_ORDER)


def catalogue() -> list[ActionSpec]:
    """All actions, grouped by category (GROUP_ORDER), then by their own order."""
    load_all()
    return sorted(registry().values(), key=lambda a: (_group_rank(a.group), a.order, a.name))


def run_action_result(action_id: str, params: dict | None, ctx) -> ActionResult | None:
    """Run an action by id. Returns its message (and optional click target), or None
    for an unknown action."""
    load_all()
    spec = registry().get(action_id)
    if spec is None:
        log.warning("Unknown action %s", action_id)
        return None
    result = spec.func(ctx, params or {})
    if isinstance(result, ActionResult):
        return result
    return ActionResult(result if isinstance(result, str) else spec.name)


def run_action(action_id: str, params: dict | None, ctx) -> str | None:
    """Run an action by id. Returns a message for the notification, or None."""
    result = run_action_result(action_id, params, ctx)
    return result.message if result else None
