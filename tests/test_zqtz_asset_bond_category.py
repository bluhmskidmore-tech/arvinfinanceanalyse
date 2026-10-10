"""黄金样例：ZQTZ 资产侧债券单行分类（与资产负债表迁徙语义对齐）。"""

from __future__ import annotations

import duckdb
import pytest

from backend.app.core_finance.zqtz_asset_bond_category import (
    ZQTZ_ASSET_BOND_ROWS,
    _row_matches_definition,
    classify_zqtz_asset_bond_label,
    is_parent_zqtz_business_row,
    match_zqtz_asset_bond_rows,
)
from backend.app.repositories.accounting_asset_movement_repo import AccountingAssetMovementRepository


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


@pytest.mark.parametrize("prefix", ["G0", "G2"])
def test_trust_prefix_matches_one_parent_and_trust_detail(prefix: str) -> None:
    row = {"bond_type": "其他", "instrument_code": f"{prefix}-TRUST", "currency_code": "CNY"}
    matches = match_zqtz_asset_bond_rows(row)
    parents = [
        item["row_key"] for item in matches
        if is_parent_zqtz_business_row(item["row_key"], item["row_label"], item.get("source_note"))
    ]
    assert parents == ["asset_zqtz_non_bottom_investment"]
    assert {item["row_key"] for item in matches} == {
        "asset_zqtz_non_bottom_investment", "asset_zqtz_detail_trust_plan",
    }
    assert classify_zqtz_asset_bond_label(row) == "信托计划"


def test_fi_large_cd_source_alias_matches_interbank_cd() -> None:
    row = {
        "bond_type": "大额存单", "asset_class": "大额存单", "instrument_code": "112-TEST",
        "instrument_name": "测试银行CD001", "currency_code": "CNY",
    }
    assert [item["row_key"] for item in match_zqtz_asset_bond_rows(row)] == ["asset_zqtz_interbank_cd"]


@pytest.mark.parametrize("instrument_code", ["292680026", "292680027"])
@pytest.mark.parametrize("bond_type", ["企业债", "其他"])
def test_indonesia_sovereign_cny_bonds_match_only_foreign_bonds(instrument_code: str, bond_type: str) -> None:
    # FI 导出标为企业债，正式余额标为其他；二者均为印尼政府人民币债。
    row = {
        "instrument_code": instrument_code, "bond_type": bond_type,
        "instrument_name": "26印度尼西亚债01", "issuer_name": "印度尼西亚共和国",
        "currency_code": "CNY",
    }
    assert [item["row_key"] for item in match_zqtz_asset_bond_rows(row)] == ["asset_zqtz_foreign_bond"]


@pytest.mark.parametrize("instrument_code", ["292680004", "292680008", "HK0001145967"])
@pytest.mark.parametrize("bond_type", ["其他", "企业债", "商业银行债"])
def test_owner_confirmed_foreign_bonds_have_one_business_parent(instrument_code: str, bond_type: str) -> None:
    row = {
        "instrument_code": instrument_code,
        "bond_type": bond_type,
        "sub_type": "其他债券",
        "currency_code": "CNY",
        "invest_type_std": "H",
        "accounting_basis": "AC",
    }
    assert [item["row_key"] for item in match_zqtz_asset_bond_rows(row)] == ["asset_zqtz_foreign_bond"]
    assert classify_zqtz_asset_bond_label(row) == "外国债券"


def _sql_matched_row_keys(
    row: dict[str, str | None], row_defs: tuple[dict, ...] = ZQTZ_ASSET_BOND_ROWS,
) -> list[str]:
    columns = (
        "instrument_code", "bond_type", "sub_type", "business_type_primary", "business_type_final",
        "instrument_name", "asset_class", "currency_code", "accounting_basis",
    )
    with duckdb.connect(":memory:") as conn:
        conn.execute(
            "create table fact_formal_zqtz_balance_daily ("
            + ", ".join(f"{column} varchar" for column in columns) + ")"
        )
        conn.execute(
            "insert into fact_formal_zqtz_balance_daily values ("
            + ", ".join("?" for _ in columns) + ")",
            [row.get(column) for column in columns],
        )
        repo = AccountingAssetMovementRepository(path=":memory:")
        matched = []
        for row_def in row_defs:
            predicate, params = repo._zqtz_asset_predicate(conn, row_def)
            if conn.execute(
                f"select count(*) from fact_formal_zqtz_balance_daily where {predicate}", params,
            ).fetchone()[0]:
                matched.append(str(row_def["row_key"]))
        return matched


