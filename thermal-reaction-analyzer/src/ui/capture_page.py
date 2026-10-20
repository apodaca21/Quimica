"""Instrucciones de captura FLIR y galería de la sesión."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
CAPTURAS = ROOT / "data" / "captures"


def render_capture_page() -> None:
    st.markdown("<div class='hero-kicker'>Cámara USB</div>", unsafe_allow_html=True)
    st.markdown("<h1 class='hero-title'>Captura FLIR</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p class='hero-subtitle'>Vista en vivo de la FLIR conectada. No usa la cámara del Mac.</p>",
        unsafe_allow_html=True,
    )
    st.info(
        "La vista en vivo abre una ventana aparte con OpenCV. "
        "Ahí están los botones Contraste, Capturar y Salir. "
        "El contraste no son grados Celsius."
    )
    st.subheader("Comando en Terminal")
    st.code(
        'cd "/Users/alejandroapodaca/Documents/Carpeta 1/Escuela7/Quimica/thermal-reaction-analyzer"\n'
        "./scripts/abrir_flir.sh",
        language="bash",
    )
    st.caption("También sirve:  `.venv/bin/python -u scripts/captura_flir.py`")
    st.markdown(
        """
**En la ventana de la FLIR**

| Control | Qué hace |
|---|---|
| Botón **Contraste** o tecla `c` | Alterna vista normal / contraste visual |
| Botón **Capturar** o tecla `s` | Guarda la captura en la carpeta de esta sesión |
| Botón **Salir** o tecla `q` | Cierra la cámara |

Las capturas quedan en `data/captures/sesion_FECHA_HORA/`.
        """
    )

    if not CAPTURAS.exists():
        st.warning("Todavía no hay capturas. Abre la FLIR con el comando de arriba y pulsa Capturar.")
        return

    sesiones = sorted(
        [ruta for ruta in CAPTURAS.iterdir() if ruta.is_dir() and ruta.name.startswith("sesion_")],
        reverse=True,
    )
    if not sesiones:
        st.warning("Todavía no hay carpetas de sesión.")
        return

    elegida = st.selectbox("Sesión", sesiones, format_func=lambda ruta: ruta.name)
    fotos = sorted(elegida.glob("captura_*_vista.jpg"), reverse=True)
    st.write(f"Carpeta: `{elegida}`")
    if not fotos:
        st.caption("Esta sesión aún no tiene capturas.")
        return

    columnas = st.columns(3)
    for indice, foto in enumerate(fotos[:12]):
        with columnas[indice % 3]:
            st.image(Image.open(foto), caption=foto.name, width="stretch")
