from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.app.governance.settings import get_settings
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
    report_date: str = Query(...),
    currency_basis: str = Query("CNX"),
) -> dict[str, object]:
    return refresh_accounting_asset_movement(
        get_settings(),
        report_date=report_date,
        currency_basis=currency_basis,
    )
