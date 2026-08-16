"""Approved leadership insights plus the legacy candidate compatibility route.

`MTR-PNLBIZ-001`~`005` and `007` are approved descriptive business-analysis
metrics. They re-aggregate governed parent rows from
`pnl_service.pnl_by_business_ytd_envelope` and
`pnl_service.pnl_by_business_monthly_envelope`. The formal endpoint admits
those analytical wrappers only when their dates, lineage and formal-fact source
tables pass the component gate below. The legacy candidate endpoint remains
analytical and always returns ``formal_use_allowed=false``.

`reconciliation_diagnostics` (`MTR-PNLBIZ-006`) is a **different metric kind**:
an approved formal data-quality / reconciliation health diagnostic, not a
business-analysis re-aggregation. It batches the existing single-day
`PnlRepository.count_untraced_formal_fi_rows` SQL (see
`docs/page_contracts.md` §14.8.1 section G) across trailing month-end report
dates. It intentionally does re-query `fact_formal_pnl_fi` /
`fact_formal_zqtz_balance_daily`, uses an `untraced_`-prefixed field
vocabulary distinct from the business-analysis rows above, and must not be
mixed into monthly/YTD business contribution conclusions.
"""

from __future__ import annotations

import uuid
from calendar import monthrange
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any

from backend.app.core_finance.pnl import TWOPLACES
from backend.app.core_finance.pnl_by_business_insights import (
    build_business_type_concentration,
    build_business_type_share_drift,
    build_negative_ftp_persistence,
    build_scale_yield_quadrant,
)
from backend.app.core_finance.zqtz_asset_bond_category import is_parent_zqtz_business_row
from backend.app.repositories.pnl_repo import PnlRepository
from backend.app.schemas.pnl import (
    PnlByBusinessCandidateInsightsPayload,
    PnlByBusinessInsightsPayload,
)
from backend.app.services import pnl_service
from backend.app.services.formal_result_runtime import (
    FallbackMode,
    QualityFlag,
    ResultBasis,
    VendorStatus,
    build_result_envelope,
)

CACHE_VERSION = "cv_pnl_by_business_candidate_insights_v2"
RULE_VERSION = "rv_pnl_by_business_candidate_insights_v2"
RESULT_KIND = "pnl.by_business_candidate_insights"
FORMAL_CACHE_VERSION = "cv_pnl_by_business_insights_v2"
FORMAL_RULE_VERSION = "rv_pnl_by_business_insights_v2"
FORMAL_RESULT_KIND = "pnl.by_business_insights"

_ZERO = Decimal("0")
_HUNDRED = Decimal("100")
_FORMAL_COMPONENT_REQUIRED_TABLES = frozenset(
    {
        "fact_formal_pnl_fi",
        "fact_nonstd_pnl_bridge",
        "fact_formal_zqtz_balance_daily",
        "ZQTZ_ASSET_BOND_ROWS",
    }
)
_NONFORMAL_COMPONENT_TABLE_PREFIXES = ("data_input/",)


def _quantize_pct(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES)


def _trace_id(prefix: str) -> str:
    return f"tr_{prefix}_{uuid.uuid4().hex[:12]}"


def _parent_rows(items: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        item
        for item in items
        if is_parent_zqtz_business_row(
            str(item.get("row_key") or ""),
            str(item.get("business_type") or ""),
            item.get("source_note"),
        )
    ]


def _envelope_meta(envelope: Mapping[str, object]) -> dict[str, Any]:
    meta = envelope.get("result_meta")
    return dict(meta) if isinstance(meta, Mapping) else {}


def _envelope_result(envelope: Mapping[str, object]) -> dict[str, Any]:
    result = envelope.get("result")
    return dict(result) if isinstance(result, Mapping) else {}


def _resolved_ytd_date(envelope: Mapping[str, object]) -> str | None:
    meta = _envelope_meta(envelope)
    result = _envelope_result(envelope)
    meta_date = str(meta.get("resolved_report_date") or "") or None
    payload_date = str(result.get("period_end_date") or "") or None
    if not meta_date or not payload_date or meta_date != payload_date:
        return None
    return meta_date


def _prior_year_same_period_date(as_of_date: str) -> str:
    current = date.fromisoformat(as_of_date)
    baseline_year = current.year - 1
    baseline_day = min(current.day, monthrange(baseline_year, current.month)[1])
    return date(baseline_year, current.month, baseline_day).isoformat()


