from __future__ import annotations

import contextlib
import hashlib
import io
import json
import logging
import os
import subprocess
import sys
import threading
import uuid
from _thread import LockType
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Literal, cast

import duckdb
import pandas as pd
from backend.app.core_finance.macro.equity_strategies import REQUIRED_FACTOR_INPUTS
from backend.app.core_finance.macro.toolkit.paths import OUTPUT_DIR
from backend.app.core_finance.macro.toolkit.runner import (
    PROJECT_ROOT,
    TOOLKIT_ROOT,
    get_toolkit_script,
    iter_toolkit_scripts,
    run_toolkit_script,
)
from backend.app.core_finance.macro.toolkit.system_sources import (
    load_series_by_aliases,
    normalize_macro_alias,
    normalize_macro_source_names,
)
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.repositories.cffex_member_rank_repo import (
    normalize_cffex_contract,
    normalize_cffex_sources,
)
from backend.app.repositories.choice_stock_units import (
    amount_rmb_sql,
    scale_unknown_sql,
)
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    GovernanceRepository,
)
from backend.app.security.auth_context import AuthContext

# ---------------------------------------------------------------------------
# 门面 re-export：以下名字的实现已按内聚拆分到同级 macro_toolkit_service_* 子模块，
# 逐名显式重新导入，保持本模块的公开 / monkeypatch 命名空间完全不变。
# ---------------------------------------------------------------------------
from backend.app.services.macro_toolkit_service_commodity_inputs import (
    DEFAULT_MACRO_COMMODITY_REFRESH_PRODUCTS,
    _commodity_futures_coverage,
    _commodity_futures_missing_nanhua,
    _commodity_futures_nanhua_input,
    _normalize_commodity_trade_date,
)
from backend.app.services.macro_toolkit_service_model_chain import (
    _MODEL_CHAIN_DAILY_CHAIN_RECEIPT_NAME,
    _MODEL_CHAIN_DCC_META_COLUMNS,
    _MODEL_CHAIN_DETAIL_HEADLINE,
    _MODEL_CHAIN_FINAL_SIGNAL_ARTIFACT,
    _MODEL_CHAIN_FRESHNESS_RECEIPT_NAME,
    _MODEL_CHAIN_MISSING_HEADLINE,
    _MODEL_CHAIN_MONITOR_LOG_TAIL_ROWS,
    _MODEL_CHAIN_NA_TEXT,
    _MODEL_CHAIN_STEP_DEFINITIONS,
    _MODEL_CHAIN_TREND_MAX_POINTS,
    _MODEL_CHAIN_TREND_SIGNAL_SYMBOLS,
    _load_model_chain_frame,
    _model_chain_as_of,
    _model_chain_backtest_headline,
    _model_chain_cell_text,
    _model_chain_contains,
    _model_chain_crisis_headline,
    _model_chain_crisis_trend_series,
    _model_chain_cta_headline,
    _model_chain_daily_chain_summary,
    _model_chain_dcc_headline,
    _model_chain_dcc_trend_series,
    _model_chain_final_signal_as_of_date,
    _model_chain_final_signal_headline,
    _model_chain_final_signal_trend_series,
    _model_chain_freshness_summary,
    _model_chain_garch_headline,
    _model_chain_latest_date_text,
    _model_chain_max_row,
    _model_chain_merrill_headline,
    _model_chain_merrill_trend_series,
    _model_chain_model_payload,
    _model_chain_monitor_alerts_headline,
    _model_chain_performance_headline,
    _model_chain_rebalance_headline,
    _model_chain_receipt_summary,
    _model_chain_regime_headline,
    _model_chain_risk_monitor_headline,
    _model_chain_risk_parity_headline,
    _model_chain_scheduler_payload,
    _model_chain_signal_trend_value,
    _model_chain_table,
    _model_chain_trend_column,
    _model_chain_trend_payload,
    _model_chain_trend_points,
    build_model_chain_results,
)
from backend.app.services.macro_toolkit_service_readiness import (
    _MACRO_MODEL_DEFINITIONS,
    _MONTHLY_CADENCE_ARTIFACTS,
    _is_generation_evidence_artifact,
    _is_history_artifact,
    _is_monthly_cadence_artifact,
    _macro_artifact_receipt,
    _macro_generation_freshness,
    _macro_monthly_output_freshness,
    _macro_output_content_dates,
    _macro_output_freshness,
    _macro_output_health,
    _macro_output_health_status,
    _macro_output_modified_date,
    _macro_readiness_date_basis,
    _macro_readiness_degraded_reason,
    _macro_readiness_evidence_level,
    _macro_run_blocker,
    _macro_run_data_asof,
    _macro_run_degraded_reason,
    _macro_run_manifest,
)
from backend.app.services.macro_toolkit_service_support import (
    MACRO_TOOLKIT_FORMAL_USE_ALLOWED,
    MACRO_TOOLKIT_MODEL_READINESS_SURFACE,
    MACRO_TOOLKIT_OBSERVATION_ONLY,
    MACRO_TOOLKIT_OUTPUT_DATE_COLUMNS,
    MACRO_TOOLKIT_RUN_CHAIN_ENDPOINT,
    ThemeOverlayRefreshMode,
    _WRITE_REFRESH_PUBLIC_FAILURE_CATEGORIES,
    _WRITE_REFRESH_PUBLIC_STATUSES,
    _WRITE_REFRESH_RETRY_PENDING_AFTER,
    _choice_stock_base_table_status,
    _choice_stock_daily_observation_status_with_freshness,
    _choice_stock_factor_snapshot_status_with_freshness,
    _choice_stock_table_freshness,
    _choice_stock_table_status,
    _choice_stock_theme_overlay_source_version,
    _coerce_frame_date,
    _float_or_none,
    _int_or_zero,
    _latest_result_field,
    _normalize_idempotency_key,
    _normalize_theme_overlay_mode,
    _normalize_write_refresh_public_record,
    _optional_int,
    _optional_text,
    _public_text_list,
    _public_text_mapping,
    _result_row_count,
    _tail_text,
    _unique_texts,
    _write_refresh_quality_flag,
    _write_refresh_record_blocks_dispatch,
    _write_refresh_record_is_within_retry_window,
)


def materialize_choice_stock_factor_snapshot(*args: object, **kwargs: object) -> object:
    from backend.app.tasks.choice_stock_materialize import (
        materialize_choice_stock_factor_snapshot as _fn,
    )

    return _fn(*args, **kwargs)


def materialize_choice_stock_inputs(*args: object, **kwargs: object) -> object:
    from backend.app.tasks.choice_stock_materialize import (
        materialize_choice_stock_inputs as _fn,
    )

    return _fn(*args, **kwargs)


def append_choice_stock_refresh_completion(*args: object, **kwargs: object) -> object:
    from backend.app.tasks.choice_stock_observation_manifest import (
        append_choice_stock_refresh_completion as _fn,
    )

    return _fn(*args, **kwargs)


def build_choice_stock_observation_manifest(*args: object, **kwargs: object) -> object:
    from backend.app.tasks.choice_stock_observation_manifest import (
        build_choice_stock_observation_manifest as _fn,
    )

    return _fn(*args, **kwargs)


def verify_choice_stock_daily_observation_landing(*args: object, **kwargs: object) -> object:
    from backend.app.tasks.choice_stock_observation_manifest import (
        verify_choice_stock_daily_observation_landing as _fn,
    )

    return _fn(*args, **kwargs)


def refresh_choice_stock_theme_overlay(*args: object, **kwargs: object) -> object:
    from backend.app.tasks.choice_stock_theme_overlay_refresh import (
        refresh_choice_stock_theme_overlay as _fn,
    )

    return _fn(*args, **kwargs)


def run_commodity_daily_ingest(*args: object, **kwargs: object) -> object:
    from backend.app.tasks.commodity_daily_ingest import run_commodity_daily_ingest as _fn

    return _fn(*args, **kwargs)


class _RunCommodityDailyIngestTaskProxy:
    def send(self, **kwargs: object) -> object:
        from backend.app.tasks.commodity_daily_ingest import (
            run_commodity_daily_ingest_task as _actor,
        )

        return _actor.send(**kwargs)

    def __getattr__(self, name: str) -> object:
        from backend.app.tasks.commodity_daily_ingest import (
            run_commodity_daily_ingest_task as _actor,
        )

        return getattr(_actor, name)


run_commodity_daily_ingest_task = _RunCommodityDailyIngestTaskProxy()

class _RunCffexMemberRankRefreshTaskProxy:
    def send(self, **kwargs: object) -> object:
        from backend.app.tasks.macro_toolkit_write_refresh import (
            run_cffex_member_rank_refresh_task as _actor,
        )

        return _actor.send(**kwargs)

    def __getattr__(self, name: str) -> object:
        from backend.app.tasks.macro_toolkit_write_refresh import (
            run_cffex_member_rank_refresh_task as _actor,
        )

        return getattr(_actor, name)


run_cffex_member_rank_refresh_task = _RunCffexMemberRankRefreshTaskProxy()

class _RunMacroSourceBackfillRefreshTaskProxy:
    def send(self, **kwargs: object) -> object:
        from backend.app.tasks.macro_toolkit_write_refresh import (
            run_macro_source_backfill_refresh_task as _actor,
        )

        return _actor.send(**kwargs)

    def __getattr__(self, name: str) -> object:
        from backend.app.tasks.macro_toolkit_write_refresh import (
            run_macro_source_backfill_refresh_task as _actor,
        )

        return getattr(_actor, name)


run_macro_source_backfill_refresh_task = _RunMacroSourceBackfillRefreshTaskProxy()


class _RunChoiceStockRefreshTaskProxy:
    def send(self, **kwargs: object) -> object:
        from backend.app.tasks.choice_stock_refresh import (
            run_choice_stock_refresh_task as _actor,
        )

        return _actor.send(**kwargs)

    def __getattr__(self, name: str) -> object:
        from backend.app.tasks.choice_stock_refresh import (
            run_choice_stock_refresh_task as _actor,
        )

        return getattr(_actor, name)


run_choice_stock_refresh_task = _RunChoiceStockRefreshTaskProxy()

logger = logging.getLogger(__name__)

CHOICE_STOCK_REFRESH_JOB_NAME = "choice_stock_refresh"
CHOICE_STOCK_REFRESH_CACHE_KEY = "choice_stock.history_and_factor_snapshot"
CHOICE_STOCK_REFRESH_CACHE_VERSION = "choice_stock_refresh_v1"
CHOICE_STOCK_REFRESH_LOCK = "lock:choice_stock_refresh"
CHOICE_STOCK_REFRESH_RULE_VERSION = "rv_choice_stock_materialization_front_layer_v1"
CHOICE_STOCK_THEME_OVERLAY_VENDOR_VERSION = "vv_tushare_ths_current_overlay_v1"
_CHOICE_STOCK_REFRESH_IN_FLIGHT_STATUSES = {"queued", "running", "retrying"}
COMMODITY_FUTURES_REFRESH_JOB_NAME = "commodity_futures_daily_ingest"
COMMODITY_FUTURES_REFRESH_CACHE_KEY = "commodity_futures.daily"
COMMODITY_FUTURES_REFRESH_CACHE_VERSION = "commodity_futures_daily_v1"
COMMODITY_FUTURES_REFRESH_RULE_VERSION = "rv_commodity_daily_v1"
CFFEX_MEMBER_RANK_REFRESH_JOB_NAME = "cffex_member_rank_refresh"
CFFEX_MEMBER_RANK_REFRESH_CACHE_KEY = "macro_toolkit.cffex_member_rank"
CFFEX_MEMBER_RANK_REFRESH_CACHE_VERSION = "cffex_member_rank_refresh_v1"
CFFEX_MEMBER_RANK_REFRESH_RULE_VERSION = "rv_cffex_member_rank_async_v1"
_CFFEX_REFRESH_IN_FLIGHT_STATUSES = {"queued", "running", "retrying"}
MACRO_SOURCE_BACKFILL_JOB_NAME = "macro_source_backfill_refresh"
MACRO_SOURCE_BACKFILL_CACHE_KEY = "macro_toolkit.source_backfill"
MACRO_SOURCE_BACKFILL_CACHE_VERSION = "macro_source_backfill_v1"
MACRO_SOURCE_BACKFILL_RULE_VERSION = "rv_macro_source_backfill_async_v1"
_MACRO_SOURCE_REFRESH_IN_FLIGHT_STATUSES = {"queued", "running", "retrying"}
_WRITE_REFRESH_MAX_RETRIES = 3
EQUITY_PRICE_LOOKBACK_DAYS = 260
EQUITY_PRICE_MIN_OBSERVATIONS = 80
EQUITY_PRICE_MAX_STOCKS = 500
A_SHARE_RISK_LOOKBACK_DAYS = 35
A_SHARE_RISK_MAX_STOCKS = 8000
_CANONICAL_ISO_DATE_COLUMNS = {
    ("choice_stock_daily_observation", "trade_date"),
    ("fact_formal_risk_tensor_daily", "report_date"),
    ("fact_formal_yield_curve_daily", "trade_date"),
    ("fact_formal_bond_analytics_daily", "report_date"),
}
_DateColumnCacheKey = tuple[str, int, int, str, str]
_CANONICAL_ISO_DATE_CACHE: dict[_DateColumnCacheKey, bool] = {}
_CANONICAL_ISO_DATE_CACHE_LOCK = threading.Lock()
_CANONICAL_ISO_DATE_PROBE_LOCKS: dict[_DateColumnCacheKey, LockType] = {}
_CANONICAL_ISO_DATE_CACHE_MAX_ENTRIES = 64
MACRO_TOOLKIT_CHAIN_LOCK = LockDefinition(key="lock:macro_toolkit:script-chain", ttl_seconds=900)
MACRO_TOOLKIT_SCRIPT_ARTIFACT_SURFACE = "/macro-toolkit#macro-toolkit-script-artifact-detail"

_CURVE_TYPE_TO_ID = {
    "treasury": "CN_GOVT",
    "cdb": "CN_CDB",
    "aaa_credit": "CN_CREDIT_AAA",
    "aa_plus_credit": "CN_CREDIT_AA_PLUS",
    "aa_credit": "CN_CREDIT_AA",
}

