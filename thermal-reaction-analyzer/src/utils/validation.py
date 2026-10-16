"""Validaciones recuperables con mensajes en español."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from src.utils.limits import (
    MAX_CHANGE_C,
    MAX_DURATION_S,
    MAX_ESTIMATED_BYTES,
    MAX_IMPORT_FRAMES,
    MAX_INTERVAL_S,
    MAX_MATRIX_SIDE,
    MAX_NOISE_STD_C,
    MAX_SIM_FRAMES,
    MAX_TEMPERATURE_C,
    MIN_INTERVAL_S,
    MIN_TEMPERATURE_C,
    estimated_matrix_bytes,
)


class ValidationError(ValueError):
    """Error de datos que la interfaz puede mostrar sin detener la aplicación."""


def require_finite_matrix(matrix: np.ndarray, origen: str = "la matriz") -> np.ndarray:
    if not isinstance(matrix, np.ndarray):
        raise ValidationError(f"No se recibió {origen} numérica.")
    if matrix.size == 0 or matrix.ndim != 2:
        raise ValidationError(f"{origen.capitalize()} debe ser una matriz bidimensional con datos.")
    if not np.issubdtype(matrix.dtype, np.number):
        raise ValidationError(f"{origen.capitalize()} contiene valores que no son numéricos.")
    numeric = np.asarray(matrix, dtype=np.float64)
    if not np.isfinite(numeric).all():
        raise ValidationError(f"{origen.capitalize()} contiene valores vacíos, NaN o infinitos.")
    height, width = numeric.shape
    if height > MAX_MATRIX_SIDE or width > MAX_MATRIX_SIDE:
        raise ValidationError(
            f"La matriz de {width} × {height} px supera el lado máximo de {MAX_MATRIX_SIDE} px."
        )
    if estimated_matrix_bytes(1, height, width) > MAX_ESTIMATED_BYTES:
        raise ValidationError("La matriz supera el límite de memoria configurado.")
    return numeric


def validate_roi(x: int, y: int, width: int, height: int, image_height: int, image_width: int) -> None:
    if width < 1 or height < 1:
        raise ValidationError("La región de interés debe tener ancho y alto de al menos 1 píxel.")
    if x < 0 or y < 0 or x + width > image_width or y + height > image_height:
        raise ValidationError(
            "La región de interés sale de los límites de la imagen "
            f"({image_width} × {image_height} px)."
        )


def clamp_roi(
    x: int, y: int, width: int, height: int, image_height: int, image_width: int
) -> tuple[int, int, int, int]:
    if image_height < 1 or image_width < 1:
        raise ValidationError("No hay una imagen válida para recortar la región de interés.")
    roi_w = int(min(max(int(width), 1), image_width))
    roi_h = int(min(max(int(height), 1), image_height))
    roi_x = int(min(max(int(x), 0), image_width - roi_w))
    roi_y = int(min(max(int(y), 0), image_height - roi_h))
    return roi_x, roi_y, roi_w, roi_h


def validate_time_step(t1: float, t2: float) -> float:
    if not math.isfinite(t1) or not math.isfinite(t2):
        raise ValidationError("La serie contiene marcas de tiempo no numéricas.")
    delta = float(t2) - float(t1)
    if delta == 0:
        raise ValidationError("El intervalo de tiempo entre dos cuadros es cero.")
    if delta < 0:
        raise ValidationError("Las marcas de tiempo deben estar ordenadas de forma creciente.")
    return delta


def frame_count(duration_s: float, interval_s: float) -> int:
    if interval_s <= 0:
        raise ValidationError("El intervalo de muestreo debe ser mayor que cero.")
    return int(round(float(duration_s) / float(interval_s))) + 1


def validate_simulation_config(
    initial_temperature_c: float,
    change_magnitude_c: float,
    duration_s: float,
    interval_s: float,
    noise_std_c: float,
    seed: int,
) -> int:
    values = {
        "temperatura inicial": initial_temperature_c,
        "magnitud del cambio": change_magnitude_c,
        "duración": duration_s,
        "intervalo": interval_s,
        "ruido": noise_std_c,
    }
    for name, value in values.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValidationError(f"El valor de {name} no es numérico.")
    if not MIN_TEMPERATURE_C <= float(initial_temperature_c) <= MAX_TEMPERATURE_C:
        raise ValidationError(
            f"La temperatura inicial debe estar entre {MIN_TEMPERATURE_C:g} y {MAX_TEMPERATURE_C:g} °C."
        )
    if not 0 <= float(change_magnitude_c) <= MAX_CHANGE_C:
        raise ValidationError(f"La magnitud del cambio debe estar entre 0 y {MAX_CHANGE_C:g} °C.")
    if not 0 < float(duration_s) <= MAX_DURATION_S:
        raise ValidationError(f"La duración debe ser mayor que 0 y como máximo {MAX_DURATION_S:g} s.")
    if not MIN_INTERVAL_S <= float(interval_s) <= MAX_INTERVAL_S:
        raise ValidationError(
            f"El intervalo de muestreo debe estar entre {MIN_INTERVAL_S:g} y {MAX_INTERVAL_S:g} s."
        )
    if float(interval_s) > float(duration_s):
        raise ValidationError("El intervalo de muestreo no puede ser mayor que la duración.")
    if not 0 <= float(noise_std_c) <= MAX_NOISE_STD_C:
        raise ValidationError(f"El ruido simulado debe estar entre 0 y {MAX_NOISE_STD_C:g} °C.")
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)):
        raise ValidationError("La semilla aleatoria debe ser un número entero.")
    count = frame_count(float(duration_s), float(interval_s))
    if count < 2:
        raise ValidationError("La simulación necesita al menos dos cuadros.")
    if count > MAX_SIM_FRAMES:
        raise ValidationError(
            f"Esa duración e intervalo producen {count} cuadros. El máximo es {MAX_SIM_FRAMES}."
        )
    if estimated_matrix_bytes(count, 120, 160) > MAX_ESTIMATED_BYTES:
        raise ValidationError("La simulación solicitada supera el límite de memoria.")
    return count


def validate_import_stack(n_frames: int, height: int, width: int) -> None:
    if n_frames < 1:
        raise ValidationError("No hay cuadros para importar.")
    if n_frames > MAX_IMPORT_FRAMES:
        raise ValidationError(
            f"La importación tiene {n_frames} cuadros. El máximo es {MAX_IMPORT_FRAMES}."
        )
    if estimated_matrix_bytes(n_frames, height, width) > MAX_ESTIMATED_BYTES:
        raise ValidationError("Los datos importados superan el límite de memoria.")


def as_int(value: Any, label: str) -> int:
    try:
        if isinstance(value, bool):
            raise TypeError
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{label} debe ser un número entero.") from exc
