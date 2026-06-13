from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from pathlib import Path

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
from backend.app.core_finance.macro.toolkit.system_sources import load_series_by_alias
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from backend.app.security.auth_context import AuthContext
from backend.app.services.cffex_member_rank_service import materialize_cffex_member_rank
from backend.app.tasks.choice_stock_materialize import (
    materialize_choice_stock_factor_snapshot,
    materialize_choice_stock_inputs,
)
from backend.app.tasks.commodity_daily_ingest import run_commodity_daily_ingest, run_commodity_daily_ingest_task
from fastapi import BackgroundTasks

CHOICE_STOCK_REFRESH_JOB_NAME = "choice_stock_refresh"
CHOICE_STOCK_REFRESH_CACHE_KEY = "choice_stock.history_and_factor_snapshot"
CHOICE_STOCK_REFRESH_CACHE_VERSION = "choice_stock_refresh_v1"
CHOICE_STOCK_REFRESH_LOCK = "lock:choice_stock_refresh"
CHOICE_STOCK_REFRESH_RULE_VERSION = "rv_choice_stock_materialization_front_layer_v1"
_CHOICE_STOCK_REFRESH_IN_FLIGHT_STATUSES = {"queued", "running"}
DEFAULT_MACRO_COMMODITY_REFRESH_PRODUCTS = ("RB", "I", "CU", "AL", "SC", "AU", "NHCI")
COMMODITY_FUTURES_REFRESH_JOB_NAME = "commodity_futures_daily_ingest"
COMMODITY_FUTURES_REFRESH_CACHE_KEY = "commodity_futures.daily"
COMMODITY_FUTURES_REFRESH_CACHE_VERSION = "commodity_futures_daily_v1"
COMMODITY_FUTURES_REFRESH_RULE_VERSION = "rv_commodity_daily_v1"
EQUITY_PRICE_LOOKBACK_DAYS = 260
EQUITY_PRICE_MIN_OBSERVATIONS = 80
EQUITY_PRICE_MAX_STOCKS = 500
A_SHARE_RISK_LOOKBACK_DAYS = 35
A_SHARE_RISK_MAX_STOCKS = 8000
MACRO_TOOLKIT_OBSERVATION_ONLY = True
MACRO_TOOLKIT_FORMAL_USE_ALLOWED = False
MACRO_TOOLKIT_OUTPUT_DATE_COLUMNS = ("日期", "date", "trade_date", "as_of_date")
MACRO_TOOLKIT_CHAIN_LOCK = LockDefinition(key="lock:macro_toolkit:script-chain", ttl_seconds=900)
MACRO_TOOLKIT_RUN_CHAIN_ENDPOINT = "/ui/macro/toolkit/scripts/run-chain"
MACRO_TOOLKIT_MODEL_READINESS_SURFACE = "/macro-toolkit#macro-toolkit-model-readiness-detail"
MACRO_TOOLKIT_SCRIPT_ARTIFACT_SURFACE = "/macro-toolkit#macro-toolkit-script-artifact-detail"

_MACRO_MODEL_DEFINITIONS: tuple[dict[str, object], ...] = (
    {
        "id": "merrill_clock",
        "label": "Merrill Clock",
        "script_name": "merrill_clock_cn",
        "expected_outputs": ("merrill_clock_latest.csv", "merrill_clock_history.csv"),
        "notes": ("Macro cycle and asset allocation candidate signal.",),
    },
    {
        "id": "crisis_score",
        "label": "Crisis Score",
        "script_name": "crisis_score_cn",
        "expected_outputs": ("crisis_score_latest.csv", "crisis_score_history.csv"),
        "notes": ("Stress score candidate signal.",),
    },
    {
        "id": "bond_futures_basis",
        "label": "Bond Futures Basis / IRR / Safety Margin",
        "script_name": "bond_futures_data",
        "expected_outputs": ("bond_futures_latest.csv", "bond_futures_history.csv"),
        "notes": ("Treasury futures basis and safety-margin evidence.",),
    },
    {
        "id": "bond_futures_four_factor",
        "label": "Bond Futures Four-Factor Trend",
        "script_name": "bond_futures_signals",
        "expected_outputs": ("bond_signals_latest.csv",),
        "notes": ("MA, channel, MACD and Bollinger style treasury-futures signal evidence.",),
    },
    {
        "id": "funding_conditions",
        "label": "Funding Conditions / Flow",
        "script_name": "merrill_clock_cn",
        "expected_outputs": ("merrill_clock_latest.csv",),
        "notes": ("Funding condition is evidenced through DR007/NCD inputs and Merrill liquidity momentum, not a standalone formal metric.",),
    },
    {
        "id": "crowding",
        "label": "Crowding",
        "script_name": "crowding_cn",
        "expected_outputs": ("crowding_latest.csv", "crowding_history.csv"),
        "notes": ("Crowding candidate signal.",),
    },
    {
        "id": "dcc_garch",
        "label": "DCC-GARCH",
        "script_name": "dcc_garch_cn",
        "expected_outputs": ("dcc_latest.csv", "dcc_results.csv"),
        "notes": ("Dynamic conditional correlation candidate signal.",),
    },
    {
        "id": "cta_trend",
        "label": "CTA Trend",
        "script_name": "cta_trend_cn",
        "expected_outputs": ("cta_results.csv",),
        "notes": ("CTA trend candidate signal.",),
    },
    {
        "id": "final_signal",
        "label": "Final Signal Aggregator",
        "script_name": "signal_aggregator",
        "expected_outputs": ("final_signal.csv",),
        "notes": ("Aggregates macro, bond futures, crisis and crowding evidence.",),
    },
    {
        "id": "risk_monitor",
        "label": "Risk Monitor",
        "script_name": "risk_monitor",
        "expected_outputs": ("risk_state.csv", "risk_log.csv"),
        "notes": ("Risk warning threshold monitor.",),
    },
)

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


