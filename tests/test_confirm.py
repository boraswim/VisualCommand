"""Countdown confirmation popup and routing of power actions."""
import time
import tkinter as tk

import pytest

from visualcommand.main import App
from visualcommand.toast import Toast, countdown_text


@pytest.fixture(scope="module")
def root():
    # One Tk for the whole module: creating/destroying many Tk instances in a row
    # intermittently fails on Windows ("Can't find a usable tk.tcl").
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


def pump(root, until, timeout=3.0):
    end = time.monotonic() + timeout
    while not until() and time.monotonic() < end:
        root.update()
        time.sleep(0.01)
    return until()


def test_countdown_end_executes_and_closes(root):
    t, done = Toast(root), []
    t.confirm("✌ Peace sign", "Shut down", 0.4,
              on_execute=lambda: done.append("exec"), on_cancel=lambda: done.append("cancel"))
    assert t.confirming
    assert pump(root, lambda: done)
    assert done == ["exec"] and not t.confirming and t._win is None


def test_cancel_button_cancels(root):
    t, done = Toast(root), []
    t.confirm("Test", "Restart", 5, on_execute=lambda: done.append("exec"),
              on_cancel=lambda: done.append("cancel"))
    root.update()
    t._confirm["buttons"][1].invoke()          # the Cancel button
    root.update()
    assert done == ["cancel"] and not t.confirming
    time.sleep(0.2)
    root.update()
    assert done == ["cancel"]                  # countdown must not fire afterwards


def test_execute_button_runs_immediately(root):
    t, done = Toast(root), []
    t.confirm("Test", "Sleep", 5, on_execute=lambda: done.append("exec"),
              on_cancel=lambda: done.append("cancel"))
    root.update()
    t._confirm["buttons"][0].invoke()          # the Execute button
    assert done == ["exec"]


def test_plain_popups_dont_replace_a_pending_confirmation(root):
    t, done = Toast(root), []
    t.confirm("Test", "Shut down", 5, on_execute=lambda: done.append("exec"),
              on_cancel=lambda: done.append("cancel"))
    assert t.show("👍 Thumbs up", "Screenshot saved") is False
    t.hide_message()                           # e.g. before a screenshot
    assert t.confirming and done == []
    t.cancel()


def test_newer_confirmation_cancels_the_older_one(root):
    t, done = Toast(root), []
    t.confirm("A", "Shut down", 5, on_execute=lambda: done.append("execA"),
              on_cancel=lambda: done.append("cancelA"))
    t.confirm("B", "Restart", 5, on_execute=lambda: done.append("execB"),
              on_cancel=lambda: done.append("cancelB"))
    assert done == ["cancelA"]
    t.execute_now()
    assert done == ["cancelA", "execB"]


def test_countdown_text_rounds_up():
    assert countdown_text("Shut down", 10) == "Shut down in 10 s"
    assert countdown_text("Shut down", 9.2) == "Shut down in 10 s"
    assert countdown_text("Shut down", 0.1) == "Shut down in 1 s"


class _Fake:
    def __init__(self):
        self.confirmed, self.ran = [], []
        fake = self

        class Ex:
            def submit(self, fn, *args):
                fake.ran.append(args)
        self._executor = Ex()

    def _request_confirm(self, gid, spec, params):
        self.confirmed.append((gid, spec.id))

    def _run_action(self, *args):
        pass


@pytest.mark.parametrize("gid", ["Victory", ""])          # gesture and Test button
def test_power_actions_go_through_confirmation(gid):
    f = _Fake()
    App._dispatch(f, gid, "shutdown", {})
    assert f.confirmed == [(gid, "shutdown")] and f.ran == []


class _ConfirmApp:
    """Just enough of App for _request_confirm."""
    def __init__(self, sounds=True):
        self.posted = []
        self.cfg = type("C", (), {"get": staticmethod(lambda k, d=None: sounds if k == "sounds" else d)})

    def _label(self, gid):
        return App._label(self, gid)

    def post(self, fn):
        self.posted.append(fn)


@pytest.mark.parametrize("gid, expected", [("Victory", ["attention"]), ("", [])])
def test_power_popup_plays_attention_sound_for_gestures_only(monkeypatch, gid, expected):
    from visualcommand import actions, sound
    played = []
    monkeypatch.setattr(sound, "play", lambda name="action": played.append(name))
    App._request_confirm(_ConfirmApp(), gid, actions.registry()["shutdown"], {})
    assert played == expected


def test_three_fingers_icon_is_not_the_vulcan_salute():
    from visualcommand.gestures import registry
    assert registry()["Three_Fingers"].icon != "🖖"


def test_other_actions_run_directly():
    f = _Fake()
    App._dispatch(f, "Thumb_Up", "screenshot", {})
    assert f.confirmed == [] and f.ran == [("Thumb_Up", "screenshot", {})]
