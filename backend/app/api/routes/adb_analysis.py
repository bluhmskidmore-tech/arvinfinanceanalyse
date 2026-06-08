"""ADB 日均资产负债分析 API（与 V1 `/api/analysis/adb*` 路径对齐）。"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime
from pathlib import Path
from typing import Annotated

from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services import adb_analysis_service
from fastapi import APIRouter, Depends, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis", tags=["analysis-adb"])


def _parse_opt_date(s: str | None) -> date | None:
    if not s or not str(s).strip():
        return None
    try:
        return datetime.strptime(str(s).strip(), "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid date; expected YYYY-MM-DD.") from None


def _ensure_adb_analysis_read_allowed(auth: AuthContext, settings) -> None:
    try:
        ensure_user_allowed(
            auth=auth,
            settings=settings,
            resource="adb_analysis",
            action="read",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/adb")
def get_adb(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
):
    sd, ed = _parse_opt_date(start_date), _parse_opt_date(end_date)
    if sd is None or ed is None:
        raise HTTPException(status_code=422, detail="start_date and end_date are required.")
    if sd > ed:
        raise HTTPException(status_code=400, detail="start_date must be <= end_date")
    from backend.app.governance.settings import get_settings

    _ensure_adb_analysis_read_allowed(auth, get_settings())
    return adb_analysis_service.adb_envelope_for_dates(sd.isoformat(), ed.isoformat())


@router.get("/adb-comparison", operation_id="get_adb_comparison_legacy")
@router.get("/adb/comparison", operation_id="get_adb_comparison")
def adb_comparison(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    top_n: int = Query(20, ge=1, le=200),
):
    sd, ed = _parse_opt_date(start_date), _parse_opt_date(end_date)
    if sd is None or ed is None:
        raise HTTPException(status_code=422, detail="start_date and end_date are required.")
    from backend.app.governance.settings import get_settings

    _ensure_adb_analysis_read_allowed(auth, get_settings())
    try:
        return adb_analysis_service.adb_comparison_envelope(
            sd.isoformat(),
            ed.isoformat(),
            top_n=top_n,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get adb comparison: {e}") from e


@router.get("/adb/monthly")
def adb_monthly(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    year: int | None = Query(None, description="统计年份，默认为当前年"),
):
    y = year if year is not None else date.today().year
    from backend.app.governance.settings import get_settings

    _ensure_adb_analysis_read_allowed(auth, get_settings())
    try:
        return adb_analysis_service.adb_monthly_envelope(y)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get monthly adb: {e}") from e


@router.get("/adb/coverage")
def adb_coverage(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
):
    """诊断 fact_formal 表在指定区间内的数据覆盖情况。"""
    sd, ed = _parse_opt_date(start_date), _parse_opt_date(end_date)
    if sd is None or ed is None:
        raise HTTPException(status_code=422, detail="start_date and end_date are required.")

    from backend.app.governance.settings import get_settings

    settings = get_settings()
    _ensure_adb_analysis_read_allowed(auth, settings)
    try:
        return adb_analysis_service.adb_coverage_diagnostics(sd.isoformat(), ed.isoformat())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/adb/backfill")
def adb_backfill(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
):
    """批量物化 fact_formal 表中缺失的日期。从快照表读取数据，生成 formal 表行。"""
    sd, ed = _parse_opt_date(start_date), _parse_opt_date(end_date)
    if sd is None or ed is None:
        raise HTTPException(status_code=422, detail="start_date and end_date are required.")
    if (ed - sd).days > 365:
        raise HTTPException(status_code=400, detail="Range too large; max 365 days.")

    from backend.app.governance.settings import get_settings

    settings = get_settings()
    try:
        ensure_user_allowed(
            auth=auth,
            settings=settings,
            resource="adb_analysis",
            action="backfill",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    try:
        candidate_dates = adb_analysis_service.adb_backfill_candidate_dates(sd.isoformat(), ed.isoformat())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    db_path = str(settings.duckdb_path)
    missing = list(candidate_dates["missing_dates"])
    if not missing:
        return {
            "status": "no_action",
            "message": "All snapshot dates already materialized.",
            "snapshot_dates": len(candidate_dates["snapshot_dates"]),
            "formal_dates": len(candidate_dates["formal_dates"]),
        }

    # Import materialization function
    from backend.app.tasks.balance_analysis_materialize import (
        _execute_balance_analysis_materialization,
    )

    success = 0
    failed: list[dict] = []
    for report_date_str in missing:
        t0 = time.time()
        try:
            result = _execute_balance_analysis_materialization(
                report_date=report_date_str,
                duckdb_file=Path(db_path),
                governance_dir=str(settings.governance_path),
                data_root=str(settings.data_input_root),
            )
            elapsed = time.time() - t0
            logger.info(
                "Backfill %s OK: zqtz=%d tyw=%d (%.1fs)",
                report_date_str,
                result.payload.get("zqtz_rows", 0),
                result.payload.get("tyw_rows", 0),
                elapsed,
            )
            success += 1
        except Exception as exc:
            elapsed = time.time() - t0
            logger.warning("Backfill %s FAILED: %s (%.1fs)", report_date_str, exc, elapsed)
            failed.append({"date": report_date_str, "error": str(exc)})

    return {
        "status": "completed",
        "total_missing": len(missing),
        "success": success,
        "failed_count": len(failed),
        "failed": failed[:20],
        "message": f"Backfilled {success}/{len(missing)} dates.",
    }
