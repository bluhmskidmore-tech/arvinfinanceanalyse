import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api import router as api_router
from backend.app.governance.settings import get_settings
from backend.app.observability import setup_opentelemetry
from backend.app.services.hermes_agent_service import warm_hermes_bridge_if_configured
from backend.app.storage_bootstrap import run_startup_storage_migrations


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Blocking Postgres/DuckDB bootstrap off the event loop (Windows uvicorn + sync
    # drivers can otherwise stall startup indefinitely).
    await asyncio.to_thread(run_startup_storage_migrations)
    warm_hermes_bridge_if_configured(get_settings())
    yield


app = FastAPI(
    title="MOSS Agent Analytics OS",
    version="0.1.0",
    lifespan=lifespan,
)
setup_opentelemetry(app)
_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)
