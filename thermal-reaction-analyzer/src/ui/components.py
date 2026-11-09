"""Componentes compartidos del visualizador térmico."""

from __future__ import annotations

import html
import time
from datetime import timedelta

import plotly.graph_objects as go
import streamlit as st

from src.models.experiment import Experiment
from src.models.thermal_frame import DataOrigin, origin_label
from src.services.export_service import figures_html, series_csv, series_json
from src.services.thermal_analysis import AnalysisResult, analyze_experiment
from src.services.thermal_interpretation import ThermalInterpretation, classify_thermal_behavior
from src.ui.state import active_experiment
from src.utils.validation import ValidationError, clamp_roi

PALETTES = ["Inferno", "Magma", "Plasma", "Viridis", "Cividis", "Hot"]


def _dark(fig: go.Figure, height: int = 320) -> go.Figure:
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(12,18,32,0.35)",
        height=height,
        margin=dict(l=48, r=16, t=42, b=42),
        font=dict(color="#E8EEF9"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    return fig


def heatmap_figure(matrix, x: int, y: int, width: int, height: int, palette: str) -> go.Figure:
    figure = go.Figure(
        data=[
            go.Heatmap(
                z=matrix,
                colorscale=palette,
                colorbar=dict(title="°C"),
                hovertemplate="x=%{x}<br>y=%{y}<br>%{z:.2f} °C<extra></extra>",
            )
        ]
    )
    figure.add_shape(
        type="rect",
        x0=x - 0.5,
        x1=x + width - 0.5,
        y0=y - 0.5,
        y1=y + height - 0.5,
        line=dict(color="#67E8F9", width=2),
    )
    figure.update_xaxes(title="x (px)")
    figure.update_yaxes(title="y (px)", autorange="reversed")
    figure.update_layout(title="Mapa térmico de la superficie")
    return _dark(figure)


def series_figure(result: AnalysisResult, frame_index: int, title: str, mean_name: str) -> go.Figure:
    table = result.table
    times = table["tiempo_s"]
    means = table["temperatura_promedio_C"]
    figure = go.Figure()
    figure.add_trace(go.Scatter(x=times, y=means, mode="lines+markers", name=mean_name, line=dict(color="#67E8F9")))
    figure.add_hline(
        y=result.baseline_c,
        line_dash="dot",
        line_color="#A78BFA",
        annotation_text="Línea base",
        annotation_position="top left",
    )
    if len(table) >= 2:
        max_index = int(means.idxmax())
        min_index = int(means.idxmin())
        figure.add_trace(
            go.Scatter(
                x=[times.iloc[max_index]],
                y=[means.iloc[max_index]],
                mode="markers",
                name="Máximo",
                marker=dict(size=12, color="#FB7185", symbol="diamond"),
            )
        )
        figure.add_trace(
            go.Scatter(
                x=[times.iloc[min_index]],
                y=[means.iloc[min_index]],
                mode="markers",
                name="Mínimo",
                marker=dict(size=12, color="#38BDF8", symbol="circle"),
            )
        )
        current = min(max(frame_index, 0), len(table) - 1)
        figure.add_trace(
            go.Scatter(
                x=[times.iloc[current]],
                y=[means.iloc[current]],
                mode="markers",
                name="Cuadro actual",
                marker=dict(size=11, color="#F8FAFC", symbol="x"),
            )
        )
    figure.update_xaxes(title="Tiempo (s)")
    figure.update_yaxes(title="Temperatura promedio de la ROI (°C)")
    figure.update_layout(title=title)
    return _dark(figure)


def range_figure(result: AnalysisResult) -> go.Figure:
    table = result.table
    figure = go.Figure()
    figure.add_trace(go.Scatter(x=table["tiempo_s"], y=table["temperatura_max_C"], name="Máxima", line=dict(color="#FB7185")))
    figure.add_trace(go.Scatter(x=table["tiempo_s"], y=table["temperatura_min_C"], name="Mínima", line=dict(color="#38BDF8")))
    figure.update_xaxes(title="Tiempo (s)")
    figure.update_yaxes(title="Temperatura (°C)")
    figure.update_layout(title="Temperatura mínima y máxima")
    return _dark(figure, 280)


def delta_figure(result: AnalysisResult) -> go.Figure:
    table = result.table
    figure = go.Figure(
        data=[go.Scatter(x=table["tiempo_s"], y=table["delta_T_C"], name="ΔT", line=dict(color="#A78BFA"))]
    )
    figure.add_hline(y=0, line_dash="dot", line_color="#64748B")
    figure.update_xaxes(title="Tiempo (s)")
    figure.update_yaxes(title="ΔT respecto a la línea base (°C)")
    figure.update_layout(title="Cambio de temperatura")
    return _dark(figure, 280)


def metric_card(label: str, value: str, unit: str = "", compact: bool = False) -> str:
    unit_html = f"<span class='metric-unit'>{html.escape(unit)}</span>" if unit else ""
    klass = "metric-card metric-card-sm" if compact else "metric-card"
    return (
        f"<div class='{klass}'>"
        f"<div class='metric-label'>{html.escape(label)}</div>"
        f"<div class='metric-value'>{html.escape(value)}{unit_html}</div>"
        "</div>"
    )


def render_pills(items: list[tuple[str, str]]) -> None:
    parts = "".join(
        f"<span class='pill'><strong>{html.escape(label)}:</strong> {html.escape(value)}</span>"
        for label, value in items
    )
    st.markdown(f"<div class='pill-row'>{parts}</div>", unsafe_allow_html=True)


def render_thermal_interpretation(
    result: AnalysisResult,
    experiment: Experiment | None = None,
    compact: bool = False,
) -> ThermalInterpretation:
    """Muestra la lectura automática y devuelve el resultado para la pantalla."""
    interpretation = classify_thermal_behavior(result, experiment=experiment)
    if compact:
        st.markdown(
            f"**{html.escape(interpretation.label)}** · {html.escape(interpretation.confidence.capitalize())}"
        )
        st.caption(interpretation.summary)
        st.caption(f"Predicción: {interpretation.reaction_prediction}")
        with st.expander("Evidencia y advertencias"):
            for item in interpretation.evidence:
                st.markdown(f"- {html.escape(item)}")
            st.markdown("**Evidencia de la predicción:**")
            for item in interpretation.reaction_evidence:
                st.markdown(f"- {html.escape(item)}")
            for item in interpretation.warnings:
                st.markdown(f"- {html.escape(item)}")
        return interpretation
    st.markdown("<div class='panel'><h3>Asistente de comportamiento térmico</h3>", unsafe_allow_html=True)
    st.write(interpretation.summary)
    left, right = st.columns(2)
    left.metric("Clasificación", interpretation.label)
    right.metric("Confianza orientativa", interpretation.confidence.capitalize())
    st.markdown(f"**Predicción orientativa de reacción:** {html.escape(interpretation.reaction_prediction)}")
    st.caption(f"Confianza de la predicción: {interpretation.reaction_confidence}")
    with st.expander("Ver evidencia del análisis"):
        for item in interpretation.evidence:
            st.markdown(f"- {html.escape(item)}")
        st.markdown("**Evidencia de la predicción:**")
        for item in interpretation.reaction_evidence:
            st.markdown(f"- {html.escape(item)}")
    st.markdown(
        "<ul class='warning-list'>"
        + "".join(f"<li>{html.escape(item)}</li>" for item in interpretation.warnings)
        + "</ul></div>",
        unsafe_allow_html=True,
    )
    return interpretation


def render_empty(message: str) -> None:
    st.markdown(f"<div class='empty-state'>{html.escape(message)}</div>", unsafe_allow_html=True)


def _ensure_widget(key: str, value: int, upper: int, lower: int = 0) -> None:
    if key not in st.session_state:
        st.session_state[key] = int(min(max(value, lower), upper))


def _roi_controls(width: int, height: int, compact: bool = False) -> tuple[int, int, int, int]:
    _ensure_widget("roi_x_input", int(st.session_state.roi_x), width - 1)
    _ensure_widget("roi_y_input", int(st.session_state.roi_y), height - 1)
    _ensure_widget("roi_w_input", int(st.session_state.roi_w), width, 1)
    _ensure_widget("roi_h_input", int(st.session_state.roi_h), height, 1)
    if compact:
        row1 = st.columns(2)
        row2 = st.columns(2)
        x = row1[0].number_input("X", min_value=0, max_value=width - 1, key="roi_x_input")
        y = row1[1].number_input("Y", min_value=0, max_value=height - 1, key="roi_y_input")
        roi_w = row2[0].number_input("Ancho", min_value=1, max_value=width, key="roi_w_input")
        roi_h = row2[1].number_input("Alto", min_value=1, max_value=height, key="roi_h_input")
    else:
        columns = st.columns(4)
        x = columns[0].number_input("Posición X", min_value=0, max_value=width - 1, key="roi_x_input")
        y = columns[1].number_input("Posición Y", min_value=0, max_value=height - 1, key="roi_y_input")
        roi_w = columns[2].number_input("Ancho", min_value=1, max_value=width, key="roi_w_input")
        roi_h = columns[3].number_input("Alto", min_value=1, max_value=height, key="roi_h_input")
    fitted = clamp_roi(int(x), int(y), int(roi_w), int(roi_h), height, width)
    st.session_state.roi_x, st.session_state.roi_y, st.session_state.roi_w, st.session_state.roi_h = fitted
    return fitted


def _advance_playback(n_frames: int) -> None:
    if not st.session_state.playing or n_frames < 2:
        st.session_state.pop("_playback_tick", None)
        return
    now = time.monotonic()
    previous = st.session_state.get("_playback_tick")
    delay = float(st.session_state.playback_delay_s)
    if previous is None:
        st.session_state._playback_tick = now
        return
    if now - float(previous) < delay * 0.75:
        return
    st.session_state._playback_tick = now
    if int(st.session_state.frame_index) >= n_frames - 1:
        st.session_state.playing = False
        return
    st.session_state.frame_index = int(st.session_state.frame_index) + 1
    st.session_state.instante = int(st.session_state.frame_index)


def _playback_controls(n_frames: int, compact: bool = False) -> None:
    if compact:
        row = st.columns(4)
        if row[0].button("▶", disabled=n_frames < 2, width="stretch", help="Reproducir"):
            st.session_state.playing = True
            st.session_state.pop("_playback_tick", None)
        if row[1].button("⏸", width="stretch", help="Pausar"):
            st.session_state.playing = False
        if row[2].button("⏮", width="stretch", help="Reiniciar"):
            st.session_state.playing = False
            st.session_state.frame_index = 0
            st.session_state.instante = 0
        if row[3].button("⏭", disabled=n_frames < 2, width="stretch", help="Avanzar cuadro"):
            st.session_state.playing = False
            st.session_state.frame_index = min(n_frames - 1, int(st.session_state.frame_index) + 1)
            st.session_state.instante = int(st.session_state.frame_index)
        st.session_state.playback_delay_s = st.slider(
            "Intervalo (s)",
            min_value=0.5,
            max_value=2.0,
            value=float(st.session_state.playback_delay_s),
            step=0.1,
            help="Tiempo entre cuadros en la pantalla.",
        )
        return
    controls = st.columns(5)
    if controls[0].button("Reproducir", disabled=n_frames < 2, width="stretch"):
        st.session_state.playing = True
        st.session_state.pop("_playback_tick", None)
    if controls[1].button("Pausar", width="stretch"):
        st.session_state.playing = False
    if controls[2].button("Reiniciar", width="stretch"):
        st.session_state.playing = False
        st.session_state.frame_index = 0
        st.session_state.instante = 0
    if controls[3].button("Avanzar cuadro", disabled=n_frames < 2, width="stretch"):
        st.session_state.playing = False
        st.session_state.frame_index = min(n_frames - 1, int(st.session_state.frame_index) + 1)
        st.session_state.instante = int(st.session_state.frame_index)
    st.session_state.playback_delay_s = controls[4].slider(
        "Intervalo visual (s)",
        min_value=0.5,
        max_value=2.0,
        value=float(st.session_state.playback_delay_s),
        step=0.1,
        help="Tiempo entre cuadros en la pantalla. No cambia el tiempo del experimento.",
    )


def _draw_numeric(experiment: Experiment, compact: bool = False) -> None:
    frames = experiment.numeric_frames
    height, width = frames[0].matrix.shape  # type: ignore[union-attr]
    x, y, roi_w, roi_h = _roi_controls(width, height, compact=compact)
    max_baseline = max(1, len(frames))
    if compact:
        opts = st.columns(2)
        baseline_count = opts[0].number_input(
            "Línea base",
            min_value=1,
            max_value=max_baseline,
            value=min(int(st.session_state.baseline_frames), max_baseline),
            step=1,
            help="Promedio de los primeros cuadros de la ROI.",
        )
        palette = opts[1].selectbox(
            "Paleta",
            PALETTES,
            index=PALETTES.index(st.session_state.palette) if st.session_state.palette in PALETTES else 0,
        )
    else:
        baseline_count = st.number_input(
            "Cuadros de la línea base",
            min_value=1,
            max_value=max_baseline,
            value=min(int(st.session_state.baseline_frames), max_baseline),
            step=1,
            help="La temperatura inicial es el promedio de los primeros cuadros de la ROI.",
        )
        palette = st.selectbox(
            "Paleta térmica",
            PALETTES,
            index=PALETTES.index(st.session_state.palette) if st.session_state.palette in PALETTES else 0,
        )
    st.session_state.baseline_frames = int(baseline_count)
    st.session_state.palette = palette
    n_frames = len(frames)
    _playback_controls(n_frames, compact=compact)

    delay = float(st.session_state.playback_delay_s) if st.session_state.playing else None

    @st.fragment(run_every=timedelta(seconds=delay) if delay else None)
    def synced_viewer() -> None:
        current = active_experiment()
        if current is None or not current.has_numeric_data:
            return
        current_frames = current.numeric_frames
        _advance_playback(len(current_frames))
        index = min(max(int(st.session_state.frame_index), 0), len(current_frames) - 1)
        st.session_state.frame_index = index
        if len(current_frames) > 1:
            if "instante" not in st.session_state or st.session_state.playing:
                st.session_state.instante = index
            chosen = st.slider("Instante", 0, len(current_frames) - 1, key="instante")
            if not st.session_state.playing and int(chosen) != index:
                st.session_state.frame_index = int(chosen)
                index = int(chosen)
        elif not compact:
            st.caption("Hay un solo cuadro. No se construyó una serie temporal.")
        try:
            result = analyze_experiment(current, x, y, roi_w, roi_h, int(st.session_state.baseline_frames))
        except ValidationError as exc:
            st.error(str(exc))
            return
        stats = result.frame_stats[index]
        row = result.table.iloc[index]
        values = [
            ("Mín.", f"{stats.min_c:.2f}", "°C") if compact else ("Temperatura mínima", f"{stats.min_c:.2f}", "°C"),
            ("Máx.", f"{stats.max_c:.2f}", "°C") if compact else ("Temperatura máxima", f"{stats.max_c:.2f}", "°C"),
            ("Prom.", f"{stats.mean_c:.2f}", "°C") if compact else ("Temperatura promedio", f"{stats.mean_c:.2f}", "°C"),
            ("ΔT", f"{float(row['delta_T_C']):.2f}", "°C") if compact else ("Cambio ΔT del cuadro", f"{float(row['delta_T_C']):.2f}", "°C"),
        ]
        if compact:
            cards = st.columns(2)
            for column, (label, value, unit) in zip(cards, values[:2]):
                column.markdown(metric_card(label, value, unit, compact=True), unsafe_allow_html=True)
            cards = st.columns(2)
            for column, (label, value, unit) in zip(cards, values[2:]):
                column.markdown(metric_card(label, value, unit, compact=True), unsafe_allow_html=True)
        else:
            cards = st.columns(4)
            for column, (label, value, unit) in zip(cards, values):
                column.markdown(metric_card(label, value, unit), unsafe_allow_html=True)
        matrix = current_frames[index].matrix
        if compact:
            mapa, serie, lectura = st.tabs(["Mapa", "Serie", "Lectura"])
            with mapa:
                st.plotly_chart(
                    heatmap_figure(matrix, x, y, roi_w, roi_h, st.session_state.palette),
                    width="stretch",
                    config={"displayModeBar": False},
                )
            with serie:
                if len(current_frames) < 2 or result.table["tiempo_s"].isna().any():
                    render_empty("No hay una serie temporal.")
                else:
                    st.plotly_chart(
                        series_figure(result, index, "Evolución de la ROI", "Promedio"),
                        width="stretch",
                        config={"displayModeBar": False},
                    )
            with lectura:
                st.caption(f"{result.trend} · ΔT {result.delta_t_c:.2f} °C · base {result.baseline_c:.2f} °C")
                render_thermal_interpretation(result, experiment, compact=True)
        else:
            left, right = st.columns(2)
            with left:
                st.plotly_chart(
                    heatmap_figure(matrix, x, y, roi_w, roi_h, st.session_state.palette),
                    width="stretch",
                )
                st.caption(
                    f"Punto más caliente: ({stats.hottest_x}, {stats.hottest_y}) px. "
                    f"Punto más frío: ({stats.coldest_x}, {stats.coldest_y}) px. "
                    f"Desviación estándar de la ROI: {stats.std_c:.2f} °C."
                )
            with right:
                if len(current_frames) < 2 or result.table["tiempo_s"].isna().any():
                    render_empty("No hay una serie temporal. Un solo cuadro no describe una evolución.")
                else:
                    st.plotly_chart(
                        series_figure(result, index, "Evolución térmica de la ROI", "Promedio de la ROI"),
                        width="stretch",
                    )
            st.markdown("<div class='panel'><h3>Interpretación</h3>", unsafe_allow_html=True)
            st.write(result.explanation)
            st.markdown(
                f"**Tendencia de la serie:** {result.trend}  \n**ΔT de la serie:** {result.delta_t_c:.2f} °C  \n"
                f"**Línea base:** {result.baseline_c:.2f} °C, calculada con {result.baseline_frames} cuadro(s)."
            )
            st.markdown(
                "<ul class='warning-list'>"
                + "".join(f"<li>{html.escape(item)}</li>" for item in result.warnings)
                + "</ul></div>",
                unsafe_allow_html=True,
            )
            render_thermal_interpretation(result, experiment)
        st.session_state["latest_result"] = result
        st.session_state["latest_figures"] = [
            series_figure(result, index, "Temperatura promedio", "Promedio"),
            range_figure(result),
            delta_figure(result),
        ]

    synced_viewer()
    _render_downloads(experiment)


def _render_downloads(experiment: Experiment) -> None:
    result = st.session_state.get("latest_result")
    figures = st.session_state.get("latest_figures")
    if not isinstance(result, AnalysisResult) or result.table.empty:
        return
    st.caption("Exportar")
    csv_bytes = series_csv(experiment, result)
    json_bytes = series_json(experiment, result)
    columns = st.columns(3)
    columns[0].download_button(
        "CSV",
        data=csv_bytes,
        file_name=f"{experiment.file_stem}_serie.csv",
        mime="text/csv",
        width="stretch",
    )
    columns[1].download_button(
        "JSON",
        data=json_bytes,
        file_name=f"{experiment.file_stem}_resumen.json",
        mime="application/json",
        width="stretch",
    )
    if figures:
        columns[2].download_button(
            "Gráficas",
            data=figures_html(figures, experiment.name),
            file_name=f"{experiment.file_stem}_graficas.html",
            mime="text/html",
            width="stretch",
        )


def render_workspace(compact: bool = False) -> None:
    experiment = active_experiment()
    if experiment is None:
        if compact:
            st.markdown(
                "<div class='empty-state'>Sin ensayo de cámara. Inicia el experimento "
                "con la FLIR a la izquierda.</div>",
                unsafe_allow_html=True,
            )
            return
        render_empty("No hay un experimento activo. Inicia un ensayo con la cámara FLIR.")
        return
    if compact:
        st.caption(f"{experiment.name} · {_data_kind(experiment.origin)}")
    else:
        render_pills(
            [
                ("Estado", "Listo" if experiment.frames else "Sin datos"),
                ("Fuente", origin_label(experiment.origin) if experiment.frames else "Sin cuadros"),
                ("Experimento", experiment.name),
                ("Tipo de dato", _data_kind(experiment.origin) if experiment.frames else "Registro sin temperaturas"),
                ("Fecha", experiment.session_date),
            ]
        )
    if not experiment.has_numeric_data:
        render_empty("Este ensayo no tiene temperaturas cuantitativas. Puedes inspeccionar la imagen, sin asignar grados Celsius.")
        _render_visuals(experiment)
        return
    _draw_numeric(experiment, compact=compact)


def _data_kind(origin: DataOrigin) -> str:
    if origin == DataOrigin.SIMULACION:
        return "Simulación, no es una medición"
    if origin == DataOrigin.IMPORTADO_CUANTITATIVO:
        return "Cuantitativo importado, no verificado con cámara"
    if origin == DataOrigin.MEDICION_RADIOMETRICA_VERIFICADA:
        return "Medición radiométrica verificada"
    if origin == DataOrigin.FLIR_PENDIENTE:
        return "Metadatos FLIR sin conversión verificada"
    if origin == DataOrigin.VISTA_FLIR_USB:
        return "Vista USB, temperatura aparente"
    return "Imagen visual"


def _render_visuals(experiment: Experiment) -> None:
    for frame in experiment.frames:
        if frame.preview_rgb is None:
            continue
        st.image(frame.preview_rgb, caption=frame.source_name, width="stretch")
        if frame.metadata:
            with st.expander(f"Metadatos de {frame.source_name}"):
                st.json(_public_metadata(frame.metadata))


def _public_metadata(metadata: dict) -> dict:
    visible = {}
    for key, value in metadata.items():
        if key == "metadatos" and isinstance(value, dict):
            visible[key] = {str(item_key): item_value for item_key, item_value in list(value.items())[:40]}
        else:
            visible[key] = value
    return visible
