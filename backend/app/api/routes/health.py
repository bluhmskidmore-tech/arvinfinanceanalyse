from backend.app.governance.settings import get_settings
from backend.app.services.health_service import ready_health_payload
from fastapi import APIRouter

router = APIRouter(prefix="/health")


@router.get("/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready() -> dict[str, object]:
    return ready_health_payload(get_settings())
