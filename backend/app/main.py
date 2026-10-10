import asyncio
import logging
import os
import threading
import time
from collections.abc import Callable
from contextlib import asynccontextmanager

from anyio import to_thread
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.app.governance.settings import get_settings
from backend.app.repositories.duckdb_read_context import DuckDBReadSelectionError
from backend.app.repositories.financial_result_publication_repo import FinancialPublicationError
from backend.app.repositories.system_read_publication_repo import (
    SYSTEM_READ_GENERATION_HEADER,
    SystemReadSettings,
    active_system_read_scope,
    async_system_read_scope,
    resolve_system_read_publication,
    system_read_scope,
)
from backend.app.security.auth_context import get_auth_context, validate_auth_startup_guardrails
from backend.app.security.local_access import LocalDevelopmentAccessMiddleware

# Configured before validate_auth_startup_guardrails() so its startup security
# banner (logger.warning in development, logger.info otherwise) is never lost
# to Python's WARNING-only "no handlers configured" lastResort fallback.
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
logging.getLogger("backend.app.services.executive_service").setLevel(logging.INFO)

logger = logging.getLogger(__name__)

_settings = get_settings()
validate_auth_startup_guardrails(_settings)

from backend.app.api import router as api_router  # noqa: E402
from backend.app.api.deps import ensure_read_allowed  # noqa: E402
from backend.app.observability import setup_opentelemetry  # noqa: E402
from backend.app.observability.response_cache import resolve_default_ttl  # noqa: E402
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
_SYSTEM_READ_LIVE_GET_PATHS = frozenset(
    {
        "/health",
        "/health/live",
        "/api/bond-analytics/refresh-status",
        "/ui/balance-analysis/current-user",
        "/ui/balance-analysis/refresh-status",
    }
)


class SystemReadPublicationMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        settings_provider: Callable[[], SystemReadSettings] = get_settings,
    ) -> None:
        self.app = app
        self._settings_provider = settings_provider

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        settings = self._settings_provider()
        if not bool(
            getattr(settings, "system_read_publication_enabled", False)
        ):
            await self.app(scope, receive, send)
            return
        method = str(scope.get("method") or "").upper()
        path = str(scope.get("path") or "")
        is_read_request = method in {"GET", "HEAD"} or (
            method == "POST" and path == "/api/cube/query"
        )
        if path in _SYSTEM_READ_LIVE_GET_PATHS or not is_read_request:
            with active_system_read_scope():
                await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        if method in {"GET", "HEAD"} and path.rstrip("/") == "/api/system-read-publication":
            # The handshake discloses the selected generation. Check its own
            # read policy before loading publication artifacts or adding headers.
            auth = get_auth_context(
                request=Request(scope),
                x_user_id=headers.get("X-User-Id"),
                x_user_role=headers.get("X-User-Role"),
            )
            try:
                await to_thread.run_sync(
                    lambda: ensure_read_allowed(
                        auth, "data_health", settings=settings, allow_dev_fallback=True,
                    )
                )
            except HTTPException as exc:
                response = JSONResponse(
                    status_code=exc.status_code,
                    content={"detail": exc.detail},
                    headers=exc.headers,
                )
                await response(scope, receive, send)
                return

        requested_generation = headers.get(SYSTEM_READ_GENERATION_HEADER)
        response_started = False
        try:
            async with async_system_read_scope(settings, generation=requested_generation) as publication:
                assert publication is not None

                async def send_with_generation(message: Message) -> None:
                    nonlocal response_started
                    if message["type"] == "http.response.start":
                        response_started = True
                        MutableHeaders(scope=message)[SYSTEM_READ_GENERATION_HEADER] = (
                            publication.generation
                        )
                    await send(message)

                await self.app(scope, receive, send_with_generation)
        except (FinancialPublicationError, DuckDBReadSelectionError):
            logger.exception("system_read_publication_request_rejected")
            if response_started:
                raise
            response = JSONResponse(
                status_code=503,
                content={"detail": "A valid system read publication is unavailable."},
            )
            await response(scope, receive, send)


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


def warm_home_background_caches_if_configured(settings: SystemReadSettings) -> bool:
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


def _warm_home_background_caches_periodically(settings: SystemReadSettings) -> None:
    started_at = time.monotonic()
    _warm_home_background_caches_quietly(settings)
    interval_seconds = resolve_home_background_warmup_interval_seconds()
    if interval_seconds <= 0:
        return
    # The lifespan warmed the snapshot right before this thread started.
    snapshot_refreshed_at = started_at
    # Count the initial pass too: its early entries can otherwise expire while
    # a full interval is added after the remaining (slower) warmup steps.
    next_pass_at = started_at + interval_seconds
    while True:
        time.sleep(max(0.0, next_pass_at - time.monotonic()))
        # Anchor to a fixed cadence: sleeping a full interval *after* each pass
        # would stretch the effective period by the pass duration and could
        # drift past the response-cache TTL on slow passes.
        next_pass_at = max(next_pass_at + interval_seconds, time.monotonic())
        try:
            _run_home_background_warmup_pass(settings, force_refresh=True)
            if time.monotonic() - snapshot_refreshed_at >= HOME_SNAPSHOT_REFRESH_INTERVAL_SECONDS:
                with system_read_scope(settings):
                    warm_home_snapshot_cache_blocking_if_configured(
                        settings,
                        force_refresh=True,
                    )
                snapshot_refreshed_at = time.monotonic()
        except Exception:
            logger.exception("home_background_warmup_refresh_failed")


def _warm_home_background_caches_quietly(settings: SystemReadSettings) -> None:
    delay_seconds = resolve_home_background_warmup_delay_seconds()
    if delay_seconds > 0:
        time.sleep(delay_seconds)
    _run_home_background_warmup_pass(settings)


def _run_home_background_warmup_pass(settings: SystemReadSettings, *, force_refresh: bool = False) -> None:
    with system_read_scope(settings):
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
    if bool(getattr(settings, "system_read_publication_enabled", False)):
        await asyncio.to_thread(resolve_system_read_publication, settings)
    warm_hermes_bridge_if_configured(settings)
    # 首页快照预热可能耗时数十秒；它不应阻塞 /health 与其他页面 API 上线。
    # 预热状态已由 /health/ready.checks.home_snapshot_prewarm 单独披露。
    with system_read_scope(settings):
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
app.add_middleware(SystemReadPublicationMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=[
        "Accept",
        "Authorization",
        "Content-Type",
        "Idempotency-Key",
        SYSTEM_READ_GENERATION_HEADER,
        "X-User-Id",
        "X-User-Role",
    ],
    expose_headers=[SYSTEM_READ_GENERATION_HEADER],
)
app.add_middleware(
    LocalDevelopmentAccessMiddleware,
    environment=_settings.environment,
    local_only_api=_settings.local_only_api,
)
app.include_router(api_router)
