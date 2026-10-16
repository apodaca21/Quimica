"""Pruebas de la región de interés."""

from __future__ import annotations

import numpy as np
import pytest

from src.services.roi_analysis import analyze_roi
from src.utils.validation import ValidationError


def test_la_roi_calcula_estadisticos_y_posiciones() -> None:
    matrix = np.zeros((4, 5), dtype=np.float64)
    matrix[1, 2] = 1.0
    matrix[1, 3] = 3.0
    matrix[2, 2] = 5.0
    matrix[2, 3] = 7.0
    stats = analyze_roi(matrix, x=2, y=1, width=2, height=2)
    assert stats.min_c == pytest.approx(1.0)
    assert stats.max_c == pytest.approx(7.0)
    assert stats.mean_c == pytest.approx(4.0)
    assert stats.std_c == pytest.approx(np.sqrt(5.0))
    assert (stats.hottest_x, stats.hottest_y) == (3, 2)
    assert (stats.coldest_x, stats.coldest_y) == (2, 1)
    assert stats.count == 4


def test_una_roi_fuera_de_limites_se_rechaza() -> None:
    matrix = np.ones((120, 160), dtype=np.float64)
    with pytest.raises(ValidationError):
        analyze_roi(matrix, x=-1, y=0, width=10, height=10)
    with pytest.raises(ValidationError):
        analyze_roi(matrix, x=150, y=0, width=20, height=10)
    with pytest.raises(ValidationError):
        analyze_roi(matrix, x=0, y=0, width=0, height=10)
