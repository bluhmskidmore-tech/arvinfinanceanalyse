from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

from backend.app.core_finance.alert_engine import evaluate_alerts
from backend.app.core_finance.liability_analytics_compat import compute_liability_yield_metrics
from backend.app.core_finance.risk_tensor import PortfolioRiskTensor
from backend.app.governance.formal_compute_lineage import resolve_completed_formal_build_lineage
from backend.app.governance.settings import get_settings
from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
from backend.app.repositories.dashboard_repo import DashboardRepository
from backend.app.repositories.formal_zqtz_balance_metrics_repo import (
    FormalZqtzBalanceMetricsRepository,
)
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from backend.app.repositories.liability_analytics_repo import LiabilityAnalyticsRepository
from backend.app.repositories.news_warehouse_repo import NewsWarehouseRepository
from backend.app.repositories.pnl_repo import PnlRepository
from backend.app.repositories.product_category_pnl_repo import ProductCategoryPnlRepository
from backend.app.repositories.risk_tensor_repo import load_latest_bond_analytics_lineage
from backend.app.schemas.common_numeric import Numeric
from backend.app.schemas.executive_dashboard import (
    AlertItem,
    AlertsPayload,
    AttributionSegment,
    ContributionPayload,
    ContributionRow,
    ExecutiveMetric,
    HomeIncomeTrendPayload,
    HomeIncomeTrendPoint,
    HomeResearchReportItem,
    HomeResearchReportsPayload,
    HomeSnapshotPayload,
    OverviewPayload,
    PnlAttributionPayload,
    ProductCategoryMonthlyHeadlinePayload,
    ProductCategoryYtdHeadlinePayload,
    RiskOverviewPayload,
    RiskSignal,
    SummaryPayload,
    SummaryPoint,
    VerdictPayload,
    VerdictReason,
    VerdictSuggestion,
    VerdictTone,
)
from backend.app.services.bond_analytics_service import (
    BENCHMARK_EXCESS_RECON_GAP,
    BOND_ANALYTICS_FOREIGN_CURRENCY_FALLBACK_WARNING,
    get_benchmark_excess,
    get_benchmark_excess_many,
)
from backend.app.services.formal_result_runtime import build_result_envelope
from backend.app.services.kpi_service import (
    resolve_executive_kpi_metrics,
    resolve_kpi_authority_gate,
)
from backend.app.services.product_category_pnl_service import (
    product_category_pnl_envelope,
    resolve_product_category_ytd_payload_for_home_snapshot,
)
from backend.app.services.risk_tensor_service import (
    risk_tensor_dates_envelope,
    risk_tensor_envelope,
)
from backend.app.services.runtime_cache import InMemoryTTLCache, get_runtime_cache

# 与 tasks 模块常量对齐；只读路径不得 import tasks（broker/actor 注册）。
BOND_ANALYTICS_CACHE_KEY = "bond_analytics:materialize:formal"
PNL_CACHE_KEY = "pnl:phase2:materialize:formal"

PNL_JOB_NAME = "pnl_materialize"

_HOME_INCOME_BENCHMARK_ID = "CDB_INDEX"
_HOME_INCOME_BENCHMARK_PERIOD_TYPE = "MoM"
_HOME_INCOME_CURVE_FALLBACK_PREFIX = "YIELD_CURVE_LATEST_FALLBACK"
_HOME_INCOME_MAX_CURVE_FALLBACK_DAYS = 7
_HOME_SNAPSHOT_OVERVIEW_HISTORY_POINTS = 3
_HOME_CACHE_GOVERNANCE_FILES = ("cache_manifest.jsonl", "cache_build_run.jsonl")
_HOME_CACHE_GOVERNANCE_TAIL_BYTES = 8192
_HOME_CACHE_BUILD_RUN_TAIL_BYTES = 256 * 1024
_MISS_SOURCE = "sv_exec_dashboard_explicit_miss_v1"
_DEFAULT_SOURCE = "sv_exec_dashboard_v1"
_DEFAULT_RULE = "rv_exec_dashboard_v1"
_CACHE_VERSION = "cv_exec_dashboard_v1"
_EXECUTIVE_OVERVIEW_CACHE_TTL_SECONDS: float = 300.0
_ExecutiveOverviewCacheKey = tuple[object, ...]
_EXECUTIVE_OVERVIEW_CACHE: InMemoryTTLCache[
    _ExecutiveOverviewCacheKey,
    dict[str, object],
] = get_runtime_cache(
    "executive.overview",
    ttl_seconds=_EXECUTIVE_OVERVIEW_CACHE_TTL_SECONDS,
    clock=lambda: time.monotonic(),
)
logger = logging.getLogger(__name__)
_logger = logging.getLogger(__name__)
_DEFAULT_RESOLVE_COMPLETED_FORMAL_BUILD_LINEAGE = resolve_completed_formal_build_lineage
_DEFAULT_LOAD_LATEST_BOND_ANALYTICS_LINEAGE = load_latest_bond_analytics_lineage

# Yuan → 亿 conversion factor; a single named constant avoids magic-number scatter.
_YUAN_PER_YI: float = 1e8
_BASIS_POINTS_PER_PERCENT: float = 100.0


def _normalize_report_date(report_date: str | None) -> str | None:
    if report_date is None:
        return None
    return date.fromisoformat(str(report_date).strip()).isoformat()


def _safe_report_year(report_date: str | None) -> int | None:
    if not report_date:
        return None
    try:
        return date.fromisoformat(str(report_date).strip()).year
    except ValueError:
        return None


def _single_effective_report_date(*report_dates: str | None) -> str | None:
    resolved = [str(value or "").strip() for value in report_dates]
    if not resolved or any(not value for value in resolved):
        return None
    first = resolved[0]
    return first if all(value == first for value in resolved) else None


def _envelope(
    result_kind: str,
    result: object,
    *,
    quality_flag: Literal["ok", "warning", "error", "stale"] = "ok",
    vendor_status: Literal["ok", "vendor_stale", "vendor_unavailable"] = "ok",
    fallback_mode: Literal["none", "latest_snapshot"] = "none",
    source_version: str = _DEFAULT_SOURCE,
    rule_version: str = _DEFAULT_RULE,
    filters_applied: dict[str, object] | None = None,
    requested_report_date: str | None = None,
    resolved_report_date: str | None = None,
    as_of_date: str | None = None,
    date_basis: str | None = None,
    fallback_date: str | None = None,
) -> dict[str, object]:
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_{result_kind.replace('.', '_')}",
        result_kind=result_kind,
        cache_version=_CACHE_VERSION,
        source_version=source_version,
        rule_version=rule_version,
        quality_flag=quality_flag,
        vendor_status=vendor_status,
        fallback_mode=fallback_mode,
        filters_applied=filters_applied,
        requested_report_date=requested_report_date,
        resolved_report_date=resolved_report_date,
        as_of_date=as_of_date,
        date_basis=date_basis,
        fallback_date=fallback_date,
        result_payload=result.model_dump(mode="json"),
        source_surface="executive_analytical",
    )


def _fmt_yi_amount(value: float | None, *, signed: bool = False) -> Numeric:
    """Format a yuan-denominated amount into a Numeric in yi display.

    Retains the original signature to minimize churn at call sites (they just
    receive a Numeric instead of str now; ExecutiveMetric etc. accept both
    thanks to W2.1 coercion, but callers building Numerics directly bypass
    the coerce path).
    """
    if value is None:
        return Numeric(
            raw=None,
            unit="yuan",
            display="—" if signed else "0.00 亿",
            precision=2,
            sign_aware=signed,
        )
    v = float(value)
    yi = v / _YUAN_PER_YI
    if signed:
        sign = "+" if yi >= 0 else ""
        display = f"{sign}{yi:,.2f} 亿"
    else:
        display = f"{yi:,.2f} 亿"
    return Numeric(
        raw=v,
        unit="yuan",
        display=display,
        precision=2,
        sign_aware=signed,
    )


def _fmt_signed_segment_yi(yi: float) -> Numeric:
    sign = "+" if yi >= 0 else ""
    return Numeric(
        raw=float(yi) * _YUAN_PER_YI,
        unit="yuan",
        display=f"{sign}{yi:.2f} 亿",
        precision=2,
        sign_aware=True,
    )


def _fmt_signed_percent(value: float | None) -> Numeric:
    if value is None:
        return Numeric(raw=None, unit="pct", display="—", precision=2, sign_aware=True)
    sign = "+" if float(value) >= 0 else ""
    return Numeric(
        raw=float(value) / 100.0,  # raw 是 decimal ratio
        unit="pct",
        display=f"{sign}{float(value):.2f}%",
        precision=2,
        sign_aware=True,
    )


def _normalize_ratio_percent_input(value: float | None) -> float:
    """Treat input as decimal-ratio (e.g. 0.035 = 3.5%).

    Upstream callers (compute_liability_yield_metrics → weighted_rate) all
    return decimal ratios.  The previous heuristic threshold ``abs(v) >= 0.1``
    caused a 100× error for NIM values at or above 10 bp decimal (0.001).
    """
    if value is None:
        return 0.0
    return float(value)


def _fmt_signed_ratio_percent(value: float | None) -> Numeric:
    if value is None:
        return Numeric(raw=None, unit="pct", display="N/A", precision=2, sign_aware=True)
    ratio = _normalize_ratio_percent_input(value)
    sign = "+" if ratio >= 0 else ""
    return Numeric(
        raw=ratio,
        unit="pct",
        display=f"{sign}{ratio * 100.0:.2f}%",
        precision=2,
        sign_aware=True,
    )


def _previous_report_date(dates: list[str], current_report_date: str | None) -> str | None:
    if not current_report_date or not dates:
        return None
    if current_report_date in dates:
        idx = dates.index(current_report_date)
        if idx + 1 < len(dates):
            return dates[idx + 1]
    return None


def _fetch_executive_aum_row(
    balance_repo: object,
    *,
    report_date: str,
    currency_basis: str = "CNY",
) -> dict[str, object] | None:
    fetch_formal_overview = getattr(balance_repo, "fetch_formal_overview", None)
    if callable(fetch_formal_overview):
        try:
            row = fetch_formal_overview(
                report_date=report_date,
                position_scope="asset",
                currency_basis=currency_basis,
            )
        except (RuntimeError, OSError, TypeError, ValueError, AttributeError):
            row = None
        if row is None:
            pass
        else:
            return {
                **row,
                "_metric_scope": "combined_formal_balance",
            }

    row = balance_repo.fetch_zqtz_asset_market_value(
        report_date=report_date,
        currency_basis=currency_basis,
    )
    if row is None:
        return None
    return {
        **row,
        "_metric_scope": "zqtz_only",
    }


def _list_executive_aum_report_dates(
    balance_repo: object,
    *,
    currency_basis: str = "CNY",
) -> list[str]:
    list_formal_overview_report_dates = getattr(balance_repo, "list_formal_overview_report_dates", None)
    if callable(list_formal_overview_report_dates):
        try:
            dates = list(
                list_formal_overview_report_dates(
                    position_scope="asset",
                    currency_basis=currency_basis,
                )
            )
            if dates:
                return dates
        except (RuntimeError, OSError, TypeError, ValueError, AttributeError):
            pass
    list_report_dates = getattr(balance_repo, "list_report_dates", None)
    if not callable(list_report_dates):
        return []
    try:
        return list(list_report_dates(currency_basis=currency_basis))
    except TypeError:
        return list(list_report_dates())


def _lineage_tokens(*values: object) -> list[str]:
    tokens: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        for token in text.split("__"):
            for dirty_part in token.split(","):
                normalized = dirty_part.strip()
                if normalized:
                    tokens.add(normalized)
    return sorted(tokens)


def _lineage_tokens_from_rows(rows: list[dict[str, object]], field_name: str) -> list[str]:
    return _lineage_tokens(*(row.get(field_name) for row in rows))


def _lineage_tokens_from_payload(payload: dict[str, object], field_name: str) -> list[str]:
    return _lineage_tokens(payload.get(field_name))


def _lineage_tokens_from_state(state: dict[str, object], field_name: str) -> list[str]:
    value = state.get(field_name, [])
    if isinstance(value, (list, tuple, set)):
        return _lineage_tokens(*value)
    return _lineage_tokens(value)


def _state_has_lineage_tokens(state: dict[str, object]) -> bool:
    return bool(_lineage_tokens_from_state(state, "source_versions")) and bool(
        _lineage_tokens_from_state(state, "rule_versions")
    )


def _state_missing_required_lineage(state: dict[str, object]) -> bool:
    return bool(state.get("missing_lineage")) or not _state_has_lineage_tokens(state)


def _mapping_missing_required_lineage(row: dict[str, object] | None) -> bool:
    if row is None:
        return False
    return not (
        _lineage_tokens(row.get("source_version"))
        and _lineage_tokens(row.get("rule_version"))
    )


def _join_lineage_tokens(*values: object) -> str:
    return "__".join(_lineage_tokens(*values))


class _HomeCacheBuildRunRows(list[dict[str, object]]):
    def __init__(self, rows: list[dict[str, object]], *, is_partial: bool) -> None:
        super().__init__(rows)
        self.is_partial = is_partial
        self.full_rows: list[dict[str, object]] | None = None
        self._full_rows_lock = threading.Lock()


class _HomeCacheBuildRunFallbackState:
    def __init__(self) -> None:
        self.full_rows_failed = False


def _read_all_cache_build_runs_for_executive_overview(
    governance_dir: str,
) -> _HomeCacheBuildRunRows | None:
    try:
        rows = GovernanceRepository(base_dir=governance_dir).read_all(CACHE_BUILD_RUN_STREAM)
    except (RuntimeError, OSError, TypeError, ValueError):
        return None
    return _HomeCacheBuildRunRows(rows, is_partial=False)


def _read_recent_cache_build_runs_for_executive_overview(
    governance_dir: str,
) -> _HomeCacheBuildRunRows | None:
    target = Path(governance_dir) / f"{CACHE_BUILD_RUN_STREAM}.jsonl"
    try:
        stat = target.stat()
    except OSError:
        return None
    try:
        with target.open("rb") as handle:
            if stat.st_size > _HOME_CACHE_BUILD_RUN_TAIL_BYTES:
                handle.seek(-_HOME_CACHE_BUILD_RUN_TAIL_BYTES, 2)
                handle.readline()
            data = handle.read().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    is_partial = stat.st_size > _HOME_CACHE_BUILD_RUN_TAIL_BYTES
    rows: list[dict[str, object]] = []
    for line in data.splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return _HomeCacheBuildRunRows(rows, is_partial=is_partial)


def _full_cache_build_runs_for_partial_rows(
    rows: list[dict[str, object]],
    *,
    governance_dir: str,
    fallback_state: _HomeCacheBuildRunFallbackState | None = None,
) -> list[dict[str, object]] | None:
    if not isinstance(rows, _HomeCacheBuildRunRows) or not rows.is_partial:
        return None
    if rows.full_rows is not None:
        return rows.full_rows
    if fallback_state is not None and fallback_state.full_rows_failed:
        return None
    with rows._full_rows_lock:
        if rows.full_rows is not None:
            return rows.full_rows
        if fallback_state is not None and fallback_state.full_rows_failed:
            return None
        full_rows = _read_all_cache_build_runs_for_executive_overview(governance_dir)
        if full_rows is None:
            if fallback_state is not None:
                fallback_state.full_rows_failed = True
            return None
        rows.full_rows = full_rows
    return rows.full_rows


def _cache_build_runs_full_fallback_failed(
    fallback_state: _HomeCacheBuildRunFallbackState,
) -> bool:
    return fallback_state.full_rows_failed


def _read_cache_build_runs_for_executive_overview(governance_dir: str) -> list[dict[str, object]] | None:
    if not governance_dir:
        return None
    if (
        resolve_completed_formal_build_lineage is not _DEFAULT_RESOLVE_COMPLETED_FORMAL_BUILD_LINEAGE
        and load_latest_bond_analytics_lineage is not _DEFAULT_LOAD_LATEST_BOND_ANALYTICS_LINEAGE
    ):
        return None
    fingerprint = _governance_file_fingerprint(governance_dir, CACHE_BUILD_RUN_STREAM)
    if fingerprint is None:
        return _read_all_cache_build_runs_for_executive_overview(governance_dir)

    cache_key: _HomeCacheBuildRunsKey = (governance_dir, fingerprint)

    def produce() -> list[dict[str, object]] | None:
        recent_rows = _read_recent_cache_build_runs_for_executive_overview(governance_dir)
        if recent_rows is not None:
            return recent_rows
        return _read_all_cache_build_runs_for_executive_overview(governance_dir)

    return _HOME_CACHE_BUILD_RUNS_CACHE.get_or_set(cache_key, produce)


def _resolve_kpi_authority_gate_for_overview(
    *,
    dsn: str,
    year: int | None,
) -> dict[str, object]:
    cache_key: _HomeKpiGateCacheKey = (dsn, year, id(resolve_kpi_authority_gate))

    def produce() -> dict[str, object]:
        return resolve_kpi_authority_gate(dsn=dsn, year=year)

    return dict(_HOME_KPI_GATE_CACHE.get_or_set(cache_key, produce))


def _resolve_executive_kpi_metrics_for_overview(
    *,
    dsn: str,
    report_date: str | None,
) -> list[dict[str, object]]:
    cache_key: _HomeKpiMetricsCacheKey = (dsn, report_date, id(resolve_executive_kpi_metrics))

    def produce() -> list[dict[str, object]]:
        return resolve_executive_kpi_metrics(dsn=dsn, report_date=report_date)

    return [dict(item) for item in _HOME_KPI_METRICS_CACHE.get_or_set(cache_key, produce)]


def _latest_completed_cache_build_run(
    rows: list[dict[str, object]],
    *,
    cache_key: str,
    job_name: str,
    report_date: str,
    require_source_version: bool = False,
) -> dict[str, object] | None:
    for row in reversed(rows):
        if str(row.get("cache_key") or "").strip() != cache_key:
            continue
        if str(row.get("status") or "").strip() != "completed":
            continue
        if str(row.get("job_name") or "").strip() != job_name:
            continue
        if str(row.get("report_date") or "").strip() != report_date:
            continue
        if require_source_version and not str(row.get("source_version") or "").strip():
            continue
        return row
    return None


def _completed_formal_build_lineage_from_rows(
    rows: list[dict[str, object]] | None,
    *,
    governance_dir: str,
    cache_key: str,
    job_name: str,
    report_date: str,
    fallback_state: _HomeCacheBuildRunFallbackState | None = None,
) -> dict[str, object] | None:
    if rows is None or resolve_completed_formal_build_lineage is not _DEFAULT_RESOLVE_COMPLETED_FORMAL_BUILD_LINEAGE:
        return resolve_completed_formal_build_lineage(
            governance_dir=governance_dir,
            cache_key=cache_key,
            job_name=job_name,
            report_date=report_date,
        )
    latest = _latest_completed_cache_build_run(
        rows,
        cache_key=cache_key,
        job_name=job_name,
        report_date=report_date,
        require_source_version=True,
    )
    if latest is not None:
        return latest
    full_rows = _full_cache_build_runs_for_partial_rows(
        rows,
        governance_dir=governance_dir,
        fallback_state=fallback_state,
    )
    if full_rows is None:
        return None
    return _latest_completed_cache_build_run(
        full_rows,
        cache_key=cache_key,
        job_name=job_name,
        report_date=report_date,
        require_source_version=True,
    )


