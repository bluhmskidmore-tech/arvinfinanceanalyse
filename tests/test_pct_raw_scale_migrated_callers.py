"""Migrated callers must declare pct raw scale explicitly (raw_scale="percent").

Covers the high-risk callers whose percent-point inputs can legitimately fall
into (0, 1] — where the legacy abs(raw) > 1 heuristic in
``backend.app.schemas.common_numeric._normalize_numeric_raw`` would misread
them as decimal ratios (0.85% rendered as 85.00%).
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.services.bond_analytics_service import _pct_points_numeric_json
from backend.app.services.dashboard_service import _pct_change_numeric


class TestDashboardPctChangeNumeric:
    def test_change_above_one_percent_unchanged(self) -> None:
        # +5% change: 105 vs 100.
        numeric = _pct_change_numeric(Decimal("5"), Decimal("100"))
        assert numeric.raw == pytest.approx(0.05)
        assert numeric.display == "+5.00%"

    def test_sub_one_percent_change_is_percent_points(self) -> None:
        # +0.5% change must not be kept as a 50% ratio.
        numeric = _pct_change_numeric(Decimal("0.5"), Decimal("100"))
        assert numeric.raw == pytest.approx(0.005)
        assert numeric.display == "+0.50%"

    def test_zero_change(self) -> None:
        numeric = _pct_change_numeric(Decimal("0"), Decimal("100"))
        assert numeric.raw == pytest.approx(0.0)
        assert numeric.display == "+0.00%"

    def test_non_positive_previous_returns_null(self) -> None:
        numeric = _pct_change_numeric(Decimal("1"), Decimal("0"))
        assert numeric.raw is None
        assert numeric.display == "—"


class TestBondAnalyticsPctPointsNumericJson:
    def test_above_one_percent_points(self) -> None:
        out = _pct_points_numeric_json(Decimal("2.38"))
        assert out["raw"] == pytest.approx(0.0238)
        assert out["display"] == "+2.38%"
        assert out["unit"] == "pct"

    def test_sub_one_percent_points(self) -> None:
        # A 0.85% weighted YTM / period return must not become 85%.
        out = _pct_points_numeric_json(Decimal("0.85"))
        assert out["raw"] == pytest.approx(0.0085)
        assert out["display"] == "+0.85%"

    def test_zero(self) -> None:
        out = _pct_points_numeric_json(Decimal("0"))
        assert out["raw"] == pytest.approx(0.0)

    def test_none_is_null_numeric(self) -> None:
        out = _pct_points_numeric_json(None)
        assert out["raw"] is None
        assert out["display"] == "—"