_CURVE_ALIAS_POINTS = (
    ("S0059743", "CN_GOVT", "1Y"),
    ("S0059746", "CN_GOVT", "3Y"),
    ("S0059747", "CN_GOVT", "5Y"),
    ("S0059748", "CN_GOVT", "7Y"),
    ("S0059749", "CN_GOVT", "10Y"),
    ("S0059752", "CN_GOVT", "30Y"),
    ("S0059650", "CN_CREDIT_AAA", "1Y"),
    ("S0059651", "CN_CREDIT_AAA", "3Y"),
    ("S0059652", "CN_CREDIT_AAA", "5Y"),
    ("S0059653", "CN_CREDIT_AA_PLUS", "1Y"),
    ("S0059654", "CN_CREDIT_AA_PLUS", "3Y"),
    ("S0059655", "CN_CREDIT_AA_PLUS", "5Y"),
    ("S0059656", "CN_CREDIT_AA", "1Y"),
    ("S0059657", "CN_CREDIT_AA", "3Y"),
    ("S0059760", "CN_CREDIT_AA", "5Y"),
    ("DR007.IB", "CN_DR", "7D"),
    ("M0041653", "CN_RRP", "7D"),
    ("M0041813", "CN_NCD", "3M"),
    ("CA.US_GOV_10Y", "US_GOVT", "10Y"),
)


@dataclass(frozen=True)
class MacroToolkitActionResult:
    payload: dict[str, object]
    quality_flag: str = "ok"
    fallback_mode: str = "none"
    as_of_date: str | None = None


class MacroToolkitConflictError(RuntimeError):
    pass


class MacroToolkitQueueError(RuntimeError):
    pass


