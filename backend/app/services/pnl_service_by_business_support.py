"""业务种类损益的来源复核、质量标记、手工调整和预计算辅助函数。"""
from __future__ import annotations

import re
from calendar import monthrange
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Literal, TypedDict

from backend.app.core_finance.pnl_by_business_insights import (
    prior_year_same_period_date,
    trailing_month_keys,
)
from backend.app.core_finance.zqtz_asset_bond_category import ZQTZ_ASSET_BOND_ROWS
from backend.app.governance.settings import Settings
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.repositories.pnl_repo import PnlRepository
from backend.app.schemas.pnl import (
    PnlByBusinessBalanceQualityIssue,
    PnlByBusinessMonthlyPayload,
    PnlByBusinessYtdPayload,
)
from backend.app.services.pnl_by_business_adjustments import (
    PNL_BY_BUSINESS_ADJUSTMENT_STREAM,
    active_pnl_by_business_manual_adjustments_for_period,
    load_pnl_by_business_manual_adjustment_events,
    reduce_latest_pnl_by_business_manual_adjustments,
)
from backend.app.services.pnl_service_shared_utils import _coverage_quality_flag, _norm_text


class PnlByBusinessPageDependency(TypedDict):
    key: str
    year: int
    requested_report_date: str


def _pnl_by_business_ytd_quality_flag(payload: PnlByBusinessYtdPayload) -> Literal["warning"] | None:
    if _coverage_quality_flag(payload.coverage_days, payload.expected_days):
        return "warning"
    if payload.unallocated_row_count > 0 or payload.reconciliation_delta != Decimal("0"):
        return "warning"
    return None


def _pnl_by_business_monthly_quality_flag(payload: PnlByBusinessMonthlyPayload) -> Literal["warning"] | None:
    for bucket in payload.months:
        if _coverage_quality_flag(bucket.coverage_days, bucket.expected_days):
            return "warning"
        if bucket.unallocated_row_count > 0 or bucket.reconciliation_delta != Decimal("0"):
            return "warning"
    return None


def _attach_pnl_by_business_balance_quality(
    *, governance_dir: str, payload: dict[str, object], resolved_report_date: str
) -> dict[str, object]:
    """Overlay current source-review state on both live and precomputed responses."""
    period_end = str(payload.get("period_end_date") or payload.get("as_of_date") or resolved_report_date)
    period_start = str(payload.get("period_start_date") or f"{period_end[:4]}-01-01")
    latest: dict[str, dict[str, object]] = {}
    for event in GovernanceRepository(base_dir=governance_dir).read_all("data_quality_remediation"):
        if event.get("scope") == "pnl_by_business_balance" and event.get("issue_id"):
            latest[str(event["issue_id"])] = event
    issues = [
        PnlByBusinessBalanceQualityIssue(
            issue_id=issue_id,
            report_date=str(event["report_date"]),
            reason=str(event["reason"]),
            source_file=str(event.get("source_file") or ""),
            source_version=str(event.get("source_version") or ""),
        ).model_dump(mode="json")
        for issue_id, event in sorted(latest.items())
        if event.get("status") == "pending"
        and period_start <= str(event.get("report_date") or "") <= period_end
    ]
    result = {**payload, "balance_quality_issues": issues}
    months = payload.get("months")
    if isinstance(months, list):
        result["months"] = [
            {
                **bucket,
                "balance_quality_issues": [
                    issue for issue in issues
                    if str(bucket["period_start_date"]) <= issue["report_date"] <= str(bucket["period_end_date"])
                ],
            }
            for bucket in months
        ]
        change = payload.get("management_change")
        if isinstance(change, dict):
            warning_months = sorted({
                issue["report_date"][:7] for issue in issues
                if issue["report_date"][:7] in {change.get("current_month_key"), change.get("previous_month_key")}
            })
            result["management_change"] = {
                **change,
                "balance_quality_warning_months": warning_months,
                "comparison_status": (
                    "data_quality_warning" if warning_months and change.get("comparison_available")
                    else change.get("comparison_status")
                ),
            }
    return result


def _load_pnl_by_business_manual_adjustment_events(settings: Settings) -> list[dict[str, object]]:
    return load_pnl_by_business_manual_adjustment_events(settings.governance_path)


def _reduce_latest_pnl_by_business_manual_adjustments(events: list[dict[str, object]]) -> list[dict[str, object]]:
    return reduce_latest_pnl_by_business_manual_adjustments(events)


def _active_pnl_by_business_manual_adjustments(settings: Settings, *, report_date: str) -> list[dict[str, object]]:
    return [
        record
        for record in active_pnl_by_business_manual_adjustments_for_period(
            settings.governance_path,
            year=int(report_date[:4]),
            period_end=report_date,
        )
        if str(record.get("report_date") or "") == report_date
    ]


def _require_pnl_by_business_manual_adjustment(settings: Settings, adjustment_id: str) -> dict[str, object]:
    records = _reduce_latest_pnl_by_business_manual_adjustments(
        _load_pnl_by_business_manual_adjustment_events(settings)
    )
    for record in records:
        if str(record.get("adjustment_id") or "") == adjustment_id:
            return record
    raise ValueError(f"Unknown pnl-by-business adjustment_id={adjustment_id}")


def _manual_adjustment_row_def(record: Mapping[str, object]) -> dict[str, object]:
    row_key = str(record.get("manual_business_row_key") or record.get("row_key") or "").strip()
    for row_def in ZQTZ_ASSET_BOND_ROWS:
        if str(row_def.get("row_key") or "") == row_key:
            return row_def
    return {
        "row_key": row_key or "manual_unclassified",
        "sort_order": 999,
        "row_label": str(record.get("manual_business_type") or record.get("business_type") or row_key or "手工调整"),
        "source_note": str(record.get("source_note") or "pnl_by_business_adjustments"),
    }


