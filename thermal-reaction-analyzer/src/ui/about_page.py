"""Contexto académico y límites del primer avance."""

from __future__ import annotations

import streamlit as st

from src.services.flir_reader import RADIOMETRIC_CONVERSION_VERIFIED, exiftool_executable


def render_about_compact() -> None:
    """Resumen del proyecto para el panel derecho."""
    st.caption("Todo el ensayo sale de la cámara FLIR")
    st.markdown(
        """
- Preview y muestreo en vivo de la **escena USB**.
- El ΔT sigue el cambio real de esa escena, anclado a la T que muestra la FLIR.
- Con **NaOH**, un calentamiento es compatible con disolución o neutralización exotérmica.
- No hay modelo simulado de reacción ni se calcula entalpía.
        """
    )
    st.caption(
        "ExifTool: "
        + ("disponible." if exiftool_executable() else "no instalado.")
        + " JPEG radiométrico C5: "
        + ("verificado." if RADIOMETRIC_CONVERSION_VERIFIED else "aún no verificado.")
    )


def render_about_page() -> None:
    st.markdown("<div class='hero-kicker'>Primer avance</div>", unsafe_allow_html=True)
    st.markdown("<h1 class='hero-title'>Información del proyecto</h1>", unsafe_allow_html=True)
    st.markdown(
        """
El analizador registra cómo cambia la temperatura superficial durante un ensayo.
Un termómetro puntual no muestra la distribución, las zonas calientes o frías ni la evolución del campo térmico.

**Objetivo de este avance:** visualizar, registrar y analizar la escena térmica de la cámara FLIR
durante un ensayo con NaOH, sin usar un modelo simulado de reacción.
        """
    )
    st.subheader("Qué se puede afirmar")
    st.markdown(
        """
- Una subida del promedio de la ROI es una **tendencia de calentamiento superficial**.
- Una bajada es una **tendencia de enfriamiento superficial**.
- Un cambio pequeño es una **temperatura aproximadamente estable**.
- Nada de lo anterior demuestra, por sí solo, que la reacción sea endotérmica o exotérmica.
- El programa no calcula entalpía.
        """
    )
    st.subheader("FLIR C5 y E8xt")
    st.write(
        "La cámara principal prevista es la FLIR C5 (160 × 120). La E8xt (320 × 240) queda para un avance posterior. "
        "En **Captura FLIR** puedes ver la cámara USB en vivo dentro de la app; esa vista es visual "
        "(y opcionalmente con contraste), no un flujo radiométrico calibrado en °C desde Python."
    )
    st.write(
        "ExifTool: "
        + ("está disponible en este equipo." if exiftool_executable() else "no está instalado. Es opcional.")
    )
    st.write(
        "Conversión radiométrica verificada: "
        + ("sí." if RADIOMETRIC_CONVERSION_VERIFIED else "no. Hace falta un JPEG original de la FLIR C5.")
    )
    st.subheader("Evidencias para la profesora")
    st.markdown(
        """
1. Abre el panel: la cámara FLIR ya está en preview.
2. Copia la temperatura que muestra la FLIR y nombra el ensayo.
3. Inicia el experimento y observa ΔT de la escena real.
4. Lee la predicción orientativa para NaOH.
5. Descarga el CSV/JSON con el nombre del ensayo.
6. Las fotos quedan en Galería.

Para capturar la pantalla en macOS: `Cmd + Shift + 4`.
        """
    )
