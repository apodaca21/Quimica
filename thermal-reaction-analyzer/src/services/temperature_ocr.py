"""Lectura de temperaturas dibujadas por la FLIR sobre el video UVC.

Tesseract es opcional. Sin el binario, el parseo de texto y la validación siguen
disponibles; las lecturas de imagen quedan ausentes.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

import cv2
import numpy as np

from src.models.telemetry import (
    DEFAULT_OCR_REGIONS,
    SPOT_PANEL,
    OcrRegion,
    ReadingQuality,
    TemperatureReading,
    TemperatureSource,
)
from src.utils.limits import MAX_TEMPERATURE_C, MIN_TEMPERATURE_C

ROOT = Path(__file__).resolve().parents[2]
OCR_CONFIG_PATH = ROOT / "data" / "lab" / "ocr_regions.json"
TEMP_PATTERN = re.compile(
    r"([+-]?(?:\d{1,3}[.,]\d{1,2}|\d{1,3}))\s*(?:°\s*)?C?",
    re.IGNORECASE,
)
OVERLAY_WITH_C = re.compile(r"(\d{1,2}[.,]\d)\s*(?:°\s*)?C\b", re.IGNORECASE)
OVERLAY_DECIMAL = re.compile(r"(?<!\d)(\d{1,2}[.,]\d)(?!\d)")


_TESSERACT_CONFIGURED = False
_TESSERACT_CANDIDATES = (
    "/opt/homebrew/bin/tesseract",
    "/usr/local/bin/tesseract",
    "/usr/bin/tesseract",
)


def configure_tesseract() -> str | None:
    """Localiza el binario de Tesseract en macOS aunque PATH esté incompleto."""
    global _TESSERACT_CONFIGURED
    try:
        import pytesseract
    except ImportError:
        return None
    if _TESSERACT_CONFIGURED and Path(str(pytesseract.pytesseract.tesseract_cmd)).exists():
        return str(pytesseract.pytesseract.tesseract_cmd)
    found = shutil.which("tesseract")
    if not found:
        for candidate in _TESSERACT_CANDIDATES:
            if Path(candidate).exists():
                found = candidate
                break
    env = os.environ.get("TESSERACT_CMD")
    if env and Path(env).exists():
        found = env
    if not found:
        return None
    pytesseract.pytesseract.tesseract_cmd = found
    _TESSERACT_CONFIGURED = True
    return found


def tesseract_available() -> bool:
    if configure_tesseract() is None:
        return False
    try:
        from pytesseract import get_tesseract_version

        get_tesseract_version()
    except Exception:
        return False
    return True


def parse_overlay_temperatures(text: str) -> list[float]:
    """Lee las cifras del overlay FLIR (25.9 °C), no enteros sueltos ni la escala."""
    cleaned = (text or "").replace("\n", " ").replace("O", "0")
    dotted = cleaned.replace(",", ".")
    found: list[float] = []
    for match in OVERLAY_WITH_C.finditer(dotted):
        found.append(float(match.group(1).replace(",", ".")))
    if len(found) >= 3:
        return found[:3]
    for match in OVERLAY_DECIMAL.finditer(dotted):
        value = float(match.group(1).replace(",", "."))
        if 10.0 <= value <= 90.0 and value not in found:
            found.append(value)
    return found[:3]


def parse_temperature_text(text: str) -> tuple[float | None, str]:
    """Extrae el primer número compatible con una temperatura de overlay."""
    overlay = parse_overlay_temperatures(text)
    if overlay:
        return overlay[0], "ok"
    cleaned = (text or "").replace("\n", " ").replace("O", "0").replace("o", "0")
    cleaned = cleaned.replace(" ", "")
    match = TEMP_PATTERN.search(cleaned.replace(",", "."))
    if match is None:
        match = TEMP_PATTERN.search((text or "").replace("\n", " "))
        if match is None:
            return None, "sin número reconocible"
        raw = match.group(1).replace(",", ".")
    else:
        raw = match.group(1).replace(",", ".")
    try:
        value = float(raw)
    except ValueError:
        return None, "número no convertible"
    if value < 10 or abs(value - round(value)) < 1e-9:
        return None, "no parece una cifra del overlay FLIR"
    return value, "ok"


def validate_temperature(
    value: float | None,
    *,
    previous: float | None = None,
    min_c: float = MIN_TEMPERATURE_C,
    max_c: float = MAX_TEMPERATURE_C,
    max_jump_c: float = 12.0,
) -> tuple[bool, ReadingQuality, str]:
    if value is None:
        return False, ReadingQuality.AUSENTE, "lectura vacía"
    if not np.isfinite(value):
        return False, ReadingQuality.INVALIDA, "valor no finito"
    if value < min_c or value > max_c:
        return False, ReadingQuality.INVALIDA, f"fuera de intervalo ({min_c:g} a {max_c:g} °C)"
    if previous is not None and abs(value - previous) > max_jump_c:
        return False, ReadingQuality.SOSPECHOSA, f"salto de {value - previous:+.1f} °C respecto a la anterior"
    quality = ReadingQuality.ALTA
    if previous is not None and abs(value - previous) > max_jump_c * 0.5:
        quality = ReadingQuality.MEDIA
    return True, quality, "válida"


def preprocess_crop(bgr: np.ndarray) -> np.ndarray:
    if bgr.size == 0:
        return bgr
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY) if bgr.ndim == 3 else bgr
    scale = 4 if min(gray.shape[:2]) < 80 else 3
    big = cv2.resize(gray, (gray.shape[1] * scale, gray.shape[0] * scale), interpolation=cv2.INTER_CUBIC)
    big = cv2.GaussianBlur(big, (3, 3), 0)
    _, binary = cv2.threshold(big, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if float(np.mean(binary)) > 127:
        binary = cv2.bitwise_not(binary)
    return binary


def crop_region(frame_bgr: np.ndarray, region: OcrRegion) -> np.ndarray:
    alto, ancho = frame_bgr.shape[:2]
    x0, y0, x1, y1 = region.pixel_box(ancho, alto)
    return frame_bgr[y0:y1, x0:x1].copy()


def _run_tesseract(image: np.ndarray, psm: int = 7) -> str:
    import pytesseract

    config = f"--psm {psm} -c tessedit_char_whitelist=0123456789.,C"
    return pytesseract.image_to_string(image, config=config) or ""


def _ocr_value(bgr: np.ndarray, psm: int) -> tuple[float | None, str]:
    if bgr.size == 0:
        return None, ""
    try:
        raw = _run_tesseract(preprocess_crop(bgr), psm=psm)
    except Exception:
        return None, ""
    parsed = parse_overlay_temperatures(raw)
    return (parsed[0] if parsed else None), raw


def read_overlay_spots(frame_bgr: np.ndarray) -> tuple[list[float | None], str]:
    """Lee las tres temperaturas del panel izquierdo de la FLIR, en orden."""
    slots: list[float | None] = [None, None, None]
    if frame_bgr is None or frame_bgr.size == 0 or not tesseract_available():
        return slots, ""
    crop = crop_region(frame_bgr, SPOT_PANEL)
    texts: list[str] = []
    if crop.size:
        panel_value, raw = _ocr_value(crop, 6)
        if raw:
            texts.append(raw)
        panel_values = parse_overlay_temperatures(raw)
        for index, value in enumerate(panel_values[:3]):
            slots[index] = value
        alto, ancho = crop.shape[:2]
        row_h = max(10, alto // 3)
        for index in range(3):
            y0 = index * row_h
            y1 = alto if index == 2 else min(alto, (index + 1) * row_h)
            row = crop[y0:y1, int(ancho * 0.22) :]
            value, piece = _ocr_value(row, 7)
            if piece:
                texts.append(piece)
            if value is None:
                value, piece = _ocr_value(row, 8)
            if value is not None:
                slots[index] = value
    for index, region in enumerate(DEFAULT_OCR_REGIONS[:3]):
        if slots[index] is not None:
            continue
        value, piece = _ocr_value(crop_region(frame_bgr, region), 7)
        if piece:
            texts.append(piece)
        if value is not None:
            slots[index] = value
    return slots, " | ".join(part.strip() for part in texts if part.strip())


def read_region(
    frame_bgr: np.ndarray,
    region: OcrRegion,
    *,
    timestamp_s: float,
    previous_c: float | None = None,
    unix_time: float | None = None,
) -> TemperatureReading:
    crop = crop_region(frame_bgr, region)
    if crop.size == 0:
        return TemperatureReading(
            timestamp_s=timestamp_s,
            value_c=None,
            unit="°C",
            source=TemperatureSource.FLIR_OCR,
            measure_kind=region.measure_kind,
            quality=ReadingQuality.AUSENTE,
            region_id=region.id,
            raw_text="",
            valid=False,
            unix_time=unix_time,
            notes="recorte vacío",
        )
    if not tesseract_available():
        return TemperatureReading(
            timestamp_s=timestamp_s,
            value_c=None,
            unit="°C",
            source=TemperatureSource.FLIR_OCR,
            measure_kind=region.measure_kind,
            quality=ReadingQuality.AUSENTE,
            region_id=region.id,
            raw_text="",
            valid=False,
            unix_time=unix_time,
            notes="Tesseract no está disponible en este equipo",
        )
    prepared = preprocess_crop(crop)
    try:
        raw = _run_tesseract(prepared)
    except Exception as exc:  # pragma: no cover - motor externo
        return TemperatureReading(
            timestamp_s=timestamp_s,
            value_c=None,
            unit="°C",
            source=TemperatureSource.FLIR_OCR,
            measure_kind=region.measure_kind,
            quality=ReadingQuality.AUSENTE,
            region_id=region.id,
            raw_text="",
            valid=False,
            unix_time=unix_time,
            notes=f"OCR falló: {exc}",
        )
    value, parse_note = parse_temperature_text(raw)
    valid, quality, note = validate_temperature(value, previous=previous_c)
    return TemperatureReading(
        timestamp_s=timestamp_s,
        value_c=value if valid else (None if quality in {ReadingQuality.AUSENTE, ReadingQuality.INVALIDA} else value),
        unit="°C",
        source=TemperatureSource.FLIR_OCR,
        measure_kind=region.measure_kind,
        quality=quality,
        region_id=region.id,
        raw_text=raw.strip(),
        valid=valid,
        unix_time=unix_time,
        notes=f"{parse_note}; {note}",
    )


def load_ocr_regions(path: Path = OCR_CONFIG_PATH) -> list[OcrRegion]:
    if not path.exists():
        return [region.clamp() for region in DEFAULT_OCR_REGIONS]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [region.clamp() for region in DEFAULT_OCR_REGIONS]
    regions = [OcrRegion.from_dict(item).clamp() for item in data.get("regions", [])]
    return regions or [region.clamp() for region in DEFAULT_OCR_REGIONS]


def save_ocr_regions(regions: list[OcrRegion], path: Path = OCR_CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"regions": [region.clamp().as_dict() for region in regions]}
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


_OVERLAY_COLORS = {
    "principal": (0, 220, 255),
    "spot": (80, 170, 255),
    "minimo": (160, 220, 120),
    "maximo": (90, 90, 255),
    "otra": (200, 160, 255),
}


def overlay_regions(frame_bgr: np.ndarray, regions: list[OcrRegion], color: tuple[int, int, int] | None = None) -> np.ndarray:
    canvas = frame_bgr.copy()
    alto, ancho = canvas.shape[:2]
    for region in regions:
        if not region.enabled:
            continue
        x0, y0, x1, y1 = region.pixel_box(ancho, alto)
        tint = color or _OVERLAY_COLORS.get(region.measure_kind, (0, 220, 255))
        cv2.rectangle(canvas, (x0, y0), (x1, y1), tint, 1)
        label = region.label
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
        tx = min(ancho - tw - 4, x1 + 5)
        ty = min(alto - 4, max(th + 3, y0 + th))
        cv2.rectangle(canvas, (tx - 2, ty - th - 2), (tx + tw + 2, ty + 3), (12, 16, 28), -1)
        cv2.putText(canvas, label, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.42, tint, 1, cv2.LINE_AA)
    return canvas
