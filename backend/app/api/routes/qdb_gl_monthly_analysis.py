from __future__ import annotations

from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.qdb_gl_monthly_analysis_service import (
    create_qdb_gl_monthly_analysis_manual_adjustment,
    export_qdb_gl_monthly_analysis_workbook_xlsx,
    export_qdb_gl_monthly_analysis_manual_adjustments_csv,
    list_qdb_gl_monthly_analysis_manual_adjustments,
    qdb_gl_monthly_analysis_refresh_status,
    qdb_gl_monthly_analysis_scenario_envelope,
    qdb_gl_monthly_analysis_dates_envelope,
    qdb_gl_monthly_analysis_workbook_envelope,
    refresh_qdb_gl_monthly_analysis,
    restore_qdb_gl_monthly_analysis_manual_adjustment,
    revoke_qdb_gl_monthly_analysis_manual_adjustment,
    update_qdb_gl_monthly_analysis_manual_adjustment,
)


router = APIRouter(prefix="/ui/qdb-gl-monthly-analysis")


def _raise_qdb_gl_reserved_surface() -> None:
    raise HTTPException(
        status_code=503,
        detail="QDB GL monthly analysis surfaces are reserved by the current boundary.",
    )


@router.get("/dates")
def dates() -> dict[str, object]:
    _raise_qdb_gl_reserved_surface()


@router.get("/workbook")
def workbook(report_month: str = Query(...)) -> dict[str, object]:
    _raise_qdb_gl_reserved_surface()


@router.get("/workbook/export")
def export_workbook(report_month: str = Query(...)) -> Response:
    _raise_qdb_gl_reserved_surface()


@router.post("/refresh")
def refresh(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_month: str = Query(...),
) -> dict[str, object]:
    _raise_qdb_gl_reserved_surface()


@router.get("/refresh-status")
def refresh_status(run_id: str = Query(...)) -> dict[str, object]:
    _raise_qdb_gl_reserved_surface()


@router.get("/scenario")
def scenario(
    report_month: str = Query(...),
    scenario_name: str = Query(...),
    deviation_warn: float | None = Query(None),
    deviation_alert: float | None = Query(None),
    deviation_critical: float | None = Query(None),
) -> dict[str, object]:
    _raise_qdb_gl_reserved_surface()


@router.post("/manual-adjustments")
def create_manual_adjustment(
    payload: dict[str, object],
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    _raise_qdb_gl_reserved_surface()


@router.get("/manual-adjustments")
def list_manual_adjustments(report_month: str = Query(...)) -> dict[str, object]:
    _raise_qdb_gl_reserved_surface()


@router.get("/manual-adjustments/export")
def export_manual_adjustments(report_month: str = Query(...)) -> Response:
    _raise_qdb_gl_reserved_surface()


@router.post("/manual-adjustments/{adjustment_id}/edit")
def edit_manual_adjustment(
    adjustment_id: str,
    payload: dict[str, object],
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    _raise_qdb_gl_reserved_surface()


@router.post("/manual-adjustments/{adjustment_id}/revoke")
def revoke_manual_adjustment(
    adjustment_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    _raise_qdb_gl_reserved_surface()


@router.post("/manual-adjustments/{adjustment_id}/restore")
def restore_manual_adjustment(
    adjustment_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    _raise_qdb_gl_reserved_surface()
