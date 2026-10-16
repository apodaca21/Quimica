"""Métricas de serie temporal e interpretación química prudente."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.models.experiment import Experiment
from src.models.thermal_frame import DataOrigin
from src.services.roi_analysis import RoiStats, analyze_roi, mean_temperature
from src.utils.validation import ValidationError, validate_time_step

TABLE_COLUMNS = [
    "tiempo_s",
    "temperatura_min_C",
    "temperatura_max_C",
    "temperatura_promedio_C",
    "delta_T_C",
    "tasa_C_por_s",
    "desviacion_estandar_C",
]

MEASUREMENT_WARNINGS = [
    "La emisividad, los reflejos, la temperatura ambiente y la calibración cambian la temperatura aparente.",
    "Observar a través de vidrio puede bloquear o distorsionar la radiación infrarroja.",
    "No se calcula la entalpía: harían falta masas, capacidades caloríficas y condiciones de balance.",
    "El signo de ΔT superficial no demuestra por sí solo el carácter endotérmico o exotérmico de una reacción.",
]

ORIGIN_NOTES = {
    DataOrigin.SIMULACION: "Los valores son simulados. No corresponden a una medición física.",
    DataOrigin.IMPORTADO_CUANTITATIVO: (
        "Los valores provienen de un archivo numérico importado. "
        "No son una medición radiométrica verificada con la FLIR C5."
    ),
    DataOrigin.MEDICION_RADIOMETRICA_VERIFICADA: (
        "Medición radiométrica verificada con el procedimiento aprobado para la cámara."
    ),
}


@dataclass
class AnalysisResult:
    table: pd.DataFrame
    baseline_c: float
    delta_t_c: float
    trend: str
    explanation: str
    warnings: list[str] = field(default_factory=list)
    frame_stats: list[RoiStats] = field(default_factory=list)
    baseline_frames: int = 1


def delta_temperature(final_c: float, initial_c: float) -> float:
    """ΔT = T_final − T_inicial."""
    return float(final_c) - float(initial_c)


def approximate_rate(temperature_2_c: float, temperature_1_c: float, time_2_s: float, time_1_s: float) -> float:
    """dT/dt ≈ (T₂ − T₁) / (t₂ − t₁), en °C/s."""
    step = validate_time_step(time_1_s, time_2_s)
    return (float(temperature_2_c) - float(temperature_1_c)) / step


def baseline_temperature(means_c: np.ndarray, baseline_frames: int) -> float:
    values = np.asarray(means_c, dtype=np.float64)
    if values.size == 0:
        raise ValidationError("No hay temperaturas para definir la línea base.")
    count = max(1, min(int(baseline_frames), int(values.size)))
    return mean_temperature(values[:count])


def interpret_trend(delta_t_c: float, sample_count: int, stable_threshold_c: float = 0.5) -> str:
    if sample_count < 2:
        return "Datos insuficientes para establecer una tendencia."
    if abs(delta_t_c) < stable_threshold_c:
        return "Temperatura aproximadamente estable."
    if delta_t_c > 0:
        return "Tendencia de calentamiento superficial."
    return "Tendencia de enfriamiento superficial."


def _explanation(trend: str, origin: DataOrigin, delta_t_c: float, baseline_c: float) -> str:
    if trend.startswith("Datos insuficientes"):
        detail = "Con un solo cuadro se pueden leer temperaturas, pero no una evolución temporal."
    else:
        detail = (
            f"La línea base es {baseline_c:.2f} °C y el cambio de la serie es {delta_t_c:.2f} °C. "
            "La lectura describe la superficie observada en la región seleccionada."
        )
    note = ORIGIN_NOTES.get(origin, "")
    return f"{trend} {detail} {note}".strip()


def analyze_experiment(
    experiment: Experiment,
    x: int,
    y: int,
    width: int,
    height: int,
    baseline_frames: int = 1,
) -> AnalysisResult:
    frames = experiment.numeric_frames
    if not frames:
        raise ValidationError("El experimento no tiene datos de temperatura para analizar.")
    if len(frames) > 1 and any(frame.timestamp_s is None for frame in frames):
        raise ValidationError("La secuencia no tiene marcas de tiempo válidas en todos los cuadros.")

    stats = [analyze_roi(frame.matrix, x, y, width, height) for frame in frames if frame.matrix is not None]
    means = np.array([item.mean_c for item in stats], dtype=np.float64)
    count = max(1, min(int(baseline_frames), len(stats)))
    baseline = baseline_temperature(means, count)
    rows: list[dict[str, float | None]] = []
    for index, (frame, item) in enumerate(zip(frames, stats)):
        rate: float | None = None
        if index > 0:
            previous = frames[index - 1]
            if frame.timestamp_s is None or previous.timestamp_s is None:
                raise ValidationError("La secuencia no tiene marcas de tiempo válidas.")
            rate = approximate_rate(
                item.mean_c,
                stats[index - 1].mean_c,
                float(frame.timestamp_s),
                float(previous.timestamp_s),
            )
        rows.append(
            {
                "tiempo_s": frame.timestamp_s,
                "temperatura_min_C": item.min_c,
                "temperatura_max_C": item.max_c,
                "temperatura_promedio_C": item.mean_c,
                "delta_T_C": delta_temperature(item.mean_c, baseline),
                "tasa_C_por_s": rate,
                "desviacion_estandar_C": item.std_c,
            }
        )
    series_delta = delta_temperature(stats[-1].mean_c, baseline)
    trend = interpret_trend(series_delta, len(stats))
    warnings = list(MEASUREMENT_WARNINGS)
    note = ORIGIN_NOTES.get(experiment.origin)
    if note:
        warnings.insert(0, note)
    return AnalysisResult(
        table=pd.DataFrame(rows, columns=TABLE_COLUMNS),
        baseline_c=baseline,
        delta_t_c=series_delta,
        trend=trend,
        explanation=_explanation(trend, experiment.origin, series_delta, baseline),
        warnings=warnings,
        frame_stats=stats,
        baseline_frames=count,
    )
