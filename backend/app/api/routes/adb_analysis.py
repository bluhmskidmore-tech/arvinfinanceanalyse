"""ADB 日均资产负债分析 API（与 V1 `/api/analysis/adb*` 路径对齐）。"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Annotated, NoReturn

from backend.app.api.deps import ensure_read_allowed
from backend.app.schemas.adb_analysis import (
    AdbAnalysisEnvelope,
    AdbBackfillResponse,
    AdbCoverageResponse,
    AdbInsightsEnvelope,
)
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services import adb_analysis_service
from fastapi import APIRouter, Depends, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis", tags=["analysis-adb"])


def _error_detail(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _raise_adb_service_http_error(
    exc: Exception,
    *,
    operation: str,
    request_context: str,
) -> NoReturn:
    logger.error(
        "ADB %s failed context=%s error_type=%s: %s",
        operation,
        request_context,
        type(exc).__name__,
        exc,
    )
    if isinstance(exc, FileNotFoundError):
        raise HTTPException(
            status_code=503,
            detail=_error_detail("ADB_SOURCE_UNAVAILABLE", "ADB 数据源暂时不可用。"),
        ) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(
            status_code=422,
            detail=_error_detail("ADB_REQUEST_INVALID", "ADB 请求参数无效。"),
        ) from exc
    if isinstance(exc, RuntimeError):
        raise HTTPException(
            status_code=503,
            detail=_error_detail("ADB_SERVICE_UNAVAILABLE", "ADB 分析服务暂时不可用。"),
        ) from exc
    raise HTTPException(
        status_code=500,
        detail=_error_detail("ADB_INTERNAL_ERROR", "ADB 分析请求处理失败。"),
    ) from exc


def _parse_opt_date(s: str | None) -> date | None:
    if not s or not str(s).strip():
        return None
    try:
        return datetime.strptime(str(s).strip(), "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=_error_detail(
                "ADB_DATE_FORMAT_INVALID",
                "日期格式无效，应为 YYYY-MM-DD。",
            ),
        ) from None


def _ensure_adb_analysis_read_allowed(auth: AuthContext, settings) -> None:
    ensure_read_allowed(auth, "adb_analysis", settings=settings, authorize=ensure_user_allowed)


@router.get(
    "/adb",
    response_model=AdbAnalysisEnvelope,
)
def get_adb(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
):
    sd, ed = _parse_opt_date(start_date), _parse_opt_date(end_date)
    if sd is None or ed is None:
        raise HTTPException(
            status_code=422,
            detail=_error_detail("ADB_DATE_REQUIRED", "开始日期和结束日期不能为空。"),
        )
    if sd > ed:
        raise HTTPException(
            status_code=400,
            detail=_error_detail("ADB_DATE_RANGE_INVALID", "开始日期不能晚于结束日期。"),
        )
    from backend.app.governance.settings import get_settings

    _ensure_adb_analysis_read_allowed(auth, get_settings())
    try:
        return adb_analysis_service.adb_envelope_for_dates(sd.isoformat(), ed.isoformat())
    # This route boundary sanitizes every service failure into the stable HTTP contract.
    except Exception as exc:  # noqa: BLE001
        _raise_adb_service_http_error(
            exc,
            operation="daily",
            request_context=f"start_date={sd.isoformat()} end_date={ed.isoformat()}",
        )


@router.get(
    "/adb-comparison",
    operation_id="get_adb_comparison_legacy",
    response_model=AdbAnalysisEnvelope,
)
@router.get(
    "/adb/comparison",
    operation_id="get_adb_comparison",
    response_model=AdbAnalysisEnvelope,
)
def adb_comparison(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    top_n: int = Query(20, ge=1, le=200),
):
    sd, ed = _parse_opt_date(start_date), _parse_opt_date(end_date)
    if sd is None or ed is None:
        raise HTTPException(
            status_code=422,
            detail=_error_detail("ADB_DATE_REQUIRED", "开始日期和结束日期不能为空。"),
        )
    from backend.app.governance.settings import get_settings

    _ensure_adb_analysis_read_allowed(auth, get_settings())
    try:
        return adb_analysis_service.adb_comparison_envelope(
            sd.isoformat(),
            ed.isoformat(),
            top_n=top_n,
        )
    # This route boundary sanitizes every service failure into the stable HTTP contract.
    except Exception as exc:  # noqa: BLE001
        _raise_adb_service_http_error(
            exc,
            operation="comparison",
            request_context=f"start_date={sd.isoformat()} end_date={ed.isoformat()}",
        )


@router.get(
    "/adb/insights",
    response_model=AdbInsightsEnvelope,
)
def adb_insights(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
):
    """区间深度分析：规模归因、NIM 量价分解、波动异常、结构集中度与结构化结论。"""
    sd, ed = _parse_opt_date(start_date), _parse_opt_date(end_date)
    if sd is None or ed is None:
        raise HTTPException(
            status_code=422,
            detail=_error_detail("ADB_DATE_REQUIRED", "开始日期和结束日期不能为空。"),
        )
    if sd > ed:
        raise HTTPException(
            status_code=400,
            detail=_error_detail("ADB_DATE_RANGE_INVALID", "开始日期不能晚于结束日期。"),
        )
    from backend.app.governance.settings import get_settings

    _ensure_adb_analysis_read_allowed(auth, get_settings())
    try:
        return adb_analysis_service.adb_insights_envelope(sd.isoformat(), ed.isoformat())
    # This route boundary sanitizes every service failure into the stable HTTP contract.
    except Exception as exc:  # noqa: BLE001
        _raise_adb_service_http_error(
            exc,
            operation="insights",
            request_context=f"start_date={sd.isoformat()} end_date={ed.isoformat()}",
        )


@router.get(
    "/adb/monthly",
    response_model=AdbAnalysisEnvelope,
)
def adb_monthly(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    year: int | None = Query(None, description="统计年份，默认为当前年"),
):
    y = year if year is not None else date.today().year
    from backend.app.governance.settings import get_settings

    _ensure_adb_analysis_read_allowed(auth, get_settings())
    try:
        return adb_analysis_service.adb_monthly_envelope(y)
    # This route boundary sanitizes every service failure into the stable HTTP contract.
    except Exception as exc:  # noqa: BLE001
        _raise_adb_service_http_error(
            exc,
            operation="monthly",
            request_context=f"year={y}",
        )


@router.get(
    "/adb/coverage",
    response_model=AdbCoverageResponse,
    response_model_exclude_none=True,
)
def adb_coverage(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
):
    """诊断 fact_formal 表在指定区间内的数据覆盖情况。"""
    sd, ed = _parse_opt_date(start_date), _parse_opt_date(end_date)
    if sd is None or ed is None:
        raise HTTPException(
            status_code=422,
            detail=_error_detail("ADB_DATE_REQUIRED", "开始日期和结束日期不能为空。"),
        )

    from backend.app.governance.settings import get_settings

    settings = get_settings()
    _ensure_adb_analysis_read_allowed(auth, settings)
    try:
        return adb_analysis_service.adb_coverage_diagnostics(sd.isoformat(), ed.isoformat())
    # This route boundary sanitizes every service failure into the stable HTTP contract.
    except Exception as exc:  # noqa: BLE001
        _raise_adb_service_http_error(
            exc,
            operation="coverage",
            request_context=f"start_date={sd.isoformat()} end_date={ed.isoformat()}",
        )


@router.post(
    "/adb/backfill",
    response_model=AdbBackfillResponse,
)
def adb_backfill(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
):
    """批量物化 fact_formal 表中缺失的日期。从快照表读取数据，生成 formal 表行。"""
    sd, ed = _parse_opt_date(start_date), _parse_opt_date(end_date)
    if sd is None or ed is None:
        raise HTTPException(
            status_code=422,
            detail=_error_detail("ADB_DATE_REQUIRED", "开始日期和结束日期不能为空。"),
        )
    if sd > ed:
        raise HTTPException(
            status_code=400,
            detail=_error_detail("ADB_DATE_RANGE_INVALID", "开始日期不能晚于结束日期。"),
        )
    if (ed - sd).days > 365:
        raise HTTPException(
            status_code=400,
            detail=_error_detail(
                "ADB_BACKFILL_RANGE_TOO_LARGE",
                "补建日期区间不能超过 365 天。",
            ),
        )

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
        logger.warning(
            "ADB backfill denied user_id=%s error_type=%s: %s",
            auth.user_id,
            type(exc).__name__,
            exc,
        )
        raise HTTPException(
            status_code=403,
            detail=_error_detail("ADB_BACKFILL_FORBIDDEN", "无权执行 ADB 补建。"),
        ) from exc
    except RuntimeError as exc:
        logger.error(
            "ADB backfill authorization unavailable user_id=%s error_type=%s: %s",
            auth.user_id,
            type(exc).__name__,
            exc,
        )
        raise HTTPException(
            status_code=503,
            detail=_error_detail(
                "ADB_AUTHORIZATION_UNAVAILABLE",
                "ADB 权限校验服务暂时不可用。",
            ),
        ) from exc
    try:
        return adb_analysis_service.dispatch_adb_backfill(sd.isoformat(), ed.isoformat())
    # This route boundary sanitizes every service failure into the stable HTTP contract.
    except Exception as exc:  # noqa: BLE001
        _raise_adb_service_http_error(
            exc,
            operation="backfill",
            request_context=f"start_date={sd.isoformat()} end_date={ed.isoformat()}",
        )
