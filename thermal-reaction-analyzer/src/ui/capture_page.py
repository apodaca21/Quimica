"""Vista en vivo FLIR: la cámara es lo principal; el resto es secundario."""

from __future__ import annotations

import base64
from datetime import timedelta
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
import streamlit as st
from PIL import Image

from src.services.flir_camera import ErrorDeCamara, get_live_session
from src.ui.lab_runtime import current_record, ensure_lab_state, ingest_ocr

ROOT = Path(__file__).resolve().parents[2]
CAPTURAS = ROOT / "data" / "captures"


def _frame_html(rgb: np.ndarray) -> str:
    """Un solo bloque HTML: evita el cuadro vacío + imagen separados de Streamlit."""
    buf = BytesIO()
    Image.fromarray(rgb).save(buf, format="JPEG", quality=82)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return (
        "<div class='camera-stage'>"
        f"<img src='data:image/jpeg;base64,{b64}' alt='FLIR en vivo'/>"
        "</div>"
    )


def init_live_state() -> None:
    defaults = {
        "flir_live": False,
        "flir_contrast": False,
        "flir_label": "",
        "flir_last_save": "",
        "flir_error": "",
        "flir_recording": False,
        "flir_autostart_done": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def start_live_camera() -> None:
    st.session_state.flir_error = ""
    try:
        etiqueta = get_live_session().start()
    except ErrorDeCamara as exc:
        st.session_state.flir_live = False
        st.session_state.flir_error = str(exc)
        return
    st.session_state.flir_live = True
    st.session_state.flir_label = etiqueta
    st.session_state.flir_last_save = ""


def stop_live_camera() -> None:
    get_live_session().stop()
    st.session_state.flir_live = False
    st.session_state.flir_label = ""
    st.session_state.flir_recording = False


def start_playback_file(path: Path) -> None:
    st.session_state.flir_error = ""
    try:
        etiqueta = get_live_session().start_from_file(path)
    except ErrorDeCamara as exc:
        st.session_state.flir_live = False
        st.session_state.flir_error = str(exc)
        return
    st.session_state.flir_live = True
    st.session_state.flir_label = etiqueta
    st.session_state.flir_last_save = ""
    st.session_state.flir_recording = False


def toggle_recording() -> None:
    session = get_live_session()
    if st.session_state.get("flir_recording"):
        ruta = session.stop_recording()
        st.session_state.flir_recording = False
        if ruta is not None:
            st.session_state.flir_last_save = ruta.name
        return
    try:
        ruta = session.start_recording()
    except ErrorDeCamara as exc:
        st.session_state.flir_error = str(exc)
        st.session_state.flir_recording = False
        return
    st.session_state.flir_recording = True
    st.session_state.flir_last_save = ruta.name
    st.session_state.flir_error = ""


def capture_live_still() -> None:
    try:
        ruta = get_live_session().capturar(st.session_state.flir_contrast)
    except ErrorDeCamara as exc:
        st.session_state.flir_error = str(exc)
        st.session_state.flir_live = False
        return
    st.session_state.flir_last_save = ruta.name
    st.session_state.flir_error = ""
    record = current_record(st.session_state)
    if record is not None:
        record.captures.append(str(ruta))


def _toolbar() -> None:
    c1, c2, c3, c4 = st.columns([1.1, 1, 1.1, 1.2])
    with c1:
        st.button(
            "Iniciar",
            type="primary",
            width="stretch",
            disabled=st.session_state.flir_live,
            on_click=start_live_camera,
        )
    with c2:
        st.button(
            "Detener",
            width="stretch",
            disabled=not st.session_state.flir_live,
            on_click=stop_live_camera,
        )
    with c3:
        st.button(
            "Foto",
            width="stretch",
            disabled=not st.session_state.flir_live,
            on_click=capture_live_still,
        )
    with c4:
        etiqueta = "Detener grabación" if st.session_state.flir_recording else "Grabar"
        st.button(
            etiqueta,
            width="stretch",
            disabled=not st.session_state.flir_live,
            on_click=toggle_recording,
            key="flir_record_btn",
        )
    st.toggle(
        "Contraste",
        key="flir_contrast",
        disabled=not st.session_state.flir_live,
        help="Solo visual. No son °C.",
    )


def render_gallery_compact() -> None:
    """Galería de capturas en el panel derecho."""
    st.caption("Fotos de esta sesión. La cámara sigue a la izquierda.")
    _gallery()


def _gallery() -> None:
    if not CAPTURAS.exists():
        st.caption("Aún no hay capturas guardadas.")
        return
    sesiones = sorted(
        [ruta for ruta in CAPTURAS.iterdir() if ruta.is_dir() and ruta.name.startswith("sesion_")],
        reverse=True,
    )
    if not sesiones:
        st.caption("Aún no hay carpetas de sesión.")
        return
    elegida = st.selectbox("Sesión", sesiones, format_func=lambda ruta: ruta.name)
    fotos = sorted(elegida.glob("captura_*_vista.jpg"), reverse=True)
    if not fotos:
        st.caption("Esta sesión aún no tiene fotos.")
        return
    columnas = st.columns(3)
    for indice, foto in enumerate(fotos[:9]):
        with columnas[indice % 3]:
            st.image(Image.open(foto), caption=foto.name, width="stretch")


def render_live_stream(show_status: bool = True) -> None:
    """Renderiza el video dentro de Streamlit mientras la cámara está activa."""
    intervalo = timedelta(milliseconds=180) if st.session_state.flir_live else None

    @st.fragment(run_every=intervalo)
    def _escenario() -> None:
        if st.session_state.flir_live:
            try:
                vista_bgr, original, _ = get_live_session().read(
                    con_contraste=st.session_state.flir_contrast
                )
            except ErrorDeCamara as exc:
                mensaje = str(exc)
                if "reintentando" in mensaje.lower():
                    st.markdown(
                        "<div class='camera-stage'><div class='camera-placeholder'>"
                        f"<p>{mensaje}</p></div></div>",
                        unsafe_allow_html=True,
                    )
                    return
                st.session_state.flir_live = False
                st.session_state.flir_error = mensaje
                get_live_session().stop()
            else:
                import time

                ensure_lab_state(st.session_state)
                st.session_state.last_preview_bgr = original
                if st.session_state.get("ocr_enabled", True):
                    ingest_ocr(original, st.session_state, time.monotonic())
                rgb = cv2.cvtColor(vista_bgr, cv2.COLOR_BGR2RGB)
                st.markdown(_frame_html(rgb), unsafe_allow_html=True)
                if show_status:
                    nota = []
                    if st.session_state.flir_label:
                        nota.append(st.session_state.flir_label)
                    if st.session_state.flir_contrast:
                        nota.append("contraste visual · no °C")
                    if st.session_state.flir_last_save:
                        nota.append(f"guardado {st.session_state.flir_last_save}")
                    if nota:
                        st.caption(" · ".join(nota))
                return

        error = st.session_state.flir_error
        if error:
            corto = error.split("\n", 1)[0]
            detalle = (
                "Conecta la FLIR, enciéndela y autoriza Cámara para Terminal/Cursor "
                "en Ajustes del Sistema → Privacidad y seguridad → Cámara."
            )
            st.markdown(
                "<div class='camera-stage'><div class='camera-placeholder'>"
                f"<strong>{corto}</strong>"
                f"<p>{detalle}</p>"
                "<p>Pulsa <strong>Iniciar</strong> otra vez cuando esté lista.</p>"
                "</div></div>",
                unsafe_allow_html=True,
            )
            return

        st.markdown(
            "<div class='camera-stage'><div class='camera-placeholder'>"
            "<strong>La cámara se verá aquí</strong>"
            "<p>Pulsa <strong>Iniciar</strong>. Esta vista no usa la cámara del Mac.</p>"
            "</div></div>",
            unsafe_allow_html=True,
        )

    _escenario()


def render_capture_page() -> None:
    init_live_state()

    _toolbar()
    render_live_stream(show_status=False)

    with st.expander("Galería y opciones", expanded=False):
        st.caption("Secundario: fotos guardadas y ventana aparte de OpenCV.")
        _gallery()
        st.code(
            'cd "/Users/alejandroapodaca/Documents/Carpeta 1/Escuela7/Quimica/thermal-reaction-analyzer"\n'
            "./scripts/abrir_flir.sh",
            language="bash",
        )
