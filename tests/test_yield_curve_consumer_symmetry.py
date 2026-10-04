"""
Single-point parity between curve consumers (see docs/CURRENT_EXECUTION_UPDATE_2026-04-12.md).

`_resolve_curve_for_service` must use `format_yield_curve_latest_fallback_warning` from
`yield_curve_repo` so fallback warnings stay single-sourced.
"""

from __future__ import annotations

from tests.helpers import ROOT


def test_read_curve_preserves_source_nodes_and_independent_node_shift():
    from decimal import Decimal

    from backend.app.core_finance.bond_analytics.common import build_full_curve
    from backend.app.core_finance.bond_analytics.read_models import _CurveRateLookup as BondLookup
    from backend.app.core_finance.pnl_bridge import _CurveRateLookup as BridgeLookup

    curve = {k: Decimal(v) for k, v in {"1M": "1.7", "1Y": "2", "5Y": "2.5", "10Y": "3", "15Y": "4", "20Y": "3.5", "30Y": "4"}.items()}
    full = build_full_curve(curve)
    assert full["1M"] == Decimal("1.7")
    assert full["15Y"] == Decimal("4")
    for lookup in (BondLookup(), BridgeLookup()):
        target = Decimal("15") if isinstance(lookup, BondLookup) else 15.0
        month = Decimal(1) / 12 if isinstance(lookup, BondLookup) else 1 / 12
        assert lookup.rate(curve, target) == Decimal("4")
        assert lookup.rate(curve, month) == Decimal("1.7")
        shifted = dict(curve, **{"15Y": Decimal("4.1")})
        assert lookup.rate(shifted, target) - lookup.rate(curve, target) == Decimal("0.1")


def test_read_curve_linear_missing_nodes_and_consumer_parity():
    from decimal import Decimal

    from backend.app.core_finance.bond_analytics.common import build_full_curve
    from backend.app.core_finance.bond_analytics.read_models import _CurveRateLookup as BondLookup
    from backend.app.core_finance.pnl_bridge import _CurveRateLookup as BridgeLookup

    curve = {"3M": Decimal("1.625"), "1Y": Decimal("2"), "5Y": Decimal("4"), "10Y": Decimal("6.5"), "30Y": Decimal("16.5")}
    assert build_full_curve(curve)["3Y"] == Decimal("3")
    for years, expected in [(Decimal("3"), Decimal("3")), (Decimal("7.5"), Decimal("5.25"))]:
        assert BondLookup().rate(curve, years) == expected
        assert BridgeLookup().rate(curve, float(years)) == expected
    nonlinear = {"1Y": Decimal("2"), "5Y": Decimal("2.5"), "15Y": Decimal("4"), "30Y": Decimal("3")}
    for years in (Decimal("3"), Decimal("12"), Decimal("18")):
        assert BondLookup().rate(nonlinear, years) == BridgeLookup().rate(nonlinear, float(years))


def test_pnl_bridge_and_bond_analytics_import_shared_fallback_formatter():
    paths = [
        ROOT / "backend" / "app" / "services" / "pnl_bridge_service.py",
        ROOT / "backend" / "app" / "services" / "bond_analytics_service.py",
    ]
    needle = "format_yield_curve_latest_fallback_warning"
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert needle in text, path
        assert "from backend.app.repositories.yield_curve_repo import" in text
    repo_text = (ROOT / "backend" / "app" / "repositories" / "yield_curve_repo.py").read_text(encoding="utf-8")
    assert "def format_yield_curve_latest_fallback_warning" in repo_text


_CORRUPT_LINEAGE_SUBSTRING = (
    "Corrupt or inconsistent {curve_type} curve snapshot lineage for trade_date="
)


def test_pnl_bridge_and_bond_analytics_share_corrupt_lineage_error_template():
    paths = [
        ROOT / "backend" / "app" / "services" / "pnl_bridge_service.py",
        ROOT / "backend" / "app" / "services" / "bond_analytics_service.py",
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert text.count(_CORRUPT_LINEAGE_SUBSTRING) == 2, path