def _bond_analytics_lineage_from_rows(
    rows: list[dict[str, object]] | None,
    *,
    governance_dir: str,
    report_date: str,
    fallback_state: _HomeCacheBuildRunFallbackState | None = None,
) -> dict[str, str] | None:
    if rows is None or load_latest_bond_analytics_lineage is not _DEFAULT_LOAD_LATEST_BOND_ANALYTICS_LINEAGE:
        return load_latest_bond_analytics_lineage(
            governance_dir=governance_dir,
            report_date=report_date,
        )
    latest = _latest_completed_cache_build_run(
        rows,
        cache_key=BOND_ANALYTICS_CACHE_KEY,
        job_name="bond_analytics_materialize",
        report_date=report_date,
        require_source_version=True,
    )
    if latest is None:
        full_rows = _full_cache_build_runs_for_partial_rows(
            rows,
            governance_dir=governance_dir,
            fallback_state=fallback_state,
        )
        if full_rows is not None:
            latest = _latest_completed_cache_build_run(
                full_rows,
                cache_key=BOND_ANALYTICS_CACHE_KEY,
                job_name="bond_analytics_materialize",
                report_date=report_date,
                require_source_version=True,
            )
    if latest is None:
        return None
    return {
        "source_version": str(latest.get("source_version") or "").strip(),
        "rule_version": str(latest.get("rule_version") or "").strip(),
        "cache_version": str(latest.get("cache_version") or "").strip(),
        "vendor_version": str(latest.get("vendor_version") or "vv_none").strip() or "vv_none",
    }


def _format_percent_change(current: float | None, previous: float | None) -> Numeric:
    if current is None or previous in (None, 0):
        return Numeric(raw=None, unit="pct", display="无环比", precision=2, sign_aware=True)
    change = ((float(current) - float(previous)) / float(previous)) * 100
    sign = "+" if change >= 0 else ""
    return Numeric(
        raw=change / 100.0,
        unit="pct",
        display=f"{sign}{change:.2f}%",
        precision=2,
        sign_aware=True,
    )


def _format_point_change(current: float | None, previous: float | None) -> Numeric:
    if current is None or previous is None:
        return Numeric(raw=None, unit="bp", display="无环比", precision=2, sign_aware=True)
    change = float(current) - float(previous)
    sign = "+" if change >= 0 else ""
    return Numeric(
        raw=change * 100.0,  # bp = percent point * 100
        unit="bp",
        display=f"{sign}{change:.2f}pp",
        precision=2,
        sign_aware=True,
    )


def _format_ratio_point_change(current: float | None, previous: float | None) -> Numeric:
    if current is None or previous is None:
        return Numeric(raw=None, unit="bp", display="N/A", precision=2, sign_aware=True)
    current_ratio = _normalize_ratio_percent_input(current)
    previous_ratio = _normalize_ratio_percent_input(previous)
    change_ratio = current_ratio - previous_ratio
    sign = "+" if change_ratio >= 0 else ""
    return Numeric(
        raw=change_ratio * 10000.0,
        unit="bp",
        display=f"{sign}{change_ratio * 100.0:.2f}pp",
        precision=2,
        sign_aware=True,
    )


def _unavailable_metric(
    *,
    metric_id: str,
    label: str,
    detail: str,
    delta: str = "未接入",
    tone: Literal["positive", "neutral", "warning", "negative"] = "warning",
) -> ExecutiveMetric:
    return ExecutiveMetric(
        id=metric_id,
        label=label,
        value=Numeric(raw=None, unit="yuan", display="—", precision=2, sign_aware=False),
        delta=Numeric(raw=None, unit="pct", display=delta, precision=2, sign_aware=True),
        tone=tone,
        detail=detail,
    )


def _tone_for_signed(yi: float) -> str:
    if yi > 0:
        return "positive"
    if yi < 0:
        return "negative"
    return "neutral"


_CATEGORY_ID_TO_ATTRIBUTION_SEGMENT: dict[str, str] = {
    # Only level-1 category_ids reach _aggregate_attribution_segments (via
    # _level1_monthly_rows L380-384).  Currently only ``bond_investment``
    # defines children at level 1 in product_category_mapping.py; other
    # product categories (interbank, repo, NCD, etc.) are all level 0 and
    # flow entirely into the ``other`` bucket by design.
    "bond_tpl": "trading",
    "bond_ac": "carry",
    "bond_fvoci": "carry",
    "bond_ac_other": "credit",
    "bond_valuation_spread": "roll",
}


def _level1_monthly_rows(
    repo: ProductCategoryPnlRepository,
    report_date: str | None = None,
) -> tuple[str, list[dict[str, object]]] | None:
    target_report_date = _normalize_report_date(report_date)
    if target_report_date is None:
        dates = repo.list_report_dates()
        if not dates:
            return None
        target_report_date = dates[0]
    rows = repo.fetch_rows(target_report_date, "monthly")
    level1 = [
        r
        for r in rows
        if int(r.get("level") or -1) == 1 and not bool(r.get("is_total"))
    ]
    if not level1:
        return None
    return target_report_date, level1


def _aggregate_attribution_segments(rows: list[dict[str, object]]) -> dict[str, float]:
    totals = {"carry": 0.0, "roll": 0.0, "credit": 0.0, "trading": 0.0, "other": 0.0}
    for r in rows:
        cid = str(r.get("category_id") or "")
        raw = r.get("business_net_income")
        try:
            val = float(raw) if raw is not None else 0.0
        except (TypeError, ValueError):
            val = 0.0
        seg = _CATEGORY_ID_TO_ATTRIBUTION_SEGMENT.get(cid, "other")
        totals[seg] += val / _YUAN_PER_YI
    return totals


def _build_pnl_attribution_from_repo(
    repo: ProductCategoryPnlRepository,
    report_date: str | None = None,
) -> tuple[PnlAttributionPayload, list[dict[str, object]]] | None:
    packed = _level1_monthly_rows(repo, report_date)
    if packed is None:
        return None
    _report_date, rows = packed
    seg = _aggregate_attribution_segments(rows)
    total_yi = sum(seg.values())
    order = [
        ("carry", "Carry", seg["carry"]),
        ("roll", "Roll-down", seg["roll"]),
        ("credit", "信用利差", seg["credit"]),
        ("trading", "交易损益", seg["trading"]),
        ("other", "其他", seg["other"]),
    ]
    segments = [
        AttributionSegment(
            id=key,
            label=label,
            amount=_fmt_signed_segment_yi(val),
            tone=_tone_for_signed(val),
        )
        for key, label, val in order
    ]
    return (
        PnlAttributionPayload(
            title="经营贡献拆解",
            total=_fmt_yi_amount(total_yi * 1e8, signed=True),
            segments=segments,
        ),
        rows,
    )


_ZERO_ATTRIBUTION_SEGMENTS = [
    ("carry", "Carry"),
    ("roll", "Roll-down"),
    ("credit", "信用利差"),
    ("trading", "交易损益"),
    ("other", "其他"),
]


def _zero_pnl_attribution_payload(title: str) -> PnlAttributionPayload:
    segments = [
        AttributionSegment(
            id=key,
            label=label,
            amount=_fmt_signed_segment_yi(0.0),
            tone=_tone_for_signed(0.0),
        )
        for key, label in _ZERO_ATTRIBUTION_SEGMENTS
    ]
    return PnlAttributionPayload(
        title=title,
        total=Numeric(raw=0.0, unit="yuan", display="0 亿", precision=0, sign_aware=False),
        segments=segments,
    )


def _pnl_attribution_explicit_miss_payload(report_date: str) -> PnlAttributionPayload:
    return _zero_pnl_attribution_payload(f"经营贡献拆解（{report_date} 无受控产品分类月度数据）")


def _pnl_attribution_unavailable_payload() -> PnlAttributionPayload:
    return _zero_pnl_attribution_payload("经营贡献拆解（当前无受控产品分类月度数据）")


def _contribution_explicit_miss_payload(report_date: str) -> ContributionPayload:
    return ContributionPayload(
        title="团队 / 账户 / 策略贡献",
        rows=[],
    )


def _contribution_unavailable_payload() -> ContributionPayload:
    return ContributionPayload(
        title="团队 / 账户 / 策略贡献",
        rows=[],
    )


def _empty_risk_overview_payload() -> RiskOverviewPayload:
    return RiskOverviewPayload(
        title="风险全景",
        signals=[],
    )


def _empty_alerts_payload() -> AlertsPayload:
    return AlertsPayload(
        title="预警与事件",
        items=[],
    )


def _build_repo_payload_envelope(
    result_kind: str,
    repo_factory,
    build_fn,
    miss_payload_fn,
    unavailable_payload_fn,
    report_date: str | None,
    normalized: str | None,
) -> dict[str, object]:
    """共用模式：构建 ProductCategoryPnlRepository 类端点的 envelope。

    消除 executive_pnl_attribution / executive_contribution 的重复结构。
    """
    repo = None
    try:
        repo = repo_factory()
    except (RuntimeError, OSError, TypeError, ValueError):
        if normalized is not None:
            return _envelope(
                result_kind,
                miss_payload_fn(normalized),
                quality_flag="warning",
                vendor_status="vendor_unavailable",
                source_version=_MISS_SOURCE,
                filters_applied={"report_date": normalized},
            )

    built = None
    src = _DEFAULT_SOURCE
    rule = _DEFAULT_RULE
    if repo is not None:
        try:
            result = build_fn(repo, report_date)
            if result is not None:
                built, rows = result
                src = _join_lineage_tokens(src, *_lineage_tokens_from_rows(rows, "source_version"))
                rule = _join_lineage_tokens(rule, *_lineage_tokens_from_rows(rows, "rule_version"))
        except (RuntimeError, OSError, TypeError, ValueError, KeyError):
            if normalized is not None:
                return _envelope(
                    result_kind,
                    miss_payload_fn(normalized),
                    quality_flag="warning",
                    source_version=_MISS_SOURCE,
                    filters_applied={"report_date": normalized},
                )

    if built is not None:
        return _envelope(
            result_kind,
            built,
            source_version=src,
            rule_version=rule,
            filters_applied={
                "report_date": normalized
                or next(
                    (
                        str(row.get("report_date") or "").strip()
                        for row in rows
                        if str(row.get("report_date") or "").strip()
                    ),
                    None,
                ),
            },
        )

    if normalized is not None:
        return _envelope(
            result_kind,
            miss_payload_fn(normalized),
            quality_flag="warning",
            vendor_status="vendor_unavailable",
            source_version=_MISS_SOURCE,
            filters_applied={"report_date": normalized},
        )

    return _envelope(
        result_kind,
        unavailable_payload_fn(),
        quality_flag="warning",
        vendor_status="vendor_unavailable",
        source_version=_MISS_SOURCE,
        filters_applied={"report_date": None},
    )


def _build_contribution_from_repo(
    repo: ProductCategoryPnlRepository,
    report_date: str | None = None,
) -> tuple[ContributionPayload, list[dict[str, object]]] | None:
    packed = _level1_monthly_rows(repo, report_date)
    if packed is None:
        return None
    report_date, rows = packed
    seg = _aggregate_attribution_segments(rows)
    rates_yi = seg["carry"] + seg["roll"]
    credit_yi = seg["credit"]
    trading_yi = seg["trading"]
    groups: list[tuple[str, str, float]] = [
        ("rates", "利率组", rates_yi),
        ("credit", "信用组", credit_yi),
        ("trading", "交易组", trading_yi),
    ]
    max_abs = max((abs(g[2]) for g in groups), default=0.0)

    def _completion(yi: float) -> int:
        if max_abs <= 0:
            return 0
        return int(min(100, max(0, round(abs(yi) / max_abs * 100))))

    def _status(yi: float) -> str:
        if max_abs <= 0:
            return "待观察"
        if abs(yi) >= max_abs * 0.95:
            return "核心拉动"
        if abs(yi) >= max_abs * 0.35:
            return "稳定贡献"
        return "波动偏大"

    contribution_rows = [
        ContributionRow(
            id=gid,
            name=gname,
            owner="按团队",
            contribution=_fmt_signed_segment_yi(val),
            completion=_completion(val),
            status=_status(val),
        )
        for gid, gname, val in groups
    ]
    return (
        ContributionPayload(
            title="团队 / 账户 / 策略贡献",
            rows=contribution_rows,
        ),
        rows,
    )


def _history_date_slice(
    report_dates: list[str],
    current_report_date: str | None,
    n: int,
) -> list[str] | None:
    if not report_dates:
        return None
    if current_report_date is None:
        return report_dates[:n]
    try:
        idx = report_dates.index(current_report_date)
    except ValueError:
        return None
    return report_dates[idx : idx + n]


def _fetch_aum_history(
    balance_repo: FormalZqtzBalanceMetricsRepository,
    *,
    report_dates: list[str],
    current_report_date: str | None,
    n: int = 20,
) -> list[float] | None:
    """逐日取 _fetch_executive_aum_row(...)['total_market_value_amount']，按时间正序返回最近 n 个。
    单日异常跳过；整体异常返回 None。"""
    try:
        slice_dates = _history_date_slice(report_dates, current_report_date, n)
        if not slice_dates:
            return None
        fetch_history = getattr(balance_repo, "fetch_formal_overview_history", None)
        if callable(fetch_history):
            try:
                rows_by_date = fetch_history(
                    report_dates=slice_dates,
                    position_scope="asset",
                    currency_basis="CNY",
                )
                values = [
                    float(row["total_market_value_amount"])
                    for d in slice_dates
                    if (row := rows_by_date.get(d)) is not None
                    and row.get("total_market_value_amount") is not None
                ]
                if values:
                    values.reverse()
                    return values
            except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
                pass
        values: list[float] = []
        for d in slice_dates:
            try:
                row = _fetch_executive_aum_row(
                    balance_repo,
                    report_date=d,
                    currency_basis="CNY",
                )
                if row is None:
                    continue
                v = row.get("total_market_value_amount")
                if v is not None:
                    values.append(float(v))
            except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
                continue
        if not values:
            return None
        values.reverse()
        return values
    except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
        return None


def _fetch_aum_context(
    balance_repo: FormalZqtzBalanceMetricsRepository,
    *,
    report_dates: list[str],
    current_report_date: str | None,
    n: int = 20,
) -> tuple[dict[str, dict[str, object]], list[float] | None]:
    slice_dates = _history_date_slice(report_dates, current_report_date, n) or []
    fetch_dates = list(slice_dates)
    previous_report_date = _previous_report_date(report_dates, current_report_date)
    for d in (current_report_date, previous_report_date):
        if d is not None and d not in fetch_dates:
            fetch_dates.append(d)
    if not fetch_dates:
        return {}, None

    fetch_history = getattr(balance_repo, "fetch_formal_overview_history", None)
    if callable(fetch_history):
        try:
            rows_by_date = fetch_history(
                report_dates=fetch_dates,
                position_scope="asset",
                currency_basis="CNY",
            )
            if rows_by_date:
                values = [
                    float(row["total_market_value_amount"])
                    for d in slice_dates
                    if (row := rows_by_date.get(d)) is not None
                    and row.get("total_market_value_amount") is not None
                ]
                if values:
                    values.reverse()
                return rows_by_date, values or None
        except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
            pass

    rows_by_date: dict[str, dict[str, object]] = {}
    for d in fetch_dates:
        try:
            row = _fetch_executive_aum_row(
                balance_repo,
                report_date=d,
                currency_basis="CNY",
            )
        except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
            row = None
        if row is not None:
            rows_by_date[d] = row
    values = [
        float(row["total_market_value_amount"])
        for d in slice_dates
        if (row := rows_by_date.get(d)) is not None
        and row.get("total_market_value_amount") is not None
    ]
    if values:
        values.reverse()
    return rows_by_date, values or None


def _fetch_ytd_history(
    pnl_repo: PnlRepository,
    *,
    report_dates: list[str],
    current_report_date: str | None,
    n: int = 20,
) -> list[float] | None:
    """逐日取 FI + nonstd bridge 年度累计损益。"""
    try:
        slice_dates = _history_date_slice(report_dates, current_report_date, n)
        if not slice_dates:
            return None
        sum_formal_history = getattr(pnl_repo, "sum_formal_total_pnl_through_report_dates", None)
        if callable(sum_formal_history):
            try:
                formal_by_date = sum_formal_history(slice_dates)
                sum_nonstd_history = getattr(
                    pnl_repo,
                    "sum_nonstd_bridge_total_pnl_through_report_dates",
                    None,
                )
                nonstd_by_date = (
                    sum_nonstd_history(slice_dates) if callable(sum_nonstd_history) else {}
                )
                values = [
                    float(formal_by_date[d] + nonstd_by_date.get(d, 0))
                    for d in slice_dates
                    if d in formal_by_date
                ]
                if values:
                    values.reverse()
                    return values
            except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
                pass
        values: list[float] = []
        for d in slice_dates:
            try:
                v = _sum_business_ytd_pnl(pnl_repo, d)
                if v is not None:
                    values.append(float(v))
            except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
                continue
        if not values:
            return None
        values.reverse()
        return values
    except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
        return None


def _sum_business_ytd_pnl(pnl_repo: PnlRepository, report_date: str):
    formal = pnl_repo.sum_formal_total_pnl_through_report_date(report_date)
    nonstd_sum = getattr(pnl_repo, "sum_nonstd_bridge_total_pnl_through_report_date", None)
    if not callable(nonstd_sum):
        return formal
    return formal + nonstd_sum(report_date)


def _fetch_ytd_context(
    pnl_repo: PnlRepository,
    *,
    report_dates: list[str],
    current_report_date: str | None,
    n: int = 20,
) -> tuple[dict[str, object], list[float] | None]:
    slice_dates = _history_date_slice(report_dates, current_report_date, n) or []
    fetch_dates = list(slice_dates)
    previous_report_date = _previous_report_date(report_dates, current_report_date)
    for d in (current_report_date, previous_report_date):
        if d is not None and d not in fetch_dates:
            fetch_dates.append(d)
    if not fetch_dates:
        return {}, None

    sum_formal_history = getattr(pnl_repo, "sum_formal_total_pnl_through_report_dates", None)
    if callable(sum_formal_history):
        try:
            formal_by_date = sum_formal_history(fetch_dates)
            sum_nonstd_history = getattr(
                pnl_repo,
                "sum_nonstd_bridge_total_pnl_through_report_dates",
                None,
            )
            nonstd_by_date = (
                sum_nonstd_history(fetch_dates) if callable(sum_nonstd_history) else {}
            )
            values_by_date = {
                d: formal_by_date[d] + nonstd_by_date.get(d, 0)
                for d in fetch_dates
                if d in formal_by_date
            }
            values = [float(values_by_date[d]) for d in slice_dates if d in values_by_date]
            if values:
                values.reverse()
            return values_by_date, values or None
        except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
            pass

    values_by_date: dict[str, object] = {}
    for d in fetch_dates:
        try:
            values_by_date[d] = _sum_business_ytd_pnl(pnl_repo, d)
        except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
            continue
    values = [float(values_by_date[d]) for d in slice_dates if d in values_by_date]
    if values:
        values.reverse()
    return values_by_date, values or None


