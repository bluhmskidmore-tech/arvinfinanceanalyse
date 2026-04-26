from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal


BasisBucket = Literal["AC", "OCI", "TPL"]
ReconciliationStatus = Literal["matched", "mismatch", "gl_only", "zqtz_only"]

ZERO = Decimal("0")
DEFAULT_TOLERANCE = Decimal("0.01")
_BUCKET_ORDER: tuple[BasisBucket, ...] = ("AC", "OCI", "TPL")


@dataclass(slots=True, frozen=True)
class ZqtzAccountingAssetBalance:
    report_date: date
    accounting_basis: str
    market_value_amount: Decimal
    amortized_cost_amount: Decimal
    position_scope: str = "asset"
    currency_basis: str = "CNY"
    source_version: str = ""
    rule_version: str = ""


@dataclass(slots=True, frozen=True)
class GlAccountingAssetBalance:
    report_date: date
    account_code: str
    beginning_balance: Decimal
    ending_balance: Decimal
    currency_basis: str = "CNY"
    source_version: str = ""
    rule_version: str = ""


@dataclass(slots=True, frozen=True)
class AccountingAssetMovementRow:
    report_date: date
    report_month: str
    basis_bucket: BasisBucket
    previous_balance: Decimal
    current_balance: Decimal
    balance_change: Decimal
    change_pct: Decimal | None
    contribution_pct: Decimal | None
    zqtz_amount: Decimal
    gl_amount: Decimal
    reconciliation_diff: Decimal
    reconciliation_status: ReconciliationStatus
    source_version: str = ""
    rule_version: str = ""


def build_accounting_asset_movement_rows(
    *,
    report_date: date,
    zqtz_rows: list[ZqtzAccountingAssetBalance],
    gl_rows: list[GlAccountingAssetBalance],
    tolerance: Decimal = DEFAULT_TOLERANCE,
) -> list[AccountingAssetMovementRow]:
    zqtz_amounts = {bucket: ZERO for bucket in _BUCKET_ORDER}
    gl_beginning = {bucket: ZERO for bucket in _BUCKET_ORDER}
    gl_ending = {bucket: ZERO for bucket in _BUCKET_ORDER}
    source_versions: list[str] = []
    rule_versions: list[str] = []

    for row in zqtz_rows:
        if row.report_date != report_date or row.position_scope != "asset":
            continue
        bucket = _bucket_from_accounting_basis(row.accounting_basis)
        if bucket is None:
            continue
        zqtz_amounts[bucket] += (
            row.amortized_cost_amount if bucket == "AC" else row.market_value_amount
        )
        _append_unique(source_versions, row.source_version)
        _append_unique(rule_versions, row.rule_version)

    for row in gl_rows:
        if row.report_date != report_date:
            continue
        bucket = _bucket_from_gl_account(row.account_code)
        if bucket is None:
            continue
        gl_beginning[bucket] += row.beginning_balance
        gl_ending[bucket] += row.ending_balance
        _append_unique(source_versions, row.source_version)
        _append_unique(rule_versions, row.rule_version)

    changes = {
        bucket: gl_ending[bucket] - gl_beginning[bucket]
        for bucket in _BUCKET_ORDER
    }
    total_abs_change = sum((abs(value) for value in changes.values()), ZERO)

    rows: list[AccountingAssetMovementRow] = []
    for bucket in _BUCKET_ORDER:
        beginning = gl_beginning[bucket]
        ending = gl_ending[bucket]
        change = changes[bucket]
        zqtz_amount = zqtz_amounts[bucket]
        diff = zqtz_amount - ending
        rows.append(
            AccountingAssetMovementRow(
                report_date=report_date,
                report_month=f"{report_date:%Y-%m}",
                basis_bucket=bucket,
                previous_balance=beginning,
                current_balance=ending,
                balance_change=change,
                change_pct=_pct(change, beginning),
                contribution_pct=_pct(abs(change), total_abs_change),
                zqtz_amount=zqtz_amount,
                gl_amount=ending,
                reconciliation_diff=diff,
                reconciliation_status=_reconciliation_status(
                    zqtz_amount=zqtz_amount,
                    gl_amount=ending,
                    diff=diff,
                    tolerance=tolerance,
                ),
                source_version="__".join(source_versions),
                rule_version="__".join(rule_versions),
            )
        )
    return rows


def _bucket_from_accounting_basis(value: str) -> BasisBucket | None:
    normalized = str(value or "").strip().upper()
    if normalized in {"AC", "H"}:
        return "AC"
    if normalized in {"FVOCI", "OCI", "A"}:
        return "OCI"
    if normalized in {"FVTPL", "TPL", "T"}:
        return "TPL"
    return None


def _bucket_from_gl_account(account_code: str) -> BasisBucket | None:
    code = str(account_code or "").strip()
    if code.startswith("141"):
        return "TPL"
    if code.startswith(("142", "143")):
        return "AC"
    if code.startswith("144"):
        return "OCI"
    return None


def _reconciliation_status(
    *,
    zqtz_amount: Decimal,
    gl_amount: Decimal,
    diff: Decimal,
    tolerance: Decimal,
) -> ReconciliationStatus:
    if abs(diff) <= tolerance:
        return "matched"
    if gl_amount == ZERO:
        return "zqtz_only"
    if zqtz_amount == ZERO:
        return "gl_only"
    return "mismatch"


def _pct(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    if denominator == ZERO:
        return None
    return numerator / abs(denominator) * Decimal("100")


def _append_unique(items: list[str], value: str) -> None:
    normalized = str(value or "").strip()
    if normalized and normalized not in items:
        items.append(normalized)


__all__ = [
    "AccountingAssetMovementRow",
    "BasisBucket",
    "GlAccountingAssetBalance",
    "ReconciliationStatus",
    "ZqtzAccountingAssetBalance",
    "build_accounting_asset_movement_rows",
]
