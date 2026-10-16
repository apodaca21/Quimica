"""Panel principal."""

from __future__ import annotations

import streamlit as st

from src.ui.components import render_workspace


def render_dashboard() -> None:
    st.markdown("<div class='hero-kicker'>Laboratorio de química</div>", unsafe_allow_html=True)
    st.markdown("<h1 class='hero-title'>Analizador térmico</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p class='hero-subtitle'>Sistema de monitoreo y análisis de reacciones químicas.</p>",
        unsafe_allow_html=True,
    )
    render_workspace()
    st.caption("Las tarjetas muestran la región de interés del cuadro seleccionado. ΔT usa la línea base definida abajo.")
