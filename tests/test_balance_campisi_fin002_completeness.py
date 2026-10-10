"""FIN002: incomplete coupon evidence cannot publish full-portfolio income.

All holdings are synthetic. Amounts are yuan at input and wan-yuan at output;
coupon rates are percentage points. No business database is read or written.
"""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from backend.app.core_finance.balance_analysis import FormalZqtzBalanceFactRow
from backend.app.core_finance.balance_analysis_workbook import _build_campisi_table
from backend.app.schemas.balance_analysis import BalanceAnalysisWorkbookTable


pytestmark = pytest.mark.unit


def _asset(
    code: str,
    coupon: Decimal | None,
    *,
    face: Decimal = Decimal("100000000"),
    bond_type: str = "企业债",
) -> FormalZqtzBalanceFactRow:
    return FormalZqtzBalanceFactRow(
        report_date=date(2026, 9, 30),
        instrument_code=code,
        instrument_name=code,
        portfolio_name="synthetic",
        cost_center="synthetic",
        account_category="",
        asset_class="FVTPL债",
        bond_type=bond_type,
        issuer_name="synthetic",
        industry_name="未分类",
        rating="AAA",
        invest_type_std="T",
        accounting_basis="FVTPL",
        position_scope="asset",
        currency_basis="CNY",
        currency_code="CNY",
        face_value_amount=face,
        market_value_amount=face,
        amortized_cost_amount=face,
        accrued_interest_amount=Decimal("0"),
        coupon_rate=coupon,
        ytm_value=None,
        maturity_date=date(2031, 9, 30),
        interest_mode="固定",
        is_issuance_like=False,
    )


def _benchmark(coupon: Decimal | None = Decimal("3"), **kwargs) -> FormalZqtzBalanceFactRow:
    return _asset("benchmark", coupon, bond_type="政策性金融债", **kwargs)


def _by_type(rows: list[FormalZqtzBalanceFactRow]) -> dict[str, dict]:
    return {row["bond_type"]: row for row in _build_campisi_table(rows)["rows"]}


def test_mixed_coupon_keeps_full_metrics_null_and_known_spread_in_same_scope() -> None:
    rows = [_benchmark(), _asset("known", Decimal("4")), _asset("missing", None)]
    result = _by_type(rows)
    corporate = result["企业债"]

    # 4% of the known one hundred million is 400 wan-yuan. It is not the full
    # two hundred million's income. Its 3% benchmark cost is only 300 wan-yuan.
    assert corporate["coupon_income_amount"] is None
    assert corporate["weighted_rate_pct"] is None
    assert corporate["spread_bp"] is None
    assert corporate["spread_income_amount"] is None
    assert corporate["share_of_income"] is None
    assert corporate["known_coupon_income_amount"] == Decimal("400")
    assert corporate["known_weighted_rate_pct"] == Decimal("4")
    assert corporate["known_spread_bp"] == Decimal("100")
    assert corporate["known_spread_income_amount"] == Decimal("100")
    assert corporate["coupon_known_balance_amount"] == Decimal("10000")
    assert corporate["coupon_known_abs_face_amount"] == Decimal("10000")
    assert corporate["coupon_total_abs_face_amount"] == Decimal("20000")
    assert corporate["balance_amount"] == Decimal("20000")
    assert corporate["coupon_coverage_ratio"] == Decimal("0.5")
    assert corporate["coupon_known_count"] == 1
    assert corporate["coupon_required_count"] == 2
    assert corporate["coupon_coverage_status"] == "部分缺失"
    assert corporate["known_total_coupon_income_amount"] == Decimal("700")
    assert corporate["known_share_of_income"] == Decimal("4") / Decimal("7")
    # Even a complete bucket cannot divide by an incomplete portfolio total.
    assert result["政策性金融债"]["coupon_income_amount"] == Decimal("300")
    assert result["政策性金融债"]["share_of_income"] is None
    assert corporate["total_coupon_income_amount"] is None
    assert corporate["portfolio_coupon_coverage_status"] == "部分缺失"


