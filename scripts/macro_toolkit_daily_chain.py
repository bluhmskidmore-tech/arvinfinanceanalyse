"""Operator CLI for the daily macro-toolkit model chain run.

Runs, in a single-writer sequence (after the freshness refresh timer has
updated vendor data):

1. the registered macro-toolkit script chain (merrill clock, crisis score,
   bond futures, crowding, DCC, CTA, signal aggregator, risk monitor);
2. the off-chain model scripts that complete the due-diligence note's
   ten-model set (GARCH, regime switch, risk parity, rebalance,
   performance metrics, backtest) in dependency order;
3. the illustrated daily report generator (generate_bond_macro_report),
   which consumes every model artifact above and therefore runs last.

Observation-only: artifacts stay non-formal and never enter formal finance.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core_finance.macro.toolkit.runner import run_toolkit_script  # noqa: E402
from backend.app.governance.settings import get_settings  # noqa: E402
from backend.app.services import macro_toolkit_service  # noqa: E402

RECEIPT_SCHEMA_VERSION = 1
TASK_NAME = "macro_toolkit_daily_chain"
SOURCE_VERSION = "macro_toolkit_daily_chain_v1"
SUCCESS_STATUSES = frozenset({"completed", "degraded", "dry_run"})
CHAIN_STEP_TIMEOUT_SECONDS = 300

# Off-chain model scripts, in dependency order: risk parity consumes the fresh
# merrill quadrant; rebalance/performance/backtest consume risk-parity weights.
EXTRA_MODEL_SCRIPTS: tuple[str, ...] = (
    "garch_multi_asset",
    "regime_switch_cn",
    "risk_parity_cn",
    "rebalance_cn",
    "performance_metrics_cn",
    "backtest_cn",
    # 图文日报消费上面全部模型产物 CSV，必须排在最后一步。
    "generate_bond_macro_report",
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run", action="store_true", help="Plan the chain without executing scripts.")
    modes.add_argument("--run-once", action="store_true", help="Run the full chain synchronously.")
    parser.add_argument("--receipt-path", type=Path, help="Atomically write a JSON run receipt.")
    parser.add_argument(
        "--run-kind",
        choices=("manual", "shadow", "scheduled"),
        default="manual",
        help="Classify the caller for receipt validation (default: manual).",
    )
    parser.add_argument(
        "--skip-extra-scripts",
        action="store_true",
        help="Run only the registered chain; skip the off-chain model scripts and the daily report.",
    )
    return parser


def _safe_error(exc: BaseException) -> str:
    message = " ".join(str(exc).split()) or "no error details"
    return f"{type(exc).__name__}: {message[:300]}"


def _resolve_commit_sha() -> tuple[str | None, str | None]:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"commit SHA unavailable: {_safe_error(exc)}"
    commit_sha = completed.stdout.strip()
    if completed.returncode != 0 or not commit_sha:
        return None, f"commit SHA unavailable: git exited with code {completed.returncode}"
    return commit_sha, None


def _write_receipt_atomic(path: Path, receipt: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(receipt, handle, ensure_ascii=False, default=str, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.replace(path)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


def run_daily_chain(*, dry_run: bool, include_extra_scripts: bool) -> dict[str, object]:
    """Execute the registered chain plus the off-chain model scripts."""
    settings = get_settings()
    # 以日历今天为新鲜度基准：正式调度时点（19:10，freshness 18:30 之后）当天数据
    # 已入库，产物即 current；盘前手动触发时数据仍是上一交易日，判 stale 属如实呈现。
    reference_date = date.today().isoformat()
    chain_result = macro_toolkit_service.run_macro_toolkit_chain(
        dry_run=dry_run,
        timeout_seconds=CHAIN_STEP_TIMEOUT_SECONDS,
        reference_date=reference_date,
        governance_path=None if dry_run else settings.governance_path,
    )
    chain_status = str(chain_result.get("status") or "failed")

    extra_steps: list[dict[str, object]] = []
    extra_failed = False
    for script_name in EXTRA_MODEL_SCRIPTS if include_extra_scripts else ():
        if dry_run:
            extra_steps.append({"script": script_name, "status": "dry_run"})
            continue
        # run_toolkit_script 为进程内执行：正常返回即成功，脚本失败以异常/非零 SystemExit 呈现。
        try:
            run_toolkit_script(script_name)
        except SystemExit as exc:
            if exc.code in (0, None):
                extra_steps.append({"script": script_name, "status": "completed"})
                continue
            extra_steps.append(
                {"script": script_name, "status": "failed", "error": f"SystemExit: {exc.code}"}
            )
            extra_failed = True
        except Exception as exc:  # noqa: BLE001 - one failing model must not hide the rest
            extra_steps.append({"script": script_name, "status": "error", "error": _safe_error(exc)})
            extra_failed = True
        else:
            extra_steps.append({"script": script_name, "status": "completed"})

    if chain_status not in SUCCESS_STATUSES or extra_failed:
        status = "failed"
    else:
        status = chain_status
    return {
        "status": status,
        "source_version": SOURCE_VERSION,
        "reference_date": reference_date,
        "chain": {
            "status": chain_status,
            "chain_id": chain_result.get("chain_id"),
            "readiness_after": chain_result.get("readiness_after"),
        },
        "extra_scripts": extra_steps,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    include_extra_scripts = not args.skip_extra_scripts
    invocation_mode = "dry_run" if args.dry_run else "run_once"
    try:
        result = run_daily_chain(dry_run=args.dry_run, include_extra_scripts=include_extra_scripts)
    except Exception as exc:  # noqa: BLE001 - scheduled runs must always produce a receipt
        result = {
            "status": "failed",
            "source_version": SOURCE_VERSION,
            "error": _safe_error(exc),
            "chain": {},
            "extra_scripts": [],
        }
    status = str(result.get("status") or "failed")
    exit_code = 0 if status in SUCCESS_STATUSES else 1
    print(json.dumps(result, ensure_ascii=False, default=str))
    if args.receipt_path is not None:
        commit_sha, commit_warning = _resolve_commit_sha()
        warnings = [commit_warning] if commit_warning else []
        receipt: dict[str, object] = {
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "generated_at": datetime.now(UTC).isoformat(),
            "run_kind": args.run_kind,
            "invocation_mode": invocation_mode,
            "task_name": TASK_NAME,
            "commit_sha": commit_sha,
            "source_version": SOURCE_VERSION,
            "status": status,
            "exit_code": exit_code,
            "result": result,
            "warnings": warnings,
        }
        try:
            _write_receipt_atomic(args.receipt_path, receipt)
        except Exception as exc:  # noqa: BLE001 - receipt durability is a hard CLI failure
            print(f"receipt write failed: {_safe_error(exc)}", file=sys.stderr)
            return 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
