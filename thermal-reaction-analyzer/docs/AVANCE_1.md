# Avance 1 — Analizador térmico de reacciones químicas

## 1. Introducción

Este avance presenta un programa de escritorio, accesible desde el navegador, para observar cómo se distribuye y cómo cambia la temperatura de una superficie. El caso de estudio es el seguimiento térmico de un experimento de química. La versión actual ya se puede demostrar sin conectar la FLIR C5.

Los números que produce el simulador son ejemplos controlados. No son mediciones de una reacción real.

## 2. Planteamiento del problema

En el laboratorio suele medirse la temperatura con un termómetro en uno o varios instantes. Esa lectura no muestra:

- la distribución de temperatura en una superficie;
- las zonas más calientes y más frías;
- cambios rápidos;
- la evolución durante el ensayo;
- la diferencia entre dos experimentos.

La propuesta es recibir datos térmicos, visualizarlos y calcular métricas de la región que interesa observar.

## 3. Objetivo general

Desarrollar un sistema que permita visualizar, registrar y analizar los cambios de temperatura asociados con reacciones químicas, mediante imágenes térmicas y una interfaz digital.

## 4. Objetivos específicos de este avance

- Ejecutar la aplicación en macOS con Apple Silicon sin una cámara conectada.
- Simular calentamiento, enfriamiento y un control aproximadamente estable en matrices de 160 × 120 px.
- Mostrar un mapa térmico, una gráfica temporal y las temperaturas mínima, máxima y promedio de una región rectangular.
- Calcular ΔT, la desviación estándar y una tasa aproximada de cambio.
- Importar CSV, NPY y NPZ, y mostrar JPG o PNG sin inventar temperaturas.
- Dejar un adaptador FLIR que inspecciona metadatos y no da por válida una conversión.
- Exportar CSV, JSON y gráficas HTML.
- Probar el cálculo con Pytest.

## 5. Tecnologías utilizadas

- Python 3.12.15, instalado con Homebrew.
- Streamlit para la interfaz.
- Plotly para el mapa y las gráficas.
- NumPy para las matrices y las fórmulas.
- Pandas para la tabla de la serie.
- Pillow para leer imágenes.
- Pytest para las pruebas.

ExifTool no está instalado en el equipo de desarrollo. El programa arranca igual. OpenCV y SciPy no se usaron.

## 6. Arquitectura del software

La interfaz vive en `app.py` y en `src/ui`. El estado de la sesión guarda los ensayos, el cuadro visible, la reproducción y la región de interés.

El procesamiento está separado de la pantalla:

- `src/models` define el cuadro térmico y el experimento.
- `src/services/simulation.py` genera las matrices.
- `src/services/roi_analysis.py` y `thermal_analysis.py` calculan las métricas.
- `src/services/data_import.py` lee archivos.
- `src/services/flir_reader.py` habla con ExifTool, si existe.
- `src/services/export_service.py` prepara CSV, JSON y HTML.

Cada cuadro guarda la matriz, la unidad, el tiempo, el origen, el identificador del experimento, los metadatos y si la lectura radiométrica es válida. En este avance esa validez permanece en falso, salvo que en el futuro se incorpore una medición ya verificada.

## 7. Fundamento matemático

Sobre la región de interés de un cuadro:

- temperatura promedio: T̄ = (Σ Tᵢ) / N
- desviación estándar poblacional: σ = √[Σ(Tᵢ − T̄)² / N]

Sobre la serie temporal de promedios de esa región:

- línea base: promedio de los primeros cuadros elegidos; por defecto, el primero
- ΔT = T_final − T_línea base
- tasa aproximada: (T₂ − T₁) / (t₂ − t₁), en °C/s

Un intervalo de tiempo igual a cero se rechaza. Con un solo cuadro no se inventa una serie.

La interpretación usa cuatro frases: calentamiento superficial, enfriamiento superficial, temperatura aproximadamente estable o datos insuficientes. El umbral de estabilidad es 0.5 °C en el ΔT de la serie. Ninguna de esas frases afirma que la reacción sea endotérmica o exotérmica, y el programa no calcula entalpía.

## 8. Módulos implementados

1. **Panel principal.** Encabezado, estado, fuente, nombre, tipo de dato y fecha. Cuatro tarjetas, mapa con paleta, gráfica y texto de interpretación. Si no hay datos, el panel queda vacío a propósito.
2. **Simulación térmica.** Tres escenarios, parámetros editables y controles de reproducir, pausar, reiniciar, avanzar y elegir el instante.
3. **Importación.** JPG, JPEG, PNG, CSV, NPY y NPZ. Distingue simulación, datos cuantitativos importados, imagen visual y FLIR pendiente de validación.
4. **Región de interés.** Posición X, Y, ancho y alto, con un rectángulo sobre el mapa. Los cálculos usan la matriz numérica y se recortan a sus límites.
5. **Análisis.** Tabla temporal, tres gráficas y comparación de dos ensayos de la sesión.
6. **Exportación.** CSV con unidades en el encabezado, JSON y HTML interactivo.

