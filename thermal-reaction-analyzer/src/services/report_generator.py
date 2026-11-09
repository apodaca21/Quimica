"""Reporte PDF del ensayo. No afirma una reacción exacta."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from src.services.experiment_storage import ExperimentRecord
from src.services.naoh_catalog import predict_naoh_family
from src.services.telemetry_service import TelemetrySeries


def _safe(text: str) -> str:
    return (
        (text or "")
        .replace("—", "-")
        .replace("–", "-")
        .replace("°", " deg")
        .replace("σ", "sigma")
        .replace("Δ", "d")
        .encode("latin-1", "replace")
        .decode("latin-1")
    )


def build_report_pdf(record: ExperimentRecord) -> bytes:
    try:
        from fpdf import FPDF
    except ImportError as exc:
        raise RuntimeError("Falta fpdf2 para generar el PDF.") from exc

    series = TelemetrySeries(readings=list(record.readings))
    metrics = series.metrics(record.reference_c, record.mix_time_s)
    category = "estable"
    if metrics.delta_c is not None and metrics.delta_c >= 0.8:
        category = "exotermico_posible"
    elif metrics.delta_c is not None and metrics.delta_c <= -0.8:
        category = "endotermico_posible"
    prediction, confidence, evidence = predict_naoh_family(
        category,
        None,
        metrics.delta_c or 0.0,
        metrics.min_c,
    )
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_x(10)
    pdf.multi_cell(190, 8, _safe("THERMAL LAB - reporte de ensayo"))
    pdf.set_font("Helvetica", size=11)
    lines = [
        f"Nombre del ensayo: {record.name}",
        f"Reaccion: {record.reaction_name or record.process_type or 'no registrada'}",
        f"Fecha: {record.created_at}    Duracion: {metrics.elapsed_s:.1f} s    Prueba n. {record.trial_n}",
        f"Grupo: {record.group_name or 'n/d'}    Registra: {record.operator or 'n/d'}",
        f"Objetivo: {record.objective or 'Seguimiento termico superficial.'}",
        f"Materiales: {record.reagents or record.protocol or 'no registrados'}",
        f"Concentracion: {record.concentration or 'no registrada'}",
        "Equipo: FLIR USB UVC 640x480. Fuente: overlay OCR o entrada manual.",
        "No se uso una matriz radiometrica verificada.",
        (
            f"Condiciones: ambiente {record.ambient_c} C, recipiente {record.vessel or 'n/d'}, "
            f"emisividad {record.emissivity or 'n/d'}, distancia {record.distance_m or 'n/d'} m."
        ),
        (
            f"T inicial {metrics.initial_c} C | T actual {metrics.current_c} C | "
            f"T max {metrics.max_c} C | dT {metrics.delta_c} C"
        ),
        "Eventos:",
    ]
    if not record.events:
        lines.append("- sin eventos registrados")
    for event in record.events:
        lines.append(f"- t={event.timestamp_s:.1f}s  {event.kind}  {event.condition}")
    lines.append(f"Interpretacion orientativa ({confidence}): {prediction}")
    lines.extend(f"- {item}" for item in evidence[:4])
    lines.append(
        "Limitaciones: el video USB no es C calibrados por pixel. "
        "La curva no identifica una reaccion exacta ni calcula entalpia."
    )
    lines.append(f"Observaciones: {record.observations or 'ninguna.'}")
    for line in lines:
        pdf.set_x(10)
        pdf.multi_cell(190, 6, _safe(line))
    buffer = BytesIO()
    pdf.output(buffer)
    return bytes(buffer.getvalue())


def write_report(record: ExperimentRecord, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(build_report_pdf(record))
    return path
