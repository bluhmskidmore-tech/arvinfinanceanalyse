"""ADB 日均资产负债分析 API（与 V1 `/api/analysis/adb*` 路径对齐）。"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Query

from backend.app.services import adb_analysis_service

router = APIRouter(prefix="/api/analysis", tags=["analysis-adb"])


def _parse_opt_date(s: str | None) -> date | None:
    if not s or not str(s).strip():
        return None
    try:
        return datetime.strptime(str(s).strip(), "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid date; expected YYYY-MM-DD.") from None


@router.get("/adb")
def get_adb(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
):
    sd, ed = _parse_opt_date(start_date), _parse_opt_date(end_date)
    if sd is None or ed is None:
        raise HTTPException(status_code=422, detail="start_date and end_date are required.")
    if sd > ed:
        raise HTTPException(status_code=400, detail="start_date must be <= end_date")
    return adb_analysis_service.adb_envelope_for_dates(sd.isoformat(), ed.isoformat())


@router.get("/adb-comparison")
@router.get("/adb/comparison")
def adb_comparison(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    top_n: int = Query(20, ge=1, le=200),
):
    sd, ed = _parse_opt_date(start_date), _parse_opt_date(end_date)
    if sd is None or ed is None:
        raise HTTPException(status_code=422, detail="start_date and end_date are required.")
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
    year: int | None = Query(None, description="统计年份，默认为当前年"),
):
    y = year if year is not None else date.today().year
    try:
        return adb_analysis_service.adb_monthly_envelope(y)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get monthly adb: {e}") from e
