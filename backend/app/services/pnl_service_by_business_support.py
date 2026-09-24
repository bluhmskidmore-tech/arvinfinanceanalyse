"""pnl_service 门面的 by-business 辅助子模块：手工调整事件包装与预计算参数/记录纯工具（自 pnl_service.py 逐字拆出）。"""
from __future__ import annotations

import re
from calendar import monthrange
from datetime import date

from backend.app.core_finance.zqtz_asset_bond_category import ZQTZ_ASSET_BOND_ROWS
from backend.app.governance.settings import Settings
from backend.app.repositories.pnl_repo import PnlRepository
from backend.app.services.pnl_by_business_adjustments import (
    PNL_BY_BUSINESS_ADJUSTMENT_STREAM,
    active_pnl_by_business_manual_adjustments_for_period,
    load_pnl_by_business_manual_adjustment_events,
    reduce_latest_pnl_by_business_manual_adjustments,
)
from backend.app.services.pnl_service_shared_utils import _norm_text


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


def _manual_adjustment_row_def(record: dict[str, object]) -> dict[str, object]:
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
