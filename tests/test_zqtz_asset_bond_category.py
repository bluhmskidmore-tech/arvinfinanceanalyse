"""黄金样例：ZQTZ 资产侧债券单行分类（与资产负债表迁徙语义对齐）。"""

from __future__ import annotations

import pytest

from backend.app.core_finance.zqtz_asset_bond_category import (
    classify_zqtz_asset_bond_label,
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
