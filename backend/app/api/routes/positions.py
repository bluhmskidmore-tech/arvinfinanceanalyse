"""HTTP routes for positions / snapshot drill-down read APIs."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query

import backend.app.services.positions_service as positions_service

router = APIRouter(prefix="/api/positions", tags=["positions"])


def _bad_date(detail: str) -> HTTPException:
    return HTTPException(status_code=422, detail=detail)


@router.get("/bonds/sub_types")
def bonds_sub_types(report_date: str | None = Query(None)):
    return positions_service.bond_sub_types_envelope((report_date or "").strip())


@router.get("/bonds")
def bonds_list(
    report_date: str = Query(..., description="YYYY-MM-DD"),
    sub_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    include_issued: bool = Query(False),
):
    rd = report_date.strip()
    if not rd:
        raise _bad_date("report_date is required.")
    return positions_service.bonds_list_envelope(
        report_date=rd,
        sub_type=sub_type.strip() if sub_type else None,
        page=page,
        page_size=page_size,
        include_issued=include_issued,
    )


@router.get("/counterparty/bonds")
def counterparty_bonds(
    start_date: str = Query(..., description="YYYY-MM-DD"),
    end_date: str = Query(..., description="YYYY-MM-DD"),
    sub_type: str | None = Query(None),
    top_n: int | None = Query(None, ge=1, le=5000),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    sd, ed = start_date.strip(), end_date.strip()
    if not sd or not ed:
        raise _bad_date("start_date and end_date are required.")
    return positions_service.counterparty_bonds_envelope(
        start_date=sd,
        end_date=ed,
        sub_type=sub_type.strip() if sub_type else None,
        top_n=top_n,
        page=page,
        page_size=page_size,
    )


@router.get("/interbank/product_types")
def interbank_product_types(report_date: str | None = Query(None)):
    return positions_service.interbank_product_types_envelope((report_date or "").strip())


@router.get("/interbank")
def interbank_list(
    report_date: str = Query(..., description="YYYY-MM-DD"),
    product_type: str | None = Query(None),
    direction: str | None = Query(None, description="Asset | Liability | ALL"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
):
    rd = report_date.strip()
    if not rd:
        raise _bad_date("report_date is required.")
    if direction is not None and direction not in ("Asset", "Liability", "ALL"):
        raise _bad_date("direction must be Asset, Liability, ALL, or omitted.")
    return positions_service.interbank_list_envelope(
        report_date=rd,
        product_type=product_type.strip() if product_type else None,
        direction=direction,
        page=page,
        page_size=page_size,
    )


@router.get("/counterparty/interbank/split")
def counterparty_interbank_split(
    start_date: str = Query(...),
    end_date: str = Query(...),
    product_type: str | None = Query(None),
    top_n: int | None = Query(None, ge=1, le=5000),
):
    sd, ed = start_date.strip(), end_date.strip()
    if not sd or not ed:
        raise _bad_date("start_date and end_date are required.")
    return positions_service.counterparty_interbank_split_envelope(
        start_date=sd,
        end_date=ed,
        product_type=product_type.strip() if product_type else None,
        top_n=top_n,
    )


@router.get("/stats/rating")
def stats_rating(
    start_date: str = Query(...),
    end_date: str = Query(...),
    sub_type: str | None = Query(None),
):
    sd, ed = start_date.strip(), end_date.strip()
    if not sd or not ed:
        raise _bad_date("start_date and end_date are required.")
    return positions_service.stats_rating_envelope(
        start_date=sd,
        end_date=ed,
        sub_type=sub_type.strip() if sub_type else None,
    )


@router.get("/stats/industry")
def stats_industry(
    start_date: str = Query(...),
    end_date: str = Query(...),
    sub_type: str | None = Query(None),
    top_n: int | None = Query(None, ge=1, le=500),
):
    sd, ed = start_date.strip(), end_date.strip()
    if not sd or not ed:
        raise _bad_date("start_date and end_date are required.")
    return positions_service.stats_industry_envelope(
        start_date=sd,
        end_date=ed,
        sub_type=sub_type.strip() if sub_type else None,
        top_n=top_n,
    )


@router.get("/customer/details")
def customer_details(
    customer_name: str = Query(...),
    report_date: str | None = Query(None),
):
    name = customer_name.strip()
    if not name:
        raise _bad_date("customer_name is required.")
    return positions_service.customer_details_envelope(
        customer_name=name,
        report_date=(report_date or "").strip(),
    )


@router.get("/customer/trend")
def customer_trend(
    customer_name: str = Query(...),
    end_date: str | None = Query(None),
    days: int = Query(30, ge=1, le=3660),
):
    name = customer_name.strip()
    if not name:
        raise _bad_date("customer_name is required.")
    ed = (end_date or "").strip() or date.today().isoformat()
    return positions_service.customer_trend_envelope(
        customer_name=name,
        end_date=ed,
        days=days,
    )
