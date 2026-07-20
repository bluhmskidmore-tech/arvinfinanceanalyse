"""Tests for fx_mid_conversion caliber rule (FX mid-rate date selection)."""

from __future__ import annotations

import importlib
from datetime import date
from decimal import Decimal

import pytest

from backend.app.core_finance.calibers import (
    ALL_CELLS,
    Basis,
    Resolution,
    View,
    get_caliber_rule,
)
from backend.app.core_finance.calibers.rules.fx_mid_conversion import (
    _FX_DATE_POLICY,
    DESCRIPTOR,
    InapplicableFxConversion,
    select_fx_date,
)
from backend.app.core_finance.fx_rates import FxRateUnavailableError, get_usd_cny_rate

_BD = date(2024, 1, 2)
_ASOF = date(2024, 3, 4)


def test_descriptor_basic_metadata() -> None:
    assert DESCRIPTOR.rule_id == "fx_mid_conversion"
    assert DESCRIPTOR.rule_version == "v1.0"
    assert DESCRIPTOR.canonical_module == "backend.app.core_finance.fx_rates"
    assert DESCRIPTOR.canonical_callable == "get_usd_cny_rate"
    assert "fact_formal_zqtz_balance_daily" in DESCRIPTOR.applies_to
    assert "fact_formal_tyw_balance_daily" in DESCRIPTOR.applies_to
    assert "fact_formal_pnl_fi_daily" in DESCRIPTOR.applies_to
    assert "fact_formal_product_category_pnl_daily" in DESCRIPTOR.applies_to


def test_matrix_is_complete_9_cells() -> None:
    assert len(DESCRIPTOR.cells) == 9


@pytest.mark.parametrize(
    ("basis", "view", "expected"),
    [
        (Basis.FORMAL, View.ACCOUNTING, Resolution.COMPUTE_VIA_CANONICAL),
        (Basis.FORMAL, View.MANAGEMENT, Resolution.COMPUTE_VIA_CANONICAL),
        (Basis.FORMAL, View.EXTERNAL_EXPOSURE, Resolution.COMPUTE_VIA_CANONICAL),
        (Basis.SCENARIO, View.ACCOUNTING, Resolution.COMPUTE_VIA_CANONICAL),
        (Basis.SCENARIO, View.MANAGEMENT, Resolution.COMPUTE_VIA_CANONICAL),
        (Basis.SCENARIO, View.EXTERNAL_EXPOSURE, Resolution.COMPUTE_VIA_CANONICAL),
        (Basis.ANALYTICAL, View.ACCOUNTING, Resolution.NOT_APPLICABLE),
        (Basis.ANALYTICAL, View.MANAGEMENT, Resolution.COMPUTE_VIA_CANONICAL),
        (Basis.ANALYTICAL, View.EXTERNAL_EXPOSURE, Resolution.COMPUTE_VIA_CANONICAL),
    ],
    ids=[
        "formal-accounting",
        "formal-management",
        "formal-external_exposure",
        "scenario-accounting",
        "scenario-management",
        "scenario-external_exposure",
        "analytical-accounting",
        "analytical-management",
        "analytical-external_exposure",
    ],
)
def test_matrix_values_match_specification(
    basis: Basis,
    view: View,
    expected: Resolution,
) -> None:
    assert DESCRIPTOR.resolve(basis, view) == expected


def test_canonical_callable_get_usd_cny_rate_exists_in_fx_rates_module() -> None:
    mod = importlib.import_module(DESCRIPTOR.canonical_module)
    fn = getattr(mod, DESCRIPTOR.canonical_callable)
    assert callable(fn)


def test_descriptor_is_registered_after_package_import() -> None:
    registered = get_caliber_rule("fx_mid_conversion")
    assert registered is DESCRIPTOR


def test_fx_date_policy_covers_exactly_compute_cells() -> None:
    compute_cells = {
        cell
        for cell in ALL_CELLS
        if DESCRIPTOR.resolve(*cell) == Resolution.COMPUTE_VIA_CANONICAL
    }
    assert len(compute_cells) == 8
    assert set(_FX_DATE_POLICY.keys()) == compute_cells


@pytest.mark.parametrize(
    ("basis", "view", "expected_policy"),
    [
        (Basis.FORMAL, View.ACCOUNTING, "business_date"),
        (Basis.FORMAL, View.MANAGEMENT, "business_date"),
        (Basis.FORMAL, View.EXTERNAL_EXPOSURE, "business_date"),
        (Basis.SCENARIO, View.ACCOUNTING, "as_of_date"),
        (Basis.SCENARIO, View.MANAGEMENT, "as_of_date"),
        (Basis.SCENARIO, View.EXTERNAL_EXPOSURE, "as_of_date"),
        (Basis.ANALYTICAL, View.MANAGEMENT, "as_of_date"),
        (Basis.ANALYTICAL, View.EXTERNAL_EXPOSURE, "as_of_date"),
    ],
)
def test_fx_date_policy_values_by_cell(
    basis: Basis,
    view: View,
    expected_policy: str,
) -> None:
    assert _FX_DATE_POLICY[(basis, view)] == expected_policy


