"""ADB 日均资产负债分析 API（与 V1 `/api/analysis/adb*` 路径对齐）。"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime
from pathlib import Path

from backend.app.services import adb_analysis_service
from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

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


@router.get("/adb-comparison", operation_id="get_adb_comparison_legacy")
@router.get("/adb/comparison", operation_id="get_adb_comparison")
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


@router.get("/adb/coverage")
def adb_coverage(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
):
    """诊断 fact_formal 表在指定区间内的数据覆盖情况。"""
    sd, ed = _parse_opt_date(start_date), _parse_opt_date(end_date)
    if sd is None or ed is None:
        raise HTTPException(status_code=422, detail="start_date and end_date are required.")

    import duckdb
    from backend.app.governance.settings import get_settings

    settings = get_settings()
    db_path = str(settings.duckdb_path)
    if not Path(db_path).exists():
        raise HTTPException(status_code=500, detail=f"DuckDB not found: {db_path}")

    conn = duckdb.connect(db_path, read_only=True)
    try:
        calendar_days = (ed - sd).days + 1
        result: dict = {
            "start_date": sd.isoformat(),
            "end_date": ed.isoformat(),
            "calendar_days": calendar_days,
            "snapshot_tables": {},
            "formal_tables": {},
        }

        for tbl, label in [
            ("zqtz_bond_daily_snapshot", "zqtz_snapshot"),
            ("tyw_interbank_daily_snapshot", "tyw_snapshot"),
        ]:
            try:
                rows = conn.execute(
                    f"SELECT DISTINCT cast(report_date as varchar) FROM {tbl} "
                    f"WHERE cast(report_date as date) BETWEEN ? AND ? ORDER BY 1",
                    [sd, ed],
                ).fetchall()
                dates = [r[0] for r in rows]
                result["snapshot_tables"][label] = {
                    "dates_count": len(dates),
                    "dates": dates,
                }
            except duckdb.Error:
                result["snapshot_tables"][label] = {"dates_count": 0, "dates": [], "error": "table_not_found"}

        for tbl, label in [
            ("fact_formal_zqtz_balance_daily", "formal_zqtz"),
            ("fact_formal_tyw_balance_daily", "formal_tyw"),
        ]:
            try:
                rows = conn.execute(
                    f"SELECT DISTINCT cast(report_date as varchar) FROM {tbl} "
                    f"WHERE cast(report_date as date) BETWEEN ? AND ? AND currency_basis = 'CNY' ORDER BY 1",
                    [sd, ed],
                ).fetchall()
                dates = [r[0] for r in rows]
                result["formal_tables"][label] = {
                    "dates_count": len(dates),
                    "dates": dates,
                }
            except duckdb.Error:
                result["formal_tables"][label] = {"dates_count": 0, "dates": [], "error": "table_not_found"}

        # Compute missing dates: in snapshot but not in formal
        snap_dates: set[str] = set()
        for info in result["snapshot_tables"].values():
            snap_dates.update(info.get("dates", []))
        formal_dates: set[str] = set()
        for info in result["formal_tables"].values():
            formal_dates.update(info.get("dates", []))

        missing = sorted(snap_dates - formal_dates)
        result["snapshot_date_count"] = len(snap_dates)
        result["formal_date_count"] = len(formal_dates)
        result["missing_dates"] = missing
        result["missing_count"] = len(missing)
        result["coverage_pct"] = round(len(formal_dates) / max(len(snap_dates), 1) * 100, 1)

        return result
    finally:
        conn.close()


@router.post("/adb/backfill")
def adb_backfill(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
):
    """批量物化 fact_formal 表中缺失的日期。从快照表读取数据，生成 formal 表行。"""
    sd, ed = _parse_opt_date(start_date), _parse_opt_date(end_date)
    if sd is None or ed is None:
        raise HTTPException(status_code=422, detail="start_date and end_date are required.")
    if (ed - sd).days > 365:
        raise HTTPException(status_code=400, detail="Range too large; max 365 days.")

    import duckdb
    from backend.app.governance.settings import get_settings

    settings = get_settings()
    db_path = str(settings.duckdb_path)
    if not Path(db_path).exists():
        raise HTTPException(status_code=500, detail=f"DuckDB not found: {db_path}")

    # Find snapshot dates in range
    conn = duckdb.connect(db_path, read_only=True)
    try:
        snap_dates: set[str] = set()
        for tbl in ("zqtz_bond_daily_snapshot", "tyw_interbank_daily_snapshot"):
            try:
                rows = conn.execute(
                    f"SELECT DISTINCT cast(report_date as varchar) FROM {tbl} "
                    f"WHERE cast(report_date as date) BETWEEN ? AND ?",
                    [sd, ed],
                ).fetchall()
                snap_dates.update(r[0] for r in rows if r[0])
            except duckdb.Error:
                pass

        formal_dates: set[str] = set()
        for tbl in ("fact_formal_zqtz_balance_daily", "fact_formal_tyw_balance_daily"):
            try:
                rows = conn.execute(
                    f"SELECT DISTINCT cast(report_date as varchar) FROM {tbl} "
                    f"WHERE cast(report_date as date) BETWEEN ? AND ?",
                    [sd, ed],
                ).fetchall()
                formal_dates.update(r[0] for r in rows if r[0])
            except duckdb.Error:
                pass
    finally:
        conn.close()

    missing = sorted(snap_dates - formal_dates)
    if not missing:
        return {
            "status": "no_action",
            "message": "All snapshot dates already materialized.",
            "snapshot_dates": len(snap_dates),
            "formal_dates": len(formal_dates),
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
