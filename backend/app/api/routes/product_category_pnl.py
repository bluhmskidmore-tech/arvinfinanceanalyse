from __future__ import annotations

from typing import Annotated
import importlib

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from backend.app.governance.settings import get_settings
from backend.app.services.product_category_pnl_service import (
    AVAILABLE_VIEWS,
    ProductCategoryRefreshConflictError,
    ProductCategoryRefreshServiceError,
    create_product_category_manual_adjustment,
    export_product_category_manual_adjustments_csv,
    list_product_category_manual_adjustments,
    product_category_dates_envelope,
    product_category_pnl_envelope,
    product_category_refresh_status,
    revoke_product_category_manual_adjustment,
    refresh_product_category_pnl,
    restore_product_category_manual_adjustment,
    update_product_category_manual_adjustment,
)
from backend.app.schemas.product_category_pnl import (
    ProductCategoryManualAdjustmentCreateRequest,
    ProductCategoryManualAdjustmentQuery,
    ProductCategoryManualAdjustmentUpdateRequest,
)


router = APIRouter(prefix="/ui/pnl/product-category")


@router.get("/dates")
def dates() -> dict[str, object]:
    return product_category_dates_envelope(get_settings().duckdb_path)


@router.get("")
def detail(
    report_date: str = Query(...),
    view: str = Query("monthly"),
    scenario_rate_pct: float | None = Query(None),
) -> dict[str, object]:
    if view not in AVAILABLE_VIEWS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported product-category view={view!r}; expected one of {AVAILABLE_VIEWS}",
        )
    try:
        return product_category_pnl_envelope(
            get_settings().duckdb_path,
            report_date=report_date,
            view=view,
            scenario_rate_pct=scenario_rate_pct,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail.startswith("No product-category read model rows"):
            raise HTTPException(status_code=404, detail=detail) from exc
        raise HTTPException(status_code=422, detail=detail) from exc


@router.post("/refresh")
def refresh() -> dict[str, object]:
    try:
        return refresh_product_category_pnl(get_settings())
    except ProductCategoryRefreshConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProductCategoryRefreshServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/refresh-status")
def refresh_status(run_id: str = Query(...)) -> dict[str, object]:
    product_category_service = importlib.import_module(
        "backend.app.services.product_category_pnl_service"
    )

    try:
        return product_category_service.product_category_refresh_status(get_settings(), run_id=run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/manual-adjustments")
def create_manual_adjustment(
    payload: ProductCategoryManualAdjustmentCreateRequest,
) -> dict[str, object]:
    return create_product_category_manual_adjustment(get_settings(), payload)


@router.get("/manual-adjustments")
def list_manual_adjustments(
    query: Annotated[ProductCategoryManualAdjustmentQuery, Depends()],
) -> dict[str, object]:
    return list_product_category_manual_adjustments(
        get_settings(),
        report_date=query.report_date,
        adjustment_id=query.adjustment_id,
        adjustment_id_exact=query.adjustment_id_exact,
        account_code=query.account_code,
        approval_status=query.approval_status,
        event_type=query.event_type,
        current_sort_field=query.current_sort_field,
        current_sort_dir=query.current_sort_dir,
        event_sort_field=query.event_sort_field,
        event_sort_dir=query.event_sort_dir,
        created_at_from=query.created_at_from,
        created_at_to=query.created_at_to,
        adjustment_limit=query.adjustment_limit,
        adjustment_offset=query.adjustment_offset,
        limit=query.limit,
        offset=query.offset,
    )


@router.get("/manual-adjustments/export")
def export_manual_adjustments(
    query: Annotated[ProductCategoryManualAdjustmentQuery, Depends()],
) -> Response:
    filename, content = export_product_category_manual_adjustments_csv(
        get_settings(),
        report_date=query.report_date,
        adjustment_id=query.adjustment_id,
        adjustment_id_exact=query.adjustment_id_exact,
        account_code=query.account_code,
        approval_status=query.approval_status,
        event_type=query.event_type,
        current_sort_field=query.current_sort_field,
        current_sort_dir=query.current_sort_dir,
        event_sort_field=query.event_sort_field,
        event_sort_dir=query.event_sort_dir,
        created_at_from=query.created_at_from,
        created_at_to=query.created_at_to,
    )
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/manual-adjustments/{adjustment_id}/revoke")
def revoke_manual_adjustment(adjustment_id: str) -> dict[str, object]:
    try:
        return revoke_product_category_manual_adjustment(get_settings(), adjustment_id=adjustment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/manual-adjustments/{adjustment_id}/edit")
def edit_manual_adjustment(
    adjustment_id: str,
    payload: ProductCategoryManualAdjustmentUpdateRequest,
) -> dict[str, object]:
    try:
        return update_product_category_manual_adjustment(
            get_settings(),
            adjustment_id=adjustment_id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/manual-adjustments/{adjustment_id}/restore")
def restore_manual_adjustment(adjustment_id: str) -> dict[str, object]:
    try:
        return restore_product_category_manual_adjustment(get_settings(), adjustment_id=adjustment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
