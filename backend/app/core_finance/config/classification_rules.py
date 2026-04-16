"""
Canonical classification rules shared across core finance services.
（自 MOSS-V2 core_finance/config 迁入）
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

CNY_CURRENCIES: tuple[str, ...] = ("人民币", "CNY", "RMB", "CNH")
USD_CURRENCIES: tuple[str, ...] = ("美元", "USD")

LEDGER_ASSET_ACCOUNT_PREFIXES: tuple[str, ...] = ("120", "121", "140", "141", "142", "143", "144")
LEDGER_LIABILITY_ACCOUNT_PREFIXES: tuple[str, ...] = ("233", "234", "235", "241", "242", "255", "272")
LEDGER_PNL_ACCOUNT_PREFIXES: tuple[str, ...] = ("514", "516", "517")

INTERBANK_ASSET_KEYWORDS: tuple[str, ...] = (
    "%拆放%",
    "%拆出%",
    "%存放%",
    "%买入返售%",
    "%逆回购%",
)

INTERBANK_LIABILITY_KEYWORDS: tuple[str, ...] = (
    "%拆入%",
    "%卖出回购%",
    "%同业存放%",
    "%存放同业%",
    "%吸收%",
    "%存入%",
)

INTERBANK_LIABILITY_CORE_KEYWORDS: tuple[str, ...] = (
    "%拆入%",
    "%卖出回购%",
)

NCD_KEYWORDS: tuple[str, ...] = (
    "%同业存单%",
    "%存单%",
)

INTERBANK_ASSET_KEYWORDS_PLAIN: tuple[str, ...] = (
    "拆出",
    "拆放",
    "存放",
    "买入",
    "逆回购",
    "买入返售",
)

INTERBANK_LIABILITY_KEYWORDS_PLAIN: tuple[str, ...] = (
    "拆入",
    "卖出",
    "吸收",
    "存入",
    "同业存放",
)


def _contains_sql_like_substring(text: str, pattern: str) -> bool:
    core = pattern.strip("%")
    return bool(core) and core in text


def is_bond_liability(asset_class: Optional[str]) -> bool:
    if asset_class is None:
        return False
    normalized = str(asset_class).strip()
    upper = normalized.upper()
    return (
        upper == "ISSUED"
        or "发行类" in normalized
        or "发行" in normalized
        or "负债" in normalized
    )


def is_bond_asset(asset_class: Optional[str]) -> bool:
    if asset_class is None:
        return True
    return not is_bond_liability(asset_class)


def is_interbank_asset(product_type: Optional[str]) -> bool:
    text = str(product_type or "")
    if any(_contains_sql_like_substring(text, kw) for kw in INTERBANK_ASSET_KEYWORDS):
        return True
    return any(kw in text for kw in INTERBANK_ASSET_KEYWORDS_PLAIN)


def is_interbank_liability(product_type: Optional[str]) -> bool:
    text = str(product_type or "")
    return any(_contains_sql_like_substring(text, kw) for kw in INTERBANK_LIABILITY_KEYWORDS)


def is_interbank_liability_core(product_type: Optional[str]) -> bool:
    text = str(product_type or "")
    return any(_contains_sql_like_substring(text, kw) for kw in INTERBANK_LIABILITY_CORE_KEYWORDS)


def infer_invest_type(
    portfolio: Optional[str],
    asset_type: Optional[str],
    asset_class: Optional[str] = None,
    interest_income: Optional[Decimal] = None,
    is_nonstd: bool = False,
) -> Optional[str]:
    if is_nonstd and interest_income is not None:
        return "H" if interest_income > 0 else "T"
    for value in (asset_type, portfolio):
        if not value:
            continue
        text = str(value).strip().upper()
        if text in ("A", "T", "H"):
            return text
        if text and text[-1] in ("A", "T", "H"):
            return text[-1]
    if asset_class:
        normalized = str(asset_class).strip()
        upper = normalized.upper()
        if "可供出售" in normalized or "AFS" in upper:
            return "A"
        if "交易" in normalized or "TRADING" in upper:
            return "T"
        if "持有至到期" in normalized or "HTM" in upper:
            return "H"
    return None
