"""Schedulable orchestration for macro-toolkit price/commodity freshness.

Keeps the observation cards (CTA / DCC / risk parity / crisis inputs) readable by
refreshing, in a single-writer sequence:

1. commodity futures + Nanhua index daily bars
2. public cross-asset headlines (CSI300/500, copper CA.*, DR007, …)
3. Choice 7D reverse-repo policy rate
4. Tushare SHIBOR tenors used by the NCD funding proxy
5. CFFEX member-rank for the latest weekday (soft-fail on weekends / vendor gaps)

Does not change formal-use policy; observation cards remain non-formal.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TypeVar

import duckdb
import requests

from backend.app.governance.settings import get_settings
from backend.app.services.cffex_member_rank_service import materialize_cffex_member_rank
from backend.app.tasks.broker import register_actor_once
from backend.app.tasks.choice_macro import (
    NCD_SHIBOR_LOOKBACK_DAYS,
    NCD_SHIBOR_TENORS,
    PublicCrossAssetRetryableError,
    refresh_public_cross_asset_headlines,
    refresh_tushare_ncd_shibor_proxy,
)
from backend.app.tasks.commodity_daily_ingest import run_commodity_daily_ingest

logger = logging.getLogger(__name__)

DEFAULT_COMMODITY_LOOKBACK_DAYS = 14
DEFAULT_PUBLIC_HEADLINE_LOOKBACK_DAYS = 120
DEFAULT_POLICY_RATE_LOOKBACK_DAYS = 45
POLICY_RATE_SERIES_ID = "EMM00088132"
SOURCE_VERSION = "macro_toolkit_freshness_refresh_v3"
DUCKDB_WRITE_RETRY_ATTEMPTS = 6
DUCKDB_WRITE_RETRY_SLEEP_SECONDS = 10.0
CFFEX_FALLBACK_WORKDAYS = 10
CFFEX_EMPTY_ATTEMPT_STATUSES = frozenset({"empty"})
CFFEX_RETRYABLE_ATTEMPT_STATUSES = frozenset({"error", "unavailable"})
NCD_SHIBOR_SERIES_IDS: tuple[str, ...] = tuple(
    str(meta["series_id"]) for meta in NCD_SHIBOR_TENORS.values()
)
TRACKED_CHOICE_SERIES_IDS: tuple[str, ...] = (
    "CA.CSI300",
    "CA.CSI500",
    "CA.COPPER",
    "NHCI.NH",
    POLICY_RATE_SERIES_ID,
    *NCD_SHIBOR_SERIES_IDS,
)
REQUIRED_STEP_NAMES = frozenset(
    {
        "commodity_daily_ingest",
        "public_cross_asset_headlines",
        "choice_policy_rate_7d",
        "tushare_ncd_shibor",
    }
)

# Core legs for CTA/DCC/RP observation cards plus common toolkit commodities.
DEFAULT_COMMODITY_PRODUCTS: tuple[str, ...] = (
    "CU",
    "AL",
    "AU",
    "SC",
    "NHCI",
    "NHII",
    "RB",
    "HC",
    "I",
    "JM",
    "J",
    "ZN",
    "TA",
    "MA",
    "M",
    "P",
    "AG",
    "TS",
    "TF",
    "T",
    "TL",
)

_T = TypeVar("_T")


class RetryableFreshnessError(RuntimeError):
    """A scheduled refresh failure that should be retried by Dramatiq."""


def _new_run_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"macro-toolkit-freshness-{stamp}-{uuid.uuid4().hex[:8]}"


def _latest_weekday_on_or_before(day: date) -> date:
    cursor = day
    while cursor.weekday() >= 5:
        cursor -= timedelta(days=1)
    return cursor


def _recent_weekdays_on_or_before(day: date, *, limit: int) -> list[date]:
    candidates: list[date] = []
    cursor = day
    while len(candidates) < limit:
        if cursor.weekday() < 5:
            candidates.append(cursor)
        cursor -= timedelta(days=1)
    return candidates


def _safe_error_reason(exc: BaseException) -> str:
    message = " ".join(str(exc).split()) or "no error details"
    return f"{type(exc).__name__}: {message[:500]}"


def _is_non_retryable_contract_error(exc: BaseException) -> bool:
    return isinstance(
        exc,
        (ValueError, TypeError, PermissionError, ImportError, AttributeError),
    )


def _is_retryable_task_error(exc: BaseException) -> bool:
    if _is_non_retryable_contract_error(exc):
        return False
    if isinstance(exc, PublicCrossAssetRetryableError):
        return True
    if isinstance(exc, requests.exceptions.HTTPError):
        response = exc.response
        status_code = int(response.status_code) if response is not None else None
        if status_code is not None and 400 <= status_code < 500:
            return status_code in {408, 429}
        return True
    if _is_duckdb_writer_contention(exc):
        return True
    return isinstance(
        exc,
        (
            ConnectionError,
            TimeoutError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.RequestException,
        ),
    )


def _cffex_attempt_summary(attempt: dict[str, object]) -> str:
    status = str(attempt.get("status") or "unknown")
    error_type = str(
        attempt.get("error_type")
        or attempt.get("exception_type")
        or status
    )
    detail = " ".join(str(attempt.get("detail") or "").split())
    source_vendor = str(attempt.get("source_vendor") or "unknown_vendor")
    contract = str(attempt.get("contract") or "unknown_contract")
    summary = f"{source_vendor}/{contract} {error_type}"
    if detail:
        summary = f"{summary}: {detail[:500]}"
    return summary


def _is_retryable_cffex_attempt(attempt: dict[str, object]) -> bool:
    status = str(attempt.get("status") or "").strip().casefold()
    if status not in CFFEX_RETRYABLE_ATTEMPT_STATUSES:
        return False
    error_type = str(
        attempt.get("error_type")
        or attempt.get("exception_type")
        or ""
    ).strip().casefold()
    if any(
        marker in error_type
        for marker in (
            "authentication",
            "authorization",
            "credential",
            "invalidtoken",
            "permission",
            "valueerror",
            "typeerror",
            "parameter",
            "validation",
            "configuration",
            "importerror",
            "attributeerror",
        )
    ):
        return False
    detail = str(attempt.get("detail") or "").casefold()
    if any(
        marker in detail
        for marker in (
            "token",
            "credential",
            "authentication",
            "authorization",
            "permission",
            "unauthorized",
            "forbidden",
            "parameter",
            "invalid exchange",
            "invalid contract",
            "not configured",
            "not installed",
            "权限",
            "认证",
            "参数",
        )
    ):
        return False
    if any(
        marker in error_type
        for marker in (
            "connection",
            "timeout",
            "network",
            "proxy",
            "sslerror",
            "httperror",
            "requestexception",
            "remotedisconnected",
        )
    ):
        return True
    return any(
        marker in detail
        for marker in (
            "connection",
            "timed out",
            "timeout",
            "network",
            "temporary failure",
            "temporarily unavailable",
            "remote disconnected",
            "service unavailable",
            "too many requests",
            "connection reset",
            "http 408",
            "http 429",
            "http 500",
            "http 502",
            "http 503",
            "http 504",
        )
    )


def _step_receipt(
    *,
    step: str,
    status: str,
    started_at: datetime,
    started_clock: float,
    attempt_count: int,
    result: object | None = None,
    reason: str | None = None,
    **details: object,
) -> dict[str, object]:
    finished_at = datetime.now(UTC)
    receipt: dict[str, object] = {
        "step": step,
        "status": status,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": round(max(time.monotonic() - started_clock, 0.0), 6),
        "attempt_count": attempt_count,
        **details,
    }
    if result is not None:
        receipt["result"] = result
    if reason is not None:
        receipt["reason"] = reason
    return receipt


def _is_duckdb_writer_contention(exc: BaseException) -> bool:
    message = str(exc).lower()
    return isinstance(exc, duckdb.Error) and (
        "already open" in message
        or "database is locked" in message
        or "could not set lock" in message
        or "conflicting lock" in message
        or "lock on file" in message
    )


def _call_with_duckdb_retry(label: str, fn: Callable[[], _T]) -> _T:
    last_exc: BaseException | None = None
    for attempt in range(1, DUCKDB_WRITE_RETRY_ATTEMPTS + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - retry only writer contention
            last_exc = exc
            if not _is_duckdb_writer_contention(exc) or attempt >= DUCKDB_WRITE_RETRY_ATTEMPTS:
                raise
            logger.warning(
                "macro toolkit freshness: %s hit DuckDB writer contention attempt=%s/%s; sleep=%.0fs err=%s",
                label,
                attempt,
                DUCKDB_WRITE_RETRY_ATTEMPTS,
                DUCKDB_WRITE_RETRY_SLEEP_SECONDS,
                exc,
            )
            time.sleep(DUCKDB_WRITE_RETRY_SLEEP_SECONDS)
    assert last_exc is not None
    raise last_exc


def _run_required_step(
    *,
    step: str,
    fn: Callable[[], object],
    result_fields: Sequence[str],
) -> dict[str, object]:
    started_at = datetime.now(UTC)
    started_clock = time.monotonic()
    attempt_count = 0

    def counted_call() -> object:
        nonlocal attempt_count
        attempt_count += 1
        return fn()

    try:
        raw_result = _call_with_duckdb_retry(step, counted_call)
    except Exception as exc:  # noqa: BLE001 - required failure must retain receipts
        if _is_retryable_task_error(exc):
            raise
        reason = f"{step} failed: {_safe_error_reason(exc)}"
        logger.error("macro toolkit freshness: %s", reason)
        return _step_receipt(
            step=step,
            status="failed",
            started_at=started_at,
            started_clock=started_clock,
            attempt_count=attempt_count,
            reason=reason,
        )

    if not isinstance(raw_result, dict):
        return _step_receipt(
            step=step,
            status="failed",
            started_at=started_at,
            started_clock=started_clock,
            attempt_count=attempt_count,
            reason=f"{step} returned invalid result type: {type(raw_result).__name__}",
        )

    result = {field: raw_result.get(field) for field in result_fields}
    raw_status = str(raw_result.get("status") or "unknown")
    if raw_status in {"completed", "success", "partial", "degraded"}:
        row_count_reason: str | None = None
        if "row_count" not in raw_result:
            row_count_reason = "missing row_count"
        else:
            try:
                row_count = int(raw_result["row_count"])
            except (TypeError, ValueError, OverflowError):
                row_count_reason = "invalid row_count"
            else:
                if row_count <= 0:
                    row_count_reason = f"non-positive row_count: {row_count}"
        if row_count_reason is not None:
            return _step_receipt(
                step=step,
                status="failed",
                started_at=started_at,
                started_clock=started_clock,
                attempt_count=attempt_count,
                result=result,
                reason=f"{step} returned success status with {row_count_reason}",
            )
        receipt_status = (
            "success" if raw_status in {"completed", "success"} else "degraded"
        )
        return _step_receipt(
            step=step,
            status=receipt_status,
            started_at=started_at,
            started_clock=started_clock,
            attempt_count=attempt_count,
            result=result,
            reason=(
                f"{step} returned {raw_status} status"
                if receipt_status == "degraded"
                else None
            ),
        )
    return _step_receipt(
        step=step,
        status="failed",
        started_at=started_at,
        started_clock=started_clock,
        attempt_count=attempt_count,
        result=result,
        reason=f"{step} returned non-success status: {raw_status}",
    )


def _has_required_step_failure(steps: Sequence[dict[str, object]]) -> bool:
    statuses_by_name = {
        str(step.get("step")): str(step.get("status"))
        for step in steps
        if step.get("step") in REQUIRED_STEP_NAMES
    }
    return any(
        statuses_by_name.get(step_name) not in {"success", "degraded"}
        for step_name in REQUIRED_STEP_NAMES
    )


def _has_required_step_degradation(steps: Sequence[dict[str, object]]) -> bool:
    return any(
        step.get("step") in REQUIRED_STEP_NAMES
        and str(step.get("status")) == "degraded"
        for step in steps
    )


def _run_cffex_step(*, report_date: date, duckdb_path: str) -> dict[str, object]:
    started_at = datetime.now(UTC)
    started_clock = time.monotonic()
    attempt_count = 0
    attempts: list[dict[str, object]] = []
    candidates = _recent_weekdays_on_or_before(
        report_date,
        limit=CFFEX_FALLBACK_WORKDAYS,
    )

    def finish(
        *,
        status: str,
        reason: str | None = None,
        trade_date: date | None = None,
        row_count: int | None = None,
        payload_keys: list[str] | None = None,
    ) -> dict[str, object]:
        result: dict[str, object] = {"attempts": attempts}
        if row_count is not None:
            result["row_count"] = row_count
        if payload_keys is not None:
            result["payload_keys"] = payload_keys
        return _step_receipt(
            step="cffex_member_rank",
            status=status,
            started_at=started_at,
            started_clock=started_clock,
            attempt_count=attempt_count,
            result=result,
            reason=reason,
            **({"trade_date": trade_date.isoformat()} if trade_date is not None else {}),
        )

    for trade_date in candidates:
        candidate_attempts_before = attempt_count

        def materialize(candidate: date = trade_date) -> object:
            nonlocal attempt_count
            attempt_count += 1
            return materialize_cffex_member_rank(
                trade_date=candidate.isoformat(),
                duckdb_path=duckdb_path,
                sources=("tushare",),
            )

        try:
            raw_result = _call_with_duckdb_retry("cffex_member_rank", materialize)
        except Exception as exc:  # noqa: BLE001 - optional source degrades the run
            reason = _safe_error_reason(exc)
            logger.warning(
                "macro toolkit freshness: cffex attempt failed trade_date=%s err=%s",
                trade_date.isoformat(),
                reason,
            )
            attempts.append(
                {
                    "trade_date": trade_date.isoformat(),
                    "status": "failed",
                    "reason": reason,
                    "error_type": type(exc).__name__,
                    "attempt_count": attempt_count - candidate_attempts_before,
                }
            )
            if _is_retryable_task_error(exc):
                raise
            return finish(
                status="failed" if _is_non_retryable_contract_error(exc) else "degraded",
                reason=f"CFFEX failed for {trade_date.isoformat()}: {reason}",
                trade_date=trade_date,
            )

        if not isinstance(raw_result, dict):
            reason = f"invalid result type: {type(raw_result).__name__}"
            attempts.append(
                {
                    "trade_date": trade_date.isoformat(),
                    "status": "failed",
                    "reason": reason,
                    "attempt_count": attempt_count - candidate_attempts_before,
                }
            )
            return finish(
                status="failed",
                reason=f"CFFEX failed for {trade_date.isoformat()}: {reason}",
                trade_date=trade_date,
            )

        raw_source_attempts = raw_result.get("attempts")
        legacy_attempts_omitted = "attempts" not in raw_result
        if raw_source_attempts is None:
            source_attempts: list[dict[str, object]] = []
        elif isinstance(raw_source_attempts, list) and all(
            isinstance(item, dict) for item in raw_source_attempts
        ):
            source_attempts = [dict(item) for item in raw_source_attempts]
        else:
            reason = "invalid attempts payload"
            attempts.append(
                {
                    "trade_date": trade_date.isoformat(),
                    "status": "failed",
                    "reason": reason,
                    "source_attempts": [],
                    "attempt_count": attempt_count - candidate_attempts_before,
                }
            )
            return finish(
                status="failed",
                reason=f"CFFEX failed for {trade_date.isoformat()}: {reason}",
                trade_date=trade_date,
                payload_keys=sorted(str(key) for key in raw_result),
            )

        if "row_count" not in raw_result:
            reason = "missing row_count"
            attempts.append(
                {
                    "trade_date": trade_date.isoformat(),
                    "status": "failed",
                    "reason": reason,
                    "source_attempts": source_attempts,
                    "attempt_count": attempt_count - candidate_attempts_before,
                }
            )
            return finish(
                status="failed",
                reason=f"CFFEX failed for {trade_date.isoformat()}: {reason}",
                trade_date=trade_date,
                payload_keys=sorted(str(key) for key in raw_result),
            )
        try:
            row_count = int(raw_result["row_count"])
        except (TypeError, ValueError, OverflowError):
            reason = "invalid row_count"
            attempts.append(
                {
                    "trade_date": trade_date.isoformat(),
                    "status": "failed",
                    "reason": reason,
                    "source_attempts": source_attempts,
                    "attempt_count": attempt_count - candidate_attempts_before,
                }
            )
            return finish(
                status="failed",
                reason=f"CFFEX failed for {trade_date.isoformat()}: {reason}",
                trade_date=trade_date,
                payload_keys=sorted(str(key) for key in raw_result),
            )
        if row_count < 0:
            reason = "negative row_count"
            attempts.append(
                {
                    "trade_date": trade_date.isoformat(),
                    "status": "failed",
                    "reason": reason,
                    "source_attempts": source_attempts,
                    "attempt_count": attempt_count - candidate_attempts_before,
                }
            )
            return finish(
                status="failed",
                reason=f"CFFEX failed for {trade_date.isoformat()}: {reason}",
                trade_date=trade_date,
                payload_keys=sorted(str(key) for key in raw_result),
            )

        anomalous_attempts = [
            item
            for item in source_attempts
            if str(item.get("status") or "").strip().casefold()
            not in CFFEX_EMPTY_ATTEMPT_STATUSES | {"materialized"}
        ]
        if row_count == 0:
            all_attempts_empty = legacy_attempts_omitted or (
                bool(source_attempts)
                and all(
                    str(item.get("status") or "").strip().casefold()
                    in CFFEX_EMPTY_ATTEMPT_STATUSES
                    for item in source_attempts
                )
            )
            if all_attempts_empty:
                logger.warning(
                    "macro toolkit freshness: cffex returned true empty rows trade_date=%s; trying fallback",
                    trade_date.isoformat(),
                )
                attempts.append(
                    {
                        "trade_date": trade_date.isoformat(),
                        "status": "zero_rows",
                        "row_count": 0,
                        "source_attempts": source_attempts,
                        "attempt_count": attempt_count - candidate_attempts_before,
                    }
                )
                continue

            summaries = [_cffex_attempt_summary(item) for item in anomalous_attempts]
            reason = "; ".join(summaries) or "CFFEX returned no true-empty source attempts"
            attempts.append(
                {
                    "trade_date": trade_date.isoformat(),
                    "status": "failed",
                    "row_count": 0,
                    "reason": reason,
                    "source_attempts": source_attempts,
                    "attempt_count": attempt_count - candidate_attempts_before,
                }
            )
            if any(_is_retryable_cffex_attempt(item) for item in anomalous_attempts):
                raise RetryableFreshnessError(
                    f"CFFEX failed for {trade_date.isoformat()}: {reason}"
                )
            return finish(
                status="failed",
                reason=f"CFFEX failed for {trade_date.isoformat()}: {reason}",
                trade_date=trade_date,
                row_count=0,
                payload_keys=sorted(str(key) for key in raw_result),
            )

        attempts.append(
            {
                "trade_date": trade_date.isoformat(),
                "status": "degraded" if anomalous_attempts else "success",
                "row_count": row_count,
                "source_attempts": source_attempts,
                "attempt_count": attempt_count - candidate_attempts_before,
            }
        )
        anomaly_reason = (
            "; ".join(_cffex_attempt_summary(item) for item in anomalous_attempts)
            if anomalous_attempts
            else None
        )
        return finish(
            status="degraded" if anomalous_attempts else "success",
            reason=(
                f"CFFEX partially materialized for {trade_date.isoformat()}: {anomaly_reason}"
                if anomaly_reason
                else None
            ),
            trade_date=trade_date,
            row_count=row_count,
            payload_keys=sorted(str(key) for key in raw_result),
        )

    return finish(
        status="degraded",
        reason=f"CFFEX returned zero rows across latest {CFFEX_FALLBACK_WORKDAYS} workdays",
    )


def _refresh_choice_policy_rate_7d(
    *,
    duckdb_path: str,
    report_date: str,
    lookback_days: int = DEFAULT_POLICY_RATE_LOOKBACK_DAYS,
) -> dict[str, object]:
    from backend.scripts.backfill_crisis_score_inputs import backfill_crisis_score_inputs

    end = date.fromisoformat(report_date)
    start_date = (end - timedelta(days=max(lookback_days - 1, 0))).isoformat()
    payload = backfill_crisis_score_inputs(
        duckdb_path=duckdb_path,
        start_date=start_date,
        end_date=report_date,
        dry_run=False,
        aliases=["M0041653"],
    )
    result = (payload.get("results") or {}).get("M0041653") or {}
    return {
        "status": str(result.get("status") or ("error" if payload.get("errors") else "unknown")),
        "row_count": int(result.get("written_rows") or result.get("row_count") or 0),
        "series_id": POLICY_RATE_SERIES_ID,
        "run_id": payload.get("run_id"),
        "start_date": start_date,
        "end_date": report_date,
        "errors": payload.get("errors") or {},
    }


def _append_evidence_warning(
    warnings: list[str] | None,
    area: str,
    exc: BaseException,
) -> None:
    if warnings is not None:
        warnings.append(f"latest_observation_dates.{area}: {_safe_error_reason(exc)}")


def _read_latest_observation_dates(
    duckdb_path: str | Path,
    *,
    warnings: list[str] | None = None,
) -> dict[str, str | None]:
    """Read-only post-run evidence for go-live / operator logs."""
    path = Path(duckdb_path)
    out: dict[str, str | None] = {
        "fact_commodity_futures_daily": None,
        "fact_cffex_member_rank_daily": None,
        **dict.fromkeys(TRACKED_CHOICE_SERIES_IDS),
    }
    if not path.exists():
        if warnings is not None:
            warnings.append("latest_observation_dates: DuckDB path does not exist")
        return out
    try:
        conn = duckdb.connect(str(path), read_only=True)
    except Exception as exc:  # noqa: BLE001 - evidence must be fail-soft
        _append_evidence_warning(warnings, "connect", exc)
        return out

    def fetchone(area: str, sql: str) -> tuple[object, ...] | None:
        try:
            return conn.execute(sql).fetchone()
        except Exception as exc:  # noqa: BLE001 - retain other evidence
            _append_evidence_warning(warnings, area, exc)
            return None

    def fetchall(area: str, sql: str) -> list[tuple[object, ...]]:
        try:
            return conn.execute(sql).fetchall()
        except Exception as exc:  # noqa: BLE001 - retain other evidence
            _append_evidence_warning(warnings, area, exc)
            return []

    try:
        try:
            tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
        except Exception as exc:  # noqa: BLE001 - evidence must be fail-soft
            _append_evidence_warning(warnings, "tables", exc)
            return out
        if "fact_commodity_futures_daily" in tables:
            row = fetchone(
                "fact_commodity_futures_daily",
                "select max(try_cast(trade_date as date)) from fact_commodity_futures_daily"
            )
            if row and row[0] is not None:
                out["fact_commodity_futures_daily"] = row[0].isoformat()
        if "fact_cffex_member_rank_daily" in tables:
            row = fetchone(
                "fact_cffex_member_rank_daily",
                "select max(try_cast(trade_date as date)) from fact_cffex_member_rank_daily"
            )
            if row and row[0] is not None:
                out["fact_cffex_member_rank_daily"] = row[0].isoformat()
        if "fact_choice_macro_daily" in tables:
            series_sql = ", ".join(f"'{series_id}'" for series_id in TRACKED_CHOICE_SERIES_IDS)
            rows = fetchall(
                "fact_choice_macro_daily",
                f"""
                select series_id, max(try_cast(trade_date as date))
                from fact_choice_macro_daily
                where series_id in ({series_sql})
                group by series_id
                """,
            )
            for series_id, observation in rows:
                if observation is not None:
                    out[str(series_id)] = observation.isoformat()
        # NHCI may live only in commodity fact (mapped as NHCI.NH by system_sources).
        if out["NHCI.NH"] is None and "fact_commodity_futures_daily" in tables:
            row = fetchone(
                "fact_commodity_futures_daily.NHCI",
                """
                select max(try_cast(trade_date as date))
                from fact_commodity_futures_daily
                where upper(product_code) = 'NHCI'
                """,
            )
            if row and row[0] is not None:
                out["NHCI.NH"] = row[0].isoformat()
        if out["CA.COPPER"] is None and "fact_commodity_futures_daily" in tables:
            row = fetchone(
                "fact_commodity_futures_daily.CU",
                """
                select max(try_cast(trade_date as date))
                from fact_commodity_futures_daily
                where upper(product_code) = 'CU'
                """,
            )
            if row and row[0] is not None:
                out["CA.COPPER"] = row[0].isoformat()
    finally:
        try:
            conn.close()
        except Exception as exc:  # noqa: BLE001 - retain collected evidence
            _append_evidence_warning(warnings, "close", exc)
    return out


def _collect_latest_observation_dates(
    duckdb_path: str | Path,
) -> tuple[dict[str, str | None], list[str]]:
    warnings: list[str] = []
    try:
        latest_dates = _read_latest_observation_dates(duckdb_path, warnings=warnings)
    except Exception as exc:  # noqa: BLE001 - monkeypatch/vendor reader must not erase receipts
        warnings.append(f"latest_observation_dates: {_safe_error_reason(exc)}")
        return {}, warnings
    return latest_dates, warnings


def refresh_macro_toolkit_freshness(
    *,
    dry_run: bool = False,
    today: date | None = None,
    duckdb_path: str | Path | None = None,
    commodity_lookback_days: int = DEFAULT_COMMODITY_LOOKBACK_DAYS,
    public_headline_lookback_days: int = DEFAULT_PUBLIC_HEADLINE_LOOKBACK_DAYS,
    commodity_products: Sequence[str] | None = None,
    include_cffex: bool = True,
) -> dict[str, object]:
    """Run the freshness pipeline synchronously (or plan it in dry-run)."""
    settings = get_settings()
    report_date = today or date.today()
    resolved_duckdb = str(Path(duckdb_path or settings.duckdb_path))
    products = (
        tuple(commodity_products)
        if commodity_products is not None
        else DEFAULT_COMMODITY_PRODUCTS
    )
    start_date = (report_date - timedelta(days=max(commodity_lookback_days, 1))).isoformat()
    end_date = report_date.isoformat()
    run_id = _new_run_id()
    steps: list[dict[str, object]] = []

    if dry_run:
        commodity_started_at = datetime.now(UTC)
        commodity_started_clock = time.monotonic()
        try:
            commodity_plan = run_commodity_daily_ingest(
                start_date=start_date,
                end_date=end_date,
                duckdb_path=resolved_duckdb,
                products=products,
                dry_run=True,
            )
        except Exception as exc:  # noqa: BLE001 - keep the full dry-run plan visible
            steps.append(
                _step_receipt(
                    step="commodity_daily_ingest",
                    status="failed",
                    started_at=commodity_started_at,
                    started_clock=commodity_started_clock,
                    attempt_count=1,
                    reason=(
                        "commodity_daily_ingest dry-run failed: "
                        f"{_safe_error_reason(exc)}"
                    ),
                )
            )
        else:
            steps.append(
                _step_receipt(
                    step="commodity_daily_ingest",
                    status="dry_run",
                    started_at=commodity_started_at,
                    started_clock=commodity_started_clock,
                    attempt_count=1,
                    result=commodity_plan,
                )
            )

        headlines_started_at = datetime.now(UTC)
        headlines_started_clock = time.monotonic()
        steps.append(
            _step_receipt(
                step="public_cross_asset_headlines",
                status="dry_run",
                started_at=headlines_started_at,
                started_clock=headlines_started_clock,
                attempt_count=0,
                result={
                    "lookback_days": public_headline_lookback_days,
                    "report_date": end_date,
                },
            )
        )
        policy_rate_started_at = datetime.now(UTC)
        policy_rate_started_clock = time.monotonic()
        steps.append(
            _step_receipt(
                step="choice_policy_rate_7d",
                status="dry_run",
                started_at=policy_rate_started_at,
                started_clock=policy_rate_started_clock,
                attempt_count=0,
                result={
                    "lookback_days": DEFAULT_POLICY_RATE_LOOKBACK_DAYS,
                    "report_date": end_date,
                    "series_id": POLICY_RATE_SERIES_ID,
                },
            )
        )
        ncd_started_at = datetime.now(UTC)
        ncd_started_clock = time.monotonic()
        steps.append(
            _step_receipt(
                step="tushare_ncd_shibor",
                status="dry_run",
                started_at=ncd_started_at,
                started_clock=ncd_started_clock,
                attempt_count=0,
                result={
                    "lookback_days": NCD_SHIBOR_LOOKBACK_DAYS,
                    "report_date": end_date,
                },
            )
        )
        cffex_started_at = datetime.now(UTC)
        cffex_started_clock = time.monotonic()
        if include_cffex:
            steps.append(
                _step_receipt(
                    step="cffex_member_rank",
                    status="dry_run",
                    started_at=cffex_started_at,
                    started_clock=cffex_started_clock,
                    attempt_count=0,
                    trade_date=_latest_weekday_on_or_before(report_date).isoformat(),
                    result={"fallback_workdays": CFFEX_FALLBACK_WORKDAYS},
                )
            )
        else:
            steps.append(
                _step_receipt(
                    step="cffex_member_rank",
                    status="skipped",
                    started_at=cffex_started_at,
                    started_clock=cffex_started_clock,
                    attempt_count=0,
                    reason="CFFEX refresh disabled",
                )
            )
        latest_dates, evidence_warnings = _collect_latest_observation_dates(resolved_duckdb)
        dry_run_status = (
            "failed" if any(step["status"] == "failed" for step in steps) else "dry_run"
        )
        return {
            "status": dry_run_status,
            "run_id": run_id,
            "source_version": SOURCE_VERSION,
            "report_date": end_date,
            "duckdb_path": resolved_duckdb,
            "steps": steps,
            "latest_observation_dates": latest_dates,
            "warnings": evidence_warnings,
        }

    steps.append(
        _run_required_step(
            step="commodity_daily_ingest",
            fn=lambda: run_commodity_daily_ingest(
                start_date=start_date,
                end_date=end_date,
                duckdb_path=resolved_duckdb,
                products=products,
                dry_run=False,
            ),
            result_fields=(
                "status",
                "row_count",
                "product_count",
                "start_date",
                "end_date",
            ),
        ),
    )

    steps.append(
        _run_required_step(
            step="public_cross_asset_headlines",
            fn=lambda: refresh_public_cross_asset_headlines(
                duckdb_path=resolved_duckdb,
                lookback_days=public_headline_lookback_days,
                report_date=end_date,
            ),
            result_fields=(
                "status",
                "row_count",
                "series_count",
                "run_id",
                "warnings",
                "warning_count",
                "failed_sources",
                "source_failures",
                "covered_required_series",
            ),
        ),
    )

    steps.append(
        _run_required_step(
            step="choice_policy_rate_7d",
            fn=lambda: _refresh_choice_policy_rate_7d(
                duckdb_path=resolved_duckdb,
                report_date=end_date,
            ),
            result_fields=(
                "status",
                "row_count",
                "series_id",
                "run_id",
                "start_date",
                "end_date",
                "errors",
            ),
        ),
    )

    steps.append(
        _run_required_step(
            step="tushare_ncd_shibor",
            fn=lambda: refresh_tushare_ncd_shibor_proxy(
                duckdb_path=resolved_duckdb,
                report_date=end_date,
            ),
            result_fields=("status", "row_count", "series_count", "run_id"),
        ),
    )

    if include_cffex:
        cffex_step = _run_cffex_step(
            report_date=report_date,
            duckdb_path=resolved_duckdb,
        )
    else:
        cffex_started_at = datetime.now(UTC)
        cffex_started_clock = time.monotonic()
        cffex_step = _step_receipt(
            step="cffex_member_rank",
            status="skipped",
            started_at=cffex_started_at,
            started_clock=cffex_started_clock,
            attempt_count=0,
            reason="CFFEX refresh disabled",
        )
    steps.append(cffex_step)

    required_failed = _has_required_step_failure(steps)
    required_degraded = _has_required_step_degradation(steps)
    if required_failed:
        status = "failed"
    elif cffex_step["status"] == "failed":
        status = "failed"
    elif required_degraded:
        status = "degraded"
    elif cffex_step["status"] in {"success", "skipped"}:
        status = "success"
    else:
        status = "degraded"
    latest_dates, evidence_warnings = _collect_latest_observation_dates(resolved_duckdb)
    return {
        "status": status,
        "run_id": run_id,
        "source_version": SOURCE_VERSION,
        "report_date": end_date,
        "duckdb_path": resolved_duckdb,
        "steps": steps,
        "latest_observation_dates": latest_dates,
        "warnings": evidence_warnings,
    }


refresh_macro_toolkit_freshness_actor = register_actor_once(
    "refresh_macro_toolkit_freshness",
    refresh_macro_toolkit_freshness,
    time_limit_ms=3_600_000,
)
