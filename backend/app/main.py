from fastapi import FastAPI

from backend.app.api import router as api_router

app = FastAPI(title="MOSS Agent Analytics OS", version="0.1.0")
app.include_router(api_router)
