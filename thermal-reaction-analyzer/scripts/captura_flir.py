"""Vista en vivo de la cámara USB FLIR conectada a la Mac.

Abre solo la FLIR (640 × 480), no la webcam del Mac.
El contraste visual no son grados Celsius.

Controles en la ventana:
  Botón «Contraste»  o tecla c  → ver con o sin contraste
  Botón «Capturar»   o tecla s  → guardar captura en la carpeta de la sesión
  Botón «Salir»      o tecla q  → cerrar

Comando:
  ./scripts/abrir_flir.sh
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

INDICES = (0, 1, 2)
TIEMPO_APERTURA_MS = 5000
TIEMPO_LECTURA_MS = 3000
FALLOS_MAX = 30
BARRA_ALTO = 56
ROOT = Path(__file__).resolve().parents[1]
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
        "archivos *_vista.jpg = lo que se veía en la ventana al capturar\n",
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


def _botones(ancho: int) -> dict[str, tuple[int, int, int, int]]:
    margen = 10
    alto = BARRA_ALTO - 16
    anchos = [170, 160, 110]
    x = margen
    nombres = ("contraste", "capturar", "salir")
    zonas = {}
    for nombre, w in zip(nombres, anchos):
        zonas[nombre] = (x, 8, x + w, 8 + alto)
        x += w + margen
    # Ajuste fino si la ventana es más ancha
    if x < ancho - margen:
        pass
    return zonas


def _dibujar_barra(
    canvas: np.ndarray,
    zonas: dict[str, tuple[int, int, int, int]],
    con_contraste: bool,
    aviso: str,
) -> None:
    alto, ancho = canvas.shape[:2]
    y0 = alto - BARRA_ALTO
    cv2.rectangle(canvas, (0, y0), (ancho, alto), (24, 28, 40), -1)
    etiquetas = {
        "contraste": "Contraste: ON" if con_contraste else "Contraste: OFF",
        "capturar": "Capturar",
        "salir": "Salir",
    }
    colores = {
        "contraste": (40, 160, 90) if con_contraste else (70, 70, 90),
        "capturar": (180, 120, 40),
        "salir": (60, 60, 160),
    }
    for nombre, (x1, y1, x2, y2) in zonas.items():
        cv2.rectangle(
            canvas,
            (x1, y0 + y1),
            (x2, y0 + y2),
            colores[nombre],
            -1,
        )
        cv2.putText(
            canvas,
            etiquetas[nombre],
            (x1 + 10, y0 + y1 + 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
    if aviso:
        cv2.putText(
            canvas,
            aviso[:70],
            (10, y0 - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (220, 240, 255),
            1,
            cv2.LINE_AA,
        )


def mostrar(captura: cv2.VideoCapture, indice: int, etiqueta: str, sesion: Path) -> None:
    ventana = "FLIR USB — captura y contraste"
    cv2.namedWindow(ventana, cv2.WINDOW_NORMAL)
    estado = {
        "con_contraste": False,
        "capturar": False,
        "salir": False,
        "aviso": f"Sesión: {sesion.name}",
        "zonas": {},
    }

    def al_clic(evento: int, x: int, y: int, _flags: int, _param: object) -> None:
        if evento != cv2.EVENT_LBUTTONDOWN:
            return
        alto = estado.get("alto_canvas", 0)
        y0 = alto - BARRA_ALTO
        if y < y0:
            return
        local_y = y - y0
        for nombre, (x1, y1, x2, y2) in estado["zonas"].items():
            if x1 <= x <= x2 and y1 <= local_y <= y2:
                if nombre == "contraste":
                    estado["con_contraste"] = not estado["con_contraste"]
                    estado["aviso"] = (
                        "Contraste visual activado (no son °C)."
                        if estado["con_contraste"]
                        else "Vista sin contraste."
                    )
                elif nombre == "capturar":
                    estado["capturar"] = True
                elif nombre == "salir":
                    estado["salir"] = True

    cv2.setMouseCallback(ventana, al_clic)
    print(f"Mostrando índice {indice}: {etiqueta}", flush=True)
    print(f"Capturas de esta sesión: {sesion}", flush=True)
    print("Botones: Contraste | Capturar | Salir. Teclas: c, s, q.", flush=True)

    try:
        fallos_seguidos = 0
        while True:
            correcto, frame = captura.read()
            if not correcto or frame is None:
                fallos_seguidos += 1
                if fallos_seguidos >= FALLOS_MAX:
                    raise ErrorDeCamara(
                        "La FLIR dejó de enviar cuadros. Revisa el cable USB y que esté encendida."
                    )
                continue
            fallos_seguidos = 0

            original = frame.copy()
            contraste = aplicar_contraste(original)
            imagen = contraste if estado["con_contraste"] else original.copy()
            etiqueta_modo = (
                "Contraste visual. No son grados Celsius."
                if estado["con_contraste"]
                else "FLIR USB, imagen de la camara"
            )
            cv2.putText(
                imagen,
                etiqueta_modo,
                (12, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

            canvas = np.zeros((imagen.shape[0] + BARRA_ALTO, imagen.shape[1], 3), dtype=np.uint8)
            canvas[: imagen.shape[0], :, :] = imagen
            estado["alto_canvas"] = canvas.shape[0]
            estado["zonas"] = _botones(canvas.shape[1])
            _dibujar_barra(canvas, estado["zonas"], estado["con_contraste"], estado["aviso"])

            if estado["capturar"]:
                estado["capturar"] = False
                ruta = guardar_captura(
                    sesion,
                    original,
                    contraste,
                    canvas,
                    estado["con_contraste"],
                )
                estado["aviso"] = f"Guardado: {ruta.name}"
                print(f"Captura guardada en {ruta}", flush=True)

            cv2.imshow(ventana, canvas)
            tecla = cv2.waitKey(1) & 0xFF
            if tecla == ord("q") or estado["salir"]:
                break
            if tecla == ord("c"):
                estado["con_contraste"] = not estado["con_contraste"]
                estado["aviso"] = (
                    "Contraste visual activado (no son °C)."
                    if estado["con_contraste"]
                    else "Vista sin contraste."
                )
            if tecla == ord("s"):
                estado["capturar"] = True
            if cv2.getWindowProperty(ventana, cv2.WND_PROP_VISIBLE) == 0:
                break
    finally:
        captura.release()
        cv2.destroyAllWindows()
        print(f"Sesión cerrada. Archivos en: {sesion}", flush=True)


def main() -> int:
    try:
        sesion = crear_sesion_capturas()
        captura, indice, etiqueta = buscar_camara_externa()
    except ErrorDeCamara as exc:
        print("No se pudo iniciar la cámara FLIR.", file=sys.stderr)
        print(exc, file=sys.stderr)
        print(
            "Autoriza Cámara para Terminal o Cursor en "
            "Ajustes del Sistema > Privacidad y seguridad > Cámara.",
            file=sys.stderr,
        )
        return 1
    except OSError as exc:
        print(f"No se pudo crear la carpeta de sesión: {exc}", file=sys.stderr)
        return 1
    try:
        mostrar(captura, indice, etiqueta, sesion)
    except ErrorDeCamara as exc:
        print(exc, file=sys.stderr)
        return 1
    except cv2.error as exc:
        print(f"OpenCV falló: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
