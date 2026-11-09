"""Estilos de la consola de trabajo."""

from __future__ import annotations

import streamlit as st

CSS = """
<style>
header[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
.stDeployButton,
div[data-testid="stStatusWidget"] {
    display: none !important;
}
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }

html, body, .stApp {
    height: 100%;
}
.stApp {
    background:
        radial-gradient(900px 420px at 0% -10%, rgba(88, 80, 236, 0.22), transparent 55%),
        radial-gradient(700px 380px at 100% 0%, rgba(34, 211, 238, 0.10), transparent 50%),
        #0b1020;
}
[data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"] {
    display: none !important;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2 {
    font-size: 1.05rem;
    margin: 0.2rem 0 0.15rem;
}
[data-testid="stMainBlockContainer"],
.block-container {
    padding: 0.45rem 0.85rem 0.35rem !important;
    max-width: 100% !important;
}
.stApp [data-testid="stVerticalBlock"] {
    gap: 0.35rem;
}
.stButton button {
    min-height: 3.15rem;
    padding: 0.55rem 1rem;
    font-size: 1.08rem !important;
    font-weight: 670 !important;
    border-radius: 12px !important;
}
div[data-testid="stTextInput"] input {
    font-size: 1.45rem !important;
    font-weight: 700 !important;
    min-height: 3.2rem !important;
    border-radius: 12px !important;
}
div[data-testid="stTextArea"] textarea {
    font-size: 1.05rem !important;
    min-height: 8.5rem !important;
    border-radius: 12px !important;
}
.notes-title {
    color: #c9d6ee;
    font-size: 0.92rem;
    font-weight: 650;
    margin: 0.15rem 0 0.25rem;
}
div[data-testid="stPills"] {
    margin: 0.1rem 0 0.25rem;
}
h1, h2, h3 { letter-spacing: -0.03em; }
.app-bar {
    display: flex;
    align-items: baseline;
    gap: 0.75rem;
    margin: 0 0 0.15rem;
}
.app-title {
    font-size: 1.28rem;
    font-weight: 700;
    color: #f4f7ff;
    margin: 0;
    letter-spacing: 0.04em;
}
.app-kicker {
    color: #8ea0c4;
    font-size: 0.78rem;
    margin: 0.08rem 0 0;
}
.app-status {
    color: #8be9ff;
    font-size: 0.78rem;
}
.status-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    align-items: center;
    min-height: 2.4rem;
}
.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    border-radius: 999px;
    padding: 0.28rem 0.7rem;
    font-size: 0.78rem;
    font-weight: 600;
    border: 1px solid rgba(148, 163, 196, 0.28);
    background: rgba(16, 24, 42, 0.88);
    color: #c9d6ee;
}
.status-pill i {
    width: 0.48rem;
    height: 0.48rem;
    border-radius: 50%;
    background: #64748b;
    display: inline-block;
}
.status-pill.on {
    border-color: rgba(52, 211, 153, 0.45);
    color: #d1fae5;
}
.status-pill.on i { background: #34d399; box-shadow: 0 0 8px #34d399; }
.status-pill.wait {
    border-color: rgba(167, 139, 250, 0.4);
    color: #e9d5ff;
}
.status-pill.wait i { background: #a78bfa; }
.status-pill.run {
    border-color: rgba(103, 232, 249, 0.45);
    color: #cffafe;
}
.status-pill.run i { background: #67e8f9; box-shadow: 0 0 8px #67e8f9; }
.status-pill.off {
    border-color: rgba(251, 113, 133, 0.35);
    color: #fecdd3;
}
.status-pill.off i { background: #fb7185; }
.ready-card {
    margin-top: 0.55rem;
    border: 1px solid rgba(124, 108, 255, 0.32);
    border-radius: 12px;
    padding: 0.85rem 0.95rem;
    background: linear-gradient(180deg, rgba(24, 32, 58, 0.92), rgba(12, 18, 34, 0.92));
    color: #d5def0;
}
.ready-card strong {
    display: block;
    color: #f4f7ff;
    font-size: 0.95rem;
    margin-bottom: 0.28rem;
}
.ready-card p {
    margin: 0;
    color: #9eb0d0;
    font-size: 0.84rem;
    line-height: 1.4;
}
.hero-kicker {
    color: #8be9ff;
    font-size: 0.72rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    margin-bottom: 0.1rem;
}
.hero-title {
    font-size: 1.45rem;
    font-weight: 680;
    margin: 0;
    color: #f4f7ff;
}
.hero-subtitle { color: #b7c3dc; margin: 0.2rem 0 0.45rem; font-size: 0.92rem; }
.pill-row { display: flex; flex-wrap: wrap; gap: 0.35rem; margin: 0.15rem 0 0.35rem; }
.pill {
    border: 1px solid rgba(103, 232, 249, 0.35);
    background: rgba(18, 28, 52, 0.9);
    color: #d7e4ff;
    border-radius: 999px;
    padding: 0.18rem 0.55rem;
    font-size: 0.75rem;
}
.pill strong { color: #67e8f9; font-weight: 640; }
.metric-card {
    background: linear-gradient(180deg, rgba(28, 38, 68, 0.95), rgba(16, 22, 40, 0.95));
    border: 1px solid rgba(124, 108, 255, 0.35);
    border-radius: 12px;
    padding: 0.55rem 0.65rem 0.5rem;
    min-height: 4.15rem;
    margin: 0 0 0.55rem;
}
.metric-card-sm .metric-value { font-size: 1.12rem; }
.metric-label { color: #9aaacc; font-size: 0.72rem; }
.metric-value { color: #f5f8ff; font-size: 1.22rem; font-weight: 680; line-height: 1.15; margin-top: 0.1rem; }
.metric-unit { color: #7f93b8; font-size: 0.78rem; margin-left: 0.2rem; }
.panel {
    background: rgba(14, 20, 36, 0.72);
    border: 1px solid rgba(124, 140, 196, 0.22);
    border-radius: 12px;
    padding: 0.55rem 0.7rem;
    margin-top: 0.25rem;
}
.panel h3 { margin: 0 0 0.25rem; font-size: 0.95rem; }
.empty-state {
    border: 1px solid rgba(124, 108, 255, 0.32);
    border-radius: 12px;
    padding: 0.85rem 0.95rem;
    color: #c5d2ea;
    background: rgba(12, 18, 34, 0.65);
    font-size: 0.88rem;
}
.warning-list { color: #d5deef; margin: 0.2rem 0 0; padding-left: 1.1rem; font-size: 0.82rem; }
.camera-stage {
    background: #05080f;
    border: 1px solid rgba(124, 140, 196, 0.28);
    border-radius: 14px;
    min-height: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0.3rem;
    margin: 0;
    overflow: hidden;
}
.camera-stage img {
    display: block;
    width: 100%;
    max-height: calc(100vh - 92px);
    height: auto;
    object-fit: contain;
    border-radius: 10px;
}
.camera-stage:has(.camera-placeholder) { min-height: calc(100vh - 92px); }
.camera-placeholder {
    text-align: center;
    color: #9eb0d0;
    padding: 2rem 1rem;
    max-width: 26rem;
}
.camera-placeholder strong { color: #e8eefc; font-size: 1.05rem; }
.camera-placeholder p { margin: 0.45rem 0 0; color: #8fa2c2; font-size: 0.88rem; }
.camera-toolbar { margin: 0; }
.capture-title {
    font-size: 1.05rem;
    font-weight: 650;
    color: #f4f7ff;
    margin: 0 0 0.2rem;
}
.side-hint { color: #9eb0d0; font-size: 0.82rem; margin: 0; }
.predict-card {
    background: rgba(16, 28, 52, 0.95);
    border: 1px solid rgba(103, 232, 249, 0.4);
    border-radius: 12px;
    padding: 0.5rem 0.65rem 0.45rem;
    margin-top: 0.25rem;
}
.predict-card .label {
    color: #8be9ff;
    font-size: 0.7rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}
.predict-card .value {
    color: #f4f7ff;
    font-size: 0.92rem;
    font-weight: 640;
    margin: 0.28rem 0 0.2rem;
    line-height: 1.3;
}
.predict-card p { color: #9eb0d0; font-size: 0.78rem; margin: 0.15rem 0 0; }
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
