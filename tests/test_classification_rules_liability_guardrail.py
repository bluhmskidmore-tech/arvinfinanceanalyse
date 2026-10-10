"""Guardrails keeping liability positions out of asset-side measurement buckets.

Background (2026-08 financial audit): ``_HAT_H_LABEL_SUBSTRINGS`` maps pure
liability labels (发行类债务、同业拆入、卖出回购证券 …) to ``H``, which the
downstream ``accounting_basis`` derivation turns into ``AC`` — an asset-side
category. On 2026-07-31 that produced 244 rows carrying
``invest_type_std='H'`` + ``accounting_basis='AC'`` + ``position_scope='liability'``
for 989.73 亿元 (139,460 rows across all history).

Re-mapping those labels would restate persisted balances and needs a historical
backfill, so it is deliberately out of scope here. These tests pin the two
things that can be done without touching a single stored number:

1. the H mapping stays byte-for-byte identical (no silent restatement);
2. the liability path is observable and rejectable at the consumption boundary.
"""

from __future__ import annotations

import logging

import pytest

from backend.app.core_finance.accounting_basis_constants import (
    ACCOUNTING_BASIS_AC,
    ACCOUNTING_BASIS_FVOCI,
    ACCOUNTING_BASIS_FVTPL,
)
from backend.app.core_finance.config import classification_rules as rules
from backend.app.core_finance.config.classification_rules import (
    _HAT_H_LABEL_SUBSTRINGS,
    LiabilityAccountingBasisError,
    assert_position_scope_accounting_basis,
    check_position_scope_accounting_basis,
    infer_invest_type,
    is_asset_side_accounting_basis,
    is_liability_invest_label,
    is_liability_position_scope,
)

LIABILITY_LABELS = (
    "发行类债务",
    "发行类债券",
    "发行类债劵",
    "同业拆入",
    "同业存放",
    "卖出回购证券",
    "卖出回购票据",
)

ASSET_LABELS = (
    "应收投资款项",
    "拆放同业",
    "买入返售证券",
    "存放同业",
    "持有至到期同业存单",
)


@pytest.fixture(autouse=True)
def _reset_label_warning_dedupe():
    rules._warned_liability_invest_labels.clear()
    yield
    rules._warned_liability_invest_labels.clear()


@pytest.mark.parametrize("label", LIABILITY_LABELS)
def test_liability_labels_are_recognised_as_liabilities(label: str) -> None:
    assert is_liability_invest_label(label) is True


@pytest.mark.parametrize("label", ASSET_LABELS)
def test_asset_labels_are_not_flagged_as_liabilities(label: str) -> None:
    """存放同业 / 拆放同业 are placements (assets) despite matching liability keywords."""
    assert is_liability_invest_label(label) is False


def test_liability_label_set_covers_every_liability_in_the_h_mapping() -> None:
    """Nothing in the H label list may be a liability without the guardrail seeing it."""
    flagged = {label for label in _HAT_H_LABEL_SUBSTRINGS if is_liability_invest_label(label)}
    assert flagged == set(LIABILITY_LABELS)
    assert set(_HAT_H_LABEL_SUBSTRINGS) - flagged == set(ASSET_LABELS)


@pytest.mark.parametrize("label", LIABILITY_LABELS)
def test_liability_labels_still_map_to_h_so_no_stored_number_moves(label: str) -> None:
    """Deliberate no-op on the caliber: changing this restates 989.73 亿元."""
    assert infer_invest_type(None, label, None) == "H"
    assert infer_invest_type(None, None, label) == "H"


@pytest.mark.parametrize("label", LIABILITY_LABELS)
def test_liability_label_resolution_is_logged_instead_of_silent(label, caplog) -> None:
    with caplog.at_level(logging.WARNING, logger=rules.__name__):
        assert infer_invest_type(None, label, None) == "H"

    records = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(records) == 1
    message = records[0].getMessage()
    assert label in message
    assert "liability" in message


def test_liability_label_warning_is_emitted_once_per_label(caplog) -> None:
    """One line per distinct label, not one per row of a 10^5-row ETL pass."""
    with caplog.at_level(logging.WARNING, logger=rules.__name__):
        for _ in range(50):
            infer_invest_type(None, "发行类债券", None)
            infer_invest_type(None, "同业拆入", None)

    warned_labels = {record.args[0] for record in caplog.records if record.levelno == logging.WARNING}
    assert warned_labels == {"发行类债券", "同业拆入"}


@pytest.mark.parametrize("label", ASSET_LABELS)
def test_asset_labels_do_not_warn(label, caplog) -> None:
    with caplog.at_level(logging.WARNING, logger=rules.__name__):
        infer_invest_type(None, label, None)
    assert [record for record in caplog.records if record.levelno == logging.WARNING] == []


@pytest.mark.parametrize("basis", [ACCOUNTING_BASIS_AC, ACCOUNTING_BASIS_FVOCI, ACCOUNTING_BASIS_FVTPL])
def test_liability_scope_with_asset_basis_is_a_violation(basis: str) -> None:
    violation = check_position_scope_accounting_basis(
        position_scope="liability",
        accounting_basis=basis,
        context="fact_formal_zqtz_balance_daily 2026-07-31",
    )
    assert violation is not None
    assert basis in violation
    assert "position_scope" in violation
    assert "fact_formal_zqtz_balance_daily 2026-07-31" in violation

    with pytest.raises(LiabilityAccountingBasisError):
        assert_position_scope_accounting_basis(position_scope="liability", accounting_basis=basis)


@pytest.mark.parametrize(
    ("position_scope", "accounting_basis"),
    [
        ("asset", ACCOUNTING_BASIS_AC),
        ("asset", ACCOUNTING_BASIS_FVOCI),
        ("liability", "AMORTISED_COST_LIABILITY"),
        ("liability", ""),
        ("liability", None),
        (None, ACCOUNTING_BASIS_AC),
    ],
)
def test_clean_combinations_pass(position_scope, accounting_basis) -> None:
    assert (
        check_position_scope_accounting_basis(
            position_scope=position_scope,
            accounting_basis=accounting_basis,
        )
        is None
    )
    assert_position_scope_accounting_basis(
        position_scope=position_scope,
        accounting_basis=accounting_basis,
    )


def test_scope_and_basis_matching_is_case_and_whitespace_tolerant() -> None:
    assert is_liability_position_scope("  Liability ") is True
    assert is_liability_position_scope("asset") is False
    assert is_asset_side_accounting_basis(" ac ") is True
    assert is_asset_side_accounting_basis("fvoci") is True
    assert is_asset_side_accounting_basis("LIABILITY_AC") is False
    assert is_asset_side_accounting_basis(None) is False
    with pytest.raises(LiabilityAccountingBasisError):
        assert_position_scope_accounting_basis(position_scope=" LIABILITY ", accounting_basis=" ac ")
