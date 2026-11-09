"""Pruebas del laboratorio térmico: OCR, telemetría, ROI, persistencia y reporte."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from src.models.telemetry import (
    OcrRegion,
    ReadingQuality,
    TemperatureReading,
    TemperatureSource,
    VisualRoi,
)
from src.services.alert_service import AlertConfig, evaluate_alerts
from src.services.baseline_analysis import compute_baseline
from src.services.camera_diagnostics import inspect_frame
from src.services.event_detection import detect_events
from src.services.experiment_comparison import aligned_series, comparison_table, sources_compatible
from src.services.experiment_storage import ExperimentRecord, load_experiment, new_record, save_experiment
from src.services.report_generator import build_report_pdf
from src.services.roi_tracker import RoiTracker
from src.services.telemetry_service import TelemetrySeries, approximate_rate
from src.services.temperature_ocr import parse_temperature_text, tesseract_available, validate_temperature
from src.services.visual_thermal_analysis import visual_delta, visual_stats


def _reading(t: float, value: float, valid: bool = True) -> TemperatureReading:
    return TemperatureReading(
        timestamp_s=t,
        value_c=value,
        unit="°C",
        source=TemperatureSource.FLIR_OCR,
        measure_kind="principal",
        quality=ReadingQuality.ALTA if valid else ReadingQuality.AUSENTE,
        valid=valid,
    )


def test_telemetria_vive_sin_ensayo(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.models.telemetry import OcrRegion, ReadingQuality
    from src.ui.lab_runtime import ingest_ocr

    def fake_read(frame, region, **kwargs):
        return TemperatureReading(
            timestamp_s=kwargs["timestamp_s"],
            value_c=25.2,
            unit="°C",
            source=TemperatureSource.FLIR_OCR,
            measure_kind=region.measure_kind,
            quality=ReadingQuality.ALTA,
            valid=True,
        )

    monkeypatch.setattr("src.ui.lab_runtime.read_overlay_spots", lambda _frame: ([], ""))
    monkeypatch.setattr("src.ui.lab_runtime.read_region", fake_read)
    session = {
        "ocr_enabled": True,
        "ocr_last_t": 0.0,
        "ocr_period_s": 0.1,
        "ocr_regions": [OcrRegion("spot_a", "A", 0.1, 0.1, 0.2, 0.1, "principal")],
        "live_readings": [],
        "lab_record": None,
    }
    produced = ingest_ocr(np.zeros((48, 64, 3), dtype=np.uint8), session, 1.0)
    assert produced and produced[0].value_c == pytest.approx(25.2)
    assert session["live_readings"]


def test_recortes_ocr_por_defecto_no_se_solapan() -> None:
    from src.models.telemetry import DEFAULT_OCR_REGIONS

    boxes = [(item.x, item.y, item.x + item.w, item.y + item.h) for item in DEFAULT_OCR_REGIONS if item.enabled]
    for index, first in enumerate(boxes):
        for second in boxes[index + 1 :]:
            overlap_x = min(first[2], second[2]) - max(first[0], second[0])
            overlap_y = min(first[3], second[3]) - max(first[1], second[1])
            assert overlap_x <= 0 or overlap_y <= 0


def test_parsea_los_tres_spots_del_overlay() -> None:
    from src.services.temperature_ocr import parse_overlay_temperatures

    values = parse_overlay_temperatures("25.9°C\n26.4°C\n23.7°C")
    assert values == [25.9, 26.4, 23.7]


def test_rechaza_basura_que_no_es_overlay_flir() -> None:
    from src.services.temperature_ocr import parse_overlay_temperatures, parse_temperature_text

    assert parse_overlay_temperatures("7.0 4.0") == []
    value, _ = parse_temperature_text("7.0")
    assert value is None


def test_parsea_decimales_con_coma_y_simbolo() -> None:
    value, _ = parse_temperature_text("21,5 °C")
    assert value == pytest.approx(21.5)
    value, _ = parse_temperature_text("35.8")
    assert value == pytest.approx(35.8)
    value, _ = parse_temperature_text("19.4°C")
    assert value == pytest.approx(19.4)


def test_rechaza_lectura_invalida_y_vacia() -> None:
    assert parse_temperature_text("FLIR")[0] is None
    valid, quality, _ = validate_temperature(None)
    assert valid is False and quality is ReadingQuality.AUSENTE
    valid, quality, _ = validate_temperature(900.0)
    assert valid is False and quality is ReadingQuality.INVALIDA


def test_salto_brusco_no_se_acepta_como_valido() -> None:
    valid, quality, _ = validate_temperature(40.0, previous=20.0, max_jump_c=8.0)
    assert valid is False
    assert quality is ReadingQuality.SOSPECHOSA


def test_ocr_ausente_se_reporta_sin_inventar_temperatura(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.services.temperature_ocr as ocr

    monkeypatch.setattr(ocr, "tesseract_available", lambda: False)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    region = OcrRegion("p", "p", 0.1, 0.1, 0.2, 0.1)
    reading = ocr.read_region(frame, region, timestamp_s=0.0)
    assert reading.valid is False
    assert reading.value_c is None
    assert reading.quality is ReadingQuality.AUSENTE


@pytest.mark.skipif(not tesseract_available(), reason="Tesseract no instalado")
def test_ocr_lee_un_numero_sintetico() -> None:
    from PIL import Image, ImageDraw, ImageFont

    from src.services.temperature_ocr import read_region

    image = Image.new("RGB", (640, 480), (10, 10, 10))
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 42)
    except OSError:
        font = ImageFont.load_default()
    draw.rectangle((20, 180, 180, 260), fill=(0, 0, 0))
    draw.text((28, 195), "24.8 C", fill=(255, 255, 255), font=font)
    frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    region = OcrRegion("p", "p", 0.03, 0.37, 0.28, 0.18, "principal")
    reading = read_region(frame, region, timestamp_s=1.0)
    assert reading.valid is True
    assert reading.value_c == pytest.approx(24.8, abs=0.2)


def test_linea_base_requiere_lecturas_validas() -> None:
    early = compute_baseline([_reading(i, 24.0) for i in range(3)], min_count=5)
    assert early.ready is False
    ready = compute_baseline([_reading(i * 0.5, 24.0 + 0.05 * (i % 2)) for i in range(8)], min_count=5)
    assert ready.ready is True
    assert ready.reference_c == pytest.approx(24.0, abs=0.1)


def test_delta_t_usa_referencia_y_no_el_color() -> None:
    series = TelemetrySeries(readings=[_reading(0, 24.0), _reading(5, 31.2)])
    metrics = series.metrics(reference_c=24.0)
    assert metrics.delta_c == pytest.approx(7.2)
    assert metrics.current_c == pytest.approx(31.2)


def test_tasa_con_intervalos_irregulares() -> None:
    assert approximate_rate(26.0, 24.0, 3.5, 1.0) == pytest.approx(0.8)


def test_detecta_inicio_de_calentamiento() -> None:
    readings = [_reading(i, 24.0 + 0.4 * i) for i in range(6)]
    events = detect_events(readings, heat_threshold_c=0.8)
    assert any(item.kind == "inicio_calentamiento" for item in events)


def test_detecta_pico_termico() -> None:
    values = [24.0, 26.0, 29.0, 31.0, 28.5, 26.5]
    readings = [_reading(float(i), value) for i, value in enumerate(values)]
    events = detect_events(readings, heat_threshold_c=0.8)
    assert any(item.kind == "pico_termico" for item in events)


def test_detecta_estabilizacion() -> None:
    readings = [_reading(float(i), 24.05 + 0.01 * (i % 2)) for i in range(12)]
    events = detect_events(readings, heat_threshold_c=5.0, stable_std_c=0.2, window=5)
    assert any(item.kind == "estabilizacion" for item in events)


def test_roi_queda_dentro_de_limites() -> None:
    roi = VisualRoi(x=0.95, y=0.95, w=0.4, h=0.4).clamp()
    assert roi.x + roi.w <= 1.0001
    assert roi.y + roi.h <= 1.0001


def test_seguimiento_perdido_no_mueve_en_silencio() -> None:
    tracker = RoiTracker(VisualRoi(0.2, 0.2, 0.2, 0.2))
    patterned = np.zeros((120, 160, 3), dtype=np.uint8)
    patterned[24:48, 32:64] = (0, 255, 255)
    patterned[30:40, 40:50] = (255, 0, 0)
    tracker.enable_tracking(patterned)
    other = np.full((120, 160, 3), 40, dtype=np.uint8)
    state = tracker.update(other)
    assert state.lost is True
    assert state.tracking is False


def test_comparacion_alinea_al_evento_de_mezcla() -> None:
    a = new_record("A")
    a.mix_time_s = 5.0
    a.readings = [_reading(4.0, 24.0), _reading(6.0, 27.0)]
    b = new_record("B")
    b.mix_time_s = 10.0
    b.readings = [_reading(9.0, 25.0), _reading(11.0, 26.0)]
    aligned_a = aligned_series(a)
    aligned_b = aligned_series(b)
    assert aligned_a[0][0] == pytest.approx(-1.0)
    assert aligned_b[0][0] == pytest.approx(-1.0)
    table = comparison_table([a, b])
    assert len(table) == 2
    assert sources_compatible([a, b]) is True


def test_el_ensayo_guarda_el_nombre_de_la_reaccion() -> None:
    from src.ui.lab_runtime import start_lab_experiment

    session = {
        "experiment_name": "Prueba_1",
        "reaction_name": "Neutralización de HCl con NaOH",
        "live_protocol": "otra_reaccion",
        "lab_reagents": "NaOH + HCl",
        "lab_concentration": "1 M",
        "lab_group": "Equipo 3",
        "lab_operator": "Ana",
        "lab_trial": 2,
        "lab_objective": "Registrar el aumento de temperatura superficial.",
    }
    record = start_lab_experiment(session)
    assert record.reaction_name == "Neutralización de HCl con NaOH"
    assert record.reagents == "NaOH + HCl"
    assert record.trial_n == 2
    assert record.group_name == "Equipo 3"


def test_persistencia_de_sesiones(tmp_path: Path) -> None:
    db = tmp_path / "lab.sqlite"
    record = new_record("NaOH_1", protocol="disolucion_agua", reagents="NaOH + agua")
    record.readings.append(_reading(1.0, 24.8))
    save_experiment(record, db)
    loaded = load_experiment(record.id, db)
    assert loaded is not None
    assert loaded.name == "NaOH_1"
    assert loaded.readings[0].value_c == pytest.approx(24.8)


def test_exportacion_y_reporte_pdf() -> None:
    record = new_record("PDF")
    record.readings = [_reading(0, 24.0), _reading(10, 28.0)]
    record.reference_c = 24.0
    pdf = build_report_pdf(record)
    assert pdf.startswith(b"%PDF")


def test_diagnostico_no_afirma_radiometria() -> None:
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    info = inspect_frame(frame)
    assert info.radiometric_confirmed is False
    assert info.is_16bit is False


def test_visual_no_se_convierte_a_celsius() -> None:
    dark = np.zeros((80, 80, 3), dtype=np.uint8)
    bright = np.full((80, 80, 3), 200, dtype=np.uint8)
    roi = VisualRoi(0, 0, 1, 1)
    delta = visual_delta(visual_stats(bright, roi), visual_stats(dark, roi))
    assert delta > 0
    assert "No se convierte" in " ".join(visual_stats(bright, roi).notes)


def test_desconexion_camara_no_inventa_cuadros() -> None:
    from src.services.flir_camera import ErrorDeCamara, FlirLiveSession

    session = FlirLiveSession()
    with pytest.raises(ErrorDeCamara):
        session.read()


def test_reproduccion_de_video_sin_hardware(tmp_path: Path) -> None:
    from src.services.flir_camera import FlirLiveSession

    clip = tmp_path / "clip.avi"
    writer = cv2.VideoWriter(str(clip), cv2.VideoWriter_fourcc(*"MJPG"), 5.0, (64, 48))
    assert writer.isOpened()
    for index in range(4):
        writer.write(np.full((48, 64, 3), 20 + index * 10, dtype=np.uint8))
    writer.release()
    session = FlirLiveSession()
    etiqueta = session.start_from_file(clip)
    assert "Reproducción" in etiqueta
    vista, original, _contraste = session.read()
    assert original.shape[1] == 64
    assert vista.size > 0
    session.stop()
    assert session.activa is False


def test_tabla_comparativa_exportable() -> None:
    from src.services.experiment_comparison import comparison_csv

    a = new_record("A")
    a.readings = [_reading(0, 24.0), _reading(5, 27.0)]
    b = new_record("B")
    b.readings = [_reading(0, 23.0), _reading(4, 23.5)]
    csv_text = comparison_csv(comparison_table([a, b]))
    assert "ensayo,fuente" in csv_text
    assert "A" in csv_text and "B" in csv_text


def test_alertas_tienen_histéresis() -> None:
    from src.services.telemetry_service import TelemetryMetrics

    metrics = TelemetryMetrics(
        current_c=70.0,
        initial_c=24.0,
        max_c=70.0,
        min_c=24.0,
        delta_c=46.0,
        rate_c_per_s=0.1,
        elapsed_s=10.0,
        time_to_max_s=10.0,
        time_since_mix_s=None,
        mean_c=40.0,
        stable=False,
        valid_count=8,
        source_label="flir_ocr",
    )
    first = evaluate_alerts(metrics, 0, [], 10.0, AlertConfig(max_temp_c=60.0, cooldown_s=12.0))
    second = evaluate_alerts(metrics, 0, first, 11.0, AlertConfig(max_temp_c=60.0, cooldown_s=12.0))
    assert first and not second