def refresh_cffex_member_rank(
    *,
    duckdb_path: str | Path,
    trade_date: str | None,
    contracts: tuple[str, ...],
    sources: tuple[str, ...],
) -> MacroToolkitActionResult:
    payload = materialize_cffex_member_rank(
        duckdb_path=duckdb_path,
        trade_date=trade_date,
        contracts=contracts,
        sources=sources,
    )
    return MacroToolkitActionResult(
        payload=payload,
        quality_flag="ok" if int(payload.get("row_count") or 0) > 0 else "warning",
        fallback_mode="none",
        as_of_date=_optional_text(payload.get("trade_date")),
    )


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
    background_tasks: BackgroundTasks,
    duckdb_path: str,
    catalog_path: str,
    governance_path: str,
    as_of_date: str,
    refresh_history: bool,
    refresh_factors: bool,
    factor_max_stock_count: int | None,
    permission: dict[str, object],
    idempotency_key: str | None = None,
) -> MacroToolkitActionResult:
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
                    idempotency_key=normalized_idempotency_key,
                )
                if existing_idempotent_run is not None:
                    return MacroToolkitActionResult(
                        payload={
                            **_normalize_choice_stock_refresh_record(existing_idempotent_run),
                            "idempotency_replay": True,
                        },
                        quality_flag="ok",
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
                permission=permission,
                idempotency_key=normalized_idempotency_key,
            )
            append_choice_stock_refresh_run(governance_path, queued_payload)
            background_tasks.add_task(
                _run_choice_stock_refresh_job,
                duckdb_path=duckdb_path,
                catalog_path=catalog_path,
                governance_path=governance_path,
                run_id=run_id,
                as_of_date=as_of_date,
                queued_at=queued_at,
                refresh_history=refresh_history,
                refresh_factors=refresh_factors,
                factor_max_stock_count=factor_max_stock_count,
                permission=permission,
                idempotency_key=normalized_idempotency_key,
            )
    except TimeoutError as exc:
        raise MacroToolkitConflictError(
            f"Choice stock refresh already in progress for as_of_date={as_of_date}."
        ) from exc

    return MacroToolkitActionResult(
        payload={**queued_payload, "idempotency_replay": False},
        quality_flag="ok",
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
    history_row_count: int | None = None,
    factor_row_count: int | None = None,
    source_version: object | None = None,
    vendor_version: object | None = None,
    error_message: str | None = None,
    failure_category: str | None = None,
    failure_reason: str | None = None,
    permission: dict[str, object] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, object]:
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
        "created_at": datetime.now(UTC).isoformat(),
        "refresh_history": refresh_history,
        "refresh_factors": refresh_factors,
        "factor_max_stock_count": factor_max_stock_count,
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
        if str(record.get("status") or "") in _CHOICE_STOCK_REFRESH_IN_FLIGHT_STATUSES:
            return record
    return None


