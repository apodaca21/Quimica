"""Pruebas de promedio, desviación y ΔT."""

from __future__ import annotations

import numpy as np
import pytest

from src.models.experiment import Experiment
from src.models.thermal_frame import DataOrigin, ThermalFrame
from src.services.roi_analysis import mean_temperature, population_std
from src.services.thermal_analysis import (
    TABLE_COLUMNS,
    analyze_experiment,
    approximate_rate,
    delta_temperature,
)
from src.services.thermal_interpretation import classify_thermal_behavior
from src.utils.validation import ValidationError


def test_el_promedio_es_la_suma_dividida_entre_n() -> None:
    values = np.array([10.0, 12.0, 14.0, 16.0])
    assert mean_temperature(values) == pytest.approx(13.0)


def test_la_desviacion_estandar_usa_n() -> None:
    values = np.array([1.0, 3.0, 5.0, 7.0])
    expected = np.sqrt(((1 - 4) ** 2 + (3 - 4) ** 2 + (5 - 4) ** 2 + (7 - 4) ** 2) / 4)
    assert population_std(values) == pytest.approx(expected)


def test_delta_t_es_final_menos_inicial() -> None:
    assert delta_temperature(36.0, 24.0) == pytest.approx(12.0)


def test_la_tasa_rechaza_un_intervalo_cero() -> None:
    with pytest.raises(ValidationError):
        approximate_rate(30.0, 24.0, 5.0, 5.0)


def test_la_serie_calcula_delta_respecto_a_la_linea_base() -> None:
    frames = []
    experiment = Experiment(name="Serie", origin=DataOrigin.SIMULACION)
    for index, temperature in enumerate((10.0, 12.0, 16.0)):
        frames.append(
            ThermalFrame(
                matrix=np.full((2, 2), temperature, dtype=np.float32),
                unit="°C",
                timestamp_s=float(index),
                origin=DataOrigin.SIMULACION,
                experiment_id=experiment.id,
            )
        )
    experiment.frames = frames
    result = analyze_experiment(experiment, 0, 0, 2, 2, baseline_frames=1)
    assert list(result.table.columns) == TABLE_COLUMNS
    assert result.baseline_c == pytest.approx(10.0)
    assert result.delta_t_c == pytest.approx(6.0)
    assert result.trend == "Tendencia de calentamiento superficial."
    assert result.table.iloc[1]["tasa_C_por_s"] == pytest.approx(2.0)


def _result_for(values: tuple[float, ...]) -> object:
    experiment = Experiment(name="Clasificación", origin=DataOrigin.SIMULACION)
    experiment.frames = [
        ThermalFrame(
            matrix=np.full((2, 2), temperature, dtype=np.float32),
            unit="°C",
            timestamp_s=float(index),
            origin=DataOrigin.SIMULACION,
            experiment_id=experiment.id,
        )
        for index, temperature in enumerate(values)
    ]
    return analyze_experiment(experiment, 0, 0, 2, 2, baseline_frames=1)


def test_el_asistente_detecta_comportamiento_exotermico_posible() -> None:
    interpretation = classify_thermal_behavior(_result_for((20.0, 21.0, 23.0, 25.0)))
    assert interpretation.category == "exotermico_posible"
    assert interpretation.max_delta_c == pytest.approx(5.0)


def test_el_asistente_detecta_un_pico_transitorio() -> None:
    interpretation = classify_thermal_behavior(_result_for((20.0, 24.0, 22.0, 20.8)))
    assert interpretation.category == "transitorio"


def test_el_asistente_detecta_comportamiento_endotermico_posible() -> None:
    interpretation = classify_thermal_behavior(_result_for((20.0, 19.0, 17.0, 16.0)))
    assert interpretation.category == "endotermico_posible"


def test_el_asistente_sugiere_neutralizacion_si_hay_acido_y_base() -> None:
    result = _result_for((20.0, 21.0, 23.0, 25.0))
    experiment = Experiment(
        name="Neutralización",
        origin=DataOrigin.SIMULACION,
        assay_type="Neutralización ácido-base",
        reagents="HCl + NaOH",
    )
    interpretation = classify_thermal_behavior(result, experiment=experiment)
    assert "neutralización" in interpretation.reaction_prediction.lower()
    assert "NaOH" in interpretation.reaction_prediction
