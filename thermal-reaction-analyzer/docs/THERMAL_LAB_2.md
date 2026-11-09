# THERMAL LAB 2.0 — documentación técnica y científica

## Auditoría del sistema existente

Antes de extender el código se inspeccionaron `app.py`, `src/models/`, `src/services/`, `src/ui/`, `src/utils/`, `tests/`, `requirements.txt`, `README.md` y `docs/`.

1. **Selección de cámara.** `src/services/flir_camera.py` abre índices 0–2 con `cv2.CAP_AVFOUNDATION`, descarta resoluciones de webcam del Mac (≥1280) y elige 640 × 480. Si `system_profiler` reporta VendorID 2507 / ProductID 4107, la etiqueta es FLIR Systems.
2. **Captura.** Una sola `FlirLiveSession` global con candado. `read()` entrega BGR 8 bits. El contraste es `COLORMAP_INFERNO` sobre el gris: no son °C.
3. **Streamlit.** `st.fragment` ~180 ms incrusta un JPEG. No hay un segundo `VideoCapture`.
4. **Temperaturas del dashboard anterior.** Parte del avance 1 infería valores a partir del brillo (`live_thermal.py`). Eso **no** alimenta ΔT de Thermal Lab. Las lecturas cuantitativas nuevas son OCR del overlay o entrada manual.
5. **ΔT actual.** `TelemetrySeries.metrics`: ΔT = T_actual − T_referencia, con T_referencia de la línea base (o la última válida si el usuario permite análisis sin línea base).
6. **Guardado.** Ensayos en SQLite (`data/lab/thermal_lab.sqlite`). Fotos y videos en `data/captures/`.
7. **Estructuras reutilizadas.** `Experiment`, catálogo NaOH, exportación JSON, ROI visual previa, estilos oscuros.
8. **Sesiones.** `st.session_state` + `lab_runtime`. El hilo de captura no toca `session_state`.
9. **Pruebas.** Se conservan las 28 originales; se añadieron casos de laboratorio.
10. **Dependencia de T reales vs inferidas.** Cuantitativo: OCR/manual. Visual: color, contornos, ROI. Inferencia por color: excluida de las métricas del laboratorio.

## Capacidades de la cámara (estado verificado en software)

- Flujo UVC 640 × 480 en macOS vía AVFoundation.
- OpenCV entrega típicamente un arreglo BGR `uint8` de forma `(480, 640, 3)`.
- **No se afirmó Y16 ni radiometría.** `camera_diagnostics.radiometric_confirmed` es siempre `False` hasta una verificación futura.
- 640 × 480 es la resolución del **video compuesto** (imagen + overlay), no necesariamente la del sensor IR.

El diagnóstico en **Configuración** muestra forma, dtype, fourcc y backend del cuadro actual.

## Configurar OCR para esta FLIR

1. Instala Tesseract: `brew install tesseract`. Sin el binario, pytesseract no lee; la app marca calidad `ausente` y deja el respaldo manual.
2. Con la cámara en vivo, abre **Configuración**.
3. **Congelar cuadro** cuando se vea nítida la cifra.
4. Ajusta x, y, ancho y alto alrededor **de un solo número**. No asumas que tres cifras son min/max/promedio.
5. Elige la etiqueta: principal, spot, mínimo, máximo u otra.
6. Comprueba «OCR ve: …». Si el texto no es la temperatura, mueve el recorte.
7. **Guardar recortes OCR** escribe `data/lab/ocr_regions.json` (coordenadas normalizadas 0–1).
8. Puedes activar varias regiones; solo `principal` alimenta ΔT de las tarjetas.

Intervalo de lectura: ~0.7 s (configurable, 0.4–3.0 s). Un fallo no copia la lectura previa.

## Flujo experimental

A. Preparación: nombre, protocolo NaOH, masa/volumen/ambiente/recipiente/emisividad/distancia (opcionales).
B. Línea base: varias lecturas válidas; el panel indica si la referencia es estable.
C. **Marcar mezcla**: línea vertical, conserva datos previos, fija T_referencia.
D. Observación: gráfica, eventos, ΔT, alertas informativas (no son un sistema de seguridad certificado).
E. Finalizar y guardar: SQLite + PDF/JSON.

No hay instrucciones automáticas de mezclado de NaOH.

## Modo presentación

Interruptor **Presentación** arriba a la derecha. Oculta pestañas, agranda cámara y métricas, mantiene la procedencia de los datos. Sirve para proyectar frente a la profesora.

## Guía de demostración

1. Conectar FLIR USB, autorizar Cámara en macOS para Terminal/Cursor.
2. Abrir `streamlit run app.py`.
3. Mostrar video 640 × 480 y las cifras del overlay.
4. Calibrar OCR y leer un número coincidente.
5. Iniciar línea base (~10 s).
6. Marcar mezcla según el protocolo aprobado.
7. Señalar ΔT, dT/dt y eventos (calentamiento, pico, estabilización).
8. Mostrar ROI visual (decir explícitamente que no es °C).
9. Guardar, comparar con un control, descargar PDF.

Si la cámara falla: **Configuración → Reproducir video**. El encabezado dirá «Reproducción … (no es la FLIR en vivo)».

## Limitaciones

- No hay matriz radiométrica verificada.
- El OCR depende del contraste del overlay y de Tesseract.
- La paleta FLIR puede autoescalar; los contornos visuales no son isotermas.
- No se calcula entalpía con la temperatura de la superficie del vaso.
- La interpretación NaOH es orientativa.
- Grabación: AVI MJPG en la carpeta de sesión, no dentro de SQLite.

## Qué se validó cómo

| Función | Validación |
| --- | --- |
| Apertura FLIR 640 × 480, vista en vivo Streamlit | Hardware en sesiones previas de este proyecto (no revalidada en esta pasada de código) |
| OCR sobre overlay real de la FLIR | **No verificado con hardware en esta entrega.** Pruebas sintéticas; se omite si falta Tesseract |
| Parseo, validación, ΔT, dT/dt, línea base, eventos, alertas | Pytest |
| ROI, contornos, no conversión a °C | Pytest |
| Persistencia SQLite, CSV, PDF | Pytest |
| Reproducción de video sin cámara | Pytest (AVI sintético) |
| Desconexión sin inventar cuadros | Pytest |
| Grabación AVI y calibración OCR en UI | Implementadas; no ejercitadas aquí con la FLIR física |

No se usaron temperaturas inventadas para simular una medición radiométrica.

## Archivos principales añadidos o extendidos

- `src/models/telemetry.py`
- `src/services/camera_diagnostics.py`, `temperature_ocr.py`, `telemetry_service.py`, `baseline_analysis.py`, `event_detection.py`, `visual_thermal_analysis.py`, `roi_tracker.py`, `experiment_storage.py`, `experiment_comparison.py`, `alert_service.py`, `report_generator.py`
- `src/ui/dashboard.py`, `src/ui/lab_runtime.py`, `src/ui/capture_page.py`
- `src/services/flir_camera.py` (reproducción y grabación)
- `tests/test_thermal_lab.py`
- `data/lab/`
