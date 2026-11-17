"""Cheap lighting analysis and enhancement for the in-memory frame.

Runs on the already-downscaled frame before inference. Nothing is stored.
"""
from __future__ import annotations

import math

import cv2
import numpy as np

GOOD, LOW, BACKLIT, FLAT = "good", "low", "backlit", "flat"


def analyze(frame_bgr: np.ndarray) -> str:
    """Classify the scene lighting from an 80x60 grey thumbnail (~0.1 ms)."""
    thumb = cv2.resize(frame_bgr, (80, 60), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(thumb, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    mean = float(gray.mean())
    std = float(gray.std())
    centre = float(gray[15:45, 20:60].mean())
    bright = float((gray > 0.9).mean())
    if mean < 0.22:
        return LOW
    if bright > 0.10 and centre < mean * 0.8:
        return BACKLIT
    if std < 0.10:
        return FLAT
    return GOOD


class Enhancer:
    """Gamma lift (lookup table) + CLAHE on luminance only."""

    def __init__(self) -> None:
        self._clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        self._luts: dict[float, np.ndarray] = {}

    def _lut(self, gamma: float) -> np.ndarray:
        gamma = round(gamma, 2)
        lut = self._luts.get(gamma)
        if lut is None:
            x = np.arange(256, dtype=np.float32) / 255.0
            lut = np.clip((x ** gamma) * 255.0, 0, 255).astype(np.uint8)
            self._luts[gamma] = lut
        return lut

    def apply(self, frame_bgr: np.ndarray, status: str, mode: str = "auto") -> np.ndarray:
        if mode == "off" or (mode == "auto" and status == GOOD):
            return frame_bgr
        ycc = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2YCrCb)
        y = ycc[:, :, 0]
        mean = float(y.mean()) / 255.0
        if mean < 0.4:
            # Pick the gamma that moves the mean brightness to ~0.45.
            gamma = max(0.35, min(1.0, math.log(0.45) / math.log(max(mean, 0.02))))
            y = cv2.LUT(y, self._lut(gamma))
        ycc[:, :, 0] = self._clahe.apply(y)
        return cv2.cvtColor(ycc, cv2.COLOR_YCrCb2BGR)
