from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from backend.app.services.macro_bond_linkage_service import get_macro_bond_linkage

router = APIRouter(prefix="/api/macro-bond-linkage", tags=["macro-analysis"])


@router.get("/analysis")
def macro_bond_analysis(report_date: date = Query(...)) -> dict[str, object]:
    try:
        return get_macro_bond_linkage(report_date)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
