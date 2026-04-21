from __future__ import annotations

from typing import Literal

from backend.app.core_finance.config import CNY_CURRENCIES, USD_CURRENCIES

NormalizedInvestTypeStd = Literal["H", "A", "T"]
NormalizedAccountingBasis = Literal["AC", "FVOCI", "FVTPL"]
NormalizedCurrencyBasis = Literal["CNY", "CNX"]

_H_LABELS = frozenset(
    {
        "应收投资款项",
        "发行类债务",
        "发行类债券",
        "拆放同业",
        "买入返售证券",
        "存放同业",
        "同业拆入",
        "同业存放",
        "卖出回购证券",
        "卖出回购票据",
        "持有至到期同业存单",
    }
)


def is_approved_status(value: str | None) -> bool:
    return str(value or "").strip().lower() == "approved"


def derive_invest_type_std_value(invest_type_raw: str) -> NormalizedInvestTypeStd:
    raw = str(invest_type_raw or "")
    normalized = raw.strip().lower()
    upper = raw.strip().upper()
    if not normalized:
        raise ValueError("invest_type_raw is required")
    if "可供出售" in normalized or "AFS" in upper or "FVOCI" in upper or "其他债权" in normalized or "OCI" in upper:
        return "A"
    if "交易" in normalized or "TRADING" in upper or "FVTPL" in upper or "TPL" in upper or upper in {"T", "TRADING_ASSET_RAW"}:
        return "T"
    if "持有至到期" in normalized or "HTM" in upper or "摊余成本" in normalized:
        return "H"
    if any(label.lower() in normalized for label in _H_LABELS):
        return "H"
    raise ValueError(f"Unrecognized invest_type_raw={invest_type_raw!r}")


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
