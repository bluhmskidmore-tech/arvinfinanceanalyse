"""Candidate (non-formal) analytical insights for `/pnl-by-business`.

These metrics are registered as `status=candidate` in
`docs/metric_dictionary.md` (`MTR-PNLBIZ-001`~`005`), mirroring the
`concentration-monitor` candidate pattern. They only re-aggregate
already-computed parent rows from `pnl_service.pnl_by_business_ytd_envelope`
and `pnl_service.pnl_by_business_monthly_envelope`; they never re-query
`fact_formal_pnl_fi` / `fact_formal_zqtz_balance_daily` directly and must not
be treated as formal PnL, concentration-limit, or FTP truth.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from backend.app.core_finance.pnl import TWOPLACES
from backend.app.schemas.pnl import PnlByBusinessCandidateInsightsPayload
from backend.app.services import pnl_service
from backend.app.services.formal_result_runtime import build_result_envelope
from backend.app.services.pnl_service import _is_parent_zqtz_business_row

CACHE_VERSION = "cv_pnl_by_business_candidate_insights_v1"
RULE_VERSION = "rv_pnl_by_business_candidate_insights_v1"
RESULT_KIND = "pnl.by_business_candidate_insights"

_ZERO = Decimal("0")
_HUNDRED = Decimal("100")


def _quantize_pct(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES)


def _trace_id(prefix: str) -> str:
    return f"tr_{prefix}_{uuid.uuid4().hex[:12]}"


def _parent_rows(items: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        item
        for item in items
        if _is_parent_zqtz_business_row(
            str(item.get("row_key") or ""),
            str(item.get("business_type") or ""),
            item.get("source_note"),
        )
    ]


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
    items = list(envelope.get("result", {}).get("items", []))
    parent_rows = _parent_rows(items)

    entries: list[tuple[str, str, Decimal]] = []
    total_balance = _ZERO
    for item in parent_rows:
        avg_balance = Decimal(str(item.get("avg_balance") or "0"))
        if avg_balance <= _ZERO:
            continue
        entries.append((str(item["row_key"]), str(item["business_type"]), avg_balance))
        total_balance += avg_balance

    if not entries or total_balance <= _ZERO:
        return {
            "year": year,
            "as_of_date": as_of_date,
            "total_avg_balance": None,
            "hhi_pct": None,
            "top_n": top_n,
            "top_n_share_pct": None,
            "rows": [],
        }

    ranked = sorted(entries, key=lambda entry: entry[2], reverse=True)
    hhi_ratio = _ZERO
    rows: list[dict[str, object]] = []
    for row_key, business_type, avg_balance in ranked:
        share_ratio = avg_balance / total_balance
        hhi_ratio += share_ratio * share_ratio
        rows.append(
            {
                "row_key": row_key,
                "business_type": business_type,
                "avg_balance": avg_balance,
                "share_pct": _quantize_pct(share_ratio * _HUNDRED),
            }
        )
    top_n_balance = sum((entry[2] for entry in ranked[:top_n]), _ZERO)
    return {
        "year": year,
        "as_of_date": as_of_date,
        "total_avg_balance": total_balance,
        "hhi_pct": _quantize_pct(hhi_ratio * _HUNDRED),
        "top_n": top_n,
        "top_n_share_pct": _quantize_pct((top_n_balance / total_balance) * _HUNDRED),
        "rows": rows,
    }


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
    if not window_month_keys:
        return {}
    window = set(window_month_keys)
    as_of_year = int(as_of_date[:4])
    years_needed = sorted({int(key[:4]) for key in window_month_keys})
    buckets: dict[str, dict[str, object]] = {}
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
        for bucket in envelope.get("result", {}).get("months", []):
            month_key = str(bucket.get("month_key") or "")
            if month_key in window:
                buckets[month_key] = bucket
    return buckets


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

    overall_series: list[tuple[str, Decimal | None]] = []
    row_values: dict[str, dict[str, Decimal | None]] = {}
    row_labels: dict[str, str] = {}
    for month_key in window_month_keys:
        bucket = monthly_by_key.get(month_key)
        if bucket is None:
            overall_series.append((month_key, None))
            continue
        summary_ftp = (bucket.get("summary") or {}).get("ftp_net_pnl")
        overall_series.append((month_key, Decimal(str(summary_ftp)) if summary_ftp is not None else None))
        for item in _parent_rows(list(bucket.get("items", []))):
            row_key = str(item["row_key"])
            row_labels[row_key] = str(item["business_type"])
            ftp_value = item.get("ftp_net_pnl")
            row_values.setdefault(row_key, {})[month_key] = (
                Decimal(str(ftp_value)) if ftp_value is not None else None
            )

    overall_stats = _persistence_stats(overall_series)
    rows: list[dict[str, object]] = []
    for row_key in sorted(row_values):
        values = row_values[row_key]
        series = [(month_key, values.get(month_key)) for month_key in window_month_keys]
        stats = _persistence_stats(series)
        rows.append(
            {
                "row_key": row_key,
                "business_type": row_labels[row_key],
                **stats,
            }
        )

    return {
        "as_of_date": as_of_date,
        "lookback_months": lookback_months,
        "window_start_month": window_month_keys[0] if window_month_keys else None,
        "window_end_month": window_month_keys[-1] if window_month_keys else None,
        "rows": rows,
        **overall_stats,
    }


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
    current = compute_business_type_concentration(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        year=year,
        as_of_date=as_of_date,
    )
    baseline_year = year - 1
    baseline_as_of_date = f"{baseline_year}-12-31"
    baseline: dict[str, object] | None
    try:
        baseline = compute_business_type_concentration(
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
            year=baseline_year,
            as_of_date=baseline_as_of_date,
        )
    except ValueError:
        baseline = None

    baseline_rows_by_key = {
        str(row["row_key"]): row for row in (baseline["rows"] if baseline is not None else [])
    }
    rows: list[dict[str, object]] = []
    for row in current["rows"]:
        baseline_row = baseline_rows_by_key.get(str(row["row_key"]))
        baseline_share_pct = baseline_row["share_pct"] if baseline_row is not None else None
        drift_pp = (
            _quantize_pct(Decimal(str(row["share_pct"])) - Decimal(str(baseline_share_pct)))
            if baseline_share_pct is not None
            else None
        )
        rows.append(
            {
                "row_key": row["row_key"],
                "business_type": row["business_type"],
                "current_share_pct": row["share_pct"],
                "baseline_share_pct": baseline_share_pct,
                "drift_pp": drift_pp,
            }
        )

    return {
        "year": year,
        "as_of_date": as_of_date,
        "baseline_year": baseline_year,
        "baseline_as_of_date": baseline_as_of_date if baseline is not None else None,
        "baseline_available": baseline is not None,
        "rows": rows,
    }


def pnl_by_business_candidate_insights_envelope(
    *,
    duckdb_path: str,
    governance_dir: str,
    year: int,
    as_of_date: str,
) -> dict[str, object]:
    """组装候选分析指标信封；``formal_use_allowed`` 恒为 ``False``，不接受任何调用方覆盖。"""
    concentration = compute_business_type_concentration(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        year=year,
        as_of_date=as_of_date,
    )
    negative_ftp_persistence = compute_negative_ftp_persistence(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        as_of_date=as_of_date,
    )
    share_drift = compute_business_type_share_drift(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        year=year,
        as_of_date=as_of_date,
    )
    result_payload = PnlByBusinessCandidateInsightsPayload.model_validate(
        {
            "year": year,
            "as_of_date": as_of_date,
            "concentration": concentration,
            "negative_ftp_persistence": negative_ftp_persistence,
            "share_drift": share_drift,
        }
    ).model_dump(mode="json")

    envelope = build_result_envelope(
        basis="analytical",
        trace_id=_trace_id("pnl_by_business_candidate_insights"),
        result_kind=RESULT_KIND,
        cache_version=CACHE_VERSION,
        source_version=f"sv_pnl_by_business_candidate_insights_{year}_{as_of_date}",
        rule_version=RULE_VERSION,
        quality_flag="ok" if concentration.get("hhi_pct") is not None else "warning",
        result_payload=result_payload,
        filters_applied={"year": year, "as_of_date": as_of_date},
        tables_used=["pnl.by_business_ytd", "pnl.by_business_monthly"],
        requested_report_date=as_of_date,
        resolved_report_date=as_of_date,
        as_of_date=as_of_date,
    )
    assert envelope["result_meta"]["formal_use_allowed"] is False
    return envelope
