"""Tests for issuance_exclusion caliber rule (bond-liability include/exclude gate)."""

from __future__ import annotations

import importlib

import pytest

from backend.app.core_finance.calibers import (
    Basis,
    Resolution,
    View,
    get_caliber_rule,
)
from backend.app.core_finance.calibers.rules.issuance_exclusion import DESCRIPTOR


def test_descriptor_basic_metadata() -> None:
    assert DESCRIPTOR.rule_id == "issuance_exclusion"
    assert DESCRIPTOR.rule_version == "v1.0"
    assert (
        DESCRIPTOR.canonical_module
        == "backend.app.core_finance.config.classification_rules"
    )
    assert DESCRIPTOR.canonical_callable == "is_bond_liability"
    assert "fact_formal_zqtz_balance_daily" in DESCRIPTOR.applies_to
    assert "fact_formal_bond_analytics_daily" in DESCRIPTOR.applies_to
    assert "fact_formal_pnl_fi_daily" in DESCRIPTOR.applies_to
    assert "fact_formal_product_category_pnl_daily" in DESCRIPTOR.applies_to


def test_matrix_is_complete_9_cells() -> None:
    assert len(DESCRIPTOR.cells) == 9


@pytest.mark.parametrize(
    ("basis", "view", "expected"),
    [
        (Basis.FORMAL, View.ACCOUNTING, Resolution.INCLUDE),
        (Basis.FORMAL, View.MANAGEMENT, Resolution.EXCLUDE),
        (Basis.FORMAL, View.EXTERNAL_EXPOSURE, Resolution.EXCLUDE),
        (Basis.SCENARIO, View.ACCOUNTING, Resolution.INHERIT_FROM_FORMAL),
        (Basis.SCENARIO, View.MANAGEMENT, Resolution.INHERIT_FROM_FORMAL),
        (Basis.SCENARIO, View.EXTERNAL_EXPOSURE, Resolution.INHERIT_FROM_FORMAL),
        (Basis.ANALYTICAL, View.ACCOUNTING, Resolution.INCLUDE),
        (Basis.ANALYTICAL, View.MANAGEMENT, Resolution.EXCLUDE),
        (Basis.ANALYTICAL, View.EXTERNAL_EXPOSURE, Resolution.EXCLUDE),
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


def test_canonical_callable_exists_in_classification_rules_module() -> None:
    mod = importlib.import_module(DESCRIPTOR.canonical_module)
    fn = getattr(mod, DESCRIPTOR.canonical_callable)
    assert callable(fn)


def test_descriptor_is_registered_after_package_import() -> None:
    registered = get_caliber_rule("issuance_exclusion")
    assert registered is DESCRIPTOR


def test_applies_to_only_uses_fact_formal_daily_table_names() -> None:
    for name in DESCRIPTOR.applies_to:
        assert name.startswith("fact_formal_")
        assert name.endswith("_daily")
