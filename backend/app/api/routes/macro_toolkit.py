from __future__ import annotations

import uuid
from collections.abc import (
    Iterable,
)
from datetime import (
    date,
)
from pathlib import Path
from typing import Annotated, Literal, cast
from urllib.parse import quote

from backend.app.api.deps import ensure_read_allowed
from backend.app.governance.settings import (
    get_settings,
)
from backend.app.observability.response_cache import (
    market_home_macro_analysis_cache_key,
    market_home_response_cache,
    market_home_strategy_summaries_cache_key,
)
from backend.app.repositories.cffex_member_rank_repo import (
    DEFAULT_CFFEX_CONTRACTS,
)
from backend.app.schemas.macro_toolkit import (
    MacroToolkitAnalysisEnvelope,
    MacroToolkitDynamicEnvelope,
    MacroToolkitScriptsEnvelope,
    MacroToolkitStrategySummariesEnvelope,
)
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services import (
    macro_adversarial_signal_service,
    macro_report_asset_service,
    macro_toolkit_read_service,
    macro_toolkit_refresh_receipt_service,
    macro_toolkit_service,
)
from backend.app.services.formal_result_runtime import build_result_envelope
from backend.app.services.macro_toolkit_presentation import (
    _SOURCE_BACKFILL_TARGETS,
    _latest_source_check_date,
)
from backend.app.services.macro_toolkit_route_support import (
    _DEFAULT_MACRO_COMMODITY_REFRESH_PRODUCTS,
    DEFAULT_CRISIS_SCORE_HISTORY_LIMIT,
    DEFAULT_DATA_SOURCES,
    OMITTED_SOURCE_SCRIPTS,
    OUTPUT_DIR,
    TOOLKIT_ROOT,
    _capability_plan,
    _cffex_member_rank_status,
    _choice_stock_refresh_overview,
    _choice_stock_refresh_permission_payload,
    _choice_stock_refresh_status,
    _commodity_futures_refresh_permission_payload,
    _commodity_futures_status,
    _decision_summary_observation_keys,
    _default_choice_stock_refresh_as_of_date,
    _default_source_backfill_start_date,
    _envelope,
    _macro_commodity_product_codes,
    _model_chain_artifacts_all_ok,
    _output_files,
    _script_payload,
    _script_warnings,
    _source_checks,
    iter_toolkit_scripts,
    pd,
)
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field

router = APIRouter(prefix="/ui/macro/toolkit", tags=["macro-toolkit"])


class MacroToolkitRunRequest(BaseModel):
    argv: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=120, ge=5, le=600)


class MacroToolkitRunChainRequest(BaseModel):
    dry_run: bool = True
    timeout_seconds: int = Field(default=120, ge=5, le=600)


class CffexMemberRankRefreshRequest(BaseModel):
    trade_date: str | None = None
    contracts: list[str] = Field(default_factory=lambda: list(DEFAULT_CFFEX_CONTRACTS))
    sources: list[str] = Field(default_factory=lambda: ["choice", "tushare"])


class ChoiceStockRefreshRequest(BaseModel):
    as_of_date: str | None = None
    refresh_history: bool = True
    refresh_factors: bool = True
    factor_max_stock_count: int | None = Field(default=None, ge=1)
    theme_overlay_mode: Literal["off", "dry_run", "archive"] = "off"


class SourceBackfillRefreshRequest(BaseModel):
    alias: str = Field(min_length=1)
    start_date: str | None = None
    end_date: str | None = None
    sources: list[str] | None = None


class CommodityFuturesRefreshRequest(BaseModel):
    start_date: str | None = None
    end_date: str | None = None
    products: list[str] | None = None
    dry_run: bool = False


def _owner_scoped_choice_stock_refresh_overview(
    auth: AuthContext,
    *,
    duckdb_path: str | Path,
    governance_path: str | Path,
    reference_date: str | date | None,
) -> dict[str, object]:
    normalized_reference_date = None
    if reference_date is not None:
        reference_date_text = str(reference_date).strip()
        if reference_date_text:
            normalized_reference_date = reference_date_text
    return _choice_stock_refresh_overview(
        duckdb_path,
        governance_path,
        permission=_choice_stock_refresh_permission_payload(auth),
        reference_date=normalized_reference_date,
        expected_user_id=auth.user_id,
    )


