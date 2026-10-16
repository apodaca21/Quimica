"""Exportación de resultados en CSV, JSON y HTML."""

from __future__ import annotations

import json
from html import escape
from typing import Any

import pandas as pd
import plotly.graph_objects as go

from src.models.experiment import Experiment
from src.models.thermal_frame import origin_label
from src.services.thermal_analysis import TABLE_COLUMNS, AnalysisResult

UNITS = {
    "temperatura": "°C",
    "tiempo": "s",
    "tasa": "°C/s",
    "delta_T": "°C",
}


def series_csv(experiment: Experiment, result: AnalysisResult) -> bytes:
    lines = [
        f"# nombre: {experiment.name}",
        f"# origen: {experiment.origin.value}",
        "# temperatura_unidad: °C",
        "# tiempo_unidad: s",
        "# tasa_unidad: °C/s",
        "# aviso: los datos conservan el origen declarado y no implican entalpía",
    ]
    table = result.table.loc[:, TABLE_COLUMNS]
    payload = "\n".join(lines) + "\n" + table.to_csv(index=False)
    return payload.encode("utf-8-sig")


def series_json(experiment: Experiment, result: AnalysisResult) -> bytes:
    rows = json.loads(result.table.to_json(orient="records", double_precision=6))
    document: dict[str, Any] = {
        "id": experiment.id,
        "nombre": experiment.name,
        "descripcion": experiment.description,
        "fecha": experiment.session_date,
        "tipo_de_ensayo": experiment.assay_type,
        "reactivos": experiment.reagents,
        "temperatura_ambiente_C": experiment.ambient_temperature_c,
        "observaciones": experiment.observations,
        "origen": experiment.origin.value,
        "origen_etiqueta": origin_label(experiment.origin),
        "medicion_radiometrica_verificada": experiment.origin.value == "medicion_radiometrica_verificada",
        "unidades": UNITS,
        "linea_base_C": result.baseline_c,
        "cuadros_linea_base": result.baseline_frames,
        "delta_T_serie_C": result.delta_t_c,
        "tendencia": result.trend,
        "explicacion": result.explanation,
        "advertencias": result.warnings,
        "parametros": experiment.parameters,
        "filas": rows,
    }
    return json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8")


def figures_html(figures: list[go.Figure], title: str) -> bytes:
    sections = [
        "<!DOCTYPE html>",
        "<html lang='es'><head><meta charset='utf-8'>",
        f"<title>{escape(title)}</title>",
        "<style>body{background:#0b1020;color:#e8eef9;font-family:sans-serif;margin:24px;}</style>",
        "</head><body>",
        f"<h1>{escape(title)}</h1>",
        "<p>Gráficas interactivas exportadas desde el Analizador térmico. "
        "El origen de los datos está en el archivo JSON del mismo experimento.</p>",
    ]
    for figure in figures:
        sections.append(figure.to_html(full_html=False, include_plotlyjs="cdn"))
    sections.append("</body></html>")
    return "\n".join(sections).encode("utf-8")


def read_series_csv(payload: bytes) -> pd.DataFrame:
    text = payload.decode("utf-8-sig")
    from io import StringIO

    return pd.read_csv(StringIO(text), comment="#")