def compute_business_type_concentration(
    *,
    duckdb_path: str,
    governance_dir: str,
    year: int,
    as_of_date: str | None,
    top_n: int = 3,
) -> dict[str, object]:
    """业务种类集中度（HHI + 前 N 大占比），基于 YTD 父级行 ``avg_balance`` 二次聚合。

    只读 :func:`pnl_service.pnl_by_business_ytd_envelope` 的返回结果，不重新查询任何原始表。
    """
    envelope = pnl_service.pnl_by_business_ytd_envelope(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        year=year,
        as_of_date=as_of_date,
    )
    result = _envelope_result(envelope)
    return build_business_type_concentration(
        items=list(result.get("items", [])),
        year=year,
        as_of_date=_resolved_ytd_date(envelope),
        top_n=top_n,
    )


def _trailing_month_keys(as_of_date: str, lookback_months: int) -> list[str]:
    year = int(as_of_date[:4])
    month = int(as_of_date[5:7])
    keys: list[str] = []
    for _ in range(lookback_months):
        keys.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(keys))


def _collect_monthly_buckets(
    *,
    duckdb_path: str,
    governance_dir: str,
    as_of_date: str,
    window_month_keys: list[str],
) -> dict[str, dict[str, object]]:
    buckets, _ = _collect_monthly_inputs(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        as_of_date=as_of_date,
        window_month_keys=window_month_keys,
    )
    return buckets


def _collect_monthly_inputs(
    *,
    duckdb_path: str,
    governance_dir: str,
    as_of_date: str,
    window_month_keys: list[str],
) -> tuple[dict[str, dict[str, object]], list[dict[str, object]]]:
    if not window_month_keys:
        return {}, []
    window = set(window_month_keys)
    as_of_year = int(as_of_date[:4])
    years_needed = sorted({int(key[:4]) for key in window_month_keys})
    buckets: dict[str, dict[str, object]] = {}
    envelopes: list[dict[str, object]] = []
    for year in years_needed:
        year_as_of = as_of_date if year == as_of_year else None
        try:
            envelope = pnl_service.pnl_by_business_monthly_envelope(
                duckdb_path=duckdb_path,
                governance_dir=governance_dir,
                year=year,
                as_of_date=year_as_of,
            )
        except ValueError:
            continue
        envelopes.append(envelope)
        for bucket in _envelope_result(envelope).get("months", []):
            month_key = str(bucket.get("month_key") or "")
            if month_key in window:
                buckets[month_key] = bucket
    return buckets, envelopes


def _longest_negative_streak(series: list[tuple[str, Decimal | None]]) -> int:
    longest = 0
    current = 0
    for _, value in series:
        if value is not None and value < _ZERO:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _persistence_stats(series: list[tuple[str, Decimal | None]]) -> dict[str, object]:
    available = [value for _, value in series if value is not None]
    negative_count = sum(1 for value in available if value < _ZERO)
    negative_share_pct = (
        _quantize_pct(Decimal(negative_count) / Decimal(len(available)) * _HUNDRED) if available else None
    )
    return {
        "months_observed": len(available),
        "negative_ftp_month_share_pct": negative_share_pct,
        "negative_ftp_longest_streak_months": _longest_negative_streak(series),
    }


def compute_negative_ftp_persistence(
    *,
    duckdb_path: str,
    governance_dir: str,
    as_of_date: str,
    lookback_months: int = 12,
) -> dict[str, object]:
    """负 FTP 持续性追踪：近 ``lookback_months`` 个月父级行 ``ftp_net_pnl`` 的负值占比与最长连续负值月数。

    只读 :func:`pnl_service.pnl_by_business_monthly_envelope` 的返回结果；跨自然年边界时分别调用
    两次并按 ``month_key`` 去重取最新；某年份无数据（``ValueError``）时跳过该年继续，不整体报错。
    """
    window_month_keys = _trailing_month_keys(as_of_date, lookback_months)
    monthly_by_key = _collect_monthly_buckets(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        as_of_date=as_of_date,
        window_month_keys=window_month_keys,
    )
    return build_negative_ftp_persistence(
        monthly_by_key=monthly_by_key,
        as_of_date=as_of_date,
        lookback_months=lookback_months,
    )


