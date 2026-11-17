"""Developer tool: record deliberate poses vs everyday hand movement (numbers only).

First prompts a few deliberate poses, then asks you to just behave normally (type,
use the mouse, touch your face, stretch...) so accidental detections can be found.
Stores per frame only MediaPipe's numbers: 21 landmarks with x, y and z (depth),
pose label/score and handedness. Never an image.

Usage:  python scripts/diagnose_false_triggers.py OUT.json [--pose Open_Palm] [--camera 0]
"""
from __future__ import annotations

import argparse
import json
import threading
import time
import tkinter as tk

import cv2

from visualcommand import lighting
from visualcommand.features import HAND_CONNECTIONS
from visualcommand.tracker import FRAME_SIZE, create_recognizer
from visualcommand.winutil import set_dpi_aware

POSE_TEXT = {"Open_Palm": "OPEN PALM ✋ facing the camera"}


def plan_for(pose: str) -> list[tuple[str, str, float, float]]:
    """(label, text, ready seconds, act seconds)"""
    text = POSE_TEXT.get(pose, pose)
    steps = []
    for side in ("right", "left", "right", "left"):
        steps.append((f"{pose}:{side}", f"{side.upper()} hand: {text}", 1.3, 2.7))
    steps.append(("natural", "Act NORMALLY now: type, use the mouse, touch your face,\n"
                             "stretch, pick something up, wave at someone...\n"
                             f"Anything EXCEPT a deliberate {pose.replace('_', ' ').lower()}",
                  2.0, 40.0))
    return steps


class Recorder(threading.Thread):
    def __init__(self, camera: int, mirror: bool):
        super().__init__(daemon=True)
        self.camera, self.mirror = camera, mirror
        self.frames: list[dict] = []
        self.label = None
        self.latest = []
        self.done = threading.Event()
        self.error = ""

    def run(self):
        try:
            cap = cv2.VideoCapture(self.camera, cv2.CAP_DSHOW,
                                   [cv2.CAP_PROP_FRAME_WIDTH, 640, cv2.CAP_PROP_FRAME_HEIGHT, 480])
            if not cap.isOpened():
                self.error = "Camera unavailable (is VisualCommand still running?)"
                return
            rec = create_recognizer(0.7)
            enh = lighting.Enhancer()
            import mediapipe as mp
            ts = 0
            while not self.done.is_set():
                ok, frame = cap.read()
                if not ok:
                    continue
                now = time.monotonic()
                ts = max(ts + 1, int(now * 1000))
                img = cv2.resize(frame, FRAME_SIZE, interpolation=cv2.INTER_AREA)
                del frame
                if self.mirror:
                    img = cv2.flip(img, 1)
                light = lighting.analyze(img)
                img = enh.apply(img, light, "auto")
                image = mp.Image(image_format=mp.ImageFormat.SRGB,
                                 data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
                del img
                res = rec.recognize_for_video(image, ts)
                hands = []
                for i, lm in enumerate(res.hand_landmarks or []):
                    g = res.gestures[i][0] if res.gestures and res.gestures[i] else None
                    h = res.handedness[i][0] if res.handedness and res.handedness[i] else None
                    hands.append({
                        "lm": [[round(p.x, 4), round(p.y, 4), round(p.z, 4)] for p in lm],
                        "mp_label": g.category_name if g else "None",
                        "mp_score": round(g.score, 3) if g else 0.0,
                        "handedness": h.category_name if h else "",
                        "handedness_score": round(h.score, 3) if h else 0.0,
                    })
                self.latest = hands
                self.frames.append({"t": now, "label": self.label, "lighting": light, "hands": hands})
            cap.release()
            rec.close()
        except Exception as exc:
            self.error = repr(exc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--pose", default="Open_Palm")
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--mirror", action="store_true", help="flip frames (match mirror_image=true)")
    args = ap.parse_args()
    set_dpi_aware()
    rec = Recorder(args.camera, args.mirror)
    rec.start()

    root = tk.Tk()
    root.title("VisualCommand false-trigger check (records numbers only, no images)")
    root.attributes("-topmost", True)
    root.configure(bg="#1f1f23")
    title = tk.Label(root, font=("Segoe UI Semibold", 18), fg="white", bg="#1f1f23", width=52,
                     justify="center")
    title.pack(pady=(18, 4))
    sub = tk.Label(root, font=("Segoe UI", 12), fg="#bbbbbb", bg="#1f1f23")
    sub.pack()
    canvas = tk.Canvas(root, width=480, height=360, bg="#2b2b31", highlightthickness=0)
    canvas.pack(pady=12)

    plan = []
    t = time.monotonic() + 3.0
    for label, text, ready, act in plan_for(args.pose):
        plan.append((t, t + ready, t + ready + act, label, text))
        t += ready + act
    end_time = t

    def tick():
        now = time.monotonic()
        if rec.error:
            title.configure(text="Error", fg="#ff7070")
            sub.configure(text=rec.error)
            root.after(4000, root.destroy)
            return
        if now >= end_time:
            rec.done.set()
            title.configure(text="Done, thank you!", fg="#7ee2a0")
            sub.configure(text="Saving…")
            root.after(800, root.destroy)
            return
        cur = next((p for p in plan if p[0] <= now < p[2]), None)
        if cur is None:
            rec.label = None
            title.configure(text="Get ready", fg="white")
            sub.configure(text=f"Starting in {max(0, plan[0][0] - now):.0f} s")
        else:
            start, act, stop, label, text = cur
            idx = plan.index(cur) + 1
            if now < act:
                rec.label = None
                title.configure(text=f"Next: {text}", fg="#bbbbbb")
                sub.configure(text=f"Step {idx}/{len(plan)} · starts in {act - now:.1f} s")
            else:
                rec.label = label
                title.configure(text=("NOW: " if label != "natural" else "") + text, fg="#7ee2a0")
                sub.configure(text=f"Step {idx}/{len(plan)} · {stop - now:.0f} s left")
        canvas.delete("all")
        for h in rec.latest:
            # drawn mirrored so it moves like a mirror
            pts = [((1 - x) * 480, y * 360) for x, y, _z in h["lm"]]
            for a, b in HAND_CONNECTIONS:
                canvas.create_line(*pts[a], *pts[b], fill="#58dc78", width=2)
        root.after(33, tick)

    root.after(50, tick)
    root.mainloop()
    rec.done.set()
    rec.join(timeout=3)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"pose": args.pose, "frames": rec.frames}, fh)
    print(f"Saved {len(rec.frames)} frames to {args.out}; error={rec.error or 'none'}")


if __name__ == "__main__":
    main()
