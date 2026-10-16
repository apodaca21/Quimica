"""Importación de matrices numéricas e imágenes."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, UnidentifiedImageError

from src.models.experiment import Experiment
from src.models.thermal_frame import DataOrigin, ThermalFrame
from src.services.flir_reader import FlirInspection, inspect_jpeg
from src.utils.limits import MAX_FILE_BYTES
from src.utils.validation import ValidationError, require_finite_matrix, validate_import_stack, validate_time_step

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
NUMERIC_SUFFIXES = {".csv", ".npy", ".npz"}


@dataclass
class ImportResult:
    experiment: Experiment | None
    messages: list[str] = field(default_factory=list)
    inspections: list[FlirInspection] = field(default_factory=list)


def _check_size(path: Path) -> None:
    size = path.stat().st_size
    if size <= 0:
        raise ValidationError(f"El archivo {path.name} está vacío.")
    if size > MAX_FILE_BYTES:
        raise ValidationError(f"El archivo {path.name} supera el tamaño máximo de 20 MB.")


def _load_matrix_csv(path: Path) -> np.ndarray:
    try:
        table = pd.read_csv(path, header=None)
    except (OSError, pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise ValidationError(f"No se pudo leer el CSV {path.name}.") from exc
    numeric = table.apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any():
        raise ValidationError(f"El CSV {path.name} contiene valores no numéricos, vacíos o no finitos.")
    return require_finite_matrix(numeric.to_numpy(dtype=np.float64), origen=f"el archivo {path.name}")


def _as_frame_stack(array: np.ndarray, name: str) -> np.ndarray:
    if array.ndim == 2:
        frame = require_finite_matrix(array, origen=f"el archivo {name}")
        return frame[None, :, :]
    if array.ndim == 3:
        if array.shape[0] > array.shape[1] and array.shape[0] > array.shape[2]:
            frames = array
        elif array.shape[-1] <= 8 and array.shape[0] > 8 and array.shape[1] > 8:
            raise ValidationError(
                f"{name} parece una imagen en color, no una secuencia de temperaturas."
            )
        else:
            frames = array
        checked = [require_finite_matrix(frame, origen=f"el cuadro de {name}") for frame in frames]
        return np.stack(checked, axis=0)
    raise ValidationError(f"{name} no es una matriz 2D ni una secuencia 3D de temperaturas.")


def _load_npy(path: Path) -> tuple[np.ndarray, np.ndarray | None]:
    try:
        array = np.load(path, allow_pickle=False)
    except (OSError, ValueError) as exc:
        raise ValidationError(f"No se pudo leer el archivo NumPy {path.name}.") from exc
    return _as_frame_stack(np.asarray(array), path.name), None


def _load_npz(path: Path) -> tuple[np.ndarray, np.ndarray | None]:
    try:
        with np.load(path, allow_pickle=False) as archive:
            if "temperaturas" in archive:
                temperatures = np.asarray(archive["temperaturas"])
            elif "temperatures" in archive:
                temperatures = np.asarray(archive["temperatures"])
            elif len(archive.files) == 1:
                temperatures = np.asarray(archive[archive.files[0]])
            else:
                raise ValidationError(
                    f"{path.name} debe incluir el arreglo 'temperaturas' o un único arreglo."
                )
            times = None
            for key in ("tiempos_s", "timestamps_s", "time_s"):
                if key in archive:
                    times = np.asarray(archive[key], dtype=np.float64)
                    break
    except ValidationError:
        raise
    except (OSError, ValueError) as exc:
        raise ValidationError(f"No se pudo leer el archivo NPZ {path.name}.") from exc
    return _as_frame_stack(temperatures, path.name), times


def _validate_times(times: np.ndarray | None, count: int, manual_interval_s: float | None) -> list[float | None]:
    if count == 1:
        if times is not None:
            if len(times) != 1 or not np.isfinite(times[0]):
                raise ValidationError("La marca de tiempo del cuadro único no es válida.")
            return [float(times[0])]
        return [0.0]
    if times is not None:
        if len(times) != count or not np.isfinite(times).all():
            raise ValidationError("Las marcas de tiempo no coinciden con el número de cuadros o no son numéricas.")
        ordered = [float(value) for value in times]
        for previous, current in zip(ordered, ordered[1:]):
            validate_time_step(previous, current)
        return ordered
    if manual_interval_s is None:
        raise ValidationError("La secuencia no tiene marcas de tiempo. Indica un intervalo de captura en segundos.")
    if not np.isfinite(manual_interval_s) or manual_interval_s <= 0:
        raise ValidationError("El intervalo de captura manual debe ser mayor que cero.")
    return [index * float(manual_interval_s) for index in range(count)]


def _numeric_experiment(
    name: str,
    frames: np.ndarray,
    times: list[float | None],
    source_names: list[str],
) -> Experiment:
    validate_import_stack(len(frames), int(frames.shape[1]), int(frames.shape[2]))
    experiment = Experiment(
        name=name,
        origin=DataOrigin.IMPORTADO_CUANTITATIVO,
        description="Matrices numéricas importadas. No son una medición radiométrica verificada.",
        assay_type="Datos importados",
        observations="El archivo aporta números de temperatura. La cámara no los certificó.",
        parameters={"cuadros": int(len(frames)), "alto": int(frames.shape[1]), "ancho": int(frames.shape[2])},
    )
    experiment.frames = [
        ThermalFrame(
            matrix=frames[index],
            unit="°C",
            timestamp_s=times[index],
            origin=DataOrigin.IMPORTADO_CUANTITATIVO,
            experiment_id=experiment.id,
            metadata={"archivo": source_names[index]},
            radiometric_valid=False,
            source_name=source_names[index],
        )
        for index in range(len(frames))
    ]
    return experiment


def _preview_rgb(path: Path) -> np.ndarray:
    try:
        with Image.open(path) as image:
            return np.asarray(image.convert("RGB"))
    except (UnidentifiedImageError, OSError) as exc:
        raise ValidationError("El archivo de imagen está dañado o no es un formato compatible.") from exc


def import_paths(
    paths: list[Path],
    experiment_name: str,
    manual_interval_s: float | None = None,
) -> ImportResult:
    if not paths:
        raise ValidationError("No se seleccionó ningún archivo.")
    ordered = sorted(paths, key=lambda item: item.name.lower())
    suffixes = {path.suffix.lower() for path in ordered}
    if not suffixes.issubset(IMAGE_SUFFIXES | NUMERIC_SUFFIXES):
        unknown = ", ".join(sorted(suffixes - IMAGE_SUFFIXES - NUMERIC_SUFFIXES))
        raise ValidationError(f"Formato no compatible: {unknown}.")
    if suffixes & IMAGE_SUFFIXES and suffixes & NUMERIC_SUFFIXES:
        raise ValidationError("Importa por separado las imágenes y las matrices numéricas.")
    for path in ordered:
        _check_size(path)

    if suffixes <= NUMERIC_SUFFIXES:
        stacks: list[np.ndarray] = []
        names: list[str] = []
        embedded_times: list[float] | None = None
        for path in ordered:
            suffix = path.suffix.lower()
            if suffix == ".csv":
                matrix = _load_matrix_csv(path)
                stacks.append(matrix[None, :, :])
                names.append(path.name)
            elif suffix == ".npy":
                frames, _times = _load_npy(path)
                stacks.extend(frame[None, :, :] for frame in frames)
                names.extend(f"{path.name}#{index + 1}" for index in range(len(frames)))
            else:
                frames, times = _load_npz(path)
                if times is not None and len(ordered) == 1:
                    embedded_times = [float(value) for value in times]
                stacks.extend(frame[None, :, :] for frame in frames)
                names.extend(f"{path.name}#{index + 1}" for index in range(len(frames)))
        shapes = {stack.shape[1:] for stack in stacks}
        if len(shapes) != 1:
            raise ValidationError("Todas las matrices de la secuencia deben tener la misma resolución.")
        combined = np.concatenate(stacks, axis=0)
        times = _validate_times(
            None if embedded_times is None else np.asarray(embedded_times, dtype=np.float64),
            len(combined),
            manual_interval_s,
        )
        if len(combined) == 1:
            times = [None]
        experiment = _numeric_experiment(experiment_name, combined, times, names)
        message = (
            "Datos cuantitativos importados. No corresponden a una medición radiométrica verificada."
        )
        if len(combined) == 1:
            message += " Hay un solo cuadro, así que no se inventó una serie temporal."
        return ImportResult(experiment=experiment, messages=[message])

    frames: list[ThermalFrame] = []
    messages: list[str] = []
    inspections: list[FlirInspection] = []
    experiment = Experiment(
        name=experiment_name,
        origin=DataOrigin.IMAGEN_VISUAL,
        description="Imágenes importadas para inspección visual.",
        assay_type="Imagen",
        observations="Sin temperaturas cuantitativas verificadas.",
    )
    for path in ordered:
        suffix = path.suffix.lower()
        preview = _preview_rgb(path)
        if suffix in {".jpg", ".jpeg"}:
            inspection = inspect_jpeg(path)
            inspections.append(inspection)
            messages.append(f"{path.name}: {inspection.message}")
            origin = (
                DataOrigin.FLIR_PENDIENTE
                if inspection.has_planck_constants or inspection.has_raw_thermal_metadata
                else DataOrigin.IMAGEN_VISUAL
            )
            metadata = {
                "archivo": path.name,
                "exiftool": inspection.exiftool_available,
                "planck_detectado": inspection.has_planck_constants,
                "raw_termico_detectado": inspection.has_raw_thermal_metadata,
                "metadatos": inspection.metadata,
            }
        else:
            origin = DataOrigin.IMAGEN_VISUAL
            metadata = {"archivo": path.name}
            messages.append(f"{path.name}: imagen visual sin temperaturas verificables.")
        frames.append(
            ThermalFrame(
                matrix=None,
                unit="",
                timestamp_s=None,
                origin=origin,
                experiment_id=experiment.id,
                metadata=metadata,
                radiometric_valid=False,
                preview_rgb=preview,
                source_name=path.name,
            )
        )
    if any(frame.origin == DataOrigin.FLIR_PENDIENTE for frame in frames):
        experiment.origin = DataOrigin.FLIR_PENDIENTE
    experiment.frames = frames
    return ImportResult(experiment=experiment, messages=messages, inspections=inspections)
