"""Comparación de ensayos reales alineados al evento de mezcla."""

from __future__ import annotations

from dataclasses import dataclass

from src.models.telemetry import TemperatureReading
from src.services.experiment_storage import ExperimentRecord
from src.services.telemetry_service import TelemetrySeries, is_quantitative


@dataclass
class ComparisonRow:
    id: str
    name: str
    source: str
    initial_c: float | None
    max_delta_c: float | None
    time_to_peak_s: float | None
    duration_s: float | None
    mean_rate_c_per_s: float | None
    valid_count: int
    mix_marked: bool


def aligned_series(record: ExperimentRecord) -> list[tuple[float, float]]:
    """Tiempos relativos al mix (o al inicio) y temperaturas válidas."""
    origin = record.mix_time_s
    points: list[tuple[float, float]] = []
    for reading in record.readings:
        if not is_quantitative(reading) or reading.value_c is None:
            continue
        t0 = reading.timestamp_s if origin is None else reading.timestamp_s - origin
        points.append((t0, float(reading.value_c)))
    return points


def summarize(record: ExperimentRecord) -> ComparisonRow:
    series = TelemetrySeries(readings=list(record.readings))
    metrics = series.metrics(record.reference_c, record.mix_time_s)
    rate = metrics.rate_c_per_s
    if metrics.valid_count >= 2 and metrics.elapsed_s:
        valid = [item for item in record.readings if is_quantitative(item) and item.value_c is not None]
        if len(valid) >= 2:
            dt = float(valid[-1].timestamp_s) - float(valid[0].timestamp_s)
            dv = float(valid[-1].value_c) - float(valid[0].value_c)
            rate = None if dt == 0 else dv / dt
    return ComparisonRow(
        id=record.id,
        name=record.name,
        source=record.temperature_source,
        initial_c=metrics.initial_c,
        max_delta_c=None if metrics.max_c is None or metrics.initial_c is None else metrics.max_c - metrics.initial_c,
        time_to_peak_s=metrics.time_to_max_s,
        duration_s=metrics.elapsed_s,
        mean_rate_c_per_s=rate,
        valid_count=metrics.valid_count,
        mix_marked=record.mix_time_s is not None,
    )


def comparison_table(records: list[ExperimentRecord]) -> list[ComparisonRow]:
    return [summarize(item) for item in records]


def sources_compatible(records: list[ExperimentRecord]) -> bool:
    kinds = {item.temperature_source for item in records}
    return len(kinds) <= 1


def comparison_csv(rows: list[ComparisonRow]) -> str:
    lines = ["ensayo,fuente,T0_C,dT_max_C,t_pico_s,duracion_s,tasa_C_s,lecturas,mezcla"]
    for row in rows:
        lines.append(
            ",".join(
                [
                    row.name.replace(",", " "),
                    row.source,
                    "" if row.initial_c is None else f"{row.initial_c:.3f}",
                    "" if row.max_delta_c is None else f"{row.max_delta_c:.3f}",
                    "" if row.time_to_peak_s is None else f"{row.time_to_peak_s:.3f}",
                    "" if row.duration_s is None else f"{row.duration_s:.3f}",
                    "" if row.mean_rate_c_per_s is None else f"{row.mean_rate_c_per_s:.5f}",
                    str(row.valid_count),
                    "si" if row.mix_marked else "no",
                ]
            )
        )
    return "\n".join(lines) + "\n"
