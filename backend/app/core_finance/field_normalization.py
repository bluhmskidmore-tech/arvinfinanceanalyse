from __future__ import annotations

from typing import Literal

from backend.app.core_finance.config import CNY_CURRENCIES, USD_CURRENCIES

from .accounting_basis_constants import (
    ACCOUNTING_BASIS_AC,
    ACCOUNTING_BASIS_FVOCI,
    ACCOUNTING_BASIS_FVTPL,
)

NormalizedInvestTypeStd = Literal["H", "A", "T"]
NormalizedAccountingBasis = Literal["AC", "FVOCI", "FVTPL"]
NormalizedCurrencyBasis = Literal["CNY", "CNX"]
OriginalAssetCurrency = Literal["CNY", "USD"]

# Re-export: canonical tokens live in ``accounting_basis_constants`` (leaf module)
# to avoid import cycles with ``config.classification_rules``.
__all__ = [
    "ACCOUNTING_BASIS_AC",
    "ACCOUNTING_BASIS_FVOCI",
    "ACCOUNTING_BASIS_FVTPL",
    "NormalizedAccountingBasis",
    "NormalizedCurrencyBasis",
    "NormalizedInvestTypeStd",
    "OriginalAssetCurrency",
    "TRADABLE_STATUS_SQL_IN_LIST",
    "TRADABLE_STATUS_VALUES",
    "TRADING_STATUS_VALUES",
    "derive_accounting_basis_value",
    "is_approved_status",
    "is_tradestatus_halted",
    "is_tradestatus_tradable",
    "normalize_currency_basis_value",
    "original_asset_currency_from_instrument_code",
    "resolve_pnl_source_currency",
    "tradable_status_sql_condition",
]

# 供应商 tradestatus 字段的"明确正常交易"取值词表（英文大小写不敏感，已折叠为小写）。
TRADING_STATUS_VALUES: tuple[str, ...] = ("trading", "交易", "正常交易")

# "可交易"完整词表：明确交易词表 + "复牌"（复牌当日即恢复正常交易，
# docs/data_contracts.md §4.10；旧词表把复牌日误判为不可交易）。
TRADABLE_STATUS_VALUES: tuple[str, ...] = (*TRADING_STATUS_VALUES, "复牌")

# choice_stock_daily_observation 的 tradestatus 语义（docs/data_contracts.md §4.10）：
# choice_native 代际（2026-01-05 起）不提供状态字段，落地为空串；空串/NULL/空白
# 视为正常交易日。非空值按可交易词表判定（"停牌一天"/"连续停牌"等即不可交易）。
# SQL IN 列表首项 '' 即空白语义；须配合 lower(trim(coalesce(..., ''))) 归一化使用。
TRADABLE_STATUS_SQL_IN_LIST: str = "(" + ", ".join(f"'{value}'" for value in ("", *TRADABLE_STATUS_VALUES)) + ")"


def is_tradestatus_tradable(value: object | None) -> bool:
    """判定 tradestatus 是否为可交易日：空串/None/空白 → True；非空按词表。"""
    text = str(value or "").strip()
    if not text:
        return True
    return text.casefold() in TRADABLE_STATUS_VALUES


def is_tradestatus_halted(value: object | None) -> bool:
    """判定 tradestatus 是否为显式停牌/不可交易日：非空且不可交易。

    与 ``is_tradestatus_tradable`` 在非空域互补：空串/None/空白是 choice_native
    代际的正常交易日（不是停牌）；"停牌一天"/"连续停牌"/"盘中停牌"/"Suspended"
    等非空非可交易词值判停牌；未知非空值 fail-closed 判停牌（卖出顺延方向保守
    正确）。SQL 侧同语义请用 ``not tradable_status_sql_condition(...)``。
    """
    text = str(value or "").strip()
    return bool(text) and not is_tradestatus_tradable(text)


def tradable_status_sql_condition(column_expr: str) -> str:
    """生成与 ``is_tradestatus_tradable`` 同语义的 SQL 判定片段。

    ``column_expr`` 为 tradestatus 列表达式（可带表别名）；NULL/空白归一化为
    空串后落入 IN 列表首项，与 Python 侧口径一致。
    """
    return f"(lower(trim(coalesce(cast({column_expr} as varchar), ''))) in {TRADABLE_STATUS_SQL_IN_LIST})"


def is_approved_status(value: str | None) -> bool:
    return str(value or "").strip().lower() == "approved"


def derive_accounting_basis_value(
    invest_type_std: NormalizedInvestTypeStd,
) -> NormalizedAccountingBasis:
    mapping: dict[NormalizedInvestTypeStd, NormalizedAccountingBasis] = {
        "H": "AC",
        "A": "FVOCI",
        "T": "FVTPL",
    }
    return mapping[invest_type_std]


def normalize_currency_basis_value(value: str | None) -> NormalizedCurrencyBasis:
    normalized = str(value or "").strip()
    upper = normalized.upper()
    if not normalized:
        return "CNY"
    if upper == "CNX" or normalized == "综本":
        return "CNX"
    if normalized in CNY_CURRENCIES or upper in {"CNY", "RMB", "CNH"}:
        return "CNY"
    raise ValueError(f"Unsupported currency_basis={value}")


def original_asset_currency_from_instrument_code(
    value: object,
    currency_code: object = None,
) -> OriginalAssetCurrency:
    normalized_currency = str(currency_code or "").strip()
    upper_currency = normalized_currency.upper()
    if normalized_currency in USD_CURRENCIES or upper_currency == "USD":
        return "USD"
    if normalized_currency in CNY_CURRENCIES or upper_currency in {"CNY", "RMB", "CNH"}:
        return "CNY"
    instrument_code = str(value or "").strip().upper()
    return "USD" if instrument_code.startswith("J1") else "CNY"


def resolve_pnl_source_currency(value: str | None) -> tuple[NormalizedCurrencyBasis, str | None]:
    normalized = str(value or "").strip()
    upper = normalized.upper()
    if not normalized:
        return "CNY", None
    if upper == "CNX" or normalized == "综本":
        return "CNX", None
    if normalized in CNY_CURRENCIES or upper in {"CNY", "RMB", "CNH"}:
        return "CNY", None
    if normalized in USD_CURRENCIES or upper == "USD":
        return "CNY", "USD"
    raise ValueError(f"Unsupported pnl source currency={value}")