## 9. Metodología de simulación

El modelo ilustrativo es:

T(x, y, t) = T_base + A(t) · G(x, y) + ε(x, y, t)

G es una gaussiana con máximo en el centro. A(t) crece en el calentamiento, decrece en el enfriamiento y oscila con amplitud pequeña en el control. ε es ruido normal reproducible con una semilla.

No es una solución de la ecuación de calor ni un reemplazo del calorímetro. Las temperaturas de ejemplo, como pasar de 24 °C a 36 °C, solo sirven para probar la interfaz.

La reproducción usa un fragmento de Streamlit con un intervalo visual de 0.5 s a 2 s. Ese intervalo no modifica el tiempo del experimento. La reproducción se detiene en el último cuadro y puede pausarse.

Límites: 180 cuadros, 180 s y una estimación máxima de 64 MB.

## 10. Pruebas ejecutadas

Se ejecutó `pytest` con el intérprete del entorno virtual (Python 3.12.15), sin cámara y sin ExifTool.

Resultado: **18 passed** en 17.42 s.

Cubren, entre otras comprobaciones:

1. Matrices de 120 filas por 160 columnas (alto × ancho de la FLIR C5).
2. La misma semilla produce la misma secuencia.
3. El calentamiento aumenta el promedio espacial.
4. El enfriamiento lo disminuye.
5. El promedio coincide con la suma dividida entre N.
6. ΔT es la temperatura final menos la inicial.
7. La ROI de un caso conocido devuelve mínimo, máximo, promedio, desviación y posiciones.
8. Una ROI fuera de la imagen se rechaza.
9. El CSV conserva las columnas y declara °C, s y °C/s.
10. Un JPEG sin información radiométrica no produce una matriz de temperatura.

También se comprobó que unos metadatos de Planck simulados en la prueba no marcan la conversión como válida.

Además, la interfaz se ejecutó con el banco de pruebas de Streamlit: el panel abre, una simulación de calentamiento registra 31 cuadros, aparecen el mapa, la gráfica y las descargas, y las secciones de análisis, importación e información cargan sin excepción. No se usó una cámara.

## 11. Resultados preliminares

Con ruido cero, temperatura inicial 24 °C y magnitud 12 °C, el promedio espacial del calentamiento simulado aumenta entre el primer y el último cuadro. En el enfriamiento de magnitud 6 °C, el promedio disminuye. Esos resultados confirman el modelo numérico. No describen una reacción química realizada en el laboratorio.

La región central cambia más que los bordes, así que una ROI centrada no coincide con una ROI en la esquina. Esa diferencia también es una consecuencia del modelo, no una observación experimental.

## 12. Limitaciones actuales

- No hay integración validada con la FLIR C5 ni con la E8xt.
- Encontrar constantes de Planck no autoriza a publicar temperaturas.
- La corrección por emisividad, atmósfera, ventana y orden de bytes no está verificada.
- ExifTool no está instalado en este equipo.
- Los ensayos viven en la sesión del navegador. No hay base de datos ni PDF.
- La comparación y las gráficas usan la ROI definida en la sesión.
- Medir a través de vidrio, la emisividad, los reflejos, el ambiente y la calibración siguen siendo fuentes de error cuando existan datos reales.

## 13. Actividades pendientes

- Obtener JPEG originales de la FLIR C5.
- Verificar el formato del bloque térmico, la conversión y la calibración.
- Decidir si la E8xt entra en el flujo.
- Comparar el sistema con un termómetro u otra referencia.
- Registrar reacciones reales y conservar el historial.
- Redactar el reporte científico final.

## 14. Plan para el siguiente avance

1. Importar fotografías reales de la C5 y documentar qué metadatos aparecen.
2. Comparar una conversión candidata contra una referencia de temperatura antes de mostrarla como medición.
3. Mantener separados, también en ese avance, la simulación, el archivo numérico importado y la medición verificada.
4. Si la verificación falla, la aplicación debe seguir funcionando con simulación e importación, como ahora.

## Evidencias para la exposición

En macOS, `Cmd + Shift + 4` guarda una captura.

Sugerencia de tomas:

1. Panel principal recién abierto, con el aviso de que no hay experimento.
2. Simulación de calentamiento con el mapa y la gráfica.
3. Tarjetas de mínimo, máximo, promedio y ΔT.
4. La misma simulación con una ROI en el centro y otra en una esquina.
5. El recuadro de interpretación y sus advertencias.
6. El botón de descarga CSV.
7. La importación de `data/samples/secuencia_simulada.npz`, con el aviso de dato cuantitativo no verificado.
8. La página de importación FLIR, donde se explica que la conversión de la C5 está pendiente.

No conviene presentar estas capturas como pruebas hechas con la cámara.
