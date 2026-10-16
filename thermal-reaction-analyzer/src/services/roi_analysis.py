"""Cálculos sobre una región rectangular de un cuadro."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.utils.validation import require_finite_matrix, validate_roi


@dataclass(frozen=True)
class RoiStats:
    min_c: float
    max_c: float
    mean_c: float
    std_c: float
    hottest_x: int
    hottest_y: int
    coldest_x: int
    coldest_y: int
    count: int


def population_std(values: np.ndarray) -> float:
    """σ = √[Σ(Tᵢ − T̄)² / N]."""
    flat = np.asarray(values, dtype=np.float64).ravel()
    if flat.size == 0:
        raise ValueError("No hay valores para calcular la desviación estándar.")
    mean = float(np.sum(flat) / flat.size)
    return float(np.sqrt(np.sum((flat - mean) ** 2) / flat.size))


def mean_temperature(values: np.ndarray) -> float:
    """T̄ = (Σ Tᵢ) / N."""
    flat = np.asarray(values, dtype=np.float64).ravel()
    if flat.size == 0:
        raise ValueError("No hay valores para calcular el promedio.")
    return float(np.sum(flat) / flat.size)


def analyze_roi(matrix: np.ndarray, x: int, y: int, width: int, height: int) -> RoiStats:
    """Estadísticos de la ROI. Las posiciones vuelven a coordenadas de la matriz completa."""
    numeric = require_finite_matrix(matrix)
    image_height, image_width = numeric.shape
    validate_roi(int(x), int(y), int(width), int(height), image_height, image_width)
    region = numeric[int(y) : int(y) + int(height), int(x) : int(x) + int(width)]
    cold_y, cold_x = np.unravel_index(int(np.argmin(region)), region.shape)
    hot_y, hot_x = np.unravel_index(int(np.argmax(region)), region.shape)
    return RoiStats(
        min_c=float(np.min(region)),
        max_c=float(np.max(region)),
        mean_c=mean_temperature(region),
        std_c=population_std(region),
        hottest_x=int(x) + int(hot_x),
        hottest_y=int(y) + int(hot_y),
        coldest_x=int(x) + int(cold_x),
        coldest_y=int(y) + int(cold_y),
        count=int(region.size),
    )
