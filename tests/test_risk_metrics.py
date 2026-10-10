"""Golden tests for core_finance.risk_metrics (HHI 0–10000 scale)."""

from __future__ import annotations

from decimal import Decimal

from tests.helpers import load_module


def _mod():
    return load_module(
        "backend.app.core_finance.risk_metrics",
        "backend/app/core_finance/risk_metrics.py",
    )


# ---------------------------------------------------------------------------
# calc_hhi — scale is Σ share² × 10000 (classic HHI), not 0–1
# ---------------------------------------------------------------------------


def test_calc_hhi_single_position_is_10000():
    mod = _mod()
    hhi = mod.calc_hhi(
        [{"issuer_id": "A", "market_value": "100"}],
        group_by="issuer",
    )
    assert hhi == Decimal("10000")


def test_calc_hhi_n_equal_weight_is_10000_over_n():
    mod = _mod()
    n = 4
    positions = [
        {"issuer_id": f"I{i}", "market_value": "25"} for i in range(n)
    ]
    hhi = mod.calc_hhi(positions, group_by="issuer")
    # n equal shares → n × (1/n)² × 10000 = 10000/n
    assert hhi == Decimal("10000") / Decimal(n)


def test_calc_hhi_known_uneven_distribution():
    mod = _mod()
    # shares 0.6, 0.3, 0.1 → Σ s² = 0.36 + 0.09 + 0.01 = 0.46 → ×10000 = 4600
    hhi = mod.calc_hhi(
        [
            {"issuer_id": "A", "market_value": "60"},
            {"issuer_id": "B", "market_value": "30"},
            {"issuer_id": "C", "market_value": "10"},
        ],
        group_by="issuer",
    )
    assert hhi == Decimal("4600")


def test_calc_hhi_aggregates_same_issuer():
    mod = _mod()
    # two rows same issuer → single group → HHI = 10000
    hhi = mod.calc_hhi(
        [
            {"issuer_id": "A", "market_value": "40"},
            {"issuer_id": "A", "market_value": "60"},
        ],
        group_by="issuer",
    )
    assert hhi == Decimal("10000")


def test_calc_hhi_instrument_group_by():
    mod = _mod()
    hhi = mod.calc_hhi(
        [
            {"instrument_id": "X", "market_value": "50"},
            {"instrument_id": "Y", "market_value": "50"},
        ],
        group_by="instrument",
    )
    assert hhi == Decimal("5000")


def test_calc_hhi_empty_input_returns_zero():
    mod = _mod()
    assert mod.calc_hhi([]) == Decimal("0")


def test_calc_hhi_zero_market_value_returns_zero():
    mod = _mod()
    assert (
        mod.calc_hhi(
            [
                {"issuer_id": "A", "market_value": "0"},
                {"issuer_id": "B", "market_value": "0"},
            ]
        )
        == Decimal("0")
    )


def test_calc_hhi_negative_market_value_uses_abs():
    """Documented semantics: share 按绝对值归一；负市值不报错，按 |MV| 入权。"""
    mod = _mod()
    hhi = mod.calc_hhi(
        [
            {"issuer_id": "A", "market_value": "-60"},
            {"issuer_id": "B", "market_value": "40"},
        ],
        group_by="issuer",
    )
    # |−60| + 40 = 100 → shares 0.6² + 0.4² = 0.52 → 5200
    assert hhi == Decimal("5200")


def test_calc_hhi_missing_weight_treated_as_zero():
    mod = _mod()
    hhi = mod.calc_hhi(
        [
            {"issuer_id": "A"},  # missing market_value → 0
            {"issuer_id": "B", "market_value": "100"},
        ]
    )
    assert hhi == Decimal("10000")


# ---------------------------------------------------------------------------
# credit_concentration_check
# ---------------------------------------------------------------------------


def test_credit_concentration_check_levels_and_alerts():
    mod = _mod()

    ok = mod.credit_concentration_check(Decimal("500"), None, None)
    assert ok["level"] == "OK"
    assert ok["alerts"] == []

    medium = mod.credit_concentration_check(Decimal("1200"), None, None)
    assert medium["level"] == "MEDIUM"

    warning = mod.credit_concentration_check(Decimal("2000"), None, None)
    assert warning["level"] == "WARNING"

    critical = mod.credit_concentration_check(Decimal("3000"), None, None)
    assert critical["level"] == "CRITICAL"

    # issuer > 10% lifts OK → MEDIUM; industry > 20% lifts to WARNING
    with_alerts = mod.credit_concentration_check(
        Decimal("500"),
        Decimal("12"),
        Decimal("25"),
    )
    assert with_alerts["level"] == "WARNING"
    assert "issuer_concentration_gt_10pct" in with_alerts["alerts"]
    assert "industry_concentration_gt_20pct" in with_alerts["alerts"]
    assert with_alerts["hhi"] == Decimal("500")


# ---------------------------------------------------------------------------
# weighted_avg_ytm
# ---------------------------------------------------------------------------


def test_weighted_avg_ytm_market_value_weighted():
    mod = _mod()
    # (100×0.03 + 300×0.05) / 400 = 0.045
    ytm = mod.weighted_avg_ytm(
        [
            {"market_value": "100", "yield_to_maturity": "0.03"},
            {"market_value": "300", "yield_to_maturity": "0.05"},
        ]
    )
    assert ytm == Decimal("0.045")


def test_weighted_avg_ytm_skips_missing_ytm_and_empty_is_zero():
    mod = _mod()
    ytm = mod.weighted_avg_ytm(
        [
            {"market_value": "100", "yield_to_maturity": None},
            {"market_value": "200", "yield_to_maturity": "0.04"},
        ]
    )
    assert ytm == Decimal("0.04")
    assert mod.weighted_avg_ytm([]) == Decimal("0")


# ---------------------------------------------------------------------------
# stress_test_pnl
# ---------------------------------------------------------------------------


def test_stress_test_pnl_neg_dv01_times_shock_bp():
    mod = _mod()
    result = mod.stress_test_pnl(Decimal("1.5"), [10, -25, 0])
    assert result == [
        {"shock_bp": 10, "pnl": Decimal("-15.0")},
        {"shock_bp": -25, "pnl": Decimal("37.5")},
        {"shock_bp": 0, "pnl": Decimal("0.0")},
    ]
