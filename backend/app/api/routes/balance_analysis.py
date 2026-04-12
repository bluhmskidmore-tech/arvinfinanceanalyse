from __future__ import annotations

import importlib
from datetime import datetime
from typing import Literal
from urllib.parse import quote

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from backend.app.governance.settings import get_settings
from backend.app.security.auth_stub import AuthContext, get_auth_context
from backend.app.services.advanced_attribution_service import advanced_attribution_bundle_envelope
from backend.app.services.balance_analysis_service import (
    BalanceAnalysisRefreshConflictError,
    BalanceAnalysisRefreshServiceError,
    balance_analysis_decision_items_envelope,
    balance_analysis_basis_breakdown_envelope,
    balance_analysis_dates_envelope,
    balance_analysis_detail_envelope,
    balance_analysis_overview_envelope,
    balance_analysis_refresh_status,
    balance_analysis_summary_envelope,
    balance_analysis_workbook_envelope,
    export_balance_analysis_workbook_xlsx,
    export_balance_analysis_summary_csv,
    refresh_balance_analysis,
    update_balance_analysis_decision_status,
)
from backend.app.schemas.balance_analysis import BalanceAnalysisDecisionStatusUpdateRequest

router = APIRouter(prefix="/ui/balance-analysis")


def _build_attachment_disposition(filename: str, *, fallback_filename: str | None = None) -> str:
    fallback = fallback_filename or filename
    return f"attachment; filename={fallback}; filename*=UTF-8''{quote(filename)}"


def _require_balance_analysis_report_date_qs(report_date: str) -> str:
    """YYYY-MM-DD calendar validation; aligned with balance_analysis_service._parse_date format."""
    candidate = str(report_date).strip()
    try:
        datetime.strptime(candidate, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="report_date must be a valid calendar date in YYYY-MM-DD format.",
        ) from exc
    return candidate


@router.get("/dates")
def dates() -> dict[str, object]:
    settings = get_settings()
    try:
        return balance_analysis_dates_envelope(
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("")
def detail(
    report_date: str = Query(...),
    position_scope: Literal["asset", "liability", "all"] = Query("all"),
    currency_basis: Literal["native", "CNY"] = Query("CNY"),
) -> dict[str, object]:
    settings = get_settings()
    try:
        return balance_analysis_detail_envelope(
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
            report_date=report_date,
            position_scope=position_scope,
            currency_basis=currency_basis,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/overview")
def overview(
    report_date: str = Query(...),
    position_scope: Literal["asset", "liability", "all"] = Query("all"),
    currency_basis: Literal["native", "CNY"] = Query("CNY"),
) -> dict[str, object]:
    settings = get_settings()
    try:
        return balance_analysis_overview_envelope(
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
            report_date=report_date,
            position_scope=position_scope,
            currency_basis=currency_basis,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/summary")
def summary(
    report_date: str = Query(...),
    position_scope: Literal["asset", "liability", "all"] = Query("all"),
    currency_basis: Literal["native", "CNY"] = Query("CNY"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, object]:
    settings = get_settings()
    try:
        return balance_analysis_summary_envelope(
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
            report_date=report_date,
            position_scope=position_scope,
            currency_basis=currency_basis,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/summary-by-basis")
def summary_by_basis(
    report_date: str = Query(...),
    position_scope: Literal["asset", "liability", "all"] = Query("all"),
    currency_basis: Literal["native", "CNY"] = Query("CNY"),
) -> dict[str, object]:
    settings = get_settings()
    try:
        return balance_analysis_basis_breakdown_envelope(
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
            report_date=report_date,
            position_scope=position_scope,
            currency_basis=currency_basis,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/advanced-attribution")
def advanced_attribution(
    report_date: str = Query(..., description="Report date (YYYY-MM-DD) for the not_ready attribution contract."),
    scenario_name: str | None = Query(
        None,
        description="Optional scenario label; treated as scenario only when explicit shock inputs are supplied.",
    ),
    treasury_shift_bp: int | None = Query(
        None,
        description="Optional treasury curve shock in basis points; activates scenario semantics when provided.",
    ),
    spread_shift_bp: int | None = Query(
        None,
        description="Optional spread shock in basis points; activates scenario semantics when provided.",
    ),
) -> dict[str, object]:
    """Analytical/scenario advanced attribution contract; never part of the governed workbook tables."""
    normalized = _require_balance_analysis_report_date_qs(report_date)
    settings = get_settings()
    return advanced_attribution_bundle_envelope(
        report_date=normalized,
        scenario_name=scenario_name,
        treasury_shift_bp=treasury_shift_bp,
        spread_shift_bp=spread_shift_bp,
        duckdb_path=str(settings.duckdb_path),
        governance_dir=str(settings.governance_path),
    )


@router.get("/workbook")
def workbook(
    report_date: str = Query(...),
    position_scope: Literal["asset", "liability", "all"] = Query("all"),
    currency_basis: Literal["native", "CNY"] = Query("CNY"),
) -> dict[str, object]:
    settings = get_settings()
    try:
        return balance_analysis_workbook_envelope(
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
            report_date=report_date,
            position_scope=position_scope,
            currency_basis=currency_basis,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/current-user")
def current_user(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    return {
        "user_id": auth.user_id,
        "role": auth.role,
        "identity_source": auth.identity_source,
    }


@router.get("/decision-items")
def decision_items(
    report_date: str = Query(...),
    position_scope: Literal["asset", "liability", "all"] = Query("all"),
    currency_basis: Literal["native", "CNY"] = Query("CNY"),
) -> dict[str, object]:
    settings = get_settings()
    try:
        return balance_analysis_decision_items_envelope(
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
            report_date=report_date,
            position_scope=position_scope,
            currency_basis=currency_basis,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/decision-items/status")
def update_decision_status(
    payload: BalanceAnalysisDecisionStatusUpdateRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    settings = get_settings()
    try:
        return update_balance_analysis_decision_status(
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
            update=payload,
            updated_by=auth.user_id,
        ).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/summary/export")
def export_summary(
    report_date: str = Query(...),
    position_scope: Literal["asset", "liability", "all"] = Query("all"),
    currency_basis: Literal["native", "CNY"] = Query("CNY"),
) -> Response:
    settings = get_settings()
    try:
        filename, content = export_balance_analysis_summary_csv(
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
            report_date=report_date,
            position_scope=position_scope,
            currency_basis=currency_basis,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/workbook/export")
def export_workbook(
    report_date: str = Query(...),
    position_scope: Literal["asset", "liability", "all"] = Query("all"),
    currency_basis: Literal["native", "CNY"] = Query("CNY"),
) -> Response:
    settings = get_settings()
    try:
        filename, content = export_balance_analysis_workbook_xlsx(
            duckdb_path=str(settings.duckdb_path),
            governance_dir=str(settings.governance_path),
            report_date=report_date,
            position_scope=position_scope,
            currency_basis=currency_basis,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": _build_attachment_disposition(
                filename,
                fallback_filename=f"balance-analysis-workbook-{report_date}.xlsx",
            )
        },
    )


@router.post("/refresh")
def refresh(report_date: str = Query(...)) -> dict[str, object]:
    settings = get_settings()
    try:
        return refresh_balance_analysis(settings, report_date=report_date)
    except BalanceAnalysisRefreshConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except BalanceAnalysisRefreshServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/refresh-status")
def refresh_status(run_id: str = Query(...)) -> dict[str, object]:
    settings = get_settings()
    try:
        service_mod = importlib.import_module("backend.app.services.balance_analysis_service")
        return service_mod.balance_analysis_refresh_status(settings, run_id=run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
