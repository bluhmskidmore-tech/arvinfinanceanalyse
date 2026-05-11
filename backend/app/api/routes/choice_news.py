import re
from typing import Annotated

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.choice_news_service import choice_news_latest_envelope
from backend.app.services.tushare_news_ingest_service import ingest_tushare_npr_to_choice_news
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter(prefix="/ui/news")
# Same ingest under `/api/news/...` so gateways that only forward `/api/**` still work (dev proxy already covers both).
router_api_news = APIRouter(prefix="/api/news")
_STOCK_CODE_CHOICE_NEWS_PATTERN = re.compile(r"^[0-9A-Za-z.\-]{1,16}$")


def _raise_choice_news_reserved_surface() -> None:
    raise HTTPException(
        status_code=503,
        detail="Choice news surfaces are reserved by the current boundary.",
    )


@router.get("/choice-events/latest")
def choice_events_latest(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    group_id: str | None = None,
    topic_code: str | None = None,
    stock_code: str | None = Query(default=None, max_length=16),
    error_only: bool = False,
    received_from: str | None = None,
    received_to: str | None = None,
) -> dict[str, object]:
    cleaned_stock_code = None
    if stock_code is not None and stock_code.strip():
        cleaned_stock_code = stock_code.strip().upper()
        if not _STOCK_CODE_CHOICE_NEWS_PATTERN.fullmatch(cleaned_stock_code):
            raise HTTPException(
                status_code=400,
                detail="Invalid stock_code. Allowed characters: letters, digits, '.', '-'.",
            )

    settings = get_settings()
    try:
        ensure_user_allowed(
            auth=auth,
            settings=settings,
            resource="choice_news.data",
            action="read",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return choice_news_latest_envelope(
        duckdb_path=str(settings.duckdb_path),
        limit=limit,
        offset=offset,
        group_id=group_id,
        topic_code=topic_code,
        stock_code=cleaned_stock_code,
        error_only=error_only,
        received_from=received_from,
        received_to=received_to,
    )


def _tushare_npr_ingest_handler(limit: int, auth: AuthContext) -> dict[str, object]:
    """Pull Tushare `pro.npr` headlines into `choice_news_event` (local dev / fallback)."""
    settings = get_settings()
    try:
        ensure_user_allowed(auth=auth, settings=settings, resource="choice_news.data", action="import")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        return ingest_tushare_npr_to_choice_news(settings.duckdb_path, limit=limit)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Tushare ingest failed: {exc}") from exc


@router.post("/tushare-npr/ingest")
def tushare_npr_ingest_ui(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    limit: int = Query(default=20, ge=1, le=500),
) -> dict[str, object]:
    _raise_choice_news_reserved_surface()


@router_api_news.post("/tushare-npr/ingest")
def tushare_npr_ingest_api(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    limit: int = Query(default=20, ge=1, le=500),
) -> dict[str, object]:
    _raise_choice_news_reserved_surface()
