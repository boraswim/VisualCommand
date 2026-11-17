"""Shutdown actions: check the command sent, never actually run shutdown.exe."""
import pytest

from visualcommand import actions
from visualcommand.actions import system


@pytest.fixture
def calls(monkeypatch):
    seen = []

    class Proc:
        returncode = 0

    def fake_run(cmd, **kw):
        seen.append((cmd, kw))
        return Proc()

    monkeypatch.setattr(system.subprocess, "run", fake_run)
    return seen


def test_shutdown_schedules_30_second_shutdown(calls):
    msg = actions.run_action("shutdown_30s", {}, ctx=None)
    cmd, kw = calls[0]
    assert cmd[0].lower().endswith("shutdown.exe")
    assert cmd[1:4] == ["/s", "/t", "30"]
    assert "/f" not in cmd                       # never force-close unsaved apps
    assert kw["creationflags"] == system.subprocess.CREATE_NO_WINDOW
    assert "30 seconds" in msg


def test_cancel_shutdown(calls):
    assert actions.run_action("cancel_shutdown", {}, ctx=None) == "Shutdown cancelled"
    assert calls[0][0][1:] == ["/a"]


def test_reports_already_scheduled(monkeypatch):
    class Proc:
        returncode = 1190
    monkeypatch.setattr(system.subprocess, "run", lambda cmd, **kw: Proc())
    assert "already scheduled" in actions.run_action("shutdown_30s", {}, ctx=None)


def test_both_listed_in_catalogue():
    ids = [a.id for a in actions.catalogue()]
    assert "shutdown_30s" in ids and "cancel_shutdown" in ids
