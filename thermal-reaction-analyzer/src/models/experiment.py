"""Experimento de laboratorio asociado a una secuencia de cuadros."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any
from uuid import uuid4

from src.models.thermal_frame import DataOrigin, ThermalFrame


@dataclass
class Experiment:
    name: str
    origin: DataOrigin
    description: str = ""
    session_date: str = field(default_factory=lambda: date.today().isoformat())
    assay_type: str = ""
    reagents: str = ""
    ambient_temperature_c: float | None = None
    observations: str = ""
    frames: list[ThermalFrame] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid4().hex[:8])

    def __post_init__(self) -> None:
        if not isinstance(self.origin, DataOrigin):
            self.origin = DataOrigin(self.origin)
        for frame in self.frames:
            frame.experiment_id = self.id

    @property
    def numeric_frames(self) -> list[ThermalFrame]:
        return [frame for frame in self.frames if frame.has_temperature]

    @property
    def has_numeric_data(self) -> bool:
        return bool(self.numeric_frames)

    @property
    def has_time_series(self) -> bool:
        timed = [frame for frame in self.numeric_frames if frame.timestamp_s is not None]
        return len(timed) >= 2
