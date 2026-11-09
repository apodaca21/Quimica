"""ROI visual. Empieza fija; el seguimiento opcional no se mueve en silencio si falla."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from src.models.telemetry import VisualRoi


@dataclass
class TrackState:
    roi: VisualRoi
    tracking: bool = False
    lost: bool = False
    message: str = "ROI fija"


class RoiTracker:
    def __init__(self, roi: VisualRoi) -> None:
        self.state = TrackState(roi=roi.clamp())
        self._template: np.ndarray | None = None

    def set_roi(self, roi: VisualRoi) -> None:
        self.state = TrackState(roi=roi.clamp(), tracking=False, lost=False, message="ROI fija")
        self._template = None

    def enable_tracking(self, frame_bgr: np.ndarray) -> None:
        from src.services.visual_thermal_analysis import roi_slice

        crop = roi_slice(frame_bgr, self.state.roi)
        if crop.size == 0:
            self.state.lost = True
            self.state.tracking = False
            self.state.message = "No se pudo iniciar el seguimiento: recorte vacío."
            return
        self._template = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        self.state.tracking = True
        self.state.lost = False
        self.state.message = "Seguimiento activo"

    def update(self, frame_bgr: np.ndarray) -> TrackState:
        if not self.state.tracking or self._template is None:
            return self.state
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        res = cv2.matchTemplate(gray, self._template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if max_val < 0.55:
            self.state.tracking = False
            self.state.lost = True
            self.state.message = "Seguimiento perdido. Selecciona de nuevo la ROI."
            self._template = None
            return self.state
        alto, ancho = gray.shape[:2]
        th, tw = self._template.shape[:2]
        self.state.roi = VisualRoi(
            x=max_loc[0] / ancho,
            y=max_loc[1] / alto,
            w=tw / ancho,
            h=th / alto,
        ).clamp()
        self.state.lost = False
        self.state.message = f"Seguimiento activo ({max_val:.2f})"
        return self.state
