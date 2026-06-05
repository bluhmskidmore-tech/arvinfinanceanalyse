from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class SourcePreviewSummary(BaseModel):
    ingest_batch_id: str | None = None
    batch_created_at: str | None = None
    source_family: str
    report_date: str | None = None
    report_start_date: str | None = None
    report_end_date: str | None = None
    report_granularity: str | None = None
    source_file: str
    total_rows: int
    manual_review_count: int
    source_version: str
    rule_version: str
    group_counts: dict[str, int]
    preview_mode: str = "tabular"


class SourcePreviewPayload(BaseModel):
    sources: list[SourcePreviewSummary]


class SourcePreviewHistoryPage(BaseModel):
    limit: int
    offset: int
    total_rows: int
    rows: list[SourcePreviewSummary]


class ZqtzPreviewRow(BaseModel):
    ingest_batch_id: str
    row_locator: int
    report_date: str | None = None
    business_type_primary: str
    business_type_final: str
    asset_group: str
    instrument_code: str
    instrument_name: str
    account_category: str
    manual_review_needed: bool


class TywPreviewRow(BaseModel):
    ingest_batch_id: str
    row_locator: int
    report_date: str | None = None
    business_type_primary: str
    product_group: str
    institution_category: str
    special_nature: str
    counterparty_name: str
    investment_portfolio: str
    manual_review_needed: bool


class PnlPreviewRow(BaseModel):
    ingest_batch_id: str
    row_locator: int
    report_date: str | None = None
    instrument_code: str
    invest_type_raw: str
    portfolio_name: str
    cost_center: str
    currency: str
    manual_review_needed: bool


class NonstdPnlPreviewRow(BaseModel):
    ingest_batch_id: str
    row_locator: int
    report_date: str | None = None
    journal_type: str
    product_type: str
    asset_code: str
    account_code: str
    dc_flag_raw: str
    raw_amount: str
    manual_review_needed: bool


class RuleTraceRow(BaseModel):
    ingest_batch_id: str
    row_locator: int
    trace_step: int
    field_name: str
    field_value: str
    derived_label: str
    manual_review_needed: bool


class PreviewColumn(BaseModel):
    key: str
    label: str
    type: Literal["string", "number", "boolean"]


class PreviewRowPage(BaseModel):
    source_family: str
    ingest_batch_id: str | None = None
    limit: int
    offset: int
    total_rows: int
    columns: list[PreviewColumn]
    rows: list[dict[str, object]]


class RuleTracePage(BaseModel):
    source_family: str
    ingest_batch_id: str | None = None
    limit: int
    offset: int
    total_rows: int
    columns: list[PreviewColumn]
    rows: list[dict[str, object]]
