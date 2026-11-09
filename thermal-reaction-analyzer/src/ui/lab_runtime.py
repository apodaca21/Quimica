"""Estado de laboratorio en session_state, sin hilos de captura."""

from __future__ import annotations

import time
from dataclasses import replace
from datetime import datetime

from src.models.telemetry import (
    DEFAULT_OCR_REGIONS,
    OCR_LAYOUT_VERSION,
    OcrRegion,
    ReadingQuality,
    TemperatureReading,
    TemperatureSource,
    VisualRoi,
)
from src.services.experiment_storage import ExperimentRecord, new_record
from src.services.naoh_catalog import PROTOCOLS
from src.services.temperature_ocr import load_ocr_regions, read_overlay_spots, read_region
from src.services.telemetry_service import TelemetrySeries

LAB_DEFAULTS = {
    "lab_stage": "preparacion",
    "lab_record": None,
    "ocr_enabled": True,
    "ocr_last_t": 0.0,
    "ocr_period_s": 0.7,
    "missing_streak": 0,
    "presentation_mode": False,
    "show_contours": False,
    "show_ocr_boxes": False,
    "show_roi": False,
    "overlay_layout_version": 0,
    "visual_roi": VisualRoi(0.32, 0.32, 0.32, 0.32),
    "background_roi": None,
    "frozen_frame": None,
    "ocr_preview_id": "spot_b",
    "ocr_layout_version": 0,
    "manual_temp": 24.8,
    "allow_no_baseline": False,
    "mix_marked": False,
    "lab_tab": "Experimento",
    "lab_mass": 0.0,
    "lab_vol": 0.0,
    "lab_amb": 24.0,
    "lab_vessel": "",
    "lab_notes": "",
    "lab_emis": 0.95,
    "lab_dist": 0.4,
    "use_background_roi": False,
    "live_readings": [],
    "live_t0_mono": None,
    "live_spots": [],
    "reaction_name": "",
    "lab_reagents": "",
    "lab_concentration": "",
    "lab_group": "",
    "lab_operator": "",
    "lab_trial": 1,
    "lab_objective": "",
}


def ensure_lab_state(session: dict) -> None:
    for key, value in LAB_DEFAULTS.items():
        if key not in session:
            session[key] = value
    if session.get("ocr_layout_version") != OCR_LAYOUT_VERSION:
        session["ocr_regions"] = [region.clamp() for region in DEFAULT_OCR_REGIONS]
        session["ocr_layout_version"] = OCR_LAYOUT_VERSION
        session["ocr_preview_id"] = "spot_b"
        session["live_readings"] = []
        session["live_spots"] = []
        session["live_t0_mono"] = None
        for region_id in ("principal", "spot_a", "spot_b", "spot_c", "panel"):
            for prefix in ("ox_", "oy_", "ow_", "oh_", "ok_", "oe_"):
                session.pop(f"{prefix}{region_id}", None)
    elif "ocr_regions" not in session:
        session["ocr_regions"] = load_ocr_regions()
    if session.get("overlay_layout_version") != 3:
        session["show_ocr_boxes"] = False
        session["show_roi"] = False
        session["show_contours"] = False
        session["overlay_layout_version"] = 3


def current_record(session: dict) -> ExperimentRecord | None:
    record = session.get("lab_record")
    return record if isinstance(record, ExperimentRecord) else None


def start_lab_experiment(session: dict) -> ExperimentRecord:
    reaction = str(session.get("reaction_name") or "").strip()
    key = str(session.get("live_protocol") or "otra_reaccion")
    protocol = PROTOCOLS.get(key, PROTOCOLS["otra_reaccion"])
    if not reaction:
        reaction = protocol["label"]
    name = str(session.get("experiment_name") or "").strip() or reaction or f"Ensayo_{datetime.now().strftime('%H%M')}"
    reagents = str(session.get("lab_reagents") or "").strip() or protocol["reagents"]
    record = new_record(name, protocol=key, reagents=reagents)
    record.reaction_name = reaction
    record.process_type = str(session.get("reaction_name") or protocol["assay"]).strip() or protocol["assay"]
    record.objective = str(session.get("lab_objective") or "").strip() or "Seguimiento térmico superficial de un ensayo de laboratorio."
    record.concentration = str(session.get("lab_concentration") or "").strip()
    record.group_name = str(session.get("lab_group") or "").strip()
    record.operator = str(session.get("lab_operator") or "").strip()
    record.trial_n = int(session.get("lab_trial") or 1)
    record.temperature_source = "flir_ocr"
    record.status = "baseline"
    record.started_unix = time.time()
    record.config = {"protocolo": key, "reaccion": reaction}
    session["lab_record"] = record
    session["lab_t0_mono"] = time.monotonic()
    session["lab_stage"] = "baseline"
    session["mix_marked"] = False
    session["missing_streak"] = 0
    session["ocr_last_t"] = 0.0
    return record


