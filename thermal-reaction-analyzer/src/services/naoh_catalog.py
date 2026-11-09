"""Catálogo de ensayos escolares con NaOH y predicción según ΔT.

Referencias de comportamiento térmico (laboratorios escolares):
- Disolución de NaOH(s) en agua: exotérmica; ΔT típico de varios °C hasta >10 °C.
- Neutralización NaOH(aq) + HCl(aq): exotérmica; ΔT típico ~5–10 °C en mezclas ~1 M.
- Neutralización NaOH + ácido acético: también exotérmica, un poco menor que con HCl.
- NaOH(s) + HCl(aq): disolución + neutralización, ΔT mayor.

La temperatura superficial no identifica una reacción exacta; el catálogo solo
ordena las familias compatibles con NaOH y con el signo de ΔT.
"""

from __future__ import annotations

import unicodedata

from src.models.experiment import Experiment

PROTOCOLS: dict[str, dict[str, str]] = {
    "disolucion_agua": {
        "label": "Disolución de NaOH(s) en agua",
        "reagents": "NaOH sólido + H2O",
        "assay": "Disolución de hidróxido de sodio",
        "equation": "NaOH(s) → Na+(aq) + OH-(aq)",
        "hint": "Exotérmica. En laboratorio escolar el agua suele calentarse varios °C.",
    },
    "neutralizacion_hcl": {
        "label": "Neutralización NaOH + HCl",
        "reagents": "NaOH(aq) + HCl(aq)",
        "assay": "Neutralización ácido-base",
        "equation": "NaOH(aq) + HCl(aq) → NaCl(aq) + H2O(l)",
        "hint": "Exotérmica. Con soluciones ~1 M el ΔT suele estar cerca de 5–10 °C.",
    },
    "neutralizacion_acetico": {
        "label": "Neutralización NaOH + ácido acético",
        "reagents": "NaOH(aq) + CH3COOH(aq)",
        "assay": "Neutralización con ácido débil",
        "equation": "NaOH(aq) + CH3COOH(aq) → CH3COONa(aq) + H2O(l)",
        "hint": "Exotérmica, un poco menor que la de HCl porque el ácido es débil.",
    },
    "solido_hcl": {
        "label": "NaOH(s) + HCl(aq)",
        "reagents": "NaOH sólido + HCl(aq)",
        "assay": "Disolución y neutralización",
        "equation": "NaOH(s) + HCl(aq) → NaCl(aq) + H2O(l)",
        "hint": "Exotérmica más intensa: suma la disolución y la formación de agua.",
    },
    "otro_naoh": {
        "label": "Otro ensayo con NaOH",
        "reagents": "NaOH",
        "assay": "Ensayo con hidróxido de sodio",
        "equation": "",
        "hint": "Los procesos típicos con NaOH en este laboratorio son exotérmicos.",
    },
    "control": {
        "label": "Ensayo control (sin reacción)",
        "reagents": "agua o blanco",
        "assay": "Control",
        "equation": "",
        "hint": "Sirve para comparar. No debe interpretarse como una reacción de NaOH.",
    },
    "otra_reaccion": {
        "label": "Otra reacción (escribir el nombre)",
        "reagents": "",
        "assay": "Otro proceso",
        "equation": "",
        "hint": "Registra el nombre y las sustancias. El ΔT no identifica la reacción por sí solo.",
    },
}


def protocol_keys() -> list[str]:
    return list(PROTOCOLS)


def protocol_label(key: str) -> str:
    return PROTOCOLS.get(key, PROTOCOLS["otro_naoh"])["label"]


def _fold(texto: str) -> str:
    normalized = unicodedata.normalize("NFD", texto.lower())
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def infer_protocol(experiment: Experiment | None) -> str:
    if experiment is not None:
        declared = str(experiment.parameters.get("protocolo") or "")
        if declared in PROTOCOLS:
            return declared
        blob = _fold(
            " ".join(
                (
                    experiment.assay_type,
                    experiment.reagents,
                    experiment.description,
                    experiment.observations,
                )
            )
        )
        if "hcl" in blob or "clorhidrico" in blob:
            return "neutralizacion_hcl"
        if "acetico" in blob or "vinagre" in blob or "ch3cooh" in blob:
            return "neutralizacion_acetico"
        if "disolu" in blob or "agua" in blob:
            return "disolucion_agua"
        if "naoh" in blob:
            return "otro_naoh"
    return "otro_naoh"


def predict_naoh_family(
    category: str,
    experiment: Experiment | None,
    max_delta_c: float | None = None,
    min_delta_c: float | None = None,
) -> tuple[str, str, tuple[str, ...]]:
    """Predice la familia de reacción NaOH más compatible con ΔT y el protocolo."""
    protocol_key = infer_protocol(experiment)
    protocol = PROTOCOLS.get(protocol_key, PROTOCOLS["otro_naoh"])
    chosen = protocol["label"]
    equation = protocol["equation"]
    delta = max_delta_c if max_delta_c is not None else 0.0
    drop = abs(min_delta_c) if min_delta_c is not None else 0.0

    if category in {"insuficiente", "estable"}:
        return (
            f"Aún no hay cambio térmico suficiente. Protocolo: {chosen}.",
            "baja",
            (
                "Espera a disolver o mezclar el NaOH.",
                protocol["hint"],
            ),
        )

    if category == "endotermico_posible" or (drop >= 0.8 and drop > delta):
        return (
            "El enfriamiento no coincide con los ensayos típicos de NaOH "
            "(disolución y neutralización son exotérmicos).",
            "media",
            (
                f"Se observó una bajada térmica de {drop:.2f} °C.",
                "Revisa si el sólido era NaOH o si hay evaporación/ambiente más frío.",
                protocol["hint"],
            ),
        )

    if delta >= 10:
        prediction = (
            f"Compatible con {chosen}: calentamiento fuerte, típico de NaOH(s) en agua "
            "o de NaOH(s) + ácido."
        )
        confidence = "alta" if protocol_key in {"disolucion_agua", "solido_hcl"} else "media-alta"
    elif delta >= 4:
        prediction = (
            f"Compatible con {chosen}: calentamiento moderado, típico de neutralización "
            "NaOH + ácido o de una disolución diluida."
        )
        confidence = "alta" if protocol_key.startswith("neutralizacion") else "media-alta"
    elif delta >= 0.8:
        prediction = (
            f"Inicio de calentamiento compatible con {chosen}. "
            "Sigue el ensayo; el ΔT aún es pequeño."
        )
        confidence = "media"
    else:
        prediction = f"Cambio térmico leve. Protocolo declarado: {chosen}."
        confidence = "baja"

    evidence = [
        f"Protocolo elegido: {chosen}.",
        f"ΔT máximo respecto a la línea base: {delta:+.2f} °C.",
        protocol["hint"],
        "Predicción orientativa: la FLIR ve temperatura superficial, no entalpía.",
    ]
    if equation:
        evidence.insert(1, f"Reacción de referencia: {equation}.")
    return prediction, confidence, tuple(evidence)
