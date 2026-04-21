"""W-balance-2026-04-21 trial migration of hat_mapping — canonical equivalence tests.

Ensures ``balance_analysis.derive_invest_type_std`` (wrapper) and
``classification_rules.infer_invest_type`` / substring helper behavior stay aligned
with legacy H-label coverage from field_normalization and pre-migration balance
analysis label sets.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.core_finance.balance_analysis import derive_invest_type_std
from backend.app.core_finance.config.classification_rules import (
    _HAT_H_LABEL_SUBSTRINGS,
    _match_invest_type_by_substring,
    infer_invest_type,
)
from backend.app.core_finance.field_normalization import _H_LABELS

# Pre-migration inline `_H_LABELS` from balance_analysis (before W-balance-2026-04-21).
# Includes 发行类债劵 (劵) so regressions if canonical drops that variant are caught.
_LEGACY_BALANCE_ANALYSIS_H_LABELS: frozenset[str] = frozenset(
    {
        "应收投资款项",
        "发行类债劵",
        "发行类债券",
        "拆放同业",
        "买入返售证券",
        "存放同业",
        "同业拆入",
        "同业存放",
        "卖出回购证券",
        "卖出回购票据",
        "持有至到期同业存单",
    }
)


def test_field_normalization_h_labels_round_trip_through_canonical() -> None:
    for label in sorted(_H_LABELS):
        assert derive_invest_type_std(label) == "H"
        assert infer_invest_type(None, label, None) == "H"


def test_legacy_balance_analysis_h_labels_still_map_to_h_via_wrapper() -> None:
    missing_in_canonical = _LEGACY_BALANCE_ANALYSIS_H_LABELS - frozenset(_HAT_H_LABEL_SUBSTRINGS)
    assert not missing_in_canonical, (
        f"legacy H labels missing from _HAT_H_LABEL_SUBSTRINGS: {sorted(missing_in_canonical)}"
    )
    for label in sorted(_LEGACY_BALANCE_ANALYSIS_H_LABELS):
        assert derive_invest_type_std(label) == "H"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("可供出售金融资产", "A"),
        ("其他债权投资", "A"),
        ("AFS port", "A"),
        ("FVOCI book", "A"),
        ("OCI bucket", "A"),
        ("交易性金融资产", "T"),
        ("TRADING_ASSET_RAW", "T"),
        ("fvtpl assets", "T"),
        ("tpl bucket", "T"),
        ("持有至到期投资", "H"),
        ("摊余成本计量金融资产", "H"),
        ("HTM port", "H"),
        *[(s, "H") for s in _HAT_H_LABEL_SUBSTRINGS],
    ],
)
def test_match_invest_type_by_substring_parametrized(value: str, expected: str) -> None:
    assert _match_invest_type_by_substring(value) == expected


@pytest.mark.parametrize("value", ["", "  ", "完全不相关的标签"])
def test_match_and_infer_return_none_for_non_matching_labels(value: str) -> None:
    assert _match_invest_type_by_substring(value) is None
    assert infer_invest_type(None, value, None) is None


def test_derive_invest_type_std_empty_string_raises_legacy_value_error() -> None:
    with pytest.raises(ValueError, match="Unrecognized invest_type_raw"):
        derive_invest_type_std("")


def test_infer_asset_type_suffix_wins_before_substring_fallback() -> None:
    assert infer_invest_type("portfolioH", "asset_T", None) == "T"


def test_infer_substring_fallback_uses_asset_class_when_types_absent() -> None:
    assert infer_invest_type(None, None, "买入返售证券") == "H"


@pytest.mark.parametrize(
    ("interest", "expected"),
    [
        (Decimal("1.5"), "H"),
        (Decimal("-1"), "T"),
    ],
)
def test_infer_nonstd_interest_income_branch(interest: Decimal, expected: str) -> None:
    assert infer_invest_type(None, None, None, interest_income=interest, is_nonstd=True) == expected
