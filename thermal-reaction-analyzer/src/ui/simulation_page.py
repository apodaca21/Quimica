"""Página de simulación térmica."""

from __future__ import annotations

import streamlit as st

from src.services.simulation import SCENARIO_LABELS, SimulationConfig, generate_simulation
from src.ui.components import render_workspace
from src.ui.state import activate
from src.utils.limits import (
    MAX_CHANGE_C,
    MAX_DURATION_S,
    MAX_INTERVAL_S,
    MAX_NOISE_STD_C,
    MAX_SIM_FRAMES,
    MAX_TEMPERATURE_C,
    MIN_INTERVAL_S,
    MIN_TEMPERATURE_C,
)
from src.utils.validation import ValidationError

SCENARIO_HELP = {
    "calentamiento": "La región central se calienta de forma gradual. Ejemplo ilustrativo: de 24 °C hacia 36 °C.",
    "enfriamiento": "La región central se enfría de forma gradual. Ejemplo ilustrativo: de 24 °C hacia 18 °C.",
    "control": "La temperatura permanece cerca del valor inicial, con una oscilación pequeña.",
}


def render_simulation_page() -> None:
    st.markdown("<div class='hero-kicker'>Motor ilustrativo</div>", unsafe_allow_html=True)
    st.markdown("<h1 class='hero-title'>Simulación térmica</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p class='hero-subtitle'>Genera matrices de 160 × 120 px para probar el análisis sin una cámara conectada.</p>",
        unsafe_allow_html=True,
    )
    st.info(
        "Este modelo es ilustrativo: T(x, y, t) = T_base + A(t)·G(x, y) + ruido. "
        "No es una solución termodinámica ni una medición experimental. "
        f"Límite: {MAX_SIM_FRAMES} cuadros, {MAX_DURATION_S:g} s y 64 MB estimados."
    )
    left, right = st.columns(2)
    scenario = left.selectbox(
        "Escenario",
        list(SCENARIO_LABELS),
        format_func=lambda key: SCENARIO_LABELS[key],
    )
    st.caption(SCENARIO_HELP[scenario])
    name = left.text_input("Nombre del experimento", value="Simulación de demostración")
    initial = right.number_input("Temperatura inicial (°C)", min_value=MIN_TEMPERATURE_C, max_value=MAX_TEMPERATURE_C, value=24.0, step=0.5)
    magnitude_label = "Amplitud de la fluctuación (°C)" if scenario == "control" else "Magnitud del cambio (°C)"
    default_magnitude = 0.4 if scenario == "control" else (12.0 if scenario == "calentamiento" else 6.0)
    magnitude = right.number_input(magnitude_label, min_value=0.0, max_value=MAX_CHANGE_C, value=default_magnitude, step=0.5)
    duration = left.number_input("Duración (s)", min_value=MIN_INTERVAL_S, max_value=MAX_DURATION_S, value=30.0, step=1.0)
    interval = left.number_input("Intervalo de muestreo (s)", min_value=MIN_INTERVAL_S, max_value=MAX_INTERVAL_S, value=1.0, step=0.25)
    noise = right.number_input("Ruido simulado (°C)", min_value=0.0, max_value=MAX_NOISE_STD_C, value=0.15, step=0.05)
    seed = right.number_input("Semilla aleatoria", min_value=0, max_value=2**31 - 1, value=7, step=1)
    if st.button("Iniciar simulación", type="primary"):
        try:
            experiment = generate_simulation(
                SimulationConfig(
                    scenario=scenario,
                    initial_temperature_c=float(initial),
                    change_magnitude_c=float(magnitude),
                    duration_s=float(duration),
                    interval_s=float(interval),
                    noise_std_c=float(noise),
                    seed=int(seed),
                    name=name,
                )
            )
        except ValidationError as exc:
            st.error(str(exc))
        else:
            activate(experiment, start_playback=True)
            st.success(
                f"Simulación registrada con {len(experiment.frames)} cuadros. "
                "Los datos quedan marcados como simulación."
            )
    render_workspace()
