from __future__ import annotations

from datetime import UTC, datetime

from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from backend.app.tasks.broker import register_actor_once

MACRO_SOURCE_BACKFILL_JOB_NAME = "macro_source_backfill_refresh"
MACRO_SOURCE_BACKFILL_CACHE_KEY = "macro_toolkit.source_backfill"
MACRO_SOURCE_BACKFILL_CACHE_VERSION = "macro_source_backfill_v1"
MACRO_SOURCE_BACKFILL_RULE_VERSION = "rv_macro_source_backfill_async_v1"
CFFEX_MEMBER_RANK_REFRESH_JOB_NAME = "cffex_member_rank_refresh"
CFFEX_MEMBER_RANK_REFRESH_CACHE_KEY = "macro_toolkit.cffex_member_rank"
CFFEX_MEMBER_RANK_REFRESH_CACHE_VERSION = "cffex_member_rank_refresh_v1"
CFFEX_MEMBER_RANK_REFRESH_RULE_VERSION = "rv_cffex_member_rank_async_v1"
_RETRYABLE_CFFEX_ATTEMPT_STATUSES = {"error", "unavailable"}
_WRITE_REFRESH_MAX_RETRIES = 3
_WRITE_REFRESH_MAX_ATTEMPTS = _WRITE_REFRESH_MAX_RETRIES + 1


class CffexMemberRankVendorError(RuntimeError):
    pass


def _backfill_macro_series(**kwargs: object) -> dict[str, object]:
    from backend.app.tasks.macro_backfill import backfill_macro_series

    return backfill_macro_series(**kwargs)


def _backfill_crisis_score_inputs(**kwargs: object) -> dict[str, object]:
    from backend.scripts.backfill_crisis_score_inputs import backfill_crisis_score_inputs

    return backfill_crisis_score_inputs(**kwargs)


def _materialize_cffex_member_rank(**kwargs: object) -> dict[str, object]:
    from backend.app.services.cffex_member_rank_service import materialize_cffex_member_rank

    return materialize_cffex_member_rank(**kwargs)


