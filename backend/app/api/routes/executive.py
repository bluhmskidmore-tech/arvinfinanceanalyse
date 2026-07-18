from datetime import date, timedelta
from pathlib import Path
from typing import Annotated

from backend.app.api.perf_logging import timed_api_call
from backend.app.governance.settings import get_settings
from backend.app.repositories.home_macro_release_context_repo import (
    HomeMacroReleaseContextRepository,
)
from backend.app.schemas.executive_dashboard import ExecutiveOverviewEnvelope
from backend.app.schemas.home_macro_release_context import HomeMacroReleaseContextEnvelope
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
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
from backend.app.services.home_macro_release_context_service import (
    HomeMacroReleaseContextService,
)
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter(prefix="/ui")

_HOME_MACRO_RELEASE_BINDINGS = Path(__file__).resolve().parents[4] / "config" / "home_macro_release_bindings.json"

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


def _ensure_executive_read_allowed(auth: AuthContext) -> None:
    try:
        ensure_user_allowed(
            auth=auth,
            settings=get_settings(),
            resource="executive",
            action="read",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/home/overview", response_model=ExecutiveOverviewEnvelope)
def overview(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str | None = None,
) -> dict[str, object]:
    _ensure_executive_read_allowed(auth)
    return executive_overview(report_date=_normalize_report_date(report_date))


@router.get("/home/summary")
def summary(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str | None = None,
) -> dict[str, object]:
    _ensure_executive_read_allowed(auth)
    return executive_summary(report_date=_normalize_report_date(report_date))


@router.get("/pnl/attribution")
def pnl_attribution(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str | None = None,
) -> dict[str, object]:
    _ensure_executive_read_allowed(auth)
    return executive_pnl_attribution(report_date=_normalize_report_date(report_date))


@router.get("/risk/overview")
def risk_overview(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str | None = None,
) -> dict[str, object]:
    _ensure_executive_read_allowed(auth)
    _raise_executive_reserved_surface("risk_overview")


@router.get("/home/contribution")
def contribution(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str | None = None,
) -> dict[str, object]:
    _ensure_executive_read_allowed(auth)
    _raise_executive_reserved_surface("contribution")


@router.get("/home/alerts")
def alerts(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str | None = None,
) -> dict[str, object]:
    _ensure_executive_read_allowed(auth)
    _raise_executive_reserved_surface("alerts")


@router.get("/home/snapshot")
def home_snapshot(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str | None = None,
    allow_partial: bool = False,
) -> dict[str, object]:
    normalized_report_date = _normalize_report_date(report_date)
    _ensure_executive_read_allowed(auth)
    return timed_api_call(
        "/ui/home/snapshot",
        lambda: _require_landed_executive_surface(
            home_snapshot_envelope(
                report_date=normalized_report_date,
                allow_partial=allow_partial,
            ),
            route_name="home_snapshot",
        ),
    )


@router.get("/home/research-reports")
def home_research_reports(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str,
    limit: int = Query(5, ge=1, le=20),
) -> dict[str, object]:
    normalized_report_date = _normalize_report_date(report_date)
    assert normalized_report_date is not None
    _ensure_executive_read_allowed(auth)
    return timed_api_call(
        "/ui/home/research-reports",
        lambda: home_research_reports_envelope(
            report_date=normalized_report_date,
            limit=limit,
        ),
    )


@router.get("/home/income-trend")
def home_income_trend(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_date: str,
    window: int = Query(7, ge=1, le=30),
) -> dict[str, object]:
    normalized_report_date = _normalize_report_date(report_date)
    assert normalized_report_date is not None
    _ensure_executive_read_allowed(auth)
    return timed_api_call(
        "/ui/home/income-trend",
        lambda: home_income_trend_envelope(
            report_date=normalized_report_date,
            window=window,
        ),
    )


@router.get(
    "/home/macro-release-context",
    response_model=HomeMacroReleaseContextEnvelope,
)
def home_macro_release_context(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    start_date: date | None = None,
    end_date: date | None = None,
    history_limit: int = Query(8, ge=1, le=20),
) -> HomeMacroReleaseContextEnvelope:
    _ensure_executive_read_allowed(auth)
    effective_start = start_date or date.today()
    effective_end = end_date or effective_start + timedelta(days=45)
    if effective_end < effective_start:
        raise HTTPException(
            status_code=422,
            detail="end_date must be on or after start_date.",
        )

    settings = get_settings()
    service = HomeMacroReleaseContextService(
        repository=HomeMacroReleaseContextRepository(settings.duckdb_path),
        bindings_path=_HOME_MACRO_RELEASE_BINDINGS,
    )
    return timed_api_call(
        "/ui/home/macro-release-context",
        lambda: service.build_envelope(
            window_start_date=effective_start,
            window_end_date=effective_end,
            history_limit=history_limit,
        ),
    )
