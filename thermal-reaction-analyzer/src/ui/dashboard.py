"""THERMAL LAB: cámara, telemetría OCR y flujo experimental."""

from __future__ import annotations

import time
from datetime import timedelta
from html import escape

import plotly.graph_objects as go
import streamlit as st

from src.models.telemetry import OcrRegion
from src.services.alert_service import evaluate_alerts
from src.services.baseline_analysis import compute_baseline
from src.services.camera_diagnostics import inspect_frame
from src.services.event_detection import detect_events
from src.services.experiment_comparison import aligned_series, comparison_csv, comparison_table, sources_compatible
from src.services.experiment_storage import list_experiments, load_experiment, save_experiment
from src.services.flir_camera import get_live_session
from src.services.naoh_catalog import protocol_keys, protocol_label
from src.services.report_generator import build_report_pdf
from src.services.temperature_ocr import (
    crop_region,
    read_region,
    save_ocr_regions,
    tesseract_available,
)
from src.services.telemetry_service import TelemetrySeries
from src.ui.capture_page import (
    capture_live_still,
    init_live_state,
    render_gallery_compact,
    render_live_stream,
    start_live_camera,
    start_playback_file,
    stop_live_camera,
    toggle_recording,
)
from src.ui.components import metric_card
from src.ui.lab_runtime import current_record, ensure_lab_state, register_manual, start_lab_experiment
from src.ui.state import init_state


def _ensure_camera_preview() -> None:
    init_live_state()
    if st.session_state.flir_live or st.session_state.flir_autostart_done:
        return
    st.session_state.flir_autostart_done = True
    start_live_camera()


_STAGE_LABELS = {
    "preparacion": ("En espera", "wait"),
    "baseline": ("Línea base", "run"),
    "observacion": ("En observación", "run"),
    "cerrado": ("Guardado", "wait"),
}
_IDLE_METRICS = (
    ("Spot 1", "—", "°C"),
    ("Spot 2", "—", "°C"),
    ("Spot 3", "—", "°C"),
    ("ΔT", "—", "°C"),
    ("Máx", "—", "°C"),
    ("Tiempo", "—", "s"),
)


def _header() -> None:
    live = bool(st.session_state.flir_live)
    record = current_record(st.session_state)
    stage = str(st.session_state.get("lab_stage") or "preparacion")
    exp_label, exp_klass = _STAGE_LABELS.get(stage, ("En espera", "wait"))
    if record is None:
        exp_label, exp_klass = "En espera", "wait"
    cam_klass = "on" if live else "off"
    cam_label = "FLIR conectada" if live else "FLIR desconectada"
    left, mid, right = st.columns([2.1, 2.8, 1.1])
    with left:
        st.markdown(
            "<p class='app-title'>THERMAL LAB</p>"
            "<p class='app-kicker'>Laboratorio de análisis térmico</p>",
            unsafe_allow_html=True,
        )
    with mid:
        st.markdown(
            "<div class='status-row'>"
            f"<span class='status-pill {cam_klass}'><i></i>{cam_label}</span>"
            f"<span class='status-pill {exp_klass}'><i></i>{exp_label}</span>"
            "</div>",
            unsafe_allow_html=True,
        )
    with right:
        st.toggle("Presentación", key="presentation_mode", help="Amplía cámara y métricas para la demostración.")


def _metric_grid(values: list[tuple[str, str, str]] | tuple[tuple[str, str, str], ...]) -> None:
    items = list(values)
    for start in (0, 3):
        row = items[start : start + 3]
        if not row:
            continue
        cols = st.columns(3, gap="small")
        for column, (label, value, unit) in zip(cols, row):
            column.markdown(
                metric_card(label, value, unit, compact=True),
                unsafe_allow_html=True,
            )


