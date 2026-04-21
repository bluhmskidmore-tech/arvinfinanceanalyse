"""Tests for bundled accounting basis (AC / FVOCI / FVTPL) caliber rule."""

from __future__ import annotations

import pytest

from backend.app.core_finance.calibers import (
    Basis,
    Resolution,
    View,
    get_caliber_rule,
)
from backend.app.core_finance.calibers.rules.accounting_basis import DESCRIPTOR
from backend.app.core_finance.field_normalization import derive_accounting_basis_value


def test_descriptor_basic_metadata() -> None:
    assert DESCRIPTOR.rule_id == "accounting_basis"
    assert DESCRIPTOR.rule_version == "v1.0"
    assert DESCRIPTOR.canonical_module == "backend.app.core_finance.field_normalization"
    assert DESCRIPTOR.canonical_callable == "derive_accounting_basis_value"
    assert "fact_formal_pnl_fi_daily" in DESCRIPTOR.applies_to
    assert "fact_formal_zqtz_balance_daily" in DESCRIPTOR.applies_to
    assert "fact_formal_bond_analytics_daily" in DESCRIPTOR.applies_to


def test_matrix_is_complete_9_cells() -> None:
    assert len(DESCRIPTOR.cells) == 9


@pytest.mark.parametrize(
    ("basis", "view", "expected"),
    [
        (Basis.FORMAL, View.ACCOUNTING, Resolution.COMPUTE_VIA_CANONICAL),
        (Basis.FORMAL, View.MANAGEMENT, Resolution.INHERIT_FROM_FORMAL),
        (Basis.FORMAL, View.EXTERNAL_EXPOSURE, Resolution.INHERIT_FROM_FORMAL),
        (Basis.SCENARIO, View.ACCOUNTING, Resolution.INHERIT_FROM_FORMAL),
        (Basis.SCENARIO, View.MANAGEMENT, Resolution.INHERIT_FROM_FORMAL),
        (Basis.SCENARIO, View.EXTERNAL_EXPOSURE, Resolution.INHERIT_FROM_FORMAL),
        (Basis.ANALYTICAL, View.ACCOUNTING, Resolution.INHERIT_FROM_FORMAL),
        (Basis.ANALYTICAL, View.MANAGEMENT, Resolution.INHERIT_FROM_FORMAL),
        (Basis.ANALYTICAL, View.EXTERNAL_EXPOSURE, Resolution.INHERIT_FROM_FORMAL),
    ],
)
def test_matrix_values_match_specification(
    basis: Basis,
    view: View,
    expected: Resolution,
) -> None:
    assert DESCRIPTOR.resolve(basis, view) == expected


def test_derive_accounting_basis_value_htat_mapping() -> None:
    assert derive_accounting_basis_value("H") == "AC"
    assert derive_accounting_basis_value("A") == "FVOCI"
    assert derive_accounting_basis_value("T") == "FVTPL"


def test_descriptor_is_registered_after_package_import() -> None:
    registered = get_caliber_rule("accounting_basis")
    assert registered is DESCRIPTOR
