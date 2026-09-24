"""Direct tests for core_finance.adb_interbank_labels（同业 product_type → 展示分类）。

生产调用方：backend/app/services/adb_analysis_service.py（side 已归一为 "Asset"/"Liability"，
product_type 可能为 None）。用例锁定 V1 domain_dictionary 对齐的现状行为。
"""

from __future__ import annotations

import pytest

from backend.app.core_finance.adb_interbank_labels import map_ib_category


@pytest.mark.parametrize(
    ("product_type", "side", "expected"),
    [
        ("拆放同业", "Asset", "同业拆出/存放"),
        ("存放同业", "Asset", "同业拆出/存放"),
        ("买入返售金融资产", "Asset", "买入返售"),
        ("同业拆入", "Liability", "同业拆入/存放"),
        ("同业存放", "Liability", "同业拆入/存放"),
        ("卖出回购金融资产", "Liability", "卖出回购"),
    ],
    ids=[
        "asset-拆放",
        "asset-存放",
        "asset-买入返售",
        "liability-拆入",
        "liability-存放",
        "liability-卖出回购",
    ],
)
def test_map_ib_category_main_groupings(
    product_type: str,
    side: str,
    expected: str,
) -> None:
    assert map_ib_category(product_type, side) == expected


@pytest.mark.parametrize(
    ("product_type", "side", "expected"),
    [
        (None, "Asset", "同业资产-其他"),
        (None, "Liability", "同业负债-其他"),
        ("", "Asset", "同业资产-其他"),
        ("   ", "Liability", "同业负债-其他"),
        ("  拆放同业  ", "Asset", "同业拆出/存放"),
        ("金融债投资", "Asset", "同业资产-金融债投资"),
        ("发行同业存单", "Liability", "同业负债-发行同业存单"),
    ],
    ids=[
        "none-asset",
        "none-liability",
        "empty-asset",
        "whitespace-liability",
        "keyword-strip-asset",
        "unknown-asset-passthrough",
        "unknown-liability-passthrough",
    ],
)
def test_map_ib_category_boundary_none_empty_and_unknown_passthrough(
    product_type: str | None,
    side: str,
    expected: str,
) -> None:
    assert map_ib_category(product_type, side) == expected