def latest_choice_stock_refresh_for_idempotency_key(
    governance_path: str | Path,
    *,
    as_of_date: str,
    refresh_history: bool,
    refresh_factors: bool,
    factor_max_stock_count: int | None,
    idempotency_key: str,
) -> dict[str, object] | None:
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
        "actions": ["history", "factor_snapshot"],
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
    except duckdb.Error:
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


def _commodity_futures_coverage(products: list[dict[str, object]]) -> dict[str, object]:
    available_products = [
        str(item["product_code"])
        for item in products
        if str(item.get("product_code") or "") in DEFAULT_MACRO_COMMODITY_REFRESH_PRODUCTS
        and int(item.get("row_count") or 0) > 0
    ]
    return {
        "target_product_count": len(DEFAULT_MACRO_COMMODITY_REFRESH_PRODUCTS),
        "available_product_count": len(available_products),
        "available_products": available_products,
        "missing_products": [
            product for product in DEFAULT_MACRO_COMMODITY_REFRESH_PRODUCTS if product not in set(available_products)
        ],
        "products": products,
    }


def _commodity_futures_missing_nanhua(status: str) -> dict[str, object]:
    return {
        "status": status,
        "product_code": "NHCI",
        "series_id": "NH0100.NHF",
        "system_series_id": "NHCI.NH",
        "latest_trade_date": None,
        "latest_value": None,
        "row_count": 0,
        "source_version": None,
        "vendor_version": None,
        "rule_version": None,
    }


def _normalize_commodity_trade_date(value: object) -> str | None:
    text = str(value or "").strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    if len(text) >= 10:
        return text[:10]
    return text or None


def _commodity_futures_nanhua_input(conn: duckdb.DuckDBPyConnection) -> dict[str, object]:
    row = conn.execute(
        """
        with normalized as (
          select
            trade_date,
            close_value,
            source_version,
            vendor_version,
            rule_version,
            case
              when regexp_matches(cast(trade_date as varchar), '^[0-9]{8}$')
                then try_strptime(cast(trade_date as varchar), '%Y%m%d')::date
              else try_cast(left(cast(trade_date as varchar), 10) as date)
            end as normalized_trade_date
          from fact_commodity_futures_daily
          where product_code = 'NHCI'
        )
        select trade_date, close_value, count(*) over () as row_count, source_version, vendor_version, rule_version
        from normalized
        order by normalized_trade_date desc nulls last, trade_date desc
        limit 1
        """
    ).fetchone()
    if not row:
        return _commodity_futures_missing_nanhua("missing")
    trade_date, latest_value, row_count, source_version, vendor_version, rule_version = row
    return {
        "status": "hit",
        "product_code": "NHCI",
        "series_id": "NH0100.NHF",
        "system_series_id": "NHCI.NH",
        "latest_trade_date": _normalize_commodity_trade_date(trade_date),
        "latest_value": float(latest_value) if latest_value is not None else None,
        "row_count": int(row_count or 0),
        "source_version": str(source_version) if source_version is not None else None,
        "vendor_version": str(vendor_version) if vendor_version is not None else None,
        "rule_version": str(rule_version) if rule_version is not None else None,
    }


def load_equity_strategy_price_context(duckdb_path: str | Path | None) -> dict[str, object] | None:
    if duckdb_path is None:
        return None
    path = Path(duckdb_path)
    if not path.exists():
        return None
    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error:
        return None
    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        if "choice_stock_daily_observation" not in tables:
            return None
        latest_row = conn.execute(
            """
            select max(try_cast(trade_date as date))
            from choice_stock_daily_observation
            where close_value is not null
              and close_value > 0
            """
        ).fetchone()
        latest_trade_date = latest_row[0] if latest_row else None
        if latest_trade_date is None:
            return None
        start_date = latest_trade_date - timedelta(days=EQUITY_PRICE_LOOKBACK_DAYS)
        frame = conn.execute(
            f"""
            with latest_sample as (
              select stock_code
              from choice_stock_daily_observation
              where try_cast(trade_date as date) = ?
                and close_value is not null
                and close_value > 0
              order by coalesce(amount, 0) desc, stock_code asc
              limit {EQUITY_PRICE_MAX_STOCKS}
            )
            select
              daily.try_cast_date as trade_date,
              daily.stock_code,
              daily.close_value,
              daily.amount,
              daily.pctchange,
              daily.turn,
              daily.amplitude,
              daily.highlimit,
              daily.lowlimit,
              daily.source_version,
              daily.vendor_version
            from (
              select
                try_cast(trade_date as date) as try_cast_date,
                stock_code,
                close_value,
                amount,
                pctchange,
                turn,
                amplitude,
                highlimit,
                lowlimit,
                source_version,
                vendor_version
              from choice_stock_daily_observation
            ) daily
            join latest_sample sample
              on sample.stock_code = daily.stock_code
            where daily.try_cast_date > ?
              and daily.try_cast_date <= ?
              and daily.close_value is not null
              and daily.close_value > 0
            order by daily.try_cast_date asc, daily.stock_code asc
            """,
            [latest_trade_date, start_date, latest_trade_date],
        ).df()
    except duckdb.Error:
        return None
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
    financials = load_equity_strategy_factor_snapshot(path, latest_trade_date.isoformat())
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
    }


