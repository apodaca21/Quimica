"""Límites de memoria, duración y tamaño para simulaciones e importaciones."""

from __future__ import annotations

THERMAL_WIDTH = 160
THERMAL_HEIGHT = 120

MAX_SIM_FRAMES = 180
MAX_DURATION_S = 180.0
MIN_INTERVAL_S = 0.25
MAX_INTERVAL_S = 30.0
MIN_TEMPERATURE_C = -40.0
MAX_TEMPERATURE_C = 250.0
MAX_NOISE_STD_C = 2.0
MAX_CHANGE_C = 80.0

MAX_IMPORT_FRAMES = 180
MAX_MATRIX_SIDE = 512
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_ESTIMATED_BYTES = 64 * 1024 * 1024

BYTES_PER_FLOAT = 4


def estimated_matrix_bytes(n_frames: int, height: int, width: int) -> int:
    return int(n_frames) * int(height) * int(width) * BYTES_PER_FLOAT
