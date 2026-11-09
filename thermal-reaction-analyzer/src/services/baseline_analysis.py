"""Línea base a partir de lecturas válidas previas al evento."""

from __future__ import annotations

from dataclasses import dataclass

from src.models.telemetry import TemperatureReading
from src.services.telemetry_service import is_quantitative


@dataclass
class BaselineResult:
    ready: bool
    reference_c: float | None
    std_c: float | None
    valid_count: int
    duration_s: float
    notes: tuple[str, ...]


def compute_baseline(
    readings: list[TemperatureReading],
    min_count: int = 5,
    max_std_c: float = 0.6,
) -> BaselineResult:
    valid = [item for item in readings if is_quantitative(item) and item.value_c is not None]
    if len(valid) < min_count:
        return BaselineResult(
            ready=False,
            reference_c=None,
            std_c=None,
            valid_count=len(valid),
            duration_s=0.0,
            notes=(
                f"Se necesitan al menos {min_count} lecturas válidas para la línea base.",
                f"Hay {len(valid)}.",
            ),
        )
    values = [float(item.value_c) for item in valid]
    mean = sum(values) / len(values)
    var = sum((item - mean) ** 2 for item in values) / len(values)
    std = var ** 0.5
    duration = float(valid[-1].timestamp_s) - float(valid[0].timestamp_s)
    ready = std <= max_std_c
    notes = (
        f"Referencia {mean:.2f} °C con σ={std:.3f} °C en {len(valid)} lecturas.",
        "La línea base usa solo temperaturas FLIR/radiométricas válidas.",
    )
    if not ready:
        notes = notes + (f"σ supera {max_std_c:.2f} °C; espera a que se estabilice o inicia sin línea base.",)
    return BaselineResult(
        ready=ready,
        reference_c=mean,
        std_c=std,
        valid_count=len(valid),
        duration_s=duration,
        notes=notes,
    )
