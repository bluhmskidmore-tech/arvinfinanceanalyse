from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query

from backend.app.services.credit_spread_analysis_service import get_credit_spread_analysis

router = APIRouter(prefix="/api/credit-spread-analysis", tags=["credit-spread"])


@router.get("/detail")
def credit_spread_detail(report_date: date = Query(...)):
    return get_credit_spread_analysis(report_date)
