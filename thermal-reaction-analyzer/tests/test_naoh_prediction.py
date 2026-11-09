"""Predicción de ensayos escolares con NaOH y nombres de archivo."""

from __future__ import annotations

import numpy as np

from src.models.experiment import Experiment
from src.models.thermal_frame import DataOrigin, ThermalFrame
from src.services.live_thermal import apparent_matrix, scene_mean_gray
from src.services.naoh_catalog import infer_protocol, predict_naoh_family
from src.services.thermal_analysis import analyze_experiment
from src.services.thermal_interpretation import classify_thermal_behavior
from src.utils.names import file_stem, slugify


def _heating_result() -> object:
    experiment = Experiment(
        name="NaOH agua",
        origin=DataOrigin.SIMULACION,
        reagents="NaOH sólido + H2O",
        assay_type="Disolución",
        parameters={"protocolo": "disolucion_agua"},
    )
    experiment.frames = [
        ThermalFrame(
            matrix=np.full((2, 2), temperature, dtype=np.float32),
            unit="°C",
            timestamp_s=float(index),
            origin=DataOrigin.SIMULACION,
            experiment_id=experiment.id,
        )
        for index, temperature in enumerate((22.0, 26.0, 30.0, 34.0))
    ]
    return experiment, analyze_experiment(experiment, 0, 0, 2, 2, baseline_frames=1)


def test_slugify_distinguishes_experiment_names() -> None:
    assert slugify("Ensayo NaOH 1") == "ensayo_naoh_1"
    assert file_stem("Neutralización HCl", "abc123") == "neutralizacion_hcl_abc123"


def test_hcl_con_naoh_se_infiere_como_neutralizacion() -> None:
    experiment = Experiment(name="N", origin=DataOrigin.SIMULACION, reagents="HCl + NaOH")
    assert infer_protocol(experiment) == "neutralizacion_hcl"


def test_calentamiento_fuerte_sugiere_disolucion_de_naoh() -> None:
    prediction, confidence, evidence = predict_naoh_family(
        "exotermico_posible",
        Experiment(
            name="D",
            origin=DataOrigin.SIMULACION,
            reagents="NaOH sólido + H2O",
            parameters={"protocolo": "disolucion_agua"},
        ),
        max_delta_c=12.0,
        min_delta_c=0.0,
    )
    assert "NaOH(s) en agua" in prediction
    assert confidence == "alta"
    assert any("exotérmica" in item.lower() or "exotermica" in item.lower() or "calor" in item.lower() for item in evidence)


def test_enfriamiento_no_coincide_con_naoh_tipico() -> None:
    prediction, _, _ = predict_naoh_family(
        "endotermico_posible",
        Experiment(name="E", origin=DataOrigin.SIMULACION, reagents="NaOH", parameters={"protocolo": "otro_naoh"}),
        max_delta_c=0.1,
        min_delta_c=-4.0,
    )
    assert "no coincide" in prediction.lower()


def test_el_asistente_usa_el_catalogo_naoh_en_calentamiento() -> None:
    experiment, result = _heating_result()
    interpretation = classify_thermal_behavior(result, experiment=experiment)
    assert "NaOH" in interpretation.reaction_prediction
    assert interpretation.category == "exotermico_posible"


def test_la_matriz_aparente_sube_si_la_escena_se_aclara() -> None:
    dark = np.full((480, 640, 3), 40, dtype=np.uint8)
    bright = np.full((480, 640, 3), 120, dtype=np.uint8)
    gray0 = scene_mean_gray(dark)
    cold = apparent_matrix(dark, gray0, t_ref_c=24.0)
    hot = apparent_matrix(bright, gray0, t_ref_c=24.0)
    assert float(hot.mean()) > float(cold.mean())
    assert cold.shape == (120, 160)