def _store_reading(session: dict, record, now_mono: float, reading: TemperatureReading) -> None:
    live: list[TemperatureReading] = session.setdefault("live_readings", [])
    live.append(reading)
    if (
        record is not None
        and record.started_unix is not None
        and session.get("lab_stage") in {"baseline", "observacion"}
    ):
        exp_t0 = float(session.get("lab_t0_mono") or now_mono)
        record.readings.append(replace(reading, timestamp_s=max(0.0, now_mono - exp_t0)))
    if len(live) > 600:
        session["live_readings"] = live[-400:]


def ingest_ocr(frame_bgr, session: dict, now_mono: float) -> list[TemperatureReading]:
    if not session.get("ocr_enabled", True):
        return []
    period = float(session.get("ocr_period_s") or 0.7)
    last = float(session.get("ocr_last_t") or 0.0)
    if now_mono - last < period:
        return []
    session["ocr_last_t"] = now_mono
    if session.get("live_t0_mono") is None:
        session["live_t0_mono"] = now_mono
    live_t0 = float(session["live_t0_mono"])
    live_ts = max(0.0, now_mono - live_t0)
    record = current_record(session)
    spots, raw = read_overlay_spots(frame_bgr)
    produced: list[TemperatureReading] = []
    if any(value is not None for value in spots):
        previous = list(session.get("live_spots") or [None, None, None])
        while len(previous) < 3:
            previous.append(None)
        padded = list(spots) + [None, None, None]
        for index in range(3):
            if padded[index] is None:
                padded[index] = previous[index]
        session["live_spots"] = padded[:3]
        kinds = ["spot", "principal", "spot"]
        ids = ["spot_a", "spot_b", "spot_c"]
        for index, value in enumerate(padded[:3]):
            if value is None:
                continue
            reading = TemperatureReading(
                timestamp_s=live_ts,
                value_c=value,
                unit="°C",
                source=TemperatureSource.FLIR_OCR,
                measure_kind=kinds[index],
                quality=ReadingQuality.ALTA,
                valid=True,
                region_id=ids[index],
                raw_text=raw,
                unix_time=time.time(),
                notes="overlay FLIR",
            )
            _store_reading(session, record, now_mono, reading)
            produced.append(reading)
        session["missing_streak"] = 0
        return produced

    session["live_spots"] = []
    series = TelemetrySeries(readings=list(session.get("live_readings") or []))
    previous = series.last_valid_value()
    got_valid = False
    regions: list[OcrRegion] = session.get("ocr_regions") or []
    for region in regions:
        if not region.enabled:
            continue
        reading = read_region(
            frame_bgr,
            region,
            timestamp_s=live_ts,
            previous_c=previous if region.measure_kind == "principal" else None,
            unix_time=time.time(),
        )
        _store_reading(session, record, now_mono, reading)
        produced.append(reading)
        if reading.valid and reading.measure_kind == "principal":
            got_valid = True
            previous = reading.value_c
    if got_valid:
        session["missing_streak"] = 0
        session["live_spots"] = [
            item.value_c
            for item in produced
            if item.valid and item.value_c is not None
        ][:3]
    else:
        session["missing_streak"] = int(session.get("missing_streak") or 0) + 1
    return produced


def register_manual(session: dict, value_c: float) -> TemperatureReading:
    from src.models.telemetry import ReadingQuality

    record = current_record(session)
    if record is None or record.started_unix is None:
        raise RuntimeError("No hay ensayo activo.")
    t0 = float(session.get("lab_t0_mono") or time.monotonic())
    timestamp = max(0.0, time.monotonic() - t0)
    reading = TemperatureReading(
        timestamp_s=timestamp,
        value_c=float(value_c),
        unit="°C",
        source=TemperatureSource.FLIR_MANUAL,
        measure_kind="principal",
        quality=ReadingQuality.MEDIA,
        valid=True,
        unix_time=time.time(),
        notes="entrada manual de respaldo",
    )
    record.readings.append(reading)
    session["missing_streak"] = 0
    return reading
