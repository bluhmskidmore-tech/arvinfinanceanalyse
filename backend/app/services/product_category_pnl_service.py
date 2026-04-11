from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.governance.settings import Settings
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    GovernanceRepository,
)
from backend.app.repositories.product_category_pnl_repo import ProductCategoryPnlRepository
from backend.app.schemas.analysis_service import AnalysisQuery
from backend.app.schemas.materialize import CacheBuildRunRecord
from backend.app.schemas.product_category_pnl import (
    ProductCategoryCurrentSortField,
    ProductCategoryDatesPayload,
    ProductCategoryEventSortField,
    ProductCategoryManualAdjustmentCreateRequest,
    ProductCategoryManualAdjustmentListPayload,
    ProductCategoryManualAdjustmentPayload,
    ProductCategorySortDirection,
    ProductCategoryManualAdjustmentUpdateRequest,
    ProductCategoryPnlPayload,
    ProductCategoryPnlRow,
)
from backend.app.schemas.result_meta import ResultMeta
from backend.app.services.analysis_service import (
    UnifiedAnalysisService,
    build_default_analysis_service,
)
from backend.app.tasks.product_category_pnl import (
    PRODUCT_CATEGORY_ADJUSTMENT_STREAM,
    PRODUCT_CATEGORY_PNL_LOCK,
    materialize_product_category_pnl,
)


RULE_VERSION = "rv_product_category_pnl_v1"
CACHE_VERSION = "cv_product_category_pnl_v1"
AVAILABLE_VIEWS = ["monthly", "qtd", "ytd", "year_to_report_month_end"]
PENDING_SOURCE_VERSION = "sv_product_category_pending"
PRODUCT_CATEGORY_JOB_NAME = "product_category_pnl"
PRODUCT_CATEGORY_CACHE_KEY = "product_category_pnl.formal"
IN_FLIGHT_STATUSES = {"queued", "running"}
STALE_IN_FLIGHT_AFTER = timedelta(hours=1)


class ProductCategoryRefreshServiceError(RuntimeError):
    pass


class ProductCategoryRefreshConflictError(RuntimeError):
    pass


def queue_product_category_pnl_refresh(settings: Settings) -> dict[str, object]:
    try:
        with acquire_lock(
            _refresh_trigger_lock(),
            base_dir=settings.governance_path,
            timeout_seconds=0.1,
        ):
            existing = _latest_inflight_refresh(settings)
            if existing is not None:
                raise ProductCategoryRefreshConflictError(
                    "Product-category refresh already in progress."
                )

            run_id = _build_run_id()
            queued_at = datetime.now(timezone.utc).isoformat()
            governance_repo = GovernanceRepository(base_dir=settings.governance_path)
            governance_repo.append(
                CACHE_BUILD_RUN_STREAM,
                {
                    **CacheBuildRunRecord(
                        run_id=run_id,
                        job_name=PRODUCT_CATEGORY_JOB_NAME,
                        status="queued",
                        cache_key=PRODUCT_CATEGORY_CACHE_KEY,
                        lock=PRODUCT_CATEGORY_PNL_LOCK.key,
                        source_version=PENDING_SOURCE_VERSION,
                        vendor_version="vv_none",
                    ).model_dump(),
                    "queued_at": queued_at,
                },
            )

            try:
                materialize_product_category_pnl.send(
                    duckdb_path=str(settings.duckdb_path),
                    source_dir=str(settings.product_category_source_dir),
                    governance_dir=str(settings.governance_path),
                    run_id=run_id,
                )
            except Exception as exc:
                _record_dispatch_failure(
                    settings=settings,
                    run_id=run_id,
                    error_message="Product-category refresh queue dispatch failed.",
                )
                raise ProductCategoryRefreshServiceError(
                    "Product-category refresh queue dispatch failed."
                ) from exc

            return {
                "status": "queued",
                "run_id": run_id,
                "job_name": PRODUCT_CATEGORY_JOB_NAME,
                "trigger_mode": "async",
                "cache_key": PRODUCT_CATEGORY_CACHE_KEY,
            }
    except TimeoutError as exc:
        raise ProductCategoryRefreshConflictError(
            "Product-category refresh already in progress."
        ) from exc


