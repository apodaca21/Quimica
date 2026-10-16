"""Registro, comparación y exportación de ensayos."""

from __future__ import annotations

from datetime import date

import streamlit as st

from src.models.experiment import Experiment
from src.models.thermal_frame import DataOrigin, origin_label
from src.services.export_service import figures_html, series_csv, series_json
from src.services.thermal_analysis import analyze_experiment
from src.ui.components import delta_figure, range_figure, render_empty, series_figure
from src.ui.state import activate, active_experiment, experiments
from src.utils.validation import ValidationError, clamp_roi


def created_date() -> str:
    return date.today().isoformat()


def _save_form(experiment: Experiment | None) -> None:
    form_key = experiment.id if experiment else "nuevo"
    with st.form(f"ensayo-{form_key}"):
        name = st.text_input("Nombre", value=experiment.name if experiment else "")
        description = st.text_area("Descripción", value=experiment.description if experiment else "")
        session_date = st.text_input("Fecha", value=experiment.session_date if experiment else "")
        assay = st.text_input("Tipo de ensayo", value=experiment.assay_type if experiment else "")
        reagents = st.text_input("Reactivos utilizados", value=experiment.reagents if experiment else "")
        ambient = st.number_input(
            "Temperatura ambiente (°C)",
            value=float(experiment.ambient_temperature_c or 24.0),
            step=0.5,
        )
        observations = st.text_area("Observaciones", value=experiment.observations if experiment else "")
        submitted = st.form_submit_button("Guardar datos del ensayo")
    if not submitted:
        return
    if experiment is None:
        created = Experiment(
            name=name.strip() or "Ensayo sin nombre",
            origin=DataOrigin.SIMULACION,
            description=description,
            session_date=session_date or created_date(),
            assay_type=assay or "Registro de sesión",
            reagents=reagents,
            ambient_temperature_c=float(ambient),
            observations=(
                "Ensayo registrado en la sesión, todavía sin cuadros térmicos. "
                "No se generaron temperaturas. "
                + observations
            ).strip(),
        )
        activate(created)
        st.success("Ensayo registrado. Aún no tiene datos térmicos.")
        return
    experiment.name = name.strip() or experiment.name
    experiment.description = description
    experiment.session_date = session_date
    experiment.assay_type = assay
    experiment.reagents = reagents
    experiment.ambient_temperature_c = float(ambient)
    experiment.observations = observations
    st.success("Datos del ensayo actualizados.")


def _analysis_for(experiment: Experiment):
    frame = experiment.numeric_frames[0]
    height, width = frame.matrix.shape  # type: ignore[union-attr]
    x, y, roi_w, roi_h = clamp_roi(
        int(st.session_state.roi_x),
        int(st.session_state.roi_y),
        int(st.session_state.roi_w),
        int(st.session_state.roi_h),
        int(height),
        int(width),
    )
    return analyze_experiment(experiment, x, y, roi_w, roi_h, int(st.session_state.baseline_frames))


def render_experiments_page() -> None:
    st.markdown("<div class='hero-kicker'>Sesión de laboratorio</div>", unsafe_allow_html=True)
    st.markdown("<h1 class='hero-title'>Análisis de experimentos</h1>", unsafe_allow_html=True)
    stored = experiments()
    current = active_experiment()
    if stored:
        labels = {
            f"{item.name} · {(origin_label(item.origin) if item.frames else 'Sin datos')} · {item.id}": item.id
            for item in stored.values()
        }
        selected = st.selectbox("Ensayo activo", list(labels), index=_index_of(labels, current.id if current else None))
        if labels[selected] != st.session_state.active_id:
            activate(stored[labels[selected]])
            current = active_experiment()
    _save_form(current)
    if current is None or not current.has_numeric_data:
        render_empty("El ensayo activo no tiene una matriz de temperatura. Simula o importa datos cuantitativos.")
        return
    if not current.has_time_series:
        render_empty("Hay temperaturas, pero no una serie temporal con al menos dos cuadros.")
        return
    try:
        result = _analysis_for(current)
    except ValidationError as exc:
        st.error(str(exc))
        return
    st.subheader("Tabla de la región de interés")
    st.dataframe(result.table, width="stretch", hide_index=True)
    st.plotly_chart(series_figure(result, len(result.table) - 1, "Temperatura promedio frente al tiempo", "Promedio"), width="stretch")
    left, right = st.columns(2)
    left.plotly_chart(range_figure(result), width="stretch")
    right.plotly_chart(delta_figure(result), width="stretch")
    csv_bytes = series_csv(current, result)
    json_bytes = series_json(current, result)
    html_bytes = figures_html(
        [
            series_figure(result, len(result.table) - 1, "Temperatura promedio", "Promedio"),
            range_figure(result),
            delta_figure(result),
        ],
        current.name,
    )
    columns = st.columns(3)
    columns[0].download_button("Descargar CSV", csv_bytes, f"{current.id}_serie.csv", "text/csv", width="stretch")
    columns[1].download_button("Descargar JSON", json_bytes, f"{current.id}_resumen.json", "application/json", width="stretch")
    columns[2].download_button("Descargar gráficas HTML", html_bytes, f"{current.id}_graficas.html", "text/html", width="stretch")

    st.subheader("Comparar dos ensayos")
    comparable = [item for item in stored.values() if item.has_time_series]
    if len(comparable) < 2:
        st.caption("Carga al menos dos ensayos con series temporales para compararlos.")
        return
    options = {f"{item.name} ({origin_label(item.origin)})": item.id for item in comparable}
    first, second = st.columns(2)
    left_id = options[first.selectbox("Primer ensayo", list(options), key="cmp_a")]
    right_id = options[second.selectbox("Segundo ensayo", list(options), index=1, key="cmp_b")]
    if left_id == right_id:
        st.warning("Elige dos ensayos distintos.")
        return
    try:
        left_result = _analysis_for(stored[left_id])
        right_result = _analysis_for(stored[right_id])
    except ValidationError as exc:
        st.error(str(exc))
        return
    import plotly.graph_objects as go

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=left_result.table["tiempo_s"],
            y=left_result.table["temperatura_promedio_C"],
            name=f"{stored[left_id].name} · {origin_label(stored[left_id].origin)}",
            line=dict(color="#67E8F9"),
        )
    )
    figure.add_trace(
        go.Scatter(
            x=right_result.table["tiempo_s"],
            y=right_result.table["temperatura_promedio_C"],
            name=f"{stored[right_id].name} · {origin_label(stored[right_id].origin)}",
            line=dict(color="#A78BFA"),
        )
    )
    figure.update_layout(template="plotly_dark", title="Comparación del promedio de la ROI", paper_bgcolor="rgba(0,0,0,0)")
    figure.update_xaxes(title="Tiempo (s)")
    figure.update_yaxes(title="Temperatura promedio (°C)")
    st.plotly_chart(figure, width="stretch")
    st.caption("La comparación no convierte una simulación en una medición ni calcula entalpía.")


def _index_of(labels: dict[str, str], active_id: str | None) -> int:
    if active_id is None:
        return 0
    for index, value in enumerate(labels.values()):
        if value == active_id:
            return index
    return 0
