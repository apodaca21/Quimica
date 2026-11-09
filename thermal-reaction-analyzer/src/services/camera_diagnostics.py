"""Diagnóstico de la captura FLIR USB. No afirma radiometría no verificada."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import cv2
import numpy as np


def fourcc_to_str(value: float | int) -> str:
    code = int(value)
    if code <= 0:
        return ""
    chars = "".join(chr((code >> (8 * i)) & 0xFF) for i in range(4))
    return "".join(ch if 32 <= ord(ch) < 127 else "?" for ch in chars)


@dataclass
class CaptureDiagnostics:
    connected: bool
    width: int = 0
    height: int = 0
    channels: int = 0
    dtype: str = ""
    fourcc: str = ""
    backend: str = ""
    convert_rgb: float | None = None
    is_16bit: bool = False
    radiometric_confirmed: bool = False
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def inspect_frame(frame: np.ndarray | None, captura: cv2.VideoCapture | None = None) -> CaptureDiagnostics:
    """Describe lo que OpenCV entrega. No declara Y16 ni radiometría."""
    if frame is None or frame.size == 0:
        return CaptureDiagnostics(
            connected=False,
            notes=("No hay cuadro para inspeccionar.",),
        )
    channels = 1 if frame.ndim == 2 else int(frame.shape[2])
    is_16bit = str(frame.dtype) in {"uint16", "int16"}
    fourcc = ""
    convert_rgb = None
    backend = ""
    if captura is not None:
        fourcc = fourcc_to_str(captura.get(cv2.CAP_PROP_FOURCC))
        convert_rgb = float(captura.get(cv2.CAP_PROP_CONVERT_RGB))
        backend = captura.getBackendName() if hasattr(captura, "getBackendName") else ""
    notes = [
        f"OpenCV entrega un arreglo {frame.shape} dtype={frame.dtype}.",
        "En macOS + AVFoundation el flujo UVC suele llegar como BGR de 8 bits.",
        "640 × 480 es la resolución del video compuesto, no necesariamente la del sensor IR.",
    ]
    if is_16bit:
        notes.append(
            "El arreglo es de 16 bits, pero eso no confirma un formato radiométrico Y16 calibrado."
        )
    else:
        notes.append("No se observó un buffer de 16 bits en este cuadro.")
    notes.append("La conversión radiométrica por píxel permanece no verificada.")
    return CaptureDiagnostics(
        connected=True,
        width=int(frame.shape[1]),
        height=int(frame.shape[0]),
        channels=channels,
        dtype=str(frame.dtype),
        fourcc=fourcc,
        backend=backend,
        convert_rgb=convert_rgb,
        is_16bit=is_16bit,
        radiometric_confirmed=False,
        notes=tuple(notes),
    )
