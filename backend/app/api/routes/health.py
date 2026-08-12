from backend.app.governance.settings import get_settings
from backend.app.services.health_service import ready_health_payload
from fastapi import APIRouter, Response, status

router = APIRouter(prefix="/health")


@router.get("/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready(response: Response) -> dict[str, object]:
    payload = ready_health_payload(get_settings())
    if payload.get("status") != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return payload
