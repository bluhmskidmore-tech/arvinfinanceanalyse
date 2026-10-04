"""Independent economic counterexamples from the September calculation audit."""
from datetime import date
from decimal import Decimal

import pytest

from backend.app.core_finance.campisi import (
    aggregate_maturity_buckets, benchmark_yield_change_decimal, campisi_attribution,
    campisi_enhanced, maturity_bucket_attribution,
)
from backend.app.core_finance.pnl_attribution.workbench import build_krd_attribution
from backend.app.services.campisi_attribution_service import merge_positions


def _row(amount=1000000):
    return dict(instrument_code="SYNTHETIC", portfolio_name="P", cost_center="C",
                accounting_class="FVTPL", currency_code="CNY", market_value=amount,
                face_value=amount, coupon_rate=0, ytm=0.02, asset_class_std="AAA",
                maturity_date=date(2028, 1, 1), accrued_interest=0)


def _market(value=2):
    return {"treasury_1y": value, "treasury_3y": value, "credit_spread_aaa_3y": 50}


@pytest.mark.parametrize("end_amount", [2000000, 500000])
@pytest.mark.parametrize("calculator", [campisi_attribution, campisi_enhanced])
def test_principal_change_without_cashflows_is_excluded(end_amount, calculator):
    positions = merge_positions([_row()], [_row(end_amount)])
    result = calculator(positions, _market(), _market(2.1), date(2026, 1, 1), date(2026, 1, 31))
    totals = result["totals"] if isinstance(result, dict) else result.totals
    assert totals["total_return"] == 0  # empty covered subtotal; explicitly unavailable below
    availability = result["effect_availability"] if isinstance(result, dict) else result.effect_availability
    assert availability["position_change"]["status"] == "unavailable"
    assert availability["position_change"]["unavailable_bonds"] == 1
    assert availability["position_change"]["unavailable_market_value_start"] == 1000000
    assert availability["position_change"]["unavailable_market_value_end"] == end_amount
    assert availability["position_change"]["covered_bonds"] == 0
    rows = result["by_bond"] if isinstance(result, dict) else result.by_bond
    assert rows == []


def test_partial_principal_exclusion_does_not_dilute_or_extrapolate_covered_pnl():
    unchanged = {**_row(), "instrument_code": "STABLE"}
    positions = merge_positions([_row(), unchanged], [_row(2000000), {**unchanged, "market_value": 1000100}])
    result = campisi_attribution(positions, _market(), _market(), date(2026, 1, 1), date(2026, 1, 31))
    assert result.totals["total_return"] == 100
    assert result.totals["market_value_start"] == 1000000
    assert result.effect_availability["position_change"]["status"] == "partial"
    assert result.effect_availability["position_change"]["unavailable_bonds"] == 1
    assert [r["bond_code"] for r in result.by_bond] == ["STABLE"]
    assert result.effect_availability["position_change"]["covered_bonds"] == 1


@pytest.mark.parametrize("calculator", [campisi_attribution, campisi_enhanced])
@pytest.mark.parametrize("movement", ["sold", "bought", "replaced"])
@pytest.mark.parametrize("mixed", [False, True])
def test_single_sided_positions_are_excluded_from_coverage_and_return_denominator(calculator, movement, mixed):
    sold = {**_row(), "instrument_code": "SOLD"}
    bought = {**_row(), "instrument_code": "BOUGHT"}
    stable = {**_row(), "instrument_code": "STABLE"}
    start = [sold] if movement in {"sold", "replaced"} else []
    end = [bought] if movement in {"bought", "replaced"} else []
    excluded_count = 2 if movement == "replaced" else 1
    if mixed:
        start.append(stable)
        end.append({**stable, "market_value": 1000100})
    positions = merge_positions(start, end)
    result = calculator(positions, _market(), _market(), date(2026, 1, 1), date(2026, 1, 31))
    payload = result if isinstance(result, dict) else vars(result)
    coverage = payload["effect_availability"]["position_change"]
    assert coverage["status"] == ("partial" if mixed else "unavailable")
    assert coverage["unavailable_bonds"] == excluded_count
    assert coverage["covered_bonds"] == (1 if mixed else 0)
    assert coverage["unavailable_market_value_start"] == (1000000 if movement != "bought" else 0)
    assert coverage["unavailable_market_value_end"] == (1000000 if movement != "sold" else 0)
    assert [row["bond_code"] for row in payload["by_bond"]] == (["STABLE"] if mixed else [])
    assert payload["totals"]["market_value_start"] == (1000000 if mixed else 0)
    assert payload["totals"]["total_return"] == (100 if mixed else 0)
    if movement != "bought":
        assert any("position_start_only" in message for message in payload["diagnostics"])
    if movement != "sold":
        assert any("position_end_only" in message for message in payload["diagnostics"])
    if mixed:
        assert payload["by_asset_class"][0]["selection_effect_pct"] == Decimal("0.01")
        if calculator is campisi_attribution:
            assert payload["by_asset_class"][0]["total_return_pct"] == Decimal("0.01")
    else:
        assert payload["by_asset_class"] == []
    cached_buckets = aggregate_maturity_buckets(payload["by_bond"])
    cold_buckets = maturity_bucket_attribution(positions, _market(), _market(), date(2026, 1, 1), date(2026, 1, 31))
    assert cached_buckets == cold_buckets
    assert sum(row["market_value_start"] for row in cold_buckets.values()) == (1000000 if mixed else 0)
    assert sum(row["total_return"] for row in cold_buckets.values()) == (100 if mixed else 0)


