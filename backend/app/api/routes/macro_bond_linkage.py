from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from backend.app.services.macro_bond_linkage_service import get_macro_bond_linkage

router = APIRouter(prefix="/api/macro-bond-linkage", tags=["macro-analysis"])


def _raise_macro_bond_linkage_reserved_surface() -> None:
    raise HTTPException(
        status_code=503,
        detail="Macro bond linkage analysis is reserved by the current boundary.",
    )


@router.get("/analysis")
def macro_bond_analysis(report_date: date = Query(...)) -> dict[str, object]:
    _raise_macro_bond_linkage_reserved_surface()
