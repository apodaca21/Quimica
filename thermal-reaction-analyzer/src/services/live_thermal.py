"""Muestreo de la vista USB FLIR como temperatura aparente de la escena."""

from __future__ import annotations

import time

import cv2
import numpy as np

from src.models.experiment import Experiment
from src.models.thermal_frame import DataOrigin, ThermalFrame
from src.utils.limits import MAX_SIM_FRAMES, THERMAL_HEIGHT, THERMAL_WIDTH

HUD_TOP = 72
HUD_LEFT = 86
HUD_RIGHT = 18
HUD_BOTTOM = 18
C_PER_GRAY = 0.12
SAMPLE_EVERY_S = 0.4


def crop_scene(gray: np.ndarray) -> np.ndarray:
    """Recorta overlays de la FLIR (escala y lecturas)."""
    high, width = gray.shape[:2]
    y0, y1 = HUD_TOP, max(HUD_TOP + 8, high - HUD_BOTTOM)
    x0, x1 = HUD_LEFT, max(HUD_LEFT + 8, width - HUD_RIGHT)
    return gray[y0:y1, x0:x1]


def apparent_matrix(
    frame_bgr: np.ndarray,
    gray0: float,
    t_ref_c: float = 24.0,
    c_per_gray: float = C_PER_GRAY,
) -> np.ndarray:
    """Mapa 160×120 a partir de la escena USB, anclado a la T que muestra la FLIR."""
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    scene = crop_scene(gray)
    small = cv2.resize(scene, (THERMAL_WIDTH, THERMAL_HEIGHT), interpolation=cv2.INTER_AREA)
    return (float(t_ref_c) + (small.astype(np.float32) - float(gray0)) * float(c_per_gray))


def scene_mean_gray(frame_bgr: np.ndarray) -> float:
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    return float(np.mean(crop_scene(gray)))


def maybe_append_live_frame(
    experiment: Experiment,
    frame_bgr: np.ndarray,
    state: dict,
    now_s: float | None = None,
) -> bool:
    """Agrega un cuadro si pasó el intervalo. Devuelve True si se guardó."""
    now = time.monotonic() if now_s is None else now_s
    last = float(state.get("live_sample_t") or 0.0)
    if now - last < SAMPLE_EVERY_S:
        return False
    if len(experiment.numeric_frames) >= MAX_SIM_FRAMES:
        return False

    mean_gray = scene_mean_gray(frame_bgr)
    if state.get("live_gray0") is None:
        state["live_gray0"] = mean_gray
        state["live_t0"] = now
    gray0 = float(state["live_gray0"])
    t_ref = float(state.get("live_t_ref_c") or 24.0)
    t0 = float(state.get("live_t0") or now)
    matrix = apparent_matrix(frame_bgr, gray0, t_ref)
    frame = ThermalFrame(
        matrix=matrix,
        unit="°C",
        timestamp_s=max(0.0, now - t0),
        origin=DataOrigin.VISTA_FLIR_USB,
        experiment_id=experiment.id,
        source_name=experiment.name,
        metadata={"estimacion": "vista_usb_no_radiometrica", "gray_medio": mean_gray},
    )
    experiment.frames.append(frame)
    state["live_sample_t"] = now
    return True
