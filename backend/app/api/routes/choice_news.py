import re
from typing import Annotated

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.choice_news_service import (
    StockMatchMode,
    choice_news_latest_batch_envelope,
    choice_news_latest_envelope,
)
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter(prefix="/ui/news")
# Same ingest under `/api/news/...` so gateways that only forward `/api/**` still work (dev proxy already covers both).
router_api_news = APIRouter(prefix="/api/news")
_STOCK_CODE_CHOICE_NEWS_PATTERN = re.compile(r"^[0-9A-Za-z.\-]{1,16}$")
_CHOICE_NEWS_BATCH_MAX_ITEMS = 16
_CHOICE_NEWS_BATCH_LIMIT_MIN = 1
_CHOICE_NEWS_BATCH_LIMIT_MAX = 500


def _parse_choice_news_batch_requests(
    raw: str | None,
    *,
    param_name: str,
) -> list[tuple[str, int]]:
    """解析逗号分隔的 '<code>:<limit>' 对；非法格式抛 400。"""
    if raw is None or not raw.strip():
        return []
    requests: list[tuple[str, int]] = []
    for segment in raw.split(","):
        token = segment.strip()
        if not token:
            continue
        code_text, separator, limit_text = token.rpartition(":")
        code = code_text.strip()
        limit_token = limit_text.strip()
        if not separator or not code or not limit_token:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid {param_name} entry {token!r}. Expected '<code>:<limit>'.",
            )
        try:
            limit = int(limit_token)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid {param_name} entry {token!r}. limit must be an integer.",
            ) from exc
        if not (_CHOICE_NEWS_BATCH_LIMIT_MIN <= limit <= _CHOICE_NEWS_BATCH_LIMIT_MAX):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid {param_name} entry {token!r}. limit must be within "
                    f"{_CHOICE_NEWS_BATCH_LIMIT_MIN}..{_CHOICE_NEWS_BATCH_LIMIT_MAX}."
                ),
            )
        requests.append((code, limit))
    return requests


def _raise_choice_news_reserved_surface() -> None:
    raise HTTPException(
        status_code=503,
        detail="Choice news surfaces are reserved by the current boundary.",
    )


def _ensure_choice_news_ingest_allowed(auth: AuthContext) -> None:
    """授权先于保留判断：解除保留时替换函数体也不会出现无 RBAC 的写路径。"""
    settings = get_settings()
    try:
        ensure_user_allowed(
            auth=auth,
            settings=settings,
            resource="choice_news.data",
            action="import",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/choice-events/latest")
def choice_events_latest(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    group_id: str | None = None,
    topic_code: str | None = None,
    stock_code: str | None = Query(default=None, max_length=16),
    stock_name: str | None = Query(default=None, max_length=64),
    stock_match_mode: StockMatchMode = Query(default="best_effort"),
    include_payload_json: bool = Query(default=True),
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

    cleaned_stock_name = None
    if stock_name is not None and stock_name.strip():
        if cleaned_stock_code is None:
            raise HTTPException(
                status_code=400,
                detail="stock_name is only allowed as an alias when stock_code is provided.",
            )
        cleaned_stock_name = stock_name.strip().upper()

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
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return choice_news_latest_envelope(
        duckdb_path=str(settings.duckdb_path),
        limit=limit,
        offset=offset,
        group_id=group_id,
        topic_code=topic_code,
        stock_code=cleaned_stock_code,
        stock_name=cleaned_stock_name,
        stock_match_mode=stock_match_mode,
        include_payload_json=include_payload_json,
        error_only=error_only,
        received_from=received_from,
        received_to=received_to,
    )


@router.get("/choice-events/latest-batch")
def choice_events_latest_batch(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    topics: str | None = Query(
        default=None,
        description="Comma-separated '<topic_code>:<limit>' pairs, e.g. 'S888010007API:6,C000003002:6'.",
    ),
    groups: str | None = Query(
        default=None,
        description="Comma-separated '<group_id>:<limit>' pairs, e.g. 'tushare_news:8,tushare_major:8'.",
    ),
) -> dict[str, object]:
    topic_requests = _parse_choice_news_batch_requests(topics, param_name="topics")
    group_requests = _parse_choice_news_batch_requests(groups, param_name="groups")
    if not topic_requests and not group_requests:
        raise HTTPException(
            status_code=400,
            detail="At least one non-empty 'topics' or 'groups' parameter is required.",
        )
    total_items = len(topic_requests) + len(group_requests)
    if total_items > _CHOICE_NEWS_BATCH_MAX_ITEMS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Too many batch entries ({total_items}). "
                f"Maximum is {_CHOICE_NEWS_BATCH_MAX_ITEMS}."
            ),
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
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return choice_news_latest_batch_envelope(
        duckdb_path=str(settings.duckdb_path),
        topic_requests=topic_requests,
        group_requests=group_requests,
    )


@router.post("/tushare-npr/ingest")
def tushare_npr_ingest_ui(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    limit: int = Query(default=20, ge=1, le=500),
) -> dict[str, object]:
    _ensure_choice_news_ingest_allowed(auth)
    _raise_choice_news_reserved_surface()


@router_api_news.post("/tushare-npr/ingest")
def tushare_npr_ingest_api(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    limit: int = Query(default=20, ge=1, le=500),
) -> dict[str, object]:
    _ensure_choice_news_ingest_allowed(auth)
    _raise_choice_news_reserved_surface()
