"""Simulación ilustrativa de matrices térmicas de 160 × 120 px.

El modelo es

    T(x, y, t) = T_base + A(t) · G(x, y) + ε(x, y, t)

No representa una solución termodinámica ni una medición de cámara.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.models.experiment import Experiment
from src.models.thermal_frame import DataOrigin, ThermalFrame
from src.utils.limits import THERMAL_HEIGHT, THERMAL_WIDTH
from src.utils.validation import ValidationError, validate_simulation_config

SCENARIOS = ("calentamiento", "enfriamiento", "control")

SCENARIO_LABELS = {
    "calentamiento": "Aumento de temperatura",
    "enfriamiento": "Disminución de temperatura",
    "control": "Control estable",
}

MODEL_NOTE = (
    "Modelo ilustrativo T(x, y, t) = T_base + A(t)·G(x, y) + ε(x, y, t). "
    "No es una solución termodinámica ni una medición física."
)


@dataclass(frozen=True)
class SimulationConfig:
    scenario: str
    initial_temperature_c: float
    change_magnitude_c: float
    duration_s: float
    interval_s: float
    noise_std_c: float
    seed: int
    name: str = "Simulación térmica"
    description: str = ""


def spatial_profile(height: int = THERMAL_HEIGHT, width: int = THERMAL_WIDTH) -> np.ndarray:
    """Gaussiana centrada: máximo 1 en el centro y caída suave hacia los bordes."""
    y_axis = np.linspace(-1.0, 1.0, height, dtype=np.float64)
    x_axis = np.linspace(-1.0, 1.0, width, dtype=np.float64)
    xx, yy = np.meshgrid(x_axis, y_axis)
    profile = np.exp(-(xx**2 + yy**2) / (2.0 * 0.35**2))
    return profile / profile.max()


def temporal_amplitude(times_s: np.ndarray, scenario: str, magnitude_c: float) -> np.ndarray:
    """Evolución temporal A(t), en °C."""
    if scenario not in SCENARIOS:
        raise ValidationError("El escenario de simulación no es válido.")
    times = np.asarray(times_s, dtype=np.float64)
    span = float(times[-1] - times[0]) if len(times) > 1 else 1.0
    progress = (times - times[0]) / span if span > 0 else np.zeros_like(times)
    smooth = (1.0 - np.exp(-3.0 * progress)) / (1.0 - np.exp(-3.0))
    if scenario == "calentamiento":
        return magnitude_c * smooth
    if scenario == "enfriamiento":
        return -magnitude_c * smooth
    return magnitude_c * np.sin(2.0 * np.pi * progress)


def generate_matrices(config: SimulationConfig) -> tuple[np.ndarray, np.ndarray]:
    """Devuelve tiempos en segundos y matrices con forma (n, 120, 160)."""
    if config.scenario not in SCENARIOS:
        raise ValidationError("El escenario de simulación no es válido.")
    count = validate_simulation_config(
        config.initial_temperature_c,
        config.change_magnitude_c,
        config.duration_s,
        config.interval_s,
        config.noise_std_c,
        config.seed,
    )
    times = np.linspace(0.0, float(config.duration_s), count, dtype=np.float64)
    profile = spatial_profile()
    amplitude = temporal_amplitude(times, config.scenario, float(config.change_magnitude_c))
    rng = np.random.default_rng(int(config.seed))
    noise = rng.normal(0.0, float(config.noise_std_c), size=(count, *profile.shape))
    matrices = config.initial_temperature_c + amplitude[:, None, None] * profile[None, :, :] + noise
    return times, matrices.astype(np.float32)


def generate_simulation(config: SimulationConfig) -> Experiment:
    times, matrices = generate_matrices(config)
    experiment = Experiment(
        name=config.name.strip() or "Simulación térmica",
        origin=DataOrigin.SIMULACION,
        description=config.description
        or "Secuencia generada por el simulador ilustrativo. No corresponde a una medición física.",
        assay_type=SCENARIO_LABELS[config.scenario],
        observations=MODEL_NOTE,
        parameters={
            "escenario": config.scenario,
            "temperatura_inicial_C": float(config.initial_temperature_c),
            "magnitud_C": float(config.change_magnitude_c),
            "duracion_s": float(config.duration_s),
            "intervalo_s": float(config.interval_s),
            "ruido_C": float(config.noise_std_c),
            "semilla": int(config.seed),
            "modelo": MODEL_NOTE,
            "resolucion_ancho_alto": f"{THERMAL_WIDTH} × {THERMAL_HEIGHT}",
        },
    )
    experiment.frames = [
        ThermalFrame(
            matrix=matrices[index],
            unit="°C",
            timestamp_s=float(times[index]),
            origin=DataOrigin.SIMULACION,
            experiment_id=experiment.id,
            metadata={"escenario": config.scenario, "indice": index},
            radiometric_valid=False,
            source_name=f"simulacion_{index:03d}",
        )
        for index in range(len(times))
    ]
    return experiment
