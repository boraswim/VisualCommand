"""Power actions: check the commands sent, never actually shut down / restart / sleep."""
import json

import pytest

from visualcommand import actions
from visualcommand.actions import power
from visualcommand.config import Config


@pytest.fixture
def calls(monkeypatch):
    seen = []

    class Proc:
        returncode = 0

    def fake_run(cmd, **kw):
        seen.append((cmd, kw))
        return Proc()

    monkeypatch.setattr(power.subprocess, "run", fake_run)
    return seen


def test_power_category_has_shutdown_restart_sleep_with_10s_countdown():
    specs = {a.id: a for a in actions.catalogue() if a.group == "Power"}
    assert set(specs) == {"shutdown", "restart", "sleep"}
    assert all(s.confirm_seconds == 10 for s in specs.values())


def test_old_shutdown_actions_removed_and_lock_stays_instant():
    ids = {a.id: a for a in actions.catalogue()}
    assert "shutdown_30s" not in ids and "cancel_shutdown" not in ids
    assert ids["lock_pc"].confirm_seconds == 0 and ids["lock_pc"].group == "System"


def test_categories_come_in_order():
    groups = [a.group for a in actions.catalogue()]
    seen = list(dict.fromkeys(groups))
    assert seen == sorted(seen, key=lambda g: actions.GROUP_ORDER.index(g))
    assert groups == sorted(groups, key=lambda g: actions.GROUP_ORDER.index(g))


def test_shutdown_runs_immediately_without_force(calls):
    """The countdown happens in our popup, so Windows gets no extra delay."""
    assert actions.run_action("shutdown", {}, ctx=None) == "Shutting down"
    cmd, kw = calls[0]
    assert cmd[0].lower().endswith("shutdown.exe")
    assert cmd[1:] == ["/s", "/t", "0"]
    assert kw["creationflags"] == power.subprocess.CREATE_NO_WINDOW


def test_restart_command(calls):
    assert actions.run_action("restart", {}, ctx=None) == "Restarting"
    assert calls[0][0][1:] == ["/r", "/t", "0"]


def test_failed_shutdown_raises(monkeypatch):
    class Proc:
        returncode = 5
    monkeypatch.setattr(power.subprocess, "run", lambda cmd, **kw: Proc())
    with pytest.raises(RuntimeError):
        actions.run_action("shutdown", {}, ctx=None)


def test_sleep_calls_setsuspendstate_without_hibernate(monkeypatch):
    seen = []

    class FakePowrprof:
        @staticmethod
        def SetSuspendState(hibernate, force, wake):
            seen.append((hibernate, force, wake))
            return 1

    monkeypatch.setattr(power.ctypes, "windll", type("W", (), {"powrprof": FakePowrprof})())
    assert actions.run_action("sleep", {}, ctx=None) == "Going to sleep"
    assert seen == [(False, False, False)]


def test_old_shutdown_mappings_migrated(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"version": 6, "mappings": {
        "Call_Me": {"action": "shutdown_30s"}, "Rock": {"action": "cancel_shutdown"},
        "Thumb_Up": {"action": "screenshot"}}}), encoding="utf-8")
    maps = Config(p).mappings()
    assert maps["Call_Me"]["action"] == "shutdown"
    assert "Rock" not in maps and maps["Thumb_Up"]["action"] == "screenshot"
