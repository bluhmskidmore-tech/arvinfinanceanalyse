from __future__ import annotations

from backend.app.services.market_data_ncd_proxy_service import ncd_funding_proxy_envelope
from fastapi import APIRouter

router = APIRouter(prefix="/ui/market-data", tags=["market-data"])


@router.get("/ncd-funding-proxy")
def ncd_funding_proxy() -> dict[str, object]:
    return ncd_funding_proxy_envelope()