def test_same_security_moving_accounting_class_is_not_joined_as_price_return():
    positions = merge_positions([_row()], [{**_row(), "accounting_class": "FVOCI"}])
    assert len(positions) == 2
    result = campisi_attribution(positions, _market(), _market(), date(2026, 1, 1), date(2026, 1, 31))
    assert result.totals["total_return"] == 0
    assert any("position_start_only" in d for d in result.diagnostics)
    assert any("position_end_only" in d for d in result.diagnostics)


def test_formal_bridge_zero_pnl_remains_observed_despite_changed_principal():
    from backend.app.services.campisi_attribution_service import _formal_bridge_to_campisi_result
    row = dict(instrument_code="SYNTHETIC", portfolio_name="P", cost_center="C", accounting_basis="FVTPL",
               beginning_dirty_mv=1000000, ending_dirty_mv=2000000, carry=0, roll_down=0, treasury_curve=0,
               credit_spread=0, fx_translation=0, realized_trading=0, unrealized_fv=0, manual_adjustment=0,
               actual_pnl=0, residual=0, quality_flag="ok")
    result = _formal_bridge_to_campisi_result(
        bridge_envelope={"result": {"rows": [row]}}, positions=merge_positions([_row()], [_row(2000000)]),
        start_date=date(2026, 1, 1), end_date=date(2026, 1, 31),
    )
    assert result.totals["total_return"] == 0
    assert len(result.by_bond) == 1
    assert result.effect_availability.get("position_change", {}).get("status", "ok") == "ok"


@pytest.mark.parametrize("side", ["start", "end"])
def test_missing_principal_does_not_establish_a_constant_position(side):
    start, end = _row(), _row()
    (start if side == "start" else end)["face_value"] = None
    result = campisi_attribution(merge_positions([start], [end]), _market(), _market(), date(2026, 1, 1), date(2026, 1, 31))
    assert result.by_bond == []
    assert result.effect_availability["position_change"]["status"] == "unavailable"


@pytest.mark.parametrize("start,end,expected", [("0.40", "0.45", "0.0005"), ("0.49", "0.50", "0.0001")])
def test_declared_percent_curve_does_not_guess_units_from_magnitude(start, end, expected):
    assert benchmark_yield_change_decimal(_market(start), _market(end), 2) == Decimal(expected)


@pytest.mark.parametrize("shift", [None, float("nan"), float("inf")])
def test_missing_curve_shift_is_not_observed_zero(shift):
    row = dict(instrument_code="SYNTHETIC", accounting_class="FVOCI", currency_code="CNY",
               asset_class_std="rate", tenor_bucket="5Y", market_value=1000000,
               modified_duration=2, macaulay_duration=2, convexity=0,
               maturity_date="2031-06-30", years_to_maturity=5, ytm=0.03, dv01=200)
    result = build_krd_attribution(report_date="2026-06-30", start_date="2026-05-31", end_date="2026-06-30",
                                   bond_rows_start=[row], bond_rows_end=[row], treasury_shift_bp=shift)
    assert result["total_duration_effect"] is None
    assert result["max_contribution_value"] is None
    assert result["max_contribution_tenor"] == ""
    assert result["curve_shift_type"] == "unavailable"
    assert result["calculation_status"] == "unavailable"
    assert result["buckets"][0]["duration_contribution"] is None
    assert result["buckets"][0]["contribution_pct"] is None


def test_observed_zero_curve_shift_stays_zero():
    result = build_krd_attribution(report_date="2026-06-30", start_date="2026-05-31", end_date="2026-06-30",
                                   bond_rows_start=[], bond_rows_end=[], treasury_shift_bp=0)
    assert result["total_duration_effect"] == 0
    assert result["curve_shift_type"] == "parallel"
    assert result["calculation_status"] == "complete"


@pytest.mark.parametrize("with_covered_row", [True, False])
def test_krd_status_reflects_risk_exclusions(with_covered_row):
    covered = dict(instrument_code="KNOWN", asset_class_std="rate", tenor_bucket="5Y",
                   market_value=1000000, modified_duration=2, macaulay_duration=2, convexity=0,
                   maturity_date="2031-06-30", years_to_maturity=5, ytm=0.03, dv01=200)
    excluded = {**covered, "instrument_code": "MISSING", "maturity_date": None,
                "years_to_maturity": None, "modified_duration": 0}
    rows = [excluded, covered] if with_covered_row else [excluded]
    result = build_krd_attribution(report_date="2026-06-30", start_date="2026-05-31", end_date="2026-06-30",
                                   bond_rows_start=rows, bond_rows_end=rows, treasury_shift_bp=1)
    assert result["calculation_status"] == ("partial" if with_covered_row else "unavailable")
    assert result["total_duration_effect"] == (-200 if with_covered_row else None)
