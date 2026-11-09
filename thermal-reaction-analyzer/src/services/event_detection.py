"""Detección de eventos térmicos con ventana y umbrales configurables."""

from __future__ import annotations

from src.models.telemetry import TemperatureReading, ThermalEvent
from src.services.telemetry_service import is_quantitative


def detect_events(
    readings: list[TemperatureReading],
    previous: list[ThermalEvent] | None = None,
    *,
    heat_threshold_c: float = 0.8,
    cool_threshold_c: float = 0.8,
    stable_std_c: float = 0.25,
    window: int = 5,
    mix_time_s: float | None = None,
) -> list[ThermalEvent]:
    """Añade eventos nuevos; no reescribe los ya registrados."""
    known = list(previous or [])
    kinds = {item.kind for item in known}
    valid = [item for item in readings if is_quantitative(item) and item.value_c is not None]
    if len(valid) < 2:
        return known
    values = [float(item.value_c) for item in valid]
    times = [float(item.timestamp_s) for item in valid]
    start_t = times[0] if mix_time_s is None else mix_time_s
    post = [(t, v) for t, v in zip(times, values) if t >= start_t]
    if len(post) < 2:
        return known

    first_v = post[0][1]
    last_t, last_v = post[-1]
    rise = last_v - first_v
    span = [pair[1] for pair in post[-window:]]
    if "inicio_calentamiento" not in kinds and rise >= heat_threshold_c:
        known.append(
            ThermalEvent(
                timestamp_s=last_t,
                kind="inicio_calentamiento",
                value_c=last_v,
                condition=f"ΔT ≥ {heat_threshold_c:.2f} °C respecto a la referencia de evento",
            )
        )
        kinds.add("inicio_calentamiento")
    if "inicio_enfriamiento" not in kinds and rise <= -cool_threshold_c:
        known.append(
            ThermalEvent(
                timestamp_s=last_t,
                kind="inicio_enfriamiento",
                value_c=last_v,
                condition=f"ΔT ≤ -{cool_threshold_c:.2f} °C respecto a la referencia de evento",
            )
        )
        kinds.add("inicio_enfriamiento")

    peak_t, peak_v = max(post, key=lambda pair: pair[1])
    if peak_v >= first_v + heat_threshold_c and last_v <= peak_v - heat_threshold_c * 0.35:
        if "pico_termico" not in kinds:
            known.append(
                ThermalEvent(
                    timestamp_s=peak_t,
                    kind="pico_termico",
                    value_c=peak_v,
                    condition="máximo local seguido de descenso apreciable",
                )
            )
            kinds.add("pico_termico")

    if len(span) >= window:
        avg = sum(span) / len(span)
        std = (sum((item - avg) ** 2 for item in span) / len(span)) ** 0.5
        if std <= stable_std_c and "estabilizacion" not in kinds and len(post) >= window + 2:
            known.append(
                ThermalEvent(
                    timestamp_s=last_t,
                    kind="estabilizacion",
                    value_c=last_v,
                    condition=f"σ ≤ {stable_std_c:.2f} °C en {window} lecturas",
                )
            )
    if len(values) >= 2:
        slope_now = (values[-1] - values[-2]) / (times[-1] - times[-2] if times[-1] != times[-2] else 1)
        if abs(slope_now) > 0.05 and "cambio_tendencia" not in kinds and len(values) >= 6:
            prev_slope = (values[-3] - values[-5]) / (times[-3] - times[-5] if times[-3] != times[-5] else 1)
            if prev_slope * slope_now < 0:
                known.append(
                    ThermalEvent(
                        timestamp_s=times[-1],
                        kind="cambio_tendencia",
                        value_c=values[-1],
                        condition="cambio de signo de dT/dt",
                    )
                )
    return known
