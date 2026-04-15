from __future__ import annotations

from backend.app.core_finance.liability_analytics_compat import (
    compute_liabilities_monthly,
    compute_liability_counterparty,
    compute_liability_risk_buckets,
    compute_liability_yield_metrics,
)
from backend.app.repositories.liability_analytics_repo import LiabilityAnalyticsRepository


def _resolve_report_date(repo: LiabilityAnalyticsRepository, report_date: str | None) -> str:
    candidate = str(report_date or "").strip()
    if candidate:
        return candidate
    return repo.resolve_latest_report_date() or ""


def liability_risk_buckets_payload(*, duckdb_path: str, report_date: str | None) -> dict[str, object]:
    repo = LiabilityAnalyticsRepository(duckdb_path)
    resolved_date = _resolve_report_date(repo, report_date)
    if not resolved_date:
        return {
            "report_date": "",
            "liabilities_structure": [],
            "liabilities_term_buckets": [],
            "interbank_liabilities_structure": [],
            "interbank_liabilities_term_buckets": [],
            "issued_liabilities_structure": [],
            "issued_liabilities_term_buckets": [],
        }
    return compute_liability_risk_buckets(
        resolved_date,
        repo.fetch_zqtz_rows(resolved_date),
        repo.fetch_tyw_rows(resolved_date),
    )


def liability_yield_metrics_payload(*, duckdb_path: str, report_date: str | None) -> dict[str, object]:
    repo = LiabilityAnalyticsRepository(duckdb_path)
    resolved_date = _resolve_report_date(repo, report_date)
    if not resolved_date:
        return {
            "report_date": "",
            "kpi": {
                "asset_yield": None,
                "liability_cost": None,
                "market_liability_cost": None,
                "nim": None,
            },
        }
    return compute_liability_yield_metrics(
        resolved_date,
        repo.fetch_zqtz_rows(resolved_date),
        repo.fetch_tyw_rows(resolved_date),
    )


def liability_counterparty_payload(
    *,
    duckdb_path: str,
    report_date: str | None,
    top_n: int,
) -> dict[str, object]:
    repo = LiabilityAnalyticsRepository(duckdb_path)
    resolved_date = _resolve_report_date(repo, report_date)
    if not resolved_date:
        return {"report_date": "", "total_value": 0.0, "top_10": [], "by_type": []}
    return compute_liability_counterparty(
        resolved_date,
        repo.fetch_tyw_rows(resolved_date),
        top_n=top_n,
    )


def liabilities_monthly_payload(*, duckdb_path: str, year: int) -> dict[str, object]:
    repo = LiabilityAnalyticsRepository(duckdb_path)
    return compute_liabilities_monthly(
        year,
        repo.fetch_zqtz_liability_rows_for_year(year),
        repo.fetch_tyw_liability_rows_for_year(year),
    )
