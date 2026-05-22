import asyncio
import logging
from contextlib import asynccontextmanager

from backend.app.api import router as api_router
from backend.app.governance.settings import get_settings
from backend.app.observability import setup_opentelemetry
from backend.app.services.executive_service import warm_home_snapshot_cache_if_configured
from backend.app.services.hermes_agent_service import warm_hermes_bridge_if_configured
from backend.app.storage_bootstrap import run_startup_storage_migrations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
logging.getLogger("backend.app.services.executive_service").setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Blocking Postgres/DuckDB bootstrap off the event loop (Windows uvicorn + sync
    # drivers can otherwise stall startup indefinitely).
    await asyncio.to_thread(run_startup_storage_migrations)
    settings = get_settings()
    warm_hermes_bridge_if_configured(settings)
    warm_home_snapshot_cache_if_configured(settings)
    yield


app = FastAPI(
    title="MOSS Agent Analytics OS",
    version="0.1.0",
    lifespan=lifespan,
)
setup_opentelemetry(app)
_settings = get_settings()
app.add_middleware(
    GZipMiddleware,
    minimum_size=1024,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Accept", "Authorization", "Content-Type", "X-User-Id", "X-User-Role"],
)
app.include_router(api_router)
