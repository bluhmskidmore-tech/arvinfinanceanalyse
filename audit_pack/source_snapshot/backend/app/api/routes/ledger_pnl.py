"""Ledger 口径损益 API 路由。"""
from importlib import import_module

from fastapi import APIRouter, Query

from backend.app.governance.settings import get_settings

router = APIRouter(prefix="/api")


def _svc():
    return import_module("backend.app.services.ledger_pnl_service")


@router.get("/ledger-pnl/dates")
def dates() -> dict[str, object]:
    settings = get_settings()
    return _svc().ledger_pnl_dates_envelope(
        source_dir=str(settings.product_category_source_dir),
    )


@router.get("/ledger-pnl/data")
def data(
    date: str = Query(..., description="报告日期 YYYY-MM-DD"),
    currency: str | None = Query(None, description="币种过滤 CNX/CNY"),
) -> dict[str, object]:
    settings = get_settings()
    return _svc().ledger_pnl_data_envelope(
        source_dir=str(settings.product_category_source_dir),
        report_date=date,
        currency=currency,
    )


@router.get("/ledger-pnl/summary")
def summary(
    date: str = Query(..., description="报告日期 YYYY-MM-DD"),
    currency: str | None = Query(None, description="币种过滤 CNX/CNY"),
) -> dict[str, object]:
    settings = get_settings()
    return _svc().ledger_pnl_summary_envelope(
        source_dir=str(settings.product_category_source_dir),
        report_date=date,
        currency=currency,
    )