def compute_business_type_share_drift(
    *,
    duckdb_path: str,
    governance_dir: str,
    year: int,
    as_of_date: str,
) -> dict[str, object]:
    """业务种类份额漂移：当前份额 vs 上一年末份额，按 ``row_key`` 对齐计算百分点漂移。

    上一年无 formal 数据时（:func:`compute_business_type_concentration` 内部抛 ``ValueError``），
    降级返回 ``baseline_share_pct=None``/``drift_pp=None``，不向上抛出异常。
    """
    current_envelope = pnl_service.pnl_by_business_ytd_envelope(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        year=year,
        as_of_date=as_of_date,
    )
    resolved_date = _resolved_ytd_date(current_envelope)
    if resolved_date is None:
        raise RuntimeError("Current YTD resolved report date is missing or inconsistent.")
    current_result = _envelope_result(current_envelope)
    current = build_business_type_concentration(
        items=list(current_result.get("items", [])),
        year=year,
        as_of_date=resolved_date,
    )
    baseline_year = year - 1
    baseline_as_of_date = _prior_year_same_period_date(resolved_date)
    baseline: dict[str, object] | None
    try:
        baseline_envelope = pnl_service.pnl_by_business_ytd_envelope(
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
            year=baseline_year,
            as_of_date=baseline_as_of_date,
        )
        baseline_resolved_date = _resolved_ytd_date(baseline_envelope)
        if baseline_resolved_date != baseline_as_of_date:
            baseline = None
        else:
            baseline = build_business_type_concentration(
                items=list(_envelope_result(baseline_envelope).get("items", [])),
                year=baseline_year,
                as_of_date=baseline_as_of_date,
            )
    except ValueError:
        baseline = None
    return build_business_type_share_drift(
        current=current,
        baseline=baseline,
        year=year,
        as_of_date=resolved_date,
        baseline_year=baseline_year,
        baseline_as_of_date=baseline_as_of_date,
    )


def compute_scale_yield_quadrant(
    *,
    duckdb_path: str,
    governance_dir: str,
    year: int,
    as_of_date: str,
) -> dict[str, object]:
    envelope = pnl_service.pnl_by_business_ytd_envelope(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        year=year,
        as_of_date=as_of_date,
    )
    result = _envelope_result(envelope)
    resolved_date = _resolved_ytd_date(envelope)
    if resolved_date is None:
        raise RuntimeError("Current YTD resolved report date is missing or inconsistent.")
    return build_scale_yield_quadrant(
        items=list(result.get("items", [])),
        year=year,
        as_of_date=resolved_date,
    )


# ── Reconciliation diagnostics (NOT a business-analysis metric) ─────────────
# Approved diagnostic-only `MTR-PNLBIZ-006`. This block is a batch-mode
# reuse of the existing single-day `PnlRepository.count_untraced_formal_fi_rows`
# reconciliation SQL (docs/page_contracts.md §14.8.1 G). It measures formal
# data-quality/reconciliation health, not business contribution or drag, and
# must be kept structurally separate from `concentration` /
# `negative_ftp_persistence` / `share_drift` above. Field names use the
# `untraced_` prefix (not `business_type` / `share_pct` style) to make this
# distinction explicit at the schema level.


def _resolve_trailing_month_end_report_dates(
    *,
    all_report_dates: list[str],
    as_of_date: str,
    lookback_months: int,
) -> list[str]:
    """近 ``lookback_months`` 个自然月各自的实际 formal 报表日（非自然月最后一天）。

    某月没有 formal 数据时该月直接缺席，不做插值/回填；返回列表长度恒 <= ``lookback_months``。
    """
    window_month_keys = _trailing_month_keys(as_of_date, lookback_months)
    window = set(window_month_keys)
    latest_by_month: dict[str, str] = {}
    for report_date in all_report_dates:
        month_key = report_date[:7]
        if month_key not in window or report_date > as_of_date:
            continue
        if report_date > latest_by_month.get(month_key, ""):
            latest_by_month[month_key] = report_date
    return [latest_by_month[month_key] for month_key in window_month_keys if month_key in latest_by_month]