def _camera_bar() -> None:
    live = bool(st.session_state.flir_live)
    locked = st.session_state.lab_stage in {"baseline", "observacion"}
    st.text_input("Nombre del ensayo", key="experiment_name", disabled=locked)
    a, b, c, d = st.columns([1.35, 1.05, 1, 1.15])
    a.button("Tomar fotografía", type="primary", width="stretch", disabled=not live, on_click=capture_live_still, key="lab_photo")
    grabar = "Detener grabación" if st.session_state.get("flir_recording") else "Grabar"
    b.button(grabar, width="stretch", disabled=not live, on_click=toggle_recording, key="lab_record_btn")
    if live:
        c.button("Detener cámara", width="stretch", on_click=stop_live_camera, key="lab_stop")
    elif c.button("Reconectar", width="stretch", key="lab_reconnect"):
        st.session_state.flir_autostart_done = False
        start_live_camera()
    d.toggle("Contraste visual", key="flir_contrast", disabled=not live, help="Solo visual. No son °C.")


def _chart(readings, reference_c=None, mix_time_s=None, events=()) -> None:
    series = TelemetrySeries(readings=list(readings))
    valid = series.valid()
    fig = go.Figure()
    if valid:
        fig.add_trace(
            go.Scatter(
                x=[item.timestamp_s for item in valid],
                y=[item.value_c for item in valid],
                mode="lines+markers",
                name="T FLIR",
                line=dict(color="#67E8F9", width=2),
            )
        )
    if reference_c is not None:
        fig.add_hline(y=reference_c, line_dash="dot", line_color="#A78BFA", annotation_text="línea base")
    if mix_time_s is not None:
        fig.add_vline(x=mix_time_s, line_color="#FB7185", line_width=2, annotation_text="mezcla")
    for event in events:
        if event.kind.startswith("alerta"):
            continue
        fig.add_vline(x=event.timestamp_s, line_dash="dash", line_color="#F8FAFC", opacity=0.35)
    fig.update_layout(
        template="plotly_dark",
        height=220 if st.session_state.presentation_mode else 260,
        margin=dict(l=40, r=10, t=24, b=36),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(12,18,32,0.45)",
        title="Temperatura FLIR frente al tiempo",
        xaxis_title="t (s)",
        yaxis_title="°C",
        showlegend=False,
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def _telemetry_from_readings(readings, reference_c=None, mix_time_s=None) -> None:
    series = TelemetrySeries(readings=list(readings))
    valid = series.valid()
    if reference_c is None and valid:
        reference_c = valid[0].value_c
    metrics = series.metrics(reference_c, mix_time_s)
    spots = list(st.session_state.get("live_spots") or [])
    while len(spots) < 3:
        spots.append(None)
    def _fmt(value: float | None) -> str:
        return "—" if value is None else f"{value:.1f}"

    values = [
        ("Spot 1", _fmt(spots[0]), "°C"),
        ("Spot 2", _fmt(spots[1] if spots[1] is not None else metrics.current_c), "°C"),
        ("Spot 3", _fmt(spots[2]), "°C"),
        ("ΔT", None if metrics.delta_c is None else f"{metrics.delta_c:+.1f}", "°C"),
        ("Máx", None if metrics.max_c is None else f"{metrics.max_c:.1f}", "°C"),
        ("Tiempo", f"{metrics.elapsed_s:.0f}", "s"),
    ]
    _metric_grid(
        [
            (label, "—" if value is None else value, unit)
            for label, value, unit in values
        ]
    )
    if spots[0] is not None:
        st.caption("Valores leídos del overlay de la FLIR (los mismos de la cámara).")
    elif metrics.valid_count:
        st.caption(f"{metrics.valid_count} lecturas de la FLIR")
    else:
        st.caption("Leyendo las temperaturas que muestra la cámara…")


def _mark_mix() -> None:
    record = current_record(st.session_state)
    if record is None or record.started_unix is None:
        return
    t0 = float(st.session_state.get("lab_t0_mono") or time.monotonic())
    record.mix_time_s = max(0.0, time.monotonic() - t0)
    baseline = compute_baseline(record.readings)
    if baseline.reference_c is not None:
        record.reference_c = baseline.reference_c
    elif st.session_state.get("allow_no_baseline"):
        series = TelemetrySeries(readings=list(record.readings))
        record.reference_c = series.last_valid_value()
    record.status = "observacion"
    st.session_state.lab_stage = "observacion"
    st.session_state.mix_marked = True


def _finish() -> None:
    record = current_record(st.session_state)
    if record is None:
        return
    _fill_record_fields(record)
    record.status = "cerrado"
    st.session_state.lab_stage = "cerrado"
    save_experiment(record)


def _fill_record_fields(record) -> None:
    record.mass_g = st.session_state.get("lab_mass") or None
    record.volume_ml = st.session_state.get("lab_vol") or None
    record.ambient_c = st.session_state.get("lab_amb")
    record.vessel = st.session_state.get("lab_vessel") or ""
    record.observations = st.session_state.get("lab_notes") or ""
    record.emissivity = st.session_state.get("lab_emis") or None
    record.distance_m = st.session_state.get("lab_dist") or None
    record.reaction_name = str(st.session_state.get("reaction_name") or record.reaction_name)
    record.reagents = str(st.session_state.get("lab_reagents") or record.reagents)
    record.concentration = str(st.session_state.get("lab_concentration") or "")
    record.group_name = str(st.session_state.get("lab_group") or "")
    record.operator = str(st.session_state.get("lab_operator") or "")
    record.trial_n = int(st.session_state.get("lab_trial") or 1)
    record.objective = str(st.session_state.get("lab_objective") or record.objective)


def _experiment_tab() -> None:
    locked = st.session_state.lab_stage in {"baseline", "observacion"}
    st.markdown("**Reacción y registro de la prueba**")
    st.text_input(
        "Nombre de la reacción",
        key="reaction_name",
        disabled=locked,
        placeholder="Ej. Disolución de NaOH, neutralización con HCl, control con agua…",
    )
    st.selectbox(
        "Tipo de ensayo",
        protocol_keys(),
        format_func=protocol_label,
        key="live_protocol",
        disabled=locked,
        help="Puedes elegir un protocolo sugerido o 'Otra reacción' y escribir el nombre arriba.",
    )
    extras = st.columns(3)
    extras[0].text_input("Sustancias o reactivos", key="lab_reagents", disabled=locked, placeholder="NaOH, H2O, HCl…")
    extras[1].text_input("Concentración", key="lab_concentration", disabled=locked, placeholder="1 M, 0.5 M…")
    extras[2].number_input("N.º de prueba", min_value=1, step=1, key="lab_trial", disabled=locked)
    extras = st.columns(3)
    extras[0].text_input("Equipo o grupo", key="lab_group", disabled=locked)
    extras[1].text_input("Quien registra", key="lab_operator", disabled=locked)
    extras[2].text_input("Recipiente", key="lab_vessel", disabled=locked)
    st.text_input("Objetivo del ensayo", key="lab_objective", disabled=locked, placeholder="Observar el cambio de temperatura superficial al mezclar…")
    extras = st.columns(2)
    extras[0].number_input("Masa (g)", min_value=0.0, step=0.1, key="lab_mass", disabled=locked)
    extras[1].number_input("Volumen (mL)", min_value=0.0, step=0.5, key="lab_vol", disabled=locked)
    extras = st.columns(2)
    extras[0].number_input("T ambiente (°C)", step=0.5, key="lab_amb", disabled=locked)
    extras[1].number_input("Emisividad (si se conoce)", min_value=0.0, max_value=1.0, step=0.01, key="lab_emis", disabled=locked)
    extras = st.columns(2)
    extras[0].number_input("Distancia a la cámara (m)", min_value=0.0, step=0.05, key="lab_dist", disabled=locked)
    extras[1].checkbox("Permitir análisis sin línea base", key="allow_no_baseline", disabled=locked)
    row = st.columns(3)
    if row[0].button("Iniciar línea base", type="primary", width="stretch", disabled=locked, key="lab_start"):
        record = start_lab_experiment(st.session_state)
        _fill_record_fields(record)
    row[1].button("Marcar mezcla", width="stretch", disabled=st.session_state.lab_stage != "baseline", on_click=_mark_mix, key="lab_mix")
    row[2].button("Finalizar y guardar", width="stretch", disabled=current_record(st.session_state) is None, on_click=_finish, key="lab_end")
    st.caption("No hay instrucciones automáticas de mezclado. Sigue el protocolo aprobado por la profesora.")
    st.number_input("Respaldo manual T FLIR (°C)", step=0.1, key="manual_temp")
    if st.button("Registrar T manual", width="stretch", disabled=current_record(st.session_state) is None, key="lab_manual"):
        try:
            register_manual(st.session_state, float(st.session_state.manual_temp))
        except RuntimeError as exc:
            st.error(str(exc))


def _analysis_tab(record) -> None:
    if record is None:
        st.caption("Inicia un ensayo para ver el análisis.")
        return
    series = TelemetrySeries(readings=list(record.readings))
    metrics = series.metrics(record.reference_c, record.mix_time_s)
    from src.models.experiment import Experiment
    from src.models.thermal_frame import DataOrigin
    from src.services.naoh_catalog import predict_naoh_family

    category = "estable"
    if metrics.delta_c is not None and metrics.delta_c >= 0.8:
        category = "exotermico_posible"
    elif metrics.delta_c is not None and metrics.delta_c <= -0.8:
        category = "endotermico_posible"
    dummy = Experiment(name=record.name, origin=DataOrigin.IMAGEN_VISUAL, reagents=record.reagents, parameters={"protocolo": record.protocol})
    prediction, confidence, evidence = predict_naoh_family(category, dummy, metrics.delta_c, metrics.min_c)
    st.markdown(
        f"<div class='predict-card'><div class='label'>Interpretación térmica</div>"
        f"<div class='value'>{escape(prediction)}</div>"
        f"<p>Confianza: {escape(confidence)}. No identifica una reacción exacta ni calcula entalpía.</p></div>",
        unsafe_allow_html=True,
    )
    for item in evidence[:4]:
        st.caption(item)
    st.write("Eventos")
    if not record.events:
        st.caption("Sin eventos todavía.")
    for event in record.events[-8:]:
        st.caption(f"t={event.timestamp_s:.1f}s · {event.kind} · {event.condition}")


def _compare_tab() -> None:
    rows = list_experiments()
    if len(rows) < 1:
        st.caption("Guarda al menos un ensayo para comparar.")
        return
    labels = {f"{name} · {created}": eid for eid, name, created, _status in rows}
    chosen = st.multiselect("Ensayos", list(labels), default=list(labels)[:2])
    records = [load_experiment(labels[item]) for item in chosen]
    records = [item for item in records if item is not None]
    if len(records) < 2:
        st.caption("Elige dos o más.")
        return
    if not sources_compatible(records):
        st.warning("Las fuentes de temperatura no son iguales. La comparación es solo orientativa.")
    table = comparison_table(records)
    st.dataframe(
        [
            {
                "ensayo": row.name,
                "fuente": row.source,
                "T0": row.initial_c,
                "dT max": row.max_delta_c,
                "t pico s": row.time_to_peak_s,
                "duración s": row.duration_s,
                "mezcla": row.mix_marked,
            }
            for row in table
        ],
        width="stretch",
        hide_index=True,
    )
    st.download_button(
        "Tabla comparativa CSV",
        data=comparison_csv(table).encode("utf-8"),
        file_name="comparacion_ensayos.csv",
        mime="text/csv",
        width="stretch",
    )
    fig = go.Figure()
    colors = ["#67E8F9", "#A78BFA", "#FB7185", "#F59E0B"]
    for index, record in enumerate(records):
        points = aligned_series(record)
        if not points:
            continue
        fig.add_trace(
            go.Scatter(
                x=[p[0] for p in points],
                y=[p[1] for p in points],
                name=record.name,
                line=dict(color=colors[index % len(colors)]),
            )
        )
    fig.update_layout(
        template="plotly_dark",
        height=280,
        paper_bgcolor="rgba(0,0,0,0)",
        title="Curvas alineadas al evento de mezcla (t=0)",
        xaxis_title="t - t_mezcla (s)",
        yaxis_title="°C",
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def _config_tab() -> None:
    st.caption("Calibración OCR: congela un cuadro, ajusta el recorte y comprueba el texto.")
    st.write("Tesseract:", "disponible" if tesseract_available() else "no instalado — usa T manual")
    regions: list[OcrRegion] = st.session_state.ocr_regions
    names = [item.id for item in regions]
    chosen = st.selectbox("Región", names, key="ocr_preview_id")
    region = next(item for item in regions if item.id == chosen)
    c1, c2 = st.columns(2)
    region.x = c1.slider("x", 0.0, 0.95, region.x, 0.005, key=f"ox_{region.id}")
    region.y = c2.slider("y", 0.0, 0.95, region.y, 0.005, key=f"oy_{region.id}")
    region.w = c1.slider("ancho", 0.04, 0.6, region.w, 0.005, key=f"ow_{region.id}")
    region.h = c2.slider("alto", 0.04, 0.4, region.h, 0.005, key=f"oh_{region.id}")
    region.measure_kind = st.selectbox(
        "Esta cifra es",
        ["principal", "spot", "minimo", "maximo", "otra"],
        index=["principal", "spot", "minimo", "maximo", "otra"].index(region.measure_kind)
        if region.measure_kind in {"principal", "spot", "minimo", "maximo", "otra"}
        else 0,
        key=f"ok_{region.id}",
    )
    region.enabled = st.checkbox("Activa", value=region.enabled, key=f"oe_{region.id}")
    freeze, live_btn = st.columns(2)
    if freeze.button("Congelar cuadro", key="freeze_ocr"):
        preview = st.session_state.get("last_preview_bgr")
        st.session_state.frozen_frame = None if preview is None else preview.copy()
    if live_btn.button("Usar cuadro en vivo", key="unfreeze_ocr"):
        st.session_state.frozen_frame = None
    frame = st.session_state.get("frozen_frame")
    if frame is None:
        frame = st.session_state.get("last_preview_bgr")
    if frame is not None:
        crop = crop_region(frame, region)
        st.image(crop[:, :, ::-1], caption="Recorte ampliado", width="stretch")
        reading = read_region(frame, region, timestamp_s=0.0)
        st.write(f"OCR ve: `{reading.raw_text or '—'}` → {reading.value_c} °C ({reading.quality.value})")
        st.caption(reading.notes)
    if st.button("Guardar recortes OCR", key="save_ocr"):
        save_ocr_regions(regions)
        st.success("Coordenadas guardadas en data/lab/ocr_regions.json")
    st.divider()
    diag = inspect_frame(frame, get_live_session().capture if st.session_state.flir_live else None)
    st.write(diag.as_dict())
    for note in diag.notes:
        st.caption(note)
    st.number_input("Periodo OCR (s)", min_value=0.4, max_value=3.0, step=0.1, key="ocr_period_s")
    st.caption("Reproducción sin cámara: sube un AVI/MP4 grabado. Queda identificado como video, no como FLIR en vivo.")
    uploaded = st.file_uploader("Video de prueba", type=["mp4", "avi", "mov", "mkv"], key="lab_video")
    if uploaded is not None and st.button("Reproducir video", key="lab_play_video"):
        from src.services.experiment_storage import LAB_DIR

        LAB_DIR.mkdir(parents=True, exist_ok=True)
        dest = LAB_DIR / uploaded.name
        dest.write_bytes(uploaded.getvalue())
        start_playback_file(dest)


def _exports(record) -> None:
    if record is None or not record.readings:
        return
    c1, c2 = st.columns(2)
    try:
        pdf = build_report_pdf(record)
    except RuntimeError as exc:
        c1.caption(str(exc))
    else:
        c1.download_button("Reporte PDF", data=pdf, file_name=f"{record.name}_reporte.pdf", mime="application/pdf", width="stretch")
    import json

    c2.download_button(
        "JSON",
        data=json.dumps(record.as_dict(), ensure_ascii=False, indent=2).encode("utf-8"),
        file_name=f"{record.name}_ensayo.json",
        mime="application/json",
        width="stretch",
    )


def render_dashboard() -> None:
    init_state()
    ensure_lab_state(st.session_state)
    _ensure_camera_preview()
    _header()
    _camera_bar()
    record = current_record(st.session_state)
    if record is not None and st.session_state.lab_stage in {"baseline", "observacion"}:
        record.events = detect_events(record.readings, record.events, mix_time_s=record.mix_time_s)
        series = TelemetrySeries(readings=list(record.readings))
        metrics = series.metrics(record.reference_c, record.mix_time_s)
        extra = evaluate_alerts(metrics, int(st.session_state.missing_streak), record.events, time.monotonic())
        if extra:
            record.events.extend(extra)
            if any(item.kind.startswith("alerta") for item in extra) and st.session_state.flir_live:
                capture_live_still()

    present = bool(st.session_state.presentation_mode)
    camera, telemetry = st.columns([1.75, 1] if present else [1.45, 1], gap="small")
    with camera:
        render_live_stream(show_status=False)
    with telemetry:
        live = bool(st.session_state.flir_live)
        refresh = timedelta(milliseconds=700) if live else None

        @st.fragment(run_every=refresh)
        def _live_panel() -> None:
            current = current_record(st.session_state)
            if current is not None and current.readings:
                readings = current.readings
                reference = current.reference_c
                mix = current.mix_time_s
                events = current.events
            else:
                readings = list(st.session_state.get("live_readings") or [])
                reference = None
                mix = None
                events = ()
            if not readings:
                _metric_grid(_IDLE_METRICS)
                st.markdown(
                    "<div class='ready-card'><strong>Cámara en vivo</strong>"
                    "<p>Las tarjetas se llenan con las temperaturas que muestra la FLIR. "
                    "Si aún aparecen guiones, espera un par de segundos o confirma el recorte en Configuración.</p></div>",
                    unsafe_allow_html=True,
                )
                return
            _telemetry_from_readings(readings, reference, mix)
            _chart(readings, reference, mix, events)
            if current is None:
                st.caption("Vista previa de la cámara. Inicia el ensayo para guardar esta curva.")
            elif st.session_state.lab_stage == "baseline":
                baseline = compute_baseline(current.readings)
                st.info(
                    " ".join(baseline.notes)
                    if not baseline.ready
                    else f"Línea base lista: {baseline.reference_c:.2f} °C"
                )

        _live_panel()
        if record is not None:
            _exports(record)
        st.markdown("<p class='notes-title'>Notas del ensayo</p>", unsafe_allow_html=True)
        st.text_area(
            "Notas del ensayo",
            key="lab_notes",
            height=160,
            label_visibility="collapsed",
            placeholder="Escribe aquí observaciones, color, burbujeo, momento de mezcla u otros detalles del ensayo.",
        )
        active = current_record(st.session_state)
        if active is not None:
            active.observations = str(st.session_state.get("lab_notes") or "")
            if st.session_state.lab_stage == "preparacion":
                name = str(st.session_state.get("experiment_name") or "").strip()
                if name:
                    active.name = name

    if present:
        st.caption("Modo presentación: cámara, curva y notas ampliadas.")
        return
    experimento, analisis, comparaciones, galeria, config = st.tabs(
        ["Experimento", "Análisis", "Comparaciones", "Capturas", "Configuración"]
    )
    with experimento:
        _experiment_tab()
    with analisis:
        _analysis_tab(record)
    with comparaciones:
        _compare_tab()
    with galeria:
        render_gallery_compact()
    with config:
        _config_tab()
