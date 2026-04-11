from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict


BalanceAnalysisSourceFamily = Literal["zqtz", "tyw", "combined"]
BalancePositionScope = Literal["asset", "liability", "all"]
BalanceCurrencyBasis = Literal["native", "CNY"]
BalanceAnalysisWorkbookSectionKind = Literal[
    "table",
    "decision_items",
    "event_calendar",
    "risk_alerts",
]


class BalanceAnalysisDetailRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_family: Literal["zqtz", "tyw"]
    report_date: str
    row_key: str
    display_name: str
    position_scope: BalancePositionScope
    currency_basis: BalanceCurrencyBasis
    invest_type_std: str
    accounting_basis: str
    market_value_amount: Decimal
    amortized_cost_amount: Decimal
    accrued_interest_amount: Decimal
    is_issuance_like: bool | None = None


class BalanceAnalysisSummaryRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_family: BalanceAnalysisSourceFamily
    position_scope: BalancePositionScope
    currency_basis: BalanceCurrencyBasis
    row_count: int
    market_value_amount: Decimal
    amortized_cost_amount: Decimal
    accrued_interest_amount: Decimal


class BalanceAnalysisTableRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row_key: str
    source_family: Literal["zqtz", "tyw"]
    display_name: str
    owner_name: str
    category_name: str
    position_scope: BalancePositionScope
    currency_basis: BalanceCurrencyBasis
    invest_type_std: str
    accounting_basis: str
    detail_row_count: int
    market_value_amount: Decimal
    amortized_cost_amount: Decimal
    accrued_interest_amount: Decimal


class BalanceAnalysisPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    position_scope: BalancePositionScope
    currency_basis: BalanceCurrencyBasis
    details: list[BalanceAnalysisDetailRow]
    summary: list[BalanceAnalysisSummaryRow]


class BalanceAnalysisSummaryTablePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    position_scope: BalancePositionScope
    currency_basis: BalanceCurrencyBasis
    limit: int
    offset: int
    total_rows: int
    rows: list[BalanceAnalysisTableRow]


class BalanceAnalysisBasisBreakdownRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_family: Literal["zqtz", "tyw"]
    invest_type_std: str
    accounting_basis: str
    position_scope: BalancePositionScope
    currency_basis: BalanceCurrencyBasis
    detail_row_count: int
    market_value_amount: Decimal
    amortized_cost_amount: Decimal
    accrued_interest_amount: Decimal


class BalanceAnalysisBasisBreakdownPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    position_scope: BalancePositionScope
    currency_basis: BalanceCurrencyBasis
    rows: list[BalanceAnalysisBasisBreakdownRow]


class BalanceAnalysisDatesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_dates: list[str]


class BalanceAnalysisWorkbookCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    value: Decimal | str | int
    note: str | None = None


class BalanceAnalysisWorkbookColumn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str


class BalanceAnalysisWorkbookTable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    title: str
    section_kind: BalanceAnalysisWorkbookSectionKind
    columns: list[BalanceAnalysisWorkbookColumn]
    rows: list[dict[str, Decimal | str | int | None]]


class BalanceAnalysisWorkbookPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    position_scope: BalancePositionScope
    currency_basis: BalanceCurrencyBasis
    cards: list[BalanceAnalysisWorkbookCard]
    tables: list[BalanceAnalysisWorkbookTable]
