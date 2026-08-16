import asyncio
import logging
import os
import threading
import time
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
from backend.app.api.response_cache import resolve_default_ttl  # noqa: E402
from backend.app.observability import setup_opentelemetry  # noqa: E402
from backend.app.services.executive_service import (  # noqa: E402
    warm_home_income_trend_cache_in_current_thread_if_configured,
    warm_home_snapshot_cache_blocking_if_configured,
    warm_home_snapshot_cache_if_configured,
)
from backend.app.services.hermes_agent_service import (  # noqa: E402
    stop_managed_hermes_bridge,
    warm_hermes_bridge_if_configured,
)
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

logger = logging.getLogger(__name__)

DEFAULT_HOME_BACKGROUND_WARMUP_DELAY_SECONDS = 2.0
_HOME_BACKGROUND_WARMUP_DELAY_ENV = "MOSS_HOME_BACKGROUND_WARMUP_DELAY_SECONDS"
# A warmed entry is only useful while the response cache still holds it. Refreshing
# at a fraction of the TTL keeps the dashboard-home keys resident, so a page load
# that arrives after an idle period does not pay the multi-second cold recompute.
HOME_BACKGROUND_WARMUP_REFRESH_RATIO = 0.8
_HOME_BACKGROUND_WARMUP_INTERVAL_ENV = "MOSS_HOME_BACKGROUND_WARMUP_INTERVAL_SECONDS"
# The home snapshot cache lives 3600s (executive_service._HOME_SNAPSHOT_CACHE_TTL_SECONDS)
# but was only warmed at boot, so the first request after an hour of uptime paid a
# full cold rebuild. Refresh it from the warmup loop at 80% of that TTL.
HOME_SNAPSHOT_REFRESH_INTERVAL_SECONDS = 2880.0


def resolve_home_background_warmup_delay_seconds(
    default: float = DEFAULT_HOME_BACKGROUND_WARMUP_DELAY_SECONDS,
) -> float:
    raw = os.getenv(_HOME_BACKGROUND_WARMUP_DELAY_ENV)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value >= 0 else default


def resolve_home_background_warmup_interval_seconds() -> float:
    """Seconds between warmup passes; a non-positive value keeps a single pass."""
    default = resolve_default_ttl() * HOME_BACKGROUND_WARMUP_REFRESH_RATIO
    raw = os.getenv(_HOME_BACKGROUND_WARMUP_INTERVAL_ENV)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def warm_home_background_caches_if_configured(settings: object) -> bool:
    if not (
        bool(getattr(settings, "home_income_trend_prewarm_enabled", False))
        or bool(getattr(settings, "market_home_prewarm_enabled", False))
    ):
        return False
    thread = threading.Thread(
        target=_warm_home_background_caches_periodically,
        args=(settings,),
        daemon=True,
        name="moss-home-background-warmup",
    )
    thread.start()
    return True


def _warm_home_background_caches_periodically(settings: object) -> None:
    _warm_home_background_caches_quietly(settings)
    interval_seconds = resolve_home_background_warmup_interval_seconds()
    if interval_seconds <= 0:
        return
    # The lifespan warmed the snapshot right before this thread started.
    snapshot_refreshed_at = time.monotonic()
    next_pass_at = time.monotonic() + interval_seconds
    while True:
        time.sleep(max(0.0, next_pass_at - time.monotonic()))
        # Anchor to a fixed cadence: sleeping a full interval *after* each pass
        # would stretch the effective period by the pass duration and could
        # drift past the response-cache TTL on slow passes.
        next_pass_at = max(next_pass_at + interval_seconds, time.monotonic())
        try:
            _run_home_background_warmup_pass(settings, force_refresh=True)
            if time.monotonic() - snapshot_refreshed_at >= HOME_SNAPSHOT_REFRESH_INTERVAL_SECONDS:
                warm_home_snapshot_cache_blocking_if_configured(settings, force_refresh=True)
                snapshot_refreshed_at = time.monotonic()
        except Exception:
            logger.exception("home_background_warmup_refresh_failed")


def _warm_home_background_caches_quietly(settings: object) -> None:
    delay_seconds = resolve_home_background_warmup_delay_seconds()
    if delay_seconds > 0:
        time.sleep(delay_seconds)
    _run_home_background_warmup_pass(settings)


def _run_home_background_warmup_pass(settings: object, *, force_refresh: bool = False) -> None:
    warm_home_income_trend_cache_in_current_thread_if_configured(
        settings,
        force_refresh=force_refresh,
    )
    warm_market_home_cache_in_current_thread_if_configured(
        settings,
        force_refresh=force_refresh,
    )


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
    # 首页快照预热可能耗时数十秒；它不应阻塞 /health 与其他页面 API 上线。
    # 预热状态已由 /health/ready.checks.home_snapshot_prewarm 单独披露。
    warm_home_snapshot_cache_if_configured(settings)
    warm_home_background_caches_if_configured(settings)
    yield
    stop_managed_hermes_bridge()


app = FastAPI(
    title="MOSS Agent Analytics OS",
    version="0.1.0",
    lifespan=lifespan,
)
setup_opentelemetry(app)
app.add_middleware(
    GZipMiddleware,
    minimum_size=1024,
    # Starlette defaults to level 9; measured on the home payloads it costs ~5x
    # the CPU of level 6 for a size difference within +-1.5% (sometimes larger).
    compresslevel=6,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Accept", "Authorization", "Content-Type", "X-User-Id", "X-User-Role"],
)
app.include_router(api_router)