def product_category_refresh_status(settings: Settings, run_id: str) -> dict[str, object]:
    matching_records = [
        record
        for record in _load_refresh_run_records(settings)
        if str(record.get("run_id")) == run_id
    ]
    if not matching_records:
        raise ValueError(f"Unknown product-category refresh run_id={run_id}")
    latest = matching_records[-1]
    return {
        **latest,
        "trigger_mode": "async" if latest["status"] in {"queued", "running"} else "terminal",
    }


def create_product_category_manual_adjustment(
    settings: Settings,
    payload: ProductCategoryManualAdjustmentCreateRequest,
) -> dict[str, object]:
    created_at = datetime.now(timezone.utc).isoformat()
    adjustment_id = f"pca-{uuid4()}"
    record = ProductCategoryManualAdjustmentPayload(
        adjustment_id=adjustment_id,
        event_type="created",
        created_at=created_at,
        stream=PRODUCT_CATEGORY_ADJUSTMENT_STREAM,
        **payload.model_dump(),
    )
    GovernanceRepository(base_dir=settings.governance_path).append(
        PRODUCT_CATEGORY_ADJUSTMENT_STREAM,
        record.model_dump(mode="json"),
    )
    return record.model_dump(mode="json")


def list_product_category_manual_adjustments(
    settings: Settings,
    report_date: str,
    adjustment_id: str | None = None,
    adjustment_id_exact: bool = False,
    account_code: str | None = None,
    approval_status: str | None = None,
    event_type: str | None = None,
    current_sort_field: ProductCategoryCurrentSortField = "created_at",
    current_sort_dir: ProductCategorySortDirection = "desc",
    event_sort_field: ProductCategoryEventSortField = "created_at",
    event_sort_dir: ProductCategorySortDirection = "desc",
    created_at_from: datetime | None = None,
    created_at_to: datetime | None = None,
    adjustment_limit: int = 20,
    adjustment_offset: int = 0,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, object]:
    events = _load_manual_adjustment_events(settings)
    records = _reduce_latest_adjustments(events)
    adjustments = [
        ProductCategoryManualAdjustmentPayload.model_validate(record)
        for record in records
        if _matches_adjustment_filter(
            record,
            report_date=report_date,
            adjustment_id=adjustment_id,
            adjustment_id_exact=adjustment_id_exact,
            account_code=account_code,
            approval_status=approval_status,
            event_type=event_type,
            apply_event_type=False,
            created_at_from=created_at_from,
            created_at_to=created_at_to,
        )
    ]
    adjustments = _sort_adjustment_payloads(
        adjustments,
        field=current_sort_field,
        direction=current_sort_dir,
    )
    paged_adjustments = adjustments[adjustment_offset : adjustment_offset + adjustment_limit]
    timeline = [
        ProductCategoryManualAdjustmentPayload.model_validate(record)
        for record in events
        if _matches_adjustment_filter(
            record,
            report_date=report_date,
            adjustment_id=adjustment_id,
            adjustment_id_exact=adjustment_id_exact,
            account_code=account_code,
            approval_status=approval_status,
            event_type=event_type,
            apply_event_type=True,
            created_at_from=created_at_from,
            created_at_to=created_at_to,
        )
    ]
    timeline = _sort_adjustment_payloads(
        timeline,
        field=event_sort_field,
        direction=event_sort_dir,
    )
    paged_timeline = timeline[offset : offset + limit]
    return ProductCategoryManualAdjustmentListPayload(
        report_date=report_date,
        adjustment_count=len(adjustments),
        adjustment_limit=adjustment_limit,
        adjustment_offset=adjustment_offset,
        event_total=len(timeline),
        event_limit=limit,
        event_offset=offset,
        adjustments=paged_adjustments,
        events=paged_timeline,
    ).model_dump(mode="json")


