"""Alertas informativas. No son un sistema certificado de seguridad."""

from __future__ import annotations

from dataclasses import dataclass

from src.models.telemetry import ThermalEvent
from src.services.telemetry_service import TelemetryMetrics


@dataclass
class AlertConfig:
    max_temp_c: float = 60.0
    max_delta_c: float = 20.0
    max_rate_c_per_s: float = 2.0
    missing_readings: int = 8
    cooldown_s: float = 12.0


def evaluate_alerts(
    metrics: TelemetryMetrics,
    missing_streak: int,
    previous: list[ThermalEvent],
    now_s: float,
    config: AlertConfig | None = None,
) -> list[ThermalEvent]:
    cfg = config or AlertConfig()
    extra: list[ThermalEvent] = []
    recent = [item for item in previous if now_s - item.timestamp_s < cfg.cooldown_s]
    recent_kinds = {item.kind for item in recent}

    def _add(kind: str, value: float | None, condition: str) -> None:
        if kind in recent_kinds:
            return
        extra.append(
            ThermalEvent(
                timestamp_s=now_s,
                kind=kind,
                value_c=value,
                condition=condition,
                notes="Alerta informativa. No es un sistema de seguridad certificado.",
            )
        )

    if metrics.current_c is not None and metrics.current_c >= cfg.max_temp_c:
        _add("alerta_temp_max", metrics.current_c, f"T ≥ {cfg.max_temp_c:.1f} °C")
    if metrics.delta_c is not None and metrics.delta_c >= cfg.max_delta_c:
        _add("alerta_delta", metrics.delta_c, f"ΔT ≥ {cfg.max_delta_c:.1f} °C")
    if metrics.rate_c_per_s is not None and metrics.rate_c_per_s >= cfg.max_rate_c_per_s:
        _add("alerta_tasa", metrics.rate_c_per_s, f"dT/dt ≥ {cfg.max_rate_c_per_s:.2f} °C/s")
    if missing_streak >= cfg.missing_readings:
        _add("alerta_perdida_lecturas", None, f"{missing_streak} lecturas ausentes seguidas")
    return extra
