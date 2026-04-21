"""Tests for fx_mid_conversion caliber rule (FX mid-rate date selection)."""

from __future__ import annotations

import importlib
from datetime import date

import pytest

from backend.app.core_finance.calibers import (
    ALL_CELLS,
    Basis,
    Resolution,
    View,
    get_caliber_rule,
)
from backend.app.core_finance.calibers.rules.fx_mid_conversion import (
    DESCRIPTOR,
    InapplicableFxConversion,
    _FX_DATE_POLICY,
    select_fx_date,
)


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
