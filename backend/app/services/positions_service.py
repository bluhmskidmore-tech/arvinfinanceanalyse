"""Positions read service — snapshot aggregations with formal result envelopes."""
from __future__ import annotations

import uuid
from datetime import date, timedelta

from backend.app.governance.settings import get_settings
from backend.app.repositories.positions_repo import PositionsRepository
from backend.app.schemas.positions import (
    BondPositionItem,
    BondPositionsPageResponse,
    CounterpartyStatsResponse,
    CustomerBalanceTrendResponse,
    CustomerBondDetailsResponse,
    IndustryStatsResponse,
    InterbankCounterpartySplitResponse,
    InterbankPositionItem,
    InterbankPositionsPageResponse,
    ProductTypesResponse,
    RatingStatsResponse,
    SubTypesResponse,
)
from backend.app.services.formal_result_runtime import (
    build_formal_result_envelope,
    build_formal_result_meta,
)

CACHE_VERSION = "cv_positions_read_v1"
RULE_VERSION = "rv_positions_read_v1"
EMPTY_SOURCE_VERSION = "sv_positions_snapshot_empty"


def _trace_id() -> str:
    return f"tr_{uuid.uuid4().hex[:12]}"


def _merge_versions(values: list[str], *, empty_value: str) -> str:
    merged = sorted({value.strip() for value in values if value and value.strip()})
    return "__".join(merged) or empty_value


def _repo() -> PositionsRepository:
    settings = get_settings()
    return PositionsRepository(str(settings.duckdb_path))


def _meta(*, result_kind: str, src: list[str], rule: list[str]) -> object:
    return build_formal_result_meta(
        trace_id=_trace_id(),
        result_kind=result_kind,
        cache_version=CACHE_VERSION,
        source_version=_merge_versions(src, empty_value=EMPTY_SOURCE_VERSION),
        rule_version=_merge_versions(rule, empty_value=RULE_VERSION),
    )


def bond_sub_types_envelope(report_date: str) -> dict[str, object]:
    repo = _repo()
    sub_types = repo.list_bond_sub_types(report_date)
    src, rule = repo.collect_lineage_versions(
        zqtz_where_sql="report_date = ?::date",
        zqtz_params=[report_date],
        tyw_where_sql="1=0",
        tyw_params=[],
    )
    payload = SubTypesResponse(sub_types=sub_types)
    return build_formal_result_envelope(
        result_meta=_meta(result_kind="positions.bonds.sub_types", src=src, rule=rule),
        result_payload=payload.model_dump(mode="json"),
    )


def bonds_list_envelope(
    *,
    report_date: str,
    sub_type: str | None,
    page: int,
    page_size: int,
    include_issued: bool,
) -> dict[str, object]:
    repo = _repo()
    items, total = repo.list_bonds(report_date, sub_type, page, page_size, include_issued)
    src, rule = repo.collect_lineage_versions(
        zqtz_where_sql="report_date = ?::date",
        zqtz_params=[report_date],
        tyw_where_sql="1=0",
        tyw_params=[],
    )
    payload = BondPositionsPageResponse(
        items=[BondPositionItem.model_validate(row) for row in items],
        total=total,
        page=page,
        page_size=page_size,
    )
    return build_formal_result_envelope(
        result_meta=_meta(result_kind="positions.bonds.list", src=src, rule=rule),
        result_payload=payload.model_dump(mode="json"),
    )


def counterparty_bonds_envelope(
    *,
    start_date: str,
    end_date: str,
    sub_type: str | None,
    top_n: int | None,
    page: int,
    page_size: int,
) -> dict[str, object]:
    repo = _repo()
    raw = repo.aggregate_counterparty_bonds(start_date, end_date, sub_type, top_n, page, page_size)
    src, rule = repo.collect_lineage_versions(
        zqtz_where_sql="report_date between ?::date and ?::date",
        zqtz_params=[start_date, end_date],
        tyw_where_sql="1=0",
        tyw_params=[],
    )
    payload = CounterpartyStatsResponse.model_validate(raw)
    return build_formal_result_envelope(
        result_meta=_meta(result_kind="positions.counterparty.bonds", src=src, rule=rule),
        result_payload=payload.model_dump(mode="json"),
    )


def interbank_product_types_envelope(report_date: str) -> dict[str, object]:
    repo = _repo()
    types_list = repo.list_interbank_product_types(report_date)
    src, rule = repo.collect_lineage_versions(
        zqtz_where_sql="1=0",
        zqtz_params=[],
        tyw_where_sql="report_date = ?::date",
        tyw_params=[report_date],
    )
    payload = ProductTypesResponse(product_types=types_list)
    return build_formal_result_envelope(
        result_meta=_meta(result_kind="positions.interbank.product_types", src=src, rule=rule),
        result_payload=payload.model_dump(mode="json"),
    )