def run_macro_source_backfill_refresh(
    *,
    duckdb_path: str,
    governance_dir: str,
    run_id: str,
    alias: str,
    series_id: str,
    series_name: str,
    backfill_mode: str,
    start_date: str,
    end_date: str,
    sources: tuple[str, ...],
    request_fingerprint: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, object]:
    repo = GovernanceRepository(base_dir=governance_dir)
    resumed_payload = _cache_invalidation_retry_result(
        repo,
        run_id=run_id,
        job_name=MACRO_SOURCE_BACKFILL_JOB_NAME,
    )
    attempt_count = _next_attempt_count(
        repo,
        run_id=run_id,
        job_name=MACRO_SOURCE_BACKFILL_JOB_NAME,
    )
    base = {
        "run_id": run_id,
        "job_name": MACRO_SOURCE_BACKFILL_JOB_NAME,
        "cache_key": MACRO_SOURCE_BACKFILL_CACHE_KEY,
        "cache_version": MACRO_SOURCE_BACKFILL_CACHE_VERSION,
        "rule_version": MACRO_SOURCE_BACKFILL_RULE_VERSION,
        "report_date": end_date,
        "alias": alias,
        "series_ids": [series_id],
        "series_names": [series_name],
        "backfill_mode": backfill_mode,
        "start_date": start_date,
        "end_date": end_date,
        "sources": list(sources),
        "duckdb_path": duckdb_path,
        "request_fingerprint": request_fingerprint,
        "idempotency_key": idempotency_key,
        "attempt_count": attempt_count,
        "max_attempts": _WRITE_REFRESH_MAX_ATTEMPTS,
    }
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            **base,
            "status": "running",
            "trigger_mode": "async",
            "started_at": datetime.now(UTC).isoformat(),
            "resume_phase": (
                "cache_invalidation" if resumed_payload is not None else "write"
            ),
        },
    )
    try:
        payload = (
            resumed_payload
            if resumed_payload is not None
            else _execute_macro_source_backfill(
                duckdb_path=duckdb_path,
                alias=alias,
                series_name=series_name,
                backfill_mode=backfill_mode,
                start_date=start_date,
                end_date=end_date,
                sources=sources,
            )
        )
    except Exception as exc:
        failure_status, retry_pending = _retry_failure_state(
            attempt_count=attempt_count,
            retryable=_is_retryable_failure(exc),
        )
        repo.append(
            CACHE_BUILD_RUN_STREAM,
            {
                **base,
                "status": failure_status,
                "trigger_mode": _attempt_trigger_mode(failure_status),
                "finished_at": datetime.now(UTC).isoformat(),
                "error_message": str(exc),
                "failure_category": "backfill_failure",
                "failure_reason": type(exc).__name__,
                "retryable": retry_pending,
            },
        )
        raise

    status = str(payload.get("status") or "completed")
    terminal = {
        **base,
        **payload,
        "run_id": run_id,
        "job_name": MACRO_SOURCE_BACKFILL_JOB_NAME,
        "status": status,
        "trigger_mode": "terminal",
        "retryable": False,
        "result": payload,
    }
    if int(payload.get("total_added") or 0) > 0:
        try:
            _invalidate_macro_source_caches()
        except Exception as exc:
            failure_status, retry_pending = _retry_failure_state(
                attempt_count=attempt_count,
                retryable=True,
            )
            repo.append(
                CACHE_BUILD_RUN_STREAM,
                {
                    **base,
                    **payload,
                    "run_id": run_id,
                    "job_name": MACRO_SOURCE_BACKFILL_JOB_NAME,
                    "status": failure_status,
                    "write_status": status,
                    "trigger_mode": _attempt_trigger_mode(failure_status),
                    "finished_at": datetime.now(UTC).isoformat(),
                    "error_message": str(exc),
                    "failure_category": "cache_invalidation",
                    "failure_reason": type(exc).__name__,
                    "retryable": retry_pending,
                    "result": payload,
                },
            )
            raise
    terminal["finished_at"] = datetime.now(UTC).isoformat()
    repo.append(CACHE_BUILD_RUN_STREAM, terminal)
    return terminal