def export_product_category_manual_adjustments_csv(
    settings: Settings,
    report_date: str,
    adjustment_id: str | None = None,
    adjustment_id_exact: bool = False,
    account_code: str | None = None,
    approval_status: str | None = None,
    event_type: str | None = None,
    current_sort_field: ProductCategoryCurrentSortField = "created_at",
    current_sort_dir: ProductCategorySortDirection = "desc",
    event_sort_field: ProductCategoryEventSortField = "created_at",
    event_sort_dir: ProductCategorySortDirection = "desc",
    created_at_from: datetime | None = None,
    created_at_to: datetime | None = None,
) -> tuple[str, str]:
    events = _load_manual_adjustment_events(settings)
    records = _reduce_latest_adjustments(events)
    adjustments = [
        ProductCategoryManualAdjustmentPayload.model_validate(record)
        for record in records
        if _matches_adjustment_filter(
            record,
            report_date=report_date,
            adjustment_id=adjustment_id,
            adjustment_id_exact=adjustment_id_exact,
            account_code=account_code,
            approval_status=approval_status,
            event_type=event_type,
            apply_event_type=False,
            created_at_from=created_at_from,
            created_at_to=created_at_to,
        )
    ]
    adjustments = _sort_adjustment_payloads(
        adjustments,
        field=current_sort_field,
        direction=current_sort_dir,
    )
    timeline = [
        ProductCategoryManualAdjustmentPayload.model_validate(record)
        for record in events
        if _matches_adjustment_filter(
            record,
            report_date=report_date,
            adjustment_id=adjustment_id,
            adjustment_id_exact=adjustment_id_exact,
            account_code=account_code,
            approval_status=approval_status,
            event_type=event_type,
            apply_event_type=True,
            created_at_from=created_at_from,
            created_at_to=created_at_to,
        )
    ]
    timeline = _sort_adjustment_payloads(
        timeline,
        field=event_sort_field,
        direction=event_sort_dir,
    )
    filename = f"product-category-audit-{report_date}.csv"
    return filename, _build_adjustment_csv(adjustments, timeline)


def revoke_product_category_manual_adjustment(
    settings: Settings,
    adjustment_id: str,
) -> dict[str, object]:
    records = _reduce_latest_adjustments(_load_manual_adjustment_events(settings))
    current = next((record for record in records if record["adjustment_id"] == adjustment_id), None)
    if current is None:
        raise ValueError(f"Unknown product-category adjustment_id={adjustment_id}")
    if current["approval_status"] == "rejected":
        return current

    revoked = ProductCategoryManualAdjustmentPayload.model_validate(
        {
            **current,
            "event_type": "revoked",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "approval_status": "rejected",
        }
    )
    GovernanceRepository(base_dir=settings.governance_path).append(
        PRODUCT_CATEGORY_ADJUSTMENT_STREAM,
        revoked.model_dump(mode="json"),
    )
    return revoked.model_dump(mode="json")


