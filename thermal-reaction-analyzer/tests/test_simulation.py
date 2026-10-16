"""Pruebas del simulador ilustrativo."""

from __future__ import annotations

import numpy as np
import pytest

from src.services.simulation import SimulationConfig, generate_matrices, generate_simulation
from src.utils.limits import THERMAL_HEIGHT, THERMAL_WIDTH
from src.utils.validation import ValidationError


def _config(scenario: str, **overrides: float | int | str) -> SimulationConfig:
    values: dict[str, float | int | str] = {
        "scenario": scenario,
        "initial_temperature_c": 24.0,
        "change_magnitude_c": 12.0 if scenario == "calentamiento" else 6.0,
        "duration_s": 10.0,
        "interval_s": 1.0,
        "noise_std_c": 0.0,
        "seed": 7,
    }
    values.update(overrides)
    return SimulationConfig(**values)  # type: ignore[arg-type]


def test_la_simulacion_mide_160_de_ancho_por_120_de_alto() -> None:
    _times, matrices = generate_matrices(_config("calentamiento"))
    assert matrices.shape[1:] == (THERMAL_HEIGHT, THERMAL_WIDTH)
    assert matrices.shape[1] == 120
    assert matrices.shape[2] == 160


def test_la_simulacion_es_reproducible_con_la_misma_semilla() -> None:
    config = _config("calentamiento", noise_std_c=0.4, seed=21)
    first_times, first = generate_matrices(config)
    second_times, second = generate_matrices(config)
    assert np.array_equal(first_times, second_times)
    assert np.array_equal(first, second)


def test_el_calentamiento_tiene_tendencia_creciente() -> None:
    _times, matrices = generate_matrices(_config("calentamiento", change_magnitude_c=12.0))
    assert float(matrices[-1].mean()) > float(matrices[0].mean())


def test_el_enfriamiento_tiene_tendencia_decreciente() -> None:
    _times, matrices = generate_matrices(_config("enfriamiento", change_magnitude_c=6.0))
    assert float(matrices[-1].mean()) < float(matrices[0].mean())


def test_el_control_no_se_etiqueta_como_medicion() -> None:
    experiment = generate_simulation(_config("control", change_magnitude_c=0.3))
    assert experiment.origin.value == "simulacion"
    assert all(frame.radiometric_valid is False for frame in experiment.frames)


def test_se_rechaza_una_simulacion_demasiado_larga() -> None:
    with pytest.raises(ValidationError):
        generate_matrices(_config("calentamiento", duration_s=180.0, interval_s=0.25))
