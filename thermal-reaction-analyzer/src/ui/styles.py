"""Estilos del tablero científico."""

from __future__ import annotations

import streamlit as st

CSS = """
<style>
.stApp {
    background:
        radial-gradient(900px 420px at 0% -10%, rgba(88, 80, 236, 0.28), transparent 55%),
        radial-gradient(700px 380px at 100% 0%, rgba(34, 211, 238, 0.12), transparent 50%),
        #0b1020;
}
[data-testid="stSidebar"] {
    background: #101628;
    border-right: 1px solid rgba(124, 140, 196, 0.25);
}
.block-container { padding-top: 1.4rem; max-width: 1240px; }
h1, h2, h3 { letter-spacing: -0.03em; }
.hero-kicker {
    color: #8be9ff;
    font-size: 0.78rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    margin-bottom: 0.2rem;
}
.hero-title {
    font-size: 2.1rem;
    font-weight: 680;
    margin: 0;
    color: #f4f7ff;
}
.hero-subtitle { color: #b7c3dc; margin: 0.35rem 0 0.8rem; }
.pill-row { display: flex; flex-wrap: wrap; gap: 0.45rem; margin: 0.4rem 0 1rem; }
.pill {
    border: 1px solid rgba(103, 232, 249, 0.35);
    background: rgba(18, 28, 52, 0.9);
    color: #d7e4ff;
    border-radius: 999px;
    padding: 0.28rem 0.7rem;
    font-size: 0.82rem;
}
.pill strong { color: #67e8f9; font-weight: 640; }
.metric-card {
    background: linear-gradient(180deg, rgba(28, 38, 68, 0.95), rgba(16, 22, 40, 0.95));
    border: 1px solid rgba(124, 108, 255, 0.35);
    border-radius: 16px;
    padding: 0.9rem 1rem 0.75rem;
    min-height: 104px;
}
.metric-label { color: #9aaacc; font-size: 0.82rem; }
.metric-value { color: #f5f8ff; font-size: 1.7rem; font-weight: 680; line-height: 1.15; margin-top: 0.25rem; }
.metric-unit { color: #7f93b8; font-size: 0.85rem; margin-left: 0.2rem; }
.panel {
    background: rgba(14, 20, 36, 0.72);
    border: 1px solid rgba(124, 140, 196, 0.22);
    border-radius: 16px;
    padding: 0.9rem 1rem;
    margin-top: 0.6rem;
}
.panel h3 { margin: 0 0 0.4rem; font-size: 1.05rem; }
.empty-state {
    border: 1px dashed rgba(103, 232, 249, 0.4);
    border-radius: 16px;
    padding: 1.4rem 1.2rem;
    color: #c5d2ea;
    background: rgba(12, 18, 34, 0.65);
}
.warning-list { color: #d5deef; margin: 0.2rem 0 0; padding-left: 1.1rem; }
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
