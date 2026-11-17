"""Developer tool: guided per-hand pose check (records numbers only, no images).

Prompts each pose with your RIGHT and LEFT hand and runs two recognizers side by
side on every frame: one on the mirrored frame (what the app does) and one on the
camera frame as delivered. For each it stores MediaPipe's pose label/score,
handedness and the 21 landmark coordinates, so differences between hands (and
whether mirroring is right for this camera) can be analysed afterwards.

Usage:  python scripts/diagnose_poses.py OUT.json [--camera 0]
"""
from __future__ import annotations

import argparse
import json
import threading
import time
import tkinter as tk

import cv2

from visualcommand import lighting
from visualcommand.features import HAND_CONNECTIONS, build_hands
from visualcommand.tracker import FRAME_SIZE, create_recognizer
from visualcommand.winutil import set_dpi_aware

READY, HOLD = 1.3, 2.7
POSES = [
    ("Open_Palm", "OPEN PALM ✋ (palm facing the camera)"),
    ("Thumb_Up", "THUMBS UP 👍"),
    ("Closed_Fist", "FIST ✊"),
    ("Victory", "PEACE SIGN ✌"),
    ("Pointing_Up", "POINT UP ☝"),
    ("ILoveYou", "I LOVE YOU 🤟 (thumb, index, pinky)"),
    ("OK_Sign", "OK SIGN 👌"),
    ("Rock", "ROCK ON 🤘 (thumb tucked)"),
    ("Call_Me", "CALL ME 🤙"),
]
STEPS = [(pose, side, f"{side.upper()} hand: {text}") for pose, text in POSES
         for side in ("right", "left")]


class Recorder(threading.Thread):
    def __init__(self, camera: int):
        super().__init__(daemon=True)
        self.camera = camera
        self.frames: list[dict] = []
        self.step = None
        self.latest = []
        self.done = threading.Event()
        self.error = ""

    def run(self):
        try:
            cap = cv2.VideoCapture(self.camera, cv2.CAP_DSHOW)
            if not cap.isOpened():
                self.error = "Camera unavailable (is VisualCommand still running?)"
                return
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            recs = {"mirrored": create_recognizer(0.7), "raw": create_recognizer(0.7)}
            enh = lighting.Enhancer()
            import mediapipe as mp
            ts = 0
            aspect = FRAME_SIZE[0] / FRAME_SIZE[1]
            while not self.done.is_set():
                ok, frame = cap.read()
                if not ok:
                    continue
                now = time.monotonic()
                ts = max(ts + 1, int(now * 1000))
                raw = cv2.resize(frame, FRAME_SIZE, interpolation=cv2.INTER_AREA)
                del frame
                light = lighting.analyze(raw)
                raw = enh.apply(raw, light, "auto")
                entry = {"t": now, "step": self.step, "lighting": light}
                for name, img in (("mirrored", cv2.flip(raw, 1)), ("raw", raw)):
                    image = mp.Image(image_format=mp.ImageFormat.SRGB,
                                     data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
                    hands = build_hands(now, recs[name].recognize_for_video(image, ts), aspect, light)
                    entry[name] = [{
                        "landmarks": h.landmarks.round(4).tolist(),
                        "mp_label": h.mp_label, "mp_score": round(h.mp_score, 3),
                        "handedness": h.handedness,
                        "handedness_score": round(h.extra.get("handedness_score", 0.0), 3),
                    } for h in hands]
                    if name == "mirrored":
                        self.latest = hands
                del raw
                self.frames.append(entry)
            cap.release()
            for r in recs.values():
                r.close()
        except Exception as exc:
            self.error = repr(exc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--camera", type=int, default=0)
    args = ap.parse_args()
    set_dpi_aware()
    rec = Recorder(args.camera)
    rec.start()

    root = tk.Tk()
    root.title("VisualCommand pose check (records numbers only, no images)")
    root.attributes("-topmost", True)
    root.configure(bg="#1f1f23")
    title = tk.Label(root, font=("Segoe UI Semibold", 22), fg="white", bg="#1f1f23", width=42)
    title.pack(pady=(18, 4))
    sub = tk.Label(root, font=("Segoe UI", 12), fg="#bbbbbb", bg="#1f1f23")
    sub.pack()
    canvas = tk.Canvas(root, width=480, height=360, bg="#2b2b31", highlightthickness=0)
    canvas.pack(pady=12)
    status = tk.Label(root, font=("Segoe UI", 10), fg="#999999", bg="#1f1f23")
    status.pack(pady=(0, 14))

    plan = []
    t = time.monotonic() + 3.0
    for pose, side, text in STEPS:
        plan.append((t, t + READY, t + READY + HOLD, pose, side, text))
        t += READY + HOLD
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
            rec.step = None
            title.configure(text="Get ready: use ONE hand at a time", fg="white")
            sub.configure(text=f"Starting in {max(0, plan[0][0] - now):.0f} s · keep the other hand down")
        else:
            start, hold, stop, pose, side, text = cur
            idx = plan.index(cur) + 1
            if now < hold:
                rec.step = None
                title.configure(text=f"Next: {text}", fg="#bbbbbb")
                sub.configure(text=f"Step {idx}/{len(plan)} · get ready, hold in {hold - now:.1f} s")
            else:
                rec.step = [pose, side]
                title.configure(text=f"HOLD: {text}", fg="#7ee2a0")
                sub.configure(text=f"Step {idx}/{len(plan)} · {stop - now:.1f} s left · other hand down")
        canvas.delete("all")
        for h in rec.latest:
            pts = [(x * 480, y * 360) for x, y in h.landmarks]
            for a, b in HAND_CONNECTIONS:
                canvas.create_line(*pts[a], *pts[b], fill="#58dc78", width=2)
        status.configure(text=f"hands {len(rec.latest)} · frames {len(rec.frames)}")
        root.after(33, tick)

    root.after(50, tick)
    root.mainloop()
    rec.done.set()
    rec.join(timeout=3)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"frames": rec.frames}, fh)
    print(f"Saved {len(rec.frames)} frames to {args.out}; error={rec.error or 'none'}")


if __name__ == "__main__":
    main()
