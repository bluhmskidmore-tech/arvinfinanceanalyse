from __future__ import annotations

from typing import Annotated

import duckdb
from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.accounting_asset_movement_service import (
    AccountingAssetMovementReadModelNotFoundError,
    accounting_asset_movement_dates_envelope,
    accounting_asset_movement_envelope,
    refresh_accounting_asset_movement,
)
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter(prefix="/ui/balance-movement-analysis")


def _ensure_accounting_asset_movement_read_allowed(auth: AuthContext, settings) -> None:
    try:
        ensure_user_allowed(
            auth=auth,
            settings=settings,
            resource="accounting_asset_movement",
            action="read",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/dates")
def dates(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    currency_basis: str = Query("CNX"),
) -> dict[str, object]:
    settings = get_settings()
    _ensure_accounting_asset_movement_read_allowed(auth, settings)
    try:
        return accounting_asset_movement_dates_envelope(
            settings.duckdb_path,
            currency_basis=currency_basis,
        )
    except duckdb.Error as exc:
        raise HTTPException(
            status_code=503,
            detail="Balance movement data is temporarily unavailable.",
        ) from exc


@router.get("")
def detail(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str = Query(...),
    currency_basis: str = Query("CNX"),
) -> dict[str, object]:
    settings = get_settings()
    _ensure_accounting_asset_movement_read_allowed(auth, settings)
    try:
        return accounting_asset_movement_envelope(
            settings.duckdb_path,
            report_date=report_date,
            currency_basis=currency_basis,
        )
    except AccountingAssetMovementReadModelNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except duckdb.Error as exc:
        raise HTTPException(
            status_code=503,
            detail="Balance movement data is temporarily unavailable.",
        ) from exc


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