def update_product_category_manual_adjustment(
    settings: Settings,
    adjustment_id: str,
    payload: ProductCategoryManualAdjustmentUpdateRequest,
) -> dict[str, object]:
    records = _reduce_latest_adjustments(_load_manual_adjustment_events(settings))
    current = next((record for record in records if record["adjustment_id"] == adjustment_id), None)
    if current is None:
        raise ValueError(f"Unknown product-category adjustment_id={adjustment_id}")
    updated = ProductCategoryManualAdjustmentPayload.model_validate(
        {
            **current,
            **payload.model_dump(),
            "event_type": "edited",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    GovernanceRepository(base_dir=settings.governance_path).append(
        PRODUCT_CATEGORY_ADJUSTMENT_STREAM,
        updated.model_dump(mode="json"),
    )
    return updated.model_dump(mode="json")


def restore_product_category_manual_adjustment(
    settings: Settings,
    adjustment_id: str,
) -> dict[str, object]:
    records = _reduce_latest_adjustments(_load_manual_adjustment_events(settings))
    current = next((record for record in records if record["adjustment_id"] == adjustment_id), None)
    if current is None:
        raise ValueError(f"Unknown product-category adjustment_id={adjustment_id}")
    if current["approval_status"] == "approved":
        return current
    restored = ProductCategoryManualAdjustmentPayload.model_validate(
        {
            **current,
            "event_type": "restored",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "approval_status": "approved",
        }
    )
    GovernanceRepository(base_dir=settings.governance_path).append(
        PRODUCT_CATEGORY_ADJUSTMENT_STREAM,
        restored.model_dump(mode="json"),
    )
    return restored.model_dump(mode="json")


def refresh_product_category_pnl(settings: Settings) -> dict[str, object]:
    return queue_product_category_pnl_refresh(settings)


def run_product_category_refresh_sync(settings: Settings, run_id: str | None = None) -> dict[str, object]:
    payload = materialize_product_category_pnl.fn(
        duckdb_path=str(settings.duckdb_path),
        source_dir=str(settings.product_category_source_dir),
        governance_dir=str(settings.governance_path),
        run_id=run_id,
    )
    return {
        **payload,
        "job_name": "product_category_pnl",
        "trigger_mode": "sync",
    }


def product_category_dates_envelope(duckdb_path: str) -> dict[str, object]:
    repo = ProductCategoryPnlRepository(duckdb_path)
    payload = ProductCategoryDatesPayload(
        report_dates=repo.list_report_dates(),
    )
    meta = ResultMeta(
        trace_id="tr_product_category_pnl_dates",
        basis="formal",
        result_kind="product_category_pnl.dates",
        formal_use_allowed=True,
        source_version=repo.latest_source_version(),
        vendor_version="vv_none",
        rule_version=RULE_VERSION,
        cache_version=CACHE_VERSION,
        quality_flag="ok",
        scenario_flag=False,
    )
    return {
        "result_meta": meta.model_dump(mode="json"),
        "result": payload.model_dump(mode="json"),
    }


def product_category_pnl_envelope(
    duckdb_path: str,
    report_date: str,
    view: str,
    scenario_rate_pct: float | None = None,
) -> dict[str, object]:
    analysis_envelope = build_analysis_service(duckdb_path).execute(
        AnalysisQuery(
            consumer="product_category_pnl",
            analysis_key="product_category_pnl",
            report_date=report_date,
            basis="scenario" if scenario_rate_pct is not None else "formal",
            view=view,
            scenario_rate_pct=scenario_rate_pct,
        )
    )

    typed_rows = [
        ProductCategoryPnlRow.model_validate(row)
        for row in analysis_envelope.result.rows
    ]
    asset_total = next(row for row in typed_rows if row.category_id == "asset_total")
    liability_total = next(row for row in typed_rows if row.category_id == "liability_total")
    grand_total = next(row for row in typed_rows if row.category_id == "grand_total")
    payload = ProductCategoryPnlPayload(
        report_date=report_date,
        view=view,
        available_views=list(analysis_envelope.result.summary["available_views"]),
        scenario_rate_pct=scenario_rate_pct,
        rows=typed_rows,
        asset_total=asset_total,
        liability_total=liability_total,
        grand_total=grand_total,
    )
    return {
        "result_meta": analysis_envelope.result_meta.model_dump(mode="json"),
        "result": payload.model_dump(mode="json"),
    }


def build_analysis_service(duckdb_path: str) -> UnifiedAnalysisService:
    return build_default_analysis_service(duckdb_path=duckdb_path)


def _build_run_id() -> str:
    return f"{PRODUCT_CATEGORY_JOB_NAME}:{datetime.now(timezone.utc).isoformat()}"


def _refresh_trigger_lock() -> LockDefinition:
    return LockDefinition(
        key=f"{PRODUCT_CATEGORY_PNL_LOCK.key}:trigger",
        ttl_seconds=30,
    )


def _load_refresh_run_records(settings: Settings) -> list[dict[str, object]]:
    return [
        record
        for record in GovernanceRepository(base_dir=settings.governance_path).read_all(CACHE_BUILD_RUN_STREAM)
        if str(record.get("job_name")) == PRODUCT_CATEGORY_JOB_NAME
        and str(record.get("cache_key")) == PRODUCT_CATEGORY_CACHE_KEY
    ]


def _latest_inflight_refresh(settings: Settings) -> dict[str, object] | None:
    by_run_id: dict[str, dict[str, object]] = {}
    for record in _load_refresh_run_records(settings):
        by_run_id[str(record.get("run_id"))] = record
    stale_records: list[dict[str, object]] = []
    for record in reversed(list(by_run_id.values())):
        if str(record.get("status")) in IN_FLIGHT_STATUSES:
            if _is_stale_inflight_record(record):
                stale_records.append(record)
                continue
            return record
    for record in stale_records:
        _mark_stale_inflight_run(
            settings=settings,
            run_id=str(record.get("run_id")),
            error_message="Marked stale product-category refresh run as failed.",
        )
    return None


def _is_stale_inflight_record(record: dict[str, object]) -> bool:
    for field_name in ("started_at", "queued_at", "created_at"):
        raw_value = str(record.get(field_name) or "").strip()
        if not raw_value:
            continue
        timestamp = _parse_timestamp(raw_value)
        return datetime.now(timezone.utc) - timestamp > STALE_IN_FLIGHT_AFTER
    return True


def _parse_timestamp(raw_value: str) -> datetime:
    normalized = raw_value.replace("Z", "+00:00") if raw_value.endswith("Z") else raw_value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _record_dispatch_failure(
    *,
    settings: Settings,
    run_id: str,
    error_message: str,
) -> None:
    GovernanceRepository(base_dir=settings.governance_path).append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": run_id,
            "job_name": PRODUCT_CATEGORY_JOB_NAME,
            "status": "failed",
            "cache_key": PRODUCT_CATEGORY_CACHE_KEY,
            "lock": PRODUCT_CATEGORY_PNL_LOCK.key,
            "source_version": "sv_product_category_failed",
            "vendor_version": "vv_none",
            "error_message": error_message,
        },
    )


