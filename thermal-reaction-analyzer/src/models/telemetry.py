"""Lecturas, eventos y procedencia térmica verificable."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class TemperatureSource(str, Enum):
    """Origen de un valor de temperatura."""

    FLIR_OCR = "flir_ocr"
    FLIR_MANUAL = "flir_manual"
    RADIOMETRIC = "radiometric"
    VISUAL_RELATIVE = "visual_relative"


SOURCE_LABELS = {
    TemperatureSource.FLIR_OCR: "Temperatura FLIR (OCR del overlay)",
    TemperatureSource.FLIR_MANUAL: "Temperatura FLIR (entrada manual)",
    TemperatureSource.RADIOMETRIC: "Temperatura radiométrica verificada",
    TemperatureSource.VISUAL_RELATIVE: "Información visual relativa (no °C)",
}


class ReadingQuality(str, Enum):
    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"
    AUSENTE = "ausente"
    INVALIDA = "invalida"
    SOSPECHOSA = "sospechosa"


@dataclass
class TemperatureReading:
    timestamp_s: float
    value_c: float | None
    unit: str
    source: TemperatureSource
    measure_kind: str
    quality: ReadingQuality
    instrument: str = "FLIR USB UVC"
    region_id: str | None = None
    raw_text: str = ""
    valid: bool = False
    unix_time: float | None = None
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source"] = self.source.value
        payload["quality"] = self.quality.value
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TemperatureReading:
        return cls(
            timestamp_s=float(data["timestamp_s"]),
            value_c=None if data.get("value_c") is None else float(data["value_c"]),
            unit=str(data.get("unit") or "°C"),
            source=TemperatureSource(data.get("source", "flir_manual")),
            measure_kind=str(data.get("measure_kind") or "principal"),
            quality=ReadingQuality(data.get("quality", "invalida")),
            instrument=str(data.get("instrument") or "FLIR USB UVC"),
            region_id=data.get("region_id"),
            raw_text=str(data.get("raw_text") or ""),
            valid=bool(data.get("valid")),
            unix_time=data.get("unix_time"),
            notes=str(data.get("notes") or ""),
        )


@dataclass
class ThermalEvent:
    timestamp_s: float
    kind: str
    value_c: float | None = None
    condition: str = ""
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ThermalEvent:
        return cls(
            timestamp_s=float(data["timestamp_s"]),
            kind=str(data["kind"]),
            value_c=None if data.get("value_c") is None else float(data["value_c"]),
            condition=str(data.get("condition") or ""),
            notes=str(data.get("notes") or ""),
        )


@dataclass
class OcrRegion:
    """Recorte normalizado (0–1) sobre el video 640×480."""

    id: str
    label: str
    x: float
    y: float
    w: float
    h: float
    measure_kind: str = "principal"
    enabled: bool = True

    def clamp(self) -> OcrRegion:
        x = min(max(self.x, 0.0), 0.98)
        y = min(max(self.y, 0.0), 0.98)
        w = min(max(self.w, 0.02), 1.0 - x)
        h = min(max(self.h, 0.02), 1.0 - y)
        return OcrRegion(self.id, self.label, x, y, w, h, self.measure_kind, self.enabled)

    def pixel_box(self, width: int, height: int) -> tuple[int, int, int, int]:
        region = self.clamp()
        x0 = int(region.x * width)
        y0 = int(region.y * height)
        x1 = min(width, x0 + max(2, int(region.w * width)))
        y1 = min(height, y0 + max(2, int(region.h * height)))
        return x0, y0, x1, y1

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OcrRegion:
        return cls(
            id=str(data["id"]),
            label=str(data.get("label") or data["id"]),
            x=float(data["x"]),
            y=float(data["y"]),
            w=float(data["w"]),
            h=float(data["h"]),
            measure_kind=str(data.get("measure_kind") or "principal"),
            enabled=bool(data.get("enabled", True)),
        )


# Panel izquierdo de la FLIR USB 640×480: tres spots con °C, no la escala de color.
SPOT_PANEL = OcrRegion("panel", "Spots FLIR", 0.02, 0.012, 0.36, 0.30, "otra")
DEFAULT_OCR_REGIONS = (
    OcrRegion("spot_a", "Spot 1", 0.11, 0.020, 0.24, 0.085, "spot"),
    OcrRegion("spot_b", "Spot 2", 0.11, 0.108, 0.24, 0.085, "principal"),
    OcrRegion("spot_c", "Spot 3", 0.11, 0.196, 0.24, 0.090, "spot"),
)
OCR_LAYOUT_VERSION = 4


@dataclass
class VisualRoi:
    x: float = 0.30
    y: float = 0.30
    w: float = 0.35
    h: float = 0.35

    def clamp(self) -> VisualRoi:
        x = min(max(self.x, 0.0), 0.95)
        y = min(max(self.y, 0.0), 0.95)
        w = min(max(self.w, 0.04), 1.0 - x)
        h = min(max(self.h, 0.04), 1.0 - y)
        return VisualRoi(x, y, w, h)
