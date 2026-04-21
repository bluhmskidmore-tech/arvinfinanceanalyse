from __future__ import annotations

"""W-krd-2026-04-21 caliber migration: krd.map_accounting_class vs canonical hat_mapping."""

import pytest

from backend.app.core_finance.krd import map_accounting_class


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("持有至到期投资", "AC"),
        ("持有至到期债券", "AC"),
        ("可供出售金融资产", "OCI"),
        ("可供出售债券", "OCI"),
        ("交易性金融资产", "TPL"),
        ("TPL bucket", "TPL"),
        ("FVTPL portfolio", "TPL"),
    ],
)
def test_map_accounting_class_hat_branches(label: str, expected: str) -> None:
    assert map_accounting_class(label) == expected


def test_legacy_ac_fallbacks_when_canonical_returns_none() -> None:
    assert map_accounting_class("债权投资") == "AC"
    assert map_accounting_class("摊余计量") == "AC"
    assert map_accounting_class("AC") == "AC"


def test_default_fallback_unknown_is_other() -> None:
    assert map_accounting_class("完全未知会计类标签") == "other"
    assert map_accounting_class(None) == "other"
    assert map_accounting_class("") == "other"
