"""Nombres de archivo seguros para distinguir experimentos."""

from __future__ import annotations

import re
import unicodedata


def slugify(name: str, fallback: str = "ensayo") -> str:
    """Convierte un nombre visible en un identificador de archivo."""
    normalized = unicodedata.normalize("NFD", (name or "").strip())
    without_marks = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", without_marks).strip("_").lower()
    if not slug:
        slug = fallback
    return slug[:40]


def file_stem(name: str, experiment_id: str) -> str:
    return f"{slugify(name)}_{experiment_id}"
