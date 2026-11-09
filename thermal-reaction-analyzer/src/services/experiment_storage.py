"""Persistencia local de ensayos. El video no se guarda dentro de SQLite."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.models.telemetry import TemperatureReading, ThermalEvent

ROOT = Path(__file__).resolve().parents[2]
LAB_DIR = ROOT / "data" / "lab"
DB_PATH = LAB_DIR / "thermal_lab.sqlite"


@dataclass
class ExperimentRecord:
    id: str
    name: str
    created_at: str
    status: str
    protocol: str = ""
    reagents: str = ""
    process_type: str = ""
    mass_g: float | None = None
    volume_ml: float | None = None
    ambient_c: float | None = None
    vessel: str = ""
    emissivity: float | None = None
    distance_m: float | None = None
    observations: str = ""
    objective: str = ""
    temperature_source: str = "flir_ocr"
    reference_c: float | None = None
    mix_time_s: float | None = None
    started_unix: float | None = None
    readings: list[TemperatureReading] = field(default_factory=list)
    events: list[ThermalEvent] = field(default_factory=list)
    captures: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    reaction_name: str = ""
    concentration: str = ""
    group_name: str = ""
    operator: str = ""
    trial_n: int = 1

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["readings"] = [item.as_dict() for item in self.readings]
        payload["events"] = [item.as_dict() for item in self.events]
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperimentRecord:
        return cls(
            id=str(data["id"]),
            name=str(data.get("name") or "Ensayo"),
            created_at=str(data.get("created_at") or ""),
            status=str(data.get("status") or "preparacion"),
            protocol=str(data.get("protocol") or ""),
            reagents=str(data.get("reagents") or ""),
            process_type=str(data.get("process_type") or ""),
            mass_g=data.get("mass_g"),
            volume_ml=data.get("volume_ml"),
            ambient_c=data.get("ambient_c"),
            vessel=str(data.get("vessel") or ""),
            emissivity=data.get("emissivity"),
            distance_m=data.get("distance_m"),
            observations=str(data.get("observations") or ""),
            objective=str(data.get("objective") or ""),
            temperature_source=str(data.get("temperature_source") or "flir_ocr"),
            reference_c=data.get("reference_c"),
            mix_time_s=data.get("mix_time_s"),
            started_unix=data.get("started_unix"),
            readings=[TemperatureReading.from_dict(item) for item in data.get("readings", [])],
            events=[ThermalEvent.from_dict(item) for item in data.get("events", [])],
            captures=list(data.get("captures") or []),
            config=dict(data.get("config") or {}),
            reaction_name=str(data.get("reaction_name") or ""),
            concentration=str(data.get("concentration") or ""),
            group_name=str(data.get("group_name") or ""),
            operator=str(data.get("operator") or ""),
            trial_n=int(data.get("trial_n") or 1),
        )


def _connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS experiments (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL,
            payload TEXT NOT NULL
        )
        """
    )
    return conn


def save_experiment(record: ExperimentRecord, path: Path = DB_PATH) -> ExperimentRecord:
    conn = _connect(path)
    payload = json.dumps(record.as_dict(), ensure_ascii=False)
    conn.execute(
        """
        INSERT INTO experiments(id, name, created_at, status, payload)
        VALUES(?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            status=excluded.status,
            payload=excluded.payload
        """,
        (record.id, record.name, record.created_at, record.status, payload),
    )
    conn.commit()
    conn.close()
    return record


def load_experiment(experiment_id: str, path: Path = DB_PATH) -> ExperimentRecord | None:
    conn = _connect(path)
    row = conn.execute("SELECT payload FROM experiments WHERE id=?", (experiment_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return ExperimentRecord.from_dict(json.loads(row[0]))


def list_experiments(path: Path = DB_PATH) -> list[tuple[str, str, str, str]]:
    conn = _connect(path)
    rows = conn.execute(
        "SELECT id, name, created_at, status FROM experiments ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [(str(a), str(b), str(c), str(d)) for a, b, c, d in rows]


def new_record(name: str, protocol: str = "", reagents: str = "") -> ExperimentRecord:
    return ExperimentRecord(
        id=uuid4().hex[:10],
        name=name.strip() or "Ensayo",
        created_at=datetime.now().isoformat(timespec="seconds"),
        status="preparacion",
        protocol=protocol,
        reagents=reagents,
    )