def interbank_list_envelope(
    *,
    report_date: str,
    product_type: str | None,
    direction: str | None,
    page: int,
    page_size: int,
) -> dict[str, object]:
    repo = _repo()
    items, total = repo.list_interbank(report_date, product_type, direction, page, page_size)
    src, rule = repo.collect_lineage_versions(
        zqtz_where_sql="1=0",
        zqtz_params=[],
        tyw_where_sql="report_date = ?::date",
        tyw_params=[report_date],
    )
    payload = InterbankPositionsPageResponse(
        items=[InterbankPositionItem.model_validate(row) for row in items],
        total=total,
        page=page,
        page_size=page_size,
    )
    return build_formal_result_envelope(
        result_meta=_meta(result_kind="positions.interbank.list", src=src, rule=rule),
        result_payload=payload.model_dump(mode="json"),
    )


def counterparty_interbank_split_envelope(
    *,
    start_date: str,
    end_date: str,
    product_type: str | None,
    top_n: int | None,
) -> dict[str, object]:
    repo = _repo()
    raw = repo.aggregate_counterparty_interbank_split(start_date, end_date, product_type, top_n)
    src, rule = repo.collect_lineage_versions(
        zqtz_where_sql="1=0",
        zqtz_params=[],
        tyw_where_sql="report_date between ?::date and ?::date",
        tyw_params=[start_date, end_date],
    )
    payload = InterbankCounterpartySplitResponse.model_validate(raw)
    return build_formal_result_envelope(
        result_meta=_meta(result_kind="positions.counterparty.interbank.split", src=src, rule=rule),
        result_payload=payload.model_dump(mode="json"),
    )


def stats_rating_envelope(*, start_date: str, end_date: str, sub_type: str | None) -> dict[str, object]:
    repo = _repo()
    raw = repo.aggregate_rating_stats(start_date, end_date, sub_type)
    src, rule = repo.collect_lineage_versions(
        zqtz_where_sql="report_date between ?::date and ?::date",
        zqtz_params=[start_date, end_date],
        tyw_where_sql="1=0",
        tyw_params=[],
    )
    payload = RatingStatsResponse.model_validate(raw)
    return build_formal_result_envelope(
        result_meta=_meta(result_kind="positions.stats.rating", src=src, rule=rule),
        result_payload=payload.model_dump(mode="json"),
    )


def stats_industry_envelope(
    *, start_date: str, end_date: str, sub_type: str | None, top_n: int | None
) -> dict[str, object]:
    repo = _repo()
    raw = repo.aggregate_industry_stats(start_date, end_date, sub_type, top_n)
    src, rule = repo.collect_lineage_versions(
        zqtz_where_sql="report_date between ?::date and ?::date",
        zqtz_params=[start_date, end_date],
        tyw_where_sql="1=0",
        tyw_params=[],
    )
    payload = IndustryStatsResponse.model_validate(raw)
    return build_formal_result_envelope(
        result_meta=_meta(result_kind="positions.stats.industry", src=src, rule=rule),
        result_payload=payload.model_dump(mode="json"),
    )


def customer_details_envelope(*, customer_name: str, report_date: str) -> dict[str, object]:
    repo = _repo()
    raw = repo.get_customer_bond_details(customer_name, report_date)
    src, rule = repo.collect_lineage_versions(
        zqtz_where_sql="report_date = ?::date",
        zqtz_params=[report_date],
        tyw_where_sql="1=0",
        tyw_params=[],
    )
    payload = CustomerBondDetailsResponse.model_validate(raw)
    return build_formal_result_envelope(
        result_meta=_meta(result_kind="positions.customer.details", src=src, rule=rule),
        result_payload=payload.model_dump(mode="json"),
    )


def customer_trend_envelope(*, customer_name: str, end_date: str, days: int) -> dict[str, object]:
    repo = _repo()
    raw = repo.get_customer_balance_trend(customer_name, end_date, days)
    d = max(days, 1)
    try:
        end_d = date.fromisoformat(end_date)
        window_start = (end_d - timedelta(days=d - 1)).isoformat()
    except ValueError:
        window_start = end_date
    src, rule = repo.collect_lineage_versions(
        zqtz_where_sql="issuer_name = ? and report_date between ?::date and ?::date",
        zqtz_params=[customer_name, window_start, end_date],
        tyw_where_sql="1=0",
        tyw_params=[],
    )
    payload = CustomerBalanceTrendResponse.model_validate(raw)
    return build_formal_result_envelope(
        result_meta=_meta(result_kind="positions.customer.trend", src=src, rule=rule),
        result_payload=payload.model_dump(mode="json"),
    )
