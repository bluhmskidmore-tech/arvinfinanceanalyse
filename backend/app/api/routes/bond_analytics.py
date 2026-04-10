"""Bond analytics API routes — thin layer delegating to service."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query

from backend.app.services.bond_analytics_service import (
    get_accounting_class_audit,
    get_action_attribution,
    get_benchmark_excess,
    get_credit_spread_migration,
    get_krd_curve_risk,
    get_return_decomposition,
)

router = APIRouter(prefix="/api/bond-analytics", tags=["bond-analytics"])


@router.get("/return-decomposition")
def return_decomposition(
    report_date: date = Query(..., description="Report date (YYYY-MM-DD)"),
    period_type: str = Query("MoM", description="MoM / YTD / TTM"),
    asset_class: str = Query("all", description="all / rate / credit"),
    accounting_class: str = Query("all", description="all / AC / OCI / TPL"),
):
    return get_return_decomposition(report_date, period_type, asset_class, accounting_class)


@router.get("/benchmark-excess")
def benchmark_excess(
    report_date: date = Query(..., description="Report date (YYYY-MM-DD)"),
    period_type: str = Query("MoM", description="MoM / YTD / TTM"),
    benchmark_id: str = Query("CDB_INDEX", description="TREASURY_INDEX / CDB_INDEX / AAA_CREDIT_INDEX"),
):
    return get_benchmark_excess(report_date, period_type, benchmark_id)


@router.get("/krd-curve-risk")
def krd_curve_risk(
    report_date: date = Query(..., description="Report date (YYYY-MM-DD)"),
    scenario_set: str = Query("standard", description="standard / custom"),
):
    return get_krd_curve_risk(report_date, scenario_set)


@router.get("/credit-spread-migration")
def credit_spread_migration(
    report_date: date = Query(..., description="Report date (YYYY-MM-DD)"),
    spread_scenarios: str = Query("10,25,50", description="Comma-separated bp values"),
):
    return get_credit_spread_migration(report_date, spread_scenarios)


@router.get("/action-attribution")
def action_attribution(
    report_date: date = Query(..., description="Report date (YYYY-MM-DD)"),
    period_type: str = Query("MoM", description="MoM / YTD"),
):
    return get_action_attribution(report_date, period_type)


@router.get("/accounting-class-audit")
def accounting_class_audit(
    report_date: date = Query(..., description="Report date (YYYY-MM-DD)"),
):
    return get_accounting_class_audit(report_date)