def _inject_owner_scoped_choice_stock_refresh(
    payload: dict[str, object],
    auth: AuthContext,
    *,
    duckdb_path: str | Path,
    governance_path: str | Path,
) -> dict[str, object]:
    result = payload.get("result")
    if not isinstance(result, dict):
        return payload
    reference_date = result.get("as_of_date")
    if reference_date is None:
        result_meta = payload.get("result_meta")
        if isinstance(result_meta, dict):
            reference_date = result_meta.get("as_of_date")
    owner_scoped_overview = _owner_scoped_choice_stock_refresh_overview(
        auth,
        duckdb_path=duckdb_path,
        governance_path=governance_path,
        reference_date=reference_date if isinstance(reference_date, (str, date)) else None,
    )
    return {
        **payload,
        "result": {
            **result,
            "choice_stock_refresh": owner_scoped_overview,
        },
    }


def _macro_toolkit_scripts_payload_dependencies(
    settings: object,
) -> macro_toolkit_read_service.MacroToolkitScriptsPayloadDependencies:
    return macro_toolkit_read_service.MacroToolkitScriptsPayloadDependencies(
        iter_toolkit_scripts=iter_toolkit_scripts,
        script_payload=_script_payload,
        source_checks=_source_checks,
        latest_source_check_date=_latest_source_check_date,
        cffex_member_rank_status=_cffex_member_rank_status,
        commodity_futures_refresh_permission_payload=(
            lambda auth: _commodity_futures_refresh_permission_payload(
                auth,
                settings=settings,
            )
        ),
        commodity_futures_status=_commodity_futures_status,
        macro_model_readiness=macro_toolkit_service.macro_model_readiness,
        output_files=_output_files,
        capability_plan=_capability_plan,
        owner_scoped_choice_stock_refresh_overview=(
            _owner_scoped_choice_stock_refresh_overview
        ),
        script_warnings=_script_warnings,
        envelope=_envelope,
    )


