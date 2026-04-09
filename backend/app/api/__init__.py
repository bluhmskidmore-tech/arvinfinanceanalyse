from fastapi import APIRouter

from backend.app.api.routes.executive import router as executive_router
from backend.app.api.routes.health import router as health_router

router = APIRouter()
router.include_router(health_router, tags=["health"])
router.include_router(executive_router, tags=["executive"])
