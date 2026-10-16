"""Adaptador FLIR aislado.

ExifTool es opcional. Este módulo puede inspeccionar metadatos y mostrar la
fotografía, pero no convierte un JPEG a grados Celsius.

La fórmula de Planck citada por ExifTool y Thermimage,

    T = B / ln(R1 / (R2 * (raw + O)) + F) - 273.15

no se aplica. Encontrar constantes de Planck no acredita una temperatura:
faltan verificar, con un JPEG original de la FLIR C5, el formato de los datos,
el orden de bytes, la conversión y los límites de calibración.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from src.utils.validation import ValidationError

# Permanece en False hasta validar un JPEG original de la FLIR C5 del laboratorio.
RADIOMETRIC_CONVERSION_VERIFIED = False

PLANCK_TAGS = ("PlanckR1", "PlanckB", "PlanckF", "PlanckO", "PlanckR2")
RAW_TAGS = ("RawThermalImageWidth", "RawThermalImageHeight", "RawThermalImageType")

PENDING_MESSAGE = (
    "Se detectaron metadatos compatibles con un JPEG radiométrico FLIR, "
    "pero la conversión a temperatura no está verificada con una fotografía original "
    "de la FLIR C5. No se calculan temperaturas."
)
VISUAL_MESSAGE = (
    "El archivo no contiene una matriz radiométrica verificada. "
    "Se muestra la imagen y no se asignan temperaturas."
)
NO_EXIFTOOL_MESSAGE = (
    "ExifTool no está instalado. La imagen puede verse, "
    "pero no se examinarán metadatos radiométricos."
)


@dataclass
class FlirInspection:
    path: str
    exiftool_available: bool
    metadata: dict[str, Any] = field(default_factory=dict)
    has_planck_constants: bool = False
    has_raw_thermal_metadata: bool = False
    radiometric_valid: bool = False
    temperature_matrix: None = None
    message: str = VISUAL_MESSAGE
    error: str | None = None


def exiftool_executable() -> str | None:
    return shutil.which("exiftool")


def _tag_present(metadata: dict[str, Any], tag: str) -> bool:
    return any(str(key).endswith(tag) and value not in (None, "") for key, value in metadata.items())


def read_exiftool_metadata(path: Path) -> dict[str, Any]:
    executable = exiftool_executable()
    if executable is None:
        raise ValidationError(NO_EXIFTOOL_MESSAGE)
    try:
        completed = subprocess.run(
            [executable, "-j", "-n", str(path)],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValidationError(f"No se pudieron leer los metadatos con ExifTool: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "ExifTool no pudo leer el archivo."
        raise ValidationError(detail)
    try:
        payload = json.loads(completed.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise ValidationError("ExifTool devolvió metadatos que no se pudieron interpretar.") from exc
    if not payload:
        return {}
    first = payload[0]
    if not isinstance(first, dict):
        raise ValidationError("El formato de metadatos de ExifTool no es el esperado.")
    return {str(key): value for key, value in first.items() if not str(key).startswith("RawThermalImage")}


def inspect_jpeg(path: Path) -> FlirInspection:
    """Inspecciona un JPEG sin producir temperaturas."""
    if not path.is_file():
        raise ValidationError("No se encontró el archivo de imagen.")
    try:
        with Image.open(path) as image:
            image.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValidationError("El archivo de imagen está dañado o no es un formato compatible.") from exc

    inspection = FlirInspection(path=str(path), exiftool_available=exiftool_executable() is not None)
    inspection.radiometric_valid = False
    inspection.temperature_matrix = None
    if not RADIOMETRIC_CONVERSION_VERIFIED:
        inspection.radiometric_valid = False

    if not inspection.exiftool_available:
        inspection.message = NO_EXIFTOOL_MESSAGE
        inspection.error = NO_EXIFTOOL_MESSAGE
        return inspection

    try:
        inspection.metadata = read_exiftool_metadata(path)
    except ValidationError as exc:
        inspection.error = str(exc)
        inspection.message = f"{VISUAL_MESSAGE} {exc}"
        return inspection

    inspection.has_planck_constants = all(_tag_present(inspection.metadata, tag) for tag in PLANCK_TAGS)
    inspection.has_raw_thermal_metadata = any(_tag_present(inspection.metadata, tag) for tag in RAW_TAGS)
    if inspection.has_planck_constants or inspection.has_raw_thermal_metadata:
        inspection.message = PENDING_MESSAGE
    else:
        inspection.message = VISUAL_MESSAGE
    return inspection
