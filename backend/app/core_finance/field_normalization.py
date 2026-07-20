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
    "TRADING_STATUS_SQL_IN_LIST",
    "TRADING_STATUS_VALUES",
    "derive_accounting_basis_value",
    "is_approved_status",
    "is_trading_status",
    "normalize_currency_basis_value",
    "original_asset_currency_from_instrument_code",
    "resolve_pnl_source_currency",
]

# 供应商 tradestatus 字段的"可交易"取值词表（英文大小写不敏感，已折叠为小写）。
# 这是 Livermore 相关服务判定个股当日是否处于正常交易状态的唯一口径。
TRADING_STATUS_VALUES: tuple[str, ...] = ("trading", "交易", "正常交易")

# 供 SQL 使用的 IN 列表片段，须配合 lower(trim(...)) 归一化后的列表达式使用，
# 例如: f"lower(trim(coalesce(tradestatus, ''))) in {TRADING_STATUS_SQL_IN_LIST}"
TRADING_STATUS_SQL_IN_LIST: str = "(" + ", ".join(f"'{value}'" for value in TRADING_STATUS_VALUES) + ")"


def is_trading_status(value: object | None) -> bool:
    return str(value or "").strip().casefold() in TRADING_STATUS_VALUES


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