def compute_untraced_reconciliation_trend(
    *,
    duckdb_path: str,
    as_of_date: str,
    lookback_months: int = 12,
) -> dict[str, object]:
    """formal 对账健康度诊断趋势（非业务结论）：近 ``lookback_months`` 个月末的
    ``fact_formal_pnl_fi`` 未追溯行占比。仅复用既有单日诊断 SQL 的批量版本，不重新设计口径；
    不得与月报/YTD业务贡献结论混用。
    """
    unavailable = {
        "as_of_date": as_of_date,
        "lookback_months": lookback_months,
        "available": False,
        "availability_reason": "source_unavailable",
        "rows": [],
    }
    repo = PnlRepository(duckdb_path)
    try:
        all_report_dates = repo.list_formal_fi_report_dates(require_table=True)
        report_dates = _resolve_trailing_month_end_report_dates(
            all_report_dates=all_report_dates,
            as_of_date=as_of_date,
            lookback_months=lookback_months,
        )
        if not report_dates:
            return {
                **unavailable,
                "availability_reason": "no_observations",
            }
        untraced_counts = repo.count_untraced_formal_fi_rows_for_dates(report_dates)
        total_counts = repo.count_formal_fi_rows_for_dates(report_dates)
    except RuntimeError:
        return unavailable

    rows: list[dict[str, object]] = []
    for report_date in report_dates:
        total_row_count = int(total_counts.get(report_date, 0))
        untraced_row_count = int(untraced_counts.get(report_date, 0))
        untraced_share_pct = (
            _quantize_pct(Decimal(untraced_row_count) / Decimal(total_row_count) * _HUNDRED)
            if total_row_count > 0
            else None
        )
        rows.append(
            {
                "report_date": report_date,
                "untraced_row_count": untraced_row_count,
                "total_row_count": total_row_count,
                "untraced_share_pct": untraced_share_pct,
            }
        )

    return {
        "as_of_date": as_of_date,
        "lookback_months": lookback_months,
        "available": True,
        "availability_reason": None,
        "rows": rows,
    }


def _normalized_fallback_mode(envelope: Mapping[str, object]) -> FallbackMode:
    meta = _envelope_meta(envelope)
    raw_mode = str(meta.get("fallback_mode") or "")
    if raw_mode != "none":
        return "latest_snapshot"
    requested = str(meta.get("requested_report_date") or "")
    resolved = str(meta.get("resolved_report_date") or "")
    return "none" if requested and resolved and requested == resolved else "latest_snapshot"


def _component_evidence(
    component: str,
    envelope: Mapping[str, object],
    *,
    requested_default: str | None,
) -> dict[str, object]:
    meta = _envelope_meta(envelope)
    result = _envelope_result(envelope)
    requested = str(meta.get("requested_report_date") or requested_default or "") or None
    resolved = str(meta.get("resolved_report_date") or "") or None
    payload_date_field = (
        "period_end_date"
        if component in {"current_ytd", "baseline_ytd"}
        else "as_of_date"
        if component.startswith("monthly_")
        else None
    )
    payload_report_date = str(result.get(payload_date_field) or "") or None if payload_date_field is not None else None
    raw_quality = str(meta.get("quality_flag") or "error")
    quality_flag = raw_quality if raw_quality in {"ok", "warning", "error", "stale"} else "error"
    raw_vendor = str(meta.get("vendor_status") or "vendor_unavailable")
    vendor_status = raw_vendor if raw_vendor in {"ok", "vendor_stale", "vendor_unavailable"} else "vendor_unavailable"
    raw_basis = str(meta.get("basis") or "")
    basis = raw_basis if raw_basis in {"formal", "scenario", "analytical", "ledger"} else None
    formal_use_allowed = meta.get("formal_use_allowed")
    if not isinstance(formal_use_allowed, bool):
        formal_use_allowed = None
    tables_used: list[str] = []
    for candidate in (meta.get("tables_used"), result.get("source_tables")):
        if not isinstance(candidate, list):
            continue
        for table in candidate:
            table_name = str(table).strip()
            if table_name and table_name not in tables_used:
                tables_used.append(table_name)
    fallback_mode = _normalized_fallback_mode(envelope)
    evidence: dict[str, object] = {
        "component": component,
        "requested_report_date": requested,
        "resolved_report_date": resolved,
        "fallback_mode": fallback_mode,
        "quality_flag": quality_flag,
        "vendor_status": vendor_status,
        "basis": basis,
        "formal_use_allowed": formal_use_allowed,
        "result_kind": str(meta.get("result_kind") or "") or None,
        "trace_id": str(meta.get("trace_id") or "") or None,
        "source_surface": str(meta.get("source_surface") or "") or None,
        "source_version": str(meta.get("source_version") or "") or None,
        "rule_version": str(meta.get("rule_version") or "") or None,
        "cache_version": str(meta.get("cache_version") or "") or None,
        "tables_used": tables_used,
    }
    admission_reason = _component_admission_reason(
        evidence,
        expected_report_date=requested_default,
        payload_report_date=payload_report_date,
        fallback_date=str(meta.get("fallback_date") or "") or None,
    )
    evidence["formal_source_admitted"] = admission_reason is None
    evidence["admission_reason"] = admission_reason
    return evidence


