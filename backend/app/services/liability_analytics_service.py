from __future__ import annotations

from backend.app.core_finance.liability_analytics_compat import (
    compute_liabilities_monthly,
    compute_liability_counterparty,
    compute_liability_risk_buckets,
    compute_liability_yield_metrics,
)
from backend.app.repositories.liability_analytics_repo import LiabilityAnalyticsRepository
from backend.app.schemas.liability_analytics import (
    LiabilitiesMonthlyPayload,
    LiabilityCounterpartyPayload,
    LiabilityRiskBucketsPayload,
    LiabilityYieldKpi,
    LiabilityYieldMetricsPayload,
)
from backend.app.services.formal_result_runtime import build_result_envelope

LIABILITY_ANALYTICS_CACHE_VERSION = "cv_liability_analytics_v1"
LIABILITY_ANALYTICS_RULE_VERSION = "rv_liability_analytics_compat_v1"
LIABILITY_ANALYTICS_EMPTY_SOURCE_VERSION = "sv_liability_analytics_empty"


def _resolve_report_date(repo: LiabilityAnalyticsRepository, report_date: str | None) -> str:
    candidate = str(report_date or "").strip()
    if candidate:
        return candidate
    return repo.resolve_latest_report_date() or ""


def _merge_lineage(rows: list[dict[str, object]]) -> tuple[str, str]:
    source_versions = sorted(
        {
            str(row.get("source_version") or "").strip()
            for row in rows
            if str(row.get("source_version") or "").strip()
        }
    )
    rule_versions = sorted(
        {
            str(row.get("rule_version") or "").strip()
            for row in rows
            if str(row.get("rule_version") or "").strip()
        }
    )
    return (
        "__".join(source_versions) or LIABILITY_ANALYTICS_EMPTY_SOURCE_VERSION,
        "__".join(rule_versions) or LIABILITY_ANALYTICS_RULE_VERSION,
    )


def _envelope(
    *,
    result_kind: str,
    result_payload: dict[str, object],
    source_rows: list[dict[str, object]],
    quality_flag: str = "ok",
) -> dict[str, object]:
    source_version, rule_version = _merge_lineage(source_rows)
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_{result_kind}",
        result_kind=result_kind,
        cache_version=LIABILITY_ANALYTICS_CACHE_VERSION,
        source_version=source_version,
        rule_version=rule_version,
        quality_flag=quality_flag,
        vendor_version="vv_none",
        result_payload=result_payload,
    )


def liability_risk_buckets_payload(*, duckdb_path: str, report_date: str | None) -> dict[str, object]:
    repo = LiabilityAnalyticsRepository(duckdb_path)
    resolved_date = _resolve_report_date(repo, report_date)
    zqtz_rows = repo.fetch_zqtz_rows(resolved_date) if resolved_date else []
    tyw_rows = repo.fetch_tyw_rows(resolved_date) if resolved_date else []
    if not resolved_date:
        return _envelope(
            result_kind="liability_analytics.risk_buckets",
            source_rows=[],
            quality_flag="warning",
            result_payload=LiabilityRiskBucketsPayload(
                report_date="",
                liabilities_structure=[],
                liabilities_term_buckets=[],
                interbank_liabilities_structure=[],
                interbank_liabilities_term_buckets=[],
                issued_liabilities_structure=[],
                issued_liabilities_term_buckets=[],
            ).model_dump(mode="json"),
        )
    payload = compute_liability_risk_buckets(
        resolved_date,
        zqtz_rows,
        tyw_rows,
    )
    return _envelope(
        result_kind="liability_analytics.risk_buckets",
        source_rows=[*zqtz_rows, *tyw_rows],
        result_payload=LiabilityRiskBucketsPayload.model_validate(payload).model_dump(mode="json"),
    )


def liability_yield_metrics_payload(*, duckdb_path: str, report_date: str | None) -> dict[str, object]:
    repo = LiabilityAnalyticsRepository(duckdb_path)
    resolved_date = _resolve_report_date(repo, report_date)
    zqtz_rows = repo.fetch_zqtz_rows(resolved_date) if resolved_date else []
    tyw_rows = repo.fetch_tyw_rows(resolved_date) if resolved_date else []
    if not resolved_date:
        return _envelope(
            result_kind="liability_analytics.yield_metrics",
            source_rows=[],
            quality_flag="warning",
            result_payload=LiabilityYieldMetricsPayload(
                report_date="",
                kpi=LiabilityYieldKpi(),
            ).model_dump(mode="json"),
        )
    payload = compute_liability_yield_metrics(
        resolved_date,
        zqtz_rows,
        tyw_rows,
    )
    return _envelope(
        result_kind="liability_analytics.yield_metrics",
        source_rows=[*zqtz_rows, *tyw_rows],
        result_payload=LiabilityYieldMetricsPayload.model_validate(payload).model_dump(mode="json"),
    )


def liability_counterparty_payload(
    *,
    duckdb_path: str,
    report_date: str | None,
    top_n: int,
) -> dict[str, object]:
    repo = LiabilityAnalyticsRepository(duckdb_path)
    resolved_date = _resolve_report_date(repo, report_date)
    tyw_rows = repo.fetch_tyw_rows(resolved_date) if resolved_date else []
    if not resolved_date:
        return _envelope(
            result_kind="liability_analytics.counterparty",
            source_rows=[],
            quality_flag="warning",
            result_payload=LiabilityCounterpartyPayload(
                report_date="",
                total_value=0.0,
                top_10=[],
                by_type=[],
            ).model_dump(mode="json"),
        )
    payload = compute_liability_counterparty(
        resolved_date,
        tyw_rows,
        top_n=top_n,
    )
    return _envelope(
        result_kind="liability_analytics.counterparty",
        source_rows=tyw_rows,
        result_payload=LiabilityCounterpartyPayload.model_validate(payload).model_dump(mode="json"),
    )


def liabilities_monthly_payload(*, duckdb_path: str, year: int) -> dict[str, object]:
    repo = LiabilityAnalyticsRepository(duckdb_path)
    zqtz_rows = repo.fetch_zqtz_liability_rows_for_year(year)
    tyw_rows = repo.fetch_tyw_liability_rows_for_year(year)
    payload = compute_liabilities_monthly(
        year,
        zqtz_rows,
        tyw_rows,
    )
    return _envelope(
        result_kind="liability_analytics.monthly",
        source_rows=[*zqtz_rows, *tyw_rows],
        quality_flag="warning" if not payload.get("months") else "ok",
        result_payload=LiabilitiesMonthlyPayload.model_validate(payload).model_dump(mode="json"),
    )
