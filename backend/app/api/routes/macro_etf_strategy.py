from __future__ import annotations

from datetime import date
from typing import Annotated

from backend.app.api.deps import ensure_read_allowed
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
    ensure_read_allowed(
        auth,
        "market_data.macro_etf_strategy",
        settings=settings,
        allow_dev_fallback=True,
        allow_dev_fallback_on_unavailable=True,
        authorize=ensure_user_allowed,
    )
