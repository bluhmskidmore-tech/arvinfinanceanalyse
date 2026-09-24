"""Bond analytics dashboard — DuckDB aggregations with formal result envelopes."""
from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Literal

from backend.app.governance.formal_compute_lineage import (
    resolve_formal_dates_lineage,
    resolve_formal_facts_lineage,
)
from backend.app.governance.settings import get_settings
from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
from backend.app.schemas.bond_dashboard import (
    BondDashboardAssetStructurePayload,
    BondDashboardBundlePayload,
    BondDashboardBusinessTypeMetricsPayload,
    BondDashboardDatesPayload,
    BondDashboardHeadlinePayload,
    BondDashboardHomeSummaryPayload,
    BondDashboardIndustryDistributionPayload,
    BondDashboardMaturityStructurePayload,
    BondDashboardPortfolioComparisonPayload,
    BondDashboardRiskIndicatorsPayload,
    BondDashboardSpreadAnalysisPayload,
    BondDashboardYieldDistributionPayload,
)
from backend.app.schemas.common_numeric import null_numeric
from backend.app.services.bond_analytics_service import (
    get_dv01_risk,
    get_portfolio_headlines,
    get_top_holdings,
)
from backend.app.services.formal_result_runtime import (
    build_formal_result_envelope_from_lineage,
    build_result_envelope,
)
from backend.app.services.yield_curve_term_structure_service import (
    FACT_TABLE as YIELD_CURVE_FACT_TABLE,
)
from backend.app.services.yield_curve_term_structure_service import (
    get_yield_curve_term_structure,
    parse_curve_types_param,
)
from pydantic import BaseModel

# Mirrors `FormalComputeModuleDescriptor` for bond_analytics materialize (avoid importing tasks module).
BOND_ANALYTICS_JOB_NAME = "bond_analytics_materialize"
BOND_ANALYTICS_CACHE_KEY = "bond_analytics:materialize:formal"
BOND_ANALYTICS_RULE_VERSION = "rv_bond_analytics_formal_materialize_v2"
BOND_ANALYTICS_CACHE_VERSION = f"cv_bond_analytics_formal__{BOND_ANALYTICS_RULE_VERSION}"
EMPTY_SOURCE_VERSION = "sv_bond_analytics_empty"
BOND_DASHBOARD_BUNDLE_MAX_WORKERS = 6

# 口径：本服务读 `fact_formal_bond_analytics_daily`（zqtz 快照 → `compute_bond_analytics_rows` 物化）。
# 余额分析读 `fact_formal_zqtz_balance_daily` / `fact_formal_tyw_balance_daily`（`project_zqtz_formal_balance_row` 等），
# 且页面汇总可含同业(TYW)。两链路不同；同日 ZQTZ CNY 合计请用
# `python -m backend.scripts.diagnose_balance_calibration` 对比，勿在未实证前假设与余额分析总额一致。
BOND_DASHBOARD_DATA_SOURCE = "bond_analytics_facts"

Q8 = Decimal("0.00000001")

_GROUP_BY_LITERAL = Literal["bond_type", "rating", "portfolio_name", "tenor_bucket"]

BOND_DASHBOARD_DV01_BUNDLE_SECTIONS: dict[str, str] = {
    "dv01-risk": "all",
    "dv01-risk-ac": "AC",
    "dv01-risk-oci": "OCI",
    "dv01-risk-tpl": "TPL",
    "dv01-risk-all": "all",
}

BOND_DASHBOARD_ANALYTICS_BUNDLE_SECTIONS: frozenset[str] = frozenset(
    {
        "top-holdings",
        "portfolio-headlines",
        "yield-curve-term-structure",
        *BOND_DASHBOARD_DV01_BUNDLE_SECTIONS.keys(),
    }
)

BOND_DASHBOARD_BUNDLE_SECTIONS: frozenset[str] = frozenset(
    {
        "dates",
        "headline-kpis",
        "home-summary",
        "asset-structure",
        "asset-structure-rating",
        "asset-structure-portfolio-name",
        "asset-structure-tenor-bucket",
        "yield-distribution",
        "portfolio-comparison",
        "spread-analysis",
        "maturity-structure",
        "industry-distribution",
        "risk-indicators",
        "business-type-metrics",
        *BOND_DASHBOARD_ANALYTICS_BUNDLE_SECTIONS,
    }
)

BOND_DASHBOARD_BUNDLE_SECTIONS_REQUIRING_REPORT_DATE: frozenset[str] = frozenset(
    BOND_DASHBOARD_BUNDLE_SECTIONS - {"dates"}
)

_ASSET_STRUCTURE_BUNDLE_SECTION_GROUP_BY: dict[str, _GROUP_BY_LITERAL] = {
    "asset-structure": "bond_type",
    "asset-structure-rating": "rating",
    "asset-structure-portfolio-name": "portfolio_name",
    "asset-structure-tenor-bucket": "tenor_bucket",
}


