"""Equivalence + invariant tests for caliber trial migration (subject_514_516_517_merge)."""

from __future__ import annotations

from decimal import Decimal
from typing import get_args

import pytest

from backend.app.core_finance.config.classification_rules import LEDGER_PNL_ACCOUNT_PREFIXES
from backend.app.core_finance.pnl import (
    JournalType,
    SIGN_FLIP_JOURNAL_TYPES,
    _normalize_nonstd_signed_amount,
)
from backend.app.tasks.pnl_materialize import ALLOWED_NONSTD_JOURNAL_TYPES


def test_journal_type_literal_members_match_ledger_pnl_prefixes_plus_adjustment() -> None:
    assert set(get_args(JournalType)) == set(LEDGER_PNL_ACCOUNT_PREFIXES) | {"adjustment"}


def test_sign_flip_journal_types_excludes_514() -> None:
    assert SIGN_FLIP_JOURNAL_TYPES == frozenset({"516", "517"})
    assert "514" in LEDGER_PNL_ACCOUNT_PREFIXES
    assert "514" not in SIGN_FLIP_JOURNAL_TYPES


def test_allowed_nonstd_journal_types_is_canonical_plus_adjustment() -> None:
    assert ALLOWED_NONSTD_JOURNAL_TYPES == frozenset(LEDGER_PNL_ACCOUNT_PREFIXES) | {
        "adjustment"
    }


@pytest.mark.parametrize("journal_type", ("516", "517"))
def test_normalize_nonstd_signed_amount_flips_sign_for_516_and_517_under_direct_dc_flag(
    journal_type: str,
) -> None:
    assert (
        _normalize_nonstd_signed_amount(
            raw_amount=Decimal("100"),
            journal_type=journal_type,  # type: ignore[arg-type]
            dc_flag="direct_credit",
        )
        == Decimal("-100")
    )


def test_normalize_nonstd_signed_amount_no_flip_for_514_under_direct_dc_flag() -> None:
    assert (
        _normalize_nonstd_signed_amount(
            raw_amount=Decimal("100"),
            journal_type="514",
            dc_flag="direct_credit",
        )
        == Decimal("100")
    )


@pytest.mark.parametrize("journal_type", ("514", "adjustment"))
def test_normalize_nonstd_signed_amount_does_not_flip_for_514_or_adjustment(
    journal_type: str,
) -> None:
    assert (
        _normalize_nonstd_signed_amount(
            raw_amount=Decimal("100"),
            journal_type=journal_type,  # type: ignore[arg-type]
            dc_flag="direct_credit",
        )
        == Decimal("100")
    )
