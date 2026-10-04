"""Campisi 四效应主链路脏输入：披露不改数。

与 ``test_campisi_dirty_input.py`` 的 fail-loud 契约相反：
- 脏值仍静默置零参与计算（不抛异常，避免归因页硬失败）；
- 必须在 diagnostics 追加解析失败条目；
- None / 缺字段不得记解析失败。
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.core_finance.bond_four_effects import (
    COUPON_RATE_START_MISSING_DIAGNOSTIC,
    COUPON_RATE_START_PARSE_FAILED_DIAGNOSTIC,
    FACE_VALUE_START_MISSING_DIAGNOSTIC,
    FACE_VALUE_START_PARSE_FAILED_DIAGNOSTIC,
    MARKET_VALUE_END_MISSING_DIAGNOSTIC,
    MARKET_VALUE_END_PARSE_FAILED_DIAGNOSTIC,
    MARKET_VALUE_START_MISSING_DIAGNOSTIC,
    MARKET_VALUE_START_PARSE_FAILED_DIAGNOSTIC,
    POSITION_END_ONLY_DIAGNOSTIC,
    POSITION_START_ONLY_DIAGNOSTIC,
    compute_bond_four_effects,
    compute_bond_six_effects,
)
from tests.test_campisi_formula_golden import (
    START_DATE,
    _zero_coupon_bond,
    test_government_four_effect_golden_sample_closes_on_full_price_basis,
)

pytestmark = pytest.mark.unit

PARSE_FAILED_CODES = (
    COUPON_RATE_START_PARSE_FAILED_DIAGNOSTIC,
    FACE_VALUE_START_PARSE_FAILED_DIAGNOSTIC,
    MARKET_VALUE_START_PARSE_FAILED_DIAGNOSTIC,
    MARKET_VALUE_END_PARSE_FAILED_DIAGNOSTIC,
)

MISSING_CODES = (
    COUPON_RATE_START_MISSING_DIAGNOSTIC,
    FACE_VALUE_START_MISSING_DIAGNOSTIC,
    MARKET_VALUE_START_MISSING_DIAGNOSTIC,
    MARKET_VALUE_END_MISSING_DIAGNOSTIC,
)

DIRTY_FIELD_CASES = [
    ("coupon_rate_start", COUPON_RATE_START_PARSE_FAILED_DIAGNOSTIC),
    ("face_value_start", FACE_VALUE_START_PARSE_FAILED_DIAGNOSTIC),
    ("market_value_start", MARKET_VALUE_START_PARSE_FAILED_DIAGNOSTIC),
    ("market_value_end", MARKET_VALUE_END_PARSE_FAILED_DIAGNOSTIC),
]

MISSING_FIELD_CASES = [
    ("coupon_rate_start", COUPON_RATE_START_MISSING_DIAGNOSTIC),
    ("face_value_start", FACE_VALUE_START_MISSING_DIAGNOSTIC),
    ("market_value_start", MARKET_VALUE_START_MISSING_DIAGNOSTIC),
    ("market_value_end", MARKET_VALUE_END_MISSING_DIAGNOSTIC),
]


def _compute(bond: dict[str, object], *, spread: Decimal = Decimal("0.005")):
    return compute_bond_four_effects(
        bond,
        num_days=30,
        benchmark_yield_change=Decimal("0.01"),
        spread_change=spread,
        report_date=START_DATE,
    )


def test_dirty_market_value_start_zeros_rate_effects_and_discloses() -> None:
    bond = _zero_coupon_bond(bond_code="DIRTY_MV_START", market_value_start="N/A")
    result = _compute(bond)

    assert result["treasury_effect"] == Decimal("0")
    assert result["spread_effect"] == Decimal("0")
    assert MARKET_VALUE_START_PARSE_FAILED_DIAGNOSTIC in result["diagnostics"]
    assert FACE_VALUE_START_PARSE_FAILED_DIAGNOSTIC not in result["diagnostics"]


def test_dirty_coupon_rate_start_zeros_income_and_discloses() -> None:
    bond = _zero_coupon_bond(bond_code="DIRTY_COUPON", coupon_rate_start="N/A")
    result = _compute(bond, spread=Decimal("0"))

    assert result["income_return"] == Decimal("0")
    assert COUPON_RATE_START_PARSE_FAILED_DIAGNOSTIC in result["diagnostics"]


def test_dirty_face_value_start_zeros_income_and_discloses() -> None:
    bond = _zero_coupon_bond(
        bond_code="DIRTY_FACE",
        coupon_rate_start=0.05,
        face_value_start="N/A",
    )
    result = _compute(bond, spread=Decimal("0"))

    assert result["income_return"] == Decimal("0")
    assert FACE_VALUE_START_PARSE_FAILED_DIAGNOSTIC in result["diagnostics"]


def test_dirty_market_value_end_treats_end_as_zero_and_discloses() -> None:
    bond = _zero_coupon_bond(bond_code="DIRTY_MV_END", market_value_end="N/A")
    result = _compute(bond, spread=Decimal("0"))

    assert result["total_price_change"] == pytest.approx(Decimal("-1000"))
    assert result["treasury_effect"] != Decimal("0")
    assert MARKET_VALUE_END_PARSE_FAILED_DIAGNOSTIC in result["diagnostics"]


@pytest.mark.parametrize(("field", "code"), DIRTY_FIELD_CASES, ids=[c[0] for c in DIRTY_FIELD_CASES])
def test_each_dirty_core_field_discloses_without_raising(field: str, code: str) -> None:
    bond = _zero_coupon_bond(bond_code=f"DIRTY_{field}", **{field: "N/A"})
    result = _compute(bond)
    assert code in result["diagnostics"]
    for other in PARSE_FAILED_CODES:
        if other != code:
            assert other not in result["diagnostics"]


@pytest.mark.parametrize(("field", "code"), DIRTY_FIELD_CASES, ids=[c[0] for c in DIRTY_FIELD_CASES])
@pytest.mark.parametrize("missing", [None, "omit"], ids=["none", "omitted"])
def test_missing_core_fields_do_not_emit_parse_failed(
    field: str,
    code: str,
    missing: str | None,
) -> None:
    if missing == "omit":
        bond = _zero_coupon_bond(bond_code=f"MISSING_{field}")
        bond.pop(field)
    else:
        bond = _zero_coupon_bond(bond_code=f"NONE_{field}", **{field: None})
    result = _compute(bond)
    assert code not in result["diagnostics"]
    assert not any(item in PARSE_FAILED_CODES for item in result["diagnostics"])


@pytest.mark.parametrize(("field", "code"), MISSING_FIELD_CASES, ids=[c[0] for c in MISSING_FIELD_CASES])
@pytest.mark.parametrize("missing", [None, "omit"], ids=["none", "omitted"])
def test_missing_core_fields_emit_their_own_missing_diagnostic(
    field: str,
    code: str,
    missing: str | None,
) -> None:
    """``test_missing_core_fields_do_not_emit_parse_failed`` 的对偶：缺失不记解析失败，
    但必须记缺失码，否则"按 0 代入"在下游完全没有披露通道。"""
    if missing == "omit":
        bond = _zero_coupon_bond(bond_code=f"MISSING_{field}")
        bond.pop(field)
    else:
        bond = _zero_coupon_bond(bond_code=f"NONE_{field}", **{field: None})
    result = _compute(bond)
    assert code in result["diagnostics"]
    for other in MISSING_CODES:
        if other != code:
            assert other not in result["diagnostics"]


@pytest.mark.parametrize(("field", "code"), MISSING_FIELD_CASES, ids=[c[0] for c in MISSING_FIELD_CASES])
def test_dirty_core_fields_do_not_emit_missing_diagnostic(field: str, code: str) -> None:
    bond = _zero_coupon_bond(bond_code=f"DIRTY_{field}", **{field: "N/A"})
    result = _compute(bond)
    assert code not in result["diagnostics"]


def test_start_only_position_produces_no_effects_and_only_the_single_sided_code() -> None:
    """期初有、期末无：不是 -mv_start 的价格暴跌，四效应与 total_return 必须为 0。"""
    bond = _zero_coupon_bond(
        bond_code="START_ONLY",
        coupon_rate_start=0.05,
        market_value_end=None,
        accrued_interest_end=None,
        start_present=True,
        end_present=False,
    )
    result = _compute(bond)

    assert result["income_return"] == Decimal("0")
    assert result["treasury_effect"] == Decimal("0")
    assert result["spread_effect"] == Decimal("0")
    assert result["selection_effect"] == Decimal("0")
    assert result["total_return"] == Decimal("0")
    assert result["total_price_change"] == Decimal("0")
    assert POSITION_START_ONLY_DIAGNOSTIC in result["diagnostics"]
    assert POSITION_END_ONLY_DIAGNOSTIC not in result["diagnostics"]
    # 单边行只报单边码，不再重复报 market_value 缺失码。
    assert MARKET_VALUE_END_MISSING_DIAGNOSTIC not in result["diagnostics"]
    assert MARKET_VALUE_START_MISSING_DIAGNOSTIC not in result["diagnostics"]


def test_end_only_position_produces_no_effects_and_only_the_single_sided_code() -> None:
    bond = _zero_coupon_bond(
        bond_code="END_ONLY",
        coupon_rate_start=0.05,
        market_value_start=None,
        face_value_start=None,
        accrued_interest_start=None,
        market_value_end=990.0,
        start_present=False,
        end_present=True,
    )
    result = _compute(bond)

    assert result["income_return"] == Decimal("0")
    assert result["treasury_effect"] == Decimal("0")
    assert result["spread_effect"] == Decimal("0")
    assert result["selection_effect"] == Decimal("0")
    assert result["total_return"] == Decimal("0")
    assert result["total_price_change"] == Decimal("0")
    assert POSITION_END_ONLY_DIAGNOSTIC in result["diagnostics"]
    assert POSITION_START_ONLY_DIAGNOSTIC not in result["diagnostics"]
    assert MARKET_VALUE_START_MISSING_DIAGNOSTIC not in result["diagnostics"]
    # 单边豁免只覆盖 market_value；面值缺失仍必须披露。
    assert FACE_VALUE_START_MISSING_DIAGNOSTIC in result["diagnostics"]


def test_both_sides_present_markers_keep_the_normal_price_change_path() -> None:
    bond = _zero_coupon_bond(bond_code="BOTH_SIDES", start_present=True, end_present=True)
    result = _compute(bond, spread=Decimal("0"))

    assert result["total_price_change"] == pytest.approx(Decimal("-10"))
    assert result["treasury_effect"] != Decimal("0")
    assert POSITION_START_ONLY_DIAGNOSTIC not in result["diagnostics"]
    assert POSITION_END_ONLY_DIAGNOSTIC not in result["diagnostics"]


def test_six_effects_suppresses_second_order_terms_on_single_sided_position() -> None:
    bond = _zero_coupon_bond(
        bond_code="START_ONLY_SIX",
        market_value_end=None,
        accrued_interest_end=None,
        start_present=True,
        end_present=False,
    )
    result = compute_bond_six_effects(
        bond,
        num_days=30,
        benchmark_yield_change=Decimal("0.01"),
        spread_change=Decimal("0.005"),
        report_date=START_DATE,
    )

    assert result["convexity_effect"] == Decimal("0")
    assert result["cross_effect"] == Decimal("0")
    assert result["reinvestment_effect"] == Decimal("0")
    assert result["selection_effect"] == Decimal("0")
    assert result["total_return"] == Decimal("0")
    assert POSITION_START_ONLY_DIAGNOSTIC in result["diagnostics"]


def test_clean_golden_sample_has_no_parse_failed_and_keeps_numbers() -> None:
    test_government_four_effect_golden_sample_closes_on_full_price_basis()
    result = _compute(_zero_coupon_bond(), spread=Decimal("0"))
    assert result["diagnostics"] == []
    assert result["income_return"] == pytest.approx(Decimal("0"))
    modified_duration = Decimal("1") / (Decimal("1") + Decimal("0.05") / Decimal("2"))
    assert result["treasury_effect"] == pytest.approx(
        -modified_duration * Decimal("0.01") * Decimal("1000")
    )
    assert result["selection_effect"] == pytest.approx(
        Decimal("-0.2439024390"), abs=Decimal("1E-6")
    )


def test_six_effects_inherits_dirty_market_value_start_disclosure() -> None:
    bond = _zero_coupon_bond(bond_code="DIRTY_MV_START_SIX", market_value_start="N/A")
    result = compute_bond_six_effects(
        bond,
        num_days=30,
        benchmark_yield_change=Decimal("0.01"),
        spread_change=Decimal("0.005"),
        report_date=START_DATE,
    )
    assert MARKET_VALUE_START_PARSE_FAILED_DIAGNOSTIC in result["diagnostics"]
    assert result["treasury_effect"] == Decimal("0")
    assert result["spread_effect"] == Decimal("0")
    assert result["convexity_effect"] == Decimal("0")
    assert result["cross_effect"] == Decimal("0")
