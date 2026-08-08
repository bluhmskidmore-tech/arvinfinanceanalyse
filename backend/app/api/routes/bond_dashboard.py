"""Bond analytics dashboard API — aggregated read models from formal bond facts."""
from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from backend.app.api.perf_logging import timed_api_call
from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.bond_dashboard_service import (
    get_bond_dashboard_asset_structure,
    get_bond_dashboard_bundle,
    get_bond_dashboard_business_type_metrics,
    get_bond_dashboard_dates,
    get_bond_dashboard_headline_kpis,
    get_bond_dashboard_home_summary,
    get_bond_dashboard_industry_distribution,
    get_bond_dashboard_maturity_structure,
    get_bond_dashboard_portfolio_comparison,
    get_bond_dashboard_risk_indicators,
    get_bond_dashboard_spread_analysis,
    get_bond_dashboard_yield_distribution,
)
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter(prefix="/api/bond-dashboard", tags=["bond-dashboard"])

AssetGroupBy = Literal["bond_type", "rating", "portfolio_name", "tenor_bucket"]

BOND_DASHBOARD_BUNDLE_ANALYTICS_SECTIONS = frozenset(
    {
        "top-holdings",
        "portfolio-headlines",
        "dv01-risk",
        "dv01-risk-ac",
        "dv01-risk-oci",
        "dv01-risk-tpl",
        "dv01-risk-all",
        "yield-curve-term-structure",
    }
)


def _ensure_bond_dashboard_read_allowed(auth: AuthContext) -> None:
    try:
        ensure_user_allowed(
            auth=auth,
            settings=get_settings(),
            resource="bond_dashboard",
            action="read",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _ensure_bond_analytics_read_allowed(auth: AuthContext) -> None:
    try:
        ensure_user_allowed(
            auth=auth,
            settings=get_settings(),
            resource="bond_analytics",
            action="read",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _bundle_requests_bond_analytics(sections: str) -> bool:
    requested = {
        part.strip()
        for part in sections.split(",")
        if part.strip()
    }
    return bool(requested & BOND_DASHBOARD_BUNDLE_ANALYTICS_SECTIONS)


@router.get("/dates")
def dashboard_dates(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
):
    _ensure_bond_dashboard_read_allowed(auth)
    return timed_api_call(
        "/api/bond-dashboard/dates",
        get_bond_dashboard_dates,
    )


@router.get("/headline-kpis")
def headline_kpis(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: date = Query(..., description="Report date (YYYY-MM-DD)"),
):
    _ensure_bond_dashboard_read_allowed(auth)
    return timed_api_call(
        "/api/bond-dashboard/headline-kpis",
        lambda: get_bond_dashboard_headline_kpis(report_date),
    )


@router.get("/home-summary")
def home_summary(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: date = Query(..., description="Report date (YYYY-MM-DD)"),
):
    _ensure_bond_dashboard_read_allowed(auth)
    return timed_api_call(
        "/api/bond-dashboard/home-summary",
        lambda: get_bond_dashboard_home_summary(report_date),
    )


@router.get("/asset-structure")
def asset_structure(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: date = Query(..., description="Report date (YYYY-MM-DD)"),
    group_by: AssetGroupBy = Query("bond_type", description="bond_type | rating | portfolio_name | tenor_bucket"),
):
    _ensure_bond_dashboard_read_allowed(auth)
    return timed_api_call(
        "/api/bond-dashboard/asset-structure",
        lambda: get_bond_dashboard_asset_structure(report_date, group_by),
    )


@router.get("/yield-distribution")
def yield_distribution(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: date = Query(..., description="Report date (YYYY-MM-DD)"),
):
    _ensure_bond_dashboard_read_allowed(auth)
    return timed_api_call(
        "/api/bond-dashboard/yield-distribution",
        lambda: get_bond_dashboard_yield_distribution(report_date),
    )


@router.get("/portfolio-comparison")
def portfolio_comparison(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: date = Query(..., description="Report date (YYYY-MM-DD)"),
):
    _ensure_bond_dashboard_read_allowed(auth)
    return timed_api_call(
        "/api/bond-dashboard/portfolio-comparison",
        lambda: get_bond_dashboard_portfolio_comparison(report_date),
    )


@router.get("/spread-analysis")
def spread_analysis(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: date = Query(..., description="Report date (YYYY-MM-DD)"),
):
    _ensure_bond_dashboard_read_allowed(auth)
    return timed_api_call(
        "/api/bond-dashboard/spread-analysis",
        lambda: get_bond_dashboard_spread_analysis(report_date),
    )


@router.get("/maturity-structure")
def maturity_structure(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: date = Query(..., description="Report date (YYYY-MM-DD)"),
):
    _ensure_bond_dashboard_read_allowed(auth)
    return timed_api_call(
        "/api/bond-dashboard/maturity-structure",
        lambda: get_bond_dashboard_maturity_structure(report_date),
    )


@router.get("/industry-distribution")
def industry_distribution(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: date = Query(..., description="Report date (YYYY-MM-DD)"),
    top_n: int = Query(10, ge=1, le=500, description="Top industries by market value"),
):
    _ensure_bond_dashboard_read_allowed(auth)
    return timed_api_call(
        "/api/bond-dashboard/industry-distribution",
        lambda: get_bond_dashboard_industry_distribution(report_date, top_n),
    )


@router.get("/risk-indicators")
def risk_indicators(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: date = Query(..., description="Report date (YYYY-MM-DD)"),
):
    _ensure_bond_dashboard_read_allowed(auth)
    return timed_api_call(
        "/api/bond-dashboard/risk-indicators",
        lambda: get_bond_dashboard_risk_indicators(report_date),
    )


@router.get("/business-type-metrics")
def business_type_metrics(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: date = Query(..., description="Report date (YYYY-MM-DD)"),
):
    _ensure_bond_dashboard_read_allowed(auth)
    return timed_api_call(
        "/api/bond-dashboard/business-type-metrics",
        lambda: get_bond_dashboard_business_type_metrics(report_date),
    )


@router.get("/bundle")
def dashboard_bundle(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    sections: str = Query(
        ...,
        description=(
            "Comma-separated section ids, e.g. "
            "headline-kpis,risk-indicators,yield-distribution"
        ),
    ),
    report_date: date | None = Query(None, description="Report date (YYYY-MM-DD)"),
    industry_top_n: int = Query(10, ge=1, le=500, description="Top industries for industry-distribution"),
    analytics_top_n: int = Query(10, ge=1, le=500, description="Top rows for analytics bundle sections"),
    dv01_top_n: int = Query(1, ge=1, le=100, description="Top dv01 rows for bundled dv01-risk sections"),
    dv01_shock_bps: str = Query("1", description="Comma-separated dv01 shock scenarios in bps"),
    dv01_accounting_class: str = Query("all", description="Accounting class for the dv01-risk bundle alias"),
    curve_types: str = Query("treasury,cdb", description="Comma-separated yield curve types"),
):
    _ensure_bond_dashboard_read_allowed(auth)
    if _bundle_requests_bond_analytics(sections):
        _ensure_bond_analytics_read_allowed(auth)
    try:
        return timed_api_call(
            "/api/bond-dashboard/bundle",
            lambda: get_bond_dashboard_bundle(
                sections=[sections],
                report_date=report_date,
                industry_top_n=industry_top_n,
                analytics_top_n=analytics_top_n,
                dv01_top_n=dv01_top_n,
                dv01_shock_bps=dv01_shock_bps,
                dv01_accounting_class=dv01_accounting_class,
                curve_types=curve_types,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