class _TTLCache:
    def __init__(self, ttl_seconds: int = 300):
        self._store: dict[tuple, tuple[float, Any]] = {}
        self._lock = threading.Lock()
        self._ttl = ttl_seconds

    def get(self, key: tuple) -> tuple[bool, Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry and time.monotonic() - entry[0] < self._ttl:
                return True, entry[1]
            return False, None

    def set(self, key: tuple, value: Any) -> None:
        with self._lock:
            self._store[key] = (time.monotonic(), value)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


_report_dates_cache = _TTLCache(ttl_seconds=300)
_fact_rows_cache = _TTLCache(ttl_seconds=300)
_home_summary_cache = _TTLCache(ttl_seconds=300)
_fact_rows_fetch_locks: dict[tuple, threading.Lock] = {}
_fact_rows_fetch_locks_guard = threading.Lock()


def clear_bond_dashboard_runtime_cache() -> None:
    _report_dates_cache.clear()
    _fact_rows_cache.clear()
    _home_summary_cache.clear()
    with _fact_rows_fetch_locks_guard:
        _fact_rows_fetch_locks.clear()


def _duckdb_cache_version_token() -> tuple[str, int | None]:
    duckdb_path = str(get_settings().duckdb_path)
    try:
        return duckdb_path, Path(duckdb_path).stat().st_mtime_ns
    except OSError:
        return duckdb_path, None


def _report_dates() -> list[str]:
    key = (*_duckdb_cache_version_token(), "report_dates")
    hit, cached = _report_dates_cache.get(key)
    if hit:
        return cached
    report_dates = _repo().list_report_dates()
    _report_dates_cache.set(key, report_dates)
    return report_dates


def _fact_rows(report_date: str) -> list[dict[str, object]]:
    key = (*_duckdb_cache_version_token(), "fact_rows", report_date)
    hit, cached = _fact_rows_cache.get(key)
    if hit:
        return cached
    with _fact_rows_fetch_lock(key):
        hit, cached = _fact_rows_cache.get(key)
        if hit:
            return cached
        rows = _repo().fetch_bond_analytics_rows(report_date=report_date)
        _fact_rows_cache.set(key, rows)
        return rows


def _fact_rows_fetch_lock(key: tuple) -> threading.Lock:
    with _fact_rows_fetch_locks_guard:
        return _fact_rows_fetch_locks.setdefault(key, threading.Lock())


def _with_bond_dashboard_data_source(envelope: dict[str, object]) -> dict[str, object]:
    return {**envelope, "data_source": BOND_DASHBOARD_DATA_SOURCE}


def _typed_payload(schema: type[BaseModel], payload: dict[str, object]) -> dict[str, object]:
    return schema.model_validate(payload).model_dump(mode="json")


def _trace_id() -> str:
    return f"tr_{uuid.uuid4().hex[:12]}"


def _repo() -> BondAnalyticsRepository:
    return BondAnalyticsRepository(str(get_settings().duckdb_path))


def _amt(value: object) -> str:
    if value is None:
        v = Decimal("0")
    else:
        v = value if isinstance(value, Decimal) else Decimal(str(value))
    return format(v.quantize(Q8, rounding=ROUND_HALF_UP), "f")


def _rate(value: object) -> str:
    return _amt(value)


def _facts_lineage(report_date: str, rows: list[dict[str, object]]) -> dict[str, str]:
    return resolve_formal_facts_lineage(
        governance_dir=str(get_settings().governance_path),
        cache_key=BOND_ANALYTICS_CACHE_KEY,
        job_name=BOND_ANALYTICS_JOB_NAME,
        report_date=report_date,
        has_rows=bool(rows),
        row_source_versions=[
            str(row.get("source_version") or "").strip()
            for row in rows
        ],
        default_source_version=EMPTY_SOURCE_VERSION,
        default_rule_version=BOND_ANALYTICS_RULE_VERSION,
        default_cache_version=BOND_ANALYTICS_CACHE_VERSION,
    )


def _analytical_envelope(
    *,
    result_kind: str,
    report_date: str,
    result_payload: dict[str, object],
) -> dict[str, object]:
    rows = _fact_rows(report_date)
    lineage = _facts_lineage(report_date, rows)
    return _analytical_envelope_from_lineage(
        result_kind=result_kind,
        report_date=report_date,
        lineage=lineage,
        evidence_rows=len(rows),
        result_payload=result_payload,
    )


def _analytical_envelope_from_lineage(
    *,
    result_kind: str,
    report_date: str,
    lineage: dict[str, object],
    evidence_rows: int,
    result_payload: dict[str, object],
) -> dict[str, object]:
    return build_result_envelope(
        basis="analytical",
        trace_id=_trace_id(),
        result_kind=result_kind,
        cache_version=str(lineage["cache_version"]),
        source_version=str(lineage["source_version"]),
        rule_version=str(lineage["rule_version"]),
        vendor_version=str(lineage.get("vendor_version") or "vv_none"),
        # quality_flag 反映数据质量而非口径基准（口径由 basis=analytical +
        # formal_use_allowed=false 表达）。与 home-summary 及 bundle 外层同规则：
        # 有证据行为 ok、空数据为 warning。此前硬编码 "warning" 使前端首屏
        # 在数据健康时也常挂降级横幅。
        quality_flag="ok" if evidence_rows > 0 else "warning",
        source_surface="bond_analytics",
        requested_report_date=report_date,
        resolved_report_date=report_date,
        as_of_date=report_date,
        date_basis="bond_dashboard_report_date",
        filters_applied={"report_date": report_date},
        tables_used=["fact_formal_bond_analytics_daily"],
        evidence_rows=evidence_rows,
        result_payload=result_payload,
    )


class _BondDashboardBundleSharedReads:
    """Thread-safe per-bundle reads shared by section envelopes."""

    def __init__(self, report_date: date | None) -> None:
        self._report_date = report_date.isoformat() if report_date is not None else None
        self._lock = threading.RLock()
        self._fact_rows: list[dict[str, Any]] | None = None
        self._fact_rows_error: Exception | None = None
        self._lineage: dict[str, object] | None = None
        self._lineage_error: Exception | None = None
        self._prior_loaded = False
        self._prior: str | None = None
        self._prior_error: Exception | None = None
        self._headline: dict[str, object] | None = None
        self._headline_error: Exception | None = None

    def require_report_date(self) -> str:
        if self._report_date is None:
            raise ValueError("report_date is required for the requested bundle sections")
        return self._report_date

    def fact_rows(self) -> list[dict[str, Any]]:
        report_date = self.require_report_date()
        with self._lock:
            if self._fact_rows_error is not None:
                raise self._fact_rows_error
            if self._fact_rows is not None:
                return self._fact_rows
            try:
                self._fact_rows = _fact_rows(report_date)
            except Exception as exc:
                self._fact_rows_error = exc
                raise
            return self._fact_rows

    def lineage(self) -> dict[str, object]:
        report_date = self.require_report_date()
        with self._lock:
            if self._lineage_error is not None:
                raise self._lineage_error
            if self._lineage is not None:
                return self._lineage
            try:
                self._lineage = _facts_lineage(report_date, self.fact_rows())
            except Exception as exc:
                self._lineage_error = exc
                raise
            return self._lineage

    def evidence_rows(self) -> int:
        return len(self.fact_rows())

    def prior_report_date(self) -> str | None:
        report_date = self.require_report_date()
        with self._lock:
            if self._prior_error is not None:
                raise self._prior_error
            if self._prior_loaded:
                return self._prior
            try:
                self._prior = _prior_report_date(report_date)
            except Exception as exc:
                self._prior_error = exc
                raise
            self._prior_loaded = True
            return self._prior

    def headline_raw(self) -> dict[str, object]:
        report_date = self.require_report_date()
        with self._lock:
            if self._headline_error is not None:
                raise self._headline_error
            if self._headline is not None:
                return self._headline
            try:
                self._headline = _repo().fetch_dashboard_headline_kpis(
                    report_date,
                    prev_report_date=self.prior_report_date(),
                )
            except Exception as exc:
                self._headline_error = exc
                raise
            return self._headline


def _analytical_envelope_from_bundle_shared_reads(
    *,
    shared_reads: _BondDashboardBundleSharedReads,
    result_kind: str,
    result_payload: dict[str, object],
) -> dict[str, object]:
    return _analytical_envelope_from_lineage(
        result_kind=result_kind,
        report_date=shared_reads.require_report_date(),
        lineage=shared_reads.lineage(),
        evidence_rows=shared_reads.evidence_rows(),
        result_payload=result_payload,
    )


def _bond_dashboard_bundle_shared_section_envelope(
    *,
    shared_reads: _BondDashboardBundleSharedReads,
    result_kind: str,
    result_payload: dict[str, object],
) -> dict[str, object]:
    return _with_bond_dashboard_data_source(
        _analytical_envelope_from_bundle_shared_reads(
            shared_reads=shared_reads,
            result_kind=result_kind,
            result_payload=result_payload,
        )
    )


def _prior_report_date(report_date: str) -> str | None:
    dates = _report_dates()
    if report_date not in dates:
        return None
    idx = dates.index(report_date)
    if idx + 1 >= len(dates):
        return None
    return dates[idx + 1]


def _to_dec(value: object) -> Decimal:
    if value is None:
        return Decimal("0")
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _pct_str(part: Decimal, whole: Decimal) -> str:
    if whole <= 0:
        return format(Decimal("0").quantize(Q8, rounding=ROUND_HALF_UP), "f")
    return format((part / whole).quantize(Q8, rounding=ROUND_HALF_UP), "f")


def _kpi_block_from_row(row: dict[str, Any]) -> dict[str, object]:
    med = row.get("credit_spread_median")
    weighted_ytm = row.get("weighted_ytm")
    weighted_duration = row.get("weighted_duration")
    return {
        "total_market_value": _amt(row["total_market_value"]),
        "unrealized_pnl": _amt(row.get("unrealized_pnl", Decimal("0"))),
        "weighted_ytm": (
            _rate(weighted_ytm)
            if weighted_ytm is not None
            else null_numeric(unit="pct", sign_aware=True).model_dump(mode="json")
        ),
        "weighted_duration": (
            _rate(weighted_duration)
            if weighted_duration is not None
            else null_numeric(unit="ratio", sign_aware=False).model_dump(mode="json")
        ),
        "weighted_coupon": _rate(row["weighted_coupon"]),
        "credit_spread_median": (
            _rate(med)
            if med is not None
            else null_numeric(unit="pct", sign_aware=True).model_dump(mode="json")
        ),
        "total_dv01": _amt(row["total_dv01"]),
        "bond_count": int(row["bond_count"]),
    }


def get_bond_dashboard_dates() -> dict[str, object]:
    report_dates = _report_dates()
    return _with_bond_dashboard_data_source(
        build_formal_result_envelope_from_lineage(
            trace_id=_trace_id(),
            result_kind="bond_dashboard.dates",
            lineage=_dates_lineage(report_dates),
            default_cache_version=BOND_ANALYTICS_CACHE_VERSION,
            quality_flag="ok" if report_dates else "warning",
            source_surface="bond_analytics",
            result_payload=_typed_payload(
                BondDashboardDatesPayload,
                {"report_dates": report_dates},
            ),
        )
    )


def _dates_lineage(report_dates: list[str] | None = None) -> dict[str, str]:
    report_dates = _report_dates() if report_dates is None else report_dates
    return resolve_formal_dates_lineage(
        governance_dir=str(get_settings().governance_path),
        cache_key=BOND_ANALYTICS_CACHE_KEY,
        report_dates=report_dates,
        default_source_version=EMPTY_SOURCE_VERSION,
        default_rule_version=BOND_ANALYTICS_RULE_VERSION,
        default_cache_version=BOND_ANALYTICS_CACHE_VERSION,
        fallback_lineage_loader=lambda report_date: _facts_lineage(
            report_date,
            _fact_rows(report_date),
        ),
    )


def get_bond_dashboard_headline_kpis(report_date: date) -> dict[str, object]:
    rd = report_date.isoformat()
    prior = _prior_report_date(rd)
    raw = _repo().fetch_dashboard_headline_kpis(rd, prev_report_date=prior)
    fact_rows = _fact_rows(rd)
    lineage = _facts_lineage(rd, fact_rows)
    return _with_bond_dashboard_data_source(
        _analytical_envelope_from_lineage(
            result_kind="bond_dashboard.headline_kpis",
            report_date=rd,
            lineage=lineage,
            evidence_rows=len(fact_rows),
            result_payload=_bond_dashboard_headline_payload(rd, prior, raw),
        )
    )


def _bond_dashboard_headline_payload(
    report_date: str,
    prior_report_date: str | None,
    raw: dict[str, object] | None = None,
) -> dict[str, object]:
    raw = raw or _repo().fetch_dashboard_headline_kpis(
        report_date,
        prev_report_date=prior_report_date,
    )
    cur_row = raw["current"]
    prev_row = raw["previous"]
    return _typed_payload(
        BondDashboardHeadlinePayload,
        {
            "report_date": report_date,
            "prev_report_date": prior_report_date,
            "kpis": _kpi_block_from_row(cur_row),
            "prev_kpis": _kpi_block_from_row(prev_row) if prev_row is not None else None,
        },
    )


def get_bond_dashboard_business_type_metrics(report_date: date) -> dict[str, object]:
    """Analytical envelope: weighted metrics by bond_type / business bucket."""
    rd = report_date.isoformat()
    payload = _bond_dashboard_business_type_payload(rd)
    return _with_bond_dashboard_data_source(
        _analytical_envelope(
            result_kind="bond_dashboard.business_type_metrics",
            report_date=rd,
            result_payload=payload,
        )
    )


def _bond_dashboard_business_type_payload(report_date: str) -> dict[str, object]:
    rows = _repo().fetch_business_type_metrics(report_date)
    items: list[dict[str, object]] = []
    for r in rows:
        w_ytm = r.get("weighted_avg_ytm")
        w_dur = r.get("weighted_avg_duration")
        # 缺失≠0（repo 聚合以 nullif 输出 NULL 表示零覆盖）：无覆盖的指标输出空串，
        # 前端按缺值渲染 EM_DASH；此前硬编码 "0.00000000" 会被当成真实零展示。
        ytm_pct_str = (
            format((_to_dec(w_ytm) * Decimal("100")).quantize(Q8, rounding=ROUND_HALF_UP), "f")
            if w_ytm is not None
            else ""
        )
        ytm_cov = r.get("weighted_avg_ytm_coverage_ratio")
        dur_cov = r.get("weighted_avg_duration_coverage_ratio")
        items.append(
            {
                "name": str(r.get("name") or ""),
                "market_value": _amt(r.get("market_value")),
                "weighted_avg_ytm_pct": ytm_pct_str,
                "weighted_avg_duration": _rate(w_dur) if w_dur is not None else "",
                "duration_source": "",
                # 覆盖率为质量披露：组市值为零时分母不存在（repo nullif 输出 NULL）→ null。
                "weighted_avg_ytm_coverage_ratio": _rate(ytm_cov) if ytm_cov is not None else None,
                "weighted_avg_duration_coverage_ratio": _rate(dur_cov) if dur_cov is not None else None,
            }
        )
    return _typed_payload(
        BondDashboardBusinessTypeMetricsPayload,
        {"report_date": report_date, "items": items},
    )


def get_bond_dashboard_home_summary(report_date: date) -> dict[str, object]:
    rd = report_date.isoformat()
    payload, lineage, evidence_rows = _bond_dashboard_home_summary_components(rd)
    return _with_bond_dashboard_data_source(
        build_result_envelope(
            basis="analytical",
            trace_id=_trace_id(),
            result_kind="bond_dashboard.home_summary",
            cache_version=str(lineage["cache_version"]),
            source_version=str(lineage["source_version"]),
            rule_version=str(lineage["rule_version"]),
            vendor_version=str(lineage.get("vendor_version") or "vv_none"),
            quality_flag="ok" if evidence_rows > 0 else "warning",
            source_surface="bond_analytics",
            requested_report_date=rd,
            resolved_report_date=rd,
            as_of_date=rd,
            date_basis="bond_dashboard_report_date",
            filters_applied={"report_date": rd},
            tables_used=["fact_formal_bond_analytics_daily"],
            evidence_rows=evidence_rows,
            result_payload=payload,
        )
    )


def _bond_dashboard_home_summary_components(
    report_date: str,
) -> tuple[dict[str, object], dict[str, str], int]:
    key = (*_duckdb_cache_version_token(), "home_summary", report_date)
    hit, cached = _home_summary_cache.get(key)
    if hit:
        return cached

    rd = report_date
    prior = _prior_report_date(rd)
    headline_raw = _repo().fetch_dashboard_headline_kpis(rd, prev_report_date=prior)
    headline_payload = _bond_dashboard_headline_payload(rd, prior, headline_raw)
    risk_payload = _bond_dashboard_risk_payload(rd)
    asset_type = _bond_dashboard_asset_structure_payload(rd, "bond_type")
    asset_rating = _bond_dashboard_asset_structure_payload(rd, "rating")
    maturity = _bond_dashboard_maturity_payload(rd)
    industry = _bond_dashboard_industry_payload(rd, 10)
    yield_distribution = _bond_dashboard_yield_distribution_payload(
        rd,
        weighted_ytm=headline_raw["current"]["weighted_ytm"],
    )
    portfolio_comparison = _bond_dashboard_portfolio_payload(rd)
    spread = _bond_dashboard_spread_payload(rd)
    business_type = _bond_dashboard_business_type_payload(rd)

    fact_rows = _fact_rows(rd)
    lineage = _facts_lineage(rd, fact_rows)
    payload = _typed_payload(
        BondDashboardHomeSummaryPayload,
        {
            "report_date": rd,
            "headline": headline_payload,
            "risk": risk_payload,
            "asset_type": asset_type,
            "asset_rating": asset_rating,
            "maturity": maturity,
            "industry": industry,
            "yield_distribution": yield_distribution,
            "portfolio_comparison": portfolio_comparison,
            "spread": spread,
            "business_type": business_type,
        },
    )
    components = (payload, lineage, len(fact_rows))
    _home_summary_cache.set(key, components)
    return components


def get_bond_dashboard_asset_structure(
    report_date: date,
    group_by: _GROUP_BY_LITERAL,
) -> dict[str, object]:
    rd = report_date.isoformat()
    payload = _bond_dashboard_asset_structure_payload(rd, group_by)
    return _with_bond_dashboard_data_source(
        _analytical_envelope(
            result_kind="bond_dashboard.asset_structure",
            report_date=rd,
            result_payload=payload,
        )
    )


def _bond_dashboard_asset_structure_payload(
    report_date: str,
    group_by: _GROUP_BY_LITERAL,
) -> dict[str, object]:
    rows = _repo().fetch_dashboard_asset_structure(report_date, group_by=group_by)
    tot = sum((_to_dec(r["total_market_value"]) for r in rows), Decimal("0"))
    items: list[dict[str, object]] = []
    for r in rows:
        mv = _to_dec(r["total_market_value"])
        items.append(
            {
                "category": r["category"],
                "total_market_value": _amt(mv),
                "bond_count": r["bond_count"],
                "percentage": _pct_str(mv, tot),
            }
        )
    payload = {
        "report_date": report_date,
        "group_by": group_by,
        "items": items,
        "total_market_value": _amt(tot),
    }
    return _typed_payload(BondDashboardAssetStructurePayload, payload)


def get_bond_dashboard_yield_distribution(report_date: date) -> dict[str, object]:
    rd = report_date.isoformat()
    payload = _bond_dashboard_yield_distribution_payload(rd)
    return _with_bond_dashboard_data_source(
        _analytical_envelope(
            result_kind="bond_dashboard.yield_distribution",
            report_date=rd,
            result_payload=payload,
        )
    )


def _bond_dashboard_yield_distribution_payload(
    report_date: str,
    *,
    weighted_ytm: object | None = None,
) -> dict[str, object]:
    rows = _repo().fetch_dashboard_yield_distribution(report_date)
    if weighted_ytm is None:
        head = _repo().fetch_dashboard_headline_kpis(report_date, prev_report_date=None)
        weighted_ytm = head["current"]["weighted_ytm"]
    items = [
        {
            "yield_bucket": r["yield_bucket"],
            "total_market_value": _amt(r["total_market_value"]),
            "bond_count": r["bond_count"],
        }
        for r in rows
    ]
    payload = {"report_date": report_date, "items": items, "weighted_ytm": _rate(weighted_ytm)}
    return _typed_payload(BondDashboardYieldDistributionPayload, payload)


def get_bond_dashboard_portfolio_comparison(report_date: date) -> dict[str, object]:
    rd = report_date.isoformat()
    payload = _bond_dashboard_portfolio_payload(rd)
    return _with_bond_dashboard_data_source(
        _analytical_envelope(
            result_kind="bond_dashboard.portfolio_comparison",
            report_date=rd,
            result_payload=payload,
        )
    )


def _bond_dashboard_portfolio_payload(report_date: str) -> dict[str, object]:
    rows = _repo().fetch_dashboard_portfolio_comparison(report_date)
    items = [
        {
            "portfolio_name": r["portfolio_name"],
            "total_market_value": _amt(r["total_market_value"]),
            "weighted_ytm": _rate(r["weighted_ytm"]),
            "weighted_duration": _rate(r["weighted_duration"]),
            "total_dv01": _amt(r["total_dv01"]),
            "bond_count": r["bond_count"],
        }
        for r in rows
    ]
    return _typed_payload(
        BondDashboardPortfolioComparisonPayload,
        {"report_date": report_date, "items": items},
    )


def get_bond_dashboard_spread_analysis(report_date: date) -> dict[str, object]:
    rd = report_date.isoformat()
    payload = _bond_dashboard_spread_payload(rd)
    return _with_bond_dashboard_data_source(
        _analytical_envelope(
            result_kind="bond_dashboard.spread_analysis",
            report_date=rd,
            result_payload=payload,
        )
    )


def _bond_dashboard_spread_payload(report_date: str) -> dict[str, object]:
    rows = _repo().fetch_dashboard_spread_by_bond_type(report_date)
    items = [
        {
            "bond_type": r["bond_type"],
            # 缺失≠0：无 YTM 覆盖的券种中位数输出 null（schema 本就可空），
            # 此前硬编码 "0.00000000" 会被当成真实零展示。
            "median_yield": _rate(r["median_yield"]) if r["median_yield"] is not None else None,
            "bond_count": r["bond_count"],
            "total_market_value": _amt(r["total_market_value"]),
        }
        for r in rows
    ]
    return _typed_payload(
        BondDashboardSpreadAnalysisPayload,
        {"report_date": report_date, "items": items},
    )


def get_bond_dashboard_maturity_structure(report_date: date) -> dict[str, object]:
    rd = report_date.isoformat()
    payload = _bond_dashboard_maturity_payload(rd)
    return _with_bond_dashboard_data_source(
        _analytical_envelope(
            result_kind="bond_dashboard.maturity_structure",
            report_date=rd,
            result_payload=payload,
        )
    )


def _bond_dashboard_maturity_payload(report_date: str) -> dict[str, object]:
    rows = _repo().fetch_dashboard_maturity_structure(report_date)
    tot = sum((_to_dec(r["total_market_value"]) for r in rows), Decimal("0"))
    items = []
    for r in rows:
        mv = _to_dec(r["total_market_value"])
        items.append(
            {
                "maturity_bucket": r["maturity_bucket"],
                "total_market_value": _amt(mv),
                "bond_count": r["bond_count"],
                "percentage": _pct_str(mv, tot),
            }
        )
    return _typed_payload(
        BondDashboardMaturityStructurePayload,
        {"report_date": report_date, "items": items, "total_market_value": _amt(tot)},
    )


def get_bond_dashboard_industry_distribution(report_date: date, top_n: int) -> dict[str, object]:
    rd = report_date.isoformat()
    payload = _bond_dashboard_industry_payload(rd, top_n)
    return _with_bond_dashboard_data_source(
        _analytical_envelope(
            result_kind="bond_dashboard.industry_distribution",
            report_date=rd,
            result_payload=payload,
        )
    )


def _bond_dashboard_industry_payload(report_date: str, top_n: int) -> dict[str, object]:
    rows = _repo().fetch_dashboard_industry_distribution(report_date, top_n=top_n)
    tot = sum((_to_dec(r["total_market_value"]) for r in rows), Decimal("0"))
    items = []
    for r in rows:
        mv = _to_dec(r["total_market_value"])
        items.append(
            {
                "industry_name": r["industry_name"],
                "total_market_value": _amt(mv),
                "bond_count": r["bond_count"],
                "percentage": _pct_str(mv, tot),
            }
        )
    return _typed_payload(
        BondDashboardIndustryDistributionPayload,
        {"report_date": report_date, "items": items},
    )


def get_bond_dashboard_risk_indicators(report_date: date) -> dict[str, object]:
    rd = report_date.isoformat()
    payload = _bond_dashboard_risk_payload(rd)
    return _with_bond_dashboard_data_source(
        _analytical_envelope(
            result_kind="bond_dashboard.risk_indicators",
            report_date=rd,
            result_payload=payload,
        )
    )


def _bond_dashboard_risk_payload(report_date: str) -> dict[str, object]:
    row = _repo().fetch_dashboard_risk_indicators(report_date)
    convexity_coverage = row["weighted_convexity_coverage_ratio"]
    payload = {
        "report_date": report_date,
        "total_market_value": _amt(row["total_market_value"]),
        "total_dv01": _amt(row["total_dv01"]),
        "weighted_duration": _rate(row["weighted_duration"]),
        "credit_ratio": _rate(row["credit_ratio"]),
        # 覆盖率为 0 时 repo 的聚合兜底值 0 不是业务观测值；用 Numeric.raw=null
        # 保留「无覆盖」语义。显式零凸性且有覆盖时仍按真实 0 输出。
        "weighted_convexity": (
            null_numeric(unit="ratio", sign_aware=False).model_dump(mode="json")
            if _to_dec(convexity_coverage) == 0
            else _rate(row["weighted_convexity"])
        ),
        "total_spread_dv01": _amt(row["total_spread_dv01"]),
        "reinvestment_ratio_1y": _rate(row["reinvestment_ratio_1y"]),
        "weighted_convexity_coverage_ratio": _rate(convexity_coverage),
    }
    return _typed_payload(BondDashboardRiskIndicatorsPayload, payload)


def _normalize_bond_dashboard_bundle_sections(sections: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in sections:
        for part in str(raw).split(","):
            section = part.strip()
            if not section or section in seen:
                continue
            normalized.append(section)
            seen.add(section)
    if not normalized:
        raise ValueError("sections must include at least one supported section id")
    unknown = [section for section in normalized if section not in BOND_DASHBOARD_BUNDLE_SECTIONS]
    if unknown:
        raise ValueError(
            "unsupported bond-dashboard bundle sections: "
            + ", ".join(sorted(unknown))
        )
    return normalized


def _bond_dashboard_bundle_section_envelope(
    section: str,
    report_date: date | None,
    *,
    industry_top_n: int,
    analytics_top_n: int,
    dv01_top_n: int,
    dv01_shock_bps: str,
    dv01_accounting_class: str,
    curve_types: str,
    shared_reads: _BondDashboardBundleSharedReads | None = None,
) -> dict[str, object]:
    if section == "dates":
        return get_bond_dashboard_dates()
    if report_date is None:
        raise ValueError("report_date is required for the requested bundle sections")
    if section == "headline-kpis":
        if shared_reads is not None:
            rd = shared_reads.require_report_date()
            return _bond_dashboard_bundle_shared_section_envelope(
                shared_reads=shared_reads,
                result_kind="bond_dashboard.headline_kpis",
                result_payload=_bond_dashboard_headline_payload(
                    rd,
                    shared_reads.prior_report_date(),
                    shared_reads.headline_raw(),
                ),
            )
        return get_bond_dashboard_headline_kpis(report_date)
    if section == "home-summary":
        return get_bond_dashboard_home_summary(report_date)
    if section in _ASSET_STRUCTURE_BUNDLE_SECTION_GROUP_BY:
        if shared_reads is not None:
            rd = shared_reads.require_report_date()
            return _bond_dashboard_bundle_shared_section_envelope(
                shared_reads=shared_reads,
                result_kind="bond_dashboard.asset_structure",
                result_payload=_bond_dashboard_asset_structure_payload(
                    rd,
                    _ASSET_STRUCTURE_BUNDLE_SECTION_GROUP_BY[section],
                ),
            )
        return get_bond_dashboard_asset_structure(
            report_date,
            _ASSET_STRUCTURE_BUNDLE_SECTION_GROUP_BY[section],
        )
    if section == "yield-distribution":
        if shared_reads is not None:
            rd = shared_reads.require_report_date()
            headline = shared_reads.headline_raw()
            current_headline = headline["current"]
            return _bond_dashboard_bundle_shared_section_envelope(
                shared_reads=shared_reads,
                result_kind="bond_dashboard.yield_distribution",
                result_payload=_bond_dashboard_yield_distribution_payload(
                    rd,
                    weighted_ytm=current_headline["weighted_ytm"],
                ),
            )
        return get_bond_dashboard_yield_distribution(report_date)
    if section == "portfolio-comparison":
        if shared_reads is not None:
            rd = shared_reads.require_report_date()
            return _bond_dashboard_bundle_shared_section_envelope(
                shared_reads=shared_reads,
                result_kind="bond_dashboard.portfolio_comparison",
                result_payload=_bond_dashboard_portfolio_payload(rd),
            )
        return get_bond_dashboard_portfolio_comparison(report_date)
    if section == "spread-analysis":
        if shared_reads is not None:
            rd = shared_reads.require_report_date()
            return _bond_dashboard_bundle_shared_section_envelope(
                shared_reads=shared_reads,
                result_kind="bond_dashboard.spread_analysis",
                result_payload=_bond_dashboard_spread_payload(rd),
            )
        return get_bond_dashboard_spread_analysis(report_date)
    if section == "maturity-structure":
        if shared_reads is not None:
            rd = shared_reads.require_report_date()
            return _bond_dashboard_bundle_shared_section_envelope(
                shared_reads=shared_reads,
                result_kind="bond_dashboard.maturity_structure",
                result_payload=_bond_dashboard_maturity_payload(rd),
            )
        return get_bond_dashboard_maturity_structure(report_date)
    if section == "industry-distribution":
        if shared_reads is not None:
            rd = shared_reads.require_report_date()
            return _bond_dashboard_bundle_shared_section_envelope(
                shared_reads=shared_reads,
                result_kind="bond_dashboard.industry_distribution",
                result_payload=_bond_dashboard_industry_payload(rd, industry_top_n),
            )
        return get_bond_dashboard_industry_distribution(report_date, industry_top_n)
    if section == "risk-indicators":
        if shared_reads is not None:
            rd = shared_reads.require_report_date()
            return _bond_dashboard_bundle_shared_section_envelope(
                shared_reads=shared_reads,
                result_kind="bond_dashboard.risk_indicators",
                result_payload=_bond_dashboard_risk_payload(rd),
            )
        return get_bond_dashboard_risk_indicators(report_date)
    if section == "business-type-metrics":
        if shared_reads is not None:
            rd = shared_reads.require_report_date()
            return _bond_dashboard_bundle_shared_section_envelope(
                shared_reads=shared_reads,
                result_kind="bond_dashboard.business_type_metrics",
                result_payload=_bond_dashboard_business_type_payload(rd),
            )
        return get_bond_dashboard_business_type_metrics(report_date)
    if section == "top-holdings":
        return get_top_holdings(report_date, top_n=analytics_top_n)
    if section == "portfolio-headlines":
        return get_portfolio_headlines(report_date)
    if section in BOND_DASHBOARD_DV01_BUNDLE_SECTIONS:
        accounting_class = (
            dv01_accounting_class
            if section == "dv01-risk"
            else BOND_DASHBOARD_DV01_BUNDLE_SECTIONS[section]
        )
        return get_dv01_risk(
            report_date,
            accounting_class=accounting_class,
            top_n=dv01_top_n,
            shock_bps=dv01_shock_bps,
        )
    if section == "yield-curve-term-structure":
        return get_yield_curve_term_structure(
            report_date=report_date,
            curve_types=parse_curve_types_param(curve_types),
        )
    raise ValueError(f"unsupported bond-dashboard bundle section: {section}")


def _safe_bond_dashboard_bundle_section_envelope(
    section: str,
    report_date: date | None,
    *,
    industry_top_n: int,
    analytics_top_n: int,
    dv01_top_n: int,
    dv01_shock_bps: str,
    dv01_accounting_class: str,
    curve_types: str,
    shared_reads: _BondDashboardBundleSharedReads | None = None,
) -> tuple[dict[str, object] | None, dict[str, str | float | None]]:
    started_at = time.perf_counter()
    try:
        envelope = _bond_dashboard_bundle_section_envelope(
            section,
            report_date,
            industry_top_n=industry_top_n,
            analytics_top_n=analytics_top_n,
            dv01_top_n=dv01_top_n,
            dv01_shock_bps=dv01_shock_bps,
            dv01_accounting_class=dv01_accounting_class,
            curve_types=curve_types,
            shared_reads=shared_reads,
        )
    except Exception as exc:
        return None, {
            "status": "error",
            "message": str(exc) or exc.__class__.__name__,
            "duration_ms": round((time.perf_counter() - started_at) * 1000, 3),
        }
    return envelope, {
        "status": "ok",
        "message": None,
        "duration_ms": round((time.perf_counter() - started_at) * 1000, 3),
    }


def get_bond_dashboard_bundle(
    *,
    sections: list[str],
    report_date: date | None = None,
    industry_top_n: int = 10,
    analytics_top_n: int = 10,
    dv01_top_n: int = 1,
    dv01_shock_bps: str = "1",
    dv01_accounting_class: str = "all",
    curve_types: str = "treasury,cdb",
) -> dict[str, object]:
    """Aggregate existing bond-dashboard section envelopes in one response."""
    normalized_sections = _normalize_bond_dashboard_bundle_sections(sections)
    needs_report_date = any(
        section in BOND_DASHBOARD_BUNDLE_SECTIONS_REQUIRING_REPORT_DATE
        for section in normalized_sections
    )
    if needs_report_date and report_date is None:
        raise ValueError("report_date is required for the requested bundle sections")

    section_envelopes: dict[str, dict[str, object]] = {}
    section_statuses: dict[str, dict[str, str | float | None]] = {}
    failed_sections: list[str] = []
    shared_reads = _BondDashboardBundleSharedReads(report_date) if report_date is not None else None

    def load_section(section: str) -> tuple[str, dict[str, object] | None, dict[str, str | float | None]]:
        envelope, status = _safe_bond_dashboard_bundle_section_envelope(
            section,
            report_date,
            industry_top_n=industry_top_n,
            analytics_top_n=analytics_top_n,
            dv01_top_n=dv01_top_n,
            dv01_shock_bps=dv01_shock_bps,
            dv01_accounting_class=dv01_accounting_class,
            curve_types=curve_types,
            shared_reads=shared_reads,
        )
        return section, envelope, status

    max_workers = min(len(normalized_sections), BOND_DASHBOARD_BUNDLE_MAX_WORKERS)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        loaded_sections = list(executor.map(load_section, normalized_sections))

    for section, envelope, status in loaded_sections:
        section_statuses[section] = status
        if envelope is None:
            failed_sections.append(section)
            continue
        section_envelopes[section] = envelope

    rd = report_date.isoformat() if report_date is not None else None
    if rd is not None:
        if shared_reads is None:
            raise ValueError("report_date is required for the requested bundle sections")
        lineage = shared_reads.lineage()
        evidence_rows = shared_reads.evidence_rows()
        quality_flag = "warning" if failed_sections or evidence_rows <= 0 else "ok"
        basis = "analytical"
        filters_applied: dict[str, object] = {
            "report_date": rd,
            "sections": normalized_sections,
        }
        if "industry-distribution" in normalized_sections:
            filters_applied["industry_top_n"] = industry_top_n
        if "top-holdings" in normalized_sections:
            filters_applied["analytics_top_n"] = analytics_top_n
        if any(section in BOND_DASHBOARD_DV01_BUNDLE_SECTIONS for section in normalized_sections):
            filters_applied["dv01_top_n"] = dv01_top_n
            filters_applied["dv01_shock_bps"] = dv01_shock_bps
        if "dv01-risk" in normalized_sections:
            filters_applied["dv01_accounting_class"] = dv01_accounting_class
        if "yield-curve-term-structure" in normalized_sections:
            filters_applied["curve_types"] = curve_types
        tables_used = ["fact_formal_bond_analytics_daily"]
        if "yield-curve-term-structure" in normalized_sections:
            tables_used.append(YIELD_CURVE_FACT_TABLE)
    else:
        lineage = _dates_lineage()
        evidence_rows = 0
        quality_flag = "warning"
        basis = "formal"
        filters_applied = {"sections": normalized_sections}
        tables_used = []

    payload = _typed_payload(
        BondDashboardBundlePayload,
        {
            "report_date": rd,
            "requested_sections": normalized_sections,
            "sections": section_envelopes,
            "section_statuses": section_statuses,
            "failed_sections": failed_sections,
        },
    )
    envelope = build_result_envelope(
        basis=basis,
        trace_id=_trace_id(),
        result_kind="bond_dashboard.bundle",
        cache_version=str(lineage["cache_version"]),
        source_version=str(lineage["source_version"]),
        rule_version=str(lineage["rule_version"]),
        vendor_version=str(lineage.get("vendor_version") or "vv_none"),
        quality_flag=quality_flag,
        source_surface="bond_analytics",
        requested_report_date=rd,
        resolved_report_date=rd,
        as_of_date=rd,
        date_basis="bond_dashboard_report_date" if rd is not None else "bond_dashboard_dates",
        filters_applied=filters_applied,
        tables_used=tables_used,
        evidence_rows=evidence_rows,
        result_payload=payload,
    )
    return _with_bond_dashboard_data_source(envelope)
