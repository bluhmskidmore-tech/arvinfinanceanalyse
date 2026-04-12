"""Contract tests for `backend.app.schemas.source_preview`."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.schemas.source_preview import (
    NonstdPnlPreviewRow,
    PnlPreviewRow,
    PreviewColumn,
    PreviewRowPage,
    RuleTracePage,
    RuleTraceRow,
    SourcePreviewHistoryPage,
    SourcePreviewPayload,
    SourcePreviewSummary,
    TywPreviewRow,
    ZqtzPreviewRow,
)


def _minimal_summary() -> SourcePreviewSummary:
    return SourcePreviewSummary(
        source_family="zqtz",
        source_file="a.csv",
        total_rows=10,
        manual_review_count=0,
        source_version="sv",
        rule_version="rv",
        group_counts={"g": 1},
    )


def test_source_preview_summary_minimal_valid() -> None:
    s = _minimal_summary()
    assert s.preview_mode == "tabular"


def test_source_preview_payload_nests_summaries() -> None:
    inner = _minimal_summary()
    payload = SourcePreviewPayload(sources=[inner])
    assert len(payload.sources) == 1
    assert payload.sources[0].total_rows == 10


def test_source_preview_history_page_pagination_fields() -> None:
    page = SourcePreviewHistoryPage(limit=50, offset=10, total_rows=200, rows=[_minimal_summary()])
    assert page.limit == 50
    assert page.offset == 10
    assert page.total_rows == 200


@pytest.mark.parametrize("col_type", ["string", "number", "boolean"])
def test_preview_column_accepts_literal_types(col_type: str) -> None:
    c = PreviewColumn(key="k", label="L", type=col_type)  # type: ignore[arg-type]
    assert c.type == col_type


def test_preview_column_invalid_type_raises() -> None:
    with pytest.raises(ValidationError):
        PreviewColumn(key="k", label="L", type="object")  # type: ignore[arg-type]


def test_preview_row_page_and_rule_trace_page_structure() -> None:
    col = PreviewColumn(key="c", label="C", type="string")
    pr = PreviewRowPage(
        source_family="zqtz",
        limit=20,
        offset=0,
        total_rows=1,
        columns=[col],
        rows=[{"c": "v"}],
    )
    assert pr.rows == [{"c": "v"}]
    rt = RuleTracePage(
        source_family="zqtz",
        limit=20,
        offset=0,
        total_rows=0,
        columns=[col],
        rows=[],
    )
    assert rt.columns[0].type == "string"


def test_representative_typed_rows_instantiate() -> None:
    z = ZqtzPreviewRow(
        ingest_batch_id="b",
        row_locator=1,
        business_type_primary="a",
        business_type_final="b",
        asset_group="g",
        instrument_code="c",
        instrument_name="n",
        account_category="ac",
        manual_review_needed=False,
    )
    assert z.instrument_code == "c"

    t = TywPreviewRow(
        ingest_batch_id="b",
        row_locator=2,
        business_type_primary="p",
        product_group="pg",
        institution_category="ic",
        special_nature="s",
        counterparty_name="cp",
        investment_portfolio="ip",
        manual_review_needed=True,
    )
    assert t.product_group == "pg"

    p = PnlPreviewRow(
        ingest_batch_id="b",
        row_locator=3,
        instrument_code="i",
        invest_type_raw="raw",
        portfolio_name="pn",
        cost_center="cc",
        currency="CNY",
        manual_review_needed=False,
    )
    assert p.currency == "CNY"

    n = NonstdPnlPreviewRow(
        ingest_batch_id="b",
        row_locator=4,
        journal_type="j",
        product_type="pt",
        asset_code="ac",
        account_code="acc",
        dc_flag_raw="D",
        raw_amount="1.0",
        manual_review_needed=False,
    )
    assert n.raw_amount == "1.0"

    r = RuleTraceRow(
        ingest_batch_id="b",
        row_locator=5,
        trace_step=1,
        field_name="f",
        field_value="v",
        derived_label="d",
        manual_review_needed=False,
    )
    assert r.trace_step == 1
