from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from typing import Annotated, cast

from backend.app.api.deps import ensure_read_allowed
from backend.app.governance.settings import get_settings
from backend.app.observability.response_cache import CacheBuildTimeoutError, market_home_response_cache
from backend.app.schemas.market_overview import MarketOverviewSnapshotEnvelope
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.macro_toolkit_refresh_receipt_service import (
    load_macro_toolkit_refresh_receipt_health,
)
from backend.app.services.market_overview_service import (
    DEFAULT_MARKET_OVERVIEW_INCLUDE,
    MARKET_OVERVIEW_UNAVAILABLE_CACHE_TTL_SECONDS,
    SUPPORTED_MARKET_OVERVIEW_INCLUDE,
    build_market_snapshot,
    market_overview_response_requires_short_cache,
    market_overview_snapshot_cache_key,
)
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter(prefix="/ui/market-overview", tags=["market-overview"])
logger = logging.getLogger(__name__)
@router.get(
    "/snapshot",
    response_model=MarketOverviewSnapshotEnvelope,
    response_model_exclude_unset=True,
)
def market_overview_snapshot(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    include: str | None = Query(default=None),
) -> dict[str, object]:
    settings = get_settings()
    ensure_read_allowed(
        auth,
        "macro_toolkit",
        settings=settings,
        authorize=ensure_user_allowed,
    )
    resolved_include = _parse_include(include)
    refresh_receipt_health = load_macro_toolkit_refresh_receipt_health()
    cache_key = market_overview_snapshot_cache_key(
        include=resolved_include,
        duckdb_path=str(settings.duckdb_path),
        freshness_fingerprint=refresh_receipt_health.cache_fingerprint,
    )
    started = time.perf_counter()
    try:
        payload, cache_status = market_home_response_cache.get_or_build_with_status(
            cache_key,
            lambda: build_market_snapshot(
                include=resolved_include,
                duckdb_path=str(settings.duckdb_path),
                refresh_receipt_health=refresh_receipt_health,
            ),
        )
    except CacheBuildTimeoutError as exc:
        raise HTTPException(
            status_code=503,
            detail="市场快照仍在加载，请稍后重试。",
            headers={"Retry-After": "15"},
        ) from exc
    result = cast(Mapping[str, object], payload.get("result", {}))
    components = cast(Mapping[str, object], result.get("components", {}))
    load_failures = sum(
        isinstance(component, dict)
        and component.get("status") == "unavailable"
        and str(component.get("reason") or "").startswith("component load failed:")
        for component in components.values()
    )
    short_cache_required = market_overview_response_requires_short_cache(payload)
    if short_cache_required:
        market_home_response_cache.shorten_if_same(
            cache_key,
            payload,
            ttl_seconds=MARKET_OVERVIEW_UNAVAILABLE_CACHE_TTL_SECONDS,
        )
    logger.info(
        "market_overview_snapshot_read cache_status=%s load_failures=%d short_cache=%s elapsed_ms=%.1f",
        cache_status,
        load_failures,
        short_cache_required,
        (time.perf_counter() - started) * 1000,
    )
    return payload


def _parse_include(include: str | None) -> frozenset[str]:
    parsed = frozenset(item.strip().lower() for item in str(include or "").split(",") if item.strip())
    if not parsed:
        return DEFAULT_MARKET_OVERVIEW_INCLUDE
    unsupported = sorted(parsed - SUPPORTED_MARKET_OVERVIEW_INCLUDE)
    if unsupported:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported market-overview include values: {', '.join(unsupported)}",
        )
    return parsed
