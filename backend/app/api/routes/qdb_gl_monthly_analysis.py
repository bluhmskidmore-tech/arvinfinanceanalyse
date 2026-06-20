from __future__ import annotations

from typing import Annotated
from urllib.parse import quote

from backend.app.governance.settings import get_settings
from backend.app.schemas.qdb_gl_contract import QdbGlMonthlyAnalysisManualAdjustmentRequest
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.qdb_gl_monthly_analysis_service import (
    create_qdb_gl_monthly_analysis_manual_adjustment,
    export_qdb_gl_monthly_analysis_manual_adjustments_csv,
    export_qdb_gl_monthly_analysis_workbook_xlsx,
    list_qdb_gl_monthly_analysis_manual_adjustments,
    qdb_gl_monthly_analysis_dates_envelope,
    qdb_gl_monthly_analysis_refresh_status,
    qdb_gl_monthly_analysis_scenario_envelope,
    qdb_gl_monthly_analysis_workbook_envelope,
    refresh_qdb_gl_monthly_analysis,
    restore_qdb_gl_monthly_analysis_manual_adjustment,
    revoke_qdb_gl_monthly_analysis_manual_adjustment,
    update_qdb_gl_monthly_analysis_manual_adjustment,
)
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import Response

router = APIRouter(prefix="/ui/qdb-gl-monthly-analysis")


@router.get("/dates")
def dates(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    settings = get_settings()
    _ensure_qdb_gl_monthly_analysis_read_allowed(auth, settings)
    return qdb_gl_monthly_analysis_dates_envelope(
        source_dir=settings.product_category_source_dir,
    )


@router.get("/workbook")
def workbook(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_month: str = Query(...),
) -> dict[str, object]:
    settings = get_settings()
    _ensure_qdb_gl_monthly_analysis_read_allowed(auth, settings)
    try:
        return qdb_gl_monthly_analysis_workbook_envelope(
            source_dir=settings.product_category_source_dir,
            governance_dir=settings.governance_path,
            report_month=report_month,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/workbook/export")
def export_workbook(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_month: str = Query(...),
) -> Response:
    settings = get_settings()
    _ensure_qdb_gl_monthly_analysis_read_allowed(auth, settings)
    try:
        filename, content = export_qdb_gl_monthly_analysis_workbook_xlsx(
            source_dir=settings.product_category_source_dir,
            governance_dir=settings.governance_path,
            report_month=report_month,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": (
                f"attachment; filename=qdb-gl-monthly-analysis-{report_month}.xlsx; "
                f"filename*=UTF-8''{quote(filename)}"
            )
        },
    )


@router.post("/refresh")
def refresh(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    report_month: str = Query(...),
) -> dict[str, object]:
    settings = get_settings()
    _ensure_qdb_gl_monthly_analysis_refresh_allowed(auth, settings)
    try:
        return refresh_qdb_gl_monthly_analysis(
            source_dir=settings.product_category_source_dir,
            governance_dir=settings.governance_path,
            report_month=report_month,
            idempotency_key=idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/refresh-status")
def refresh_status(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    run_id: str = Query(...),
) -> dict[str, object]:
    settings = get_settings()
    _ensure_qdb_gl_monthly_analysis_read_allowed(auth, settings)
    try:
        return qdb_gl_monthly_analysis_refresh_status(
            governance_dir=settings.governance_path,
            run_id=run_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/scenario")
def scenario(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_month: str = Query(...),
    scenario_name: str = Query(...),
    deviation_warn: float | None = Query(None),
    deviation_alert: float | None = Query(None),
    deviation_critical: float | None = Query(None),
) -> dict[str, object]:
    settings = get_settings()
    overrides = {
        key: value
        for key, value in {
            "DEVIATION_WARN": deviation_warn,
            "DEVIATION_ALERT": deviation_alert,
            "DEVIATION_CRITICAL": deviation_critical,
        }.items()
        if value is not None
    }
    _ensure_qdb_gl_monthly_analysis_read_allowed(auth, settings)
    try:
        return qdb_gl_monthly_analysis_scenario_envelope(
            source_dir=settings.product_category_source_dir,
            governance_dir=settings.governance_path,
            report_month=report_month,
            scenario_name=scenario_name,
            threshold_overrides=overrides,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/manual-adjustments")
def create_manual_adjustment(
    payload: QdbGlMonthlyAnalysisManualAdjustmentRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    settings = get_settings()
    _ensure_adjustment_write_allowed(auth, settings)
    return create_qdb_gl_monthly_analysis_manual_adjustment(
        governance_dir=settings.governance_path,
        payload=payload.model_dump(mode="json"),
    )


@router.get("/manual-adjustments")
def list_manual_adjustments(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_month: str = Query(...),
) -> dict[str, object]:
    settings = get_settings()
    _ensure_qdb_gl_monthly_analysis_read_allowed(auth, settings)
    return list_qdb_gl_monthly_analysis_manual_adjustments(
        governance_dir=settings.governance_path,
        report_month=report_month,
    )


@router.get("/manual-adjustments/export")
def export_manual_adjustments(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_month: str = Query(...),
) -> Response:
    settings = get_settings()
    _ensure_qdb_gl_monthly_analysis_read_allowed(auth, settings)
    filename, content = export_qdb_gl_monthly_analysis_manual_adjustments_csv(
        governance_dir=settings.governance_path,
        report_month=report_month,
    )
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/manual-adjustments/{adjustment_id}/edit")
def edit_manual_adjustment(
    adjustment_id: str,
    payload: QdbGlMonthlyAnalysisManualAdjustmentRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    settings = get_settings()
    _ensure_adjustment_write_allowed(auth, settings)
    try:
        return update_qdb_gl_monthly_analysis_manual_adjustment(
            governance_dir=settings.governance_path,
            adjustment_id=adjustment_id,
            payload=payload.model_dump(mode="json"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/manual-adjustments/{adjustment_id}/revoke")
def revoke_manual_adjustment(
    adjustment_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    settings = get_settings()
    _ensure_adjustment_write_allowed(auth, settings)
    try:
        return revoke_qdb_gl_monthly_analysis_manual_adjustment(
            governance_dir=settings.governance_path,
            adjustment_id=adjustment_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/manual-adjustments/{adjustment_id}/restore")
def restore_manual_adjustment(
    adjustment_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    settings = get_settings()
    _ensure_adjustment_write_allowed(auth, settings)
    try:
        return restore_qdb_gl_monthly_analysis_manual_adjustment(
            governance_dir=settings.governance_path,
            adjustment_id=adjustment_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _ensure_qdb_gl_monthly_analysis_read_allowed(auth: AuthContext, settings) -> None:
    try:
        ensure_user_allowed(
            auth=auth,
            settings=settings,
            resource="qdb_gl_monthly_analysis",
            action="read",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _ensure_qdb_gl_monthly_analysis_refresh_allowed(auth: AuthContext, settings) -> None:
    try:
        ensure_user_allowed(
            auth=auth,
            settings=settings,
            resource="qdb_gl_monthly_analysis",
            action="refresh",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _ensure_adjustment_write_allowed(auth: AuthContext, settings) -> None:
    try:
        ensure_user_allowed(
            auth=auth,
            settings=settings,
            resource="qdb_gl_monthly_analysis.adjustment",
            action="write",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
