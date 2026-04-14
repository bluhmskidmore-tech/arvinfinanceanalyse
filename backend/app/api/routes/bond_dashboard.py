"""Bond analytics dashboard API — aggregated read models from formal bond facts."""
from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Query

from backend.app.services.bond_dashboard_service import (
    get_bond_dashboard_asset_structure,
    get_bond_dashboard_dates,
    get_bond_dashboard_headline_kpis,
    get_bond_dashboard_industry_distribution,
    get_bond_dashboard_maturity_structure,
    get_bond_dashboard_portfolio_comparison,
    get_bond_dashboard_risk_indicators,
    get_bond_dashboard_spread_analysis,
    get_bond_dashboard_yield_distribution,
)

router = APIRouter(prefix="/api/bond-dashboard", tags=["bond-dashboard"])

AssetGroupBy = Literal["bond_type", "rating", "portfolio_name", "tenor_bucket"]


@router.get("/dates")
def dashboard_dates():
    return get_bond_dashboard_dates()


@router.get("/headline-kpis")
def headline_kpis(report_date: date = Query(..., description="Report date (YYYY-MM-DD)")):
    return get_bond_dashboard_headline_kpis(report_date)


@router.get("/asset-structure")
def asset_structure(
    report_date: date = Query(..., description="Report date (YYYY-MM-DD)"),
    group_by: AssetGroupBy = Query("bond_type", description="bond_type | rating | portfolio_name | tenor_bucket"),
):
    return get_bond_dashboard_asset_structure(report_date, group_by)


@router.get("/yield-distribution")
def yield_distribution(report_date: date = Query(..., description="Report date (YYYY-MM-DD)")):
    return get_bond_dashboard_yield_distribution(report_date)


@router.get("/portfolio-comparison")
def portfolio_comparison(report_date: date = Query(..., description="Report date (YYYY-MM-DD)")):
    return get_bond_dashboard_portfolio_comparison(report_date)


@router.get("/spread-analysis")
def spread_analysis(report_date: date = Query(..., description="Report date (YYYY-MM-DD)")):
    return get_bond_dashboard_spread_analysis(report_date)


@router.get("/maturity-structure")
def maturity_structure(report_date: date = Query(..., description="Report date (YYYY-MM-DD)")):
    return get_bond_dashboard_maturity_structure(report_date)


@router.get("/industry-distribution")
def industry_distribution(
    report_date: date = Query(..., description="Report date (YYYY-MM-DD)"),
    top_n: int = Query(10, ge=1, le=500, description="Top industries by market value"),
):
    return get_bond_dashboard_industry_distribution(report_date, top_n)


@router.get("/risk-indicators")
def risk_indicators(report_date: date = Query(..., description="Report date (YYYY-MM-DD)")):
    return get_bond_dashboard_risk_indicators(report_date)