@pytest.mark.parametrize("code", ["292680004", "292680008", "HK0001145967"])
@pytest.mark.parametrize("suffix", [".IB", "0"])
@pytest.mark.parametrize(
    ("bond_type", "expected"),
    [
        ("其他", []),
        ("企业债", ["asset_zqtz_nonfinancial_enterprise_bond"]),
        ("商业银行债", ["asset_zqtz_commercial_financial_bond"]),
    ],
)
def test_foreign_bond_approval_does_not_extend_to_unapproved_suffixes(
    code: str, suffix: str, bond_type: str, expected: list[str],
) -> None:
    row = {"instrument_code": code + suffix, "bond_type": bond_type, "currency_code": "CNY"}
    assert [item["row_key"] for item in match_zqtz_asset_bond_rows(row)] == expected
    assert _sql_matched_row_keys(row) == expected


@pytest.mark.parametrize("code", ["292680004", "292680008", "HK0001145967"])
@pytest.mark.parametrize("bond_type", ["其他", "企业债", "商业银行债"])
@pytest.mark.parametrize("normalization", ["original", "lower", "surrounding_space"])
def test_confirmed_foreign_codes_match_python_and_sql_after_normalization(
    code: str, bond_type: str, normalization: str,
) -> None:
    if normalization == "lower":
        code = code.lower()
    elif normalization == "surrounding_space":
        code = f" {code} "
    row = {"instrument_code": code, "bond_type": bond_type, "currency_code": "CNY"}
    expected = ["asset_zqtz_foreign_bond"]
    assert [item["row_key"] for item in match_zqtz_asset_bond_rows(row)] == expected
    assert _sql_matched_row_keys(row) == expected


@pytest.mark.parametrize("code", ["US12345", "HK0001155867.EXTRA", "292680026.EXTRA", "292680027.EXTRA"])
def test_existing_foreign_prefixes_keep_python_sql_behavior(code: str) -> None:
    row = {"instrument_code": code, "bond_type": "其他", "currency_code": "CNY"}
    expected = ["asset_zqtz_foreign_bond"]
    assert [item["row_key"] for item in match_zqtz_asset_bond_rows(row)] == expected
    assert _sql_matched_row_keys(row) == expected


@pytest.mark.parametrize(
    ("code", "is_market_value"),
    [("J02205260102", True), ("J09999990102", False), ("J02205260102.EXTRA", False)],
)
def test_j0_market_value_rule_keeps_prefix_and_exact_code_conjunction(
    code: str, is_market_value: bool,
) -> None:
    row = {"instrument_code": code, "bond_type": "其他", "currency_code": "CNY"}
    python_keys = [item["row_key"] for item in match_zqtz_asset_bond_rows(row)]
    assert ("asset_zqtz_detail_local_currency_delegated_market_value" in python_keys) is is_market_value
    assert ("asset_zqtz_detail_local_currency_special_account_cost" in python_keys) is not is_market_value
    assert _sql_matched_row_keys(row) == python_keys


@pytest.mark.parametrize(
    ("code", "bond_type"),
    [
        ("US12345", "企业债"),
        ("HK0001155867", "商业银行债"),
        ("292680026", "企业债"),
        ("292680027", "企业债"),
        ("J02205260102", "其他"),
        ("J09999990102", "其他"),
    ],
)
def test_existing_sql_selectors_follow_python_code_whitespace_normalization(
    code: str, bond_type: str,
) -> None:
    row = {"instrument_code": code, "bond_type": bond_type, "currency_code": "CNY"}
    expected = [item["row_key"] for item in match_zqtz_asset_bond_rows(row)]
    assert _sql_matched_row_keys(row) == expected
    row["instrument_code"] = f" {code.lower()} "
    assert [item["row_key"] for item in match_zqtz_asset_bond_rows(row)] == expected
    assert _sql_matched_row_keys(row) == expected


@pytest.mark.parametrize(
    ("code", "bond_type", "currency", "accounting_basis", "expected"),
    [
        (" exact1 ", "商业银行债", "CNY", "AC", True),
        ("EXACT1.EXTRA", "商业银行债", "CNY", "AC", False),
        (None, "商业银行债", "CNY", "AC", False),
        ("EXACT1", "其他", "CNY", "AC", False),
        ("EXACT1", "商业银行债", "USD", "AC", False),
        ("EXACT1", "商业银行债", "CNY", "TPL", False),
        (" blocked ", "商业银行债", "CNY", "AC", False),
    ],
)
def test_additional_exact_codes_without_prefix_still_obey_other_constraints(
    code: str | None, bond_type: str, currency: str, accounting_basis: str, expected: bool,
) -> None:
    row_def = {
        "row_key": "exact_code_selector",
        "instrument_prefixes": (),
        "additional_instrument_codes": ("EXACT1", "BLOCKED"),
        "exclude_instrument_codes": ("BLOCKED",),
        "match_keywords": ("商业银行债",),
        "accounting_bases": ("AC",),
    }
    row = {
        "instrument_code": code, "bond_type": bond_type, "currency_code": currency,
        "accounting_basis": accounting_basis,
    }
    assert _row_matches_definition(row, row_def) is expected
    assert _sql_matched_row_keys(row, (row_def,)) == (["exact_code_selector"] if expected else [])
