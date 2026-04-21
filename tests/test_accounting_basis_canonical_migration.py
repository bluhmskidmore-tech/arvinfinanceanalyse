"""W-accounting-basis-migration-2026-04-21: canonical ACCOUNTING_BASIS_* tokens + gate enrollment."""

from __future__ import annotations

import pytest

from backend.app.core_finance.accounting_basis_constants import (
    ACCOUNTING_BASIS_AC,
    ACCOUNTING_BASIS_FVOCI,
    ACCOUNTING_BASIS_FVTPL,
)
from backend.app.core_finance.bond_analytics import common as bond_analytics_common
from backend.app.core_finance.bond_duration import infer_accounting_class
from backend.app.core_finance import field_normalization as field_normalization_mod
from backend.app.core_finance.field_normalization import derive_accounting_basis_value
from backend.app.core_finance.krd import map_accounting_class as krd_map_accounting_class
from backend.scripts.audit_caliber_violations import _GATE_ENFORCED_RULES


def test_accounting_basis_constants_match_literal_strings() -> None:
    assert ACCOUNTING_BASIS_AC == "AC"
    assert ACCOUNTING_BASIS_FVOCI == "FVOCI"
    assert ACCOUNTING_BASIS_FVTPL == "FVTPL"
    assert field_normalization_mod.ACCOUNTING_BASIS_AC is ACCOUNTING_BASIS_AC
    assert field_normalization_mod.ACCOUNTING_BASIS_FVOCI is ACCOUNTING_BASIS_FVOCI
    assert field_normalization_mod.ACCOUNTING_BASIS_FVTPL is ACCOUNTING_BASIS_FVTPL


def test_derive_accounting_basis_value_matches_canonical_tokens() -> None:
    assert derive_accounting_basis_value("H") == ACCOUNTING_BASIS_AC
    assert derive_accounting_basis_value("A") == ACCOUNTING_BASIS_FVOCI
    assert derive_accounting_basis_value("T") == ACCOUNTING_BASIS_FVTPL


def test_gate_enforces_accounting_basis() -> None:
    assert "accounting_basis" in _GATE_ENFORCED_RULES


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("持有至到期投资", "AC"),
        ("交易性金融资产", "TPL"),
        ("可供出售债券", "OCI"),
    ],
)
def test_infer_accounting_class_invariants_unchanged(label: str, expected: str) -> None:
    assert infer_accounting_class(label) == expected


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("持有至到期投资", "AC"),
        ("交易性金融资产", "TPL"),
        ("FVOCI债券", "OCI"),
    ],
)
def test_bond_analytics_map_accounting_class_invariants(label: str, expected: str) -> None:
    assert bond_analytics_common.map_accounting_class(label) == expected


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("持有至到期投资", "AC"),
        ("交易性金融资产", "TPL"),
        ("可供出售金融资产", "OCI"),
    ],
)
def test_krd_map_accounting_class_invariants(label: str, expected: str) -> None:
    assert krd_map_accounting_class(label) == expected
