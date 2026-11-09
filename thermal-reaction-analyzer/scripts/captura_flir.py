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

import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.flir_camera import (  # noqa: E402
    ErrorDeCamara,
    aplicar_contraste,
    buscar_camara_externa,
    crear_sesion_capturas,
    guardar_captura,
)

BARRA_ALTO = 56
FALLOS_MAX = 30


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