def run_cffex_member_rank_refresh(
    *,
    duckdb_path: str,
    governance_dir: str,
    run_id: str,
    trade_date: str | None,
    contracts: tuple[str, ...],
    sources: tuple[str, ...],
    request_fingerprint: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, object]:
    repo = GovernanceRepository(base_dir=governance_dir)
    resumed_payload = _cache_invalidation_retry_result(
        repo,
        run_id=run_id,
        job_name=CFFEX_MEMBER_RANK_REFRESH_JOB_NAME,
    )
    attempt_count = _next_attempt_count(
        repo,
        run_id=run_id,
        job_name=CFFEX_MEMBER_RANK_REFRESH_JOB_NAME,
    )
    base = {
        "run_id": run_id,
        "job_name": CFFEX_MEMBER_RANK_REFRESH_JOB_NAME,
        "cache_key": CFFEX_MEMBER_RANK_REFRESH_CACHE_KEY,
        "cache_version": CFFEX_MEMBER_RANK_REFRESH_CACHE_VERSION,
        "rule_version": CFFEX_MEMBER_RANK_REFRESH_RULE_VERSION,
        "report_date": trade_date,
        "trade_date": trade_date,
        "contracts": list(contracts),
        "sources": list(sources),
        "duckdb_path": duckdb_path,
        "request_fingerprint": request_fingerprint,
        "idempotency_key": idempotency_key,
        "attempt_count": attempt_count,
        "max_attempts": _WRITE_REFRESH_MAX_ATTEMPTS,
    }
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            **base,
            "status": "running",
            "trigger_mode": "async",
            "started_at": datetime.now(UTC).isoformat(),
            "resume_phase": (
                "cache_invalidation" if resumed_payload is not None else "write"
            ),
        },
    )
    try:
        payload = (
            resumed_payload
            if resumed_payload is not None
            else _materialize_cffex_member_rank(
                duckdb_path=duckdb_path,
                trade_date=trade_date,
                contracts=contracts,
                sources=sources,
            )
        )
        status = _cffex_terminal_status(payload)
        if status == "failed" and _cffex_vendor_failure_is_retryable(payload):
            raise CffexMemberRankVendorError(_cffex_failure_message(payload))
    except Exception as exc:
        failure_status, retry_pending = _retry_failure_state(
            attempt_count=attempt_count,
            retryable=_is_retryable_failure(exc),
        )
        repo.append(
            CACHE_BUILD_RUN_STREAM,
            {
                **base,
                "status": failure_status,
                "trigger_mode": _attempt_trigger_mode(failure_status),
                "finished_at": datetime.now(UTC).isoformat(),
                "error_message": str(exc),
                "failure_category": "vendor_failure",
                "failure_reason": type(exc).__name__,
                "retryable": retry_pending,
            },
        )
        raise

    terminal = {
        **base,
        **payload,
        "run_id": run_id,
        "job_name": CFFEX_MEMBER_RANK_REFRESH_JOB_NAME,
        "status": status,
        "trigger_mode": "terminal",
        "retryable": False,
        "result": payload,
    }
    if int(payload.get("row_count") or 0) > 0:
        try:
            _invalidate_cffex_member_rank_caches()
        except Exception as exc:
            failure_status, retry_pending = _retry_failure_state(
                attempt_count=attempt_count,
                retryable=True,
            )
            repo.append(
                CACHE_BUILD_RUN_STREAM,
                {
                    **base,
                    **payload,
                    "run_id": run_id,
                    "job_name": CFFEX_MEMBER_RANK_REFRESH_JOB_NAME,
                    "status": failure_status,
                    "write_status": status,
                    "trigger_mode": _attempt_trigger_mode(failure_status),
                    "finished_at": datetime.now(UTC).isoformat(),
                    "error_message": str(exc),
                    "failure_category": "cache_invalidation",
                    "failure_reason": type(exc).__name__,
                    "retryable": retry_pending,
                    "result": payload,
                },
            )
            raise
    terminal["finished_at"] = datetime.now(UTC).isoformat()
    repo.append(CACHE_BUILD_RUN_STREAM, terminal)
    return terminal


def _execute_macro_source_backfill(
    *,
    duckdb_path: str,
    alias: str,
    series_name: str,
    backfill_mode: str,
    start_date: str,
    end_date: str,
    sources: tuple[str, ...],
) -> dict[str, object]:
    if backfill_mode == "crisis_score_inputs":
        from backend.app.core_finance.macro.toolkit.system_sources import normalize_macro_alias

        raw = _backfill_crisis_score_inputs(
            duckdb_path=duckdb_path,
            start_date=start_date,
            end_date=end_date,
            dry_run=False,
            aliases=[alias],
        )
        canonical_alias = normalize_macro_alias(alias)
        results_by_alias = raw.get("results")
        result: dict[str, object] = {}
        if isinstance(results_by_alias, dict):
            for result_alias, result_payload in results_by_alias.items():
                if normalize_macro_alias(result_alias) == canonical_alias and isinstance(result_payload, dict):
                    result = result_payload
                    break
        status = str(result.get("status") or ("partial" if raw.get("errors") else "completed"))
        total_added = int(result.get("written_rows") or result.get("row_count") or 0)
        return {
            "status": status,
            "dry_run": False,
            "processed_count": 1 if status == "completed" else 0,
            "total_added": total_added,
            "total_fetched": int(result.get("row_count") or 0),
            "results": {canonical_alias: total_added},
            "errors": raw.get("errors") or {},
        }
    if backfill_mode != "macro_series":
        raise ValueError(f"Unsupported macro source backfill mode: {backfill_mode}")
    raw = _backfill_macro_series(
        duckdb_path=duckdb_path,
        series_names=[series_name],
        start_date=start_date,
        end_date=end_date,
        dry_run=False,
        sources_filter=list(sources),
    )
    status = str(raw.get("status") or ("partial" if raw.get("errors") else "completed"))
    return {**raw, "status": status}


