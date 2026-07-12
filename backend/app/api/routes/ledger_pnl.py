"""Ledger 口径损益 API 路由。"""
from datetime import date as calendar_date
from importlib import import_module
from typing import Annotated, Literal

from backend.app.governance.settings import get_settings
from backend.app.schemas.candidate_financial_indicator_period_comparison import (
    CandidateFinancialIndicatorPeriodComparisonEnvelope,
)
from backend.app.schemas.candidate_financial_indicators import (
    CandidateFinancialIndicatorEnvelope,
    CandidateFinancialIndicatorRevalidationReceipt,
    CandidateFinancialIndicatorRevalidationRequest,
)
from backend.app.schemas.ledger_pnl_analysis import (
    LedgerPnlAccountDetailEnvelope,
    LedgerPnlAnalysisEnvelope,
)
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from fastapi import APIRouter, Body, Depends, HTTPException, Query

router = APIRouter(prefix="/api")

_REPORT_DATE_PATTERN = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
_REPORT_MONTH_PATTERN = r"^[0-9]{4}(?:0[1-9]|1[0-2])$"
_CANDIDATE_METRIC_ID_PATTERN = (
    r"^[a-z0-9]+(?:[._][a-z0-9]+)*(?:::(?:point|ytd_average|month_average))?$"
)


def _svc():
    return import_module("backend.app.services.ledger_pnl_service")


def _candidate_svc():
    return import_module(
        "backend.app.services.candidate_financial_indicator_service"
    )


def _period_comparison_svc():
    return import_module(
        "backend.app.services.candidate_financial_indicator_period_comparison_service"
    )


def _monthly_analysis_svc():
    return import_module("backend.app.services.qdb_gl_monthly_analysis_service")


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


def _validated_report_date(value: str) -> str:
    try:
        return calendar_date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="Invalid report date; expected a real YYYY-MM-DD calendar date.",
        ) from exc


def _validated_report_month(value: str) -> str:
    try:
        calendar_date(int(value[:4]), int(value[4:]), 1)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="Invalid report month; expected a real YYYYMM month.",
        ) from exc
    return value


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
    date: str = Query(
        ...,
        pattern=_REPORT_DATE_PATTERN,
        description="报告日期 YYYY-MM-DD",
    ),
    currency: Literal["CNX", "CNY"] | None = Query(
        None,
        description="币种过滤 CNX/CNY",
    ),
) -> dict[str, object]:
    _ensure_ledger_pnl_read_allowed(auth)
    settings = get_settings()
    report_date = _validated_report_date(date)
    service = _svc()
    try:
        return service.ledger_pnl_data_envelope(
            source_dir=str(settings.product_category_source_dir),
            report_date=report_date,
            currency=currency,
        )
    except service.LedgerPnlRequestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/ledger-pnl/summary")
def summary(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    date: str = Query(
        ...,
        pattern=_REPORT_DATE_PATTERN,
        description="报告日期 YYYY-MM-DD",
    ),
    currency: Literal["CNX", "CNY"] | None = Query(
        None,
        description="币种过滤 CNX/CNY",
    ),
) -> dict[str, object]:
    _ensure_ledger_pnl_read_allowed(auth)
    settings = get_settings()
    report_date = _validated_report_date(date)
    service = _svc()
    try:
        return service.ledger_pnl_summary_envelope(
            source_dir=str(settings.product_category_source_dir),
            report_date=report_date,
            currency=currency,
        )
    except service.LedgerPnlRequestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/ledger-pnl/analysis", response_model=LedgerPnlAnalysisEnvelope)
def analysis(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    date: str = Query(
        ...,
        pattern=_REPORT_DATE_PATTERN,
        description="报告日期 YYYY-MM-DD",
    ),
    currency: Literal["CNX", "CNY"] | None = Query(
        None,
        description="会计口径 CNX/CNY；省略时使用 CNX",
    ),
) -> dict[str, object]:
    _ensure_ledger_pnl_read_allowed(auth)
    settings = get_settings()
    report_date = _validated_report_date(date)
    service = _svc()
    try:
        return service.ledger_pnl_analysis_envelope(
            source_dir=str(settings.product_category_source_dir),
            report_date=report_date,
            currency=currency,
        )
    except service.LedgerPnlRequestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/ledger-pnl/account-detail",
    response_model=LedgerPnlAccountDetailEnvelope,
)
def account_detail(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    date: str = Query(
        ...,
        pattern=_REPORT_DATE_PATTERN,
        description="报告日期 YYYY-MM-DD",
    ),
    account_code: str = Query(
        ...,
        pattern=r"^5[0-9]+$",
        max_length=32,
        description="精确 5* 损益科目代码",
    ),
    currency: Literal["CNX", "CNY"] | None = Query(
        None,
        description="会计口径 CNX/CNY；省略时使用 CNX",
    ),
) -> dict[str, object]:
    _ensure_ledger_pnl_read_allowed(auth)
    settings = get_settings()
    report_date = _validated_report_date(date)
    service = _svc()
    try:
        return service.ledger_pnl_account_detail_envelope(
            source_dir=str(settings.product_category_source_dir),
            report_date=report_date,
            account_code=account_code,
            currency=currency,
        )
    except service.LedgerPnlRequestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/ledger-pnl/formal-financial-indicators")
