"""Bond analytics dashboard — DuckDB aggregations with formal result envelopes."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Literal

from backend.app.governance.formal_compute_lineage import resolve_formal_manifest_lineage
from backend.app.governance.settings import get_settings
from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, CACHE_MANIFEST_STREAM, GovernanceRepository
from backend.app.services.formal_result_runtime import build_formal_result_envelope, build_formal_result_meta

# Mirrors `FormalComputeModuleDescriptor` for bond_analytics materialize (avoid importing tasks module).
BOND_ANALYTICS_JOB_NAME = "bond_analytics_materialize"
BOND_ANALYTICS_CACHE_KEY = "bond_analytics:materialize:formal"
BOND_ANALYTICS_RULE_VERSION = "rv_bond_analytics_formal_materialize_v1"
BOND_ANALYTICS_CACHE_VERSION = f"cv_bond_analytics_formal__{BOND_ANALYTICS_RULE_VERSION}"
EMPTY_SOURCE_VERSION = "sv_bond_analytics_empty"

Q8 = Decimal("0.00000001")

_GROUP_BY_LITERAL = Literal["bond_type", "rating", "portfolio_name", "tenor_bucket"]


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
    governance = GovernanceRepository(base_dir=get_settings().governance_path)
    build_rows = [
        row
        for row in governance.read_all(CACHE_BUILD_RUN_STREAM)
        if str(row.get("cache_key")) == BOND_ANALYTICS_CACHE_KEY
        and str(row.get("job_name")) == BOND_ANALYTICS_JOB_NAME
        and str(row.get("status")) == "completed"
        and str(row.get("report_date")) == report_date
    ]
    if not rows and not build_rows:
        return {
            "source_version": EMPTY_SOURCE_VERSION,
            "rule_version": BOND_ANALYTICS_RULE_VERSION,
            "cache_version": BOND_ANALYTICS_CACHE_VERSION,
            "vendor_version": "vv_none",
        }
    manifest_rows = [
        row for row in governance.read_all(CACHE_MANIFEST_STREAM) if str(row.get("cache_key")) == BOND_ANALYTICS_CACHE_KEY
    ]
    latest_build = build_rows[-1] if build_rows else {}
    latest_manifest = manifest_rows[-1] if manifest_rows else {}
    row_source_versions = sorted(
        {str(row.get("source_version") or "").strip() for row in rows if str(row.get("source_version") or "").strip()}
    )
    return {
        "source_version": next(
            (
                value
                for value in (
                    str(latest_build.get("source_version") or "").strip(),
                    "__".join(row_source_versions),
                    EMPTY_SOURCE_VERSION,
                )
                if value
            ),
            EMPTY_SOURCE_VERSION,
        ),
        "rule_version": next(
            (
                value
                for value in (
                    str(latest_build.get("rule_version") or "").strip(),
                    str(latest_manifest.get("rule_version") or "").strip(),
                    BOND_ANALYTICS_RULE_VERSION,
                )
                if value
            ),
            BOND_ANALYTICS_RULE_VERSION,
        ),
        "cache_version": next(
            (
                value
                for value in (
                    str(latest_build.get("cache_version") or "").strip(),
                    str(latest_manifest.get("cache_version") or "").strip(),
                    BOND_ANALYTICS_CACHE_VERSION,
                )
                if value
            ),
            BOND_ANALYTICS_CACHE_VERSION,
        ),
        "vendor_version": next(
            (
                value
                for value in (
                    str(latest_build.get("vendor_version") or "").strip(),
                    str(latest_manifest.get("vendor_version") or "").strip(),
                    "vv_none",
                )
                if value
            ),
            "vv_none",
        ),
    }


def _meta(*, result_kind: str, report_date: str) -> object:
    repo = _repo()
    rows = repo.fetch_bond_analytics_rows(report_date=report_date)
    lineage = _facts_lineage(report_date, rows)
    return build_formal_result_meta(
        trace_id=_trace_id(),
        result_kind=result_kind,
        cache_version=lineage["cache_version"],
        source_version=lineage["source_version"],
        rule_version=lineage["rule_version"],
        vendor_version=lineage["vendor_version"],
    )


def _dates_meta() -> object:
    report_dates = _repo().list_report_dates()
    if report_dates:
        try:
            manifest = resolve_formal_manifest_lineage(
                governance_dir=str(get_settings().governance_path),
                cache_key=BOND_ANALYTICS_CACHE_KEY,
            )
            lineage = {
                "source_version": str(manifest["source_version"]),
                "rule_version": str(manifest["rule_version"]),
                "cache_version": str(manifest.get("cache_version") or "").strip() or BOND_ANALYTICS_CACHE_VERSION,
                "vendor_version": str(manifest.get("vendor_version") or "").strip() or "vv_none",
            }
        except RuntimeError:
            rows = _repo().fetch_bond_analytics_rows(report_date=report_dates[0])
            lineage = _facts_lineage(report_dates[0], rows)
    else:
        lineage = {
            "source_version": EMPTY_SOURCE_VERSION,
            "rule_version": BOND_ANALYTICS_RULE_VERSION,
            "cache_version": BOND_ANALYTICS_CACHE_VERSION,
            "vendor_version": "vv_none",
        }
    return build_formal_result_meta(
        trace_id=_trace_id(),
        result_kind="bond_dashboard.dates",
        cache_version=lineage["cache_version"],
        source_version=lineage["source_version"],
        rule_version=lineage["rule_version"],
        vendor_version=lineage["vendor_version"],
    )


def _prior_report_date(report_date: str) -> str | None:
    dates = _repo().list_report_dates()
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
    return format((part / whole * Decimal("100")).quantize(Q8, rounding=ROUND_HALF_UP), "f")


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
    meta = _dates_meta()
    report_dates = _repo().list_report_dates()
    return build_formal_result_envelope(
        result_meta=meta,
        result_payload={"report_dates": report_dates},
    )


def get_bond_dashboard_headline_kpis(report_date: date) -> dict[str, object]:
    rd = report_date.isoformat()
    prior = _prior_report_date(rd)
    raw = _repo().fetch_dashboard_headline_kpis(rd, prev_report_date=prior)
    cur_row = raw["current"]
    prev_row = raw["previous"]
    payload = {
        "report_date": rd,
        "prev_report_date": prior,
        "kpis": _kpi_block_from_row(cur_row),
        "prev_kpis": _kpi_block_from_row(prev_row) if prev_row is not None else None,
    }
    return build_formal_result_envelope(
        result_meta=_meta(result_kind="bond_dashboard.headline_kpis", report_date=rd),
        result_payload=payload,
    )


def get_bond_dashboard_asset_structure(
    report_date: date,
    group_by: _GROUP_BY_LITERAL,
) -> dict[str, object]:
    rd = report_date.isoformat()
    rows = _repo().fetch_dashboard_asset_structure(rd, group_by=group_by)
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
        "report_date": rd,
        "group_by": group_by,
        "items": items,
        "total_market_value": _amt(tot),
    }
    return build_formal_result_envelope(
        result_meta=_meta(result_kind="bond_dashboard.asset_structure", report_date=rd),
        result_payload=payload,
    )


def get_bond_dashboard_yield_distribution(report_date: date) -> dict[str, object]:
    rd = report_date.isoformat()
    rows = _repo().fetch_dashboard_yield_distribution(rd)
    head = _repo().fetch_dashboard_headline_kpis(rd, prev_report_date=None)
    weighted_ytm = _rate(head["current"]["weighted_ytm"])
    items = [
        {
            "yield_bucket": r["yield_bucket"],
            "total_market_value": _amt(r["total_market_value"]),
            "bond_count": r["bond_count"],
        }
        for r in rows
    ]
    payload = {"report_date": rd, "items": items, "weighted_ytm": weighted_ytm}
    return build_formal_result_envelope(
        result_meta=_meta(result_kind="bond_dashboard.yield_distribution", report_date=rd),
        result_payload=payload,
    )


def get_bond_dashboard_portfolio_comparison(report_date: date) -> dict[str, object]:
    rd = report_date.isoformat()
    rows = _repo().fetch_dashboard_portfolio_comparison(rd)
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
    payload = {"report_date": rd, "items": items}
    return build_formal_result_envelope(
        result_meta=_meta(result_kind="bond_dashboard.portfolio_comparison", report_date=rd),
        result_payload=payload,
    )


def get_bond_dashboard_spread_analysis(report_date: date) -> dict[str, object]:
    rd = report_date.isoformat()
    rows = _repo().fetch_dashboard_spread_by_bond_type(rd)
    items = [
        {
            "bond_type": r["bond_type"],
            "median_yield": _rate(r["median_yield"]) if r["median_yield"] is not None else "0.00000000",
            "bond_count": r["bond_count"],
            "total_market_value": _amt(r["total_market_value"]),
        }
        for r in rows
    ]
    payload = {"report_date": rd, "items": items}
    return build_formal_result_envelope(
        result_meta=_meta(result_kind="bond_dashboard.spread_analysis", report_date=rd),
        result_payload=payload,
    )


def get_bond_dashboard_maturity_structure(report_date: date) -> dict[str, object]:
    rd = report_date.isoformat()
    rows = _repo().fetch_dashboard_maturity_structure(rd)
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
    payload = {"report_date": rd, "items": items, "total_market_value": _amt(tot)}
    return build_formal_result_envelope(
        result_meta=_meta(result_kind="bond_dashboard.maturity_structure", report_date=rd),
        result_payload=payload,
    )


def get_bond_dashboard_industry_distribution(report_date: date, top_n: int) -> dict[str, object]:
    rd = report_date.isoformat()
    rows = _repo().fetch_dashboard_industry_distribution(rd, top_n=top_n)
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
    payload = {"report_date": rd, "items": items}
    return build_formal_result_envelope(
        result_meta=_meta(result_kind="bond_dashboard.industry_distribution", report_date=rd),
        result_payload=payload,
    )


def get_bond_dashboard_risk_indicators(report_date: date) -> dict[str, object]:
    rd = report_date.isoformat()
    row = _repo().fetch_dashboard_risk_indicators(rd)
    payload = {
        "report_date": rd,
        "total_market_value": _amt(row["total_market_value"]),
        "total_dv01": _amt(row["total_dv01"]),
        "weighted_duration": _rate(row["weighted_duration"]),
        "credit_ratio": _rate(row["credit_ratio"]),
        "weighted_convexity": _rate(row["weighted_convexity"]),
        "total_spread_dv01": _amt(row["total_spread_dv01"]),
        "reinvestment_ratio_1y": _rate(row["reinvestment_ratio_1y"]),
    }
    return build_formal_result_envelope(
        result_meta=_meta(result_kind="bond_dashboard.risk_indicators", report_date=rd),
        result_payload=payload,
    )