def _mark_stale_inflight_run(
    *,
    settings: Settings,
    run_id: str,
    error_message: str,
) -> None:
    GovernanceRepository(base_dir=settings.governance_path).append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": run_id,
            "job_name": PRODUCT_CATEGORY_JOB_NAME,
            "status": "failed",
            "cache_key": PRODUCT_CATEGORY_CACHE_KEY,
            "lock": PRODUCT_CATEGORY_PNL_LOCK.key,
            "source_version": "sv_product_category_stale",
            "vendor_version": "vv_none",
            "error_message": error_message,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def _load_manual_adjustment_events(settings: Settings) -> list[dict[str, object]]:
    rows = GovernanceRepository(base_dir=settings.governance_path).read_all(
        PRODUCT_CATEGORY_ADJUSTMENT_STREAM
    )
    events: list[dict[str, object]] = []

    for index, row in enumerate(rows):
        adjustment_id = str(row.get("adjustment_id") or "")
        normalized = {
            "adjustment_id": adjustment_id or f"legacy-{index}",
            "event_type": str(row.get("event_type") or "legacy"),
            "created_at": str(row.get("created_at") or ""),
            "stream": PRODUCT_CATEGORY_ADJUSTMENT_STREAM,
            "report_date": str(row.get("report_date") or ""),
            "operator": str(row.get("operator") or ""),
            "approval_status": str(row.get("approval_status") or ""),
            "account_code": str(row.get("account_code") or ""),
            "currency": str(row.get("currency") or ""),
            "account_name": str(row.get("account_name") or ""),
            "beginning_balance": row.get("beginning_balance"),
            "ending_balance": row.get("ending_balance"),
            "monthly_pnl": row.get("monthly_pnl"),
            "daily_avg_balance": row.get("daily_avg_balance"),
            "annual_avg_balance": row.get("annual_avg_balance"),
        }
        events.append(normalized)

    return events