def run_macro_toolkit_script(
    *,
    name: str,
    argv: list[str],
    timeout_seconds: int,
    output_dir: str | Path = OUTPUT_DIR,
) -> dict[str, object]:
    script = get_toolkit_script(name)
    resolved_output_dir = Path(output_dir).resolve()
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    existing_python_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(TOOLKIT_ROOT), str(PROJECT_ROOT), existing_python_path) if part
    )
    env["MOSS_MACRO_TOOLKIT_OUTPUT_DIR"] = str(resolved_output_dir)
    try:
        completed = subprocess.run(
            [sys.executable, str(script.path), *argv],
            cwd=str(TOOLKIT_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "timeout",
            "script": _script_payload(script.name, script.filename, script.group, script.default_data_sources, script.optional_dependencies, script.notes, script.path),
            "exit_code": None,
            "stdout": _tail_text(exc.stdout),
            "stderr": _tail_text(exc.stderr),
            "output_files": output_files(output_dir),
            "message": f"script exceeded {timeout_seconds}s timeout",
        }
    except OSError as exc:
        stdout_text, stderr_text, exit_code = _run_toolkit_script_inline(
            script.name,
            argv,
            output_dir=resolved_output_dir,
        )
        return {
            "status": "completed" if exit_code == 0 else "failed",
            "script": _script_payload(script.name, script.filename, script.group, script.default_data_sources, script.optional_dependencies, script.notes, script.path),
            "exit_code": exit_code,
            "stdout": _tail_text(stdout_text),
            "stderr": _tail_text(f"{stderr_text}\nsubprocess fallback: {exc}".strip()),
            "output_files": output_files(output_dir),
        }

    return {
        "status": "completed" if completed.returncode == 0 else "failed",
        "script": _script_payload(script.name, script.filename, script.group, script.default_data_sources, script.optional_dependencies, script.notes, script.path),
        "exit_code": completed.returncode,
        "stdout": _tail_text(completed.stdout),
        "stderr": _tail_text(completed.stderr),
        "output_files": output_files(output_dir),
    }


def output_files(output_dir: str | Path = OUTPUT_DIR) -> list[dict[str, object]]:
    directory = Path(output_dir)
    if not directory.exists():
        return []
    files: list[dict[str, object]] = []
    for path in sorted(directory.glob("*")):
        if not path.is_file():
            continue
        stat = path.stat()
        files.append(
            {
                "name": path.name,
                "path": str(path),
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
            }
        )
    return files


def macro_model_readiness(
    *,
    output_dir: str | Path = OUTPUT_DIR,
    reference_date: str | None = None,
) -> dict[str, object]:
    files = output_files(output_dir)
    files_by_name = {str(item["name"]): item for item in files}
    model_readiness = [
        _macro_model_readiness_payload(model, files_by_name=files_by_name, reference_date=reference_date)
        for model in _MACRO_MODEL_DEFINITIONS
    ]
    counts: dict[str, int] = {}
    for item in model_readiness:
        status = str(item["readiness"])
        counts[status] = counts.get(status, 0) + 1
    degraded_count = sum(
        counts.get(status, 0)
        for status in ("missing_output", "stale", "registered_only", "degraded", "unknown")
    )
    return {
        "model_readiness": model_readiness,
        "readiness_summary": {
            "total_count": len(model_readiness),
            "artifact_backed_count": counts.get("artifact_backed", 0),
            "degraded_count": degraded_count,
            "status_counts": counts,
            "observation_only": MACRO_TOOLKIT_OBSERVATION_ONLY,
            "formal_use_allowed": MACRO_TOOLKIT_FORMAL_USE_ALLOWED,
        },
    }


def run_macro_toolkit_chain(
    *,
    dry_run: bool,
    timeout_seconds: int,
    output_dir: str | Path = OUTPUT_DIR,
    reference_date: str | None = None,
    governance_path: str | Path | None = None,
    authorize_script: Callable[[str], None] | None = None,
) -> dict[str, object]:
    if not dry_run and authorize_script is not None:
        for step in _macro_run_manifest():
            authorize_script(str(step["script_name"]))

    if dry_run or governance_path is None:
        return _run_macro_toolkit_chain_unlocked(
            dry_run=dry_run,
            timeout_seconds=timeout_seconds,
            output_dir=output_dir,
            reference_date=reference_date,
        )

    try:
        with acquire_lock(MACRO_TOOLKIT_CHAIN_LOCK, base_dir=governance_path, timeout_seconds=0.1):
            return _run_macro_toolkit_chain_unlocked(
                dry_run=dry_run,
                timeout_seconds=timeout_seconds,
                output_dir=output_dir,
                reference_date=reference_date,
            )
    except TimeoutError as exc:
        raise MacroToolkitConflictError("Macro toolkit script chain is already in progress.") from exc


def _run_macro_toolkit_chain_unlocked(
    *,
    dry_run: bool,
    timeout_seconds: int,
    output_dir: str | Path,
    reference_date: str | None,
) -> dict[str, object]:
    started_at = datetime.now(UTC).isoformat()
    chain_id = f"macro_toolkit_chain:{uuid.uuid4().hex[:12]}"
    readiness_before = macro_model_readiness(output_dir=output_dir, reference_date=reference_date)
    receipts: list[dict[str, object]] = []
    if dry_run:
        receipts = [_dry_run_receipt(step, chain_id=chain_id, output_dir=output_dir) for step in _macro_run_manifest()]
        status = "dry_run"
    else:
        status = "completed"
        for step in _macro_run_manifest():
            result = run_macro_toolkit_script(
                name=str(step["script_name"]),
                argv=[],
                timeout_seconds=timeout_seconds,
                output_dir=output_dir,
            )
            receipt = _run_receipt(step, result, chain_id=chain_id, output_dir=output_dir)
            receipts.append(receipt)
            if str(receipt["status"]) != "completed":
                status = str(receipt["status"])
                break
    readiness_after = macro_model_readiness(output_dir=output_dir, reference_date=reference_date)
    if status == "completed" and int(readiness_after["readiness_summary"]["degraded_count"]) > 0:
        status = "degraded"
    return {
        "chain_id": chain_id,
        "status": status,
        "dry_run": dry_run,
        "started_at": started_at,
        "finished_at": datetime.now(UTC).isoformat(),
        "timeout_seconds": timeout_seconds,
        "manifest": _macro_run_manifest(),
        "receipts": receipts,
        "readiness_before": readiness_before["readiness_summary"],
        "readiness_after": readiness_after["readiness_summary"],
        "model_readiness": readiness_after["model_readiness"],
        "observation_only": MACRO_TOOLKIT_OBSERVATION_ONLY,
        "formal_use_allowed": MACRO_TOOLKIT_FORMAL_USE_ALLOWED,
    }


def queue_macro_source_backfill(
    *,
    duckdb_path: str,
    governance_path: str,
    alias: str,
    series_id: str,
    series_name: str,
    backfill_mode: str,
    start_date: str,
    end_date: str,
    sources: tuple[str, ...],
    idempotency_key: str | None = None,
) -> MacroToolkitActionResult:
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError as exc:
        raise ValueError("start_date and end_date must be ISO dates (YYYY-MM-DD).") from exc
    if end < start:
        raise ValueError("end_date must be on or after start_date.")
    normalized_alias = normalize_macro_alias(alias)
    normalized_sources = normalize_macro_source_names(sources)
    if not normalized_sources:
        raise ValueError("sources must contain at least one value.")
    normalized_mode = str(backfill_mode or "").strip()
    if normalized_mode not in {"macro_series", "crisis_score_inputs"}:
        raise ValueError(f"Unsupported macro source backfill mode: {backfill_mode}")
    normalized_idempotency_key = _normalize_idempotency_key(idempotency_key)
    request_fingerprint = hashlib.sha256(
        repr(
            (
                str(Path(duckdb_path).resolve()),
                normalized_alias,
                str(series_id).strip(),
                str(series_name).strip(),
                normalized_mode,
                start_date,
                end_date,
                normalized_sources,
            )
        ).encode("utf-8")
    ).hexdigest()
    trigger_lock = LockDefinition(
        key=f"lock:{MACRO_SOURCE_BACKFILL_JOB_NAME}:trigger:{request_fingerprint[:12]}",
        ttl_seconds=30,
    )
    repo = GovernanceRepository(base_dir=governance_path)
    try:
        with acquire_lock(trigger_lock, base_dir=governance_path, timeout_seconds=0.1):
            records = _macro_source_backfill_refresh_records(repo)
            if normalized_idempotency_key is not None:
                for record in reversed(records):
                    if str(record.get("request_fingerprint") or "") != request_fingerprint:
                        continue
                    if str(record.get("idempotency_key") or "").strip() == normalized_idempotency_key:
                        status = str(record.get("status") or "queued")
                        return MacroToolkitActionResult(
                            payload=_normalize_macro_source_backfill_refresh_record(
                                record,
                                idempotency_replay=True,
                            ),
                            quality_flag=_write_refresh_quality_flag(status),
                            fallback_mode="none",
                            as_of_date=end_date,
                        )

            latest_by_run_id: dict[str, dict[str, object]] = {}
            for record in records:
                if str(record.get("request_fingerprint") or "") == request_fingerprint:
                    latest_by_run_id[str(record.get("run_id") or "")] = record
            if any(
                _write_refresh_record_blocks_dispatch(
                    record,
                    in_flight_statuses=_MACRO_SOURCE_REFRESH_IN_FLIGHT_STATUSES,
                )
                for record in latest_by_run_id.values()
            ):
                raise MacroToolkitConflictError("Macro source backfill is already in progress.")

            queued_at = datetime.now(UTC).isoformat()
            run_id = f"{MACRO_SOURCE_BACKFILL_JOB_NAME}:{end_date}:{uuid.uuid4().hex[:12]}"
            queued_payload = {
                "run_id": run_id,
                "job_name": MACRO_SOURCE_BACKFILL_JOB_NAME,
                "status": "queued",
                "trigger_mode": "async",
                "cache_key": MACRO_SOURCE_BACKFILL_CACHE_KEY,
                "cache_version": MACRO_SOURCE_BACKFILL_CACHE_VERSION,
                "lock": trigger_lock.key,
                "source_version": "sv_pending",
                "vendor_version": "vv_pending",
                "rule_version": MACRO_SOURCE_BACKFILL_RULE_VERSION,
                "report_date": end_date,
                "alias": normalized_alias,
                "series_ids": [str(series_id).strip()],
                "series_names": [str(series_name).strip()],
                "backfill_mode": normalized_mode,
                "start_date": start_date,
                "end_date": end_date,
                "sources": list(normalized_sources),
                "duckdb_path": str(duckdb_path),
                "total_added": None,
                "total_fetched": None,
                "processed_count": None,
                "queued_at": queued_at,
                "request_fingerprint": request_fingerprint,
                "idempotency_key": normalized_idempotency_key,
            }
            repo.append(CACHE_BUILD_RUN_STREAM, queued_payload)
            try:
                run_macro_source_backfill_refresh_task.send(
                    duckdb_path=str(duckdb_path),
                    governance_dir=str(governance_path),
                    run_id=run_id,
                    alias=normalized_alias,
                    series_id=str(series_id).strip(),
                    series_name=str(series_name).strip(),
                    backfill_mode=normalized_mode,
                    start_date=start_date,
                    end_date=end_date,
                    sources=normalized_sources,
                    request_fingerprint=request_fingerprint,
                    idempotency_key=normalized_idempotency_key,
                )
            except Exception as exc:
                repo.append(
                    CACHE_BUILD_RUN_STREAM,
                    {
                        **queued_payload,
                        "status": "failed",
                        "trigger_mode": "terminal",
                        "finished_at": datetime.now(UTC).isoformat(),
                        "error_message": str(exc),
                        "failure_category": "queue_dispatch_failure",
                        "failure_reason": "queue_dispatch_failed",
                    },
                )
                raise MacroToolkitQueueError("Macro source backfill queue dispatch failed.") from exc
    except TimeoutError as exc:
        raise MacroToolkitConflictError("Macro source backfill is already in progress.") from exc

    return MacroToolkitActionResult(
        payload=_normalize_macro_source_backfill_refresh_record(
            queued_payload,
            idempotency_replay=False,
        ),
        quality_flag="warning",
        fallback_mode="none",
        as_of_date=end_date,
    )


def _macro_source_backfill_refresh_records(repo: GovernanceRepository) -> list[dict[str, object]]:
    return [
        record
        for record in repo.read_all(CACHE_BUILD_RUN_STREAM)
        if str(record.get("job_name") or "") == MACRO_SOURCE_BACKFILL_JOB_NAME
        and str(record.get("cache_key") or "") == MACRO_SOURCE_BACKFILL_CACHE_KEY
    ]


def macro_source_backfill_refresh_status(
    governance_path: str | Path,
    *,
    run_id: str,
) -> dict[str, object]:
    run_id_text = str(run_id or "").strip()
    if not run_id_text:
        raise ValueError("Macro source backfill refresh run_id is required.")
    records = _macro_source_backfill_refresh_records(
        GovernanceRepository(base_dir=governance_path)
    )
    latest = next(
        (
            record
            for record in reversed(records)
            if str(record.get("run_id") or "") == run_id_text
        ),
        None,
    )
    if latest is None:
        raise ValueError(
            f"Macro source backfill refresh run not found: {run_id_text}"
        )
    return _normalize_macro_source_backfill_refresh_record(latest)


def refresh_cffex_member_rank(
    *,
    duckdb_path: str | Path,
    governance_path: str | Path,
    trade_date: str | None,
    contracts: tuple[str, ...],
    sources: tuple[str, ...],
    idempotency_key: str | None = None,
) -> MacroToolkitActionResult:
    normalized_idempotency_key = _normalize_idempotency_key(idempotency_key)
    normalized_contracts = tuple(
        dict.fromkeys(
            normalize_cffex_contract(item) for item in contracts if str(item).strip()
        )
    )
    normalized_sources = normalize_cffex_sources(sources)
    if not normalized_contracts or not normalized_sources:
        raise ValueError("contracts and sources must contain at least one value.")
    normalized_trade_date = str(trade_date or "").strip() or None
    if normalized_trade_date is not None:
        try:
            date.fromisoformat(normalized_trade_date)
        except ValueError as exc:
            raise ValueError("trade_date must be an ISO date (YYYY-MM-DD).") from exc
    request_fingerprint = hashlib.sha256(
        repr(
            (
                str(Path(duckdb_path).resolve()),
                normalized_trade_date,
                normalized_contracts,
                normalized_sources,
            )
        ).encode("utf-8")
    ).hexdigest()
    trigger_lock = LockDefinition(
        key=f"lock:{CFFEX_MEMBER_RANK_REFRESH_JOB_NAME}:trigger:{request_fingerprint[:12]}",
        ttl_seconds=30,
    )
    repo = GovernanceRepository(base_dir=governance_path)
    try:
        with acquire_lock(trigger_lock, base_dir=governance_path, timeout_seconds=0.1):
            records = _cffex_member_rank_refresh_records(repo)
            if normalized_idempotency_key is not None:
                for record in reversed(records):
                    if str(record.get("request_fingerprint") or "") != request_fingerprint:
                        continue
                    if str(record.get("idempotency_key") or "").strip() == normalized_idempotency_key:
                        status = str(record.get("status") or "queued")
                        return MacroToolkitActionResult(
                            payload=_normalize_cffex_member_rank_refresh_record(
                                record,
                                idempotency_replay=True,
                            ),
                            quality_flag=_write_refresh_quality_flag(status),
                            fallback_mode="none",
                            as_of_date=normalized_trade_date,
                        )

            latest_by_run_id: dict[str, dict[str, object]] = {}
            for record in records:
                if str(record.get("request_fingerprint") or "") == request_fingerprint:
                    latest_by_run_id[str(record.get("run_id") or "")] = record
            if any(
                _write_refresh_record_blocks_dispatch(
                    record,
                    in_flight_statuses=_CFFEX_REFRESH_IN_FLIGHT_STATUSES,
                )
                for record in latest_by_run_id.values()
            ):
                raise MacroToolkitConflictError("CFFEX member-rank refresh is already in progress.")

            queued_at = datetime.now(UTC).isoformat()
            run_id = f"{CFFEX_MEMBER_RANK_REFRESH_JOB_NAME}:{normalized_trade_date or 'latest'}:{uuid.uuid4().hex[:12]}"
            queued_payload = {
                "run_id": run_id,
                "job_name": CFFEX_MEMBER_RANK_REFRESH_JOB_NAME,
                "status": "queued",
                "trigger_mode": "async",
                "cache_key": CFFEX_MEMBER_RANK_REFRESH_CACHE_KEY,
                "cache_version": CFFEX_MEMBER_RANK_REFRESH_CACHE_VERSION,
                "lock": trigger_lock.key,
                "source_version": "sv_pending",
                "vendor_version": "vv_pending",
                "rule_version": CFFEX_MEMBER_RANK_REFRESH_RULE_VERSION,
                "report_date": normalized_trade_date,
                "trade_date": normalized_trade_date,
                "contracts": list(normalized_contracts),
                "sources": list(normalized_sources),
                "duckdb_path": str(duckdb_path),
                "row_count": None,
                "queued_at": queued_at,
                "request_fingerprint": request_fingerprint,
                "idempotency_key": normalized_idempotency_key,
            }
            repo.append(CACHE_BUILD_RUN_STREAM, queued_payload)
            try:
                run_cffex_member_rank_refresh_task.send(
                    duckdb_path=str(duckdb_path),
                    governance_dir=str(governance_path),
                    run_id=run_id,
                    trade_date=normalized_trade_date,
                    contracts=normalized_contracts,
                    sources=normalized_sources,
                    request_fingerprint=request_fingerprint,
                    idempotency_key=normalized_idempotency_key,
                )
            except Exception as exc:
                repo.append(
                    CACHE_BUILD_RUN_STREAM,
                    {
                        **queued_payload,
                        "status": "failed",
                        "trigger_mode": "terminal",
                        "finished_at": datetime.now(UTC).isoformat(),
                        "error_message": str(exc),
                        "failure_category": "queue_dispatch_failure",
                        "failure_reason": "queue_dispatch_failed",
                    },
                )
                raise MacroToolkitQueueError("CFFEX member-rank refresh queue dispatch failed.") from exc
    except TimeoutError as exc:
        raise MacroToolkitConflictError("CFFEX member-rank refresh is already in progress.") from exc

    return MacroToolkitActionResult(
        payload=_normalize_cffex_member_rank_refresh_record(
            queued_payload,
            idempotency_replay=False,
        ),
        quality_flag="warning",
        fallback_mode="none",
        as_of_date=normalized_trade_date,
    )


def _cffex_member_rank_refresh_records(repo: GovernanceRepository) -> list[dict[str, object]]:
    return [
        record
        for record in repo.read_all(CACHE_BUILD_RUN_STREAM)
        if str(record.get("job_name") or "") == CFFEX_MEMBER_RANK_REFRESH_JOB_NAME
        and str(record.get("cache_key") or "") == CFFEX_MEMBER_RANK_REFRESH_CACHE_KEY
    ]


def cffex_member_rank_refresh_status(
    governance_path: str | Path,
    *,
    run_id: str,
) -> dict[str, object]:
    run_id_text = str(run_id or "").strip()
    if not run_id_text:
        raise ValueError("CFFEX member-rank refresh run_id is required.")
    records = _cffex_member_rank_refresh_records(
        GovernanceRepository(base_dir=governance_path)
    )
    latest = next(
        (
            record
            for record in reversed(records)
            if str(record.get("run_id") or "") == run_id_text
        ),
        None,
    )
    if latest is None:
        raise ValueError(
            f"CFFEX member-rank refresh run not found: {run_id_text}"
        )
    return _normalize_cffex_member_rank_refresh_record(latest)


def _normalize_cffex_member_rank_refresh_record(
    record: dict[str, object],
    *,
    idempotency_replay: bool | None = None,
) -> dict[str, object]:
    normalized = _normalize_write_refresh_public_record(
        record,
        job_name=CFFEX_MEMBER_RANK_REFRESH_JOB_NAME,
        cache_key=CFFEX_MEMBER_RANK_REFRESH_CACHE_KEY,
        cache_version=CFFEX_MEMBER_RANK_REFRESH_CACHE_VERSION,
        rule_version=CFFEX_MEMBER_RANK_REFRESH_RULE_VERSION,
        idempotency_replay=idempotency_replay,
    )
    normalized.update(
        {
            "trade_date": _optional_text(
                record.get("trade_date") or record.get("report_date")
            ),
            "contracts": _public_text_list(record.get("contracts")),
            "sources": _public_text_list(record.get("sources")),
            "row_count": _optional_int(record.get("row_count")),
        }
    )
    return normalized


def _normalize_macro_source_backfill_refresh_record(
    record: dict[str, object],
    *,
    idempotency_replay: bool | None = None,
) -> dict[str, object]:
    normalized = _normalize_write_refresh_public_record(
        record,
        job_name=MACRO_SOURCE_BACKFILL_JOB_NAME,
        cache_key=MACRO_SOURCE_BACKFILL_CACHE_KEY,
        cache_version=MACRO_SOURCE_BACKFILL_CACHE_VERSION,
        rule_version=MACRO_SOURCE_BACKFILL_RULE_VERSION,
        idempotency_replay=idempotency_replay,
    )
    normalized.update(
        {
            "alias": _optional_text(record.get("alias")),
            "series_ids": _public_text_list(record.get("series_ids")),
            "series_names": _public_text_list(record.get("series_names")),
            "backfill_mode": _optional_text(record.get("backfill_mode")),
            "start_date": _optional_text(record.get("start_date")),
            "end_date": _optional_text(record.get("end_date")),
            "sources": _public_text_list(record.get("sources")),
            "total_added": _optional_int(record.get("total_added")),
            "total_fetched": _optional_int(record.get("total_fetched")),
            "processed_count": _optional_int(record.get("processed_count")),
            "source_by_series": _public_text_mapping(
                record.get("source_by_series")
            ),
            "vendor_versions": _public_text_mapping(record.get("vendor_versions")),
            # 失败明细（series/alias -> 原因）不得在 normalize 白名单中丢弃，
            # 否则 blocked/partial/failed 的 source 级原因对状态查询不可见。
            "errors": _public_text_mapping(record.get("errors")),
        }
    )
    return normalized


def refresh_commodity_futures(
    *,
    start_date: str,
    end_date: str,
    duckdb_path: str,
    products: tuple[str, ...],
    dry_run: bool,
    permission: dict[str, object],
) -> MacroToolkitActionResult:
    if dry_run:
        payload = run_commodity_daily_ingest(
            start_date=start_date,
            end_date=end_date,
            duckdb_path=duckdb_path,
            products=products,
            dry_run=True,
        )
        return MacroToolkitActionResult(
            payload={**payload, "permission": permission},
            quality_flag="ok" if str(payload.get("status")) == "dry_run" else "warning",
            fallback_mode="none",
            as_of_date=end_date,
        )

    run_id = f"{COMMODITY_FUTURES_REFRESH_JOB_NAME}:{end_date}:{uuid.uuid4().hex[:12]}"
    queued_at = datetime.now(UTC).isoformat()
    try:
        run_commodity_daily_ingest_task.send(
            start_date=start_date,
            end_date=end_date,
            duckdb_path=duckdb_path,
            products=products,
            dry_run=False,
        )
    except Exception as exc:
        raise MacroToolkitQueueError(str(exc)) from exc
    return MacroToolkitActionResult(
        payload={
            "status": "queued",
            "run_id": run_id,
            "job_name": COMMODITY_FUTURES_REFRESH_JOB_NAME,
            "cache_key": COMMODITY_FUTURES_REFRESH_CACHE_KEY,
            "cache_version": COMMODITY_FUTURES_REFRESH_CACHE_VERSION,
            "rule_version": COMMODITY_FUTURES_REFRESH_RULE_VERSION,
            "start_date": start_date,
            "end_date": end_date,
            "duckdb_path": duckdb_path,
            "products": list(products),
            "product_count": len(products),
            "row_count": None,
            "dry_run": False,
            "queued_at": queued_at,
            "table": "fact_commodity_futures_daily",
            "permission": permission,
        },
        quality_flag="warning",
        fallback_mode="none",
        as_of_date=end_date,
    )


def queue_choice_stock_refresh(
    *,
    duckdb_path: str,
    catalog_path: str,
    governance_path: str,
    archive_root: str = "",
    as_of_date: str,
    refresh_history: bool,
    refresh_factors: bool,
    factor_max_stock_count: int | None,
    theme_overlay_mode: ThemeOverlayRefreshMode = "off",
    permission: dict[str, object],
    idempotency_key: str | None = None,
) -> MacroToolkitActionResult:
    normalized_theme_overlay_mode = _normalize_theme_overlay_mode(theme_overlay_mode)
    normalized_idempotency_key = _normalize_idempotency_key(idempotency_key)
    try:
        with acquire_lock(
            _choice_stock_refresh_trigger_lock(as_of_date=as_of_date),
            base_dir=governance_path,
            timeout_seconds=0.1,
        ):
            if normalized_idempotency_key is not None:
                existing_idempotent_run = latest_choice_stock_refresh_for_idempotency_key(
                    governance_path,
                    as_of_date=as_of_date,
                    refresh_history=refresh_history,
                    refresh_factors=refresh_factors,
                    factor_max_stock_count=factor_max_stock_count,
                    theme_overlay_mode=normalized_theme_overlay_mode,
                    idempotency_key=normalized_idempotency_key,
                )
                if existing_idempotent_run is not None:
                    normalized_existing = _normalize_choice_stock_refresh_record(
                        existing_idempotent_run,
                        idempotency_replay=True,
                    )
                    return MacroToolkitActionResult(
                        payload=normalized_existing,
                        quality_flag=_write_refresh_quality_flag(
                            str(normalized_existing.get("status") or "")
                        ),
                        fallback_mode="none",
                        as_of_date=as_of_date,
                    )

            existing = latest_choice_stock_inflight_refresh(governance_path, as_of_date=as_of_date)
            if existing is not None:
                raise MacroToolkitConflictError(
                    f"Choice stock refresh already in progress for as_of_date={as_of_date}."
                )

            queued_at = datetime.now(UTC).isoformat()
            run_id = f"{CHOICE_STOCK_REFRESH_JOB_NAME}:{as_of_date}:{uuid.uuid4().hex[:12]}"
            queued_payload = build_choice_stock_refresh_run_payload(
                run_id=run_id,
                status="queued",
                as_of_date=as_of_date,
                queued_at=queued_at,
                refresh_history=refresh_history,
                refresh_factors=refresh_factors,
                factor_max_stock_count=factor_max_stock_count,
                theme_overlay_mode=normalized_theme_overlay_mode,
                permission=permission,
                idempotency_key=normalized_idempotency_key,
            )
            append_choice_stock_refresh_run(governance_path, queued_payload)
            try:
                run_choice_stock_refresh_task.send(
                    duckdb_path=duckdb_path,
                    catalog_path=catalog_path,
                    governance_path=governance_path,
                    archive_root=archive_root,
                    run_id=run_id,
                    as_of_date=as_of_date,
                    queued_at=queued_at,
                    refresh_history=refresh_history,
                    refresh_factors=refresh_factors,
                    factor_max_stock_count=factor_max_stock_count,
                    theme_overlay_mode=normalized_theme_overlay_mode,
                    permission=permission,
                    idempotency_key=normalized_idempotency_key,
                )
            except Exception as exc:
                append_choice_stock_refresh_run(
                    governance_path,
                    build_choice_stock_refresh_run_payload(
                        run_id=run_id,
                        status="failed",
                        as_of_date=as_of_date,
                        queued_at=queued_at,
                        finished_at=datetime.now(UTC).isoformat(),
                        refresh_history=refresh_history,
                        refresh_factors=refresh_factors,
                        factor_max_stock_count=factor_max_stock_count,
                        theme_overlay_mode=normalized_theme_overlay_mode,
                        theme_overlay_status=(
                            "not_run" if normalized_theme_overlay_mode != "off" else None
                        ),
                        error_message=str(exc),
                        failure_category="queue_dispatch_failure",
                        failure_reason=type(exc).__name__,
                        permission=permission,
                        idempotency_key=normalized_idempotency_key,
                    ),
                )
                raise MacroToolkitQueueError(
                    "Choice stock refresh queue dispatch failed."
                ) from exc
    except TimeoutError as exc:
        raise MacroToolkitConflictError(
            f"Choice stock refresh already in progress for as_of_date={as_of_date}."
        ) from exc

    return MacroToolkitActionResult(
        payload=_normalize_choice_stock_refresh_record(
            queued_payload,
            idempotency_replay=False,
        ),
        quality_flag="warning",
        fallback_mode="none",
        as_of_date=as_of_date,
    )


def append_choice_stock_refresh_run(governance_path: str | Path, payload: dict[str, object]) -> None:
    GovernanceRepository(base_dir=governance_path).append(CACHE_BUILD_RUN_STREAM, payload)


def build_choice_stock_refresh_run_payload(
    *,
    run_id: str,
    status: str,
    as_of_date: str,
    queued_at: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    refresh_history: bool = True,
    refresh_factors: bool = True,
    factor_max_stock_count: int | None = None,
    theme_overlay_mode: ThemeOverlayRefreshMode = "off",
    theme_overlay_status: str | None = None,
    theme_overlay_message: str | None = None,
    theme_overlay_member_count: int | None = None,
    theme_overlay_run_id: str | None = None,
    history_row_count: int | None = None,
    factor_row_count: int | None = None,
    source_version: object | None = None,
    vendor_version: object | None = None,
    error_message: str | None = None,
    failure_category: str | None = None,
    failure_reason: str | None = None,
    permission: dict[str, object] | None = None,
    idempotency_key: str | None = None,
    attempt_count: int | None = None,
    retryable: bool = False,
) -> dict[str, object]:
    normalized_theme_overlay_mode = _normalize_theme_overlay_mode(theme_overlay_mode)
    normalized_theme_overlay_status = _optional_text(theme_overlay_status) or (
        "off" if normalized_theme_overlay_mode == "off" else "pending"
    )
    return {
        "run_id": run_id,
        "job_name": CHOICE_STOCK_REFRESH_JOB_NAME,
        "status": status,
        "cache_key": CHOICE_STOCK_REFRESH_CACHE_KEY,
        "cache_version": CHOICE_STOCK_REFRESH_CACHE_VERSION,
        "lock": CHOICE_STOCK_REFRESH_LOCK,
        "source_version": _optional_text(source_version),
        "vendor_version": _optional_text(vendor_version),
        "rule_version": CHOICE_STOCK_REFRESH_RULE_VERSION,
        "report_date": as_of_date,
        "queued_at": queued_at,
        "started_at": started_at,
        "finished_at": finished_at,
        "error_message": error_message,
        "failure_category": failure_category,
        "failure_reason": failure_reason,
        "attempt_count": attempt_count,
        "retryable": retryable,
        "created_at": datetime.now(UTC).isoformat(),
        "refresh_history": refresh_history,
        "refresh_factors": refresh_factors,
        "factor_max_stock_count": factor_max_stock_count,
        "theme_overlay_mode": normalized_theme_overlay_mode,
        "theme_overlay_status": normalized_theme_overlay_status,
        "theme_overlay_message": _optional_text(theme_overlay_message),
        "theme_overlay_member_count": (
            0
            if normalized_theme_overlay_mode == "off" and theme_overlay_member_count is None
            else _optional_int(theme_overlay_member_count)
        ),
        "theme_overlay_run_id": _optional_text(theme_overlay_run_id),
        "history_row_count": history_row_count,
        "factor_row_count": factor_row_count,
        "permission": permission or build_choice_stock_refresh_permission_payload(),
        "trigger_mode": _choice_stock_refresh_trigger_mode(status),
        "idempotency_key": _normalize_idempotency_key(idempotency_key),
    }


def choice_stock_refresh_status(
    governance_path: str | Path,
    *,
    run_id: str = "",
) -> dict[str, object]:
    run_id_text = str(run_id or "").strip()
    records = _choice_stock_refresh_records(governance_path)
    if run_id_text:
        matching = [record for record in records if str(record.get("run_id") or "") == run_id_text]
        if not matching:
            raise ValueError(f"Choice stock refresh run not found: {run_id_text}")
        return _normalize_choice_stock_refresh_record(matching[-1])
    if not records:
        return {
            "status": "idle",
            "run_id": None,
            "job_name": CHOICE_STOCK_REFRESH_JOB_NAME,
            "cache_key": CHOICE_STOCK_REFRESH_CACHE_KEY,
            "trigger_mode": "idle",
            "permission": build_choice_stock_refresh_permission_payload(),
        }
    return _normalize_choice_stock_refresh_record(records[-1])


def choice_stock_refresh_overview(
    duckdb_path: str | Path,
    governance_path: str | Path,
    *,
    permission: dict[str, object] | None = None,
    reference_date: str | None = None,
) -> dict[str, object]:
    daily_observation, factor_snapshot = _choice_stock_materialization_statuses(
        duckdb_path,
        reference_date=reference_date,
    )
    return {
        "permission": permission or build_choice_stock_refresh_permission_payload(),
        "refresh": choice_stock_refresh_status(governance_path),
        "daily_observation": daily_observation,
        "factor_snapshot": factor_snapshot,
        "default_factor_max_stock_count": None,
    }


def latest_choice_stock_inflight_refresh(
    governance_path: str | Path,
    *,
    as_of_date: str,
) -> dict[str, object] | None:
    by_run_id: dict[str, dict[str, object]] = {}
    for record in _choice_stock_refresh_records(governance_path):
        if str(record.get("report_date") or "") != as_of_date:
            continue
        by_run_id[str(record.get("run_id") or "")] = record
    for record in reversed(list(by_run_id.values())):
        if (
            _write_refresh_record_blocks_dispatch(
                record,
                in_flight_statuses=_CHOICE_STOCK_REFRESH_IN_FLIGHT_STATUSES,
            )
            or _choice_stock_refresh_overlay_pending(record)
        ):
            return record
    return None


def latest_choice_stock_refresh_for_idempotency_key(
    governance_path: str | Path,
    *,
    as_of_date: str,
    refresh_history: bool,
    refresh_factors: bool,
    factor_max_stock_count: int | None,
    theme_overlay_mode: ThemeOverlayRefreshMode = "off",
    idempotency_key: str,
) -> dict[str, object] | None:
    normalized_theme_overlay_mode = _normalize_theme_overlay_mode(theme_overlay_mode)
    for record in reversed(_choice_stock_refresh_records(governance_path)):
        if str(record.get("report_date") or "") != as_of_date:
            continue
        if str(record.get("idempotency_key") or "").strip() != idempotency_key:
            continue
        if bool(record.get("refresh_history")) != refresh_history:
            continue
        if bool(record.get("refresh_factors")) != refresh_factors:
            continue
        if _optional_int(record.get("factor_max_stock_count")) != factor_max_stock_count:
            continue
        if _normalize_theme_overlay_mode(record.get("theme_overlay_mode") or "off") != (normalized_theme_overlay_mode):
            continue
        return record
    return None


def build_choice_stock_refresh_permission_payload(auth: AuthContext | None = None) -> dict[str, object]:
    return {
        "mode": "scoped_refresh",
        "allowed": True,
        "user_id": auth.user_id if auth else None,
        "role": auth.role if auth else None,
        "identity_source": auth.identity_source if auth else None,
        "resource": "macro_toolkit.choice_stock",
        "actions": ["history", "factor_snapshot", "theme_overlay"],
    }


def build_commodity_futures_refresh_permission_payload(
    auth: AuthContext | None = None,
    *,
    allowed: bool | None = None,
) -> dict[str, object]:
    return {
        "mode": "scoped_refresh",
        "allowed": allowed,
        "user_id": auth.user_id if auth else None,
        "role": auth.role if auth else None,
        "identity_source": auth.identity_source if auth else None,
        "resource": "macro_toolkit.commodity_futures",
        "actions": ["dry_run", "refresh"],
    }


def commodity_futures_status(duckdb_path: str | Path) -> dict[str, object]:
    base = {
        "table": "fact_commodity_futures_daily",
        "target_products": list(DEFAULT_MACRO_COMMODITY_REFRESH_PRODUCTS),
    }
    path = Path(duckdb_path)
    if not path.exists():
        return {
            **base,
            "materialized": False,
            "status": "missing_table",
            "row_count": None,
            "latest_trade_date": None,
            "source_vendors": [],
            "coverage": _commodity_futures_coverage([]),
            "nanhua_input": _commodity_futures_missing_nanhua("missing_table"),
        }
    try:
        conn = duckdb.connect(str(path), read_only=True)
        try:
            if not _duckdb_table_exists(conn, "fact_commodity_futures_daily"):
                return {
                    **base,
                    "materialized": False,
                    "status": "missing_table",
                    "row_count": None,
                    "latest_trade_date": None,
                    "source_vendors": [],
                    "coverage": _commodity_futures_coverage([]),
                    "nanhua_input": _commodity_futures_missing_nanhua("missing_table"),
                }
            row = conn.execute(
                """
                select count(*) as row_count
                from fact_commodity_futures_daily
                """
            ).fetchone()
            row_count = int(row[0] or 0) if row else 0
            product_rows = conn.execute(
                """
                with normalized as (
                  select
                    product_code,
                    case
                      when regexp_matches(cast(trade_date as varchar), '^[0-9]{8}$')
                        then try_strptime(cast(trade_date as varchar), '%Y%m%d')::date
                      else try_cast(left(cast(trade_date as varchar), 10) as date)
                    end as normalized_trade_date
                  from fact_commodity_futures_daily
                )
                select product_code, count(*) as row_count, max(normalized_trade_date) as latest_trade_date
                from normalized
                group by product_code
                order by product_code
                """
            ).fetchall()
            products = [
                {
                    "product_code": str(product_code),
                    "row_count": int(product_row_count or 0),
                    "latest_trade_date": _normalize_commodity_trade_date(product_latest),
                }
                for product_code, product_row_count, product_latest in product_rows
            ]
            product_latest_dates = [
                latest_date
                for latest_date in (
                    _normalize_commodity_trade_date(item.get("latest_trade_date")) for item in products
                )
                if latest_date
            ]
            latest_trade_date = max(product_latest_dates, default=None)
            source_vendors = [
                str(item[0]).strip()
                for item in conn.execute(
                    """
                    select distinct
                      case
                        when lower(coalesce(source_version, '')) like '%choice%' then 'choice'
                        when lower(coalesce(source_version, '')) like '%tushare%' then 'tushare'
                        when lower(coalesce(vendor_version, '')) like '%choice%' then 'choice'
                        when lower(coalesce(vendor_version, '')) like '%tushare%' then 'tushare'
                        else coalesce(nullif(vendor_version, ''), nullif(source_version, ''), 'unknown')
                      end as vendor
                    from fact_commodity_futures_daily
                    order by vendor
                    """
                ).fetchall()
                if str(item[0]).strip()
            ]
            nanhua_input = _commodity_futures_nanhua_input(conn)
            return {
                **base,
                "materialized": True,
                "status": "ok" if row_count > 0 else "empty_table",
                "row_count": row_count,
                "latest_trade_date": latest_trade_date,
                "source_vendors": source_vendors,
                "coverage": _commodity_futures_coverage(products),
                "nanhua_input": nanhua_input,
            }
        finally:
            conn.close()
    except duckdb.Error as exc:
        logger.warning(
            "DuckDB query failed surface=commodity_futures_status table=fact_commodity_futures_daily error=%s: %s",
            type(exc).__name__,
            exc,
        )
        return {
            **base,
            "materialized": False,
            "status": "unreadable_database",
            "row_count": None,
            "latest_trade_date": None,
            "source_vendors": [],
            "coverage": _commodity_futures_coverage([]),
            "nanhua_input": _commodity_futures_missing_nanhua("missing_table"),
        }


def load_equity_strategy_price_context(duckdb_path: str | Path | None) -> dict[str, object] | None:
    if duckdb_path is None:
        return None
    path = Path(duckdb_path)
    if not path.exists():
        return None
    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error as exc:
        warning = (
            f"DUCKDB_QUERY_FAILED: table=choice_stock_daily_observation "
            f"error={type(exc).__name__}: {exc}"
        )
        logger.warning(warning)
        return {
            "prices": None,
            "observations": None,
            "financials": None,
            "as_of_date": None,
            "tables_used": [],
            "source_versions": [],
            "vendor_versions": [],
            "warnings": [warning],
            "data_status": "unavailable",
        }
    unit_warnings: list[str] = []
    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        if "choice_stock_daily_observation" not in tables:
            return None
        canonical_dates = _duckdb_date_column_is_canonical_iso(
            conn,
            "choice_stock_daily_observation",
            "trade_date",
            database_path=path,
        )
        latest_date_select = (
            "try_cast(max(trade_date) as date)"
            if canonical_dates
            else "max(try_cast(trade_date as date))"
        )
        latest_row = conn.execute(
            f"""
            select {latest_date_select}
            from choice_stock_daily_observation
            where close_value is not null
              and close_value > 0
            """
        ).fetchone()
        latest_trade_date = latest_row[0] if latest_row else None
        if latest_trade_date is None:
            return None
        start_date = latest_trade_date - timedelta(days=EQUITY_PRICE_LOOKBACK_DAYS)
        sample_date_expression = (
            "trade_date" if canonical_dates else "try_cast(trade_date as date)"
        )
        daily_date_expression = (
            "daily.trade_date"
            if canonical_dates
            else "try_cast(daily.trade_date as date)"
        )
        date_parameters = (
            [
                latest_trade_date.isoformat(),
                start_date.isoformat(),
                latest_trade_date.isoformat(),
            ]
            if canonical_dates
            else [latest_trade_date, start_date, latest_trade_date]
        )

        def load_observations(
            amount_projection: str,
            unknown_projection: str,
            vendor_projection: str,
            sample_rank_expression: str,
        ) -> pd.DataFrame:
            # 样本排序键同样按 vendor 代际归一化为元:单日样本内两代零重叠,
            # 序关系本不受统一倍数影响,但 NULL/空白 vendor 行(无法定标)按
            # raw 值可能虚占 top-N 名额、下游又归一化为 NULL 浪费槽位。
            return conn.execute(
                f"""
                with latest_sample as (
                  select stock_code
                  from choice_stock_daily_observation
                  where {sample_date_expression} = ?
                    and close_value is not null
                    and close_value > 0
                  order by coalesce({sample_rank_expression}, 0) desc, stock_code asc
                  limit {EQUITY_PRICE_MAX_STOCKS}
                )
                select
                  try_cast(daily.trade_date as date) as trade_date,
                  daily.stock_code,
                  daily.close_value,
                  {amount_projection},
                  daily.pctchange,
                  daily.turn,
                  daily.amplitude,
                  daily.highlimit,
                  daily.lowlimit,
                  daily.source_version,
                  {vendor_projection},
                  {unknown_projection}
                from choice_stock_daily_observation daily
                join latest_sample sample
                  on sample.stock_code = daily.stock_code
                where {daily_date_expression} > ?
                  and {daily_date_expression} <= ?
                  and daily.close_value is not null
                  and daily.close_value > 0
                order by {daily_date_expression} asc, daily.stock_code asc
                """,
                date_parameters,
            ).df()

        # docs/data_contracts.md §4.10: amount 跨 vendor 代际统一为人民币元。
        try:
            frame = load_observations(
                amount_rmb_sql(table_alias="daily", alias="amount"),
                scale_unknown_sql(
                    "amount",
                    table_alias="daily",
                    alias="_amount_scale_unknown",
                ),
                "daily.vendor_version",
                amount_rmb_sql(alias=None),
            )
        except duckdb.BinderException as exc:
            if "vendor_version" not in str(exc).casefold():
                raise
            warning = (
                "choice_stock_daily_observation 缺少 vendor_version，"
                "低拥挤策略 amount 无法定标，已按 NULL 输出（fail-closed）。"
            )
            logger.warning(warning)
            unit_warnings.append(warning)
            frame = load_observations(
                "cast(null as double) as amount",
                "false as _amount_scale_unknown",
                "cast(null as varchar) as vendor_version",
                "amount",
            )
        unknown_scale = (
            frame.pop("_amount_scale_unknown")
            if "_amount_scale_unknown" in frame.columns
            else None
        )
        if unknown_scale is not None:
            unknown_count = int(pd.Series(unknown_scale).fillna(False).astype(bool).sum())
            if unknown_count:
                warning = (
                    "choice_stock_daily_observation 有 "
                    f"{unknown_count} 行 amount 非空但 vendor_version 为 NULL，"
                    "低拥挤策略 amount 已按未知单位置空。"
                )
                logger.warning(warning)
                unit_warnings.append(warning)
        financials = None
        if not frame.empty:
            try:
                financials = _load_equity_strategy_factor_snapshot_from_conn(
                    conn,
                    latest_trade_date.isoformat(),
                )
            except duckdb.Error as exc:
                warning = (
                    f"DUCKDB_QUERY_FAILED: table=choice_stock_factor_snapshot "
                    f"date={latest_trade_date.isoformat()} "
                    f"error={type(exc).__name__}: {exc}"
                )
                logger.warning(warning)
                unit_warnings.append(warning)
                financials = None
    except duckdb.Error as exc:
        warning = (
            f"DUCKDB_QUERY_FAILED: table=choice_stock_daily_observation "
            f"error={type(exc).__name__}: {exc}"
        )
        logger.warning(warning)
        return {
            "prices": None,
            "observations": None,
            "financials": None,
            "as_of_date": None,
            "tables_used": [],
            "source_versions": [],
            "vendor_versions": [],
            "warnings": [*unit_warnings, warning],
            "data_status": "unavailable",
        }
    finally:
        conn.close()

    if frame.empty:
        return None
    prices = (
        frame.pivot_table(index="trade_date", columns="stock_code", values="close_value", aggfunc="last")
        .sort_index()
        .apply(pd.to_numeric, errors="coerce")
    )
    prices = prices.ffill().dropna(axis=1)
    prices = prices.loc[:, (prices > 0).all(axis=0)]
    if len(prices.index) < EQUITY_PRICE_MIN_OBSERVATIONS or len(prices.columns) == 0:
        return None
    observations = frame[
        [
            "trade_date",
            "stock_code",
            "close_value",
            "amount",
            "pctchange",
            "turn",
            "amplitude",
            "highlimit",
            "lowlimit",
        ]
    ].copy()
    return {
        "prices": prices.astype("float64"),
        "observations": observations,
        "financials": financials,
        "as_of_date": latest_trade_date.isoformat(),
        "tables_used": [
            "choice_stock_daily_observation",
            *(["choice_stock_factor_snapshot"] if financials is not None else []),
        ],
        "source_versions": _unique_texts(frame["source_version"].tolist()),
        "vendor_versions": _unique_texts(frame["vendor_version"].tolist()),
        "warnings": unit_warnings,
    }


def equity_strategy_summary_warnings(
    price_context: dict[str, object] | None,
    warnings: Iterable[object] | None = None,
) -> list[str]:
    """合并策略自身告警与 price_context 中的单位类告警（docs/data_contracts.md §4.10）。

    ``load_equity_strategy_price_context`` 已将 ``vendor_version`` 缺列 / 行级 NULL
    的 fail-closed 告警写入 ``context["warnings"]``；A股策略 summary 的构造方
    （目前在 ``backend/app/api/routes/macro_toolkit.py``）应改用本函数拼装最终
    ``warnings`` 字段，而不是丢弃 ``price_context`` 中的单位降级信息。
    """
    context_warnings = (
        price_context.get("warnings") if isinstance(price_context, dict) else None
    )
    return _unique_texts([*(warnings or []), *(context_warnings or [])])


def load_equity_strategy_factor_snapshot(
    duckdb_path: Path,
    as_of_date: str,
    stock_codes: list[str] | None = None,
) -> pd.DataFrame | None:
    try:
        conn = duckdb.connect(str(duckdb_path), read_only=True)
    except duckdb.Error as exc:
        logger.warning(
            "DuckDB query failed surface=equity_factor_snapshot table=choice_stock_factor_snapshot date=%s error=%s: %s",
            as_of_date,
            type(exc).__name__,
            exc,
        )
        return None
    try:
        return _load_equity_strategy_factor_snapshot_from_conn(
            conn,
            as_of_date,
            stock_codes=stock_codes,
        )
    except duckdb.Error as exc:
        logger.warning(
            "DuckDB query failed surface=equity_factor_snapshot table=choice_stock_factor_snapshot date=%s error=%s: %s",
            as_of_date,
            type(exc).__name__,
            exc,
        )
        return None
    finally:
        conn.close()


def _load_equity_strategy_factor_snapshot_from_conn(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: str,
    stock_codes: list[str] | None = None,
) -> pd.DataFrame | None:
    tables = {row[0] for row in conn.execute("show tables").fetchall()}
    if "choice_stock_factor_snapshot" not in tables:
        return None
    factor_date_row = conn.execute(
        """
        select max(try_cast(as_of_date as date))
        from choice_stock_factor_snapshot
        where try_cast(as_of_date as date) <= try_cast(? as date)
        """,
        [as_of_date],
    ).fetchone()
    factor_as_of_date = factor_date_row[0] if factor_date_row else None
    if factor_as_of_date is None:
        return None
    rows = conn.execute(
        """
        select
          stock_code,
          pe,
          pb,
          ps,
          roe,
          gross_margin,
          three_month_return,
          twelve_month_return,
          volatility,
          dividend_yield,
          industry,
          source_version,
          vendor_version,
          rule_version,
          run_id
        from choice_stock_factor_snapshot
        where try_cast(as_of_date as date) = ?
        """,
        [factor_as_of_date],
    ).fetchall()
    if not rows:
        return None
    frame = pd.DataFrame(
        rows,
        columns=[
            "stock_code",
            "pe",
            "pb",
            "ps",
            "roe",
            "gross_margin",
            "three_month_return",
            "twelve_month_return",
            "volatility",
            "dividend_yield",
            "industry",
            "source_version",
            "vendor_version",
            "rule_version",
            "run_id",
        ],
    )
    if stock_codes is not None:
        frame = frame[frame["stock_code"].isin(stock_codes)].copy()
    else:
        frame = frame.copy()
    if frame.empty:
        return None
    numeric_columns = list(REQUIRED_FACTOR_INPUTS)
    frame[numeric_columns] = frame[numeric_columns].apply(pd.to_numeric, errors="coerce")
    frame["industry"] = frame["industry"].astype(str).str.strip()
    frame = frame.dropna(subset=numeric_columns + ["industry"])
    frame = frame[frame["industry"] != ""]
    if frame.empty:
        return None
    provenance = {
        "factor_source_versions": _unique_texts(frame["source_version"].tolist()),
        "factor_vendor_versions": _unique_texts(frame["vendor_version"].tolist()),
        "factor_rule_versions": _unique_texts(frame["rule_version"].tolist()),
        "factor_run_ids": _unique_texts(frame["run_id"].tolist()),
    }
    factors = frame.drop(columns=["source_version", "vendor_version", "rule_version", "run_id"])
    result = factors.set_index("stock_code").sort_index()
    result.attrs["provenance"] = provenance
    loaded_factor_date = factor_as_of_date.isoformat()
    result.attrs["factor_as_of_date"] = loaded_factor_date
    result.attrs["factor_date_status"] = "aligned" if loaded_factor_date == as_of_date else "fallback"
    return result


def load_a_share_stampede_risk_context(duckdb_path: str | Path | None) -> dict[str, object] | None:
    if duckdb_path is None:
        return None
    path = Path(duckdb_path)
    if not path.exists():
        return None
    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error as exc:
        warning = (
            f"DUCKDB_QUERY_FAILED: table=choice_stock_daily_observation "
            f"error={type(exc).__name__}: {exc}"
        )
        logger.warning(warning)
        return {
            "observations": pd.DataFrame(),
            "theme_frame": None,
            "tables_used": [],
            "warnings": [warning],
            "data_status": "unavailable",
        }
    warnings: list[str] = []
    try:
        if not _duckdb_table_exists(conn, "choice_stock_daily_observation"):
            return None
        canonical_dates = _duckdb_date_column_is_canonical_iso(
            conn,
            "choice_stock_daily_observation",
            "trade_date",
            database_path=path,
        )
        latest_date_select = (
            "try_cast(max(trade_date) as date)"
            if canonical_dates
            else "max(try_cast(trade_date as date))"
        )
        latest_row = conn.execute(
            f"""
            select {latest_date_select}
            from choice_stock_daily_observation
            where close_value is not null
              and close_value > 0
            """
        ).fetchone()
        latest_trade_date = latest_row[0] if latest_row else None
        if latest_trade_date is None:
            return None
        start_date = latest_trade_date - timedelta(days=A_SHARE_RISK_LOOKBACK_DAYS)
        sample_date_expression = (
            "trade_date" if canonical_dates else "try_cast(trade_date as date)"
        )
        daily_date_expression = (
            "daily.trade_date"
            if canonical_dates
            else "try_cast(daily.trade_date as date)"
        )
        date_parameters = (
            [
                latest_trade_date.isoformat(),
                start_date.isoformat(),
                latest_trade_date.isoformat(),
            ]
            if canonical_dates
            else [latest_trade_date, start_date, latest_trade_date]
        )

        def load_observations(
            amount_projection: str,
            unknown_projection: str,
            vendor_projection: str,
            sample_rank_expression: str,
        ) -> pd.DataFrame:
            # 样本排序键按 vendor 代际归一化为元(理由同低拥挤策略加载器)。
            return conn.execute(
                f"""
                with latest_sample as (
                  select stock_code
                  from choice_stock_daily_observation
                  where {sample_date_expression} = ?
                    and close_value is not null
                    and close_value > 0
                  order by coalesce({sample_rank_expression}, 0) desc, stock_code asc
                  limit {A_SHARE_RISK_MAX_STOCKS}
                )
                select
                  try_cast(daily.trade_date as date) as trade_date,
                  daily.stock_code,
                  daily.open_value,
                  daily.high_value,
                  daily.low_value,
                  daily.close_value,
                  {amount_projection},
                  daily.pctchange,
                  daily.turn,
                  daily.amplitude,
                  daily.tradestatus,
                  try_cast(daily.highlimit as double) as highlimit,
                  try_cast(daily.lowlimit as double) as lowlimit,
                  daily.source_version,
                  {vendor_projection},
                  {unknown_projection}
                from choice_stock_daily_observation daily
                join latest_sample sample
                  on sample.stock_code = daily.stock_code
                where {daily_date_expression} > ?
                  and {daily_date_expression} <= ?
                  and daily.close_value is not null
                  and daily.close_value > 0
                order by {daily_date_expression} asc, daily.stock_code asc
                """,
                date_parameters,
            ).df()

        # docs/data_contracts.md §4.10: 全市场 amount 跨 vendor 代际统一为人民币元。
        try:
            observations = load_observations(
                amount_rmb_sql(table_alias="daily", alias="amount"),
                scale_unknown_sql(
                    "amount",
                    table_alias="daily",
                    alias="_amount_scale_unknown",
                ),
                "daily.vendor_version",
                amount_rmb_sql(alias=None),
            )
        except duckdb.BinderException as exc:
            if "vendor_version" not in str(exc).casefold():
                raise
            warning = (
                "choice_stock_daily_observation 缺少 vendor_version，"
                "A 股踩踏风险 amount 无法定标，已按 NULL 输出（fail-closed）。"
            )
            logger.warning(warning)
            warnings.append(warning)
            observations = load_observations(
                "cast(null as double) as amount",
                "false as _amount_scale_unknown",
                "cast(null as varchar) as vendor_version",
                "amount",
            )
        unknown_scale = (
            observations.pop("_amount_scale_unknown")
            if "_amount_scale_unknown" in observations.columns
            else None
        )
        if unknown_scale is not None:
            unknown_count = int(pd.Series(unknown_scale).fillna(False).astype(bool).sum())
            if unknown_count:
                warning = (
                    "choice_stock_daily_observation 有 "
                    f"{unknown_count} 行 amount 非空但 vendor_version 为 NULL，"
                    "A 股踩踏风险 amount 已按未知单位置空。"
                )
                logger.warning(warning)
                warnings.append(warning)
        if observations.empty:
            return None
        tables_used = ["choice_stock_daily_observation"]
        _merge_a_share_universe(conn, observations, latest_trade_date, tables_used, warnings)
        _merge_a_share_limit_quality(conn, observations, latest_trade_date, tables_used)
        theme_frame = _load_a_share_theme_frame(conn, latest_trade_date, tables_used)
    except duckdb.Error as exc:
        warning = (
            f"DUCKDB_QUERY_FAILED: table=choice_stock_daily_observation "
            f"date={latest_trade_date.isoformat() if 'latest_trade_date' in locals() and latest_trade_date is not None else '-'} "
            f"error={type(exc).__name__}: {exc}"
        )
        logger.warning(warning)
        return {
            "observations": pd.DataFrame(),
            "theme_frame": None,
            "tables_used": [],
            "warnings": [*warnings, warning],
            "data_status": "unavailable",
        }
    finally:
        conn.close()
    return {
        "observations": observations,
        "theme_frame": theme_frame,
        "tables_used": tables_used,
        "warnings": warnings,
    }


def load_macro_curve_rows(duckdb_path: str | Path, report_date: date) -> list[dict[str, object]]:
    path = Path(duckdb_path)
    conn: duckdb.DuckDBPyConnection | None = None
    if path.exists():
        try:
            conn = duckdb.connect(str(path), read_only=True)
        except duckdb.Error as exc:
            logger.warning(
                "DuckDB query failed surface=macro_curve_rows table=fact_formal_yield_curve_daily date=%s error=%s: %s",
                report_date.isoformat(),
                type(exc).__name__,
                exc,
            )
            conn = None
    try:
        return _load_macro_curve_rows_from_conn(conn, duckdb_path, report_date)
    finally:
        if conn is not None:
            conn.close()


def _load_macro_curve_rows_from_conn(
    conn: duckdb.DuckDBPyConnection | None,
    duckdb_path: str | Path,
    report_date: date,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if conn is not None and _duckdb_table_exists(conn, "fact_formal_yield_curve_daily"):
        canonical_dates = _duckdb_date_column_is_canonical_iso(
            conn,
            "fact_formal_yield_curve_daily",
            "trade_date",
            database_path=duckdb_path,
        )
        trade_date_expression = (
            "trade_date" if canonical_dates else "try_cast(trade_date as date)"
        )
        formal_rows = conn.execute(
            f"""
            select
              cast(trade_date as varchar) as biz_date,
              lower(curve_type) as curve_type,
              tenor,
              cast(rate_pct as double) as rate_value
            from fact_formal_yield_curve_daily
            where {trade_date_expression} <= ?
            """,
            [report_date.isoformat() if canonical_dates else report_date],
        ).fetchall()
        for biz_date, curve_type, tenor, rate_value in formal_rows:
            curve_id = _CURVE_TYPE_TO_ID.get(str(curve_type))
            if curve_id and rate_value is not None:
                rows.append(
                    {
                        "biz_date": str(biz_date)[:10],
                        "curve_id": curve_id,
                        "tenor": str(tenor),
                        "rate_value": float(rate_value),
                    }
                )

    frames_by_alias = load_series_by_aliases(
        tuple(alias for alias, _, _ in _CURVE_ALIAS_POINTS),
        end=report_date.isoformat(),
        duckdb_path=duckdb_path,
    )
    for alias, curve_id, tenor in _CURVE_ALIAS_POINTS:
        frame = frames_by_alias[alias]
        if frame.empty:
            continue
        for _, sample in frame.iterrows():
            sample_date = _coerce_frame_date(sample.get("date"))
            if sample_date is None or sample_date > report_date:
                continue
            value = _float_or_none(sample.get("value"))
            if value is None:
                continue
            rows.append(
                {
                    "biz_date": sample_date.isoformat(),
                    "curve_id": curve_id,
                    "tenor": tenor,
                    "rate_value": value,
                }
            )
    return rows


def load_latest_risk_tensor_row(
    duckdb_path: str | Path,
    report_date: date,
) -> dict[str, object] | None:
    path = Path(duckdb_path)
    if not path.exists():
        return None
    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error as exc:
        logger.warning(
            "DuckDB query failed surface=risk_tensor table=fact_formal_risk_tensor_daily date=%s error=%s: %s",
            report_date.isoformat(),
            type(exc).__name__,
            exc,
        )
        return None
    try:
        return _load_latest_risk_tensor_row_from_conn(conn, report_date, path)
    finally:
        conn.close()


def _load_latest_risk_tensor_row_from_conn(
    conn: duckdb.DuckDBPyConnection | None,
    report_date: date,
    duckdb_path: str | Path,
) -> dict[str, object] | None:
    if conn is None or not _duckdb_table_exists(conn, "fact_formal_risk_tensor_daily"):
        return None
    canonical_dates = _duckdb_date_column_is_canonical_iso(
        conn,
        "fact_formal_risk_tensor_daily",
        "report_date",
        database_path=duckdb_path,
    )
    report_date_expression = (
        "report_date"
        if canonical_dates
        else "try_cast(report_date as date)"
    )
    frame = conn.execute(
        f"""
        select
          total_market_value,
          issuer_top5_weight,
          portfolio_dv01,
          bond_count,
          asset_cashflow_30d,
          asset_cashflow_90d,
          liability_cashflow_30d,
          liability_cashflow_90d,
          liquidity_gap_30d,
          liquidity_gap_90d,
          liquidity_gap_30d_ratio
        from fact_formal_risk_tensor_daily
        where {report_date_expression} <= ?
        order by {report_date_expression} desc
        limit 1
        """,
        [report_date.isoformat() if canonical_dates else report_date],
    ).fetchdf()
    if frame.empty:
        return None
    return dict(frame.iloc[0])


def load_latest_bond_positions(
    duckdb_path: str | Path,
    report_date: date,
) -> list[dict[str, object]]:
    path = Path(duckdb_path)
    if not path.exists():
        return []
    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error as exc:
        logger.warning(
            "DuckDB query failed surface=bond_positions table=fact_formal_bond_positions_daily date=%s error=%s: %s",
            report_date.isoformat(),
            type(exc).__name__,
            exc,
        )
        return []
    try:
        return _load_latest_bond_positions_from_conn(conn, report_date, path)
    finally:
        conn.close()


def _load_latest_bond_positions_from_conn(
    conn: duckdb.DuckDBPyConnection | None,
    report_date: date,
    duckdb_path: str | Path,
) -> list[dict[str, object]]:
    if conn is None or not _duckdb_table_exists(conn, "fact_formal_bond_analytics_daily"):
        return []
    canonical_dates = _duckdb_date_column_is_canonical_iso(
        conn,
        "fact_formal_bond_analytics_daily",
        "report_date",
        database_path=duckdb_path,
    )
    if canonical_dates:
        report_date_expression = "report_date"
        latest_max_expression = "max(report_date)"
        join_date_expression = "fact_formal_bond_analytics_daily.report_date"
        date_parameter: object = report_date.isoformat()
    else:
        report_date_expression = "try_cast(report_date as date)"
        latest_max_expression = "max(try_cast(report_date as date))"
        join_date_expression = (
            "try_cast(fact_formal_bond_analytics_daily.report_date as date)"
        )
        date_parameter = report_date
    frame = conn.execute(
        f"""
        with latest as (
          select {latest_max_expression} as report_date
          from fact_formal_bond_analytics_daily
          where {report_date_expression} <= ?
        )
        select
          cast(market_value as double) as market_value,
          maturity_date,
          cast(coupon_rate as double) as coupon_rate
        from fact_formal_bond_analytics_daily, latest
        where {join_date_expression} = latest.report_date
          and coalesce(cast(market_value as double), 0) > 0
        limit 5000
        """,
        [date_parameter],
    ).fetchdf()
    if frame.empty:
        return []
    positions: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        market_value = _float_or_none(row.get("market_value"))
        if market_value is None or market_value <= 0:
            continue
        positions.append(
            {
                "market_value": market_value,
                "maturity_date": _coerce_frame_date(row.get("maturity_date")),
                "coupon_rate": _float_or_none(row.get("coupon_rate")),
            }
        )
    return positions


def load_macro_capability_context(
    duckdb_path: str | Path,
    report_date: date,
) -> tuple[list[dict[str, object]], dict[str, object] | None, list[dict[str, object]]]:
    path = Path(duckdb_path)
    conn: duckdb.DuckDBPyConnection | None = None
    if path.exists():
        try:
            conn = duckdb.connect(str(path), read_only=True)
        except duckdb.Error as exc:
            logger.warning(
                "DuckDB query failed surface=macro_capability_context table=fact_formal_yield_curve_daily date=%s error=%s: %s",
                report_date.isoformat(),
                type(exc).__name__,
                exc,
            )
            conn = None
    try:
        curve_rows = _load_macro_curve_rows_from_conn(conn, duckdb_path, report_date)
        risk_tensor = _load_latest_risk_tensor_row_from_conn(conn, report_date, path)
        positions = _load_latest_bond_positions_from_conn(conn, report_date, path)
        return curve_rows, risk_tensor, positions
    finally:
        if conn is not None:
            conn.close()


def _merge_a_share_universe(
    conn: duckdb.DuckDBPyConnection,
    observations: pd.DataFrame,
    latest_trade_date: date,
    tables_used: list[str],
    warnings: list[str],
) -> None:
    if not _duckdb_table_exists(conn, "choice_stock_universe"):
        warnings.append("choice_stock_universe 未命中，ST/北交所/新股过滤仅按日线字段能力降级判断。")
        return
    rows = conn.execute(
        """
        select stock_code, stock_name
        from choice_stock_universe
        where try_cast(as_of_date as date) = ?
        """,
        [latest_trade_date],
    ).fetchall()
    if not rows:
        warnings.append("choice_stock_universe 最新交易日无样本，ST/北交所/新股过滤按日线字段能力降级判断。")
        return
    universe = pd.DataFrame(rows, columns=["stock_code", "stock_name"])
    universe["is_st"] = universe["stock_name"].astype(str).str.contains("ST|退", case=False, regex=True, na=False)
    universe["is_bse"] = universe["stock_code"].astype(str).str.endswith((".BJ", ".BSE"))
    latest_mask = pd.to_datetime(observations["trade_date"]).dt.date == latest_trade_date
    merged = observations.loc[latest_mask, ["stock_code"]].merge(universe, on="stock_code", how="left")
    observations.loc[latest_mask, "stock_name"] = merged["stock_name"].to_numpy()
    observations.loc[latest_mask, "is_st"] = merged["is_st"].fillna(False).to_numpy()
    observations.loc[latest_mask, "is_bse"] = merged["is_bse"].fillna(False).to_numpy()
    observations["is_st"] = observations["is_st"].map(lambda value: False if pd.isna(value) else bool(value))
    observations["is_bse"] = observations["is_bse"].map(lambda value: False if pd.isna(value) else bool(value))
    observations["is_st"] = observations.groupby("stock_code")["is_st"].transform("max").astype(bool)
    observations["is_bse"] = observations.groupby("stock_code")["is_bse"].transform("max").astype(bool)
    tables_used.append("choice_stock_universe")


def _merge_a_share_limit_quality(
    conn: duckdb.DuckDBPyConnection,
    observations: pd.DataFrame,
    latest_trade_date: date,
    tables_used: list[str],
) -> None:
    if not _duckdb_table_exists(conn, "choice_stock_limit_quality"):
        return
    rows = conn.execute(
        """
        select stock_code, issurgedlimit, isdeclinelimit
        from choice_stock_limit_quality
        where try_cast(as_of_date as date) = ?
        """,
        [latest_trade_date],
    ).fetchall()
    if not rows:
        return
    quality = pd.DataFrame(rows, columns=["stock_code", "is_limit_up_flag", "is_limit_down_flag"])
    latest_mask = pd.to_datetime(observations["trade_date"]).dt.date == latest_trade_date
    merged = observations.loc[latest_mask, ["stock_code"]].merge(quality, on="stock_code", how="left")
    observations.loc[latest_mask, "is_limit_up_flag"] = merged["is_limit_up_flag"].to_numpy()
    observations.loc[latest_mask, "is_limit_down_flag"] = merged["is_limit_down_flag"].to_numpy()
    tables_used.append("choice_stock_limit_quality")


def _load_a_share_theme_frame(
    conn: duckdb.DuckDBPyConnection,
    latest_trade_date: date,
    tables_used: list[str],
) -> pd.DataFrame | None:
    if _duckdb_table_exists(conn, "choice_stock_factor_snapshot"):
        rows = conn.execute(
            """
            select stock_code, industry, three_month_return
            from choice_stock_factor_snapshot
            where try_cast(as_of_date as date) = ?
            """,
            [latest_trade_date],
        ).fetchall()
        if rows:
            tables_used.append("choice_stock_factor_snapshot")
            return pd.DataFrame(rows, columns=["stock_code", "industry", "three_month_return"])
    if _duckdb_table_exists(conn, "choice_stock_sector_membership"):
        rows = conn.execute(
            """
            select stock_code, sw2021 as industry
            from choice_stock_sector_membership
            where try_cast(as_of_date as date) = ?
            """,
            [latest_trade_date],
        ).fetchall()
        if rows:
            tables_used.append("choice_stock_sector_membership")
            return pd.DataFrame(rows, columns=["stock_code", "industry"])
    return None


def default_choice_stock_refresh_as_of_date(duckdb_path: str | Path) -> str:
    path = Path(duckdb_path)
    if path.exists():
        try:
            conn = duckdb.connect(str(path), read_only=True)
            try:
                if _duckdb_table_exists(conn, "choice_stock_daily_observation"):
                    row = conn.execute("select max(trade_date) from choice_stock_daily_observation").fetchone()
                    if row and row[0] is not None:
                        return str(row[0])[:10]
            finally:
                conn.close()
        except duckdb.Error as exc:
            logger.warning(
                "DuckDB query failed surface=choice_stock_refresh_as_of_date table=choice_stock_daily_observation error=%s: %s",
                type(exc).__name__,
                exc,
            )
    return date.today().isoformat()


def _run_choice_stock_refresh_job(
    *,
    duckdb_path: str,
    catalog_path: str,
    governance_path: str,
    archive_root: str = "",
    run_id: str,
    as_of_date: str,
    queued_at: str,
    refresh_history: bool,
    refresh_factors: bool,
    factor_max_stock_count: int | None,
    theme_overlay_mode: ThemeOverlayRefreshMode = "off",
    permission: dict[str, object],
    idempotency_key: str | None = None,
) -> None:
    normalized_theme_overlay_mode = _normalize_theme_overlay_mode(theme_overlay_mode)
    normalized_idempotency_key = _normalize_idempotency_key(idempotency_key)
    attempt_count = (
        sum(
            1
            for record in _choice_stock_refresh_records(governance_path)
            if str(record.get("run_id") or "") == run_id
            and str(record.get("status") or "") == "running"
        )
        + 1
    )
    theme_overlay_run_id = f"{run_id}:theme-overlay" if normalized_theme_overlay_mode != "off" else None
    started_at = datetime.now(UTC).isoformat()
    append_choice_stock_refresh_run(
        governance_path,
        build_choice_stock_refresh_run_payload(
            run_id=run_id,
            status="running",
            as_of_date=as_of_date,
            queued_at=queued_at,
            started_at=started_at,
            refresh_history=refresh_history,
            refresh_factors=refresh_factors,
            factor_max_stock_count=factor_max_stock_count,
            theme_overlay_mode=normalized_theme_overlay_mode,
            theme_overlay_run_id=theme_overlay_run_id,
            permission=permission,
            idempotency_key=normalized_idempotency_key,
            attempt_count=attempt_count,
        ),
    )
    history_result: dict[str, object] | None = None
    factor_result: dict[str, object] | None = None
    try:
        if refresh_history:
            history_result = materialize_choice_stock_inputs(
                as_of_date=as_of_date,
                duckdb_path=duckdb_path,
                catalog_path=catalog_path,
            )
        if refresh_factors:
            factor_result = materialize_choice_stock_factor_snapshot(
                as_of_date=as_of_date,
                duckdb_path=duckdb_path,
                max_stock_count=factor_max_stock_count,
            )
        finished_at = datetime.now(UTC).isoformat()
        completed_payload = build_choice_stock_refresh_run_payload(
            run_id=run_id,
            status="completed",
            as_of_date=as_of_date,
            queued_at=queued_at,
            started_at=started_at,
            finished_at=finished_at,
            refresh_history=refresh_history,
            refresh_factors=refresh_factors,
            factor_max_stock_count=factor_max_stock_count,
            theme_overlay_mode=normalized_theme_overlay_mode,
            theme_overlay_run_id=theme_overlay_run_id,
            history_row_count=_result_row_count(history_result),
            factor_row_count=_result_row_count(factor_result),
            source_version=_latest_result_field("source_version", factor_result, history_result),
            vendor_version=_latest_result_field("vendor_version", factor_result, history_result),
            permission=permission,
            idempotency_key=normalized_idempotency_key,
            attempt_count=attempt_count,
        )
        observation_manifest = None
        if refresh_history:
            if history_result is None:
                raise RuntimeError("Choice-stock history refresh completed without a result payload")
            daily_observation_row_count = verify_choice_stock_daily_observation_landing(
                duckdb_path=duckdb_path,
                history_result=history_result,
                report_date=as_of_date,
            )
            observation_manifest = build_choice_stock_observation_manifest(
                history_result=history_result,
                refresh_run_id=run_id,
                report_date=as_of_date,
                daily_observation_row_count=daily_observation_row_count,
                created_at=finished_at,
            )
        append_choice_stock_refresh_completion(
            governance_repo=GovernanceRepository(base_dir=governance_path),
            completed_run_payload=completed_payload,
            observation_manifest=observation_manifest,
        )
    except Exception as exc:
        retry_pending = attempt_count <= _WRITE_REFRESH_MAX_RETRIES
        append_choice_stock_refresh_run(
            governance_path,
            build_choice_stock_refresh_run_payload(
                run_id=run_id,
                status="retrying" if retry_pending else "failed",
                as_of_date=as_of_date,
                queued_at=queued_at,
                started_at=started_at,
                finished_at=datetime.now(UTC).isoformat(),
                refresh_history=refresh_history,
                refresh_factors=refresh_factors,
                factor_max_stock_count=factor_max_stock_count,
                theme_overlay_mode=normalized_theme_overlay_mode,
                theme_overlay_status=("not_run" if normalized_theme_overlay_mode != "off" else None),
                theme_overlay_run_id=theme_overlay_run_id,
                history_row_count=_result_row_count(history_result),
                factor_row_count=_result_row_count(factor_result),
                source_version=_latest_result_field("source_version", factor_result, history_result),
                vendor_version=_latest_result_field("vendor_version", factor_result, history_result),
                error_message=f"{type(exc).__name__}: {exc}",
                failure_category=type(exc).__name__,
                failure_reason=str(exc),
                permission=permission,
                idempotency_key=normalized_idempotency_key,
                attempt_count=attempt_count,
                retryable=retry_pending,
            ),
        )
        raise

    if normalized_theme_overlay_mode == "off":
        return

    assert theme_overlay_run_id is not None
    try:
        theme_overlay_result = refresh_choice_stock_theme_overlay(
            mode=normalized_theme_overlay_mode,
            duckdb_path=duckdb_path,
            governance_dir=governance_path,
            archive_root=archive_root,
            expected_report_date=as_of_date,
            run_id=theme_overlay_run_id,
            source_version=_choice_stock_theme_overlay_source_version(
                parent_run_id=run_id,
                report_date=as_of_date,
            ),
            vendor_version=CHOICE_STOCK_THEME_OVERLAY_VENDOR_VERSION,
        )
    except Exception:
        logger.exception("Choice-stock theme overlay refresh raised for run_id=%s", run_id)
        theme_overlay_result = {
            "status": ("archive_failed" if normalized_theme_overlay_mode == "archive" else "dry_run_failed"),
            "message": "Theme overlay refresh failed; see server logs.",
            "member_count": 0,
            "run_id": theme_overlay_run_id,
        }

    theme_overlay_status = str(
        theme_overlay_result.get("overlay_status") or theme_overlay_result.get("status") or "unknown"
    )
    theme_overlay_message = _optional_text(theme_overlay_result.get("message"))
    if theme_overlay_status not in {"completed", "dry_run"}:
        if theme_overlay_message != "Theme overlay refresh failed; see server logs.":
            logger.warning(
                "Choice-stock theme overlay ended with status=%s for run_id=%s: %s",
                theme_overlay_status,
                run_id,
                theme_overlay_message,
            )
        theme_overlay_message = "Theme overlay refresh failed; see server logs."

    append_choice_stock_refresh_run(
        governance_path,
        build_choice_stock_refresh_run_payload(
            run_id=run_id,
            status="completed",
            as_of_date=as_of_date,
            queued_at=queued_at,
            started_at=started_at,
            finished_at=datetime.now(UTC).isoformat(),
            refresh_history=refresh_history,
            refresh_factors=refresh_factors,
            factor_max_stock_count=factor_max_stock_count,
            theme_overlay_mode=normalized_theme_overlay_mode,
            theme_overlay_status=theme_overlay_status,
            theme_overlay_message=theme_overlay_message,
            theme_overlay_member_count=_optional_int(theme_overlay_result.get("member_count")) or 0,
            theme_overlay_run_id=(_optional_text(theme_overlay_result.get("run_id")) or theme_overlay_run_id),
            history_row_count=_result_row_count(history_result),
            factor_row_count=_result_row_count(factor_result),
            source_version=_latest_result_field("source_version", factor_result, history_result),
            vendor_version=_latest_result_field("vendor_version", factor_result, history_result),
            permission=permission,
            idempotency_key=normalized_idempotency_key,
            attempt_count=attempt_count,
        ),
    )


def _run_toolkit_script_inline(name: str, argv: list[str], *, output_dir: str | Path) -> tuple[str, str, int]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    resolved_output_dir = Path(output_dir).resolve()
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    previous_env_output_dir = os.environ.get("MOSS_MACRO_TOOLKIT_OUTPUT_DIR")
    patched_modules = {
        module_name: module
        for module_name, module in sys.modules.items()
        if module_name in {"paths", "backend.app.core_finance.macro.toolkit.paths"}
    }
    previous_paths = {
        module_name: {
            attr: getattr(module, attr)
            for attr in ("OUTPUT_DIR", "ASSET_DIR")
            if hasattr(module, attr)
        }
        for module_name, module in patched_modules.items()
    }
    try:
        os.environ["MOSS_MACRO_TOOLKIT_OUTPUT_DIR"] = str(resolved_output_dir)
        for module in patched_modules.values():
            module.OUTPUT_DIR = resolved_output_dir
            module.ASSET_DIR = resolved_output_dir / "bond_macro_report_assets"
            module.ASSET_DIR.mkdir(parents=True, exist_ok=True)
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            run_toolkit_script(name, argv)
    except Exception as exc:  # pragma: no cover - returned to UI as script stderr
        stderr.write(f"\ninline runner failed: {exc}")
        return stdout.getvalue(), stderr.getvalue(), 1
    finally:
        if previous_env_output_dir is None:
            os.environ.pop("MOSS_MACRO_TOOLKIT_OUTPUT_DIR", None)
        else:
            os.environ["MOSS_MACRO_TOOLKIT_OUTPUT_DIR"] = previous_env_output_dir
        for module_name, attrs in previous_paths.items():
            module = patched_modules[module_name]
            for attr in ("OUTPUT_DIR", "ASSET_DIR"):
                if attr in attrs:
                    setattr(module, attr, attrs[attr])
                elif hasattr(module, attr):
                    delattr(module, attr)
    return stdout.getvalue(), stderr.getvalue(), 0


def _script_payload(
    name: str,
    filename: str,
    group: str,
    default_data_sources: tuple[str, ...],
    optional_dependencies: tuple[str, ...],
    notes: str,
    path: Path,
) -> dict[str, object]:
    return {
        "name": name,
        "filename": filename,
        "group": group,
        "default_data_sources": list(default_data_sources),
        "optional_dependencies": list(optional_dependencies),
        "notes": notes,
        "path": str(path.relative_to(TOOLKIT_ROOT)),
        "available": path.exists(),
    }


def _output_files() -> list[dict[str, object]]:
    return output_files(OUTPUT_DIR)


def _macro_model_readiness_payload(
    model: dict[str, object],
    *,
    files_by_name: dict[str, dict[str, object]],
    reference_date: str | None,
) -> dict[str, object]:
    expected_outputs = [str(name) for name in model["expected_outputs"]]
    script_name = str(model["script_name"])
    script = get_toolkit_script(script_name)
    outputs = [
        _macro_output_health(name, files_by_name.get(name), reference_date=reference_date)
        for name in expected_outputs
    ]
    missing_outputs = [str(item["name"]) for item in outputs if item["freshness_status"] == "missing"]
    stale_outputs = [str(item["name"]) for item in outputs if item["freshness_status"] == "stale"]
    degraded_outputs = [
        str(item["name"])
        for item in outputs
        if item["freshness_status"] in {"unknown", "future", "mixed", "invalid_date"}
    ]
    present_outputs = [item for item in outputs if item["freshness_status"] != "missing"]
    latest_modified_at = max(
        (str(item["modified_at"]) for item in outputs if item.get("modified_at")),
        default=None,
    )
    latest_content_date = max(
        (str(item["content_date"]) for item in outputs if item.get("content_date")),
        default=None,
    )
    readiness = _model_readiness_status(
        script_available=script.path.exists(),
        expected_count=len(expected_outputs),
        missing_outputs=missing_outputs,
        stale_outputs=stale_outputs,
        degraded_outputs=degraded_outputs,
        present_count=len(present_outputs),
    )
    notes = [str(note) for note in model.get("notes", ())]
    if readiness != "artifact_backed":
        notes.append("Registered script is not enough for system readiness; expected output artifacts must exist and be fresh.")
    degraded_reason = _macro_readiness_degraded_reason(
        readiness=readiness,
        script_available=script.path.exists(),
        missing_outputs=missing_outputs,
        stale_outputs=stale_outputs,
        degraded_outputs=degraded_outputs,
    )
    evidence_level = _macro_readiness_evidence_level(readiness=readiness, present_count=len(present_outputs))
    date_basis = _macro_readiness_date_basis(outputs)
    return {
        "id": str(model["id"]),
        "label": str(model["label"]),
        "script_name": script_name,
        "script_available": script.path.exists(),
        "expected_outputs": expected_outputs,
        "outputs": outputs,
        "missing_outputs": missing_outputs,
        "stale_outputs": stale_outputs,
        "degraded_outputs": degraded_outputs,
        "latest_modified_at": latest_modified_at,
        "latest_content_date": latest_content_date,
        "readiness": readiness,
        "degraded_reason": degraded_reason,
        "evidence_level": evidence_level,
        "date_basis": date_basis,
        "artifact_receipt": _macro_artifact_receipt(
            model_id=str(model["id"]),
            script_name=script_name,
            readiness=readiness,
            outputs=outputs,
            degraded_reason=degraded_reason,
            data_asof=latest_content_date,
        ),
        "observation_only": MACRO_TOOLKIT_OBSERVATION_ONLY,
        "formal_use_allowed": MACRO_TOOLKIT_FORMAL_USE_ALLOWED,
        "notes": notes,
    }


def _model_readiness_status(
    *,
    script_available: bool,
    expected_count: int,
    missing_outputs: list[str],
    stale_outputs: list[str],
    degraded_outputs: list[str],
    present_count: int,
) -> str:
    if not script_available:
        return "unknown"
    if expected_count == 0:
        return "registered_only"
    if missing_outputs and present_count == 0:
        return "missing_output"
    if missing_outputs:
        return "degraded"
    if stale_outputs:
        return "stale"
    if degraded_outputs:
        return "degraded"
    return "artifact_backed"


def _dry_run_receipt(step: dict[str, object], *, chain_id: str, output_dir: str | Path) -> dict[str, object]:
    return {
        "order": int(step["order"]),
        "chain_id": chain_id,
        "script_name": str(step["script_name"]),
        "status": "dry_run",
        "exit_code": None,
        "expected_outputs": list(step.get("expected_outputs") or []),
        "produced_outputs": [],
        "missing_outputs_after": _missing_expected_outputs(step, output_dir=output_dir),
        "degraded_reason": "dry_run_not_executed",
        "data_asof": None,
        "generated_at": datetime.now(UTC).isoformat(),
        "runtime_endpoint": MACRO_TOOLKIT_RUN_CHAIN_ENDPOINT,
        "page_surface": MACRO_TOOLKIT_SCRIPT_ARTIFACT_SURFACE,
        "formal_use_allowed": MACRO_TOOLKIT_FORMAL_USE_ALLOWED,
        "observation_only": MACRO_TOOLKIT_OBSERVATION_ONLY,
        "started_at": None,
        "finished_at": None,
        "stdout": "",
        "stderr": "",
    }


def _run_receipt(
    step: dict[str, object],
    result: dict[str, object],
    *,
    chain_id: str,
    output_dir: str | Path,
) -> dict[str, object]:
    expected_outputs = [str(name) for name in step.get("expected_outputs") or []]
    outputs = output_files(output_dir)
    output_names = {str(item["name"]) for item in outputs}
    missing_outputs_after = [name for name in expected_outputs if name not in output_names]
    degraded_reason = _macro_run_degraded_reason(status=str(result.get("status") or "unknown"), missing_outputs=missing_outputs_after)
    return {
        "order": int(step["order"]),
        "chain_id": chain_id,
        "script_name": str(step["script_name"]),
        "status": str(result.get("status") or "unknown"),
        "exit_code": result.get("exit_code"),
        "expected_outputs": expected_outputs,
        "produced_outputs": sorted(name for name in expected_outputs if name in output_names),
        "missing_outputs_after": missing_outputs_after,
        "degraded_reason": degraded_reason,
        "blocker": _macro_run_blocker(
            degraded_reason=degraded_reason,
            script_name=str(step["script_name"]),
            missing_outputs=missing_outputs_after,
        ),
        "data_asof": _macro_run_data_asof(expected_outputs=expected_outputs, outputs=outputs),
        "generated_at": datetime.now(UTC).isoformat(),
        "runtime_endpoint": MACRO_TOOLKIT_RUN_CHAIN_ENDPOINT,
        "page_surface": MACRO_TOOLKIT_SCRIPT_ARTIFACT_SURFACE,
        "formal_use_allowed": MACRO_TOOLKIT_FORMAL_USE_ALLOWED,
        "observation_only": MACRO_TOOLKIT_OBSERVATION_ONLY,
        "started_at": result.get("started_at"),
        "finished_at": result.get("finished_at"),
        "stdout": str(result.get("stdout") or ""),
        "stderr": str(result.get("stderr") or ""),
    }


def _missing_expected_outputs(step: dict[str, object], *, output_dir: str | Path) -> list[str]:
    output_names = {str(item["name"]) for item in output_files(output_dir)}
    return [str(name) for name in step.get("expected_outputs") or [] if str(name) not in output_names]


def _choice_stock_refresh_records(governance_path: str | Path) -> list[dict[str, object]]:
    try:
        rows = GovernanceRepository(base_dir=governance_path).read_all(CACHE_BUILD_RUN_STREAM)
    except Exception:
        return []
    return [
        row
        for row in rows
        if str(row.get("job_name") or "") == CHOICE_STOCK_REFRESH_JOB_NAME
        and str(row.get("cache_key") or "") == CHOICE_STOCK_REFRESH_CACHE_KEY
    ]


def _choice_stock_refresh_trigger_lock(*, as_of_date: str) -> LockDefinition:
    return LockDefinition(
        key=f"{CHOICE_STOCK_REFRESH_LOCK}:{as_of_date}:trigger",
        ttl_seconds=30,
    )


def _normalize_choice_stock_refresh_record(
    record: dict[str, object],
    *,
    idempotency_replay: bool | None = None,
) -> dict[str, object]:
    public_record = dict(record)
    overlay_pending = _choice_stock_refresh_overlay_pending(public_record)
    if overlay_pending:
        public_record["status"] = "running"
    normalized = _normalize_write_refresh_public_record(
        public_record,
        job_name=CHOICE_STOCK_REFRESH_JOB_NAME,
        cache_key=CHOICE_STOCK_REFRESH_CACHE_KEY,
        cache_version=CHOICE_STOCK_REFRESH_CACHE_VERSION,
        rule_version=CHOICE_STOCK_REFRESH_RULE_VERSION,
        idempotency_replay=idempotency_replay,
    )
    normalized.update(
        {
            "refresh_history": public_record.get("refresh_history") is True,
            "refresh_factors": public_record.get("refresh_factors") is True,
            "factor_max_stock_count": _optional_int(
                public_record.get("factor_max_stock_count")
            ),
            "history_row_count": _optional_int(
                public_record.get("history_row_count")
            ),
            "factor_row_count": _optional_int(
                public_record.get("factor_row_count")
            ),
            "theme_overlay_mode": _normalize_theme_overlay_mode(
                public_record.get("theme_overlay_mode")
            ),
            "theme_overlay_status": _optional_text(
                public_record.get("theme_overlay_status")
            ),
            "theme_overlay_message": _optional_text(
                public_record.get("theme_overlay_message")
            ),
            "theme_overlay_member_count": _optional_int(
                public_record.get("theme_overlay_member_count")
            ),
            "theme_overlay_run_id": _optional_text(
                public_record.get("theme_overlay_run_id")
            ),
            "permission": (
                public_record.get("permission")
                if isinstance(public_record.get("permission"), dict)
                else build_choice_stock_refresh_permission_payload()
            ),
        }
    )
    if overlay_pending:
        normalized["choice_completion_status"] = "completed"
    return normalized


def _choice_stock_refresh_overlay_pending(record: dict[str, object]) -> bool:
    return (
        str(record.get("status") or "") == "completed"
        and str(record.get("theme_overlay_mode") or "off") in {"dry_run", "archive"}
        and str(record.get("theme_overlay_status") or "") == "pending"
    )


def _choice_stock_refresh_trigger_mode(status: str) -> str:
    normalized = str(status or "").strip()
    if normalized in _CHOICE_STOCK_REFRESH_IN_FLIGHT_STATUSES:
        return "async"
    if normalized:
        return "terminal"
    return "idle"


def _choice_stock_daily_observation_status(
    duckdb_path: str | Path,
    *,
    reference_date: str | None = None,
) -> dict[str, object]:
    daily_observation, _ = _choice_stock_materialization_statuses(
        duckdb_path,
        reference_date=reference_date,
    )
    return daily_observation


def _choice_stock_materialization_statuses(
    duckdb_path: str | Path,
    *,
    reference_date: str | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    daily_observation, factor_snapshot = _choice_stock_materialization_base_statuses(duckdb_path)
    return (
        _choice_stock_daily_observation_status_with_freshness(
            daily_observation,
            reference_date=reference_date,
        ),
        _choice_stock_factor_snapshot_status_with_freshness(
            factor_snapshot,
            reference_date=reference_date,
        ),
    )


def _choice_stock_materialization_base_statuses(
    duckdb_path: str | Path,
) -> tuple[dict[str, object], dict[str, object]]:
    path = Path(duckdb_path)
    if not path.exists():
        return (
            _choice_stock_base_table_status("missing_database"),
            _choice_stock_base_table_status("missing_database"),
        )
    try:
        stat = path.stat()
    except OSError:
        return (
            _choice_stock_base_table_status("unreadable_database"),
            _choice_stock_base_table_status("unreadable_database"),
        )
    return _choice_stock_materialization_base_statuses_cache(
        str(path.resolve()),
        stat.st_mtime_ns,
        stat.st_size,
    )


@lru_cache(maxsize=8)
def _choice_stock_materialization_base_statuses_cache(
    duckdb_path: str,
    _mtime_ns: int,
    _size: int,
) -> tuple[dict[str, object], dict[str, object]]:
    try:
        conn = duckdb.connect(duckdb_path, read_only=True)
    except duckdb.Error as exc:
        logger.warning(
            "DuckDB query failed surface=choice_stock_materialization table=choice_stock_daily_observation error=%s: %s",
            type(exc).__name__,
            exc,
        )
        return (
            _choice_stock_base_table_status("unreadable_database"),
            _choice_stock_base_table_status("unreadable_database"),
        )
    try:
        return (
            _choice_stock_daily_observation_base_status_from_conn(conn),
            _choice_stock_factor_snapshot_base_status_from_conn(conn),
        )
    finally:
        conn.close()


def _choice_stock_daily_observation_base_status_from_conn(
    conn: duckdb.DuckDBPyConnection,
) -> dict[str, object]:
    try:
        if not _duckdb_table_exists(conn, "choice_stock_daily_observation"):
            return _choice_stock_base_table_status("missing_table")
        row = conn.execute(
            """
            select
              count(*) as row_count,
              count(distinct stock_code) as stock_count,
              count(distinct trade_date) as trade_date_count,
              max(trade_date) as latest_trade_date
            from choice_stock_daily_observation
            """
        ).fetchone()
    except duckdb.Error as exc:
        logger.warning(
            "DuckDB query failed surface=choice_stock_daily_observation_status table=choice_stock_daily_observation error=%s: %s",
            type(exc).__name__,
            exc,
        )
        return _choice_stock_base_table_status("unreadable_table")
    row_count = _int_or_zero(row[0] if row else 0)
    latest_trade_date = str(row[3])[:10] if row and row[3] is not None else None
    return {
        "materialized": row_count > 0,
        "status": "ok" if row_count > 0 else "empty_table",
        "row_count": row_count,
        "stock_count": _int_or_zero(row[1] if row else 0),
        "trade_date_count": _int_or_zero(row[2] if row else 0),
        "latest_trade_date": latest_trade_date,
    }


def _choice_stock_factor_snapshot_status(
    duckdb_path: str | Path,
    *,
    reference_date: str | None = None,
) -> dict[str, object]:
    _, factor_snapshot = _choice_stock_materialization_statuses(
        duckdb_path,
        reference_date=reference_date,
    )
    return factor_snapshot


def _choice_stock_factor_snapshot_base_status_from_conn(
    conn: duckdb.DuckDBPyConnection,
) -> dict[str, object]:
    try:
        if not _duckdb_table_exists(conn, "choice_stock_factor_snapshot"):
            return _choice_stock_base_table_status("missing_table")
        row = conn.execute(
            """
            select
              count(*) as row_count,
              count(distinct stock_code) as stock_count,
              max(as_of_date) as as_of_date
            from choice_stock_factor_snapshot
            """
        ).fetchone()
    except duckdb.Error as exc:
        logger.warning(
            "DuckDB query failed surface=choice_stock_factor_snapshot_status table=choice_stock_factor_snapshot error=%s: %s",
            type(exc).__name__,
            exc,
        )
        return _choice_stock_base_table_status("unreadable_table")
    row_count = _int_or_zero(row[0] if row else 0)
    as_of_date = str(row[2])[:10] if row and row[2] is not None else None
    return {
        "materialized": row_count > 0,
        "status": "ok" if row_count > 0 else "empty_table",
        "row_count": row_count,
        "stock_count": _int_or_zero(row[1] if row else 0),
        "as_of_date": as_of_date,
    }


def _duckdb_table_exists(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    try:
        row = conn.execute(
            """
            select count(*)
            from information_schema.tables
            where lower(table_name) = lower(?)
            """,
            [table_name],
        ).fetchone()
    except duckdb.Error as exc:
        logger.warning(
            "DuckDB query failed surface=duckdb_table_exists table=%s error=%s: %s",
            table_name,
            type(exc).__name__,
            exc,
        )
        return False
    return bool(row and row[0])


def _duckdb_date_column_is_canonical_iso(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    column_name: str,
    *,
    database_path: str | Path | None = None,
) -> bool:
    if (table_name, column_name) not in _CANONICAL_ISO_DATE_COLUMNS:
        raise ValueError(f"unsupported date column: {table_name}.{column_name}")
    cache_key = _duckdb_date_column_cache_key(database_path, table_name, column_name)
    if cache_key is None:
        return _probe_duckdb_date_column_is_canonical_iso(conn, table_name, column_name)

    with _CANONICAL_ISO_DATE_CACHE_LOCK:
        if cache_key in _CANONICAL_ISO_DATE_CACHE:
            return _CANONICAL_ISO_DATE_CACHE[cache_key]
        probe_lock = _CANONICAL_ISO_DATE_PROBE_LOCKS.setdefault(
            cache_key,
            threading.Lock(),
        )

    with probe_lock:
        with _CANONICAL_ISO_DATE_CACHE_LOCK:
            if cache_key in _CANONICAL_ISO_DATE_CACHE:
                return _CANONICAL_ISO_DATE_CACHE[cache_key]
        try:
            result = _probe_duckdb_date_column_is_canonical_iso(
                conn,
                table_name,
                column_name,
            )
        except Exception:
            with _CANONICAL_ISO_DATE_CACHE_LOCK:
                if _CANONICAL_ISO_DATE_PROBE_LOCKS.get(cache_key) is probe_lock:
                    _CANONICAL_ISO_DATE_PROBE_LOCKS.pop(cache_key, None)
            raise
        with _CANONICAL_ISO_DATE_CACHE_LOCK:
            _CANONICAL_ISO_DATE_CACHE[cache_key] = result
            while len(_CANONICAL_ISO_DATE_CACHE) > _CANONICAL_ISO_DATE_CACHE_MAX_ENTRIES:
                oldest_key = next(iter(_CANONICAL_ISO_DATE_CACHE))
                _CANONICAL_ISO_DATE_CACHE.pop(oldest_key, None)
            if _CANONICAL_ISO_DATE_PROBE_LOCKS.get(cache_key) is probe_lock:
                _CANONICAL_ISO_DATE_PROBE_LOCKS.pop(cache_key, None)
        return result


def _duckdb_date_column_cache_key(
    database_path: str | Path | None,
    table_name: str,
    column_name: str,
) -> _DateColumnCacheKey | None:
    if database_path is None:
        return None
    try:
        resolved_path = Path(database_path).resolve(strict=True)
        stat = resolved_path.stat()
    except OSError:
        return None
    return (
        os.path.normcase(str(resolved_path)),
        stat.st_mtime_ns,
        stat.st_size,
        table_name,
        column_name,
    )


def _probe_duckdb_date_column_is_canonical_iso(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    column_name: str,
) -> bool:
    row = conn.execute(
        f"""
        select 1
        from (
          select
            {column_name} as raw_date,
            try_cast({column_name} as date) as parsed_date
          from {table_name}
          where {column_name} is not null
        ) dates
        where parsed_date is null
           or cast(parsed_date as varchar) != raw_date
        limit 1
        """
    ).fetchone()
    return row is None
