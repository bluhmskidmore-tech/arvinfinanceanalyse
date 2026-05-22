from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.accounting_asset_movement_service import (
    AccountingAssetMovementReadModelNotFoundError,
    accounting_asset_movement_dates_envelope,
    accounting_asset_movement_envelope,
    refresh_accounting_asset_movement,
)

router = APIRouter(prefix="/ui/balance-movement-analysis")


@router.get("/dates")
def dates(currency_basis: str = Query("CNX")) -> dict[str, object]:
    return accounting_asset_movement_dates_envelope(
        get_settings().duckdb_path,
        currency_basis=currency_basis,
    )


@router.get("")
def detail(
    report_date: str = Query(...),
    currency_basis: str = Query("CNX"),
) -> dict[str, object]:
    try:
        return accounting_asset_movement_envelope(
            get_settings().duckdb_path,
            report_date=report_date,
            currency_basis=currency_basis,
        )
    except AccountingAssetMovementReadModelNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/refresh")
def refresh(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str = Query(...),
    currency_basis: str = Query("CNX"),
) -> dict[str, object]:
    settings = get_settings()
    try:
        ensure_user_allowed(
            auth=auth,
            settings=settings,
            resource="accounting_asset_movement",
            action="refresh",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return refresh_accounting_asset_movement(
        settings,
        report_date=report_date,
        currency_basis=currency_basis,
    )
