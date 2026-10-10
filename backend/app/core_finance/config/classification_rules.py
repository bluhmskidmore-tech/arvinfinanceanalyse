"""
Canonical classification rules shared across core finance services.
（自 MOSS-V2 core_finance/config 迁入）
"""

from __future__ import annotations

import logging
from decimal import Decimal

from backend.app.core_finance.accounting_basis_constants import (
    ACCOUNTING_BASIS_AC,
    ACCOUNTING_BASIS_FVOCI,
    ACCOUNTING_BASIS_FVTPL,
)

logger = logging.getLogger(__name__)

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

def _contains_sql_like_substring(text: str, pattern: str) -> bool:
    core = pattern.strip("%")
    return bool(core) and core in text


def is_bond_liability(asset_class: str | None) -> bool:
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


def is_bond_asset(asset_class: str | None) -> bool:
    if asset_class is None:
        return True
    return not is_bond_liability(asset_class)


LIABILITY_POSITION_SCOPE = "liability"

# CAS 22 measures financial liabilities on their own basis (摊余成本 /
# 以公允价值计量且其变动计入当期损益的金融负债). AC / FVOCI / FVTPL as used in
# this codebase are the *asset-side* categories, so a liability-scoped row must
# never carry one of them.
ASSET_SIDE_ACCOUNTING_BASES: frozenset[str] = frozenset(
    {ACCOUNTING_BASIS_AC, ACCOUNTING_BASIS_FVOCI, ACCOUNTING_BASIS_FVTPL}
)


class LiabilityAccountingBasisError(ValueError):
    """A liability-scoped position carries an asset-side measurement category."""


def is_asset_side_accounting_basis(accounting_basis: str | None) -> bool:
    return str(accounting_basis or "").strip().upper() in ASSET_SIDE_ACCOUNTING_BASES


def is_liability_position_scope(position_scope: str | None) -> bool:
    return str(position_scope or "").strip().lower() == LIABILITY_POSITION_SCOPE


def check_position_scope_accounting_basis(
    *,
    position_scope: str | None,
    accounting_basis: str | None,
    context: str = "",
) -> str | None:
    """Describe an asset/liability measurement mismatch, or ``None`` when clean.

    Consumers that aggregate by ``accounting_basis`` alone (without also
    filtering ``position_scope``) would otherwise fold liabilities into the
    asset-side AC/FVOCI/FVTPL buckets. Pure check: it never mutates the row and
    never rewrites the basis, so callers keep full control over whether a
    violation warns or rejects.
    """
    if not is_liability_position_scope(position_scope):
        return None
    if not is_asset_side_accounting_basis(accounting_basis):
        return None
    normalized_basis = str(accounting_basis or "").strip().upper()
    suffix = f" [{context}]" if context else ""
    return (
        f"position_scope=liability 的行携带资产侧计量类别 accounting_basis={normalized_basis}；"
        f"CAS 22 下金融负债的计量类别与资产侧 AC/FVOCI/FVTPL 不是同一集合，"
        f"按 accounting_basis 汇总时必须同时过滤 position_scope。{suffix}"
    )


def assert_position_scope_accounting_basis(
    *,
    position_scope: str | None,
    accounting_basis: str | None,
    context: str = "",
) -> None:
    """Fail loud on an asset-side measurement category attached to a liability."""
    violation = check_position_scope_accounting_basis(
        position_scope=position_scope,
        accounting_basis=accounting_basis,
        context=context,
    )
    if violation is not None:
        raise LiabilityAccountingBasisError(violation)


def is_interbank_asset(product_type: str | None) -> bool:
    text = str(product_type or "")
    if any(_contains_sql_like_substring(text, kw) for kw in INTERBANK_ASSET_KEYWORDS):
        return True
    return any(kw in text for kw in INTERBANK_ASSET_KEYWORDS_PLAIN)


def is_interbank_liability(product_type: str | None) -> bool:
    text = str(product_type or "")
    return any(_contains_sql_like_substring(text, kw) for kw in INTERBANK_LIABILITY_KEYWORDS)


def is_interbank_liability_core(product_type: str | None) -> bool:
    text = str(product_type or "")
    return any(_contains_sql_like_substring(text, kw) for kw in INTERBANK_LIABILITY_CORE_KEYWORDS)


_HAT_H_LABEL_SUBSTRINGS: tuple[str, ...] = (
    "应收投资款项",
    "发行类债务",
    "发行类债券",
    "发行类债劵",
    "拆放同业",
    "买入返售证券",
    "存放同业",
    "同业拆入",
    "同业存放",
    "卖出回购证券",
    "卖出回购票据",
    "持有至到期同业存单",
)

# Subset of ``_HAT_H_LABEL_SUBSTRINGS`` describing pure liability instruments.
# ``is_bond_liability`` already recognises the 发行类 family; the interbank
# funding labels below carry no 发行/负债 token and must be listed explicitly.
# Curated rather than derived from ``INTERBANK_LIABILITY_KEYWORDS`` because
# those keywords also match asset placements such as 存放同业 / 拆放同业.
_HAT_H_LIABILITY_LABEL_SUBSTRINGS: tuple[str, ...] = (
    "同业拆入",
    "同业存放",
    "卖出回购证券",
    "卖出回购票据",
)

_warned_liability_invest_labels: set[str] = set()


