"""Camera worker thread.

Privacy: each frame lives only in local variables for one loop iteration. Nothing
is written to disk, logged or sent anywhere. When tracking is off, paused or the
PC is locked, the camera is released (its LED goes off).
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque

import cv2
import numpy as np

from visualcommand import lighting
from visualcommand.features import (
    HAND_CONNECTIONS, FrameFeatures, build_hands, drop_phantom_hands, plausible_hand,
)
from visualcommand.hands import HandSlots
from visualcommand.paths import model_path
from visualcommand.winutil import session_locked

log = logging.getLogger(__name__)

LOCK_CHECK_RUNNING = 1.0   # s between lock checks while the camera is on
LOCK_CHECK_LOCKED = 0.5    # s between checks while locked: how fast an unlock is noticed
START_SUPPRESS = 0.6       # s after the camera starts during which nothing fires

PREVIEW_WINDOW = "VisualCommand preview (not recorded)"
ACTIVE_HOLD = 2.0       # stay in active mode this long after the hand disappears
# One analysis size for idle and active: MediaPipe resizes to its own small model
# inputs anyway, so a smaller idle frame saved almost no CPU but gave a blurrier
# first look at a hand that had just appeared (often already in its pose).
FRAME_SIZE = (480, 360)
ACTIVE_SIZE = FRAME_SIZE

# Status values shown in the tray / settings window
OFF, STARTING, RUNNING, PAUSED, LOCKED, CAMERA_BUSY, ERROR = (
    "off", "starting", "running", "paused", "locked", "camera busy", "error")


MAX_DETECTION_CONFIDENCE = 0.5


def recognizer_thresholds(strictness: float) -> dict[str, float]:
    """MediaPipe confidence thresholds for a given 'hand detection strictness'.

    Detection (the palm detector finding a *new* hand) stays lenient: a fist,
    thumbs-up or peace sign shows little palm and scores lower than an open hand,
    so a strict value meant poses made straight into the frame were never found.
    Presence (the landmark model confirming "this really is a hand") carries the
    strictness instead: that is what drops shadows and clothing folds.
    """
    return {
        "min_hand_detection_confidence": min(MAX_DETECTION_CONFIDENCE, strictness),
        "min_hand_presence_confidence": strictness,
        "min_tracking_confidence": max(0.3, strictness - 0.1),
    }


def create_recognizer(strictness: float = 0.7):
    """MediaPipe gesture recognizer in VIDEO mode, model loaded from the bundled file."""
    from mediapipe.tasks.python import vision
    from mediapipe.tasks.python.core.base_options import BaseOptions

    # Load from bytes: no path/encoding issues, and clearly nothing fetched remotely.
    model = model_path().read_bytes()
    options = vision.GestureRecognizerOptions(
        base_options=BaseOptions(model_asset_buffer=model),
        running_mode=vision.RunningMode.VIDEO,
        # Two hands: if something that isn't a hand (a shadow on clothing) gets
        # picked up, your real hand still has a free slot and is detected.
        num_hands=2,
        **recognizer_thresholds(strictness),
    )
    return vision.GestureRecognizer.create_from_options(options)


class Tracker(threading.Thread):
    def __init__(self, app) -> None:
        super().__init__(name="tracker", daemon=True)
        self.app = app
        self.cfg = app.cfg
        self._stop_event = threading.Event()  # not '_stop': that name is used by threading.Thread itself
        self._wake = threading.Event()
        self.status = OFF
        self.lighting = lighting.GOOD
        self.preview = False
        self._preview_open = False
        self._open_camera_settings = False
        self._orientation_check: dict | None = None
        self._cap: cv2.VideoCapture | None = None
        self._cap_index: int | None = None
        self._recognizer = None
        self._recognizer_strictness: float | None = None
        self._hands = HandSlots(2)
        self._enhancer = lighting.Enhancer()
        self._last_ts = 0
        self._last_hand = 0.0
        self._busy_notified = False
        # stats for --bench and the preview overlay
        self.stats = {"frames": 0, "proc_ms": deque(maxlen=60), "fps": 0.0}

    # --- control from other threads ----------------------------------------------
    def stop(self) -> None:
        self._stop_event.set()
        self._wake.set()

    def wake(self) -> None:
        """Re-check settings now (tracking toggled, camera changed, ...)."""
        self._wake.set()

    def set_preview(self, on: bool) -> None:
        self.preview = on
        self.wake()

    def check_orientation(self, on_done, seconds: float = 4.0) -> None:
        """Find out whether this camera delivers a mirrored picture.

        The user raises their RIGHT hand. MediaPipe labels it "Right" only when it
        sees the camera's natural (unmirrored) view; if it says "Left", the picture
        the app feeds it is mirrored and the flip setting gets toggled. `on_done(message, ok)` is called from the
        tracker thread.
        """
        self._orientation_check = {"until": time.monotonic() + seconds, "labels": [],
                                   "on_done": on_done}
        self.wake()

    def _feed_orientation_check(self, hands, now: float) -> None:
        chk = self._orientation_check
        if chk is None:
            return
        if len(hands) == 1 and hands[0].extra.get("handedness_score", 0) >= 0.8:
            chk["labels"].append(hands[0].handedness)
        if now < chk["until"] and len(chk["labels"]) < 25:
            return
        self._orientation_check = None
        labels = chk["labels"]
        if len(labels) < 5:
            chk["on_done"]("Couldn't see one hand clearly. Raise only your right hand and try again.",
                           False)
            return
        right = labels.count("Right") / len(labels)
        mirror = bool(self.cfg.get("mirror_image", False))
        if right >= 0.7:
            chk["on_done"]("Camera orientation is correct.", True)
        elif right <= 0.3:
            self.cfg.set("mirror_image", not mirror)
            log.info("Orientation check: switching mirror_image to %s", not mirror)
            chk["on_done"]("Fixed: left and right hands (and pointing directions) are now "
                           "recognised correctly.", True)
        else:
            chk["on_done"]("Result was unclear. Keep your left hand out of view and try again.",
                           False)

    def request_camera_settings(self) -> None:
        self._open_camera_settings = True
        self.wake()

    # --- internals -------------------------------------------------------------------
    def _set_status(self, status: str) -> None:
        if status != self.status:
            self.status = status
            log.info("Tracker status: %s", status)
            self.app.on_tracker_status()

    def _open(self) -> bool:
        index = int(self.cfg.get("camera_index", 0))
        t0 = time.perf_counter()
        # Pass the frame size when opening. Setting properties afterwards restarts the
        # DirectShow graph each time (measured: ~1.35 s per change, 3.9 s total vs
        # 1.05 s this way), which made the camera slow to come back after unlocking.
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW, [
            cv2.CAP_PROP_FRAME_WIDTH, 640,
            cv2.CAP_PROP_FRAME_HEIGHT, 480,
        ])
        if not cap.isOpened():
            cap.release()
            return False
        ok = False
        for _ in range(10):  # some cameras need a few frames to wake up
            ok = cap.grab()
            if ok:
                break
            time.sleep(0.05)
        if not ok:
            cap.release()
            return False
        self._cap, self._cap_index = cap, index
        log.info("Camera %d open in %.2f s", index, time.perf_counter() - t0)
        return True

    def _close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            self._cap_index = None
        self._close_preview()

    def _close_preview(self) -> None:
        if not self._preview_open:
            return
        self._preview_open = False
        try:
            cv2.destroyWindow(PREVIEW_WINDOW)
            cv2.waitKey(1)
        except cv2.error:
            pass

    def _ensure_recognizer(self) -> None:
        # Rounded so dragging the settings slider doesn't rebuild the model on every pixel.
        strictness = round(float(self.cfg.get("hand_strictness", 0.7)) * 20) / 20
        if self._recognizer is not None and self._recognizer_strictness == strictness:
            return
        if self._recognizer is not None:
            self._recognizer.close()
            self._recognizer = None
        self._recognizer = create_recognizer(strictness)
        self._recognizer_strictness = strictness
        self._last_ts = 0
        log.info("Hand detector ready (strictness %.2f)", strictness)

    def _wait(self, seconds: float) -> None:
        self._wake.wait(seconds)
        self._wake.clear()

    # --- main loop -------------------------------------------------------------------
    def run(self) -> None:
        # A bug in one frame must never leave the app silently dead: log it, reset
        # and carry on. Only give up if it keeps failing straight away.
        failures: deque = deque(maxlen=5)
        while not self._stop_event.is_set():
            try:
                self._loop()
            except Exception:
                log.exception("Tracker error, restarting")
                now = time.monotonic()
                failures.append(now)
                self._close()
                self._hands = HandSlots(2)
                if self._recognizer is not None:
                    self._recognizer.close()
                    self._recognizer = None
                if len(failures) == failures.maxlen and now - failures[0] < 60:
                    self._set_status(ERROR)
                    self.app.notify("Something keeps going wrong. Turn tracking on again to retry.",
                                    title="Tracking stopped", error=True)
                    self.cfg.set("tracking_enabled", False)
                    failures.clear()
                self._wait(2.0)
        self._close()
        if self._recognizer is not None:
            self._recognizer.close()

    def _loop(self) -> None:
        next_due = 0.0
        next_lock_check = 0.0
        while not self._stop_event.is_set():
            now = time.monotonic()

            if not self.cfg.get("tracking_enabled", True):
                self._close()
                self._set_status(OFF)
                self._wait(5.0)
                continue
            if self.app.paused_until > time.time():
                self._close()
                self._set_status(PAUSED)
                self._wait(min(5.0, self.app.paused_until - time.time()))
                continue
            if now >= next_lock_check:
                next_lock_check = now + LOCK_CHECK_RUNNING
                if session_locked():
                    self._close()
                    self._set_status(LOCKED)
                    # Notice the unlock quickly; the check is a cheap Windows call.
                    self._wait(LOCK_CHECK_LOCKED)
                    next_lock_check = 0.0
                    continue
            if self._cap is not None and self._cap_index != int(self.cfg.get("camera_index", 0)):
                self._close()   # camera changed in settings

            if self._cap is None:
                self._set_status(STARTING)
                if not self._open():
                    self._set_status(CAMERA_BUSY)
                    if not self._busy_notified:
                        self._busy_notified = True
                        self.app.notify("It may be in use by another app. Retrying every 10 seconds.",
                                        title="Camera unavailable", error=True)
                    self._wait(10.0)
                    continue
                self._busy_notified = False
                self._ensure_recognizer()
                # Nothing fires right away (e.g. a hand still up right after unlocking).
                self._hands.suppress(time.monotonic(), START_SUPPRESS)
                self._set_status(RUNNING)
                next_due = 0.0

            self._ensure_recognizer()   # no-op unless the strictness setting changed

            if self._open_camera_settings:
                self._open_camera_settings = False
                self._cap.set(cv2.CAP_PROP_SETTINGS, 1)   # the driver's own dialog

            # grab() blocks until the camera's next frame; skipped frames are never decoded.
            t0 = time.monotonic()
            if not self._cap.grab():
                log.warning("Camera stopped delivering frames")
                self._close()
                self._wait(1.0)
                continue
            if time.monotonic() - t0 < 0.004:
                time.sleep(0.01)  # backend returned instantly; don't spin

            now = time.monotonic()
            active = self.preview or (now - self._last_hand) < ACTIVE_HOLD
            fps = self.cfg.get("active_fps", 15) if active else self.cfg.get("idle_fps", 4)
            if now < next_due:
                continue
            next_due = now + 1.0 / max(1, fps)

            ok, frame = self._cap.retrieve()
            if not ok or frame is None:
                continue
            self._process(frame, active, now)
            del frame

    def _process(self, frame: np.ndarray, active: bool, now: float) -> None:
        t0 = time.perf_counter()
        size = FRAME_SIZE
        small = cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
        if self.cfg.get("mirror_image", False):
            # MediaPipe's hand model wants the camera's natural (unmirrored) view;
            # only cameras that deliver a mirrored picture need flipping back.
            small = cv2.flip(small, 1)

        light = lighting.analyze(small)
        if light != self.lighting:
            self.lighting = light
            self.app.on_tracker_status()
        small = self._enhancer.apply(small, light, self.cfg.get("lighting_mode", "auto"))

        import mediapipe as mp
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        ts = max(self._last_ts + 1, int(now * 1000))
        self._last_ts = ts
        result = self._recognizer.recognize_for_video(image, ts)

        # Positions converted to your point of view (x grows to your right).
        detected = build_hands(now, result, size[0] / size[1], light, to_user_view=True)
        hands = drop_phantom_hands([h for h in detected if plausible_hand(h)])
        if hands:
            self._last_hand = now
        self._feed_orientation_check(hands, now)

        mappings = self.cfg.mappings()
        events = self._hands.process(
            now, hands, light, set(mappings), self.cfg.sensitivity(),
            arm_id=self.cfg.get("arm_gesture", ""), arm_window=float(self.cfg.get("arm_window", 5.0)))
        for gid in events:
            self.app.on_gesture(gid)

        st = self.stats
        st["frames"] += 1
        st["proc_ms"].append((time.perf_counter() - t0) * 1000)

        if self.preview:
            kept = {id(h) for h in hands}
            self._show_preview(small, hands, [h for h in detected if id(h) not in kept])
        else:
            self._close_preview()

    def _show_preview(self, img: np.ndarray, hands: list[FrameFeatures],
                      rejected: list[FrameFeatures]) -> None:
        # Shown like a mirror, matching the hand positions (which are in your view).
        view = cv2.flip(img, 1)
        h, w = view.shape[:2]
        colours = [(90, 220, 120), (240, 170, 60)]          # hand 1 green, hand 2 blue
        for f, colour in [(r, (60, 60, 230)) for r in rejected] + list(zip(
                [s.current for s in self._hands.slots], colours)):
            if f is None or not f.hand or f.landmarks is None:
                continue
            pts = [(int(x * w), int(y * h)) for x, y in f.landmarks]
            for a, b in HAND_CONNECTIONS:
                cv2.line(view, pts[a], pts[b], colour, 2, cv2.LINE_AA)
            for p in pts:
                cv2.circle(view, p, 3, (255, 255, 255), -1, cv2.LINE_AA)
        ms = np.mean(self.stats["proc_ms"]) if self.stats["proc_ms"] else 0
        lines = []
        for i, s in enumerate(self._hands.slots, 1):
            f = s.current
            if f is None or not f.hand:
                lines.append(f"Hand {i}: -")
                continue
            pose, score = s.engine.last_pose
            fingers = "".join("1" if e else "0" for e in f.extended)
            lines.append(f"Hand {i}: {f.mp_label} {f.mp_score:.2f} | mapped {pose or '-'} "
                         f"{score:.2f} | fingers {fingers}")
            if f.mp_label == "Open_Palm":
                lines.append(f"   palm: facing {f.palm_facing:.2f} straight {f.straightness:.2f} "
                             f"spread {f.spread:.2f} width {f.palm_width:.2f} tilt {f.tilt:.0f}")
        lines += [
            f"Lighting: {self.lighting}   {ms:.1f} ms/frame" + (f"   rejected {len(rejected)}" if rejected else ""),
            "Esc closes. Frames are never saved.",
        ]
        for i, text in enumerate(lines):
            y = 18 + 18 * i
            cv2.putText(view, text, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(view, text, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.imshow(PREVIEW_WINDOW, view)
        self._preview_open = True
        key = cv2.waitKey(1) & 0xFF
        try:
            closed = cv2.getWindowProperty(PREVIEW_WINDOW, cv2.WND_PROP_VISIBLE) < 1
        except cv2.error:
            closed = True
        if key == 27 or closed:
            self.preview = False
            self._close_preview()
            self.app.on_tracker_status()
