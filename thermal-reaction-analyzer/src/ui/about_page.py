"""Contexto académico y límites del primer avance."""

from __future__ import annotations

import streamlit as st

from src.services.flir_reader import RADIOMETRIC_CONVERSION_VERIFIED, exiftool_executable
from src.services.simulation import MODEL_NOTE
from src.utils.limits import MAX_DURATION_S, MAX_SIM_FRAMES, THERMAL_HEIGHT, THERMAL_WIDTH


def render_about_page() -> None:
    st.markdown("<div class='hero-kicker'>Primer avance</div>", unsafe_allow_html=True)
    st.markdown("<h1 class='hero-title'>Información del proyecto</h1>", unsafe_allow_html=True)
    st.markdown(
        """
El analizador registra cómo cambia la temperatura superficial durante un ensayo.
Un termómetro puntual no muestra la distribución, las zonas calientes o frías ni la evolución del campo térmico.

**Objetivo de este avance:** visualizar, registrar y analizar temperaturas con datos simulados
y con matrices importadas, dejando preparada —sin dar por válida— la lectura de JPEG de la FLIR C5.
        """
    )
    st.subheader("Modelo de simulación")
    st.write(MODEL_NOTE)
    st.write(
        f"Cada cuadro simulado mide {THERMAL_WIDTH} px de ancho por {THERMAL_HEIGHT} px de alto, "
        "la resolución térmica de la FLIR C5. "
        f"La sesión acepta como máximo {MAX_SIM_FRAMES} cuadros y {MAX_DURATION_S:g} s."
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
        "No se asume un flujo radiométrico en tiempo real accesible desde Python."
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
1. Abre el panel principal y muestra el estado vacío, sin cifras inventadas.
2. En Simulación térmica, inicia un calentamiento y observa el mapa.
3. Consulta mínimo, máximo, promedio y la gráfica temporal.
4. Cambia la ROI y compara el centro con una esquina.
5. Lee ΔT, la tendencia y las advertencias.
6. Descarga el CSV.
7. Importa `data/samples/matriz_simulada.npy` o `secuencia_simulada.npz`.
8. En la importación, explica que la extracción de la C5 está preparada y no verificada.

Para capturar la pantalla en macOS: `Cmd + Shift + 4`.
        """
    )
