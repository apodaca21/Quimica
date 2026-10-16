"""Importación de imágenes y matrices."""

from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from src.services.data_import import import_paths
from src.services.flir_reader import RADIOMETRIC_CONVERSION_VERIFIED, exiftool_executable
from src.ui.components import render_workspace
from src.ui.state import activate
from src.utils.validation import ValidationError


def render_import_page() -> None:
    st.markdown("<div class='hero-kicker'>Archivos locales</div>", unsafe_allow_html=True)
    st.markdown("<h1 class='hero-title'>Importar imágenes FLIR</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p class='hero-subtitle'>Carga matrices numéricas o fotografías. Una imagen a color no se convierte a grados Celsius.</p>",
        unsafe_allow_html=True,
    )
    exiftool = exiftool_executable()
    st.info(
        "ExifTool: "
        + ("disponible." if exiftool else "no instalado. El resto del sistema funciona igual.")
        + " Conversión radiométrica de la FLIR C5: "
        + ("verificada." if RADIOMETRIC_CONVERSION_VERIFIED else "pendiente de un JPEG original de la cámara.")
    )
    with st.expander("Qué significa cada resultado"):
        st.markdown(
            """
- **Simulación:** datos generados por el modelo ilustrativo.
- **Datos cuantitativos importados:** números leídos de CSV, NPY o NPZ. No los certificó la cámara.
- **Medición radiométrica verificada:** todavía no se asigna. Hará falta un JPEG original de la FLIR C5 y una conversión comprobada.
- **Imagen visual o FLIR pendiente:** se muestra la fotografía y, si ExifTool está disponible, los metadatos. No hay temperaturas.
            """
        )
    name = st.text_input("Nombre del ensayo importado", value="Importación de laboratorio")
    interval = st.number_input(
        "Intervalo manual si la secuencia no trae tiempo (s)",
        min_value=0.25,
        max_value=30.0,
        value=1.0,
        step=0.25,
        help="Se usa solo cuando hay varias matrices y el archivo no incluye marcas de tiempo.",
    )
    uploads = st.file_uploader(
        "Archivos JPG, JPEG, PNG, CSV, NPY o NPZ",
        type=["jpg", "jpeg", "png", "csv", "npy", "npz"],
        accept_multiple_files=True,
    )
    if st.button("Importar archivos", type="primary", disabled=not uploads):
        try:
            with tempfile.TemporaryDirectory() as directory:
                paths: list[Path] = []
                for upload in uploads or []:
                    destination = Path(directory) / Path(upload.name).name
                    destination.write_bytes(upload.getvalue())
                    paths.append(destination)
                result = import_paths(paths, name.strip() or "Importación", manual_interval_s=float(interval))
        except ValidationError as exc:
            st.error(str(exc))
        else:
            for message in result.messages:
                st.warning(message) if "No se calculan" in message or "sin temperaturas" in message else st.success(message)
            if result.experiment is not None:
                activate(result.experiment, start_playback=False)
    st.subheader("Ensayo activo")
    render_workspace()
