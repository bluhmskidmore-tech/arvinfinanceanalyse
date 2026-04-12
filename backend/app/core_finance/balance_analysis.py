from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

InvestTypeStd = Literal["H", "A", "T"]
AccountingBasis = Literal["AC", "FVOCI", "FVTPL"]
BalanceCurrencyBasis = Literal["native", "CNY", "CNX"]
BalancePositionScope = Literal["asset", "liability", "all"]

_H_LABELS = frozenset(
    {
        "应收投资款项",
        "发行类债劵",
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


@dataclass(slots=True, frozen=True)
class ZqtzSnapshotRow:
    report_date: date
    instrument_code: str
    instrument_name: str
    portfolio_name: str
    cost_center: str
    account_category: str
    asset_class: str
    bond_type: str
    issuer_name: str
    industry_name: str
    rating: str
    currency_code: str
    face_value_native: Decimal
    market_value_native: Decimal
    amortized_cost_native: Decimal
    accrued_interest_native: Decimal
    coupon_rate: Decimal | None
    ytm_value: Decimal | None
    maturity_date: date | None
    is_issuance_like: bool
    overdue_days: int | None = None
    value_date: date | None = None
    customer_attribute: str = ""
    interest_mode: str = ""
    source_version: str = ""
    rule_version: str = ""
    ingest_batch_id: str = ""
    trace_id: str = ""


@dataclass(slots=True, frozen=True)
class TywSnapshotRow:
    report_date: date
    position_id: str
    product_type: str
    position_side: str
    counterparty_name: str
    account_type: str
    special_account_type: str
    core_customer_type: str
    currency_code: str
    principal_native: Decimal
    accrued_interest_native: Decimal
    funding_cost_rate: Decimal | None
    maturity_date: date | None
    source_version: str = ""
    rule_version: str = ""
    ingest_batch_id: str = ""
    trace_id: str = ""


@dataclass(slots=True, frozen=True)
class FormalZqtzBalanceFactRow:
    report_date: date
    instrument_code: str
    instrument_name: str
    portfolio_name: str
    cost_center: str
    account_category: str
    asset_class: str
    bond_type: str
    issuer_name: str
    industry_name: str
    rating: str
    invest_type_std: InvestTypeStd
    accounting_basis: AccountingBasis
    position_scope: BalancePositionScope
    currency_basis: BalanceCurrencyBasis
    currency_code: str
    face_value_amount: Decimal
    market_value_amount: Decimal
    amortized_cost_amount: Decimal
    accrued_interest_amount: Decimal
    coupon_rate: Decimal | None
    ytm_value: Decimal | None
    maturity_date: date | None
    interest_mode: str
    is_issuance_like: bool
    overdue_principal_days: int = 0
    overdue_interest_days: int = 0
    value_date: date | None = None
    customer_attribute: str = ""
    source_version: str = ""
    rule_version: str = ""
    ingest_batch_id: str = ""
    trace_id: str = ""


@dataclass(slots=True, frozen=True)
class FormalTywBalanceFactRow:
    report_date: date
    position_id: str
    product_type: str
    position_side: str
    counterparty_name: str
    account_type: str
    special_account_type: str
    core_customer_type: str
    invest_type_std: InvestTypeStd
    accounting_basis: AccountingBasis
    position_scope: BalancePositionScope
    currency_basis: BalanceCurrencyBasis
    currency_code: str
    principal_amount: Decimal
    accrued_interest_amount: Decimal
    funding_cost_rate: Decimal | None
    maturity_date: date | None
    source_version: str = ""
    rule_version: str = ""
    ingest_batch_id: str = ""
    trace_id: str = ""


def derive_invest_type_std(invest_type_raw: str) -> InvestTypeStd:
    normalized = str(invest_type_raw or "").strip().lower()
    if not normalized:
        raise ValueError("invest_type_raw is required")
    if "可供出售" in normalized or "afs" in normalized:
        return "A"
    if "交易" in normalized or "trading" in normalized:
        return "T"
    if "持有至到期" in normalized or "htm" in normalized:
        return "H"
    if any(label.lower() in normalized for label in _H_LABELS):
        return "H"
    raise ValueError(f"Unrecognized invest_type_raw={invest_type_raw!r}")


def derive_accounting_basis(invest_type_std: InvestTypeStd) -> AccountingBasis:
    mapping: dict[InvestTypeStd, AccountingBasis] = {
        "H": "AC",
        "A": "FVOCI",
        "T": "FVTPL",
    }
    return mapping[invest_type_std]


def average_daily_cny_amounts(daily_native_and_fx: list[tuple[Decimal, Decimal]]) -> Decimal:
    if not daily_native_and_fx:
        raise ValueError("daily_native_and_fx must not be empty")
    total = sum((native_amount * fx_rate) for native_amount, fx_rate in daily_native_and_fx)
    return total / Decimal(len(daily_native_and_fx))


def _zqtz_overdue_days_split(row: ZqtzSnapshotRow) -> tuple[int, int]:
    raw = row.overdue_days
    if raw is None:
        return 0, 0
    try:
        days = int(raw)
    except (TypeError, ValueError):
        return 0, 0
    if days <= 0:
        return 0, 0
    return days, 0


def project_zqtz_formal_balance_row(
    row: ZqtzSnapshotRow,
    *,
    invest_type_raw: str,
    position_scope: BalancePositionScope,
    currency_basis: BalanceCurrencyBasis,
    fx_rate: Decimal | None = None,
) -> FormalZqtzBalanceFactRow | None:
    if position_scope == "asset" and row.is_issuance_like:
        return None

    invest_type_std = derive_invest_type_std(invest_type_raw)
    accounting_basis = derive_accounting_basis(invest_type_std)
    face_value_amount = _project_amount(
        row.face_value_native,
        currency_code=row.currency_code,
        currency_basis=currency_basis,
        fx_rate=fx_rate,
    )
    market_value_amount = _project_amount(
        row.market_value_native,
        currency_code=row.currency_code,
        currency_basis=currency_basis,
        fx_rate=fx_rate,
    )
    amortized_cost_amount = _project_amount(
        row.amortized_cost_native,
        currency_code=row.currency_code,
        currency_basis=currency_basis,
        fx_rate=fx_rate,
    )
    accrued_interest_amount = _project_amount(
        row.accrued_interest_native,
        currency_code=row.currency_code,
        currency_basis=currency_basis,
        fx_rate=fx_rate,
    )
    overdue_principal_days, overdue_interest_days = _zqtz_overdue_days_split(row)
    return FormalZqtzBalanceFactRow(
        report_date=row.report_date,
        instrument_code=row.instrument_code,
        instrument_name=row.instrument_name,
        portfolio_name=row.portfolio_name,
        cost_center=row.cost_center,
        account_category=row.account_category,
        asset_class=row.asset_class,
        bond_type=row.bond_type,
        issuer_name=row.issuer_name,
        industry_name=row.industry_name,
        rating=row.rating,
        invest_type_std=invest_type_std,
        accounting_basis=accounting_basis,
        position_scope=position_scope,
        currency_basis=currency_basis,
        currency_code=row.currency_code,
        face_value_amount=face_value_amount,
        market_value_amount=market_value_amount,
        amortized_cost_amount=amortized_cost_amount,
        accrued_interest_amount=accrued_interest_amount,
        coupon_rate=row.coupon_rate,
        ytm_value=row.ytm_value,
        maturity_date=row.maturity_date,
        interest_mode=row.interest_mode,
        is_issuance_like=row.is_issuance_like,
        overdue_principal_days=overdue_principal_days,
        overdue_interest_days=overdue_interest_days,
        value_date=row.value_date,
        customer_attribute=str(row.customer_attribute or "").strip(),
        source_version=row.source_version,
        rule_version=row.rule_version,
        ingest_batch_id=row.ingest_batch_id,
        trace_id=row.trace_id,
    )


def project_tyw_formal_balance_row(
    row: TywSnapshotRow,
    *,
    invest_type_raw: str,
    position_scope: BalancePositionScope,
    currency_basis: BalanceCurrencyBasis,
    fx_rate: Decimal | None = None,
) -> FormalTywBalanceFactRow:
    invest_type_std = derive_invest_type_std(invest_type_raw)
    accounting_basis = derive_accounting_basis(invest_type_std)
    principal_amount = _project_amount(
        row.principal_native,
        currency_code=row.currency_code,
        currency_basis=currency_basis,
        fx_rate=fx_rate,
    )
    accrued_interest_amount = _project_amount(
        row.accrued_interest_native,
        currency_code=row.currency_code,
        currency_basis=currency_basis,
        fx_rate=fx_rate,
    )
    return FormalTywBalanceFactRow(
        report_date=row.report_date,
        position_id=row.position_id,
        product_type=row.product_type,
        position_side=row.position_side,
        counterparty_name=row.counterparty_name,
        account_type=row.account_type,
        special_account_type=row.special_account_type,
        core_customer_type=row.core_customer_type,
        invest_type_std=invest_type_std,
        accounting_basis=accounting_basis,
        position_scope=position_scope,
        currency_basis=currency_basis,
        currency_code=row.currency_code,
        principal_amount=principal_amount,
        accrued_interest_amount=accrued_interest_amount,
        funding_cost_rate=row.funding_cost_rate,
        maturity_date=row.maturity_date,
        source_version=row.source_version,
        rule_version=row.rule_version,
        ingest_batch_id=row.ingest_batch_id,
        trace_id=row.trace_id,
    )


def _project_amount(
    native_amount: Decimal,
    *,
    currency_code: str,
    currency_basis: BalanceCurrencyBasis,
    fx_rate: Decimal | None,
) -> Decimal:
    if currency_basis == "native":
        return native_amount
    if str(currency_code).upper() == "CNY":
        return native_amount
    if fx_rate is None:
        raise ValueError("fx_rate is required when projecting non-CNY rows into CNY/CNX basis")
    return native_amount * fx_rate
