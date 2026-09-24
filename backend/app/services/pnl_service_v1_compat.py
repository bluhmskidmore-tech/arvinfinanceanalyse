"""pnl_service 门面的 V1 兼容子模块：V1 分类行构造与业务名称归一化（自 pnl_service.py 逐字拆出）。"""
from __future__ import annotations

from decimal import Decimal

from backend.app.core_finance.zqtz_asset_bond_category import ZQTZ_ASSET_BOND_ROWS

V1_ZQTZ_PREFIX_MAP = {
    "SA": "公募基金",
    "J0": "人民币资管产品",
    "J1": "美元委外产品",
    "J4": "结构化产业基金",
    "JM": "债权投资",
    "G0": "信托结构化产品",
    "G2": "信托产品",
}
V1_BUSINESS_NAME_NORMALIZATION = {
    "存单": "同业存单",
    "次级债": "次级债券",
    "美元委外": "美元委外产品",
    "结构化融资": "信托结构化产品",
    "结构化产品": "结构化产业基金",
    "债券-其他": "其他债券",
    "未分类": "其他债券",
    "大额存单": "同业存单",
    "凭证式国债": "国债",
}


def _v1_record(
    *,
    report_date: str,
    bond_code: str,
    raw_business_type: str,
    interest_income: Decimal,
    fair_value_change: Decimal,
    capital_gain: Decimal,
    source_version: str,
    classification_row: dict[str, object],
) -> dict[str, object]:
    return {
        "report_date": report_date,
        "business_type": _v1_normalize_business_type(raw_business_type, bond_code),
        "bond_code": bond_code,
        "interest_income": interest_income,
        "fair_value_change": fair_value_change,
        "capital_gain": capital_gain,
        "manual_adjustment": Decimal("0"),
        "total_pnl": interest_income + fair_value_change + capital_gain,
        "source_version": source_version,
        "classification_row": classification_row,
    }


def _merge_v1_business_record(groups: dict[str, dict[str, object]], record: dict[str, object]) -> None:
    business_type = str(record["business_type"])
    group = groups.setdefault(
        business_type,
        {
            "interest_income": Decimal("0"),
            "fair_value_change": Decimal("0"),
            "capital_gain": Decimal("0"),
            "total_pnl": Decimal("0"),
            "asset_codes": set(),
            "row_count": 0,
        },
    )
    for key in ("interest_income", "fair_value_change", "capital_gain", "total_pnl"):
        group[key] = Decimal(str(group[key])) + Decimal(str(record[key]))
    code = str(record.get("bond_code") or "").strip()
    if code:
        group["asset_codes"].add(code)
    group["row_count"] = int(group["row_count"]) + 1


def _v1_fi_classification_row(
    *,
    report_date: str,
    row: dict[str, object],
    code: str,
    asset_class: str,
    sub_type: str,
) -> dict[str, object]:
    currency_code = str(row.get("fx_base_currency") or row.get("currency_code") or row.get("currency_basis") or "CNY")
    return {
        "report_date": report_date,
        "instrument_code": code,
        "sub_type": sub_type,
        "business_type_final": sub_type,
        "business_type_primary": sub_type or asset_class,
        "bond_type": asset_class or sub_type,
        "instrument_name": str(row.get("instrument_name") or row.get("bond_name") or code),
        "asset_class": asset_class,
        "currency_code": currency_code.strip().upper() or "CNY",
    }


def _v1_nonstd_classification_row(*, report_date: str, code: str, sub_type: str) -> dict[str, object]:
    bond_type = _zqtz_other_bond_type()
    code_u = code.upper()
    return {
        "report_date": report_date,
        "instrument_code": code,
        "sub_type": sub_type,
        "business_type_final": sub_type,
        "business_type_primary": bond_type,
        "bond_type": bond_type,
        "instrument_name": code,
        "asset_class": sub_type or bond_type,
        "currency_code": "USD" if code_u.startswith("J1") else "CNY",
    }


def _zqtz_other_bond_type() -> str:
    for row_def in ZQTZ_ASSET_BOND_ROWS:
        if row_def.get("row_key") == "asset_zqtz_non_bottom_investment":
            bond_types = tuple(str(value) for value in row_def.get("bond_types", ()))
            if bond_types:
                return bond_types[0]
    return "其他"


def _v1_normalize_business_type(raw_business_type: object, bond_code: object) -> str:
    normalized = V1_BUSINESS_NAME_NORMALIZATION.get(
        str(raw_business_type or "").strip(),
        str(raw_business_type or "").strip() or "其他债券",
    )
    if normalized != "其他债券":
        return normalized
    code = str(bond_code or "").strip().upper()
    if len(code) >= 2:
        return V1_ZQTZ_PREFIX_MAP.get(code[:2], "其他债券")
    return "其他债券"


def _v1_nonstd_display_name(asset_code: object) -> str:
    code = str(asset_code or "").strip()
    if not code or code.lower() in {"nan", "none"}:
        return "未标注"
    for prefix, name in (
        ("J0", "人民币资管产品"),
        ("JM", "债权投资"),
        ("J4", "结构化产业基金"),
        ("J1", "美元委外"),
        ("SA", "公募基金"),
        ("G0", "结构化融资"),
        ("G2", "信托产品"),
    ):
        if code.startswith(prefix):
            return name
    return "其他"


def _v1_fx_rate(base_currency: object, fx_rates: dict[str, Decimal]) -> Decimal:
    key = str(base_currency or "").strip().upper()
    if not key:
        return Decimal("1")
    return fx_rates[key]


def _append_unique_value(bucket: dict[str, object], key: str, value: str) -> None:
    if not value:
        return
    existing = str(bucket.get(key) or "")
    values = [part for part in existing.split("__") if part]
    if value not in values:
        values.append(value)
    bucket[key] = "__".join(values)
