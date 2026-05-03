from datetime import date

from fastapi import APIRouter, HTTPException

from backend.app.services.executive_service import (
    executive_alerts,
    executive_contribution,
    executive_overview,
    executive_pnl_attribution,
    executive_risk_overview,
    executive_summary,
    home_snapshot_envelope,
)

router = APIRouter(prefix="/ui")


def _normalize_report_date(report_date: str | None) -> str | None:
    if report_date is None:
        return None
    candidate = str(report_date).strip()
    try:
        return date.fromisoformat(candidate).isoformat()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="report_date must be a valid calendar date in YYYY-MM-DD format.") from exc


def _require_landed_executive_surface(
    payload: dict[str, object],
    *,
    route_name: str,
    promoted: bool = True,
) -> dict[str, object]:
    if not promoted:
        raise HTTPException(
            status_code=503,
            detail=f"Executive route {route_name} is not backed by governed data yet.",
        )
    meta = payload.get("result_meta")
    if isinstance(meta, dict) and meta.get("vendor_status") == "vendor_unavailable":
        raise HTTPException(
            status_code=503,
            detail=f"Executive route {route_name} is not backed by governed data yet.",
        )
    return payload


def _raise_executive_reserved_surface(route_name: str) -> None:
    raise HTTPException(
        status_code=503,
        detail=f"Executive route {route_name} is reserved by the current boundary.",
    )


@router.get("/home/overview")
def overview(report_date: str | None = None) -> dict[str, object]:
    return executive_overview(report_date=_normalize_report_date(report_date))


@router.get("/home/summary")
def summary(report_date: str | None = None) -> dict[str, object]:
    return executive_summary(report_date=_normalize_report_date(report_date))


@router.get("/pnl/attribution")
def pnl_attribution(report_date: str | None = None) -> dict[str, object]:
    return executive_pnl_attribution(report_date=_normalize_report_date(report_date))


@router.get("/risk/overview")
def risk_overview(report_date: str | None = None) -> dict[str, object]:
    _raise_executive_reserved_surface("risk_overview")


@router.get("/home/contribution")
def contribution(report_date: str | None = None) -> dict[str, object]:
    _raise_executive_reserved_surface("contribution")


@router.get("/home/alerts")
def alerts(report_date: str | None = None) -> dict[str, object]:
    _raise_executive_reserved_surface("alerts")


@router.get("/home/snapshot")
def home_snapshot(
    report_date: str | None = None,
    allow_partial: bool = False,
) -> dict[str, object]:
    _raise_executive_reserved_surface("home_snapshot")
