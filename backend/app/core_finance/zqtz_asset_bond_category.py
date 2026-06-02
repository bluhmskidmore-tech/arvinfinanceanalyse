"""
ZQTZ 资产侧债券明细分类 — 与 `accounting_asset_movement_repo` 中资产配置一致。

单行归类：遍历规则时按 ``sort_order`` **降序**（先匹配更细的「其中」行），保证每条头寸只属于一个 bucket。
"""

from __future__ import annotations

from typing import Any, Mapping

# 固收/非标 V1 的 classification_row 里，bond_type、business_type_primary 常为「资管计划」「证券业资管计划」等，
# 与 ZQTZ 敞口「其他」并存；仅匹配「其他」会使 match_zqtz_asset_bond_rows 落空，业务种类损益该行严重偏小。
_ZQTZ_PREFIX_BUCKET_BOND_TYPES: tuple[str, ...] = (
    "其他",
    "资管计划",
    "证券业资管计划",
    "债权投资",
    "特定目的载体及其他非标类",
)

# 唯一规则源：`_ZQTZ_ASSET_ROWS` 从本模块导出，迁徙页 DuckDB predicate 与用户态分类共用。
ZQTZ_ASSET_BOND_ROWS: tuple[dict[str, Any], ...] = (
    {
        "row_key": "asset_zqtz_central_bank_bill",
        "row_label": "央行票据",
        "sort_order": 60,
        "match_keywords": ("央行票据", "央票"),
        "source_note": "ZQTZSHOW sub_type/bond_type/name keyword in 央行票据/央票",
    },
    {
        "row_key": "asset_zqtz_treasury_bond",
        "row_label": "国债（含凭证式国债）",
        "sort_order": 62,
        "match_keywords": ("国债", "记账式国债", "凭证式国债"),
        "source_note": "ZQTZSHOW sub_type/bond_type/name keyword in 国债/记账式国债/凭证式国债",
    },
    {
        "row_key": "asset_zqtz_local_government_bond",
        "row_label": "地方政府债",
        "sort_order": 64,
        "match_keywords": ("地方政府债", "地方债", "地方政府债券"),
        "source_note": "ZQTZSHOW sub_type/bond_type/name keyword in 地方政府债/地方债/地方政府债券",
    },
    {
        "row_key": "asset_zqtz_policy_financial_bond",
        "row_label": "政策性金融债",
        "sort_order": 66,
        "match_keywords": ("政策性金融债", "政金债", "政策性银行债"),
        "source_note": "ZQTZSHOW sub_type/bond_type/name keyword in 政策性金融债/政金债/政策性银行债",
    },
    {
        "row_key": "asset_zqtz_railway_bond",
        "row_label": "铁道债",
        "sort_order": 68,
        "match_keywords": ("铁道债", "中国铁路", "铁道"),
        "source_note": "ZQTZSHOW sub_type/bond_type/name keyword in 铁道债/中国铁路/铁道",
    },
    {
        "row_key": "asset_zqtz_commercial_financial_bond",
        "row_label": "商业性金融债",
        "sort_order": 70,
        "match_keywords": ("商业性金融债", "次级债券", "商业银行债", "非银行金融债"),
        "exclude_instrument_codes": ("HK0001155867",),
        "source_note": "ZQTZSHOW sub_type/bond_type/name keyword in 商业性金融债/次级债券/商业银行债/非银行金融债",
    },
    {
        "row_key": "asset_zqtz_interbank_cd",
        "row_label": "同业存单",
        "sort_order": 72,
        "match_keywords": ("同业存单", "NCD"),
        "source_note": "ZQTZSHOW sub_type/bond_type/name keyword in 同业存单/NCD",
    },
    {
        "row_key": "asset_zqtz_nonfinancial_enterprise_bond",
        "row_label": "非金融企业债券",
        "sort_order": 74,
        "match_keywords": (
            "非金融企业债券",
            "企业债",
            "公司债",
            "中期票据",
            "短期融资券",
            "信用债券-企业",
            "信用债券-公用事业",
        ),
        "exclude_instrument_prefixes": ("US",),
        "exclude_name_contains": ("铁道",),
        "include_foreign_currency": True,
        "source_note": "ZQTZSHOW ... 剔除铁道债/外国债券清单",
    },
    {
        "row_key": "asset_zqtz_abs",
        "row_label": "资产支持证券",
        "sort_order": 76,
        "match_keywords": ("资产支持证券", "ABS", "资产证券化"),
        "source_note": "ZQTZSHOW sub_type/bond_type/name keyword in 资产支持证券/ABS/资产证券化",
    },
    {
        "row_key": "asset_zqtz_foreign_bond",
        "row_label": "外国债券",
        "sort_order": 78,
        "instrument_prefixes": ("US", "HK0001155867"),
        "source_note": "ZQTZSHOW 外国债券按披露：US* + HK0001155867*",
    },
    {
        "row_key": "asset_zqtz_public_fund",
        "row_label": "公募基金",
        "sort_order": 80,
        "bond_types": _ZQTZ_PREFIX_BUCKET_BOND_TYPES,
        "instrument_prefixes": ("SA",),
        "source_note": "ZQTZSHOW bond_type=其他 and instrument_code prefix=SA",
    },
    {
        "row_key": "asset_zqtz_non_bottom_investment",
        "row_label": "非底层投资资产",
        "sort_order": 82,
        "bond_types": _ZQTZ_PREFIX_BUCKET_BOND_TYPES,
        "instrument_prefixes": ("G0", "J0", "J1", "J4"),
        "source_note": "ZQTZSHOW bond_type=其他 and instrument_code prefix in G0/J0/J1/J4",
    },
    {
        "row_key": "asset_zqtz_detail_trust_plan",
        "row_label": "信托计划",
        "sort_order": 83,
        "bond_types": _ZQTZ_PREFIX_BUCKET_BOND_TYPES,
        "instrument_prefixes": ("G0",),
        "source_note": "ZQTZSHOW 其中项：instrument_code prefix=G0",
    },
    {
        "row_key": "asset_zqtz_detail_securities_asset_management_plan",
        "row_label": "证券业资管计划",
        "sort_order": 84,
        "bond_types": _ZQTZ_PREFIX_BUCKET_BOND_TYPES,
        "instrument_prefixes": ("J0", "J1", "J4"),
        "source_note": "ZQTZSHOW 其中项：instrument_code prefix in J0/J1/J4",
    },
    {
        "row_key": "asset_zqtz_detail_structured_finance_broker",
        "row_label": "其中：结构化融资（券商）",
        "sort_order": 85,
        "bond_types": _ZQTZ_PREFIX_BUCKET_BOND_TYPES,
        "instrument_prefixes": ("J4",),
        "source_note": "ZQTZSHOW 其中项：instrument_code prefix=J4",
    },
    {
        "row_key": "asset_zqtz_detail_foreign_currency_delegated",
        "row_label": "其中：外币委外",
        "sort_order": 86,
        "bond_types": _ZQTZ_PREFIX_BUCKET_BOND_TYPES,
        "instrument_prefixes": ("J1",),
        "source_note": "ZQTZSHOW 其中项：instrument_code prefix=J1",
    },
    {
        "row_key": "asset_zqtz_detail_local_currency_delegated_market_value",
        "row_label": "其中：本币委外（市值法）",
        "sort_order": 87,
        "bond_types": _ZQTZ_PREFIX_BUCKET_BOND_TYPES,
        "instrument_prefixes": ("J0",),
        "instrument_codes": ("J02205260102", "J02503280102", "J02512240102"),
        "source_note": "ZQTZSHOW 其中项：J0 市值法产品清单",
    },
    {
        "row_key": "asset_zqtz_detail_local_currency_special_account_cost",
        "row_label": "其中：本币专户（成本法）",
        "sort_order": 88,
        "bond_types": _ZQTZ_PREFIX_BUCKET_BOND_TYPES,
        "instrument_prefixes": ("J0",),
        "exclude_instrument_codes": ("J02205260102", "J02503280102", "J02512240102"),
        "source_note": "ZQTZSHOW 其中项：J0 剔除市值法清单后的成本法专户",
    },
    {
        "row_key": "asset_zqtz_other_debt_financing",
        "row_label": "其他债权融资类产品",
        "sort_order": 90,
        "bond_types": _ZQTZ_PREFIX_BUCKET_BOND_TYPES,
        "instrument_prefixes": ("JM",),
        "source_note": "ZQTZSHOW bond_type=其他 and instrument_code prefix=JM",
    },
)


