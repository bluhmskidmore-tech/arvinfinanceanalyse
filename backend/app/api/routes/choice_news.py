from fastapi import APIRouter, HTTPException, Query

from backend.app.governance.settings import get_settings
from backend.app.services.choice_news_service import choice_news_latest_envelope
from backend.app.services.tushare_news_ingest_service import ingest_tushare_npr_to_choice_news

router = APIRouter(prefix="/ui/news")
# Same ingest under `/api/news/...` so gateways that only forward `/api/**` still work (dev proxy already covers both).
router_api_news = APIRouter(prefix="/api/news")


@router.get("/choice-events/latest")
def choice_events_latest(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    group_id: str | None = None,
    topic_code: str | None = None,
    error_only: bool = False,
    received_from: str | None = None,
    received_to: str | None = None,
) -> dict[str, object]:
    settings = get_settings()
    return choice_news_latest_envelope(
        settings.duckdb_path,
        limit=limit,
        offset=offset,
        group_id=group_id,
        topic_code=topic_code,
        error_only=error_only,
        received_from=received_from,
        received_to=received_to,
    )


def _tushare_npr_ingest_handler(limit: int) -> dict[str, object]:
    """Pull Tushare `pro.npr` headlines into `choice_news_event` (local dev / fallback)."""
    settings = get_settings()
    try:
        return ingest_tushare_npr_to_choice_news(settings.duckdb_path, limit=limit)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Tushare ingest failed: {exc}") from exc


@router.post("/tushare-npr/ingest")
def tushare_npr_ingest_ui(
    limit: int = Query(default=20, ge=1, le=500),
) -> dict[str, object]:
    return _tushare_npr_ingest_handler(limit)


@router_api_news.post("/tushare-npr/ingest")
def tushare_npr_ingest_api(
    limit: int = Query(default=20, ge=1, le=500),
) -> dict[str, object]:
    return _tushare_npr_ingest_handler(limit)