def _component_admission_reason(
    evidence: Mapping[str, object],
    *,
    expected_report_date: str | None,
    payload_report_date: str | None,
    fallback_date: str | None,
) -> str | None:
    component = str(evidence.get("component") or "")
    expected_result_kind = (
        "pnl.by_business_ytd"
        if component in {"current_ytd", "baseline_ytd"}
        else "pnl.by_business_monthly"
        if component.startswith("monthly_")
        else None
    )
    if evidence.get("basis") != "analytical":
        return "unexpected_basis"
    if evidence.get("formal_use_allowed") is not False:
        return "unexpected_formal_use_allowed"
    if not expected_result_kind or evidence.get("result_kind") != expected_result_kind:
        return "unexpected_result_kind"
    if not evidence.get("trace_id"):
        return "missing_trace_id"
    if evidence.get("source_surface") != "formal_pnl":
        return "unexpected_source_surface"
    if not evidence.get("source_version"):
        return "missing_source_version"
    if not evidence.get("rule_version"):
        return "missing_rule_version"
    if not evidence.get("cache_version"):
        return "missing_cache_version"
    if (
        not expected_report_date
        or evidence.get("requested_report_date") != expected_report_date
        or evidence.get("resolved_report_date") != expected_report_date
        or payload_report_date != expected_report_date
    ):
        return "date_mismatch"
    if evidence.get("fallback_mode") != "none" or fallback_date:
        return "fallback_used"
    if evidence.get("quality_flag") not in {"ok", "warning"}:
        return "unusable_quality"
    if evidence.get("vendor_status") != "ok":
        return "unusable_vendor"
    tables_used_raw = evidence.get("tables_used", [])
    # Evidence dicts always carry tables_used as a list (see _component_evidence).
    assert isinstance(tables_used_raw, list)
    tables_used = {str(table) for table in tables_used_raw}
    if any(table.startswith(prefix) for table in tables_used for prefix in _NONFORMAL_COMPONENT_TABLE_PREFIXES):
        return "nonformal_source_tables"
    if not _FORMAL_COMPONENT_REQUIRED_TABLES.issubset(tables_used):
        return "missing_required_source_tables"
    return None


def _unavailable_component_evidence(
    component: str,
    *,
    requested_report_date: str,
) -> dict[str, object]:
    return {
        "component": component,
        "requested_report_date": requested_report_date,
        "resolved_report_date": None,
        "fallback_mode": "none",
        "quality_flag": "warning",
        "vendor_status": "vendor_unavailable",
        "basis": None,
        "formal_use_allowed": None,
        "result_kind": None,
        "trace_id": None,
        "source_surface": None,
        "source_version": None,
        "rule_version": None,
        "cache_version": None,
        "tables_used": [],
        "formal_source_admitted": False,
        "admission_reason": "component_unavailable",
    }