def _pnl_by_business_manual_classification(record: dict[str, object]) -> dict[str, object]:
    row_def = _manual_adjustment_row_def(record)
    label = str(row_def.get("row_label") or record.get("manual_business_type") or "")
    return {
        "report_date": _norm_text(record.get("report_date")),
        "instrument_code": _norm_text(record.get("instrument_code")),
        "instrument_name": label,
        "account_category": "manual_adjustment",
        "asset_class": label,
        "bond_type": label,
        "sub_type": label,
        "business_type_primary": label,
        "business_type_final": label,
        "invest_type_std": "",
        "accounting_basis": "manual_adjustment",
        "currency_code": "CNY",
        "manual_business_row_key": str(row_def.get("row_key") or ""),
    }


def _source_tables_with_manual_adjustments(source_tables: list[str], *, settings: Settings, loaded_dates: list[str]) -> list[str]:
    for report_date in loaded_dates:
        if _active_pnl_by_business_manual_adjustments(settings, report_date=report_date):
            if PNL_BY_BUSINESS_ADJUSTMENT_STREAM not in source_tables:
                return [*source_tables, PNL_BY_BUSINESS_ADJUSTMENT_STREAM]
            return source_tables
    return source_tables


def _normalize_pnl_by_business_precompute_year(year: int) -> int:
    normalized_year = int(year)
    if not 2000 <= normalized_year <= 2100:
        raise ValueError("year must be between 2000 and 2100.")
    return normalized_year


def _normalize_pnl_by_business_precompute_as_of_date(*, year: int, as_of_date: str | None) -> str | None:
    if as_of_date is None:
        return None
    raw_value = str(as_of_date)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_value) is None:
        raise ValueError("as_of_date must use YYYY-MM-DD format.")
    try:
        parsed = date.fromisoformat(raw_value)
    except ValueError as exc:
        raise ValueError("as_of_date must use YYYY-MM-DD format.") from exc
    if parsed.year != int(year):
        raise ValueError(f"as_of_date={parsed.isoformat()} is outside requested year={int(year)}.")
    return parsed.isoformat()


def _available_pnl_by_business_precompute_cutoffs(
    repo: PnlRepository,
    *,
    year: int,
) -> list[str]:
    cutoffs: set[str] = set()
    for raw_date in repo.list_union_report_dates():
        raw_value = str(raw_date)
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_value) is None:
            continue
        try:
            parsed = date.fromisoformat(raw_value)
        except ValueError:
            continue
        if parsed.year != int(year) or parsed.day != monthrange(parsed.year, parsed.month)[1]:
            continue
        cutoffs.add(parsed.isoformat())
    if not cutoffs:
        raise ValueError(f"No available month-end cutoffs found for year={int(year)}.")
    return sorted(cutoffs)


def pnl_by_business_page_dependencies(
    *, year: int, as_of_date: str
) -> tuple[PnlByBusinessPageDependency, ...]:
    """Return the exact read-model cutoffs consumed by the approved insights page."""
    normalized = _normalize_pnl_by_business_precompute_as_of_date(
        year=year,
        as_of_date=as_of_date,
    )
    assert normalized is not None
    parsed = date.fromisoformat(normalized)
    if parsed.day != monthrange(parsed.year, parsed.month)[1]:
        raise ValueError(f"as_of_date={normalized} is not a month-end cutoff.")
    baseline_date = prior_year_same_period_date(normalized)
    dependencies: list[PnlByBusinessPageDependency] = [
        {"key": "current_ytd", "year": year, "requested_report_date": normalized},
        {
            "key": "baseline_ytd",
            "year": year - 1,
            "requested_report_date": baseline_date,
        },
        {"key": "monthly", "year": year, "requested_report_date": normalized},
    ]
    monthly_years = {int(month_key[:4]) for month_key in trailing_month_keys(normalized, 12)}
    if year - 1 in monthly_years:
        dependencies.append(
            {
                "key": "monthly_baseline",
                "year": year - 1,
                "requested_report_date": f"{year - 1:04d}-12-31",
            }
        )
    return tuple(dependencies)


def _pnl_by_business_precompute_record_target_dates(record: dict[str, object]) -> set[str]:
    raw_dates = record.get("target_as_of_dates")
    if not isinstance(raw_dates, (list, tuple, set)):
        return set()
    return {str(item) for item in raw_dates if str(item)}


def _pnl_by_business_precompute_cutoff_result(
    record: dict[str, object],
    *,
    period_end: str,
) -> dict[str, object] | None:
    raw_results = record.get("cutoff_results")
    if not isinstance(raw_results, list):
        return None
    for item in raw_results:
        if isinstance(item, dict) and str(item.get("as_of_date") or "") == period_end:
            return item
    return None


def _safe_pnl_by_business_precompute_error_message(*, status: str, failure_category: str) -> str | None:
    if failure_category == "automatic_retry_pending":
        return "上一次预计算未完成，后台正在按策略自动重试。"
    if status != "failed":
        return None
    if failure_category == "queue_dispatch_failure":
        return "预计算任务分发失败，请检查后台队列后重试。"
    if failure_category == "stale_inflight":
        return "预计算任务长时间未更新，已解除占用，可重新生成。"
    if failure_category == "lock_timeout":
        return "预计算暂未取得数据写入锁，自动重试已结束。"
    return "预计算执行失败，自动重试已结束，请查看后台运行日志。"
