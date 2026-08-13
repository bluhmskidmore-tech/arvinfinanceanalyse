"""HTTP routes for positions / snapshot drill-down read APIs."""
from __future__ import annotations

from datetime import date
from typing import Annotated

import backend.app.services.positions_service as positions_service
from backend.app.api.deps import ensure_read_allowed
from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter(prefix="/api/positions", tags=["positions"])


def _bad_date(detail: str) -> HTTPException:
    return HTTPException(status_code=422, detail=detail)


def _date_string(value: date | None) -> str:
    return value.isoformat() if value is not None else ""


def _validated_date_range(start_date: date, end_date: date) -> tuple[str, str]:
    if start_date > end_date:
        raise _bad_date("start_date must be on or before end_date.")
    return start_date.isoformat(), end_date.isoformat()


def _ensure_positions_read_allowed(auth: AuthContext) -> None:
    # allow_dev_fallback 与 balance_analysis 等读路由对齐：仅在 development 环境
    # 且身份为匿名 viewer 回退时放行，显式身份缺 scope 仍 403（契约测试锁定）。
    ensure_read_allowed(
        auth,
        "positions",
        settings=get_settings(),
        allow_dev_fallback=True,
        authorize=ensure_user_allowed,
    )


@router.get("/bonds/sub_types")
def bonds_sub_types(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: date | None = Query(None),
):
    _ensure_positions_read_allowed(auth)
    return positions_service.bond_sub_types_envelope(_date_string(report_date))


@router.get("/bonds")
def bonds_list(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: date = Query(..., description="YYYY-MM-DD"),
    sub_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    include_issued: bool = Query(False),
):
    _ensure_positions_read_allowed(auth)
    return positions_service.bonds_list_envelope(
        report_date=report_date.isoformat(),
        sub_type=sub_type.strip() if sub_type else None,
        page=page,
        page_size=page_size,
        include_issued=include_issued,
    )


@router.get("/counterparty/bonds")
def counterparty_bonds(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    start_date: date = Query(..., description="YYYY-MM-DD"),
    end_date: date = Query(..., description="YYYY-MM-DD"),
    sub_type: str | None = Query(None),
    top_n: int | None = Query(None, ge=1, le=5000),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    _ensure_positions_read_allowed(auth)
    sd, ed = _validated_date_range(start_date, end_date)
    return positions_service.counterparty_bonds_envelope(
        start_date=sd,
        end_date=ed,
        sub_type=sub_type.strip() if sub_type else None,
        top_n=top_n,
        page=page,
        page_size=page_size,
    )


@router.get("/interbank/product_types")
def interbank_product_types(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: date | None = Query(None),
):
    _ensure_positions_read_allowed(auth)
    return positions_service.interbank_product_types_envelope(_date_string(report_date))


@router.get("/interbank")
def interbank_list(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: date = Query(..., description="YYYY-MM-DD"),
    product_type: str | None = Query(None),
    direction: str | None = Query(None, description="Asset | Liability | ALL"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
):
    _ensure_positions_read_allowed(auth)
    if direction is not None and direction not in ("Asset", "Liability", "ALL"):
        raise _bad_date("direction must be Asset, Liability, ALL, or omitted.")
    return positions_service.interbank_list_envelope(
        report_date=report_date.isoformat(),
        product_type=product_type.strip() if product_type else None,
        direction=direction,
        page=page,
        page_size=page_size,
    )


@router.get("/counterparty/interbank/split")
def counterparty_interbank_split(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    start_date: date = Query(...),
    end_date: date = Query(...),
    product_type: str | None = Query(None),
    top_n: int | None = Query(None, ge=1, le=5000),
):
    _ensure_positions_read_allowed(auth)
    sd, ed = _validated_date_range(start_date, end_date)
    return positions_service.counterparty_interbank_split_envelope(
        start_date=sd,
        end_date=ed,
        product_type=product_type.strip() if product_type else None,
        top_n=top_n,
    )


@router.get("/stats/rating")
def stats_rating(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    start_date: date = Query(...),
    end_date: date = Query(...),
    sub_type: str | None = Query(None),
):
    _ensure_positions_read_allowed(auth)
    sd, ed = _validated_date_range(start_date, end_date)
    return positions_service.stats_rating_envelope(
        start_date=sd,
        end_date=ed,
        sub_type=sub_type.strip() if sub_type else None,
    )


@router.get("/stats/industry")
def stats_industry(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    start_date: date = Query(...),
    end_date: date = Query(...),
    sub_type: str | None = Query(None),
    top_n: int | None = Query(None, ge=1, le=500),
):
    _ensure_positions_read_allowed(auth)
    sd, ed = _validated_date_range(start_date, end_date)
    return positions_service.stats_industry_envelope(
        start_date=sd,
        end_date=ed,
        sub_type=sub_type.strip() if sub_type else None,
        top_n=top_n,
    )


@router.get("/customer/details")
def customer_details(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    customer_name: str = Query(...),
    report_date: date | None = Query(None),
):
    _ensure_positions_read_allowed(auth)
    name = customer_name.strip()
    if not name:
        raise _bad_date("customer_name is required.")
    return positions_service.customer_details_envelope(
        customer_name=name,
        report_date=_date_string(report_date),
    )


@router.get("/customer/trend")
def customer_trend(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    customer_name: str = Query(...),
    end_date: date | None = Query(None),
    days: int = Query(30, ge=1, le=3660),
):
    _ensure_positions_read_allowed(auth)
    name = customer_name.strip()
    if not name:
        raise _bad_date("customer_name is required.")
    ed = _date_string(end_date) or date.today().isoformat()
    return positions_service.customer_trend_envelope(
        customer_name=name,
        end_date=ed,
        days=days,
    )
