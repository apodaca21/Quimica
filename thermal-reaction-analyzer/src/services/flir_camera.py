"""Apertura y lectura de la cámara USB FLIR (no la webcam del Mac)."""

from __future__ import annotations

import json
import subprocess
import threading
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

INDICES = (0, 1, 2)
TIEMPO_APERTURA_MS = 5000
TIEMPO_LECTURA_MS = 3000
FALLOS_MAX = 30
ROOT = Path(__file__).resolve().parents[2]
CAPTURAS_ROOT = ROOT / "data" / "captures"


class ErrorDeCamara(RuntimeError):
    """La cámara no pudo abrirse o no entregó imágenes."""


def crear_sesion_capturas(base: Path = CAPTURAS_ROOT) -> Path:
    """Crea la carpeta de esta sesión y un aviso legible."""
    base.mkdir(parents=True, exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    sesion = base / f"sesion_{marca}"
    sesion.mkdir(parents=True, exist_ok=False)
    (sesion / "LEEME.txt").write_text(
        "Capturas de la sesión de la FLIR USB.\n"
        "El contraste visual no representa grados Celsius.\n"
        "archivos *_original.jpg = imagen de la cámara\n"
        "archivos *_contraste.jpg = misma imagen con mapa de color\n"
        "archivos *_vista.jpg = lo que se veía al capturar\n",
        encoding="utf-8",
    )
    return sesion


def guardar_captura(
    sesion: Path,
    frame_original: np.ndarray,
    frame_contraste: np.ndarray,
    vista: np.ndarray,
    con_contraste: bool,
) -> Path:
    """Guarda la captura actual en la carpeta de la sesión. Devuelve la ruta de la vista."""
    marca = datetime.now().strftime("%H%M%S_%f")[:-3]
    modo = "con_contraste" if con_contraste else "sin_contraste"
    original = sesion / f"captura_{marca}_{modo}_original.jpg"
    contraste = sesion / f"captura_{marca}_{modo}_contraste.jpg"
    vista_path = sesion / f"captura_{marca}_{modo}_vista.jpg"
    cv2.imwrite(str(original), frame_original)
    cv2.imwrite(str(contraste), frame_contraste)
    cv2.imwrite(str(vista_path), vista)
    return vista_path


def nombres_de_camaras() -> list[dict[str, str]]:
    try:
        salida = subprocess.check_output(
            ["system_profiler", "SPCameraDataType", "-json"],
            text=True,
            timeout=20,
        )
        datos = json.loads(salida)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        raise ErrorDeCamara(
            "No se pudo consultar la lista de cámaras de macOS. "
            f"Detalle: {exc}"
        ) from exc
    camaras = datos.get("SPCameraDataType", [])
    if not isinstance(camaras, list):
        return []
    resultado = []
    for camara in camaras:
        if not isinstance(camara, dict):
            continue
        resultado.append(
            {
                "nombre": str(camara.get("_name", "Cámara sin nombre")),
                "modelo": str(camara.get("spcamera_model-id", "")),
            }
        )
    return resultado


def es_flir(nombre: str, modelo: str) -> bool:
    texto = f"{nombre} {modelo}".lower()
    return "flir" in texto or "vendorid_2507" in texto or "productid_4107" in texto


def es_resolucion_de_mac(ancho: int, alto: int) -> bool:
    return ancho >= 1280 or alto >= 1280


def abrir_indice(indice: int) -> tuple[cv2.VideoCapture, tuple[int, ...]]:
    captura = cv2.VideoCapture()
    captura.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, TIEMPO_APERTURA_MS)
    captura.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, TIEMPO_LECTURA_MS)
    try:
        abierta = captura.open(indice, cv2.CAP_AVFOUNDATION)
    except cv2.error as exc:
        captura.release()
        raise ErrorDeCamara(
            f"OpenCV rechazó el índice {indice}. Detalle: {exc}"
        ) from exc
    if not abierta or not captura.isOpened():
        captura.release()
        raise ErrorDeCamara(f"El índice {indice} no se abrió.")
    captura.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    for _ in range(20):
        correcto, frame = captura.read()
        if correcto and frame is not None and frame.size > 0:
            return captura, tuple(int(valor) for valor in frame.shape)
    captura.release()
    raise ErrorDeCamara(
        f"El índice {indice} se abrió, pero no entregó ninguna imagen. "
        "Revisa que la FLIR esté encendida y no en reposo."
    )


def buscar_camara_externa() -> tuple[cv2.VideoCapture, int, str]:
    camaras = nombres_de_camaras()
    ancho_flir, alto_flir = 640, 480
    informes: list[str] = []
    elegida: tuple[int, str] | None = None

    for indice in INDICES:
        try:
            captura, forma = abrir_indice(indice)
        except ErrorDeCamara as exc:
            informes.append(str(exc))
            continue
        alto, ancho = int(forma[0]), int(forma[1])
        informes.append(f"Índice {indice}: {ancho} × {alto} px.")
        captura.release()
        if es_resolucion_de_mac(ancho, alto):
            informes.append(f"Índice {indice} descartado: cámara del Mac.")
            continue
        if ancho == ancho_flir and alto == alto_flir:
            etiqueta = f"FLIR USB, {ancho} × {alto} px"
            if indice < len(camaras) and es_flir(camaras[indice]["nombre"], camaras[indice]["modelo"]):
                etiqueta = f"FLIR Systems, {ancho} × {alto} px"
            elegida = (indice, etiqueta)
            break

    if elegida is None:
        raise ErrorDeCamara(
            "No apareció la FLIR de 640 × 480 en los índices 0, 1 y 2.\n" + "\n".join(informes)
        )

    indice, etiqueta = elegida
    captura, forma = abrir_indice(indice)
    alto, ancho = int(forma[0]), int(forma[1])
    if es_resolucion_de_mac(ancho, alto) or (ancho, alto) != (ancho_flir, alto_flir):
        captura.release()
        raise ErrorDeCamara(
            f"El índice {indice} entregó {ancho} × {alto}. Cancelado para no abrir la cámara del Mac."
        )
    return captura, indice, etiqueta


