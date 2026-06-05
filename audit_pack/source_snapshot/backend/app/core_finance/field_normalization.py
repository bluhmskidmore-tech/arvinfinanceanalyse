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

# Re-export: canonical tokens live in ``accounting_basis_constants`` (leaf module)
# to avoid import cycles with ``config.classification_rules``.

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
