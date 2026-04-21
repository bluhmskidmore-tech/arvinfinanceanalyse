"""W-pnl-2026-04-21 trial migration of pnl onto canonical hat_mapping.

Equivalence and contract tests for ``pnl._normalize_fi_invest_type`` delegating to
``classification_rules.infer_invest_type`` + ``derive_accounting_basis_value``.
"""

from __future__ import annotations

import pytest

from backend.app.core_finance import pnl
from backend.app.core_finance.config.classification_rules import infer_invest_type
from backend.app.core_finance.field_normalization import _H_LABELS, derive_accounting_basis_value
from backend.app.core_finance.pnl import _normalize_fi_invest_type


def _canonical_invest_type_pair(raw: str) -> tuple[str, str]:
    """Expected (invest_type_std, accounting_basis) from the canonical classifier."""
    it = infer_invest_type(None, raw, None)
    assert it is not None, raw
    return it, derive_accounting_basis_value(it)  # type: ignore[arg-type]


@pytest.mark.parametrize("label", sorted(_H_LABELS))
def test_h_labels_equivalence_to_h_ac(label: str) -> None:
    assert _normalize_fi_invest_type(label) == ("H", "AC")


_CURATED_CANONICAL_LABELS: tuple[str, ...] = (
    # H
    "持有至到期投资",
    "摊余成本计量",
    "应收投资款项",
    "买入返售证券",
    "存放同业",
    "卖出回购证券",
    "持有至到期同业存单",
    "HTM",
    "H",
    "发行类债券",
    "发行类债劵",
    # A
    "可供出售债券",
    "AFS",
    "FVOCI",
    "OCI",
    "其他债权投资",
    "A",
    # T
    "交易性金融资产",
    "TRADING_ASSET_RAW",
    "TPL bucket",
    "FVTPL",
    "T",
)


@pytest.mark.parametrize("label", _CURATED_CANONICAL_LABELS)
def test_three_way_matrix_matches_canonical(label: str) -> None:
    assert _normalize_fi_invest_type(label) == _canonical_invest_type_pair(label)


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "   ",
        "完全不相关的标签",
        pytest.param(None, id="none"),
    ],
)
def test_unsupported_raises_value_error(bad: str | None) -> None:
    with pytest.raises(ValueError, match=r"^Unsupported invest_type_raw="):
        _normalize_fi_invest_type(bad)  # type: ignore[arg-type]


def test_legacy_normalize_removed() -> None:
    assert not hasattr(pnl, "_legacy_normalize_fi_invest_type")


def test_no_derive_invest_type_std_value_on_pnl_module() -> None:
    assert "derive_invest_type_std_value" not in dir(pnl)
