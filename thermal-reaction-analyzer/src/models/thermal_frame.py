"""Cuadro térmico y origen de los datos."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np


class DataOrigin(str, Enum):
    """Familias de datos que la interfaz debe distinguir siempre."""

    SIMULACION = "simulacion"
    IMPORTADO_CUANTITATIVO = "importado_cuantitativo"
    MEDICION_RADIOMETRICA_VERIFICADA = "medicion_radiometrica_verificada"
    IMAGEN_VISUAL = "imagen_visual"
    FLIR_PENDIENTE = "flir_pendiente_validacion"


QUANTITATIVE_ORIGINS = {
    DataOrigin.SIMULACION,
    DataOrigin.IMPORTADO_CUANTITATIVO,
    DataOrigin.MEDICION_RADIOMETRICA_VERIFICADA,
}

ORIGIN_LABELS = {
    DataOrigin.SIMULACION: "Simulación ilustrativa",
    DataOrigin.IMPORTADO_CUANTITATIVO: "Datos cuantitativos importados",
    DataOrigin.MEDICION_RADIOMETRICA_VERIFICADA: "Medición radiométrica verificada",
    DataOrigin.IMAGEN_VISUAL: "Imagen visual sin temperaturas",
    DataOrigin.FLIR_PENDIENTE: "FLIR pendiente de validación",
}


def origin_label(origin: DataOrigin) -> str:
    return ORIGIN_LABELS.get(origin, origin.value)


@dataclass
class ThermalFrame:
    """Un instante térmico.

    La matriz solo existe cuando el origen aporta temperaturas numéricas.
    ``radiometric_valid`` solo puede ser verdadero en una medición ya verificada
    con una fotografía original de la FLIR C5.
    """

    matrix: np.ndarray | None
    unit: str
    timestamp_s: float | None
    origin: DataOrigin
    experiment_id: str
    metadata: dict[str, Any] = field(default_factory=dict)
    radiometric_valid: bool = False
    preview_rgb: np.ndarray | None = None
    source_name: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.origin, DataOrigin):
            self.origin = DataOrigin(self.origin)
        if self.radiometric_valid and self.origin != DataOrigin.MEDICION_RADIOMETRICA_VERIFICADA:
            raise ValueError("Solo una medición radiométrica verificada puede marcarse como válida.")
        if self.origin == DataOrigin.MEDICION_RADIOMETRICA_VERIFICADA and not self.radiometric_valid:
            raise ValueError("Una medición radiométrica verificada debe declarar su validez.")
        if self.matrix is not None:
            self.matrix = np.asarray(self.matrix, dtype=np.float32)
        if self.preview_rgb is not None:
            self.preview_rgb = np.asarray(self.preview_rgb)

    @property
    def has_temperature(self) -> bool:
        return self.matrix is not None and self.origin in QUANTITATIVE_ORIGINS

    @property
    def height(self) -> int:
        if self.matrix is not None:
            return int(self.matrix.shape[0])
        if self.preview_rgb is not None:
            return int(self.preview_rgb.shape[0])
        return 0

    @property
    def width(self) -> int:
        if self.matrix is not None:
            return int(self.matrix.shape[1])
        if self.preview_rgb is not None:
            return int(self.preview_rgb.shape[1])
        return 0