def _cffex_terminal_status(payload: dict[str, object]) -> str:
    attempts = [item for item in payload.get("attempts") or [] if isinstance(item, dict)]
    statuses = {str(item.get("status") or "") for item in attempts}
    row_count = int(payload.get("row_count") or 0)
    if row_count > 0:
        return "completed" if statuses <= {"materialized"} else "partial"
    return "failed"


def _cffex_vendor_failure_is_retryable(payload: dict[str, object]) -> bool:
    return any(
        str(item.get("status") or "") in _RETRYABLE_CFFEX_ATTEMPT_STATUSES
        for item in payload.get("attempts") or []
        if isinstance(item, dict)
    )


def _cffex_failure_message(payload: dict[str, object]) -> str:
    details = [
        str(item.get("detail") or item.get("status") or "vendor failure")
        for item in payload.get("attempts") or []
        if isinstance(item, dict)
    ]
    return "; ".join(details) or "CFFEX member-rank vendors returned no materializable rows."


def _cache_invalidation_retry_result(
    repo: GovernanceRepository,
    *,
    run_id: str,
    job_name: str,
) -> dict[str, object] | None:
    latest = next(
        (
            record
            for record in reversed(repo.read_all(CACHE_BUILD_RUN_STREAM))
            if str(record.get("run_id") or "") == run_id
            and str(record.get("job_name") or "") == job_name
        ),
        None,
    )
    if (
        latest is None
        or str(latest.get("status") or "") not in {"retrying", "failed"}
        or str(latest.get("failure_category") or "") != "cache_invalidation"
        or latest.get("retryable") is not True
    ):
        return None
    result = latest.get("result")
    return dict(result) if isinstance(result, dict) else None


def _retry_failure_state(
    *,
    attempt_count: int,
    retryable: bool,
) -> tuple[str, bool]:
    retry_pending = retryable and attempt_count <= _WRITE_REFRESH_MAX_RETRIES
    return ("retrying" if retry_pending else "failed", retry_pending)


def _attempt_trigger_mode(status: str) -> str:
    return "async" if status == "retrying" else "terminal"


def _next_attempt_count(
    repo: GovernanceRepository,
    *,
    run_id: str,
    job_name: str,
) -> int:
    prior_attempts = sum(
        1
        for record in repo.read_all(CACHE_BUILD_RUN_STREAM)
        if str(record.get("run_id") or "") == run_id
        and str(record.get("job_name") or "") == job_name
        and str(record.get("status") or "") == "running"
    )
    return prior_attempts + 1


def _is_retryable_failure(exc: Exception) -> bool:
    return isinstance(exc, (CffexMemberRankVendorError, ConnectionError, OSError, TimeoutError))


def _invalidate_cffex_member_rank_caches() -> None:
    from backend.app.api.response_cache import market_home_response_cache

    market_home_response_cache.invalidate()


def _invalidate_macro_source_caches() -> None:
    from backend.app.api.response_cache import market_home_response_cache
    from backend.app.core_finance.macro.toolkit.system_sources import clear_system_macro_source_cache

    market_home_response_cache.invalidate()
    clear_system_macro_source_cache()


run_macro_source_backfill_refresh_task = register_actor_once(
    "run_macro_source_backfill_refresh",
    run_macro_source_backfill_refresh,
    max_retries=_WRITE_REFRESH_MAX_RETRIES,
    time_limit_ms=3_600_000,
)
run_cffex_member_rank_refresh_task = register_actor_once(
    "run_cffex_member_rank_refresh",
    run_cffex_member_rank_refresh,
    max_retries=_WRITE_REFRESH_MAX_RETRIES,
    time_limit_ms=3_600_000,
)
