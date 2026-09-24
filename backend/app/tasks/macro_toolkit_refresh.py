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

This module does not write to DuckDB; the toolkit scripts only produce CSV /
PNG files under ``data/macro_toolkit/output`` (or
``MOSS_MACRO_TOOLKIT_OUTPUT_DIR``). There is no existing manifest/versioning
convention for those file outputs (unlike the DuckDB ``cache_build_run``
governance stream used by materialize tasks), so none is invented here;
``source_version`` and per-step ``duration_seconds`` are reported directly in
the returned payload instead.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from backend.app.core_finance.macro.toolkit.paths import OUTPUT_DIR
from backend.app.core_finance.macro.toolkit.system_sources import load_series_by_alias
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.services.macro_toolkit_service import run_macro_toolkit_script
from backend.app.tasks.broker import register_actor_once

logger = logging.getLogger(__name__)

SOURCE_VERSION = "macro_toolkit_allocation_refresh_v1"
DEFAULT_TIMEOUT_SECONDS = 180
CSI500_MIN_OBSERVATIONS = 100
MACRO_TOOLKIT_ALLOCATION_REFRESH_LOCK = LockDefinition(
    key="lock:macro_toolkit:allocation-refresh",
    ttl_seconds=900,
)

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
    resolved_governance_dir = Path(governance_path) if governance_path is not None else resolved_output_dir
    run_id = f"macro_toolkit_allocation_refresh:{uuid.uuid4().hex[:12]}"
    started_at = datetime.now(UTC).isoformat()
    run_started = time.monotonic()

    try:
        with acquire_lock(
            MACRO_TOOLKIT_ALLOCATION_REFRESH_LOCK,
            base_dir=resolved_governance_dir,
            timeout_seconds=0.1,
        ):
            results = [
                _run_step(step, output_dir=resolved_output_dir, timeout_seconds=timeout_seconds) for step in STEPS
            ]
    except TimeoutError as exc:
        raise MacroToolkitRefreshConflictError(
            "Macro toolkit allocation refresh is already in progress."
        ) from exc

    finished_at = datetime.now(UTC).isoformat()
    status_counts: dict[str, int] = {}
    for result in results:
        status = str(result["status"])
        status_counts[status] = status_counts.get(status, 0) + 1

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
        }

    start = time.monotonic()
    try:
        result = run_macro_toolkit_script(
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
        }
    duration_seconds = round(time.monotonic() - start, 3)

    status = "success" if result.get("status") == "completed" else "failed"
    output_files = result.get("output_files") or []
    produced_outputs = [
        entry for entry in output_files if str(entry.get("name")) in step.expected_outputs
    ]
    return {
        "script_name": step.script_name,
        "label": step.label,
        "status": status,
        "reason": None if status == "success" else _failure_reason(result),
        "exit_code": result.get("exit_code"),
        "duration_seconds": duration_seconds,
        "expected_outputs": list(step.expected_outputs),
        "produced_outputs": produced_outputs,
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