def _build_insights_components(
    *,
    duckdb_path: str,
    governance_dir: str,
    year: int,
    as_of_date: str,
) -> tuple[dict[str, Any], list[dict[str, object]], str, bool]:
    current_envelope = pnl_service.pnl_by_business_ytd_envelope(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        year=year,
        as_of_date=as_of_date,
    )
    current_result = _envelope_result(current_envelope)
    resolved_date = _resolved_ytd_date(current_envelope)
    if resolved_date is None:
        raise RuntimeError("Current YTD resolved report date is missing or inconsistent.")
    current_items = list(current_result.get("items", []))

    concentration = build_business_type_concentration(
        items=current_items,
        year=year,
        as_of_date=resolved_date,
    )
    scale_yield_quadrant = build_scale_yield_quadrant(
        items=current_items,
        year=year,
        as_of_date=resolved_date,
    )

    baseline_year = year - 1
    baseline_requested_date = _prior_year_same_period_date(resolved_date)
    baseline_envelope: dict[str, object] | None = None
    baseline_concentration: dict[str, object] | None = None
    baseline_resolved_date: str | None = None
    baseline_fallback_mode: str = "unavailable"
    try:
        candidate_baseline_envelope = pnl_service.pnl_by_business_ytd_envelope(
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
            year=baseline_year,
            as_of_date=baseline_requested_date,
        )
        baseline_envelope = candidate_baseline_envelope
        baseline_resolved_date = _resolved_ytd_date(candidate_baseline_envelope)
        baseline_fallback_mode = _normalized_fallback_mode(candidate_baseline_envelope)
        if baseline_resolved_date == baseline_requested_date and baseline_fallback_mode == "none":
            baseline_concentration = build_business_type_concentration(
                items=list(_envelope_result(candidate_baseline_envelope).get("items", [])),
                year=baseline_year,
                as_of_date=baseline_requested_date,
            )
    except ValueError:
        baseline_envelope = None

    share_drift = build_business_type_share_drift(
        current=concentration,
        baseline=baseline_concentration,
        year=year,
        as_of_date=resolved_date,
        baseline_year=baseline_year,
        baseline_as_of_date=baseline_requested_date,
    )

    window_month_keys = _trailing_month_keys(resolved_date, 12)
    monthly_by_key, monthly_envelopes = _collect_monthly_inputs(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        as_of_date=resolved_date,
        window_month_keys=window_month_keys,
    )
    negative_ftp_persistence = build_negative_ftp_persistence(
        monthly_by_key=monthly_by_key,
        as_of_date=resolved_date,
        lookback_months=12,
    )
    reconciliation_diagnostics = compute_untraced_reconciliation_trend(
        duckdb_path=duckdb_path,
        as_of_date=resolved_date,
    )
    component_evidence = [_component_evidence("current_ytd", current_envelope, requested_default=as_of_date)]
    if baseline_envelope is not None:
        component_evidence.append(
            _component_evidence(
                "baseline_ytd",
                baseline_envelope,
                requested_default=baseline_requested_date,
            )
        )
    else:
        component_evidence.append(
            _unavailable_component_evidence(
                "baseline_ytd",
                requested_report_date=baseline_requested_date,
            )
        )

    monthly_envelope_by_component: dict[str, dict[str, object]] = {}
    for index, indexed_monthly_envelope in enumerate(monthly_envelopes, start=1):
        monthly_meta = _envelope_meta(indexed_monthly_envelope)
        monthly_date = str(monthly_meta.get("requested_report_date") or monthly_meta.get("resolved_report_date") or "")
        monthly_suffix = monthly_date[:4] if len(monthly_date) >= 4 else str(index)
        component = f"monthly_{monthly_suffix}"
        monthly_envelope_by_component[component] = indexed_monthly_envelope

    expected_monthly_years = sorted({int(month_key[:4]) for month_key in window_month_keys})
    current_year = int(resolved_date[:4])
    for monthly_year in expected_monthly_years:
        component = f"monthly_{monthly_year}"
        requested_date = resolved_date if monthly_year == current_year else f"{monthly_year}-12-31"
        monthly_envelope: dict[str, object] | None = monthly_envelope_by_component.pop(component, None)
        if monthly_envelope is None:
            evidence = _unavailable_component_evidence(
                component,
                requested_report_date=requested_date,
            )
        else:
            evidence = _component_evidence(
                component,
                monthly_envelope,
                requested_default=requested_date,
            )
        if monthly_envelope is not None and any(
            month_key not in monthly_by_key for month_key in window_month_keys if int(month_key[:4]) == monthly_year
        ):
            evidence["quality_flag"] = "warning"
        component_evidence.append(evidence)
    for component, monthly_envelope in monthly_envelope_by_component.items():
        component_evidence.append(
            _component_evidence(
                component,
                monthly_envelope,
                requested_default=None,
            )
        )
    payload = {
        "result_version": "v2",
        "year": year,
        "as_of_date": resolved_date,
        "baseline_requested_report_date": baseline_requested_date,
        "baseline_resolved_report_date": baseline_resolved_date,
        "baseline_fallback_mode": baseline_fallback_mode,
        "component_evidence": component_evidence,
        "concentration": concentration,
        "negative_ftp_persistence": negative_ftp_persistence,
        "share_drift": share_drift,
        "scale_yield_quadrant": scale_yield_quadrant,
        "reconciliation_diagnostics": reconciliation_diagnostics,
    }
    source_envelopes = [current_envelope, *monthly_envelopes]
    if baseline_envelope is not None:
        source_envelopes.append(baseline_envelope)
    return payload, source_envelopes, resolved_date, bool(share_drift["available"])


