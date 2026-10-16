"""Genera archivos de ejemplo etiquetados como simulación."""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.simulation import SimulationConfig, generate_matrices
OUTPUT = ROOT / "data" / "samples"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    config = SimulationConfig(
        scenario="calentamiento",
        initial_temperature_c=24.0,
        change_magnitude_c=12.0,
        duration_s=8.0,
        interval_s=1.0,
        noise_std_c=0.0,
        seed=7,
        name="Muestra simulada",
    )
    times, matrices = generate_matrices(config)
    np.save(OUTPUT / "matriz_simulada.npy", matrices[-1])
    np.savez(
        OUTPUT / "secuencia_simulada.npz",
        temperaturas=matrices,
        tiempos_s=times,
    )
    np.savetxt(OUTPUT / "matriz_simulada.csv", matrices[-1], delimiter=",")
    Image.new("RGB", (160, 120), (20, 24, 48)).save(OUTPUT / "fotografia_visual.jpg", quality=85)
    notice = (
        "Estos archivos fueron generados por el simulador ilustrativo.\n"
        "No son fotografías ni mediciones de la FLIR C5.\n"
        "matriz_simulada.npy y matriz_simulada.csv contienen el último cuadro\n"
        "de un calentamiento simulado, de 120 × 160 (alto × ancho), en °C.\n"
        "secuencia_simulada.npz contiene la clave 'temperaturas' y 'tiempos_s'.\n"
        "fotografia_visual.jpg no tiene datos radiométricos.\n"
    )
    (OUTPUT / "LEEME.txt").write_text(notice, encoding="utf-8")


if __name__ == "__main__":
    main()