def is_liability_invest_label(value: str | None) -> bool:
    """True when an H/A/T source label denotes a liability, not an asset.

    Covers both the 发行类 family handled by ``is_bond_liability`` and the
    interbank funding labels that reach ``_match_invest_type_by_substring``.
    """
    normalized = str(value or "").strip()
    if not normalized:
        return False
    if is_bond_liability(normalized):
        return True
    return any(label in normalized for label in _HAT_H_LIABILITY_LABEL_SUBSTRINGS)


def _warn_liability_invest_label_once(value: str, tag: str) -> None:
    """Log the first occurrence of each liability label resolved to an H/A/T tag.

    Deduplicated by label so an ETL pass over ~10^5 rows emits one line per
    distinct label instead of one per row.
    """
    if value in _warned_liability_invest_labels:
        return
    _warned_liability_invest_labels.add(value)
    logger.warning(
        "hat_mapping resolved a liability label to an asset-side invest_type: "
        "label=%r invest_type_std=%r. Downstream accounting_basis derivation maps "
        "this to an asset-side measurement category; consumers must filter "
        "position_scope='liability' before aggregating by accounting_basis. "
        "See classification_rules.assert_position_scope_accounting_basis.",
        value,
        tag,
    )


def _match_invest_type_by_substring(value: str) -> str | None:
    """Match H/A/T from a Chinese accounting label or English alias substring.

    Consolidated into ``infer_invest_type`` as part of W-balance-2026-04-21
    trial migration so that ``hat_mapping`` has a single canonical entry
    point that subsumes the bare-label normalization previously served by
    ``field_normalization.derive_invest_type_std_value``. Pure helper:
    returns ``None`` when no rule matches (caller decides whether to raise).
    """
    normalized = str(value).strip()
    if not normalized:
        return None
    upper = normalized.upper()
    if (
        "可供出售" in normalized
        or "其他债权" in normalized
        or "AFS" in upper
        or ACCOUNTING_BASIS_FVOCI in upper
        or "OCI" in upper
    ):
        return "A"
    if (
        "交易" in normalized
        or "TRADING" in upper
        or ACCOUNTING_BASIS_FVTPL in upper
        or "TPL" in upper
        or upper in {"T", "TRADING_ASSET_RAW"}
    ):
        return "T"
    if "持有至到期" in normalized or "摊余成本" in normalized or "HTM" in upper:
        return "H"
    if any(label in normalized for label in _HAT_H_LABEL_SUBSTRINGS):
        return "H"
    return None


def _match_invest_type_by_code_suffix(text: str) -> str | None:
    """Match H/A/T from a coded label whose last character is the class tag.

    Only coded forms such as ``组合A``、``账户-T``、``asset_H`` may use this
    heuristic. The character in front of the tag must be a separator or a
    non-ASCII (typically CJK) character; otherwise plain English words that
    merely happen to end in A/T/H (``CHINA``、``REIT``、``MATH``, and the
    production portfolio codes ``FIOA`` / ``RIOA`` / ``PORT``) would be
    silently classified. ``text`` is expected pre-stripped and upper-cased.
    """
    if len(text) < 2:
        return None
    suffix = text[-1]
    if suffix not in ("A", "T", "H"):
        return None
    boundary = text[-2]
    if boundary.isascii() and boundary.isalnum():
        return None
    return suffix


def infer_invest_type(
    portfolio: str | None,
    asset_type: str | None,
    asset_class: str | None = None,
    interest_income: Decimal | None = None,
    is_nonstd: bool = False,
) -> str | None:
    """Resolve H/A/T for a position (caliber rule ``hat_mapping``).

    Precedence, strongest evidence first:

    1. non-standard assets: sign of ``interest_income``;
    2. exact canonical token (``invest_type_std`` / ``invest_type_raw`` already
       normalized to ``A`` / ``T`` / ``H``);
    3. explicit accounting-label substring rules;
    4. coded last-character suffix, as a guarded fallback only.

    Rules 3 and 4 are ordered this way so an explicit label always outranks the
    suffix heuristic; see ``_match_invest_type_by_code_suffix`` for the
    separator/CJK boundary that keeps English words out of rule 4.

    Rule 3 still returns ``H`` for liability labels (发行类债务、同业拆入、
    卖出回购证券 …) because changing that would restate persisted balances.
    The liability path is no longer silent: it is routed through
    ``is_liability_invest_label`` and logged once per label, so the H→AC hop is
    visible to operators. Use ``assert_position_scope_accounting_basis`` at the
    consumption boundary to reject the resulting asset-side basis on
    liability-scoped rows.
    """
    if is_nonstd and interest_income is not None:
        return "H" if interest_income > 0 else "T"
    for value in (asset_type, portfolio):
        if not value:
            continue
        text = str(value).strip().upper()
        if text in ("A", "T", "H"):
            return text
    for value in (asset_type, asset_class, portfolio):
        if not value:
            continue
        tag = _match_invest_type_by_substring(value)
        if tag is not None:
            if is_liability_invest_label(value):
                _warn_liability_invest_label_once(str(value).strip(), tag)
            return tag
    for value in (asset_type, portfolio):
        if not value:
            continue
        suffix = _match_invest_type_by_code_suffix(str(value).strip().upper())
        if suffix is not None:
            return suffix
    return None
