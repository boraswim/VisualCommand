import threading

from visualcommand.tracker import Tracker


class _FakeApp:
    class cfg:
        @staticmethod
        def get(key, default=None):
            return default
    paused_until = 0.0

    def on_tracker_status(self): pass
    def notify(self, *a, **k): pass


def test_tracker_does_not_shadow_thread_internals():
    """Regression: 0.1.1 stored an Event in `self._stop`, hiding Thread._stop(),
    so join() on quit raised "'Event' object is not callable"."""
    t = Tracker(_FakeApp())
    own = set(vars(t)) - set(vars(threading.Thread()))
    clashes = own & set(dir(threading.Thread))
    assert not clashes, f"Tracker attributes shadow threading.Thread: {clashes}"


def test_unstarted_tracker_can_be_stopped():
    t = Tracker(_FakeApp())
    t.stop()
