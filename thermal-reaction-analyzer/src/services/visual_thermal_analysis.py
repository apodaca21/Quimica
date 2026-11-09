"""Análisis visual relativo del video térmico coloreado. No convierte color a °C."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from src.models.telemetry import VisualRoi


@dataclass
class VisualStats:
    mean_bgr: tuple[float, float, float]
    mean_gray: float
    std_gray: float
    centroid: tuple[float, float] | None
    hot_area_px: int
    contour_count: int
    notes: tuple[str, ...]


def roi_slice(frame: np.ndarray, roi: VisualRoi) -> np.ndarray:
    region = roi.clamp()
    alto, ancho = frame.shape[:2]
    x0 = int(region.x * ancho)
    y0 = int(region.y * alto)
    x1 = min(ancho, x0 + max(2, int(region.w * ancho)))
    y1 = min(alto, y0 + max(2, int(region.h * alto)))
    return frame[y0:y1, x0:x1]


def visual_stats(frame_bgr: np.ndarray, roi: VisualRoi, hot_percentile: float = 85.0) -> VisualStats:
    crop = roi_slice(frame_bgr, roi)
    notes = (
        "Análisis visual relativo del video coloreado.",
        "No se convierte intensidad ni paleta a grados Celsius.",
        "Si la FLIR autoescala la paleta, estas comparaciones dejan de ser comparables.",
    )
    if crop.size == 0:
        return VisualStats((0, 0, 0), 0.0, 0.0, None, 0, 0, notes + ("ROI vacía.",))
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    mean_bgr = tuple(float(v) for v in np.mean(crop.reshape(-1, 3), axis=0))
    mean_gray = float(np.mean(gray))
    std_gray = float(np.std(gray))
    threshold = float(np.percentile(gray, hot_percentile))
    mask = (gray >= threshold).astype(np.uint8) * 255
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    area = int(np.count_nonzero(mask))
    centroid = None
    if area > 0:
        ys, xs = np.nonzero(mask)
        centroid = (float(np.mean(xs)), float(np.mean(ys)))
    return VisualStats(mean_bgr, mean_gray, std_gray, centroid, area, len(contours), notes)


def draw_roi_and_contours(
    frame_bgr: np.ndarray,
    roi: VisualRoi,
    background: VisualRoi | None = None,
    hot_percentile: float = 85.0,
    draw_contours: bool = True,
) -> np.ndarray:
    canvas = frame_bgr.copy()
    alto, ancho = canvas.shape[:2]

    def _rect(region: VisualRoi, color: tuple[int, int, int], label: str) -> None:
        box = region.clamp()
        x0 = int(box.x * ancho)
        y0 = int(box.y * alto)
        x1 = min(ancho, x0 + max(2, int(box.w * ancho)))
        y1 = min(alto, y0 + max(2, int(box.h * alto)))
        cv2.rectangle(canvas, (x0, y0), (x1, y1), color, 2)
        cv2.putText(canvas, label, (x0, max(16, y0 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
        if draw_contours:
            crop = canvas[y0:y1, x0:x1]
            if crop.size == 0:
                return
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            mask = (gray >= np.percentile(gray, hot_percentile)).astype(np.uint8) * 255
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(crop, contours, -1, (0, 140, 255), 1)

    _rect(roi, (80, 220, 255), "ROI")
    if background is not None:
        _rect(background, (180, 80, 255), "Fondo")
    return canvas


def visual_delta(current: VisualStats, reference: VisualStats) -> float:
    """Cambio de intensidad media (unidades de gris, no °C)."""
    return current.mean_gray - reference.mean_gray