def formal_financial_indicators(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_month: str = Query(
        ...,
        pattern=_REPORT_MONTH_PATTERN,
        description="报告月份 YYYYMM",
    ),
) -> dict[str, object]:
    _ensure_ledger_pnl_read_allowed(auth)
    return _svc().ledger_pnl_formal_financial_indicator_contract_envelope(
        report_month=_validated_report_month(report_month),
    )


@router.get("/ledger-pnl/monthly-analysis/dates")
def monthly_analysis_dates(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    _ensure_ledger_pnl_read_allowed(auth)
    settings = get_settings()
    return _monthly_analysis_svc().qdb_gl_monthly_analysis_dates_envelope(
        source_dir=settings.product_category_source_dir,
    )


@router.get("/ledger-pnl/monthly-analysis/workbook")
def monthly_analysis_workbook(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_month: str = Query(
        ...,
        pattern=_REPORT_MONTH_PATTERN,
        description="报告月份 YYYYMM",
    ),
) -> dict[str, object]:
    _ensure_ledger_pnl_read_allowed(auth)
    settings = get_settings()
    try:
        return _monthly_analysis_svc().qdb_gl_monthly_analysis_workbook_envelope(
            source_dir=settings.product_category_source_dir,
            governance_dir=settings.governance_path,
            report_month=_validated_report_month(report_month),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get(
    "/ledger-pnl/candidate-financial-indicators",
    response_model=CandidateFinancialIndicatorEnvelope,
)
def candidate_financial_indicators(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_month: str = Query(
        ...,
        pattern=_REPORT_MONTH_PATTERN,
        description="报告月份 YYYYMM",
    ),
    include_lineage: bool = Query(
        False,
        description="是否返回逐科目与逐指标血缘",
    ),
    metric_id: str | None = Query(
        None,
        pattern=_CANDIDATE_METRIC_ID_PATTERN,
        max_length=160,
        description="可选的精确候选指标 ID",
    ),
) -> dict[str, object]:
    _ensure_ledger_pnl_read_allowed(auth)
    settings = get_settings()
    service = _candidate_svc()
    try:
        return service.candidate_financial_indicator_envelope(
            source_dir=str(settings.product_category_source_dir),
            report_month=_validated_report_month(report_month),
            include_lineage=include_lineage,
            metric_id=metric_id,
        )
    except service.CandidateFinancialIndicatorRequestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/ledger-pnl/candidate-financial-indicators/period-comparison",
    response_model=CandidateFinancialIndicatorPeriodComparisonEnvelope,
)
def candidate_financial_indicator_period_comparison(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_month: str = Query(
        ...,
        pattern=_REPORT_MONTH_PATTERN,
        description="报告月份 YYYYMM",
    ),
) -> dict[str, object]:
    _ensure_ledger_pnl_read_allowed(auth)
    settings = get_settings()
    service = _period_comparison_svc()
    try:
        return service.candidate_financial_indicator_period_comparison_envelope(
            source_dir=str(settings.product_category_source_dir),
            report_month=_validated_report_month(report_month),
        )
    except service.CandidateFinancialIndicatorPeriodComparisonRequestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/ledger-pnl/candidate-financial-indicators/revalidate",
    response_model=CandidateFinancialIndicatorRevalidationReceipt,
)
def revalidate_candidate_financial_indicators(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    request: Annotated[CandidateFinancialIndicatorRevalidationRequest, Body(...)],
    report_month: str = Query(..., pattern=_REPORT_MONTH_PATTERN),
    include_lineage: bool = Query(False),
    metric_id: str | None = Query(
        None,
        pattern=_CANDIDATE_METRIC_ID_PATTERN,
        max_length=160,
    ),
) -> dict[str, object]:
    _ensure_ledger_pnl_read_allowed(auth)
    settings = get_settings()
    service = _candidate_svc()
    try:
        return service.revalidate_candidate_financial_indicators(
            source_dir=str(settings.product_category_source_dir),
            report_month=_validated_report_month(report_month),
            include_lineage=include_lineage,
            metric_id=metric_id,
            request=request,
        )
    except service.CandidateFinancialIndicatorConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except service.CandidateFinancialIndicatorRequestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/ledger-pnl/formal-indicator-rule-checks")
def formal_indicator_rule_checks(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    report_month: str = Query(
        ...,
        pattern=_REPORT_MONTH_PATTERN,
        description="报告月份 YYYYMM",
    ),
) -> dict[str, object]:
    _ensure_ledger_pnl_read_allowed(auth)
    return _svc().ledger_pnl_formal_indicator_rule_checks_envelope(
        report_month=_validated_report_month(report_month),
    )