def aplicar_contraste(frame: np.ndarray) -> np.ndarray:
    gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.applyColorMap(gris, cv2.COLORMAP_INFERNO)


class FlirLiveSession:
    """Mantiene abierta la FLIR para la vista embebida en Streamlit."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._captura: cv2.VideoCapture | None = None
        self._writer: cv2.VideoWriter | None = None
        self._record_size: tuple[int, int] = (640, 480)
        self.indice: int | None = None
        self.etiqueta: str = ""
        self.sesion: Path | None = None
        self.fallos = 0
        self.source_kind: str = "camera"
        self.record_path: Path | None = None

    @property
    def activa(self) -> bool:
        return self._captura is not None and self._captura.isOpened()

    @property
    def capture(self) -> cv2.VideoCapture | None:
        return self._captura

    @property
    def recording(self) -> bool:
        return self._writer is not None

    def start(self) -> str:
        with self._lock:
            if self.activa and self.source_kind == "camera":
                return self.etiqueta
            self._release_unlocked()
            captura, indice, etiqueta = buscar_camara_externa()
            self._captura = captura
            self.indice = indice
            self.etiqueta = etiqueta
            self.source_kind = "camera"
            self.sesion = crear_sesion_capturas()
            self.fallos = 0
            return etiqueta

    def start_from_file(self, path: str | Path) -> str:
        """Reproduce un video grabado. No es la FLIR en vivo."""
        archivo = Path(path)
        with self._lock:
            self._release_unlocked()
            captura = cv2.VideoCapture(str(archivo))
            if not captura.isOpened():
                raise ErrorDeCamara(f"No se pudo abrir el video {archivo.name}.")
            correcto, frame = captura.read()
            if not correcto or frame is None or frame.size == 0:
                captura.release()
                raise ErrorDeCamara(f"El video {archivo.name} no entregó ningún cuadro.")
            captura.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self._captura = captura
            self.indice = None
            self.source_kind = "video"
            self.etiqueta = f"Reproducción {archivo.name} (no es la FLIR en vivo)"
            self.sesion = crear_sesion_capturas()
            self.fallos = 0
            return self.etiqueta

    def start_recording(self) -> Path:
        with self._lock:
            if self._captura is None:
                raise ErrorDeCamara("No hay video para grabar.")
            if self._writer is not None and self.record_path is not None:
                return self.record_path
            if self.sesion is None:
                self.sesion = crear_sesion_capturas()
            ancho = int(self._captura.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
            alto = int(self._captura.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
            ruta = self.sesion / f"video_{datetime.now().strftime('%H%M%S')}.avi"
            writer = cv2.VideoWriter(str(ruta), cv2.VideoWriter_fourcc(*"MJPG"), 8.0, (ancho, alto))
            if not writer.isOpened():
                raise ErrorDeCamara("No se pudo crear el archivo de grabación.")
            self._writer = writer
            self._record_size = (ancho, alto)
            self.record_path = ruta
            return ruta

    def stop_recording(self) -> Path | None:
        with self._lock:
            return self._stop_recording_unlocked()

    def stop(self) -> None:
        with self._lock:
            self._release_unlocked()

    def _stop_recording_unlocked(self) -> Path | None:
        ruta = self.record_path
        if self._writer is not None:
            self._writer.release()
        self._writer = None
        return ruta

    def _release_unlocked(self) -> None:
        self._stop_recording_unlocked()
        if self._captura is not None:
            self._captura.release()
        self._captura = None
        self.indice = None
        self.etiqueta = ""
        self.fallos = 0
        self.source_kind = "camera"
        self.record_path = None

    def read(self, con_contraste: bool = False) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Devuelve (vista BGR, original BGR, contraste BGR)."""
        with self._lock:
            if self._captura is None:
                raise ErrorDeCamara("La vista en vivo no está iniciada.")
            correcto, frame = self._captura.read()
            if (not correcto or frame is None or frame.size == 0) and self.source_kind == "video":
                self._captura.set(cv2.CAP_PROP_POS_FRAMES, 0)
                correcto, frame = self._captura.read()
            if not correcto or frame is None or frame.size == 0:
                self.fallos += 1
                if self.fallos >= FALLOS_MAX:
                    self._captura.release()
                    self._captura = None
                    raise ErrorDeCamara(
                        "La FLIR dejó de enviar cuadros. Revisa el cable USB y que esté encendida."
                    )
                raise ErrorDeCamara("Cuadro vacío; reintentando…")
            self.fallos = 0
            original = frame.copy()
            if self._writer is not None:
                salida = original
                ancho, alto = self._record_size
                if (original.shape[1], original.shape[0]) != (ancho, alto):
                    salida = cv2.resize(original, (ancho, alto))
                self._writer.write(salida)
            contraste = aplicar_contraste(original)
            vista = contraste if con_contraste else original.copy()
            return vista, original, contraste

    def capturar(self, con_contraste: bool) -> Path:
        vista, original, contraste = self.read(con_contraste=con_contraste)
        if self.sesion is None:
            self.sesion = crear_sesion_capturas()
        return guardar_captura(self.sesion, original, contraste, vista, con_contraste)


_SESSION: FlirLiveSession | None = None


def get_live_session() -> FlirLiveSession:
    global _SESSION
    if _SESSION is None:
        _SESSION = FlirLiveSession()
    return _SESSION
