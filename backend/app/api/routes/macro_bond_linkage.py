from __future__ import annotations

from datetime import date

from backend.app.services.macro_bond_linkage_service import get_macro_bond_linkage
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/macro-bond-linkage", tags=["macro-analysis"])


@router.get("/analysis")
def macro_bond_analysis(report_date: date = Query(...)) -> dict[str, object]:
    return get_macro_bond_linkage(report_date)
