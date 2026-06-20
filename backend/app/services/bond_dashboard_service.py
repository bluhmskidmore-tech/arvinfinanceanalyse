"""Bond analytics dashboard — DuckDB aggregations with formal result envelopes."""
from __future__ import annotations

import threading
import time
import uuid
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
    BondDashboardBusinessTypeMetricsPayload,
    BondDashboardHeadlinePayload,
    BondDashboardHomeSummaryPayload,
    BondDashboardIndustryDistributionPayload,
    BondDashboardMaturityStructurePayload,
    BondDashboardPortfolioComparisonPayload,
    BondDashboardRiskIndicatorsPayload,
    BondDashboardSpreadAnalysisPayload,
    BondDashboardYieldDistributionPayload,
)
from backend.app.services.formal_result_runtime import (
    build_formal_result_envelope_from_lineage,
    build_result_envelope,
)
from pydantic import BaseModel

# Mirrors `FormalComputeModuleDescriptor` for bond_analytics materialize (avoid importing tasks module).
BOND_ANALYTICS_JOB_NAME = "bond_analytics_materialize"
BOND_ANALYTICS_CACHE_KEY = "bond_analytics:materialize:formal"
BOND_ANALYTICS_RULE_VERSION = "rv_bond_analytics_formal_materialize_v1"
BOND_ANALYTICS_CACHE_VERSION = f"cv_bond_analytics_formal__{BOND_ANALYTICS_RULE_VERSION}"
EMPTY_SOURCE_VERSION = "sv_bond_analytics_empty"

# 口径：本服务读 `fact_formal_bond_analytics_daily`（zqtz 快照 → `compute_bond_analytics_rows` 物化）。
# 余额分析读 `fact_formal_zqtz_balance_daily` / `fact_formal_tyw_balance_daily`（`project_zqtz_formal_balance_row` 等），
# 且页面汇总可含同业(TYW)。两链路不同；同日 ZQTZ CNY 合计请用
# `python -m backend.scripts.diagnose_balance_calibration` 对比，勿在未实证前假设与余额分析总额一致。
BOND_DASHBOARD_DATA_SOURCE = "bond_analytics_facts"

Q8 = Decimal("0.00000001")

_GROUP_BY_LITERAL = Literal["bond_type", "rating", "portfolio_name", "tenor_bucket"]


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


def clear_bond_dashboard_runtime_cache() -> None:
    _report_dates_cache.clear()
    _fact_rows_cache.clear()
    _home_summary_cache.clear()


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
    rows = _repo().fetch_bond_analytics_rows(report_date=report_date)
    _fact_rows_cache.set(key, rows)
    return rows


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
    return build_result_envelope(
        basis="analytical",
        trace_id=_trace_id(),
        result_kind=result_kind,
        cache_version=str(lineage["cache_version"]),
        source_version=str(lineage["source_version"]),
        rule_version=str(lineage["rule_version"]),
        vendor_version=str(lineage.get("vendor_version") or "vv_none"),
        quality_flag="warning",
        source_surface="bond_analytics",
        requested_report_date=report_date,
        resolved_report_date=report_date,
        as_of_date=report_date,
        date_basis="bond_dashboard_report_date",
        filters_applied={"report_date": report_date},
        tables_used=["fact_formal_bond_analytics_daily"],
        evidence_rows=len(rows),
        result_payload=result_payload,
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
    return {
        "total_market_value": _amt(row["total_market_value"]),
        "unrealized_pnl": _amt(row.get("unrealized_pnl", Decimal("0"))),
        "weighted_ytm": _rate(row["weighted_ytm"]),
        "weighted_duration": _rate(row["weighted_duration"]),
        "weighted_coupon": _rate(row["weighted_coupon"]),
        "credit_spread_median": _rate(med) if med is not None else "0.00000000",
        "total_dv01": _amt(row["total_dv01"]),
        "bond_count": int(row["bond_count"]),
    }


def get_bond_dashboard_dates() -> dict[str, object]:
    report_dates = _report_dates()
    return _with_bond_dashboard_data_source(
        build_formal_result_envelope_from_lineage(
            trace_id=_trace_id(),
            result_kind="bond_dashboard.dates",
            lineage=_dates_lineage(),
            default_cache_version=BOND_ANALYTICS_CACHE_VERSION,
            source_surface="bond_analytics",
            result_payload={"report_dates": report_dates},
        )
    )


def _dates_lineage() -> dict[str, str]:
    report_dates = _report_dates()
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
        build_result_envelope(
            basis="analytical",
            trace_id=_trace_id(),
            result_kind="bond_dashboard.headline_kpis",
            cache_version=str(lineage["cache_version"]),
            source_version=str(lineage["source_version"]),
            rule_version=str(lineage["rule_version"]),
            vendor_version=str(lineage.get("vendor_version") or "vv_none"),
            quality_flag="warning",
            source_surface="bond_analytics",
            requested_report_date=rd,
            resolved_report_date=rd,
            as_of_date=rd,
            date_basis="bond_dashboard_report_date",
            filters_applied={"report_date": rd},
            tables_used=["fact_formal_bond_analytics_daily"],
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
    rows = _repo().fetch_business_type_metrics(rd)
    items: list[dict[str, object]] = []
    for r in rows:
        mv = r.get("market_value")
        w_ytm = r.get("weighted_avg_ytm")
        w_dur = r.get("weighted_avg_duration")
        ytm_pct_str = (
            format((_to_dec(w_ytm) * Decimal("100")).quantize(Q8, rounding=ROUND_HALF_UP), "f")
            if w_ytm is not None
            else "0.00000000"
        )
        items.append(
            {
                "name": str(r.get("name") or ""),
                "market_value": _amt(mv),
                "weighted_avg_ytm_pct": ytm_pct_str,
                "weighted_avg_duration": _rate(w_dur) if w_dur is not None else "0.00000000",
                "duration_source": "",
            }
        )
    payload: dict[str, object] = {"report_date": rd, "items": items}
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
        ytm_pct_str = (
            format((_to_dec(w_ytm) * Decimal("100")).quantize(Q8, rounding=ROUND_HALF_UP), "f")
            if w_ytm is not None
            else "0.00000000"
        )
        items.append(
            {
                "name": str(r.get("name") or ""),
                "market_value": _amt(r.get("market_value")),
                "weighted_avg_ytm_pct": ytm_pct_str,
                "weighted_avg_duration": _rate(w_dur) if w_dur is not None else "0.00000000",
                "duration_source": "",
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
            quality_flag="warning",
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
            "median_yield": _rate(r["median_yield"]) if r["median_yield"] is not None else "0.00000000",
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
    payload = {
        "report_date": report_date,
        "total_market_value": _amt(row["total_market_value"]),
        "total_dv01": _amt(row["total_dv01"]),
        "weighted_duration": _rate(row["weighted_duration"]),
        "credit_ratio": _rate(row["credit_ratio"]),
        "weighted_convexity": _rate(row["weighted_convexity"]),
        "total_spread_dv01": _amt(row["total_spread_dv01"]),
        "reinvestment_ratio_1y": _rate(row["reinvestment_ratio_1y"]),
    }
    return _typed_payload(BondDashboardRiskIndicatorsPayload, payload)
