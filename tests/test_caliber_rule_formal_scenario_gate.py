"""Tests for formal_scenario_gate caliber rule."""

from __future__ import annotations

import pytest

from backend.app.core_finance.calibers import (
    Basis,
    CaliberCalibrationViolation,
    Resolution,
    View,
    assert_canonical_callsite,
    get_caliber_rule,
)
from backend.app.core_finance.calibers.rules.formal_scenario_gate import (
    DESCRIPTOR,
    ForbiddenBasisViewCombination,
    assert_basis_view_allowed,
    is_basis_view_allowed,
)

_EXPECTED_FACT_TABLES = (
    "fact_formal_pnl_fi_daily",
    "fact_formal_zqtz_balance_daily",
    "fact_formal_tyw_balance_daily",
    "fact_formal_bond_analytics_daily",
    "fact_formal_product_category_pnl_daily",
)


def test_descriptor_basic_metadata() -> None:
    assert DESCRIPTOR.rule_id == "formal_scenario_gate"
    assert DESCRIPTOR.rule_version == "v1.0"
    assert (
        DESCRIPTOR.canonical_module
        == "backend.app.core_finance.calibers.rules.formal_scenario_gate"
    )
    assert DESCRIPTOR.canonical_callable == "assert_basis_view_allowed"
    for table in _EXPECTED_FACT_TABLES:
        assert table in DESCRIPTOR.applies_to


def test_matrix_is_complete_9_cells() -> None:
    assert len(DESCRIPTOR.cells) == 9


@pytest.mark.parametrize(
    ("basis", "view", "expected"),
    [
        (Basis.FORMAL, View.ACCOUNTING, Resolution.INCLUDE),
        (Basis.FORMAL, View.MANAGEMENT, Resolution.INCLUDE),
        (Basis.FORMAL, View.EXTERNAL_EXPOSURE, Resolution.INCLUDE),
        (Basis.SCENARIO, View.ACCOUNTING, Resolution.EXCLUDE),
        (Basis.SCENARIO, View.MANAGEMENT, Resolution.INCLUDE),
        (Basis.SCENARIO, View.EXTERNAL_EXPOSURE, Resolution.EXCLUDE),
        (Basis.ANALYTICAL, View.ACCOUNTING, Resolution.EXCLUDE),
        (Basis.ANALYTICAL, View.MANAGEMENT, Resolution.INCLUDE),
        (Basis.ANALYTICAL, View.EXTERNAL_EXPOSURE, Resolution.EXCLUDE),
    ],
)
def test_matrix_values_match_specification(
    basis: Basis,
    view: View,
    expected: Resolution,
) -> None:
    assert DESCRIPTOR.resolve(basis, view) == expected


def test_descriptor_is_registered_after_package_import() -> None:
    assert get_caliber_rule("formal_scenario_gate") is DESCRIPTOR


@pytest.mark.parametrize(
    ("basis", "view", "expected"),
    [
        (Basis.FORMAL, View.ACCOUNTING, True),
        (Basis.FORMAL, View.MANAGEMENT, True),
        (Basis.FORMAL, View.EXTERNAL_EXPOSURE, True),
        (Basis.SCENARIO, View.ACCOUNTING, False),
        (Basis.SCENARIO, View.MANAGEMENT, True),
        (Basis.SCENARIO, View.EXTERNAL_EXPOSURE, False),
        (Basis.ANALYTICAL, View.ACCOUNTING, False),
        (Basis.ANALYTICAL, View.MANAGEMENT, True),
        (Basis.ANALYTICAL, View.EXTERNAL_EXPOSURE, False),
    ],
)
def test_is_basis_view_allowed_matches_matrix(
    basis: Basis,
    view: View,
    expected: bool,
) -> None:
    assert is_basis_view_allowed(basis, view) == expected


@pytest.mark.parametrize(
    ("basis", "view"),
    [
        (Basis.FORMAL, View.ACCOUNTING),
        (Basis.FORMAL, View.MANAGEMENT),
        (Basis.FORMAL, View.EXTERNAL_EXPOSURE),
        (Basis.SCENARIO, View.MANAGEMENT),
        (Basis.ANALYTICAL, View.MANAGEMENT),
    ],
)
def test_assert_basis_view_allowed_passes_for_include_cells(
    basis: Basis,
    view: View,
) -> None:
    assert assert_basis_view_allowed(basis, view) is None


@pytest.mark.parametrize(
    ("basis", "view"),
    [
        (Basis.SCENARIO, View.ACCOUNTING),
        (Basis.SCENARIO, View.EXTERNAL_EXPOSURE),
        (Basis.ANALYTICAL, View.ACCOUNTING),
        (Basis.ANALYTICAL, View.EXTERNAL_EXPOSURE),
    ],
)
def test_assert_basis_view_allowed_raises_for_exclude_cells(
    basis: Basis,
    view: View,
) -> None:
    with pytest.raises(ForbiddenBasisViewCombination) as excinfo:
        assert_basis_view_allowed(basis, view)
    assert excinfo.value.basis is basis
    assert excinfo.value.view is view


def test_forbidden_exception_is_value_error_subclass() -> None:
    assert issubclass(ForbiddenBasisViewCombination, ValueError)


def test_forbidden_exception_message_references_rule_id_and_canonical_module() -> None:
    with pytest.raises(ForbiddenBasisViewCombination) as excinfo:
        assert_basis_view_allowed(Basis.SCENARIO, View.ACCOUNTING)
    msg = str(excinfo.value)
    assert "formal_scenario_gate" in msg
    assert "backend.app.core_finance.calibers.rules.formal_scenario_gate" in msg


def test_canonical_callsite_warns_for_non_canonical_module() -> None:
    with pytest.warns(CaliberCalibrationViolation):
        assert_canonical_callsite("formal_scenario_gate", "some.other.module")
