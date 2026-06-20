"""Ledger 口径损益 API 路由。"""
from importlib import import_module
from typing import Annotated

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter(prefix="/api")


def _svc():
    return import_module("backend.app.services.ledger_pnl_service")


def _ensure_ledger_pnl_read_allowed(auth: AuthContext) -> None:
    try:
        ensure_user_allowed(
            auth=auth,
            settings=get_settings(),
            resource="ledger_pnl",
            action="read",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/ledger-pnl/dates")
def dates(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    _ensure_ledger_pnl_read_allowed(auth)
    settings = get_settings()
    return _svc().ledger_pnl_dates_envelope(
        source_dir=str(settings.product_category_source_dir),
    )


@router.get("/ledger-pnl/data")
def data(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    date: str = Query(..., description="报告日期 YYYY-MM-DD"),
    currency: str | None = Query(None, description="币种过滤 CNX/CNY"),
) -> dict[str, object]:
    _ensure_ledger_pnl_read_allowed(auth)
    settings = get_settings()
    return _svc().ledger_pnl_data_envelope(
        source_dir=str(settings.product_category_source_dir),
        report_date=date,
        currency=currency,
    )


@router.get("/ledger-pnl/summary")
def summary(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    date: str = Query(..., description="报告日期 YYYY-MM-DD"),
    currency: str | None = Query(None, description="币种过滤 CNX/CNY"),
) -> dict[str, object]:
    _ensure_ledger_pnl_read_allowed(auth)
    settings = get_settings()
    return _svc().ledger_pnl_summary_envelope(
        source_dir=str(settings.product_category_source_dir),
        report_date=date,
        currency=currency,
    )


@router.get("/ledger-pnl/formal-financial-indicators")
def formal_financial_indicators(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_month: str = Query(..., description="报告月份 YYYYMM"),
) -> dict[str, object]:
    _ensure_ledger_pnl_read_allowed(auth)
    return _svc().ledger_pnl_formal_financial_indicator_contract_envelope(
        report_month=report_month,
    )
