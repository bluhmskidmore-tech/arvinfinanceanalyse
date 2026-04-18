from fastapi import APIRouter, Query

from backend.app.governance.settings import get_settings
from backend.app.services.choice_news_service import (
    ChoiceNewsReadError,
    choice_news_latest_envelope,
)

router = APIRouter(prefix="/ui/news")


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
    try:
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
    except ChoiceNewsReadError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail=str(exc)) from exc
