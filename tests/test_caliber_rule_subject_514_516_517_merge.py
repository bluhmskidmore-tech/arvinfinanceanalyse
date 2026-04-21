"""Tests for bundled subject 514/516/517 merge caliber rule."""

from __future__ import annotations

import pytest

from backend.app.core_finance.calibers import (
    Basis,
    Resolution,
    View,
    get_caliber_rule,
)
from backend.app.core_finance.calibers.rules.subject_514_516_517_merge import (
    DESCRIPTOR,
)
from backend.app.core_finance.config.classification_rules import (
    LEDGER_PNL_ACCOUNT_PREFIXES,
)


def test_descriptor_basic_metadata() -> None:
    assert DESCRIPTOR.rule_id == "subject_514_516_517_merge"
    assert DESCRIPTOR.rule_version == "v1.0"
    assert (
        DESCRIPTOR.canonical_module
        == "backend.app.core_finance.config.classification_rules"
    )
    assert DESCRIPTOR.canonical_callable == "LEDGER_PNL_ACCOUNT_PREFIXES"
    assert "fact_formal_pnl_fi_daily" in DESCRIPTOR.applies_to
    assert "fact_formal_product_category_pnl_daily" in DESCRIPTOR.applies_to


def test_matrix_is_complete_9_cells() -> None:
    assert len(DESCRIPTOR.cells) == 9


@pytest.mark.parametrize(
    ("basis", "view", "expected"),
    [
        (Basis.FORMAL, View.ACCOUNTING, Resolution.MERGE),
        (Basis.FORMAL, View.MANAGEMENT, Resolution.MERGE),
        (Basis.FORMAL, View.EXTERNAL_EXPOSURE, Resolution.MERGE),
        (Basis.SCENARIO, View.ACCOUNTING, Resolution.MERGE),
        (Basis.SCENARIO, View.MANAGEMENT, Resolution.MERGE),
        (Basis.SCENARIO, View.EXTERNAL_EXPOSURE, Resolution.INHERIT_FROM_FORMAL),
        (Basis.ANALYTICAL, View.ACCOUNTING, Resolution.MERGE),
        (Basis.ANALYTICAL, View.MANAGEMENT, Resolution.SPLIT),
        (Basis.ANALYTICAL, View.EXTERNAL_EXPOSURE, Resolution.INHERIT_FROM_FORMAL),
    ],
)
def test_matrix_values_match_specification(
    basis: Basis,
    view: View,
    expected: Resolution,
) -> None:
    assert DESCRIPTOR.resolve(basis, view) == expected


def test_canonical_module_constant_actually_exists() -> None:
    assert LEDGER_PNL_ACCOUNT_PREFIXES == ("514", "516", "517")
    assert DESCRIPTOR.canonical_callable == "LEDGER_PNL_ACCOUNT_PREFIXES"


def test_descriptor_is_registered_after_package_import() -> None:
    registered = get_caliber_rule("subject_514_516_517_merge")
    assert registered is DESCRIPTOR
