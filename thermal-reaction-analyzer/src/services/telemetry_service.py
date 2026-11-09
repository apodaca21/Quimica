"""Serie temporal de lecturas comparables (OCR, manual o radiométrica)."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.models.telemetry import ReadingQuality, TemperatureReading, TemperatureSource

QUANTITATIVE_SOURCES = {
    TemperatureSource.FLIR_OCR,
    TemperatureSource.FLIR_MANUAL,
    TemperatureSource.RADIOMETRIC,
}


def is_quantitative(reading: TemperatureReading) -> bool:
    return (
        reading.valid
        and reading.value_c is not None
        and reading.source in QUANTITATIVE_SOURCES
        and reading.quality not in {ReadingQuality.AUSENTE, ReadingQuality.INVALIDA}
    )


@dataclass
class TelemetryMetrics:
    current_c: float | None
    initial_c: float | None
    max_c: float | None
    min_c: float | None
    delta_c: float | None
    rate_c_per_s: float | None
    elapsed_s: float
    time_to_max_s: float | None
    time_since_mix_s: float | None
    mean_c: float | None
    stable: bool
    valid_count: int
    source_label: str
    notes: tuple[str, ...] = ()


@dataclass
class TelemetrySeries:
    measure_kind: str = "principal"
    readings: list[TemperatureReading] = field(default_factory=list)

    def add(self, reading: TemperatureReading) -> None:
        self.readings.append(reading)

    def valid(self) -> list[TemperatureReading]:
        return [
            item
            for item in self.readings
            if is_quantitative(item) and item.measure_kind == self.measure_kind
        ]

    def last_valid(self) -> TemperatureReading | None:
        items = self.valid()
        return items[-1] if items else None

    def last_valid_value(self) -> float | None:
        item = self.last_valid()
        return None if item is None else item.value_c

    def metrics(
        self,
        reference_c: float | None,
        mix_time_s: float | None = None,
        stable_std_c: float = 0.3,
        stable_window: int = 6,
    ) -> TelemetryMetrics:
        valid = self.valid()
        notes = [
            "Solo se usan lecturas válidas del mismo punto de medición.",
            "ΔT = T_actual − T_referencia.",
        ]
        if not valid:
            return TelemetryMetrics(
                current_c=None,
                initial_c=None,
                max_c=None,
                min_c=None,
                delta_c=None,
                rate_c_per_s=None,
                elapsed_s=0.0,
                time_to_max_s=None,
                time_since_mix_s=None,
                mean_c=None,
                stable=False,
                valid_count=0,
                source_label="sin lecturas válidas",
                notes=tuple(notes + ["Aún no hay lecturas cuantitativas comparables."]),
            )
        values = [float(item.value_c) for item in valid if item.value_c is not None]
        times = [float(item.timestamp_s) for item in valid]
        current = values[-1]
        initial = values[0]
        max_c = max(values)
        min_c = min(values)
        ref = initial if reference_c is None else float(reference_c)
        delta = current - ref
        rate = None
        if len(values) >= 2 and times[-1] != times[-2]:
            rate = (values[-1] - values[-2]) / (times[-1] - times[-2])
        elapsed = times[-1] - times[0]
        peak_index = values.index(max_c)
        time_to_max = times[peak_index] - times[0]
        time_since_mix = None if mix_time_s is None else times[-1] - mix_time_s
        window = values[-stable_window:] if len(values) >= stable_window else values
        mean = sum(values) / len(values)
        if len(window) >= 3:
            avg = sum(window) / len(window)
            var = sum((item - avg) ** 2 for item in window) / len(window)
            stable = (var ** 0.5) <= stable_std_c
        else:
            stable = False
        source = valid[-1].source.value
        return TelemetryMetrics(
            current_c=current,
            initial_c=initial,
            max_c=max_c,
            min_c=min_c,
            delta_c=delta,
            rate_c_per_s=rate,
            elapsed_s=elapsed,
            time_to_max_s=time_to_max,
            time_since_mix_s=time_since_mix,
            mean_c=mean,
            stable=stable,
            valid_count=len(valid),
            source_label=source,
            notes=tuple(notes),
        )


def approximate_rate(t2_c: float, t1_c: float, time_2_s: float, time_1_s: float) -> float:
    step = float(time_2_s) - float(time_1_s)
    if step == 0:
        raise ValueError("El intervalo de tiempo no puede ser cero.")
    return (float(t2_c) - float(t1_c)) / step
