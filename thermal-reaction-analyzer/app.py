"""Punto de entrada del Analizador térmico de reacciones químicas."""

from __future__ import annotations

import sys

import streamlit as st

from src.ui.dashboard import render_dashboard
from src.ui.state import init_state
from src.ui.styles import inject_css


def main() -> None:
    st.set_page_config(
        page_title="THERMAL LAB",
        layout="wide",
        initial_sidebar_state="collapsed",
        menu_items={"Get Help": None, "Report a Bug": None, "About": None},
    )
    inject_css()
    init_state()
    if sys.version_info[:2] != (3, 12):
        st.warning(f"Este avance está probado con Python 3.12. El intérprete actual es {sys.version.split()[0]}.")
    render_dashboard()


if __name__ == "__main__":
    main()