def _reduce_latest_adjustments(events: list[dict[str, object]]) -> list[dict[str, object]]:
    latest_by_id: dict[str, dict[str, object]] = {}
    for event in events:
        adjustment_id = str(event["adjustment_id"])
        existing = latest_by_id.get(adjustment_id)
        if existing is None or str(event["created_at"]) >= str(existing["created_at"]):
            latest_by_id[adjustment_id] = event
    return list(latest_by_id.values())


def _matches_adjustment_filter(
    record: dict[str, object],
    *,
    report_date: str,
    adjustment_id: str | None,
    adjustment_id_exact: bool,
    account_code: str | None,
    approval_status: str | None,
    event_type: str | None,
    apply_event_type: bool,
    created_at_from: datetime | None,
    created_at_to: datetime | None,
) -> bool:
    if str(record.get("report_date") or "") != report_date:
        return False
    if adjustment_id and adjustment_id.strip():
        record_adjustment_id = str(record.get("adjustment_id") or "")
        expected_adjustment_id = adjustment_id.strip()
        if adjustment_id_exact:
            if record_adjustment_id != expected_adjustment_id:
                return False
        elif expected_adjustment_id not in record_adjustment_id:
            return False
    if account_code and account_code.strip():
        if account_code.strip() not in str(record.get("account_code") or ""):
            return False
    if approval_status and approval_status.strip():
        if approval_status.strip() != str(record.get("approval_status") or ""):
            return False
    if apply_event_type and event_type and event_type.strip():
        if event_type.strip() != str(record.get("event_type") or ""):
            return False
    if created_at_from is not None or created_at_to is not None:
        record_created_at = _parse_created_at(str(record.get("created_at") or ""))
        if record_created_at is None:
            return False
        if created_at_from is not None and record_created_at < created_at_from:
            return False
        if created_at_to is not None and record_created_at > created_at_to:
            return False
    return True


def _sort_adjustment_payloads(
    items: list[ProductCategoryManualAdjustmentPayload],
    *,
    field: str,
    direction: ProductCategorySortDirection,
) -> list[ProductCategoryManualAdjustmentPayload]:
    reverse = direction == "desc"
    if field == "created_at":
        return sorted(
            items,
            key=lambda item: _parse_created_at(item.created_at) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=reverse,
        )
    return sorted(
        items,
        key=lambda item: str(getattr(item, field, "") or "").casefold(),
        reverse=reverse,
    )


def _parse_created_at(value: str) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _build_adjustment_csv(
    adjustments: list[ProductCategoryManualAdjustmentPayload],
    timeline: list[ProductCategoryManualAdjustmentPayload],
) -> str:
    headers = [
        "adjustment_id",
        "event_type",
        "created_at",
        "report_date",
        "operator",
        "approval_status",
        "account_code",
        "currency",
        "account_name",
        "monthly_pnl",
        "daily_avg_balance",
        "annual_avg_balance",
        "beginning_balance",
        "ending_balance",
    ]

    def serialize_row(row: ProductCategoryManualAdjustmentPayload) -> str:
        values = []
        for header in headers:
            value = str(getattr(row, header, "") or "")
            values.append(f'"{value.replace("\"", "\"\"")}"')
        return ",".join(values)

    sections = [
        "Current State",
        ",".join(headers),
        *[serialize_row(row) for row in adjustments],
        "",
        "Event Timeline",
        ",".join(headers),
        *[serialize_row(row) for row in timeline],
    ]
    return "\n".join(sections)
