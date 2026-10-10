"""Automated rerun of the macro toolkit "allocation / regime" script family.

The scripts under ``backend/app/core_finance/macro/toolkit/scripts`` are
currently rerun by hand through ``toolkit/runner.py``. This task wraps the
already-tested subprocess runner in
``backend.app.services.macro_toolkit_service`` so the "allocation" group
(risk parity / performance / rebalance / regime / backtest / CTA / DCC-GARCH
/ crowding / equity strategies / multi-asset GARCH) can be rerun as a single
fault-tolerant batch: one script failing never blocks the rest.

The CSI500-dependent scripts probe ``sh000905`` in the system source tables
before launch. If the source is still missing or too short, the step is
recorded as ``blocked`` for that run; once the ingest task lands CSI500 history
the same step definition executes normally.

This module still does not write to DuckDB; the toolkit scripts only produce
CSV / PNG files under ``data/macro_toolkit/output`` (or
``MOSS_MACRO_TOOLKIT_OUTPUT_DIR``). To make those file outputs reviewable
without formalizing them, each terminal run now publishes a minimal
``run_manifest.json`` inside ``_allocation_refresh_runs/<run_id>/`` and then
atomically updates ``_allocation_refresh_runs/latest_manifest.json`` only after
the final manifest is readable. The published manifest/pointer remain
observation-only evidence (`formal_use_allowed = false`).
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import SupportsIndex, SupportsInt, cast

from backend.app.core_finance.macro.toolkit.paths import OUTPUT_DIR
from backend.app.core_finance.macro.toolkit.system_sources import load_series_by_alias
from backend.app.governance.locks import acquire_lock
from backend.app.services.macro_toolkit_service import (
    MACRO_TOOLKIT_CHAIN_LOCK,
    _run_macro_toolkit_script_unlocked,
)
from backend.app.tasks.broker import register_actor_once

logger = logging.getLogger(__name__)

SOURCE_VERSION = "macro_toolkit_allocation_refresh_v1"
DEFAULT_TIMEOUT_SECONDS = 180
CSI500_MIN_OBSERVATIONS = 100
LATEST_MANIFEST_POINTER_NAME = "latest_manifest.json"
CURRENT_RUN_POINTER_NAME = LATEST_MANIFEST_POINTER_NAME
MACRO_TOOLKIT_ALLOCATION_REFRESH_LOCK = MACRO_TOOLKIT_CHAIN_LOCK


def _should_invalidate_allocation_refresh_caches(
    artifact_snapshot: dict[str, object],
) -> bool:
    return (
        str(artifact_snapshot.get("latest_pointer_status") or "") == "published"
        and (
            _payload_int(artifact_snapshot.get("copied_file_count")) > 0
            or bool(artifact_snapshot.get("cache_semantics_changed"))
        )
    )


def _payload_int(value: object) -> int:
    return int(cast(SupportsInt | SupportsIndex | str | bytes | bytearray, value or 0))


def _payload_entries(value: object) -> Iterable[object]:
    return cast(Iterable[object], value or [])


def _invalidate_allocation_refresh_caches() -> None:
    from backend.app.observability.response_cache import market_home_response_cache

    market_home_response_cache.invalidate()


class MacroToolkitRefreshConflictError(RuntimeError):
    """Raised when another allocation-refresh run already holds the lock."""


@dataclass(frozen=True, slots=True)
class RequiredSystemSeries:
    alias: str
    label: str
    min_observations: int


CSI500_REQUIREMENT = RequiredSystemSeries(
    alias="sh000905",
    label="CSI500",
    min_observations=CSI500_MIN_OBSERVATIONS,
)


@dataclass(frozen=True, slots=True)
class MacroToolkitRefreshStep:
    script_name: str
    label: str
    expected_outputs: tuple[str, ...] = ()
    required_aliases: tuple[RequiredSystemSeries, ...] = ()


# Order encodes the producer/consumer relationship: risk_parity_cn produces
# risk_parity_results.csv before its consumers (performance_metrics_cn,
# rebalance_cn). CSI500-dependent steps probe source readiness at runtime.
STEPS: tuple[MacroToolkitRefreshStep, ...] = (
    MacroToolkitRefreshStep(
        script_name="risk_parity_cn",
        label="风险平价 + 风险预算",
        expected_outputs=("risk_parity_results.csv", "risk_parity.png"),
        required_aliases=(CSI500_REQUIREMENT,),
    ),
    MacroToolkitRefreshStep(
        script_name="performance_metrics_cn",
        label="绩效评估（夏普 / 索提诺）",
        expected_outputs=("performance_results.csv", "performance.png"),
    ),
    MacroToolkitRefreshStep(
        script_name="rebalance_cn",
        label="再平衡策略（时间 / 阈值触发）",
        expected_outputs=("rebalance_results.csv", "rebalance_comparison.png", "weight_drift.png"),
    ),
    MacroToolkitRefreshStep(
        script_name="regime_switch_cn",
        label="市场状态转换模型",
        expected_outputs=(
            "regime_results.csv",
            "regime_overview.png",
            "regime_distribution.png",
            "hurst_timeseries.png",
        ),
    ),
    MacroToolkitRefreshStep(
        script_name="backtest_cn",
        label="全策略综合回测",
        expected_outputs=(
            "backtest_results.csv",
            "backtest_annual.csv",
            "backtest_run_manifest.json",
            "backtest_nav.png",
            "backtest_annual.png",
            "backtest_metrics.png",
        ),
        required_aliases=(CSI500_REQUIREMENT,),
    ),
    MacroToolkitRefreshStep(
        script_name="cta_trend_cn",
        label="CTA 趋势跟踪（均线 + 唐奇安 + ATR）",
        expected_outputs=("cta_results.csv", "cta_signals.png"),
    ),
    MacroToolkitRefreshStep(
        script_name="dcc_garch_cn",
        label="DCC-GARCH 动态相关",
        expected_outputs=("dcc_latest.csv", "dcc_results.csv", "dcc_heatmap.png", "dcc_timeseries.png"),
    ),
    MacroToolkitRefreshStep(
        script_name="crowding_cn",
        label="国债期货拥挤度",
        expected_outputs=("crowding_latest.csv", "crowding_history.csv"),
    ),
    MacroToolkitRefreshStep(
        script_name="equity_strategies",
        label="权益选股策略（合成数据自检，无系统源依赖）",
        expected_outputs=(),
    ),
    MacroToolkitRefreshStep(
        script_name="garch_multi_asset",
        label="多资产 GARCH 波动率估计",
        expected_outputs=(),
        required_aliases=(CSI500_REQUIREMENT,),
    ),
)


def run_macro_toolkit_allocation_refresh(
    *,
    output_dir: str | Path = OUTPUT_DIR,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    governance_path: str | Path | None = None,
) -> dict[str, object]:
    """Rerun every step in ``STEPS`` in order and return a structured report.

    A single script failing never stops the remaining steps. Steps whose
    ``required_aliases`` are not ready are recorded as ``status: "blocked"``
    without being executed. Concurrent runs are serialized by a short-lived
    file lock so repeated/overlapping triggers are safe (the underlying toolkit
    scripts overwrite their own CSV/PNG outputs in place).
    """
    resolved_output_dir = Path(output_dir).resolve()
    run_id = f"macro_toolkit_allocation_refresh:{uuid.uuid4().hex[:12]}"
    started_at = datetime.now(UTC).isoformat()
    run_started = time.monotonic()

    try:
        with acquire_lock(
            MACRO_TOOLKIT_ALLOCATION_REFRESH_LOCK,
            base_dir=resolved_output_dir,
            timeout_seconds=0.1,
        ):
            results = [
                _run_step(step, output_dir=resolved_output_dir, timeout_seconds=timeout_seconds) for step in STEPS
            ]
            finished_at = datetime.now(UTC).isoformat()
            status_counts: dict[str, int] = {}
            for result in results:
                status = str(result["status"])
                status_counts[status] = status_counts.get(status, 0) + 1
            artifact_snapshot = _capture_run_artifact_snapshot(
                run_id=run_id,
                output_dir=resolved_output_dir,
                results=results,
                started_at=started_at,
                finished_at=finished_at,
                timeout_seconds=timeout_seconds,
                status_counts=status_counts,
            )
    except TimeoutError as exc:
        raise MacroToolkitRefreshConflictError(
            "Macro toolkit allocation refresh is already in progress."
        ) from exc

    if _should_invalidate_allocation_refresh_caches(artifact_snapshot):
        _invalidate_allocation_refresh_caches()

    return {
        "run_id": run_id,
        "source_version": SOURCE_VERSION,
        "status": "completed",
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": round(time.monotonic() - run_started, 3),
        "timeout_seconds": timeout_seconds,
        "output_dir": str(resolved_output_dir),
        "step_count": len(results),
        "status_counts": status_counts,
        "artifact_snapshot": artifact_snapshot,
        "results": results,
    }


def _run_step(
    step: MacroToolkitRefreshStep,
    *,
    output_dir: Path,
    timeout_seconds: int,
) -> dict[str, object]:
    missing_required_aliases = _missing_required_aliases(step)
    if missing_required_aliases:
        return {
            "script_name": step.script_name,
            "label": step.label,
            "status": "blocked",
            "reason": _required_alias_block_reason(missing_required_aliases),
            "exit_code": None,
            "duration_seconds": 0.0,
            "expected_outputs": list(step.expected_outputs),
            "produced_outputs": [],
            "unchanged_outputs": [],
            "missing_expected_outputs": list(step.expected_outputs),
            "artifact_status": "partial" if step.expected_outputs else "not_applicable",
        }

    expected_output_fingerprints = {
        name: _artifact_fingerprint(output_dir / name) for name in step.expected_outputs
    }
    start = time.monotonic()
    try:
        result = _run_macro_toolkit_script_unlocked(
            name=step.script_name,
            argv=[],
            timeout_seconds=timeout_seconds,
            output_dir=output_dir,
        )
    except (Exception, SystemExit) as exc:  # noqa: BLE001 - one script must never abort the batch
        logger.exception(
            "macro toolkit allocation refresh: script launch failed script=%s",
            step.script_name,
        )
        return {
            "script_name": step.script_name,
            "label": step.label,
            "status": "failed",
            "reason": f"unexpected launch error: {exc}",
            "exit_code": None,
            "duration_seconds": round(time.monotonic() - start, 3),
            "expected_outputs": list(step.expected_outputs),
            "produced_outputs": [],
            "unchanged_outputs": [],
            "missing_expected_outputs": list(step.expected_outputs),
            "artifact_status": "partial" if step.expected_outputs else "not_applicable",
        }
    duration_seconds = round(time.monotonic() - start, 3)

    status = "success" if result.get("status") == "completed" else "failed"
    output_files = _payload_entries(result.get("output_files"))
    output_file_entries = {
        str(entry.get("name")): entry
        for entry in output_files
        if isinstance(entry, dict) and str(entry.get("name") or "").strip()
    }
    produced_outputs: list[dict[str, object]] = []
    unchanged_outputs: list[dict[str, object]] = []
    missing_expected_outputs: list[str] = []
    for expected_name in step.expected_outputs:
        entry = output_file_entries.get(expected_name)
        resolved_path = _resolve_output_path(
            output_dir=output_dir,
            name=expected_name,
            path_text=str(entry.get("path") or "").strip() if isinstance(entry, dict) else None,
        )
        after = _artifact_fingerprint(resolved_path)
        before = expected_output_fingerprints.get(expected_name)
        if after is None:
            missing_expected_outputs.append(expected_name)
            continue
        artifact_payload = {
            "name": expected_name,
            "path": str(resolved_path),
            "size_bytes": after["size_bytes"],
            "modified_at": after["modified_at"],
            "sha256": after["sha256"],
        }
        if before is not None and before == after:
            unchanged_outputs.append(artifact_payload)
            continue
        produced_outputs.append(artifact_payload)
    artifact_status = (
        "not_applicable"
        if not step.expected_outputs
        else "partial"
        if missing_expected_outputs or unchanged_outputs
        else "complete"
    )
    return {
        "script_name": step.script_name,
        "label": step.label,
        "status": status,
        "reason": None if status == "success" else _failure_reason(result),
        "exit_code": result.get("exit_code"),
        "duration_seconds": duration_seconds,
        "expected_outputs": list(step.expected_outputs),
        "produced_outputs": produced_outputs,
        "unchanged_outputs": unchanged_outputs,
        "missing_expected_outputs": missing_expected_outputs,
        "artifact_status": artifact_status,
        "stdout_tail": result.get("stdout", ""),
        "stderr_tail": result.get("stderr", ""),
    }


def _missing_required_aliases(step: MacroToolkitRefreshStep) -> list[dict[str, object]]:
    missing: list[dict[str, object]] = []
    for requirement in step.required_aliases:
        try:
            observed = len(load_series_by_alias(requirement.alias))
        except Exception as exc:  # noqa: BLE001 - preflight failures should block only this step
            missing.append(
                {
                    "alias": requirement.alias,
                    "label": requirement.label,
                    "observed": 0,
                    "required": requirement.min_observations,
                    "error": str(exc),
                }
            )
            continue
        if observed < requirement.min_observations:
            missing.append(
                {
                    "alias": requirement.alias,
                    "label": requirement.label,
                    "observed": observed,
                    "required": requirement.min_observations,
                    "error": None,
                }
            )
    return missing


def _required_alias_block_reason(missing_required_aliases: list[dict[str, object]]) -> str:
    details = []
    for item in missing_required_aliases:
        detail = (
            f"{item['label']}({item['alias']}) has {item['observed']} observations; "
            f"requires at least {item['required']}"
        )
        if item.get("error"):
            detail += f"; probe_error={item['error']}"
        details.append(detail)
    return "System-source data preflight blocked this script: " + "; ".join(details)


def _failure_reason(result: dict[str, object]) -> str:
    status = str(result.get("status") or "unknown")
    if status == "timeout":
        return str(result.get("message") or "script exceeded timeout")
    stderr = str(result.get("stderr") or "").strip()
    if stderr:
        return stderr.splitlines()[-1][:500]
    return f"script exited with status={status}"


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_json_payload(payload: object) -> str:
    digest = sha256()
    digest.update(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    return digest.hexdigest()


def _path_posix_relative(path: Path, base: Path) -> str:
    return str(path.relative_to(base)).replace("\\", "/")


def _artifact_fingerprint(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    stats = path.stat()
    return {
        "size_bytes": int(stats.st_size),
        "modified_at_ns": int(stats.st_mtime_ns),
        "modified_at": datetime.fromtimestamp(stats.st_mtime, UTC).isoformat(),
        "sha256": _sha256_file(path),
    }


def _resolve_output_path(*, output_dir: Path, name: str, path_text: str | None) -> Path:
    del path_text
    return output_dir / name


def _artifact_manifest_entry(*, path: Path, run_root: Path) -> dict[str, object]:
    stats = path.stat()
    return {
        "relative_path": _path_posix_relative(path, run_root),
        "size_bytes": int(stats.st_size),
        "sha256": _sha256_file(path),
        "modified_at": datetime.fromtimestamp(stats.st_mtime, UTC).isoformat(),
    }


def _stable_output_names(entries: object) -> list[str]:
    names: list[str] = []
    for entry in _payload_entries(entries):
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        if name:
            names.append(name)
    return sorted(set(names))


def _cache_read_semantics_payload(
    *,
    snapshot_status: str,
    status_counts: dict[str, int],
    missing_files: list[str],
    stale_files: list[str],
    results: list[dict[str, object]],
) -> dict[str, object]:
    normalized_results: list[dict[str, object]] = []
    for result in results:
        normalized_results.append(
            {
                "script_name": str(result.get("script_name") or ""),
                "status": str(result.get("status") or ""),
                "reason": str(result.get("reason") or ""),
                "artifact_status": str(result.get("artifact_status") or ""),
                "expected_outputs": [
                    str(name)
                    for name in _payload_entries(result.get("expected_outputs"))
                    if str(name or "").strip()
                ],
                "missing_expected_outputs": sorted(
                    str(name)
                    for name in _payload_entries(result.get("missing_expected_outputs"))
                    if str(name or "").strip()
                ),
                "produced_outputs": _stable_output_names(result.get("produced_outputs")),
                "unchanged_outputs": _stable_output_names(result.get("unchanged_outputs")),
            }
        )
    return {
        "snapshot_status": snapshot_status,
        "status_counts": {key: int(status_counts[key]) for key in sorted(status_counts)},
        "missing_files": sorted(missing_files),
        "stale_files": sorted(stale_files),
        "results": normalized_results,
    }


def _cache_read_semantics_hash_from_manifest_payload(manifest_payload: dict[str, object]) -> str:
    status_counts = manifest_payload.get("status_counts")
    results = manifest_payload.get("results")
    return _sha256_json_payload(
        _cache_read_semantics_payload(
            snapshot_status=str(manifest_payload.get("status") or ""),
            status_counts=status_counts if isinstance(status_counts, dict) else {},
            missing_files=[
                str(name)
                for name in _payload_entries(manifest_payload.get("missing_files"))
                if str(name or "").strip()
            ],
            stale_files=[
                str(name)
                for name in _payload_entries(manifest_payload.get("stale_files"))
                if str(name or "").strip()
            ],
            results=results if isinstance(results, list) else [],
        )
    )


def _load_latest_pointer_semantics_hash(latest_pointer_path: Path) -> str | None:
    if not latest_pointer_path.is_file():
        return None
    try:
        latest_pointer_payload = json.loads(latest_pointer_path.read_text(encoding="utf-8"))
        manifest_path_text = str(latest_pointer_payload.get("manifest_path") or "").strip()
        if not manifest_path_text:
            return None
        manifest_path = Path(manifest_path_text)
        if not manifest_path.is_file():
            return None
        manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - unreadable previous pointer should invalidate on successful publish
        logger.exception(
            "macro toolkit allocation refresh: failed to load previous latest manifest semantics pointer=%s",
            latest_pointer_path,
        )
        return None
    if not isinstance(manifest_payload, dict):
        return None
    return _cache_read_semantics_hash_from_manifest_payload(manifest_payload)


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    staging_path = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        staging_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(staging_path, path)
    finally:
        if staging_path.exists():
            staging_path.unlink(missing_ok=True)


def _capture_run_artifact_snapshot(
    *,
    run_id: str,
    output_dir: Path,
    results: list[dict[str, object]],
    started_at: str,
    finished_at: str,
    timeout_seconds: int,
    status_counts: dict[str, int],
) -> dict[str, object]:
    runs_root = output_dir / "_allocation_refresh_runs"
    safe_run_dir_name = run_id.replace(":", "__")
    final_dir = runs_root / safe_run_dir_name
    staging_dir = runs_root / f".{safe_run_dir_name}.tmp"
    manifest_path = final_dir / "run_manifest.json"
    latest_pointer_path = runs_root / LATEST_MANIFEST_POINTER_NAME
    copied_files: list[str] = []
    artifacts: list[dict[str, object]] = []
    missing_files: list[str] = []
    stale_files: list[str] = []
    snapshot_status = "captured"
    previous_semantics_hash = _load_latest_pointer_semantics_hash(latest_pointer_path)
    try:
        runs_root.mkdir(parents=True, exist_ok=True)
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        staging_dir.mkdir(parents=True, exist_ok=False)
        for result in results:
            step_name = str(result.get("script_name") or "unknown")
            step_dir = staging_dir / step_name
            step_dir.mkdir(parents=True, exist_ok=True)
            for unchanged in _payload_entries(result.get("unchanged_outputs")):
                if not isinstance(unchanged, dict):
                    continue
                unchanged_name = str(unchanged.get("name") or "").strip()
                if unchanged_name:
                    stale_files.append(f"{step_name}:{unchanged_name}")
            for missing_name in _payload_entries(result.get("missing_expected_outputs")):
                missing_name_text = str(missing_name or "").strip()
                if missing_name_text:
                    missing_files.append(f"{step_name}:{missing_name_text}")
            for produced in _payload_entries(result.get("produced_outputs")):
                if not isinstance(produced, dict):
                    continue
                source_name = str(produced.get("name") or "").strip()
                source_path_text = str(produced.get("path") or "").strip()
                if not source_name:
                    continue
                source_path = Path(source_path_text) if source_path_text else output_dir / source_name
                if not source_path.is_file():
                    fallback_path = output_dir / source_name
                    if fallback_path.is_file():
                        source_path = fallback_path
                    else:
                        missing_tag = f"{step_name}:{source_name}"
                        if missing_tag not in missing_files:
                            missing_files.append(missing_tag)
                        continue
                destination_path = step_dir / source_name
                shutil.copy2(source_path, destination_path)
                relative_path = _path_posix_relative(destination_path, staging_dir)
                copied_files.append(relative_path)
                artifacts.append(_artifact_manifest_entry(path=destination_path, run_root=staging_dir))
        snapshot_status = "captured" if not missing_files and not stale_files else "partial"
        manifest_payload = {
            "schema_version": "macro_toolkit_allocation_refresh_run_manifest.v1",
            "run_id": run_id,
            "source_version": SOURCE_VERSION,
            "status": snapshot_status,
            "observation_only": True,
            "formal_use_allowed": False,
            "started_at": started_at,
            "finished_at": finished_at,
            "timeout_seconds": timeout_seconds,
            "output_dir": str(output_dir),
            "status_counts": status_counts,
            "artifact_count": len(artifacts),
            "artifacts": artifacts,
            "copied_files": copied_files,
            "missing_files": missing_files,
            "stale_files": stale_files,
            "results": results,
        }
        current_semantics_hash = _cache_read_semantics_hash_from_manifest_payload(manifest_payload)
        staging_manifest_path = staging_dir / "run_manifest.json"
        staging_manifest_path.write_text(
            json.dumps(manifest_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if final_dir.exists():
            shutil.rmtree(final_dir)
        staging_dir.replace(final_dir)
    except Exception as exc:  # noqa: BLE001 - snapshot failure must not mask the refresh result
        logger.exception("macro toolkit allocation refresh: failed to capture run snapshot run_id=%s", run_id)
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
        return {
            "status": "unavailable",
            "run_dir": None,
            "manifest_path": None,
            "manifest_sha256": None,
            "run_status": "completed",
            "snapshot_status": "unavailable",
            "latest_pointer_status": "unavailable",
            "latest_pointer_path": None,
            "latest_pointer_sha256": None,
            "current_pointer_path": None,
            "copied_file_count": 0,
            "artifact_count": 0,
            "missing_files": missing_files,
            "stale_files": stale_files,
            "reason": str(exc),
        }

    manifest_sha256 = _sha256_file(manifest_path)
    latest_pointer_status = "published"
    latest_pointer_sha256: str | None = None
    snapshot_reason: str | None = None
    cache_semantics_changed = current_semantics_hash != previous_semantics_hash
    try:
        latest_pointer_sha256 = _publish_current_run_pointer(
            latest_pointer_path,
            run_id=run_id,
            run_dir=final_dir,
            manifest_path=manifest_path,
            manifest_sha256=manifest_sha256,
            source_version=SOURCE_VERSION,
            finished_at=finished_at,
            runs_root=runs_root,
            run_status="completed",
            snapshot_status=snapshot_status,
        )
    except Exception as exc:  # noqa: BLE001 - preserve the previous latest pointer on publish failure
        latest_pointer_status = "unchanged"
        snapshot_reason = f"latest pointer publish failed: {exc}"
        logger.exception(
            "macro toolkit allocation refresh: failed to publish latest manifest pointer run_id=%s",
            run_id,
        )
    return {
        "status": snapshot_status,
        "run_dir": str(final_dir),
        "manifest_path": str(manifest_path),
        "manifest_sha256": manifest_sha256,
        "run_status": "completed",
        "snapshot_status": snapshot_status,
        "latest_pointer_status": latest_pointer_status,
        "latest_pointer_path": str(latest_pointer_path),
        "latest_pointer_sha256": latest_pointer_sha256,
        "current_pointer_path": str(latest_pointer_path),
        "copied_file_count": len(copied_files),
        "cache_semantics_changed": cache_semantics_changed,
        "artifact_count": len(artifacts),
        "missing_files": missing_files,
        "stale_files": stale_files,
        "reason": snapshot_reason,
    }


def _publish_current_run_pointer(
    current_pointer_path: Path,
    *,
    run_id: str,
    run_dir: Path,
    manifest_path: Path,
    manifest_sha256: str,
    source_version: str,
    finished_at: str,
    runs_root: Path,
    run_status: str,
    snapshot_status: str,
) -> str:
    payload: dict[str, object] = {
        "schema_version": "macro_toolkit_allocation_refresh_latest_pointer.v1",
        "run_id": run_id,
        "run_dir": str(run_dir),
        "manifest_path": str(manifest_path),
        "run_relative_path": _path_posix_relative(run_dir, runs_root),
        "manifest_relative_path": _path_posix_relative(manifest_path, runs_root),
        "manifest_sha256": manifest_sha256,
        "source_version": source_version,
        "run_status": run_status,
        "snapshot_status": snapshot_status,
        "published_at": finished_at,
    }
    _write_json_atomic(current_pointer_path, payload)
    return _sha256_file(current_pointer_path)


run_macro_toolkit_allocation_refresh_task = register_actor_once(
    "run_macro_toolkit_allocation_refresh",
    run_macro_toolkit_allocation_refresh,
    time_limit_ms=1_800_000,
)


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description=(
            "Rerun the macro toolkit allocation/regime script family "
            "(risk_parity_cn, performance_metrics_cn, rebalance_cn, regime_switch_cn, "
            "backtest_cn, cta_trend_cn, dcc_garch_cn, crowding_cn, equity_strategies, "
            "garch_multi_asset). CSI500-dependent scripts run after a system-source "
            "data readiness preflight."
        )
    )
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args()
    payload = run_macro_toolkit_allocation_refresh(
        output_dir=args.output_dir,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
