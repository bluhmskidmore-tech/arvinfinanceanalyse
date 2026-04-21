"""W-bond-2026-04-21 caliber migration: bond_analytics common + bond_duration vs hat_mapping."""

from __future__ import annotations

import pytest

from backend.app.core_finance.bond_analytics import common as bond_analytics_common
from backend.app.core_finance.bond_duration import infer_accounting_class


class TestBondAnalyticsCommonCanonicalAccounting:
    """``map_accounting_class`` / ``get_accounting_rule_trace`` delegate to ``infer_invest_type``."""

    @pytest.mark.parametrize(
        ("label", "expected_class", "expected_rule"),
        [
            ("持有至到期投资", "AC", "R001"),
            ("交易性金融资产", "TPL", "R020"),
            ("FVOCI债券", "OCI", "R010"),
            ("完全未知会计类标签", "other", "R999"),
        ],
    )
    def test_map_and_trace(self, label: str, expected_class: str, expected_rule: str) -> None:
        assert bond_analytics_common.map_accounting_class(label) == expected_class
        rule_id, _pat = bond_analytics_common.get_accounting_rule_trace(label)
        assert rule_id == expected_rule


class TestBondDurationInferAccountingClass:
    """``infer_accounting_class`` matches legacy buckets; unknown labels default to TPL."""

    @pytest.mark.parametrize(
        ("label", "expected"),
        [
            ("持有至到期投资", "AC"),
            ("摊余成本", "AC"),
            ("债权投资", "AC"),
            ("交易性金融资产", "TPL"),
            ("TPL bucket", "TPL"),
            ("可供出售债券", "OCI"),
            ("", "TPL"),
            ("not_a_real_label_xyz", "TPL"),
        ],
    )
    def test_hat_and_fallback_branches(self, label: str, expected: str) -> None:
        assert infer_accounting_class(label) == expected