def _fetch_nim_history(
    liability_repo: LiabilityAnalyticsRepository,
    *,
    report_dates: list[str],
    current_report_date: str | None,
    n: int = 20,
) -> list[float] | None:
    """逐日 fetch_zqtz_rows + fetch_tyw_rows → compute_liability_yield_metrics → kpi.nim。"""
    try:
        slice_dates = _history_date_slice(report_dates, current_report_date, n)
        if not slice_dates:
            return None
        fetch_zqtz_history = getattr(liability_repo, "fetch_zqtz_yield_rows_for_dates", None)
        if not callable(fetch_zqtz_history):
            fetch_zqtz_history = getattr(liability_repo, "fetch_zqtz_rows_for_dates", None)
        fetch_tyw_history = getattr(liability_repo, "fetch_tyw_yield_rows_for_dates", None)
        if not callable(fetch_tyw_history):
            fetch_tyw_history = getattr(liability_repo, "fetch_tyw_rows_for_dates", None)
        if callable(fetch_zqtz_history) and callable(fetch_tyw_history):
            try:
                zqtz_rows_by_date = fetch_zqtz_history(slice_dates)
                tyw_rows_by_date = fetch_tyw_history(slice_dates)
                values: list[float] = []
                for d in slice_dates:
                    payload = compute_liability_yield_metrics(
                        d,
                        zqtz_rows_by_date.get(d, []),
                        tyw_rows_by_date.get(d, []),
                    )
                    kpi = payload.get("kpi") if isinstance(payload, dict) else None
                    v = kpi.get("nim") if isinstance(kpi, dict) else None
                    if v is not None:
                        values.append(float(v))
                if values:
                    values.reverse()
                    return values
            except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
                pass
        values: list[float] = []
        for d in slice_dates:
            try:
                fetch_zqtz_yield = getattr(liability_repo, "fetch_zqtz_yield_rows", None)
                zqtz_rows = (
                    fetch_zqtz_yield(d)
                    if callable(fetch_zqtz_yield)
                    else liability_repo.fetch_zqtz_rows(d)
                )
                tyw_rows = liability_repo.fetch_tyw_rows(d)
                payload = compute_liability_yield_metrics(d, zqtz_rows, tyw_rows)
                kpi = payload.get("kpi") if isinstance(payload, dict) else None
                v = kpi.get("nim") if isinstance(kpi, dict) else None
                if v is not None:
                    values.append(float(v))
            except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
                continue
        if not values:
            return None
        values.reverse()
        return values
    except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
        return None


def _fetch_liability_rows_by_dates(
    liability_repo: LiabilityAnalyticsRepository,
    *,
    report_dates: list[str],
    batch_method_name: str,
    single_method_name: str,
) -> dict[str, list[dict[str, object]]]:
    if not report_dates:
        return {}
    fetch_many = getattr(liability_repo, batch_method_name, None)
    if callable(fetch_many):
        try:
            rows_by_date = fetch_many(report_dates)
            return {
                d: list(rows_by_date.get(d, []))
                for d in report_dates
                if isinstance(rows_by_date, dict)
            }
        except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
            pass

    fetch_one = getattr(liability_repo, single_method_name)
    rows_by_date: dict[str, list[dict[str, object]]] = {}
    for d in report_dates:
        try:
            rows_by_date[d] = list(fetch_one(d))
        except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
            rows_by_date[d] = []
    return rows_by_date


def _fetch_nim_context(
    liability_repo: LiabilityAnalyticsRepository,
    *,
    report_dates: list[str],
    current_report_date: str | None,
    n: int = 20,
) -> _HomeNimContextValue:
    if not isinstance(liability_repo, LiabilityAnalyticsRepository):
        return _fetch_nim_context_uncached(
            liability_repo,
            report_dates=report_dates,
            current_report_date=current_report_date,
            n=n,
        )
    duckdb_path = str(getattr(liability_repo, "path", "") or _duckdb_version_token()[0])
    cache_key: _HomeNimContextCacheKey = (
        tuple(str(d).strip() for d in report_dates if str(d or "").strip()),
        current_report_date,
        n,
        _home_data_version_token(duckdb_path=duckdb_path),
    )
    hit, cached = _HOME_NIM_CONTEXT_CACHE.get(cache_key)
    if hit and cached is not None:
        _log_home_snapshot_detail_perf(
            "home_snapshot_nim",
            "context_cache_lookup",
            time.perf_counter(),
            extra="cache=hit",
            report_date=current_report_date,
            elapsed_ms=0,
        )
        return deepcopy(cached)

    def produce() -> _HomeNimContextValue:
        _log_home_snapshot_detail_perf(
            "home_snapshot_nim",
            "context_cache_lookup",
            time.perf_counter(),
            extra="cache=miss",
            report_date=current_report_date,
            elapsed_ms=0,
        )
        return _fetch_nim_context_uncached(
            liability_repo,
            report_dates=report_dates,
            current_report_date=current_report_date,
            n=n,
        )

    value = _HOME_NIM_CONTEXT_CACHE.get_or_set(cache_key, produce)
    return deepcopy(value)


def _fetch_nim_context_uncached(
    liability_repo: LiabilityAnalyticsRepository,
    *,
    report_dates: list[str],
    current_report_date: str | None,
    n: int = 20,
) -> tuple[
    dict[str, dict[str, object]],
    dict[str, list[dict[str, object]]],
    dict[str, list[dict[str, object]]],
    list[float] | None,
]:
    slice_dates = _history_date_slice(report_dates, current_report_date, n) or []
    fetch_dates = list(slice_dates)
    if current_report_date is not None and current_report_date not in fetch_dates:
        fetch_dates.insert(0, current_report_date)
    previous_report_date = _previous_report_date(report_dates, current_report_date)
    if previous_report_date is not None and previous_report_date not in fetch_dates:
        fetch_dates.append(previous_report_date)
    if not fetch_dates:
        return {}, {}, {}, None

    fetch_yield_kpis = getattr(liability_repo, "fetch_yield_kpis_for_dates", None)
    if callable(fetch_yield_kpis):
        try:
            fetch_t0 = time.perf_counter()
            payloads_by_date = fetch_yield_kpis(fetch_dates)
            if payloads_by_date and all(d in payloads_by_date for d in fetch_dates):
                _log_home_snapshot_detail_perf(
                    "home_snapshot_nim",
                    "fetch_yield_kpis_for_dates",
                    fetch_t0,
                    extra=f"dates={len(fetch_dates)} payloads={len(payloads_by_date)}",
                    report_date=current_report_date,
                )
                history_values: list[float] = []
                for d in slice_dates:
                    payload = payloads_by_date.get(d)
                    kpi = payload.get("kpi") if isinstance(payload, dict) else None
                    v = kpi.get("nim") if isinstance(kpi, dict) else None
                    if v is not None:
                        history_values.append(float(v))
                history = history_values if history_values else None
                if history is not None:
                    history.reverse()
                return payloads_by_date, {}, {}, history
        except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
            pass

    fetch_yield_rows = getattr(liability_repo, "fetch_yield_rows_for_dates", None)
    if callable(fetch_yield_rows):
        try:
            fetch_t0 = time.perf_counter()
            zqtz_rows_by_date, tyw_rows_by_date = fetch_yield_rows(fetch_dates)
            _log_home_snapshot_detail_perf(
                "home_snapshot_nim",
                "fetch_yield_rows_for_dates",
                fetch_t0,
                extra=(
                    f"dates={len(fetch_dates)} "
                    f"zqtz_rows={sum(len(rows) for rows in zqtz_rows_by_date.values())} "
                    f"tyw_rows={sum(len(rows) for rows in tyw_rows_by_date.values())}"
                ),
                report_date=current_report_date,
            )
        except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
            zqtz_rows_by_date, tyw_rows_by_date = {}, {}
    else:
        zqtz_rows_by_date, tyw_rows_by_date = {}, {}

    if not zqtz_rows_by_date and not tyw_rows_by_date:
        zqtz_rows_by_date = _fetch_liability_rows_by_dates(
            liability_repo,
            report_dates=fetch_dates,
            batch_method_name="fetch_zqtz_yield_rows_for_dates",
            single_method_name="fetch_zqtz_rows",
        )
        tyw_rows_by_date = _fetch_liability_rows_by_dates(
            liability_repo,
            report_dates=fetch_dates,
            batch_method_name="fetch_tyw_yield_rows_for_dates",
            single_method_name="fetch_tyw_rows",
        )

    payloads_by_date: dict[str, dict[str, object]] = {}
    compute_t0 = time.perf_counter()
    for d in fetch_dates:
        try:
            payloads_by_date[d] = compute_liability_yield_metrics(
                d,
                zqtz_rows_by_date.get(d, []),
                tyw_rows_by_date.get(d, []),
            )
        except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
            continue
    _log_home_snapshot_detail_perf(
        "home_snapshot_nim",
        "compute_liability_yield_metrics",
        compute_t0,
        extra=f"dates={len(fetch_dates)} payloads={len(payloads_by_date)}",
        report_date=current_report_date,
    )

    history_values: list[float] = []
    for d in slice_dates:
        payload = payloads_by_date.get(d)
        kpi = payload.get("kpi") if isinstance(payload, dict) else None
        v = kpi.get("nim") if isinstance(kpi, dict) else None
        if v is not None:
            history_values.append(float(v))
    history = history_values if history_values else None
    if history is not None:
        history.reverse()

    return payloads_by_date, zqtz_rows_by_date, tyw_rows_by_date, history


def _fetch_dv01_history(
    bond_repo: BondAnalyticsRepository,
    *,
    report_dates: list[str],
    current_report_date: str | None,
    n: int = 20,
) -> list[float] | None:
    """逐日 fetch_risk_overview_snapshot(date)['portfolio_dv01']。"""
    try:
        slice_dates = _history_date_slice(report_dates, current_report_date, n)
        if not slice_dates:
            return None
        fetch_snapshots = getattr(bond_repo, "fetch_risk_overview_snapshots", None)
        if callable(fetch_snapshots):
            try:
                snapshots_by_date = fetch_snapshots(report_dates=slice_dates)
                values = [
                    float(snapshot["portfolio_dv01"])
                    for d in slice_dates
                    if (snapshot := snapshots_by_date.get(d)) is not None
                    and snapshot.get("portfolio_dv01") is not None
                ]
                if values:
                    values.reverse()
                    return values
            except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
                pass
        values: list[float] = []
        for d in slice_dates:
            try:
                snapshot = bond_repo.fetch_risk_overview_snapshot(report_date=d)
                if snapshot is None:
                    continue
                v = snapshot.get("portfolio_dv01")
                if v is not None:
                    values.append(float(v))
            except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
                continue
        if not values:
            return None
        values.reverse()
        return values
    except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
        return None


def _fetch_dv01_context(
    bond_repo: BondAnalyticsRepository,
    *,
    report_dates: list[str],
    current_report_date: str | None,
    n: int = 20,
) -> tuple[dict[str, dict[str, object]], list[float] | None]:
    slice_dates = _history_date_slice(report_dates, current_report_date, n) or []
    fetch_dates = list(slice_dates)
    previous_report_date = _previous_report_date(report_dates, current_report_date)
    for d in (current_report_date, previous_report_date):
        if d is not None and d not in fetch_dates:
            fetch_dates.append(d)
    if not fetch_dates:
        return {}, None

    fetch_snapshots = getattr(bond_repo, "fetch_risk_overview_snapshots", None)
    if callable(fetch_snapshots):
        try:
            snapshots_by_date = fetch_snapshots(report_dates=fetch_dates)
            if snapshots_by_date:
                values = [
                    float(snapshot["portfolio_dv01"])
                    for d in slice_dates
                    if (snapshot := snapshots_by_date.get(d)) is not None
                    and snapshot.get("portfolio_dv01") is not None
                ]
                if values:
                    values.reverse()
                return snapshots_by_date, values or None
        except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
            pass

    snapshots_by_date: dict[str, dict[str, object]] = {}
    for d in fetch_dates:
        try:
            snapshot = bond_repo.fetch_risk_overview_snapshot(report_date=d)
        except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
            snapshot = None
        if snapshot is not None:
            snapshots_by_date[d] = snapshot
    values = [
        float(snapshot["portfolio_dv01"])
        for d in slice_dates
        if (snapshot := snapshots_by_date.get(d)) is not None
        and snapshot.get("portfolio_dv01") is not None
    ]
    if values:
        values.reverse()
    return snapshots_by_date, values or None


def _date_context_cache_token(
    date_context: dict[str, list[str]] | None,
) -> tuple[tuple[str, tuple[str, ...]], ...] | None:
    if date_context is None:
        return None
    return tuple(
        (str(domain), tuple(str(item) for item in dates))
        for domain, dates in sorted(date_context.items())
    )


def _executive_overview_runtime_cache_enabled() -> bool:
    try:
        from backend.app.repositories.bond_analytics_repo import (
            BondAnalyticsRepository as _CanonicalBondAnalyticsRepository,
        )
        from backend.app.repositories.formal_zqtz_balance_metrics_repo import (
            FormalZqtzBalanceMetricsRepository as _CanonicalFormalZqtzBalanceMetricsRepository,
        )
        from backend.app.repositories.liability_analytics_repo import (
            LiabilityAnalyticsRepository as _CanonicalLiabilityAnalyticsRepository,
        )
        from backend.app.repositories.pnl_repo import PnlRepository as _CanonicalPnlRepository

        duckdb_path = str(get_settings().duckdb_path)
        return (
            isinstance(
                FormalZqtzBalanceMetricsRepository(duckdb_path),
                _CanonicalFormalZqtzBalanceMetricsRepository,
            )
            and isinstance(PnlRepository(duckdb_path), _CanonicalPnlRepository)
            and isinstance(
                LiabilityAnalyticsRepository(duckdb_path),
                _CanonicalLiabilityAnalyticsRepository,
            )
            and isinstance(
                BondAnalyticsRepository(duckdb_path),
                _CanonicalBondAnalyticsRepository,
            )
        )
    except Exception:
        return False


def _executive_overview_cache_key(
    *,
    report_date: str | None,
    date_context: dict[str, list[str]] | None,
    history_points: int,
) -> _ExecutiveOverviewCacheKey | None:
    if not _executive_overview_runtime_cache_enabled():
        return None
    version_token = _home_data_version_token()
    if version_token[1] is None or version_token[3] is None:
        return None
    return (
        "executive.overview",
        report_date,
        history_points,
        _date_context_cache_token(date_context),
        *version_token,
        _DEFAULT_RULE,
        _CACHE_VERSION,
    )


