from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from backend.app.governance.settings import get_settings
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


@router.get("/dates")
def dates() -> dict[str, object]:
    settings = get_settings()
    return qdb_gl_monthly_analysis_dates_envelope(source_dir=str(settings.product_category_source_dir))


@router.get("/workbook")
def workbook(report_month: str = Query(...)) -> dict[str, object]:
    settings = get_settings()
    try:
        return qdb_gl_monthly_analysis_workbook_envelope(
            source_dir=str(settings.product_category_source_dir),
            governance_dir=str(settings.governance_path),
            report_month=report_month,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/workbook/export")
def export_workbook(report_month: str = Query(...)) -> Response:
    settings = get_settings()
    try:
        filename, content = export_qdb_gl_monthly_analysis_workbook_xlsx(
            source_dir=str(settings.product_category_source_dir),
            governance_dir=str(settings.governance_path),
            report_month=report_month,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
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
def refresh(report_month: str = Query(...)) -> dict[str, object]:
    settings = get_settings()
    try:
        return refresh_qdb_gl_monthly_analysis(
            source_dir=str(settings.product_category_source_dir),
            governance_dir=str(settings.governance_path),
            report_month=report_month,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/refresh-status")
def refresh_status(run_id: str = Query(...)) -> dict[str, object]:
    settings = get_settings()
    try:
        return qdb_gl_monthly_analysis_refresh_status(
            governance_dir=str(settings.governance_path),
            run_id=run_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/scenario")
def scenario(
    report_month: str = Query(...),
    scenario_name: str = Query(...),
    deviation_warn: float | None = Query(None),
    deviation_alert: float | None = Query(None),
    deviation_critical: float | None = Query(None),
) -> dict[str, object]:
    settings = get_settings()
    overrides = {}
    if deviation_warn is not None:
        overrides["DEVIATION_WARN"] = deviation_warn
    if deviation_alert is not None:
        overrides["DEVIATION_ALERT"] = deviation_alert
    if deviation_critical is not None:
        overrides["DEVIATION_CRITICAL"] = deviation_critical
    try:
        return qdb_gl_monthly_analysis_scenario_envelope(
            source_dir=str(settings.product_category_source_dir),
            governance_dir=str(settings.governance_path),
            report_month=report_month,
            scenario_name=scenario_name,
            threshold_overrides=overrides,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/manual-adjustments")
def create_manual_adjustment(payload: dict[str, object]) -> dict[str, object]:
    settings = get_settings()
    return create_qdb_gl_monthly_analysis_manual_adjustment(
        governance_dir=str(settings.governance_path),
        payload=payload,
    )


@router.get("/manual-adjustments")
def list_manual_adjustments(report_month: str = Query(...)) -> dict[str, object]:
    settings = get_settings()
    return list_qdb_gl_monthly_analysis_manual_adjustments(
        governance_dir=str(settings.governance_path),
        report_month=report_month,
    )


@router.get("/manual-adjustments/export")
def export_manual_adjustments(report_month: str = Query(...)) -> Response:
    settings = get_settings()
    filename, content = export_qdb_gl_monthly_analysis_manual_adjustments_csv(
        governance_dir=str(settings.governance_path),
        report_month=report_month,
    )
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/manual-adjustments/{adjustment_id}/edit")
def edit_manual_adjustment(adjustment_id: str, payload: dict[str, object]) -> dict[str, object]:
    settings = get_settings()
    try:
        return update_qdb_gl_monthly_analysis_manual_adjustment(
            governance_dir=str(settings.governance_path),
            adjustment_id=adjustment_id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/manual-adjustments/{adjustment_id}/revoke")
def revoke_manual_adjustment(adjustment_id: str) -> dict[str, object]:
    settings = get_settings()
    try:
        return revoke_qdb_gl_monthly_analysis_manual_adjustment(
            governance_dir=str(settings.governance_path),
            adjustment_id=adjustment_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/manual-adjustments/{adjustment_id}/restore")
def restore_manual_adjustment(adjustment_id: str) -> dict[str, object]:
    settings = get_settings()
    try:
        return restore_qdb_gl_monthly_analysis_manual_adjustment(
            governance_dir=str(settings.governance_path),
            adjustment_id=adjustment_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
