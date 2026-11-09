"""Interpretación prudente del comportamiento térmico de una sesión."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from src.models.experiment import Experiment
from src.services.thermal_analysis import AnalysisResult


@dataclass(frozen=True)
class ThermalInterpretation:
    """Resultado explicable del clasificador térmico.

    La clasificación describe la forma de la señal térmica; no identifica una
    sustancia ni confirma por sí sola una reacción química concreta.
    """

    category: str
    label: str
    confidence: str
    summary: str
    evidence: tuple[str, ...]
    warnings: tuple[str, ...]
    reaction_prediction: str
    reaction_confidence: str
    reaction_evidence: tuple[str, ...]
    max_delta_c: float | None = None
    min_delta_c: float | None = None
    max_rate_c_per_s: float | None = None

    def as_dict(self) -> dict[str, object]:
        """Representación lista para incluir en una exportación JSON."""
        return asdict(self)


def _confidence(amplitude_c: float, sample_count: int, threshold_c: float) -> str:
    if sample_count < 4:
        return "baja"
    if amplitude_c >= threshold_c * 4:
        return "alta"
    if amplitude_c >= threshold_c * 2:
        return "media"
    return "baja"


def _fmt_signed(value: float) -> str:
    return f"{value:+.2f} °C"


def _normalizar(texto: str) -> str:
    import unicodedata

    return "".join(
        caracter
        for caracter in unicodedata.normalize("NFD", texto.lower())
        if unicodedata.category(caracter) != "Mn"
    )


def _contiene(texto: str, opciones: tuple[str, ...]) -> bool:
    return any(opcion in texto for opcion in opciones)


def _predict_reaction_family(
    category: str,
    experiment: Experiment | None,
    max_delta_c: float | None = None,
    min_delta_c: float | None = None,
) -> tuple[str, str, tuple[str, ...]]:
    """Sugiere una familia de reacción usando reactivos y firma térmica.

    La temperatura por sí sola no permite identificar una reacción exacta. Las
    palabras de reactivos solo se usan como contexto adicional y la salida se
    etiqueta explícitamente como una predicción orientativa.
    """
    texto = ""
    if experiment is not None:
        texto = _normalizar(
            " ".join(
                (
                    experiment.assay_type,
                    experiment.reagents,
                    experiment.description,
                    experiment.observations,
                )
            )
        )

    acid = _contiene(texto, ("acido", "hcl", "h2so4", "hno3", "acido clorhidrico", "vinagre", "acetico", "ch3cooh"))
    base = _contiene(texto, ("base", "naoh", "koh", "nh3", "amoniaco", "hidroxido", "bicarbonato"))
    naoh = _contiene(texto, ("naoh", "hidroxido de sodio")) or (
        experiment is not None and bool(experiment.parameters.get("protocolo"))
    )
    if naoh:
        from src.services.naoh_catalog import predict_naoh_family

        return predict_naoh_family(category, experiment, max_delta_c, min_delta_c)
    precipitation = _contiene(texto, ("precipitado", "precipitacion", "nitrato de plata", "agcl"))
    combustion = _contiene(texto, ("combustion", "quemar", "flama", "oxigeno", "o2", "etanol", "metanol"))
    phase_change = _contiene(texto, ("fusion", "evaporacion", "ebullicion", "condensacion", "solidificacion", "cambio de fase"))
    dissolution = _contiene(texto, ("disolver", "disolucion", "solubilidad", "cloruro de calcio", "sal en agua"))

    if acid and base:
        if category == "exotermico_posible":
            return (
                "Posible neutralización ácido-base con liberación de calor",
                "media-alta",
                ("Se encontraron términos asociados con un ácido y una base.", "La señal térmica muestra aumento de temperatura."),
            )
        return (
            "Posible neutralización ácido-base",
            "media-baja" if category == "estable" else "baja",
            ("Se encontraron términos asociados con un ácido y una base.", "La señal térmica no confirma por sí sola la neutralización."),
        )
    if combustion:
        return (
            "Posible combustión u oxidación",
            "media" if category == "exotermico_posible" else "baja",
            ("Los datos del ensayo contienen términos asociados con combustión u oxígeno.",),
        )
    if precipitation:
        return (
            "Posible reacción de precipitación",
            "baja" if category == "estable" else "media-baja",
            ("Los datos del ensayo contienen términos asociados con formación de precipitado.",),
        )
    if phase_change:
        return (
            "Posible cambio de fase",
            "media-baja" if category in {"endotermico_posible", "transitorio"} else "baja",
            ("Los datos del ensayo contienen términos asociados con un cambio de fase.",),
        )
    if dissolution:
        return (
            "Posible proceso de disolución o hidratación",
            "media-baja" if category != "estable" else "baja",
            ("Los datos del ensayo contienen términos asociados con disolver una sustancia.",),
        )

    behavior = {
        "exotermico_posible": "proceso exotérmico no identificado",
        "endotermico_posible": "proceso endotérmico no identificado",
        "transitorio": "proceso térmico transitorio no identificado",
        "estable": "sin evidencia térmica suficiente para identificar una reacción",
    }.get(category, "reacción no identificable con los datos disponibles")
    return (
        f"No se puede identificar una reacción específica; resultado compatible con {behavior}",
        "baja",
        ("Agrega el tipo de ensayo y los reactivos para mejorar la predicción.",),
    )


def classify_thermal_behavior(
    result: AnalysisResult,
    stable_threshold_c: float = 0.5,
    experiment: Experiment | None = None,
) -> ThermalInterpretation:
    """Clasifica una serie térmica en categorías comprensibles para el usuario.

    Se consideran transitorios los casos en los que una señal alcanza un pico
    o un valle y después regresa de forma apreciable hacia la línea base.
    """
    table = result.table
    warnings = (
        "La clasificación describe el comportamiento de la temperatura superficial; no identifica los reactivos.",
        "Para confirmar una reacción exotérmica o endotérmica se necesitan reactivos, masas y condiciones del ensayo.",
    )
    if len(table) < 2:
        prediction, reaction_confidence, reaction_evidence = _predict_reaction_family(
            "insuficiente", experiment
        )
        return ThermalInterpretation(
            category="insuficiente",
            label="Datos insuficientes",
            confidence="baja",
            summary="Se necesitan al menos dos cuadros con tiempo para interpretar una evolución térmica.",
            evidence=("La sesión contiene menos de dos puntos temporales.",),
            warnings=warnings,
            reaction_prediction=prediction,
            reaction_confidence=reaction_confidence,
            reaction_evidence=reaction_evidence,
        )

    deltas = table["delta_T_C"].to_numpy(dtype=float)
    rates = table["tasa_C_por_s"].dropna().to_numpy(dtype=float)
    max_delta = float(np.max(deltas))
    min_delta = float(np.min(deltas))
    final_delta = float(deltas[-1])
    max_rate = float(np.max(np.abs(rates))) if rates.size else None
    warm_return = max_delta - final_delta
    cool_return = final_delta - min_delta
    warm_transient = max_delta >= stable_threshold_c and warm_return >= max(stable_threshold_c, max_delta * 0.35)
    cool_transient = min_delta <= -stable_threshold_c and cool_return >= max(stable_threshold_c, abs(min_delta) * 0.35)

    if warm_transient or cool_transient:
        category = "transitorio"
        label = "Cambio térmico transitorio"
        excursion = max(max_delta, abs(min_delta))
        confidence = _confidence(excursion, len(table), stable_threshold_c)
        summary = "La temperatura alcanza un pico o valle y después regresa parcialmente hacia la línea base."
    elif max_delta >= stable_threshold_c and max_delta >= abs(min_delta):
        category = "exotermico_posible"
        label = "Posible comportamiento exotérmico"
        confidence = _confidence(max_delta, len(table), stable_threshold_c)
        summary = "La región observada presenta un aumento térmico compatible con liberación de calor."
    elif min_delta <= -stable_threshold_c:
        category = "endotermico_posible"
        label = "Posible comportamiento endotérmico"
        confidence = _confidence(abs(min_delta), len(table), stable_threshold_c)
        summary = "La región observada presenta una disminución térmica compatible con absorción de calor."
    else:
        category = "estable"
        label = "Temperatura aproximadamente estable"
        confidence = "media" if len(table) >= 4 else "baja"
        summary = "No se observa un cambio térmico mayor al umbral configurado en la región seleccionada."

    evidence = [
        f"Cambio máximo respecto a la línea base: {_fmt_signed(max_delta)}.",
        f"Cambio mínimo respecto a la línea base: {_fmt_signed(min_delta)}.",
        f"Cambio al final de la sesión: {_fmt_signed(final_delta)}.",
    ]
    if max_rate is not None:
        evidence.append(f"Velocidad máxima de cambio: {max_rate:.3f} °C/s.")
    evidence.append(f"Umbral de cambio significativo: {stable_threshold_c:.2f} °C.")
    prediction, reaction_confidence, reaction_evidence = _predict_reaction_family(
        category, experiment, max_delta, min_delta
    )

    return ThermalInterpretation(
        category=category,
        label=label,
        confidence=confidence,
        summary=summary,
        evidence=tuple(evidence),
        warnings=warnings,
        reaction_prediction=prediction,
        reaction_confidence=reaction_confidence,
        reaction_evidence=reaction_evidence,
        max_delta_c=max_delta,
        min_delta_c=min_delta,
        max_rate_c_per_s=max_rate,
    )