def _compute_executive_overview(
    report_date: str | None = None,
    *,
    date_context: dict[str, list[str]] | None = None,
    history_points: int = 20,
) -> dict[str, object]:
    overview_t0 = time.perf_counter()
    settings = get_settings()
    governance_dir = str(getattr(settings, "governance_path", "") or "").strip()
    cache_build_runs = _read_cache_build_runs_for_executive_overview(governance_dir)
    cache_build_run_fallback_state = _HomeCacheBuildRunFallbackState()
    normalized_report_date = _normalize_report_date(report_date)
    current_balance_report_date: str | None = None
    current_pnl_report_date: str | None = None
    liability_report_date: str | None = None
    current_bond_report_date: str | None = None
    aum_raw: float | None = None
    ytd_raw: float | None = None
    nim_raw: float | None = None
    dv01_raw: float | None = None
    duration_raw: float | None = None
    overview_source_versions: list[object] = [_DEFAULT_SOURCE]
    overview_rule_versions: list[object] = [_DEFAULT_RULE]
    aum_delta: Numeric = Numeric(raw=None, unit="pct", display="无环比", precision=2, sign_aware=True)
    ytd_delta: Numeric = Numeric(raw=None, unit="pct", display="无环比", precision=2, sign_aware=True)
    nim_delta: Numeric = Numeric(raw=None, unit="bp", display="无环比", precision=2, sign_aware=True)
    dv01_delta: Numeric = Numeric(raw=None, unit="pct", display="无环比", precision=2, sign_aware=True)
    aum_history: list[float] | None = None
    ytd_history: list[float] | None = None
    nim_history: list[float] | None = None
    dv01_history: list[float] | None = None
    duration_history: list[float] | None = None
    duration_delta: Numeric = Numeric(raw=None, unit="ratio", display="N/A", precision=2, sign_aware=True)
    row: dict[str, object] | None = None

    def load_aum_state() -> dict[str, object]:
        state: dict[str, object] = {
            "current_report_date": None,
            "raw": None,
            "delta": Numeric(raw=None, unit="pct", display="N/A", precision=2, sign_aware=True),
            "history": None,
            "row": None,
            "source_versions": [],
            "rule_versions": [],
            "current_missing_lineage": False,
            "previous_missing_lineage": False,
        }
        try:
            balance_repo = FormalZqtzBalanceMetricsRepository(str(settings.duckdb_path))
            balance_report_dates = (
                _list_executive_aum_report_dates(balance_repo, currency_basis="CNY")
                if date_context is None
                else list(date_context.get("balance", []))
            )
            current_report_date = normalized_report_date or (
                balance_report_dates[0] if balance_report_dates else None
            )
            state["current_report_date"] = current_report_date
            aum_rows_by_date, history = _fetch_aum_context(
                balance_repo,
                report_dates=balance_report_dates,
                current_report_date=current_report_date,
                n=history_points,
            )
            state["history"] = history
            current_row = aum_rows_by_date.get(current_report_date) if current_report_date else None
            state["row"] = current_row
            if current_row is not None:
                raw = float(current_row["total_market_value_amount"])
                state["raw"] = raw
                state["current_missing_lineage"] = _mapping_missing_required_lineage(current_row)
                state["source_versions"] = [current_row.get("source_version")]
                state["rule_versions"] = [current_row.get("rule_version")]
                previous_report_date = _previous_report_date(
                    balance_report_dates,
                    current_report_date,
                )
                if previous_report_date is not None:
                    previous_row = aum_rows_by_date.get(previous_report_date)
                    if previous_row is not None:
                        state["previous_missing_lineage"] = _mapping_missing_required_lineage(
                            previous_row
                        )
                        state["source_versions"] = [
                            *list(state["source_versions"]),
                            previous_row.get("source_version"),
                        ]
                        state["rule_versions"] = [
                            *list(state["rule_versions"]),
                            previous_row.get("rule_version"),
                        ]
                        if state["previous_missing_lineage"]:
                            state["delta"] = Numeric(
                                raw=None,
                                unit="pct",
                                display="无环比",
                                precision=2,
                                sign_aware=True,
                            )
                        else:
                            state["delta"] = _format_percent_change(
                                raw,
                                float(previous_row["total_market_value_amount"]),
                            )
        except (RuntimeError, OSError, TypeError, ValueError):
            state["raw"] = None
        return state

    def load_ytd_state() -> dict[str, object]:
        state: dict[str, object] = {
            "current_report_date": None,
            "raw": None,
            "delta": Numeric(raw=None, unit="pct", display="N/A", precision=2, sign_aware=True),
            "history": None,
            "source_versions": [],
            "rule_versions": [],
        }
        try:
            pnl_repo = PnlRepository(str(settings.duckdb_path))
            pnl_report_dates = (
                list(
                    getattr(
                        pnl_repo,
                        "list_formal_fi_report_dates",
                        getattr(pnl_repo, "list_union_report_dates", lambda: []),
                    )()
                )
                if date_context is None
                else list(date_context.get("pnl", []))
            )
            current_report_date = normalized_report_date or (
                pnl_report_dates[0] if pnl_report_dates else None
            )
            state["current_report_date"] = current_report_date
            ytd_values_by_date, history = _fetch_ytd_context(
                pnl_repo,
                report_dates=pnl_report_dates,
                current_report_date=current_report_date,
                n=history_points,
            )
            state["history"] = history
            source_versions: list[object] = []
            rule_versions: list[object] = []
            raw: float | None = None
            if current_report_date is not None:
                if current_report_date in ytd_values_by_date:
                    raw = float(ytd_values_by_date[current_report_date])
                    state["raw"] = raw
                if governance_dir:
                    current_lineage = _completed_formal_build_lineage_from_rows(
                        cache_build_runs,
                        governance_dir=governance_dir,
                        cache_key=PNL_CACHE_KEY,
                        job_name=PNL_JOB_NAME,
                        report_date=current_report_date,
                        fallback_state=cache_build_run_fallback_state,
                    )
                    if current_lineage is not None:
                        source_versions.append(current_lineage.get("source_version"))
                        rule_versions.append(current_lineage.get("rule_version"))
                    elif raw is not None:
                        state["missing_lineage"] = True
            previous_report_date = _previous_report_date(
                pnl_report_dates,
                current_report_date,
            )
            if previous_report_date is not None:
                if governance_dir:
                    previous_lineage = _completed_formal_build_lineage_from_rows(
                        cache_build_runs,
                        governance_dir=governance_dir,
                        cache_key=PNL_CACHE_KEY,
                        job_name=PNL_JOB_NAME,
                        report_date=previous_report_date,
                        fallback_state=cache_build_run_fallback_state,
                    )
                    if previous_lineage is not None:
                        source_versions.append(previous_lineage.get("source_version"))
                        rule_versions.append(previous_lineage.get("rule_version"))
                    elif previous_report_date in ytd_values_by_date:
                        state["missing_lineage"] = True
                if previous_report_date in ytd_values_by_date:
                    state["delta"] = _format_percent_change(
                        raw,
                        float(ytd_values_by_date[previous_report_date]),
                    )
            state["source_versions"] = source_versions
            state["rule_versions"] = rule_versions
        except (RuntimeError, OSError, TypeError, ValueError):
            state["raw"] = None
        return state

    def load_nim_state() -> dict[str, object]:
        state: dict[str, object] = {
            "current_report_date": None,
            "raw": None,
            "delta": Numeric(raw=None, unit="bp", display="N/A", precision=2, sign_aware=True),
            "history": None,
            "source_versions": [],
            "rule_versions": [],
        }
        try:
            liability_repo = LiabilityAnalyticsRepository(str(settings.duckdb_path))
            liability_report_dates = (
                list(getattr(liability_repo, "list_report_dates", lambda: [])())
                if date_context is None
                else list(date_context.get("liability", []))
            )
            current_report_date = normalized_report_date or (
                liability_report_dates[0]
                if liability_report_dates
                else liability_repo.resolve_latest_report_date()
            )
            state["current_report_date"] = current_report_date
            if current_report_date:
                nim_payloads_by_date, zqtz_rows_by_date, tyw_rows_by_date, history = _fetch_nim_context(
                    liability_repo,
                    report_dates=liability_report_dates,
                    current_report_date=current_report_date,
                    n=history_points,
                )
                state["history"] = history
                zqtz_rows = zqtz_rows_by_date.get(current_report_date, [])
                tyw_rows = tyw_rows_by_date.get(current_report_date, [])
                payload = nim_payloads_by_date.get(current_report_date, {})
                source_versions: list[object] = [
                    *_lineage_tokens_from_payload(payload, "source_version"),
                    *_lineage_tokens_from_rows(zqtz_rows, "source_version"),
                    *_lineage_tokens_from_rows(tyw_rows, "source_version"),
                ]
                rule_versions: list[object] = [
                    *_lineage_tokens_from_payload(payload, "rule_version"),
                    *_lineage_tokens_from_rows(zqtz_rows, "rule_version"),
                    *_lineage_tokens_from_rows(tyw_rows, "rule_version"),
                ]
                nim_value = payload.get("kpi", {}).get("nim")
                if nim_value is not None:
                    raw = float(nim_value)
                    state["raw"] = raw
                    previous_report_date = _previous_report_date(
                        liability_report_dates,
                        current_report_date,
                    )
                    if previous_report_date is not None:
                        previous_payload = nim_payloads_by_date.get(previous_report_date, {})
                        previous_zqtz_rows = zqtz_rows_by_date.get(previous_report_date, [])
                        previous_tyw_rows = tyw_rows_by_date.get(previous_report_date, [])
                        source_versions.extend(_lineage_tokens_from_payload(previous_payload, "source_version"))
                        source_versions.extend(_lineage_tokens_from_rows(previous_zqtz_rows, "source_version"))
                        source_versions.extend(_lineage_tokens_from_rows(previous_tyw_rows, "source_version"))
                        rule_versions.extend(_lineage_tokens_from_payload(previous_payload, "rule_version"))
                        rule_versions.extend(_lineage_tokens_from_rows(previous_zqtz_rows, "rule_version"))
                        rule_versions.extend(_lineage_tokens_from_rows(previous_tyw_rows, "rule_version"))
                        state["delta"] = _format_ratio_point_change(
                            raw,
                            previous_payload.get("kpi", {}).get("nim"),
                        )
                state["source_versions"] = source_versions
                state["rule_versions"] = rule_versions
        except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
            state["raw"] = None
        return state

    def load_dv01_state() -> dict[str, object]:
        state: dict[str, object] = {
            "current_report_date": None,
            "raw": None,
            "delta": Numeric(raw=None, unit="pct", display="N/A", precision=2, sign_aware=True),
            "history": None,
            "duration_raw": None,
            "duration_delta": Numeric(raw=None, unit="ratio", display="N/A", precision=2, sign_aware=True),
            "duration_history": None,
            "duration_source": None,
            "source_versions": [],
            "rule_versions": [],
            "missing_lineage": False,
        }
        try:
            bond_repo = BondAnalyticsRepository(str(settings.duckdb_path))
            bond_report_dates = (
                list(getattr(bond_repo, "list_report_dates", lambda: [])())
                if date_context is None
                else list(date_context.get("bond", []))
            )
            current_report_date = normalized_report_date or (
                bond_report_dates[0] if bond_report_dates else None
            )
            state["current_report_date"] = current_report_date
            snapshots_by_date, history = _fetch_dv01_context(
                bond_repo,
                report_dates=bond_report_dates,
                current_report_date=current_report_date,
                n=history_points,
            )
            state["history"] = history
            previous_report_date = _previous_report_date(
                bond_report_dates,
                current_report_date,
            )
            fetch_headline = getattr(bond_repo, "fetch_dashboard_headline_kpis", None)
            if callable(fetch_headline) and current_report_date is not None:
                try:
                    headline_payload = fetch_headline(
                        current_report_date,
                        prev_report_date=previous_report_date,
                    )
                    current_headline = (
                        headline_payload.get("current")
                        if isinstance(headline_payload, dict)
                        else None
                    )
                    previous_headline = (
                        headline_payload.get("previous")
                        if isinstance(headline_payload, dict)
                        else None
                    )
                    if (
                        isinstance(current_headline, dict)
                        and current_headline.get("weighted_duration") is not None
                    ):
                        duration = float(current_headline["weighted_duration"])
                        state["duration_raw"] = duration
                        state["duration_source"] = "headline"
                        if (
                            isinstance(previous_headline, dict)
                            and previous_headline.get("weighted_duration") is not None
                        ):
                            previous_duration = float(previous_headline["weighted_duration"])
                            duration_change = duration - previous_duration
                            duration_sign = "+" if duration_change >= 0 else ""
                            state["duration_delta"] = Numeric(
                                raw=duration_change,
                                unit="ratio",
                                display=f"{duration_sign}{duration_change:.2f}",
                                precision=2,
                                sign_aware=True,
                            )
                            state["duration_history"] = [previous_duration, duration]
                except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
                    pass
            snapshot = snapshots_by_date.get(current_report_date) if current_report_date else None
            source_versions: list[object] = []
            rule_versions: list[object] = []
            if snapshot is not None and snapshot.get("portfolio_dv01") is not None:
                raw = float(snapshot["portfolio_dv01"])
                state["raw"] = raw
                if (
                    state.get("duration_raw") is None
                    and snapshot.get("portfolio_modified_duration") is not None
                ):
                    state["duration_raw"] = float(snapshot["portfolio_modified_duration"])
                    state["duration_source"] = "risk_snapshot"
                if governance_dir:
                    current_lineage = _bond_analytics_lineage_from_rows(
                        cache_build_runs,
                        governance_dir=governance_dir,
                        report_date=current_report_date,
                        fallback_state=cache_build_run_fallback_state,
                    )
                    if current_lineage is not None:
                        source_versions.append(current_lineage.get("source_version"))
                        rule_versions.append(current_lineage.get("rule_version"))
                    else:
                        state["missing_lineage"] = True
                if previous_report_date is not None:
                    previous_snapshot = snapshots_by_date.get(previous_report_date)
                    if previous_snapshot is not None and previous_snapshot.get("portfolio_dv01") is not None:
                        if governance_dir:
                            previous_lineage = _bond_analytics_lineage_from_rows(
                                cache_build_runs,
                                governance_dir=governance_dir,
                                report_date=previous_report_date,
                                fallback_state=cache_build_run_fallback_state,
                            )
                            if previous_lineage is not None:
                                source_versions.append(previous_lineage.get("source_version"))
                                rule_versions.append(previous_lineage.get("rule_version"))
                            else:
                                state["missing_lineage"] = True
                        state["delta"] = _format_percent_change(
                            raw,
                            float(previous_snapshot["portfolio_dv01"]),
                        )
                        if (
                            state.get("duration_source") != "headline"
                            and state.get("duration_raw") is not None
                            and previous_snapshot.get("portfolio_modified_duration") is not None
                        ):
                            duration_change = float(state["duration_raw"]) - float(
                                previous_snapshot["portfolio_modified_duration"]
                            )
                            duration_sign = "+" if duration_change >= 0 else ""
                            state["duration_delta"] = Numeric(
                                raw=duration_change,
                                unit="ratio",
                                display=f"{duration_sign}{duration_change:.2f}",
                                precision=2,
                                sign_aware=True,
                            )
                            state["duration_history"] = [
                                float(previous_snapshot["portfolio_modified_duration"]),
                                float(state["duration_raw"]),
                            ]
            state["source_versions"] = source_versions
            state["rule_versions"] = rule_versions
        except (RuntimeError, OSError, TypeError, ValueError, KeyError, AttributeError):
            state["raw"] = None
        return state

    domain_loaders = {
        "aum": load_aum_state,
        "ytd": load_ytd_state,
        "nim": load_nim_state,
        "dv01": load_dv01_state,
    }

    def timed_domain_load(name: str, loader) -> tuple[dict[str, object], int]:
        domain_t0 = time.perf_counter()
        state = loader()
        return state, int((time.perf_counter() - domain_t0) * 1000)

    if date_context is None:
        domain_states = {}
        domain_timings_ms = {}
        for name, loader in domain_loaders.items():
            state, elapsed_ms = timed_domain_load(name, loader)
            domain_states[name] = state
            domain_timings_ms[name] = elapsed_ms
    else:
        with ThreadPoolExecutor(max_workers=len(domain_loaders)) as executor:
            futures = {
                name: executor.submit(timed_domain_load, name, loader)
                for name, loader in domain_loaders.items()
            }
            domain_states = {}
            domain_timings_ms = {}
            for name, future in futures.items():
                state, elapsed_ms = future.result()
                domain_states[name] = state
                domain_timings_ms[name] = elapsed_ms
    for name in domain_loaders:
        _log_executive_overview_perf_step(
            f"domain_{name}",
            overview_t0,
            report_date=normalized_report_date,
            elapsed_ms=domain_timings_ms.get(name),
        )
    _log_executive_overview_perf_step(
        "domain_total",
        overview_t0,
        report_date=normalized_report_date,
    )

    aum_state = domain_states["aum"]
    current_balance_report_date = aum_state.get("current_report_date")  # type: ignore[assignment]
    aum_raw = aum_state.get("raw")  # type: ignore[assignment]
    aum_delta = aum_state.get("delta")  # type: ignore[assignment]
    aum_history = aum_state.get("history")  # type: ignore[assignment]
    row = aum_state.get("row") if isinstance(aum_state.get("row"), dict) else None
    overview_source_versions.extend(list(aum_state.get("source_versions", [])))  # type: ignore[arg-type]
    overview_rule_versions.extend(list(aum_state.get("rule_versions", [])))  # type: ignore[arg-type]

    ytd_state = domain_states["ytd"]
    current_pnl_report_date = ytd_state.get("current_report_date")  # type: ignore[assignment]
    ytd_raw = ytd_state.get("raw")  # type: ignore[assignment]
    ytd_delta = ytd_state.get("delta")  # type: ignore[assignment]
    ytd_history = ytd_state.get("history")  # type: ignore[assignment]
    overview_source_versions.extend(list(ytd_state.get("source_versions", [])))  # type: ignore[arg-type]
    overview_rule_versions.extend(list(ytd_state.get("rule_versions", [])))  # type: ignore[arg-type]

    nim_state = domain_states["nim"]
    liability_report_date = nim_state.get("current_report_date")  # type: ignore[assignment]
    nim_raw = nim_state.get("raw")  # type: ignore[assignment]
    nim_delta = nim_state.get("delta")  # type: ignore[assignment]
    nim_history = nim_state.get("history")  # type: ignore[assignment]
    overview_source_versions.extend(list(nim_state.get("source_versions", [])))  # type: ignore[arg-type]
    overview_rule_versions.extend(list(nim_state.get("rule_versions", [])))  # type: ignore[arg-type]

    dv01_state = domain_states["dv01"]
    current_bond_report_date = dv01_state.get("current_report_date")  # type: ignore[assignment]
    dv01_raw = dv01_state.get("raw")  # type: ignore[assignment]
    dv01_delta = dv01_state.get("delta")  # type: ignore[assignment]
    dv01_history = dv01_state.get("history")  # type: ignore[assignment]
    duration_raw = dv01_state.get("duration_raw")  # type: ignore[assignment]
    duration_delta = dv01_state.get("duration_delta")  # type: ignore[assignment]
    duration_history = dv01_state.get("duration_history")  # type: ignore[assignment]
    overview_source_versions.extend(list(dv01_state.get("source_versions", [])))  # type: ignore[arg-type]
    overview_rule_versions.extend(list(dv01_state.get("rule_versions", [])))  # type: ignore[arg-type]

    metrics: list[ExecutiveMetric] = []
    if aum_raw is not None:
        aum_scope = str(row.get("_metric_scope") or "") if row is not None else ""
        aum_label = "总资产规模" if aum_scope == "combined_formal_balance" else "债券资产规模（zqtz）"
        aum_caliber_label = "本币资产口径" if aum_scope == "combined_formal_balance" else "债券资产口径"
        aum_detail = (
            (
                f"来自 governed formal balance overview，在 {normalized_report_date} 的 CNY 资产口径市值合计。"
                if normalized_report_date is not None
                else f"来自 governed formal balance overview，在 {current_balance_report_date} 的 CNY 资产口径市值合计。"
            )
            if aum_scope == "combined_formal_balance"
            else (
                f"来自 fact_formal_zqtz_balance_daily，在 {normalized_report_date} 的 CNY 资产口径市值合计。"
                if normalized_report_date is not None
                else f"来自 fact_formal_zqtz_balance_daily，在 {current_balance_report_date} 的 CNY 资产口径市值合计。"
            )
        )
        metrics.append(
            ExecutiveMetric(
                id="aum",
                label=aum_label,
                caliber_label=aum_caliber_label,
                value=_fmt_yi_amount(aum_raw, signed=False),
                delta=aum_delta,
                tone="positive",
                detail=aum_detail,
                history=aum_history,
            )
        )
    if ytd_raw is not None:
        metrics.append(
            ExecutiveMetric(
                id="yield",
                label="年度损益（不扣FTP）",
                caliber_label="FI + 非标桥接",
                value=_fmt_yi_amount(ytd_raw, signed=True),
                delta=ytd_delta,
                tone="positive",
                detail=(
                    "来自 fact_formal_pnl_fi + fact_nonstd_pnl_bridge "
                    f"截至 {normalized_report_date} 的年度累计 total_pnl，不扣减 FTP。"
                    if normalized_report_date is not None
                    else (
                        "来自 fact_formal_pnl_fi + fact_nonstd_pnl_bridge "
                        f"截至 {current_pnl_report_date} 的年度累计 total_pnl，不扣减 FTP。"
                    )
                ),
                history=ytd_history,
            )
        )
    if nim_raw is not None:
        metrics.append(
            ExecutiveMetric(
                id="nim",
                label="净息差",
                value=_fmt_signed_ratio_percent(nim_raw),
                delta=nim_delta,
                tone="positive" if nim_raw >= 0 else "negative",
                detail=(
                    f"来自受治理负债分析收益指标，在 {normalized_report_date} 的 NIM 读面。"
                    if normalized_report_date is not None
                    else f"来自受治理负债分析收益指标，在 {liability_report_date} 的 NIM 读面。"
                ),
                history=nim_history,
            )
        )
    if dv01_raw is not None:
        metrics.append(
            ExecutiveMetric(
                id="dv01",
                label="组合DV01",
                value=Numeric(
                    raw=dv01_raw,
                    unit="dv01",
                    display=f"{dv01_raw:,.0f}",
                    precision=0,
                    sign_aware=False,
                ),
                delta=dv01_delta,
                tone="warning",
                detail=(
                    f"来自 bond analytics 风险快照，在 {normalized_report_date} 的全量组合 DV01；含 AC/OCI/TPL，拆分见风险全景。"
                    if normalized_report_date is not None
                    else f"来自 bond analytics 风险快照，在 {current_bond_report_date} 的全量组合 DV01；含 AC/OCI/TPL，拆分见风险全景。"
                ),
                history=dv01_history,
            )
        )
    if duration_raw is not None:
        metrics.append(
            ExecutiveMetric(
                id="duration",
                label="加权久期",
                caliber_label="利率风险资产口径",
                value=Numeric(
                    raw=duration_raw,
                    unit="ratio",
                    display=f"{duration_raw:,.2f}",
                    precision=2,
                    sign_aware=False,
                ),
                delta=duration_delta,
                tone="warning",
                detail=(
                    f"来自 bond dashboard headline，在 {normalized_report_date} 的 weighted_duration；"
                    "按 rate/credit 债券投资范围内的市值加权修正久期。"
                    if normalized_report_date is not None
                    else (
                        f"来自 bond dashboard headline，在 {current_bond_report_date} 的 weighted_duration；"
                        "按 rate/credit 债券投资范围内的市值加权修正久期。"
                    )
                ),
                history=duration_history,
            )
        )
    kpi_dsn = str(
        getattr(settings, "governance_sql_dsn", "")
        or getattr(settings, "postgres_dsn", "")
    )
    kpi_gate = _resolve_kpi_authority_gate_for_overview(
        dsn=kpi_dsn,
        year=(
            _safe_report_year(current_pnl_report_date)
            if current_pnl_report_date
            else (
                _safe_report_year(normalized_report_date)
                if normalized_report_date is not None
                else None
            )
        ),
    )
    if kpi_gate["status"] == "available":
        try:
            metrics.extend(
                ExecutiveMetric.model_validate(item)
                for item in _resolve_executive_kpi_metrics_for_overview(
                    dsn=kpi_dsn,
                    report_date=current_pnl_report_date or normalized_report_date,
                )
            )
        except (RuntimeError, ValueError, TypeError, KeyError):
            kpi_gate = {
                "status": "blocked",
                "reason": "metrics-resolution-error",
                "owner_count": 0,
                "year": kpi_gate.get("year"),
            }

    payload = OverviewPayload(title="经营总览", metrics=metrics)
    has_missing_governed_metrics = (
        aum_raw is None
        or ytd_raw is None
        or nim_raw is None
        or dv01_raw is None
    )
    lineage_fallback_failed = _cache_build_runs_full_fallback_failed(cache_build_run_fallback_state)
    aum_current_missing_lineage = bool(aum_state.get("current_missing_lineage"))
    has_missing_lineage = (
        (aum_raw is not None and aum_current_missing_lineage)
        or (ytd_raw is not None and _state_missing_required_lineage(ytd_state))
        or (dv01_raw is not None and _state_missing_required_lineage(dv01_state))
    )
    has_overview_warning = has_missing_governed_metrics or has_missing_lineage
    effective_balance_report_date = current_balance_report_date if aum_raw is not None else None
    effective_pnl_report_date = current_pnl_report_date if ytd_raw is not None else None
    effective_liability_report_date = liability_report_date if nim_raw is not None else None
    effective_risk_report_date = current_bond_report_date if dv01_raw is not None else None
    overview_report_date = _single_effective_report_date(
        effective_balance_report_date,
        effective_pnl_report_date,
        effective_liability_report_date,
        effective_risk_report_date,
    )
    return _envelope(
        "executive.overview",
        payload,
        quality_flag="warning" if has_overview_warning else "ok",
        vendor_status="vendor_unavailable" if has_overview_warning else "ok",
        source_version=(
            _MISS_SOURCE
            if has_overview_warning
            else _join_lineage_tokens(*overview_source_versions)
        ),
        rule_version=(
            _DEFAULT_RULE
            if has_overview_warning
            else _join_lineage_tokens(*overview_rule_versions)
        ),
        filters_applied={
            "requested_report_date": normalized_report_date,
            "effective_report_dates": {
                "balance": effective_balance_report_date,
                "pnl": effective_pnl_report_date,
                "liability": effective_liability_report_date,
                "risk": effective_risk_report_date,
            },
            "kpi_gate": kpi_gate,
            "lineage_fallback_failed": lineage_fallback_failed,
        },
        requested_report_date=normalized_report_date,
        resolved_report_date=overview_report_date,
        as_of_date=overview_report_date,
        date_basis="multi_domain_snapshot",
        fallback_date=None,
    )


