# Analizador térmico de reacciones químicas

Primer avance funcional del sistema para visualizar y analizar cambios de temperatura superficial. Funciona sin una cámara conectada: la fuente principal de este avance es un simulador ilustrativo, y también puede importar matrices numéricas.

## Requisitos

- macOS con Apple Silicon
- Python 3.12 de Homebrew
- Conexión a internet solo para instalar dependencias

ExifTool es opcional. Sirve para leer metadatos de un JPEG. Su ausencia no impide abrir la aplicación ni ejecutar las pruebas. No convierte un JPEG en temperaturas.

## Instalación

```bash
brew install python@3.12
cd thermal-reaction-analyzer
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

ExifTool, si más adelante se quiere inspeccionar metadatos:

```bash
brew install exiftool
```

## Ejecución

Desde la carpeta `thermal-reaction-analyzer`, con el entorno activado:

```bash
streamlit run app.py
```

La aplicación abre el panel principal. No muestra temperaturas hasta que se inicia una simulación o se importa una matriz.

## Pruebas

```bash
source .venv/bin/activate
pytest
```

En este equipo, con Python 3.12.15, el resultado fue **18 passed**.

## Archivos de ejemplo

En `data/samples` hay matrices generadas por el simulador, no fotografías de la FLIR C5:

- `matriz_simulada.npy` y `matriz_simulada.csv`: último cuadro de un calentamiento simulado, 120 × 160 (alto × ancho), en °C.
- `secuencia_simulada.npz`: claves `temperaturas` y `tiempos_s`.
- `fotografia_visual.jpg`: imagen sin datos radiométricos.

Para regenerarlos:

```bash
python scripts/generate_samples.py
```

## Qué distingue la interfaz

- **Simulación ilustrativa:** el modelo `T = T_base + A(t)·G(x, y) + ruido`.
- **Datos cuantitativos importados:** números de un CSV, NPY o NPZ. No los certificó la cámara.
- **Medición radiométrica verificada:** no se asigna en este avance.
- **Imagen visual o FLIR pendiente:** se muestra la fotografía y, si ExifTool está disponible, los metadatos. No hay grados Celsius.

## Límites de la simulación

- Resolución fija: 160 px de ancho por 120 px de alto.
- Máximo 180 cuadros.
- Duración máxima 180 s.
- Intervalo entre 0.25 s y 30 s.
- Memoria estimada máxima de 64 MB.

## FLIR C5 más adelante

Cuando exista un JPEG original de la cámara:

1. Instalar ExifTool.
2. Importar el archivo en **Importar imágenes FLIR**.
3. Revisar si aparecen constantes de Planck y el bloque térmico crudo.
4. Validar formato, orden de bytes, conversión y calibración antes de usar cualquier temperatura.
5. Solo después de esa verificación se podrá activar la conversión. Hoy `RADIOMETRIC_CONVERSION_VERIFIED` permanece en `False` dentro de `src/services/flir_reader.py`.

La documentación del avance está en `docs/AVANCE_1.md`.
