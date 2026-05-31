from datetime import date

from backend.app.api.perf_logging import timed_api_call
from backend.app.services.executive_service import (
    executive_alerts,  # noqa: F401 - reserved route contract monkeypatch target
    executive_contribution,  # noqa: F401 - reserved route contract monkeypatch target
    executive_overview,
    executive_pnl_attribution,
    executive_risk_overview,  # noqa: F401 - reserved route contract monkeypatch target
    executive_summary,
    home_income_trend_envelope,
    home_research_reports_envelope,
    home_snapshot_envelope,
)
from fastapi import APIRouter, HTTPException, Query

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
    normalized_report_date = _normalize_report_date(report_date)
    return timed_api_call(
        "/ui/home/snapshot",
        lambda: home_snapshot_envelope(
            report_date=normalized_report_date,
            allow_partial=allow_partial,
        ),
    )


@router.get("/home/research-reports")
def home_research_reports(
    report_date: str,
    limit: int = Query(5, ge=1, le=20),
) -> dict[str, object]:
    normalized_report_date = _normalize_report_date(report_date)
    assert normalized_report_date is not None
    return timed_api_call(
        "/ui/home/research-reports",
        lambda: home_research_reports_envelope(
            report_date=normalized_report_date,
            limit=limit,
        ),
    )


@router.get("/home/income-trend")
def home_income_trend(
    report_date: str,
    window: int = Query(7, ge=1, le=30),
) -> dict[str, object]:
    normalized_report_date = _normalize_report_date(report_date)
    assert normalized_report_date is not None
    return timed_api_call(
        "/ui/home/income-trend",
        lambda: home_income_trend_envelope(
            report_date=normalized_report_date,
            window=window,
        ),
    )