def executive_overview(
    report_date: str | None = None,
    *,
    date_context: dict[str, list[str]] | None = None,
    history_points: int = 20,
) -> dict[str, object]:
    normalized_report_date = _normalize_report_date(report_date)
    cache_key = _executive_overview_cache_key(
        report_date=normalized_report_date,
        date_context=date_context,
        history_points=history_points,
    )
    if cache_key is None:
        return _compute_executive_overview(
            report_date=report_date,
            date_context=date_context,
            history_points=history_points,
        )
    envelope = _EXECUTIVE_OVERVIEW_CACHE.get_or_set(
        cache_key,
        lambda: _compute_executive_overview(
            report_date=report_date,
            date_context=date_context,
            history_points=history_points,
        ),
    )
    return deepcopy(envelope)


def _executive_overview_result_meta_for_summary(
    report_date: str | None,
) -> dict[str, object] | None:
    normalized_report_date = _normalize_report_date(report_date)
    cache_key = _executive_overview_cache_key(
        report_date=normalized_report_date,
        date_context=None,
        history_points=20,
    )
    if cache_key is not None:
        hit, cached = _EXECUTIVE_OVERVIEW_CACHE.get(cache_key)
        if hit and isinstance(cached, dict):
            result_meta = cached.get("result_meta")
            if isinstance(result_meta, dict):
                return deepcopy(result_meta)
    overview_payload = executive_overview(report_date=report_date)
    if isinstance(overview_payload, dict):
        result_meta = overview_payload.get("result_meta")
        if isinstance(result_meta, dict):
            return result_meta
    return None


def executive_summary(report_date: str | None = None) -> dict[str, object]:
    payload = SummaryPayload(
        title="本周管理摘要",
        report_date=report_date,
        narrative=(
            "本周组合收益延续修复，收益主要来自久期与票息贡献。"
            "风险端仍需关注信用集中度与流动性预留，当前页面仅展示受控摘要，不生成正式分析口径。"
        ),
        points=[
            SummaryPoint(
                id="income",
                label="收益",
                tone="positive",
                text="利率下行仍是收益主驱动，票息表现稳定。",
            ),
            SummaryPoint(
                id="risk",
                label="风险",
                tone="warning",
                text="信用集中度上行，需持续关注暴露边界。",
            ),
            SummaryPoint(
                id="action",
                label="建议",
                tone="neutral",
                text="保持流动性缓冲，避免在高波动窗口放大仓位。",
            ),
        ],
    )
    overview_meta = _executive_overview_result_meta_for_summary(report_date)
    source_version = _MISS_SOURCE
    rule_version = _DEFAULT_RULE
    if isinstance(overview_meta, dict) and overview_meta.get("vendor_status") == "ok":
        source_version = str(overview_meta.get("source_version") or "").strip() or source_version
        rule_version = str(overview_meta.get("rule_version") or "").strip() or rule_version
    return _envelope(
        "executive.summary",
        payload,
        source_version=source_version,
        rule_version=rule_version,
    )


def executive_pnl_attribution(report_date: str | None = None) -> dict[str, object]:
    settings = get_settings()
    normalized = _normalize_report_date(report_date)
    return _build_repo_payload_envelope(
        result_kind="executive.pnl-attribution",
        repo_factory=lambda: ProductCategoryPnlRepository(str(settings.duckdb_path)),
        build_fn=_build_pnl_attribution_from_repo,
        miss_payload_fn=_pnl_attribution_explicit_miss_payload,
        unavailable_payload_fn=_pnl_attribution_unavailable_payload,
        report_date=report_date,
        normalized=normalized,
    )


def executive_risk_overview(report_date: str | None = None) -> dict[str, object]:
    settings = get_settings()
    governance_dir = str(getattr(settings, "governance_path", "") or "").strip()
    normalized_report_date = _normalize_report_date(report_date)
    try:
        repo = BondAnalyticsRepository(str(settings.duckdb_path))
        if normalized_report_date is not None:
            available_bond_dates = repo.list_report_dates()
            if available_bond_dates and normalized_report_date not in available_bond_dates:
                return _envelope(
                    "executive.risk-overview",
                    _empty_risk_overview_payload(),
                    quality_flag="warning",
                    vendor_status="vendor_unavailable",
                    source_version=_MISS_SOURCE,
                )
        snapshot = (
            repo.fetch_risk_overview_snapshot(report_date=normalized_report_date)
            if normalized_report_date is not None
            else repo.fetch_latest_risk_overview_snapshot()
        )
        if snapshot is not None and snapshot["report_date"] is not None:
            wdur = snapshot["portfolio_modified_duration"]
            sum_dv01 = snapshot["portfolio_dv01"]
            cred_pct = snapshot["credit_market_value_ratio_pct"]
            w_ytm = snapshot["weighted_years_to_maturity"]
            if wdur is not None and sum_dv01 is not None:
                wdur_f = float(wdur)
                dv01_f = float(sum_dv01)
                cred_f = float(cred_pct) if cred_pct is not None else 0.0
                ytm_f = float(w_ytm) if w_ytm is not None else 0.0
                asof_date = str(snapshot["report_date"])
                asof_label = (
                    f"指定日期 {asof_date}"
                    if normalized_report_date is not None
                    else f"最新日期 {asof_date}"
                )
                payload = RiskOverviewPayload(
                    title="风险全景",
                    signals=[
                        RiskSignal(
                            id="duration",
                            label="久期风险",
                            value=Numeric(raw=wdur_f, unit="ratio", display=f"{wdur_f:.2f} 年", precision=2, sign_aware=False),
                            status="stable",
                            detail=f"{asof_label}，组合市值加权修正久期（modified_duration）。",
                        ),
                        RiskSignal(
                            id="leverage",
                            label="杠杆风险",
                            value=Numeric(raw=dv01_f, unit="dv01", display=f"{dv01_f:,.0f}", precision=0, sign_aware=False),
                            status="watch",
                            detail=f"{asof_label}，DV01 合计（元口径聚合）。",
                        ),
                        RiskSignal(
                            id="credit",
                            label="信用集中度",
                            # cred_f is percent-points (repo SQL multiplies the share by 100);
                            # the pct contract stores raw as a decimal ratio.
                            value=Numeric(raw=cred_f / 100.0, unit="pct", display=f"{cred_f:.1f}%", precision=1, sign_aware=False),
                            status="warning",
                            detail=f"{asof_label}，信用类债券市值占组合市值比重。",
                        ),
                        RiskSignal(
                            id="liquidity",
                            label="流动性风险",
                            value=Numeric(raw=ytm_f, unit="ratio", display=f"{ytm_f:.2f} 年", precision=2, sign_aware=False),
                            status="stable",
                            detail=f"{asof_label}，市值加权平均剩余期限（years_to_maturity）。",
                        ),
                    ],
                )
                for split_field, split_id, split_label in (
                    ("ac_dv01", "dv01_ac", "AC DV01"),
                    ("oci_dv01", "dv01_oci", "OCI DV01"),
                    ("tpl_dv01", "dv01_tpl", "TPL DV01"),
                    ("other_dv01", "dv01_other", "未分类 DV01"),
                ):
                    split_value = snapshot.get(split_field)
                    if split_value is None:
                        continue
                    split_raw = float(split_value)
                    if split_field == "other_dv01" and split_raw == 0:
                        continue
                    split_status = "warning" if split_field == "other_dv01" else "stable"
                    payload.signals.append(
                        RiskSignal(
                            id=split_id,
                            label=split_label,
                            value=Numeric(
                                raw=split_raw,
                                unit="dv01",
                                display=f"{split_raw:,.0f}",
                                precision=0,
                                sign_aware=False,
                            ),
                            status=split_status,
                            detail=f"{asof_label}; management DV01 accounting split included in total portfolio DV01.",
                        )
                    )
                risk_source_version = _DEFAULT_SOURCE
                risk_rule_version = _DEFAULT_RULE
                if governance_dir:
                    lineage = load_latest_bond_analytics_lineage(
                        governance_dir=governance_dir,
                        report_date=asof_date,
                    )
                    if lineage is not None:
                        risk_source_version = _join_lineage_tokens(
                            risk_source_version,
                            lineage.get("source_version"),
                        )
                        risk_rule_version = _join_lineage_tokens(
                            risk_rule_version,
                            lineage.get("rule_version"),
                        )
                return _envelope(
                    "executive.risk-overview",
                    payload,
                    source_version=risk_source_version,
                    rule_version=risk_rule_version,
                )
        return _envelope(
            "executive.risk-overview",
            _empty_risk_overview_payload(),
            quality_flag="warning",
            vendor_status="vendor_unavailable",
            source_version=_MISS_SOURCE,
        )
    except (RuntimeError, OSError, TypeError, ValueError):
        pass

    return _envelope(
        "executive.risk-overview",
        _empty_risk_overview_payload(),
        quality_flag="warning",
        vendor_status="vendor_unavailable",
        source_version=_MISS_SOURCE,
    )


def executive_contribution(report_date: str | None = None) -> dict[str, object]:
    settings = get_settings()
    normalized = _normalize_report_date(report_date)
    return _build_repo_payload_envelope(
        result_kind="executive.contribution",
        repo_factory=lambda: ProductCategoryPnlRepository(str(settings.duckdb_path)),
        build_fn=_build_contribution_from_repo,
        miss_payload_fn=_contribution_explicit_miss_payload,
        unavailable_payload_fn=_contribution_unavailable_payload,
        report_date=report_date,
        normalized=normalized,
    )


def _fallback_executive_alerts() -> dict[str, object]:
    return _envelope(
        "executive.alerts",
        _empty_alerts_payload(),
        quality_flag="warning",
        vendor_status="vendor_unavailable",
        source_version=_MISS_SOURCE,
    )


def _decimal_from_formal_numeric(
    value: object,
    *,
    field_name: str,
    allow_none: bool = False,
) -> Decimal:
    if isinstance(value, dict):
        if "raw" not in value:
            raise ValueError(f"Formal risk tensor numeric field {field_name!r} has no raw value.")
        value = value["raw"]
    if value is None:
        if allow_none:
            return Decimal("0")
        raise ValueError(f"Formal risk tensor numeric field {field_name!r} is null.")
    if isinstance(value, bool):
        raise ValueError(f"Formal risk tensor numeric field {field_name!r} is boolean.")
    try:
        decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise ValueError(
            f"Formal risk tensor numeric field {field_name!r} is invalid."
        ) from exc
    if not decimal_value.is_finite():
        raise ValueError(f"Formal risk tensor numeric field {field_name!r} is not finite.")
    return decimal_value


def _portfolio_risk_tensor_from_formal_result(
    result: dict[str, object],
    *,
    expected_report_date: date,
) -> PortfolioRiskTensor:
    result_report_date = date.fromisoformat(str(result["report_date"]))
    if result_report_date != expected_report_date:
        raise ValueError(
            "Formal risk tensor report_date does not match the requested executive alerts date."
        )
    warnings = result.get("warnings") or []
    if not isinstance(warnings, list):
        raise ValueError("Formal risk tensor warnings must be a list.")

    def _numeric(field_name: str, *, allow_none: bool = False) -> Decimal:
        return _decimal_from_formal_numeric(
            result.get(field_name),
            field_name=field_name,
            allow_none=allow_none,
        )

    return PortfolioRiskTensor(
        report_date=result_report_date,
        portfolio_dv01=_numeric("portfolio_dv01"),
        regulatory_dv01=_numeric("regulatory_dv01", allow_none=True),
        krd_1y=_numeric("krd_1y"),
        krd_3y=_numeric("krd_3y"),
        krd_5y=_numeric("krd_5y"),
        krd_7y=_numeric("krd_7y"),
        krd_10y=_numeric("krd_10y"),
        krd_30y=_numeric("krd_30y"),
        cs01=_numeric("cs01"),
        portfolio_convexity=_numeric("portfolio_convexity"),
        portfolio_modified_duration=_numeric("portfolio_modified_duration"),
        issuer_concentration_hhi=_numeric("issuer_concentration_hhi"),
        issuer_top5_weight=_numeric("issuer_top5_weight"),
        asset_cashflow_30d=_numeric("asset_cashflow_30d"),
        asset_cashflow_90d=_numeric("asset_cashflow_90d"),
        liability_cashflow_30d=_numeric("liability_cashflow_30d"),
        liability_cashflow_90d=_numeric("liability_cashflow_90d"),
        liquidity_gap_30d=_numeric("liquidity_gap_30d"),
        liquidity_gap_90d=_numeric("liquidity_gap_90d"),
        liquidity_gap_30d_ratio=_numeric("liquidity_gap_30d_ratio"),
        total_market_value=_numeric("total_market_value"),
        bond_count=int(result["bond_count"]),
        quality_flag=str(result["quality_flag"]),
        warnings=[str(warning) for warning in warnings],
    )


def _load_executive_alerts_risk_tensor(
    *,
    duckdb_path: str,
    governance_dir: str,
    normalized_report_date: str,
    report_date_value: date,
) -> tuple[PortfolioRiskTensor, dict[str, object]]:
    envelope = risk_tensor_envelope(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        report_date=normalized_report_date,
    )
    result = envelope.get("result")
    result_meta = envelope.get("result_meta")
    if not isinstance(result, dict) or not isinstance(result_meta, dict):
        raise ValueError("Formal risk tensor owner returned an invalid envelope.")
    if result_meta.get("result_kind") != "risk.tensor":
        raise ValueError("Formal risk tensor owner returned an unexpected result kind.")
    if not str(result_meta.get("source_version") or "").strip():
        raise ValueError("Formal risk tensor owner returned no source lineage.")
    if not str(result_meta.get("rule_version") or "").strip():
        raise ValueError("Formal risk tensor owner returned no rule lineage.")
    return (
        _portfolio_risk_tensor_from_formal_result(
            result,
            expected_report_date=report_date_value,
        ),
        result_meta,
    )


def _latest_formal_risk_tensor_report_date(
    *,
    duckdb_path: str,
    governance_dir: str,
) -> str | None:
    envelope = risk_tensor_dates_envelope(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
    )
    result = envelope.get("result")
    result_meta = envelope.get("result_meta")
    if not isinstance(result, dict) or not isinstance(result_meta, dict):
        raise ValueError("Formal risk tensor dates owner returned an invalid envelope.")
    if result_meta.get("result_kind") != "risk.tensor.dates":
        raise ValueError("Formal risk tensor dates owner returned an unexpected result kind.")
    report_dates = result.get("report_dates")
    if not isinstance(report_dates, list):
        raise ValueError("Formal risk tensor dates owner returned invalid report_dates.")
    if not report_dates:
        return None
    return date.fromisoformat(str(report_dates[0])).isoformat()


def _formal_risk_tensor_quality_flag(
    result_meta: dict[str, object],
    tensor: PortfolioRiskTensor,
) -> Literal["ok", "warning", "error", "stale"]:
    value = str(result_meta.get("quality_flag") or tensor.quality_flag).strip()
    if value == "ok":
        return "ok"
    if value == "warning":
        return "warning"
    if value == "error":
        return "error"
    if value == "stale":
        return "stale"
    raise ValueError(f"Formal risk tensor owner returned invalid quality_flag={value!r}.")


def executive_alerts(report_date: str | None = None) -> dict[str, object]:
    settings = get_settings()
    duckdb_path = str(settings.duckdb_path)
    governance_dir = str(getattr(settings, "governance_path", "") or "").strip()
    explicit_requested = _normalize_report_date(report_date)
    try:
        normalized_report_date = explicit_requested
        if normalized_report_date is None:
            normalized_report_date = _latest_formal_risk_tensor_report_date(
                duckdb_path=duckdb_path,
                governance_dir=governance_dir,
            )
            if normalized_report_date is None:
                return _fallback_executive_alerts()
        report_date_value = date.fromisoformat(normalized_report_date)
        tensor, tensor_meta = _load_executive_alerts_risk_tensor(
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
            normalized_report_date=normalized_report_date,
            report_date_value=report_date_value,
        )
        raw = evaluate_alerts(tensor)
        occurred_at = datetime.now().strftime("%H:%M")
        items = [
            AlertItem(
                id=entry["rule_id"],
                severity=entry["severity"],
                title=entry["title"],
                occurred_at=occurred_at,
                detail=entry["detail"],
            )
            for entry in raw
        ]
        payload = AlertsPayload(title="预警与事件", items=items)
        alerts_source_version = _join_lineage_tokens(
            _DEFAULT_SOURCE,
            tensor_meta.get("source_version"),
        )
        alerts_rule_version = _join_lineage_tokens(
            _DEFAULT_RULE,
            tensor_meta.get("rule_version"),
        )
        return _envelope(
            "executive.alerts",
            payload,
            quality_flag=_formal_risk_tensor_quality_flag(tensor_meta, tensor),
            source_version=alerts_source_version,
            rule_version=alerts_rule_version,
            requested_report_date=explicit_requested,
            resolved_report_date=normalized_report_date,
            as_of_date=normalized_report_date,
            date_basis="formal_snapshot",
        )
    except (RuntimeError, OSError, TypeError, ValueError, AttributeError, KeyError):
        if explicit_requested is not None:
            return _envelope(
                "executive.alerts",
                _empty_alerts_payload(),
                quality_flag="warning",
                vendor_status="vendor_unavailable",
                source_version=_MISS_SOURCE,
            )
        return _fallback_executive_alerts()


