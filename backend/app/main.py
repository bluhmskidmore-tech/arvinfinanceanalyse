import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api import router as api_router
from backend.app.governance.settings import get_settings
from backend.app.storage_bootstrap import run_startup_storage_migrations


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Blocking Postgres/DuckDB bootstrap off the event loop (Windows uvicorn + sync
    # drivers can otherwise stall startup indefinitely).
    await asyncio.to_thread(run_startup_storage_migrations)
    yield


app = FastAPI(
    title="MOSS Agent Analytics OS",
    version="0.1.0",
    lifespan=lifespan,
)
_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)