@pytest.mark.parametrize(
    ("basis", "view", "expected"),
    [
        (Basis.FORMAL, View.ACCOUNTING, _BD),
        (Basis.FORMAL, View.MANAGEMENT, _BD),
        (Basis.FORMAL, View.EXTERNAL_EXPOSURE, _BD),
        (Basis.SCENARIO, View.ACCOUNTING, _ASOF),
        (Basis.SCENARIO, View.MANAGEMENT, _ASOF),
        (Basis.SCENARIO, View.EXTERNAL_EXPOSURE, _ASOF),
        (Basis.ANALYTICAL, View.ACCOUNTING, None),
        (Basis.ANALYTICAL, View.MANAGEMENT, _ASOF),
        (Basis.ANALYTICAL, View.EXTERNAL_EXPOSURE, _ASOF),
    ],
    ids=[
        "formal-accounting",
        "formal-management",
        "formal-external_exposure",
        "scenario-accounting",
        "scenario-management",
        "scenario-external_exposure",
        "analytical-accounting-raise",
        "analytical-management",
        "analytical-external_exposure",
    ],
)
def test_select_fx_date_all_nine_matrix_cells(
    basis: Basis,
    view: View,
    expected: date | None,
) -> None:
    if expected is None:
        with pytest.raises(InapplicableFxConversion) as excinfo:
            select_fx_date(basis, view, business_date=_BD, as_of_date=_ASOF)
        assert excinfo.value.basis is basis
        assert excinfo.value.view is view
        assert "fx_mid_conversion" in str(excinfo.value)
        return
    assert (
        select_fx_date(basis, view, business_date=_BD, as_of_date=_ASOF) == expected
    )


def test_inapplicable_fx_conversion_is_value_error_subclass() -> None:
    assert issubclass(InapplicableFxConversion, ValueError)


def test_formal_canonical_usd_cny_rate_fails_closed_when_input_rows_are_empty() -> None:
    with pytest.raises(FxRateUnavailableError) as excinfo:
        get_usd_cny_rate([], date(2026, 3, 31))

    assert "USD/CNY" in str(excinfo.value)
    assert "formal" in str(excinfo.value)


def test_formal_canonical_usd_cny_rate_fails_closed_when_only_stale_rows_exist() -> None:
    with pytest.raises(FxRateUnavailableError) as excinfo:
        get_usd_cny_rate(
            [(date(2026, 2, 1), "7.1100")],
            date(2026, 3, 31),
        )

    assert "USD/CNY" in str(excinfo.value)
    assert "formal" in str(excinfo.value)
    assert "7.25" not in str(excinfo.value)


def test_formal_canonical_usd_cny_rate_carries_forward_explicit_non_business_day() -> None:
    rate, observed_date, warnings = get_usd_cny_rate(
        [(date(2026, 2, 16), "7.1100")],
        date(2026, 2, 18),
        target_is_business_day=False,
    )

    assert rate == Decimal("7.1100")
    assert observed_date == date(2026, 2, 16)
    assert warnings
    assert "formal" in warnings[0]


def test_formal_canonical_usd_cny_rate_uses_cfets_currency_holiday_calendar() -> None:
    rate, observed_date, warnings = get_usd_cny_rate(
        [(date(2026, 1, 16), "7.1100")],
        date(2026, 1, 19),
    )

    assert rate == Decimal("7.1100")
    assert observed_date == date(2026, 1, 16)
    assert warnings
    assert "observed_date=2026-01-16" in warnings[0]


def test_formal_carry_forward_spans_2026_spring_festival_long_holiday() -> None:
    """春节 2/15-2/23 连续非营业日：2/22（假日）应能沿用 2/13（上一营业日，周五）中间价。

    2026-06-10 审计 P2 / 2026-07-19 审计 余额 M-7：原固定 3 天回看窗口在长假第 4 天起误失败。
    """
    rate, observed_date, warnings = get_usd_cny_rate(
        [(date(2026, 2, 13), "7.1200")],
        date(2026, 2, 22),
    )

    assert rate == Decimal("7.1200")
    assert observed_date == date(2026, 2, 13)
    assert warnings
    assert "carry-forward" in warnings[0]


def test_formal_carry_forward_fails_closed_when_previous_business_day_rate_missing() -> None:
    """回看途中遇到营业日但缺中间价，必须 fail-closed，不得继续跳过。"""
    with pytest.raises(FxRateUnavailableError):
        get_usd_cny_rate(
            # 2026-02-12（周四）有值，但 2/13（周五营业日）缺值；目标 2/22 在春节假期内。
            [(date(2026, 2, 12), "7.1200")],
            date(2026, 2, 22),
        )


def test_analytical_fallback_never_uses_future_rate() -> None:
    """分析口径兜底不得取 target_date 之后的汇率（2026-07-19 审计 共享 H-2 前视偏差）。"""
    with pytest.raises(FxRateUnavailableError):
        get_usd_cny_rate(
            [(date(2026, 5, 8), "7.2000")],
            date(2026, 3, 31),
            allow_stale_fallback=True,
        )


def test_analytical_stale_fallback_beyond_30_days_uses_latest_prior_rate_only() -> None:
    rate, observed_date, warnings = get_usd_cny_rate(
        [
            (date(2026, 1, 15), "7.0900"),
            (date(2026, 5, 8), "7.2000"),
        ],
        date(2026, 3, 31),
        allow_stale_fallback=True,
    )

    assert rate == Decimal("7.0900")
    assert observed_date == date(2026, 1, 15)
    assert any("stale fallback" in warning for warning in warnings)
