import asyncio
import logging
import os
import threading
from contextlib import asynccontextmanager

from anyio import to_thread

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import validate_auth_startup_guardrails
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

_settings = get_settings()
validate_auth_startup_guardrails(_settings)

from backend.app.api import router as api_router  # noqa: E402
from backend.app.observability import setup_opentelemetry  # noqa: E402
from backend.app.services.executive_service import (  # noqa: E402
    warm_home_income_trend_cache_in_current_thread_if_configured,
    warm_home_snapshot_cache_blocking_if_configured,
)
from backend.app.services.hermes_agent_service import warm_hermes_bridge_if_configured  # noqa: E402
from backend.app.services.market_home_warmup_service import (  # noqa: E402
    warm_market_home_cache_in_current_thread_if_configured,
)
from backend.app.storage_bootstrap import run_startup_storage_migrations  # noqa: E402

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
logging.getLogger("backend.app.services.executive_service").setLevel(logging.INFO)


def warm_home_background_caches_if_configured(settings: object) -> bool:
    if not (
        bool(getattr(settings, "home_income_trend_prewarm_enabled", False))
        or bool(getattr(settings, "market_home_prewarm_enabled", False))
    ):
        return False
    thread = threading.Thread(
        target=_warm_home_background_caches_quietly,
        args=(settings,),
        daemon=True,
        name="moss-home-background-warmup",
    )
    thread.start()
    return True


def _warm_home_background_caches_quietly(settings: object) -> None:
    warm_home_income_trend_cache_in_current_thread_if_configured(settings)
    warm_market_home_cache_in_current_thread_if_configured(settings)


def _configured_api_threadpool_tokens(default: int = 80) -> int:
    raw = os.environ.get("MOSS_API_THREADPOOL_TOKENS", "").strip()
    try:
        value = int(raw) if raw else default
    except ValueError:
        return default
    return max(value, 1)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Nearly all routes are sync `def` and run on the AnyIO worker-thread pool
    # (40 tokens by default); raise the cap so slow endpoints don't starve fast ones.
    to_thread.current_default_thread_limiter().total_tokens = _configured_api_threadpool_tokens()
    # Blocking Postgres/DuckDB bootstrap off the event loop (Windows uvicorn + sync
    # drivers can otherwise stall startup indefinitely).
    await asyncio.to_thread(run_startup_storage_migrations)
    settings = get_settings()
    warm_hermes_bridge_if_configured(settings)
    await asyncio.to_thread(warm_home_snapshot_cache_blocking_if_configured, settings)
    warm_home_background_caches_if_configured(settings)
    yield


app = FastAPI(
    title="MOSS Agent Analytics OS",
    version="0.1.0",
    lifespan=lifespan,
)
setup_opentelemetry(app)
app.add_middleware(
    GZipMiddleware,
    minimum_size=1024,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Accept", "Authorization", "Content-Type", "X-User-Id", "X-User-Role"],
)
app.include_router(api_router)
