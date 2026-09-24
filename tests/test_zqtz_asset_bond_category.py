"""黄金样例：ZQTZ 资产侧债券单行分类（与资产负债表迁徙语义对齐）。"""

from __future__ import annotations

import pytest

from backend.app.core_finance.zqtz_asset_bond_category import (
    ZQTZ_ASSET_BOND_ROWS,
    classify_zqtz_asset_bond_label,
    is_parent_zqtz_business_row,
    match_zqtz_asset_bond_rows,
)


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        # 关键字 + 币种：默认仅限 CNY
        (
            {
                "bond_type": "国债",
                "sub_type": "",
                "instrument_name": "",
                "instrument_code": "",
                "currency_code": "CNY",
            },
            "国债（含凭证式国债）",
        ),
        (
            {
                "bond_type": "",
                "sub_type": "",
                "instrument_name": "某公司中期票据",
                "instrument_code": "012345.SH",
                "currency_code": "CNY",
            },
            "非金融企业债券",
        ),
        # 外国债券：US 前缀优先于非金融的企业债字面匹配（若同时为 USXXX）
        (
            {
                "bond_type": "企业债",
                "instrument_name": "US Corp",
                "instrument_code": "US12345",
                "currency_code": "USD",
                "business_type_primary": "",
            },
            "外国债券",
        ),
        # 商业性金融债排除 HK 清单 code，归入外国债券
        (
            {
                "bond_type": "",
                "sub_type": "商业银行债",
                "instrument_code": "HK0001155867",
                "instrument_name": "",
                "currency_code": "",
            },
            "外国债券",
        ),
        # 非金融企业债券：排除名称含铁道
        (
            {
                "bond_type": "企业债",
                "instrument_name": "某铁道建设企业债",
                "instrument_code": "198765",
                "currency_code": "CNY",
            },
            "铁道债",
        ),
        # 非底层 vs 信托（G0 细档优先）
        (
            {
                "bond_type": "其他",
                "instrument_code": "G0123",
                "instrument_name": "",
                "currency_code": "CNY",
            },
            "信托计划",
        ),
        # J0 + 市值法清单
        (
            {
                "bond_type": "其他",
                "instrument_code": "J02205260102",
                "instrument_name": "",
                "currency_code": "CNY",
            },
            "其中：本币委外（市值法）",
        ),
        # J0 + 不在市值法清单 → 成本法专户
        (
            {
                "bond_type": "其他",
                "instrument_code": "J09999990102",
                "instrument_name": "",
                "currency_code": "CNY",
            },
            "其中：本币专户（成本法）",
        ),
        # 公募基金
        (
            {
                "bond_type": "其他",
                "instrument_code": "SA0001",
                "instrument_name": "",
                "currency_code": "CNY",
            },
            "公募基金",
        ),
        (
            {
                "bond_type": "其他",
                "instrument_code": "JM0001",
                "instrument_name": "",
                "currency_code": "CNY",
            },
            "其他债权融资类产品",
        ),
        (
            {
                "bond_type": "其他",
                "instrument_code": "J40001",
                "instrument_name": "",
                "currency_code": "CNY",
            },
            "结构化融资（券商）",
        ),
        # 敞口/损益行常见「资管计划」标签，须与「其他」等价归入 J0/J1/J4 桶（否则业务种类漏数）
        (
            {
                "bond_type": "资管计划",
                "business_type_primary": "资管计划",
                "business_type_final": "资管计划",
                "sub_type": "",
                "instrument_code": "J09999990102",
                "instrument_name": "",
                "currency_code": "CNY",
            },
            "其中：本币专户（成本法）",
        ),
    ],
)
def test_classify_zqtz_asset_bond_label(row: dict[str, str], expected: str) -> None:
    assert classify_zqtz_asset_bond_label(row) == expected


def test_match_zqtz_asset_bond_rows_includes_securities_am_for_asset_management_bond_type() -> None:
    row = {
        "bond_type": "资管计划",
        "business_type_primary": "资管计划",
        "business_type_final": "资管计划",
        "sub_type": "",
        "instrument_name": "某资管",
        "instrument_code": "J01234560102",
        "asset_class": "资管计划",
        "currency_code": "CNY",
    }
    keys = [r["row_key"] for r in match_zqtz_asset_bond_rows(row)]
    assert "asset_zqtz_detail_securities_asset_management_plan" in keys
    assert "asset_zqtz_non_bottom_investment" in keys


# 迁移自已删除的 tests/test_zqtz_adb_rollup_contract.py（原 test_backend_has_at_least_one_detail_row）。
# 那份前后端同步契约已随口径修正作废：前端 ADB rollup 手工父子映射与 fixture 已下线，
# 父级日均改由后端 /api/pnl/by-business-ytd 在父级行直接返回 avg_balance。
# 但 source_note 中的「其中项」标记不是纯注释——is_parent_zqtz_business_row
# （pnl-by-business live 与 precompute 路径共用的父级行判定）把它作为细分行信号之一，
# 因此该标记不变量保留在本文件继续守护。
def test_detail_row_marker_rows_exist_and_are_never_parent_rows() -> None:
    marked_rows = [row for row in ZQTZ_ASSET_BOND_ROWS if "其中项" in str(row.get("source_note", ""))]
    assert marked_rows, (
        "未能在 ZQTZ_ASSET_BOND_ROWS 中找到任何 source_note 含「其中项」的细分行；"
        "该标记是 is_parent_zqtz_business_row 的细分行判定信号之一，"
        "整体消失说明判定信号已退化，需人工复核父级行口径"
    )
    for row in marked_rows:
        assert not is_parent_zqtz_business_row(
            str(row["row_key"]), str(row["row_label"]), row.get("source_note")
        ), f"source_note 含「其中项」的行 {row['row_key']} 被判定为父级行，父/子口径将重复计数"


def test_unclassified_returns_other() -> None:
    assert (
        classify_zqtz_asset_bond_label(
            {
                "bond_type": "",
                "sub_type": "",
                "instrument_name": "",
                "instrument_code": "",
                "currency_code": "CNY",
            }
        )
        == "其它"
    )