def _source_tables(
    envelopes: list[dict[str, object]],
    *,
    reconciliation_available: bool,
) -> list[str]:
    tables: set[str] = set()
    for envelope in envelopes:
        meta_tables = _envelope_meta(envelope).get("tables_used")
        result_tables = _envelope_result(envelope).get("source_tables")
        for candidate in (meta_tables, result_tables):
            if isinstance(candidate, list):
                tables.update(str(table) for table in candidate if str(table).strip())
    if reconciliation_available:
        tables.update({"fact_formal_pnl_fi", "fact_formal_zqtz_balance_daily"})
    return sorted(tables)


def _composite_meta_value(
    envelopes: list[dict[str, object]],
    field: str,
    *,
    default: str,
) -> str:
    values = sorted(
        {
            str(value)
            for envelope in envelopes
            if (value := _envelope_meta(envelope).get(field)) is not None and str(value).strip()
        }
    )
    return "+".join(values) if values else default


def _composite_vendor_status(envelopes: list[dict[str, object]]) -> VendorStatus:
    allowed_statuses = {"ok", "vendor_stale", "vendor_unavailable"}
    statuses = {str(_envelope_meta(envelope).get("vendor_status") or "vendor_unavailable") for envelope in envelopes}
    if "vendor_unavailable" in statuses or any(status not in allowed_statuses for status in statuses):
        return "vendor_unavailable"
    if "vendor_stale" in statuses:
        return "vendor_stale"
    return "ok"


def _component_vendor_status(component_evidence: list[dict[str, object]]) -> VendorStatus:
    allowed_statuses = {"ok", "vendor_stale", "vendor_unavailable"}
    statuses = {str(entry.get("vendor_status") or "vendor_unavailable") for entry in component_evidence}
    if "vendor_unavailable" in statuses or any(status not in allowed_statuses for status in statuses):
        return "vendor_unavailable"
    if "vendor_stale" in statuses:
        return "vendor_stale"
    return "ok"


def _composite_fallback_date(envelopes: list[dict[str, object]]) -> str | None:
    for envelope in envelopes:
        if _normalized_fallback_mode(envelope) == "none":
            continue
        meta = _envelope_meta(envelope)
        fallback_date = str(meta.get("fallback_date") or meta.get("resolved_report_date") or "")
        if fallback_date:
            return fallback_date
    return None


def _insights_quality_flag(
    envelopes: list[dict[str, object]],
    *,
    baseline_available: bool,
    concentration_available: bool,
    quadrant_available: bool,
    negative_ftp_available: bool,
    monthly_source_complete: bool,
    reconciliation_available: bool = True,
) -> QualityFlag:
    allowed_qualities = {"ok", "warning", "error", "stale"}
    qualities = {str(_envelope_meta(envelope).get("quality_flag") or "error") for envelope in envelopes}
    if "error" in qualities or any(quality not in allowed_qualities for quality in qualities):
        return "error"
    if "stale" in qualities:
        return "stale"
    if (
        "warning" in qualities
        or not baseline_available
        or not concentration_available
        or not quadrant_available
        or not negative_ftp_available
        or not monthly_source_complete
        or not reconciliation_available
        or any(_normalized_fallback_mode(envelope) != "none" for envelope in envelopes)
        or _composite_vendor_status(envelopes) != "ok"
    ):
        return "warning"
    return "ok"