def load_equity_strategy_factor_snapshot(
    duckdb_path: Path,
    as_of_date: str,
    stock_codes: list[str] | None = None,
) -> pd.DataFrame | None:
    try:
        conn = duckdb.connect(str(duckdb_path), read_only=True)
    except duckdb.Error:
        return None
    try:
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
    except duckdb.Error:
        return None
    finally:
        conn.close()
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
    except duckdb.Error:
        return None
    try:
        if not _duckdb_table_exists(conn, "choice_stock_daily_observation"):
            return None
        latest_row = conn.execute(
            """
            select max(try_cast(trade_date as date))
            from choice_stock_daily_observation
            where close_value is not null
              and close_value > 0
            """
        ).fetchone()
        latest_trade_date = latest_row[0] if latest_row else None
        if latest_trade_date is None:
            return None
        start_date = latest_trade_date - timedelta(days=A_SHARE_RISK_LOOKBACK_DAYS)
        rows = conn.execute(
            f"""
            with latest_sample as (
              select stock_code
              from choice_stock_daily_observation
              where try_cast(trade_date as date) = ?
                and close_value is not null
                and close_value > 0
              order by coalesce(amount, 0) desc, stock_code asc
              limit {A_SHARE_RISK_MAX_STOCKS}
            )
            select
              daily.try_cast_date as trade_date,
              daily.stock_code,
              daily.open_value,
              daily.high_value,
              daily.low_value,
              daily.close_value,
              daily.amount,
              daily.pctchange,
              daily.turn,
              daily.amplitude,
              daily.tradestatus,
              try_cast(daily.highlimit as double) as highlimit,
              try_cast(daily.lowlimit as double) as lowlimit,
              daily.source_version,
              daily.vendor_version
            from (
              select
                try_cast(trade_date as date) as try_cast_date,
                stock_code,
                open_value,
                high_value,
                low_value,
                close_value,
                amount,
                pctchange,
                turn,
                amplitude,
                tradestatus,
                highlimit,
                lowlimit,
                source_version,
                vendor_version
              from choice_stock_daily_observation
            ) daily
            join latest_sample sample
              on sample.stock_code = daily.stock_code
            where daily.try_cast_date > ?
              and daily.try_cast_date <= ?
              and daily.close_value is not null
              and daily.close_value > 0
            order by daily.try_cast_date asc, daily.stock_code asc
            """,
            [latest_trade_date, start_date, latest_trade_date],
        ).fetchall()
        if not rows:
            return None
        observations = pd.DataFrame(
            rows,
            columns=[
                "trade_date",
                "stock_code",
                "open_value",
                "high_value",
                "low_value",
                "close_value",
                "amount",
                "pctchange",
                "turn",
                "amplitude",
                "tradestatus",
                "highlimit",
                "lowlimit",
                "source_version",
                "vendor_version",
            ],
        )
        tables_used = ["choice_stock_daily_observation"]
        warnings: list[str] = []
        _merge_a_share_universe(conn, observations, latest_trade_date, tables_used, warnings)
        _merge_a_share_limit_quality(conn, observations, latest_trade_date, tables_used)
        theme_frame = _load_a_share_theme_frame(conn, latest_trade_date, tables_used)
    except duckdb.Error:
        return None
    finally:
        conn.close()
    return {
        "observations": observations,
        "theme_frame": theme_frame,
        "tables_used": tables_used,
        "warnings": warnings,
    }