@pytest.mark.parametrize("coupon", [None, Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_all_missing_coupon_has_no_full_income_or_invented_full_spread(coupon) -> None:
    result = _by_type([_benchmark(), _asset("unknown", coupon)])["企业债"]
    for key in ("coupon_income_amount", "weighted_rate_pct", "spread_bp", "spread_income_amount", "share_of_income"):
        assert result[key] is None
    assert result["known_coupon_income_amount"] == Decimal("0")
    assert result["known_spread_income_amount"] == Decimal("0")
    assert result["known_weighted_rate_pct"] is None
    assert result["known_spread_bp"] is None
    assert result["coupon_coverage_ratio"] == Decimal("0")
    assert result["coupon_coverage_status"] == "全部缺失"
    assert result["coupon_known_count"] == 0
    assert result["coupon_required_count"] == 1


@pytest.mark.parametrize("coupon", [Decimal("0"), Decimal("4"), Decimal("-1.25")])
def test_complete_observations_keep_percent_units_and_existing_signed_income(coupon) -> None:
    result = _by_type([_benchmark(), _asset("observed", coupon)])["企业债"]
    expected_income = coupon * Decimal("100")
    expected_spread = (coupon - Decimal("3")) * Decimal("100")
    assert result["coupon_income_amount"] == expected_income
    assert result["known_coupon_income_amount"] == expected_income
    assert result["weighted_rate_pct"] == coupon
    assert result["known_weighted_rate_pct"] == coupon
    assert result["spread_bp"] == expected_spread
    assert result["spread_income_amount"] == expected_spread
    assert result["known_spread_income_amount"] == expected_spread
    assert result["coupon_coverage_ratio"] == Decimal("1")
    assert result["coupon_coverage_status"] == "完整"


@pytest.mark.parametrize("zero_coupon", [None, Decimal("0"), Decimal("7"), Decimal("NaN")])
def test_zero_face_coupon_never_changes_a_nonzero_buckets_coverage(zero_coupon) -> None:
    rows = [_benchmark(), _asset("known", Decimal("4"))]
    before = _build_campisi_table(rows)
    after = _build_campisi_table(rows + [_asset("zero", zero_coupon, face=Decimal("0"))])
    assert after == before


def test_zero_face_only_is_observed_zero_income_but_undefined_rate_and_coverage() -> None:
    result = _by_type([_benchmark(), _asset("zero", None, face=Decimal("0"))])["企业债"]
    assert result["coupon_income_amount"] == Decimal("0")
    assert result["spread_income_amount"] == Decimal("0")
    assert result["weighted_rate_pct"] is None
    assert result["spread_bp"] is None
    assert result["coupon_coverage_ratio"] is None
    assert result["coupon_coverage_status"] == "无面值敞口"
    assert result["coupon_required_count"] == 0


def test_signed_negative_face_keeps_income_weights_but_absolute_coverage_is_bounded() -> None:
    rows = [_benchmark(), _asset("long", Decimal("4")), _asset("unknown-short", None, face=Decimal("-50000000"))]
    result = _by_type(rows)["企业债"]
    assert result["balance_amount"] == Decimal("5000")
    assert result["coupon_known_balance_amount"] == Decimal("10000")
    assert result["coupon_known_abs_face_amount"] == Decimal("10000")
    assert result["coupon_total_abs_face_amount"] == Decimal("15000")
    assert result["coupon_coverage_ratio"] == Decimal("2") / Decimal("3")
    assert result["coupon_income_amount"] is None
    assert result["known_coupon_income_amount"] == Decimal("400")
    assert result["known_spread_income_amount"] == Decimal("100")


def test_face_coverage_and_comparison_do_not_use_market_value_weights() -> None:
    rows = [
        replace(_benchmark(Decimal("2")), market_value_amount=Decimal("900000000")),
        replace(_asset("policy-two", Decimal("4"), face=Decimal("300000000"), bond_type="政策性金融债"), market_value_amount=Decimal("100000000")),
        replace(_asset("known", Decimal("4")), market_value_amount=Decimal("300000000")),
        replace(_asset("unknown", None), market_value_amount=Decimal("10000000")),
    ]
    result = _by_type(rows)["企业债"]
    assert result["coupon_coverage_ratio"] == Decimal("0.5")
    assert result["benchmark_rate_pct"] == Decimal("3.5")
    assert result["known_coupon_income_amount"] == Decimal("400")
    assert result["known_spread_income_amount"] == Decimal("50")


def test_complete_offsetting_faces_keep_income_but_not_a_fabricated_weighted_rate() -> None:
    result = _by_type([_benchmark(), _asset("long", Decimal("4")), _asset("short", Decimal("2"), face=Decimal("-100000000"))])["企业债"]
    assert result["balance_amount"] == Decimal("0")
    assert result["coupon_income_amount"] == Decimal("200")
    assert result["spread_income_amount"] == Decimal("200")
    assert result["weighted_rate_pct"] is None
    assert result["spread_bp"] is None
    assert result["known_weighted_rate_pct"] is None
    assert result["known_spread_bp"] is None
    assert result["coupon_coverage_ratio"] == Decimal("1")
    assert result["coupon_known_count"] == result["coupon_required_count"] == 2


def test_missing_offsetting_faces_do_not_hide_incomplete_evidence() -> None:
    rows = [
        _benchmark(), _asset("known", Decimal("4")),
        _asset("unknown-long", None), _asset("unknown-short", None, face=Decimal("-100000000")),
    ]
    result = _by_type(rows)["企业债"]
    assert result["balance_amount"] == result["coupon_known_balance_amount"] == Decimal("10000")
    assert result["coupon_coverage_ratio"] == Decimal("1") / Decimal("3")
    assert result["coupon_known_count"] == 1
    assert result["coupon_required_count"] == 3
    assert result["coupon_income_amount"] is None
    assert result["spread_income_amount"] is None
    assert result["known_spread_income_amount"] == Decimal("100")


@pytest.mark.parametrize("coupons", [[], [None], [Decimal("3"), None], [Decimal("3"), Decimal("NaN")]])
def test_absent_or_incomplete_benchmark_cannot_become_a_full_comparison(coupons) -> None:
    rows = [_asset(f"benchmark-{i}", coupon, bond_type="政策性金融债") for i, coupon in enumerate(coupons)]
    rows.append(_asset("known", Decimal("4")))
    result = _by_type(rows)["企业债"]
    assert result["coupon_income_amount"] == Decimal("400")
    for key in ("benchmark_rate_pct", "spread_bp", "spread_income_amount", "known_spread_bp", "known_spread_income_amount"):
        assert result[key] is None
    assert result["benchmark_coupon_known_count"] == (1 if len(coupons) == 2 else 0)
    assert result["benchmark_coupon_required_count"] == len(coupons)
    assert result["benchmark_known_abs_face_amount"] == (Decimal("10000") if len(coupons) == 2 else Decimal("0"))
    assert result["benchmark_total_abs_face_amount"] == Decimal("10000") * len(coupons)
    if not coupons:
        assert result["benchmark_coupon_coverage_ratio"] is None
        assert result["benchmark_coverage_status"] == "缺少基准持仓"
    else:
        assert result["benchmark_coupon_coverage_ratio"] == Decimal(result["benchmark_coupon_known_count"]) / Decimal(len(coupons))


def test_benchmark_signed_cancellation_leaves_comparison_unavailable_even_at_full_coverage() -> None:
    rows = [
        _benchmark(), _asset("benchmark-short", Decimal("2"), bond_type="政策性金融债", face=Decimal("-100000000")),
        _asset("known", Decimal("4")),
    ]
    result = _by_type(rows)["企业债"]
    assert result["benchmark_balance_amount"] == Decimal("0")
    assert result["benchmark_coupon_coverage_ratio"] == Decimal("1")
    assert result["benchmark_rate_pct"] is None
    assert result["spread_income_amount"] is None
    assert result["known_spread_income_amount"] is None


def test_real_zero_benchmark_is_available_and_zero_income_denominator_has_no_share() -> None:
    result = _by_type([_benchmark(Decimal("0")), _asset("zero", Decimal("0"))])["企业债"]
    assert result["benchmark_rate_pct"] == Decimal("0")
    assert result["coupon_income_amount"] == Decimal("0")
    assert result["total_coupon_income_amount"] == Decimal("0")
    assert result["spread_bp"] == Decimal("0")
    assert result["spread_income_amount"] == Decimal("0")
    assert result["share_of_income"] is None
    assert result["known_share_of_income"] is None


def test_empty_or_liability_only_assets_have_no_campisi_rows() -> None:
    assert _build_campisi_table([])["rows"] == []
    liability = replace(_asset("liability", None), position_scope="liability", is_issuance_like=True)
    assert _build_campisi_table([liability])["rows"] == []


def test_schema_json_preserves_full_nulls_known_subtotals_and_coverage() -> None:
    table = _build_campisi_table([_benchmark(), _asset("known", Decimal("4")), _asset("unknown", None)])
    serialized = json.loads(BalanceAnalysisWorkbookTable.model_validate(table).model_dump_json())
    result = next(row for row in serialized["rows"] if row["bond_type"] == "企业债")
    for key in ("coupon_income_amount", "weighted_rate_pct", "spread_bp", "spread_income_amount", "share_of_income", "total_coupon_income_amount"):
        assert result[key] is None
    assert Decimal(result["known_coupon_income_amount"]) == Decimal("400")
    assert Decimal(result["known_spread_income_amount"]) == Decimal("100")
    assert Decimal(result["coupon_coverage_ratio"]) == Decimal("0.5")
    assert {column["key"] for column in serialized["columns"]} == set(result)
