from __future__ import annotations

from datetime import date
from typing import Annotated

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.macro_etf_strategy_service import macro_etf_strategy_envelope
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter(prefix="/ui/market-data", tags=["market-data"])


@router.get("/macro-etf-strategy")
def macro_etf_strategy(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    as_of_date: str | None = Query(default=None, min_length=8, max_length=10),
) -> dict[str, object]:
    settings = get_settings()
    _ensure_macro_etf_strategy_read_allowed(auth=auth, settings=settings)
    if as_of_date is not None:
        try:
            date.fromisoformat(as_of_date[:10])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid as_of_date. Expected YYYY-MM-DD.") from exc
    return macro_etf_strategy_envelope(
        as_of_date=as_of_date,
        duckdb_path=settings.duckdb_path,
    )


def _ensure_macro_etf_strategy_read_allowed(*, auth: AuthContext, settings: object) -> None:
    try:
        ensure_user_allowed(
            auth=auth,
            settings=settings,
            resource="market_data.macro_etf_strategy",
            action="read",
        )
    except PermissionError as exc:
        if _allows_development_fallback_read(auth=auth, environment=getattr(settings, "environment", "")):
            return
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        if _allows_development_fallback_read(auth=auth, environment=getattr(settings, "environment", "")):
            return
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _allows_development_fallback_read(*, auth: AuthContext, environment: object) -> bool:
    return (
        str(environment).strip().lower() == "development"
        and auth.identity_source == "fallback"
        and auth.user_id == "anonymous"
        and auth.role == "viewer"
    )
