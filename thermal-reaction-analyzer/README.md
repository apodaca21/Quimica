# THERMAL LAB — Analizador térmico de reacciones químicas

Laboratorio interactivo para registrar el overlay de temperatura de una cámara FLIR USB (UVC 640 × 480), analizar series temporales y comparar ensayos. Conserva el código del primer avance y añade telemetría verificable.

La aplicación **no inventa una matriz radiométrica**. Si OpenCV entrega video BGR de 8 bits, las temperaturas cuantitativas salen del número que la propia FLIR dibuja (OCR o entrada manual). El color del video es análisis visual relativo, no °C.

## Requisitos

- macOS con Apple Silicon
- Python 3.12 de Homebrew
- Cámara FLIR USB UVC (VendorID 2507 / ProductID 4107 en este equipo)
- Tesseract OCR opcional, para leer las cifras del overlay

## Instalación

```bash
brew install python@3.12
cd thermal-reaction-analyzer
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Para lectura automática de temperaturas:

```bash
brew install tesseract
```

ExifTool sigue siendo opcional y no convierte un JPEG en temperaturas.

## Ejecución

```bash
streamlit run app.py
```

Abre [http://localhost:8501](http://localhost:8501). La FLIR se intenta conectar al arrancar. Si no está disponible, usa **Reconectar** o, en **Configuración**, un video grabado de prueba (queda etiquetado como reproducción, no como FLIR en vivo).

Ventana OpenCV aparte:

```bash
./scripts/abrir_flir.sh
```

## Uso rápido (demostración)

1. Comprueba que el encabezado diga **FLIR conectada**.
2. En **Configuración**, congela un cuadro, ajusta el recorte alrededor del número de la FLIR y verifica el texto OCR.
3. Pulsa **Guardar recortes OCR**.
4. En **Experimento**, nombra el ensayo e **Iniciar línea base**.
5. Marca **Marcar mezcla** cuando ocurra el evento (sigue el protocolo de la profesora).
6. Observa T, ΔT y la gráfica. ΔT = T_actual − T_referencia, con la referencia de la línea base.
7. **Finalizar y guardar**. Compara ensayos y descarga PDF/JSON.

**Modo presentación:** interruptor *Presentación* en el encabezado. Agranda cámara y métricas y oculta las pestañas técnicas.

## Qué mide y qué no

| Tipo | Origen | ¿Es °C cuantitativo? |
| --- | --- | --- |
| Temperatura FLIR | Overlay leído por OCR o escrito a mano | Sí, del overlay de la cámara |
| Temperatura radiométrica | Matriz calibrada por píxel | Solo si se verifica (hoy no) |
| Información visual | Color, ROI, contornos | No. Relativo al video |

ΔT y dT/dt usan únicamente lecturas válidas de la misma fuente. Un OCR fallido se marca ausente; no se reutiliza en silencio la lectura anterior.

## Pruebas

```bash
source .venv/bin/activate
pytest
```

Las 28 pruebas del primer avance se conservan. Hay pruebas nuevas de OCR, telemetría, ROI, persistencia, reporte y reproducción de video.

## Datos

- `data/captures/sesion_*`: fotos y videos de la sesión de cámara (fuera de SQLite).
- `data/lab/thermal_lab.sqlite`: ensayos persistentes.
- `data/lab/ocr_regions.json`: recortes OCR normalizados.
- `data/samples`: matrices ilustrativas del simulador original, no mediciones FLIR.

Documentación técnica: `docs/THERMAL_LAB_2.md`. El avance 1 permanece en `docs/AVANCE_1.md`.