_HOME_SNAPSHOT_CALIBERS = ("balance_sheet", "pnl")
"""Business calibers for the home snapshot.

- ``balance_sheet``: AUM + NIM + DV01 — all from the same T+1 daily pipeline.
  Available dates = intersection(balance, liability, bond).
- ``pnl``: YTD P&L — independent formal build cycle.
- Market/macro data is excluded; it is real-time and not bound to report date.
"""


def _list_domain_dates() -> dict[str, set[str]]:
    """Return the set of available report_dates per caliber.

    ``balance_sheet`` = intersection of balance, liability, bond dates.
    ``pnl`` = formal fixed-income P&L dates.
    """
    settings = get_settings()

    balance_dates: set[str] = set()
    liability_dates: set[str] = set()
    bond_dates: set[str] = set()
    pnl_dates: set[str] = set()

    try:
        balance_repo = FormalZqtzBalanceMetricsRepository(str(settings.duckdb_path))
        balance_dates = set(_list_executive_aum_report_dates(balance_repo, currency_basis="CNY"))
    except (RuntimeError, OSError, TypeError, ValueError, AttributeError):
        pass

    try:
        pnl_repo = PnlRepository(str(settings.duckdb_path))
        pnl_dates = set(pnl_repo.list_formal_fi_report_dates())
    except (RuntimeError, OSError, TypeError, ValueError, AttributeError):
        pass

    try:
        liability_repo = LiabilityAnalyticsRepository(str(settings.duckdb_path))
        liability_dates = set(liability_repo.list_report_dates())
    except (RuntimeError, OSError, TypeError, ValueError, AttributeError):
        pass

    try:
        bond_repo = BondAnalyticsRepository(str(settings.duckdb_path))
        bond_dates = set(bond_repo.list_report_dates())
    except (RuntimeError, OSError, TypeError, ValueError, AttributeError):
        pass

    # balance_sheet caliber: a date is available only when ALL THREE
    # sub-sources (balance, liability, bond) have data for that date.
    bs_components = [balance_dates, liability_dates, bond_dates]
    balance_sheet_dates = (
        set.intersection(*bs_components) if all(bs_components) else set()
    )

    return {
        "balance_sheet": balance_sheet_dates,
        "pnl": pnl_dates,
    }


def _list_domain_date_context() -> dict[str, list[str]]:
    settings = get_settings()
    empty_context: dict[str, list[str]] = {
        "balance": [],
        "pnl": [],
        "liability": [],
        "bond": [],
    }
    try:
        return DashboardRepository(str(settings.duckdb_path)).list_domain_date_context()
    except (RuntimeError, OSError, TypeError, ValueError, AttributeError):
        return empty_context


def _domain_dates_from_context(context: dict[str, list[str]]) -> dict[str, set[str]]:
    balance_dates = set(context.get("balance", []))
    liability_dates = set(context.get("liability", []))
    bond_dates = set(context.get("bond", []))
    bs_components = [balance_dates, liability_dates, bond_dates]
    balance_sheet_dates = (
        set.intersection(*bs_components) if all(bs_components) else set()
    )
    return {
        "balance_sheet": balance_sheet_dates,
        "pnl": set(context.get("pnl", [])),
    }


def _compute_unified_report_date(
    *,
    requested: str | None,
    allow_partial: bool,
    domain_dates: dict[str, set[str]],
) -> tuple[str | None, list[str], dict[str, str]]:
    """Pick the authoritative report_date given inputs.

    Returns ``(report_date, domains_missing, domains_effective_date)``.
    - strict mode: returns the most recent date in the intersection; if
      ``requested`` is set and in intersection, returns it; else (None, all_domains, {}).
    - partial mode: returns ``requested`` (or max across union if not requested)
      and labels domains that don't have that date as missing.
    """
    intersection: set[str] = (
        set.intersection(*domain_dates.values()) if all(domain_dates.values()) else set()
    )

    if not allow_partial:
        # strict: intersection-only
        if requested:
            if requested in intersection:
                return (
                    requested,
                    [],
                    {domain: requested for domain in _HOME_SNAPSHOT_CALIBERS},
                )
            return (None, list(_HOME_SNAPSHOT_CALIBERS), {})
        if not intersection:
            return (None, list(_HOME_SNAPSHOT_CALIBERS), {})
        top_date = max(intersection)
        return (
            top_date,
            [],
            {domain: top_date for domain in _HOME_SNAPSHOT_CALIBERS},
        )

    # partial: accept any requested or fall back to union max
    if requested:
        target = requested
    else:
        union = set.union(*domain_dates.values()) if domain_dates.values() else set()
        if not union:
            return (None, list(_HOME_SNAPSHOT_CALIBERS), {})
        target = max(union)

    missing = [
        domain for domain in _HOME_SNAPSHOT_CALIBERS if target not in domain_dates[domain]
    ]
    effective: dict[str, str] = {}
    for domain in _HOME_SNAPSHOT_CALIBERS:
        if target in domain_dates[domain]:
            effective[domain] = target
        elif domain_dates[domain]:
            # approximate latest available for that domain
            effective[domain] = max(domain_dates[domain])
    return (target, missing, effective)


_VERDICT_TONES: frozenset[str] = frozenset({"positive", "neutral", "warning", "negative"})


def _coerce_verdict_tone(raw: str) -> VerdictTone:
    if raw in _VERDICT_TONES:
        return raw  # type: ignore[return-value]
    return "neutral"


def executive_verdict(
    *,
    overview: OverviewPayload,
    attention_count: int,
    partial_note: str | None,
    client_mode: str = "real",
) -> VerdictPayload:
    """首屏 Pyramid 定调：结论、支撑事实与下钻建议（确定性、可测试）。"""

    metrics = overview.metrics
    reasons: list[VerdictReason] = []
    for m in metrics[:3]:
        reasons.append(
            VerdictReason(
                label=m.label,
                value=m.value.display,
                detail=m.detail,
                tone=_coerce_verdict_tone(m.tone),
            )
        )

    tones = [_coerce_verdict_tone(m.tone) for m in metrics]
    pos = sum(1 for t in tones if t == "positive")
    neg = sum(1 for t in tones if t == "negative")
    warn = sum(1 for t in tones if t == "warning")

    if client_mode != "real" or partial_note:
        conclusion = "数据状态需先复核，再做方向性判断"
        tone: VerdictTone = "warning"
    elif not metrics:
        conclusion = "当前指标平稳，等待下一组观测"
        tone = "neutral"
    elif len(tones) > 0 and all(t == "neutral" for t in tones):
        conclusion = "当前指标平稳，等待下一组观测"
        tone = "neutral"
    elif pos >= neg + warn:
        conclusion = "首屏整体偏多，可基于规模与收益做方向性判断"
        tone = "positive"
    elif neg + warn > pos:
        conclusion = "首屏存在压力点，需进入专题页确认原因"
        tone = "warning"
    else:
        conclusion = "当前指标平稳，等待下一组观测"
        tone = "neutral"

    suggestions: list[VerdictSuggestion] = [
        VerdictSuggestion(text="进入对应专题页继续下钻原因链条", link=None),
    ]
    if any(_coerce_verdict_tone(m.tone) in ("warning", "negative") for m in metrics):
        suggestions.append(
            VerdictSuggestion(text="关注信用利差与久期暴露", link="/bond-analysis"),
        )
    if attention_count > 0 or partial_note:
        suggestions.append(
            VerdictSuggestion(text="复核治理状态后再做正式结论", link="/governance"),
        )

    return VerdictPayload(
        conclusion=conclusion,
        tone=tone,
        reasons=reasons,
        suggestions=suggestions,
    )


def _product_category_ytd_headline_from_values(
    report_date: str,
    values: dict[str, object],
) -> ProductCategoryYtdHeadlinePayload | None:
    if values.get("grand_total") is None:
        return None
    summary_pnl = _fmt_yi_amount(float(values["grand_total"]), signed=True)
    summary_detail = (
        "Aligned with product-category view=ytd "
        f"grand_total.business_net_income; report_date={report_date}."
    )
    intermediate = values.get("intermediate_business_income")
    if intermediate is None:
        int_numeric = _fmt_yi_amount(None, signed=True)
        int_detail = (
            "intermediate_business_income row was not found for product-category "
            f"view=ytd; report_date={report_date}."
        )
    else:
        int_numeric = _fmt_yi_amount(float(intermediate), signed=True)
        int_detail = (
            "Aligned with product-category view=ytd "
            f"intermediate_business_income; report_date={report_date}."
        )
    return ProductCategoryYtdHeadlinePayload(
        view="ytd",
        summary_pnl=summary_pnl,
        summary_pnl_detail=summary_detail,
        operating_income=summary_pnl,
        operating_income_detail=summary_detail,
        intermediate_business_income=int_numeric,
        intermediate_business_income_detail=int_detail,
    )


def _product_category_monthly_headline_from_values(
    report_date: str,
    values: dict[str, object],
) -> ProductCategoryMonthlyHeadlinePayload | None:
    if values.get("grand_total") is None:
        return None
    monthly_detail = (
        "Aligned with product-category view=monthly "
        f"grand_total.business_net_income; report_date={report_date}."
    )
    return ProductCategoryMonthlyHeadlinePayload(
        view="monthly",
        monthly_income=_fmt_yi_amount(float(values["grand_total"]), signed=True),
        monthly_income_detail=monthly_detail,
    )


def _fetch_product_category_home_headline_values(
    duck_path: str,
    report_date: str,
    views: list[str],
) -> dict[str, dict[str, object]]:
    try:
        return ProductCategoryPnlRepository(duck_path).fetch_home_headline_values(
            report_date=report_date,
            views=views,
        )
    except Exception:
        return {}


def _build_product_category_ytd_headline(report_date: str) -> ProductCategoryYtdHeadlinePayload | None:
    """与 /product-category-pnl「汇总视图」（ytd）一致：grand_total + intermediate_business_income。"""
    settings = get_settings()
    duck_path = str(getattr(settings, "duckdb_path", "") or "").strip()
    if not duck_path:
        return None
    fast_headline = _product_category_ytd_headline_from_values(
        report_date,
        _fetch_product_category_home_headline_values(duck_path, report_date, ["ytd"]).get("ytd", {}),
    )
    if fast_headline is not None:
        return fast_headline
    try:
        pc_payload = resolve_product_category_ytd_payload_for_home_snapshot(
            duck_path,
            str(settings.governance_path),
            report_date,
            float(settings.ftp_rate_pct),
        )
    except Exception:
        return None

    if pc_payload is None:
        return None

    summary_val = float(pc_payload.grand_total.business_net_income)
    summary_pnl = _fmt_yi_amount(summary_val, signed=True)
    summary_detail = (
        "与产品分类损益「汇总视图」（view=ytd）页脚「全部市场科目 + 投资收益合计」口径一致："
        f"grand_total.business_net_income；report_date={report_date}；"
        "优先读 product_category_pnl_formal_read_model（view=ytd）；"
        "若缺行则自 product_category_pnl_canonical_fact 重算（与刷数任务同口径）。"
    )
    operating = summary_pnl
    operating_detail = summary_detail

    intermediate_row = next(
        (r for r in pc_payload.rows if r.category_id == "intermediate_business_income"),
        None,
    )
    if intermediate_row is None:
        int_numeric = _fmt_yi_amount(None, signed=True)
        int_detail = (
            "未找到 intermediate_business_income 分类行（product_category ytd, "
            f"report_date={report_date}）。"
        )
    else:
        int_numeric = _fmt_yi_amount(float(intermediate_row.business_net_income), signed=True)
        int_detail = (
            "与产品分类损益「中间业务收入」（intermediate_business_income）ytd 行一致；"
            f"report_date={report_date}。"
        )

    return ProductCategoryYtdHeadlinePayload(
        view="ytd",
        summary_pnl=summary_pnl,
        summary_pnl_detail=summary_detail,
        operating_income=operating,
        operating_income_detail=operating_detail,
        intermediate_business_income=int_numeric,
        intermediate_business_income_detail=int_detail,
    )


def _build_product_category_monthly_headline(report_date: str) -> ProductCategoryMonthlyHeadlinePayload | None:
    """与 /product-category-pnl 月度视图页脚 grand_total.business_net_income 对齐。"""
    settings = get_settings()
    duck_path = str(getattr(settings, "duckdb_path", "") or "").strip()
    if not duck_path:
        return None
    fast_headline = _product_category_monthly_headline_from_values(
        report_date,
        _fetch_product_category_home_headline_values(duck_path, report_date, ["monthly"]).get("monthly", {}),
    )
    if fast_headline is not None:
        return fast_headline
    try:
        envelope = product_category_pnl_envelope(
            duck_path,
            report_date=report_date,
            view="monthly",
        )
        result_dict = envelope.get("result")
        if not isinstance(result_dict, dict):
            return None
        from backend.app.schemas.product_category_pnl import ProductCategoryPnlPayload

        pc_payload = ProductCategoryPnlPayload.model_validate(result_dict)
    except Exception:
        return None

    monthly_value = float(pc_payload.grand_total.business_net_income)
    monthly_detail = (
        "与产品分类损益「月度视图」（view=monthly）页脚"
        f"「全部市场科目 + 投资收益合计」一致：grand_total.business_net_income；report_date={report_date}。"
    )
    return ProductCategoryMonthlyHeadlinePayload(
        view="monthly",
        monthly_income=_fmt_yi_amount(monthly_value, signed=True),
        monthly_income_detail=monthly_detail,
    )


def _build_product_category_headlines(
    report_date: str,
) -> tuple[
    ProductCategoryYtdHeadlinePayload | None,
    ProductCategoryMonthlyHeadlinePayload | None,
    int,
    int,
]:
    settings = get_settings()
    duck_path = str(getattr(settings, "duckdb_path", "") or "").strip()
    if duck_path:
        started_at = time.perf_counter()
        fast_values = _fetch_product_category_home_headline_values(
            duck_path,
            report_date,
            ["ytd", "monthly"],
        )
        ytd_headline = _product_category_ytd_headline_from_values(
            report_date,
            fast_values.get("ytd", {}),
        )
        monthly_headline = _product_category_monthly_headline_from_values(
            report_date,
            fast_values.get("monthly", {}),
        )
        if ytd_headline is not None and monthly_headline is not None:
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            return ytd_headline, monthly_headline, elapsed_ms, elapsed_ms

    def timed_ytd() -> tuple[ProductCategoryYtdHeadlinePayload | None, int]:
        started_at = time.perf_counter()
        return _build_product_category_ytd_headline(report_date), int((time.perf_counter() - started_at) * 1000)

    def timed_monthly() -> tuple[ProductCategoryMonthlyHeadlinePayload | None, int]:
        started_at = time.perf_counter()
        return _build_product_category_monthly_headline(report_date), int((time.perf_counter() - started_at) * 1000)

    with ThreadPoolExecutor(max_workers=2) as executor:
        ytd_future = executor.submit(timed_ytd)
        monthly_future = executor.submit(timed_monthly)
        ytd_headline, ytd_ms = ytd_future.result()
        monthly_headline, monthly_ms = monthly_future.result()
        return ytd_headline, monthly_headline, ytd_ms, monthly_ms