def _build_insights_envelope(
    *,
    basis: ResultBasis,
    result_kind: str,
    cache_version: str,
    rule_version: str,
    payload_model: type[PnlByBusinessCandidateInsightsPayload],
    duckdb_path: str,
    governance_dir: str,
    year: int,
    as_of_date: str,
) -> dict[str, object]:
    payload, source_envelopes, resolved_date, baseline_available = _build_insights_components(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        year=year,
        as_of_date=as_of_date,
    )
    # Human: caliber-formal_scenario_gate-justified -- this is a second-layer
    # source-admission check after endpoint and basis selection, not a replacement
    # for the canonical basis/view policy.
    if basis == "formal":
        rejected_components = [
            f"{entry.get('component')}:{entry.get('admission_reason') or 'not_admitted'}"
            for entry in payload["component_evidence"]
            if not entry.get("formal_source_admitted")
        ]
        if rejected_components:
            raise RuntimeError(
                "Formal pnl-by-business insights source admission failed: " + ", ".join(rejected_components)
            )
    validated_payload = payload_model.model_validate(payload).model_dump(mode="json")
    current_meta = _envelope_meta(source_envelopes[0])
    fallback_used = bool(
        as_of_date != resolved_date
        or any(_normalized_fallback_mode(envelope) != "none" for envelope in source_envelopes)
    )
    negative_ftp = payload["negative_ftp_persistence"]
    monthly_source_complete = int(negative_ftp.get("months_observed") or 0) == int(
        negative_ftp.get("lookback_months") or 0
    )
    component_vendor_status = _component_vendor_status(payload["component_evidence"])
    reconciliation_available = bool(payload["reconciliation_diagnostics"].get("available"))
    quality_flag = _insights_quality_flag(
        source_envelopes,
        baseline_available=baseline_available,
        concentration_available=payload["concentration"].get("hhi_pct") is not None,
        quadrant_available=bool(payload["scale_yield_quadrant"].get("available")),
        negative_ftp_available=bool(negative_ftp.get("eligible")),
        monthly_source_complete=monthly_source_complete,
        reconciliation_available=reconciliation_available,
    )
    return build_result_envelope(
        basis=basis,
        trace_id=_trace_id(result_kind.replace(".", "_")),
        result_kind=result_kind,
        cache_version=cache_version,
        source_version=_composite_meta_value(
            source_envelopes,
            "source_version",
            default=f"sv_{result_kind.replace('.', '_')}_{year}_{resolved_date}",
        ),
        rule_version=rule_version,
        vendor_version=_composite_meta_value(source_envelopes, "vendor_version", default="vv_none"),
        vendor_status=component_vendor_status,
        quality_flag=quality_flag,
        fallback_mode="latest_snapshot" if fallback_used else "none",
        result_payload=validated_payload,
        filters_applied={"year": year, "as_of_date": as_of_date},
        tables_used=_source_tables(
            source_envelopes,
            reconciliation_available=reconciliation_available,
        ),
        evidence_rows=len(payload["concentration"].get("rows", [])),
        next_drill=["business_type", "currency_basis", "instrument"],
        source_surface="formal_pnl",
        requested_report_date=as_of_date,
        resolved_report_date=resolved_date,
        as_of_date=resolved_date,
        date_basis=str(current_meta.get("date_basis") or "formal_report_date_cutoff"),
        fallback_date=(
            _composite_fallback_date(source_envelopes) or (resolved_date if as_of_date != resolved_date else None)
        ),
    )


def pnl_by_business_candidate_insights_envelope(
    *,
    duckdb_path: str,
    governance_dir: str,
    year: int,
    as_of_date: str,
) -> dict[str, object]:
    """组装候选分析指标信封；``formal_use_allowed`` 恒为 ``False``，不接受任何调用方覆盖。"""
    envelope = _build_insights_envelope(
        basis="analytical",
        result_kind=RESULT_KIND,
        cache_version=CACHE_VERSION,
        rule_version=RULE_VERSION,
        payload_model=PnlByBusinessCandidateInsightsPayload,
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        year=year,
        as_of_date=as_of_date,
    )
    candidate_meta = envelope["result_meta"]
    assert isinstance(candidate_meta, dict)
    assert candidate_meta["formal_use_allowed"] is False
    return envelope


def pnl_by_business_insights_envelope(
    *,
    duckdb_path: str,
    governance_dir: str,
    year: int,
    as_of_date: str,
) -> dict[str, object]:
    """Build the approved leadership-analysis envelope for the selected cutoff."""
    envelope = _build_insights_envelope(
        basis="formal",
        result_kind=FORMAL_RESULT_KIND,
        cache_version=FORMAL_CACHE_VERSION,
        rule_version=FORMAL_RULE_VERSION,
        payload_model=PnlByBusinessInsightsPayload,
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        year=year,
        as_of_date=as_of_date,
    )
    formal_meta = envelope["result_meta"]
    assert isinstance(formal_meta, dict)
    assert formal_meta["formal_use_allowed"] is True
    return envelope
