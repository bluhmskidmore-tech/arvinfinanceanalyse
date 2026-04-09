from fastapi import APIRouter

from backend.app.services.executive_service import (
    executive_alerts,
    executive_contribution,
    executive_overview,
    executive_pnl_attribution,
    executive_risk_overview,
    executive_summary,
)

router = APIRouter(prefix="/ui")


@router.get("/home/overview")
def overview() -> dict[str, object]:
    return executive_overview()


@router.get("/home/summary")
def summary() -> dict[str, object]:
    return executive_summary()


@router.get("/pnl/attribution")
def pnl_attribution() -> dict[str, object]:
    return executive_pnl_attribution()


@router.get("/risk/overview")
def risk_overview() -> dict[str, object]:
    return executive_risk_overview()


@router.get("/home/contribution")
def contribution() -> dict[str, object]:
    return executive_contribution()


@router.get("/home/alerts")
def alerts() -> dict[str, object]:
    return executive_alerts()