def home_research_reports_envelope(
    *,
    report_date: str,
    limit: int = 5,
) -> dict[str, object]:
    """Return dashboard-home research reports from governed news warehouse rows."""

    normalized = _normalize_report_date(report_date)
    settings = get_settings()
    duckdb_path = str(settings.duckdb_path)
    rows: list[dict[str, object]] = []
    warnings: list[str] = []
    research_date_mode = "on_or_before_report_date"

    if not Path(duckdb_path).exists():
        warnings.append("DuckDB news warehouse is not available; research reports are empty.")
    else:
        try:
            rows = NewsWarehouseRepository(duckdb_path).list_research_reports(
                report_date=normalized,
                limit=limit,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            warnings.append(f"Research reports unavailable from fact_news_event: {exc}")

    source_status: Literal["ready", "empty"] = "ready" if rows else "empty"
    if not rows and not warnings:
        warnings.append("No research reports found on or before report_date.")

    payload = HomeResearchReportsPayload(
        report_date=normalized,
        source_status=source_status,
        items=[HomeResearchReportItem.model_validate(row) for row in rows],
        warnings=warnings,
    )
    return _envelope(
        "home.research_reports",
        payload,
        quality_flag="ok" if rows else "warning",
        vendor_status="ok" if rows else "vendor_unavailable",
        source_version="sv_home_research_reports_v1" if rows else "sv_home_research_reports_empty_v1",
        rule_version="rv_home_research_reports_v1",
        filters_applied={
            "report_date": normalized,
            "limit": limit,
            "source_kind": "research",
            "research_date_mode": research_date_mode,
        },
        requested_report_date=normalized,
        resolved_report_date=normalized,
        as_of_date=normalized,
        date_basis="fact_news_event.pub_time_lte_report_date",
    )


def _home_income_null_pnl() -> Numeric:
    return Numeric(
        raw=None,
        unit="yuan",
        display="-",
        precision=2,
        sign_aware=True,
    )


def _numeric_raw_and_unit_from_payload(value: object) -> tuple[float | None, str | None]:
    if isinstance(value, Numeric):
        return value.raw, value.unit
    if isinstance(value, dict):
        raw_value = value.get("raw")
        unit_value = value.get("unit")
    else:
        raw_value = getattr(value, "raw", value)
        unit_value = getattr(value, "unit", None)
    if raw_value is None:
        return None, str(unit_value) if unit_value else None
    try:
        return float(raw_value), str(unit_value) if unit_value else None
    except (TypeError, ValueError):
        return None, str(unit_value) if unit_value else None


def _home_income_pct_points_from_payload(value: object) -> float | None:
    raw, unit = _numeric_raw_and_unit_from_payload(value)
    if raw is None:
        return None
    if unit == "pct":
        return raw * _BASIS_POINTS_PER_PERCENT
    if unit == "bp":
        return raw / _BASIS_POINTS_PER_PERCENT
    # Bond analytics collapses governed pct Numerics to flat Q8 strings while
    # preserving their canonical decimal-ratio raw value.
    return raw * _BASIS_POINTS_PER_PERCENT


def _home_income_bp_points_from_payload(value: object) -> float | None:
    raw, unit = _numeric_raw_and_unit_from_payload(value)
    if raw is None:
        return None
    if unit == "pct":
        return raw * _BASIS_POINTS_PER_PERCENT
    return raw / _BASIS_POINTS_PER_PERCENT


def _home_income_benchmark_warning(point_date: str, reason: object) -> str:
    text = str(reason or "").strip()
    if not text:
        text = "benchmark/excess return unavailable"
    return f"{point_date} {_HOME_INCOME_BENCHMARK_ID}: {text}"


def _home_income_warning_date(text: str, marker: str) -> date | None:
    marker_index = text.find(marker)
    if marker_index < 0:
        return None
    try:
        return date.fromisoformat(text[marker_index + len(marker): marker_index + len(marker) + 10])
    except ValueError:
        return None


def _is_bounded_home_income_curve_fallback(reason: object) -> bool:
    text = str(reason or "")
    if _HOME_INCOME_CURVE_FALLBACK_PREFIX not in text:
        return False
    resolved_date = _home_income_warning_date(text, "from trade_date=")
    requested_date = _home_income_warning_date(text, "requested_trade_date=")
    if resolved_date is None or requested_date is None:
        return False
    fallback_days = (requested_date - resolved_date).days
    return 0 <= fallback_days <= _HOME_INCOME_MAX_CURVE_FALLBACK_DAYS


def _is_home_income_amount_disclosure_warning(reason: object) -> bool:
    return BOND_ANALYTICS_FOREIGN_CURRENCY_FALLBACK_WARNING in str(reason or "")


def _is_home_income_reconciliation_warning(reason: object) -> bool:
    return BENCHMARK_EXCESS_RECON_GAP in str(reason or "")


def _home_income_blocking_benchmark_reasons(
    benchmark_warnings: list[object],
    *,
    vendor_status: str,
) -> list[object]:
    has_bounded_curve_fallback = any(
        _is_bounded_home_income_curve_fallback(warning)
        for warning in benchmark_warnings
    )
    blocking_reasons: list[object] = [
        warning
        for warning in benchmark_warnings
        if not (
            _is_bounded_home_income_curve_fallback(warning)
            or _is_home_income_amount_disclosure_warning(warning)
            or _is_home_income_reconciliation_warning(warning)
        )
    ]
    if vendor_status != "ok" and not (
        vendor_status == "vendor_stale" and has_bounded_curve_fallback and not blocking_reasons
    ):
        blocking_reasons.append(f"vendor_status={vendor_status}")
    return blocking_reasons


_HomeIncomeBenchmarkFetch = dict[str, object] | RuntimeError | OSError | TypeError | ValueError | KeyError


def _fetch_home_income_benchmark_envelopes(point_dates: list[str]) -> dict[str, _HomeIncomeBenchmarkFetch]:
    requested_dates = []
    for point_date in point_dates:
        try:
            requested_dates.append(date.fromisoformat(point_date))
        except ValueError as exc:
            return {point_date: exc for point_date in point_dates}
    try:
        return get_benchmark_excess_many(
            requested_dates,
            _HOME_INCOME_BENCHMARK_PERIOD_TYPE,
            _HOME_INCOME_BENCHMARK_ID,
        )
    except (RuntimeError, OSError, TypeError, ValueError, KeyError):
        pass

    def load(point_date: str) -> _HomeIncomeBenchmarkFetch:
        try:
            return get_benchmark_excess(
                date.fromisoformat(point_date),
                _HOME_INCOME_BENCHMARK_PERIOD_TYPE,
                _HOME_INCOME_BENCHMARK_ID,
            )
        except (RuntimeError, OSError, TypeError, ValueError, KeyError) as exc:
            return exc

    if len(point_dates) <= 1:
        return {point_date: load(point_date) for point_date in point_dates}

    max_workers = min(len(point_dates), 8)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {point_date: executor.submit(load, point_date) for point_date in point_dates}
        return {point_date: future.result() for point_date, future in futures.items()}


def home_income_trend_envelope(
    *,
    report_date: str,
    window: int = 7,
) -> dict[str, object]:
    normalized = _normalize_report_date(report_date)
    assert normalized is not None
    bounded_window = max(1, min(int(window), 30))
    cache_key: _HomeIncomeTrendCacheKey = (
        normalized,
        bounded_window,
        _home_data_version_token(),
    )
    envelope = _HOME_INCOME_TREND_CACHE.get_or_set(
        cache_key,
        lambda: _compute_home_income_trend_envelope(
            report_date=normalized,
            window=bounded_window,
        ),
    )
    return deepcopy(envelope)


def _compute_home_income_trend_envelope(
    *,
    report_date: str,
    window: int,
) -> dict[str, object]:
    """Return recent monthly portfolio PnL points from the governed product-category read model.

    Portfolio PnL comes from product-category monthly grand_total. Benchmark
    and excess PnL are derived only when the governed CDB benchmark-excess
    surface returns a source-backed return set for the same point. Bounded
    previous-curve fallback is accepted as verified business-day fallback.
    """

    normalized = _normalize_report_date(report_date)
    assert normalized is not None
    bounded_window = max(1, min(int(window), 30))
    settings = get_settings()
    repo = ProductCategoryPnlRepository(str(settings.duckdb_path))
    rows: list[dict[str, object]] = []
    warnings: list[str] = []

    try:
        report_dates = [
            value
            for value in repo.list_report_dates()
            if value <= normalized
        ][:bounded_window]
        for candidate_date in report_dates:
            grand_total = next(
                (
                    row
                    for row in repo.fetch_rows(candidate_date, "monthly")
                    if str(row.get("category_id") or "") == "grand_total"
                ),
                None,
            )
            if grand_total is not None:
                rows.append(grand_total)
    except (RuntimeError, OSError, TypeError, ValueError, KeyError) as exc:
        warnings.append(f"Income trend unavailable from product_category_pnl_formal_read_model: {exc}")

    missing_components: list[str] = []
    benchmark_source_versions: list[str] = []
    benchmark_rule_versions: list[str] = []
    source_status: Literal["ready", "partial", "empty"] = "empty"
    if not rows and not warnings:
        warnings.append("No monthly grand_total rows found on or before report_date.")

    points: list[HomeIncomeTrendPoint] = []
    sorted_rows = sorted(rows, key=lambda item: str(item.get("report_date") or ""))
    benchmark_envelopes = _fetch_home_income_benchmark_envelopes(
        [str(row.get("report_date") or "") for row in sorted_rows]
    )
    for row in sorted_rows:
        point_date = str(row.get("report_date") or "")
        portfolio_pnl = _fmt_yi_amount(
            float(row["business_net_income"])
            if row.get("business_net_income") is not None
            else None,
            signed=True,
        )
        benchmark_pnl = _home_income_null_pnl()
        excess_pnl = _home_income_null_pnl()
        point_status: Literal["ready", "partial"] = "partial"

        try:
            benchmark_envelope = benchmark_envelopes.get(point_date)
            if isinstance(benchmark_envelope, (RuntimeError, OSError, TypeError, ValueError, KeyError)):
                raise benchmark_envelope
            benchmark_result = benchmark_envelope.get("result") if isinstance(benchmark_envelope, dict) else None
            benchmark_meta = benchmark_envelope.get("result_meta") if isinstance(benchmark_envelope, dict) else None
            if isinstance(benchmark_meta, dict):
                benchmark_source_versions.extend(_lineage_tokens(benchmark_meta.get("source_version")))
                benchmark_rule_versions.extend(_lineage_tokens(benchmark_meta.get("rule_version")))

            benchmark_warnings = (
                list(benchmark_result.get("warnings") or [])
                if isinstance(benchmark_result, dict)
                else ["benchmark/excess result missing"]
            )
            vendor_status = (
                str(benchmark_meta.get("vendor_status") or "ok")
                if isinstance(benchmark_meta, dict)
                else "vendor_unavailable"
            )
            blocking_reasons = _home_income_blocking_benchmark_reasons(
                benchmark_warnings,
                vendor_status=vendor_status,
            )
            if blocking_reasons:
                reasons = blocking_reasons or [f"vendor_status={vendor_status}"]
                warnings.extend(_home_income_benchmark_warning(point_date, reason) for reason in reasons)
            elif isinstance(benchmark_result, dict):
                portfolio_return = _home_income_pct_points_from_payload(benchmark_result.get("portfolio_return"))
                benchmark_return = _home_income_pct_points_from_payload(benchmark_result.get("benchmark_return"))
                excess_return = _home_income_bp_points_from_payload(benchmark_result.get("excess_return"))
                if (
                    portfolio_pnl.raw is not None
                    and portfolio_return is not None
                    and abs(portfolio_return) > 1e-12
                    and benchmark_return is not None
                    and excess_return is not None
                ):
                    pnl_base = portfolio_pnl.raw / portfolio_return
                    benchmark_pnl = _fmt_yi_amount(pnl_base * benchmark_return, signed=True)
                    excess_pnl = _fmt_yi_amount(pnl_base * excess_return, signed=True)
                    point_status = "ready"
                else:
                    warnings.append(
                        _home_income_benchmark_warning(
                            point_date,
                            "portfolio_return, benchmark_return or excess_return is missing/zero",
                        )
                    )
        except (RuntimeError, OSError, TypeError, ValueError, KeyError) as exc:
            warnings.append(_home_income_benchmark_warning(point_date, exc))

        points.append(
            HomeIncomeTrendPoint(
                date=point_date,
                portfolio_pnl=portfolio_pnl,
                benchmark_pnl=benchmark_pnl,
                excess_pnl=excess_pnl,
                basis="product_category_pnl_monthly",
                source_status=point_status,
            )
        )

    if points:
        source_status = "ready" if all(point.source_status == "ready" for point in points) else "partial"
    if source_status == "partial":
        missing_components = ["benchmark_pnl", "excess_pnl"]
    warnings = _lineage_tokens(*warnings)

    payload = HomeIncomeTrendPayload(
        report_date=normalized,
        window=bounded_window,
        source_status=source_status,
        points=points,
        missing_components=missing_components if rows else [],
        warnings=warnings,
    )
    return _envelope(
        "home.income_trend",
        payload,
        quality_flag="warning" if source_status != "ready" else "ok",
        vendor_status="ok" if rows else "vendor_unavailable",
        source_version=(
            _join_lineage_tokens(
                *_lineage_tokens_from_rows(rows, "source_version"),
                *benchmark_source_versions,
            )
            if rows
            else "sv_home_income_trend_empty_v1"
        ),
        rule_version=(
            _join_lineage_tokens(
                "rv_home_income_trend_v2",
                *_lineage_tokens_from_rows(rows, "rule_version"),
                *benchmark_rule_versions,
            )
            if rows
            else "rv_home_income_trend_v2"
        ),
        filters_applied={
            "report_date": normalized,
            "window": bounded_window,
            "view": "monthly",
            "category_id": "grand_total",
            "benchmark_id": _HOME_INCOME_BENCHMARK_ID,
            "benchmark_period_type": _HOME_INCOME_BENCHMARK_PERIOD_TYPE,
        },
        requested_report_date=normalized,
        resolved_report_date=points[-1].date if points else normalized,
        as_of_date=points[-1].date if points else normalized,
        date_basis="product_category_pnl_formal_read_model.report_date_lte_request",
    )


def warm_home_income_trend_cache_if_configured(settings: object) -> bool:
    if not bool(getattr(settings, "home_income_trend_prewarm_enabled", False)):
        return False
    thread = threading.Thread(
        target=_warm_home_income_trend_cache_quietly,
        kwargs={"report_date": None, "window": 7},
        daemon=True,
        name="moss-home-income-trend-warmup",
    )
    thread.start()
    return True


def warm_home_income_trend_cache_in_current_thread_if_configured(settings: object) -> bool:
    if not bool(getattr(settings, "home_income_trend_prewarm_enabled", False)):
        return False
    _warm_home_income_trend_cache_quietly(report_date=None, window=7)
    return True


def _warm_home_income_trend_cache_quietly(
    *,
    report_date: str | None,
    window: int,
) -> None:
    started_at = time.perf_counter()
    try:
        normalized_report_date = _normalize_report_date(report_date) if report_date else _latest_product_category_report_date()
        if normalized_report_date is None:
            logger.info("home_income_trend_prewarm_skip reason=no_report_date")
            return
        home_income_trend_envelope(report_date=normalized_report_date, window=window)
        logger.info(
            "home_income_trend_prewarm_done ms=%d report_date=%s window=%d",
            int((time.perf_counter() - started_at) * 1000),
            normalized_report_date,
            int(window),
        )
    except Exception:
        logger.exception("home_income_trend_prewarm_failed")


def _latest_product_category_report_date() -> str | None:
    try:
        repo = ProductCategoryPnlRepository(str(get_settings().duckdb_path))
        dates = repo.list_report_dates()
    except (RuntimeError, OSError, TypeError, ValueError, KeyError):
        return None
    return dates[0] if dates else None


def _empty_home_snapshot_payload() -> HomeSnapshotPayload:
    return HomeSnapshotPayload(
        report_date="",
        mode="strict",
        source_surface="executive_analytical",
        overview=OverviewPayload(title="经营总览", metrics=[]),
        attribution=_pnl_attribution_unavailable_payload(),
        domains_missing=list(_HOME_SNAPSHOT_CALIBERS),
        domains_effective_date={},
        verdict=None,
        product_category_ytd=None,
        product_category_monthly=None,
    )


# ---------------------------------------------------------------------------
# Home snapshot 内存 TTL 缓存
# ---------------------------------------------------------------------------
# 单进程进程内缓存，按 (report_date, allow_partial) 维度独立存储；
# TTL 过期或显式 invalidate 才会重新构造（一次约 80+ 次 DuckDB 查询 + 派生）。
# 设计权衡：
#   - 驾驶舱用户量小（管理层），日常 TTL 5 分钟足够；
#   - 不引入 Redis/外部存储，零依赖增加；
#   - 写场景（治理刷库、补数任务）应显式调用 invalidate_home_snapshot_cache();
#   - 多 worker 部署下每个 worker 独立缓存，可接受；DuckDB mtime 仍会隔离数据变更。

_HOME_SNAPSHOT_CACHE_TTL_SECONDS: float = 3600.0
_HOME_NIM_CONTEXT_CACHE_TTL_SECONDS: float = 300.0
_HOME_INCOME_TREND_CACHE_TTL_SECONDS: float = 300.0
_HOME_SUPPORT_CACHE_TTL_SECONDS: float = 300.0
_HomeDataVersionToken = tuple[object, ...]
_HomeSnapshotCacheKey = tuple[str | None, bool, _HomeDataVersionToken]
_HomeIncomeTrendCacheKey = tuple[str, int, _HomeDataVersionToken]
_HomeNimContextCacheKey = tuple[tuple[str, ...], str | None, int, _HomeDataVersionToken]
_HomeGovernanceFileFingerprint = tuple[str, int, int, str]
_HomeCacheBuildRunsKey = tuple[str, _HomeGovernanceFileFingerprint]
_HomeKpiGateCacheKey = tuple[str, int | None, int]
_HomeKpiMetricsCacheKey = tuple[str, str | None, int]
_HomeFileStatSignature = tuple[tuple[str, int, int], ...]
_HomeDuckdbStorageFingerprint = tuple[tuple[str, int, str], ...] | None
_HomeSelectedGovernanceFingerprint = tuple[tuple[str, int, int, str], ...] | None
_HomeNimContextValue = tuple[
    dict[str, dict[str, object]],
    dict[str, list[dict[str, object]]],
    dict[str, list[dict[str, object]]],
    list[float] | None,
]
_HOME_SNAPSHOT_CACHE: InMemoryTTLCache[_HomeSnapshotCacheKey, dict[str, object]] = get_runtime_cache(
    "executive.home_snapshot",
    ttl_seconds=_HOME_SNAPSHOT_CACHE_TTL_SECONDS,
    clock=lambda: time.monotonic(),
)
_HOME_NIM_CONTEXT_CACHE: InMemoryTTLCache[_HomeNimContextCacheKey, _HomeNimContextValue] = get_runtime_cache(
    "executive.home_snapshot.nim_context",
    ttl_seconds=_HOME_NIM_CONTEXT_CACHE_TTL_SECONDS,
    clock=lambda: time.monotonic(),
)
_HOME_INCOME_TREND_CACHE: InMemoryTTLCache[_HomeIncomeTrendCacheKey, dict[str, object]] = get_runtime_cache(
    "executive.home_income_trend",
    ttl_seconds=_HOME_INCOME_TREND_CACHE_TTL_SECONDS,
    clock=lambda: time.monotonic(),
)
_HOME_CACHE_BUILD_RUNS_CACHE: InMemoryTTLCache[
    _HomeCacheBuildRunsKey,
    list[dict[str, object]] | None,
] = get_runtime_cache(
    "executive.home_snapshot.cache_build_runs",
    ttl_seconds=_HOME_SUPPORT_CACHE_TTL_SECONDS,
    clock=lambda: time.monotonic(),
)
_HOME_KPI_GATE_CACHE: InMemoryTTLCache[_HomeKpiGateCacheKey, dict[str, object]] = get_runtime_cache(
    "executive.home_snapshot.kpi_gate",
    ttl_seconds=_HOME_SUPPORT_CACHE_TTL_SECONDS,
    clock=lambda: time.monotonic(),
)
_HOME_KPI_METRICS_CACHE: InMemoryTTLCache[_HomeKpiMetricsCacheKey, list[dict[str, object]]] = get_runtime_cache(
    "executive.home_snapshot.kpi_metrics",
    ttl_seconds=_HOME_SUPPORT_CACHE_TTL_SECONDS,
    clock=lambda: time.monotonic(),
)
_HOME_SNAPSHOT_PREWARM_LOCK = threading.Lock()
_HOME_SNAPSHOT_PREWARM_STATUS: dict[str, object] = {
    "ok": False,
    "status": "disabled",
    "report_date": None,
    "allow_partial": False,
    "last_duration_ms": None,
    "last_step_durations_ms": {},
    "error": None,
}
_HOME_SNAPSHOT_PROFILE_LOCAL = threading.local()
_HOME_FINGERPRINT_CACHE_LOCK = threading.Lock()
_HOME_DUCKDB_STORAGE_FINGERPRINT_CACHE: dict[
    _HomeFileStatSignature,
    _HomeDuckdbStorageFingerprint,
] = {}


def _duckdb_version_token() -> tuple[str, int | None]:
    duckdb_path = str(get_settings().duckdb_path)
    try:
        return duckdb_path, Path(duckdb_path).stat().st_mtime_ns
    except OSError:
        return duckdb_path, None


def _duckdb_file_edge_hash(path: Path, *, stat_size: int) -> str | None:
    try:
        with path.open("rb") as handle:
            head = handle.read(_HOME_CACHE_GOVERNANCE_TAIL_BYTES)
            if stat_size > _HOME_CACHE_GOVERNANCE_TAIL_BYTES:
                handle.seek(-_HOME_CACHE_GOVERNANCE_TAIL_BYTES, 2)
                tail = handle.read(_HOME_CACHE_GOVERNANCE_TAIL_BYTES)
            else:
                tail = b""
    except OSError:
        return None
    digest = hashlib.sha256()
    digest.update(head)
    digest.update(tail)
    return digest.hexdigest()


def _duckdb_storage_content_fingerprint(duckdb_path: object) -> tuple[tuple[str, int, str], ...] | None:
    path = Path(str(duckdb_path))
    try:
        path.stat()
    except OSError:
        return None
    stat_signature: list[tuple[str, int, int]] = []
    candidates = sorted(path.parent.glob(f"{path.name}*"))
    for candidate in candidates:
        try:
            stat = candidate.stat()
        except OSError:
            continue
        if candidate.is_file():
            stat_signature.append((str(candidate), stat.st_size, stat.st_mtime_ns))
    signature = tuple(stat_signature)
    if not signature:
        return None
    with _HOME_FINGERPRINT_CACHE_LOCK:
        if signature in _HOME_DUCKDB_STORAGE_FINGERPRINT_CACHE:
            return _HOME_DUCKDB_STORAGE_FINGERPRINT_CACHE[signature]
    fingerprint: list[tuple[str, int, str]] = []
    for candidate in candidates:
        try:
            stat = candidate.stat()
        except OSError:
            continue
        if not candidate.is_file():
            continue
        edge_hash = _duckdb_file_edge_hash(candidate, stat_size=stat.st_size)
        if edge_hash is None:
            return None
        fingerprint.append((candidate.name, stat.st_size, edge_hash))
    value = tuple(fingerprint) or None
    with _HOME_FINGERPRINT_CACHE_LOCK:
        _HOME_DUCKDB_STORAGE_FINGERPRINT_CACHE[signature] = value
    return value


def _governance_file_fingerprint(
    base_dir: object,
    stream: str,
) -> _HomeGovernanceFileFingerprint | None:
    base_path = Path(str(base_dir))
    path = base_path / f"{stream}.jsonl"
    try:
        stat = path.stat()
    except OSError:
        return None
    if not path.is_file():
        return None
    try:
        with path.open("rb") as handle:
            if stat.st_size > _HOME_CACHE_GOVERNANCE_TAIL_BYTES:
                handle.seek(-_HOME_CACHE_GOVERNANCE_TAIL_BYTES, 2)
            content = handle.read()
    except OSError:
        return None
    return (stream, stat.st_size, stat.st_mtime_ns, hashlib.sha256(content).hexdigest())


def _selected_governance_files_fingerprint(
    base_dir: object,
) -> tuple[tuple[str, int, int, str], ...] | None:
    base_path = Path(str(base_dir))
    if not str(base_dir or "").strip():
        return None
    fingerprint: list[tuple[str, int, int, str]] = []
    for filename in _HOME_CACHE_GOVERNANCE_FILES:
        path = base_path / filename
        try:
            stat = path.stat()
        except OSError:
            return None
        if not path.is_file():
            return None
        try:
            with path.open("rb") as handle:
                if stat.st_size > _HOME_CACHE_GOVERNANCE_TAIL_BYTES:
                    handle.seek(-_HOME_CACHE_GOVERNANCE_TAIL_BYTES, 2)
                content = handle.read()
        except OSError:
            return None
        fingerprint.append((filename, stat.st_size, stat.st_mtime_ns, hashlib.sha256(content).hexdigest()))
    return tuple(fingerprint)


def _home_data_version_token(
    *,
    duckdb_path: object | None = None,
    governance_path: object | None = None,
) -> _HomeDataVersionToken:
    settings = get_settings()
    resolved_duckdb_path = str(settings.duckdb_path if duckdb_path is None else duckdb_path)
    resolved_governance_path = str(
        getattr(settings, "governance_path", "") if governance_path is None else governance_path
    )
    return (
        resolved_duckdb_path,
        _duckdb_storage_content_fingerprint(resolved_duckdb_path),
        resolved_governance_path,
        _selected_governance_files_fingerprint(resolved_governance_path),
    )


def _home_snapshot_cache_key(
    *,
    report_date: str | None,
    allow_partial: bool,
) -> _HomeSnapshotCacheKey:
    return (report_date, allow_partial, _home_data_version_token())


def _log_home_snapshot_perf_step(
    step: str,
    started_at: float,
    *,
    extra: str,
    report_date: str | None,
    allow_partial: bool,
    elapsed_ms: int | None = None,
) -> None:
    resolved_elapsed_ms = (
        elapsed_ms if elapsed_ms is not None else int((time.perf_counter() - started_at) * 1000)
    )
    logger.info(
        "home_snapshot perf: step=%s ms=%d extra=%s report_date=%s allow_partial=%s",
        step,
        resolved_elapsed_ms,
        extra,
        report_date,
        allow_partial,
    )
    step_durations = getattr(_HOME_SNAPSHOT_PROFILE_LOCAL, "step_durations_ms", None)
    if isinstance(step_durations, dict):
        step_durations[step] = resolved_elapsed_ms


def _start_home_snapshot_step_profile() -> None:
    _HOME_SNAPSHOT_PROFILE_LOCAL.step_durations_ms = {}


def _finish_home_snapshot_step_profile() -> dict[str, int]:
    step_durations = getattr(_HOME_SNAPSHOT_PROFILE_LOCAL, "step_durations_ms", None)
    if isinstance(step_durations, dict):
        copied = {str(step): int(ms) for step, ms in step_durations.items()}
    else:
        copied = {}
    if hasattr(_HOME_SNAPSHOT_PROFILE_LOCAL, "step_durations_ms"):
        delattr(_HOME_SNAPSHOT_PROFILE_LOCAL, "step_durations_ms")
    return copied


def _log_executive_overview_perf_step(
    step: str,
    started_at: float,
    *,
    report_date: str | None,
    elapsed_ms: int | None = None,
) -> None:
    logger.info(
        "executive_overview perf: step=%s ms=%d report_date=%s",
        step,
        elapsed_ms if elapsed_ms is not None else int((time.perf_counter() - started_at) * 1000),
        report_date,
    )


def _log_home_snapshot_detail_perf(
    scope: str,
    step: str,
    started_at: float,
    *,
    extra: str,
    report_date: str | None,
    elapsed_ms: int | None = None,
) -> None:
    logger.info(
        "%s perf: step=%s ms=%d extra=%s report_date=%s",
        scope,
        step,
        elapsed_ms if elapsed_ms is not None else int((time.perf_counter() - started_at) * 1000),
        extra,
        report_date,
    )


def invalidate_home_snapshot_cache() -> None:
    """显式清空 home_snapshot 缓存。

    适用场景：
      - 治理流程完成补数 / 刷库后；
      - 后台任务希望强制下次请求拿到新数据；
      - 测试隔离。
    """
    _HOME_SNAPSHOT_CACHE.clear()
    _HOME_NIM_CONTEXT_CACHE.clear()
    _HOME_INCOME_TREND_CACHE.clear()
    _HOME_CACHE_BUILD_RUNS_CACHE.clear()
    _HOME_KPI_GATE_CACHE.clear()
    _HOME_KPI_METRICS_CACHE.clear()
    with _HOME_FINGERPRINT_CACHE_LOCK:
        _HOME_DUCKDB_STORAGE_FINGERPRINT_CACHE.clear()


def _set_home_snapshot_prewarm_status(**updates: object) -> None:
    with _HOME_SNAPSHOT_PREWARM_LOCK:
        _HOME_SNAPSHOT_PREWARM_STATUS.update(updates)


def home_snapshot_prewarm_status() -> dict[str, object]:
    with _HOME_SNAPSHOT_PREWARM_LOCK:
        return dict(_HOME_SNAPSHOT_PREWARM_STATUS)


def home_snapshot_envelope(
    *,
    report_date: str | None = None,
    allow_partial: bool = False,
) -> dict[str, object]:
    """home snapshot envelope 入口（带 TTL 缓存）。

    缓存命中：返回上次构造 envelope 的防御副本，避免调用方 mutation 污染缓存。
    缓存未命中或过期：执行 ``_compute_home_snapshot_envelope`` 并写回缓存。
    """
    total_t0 = time.perf_counter()
    normalized_report_date = _normalize_report_date(report_date)
    cache_key = _home_snapshot_cache_key(
        report_date=normalized_report_date,
        allow_partial=allow_partial,
    )
    t0 = time.perf_counter()
    cache_state = "hit" if _HOME_SNAPSHOT_CACHE.get(cache_key)[0] else "miss"
    _log_home_snapshot_perf_step(
        "cache_lookup",
        t0,
        extra=f"cache={cache_state}",
        report_date=normalized_report_date,
        allow_partial=allow_partial,
    )

    envelope = _HOME_SNAPSHOT_CACHE.get_or_set(
        cache_key,
        lambda: _compute_home_snapshot_envelope(
            report_date=normalized_report_date,
            allow_partial=allow_partial,
        ),
    )

    _log_home_snapshot_perf_step(
        "total",
        total_t0,
        extra=f"cache={cache_state}",
        report_date=normalized_report_date,
        allow_partial=allow_partial,
    )
    return deepcopy(envelope)


def warm_home_snapshot_cache_if_configured(settings: object) -> bool:
    if not bool(getattr(settings, "home_snapshot_prewarm_enabled", False)):
        _set_home_snapshot_prewarm_status(
            ok=False,
            status="disabled",
            report_date=None,
            allow_partial=False,
            last_duration_ms=None,
            last_step_durations_ms={},
            error=None,
        )
        return False
    _set_home_snapshot_prewarm_status(
        ok=False,
        status="warming",
        report_date=None,
        allow_partial=False,
        last_duration_ms=None,
        last_step_durations_ms={},
        error=None,
    )
    thread = threading.Thread(
        target=_warm_home_snapshot_cache_quietly,
        kwargs={"report_date": None, "allow_partial": False},
        daemon=True,
        name="moss-home-snapshot-warmup",
    )
    thread.start()
    return True


def warm_home_snapshot_cache_blocking_if_configured(settings: object) -> bool:
    if not bool(getattr(settings, "home_snapshot_prewarm_enabled", False)):
        _set_home_snapshot_prewarm_status(
            ok=False,
            status="disabled",
            report_date=None,
            allow_partial=False,
            last_duration_ms=None,
            last_step_durations_ms={},
            error=None,
        )
        return False
    _warm_home_snapshot_cache_quietly(report_date=None, allow_partial=False)
    return home_snapshot_prewarm_status().get("status") == "ready"


def _warm_home_snapshot_cache_quietly(
    *,
    report_date: str | None,
    allow_partial: bool,
) -> None:
    t0 = time.perf_counter()
    _set_home_snapshot_prewarm_status(
        ok=False,
        status="warming",
        report_date=report_date,
        allow_partial=allow_partial,
        last_duration_ms=None,
        last_step_durations_ms={},
        error=None,
    )
    logger.info(
        "home_snapshot_prewarm_start report_date=%s allow_partial=%s",
        report_date,
        allow_partial,
    )
    try:
        _start_home_snapshot_step_profile()
        home_snapshot_envelope(report_date=report_date, allow_partial=allow_partial)
    except Exception as exc:
        step_durations = _finish_home_snapshot_step_profile()
        _set_home_snapshot_prewarm_status(
            ok=False,
            status="failed",
            report_date=report_date,
            allow_partial=allow_partial,
            last_duration_ms=int((time.perf_counter() - t0) * 1000),
            last_step_durations_ms=step_durations,
            error=str(exc),
        )
        _logger.exception("home_snapshot_prewarm_failed")
        return
    step_durations = _finish_home_snapshot_step_profile()
    duration_ms = int((time.perf_counter() - t0) * 1000)
    _set_home_snapshot_prewarm_status(
        ok=True,
        status="ready",
        report_date=report_date,
        allow_partial=allow_partial,
        last_duration_ms=duration_ms,
        last_step_durations_ms=step_durations,
        error=None,
    )
    logger.info(
        "home_snapshot_prewarm_done ms=%d report_date=%s allow_partial=%s",
        duration_ms,
        report_date,
        allow_partial,
    )


def _build_home_snapshot_core_envelopes(
    *,
    target_date: str,
    date_context: dict[str, list[str]],
) -> tuple[dict[str, object], dict[str, object], int, int]:
    def timed_overview() -> tuple[dict[str, object], int]:
        started_at = time.perf_counter()
        envelope = executive_overview(
            report_date=target_date,
            date_context=date_context,
            history_points=_HOME_SNAPSHOT_OVERVIEW_HISTORY_POINTS,
        )
        return envelope, int((time.perf_counter() - started_at) * 1000)

    def timed_attribution() -> tuple[dict[str, object], int]:
        started_at = time.perf_counter()
        envelope = executive_pnl_attribution(report_date=target_date)
        return envelope, int((time.perf_counter() - started_at) * 1000)

    with ThreadPoolExecutor(max_workers=2) as executor:
        overview_future = executor.submit(timed_overview)
        attribution_future = executor.submit(timed_attribution)
        overview_env, overview_ms = overview_future.result()
        attribution_env, attribution_ms = attribution_future.result()
        return overview_env, attribution_env, overview_ms, attribution_ms


def _compute_home_snapshot_envelope(
    *,
    report_date: str | None = None,
    allow_partial: bool = False,
) -> dict[str, object]:
    """Build the authoritative home snapshot envelope.

    See ``docs/superpowers/specs/2026-04-18-frontend-numeric-correctness-design.md`` § 4.
    """
    compute_t0 = time.perf_counter()
    normalized = _normalize_report_date(report_date)

    step_t0 = time.perf_counter()
    date_context = _list_domain_date_context()
    _log_home_snapshot_perf_step(
        "date_context",
        step_t0,
        extra=f"domains={len(date_context)}",
        report_date=normalized,
        allow_partial=allow_partial,
    )

    step_t0 = time.perf_counter()
    domain_dates = _domain_dates_from_context(date_context)

    target_date, domains_missing, effective = _compute_unified_report_date(
        requested=normalized,
        allow_partial=allow_partial,
        domain_dates=domain_dates,
    )
    _log_home_snapshot_perf_step(
        "resolve_report_date",
        step_t0,
        extra=f"target_date={target_date or 'none'} missing={len(domains_missing)}",
        report_date=normalized,
        allow_partial=allow_partial,
    )

    if target_date is None:
        step_t0 = time.perf_counter()
        envelope = _envelope(
            "home.snapshot",
            _empty_home_snapshot_payload(),
            quality_flag="error",
            vendor_status="vendor_unavailable",
            source_version="sv_home_snapshot_empty_v1",
            filters_applied={
                "requested_report_date": normalized,
                "allow_partial": allow_partial,
                "effective_report_dates": {},
                "domains_missing": list(_HOME_SNAPSHOT_CALIBERS),
            },
        )
        _log_home_snapshot_perf_step(
            "envelope_build",
            step_t0,
            extra="target_date=none quality=error",
            report_date=normalized,
            allow_partial=allow_partial,
        )
        _log_home_snapshot_perf_step(
            "compute_total",
            compute_t0,
            extra="target_date=none",
            report_date=normalized,
            allow_partial=allow_partial,
        )
        return envelope

    step_t0 = time.perf_counter()
    overview_env, attribution_env, overview_ms, attribution_ms = _build_home_snapshot_core_envelopes(
        target_date=target_date,
        date_context=date_context,
    )
    _log_home_snapshot_perf_step(
        "executive_overview",
        step_t0,
        extra=f"target_date={target_date}",
        report_date=normalized,
        allow_partial=allow_partial,
        elapsed_ms=overview_ms,
    )

    step_t0 = time.perf_counter()
    _log_home_snapshot_perf_step(
        "executive_pnl_attribution",
        step_t0,
        extra=f"target_date={target_date}",
        report_date=normalized,
        allow_partial=allow_partial,
        elapsed_ms=attribution_ms,
    )

    step_t0 = time.perf_counter()
    overview_result = OverviewPayload.model_validate(overview_env["result"])
    attribution_result = PnlAttributionPayload.model_validate(attribution_env["result"])
    _log_home_snapshot_perf_step(
        "payload_validation",
        step_t0,
        extra=f"target_date={target_date}",
        report_date=normalized,
        allow_partial=allow_partial,
    )
    attention_count = len(domains_missing)
    partial_note = (
        "部分业务域不可用: " + ", ".join(domains_missing) if domains_missing else None
    )
    verdict = executive_verdict(
        overview=overview_result,
        attention_count=attention_count,
        partial_note=partial_note,
        client_mode="real",
    )
    step_t0 = time.perf_counter()
    (
        product_category_ytd,
        product_category_monthly,
        product_category_ytd_ms,
        product_category_monthly_ms,
    ) = _build_product_category_headlines(target_date)
    _log_home_snapshot_perf_step(
        "product_category_ytd",
        step_t0,
        extra=f"target_date={target_date} present={product_category_ytd is not None}",
        report_date=normalized,
        allow_partial=allow_partial,
        elapsed_ms=product_category_ytd_ms,
    )

    step_t0 = time.perf_counter()
    _log_home_snapshot_perf_step(
        "product_category_monthly",
        step_t0,
        extra=f"target_date={target_date} present={product_category_monthly is not None}",
        report_date=normalized,
        allow_partial=allow_partial,
        elapsed_ms=product_category_monthly_ms,
    )
    payload = HomeSnapshotPayload(
        report_date=target_date,
        mode="partial" if allow_partial else "strict",
        source_surface="executive_analytical",
        overview=overview_result,
        attribution=attribution_result,
        domains_missing=domains_missing,
        domains_effective_date=effective,
        verdict=verdict,
        product_category_ytd=product_category_ytd,
        product_category_monthly=product_category_monthly,
    )

    degraded_components: list[str] = []
    degraded_vendor_statuses: list[str] = []
    for component_name, component_envelope in (
        ("overview", overview_env),
        ("attribution", attribution_env),
    ):
        component_meta = component_envelope.get("result_meta")
        if not isinstance(component_meta, dict):
            continue
        component_quality = str(component_meta.get("quality_flag") or "").strip()
        component_vendor = str(component_meta.get("vendor_status") or "").strip()
        if (
            component_quality not in {"", "ok"}
            or component_vendor not in {"", "ok"}
        ):
            degraded_components.append(component_name)
        if component_vendor in {"vendor_stale", "vendor_unavailable"}:
            degraded_vendor_statuses.append(component_vendor)
    if product_category_ytd is None:
        degraded_components.append("product_category_ytd")
    if product_category_monthly is None:
        degraded_components.append("product_category_monthly")

    snapshot_degraded = bool(domains_missing or degraded_components)
    quality_flag: Literal["ok", "warning", "error", "stale"] = (
        "warning" if snapshot_degraded else "ok"
    )
    vendor_status: Literal["ok", "vendor_stale", "vendor_unavailable"] = (
        "vendor_unavailable"
        if domains_missing or "vendor_unavailable" in degraded_vendor_statuses
        else "vendor_stale"
        if "vendor_stale" in degraded_vendor_statuses
        else "ok"
    )

    step_t0 = time.perf_counter()
    envelope = _envelope(
        "home.snapshot",
        payload,
        quality_flag=quality_flag,
        vendor_status=vendor_status,
        source_version="sv_home_snapshot_v1",
        rule_version="rv_home_snapshot_v1",
        filters_applied={
            "requested_report_date": normalized,
            "allow_partial": allow_partial,
            "report_date": target_date,
            "effective_report_dates": effective,
            "domains_missing": domains_missing,
            "degraded_components": degraded_components,
        },
    )
    _log_home_snapshot_perf_step(
        "envelope_build",
        step_t0,
        extra=f"target_date={target_date} quality={quality_flag}",
        report_date=normalized,
        allow_partial=allow_partial,
    )
    _log_home_snapshot_perf_step(
        "compute_total",
        compute_t0,
        extra=f"target_date={target_date}",
        report_date=normalized,
        allow_partial=allow_partial,
    )
    return envelope
