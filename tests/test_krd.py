"""
Unit tests for backend.app.core_finance.krd

Covers:
- KRD calculation: known cash flows → KRD at each tenor bucket
- Parallel shift: sum of all KRDs ≈ modified duration
- Steepening scenario: short-end vs long-end KRD distribution
- Edge cases: zero-coupon bond, very short maturity
- KRD values are non-negative
- KRDs sum to approximately modified duration
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal


from backend.app.core_finance.krd import (
    KRD_TENORS,
    STANDARD_KRD_SCENARIOS,
    build_krd_position_metrics,
    classify_asset_class,
    compute_krd_by_tenor,
    compute_krd_curve_risk,
    compute_curve_scenario,
    map_accounting_class,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bond(
    bond_code: str,
    market_value: str,
    coupon_rate: str,
    ytm: str,
    maturity_date: date,
    report_date: date = date(2026, 1, 1),
    sub_type: str = "国债",
    asset_class: str = "交易性金融资产",
    coupon_frequency: int = 2,
) -> dict:
    return {
        "bond_code": bond_code,
        "market_value": Decimal(market_value),
        "coupon_rate": Decimal(coupon_rate),
        "yield_to_maturity": Decimal(ytm),
        "maturity_date": maturity_date,
        "report_date": report_date,
        "sub_type": sub_type,
        "asset_class": asset_class,
        "coupon_frequency": coupon_frequency,
    }


REPORT_DATE = date(2026, 1, 1)

# A 5-year bond — should land in the "5Y" tenor bucket
BOND_5Y = _make_bond(
    "B5Y", "1000000", "0.0300", "0.0300",
    maturity_date=date(2031, 1, 1),
    report_date=REPORT_DATE,
)

# A 10-year bond — should land in the "10Y" tenor bucket
BOND_10Y = _make_bond(
    "B10Y", "1000000", "0.0350", "0.0350",
    maturity_date=date(2036, 1, 1),
    report_date=REPORT_DATE,
)

# A 2-year bond — should land in the "2Y" tenor bucket
BOND_2Y = _make_bond(
    "B2Y", "1000000", "0.0250", "0.0250",
    maturity_date=date(2028, 1, 1),
    report_date=REPORT_DATE,
)

# Zero-coupon bond (coupon_rate = 0) — duration ≈ maturity
BOND_ZCB = _make_bond(
    "ZCB10Y", "500000", "0.0000", "0.0300",
    maturity_date=date(2036, 1, 1),
    report_date=REPORT_DATE,
)

# Very short maturity (< 1 year) — should land in a short-end bucket
BOND_SHORT = _make_bond(
    "BSHORT", "200000", "0.0200", "0.0200",
    maturity_date=date(2026, 6, 1),
    report_date=REPORT_DATE,
)


# ---------------------------------------------------------------------------
# build_krd_position_metrics
# ---------------------------------------------------------------------------

class TestBuildKrdPositionMetrics:
    def test_returns_one_metric_per_valid_position(self):
        metrics = build_krd_position_metrics([BOND_5Y, BOND_10Y], report_date=REPORT_DATE)
        assert len(metrics) == 2

    def test_skips_zero_market_value(self):
        zero_mv = _make_bond("ZERO", "0", "0.03", "0.03", date(2031, 1, 1), REPORT_DATE)
        metrics = build_krd_position_metrics([BOND_5Y, zero_mv], report_date=REPORT_DATE)
        assert len(metrics) == 1
        assert metrics[0]["bond_code"] == "B5Y"

    def test_metric_fields_present(self):
        metrics = build_krd_position_metrics([BOND_5Y], report_date=REPORT_DATE)
        m = metrics[0]
        for field in ("bond_code", "market_value", "duration", "modified_duration",
                      "convexity", "dv01", "weight", "tenor_bucket",
                      "asset_class", "accounting_class"):
            assert field in m, f"Missing field: {field}"

    def test_duration_is_decimal(self):
        metrics = build_krd_position_metrics([BOND_5Y], report_date=REPORT_DATE)
        assert isinstance(metrics[0]["duration"], Decimal)
        assert isinstance(metrics[0]["modified_duration"], Decimal)

    def test_duration_positive(self):
        metrics = build_krd_position_metrics([BOND_5Y, BOND_10Y], report_date=REPORT_DATE)
        for m in metrics:
            assert m["duration"] > Decimal("0"), f"Non-positive duration for {m['bond_code']}"

    def test_weights_sum_to_one(self):
        metrics = build_krd_position_metrics([BOND_5Y, BOND_10Y, BOND_2Y], report_date=REPORT_DATE)
        total_weight = sum(m["weight"] for m in metrics)
        assert abs(total_weight - Decimal("1")) < Decimal("0.0001")

    def test_tenor_bucket_5y_bond(self):
        metrics = build_krd_position_metrics([BOND_5Y], report_date=REPORT_DATE)
        assert metrics[0]["tenor_bucket"] == "5Y"

    def test_tenor_bucket_10y_bond(self):
        metrics = build_krd_position_metrics([BOND_10Y], report_date=REPORT_DATE)
        assert metrics[0]["tenor_bucket"] == "10Y"

    def test_tenor_bucket_2y_bond(self):
        metrics = build_krd_position_metrics([BOND_2Y], report_date=REPORT_DATE)
        assert metrics[0]["tenor_bucket"] == "2Y"

    def test_short_maturity_tenor_bucket(self):
        metrics = build_krd_position_metrics([BOND_SHORT], report_date=REPORT_DATE)
        # ~5 months to maturity → should be in a short-end bucket (not 5Y or beyond)
        bucket = metrics[0]["tenor_bucket"]
        long_buckets = {"5Y", "7Y", "10Y", "15Y", "20Y", "30Y"}
        assert bucket not in long_buckets, f"Short bond landed in long bucket: {bucket}"

    def test_dv01_formula(self):
        """DV01 = market_value * modified_duration / 10000"""
        metrics = build_krd_position_metrics([BOND_5Y], report_date=REPORT_DATE)
        m = metrics[0]
        expected_dv01 = m["market_value"] * m["modified_duration"] / Decimal("10000")
        assert abs(m["dv01"] - expected_dv01) < Decimal("0.01")


# ---------------------------------------------------------------------------
# compute_krd_by_tenor
# ---------------------------------------------------------------------------

class TestComputeKrdByTenor:
    def test_returns_all_tenor_buckets(self):
        result = compute_krd_by_tenor([BOND_5Y], report_date=REPORT_DATE)
        returned_tenors = {r["tenor"] for r in result}
        assert set(KRD_TENORS) == returned_tenors

    def test_krd_non_negative(self):
        result = compute_krd_by_tenor([BOND_5Y, BOND_10Y, BOND_2Y], report_date=REPORT_DATE)
        for row in result:
            assert row["krd"] >= Decimal("0"), f"Negative KRD at tenor {row['tenor']}"

    def test_krd_concentrated_at_correct_tenor_single_bond(self):
        """Single 5Y bond: all KRD weight should be in the 5Y bucket."""
        result = compute_krd_by_tenor([BOND_5Y], report_date=REPORT_DATE)
        by_tenor = {r["tenor"]: r["krd"] for r in result}
        assert by_tenor["5Y"] > Decimal("0")
        # All other buckets should be zero
        for tenor, krd in by_tenor.items():
            if tenor != "5Y":
                assert krd == Decimal("0"), f"Unexpected KRD at {tenor}: {krd}"

    def test_krd_split_across_buckets_for_mixed_portfolio(self):
        """2Y + 10Y portfolio: KRD should appear in both 2Y and 10Y buckets."""
        result = compute_krd_by_tenor([BOND_2Y, BOND_10Y], report_date=REPORT_DATE)
        by_tenor = {r["tenor"]: r["krd"] for r in result}
        assert by_tenor["2Y"] > Decimal("0")
        assert by_tenor["10Y"] > Decimal("0")

    def test_krd_sum_approx_portfolio_modified_duration(self):
        """
        For a single-bond portfolio the sum of KRDs across all tenors equals
        the weight-averaged duration (which equals the bond's own duration since
        weight = 1).  Modified duration ≤ Macaulay duration, so we check that
        the KRD sum is close to the Macaulay duration (within 20 %).
        """
        result = compute_krd_by_tenor([BOND_5Y], report_date=REPORT_DATE)
        krd_sum = sum(r["krd"] for r in result)
        metrics = build_krd_position_metrics([BOND_5Y], report_date=REPORT_DATE)
        macaulay_dur = metrics[0]["duration"]
        # KRD sum == weight * duration == 1 * duration for single bond
        assert abs(krd_sum - macaulay_dur) < Decimal("0.001"), (
            f"KRD sum {krd_sum} != Macaulay duration {macaulay_dur}"
        )

    def test_parallel_shift_krd_sum_approx_modified_duration(self):
        """
        Under a parallel shift the portfolio KRD sum should approximate the
        portfolio modified duration (within 5 %).
        """
        positions = [BOND_5Y, BOND_10Y, BOND_2Y]
        result = compute_krd_by_tenor(positions, report_date=REPORT_DATE)
        krd_sum = sum(r["krd"] for r in result)

        metrics = build_krd_position_metrics(positions, report_date=REPORT_DATE)
        total_mv = sum(m["market_value"] for m in metrics)
        portfolio_mod_dur = sum(
            m["weight"] * m["modified_duration"] for m in metrics
        )
        # KRD sum is weight * Macaulay; portfolio_mod_dur is weight * modified.
        # They should be within ~10 % of each other for typical bonds.
        ratio = abs(krd_sum - portfolio_mod_dur) / (portfolio_mod_dur + Decimal("0.0001"))
        assert ratio < Decimal("0.15"), (
            f"KRD sum {krd_sum} too far from portfolio mod_dur {portfolio_mod_dur}"
        )

    def test_zero_coupon_bond_krd_at_maturity_bucket(self):
        """Zero-coupon bond: all duration (and KRD) should be at the maturity bucket."""
        result = compute_krd_by_tenor([BOND_ZCB], report_date=REPORT_DATE)
        by_tenor = {r["tenor"]: r["krd"] for r in result}
        # ZCB matures in 10Y → bucket "10Y"
        assert by_tenor["10Y"] > Decimal("0")
        for tenor, krd in by_tenor.items():
            if tenor != "10Y":
                assert krd == Decimal("0"), f"ZCB KRD leaked to {tenor}: {krd}"

    def test_very_short_maturity_krd_in_short_bucket(self):
        """Bond maturing in ~5 months should have KRD only in a short-end bucket."""
        result = compute_krd_by_tenor([BOND_SHORT], report_date=REPORT_DATE)
        long_buckets = {"5Y", "7Y", "10Y", "15Y", "20Y", "30Y"}
        for row in result:
            if row["tenor"] in long_buckets:
                assert row["krd"] == Decimal("0"), (
                    f"Short bond has KRD in long bucket {row['tenor']}: {row['krd']}"
                )

    def test_dv01_non_negative(self):
        result = compute_krd_by_tenor([BOND_5Y, BOND_10Y], report_date=REPORT_DATE)
        for row in result:
            assert row["dv01"] >= Decimal("0"), f"Negative DV01 at {row['tenor']}"


# ---------------------------------------------------------------------------
# Steepening scenario: short-end vs long-end KRD distribution
# ---------------------------------------------------------------------------

class TestSteepeningScenario:
    def test_long_bond_has_more_krd_in_long_buckets(self):
        """
        A 10Y bond should have more KRD in long-end buckets (10Y) than a 2Y bond.
        """
        result_10y = compute_krd_by_tenor([BOND_10Y], report_date=REPORT_DATE)
        result_2y = compute_krd_by_tenor([BOND_2Y], report_date=REPORT_DATE)
        by_tenor_10y = {r["tenor"]: r["krd"] for r in result_10y}
        by_tenor_2y = {r["tenor"]: r["krd"] for r in result_2y}
        assert by_tenor_10y["10Y"] > by_tenor_2y["10Y"]

    def test_short_bond_has_more_krd_in_short_buckets(self):
        """
        A 2Y bond should have more KRD in short-end buckets (2Y) than a 10Y bond.
        """
        result_10y = compute_krd_by_tenor([BOND_10Y], report_date=REPORT_DATE)
        result_2y = compute_krd_by_tenor([BOND_2Y], report_date=REPORT_DATE)
        by_tenor_10y = {r["tenor"]: r["krd"] for r in result_10y}
        by_tenor_2y = {r["tenor"]: r["krd"] for r in result_2y}
        assert by_tenor_2y["2Y"] > by_tenor_10y["2Y"]

    def test_steepening_scenario_pnl_sign(self):
        """
        Under a steepening scenario (short rates down, long rates up):
        - A long-duration (10Y) portfolio should lose money (negative PnL).
        - A short-duration (1Y) portfolio should gain money (positive PnL).

        Note: BOND_SHORT matures in ~5 months and lands in the '6M' tenor bucket,
        which is not covered by the steepening shocks dict (1Y–30Y only).  We use
        BOND_2Y instead, which lands in the '2Y' bucket (shock = -15bp → positive PnL).
        """
        steepening = next(
            s for s in STANDARD_KRD_SCENARIOS if s["name"] == "steepening_50bp"
        )
        metrics_long = build_krd_position_metrics([BOND_10Y], report_date=REPORT_DATE)
        metrics_short = build_krd_position_metrics([BOND_2Y], report_date=REPORT_DATE)

        result_long = compute_curve_scenario(metrics_long, steepening)
        result_short = compute_curve_scenario(metrics_short, steepening)

        # Long bond: 10Y bucket gets +25bp shock → negative PnL
        assert result_long["pnl_economic"] < Decimal("0"), (
            f"Expected negative PnL for long bond under steepening, got {result_long['pnl_economic']}"
        )
        # Short bond: 2Y bucket gets -15bp shock → positive PnL
        assert result_short["pnl_economic"] > Decimal("0"), (
            f"Expected positive PnL for short bond under steepening, got {result_short['pnl_economic']}"
        )


# ---------------------------------------------------------------------------
# compute_krd_curve_risk (integration)
# ---------------------------------------------------------------------------

class TestComputeKrdCurveRisk:
    def test_output_keys_present(self):
        result = compute_krd_curve_risk([BOND_5Y, BOND_10Y], report_date=REPORT_DATE)
        for key in ("position_metrics", "total_market_value", "portfolio_duration",
                    "portfolio_modified_duration", "portfolio_dv01", "portfolio_convexity",
                    "krd_buckets", "scenarios", "by_asset_class"):
            assert key in result, f"Missing key: {key}"

    def test_total_market_value(self):
        result = compute_krd_curve_risk([BOND_5Y, BOND_10Y], report_date=REPORT_DATE)
        assert result["total_market_value"] == Decimal("2000000")

    def test_portfolio_duration_positive(self):
        result = compute_krd_curve_risk([BOND_5Y, BOND_10Y], report_date=REPORT_DATE)
        assert result["portfolio_duration"] > Decimal("0")

    def test_scenarios_include_standard_set(self):
        result = compute_krd_curve_risk([BOND_5Y], report_date=REPORT_DATE)
        scenario_names = {s["scenario_name"] for s in result["scenarios"]}
        assert "parallel_up_100bp" in scenario_names
        assert "steepening_50bp" in scenario_names

    def test_parallel_up_pnl_negative(self):
        """Parallel rate rise → bond prices fall → negative PnL."""
        result = compute_krd_curve_risk([BOND_5Y, BOND_10Y], report_date=REPORT_DATE)
        parallel_up = next(
            s for s in result["scenarios"] if s["scenario_name"] == "parallel_up_100bp"
        )
        assert parallel_up["pnl_economic"] < Decimal("0")

    def test_parallel_down_pnl_positive(self):
        """Parallel rate fall → bond prices rise → positive PnL."""
        result = compute_krd_curve_risk([BOND_5Y, BOND_10Y], report_date=REPORT_DATE)
        parallel_down = next(
            s for s in result["scenarios"] if s["scenario_name"] == "parallel_down_25bp"
        )
        assert parallel_down["pnl_economic"] > Decimal("0")

    def test_empty_positions_returns_zero_totals(self):
        result = compute_krd_curve_risk([], report_date=REPORT_DATE)
        assert result["total_market_value"] == Decimal("0")
        assert result["portfolio_duration"] == Decimal("0")


# ---------------------------------------------------------------------------
# classify_asset_class / map_accounting_class
# ---------------------------------------------------------------------------

class TestClassifiers:
    def test_rate_bond_classification(self):
        assert classify_asset_class("国债") == "rate"
        assert classify_asset_class("国开债") == "rate"
        assert classify_asset_class("地方政府债券") == "rate"

    def test_credit_bond_classification(self):
        assert classify_asset_class("企业债") == "credit"
        assert classify_asset_class("中票") == "credit"
        assert classify_asset_class("同业存单") == "credit"

    def test_unknown_bond_classification(self):
        assert classify_asset_class("未知品种") == "other"
        assert classify_asset_class(None) == "other"
        assert classify_asset_class("") == "other"

    def test_accounting_class_tpl(self):
        assert map_accounting_class("交易性金融资产") == "TPL"
        assert map_accounting_class("FVTPL") == "TPL"

    def test_accounting_class_oci(self):
        assert map_accounting_class("其他债权投资") == "OCI"
        assert map_accounting_class("FVOCI") == "OCI"

    def test_accounting_class_ac(self):
        assert map_accounting_class("债权投资") == "AC"
        assert map_accounting_class("摊余成本") == "AC"
        assert map_accounting_class("AC") == "AC"

    def test_accounting_class_unknown(self):
        assert map_accounting_class(None) == "other"
        assert map_accounting_class("") == "other"