def _norm_txt(v: object) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _keyword_match_any(row: Mapping[str, Any], keywords: tuple[str, ...]) -> bool:
    if not keywords:
        return True
    cols = (
        "sub_type",
        "business_type_final",
        "business_type_primary",
        "bond_type",
        "instrument_name",
        "asset_class",
    )
    for col in cols:
        text = _norm_txt(row.get(col))
        if not text:
            continue
        for kw in keywords:
            if kw and kw in text:
                return True
    return False


def _instrument_code_upper(row: Mapping[str, Any]) -> str:
    return _norm_txt(row.get("instrument_code")).upper()


def _row_matches_definition(row: Mapping[str, Any], row_def: dict[str, Any]) -> bool:
    has_selector = False

    match_keywords = tuple(str(x) for x in row_def.get("match_keywords", ()))
    if match_keywords:
        has_selector = True
        if not _keyword_match_any(row, match_keywords):
            return False

    bond_types = tuple(str(x) for x in row_def.get("bond_types", ()))
    if bond_types:
        has_selector = True
        bt = _norm_txt(row.get("bond_type"))
        btp = _norm_txt(row.get("business_type_primary"))
        if not ((bt in bond_types) or (btp in bond_types)):
            return False

    exclude_bond_types = tuple(str(x) for x in row_def.get("exclude_bond_types", ()))
    if exclude_bond_types:
        has_selector = True
        bt = _norm_txt(row.get("bond_type"))
        if bt and bt in exclude_bond_types:
            return False

    code_u = _instrument_code_upper(row)

    prefixes = tuple(str(x) for x in row_def.get("instrument_prefixes", ()))
    if prefixes:
        has_selector = True
        if not code_u or not any(code_u.startswith(p.upper()) for p in prefixes):
            return False

    for p in tuple(str(x) for x in row_def.get("exclude_instrument_prefixes", ())):
        if code_u.startswith(p.upper()):
            return False

    instrument_codes = tuple(str(x) for x in row_def.get("instrument_codes", ()))
    if instrument_codes:
        has_selector = True
        if code_u not in {c.upper() for c in instrument_codes}:
            return False

    exclude_instrument_codes = tuple(str(x) for x in row_def.get("exclude_instrument_codes", ()))
    if exclude_instrument_codes:
        ex_set = {c.upper() for c in exclude_instrument_codes}
        if code_u and code_u in ex_set:
            return False

    name_contains = tuple(str(x) for x in row_def.get("name_contains", ()))
    if name_contains:
        has_selector = True
        nm = _norm_txt(row.get("instrument_name"))
        if not nm or not any(sub in nm for sub in name_contains):
            return False

    for sub in tuple(str(x) for x in row_def.get("exclude_name_contains", ())):
        nm = _norm_txt(row.get("instrument_name"))
        if sub and nm and sub in nm:
            return False

    accounting_bases = tuple(str(x) for x in row_def.get("accounting_bases", ()))
    if accounting_bases:
        has_selector = True
        ab = _norm_txt(row.get("accounting_basis"))
        if ab not in accounting_bases:
            return False

    currency_codes_exclude = tuple(str(x) for x in row_def.get("currency_codes_exclude", ()))
    if currency_codes_exclude:
        cc = _norm_txt(row.get("currency_code"))
        if cc in currency_codes_exclude:
            return False

    elif (bond_types or match_keywords) and not prefixes and not row_def.get("include_foreign_currency"):
        cc = _norm_txt(row.get("currency_code"))
        if cc and cc.upper() != "CNY":
            return False

    return has_selector


_ZQTZ_ASSET_ROWS_DESC = tuple(sorted(ZQTZ_ASSET_BOND_ROWS, key=lambda r: int(r["sort_order"]), reverse=True))


def match_zqtz_asset_bond_rows(row: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    """Return every ZQTZ asset row definition matched by ``row`` in display order."""
    return tuple(row_def for row_def in ZQTZ_ASSET_BOND_ROWS if _row_matches_definition(row, row_def))


def classify_zqtz_asset_bond_label(row: Mapping[str, Any]) -> str:
    """返回与 ``row_label`` 一致的展示类目；不匹配时 ``其它``。"""
    for row_def in _ZQTZ_ASSET_ROWS_DESC:
        if _row_matches_definition(row, row_def):
            return str(row_def["row_label"])
    return "其它"