@router.get("/scripts", response_model=MacroToolkitScriptsEnvelope)
def macro_toolkit_scripts(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    settings = get_settings()
    _ensure_macro_toolkit_read_allowed(auth, settings)
    return macro_toolkit_read_service.build_macro_toolkit_scripts_payload(
        auth=auth,
        duckdb_path=settings.duckdb_path,
        governance_path=settings.governance_path,
        output_dir=OUTPUT_DIR,
        toolkit_root=TOOLKIT_ROOT,
        default_data_sources=DEFAULT_DATA_SOURCES,
        omitted_source_scripts=OMITTED_SOURCE_SCRIPTS,
        dependencies=_macro_toolkit_scripts_payload_dependencies(settings),
    )


@router.get("/analysis", response_model=MacroToolkitAnalysisEnvelope)
def macro_toolkit_analysis(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    detail: Annotated[str, Query(pattern="^(full|core)$")] = "full",
    history_limit: Annotated[int | None, Query(ge=1, le=1000)] = None,
) -> dict[str, object]:
    settings = get_settings()
    _ensure_macro_toolkit_read_allowed(auth, settings)
    resolved_history_limit = history_limit or DEFAULT_CRISIS_SCORE_HISTORY_LIMIT
    refresh_receipt_health = (
        macro_toolkit_refresh_receipt_service.load_macro_toolkit_refresh_receipt_health()
    )
    payload = market_home_response_cache.get_or_build(
        market_home_macro_analysis_cache_key(
            settings.duckdb_path,
            detail,
            history_limit=resolved_history_limit if detail == "full" else None,
            freshness_fingerprint=refresh_receipt_health.cache_fingerprint,
        ),
        lambda: macro_toolkit_read_service.build_macro_toolkit_analysis(
            detail,
            history_limit=resolved_history_limit,
            refresh_receipt_health=refresh_receipt_health,
        ),
    )
    return _inject_owner_scoped_choice_stock_refresh(
        payload,
        auth,
        duckdb_path=settings.duckdb_path,
        governance_path=settings.governance_path,
    )


@router.get("/report-bundle/{artifact_id}")
def macro_toolkit_report_bundle_artifact(
    artifact_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> Response:
    settings = get_settings()
    _ensure_macro_toolkit_read_allowed(auth, settings)
    bundle_dir = OUTPUT_DIR / macro_report_asset_service.BUNDLE_DIRNAME
    try:
        artifact = macro_report_asset_service.read_report_artifact(bundle_dir, artifact_id)
    except (
        macro_report_asset_service.ReportBundleNotFoundError,
        macro_report_asset_service.ReportArtifactNotFoundError,
    ) as exc:
        raise HTTPException(status_code=404, detail=exc.reason) from exc
    except macro_report_asset_service.ReportBundleInvalidError as exc:
        raise HTTPException(status_code=409, detail=exc.reason) from exc
    encoded_filename = quote(artifact.filename, safe="")
    return Response(
        content=artifact.content,
        media_type=artifact.media_type,
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/analysis/strategy-summaries",
    response_model=MacroToolkitStrategySummariesEnvelope,
)
def macro_toolkit_strategy_summaries(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    settings = get_settings()
    _ensure_macro_toolkit_read_allowed(auth, settings)
    payload = market_home_response_cache.get_or_build(
        market_home_strategy_summaries_cache_key(settings.duckdb_path),
        macro_toolkit_read_service.build_macro_toolkit_strategy_summaries,
    )
    return _inject_owner_scoped_choice_stock_refresh(
        payload,
        auth,
        duckdb_path=settings.duckdb_path,
        governance_path=settings.governance_path,
    )


@router.get("/adversarial-signal", response_model=MacroToolkitDynamicEnvelope)
def macro_toolkit_adversarial_signal(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    _ensure_macro_toolkit_read_allowed(auth, get_settings())
    payload, meta = macro_adversarial_signal_service.load_macro_adversarial_signal_payload(
        output_dir=OUTPUT_DIR
    )
    return build_result_envelope(
        basis="analytical",
        trace_id=f"macro-toolkit-adversarial-signal-{uuid.uuid4().hex[:12]}",
        result_kind="macro_toolkit.adversarial_signal",
        cache_version="cv_macro_adversarial_signal_v1",
        source_version=str(meta.get("source_version") or "macro_toolkit.adversarial_signal.missing"),
        rule_version="rv_macro_adversarial_signal_v1",
        result_payload=payload,
        quality_flag=str(meta.get("quality_flag") or "warning"),
        vendor_version=str(meta.get("vendor_version") or "macro_toolkit.local_csv"),
        vendor_status=str(meta.get("vendor_status") or "vendor_unavailable"),
        fallback_mode=str(meta.get("fallback_mode") or "none"),
        tables_used=list(meta.get("tables_used") or []),
        evidence_rows=int(meta.get("evidence_rows") or 0),
        as_of_date=str(meta.get("as_of_date")) if meta.get("as_of_date") else None,
    )


@router.get("/model-chain-results", response_model=MacroToolkitDynamicEnvelope)
def macro_toolkit_model_chain_results(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, object]:
    settings = get_settings()
    _ensure_macro_toolkit_read_allowed(auth, settings)
    chain_result = macro_toolkit_service.build_model_chain_results(OUTPUT_DIR)
    return _envelope(
        "macro_toolkit.model_chain_results",
        chain_result,
        quality_flag="ok" if _model_chain_artifacts_all_ok(chain_result) else "warning",
        fallback_mode="none",
        as_of_date=chain_result.get("as_of_date"),
    )


@router.post(
    "/cffex-member-rank/refresh",
    status_code=202,
    response_model=MacroToolkitDynamicEnvelope,
)
def macro_toolkit_refresh_cffex_member_rank(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    request: CffexMemberRankRefreshRequest | None = None,
) -> dict[str, object]:
    refresh_request = request or CffexMemberRankRefreshRequest()
    settings = get_settings()
    _ensure_cffex_member_rank_refresh_allowed(auth, settings)
    try:
        refresh = macro_toolkit_service.refresh_cffex_member_rank(
            duckdb_path=settings.duckdb_path,
            governance_path=settings.governance_path,
            trade_date=refresh_request.trade_date,
            contracts=tuple(refresh_request.contracts or DEFAULT_CFFEX_CONTRACTS),
            sources=tuple(refresh_request.sources or ["choice", "tushare"]),
            idempotency_key=idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except macro_toolkit_service.MacroToolkitConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except macro_toolkit_service.MacroToolkitQueueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _envelope(
        "macro_toolkit.cffex_member_rank_refresh",
        {
            "refresh": refresh.payload,
            "cffex_member_rank": _cffex_member_rank_status(settings.duckdb_path),
        },
        quality_flag=refresh.quality_flag,
        fallback_mode=refresh.fallback_mode,
        as_of_date=refresh.as_of_date,
    )


@router.get(
    "/cffex-member-rank/refresh-status",
    response_model=MacroToolkitDynamicEnvelope,
)
def macro_toolkit_cffex_member_rank_refresh_status(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    run_id: str = Query(...),
) -> dict[str, object]:
    settings = get_settings()
    _ensure_macro_toolkit_read_allowed(auth, settings)
    try:
        refresh = macro_toolkit_service.cffex_member_rank_refresh_status(
            settings.governance_path,
            run_id=run_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    report_date = str(
        refresh.get("trade_date") or refresh.get("report_date") or ""
    )[:10] or None
    return _envelope(
        "macro_toolkit.cffex_member_rank_refresh_status",
        {
            "refresh": refresh,
            "cffex_member_rank": _cffex_member_rank_status(
                settings.duckdb_path,
                reference_date=report_date,
            ),
        },
        quality_flag=(
            "ok" if str(refresh.get("status") or "") == "completed" else "warning"
        ),
        as_of_date=report_date,
    )


@router.post(
    "/choice-stock/refresh",
    status_code=202,
    response_model=MacroToolkitDynamicEnvelope,
)
def macro_toolkit_refresh_choice_stock(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    request: ChoiceStockRefreshRequest | None = None,
) -> dict[str, object]:
    refresh_request = request or ChoiceStockRefreshRequest()
    if (
        not refresh_request.refresh_history
        and not refresh_request.refresh_factors
        and refresh_request.theme_overlay_mode == "off"
    ):
        raise HTTPException(
            status_code=400,
            detail=("At least one of refresh_history, refresh_factors, or theme_overlay_mode must request work."),
        )

    settings = get_settings()
    _ensure_choice_stock_refresh_allowed(auth, settings)
    as_of_date = refresh_request.as_of_date or _default_choice_stock_refresh_as_of_date(settings.duckdb_path)
    permission = _choice_stock_refresh_permission_payload(auth)
    try:
        refresh = macro_toolkit_service.queue_choice_stock_refresh(
            duckdb_path=str(settings.duckdb_path),
            catalog_path=str(settings.choice_stock_catalog_file),
            governance_path=str(settings.governance_path),
            archive_root=str(settings.local_archive_path),
            as_of_date=as_of_date,
            refresh_history=refresh_request.refresh_history,
            refresh_factors=refresh_request.refresh_factors,
            factor_max_stock_count=refresh_request.factor_max_stock_count,
            theme_overlay_mode=refresh_request.theme_overlay_mode,
            permission=permission,
            idempotency_key=idempotency_key,
        )
    except macro_toolkit_service.MacroToolkitConflictError:
        raise HTTPException(
            status_code=409,
            detail=f"Choice stock refresh already in progress for as_of_date={as_of_date}.",
        ) from None
    except macro_toolkit_service.MacroToolkitQueueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _envelope(
        "macro_toolkit.choice_stock_refresh",
        {
            "refresh": refresh.payload,
            "choice_stock_refresh": _choice_stock_refresh_overview(
                settings.duckdb_path,
                settings.governance_path,
                permission=permission,
                reference_date=refresh.as_of_date,
                expected_user_id=auth.user_id,
            ),
        },
        quality_flag=refresh.quality_flag,
        fallback_mode=refresh.fallback_mode,
        as_of_date=refresh.as_of_date,
    )


@router.get(
    "/choice-stock/refresh-status",
    response_model=MacroToolkitDynamicEnvelope,
)
def macro_toolkit_choice_stock_refresh_status(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    run_id: str = Query(default=""),
) -> dict[str, object]:
    settings = get_settings()
    _ensure_macro_toolkit_read_allowed(auth, settings)
    try:
        status = _choice_stock_refresh_status(
            settings.governance_path,
            run_id=run_id,
            expected_user_id=auth.user_id,
        )
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=404, detail="Choice stock refresh run not found.") from exc
    return _envelope(
        "macro_toolkit.choice_stock_refresh_status",
        {
            "refresh": status,
            "choice_stock_refresh": _choice_stock_refresh_overview(
                settings.duckdb_path,
                settings.governance_path,
                reference_date=str(status.get("report_date") or "")[:10] or None,
                expected_user_id=auth.user_id,
            ),
        },
        quality_flag=(
            "ok" if str(status.get("status") or "") == "completed" else "warning"
        ),
    )


@router.post(
    "/source-backfill/refresh",
    status_code=202,
    response_model=MacroToolkitDynamicEnvelope,
)
def macro_toolkit_refresh_source_backfill(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    request: SourceBackfillRefreshRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, object]:
    settings = get_settings()
    _ensure_source_backfill_refresh_allowed(auth, settings)
    target = _source_backfill_target(request.alias)
    start_date = request.start_date or _default_source_backfill_start_date(request.end_date)
    end_date = request.end_date or date.today().isoformat()
    try:
        refresh = macro_toolkit_service.queue_macro_source_backfill(
            duckdb_path=str(settings.duckdb_path),
            governance_path=str(settings.governance_path),
            alias=request.alias,
            series_id=str(target["series_id"]),
            series_name=str(target["series_name"]),
            backfill_mode=str(target.get("backfill_mode") or "macro_series"),
            start_date=start_date,
            end_date=end_date,
            sources=tuple(request.sources or list(cast(Iterable[str], target["default_sources"]))),
            requested_by_user_id=auth.user_id,
            idempotency_key=idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except macro_toolkit_service.MacroToolkitConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except macro_toolkit_service.MacroToolkitQueueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _envelope(
        "macro_toolkit.source_backfill_refresh",
        {"refresh": refresh.payload},
        quality_flag=refresh.quality_flag,
        fallback_mode=refresh.fallback_mode,
        as_of_date=refresh.as_of_date,
    )


@router.get(
    "/source-backfill/refresh-status",
    response_model=MacroToolkitDynamicEnvelope,
)
def macro_toolkit_source_backfill_refresh_status(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    run_id: str = Query(...),
) -> dict[str, object]:
    settings = get_settings()
    _ensure_macro_toolkit_read_allowed(auth, settings)
    try:
        refresh = macro_toolkit_service.macro_source_backfill_refresh_status(
            settings.governance_path,
            run_id=run_id,
            expected_user_id=auth.user_id,
        )
    except (ValueError, PermissionError) as exc:
        raise HTTPException(
            status_code=404,
            detail="Macro source backfill refresh run not found.",
        ) from exc
    report_date = str(
        refresh.get("end_date") or refresh.get("report_date") or ""
    )[:10] or None
    return _envelope(
        "macro_toolkit.source_backfill_refresh_status",
        {"refresh": refresh},
        quality_flag=(
            "ok" if str(refresh.get("status") or "") == "completed" else "warning"
        ),
        as_of_date=report_date,
    )


@router.post(
    "/commodity-futures/refresh",
    response_model=MacroToolkitDynamicEnvelope,
)
def macro_toolkit_refresh_commodity_futures(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    request: CommodityFuturesRefreshRequest | None = None,
) -> dict[str, object]:
    refresh_request = request or CommodityFuturesRefreshRequest()
    settings = get_settings()
    _ensure_commodity_futures_refresh_allowed(auth, settings)
    permission = _commodity_futures_refresh_permission_payload(auth, allowed=True)
    end_date = refresh_request.end_date or date.today().isoformat()
    start_date = refresh_request.start_date or _default_source_backfill_start_date(end_date)
    products = _macro_commodity_refresh_products(refresh_request.products)
    before_status = _commodity_futures_status(settings.duckdb_path)
    try:
        refresh = macro_toolkit_service.refresh_commodity_futures(
            start_date=start_date,
            end_date=end_date,
            duckdb_path=str(settings.duckdb_path),
            governance_path=str(settings.governance_path),
            products=products,
            dry_run=refresh_request.dry_run,
            before_status=before_status,
            permission=permission,
            requested_by_user_id=auth.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except macro_toolkit_service.MacroToolkitConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except macro_toolkit_service.MacroToolkitQueueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    status = str(refresh.payload.get("status") or "")
    refresh_payload = dict(refresh.payload)
    public_permission = macro_toolkit_service._public_commodity_futures_refresh_permission(
        refresh_payload.get("permission") if isinstance(refresh_payload.get("permission"), dict) else permission
    )
    refresh_payload["permission"] = public_permission
    commodity_futures_status = before_status
    if refresh_request.dry_run:
        refresh_payload["before_status"] = before_status
        refresh_payload["after_status"] = before_status
        refresh_payload["summary"] = macro_toolkit_service.commodity_futures_refresh_summary(
            before_status=before_status,
            after_status=before_status,
            dry_run=True,
        )
    return _envelope(
        "macro_toolkit.commodity_futures_refresh",
        {
            "refresh": refresh_payload,
            "commodity_futures_refresh": {
                "permission": public_permission,
                "refresh": refresh_payload,
                "status": commodity_futures_status,
            },
        },
        quality_flag=refresh.quality_flag if status in {"queued", "dry_run"} else "warning",
        fallback_mode=refresh.fallback_mode,
        as_of_date=refresh.as_of_date or end_date,
    )


@router.get(
    "/commodity-futures/refresh-status",
    response_model=MacroToolkitDynamicEnvelope,
)
def macro_toolkit_commodity_futures_refresh_status(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    run_id: str = Query(...),
) -> dict[str, object]:
    settings = get_settings()
    _ensure_macro_toolkit_read_allowed(auth, settings)
    try:
        refresh = macro_toolkit_service.commodity_futures_refresh_status(
            settings.governance_path,
            run_id=run_id,
            expected_user_id=auth.user_id,
        )
    except (ValueError, PermissionError) as exc:
        raise HTTPException(
            status_code=404,
            detail="Commodity futures refresh run not found.",
        ) from exc
    before_snapshot = refresh.get("before_status")
    before_status = dict(before_snapshot) if isinstance(before_snapshot, dict) else None
    status = str(refresh.get("status") or "")
    terminal_statuses = {"completed", "partial", "failed", "no_rows", "blocked"}
    after_snapshot = refresh.get("after_status")
    after_status = dict(after_snapshot) if isinstance(after_snapshot, dict) else None
    unavailable_snapshot_status: dict[str, object] = {
        "materialized": None,
        "status": "snapshot_unavailable",
        "table": "fact_commodity_futures_daily",
        "row_count": None,
        "latest_trade_date": None,
        "source_vendors": [],
        "snapshot_status": "missing",
    }
    commodity_futures_status = before_status or unavailable_snapshot_status
    refresh_payload = dict(refresh)
    public_permission = macro_toolkit_service._public_commodity_futures_refresh_permission(
        refresh_payload.get("permission")
    )
    refresh_payload["permission"] = public_permission
    if status in terminal_statuses:
        commodity_futures_status = after_status or unavailable_snapshot_status
    report_date = str(
        refresh.get("end_date") or refresh.get("report_date") or ""
    )[:10] or None
    return _envelope(
        "macro_toolkit.commodity_futures_refresh_status",
        {
            "refresh": refresh_payload,
            "commodity_futures_refresh": {
                "permission": public_permission,
                "refresh": refresh_payload,
                "status": commodity_futures_status,
            },
        },
        quality_flag=(
            "ok"
            if status == "completed"
            and refresh_payload.get("terminal_snapshot_status") == "captured"
            else "warning"
        ),
        as_of_date=report_date,
    )


def _macro_commodity_refresh_products(products: list[str] | None) -> tuple[str, ...]:
    requested = list(_DEFAULT_MACRO_COMMODITY_REFRESH_PRODUCTS) if products is None else products
    normalized = tuple(str(product).strip().upper() for product in requested)
    if not normalized:
        raise HTTPException(
            status_code=400,
            detail="At least one commodity futures product is required.",
        )
    unknown = tuple(product for product in normalized if product not in _macro_commodity_product_codes())
    if unknown:
        unknown_labels = ", ".join(product or "<blank>" for product in unknown)
        raise HTTPException(
            status_code=400,
            detail=f"Unknown commodity futures product: {unknown_labels}.",
        )
    return normalized


# Script receipts are defined by individual runtime scripts, so their nested
# payload remains intentionally broad while still being exposed in OpenAPI.
@router.post("/scripts/{name}/run", response_model=dict[str, object])
def macro_toolkit_run(
    name: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    request: MacroToolkitRunRequest | None = None,
) -> dict[str, object]:
    run_request = request or MacroToolkitRunRequest()
    settings = get_settings()
    _ensure_macro_toolkit_script_execute_allowed(auth, settings, script_name=name)
    if run_request.argv:
        raise HTTPException(
            status_code=400,
            detail="Script arguments are not allowed for HTTP macro toolkit runs.",
        )
    try:
        payload = macro_toolkit_service.run_macro_toolkit_script(
            name=name,
            argv=run_request.argv,
            timeout_seconds=run_request.timeout_seconds,
            output_dir=OUTPUT_DIR,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except macro_toolkit_service.MacroToolkitConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    market_home_response_cache.invalidate()
    return payload


@router.post("/scripts/run-chain", response_model=MacroToolkitDynamicEnvelope)
def macro_toolkit_run_chain(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    request: MacroToolkitRunChainRequest | None = None,
) -> dict[str, object]:
    run_request = request or MacroToolkitRunChainRequest()
    settings = get_settings()
    _ensure_macro_toolkit_script_execute_allowed(auth, settings, script_name="macro_toolkit_chain")
    source_checks = _source_checks(settings.duckdb_path)
    try:
        payload = macro_toolkit_service.run_macro_toolkit_chain(
            dry_run=run_request.dry_run,
            timeout_seconds=run_request.timeout_seconds,
            output_dir=OUTPUT_DIR,
            reference_date=_latest_source_check_date(source_checks),
            governance_path=settings.governance_path,
            authorize_script=lambda script_name: _ensure_macro_toolkit_script_execute_allowed(
                auth,
                settings,
                script_name=script_name,
            ),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except macro_toolkit_service.MacroToolkitConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not run_request.dry_run:
        market_home_response_cache.invalidate()
    return _envelope(
        "macro_toolkit.script_chain_run",
        {"run": payload, "model_readiness": payload["model_readiness"]},
        quality_flag="ok" if str(payload.get("status")) in {"completed", "dry_run"} else "warning",
        fallback_mode="none",
        as_of_date=None,
    )


def _ensure_macro_toolkit_read_allowed(auth: AuthContext, settings: object) -> None:
    ensure_read_allowed(auth, "macro_toolkit", settings=settings, authorize=ensure_user_allowed)


def _ensure_cffex_member_rank_refresh_allowed(auth: AuthContext, settings: object) -> None:
    try:
        ensure_user_allowed(
            auth=auth,
            settings=settings,
            resource="macro_toolkit.cffex_member_rank",
            action="refresh",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _ensure_choice_stock_refresh_allowed(auth: AuthContext, settings: object) -> None:
    try:
        ensure_user_allowed(
            auth=auth,
            settings=settings,
            resource="macro_toolkit.choice_stock",
            action="refresh",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _ensure_source_backfill_refresh_allowed(auth: AuthContext, settings: object) -> None:
    try:
        ensure_user_allowed(
            auth=auth,
            settings=settings,
            resource="macro_toolkit.source_backfill",
            action="refresh",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _ensure_commodity_futures_refresh_allowed(auth: AuthContext, settings: object) -> None:
    try:
        ensure_user_allowed(
            auth=auth,
            settings=settings,
            resource="macro_toolkit.commodity_futures",
            action="refresh",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _ensure_macro_toolkit_script_execute_allowed(
    auth: AuthContext,
    settings: object,
    *,
    script_name: str,
) -> None:
    try:
        ensure_user_allowed(
            auth=auth,
            settings=settings,
            resource="macro_toolkit.script",
            action="execute",
            scope_key="script",
            scope_value=script_name,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _source_backfill_target(alias: str) -> dict[str, object]:
    key = str(alias or "").strip().lower()
    target = _SOURCE_BACKFILL_TARGETS.get(key)
    if target is None:
        raise HTTPException(status_code=400, detail=f"Unsupported macro source backfill alias: {alias}")
    return target


def _load_equity_strategy_factor_snapshot(
    duckdb_path: Path,
    as_of_date: str,
    stock_codes: list[str] | None = None,
) -> pd.DataFrame | None:
    return macro_toolkit_service.load_equity_strategy_factor_snapshot(
        duckdb_path,
        as_of_date,
        stock_codes=stock_codes,
    )


def _load_macro_curve_rows(duckdb_path: str | Path, report_date: date) -> list[dict[str, object]]:
    return macro_toolkit_service.load_macro_curve_rows(duckdb_path, report_date)


def _load_latest_risk_tensor_row(
    duckdb_path: str | Path,
    report_date: date,
) -> dict[str, object] | None:
    return macro_toolkit_service.load_latest_risk_tensor_row(duckdb_path, report_date)


def _load_latest_bond_positions(
    duckdb_path: str | Path,
    report_date: date,
) -> list[dict[str, object]]:
    return macro_toolkit_service.load_latest_bond_positions(duckdb_path, report_date)


def __getattr__(name: str) -> object:
    # Keep `_DECISION_SUMMARY_OBSERVATION_KEYS` as a compatible lazy attribute for tests.
    if name == "_DECISION_SUMMARY_OBSERVATION_KEYS":
        return _decision_summary_observation_keys()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


