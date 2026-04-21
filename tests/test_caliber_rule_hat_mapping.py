"""Tests for hat_mapping caliber rule (H/A/T investment-type mapping)."""

from __future__ import annotations

import importlib
import inspect

import pytest

from backend.app.core_finance.calibers import (
    Basis,
    Resolution,
    View,
    get_caliber_rule,
)
from backend.app.core_finance.calibers.rules.hat_mapping import DESCRIPTOR


def test_descriptor_basic_metadata() -> None:
    assert DESCRIPTOR.rule_id == "hat_mapping"
    assert DESCRIPTOR.rule_version == "v1.0"
    assert (
        DESCRIPTOR.canonical_module
        == "backend.app.core_finance.config.classification_rules"
    )
    assert DESCRIPTOR.canonical_callable == "infer_invest_type"
    assert "fact_formal_zqtz_balance_daily" in DESCRIPTOR.applies_to
    assert "fact_formal_bond_analytics_daily" in DESCRIPTOR.applies_to
    assert "fact_formal_pnl_fi_daily" in DESCRIPTOR.applies_to


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


def test_canonical_callable_infer_invest_type_exists_and_signature() -> None:
    mod = importlib.import_module(DESCRIPTOR.canonical_module)
    fn = getattr(mod, DESCRIPTOR.canonical_callable)
    assert callable(fn)
    sig = inspect.signature(fn)
    params = sig.parameters
    assert set(params) == {
        "portfolio",
        "asset_type",
        "asset_class",
        "interest_income",
        "is_nonstd",
    }
    assert params["portfolio"].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert params["asset_type"].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert params["asset_class"].default is None
    assert params["interest_income"].default is None
    assert params["is_nonstd"].default is False


def test_descriptor_is_registered_after_package_import() -> None:
    registered = get_caliber_rule("hat_mapping")
    assert registered is DESCRIPTOR


def test_applies_to_only_uses_fact_formal_daily_table_names() -> None:
    for name in DESCRIPTOR.applies_to:
        assert name.startswith("fact_formal_")
        assert name.endswith("_daily")