def load_macro_curve_rows(duckdb_path: str | Path, report_date: date) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    path = Path(duckdb_path)
    if path.exists():
        try:
            conn = duckdb.connect(str(path), read_only=True)
        except duckdb.Error:
            conn = None
        if conn is not None:
            try:
                if _duckdb_table_exists(conn, "fact_formal_yield_curve_daily"):
                    formal_rows = conn.execute(
                        """
                        select
                          cast(trade_date as varchar) as biz_date,
                          lower(curve_type) as curve_type,
                          tenor,
                          cast(rate_pct as double) as rate_value
                        from fact_formal_yield_curve_daily
                        where try_cast(trade_date as date) <= ?
                        """,
                        [report_date],
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
            finally:
                conn.close()

    for alias, curve_id, tenor in _CURVE_ALIAS_POINTS:
        frame = load_series_by_alias(alias, end=report_date.isoformat(), duckdb_path=duckdb_path)
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
    except duckdb.Error:
        return None
    try:
        if not _duckdb_table_exists(conn, "fact_formal_risk_tensor_daily"):
            return None
        frame = conn.execute(
            """
            select *
            from fact_formal_risk_tensor_daily
            where try_cast(report_date as date) <= ?
            order by try_cast(report_date as date) desc
            limit 1
            """,
            [report_date],
        ).fetchdf()
    finally:
        conn.close()
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
    except duckdb.Error:
        return []
    try:
        if not _duckdb_table_exists(conn, "fact_formal_bond_analytics_daily"):
            return []
        frame = conn.execute(
            """
            with latest as (
              select max(try_cast(report_date as date)) as report_date
              from fact_formal_bond_analytics_daily
              where try_cast(report_date as date) <= ?
            )
            select
              cast(market_value as double) as market_value,
              maturity_date,
              cast(coupon_rate as double) as coupon_rate
            from fact_formal_bond_analytics_daily, latest
            where try_cast(fact_formal_bond_analytics_daily.report_date as date) = latest.report_date
              and coalesce(cast(market_value as double), 0) > 0
            limit 5000
            """,
            [report_date],
        ).fetchdf()
    finally:
        conn.close()
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
        except duckdb.Error:
            pass
    return date.today().isoformat()


def _run_choice_stock_refresh_job(
    *,
    duckdb_path: str,
    catalog_path: str,
    governance_path: str,
    run_id: str,
    as_of_date: str,
    queued_at: str,
    refresh_history: bool,
    refresh_factors: bool,
    factor_max_stock_count: int | None,
    permission: dict[str, object],
    idempotency_key: str | None = None,
) -> None:
    normalized_idempotency_key = _normalize_idempotency_key(idempotency_key)
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
            permission=permission,
            idempotency_key=normalized_idempotency_key,
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
                history_row_count=_result_row_count(history_result),
                factor_row_count=_result_row_count(factor_result),
                source_version=_latest_result_field("source_version", factor_result, history_result),
                vendor_version=_latest_result_field("vendor_version", factor_result, history_result),
                permission=permission,
                idempotency_key=normalized_idempotency_key,
            ),
        )
    except Exception as exc:
        append_choice_stock_refresh_run(
            governance_path,
            build_choice_stock_refresh_run_payload(
                run_id=run_id,
                status="failed",
                as_of_date=as_of_date,
                queued_at=queued_at,
                started_at=started_at,
                finished_at=datetime.now(UTC).isoformat(),
                refresh_history=refresh_history,
                refresh_factors=refresh_factors,
                factor_max_stock_count=factor_max_stock_count,
                history_row_count=_result_row_count(history_result),
                factor_row_count=_result_row_count(factor_result),
                source_version=_latest_result_field("source_version", factor_result, history_result),
                vendor_version=_latest_result_field("vendor_version", factor_result, history_result),
                error_message=f"{type(exc).__name__}: {exc}",
                failure_category=type(exc).__name__,
                failure_reason=str(exc),
                permission=permission,
                idempotency_key=normalized_idempotency_key,
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


def _macro_readiness_degraded_reason(
    *,
    readiness: str,
    script_available: bool,
    missing_outputs: list[str],
    stale_outputs: list[str],
    degraded_outputs: list[str],
) -> str | None:
    if not script_available:
        return "script_unavailable"
    if missing_outputs:
        return "missing_expected_outputs"
    if stale_outputs:
        return "stale_expected_outputs"
    if degraded_outputs:
        return "indeterminate_output_dates"
    if readiness == "registered_only":
        return "no_expected_outputs_registered"
    return None


def _macro_readiness_evidence_level(*, readiness: str, present_count: int) -> str:
    if readiness == "artifact_backed":
        return "fresh_artifacts"
    if present_count:
        return "partial_artifacts"
    return "registered_script_only"


def _macro_readiness_date_basis(outputs: list[dict[str, object]]) -> str:
    statuses = {str(item["freshness_status"]) for item in outputs}
    if not outputs or statuses == {"missing"}:
        return "missing"
    bases = {
        str(item["freshness_basis"])
        for item in outputs
        if item.get("freshness_basis") and item["freshness_status"] != "missing"
    }
    if "csv_content" in bases:
        return "csv_content"
    if "file_modified_date" in bases:
        return "file_modified_date"
    return "unknown"


def _macro_artifact_receipt(
    *,
    model_id: str,
    script_name: str,
    readiness: str,
    outputs: list[dict[str, object]],
    degraded_reason: str | None,
    data_asof: str | None,
) -> dict[str, object]:
    return {
        "status": readiness,
        "model_id": model_id,
        "script_name": script_name,
        "artifact_paths": sorted(str(item["name"]) for item in outputs if item["freshness_status"] != "missing"),
        "missing_artifacts": sorted(str(item["name"]) for item in outputs if item["freshness_status"] == "missing"),
        "degraded_reason": degraded_reason,
        "data_asof": data_asof,
        "generated_at": datetime.now(UTC).isoformat(),
        "runtime_endpoint": MACRO_TOOLKIT_RUN_CHAIN_ENDPOINT,
        "page_surface": MACRO_TOOLKIT_MODEL_READINESS_SURFACE,
        "formal_use_allowed": MACRO_TOOLKIT_FORMAL_USE_ALLOWED,
        "observation_only": MACRO_TOOLKIT_OBSERVATION_ONLY,
    }


def _macro_output_health(
    name: str,
    file_payload: dict[str, object] | None,
    *,
    reference_date: str | None,
) -> dict[str, object]:
    if file_payload is None:
        return {
            "name": name,
            "freshness_status": "missing",
            "freshness_basis": "missing",
            "modified_at": None,
            "modified_date": None,
            "content_date": None,
            "content_date_min": None,
            "content_date_max": None,
            "content_date_invalid_count": 0,
            "reference_date": reference_date,
        }
    modified_at = str(file_payload.get("modified_at") or "").strip() or None
    modified_date = _macro_output_modified_date(modified_at)
    content_dates = _macro_output_content_dates(file_payload)
    content_date = content_dates["max"]
    content_date_min = content_dates["min"]
    content_date_max = content_dates["max"]
    content_date_invalid_count = int(content_dates["invalid_count"] or 0)
    has_content_date_column = bool(content_dates["date_column"])
    freshness_basis = "csv_content" if has_content_date_column else "file_modified_date"
    freshness_status = _macro_output_health_status(
        name=name,
        content_date=content_date,
        content_date_min=content_date_min,
        content_date_max=content_date_max,
        content_date_invalid_count=content_date_invalid_count,
        has_content_date_column=has_content_date_column,
        modified_date=modified_date,
        reference_date=reference_date,
    )
    return {
        "name": name,
        "freshness_status": freshness_status,
        "freshness_basis": freshness_basis,
        "modified_at": modified_at,
        "modified_date": modified_date,
        "content_date": content_date,
        "content_date_min": content_date_min,
        "content_date_max": content_date_max,
        "content_date_invalid_count": content_date_invalid_count,
        "reference_date": reference_date,
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


def _macro_output_modified_date(modified_at: str | None) -> str | None:
    if not modified_at:
        return None
    try:
        parsed = datetime.fromisoformat(modified_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.date().isoformat()
    return parsed.astimezone(UTC).date().isoformat()


def _macro_output_content_dates(file_payload: dict[str, object]) -> dict[str, str | int | None]:
    path_value = file_payload.get("path")
    if not path_value:
        return {"min": None, "max": None, "invalid_count": 0, "date_column": None}
    path = Path(str(path_value))
    if not path.is_file():
        return {"min": None, "max": None, "invalid_count": 0, "date_column": None}
    try:
        columns = pd.read_csv(path, nrows=0).columns
        date_column = next((column for column in MACRO_TOOLKIT_OUTPUT_DATE_COLUMNS if column in columns), None)
        if date_column is None:
            return {"min": None, "max": None, "invalid_count": 0, "date_column": None}
        frame = pd.read_csv(path, usecols=[date_column])
    except (OSError, UnicodeError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return {"min": None, "max": None, "invalid_count": 0, "date_column": None}
    if frame.empty:
        return {"min": None, "max": None, "invalid_count": 0, "date_column": date_column}
    raw_dates = frame[date_column].dropna()
    parsed = pd.to_datetime(raw_dates, errors="coerce")
    invalid_count = int(parsed.isna().sum())
    parsed = parsed.dropna()
    if parsed.empty:
        return {"min": None, "max": None, "invalid_count": invalid_count, "date_column": date_column}
    return {
        "min": parsed.min().date().isoformat(),
        "max": parsed.max().date().isoformat(),
        "invalid_count": invalid_count,
        "date_column": date_column,
    }


def _macro_output_health_status(
    *,
    name: str,
    content_date: str | None,
    content_date_min: str | None,
    content_date_max: str | None,
    content_date_invalid_count: int,
    has_content_date_column: bool,
    modified_date: str | None,
    reference_date: str | None,
) -> str:
    if content_date_invalid_count:
        return "invalid_date"
    if has_content_date_column and not content_date:
        return "unknown"
    if _is_generation_evidence_artifact(name):
        return _macro_generation_freshness(content_date or modified_date, reference_date)
    if content_date_min and content_date_max and content_date_min != content_date_max:
        if _is_history_artifact(name):
            return _macro_output_freshness(content_date, reference_date)
        return "mixed"
    if has_content_date_column:
        return _macro_output_freshness(content_date, reference_date)
    return _macro_generation_freshness(modified_date, reference_date)


def _is_history_artifact(name: str) -> bool:
    stem = Path(name).stem.lower()
    return stem.endswith("_history") or stem.endswith("_results") or stem.endswith("_log")


def _is_generation_evidence_artifact(name: str) -> bool:
    return Path(name).name.lower() in {"risk_state.csv", "risk_log.csv"}


def _macro_output_freshness(output_date: str | None, reference_date: str | None) -> str:
    if not output_date:
        return "unknown"
    if not reference_date:
        return "present"
    try:
        output_day = date.fromisoformat(output_date[:10])
        reference_day = date.fromisoformat(reference_date[:10])
    except ValueError:
        return "unknown"
    if output_day > reference_day:
        return "future"
    return "current" if output_day == reference_day else "stale"


def _macro_generation_freshness(modified_date: str | None, reference_date: str | None) -> str:
    status = _macro_output_freshness(modified_date, reference_date)
    return "current" if status == "future" else status


def _macro_run_manifest() -> list[dict[str, object]]:
    labels_by_script = {
        "merrill_clock_cn": "Merrill Clock",
        "crisis_score_cn": "Crisis Score",
        "bond_futures_data": "Bond Futures Basis / IRR / Safety Margin",
        "bond_futures_signals": "Bond Futures Four-Factor Trend",
        "crowding_cn": "Crowding",
        "dcc_garch_cn": "DCC-GARCH",
        "cta_trend_cn": "CTA Trend",
        "signal_aggregator": "Final Signal Aggregator",
        "risk_monitor": "Risk Monitor",
    }
    outputs_by_script: dict[str, list[str]] = {}
    for model in _MACRO_MODEL_DEFINITIONS:
        script_name = str(model["script_name"])
        outputs_by_script.setdefault(script_name, [])
        outputs_by_script[script_name].extend(str(name) for name in model["expected_outputs"])
    ordered_scripts = (
        "merrill_clock_cn",
        "crisis_score_cn",
        "bond_futures_data",
        "bond_futures_signals",
        "crowding_cn",
        "dcc_garch_cn",
        "cta_trend_cn",
        "signal_aggregator",
        "risk_monitor",
    )
    registry = {script.name: script for script in iter_toolkit_scripts()}
    manifest: list[dict[str, object]] = []
    for order, script_name in enumerate(ordered_scripts, start=1):
        script = registry[script_name]
        manifest.append(
            {
                "order": order,
                "script_name": script_name,
                "label": labels_by_script[script_name],
                "expected_outputs": sorted(set(outputs_by_script.get(script_name, []))),
                "available": script.path.exists(),
            }
        )
    return manifest


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


def _macro_run_degraded_reason(*, status: str, missing_outputs: list[str]) -> str | None:
    if status != "completed":
        return "script_execution_not_completed"
    if missing_outputs:
        return "missing_expected_outputs_after_run"
    return None


def _macro_run_blocker(
    *,
    degraded_reason: str | None,
    script_name: str,
    missing_outputs: list[str],
) -> dict[str, object] | None:
    if degraded_reason != "missing_expected_outputs_after_run":
        return None
    return {
        "type": degraded_reason,
        "script_name": script_name,
        "missing_outputs": missing_outputs,
    }


def _macro_run_data_asof(*, expected_outputs: list[str], outputs: list[dict[str, object]]) -> str | None:
    files_by_name = {str(item["name"]): item for item in outputs}
    content_dates: list[str] = []
    for name in expected_outputs:
        content_date = _macro_output_health(name, files_by_name.get(name), reference_date=None).get("content_date")
        if content_date:
            content_dates.append(str(content_date))
    return max(content_dates, default=None)


def _missing_expected_outputs(step: dict[str, object], *, output_dir: str | Path) -> list[str]:
    output_names = {str(item["name"]) for item in output_files(output_dir)}
    return [str(name) for name in step.get("expected_outputs") or [] if str(name) not in output_names]


def _tail_text(value: str | bytes | None, limit: int = 12000) -> str:
    if value is None:
        return ""
    text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
    return text[-limit:]


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


def _normalize_choice_stock_refresh_record(record: dict[str, object]) -> dict[str, object]:
    normalized = dict(record)
    normalized["trigger_mode"] = _choice_stock_refresh_trigger_mode(str(normalized.get("status") or ""))
    normalized.setdefault("permission", build_choice_stock_refresh_permission_payload())
    return normalized


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
    except duckdb.Error:
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
    except duckdb.Error:
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
    except duckdb.Error:
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


def _choice_stock_daily_observation_status_with_freshness(
    status: dict[str, object],
    *,
    reference_date: str | None = None,
) -> dict[str, object]:
    latest_trade_date = str(status.get("latest_trade_date") or "")[:10] or None
    return {
        **status,
        **_choice_stock_table_freshness(latest_trade_date, reference_date),
    }


def _choice_stock_factor_snapshot_status_with_freshness(
    status: dict[str, object],
    *,
    reference_date: str | None = None,
) -> dict[str, object]:
    as_of_date = str(status.get("as_of_date") or "")[:10] or None
    return {
        **status,
        **_choice_stock_table_freshness(as_of_date, reference_date),
    }


def _choice_stock_base_table_status(status: str) -> dict[str, object]:
    return {
        "materialized": False,
        "status": status,
        "row_count": 0,
        "stock_count": 0,
    }


def _choice_stock_table_status(status: str, *, reference_date: str | None = None) -> dict[str, object]:
    return {
        **_choice_stock_base_table_status(status),
        **_choice_stock_table_freshness(None, reference_date),
    }


def _choice_stock_table_freshness(data_date: str | None, reference_date: str | None) -> dict[str, object]:
    if not data_date:
        return {
            "freshness_status": "missing",
            "reference_date": reference_date,
            "stale_days": None,
            "fallback_mode": "missing",
            "fallback_date": None,
        }
    if not reference_date:
        return {
            "freshness_status": "unknown",
            "reference_date": None,
            "stale_days": None,
            "fallback_mode": "unknown",
            "fallback_date": None,
        }
    try:
        data_day = date.fromisoformat(data_date[:10])
        reference_day = date.fromisoformat(reference_date[:10])
    except ValueError:
        return {
            "freshness_status": "unknown",
            "reference_date": reference_date,
            "stale_days": None,
            "fallback_mode": "unknown",
            "fallback_date": None,
        }
    raw_stale_days = (reference_day - data_day).days
    stale_days = max(raw_stale_days, 0)
    if raw_stale_days <= 1:
        status = "current"
    elif raw_stale_days <= 7:
        status = "lagging"
    else:
        status = "stale"
    fallback_mode = "none" if status == "current" else "latest_available"
    return {
        "freshness_status": status,
        "reference_date": reference_day.isoformat(),
        "stale_days": stale_days,
        "fallback_mode": fallback_mode,
        "fallback_date": data_day.isoformat() if fallback_mode == "latest_available" else None,
    }


def _result_row_count(result: dict[str, object] | None) -> int | None:
    if not result:
        return None
    value = result.get("row_count")
    return None if value is None else int(value)


def _latest_result_field(field_name: str, *results: dict[str, object] | None) -> object | None:
    for result in results:
        if result and result.get(field_name):
            return result[field_name]
    return None


def _optional_text(value: object | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def _normalize_idempotency_key(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def _optional_int(value: object | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _int_or_zero(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def _coerce_frame_date(value: object) -> date | None:
    if value is None:
        return None
    if pd.isna(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if hasattr(value, "date"):
        try:
            return value.date()
        except (AttributeError, TypeError, ValueError):
            return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _unique_texts(values: list[object]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


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
    except duckdb.Error:
        return False
    return bool(row and row[0])
