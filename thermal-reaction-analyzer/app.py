"""Punto de entrada del Analizador térmico de reacciones químicas."""

from __future__ import annotations

import sys

import streamlit as st

from src.ui.about_page import render_about_page
from src.ui.dashboard import render_dashboard
from src.ui.experiments_page import render_experiments_page
from src.ui.import_page import render_import_page
from src.ui.simulation_page import render_simulation_page
from src.ui.state import init_state
from src.ui.styles import inject_css

PAGES = {
    "Panel principal": render_dashboard,
    "Simulación térmica": render_simulation_page,
    "Importar imágenes FLIR": render_import_page,
    "Análisis de experimentos": render_experiments_page,
    "Información del proyecto": render_about_page,
}


def main() -> None:
    st.set_page_config(
        page_title="Analizador térmico",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_css()
    init_state()
    if sys.version_info[:2] != (3, 12):
        st.warning(f"Este avance está probado con Python 3.12. El intérprete actual es {sys.version.split()[0]}.")
    st.sidebar.markdown("## Analizador térmico")
    st.sidebar.caption("Química · Termografía · Primer avance")
    page = st.sidebar.radio("Secciones", list(PAGES), label_visibility="collapsed")
    PAGES[page]()


if __name__ == "__main__":
    main()
