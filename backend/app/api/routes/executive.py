from datetime import date

from fastapi import APIRouter, HTTPException

from backend.app.services.executive_service import (
    executive_alerts,
    executive_contribution,
    executive_overview,
    executive_pnl_attribution,
    executive_risk_overview,
    executive_summary,
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
) -> dict[str, object]:
    meta = payload.get("result_meta")
    if isinstance(meta, dict) and meta.get("vendor_status") == "vendor_unavailable":
        raise HTTPException(
            status_code=503,
            detail=f"Executive route {route_name} is not backed by governed data yet.",
        )
    return payload


@router.get("/home/overview")
def overview(report_date: str | None = None) -> dict[str, object]:
    return executive_overview(report_date=_normalize_report_date(report_date))


@router.get("/home/summary")
def summary() -> dict[str, object]:
    return executive_summary()


@router.get("/pnl/attribution")
def pnl_attribution(report_date: str | None = None) -> dict[str, object]:
    return executive_pnl_attribution(report_date=_normalize_report_date(report_date))


@router.get("/risk/overview")
def risk_overview(report_date: str | None = None) -> dict[str, object]:
    return _require_landed_executive_surface(
        executive_risk_overview(report_date=_normalize_report_date(report_date)),
        route_name="risk_overview",
    )


@router.get("/home/contribution")
def contribution(report_date: str | None = None) -> dict[str, object]:
    return _require_landed_executive_surface(
        executive_contribution(report_date=_normalize_report_date(report_date)),
        route_name="contribution",
    )


@router.get("/home/alerts")
def alerts(report_date: str | None = None) -> dict[str, object]:
    return _require_landed_executive_surface(
        executive_alerts(report_date=_normalize_report_date(report_date)),
        route_name="alerts",
    )
