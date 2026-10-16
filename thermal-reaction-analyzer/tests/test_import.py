"""Pruebas de importación, FLIR y exportación."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from src.services.data_import import import_paths
from src.services.export_service import read_series_csv, series_csv
from src.services.flir_reader import RADIOMETRIC_CONVERSION_VERIFIED, inspect_jpeg
from src.services.simulation import SimulationConfig, generate_simulation
from src.services.thermal_analysis import TABLE_COLUMNS, analyze_experiment


def test_el_csv_exportado_conserva_columnas_y_unidades() -> None:
    experiment = generate_simulation(
        SimulationConfig(
            scenario="calentamiento",
            initial_temperature_c=24.0,
            change_magnitude_c=12.0,
            duration_s=4.0,
            interval_s=1.0,
            noise_std_c=0.0,
            seed=3,
        )
    )
    result = analyze_experiment(experiment, 40, 30, 80, 60, baseline_frames=1)
    payload = series_csv(experiment, result)
    text = payload.decode("utf-8-sig")
    assert "# temperatura_unidad: °C" in text
    assert "# tiempo_unidad: s" in text
    assert "# tasa_unidad: °C/s" in text
    table = read_series_csv(payload)
    assert list(table.columns) == TABLE_COLUMNS
    assert table["temperatura_promedio_C"].iloc[-1] > table["temperatura_promedio_C"].iloc[0]


def test_un_jpeg_sin_radiometria_no_genera_temperaturas(tmp_path: Path) -> None:
    image_path = tmp_path / "visual.jpg"
    Image.new("RGB", (32, 24), (10, 20, 30)).save(image_path, quality=85)
    inspection = inspect_jpeg(image_path)
    result = import_paths([image_path], "Foto visual")
    assert RADIOMETRIC_CONVERSION_VERIFIED is False
    assert inspection.temperature_matrix is None
    assert inspection.radiometric_valid is False
    assert result.experiment is not None
    assert result.experiment.has_numeric_data is False
    assert all(frame.matrix is None for frame in result.experiment.frames)
    assert all(frame.radiometric_valid is False for frame in result.experiment.frames)


def test_los_metadatos_de_planck_no_validan_la_conversion(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    image_path = tmp_path / "supuesto_flir.jpg"
    Image.new("RGB", (16, 16), (0, 0, 0)).save(image_path)
    monkeypatch.setattr("src.services.flir_reader.exiftool_executable", lambda: "/usr/bin/exiftool")
    monkeypatch.setattr(
        "src.services.flir_reader.read_exiftool_metadata",
        lambda _path: {
            "PlanckR1": 21106.77,
            "PlanckB": 1501.0,
            "PlanckF": 1.0,
            "PlanckO": -7340.0,
            "PlanckR2": 0.012545258,
            "RawThermalImageWidth": 160,
            "RawThermalImageHeight": 120,
        },
    )
    inspection = inspect_jpeg(image_path)
    assert inspection.has_planck_constants is True
    assert inspection.temperature_matrix is None
    assert inspection.radiometric_valid is False
    assert "No se calculan temperaturas" in inspection.message


def test_importa_npy_como_dato_cuantitativo_no_verificado(tmp_path: Path) -> None:
    matrix = np.full((8, 6), 21.5, dtype=np.float32)
    path = tmp_path / "matriz.npy"
    np.save(path, matrix)
    result = import_paths([path], "Matriz de prueba")
    assert result.experiment is not None
    assert result.experiment.origin.value == "importado_cuantitativo"
    frame = result.experiment.frames[0]
    assert frame.radiometric_valid is False
    assert frame.timestamp_s is None
    assert frame.matrix is not None
    assert float(frame.matrix.mean()) == pytest.approx(21.5)


def test_una_secuencia_sin_tiempo_exige_intervalo(tmp_path: Path) -> None:
    first = tmp_path / "a.csv"
    second = tmp_path / "b.csv"
    np.savetxt(first, np.ones((3, 3)), delimiter=",")
    np.savetxt(second, np.full((3, 3), 2.0), delimiter=",")
    with pytest.raises(Exception):
        import_paths([first, second], "Secuencia", manual_interval_s=None)
    result = import_paths([first, second], "Secuencia", manual_interval_s=1.0)
    assert result.experiment is not None
    assert [frame.timestamp_s for frame in result.experiment.frames] == [0.0, 1.0]
