"""Operator entry point for risk tensor materialization.

This script keeps DuckDB writes behind the task actor. It is not an API or
service write path.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.governance.settings import get_settings  # noqa: E402
from backend.app.tasks.risk_tensor_materialize import (  # noqa: E402
    materialize_risk_tensor_facts,
)


BOUNDARY = {
    "operator_entrypoint": True,
    "writes_duckdb_via_task": True,
    "uses_api_or_service_write_path": False,
    "changes_schema": False,
}


def run_risk_tensor_materialize(
    *,
    report_date: str,
    duckdb_path: str | Path | None = None,
    governance_dir: str | Path | None = None,
    run_id: str | None = None,
    enqueue: bool = False,
    dry_run: bool = False,
) -> dict[str, object]:
    kwargs = _task_kwargs(
        report_date=report_date,
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        run_id=run_id,
    )
    if dry_run:
        return {
            "status": "dry_run",
            "would_call": kwargs,
            "boundary": dict(BOUNDARY),
        }
    if enqueue:
        message = materialize_risk_tensor_facts.send(**kwargs)
        return {
            "status": "queued",
            "actor": materialize_risk_tensor_facts.actor_name,
            "message_id": getattr(message, "message_id", None),
            "report_date": kwargs["report_date"],
            "run_id": kwargs["run_id"],
        }
    return materialize_risk_tensor_facts.fn(**kwargs)


def _task_kwargs(
    *,
    report_date: str,
    duckdb_path: str | Path | None,
    governance_dir: str | Path | None,
    run_id: str | None,
) -> dict[str, object]:
    settings = get_settings()
    normalized_report_date = _normalize_iso_date(report_date, field_name="report_date")
    resolved_run_id = (
        run_id.strip()
        if isinstance(run_id, str) and run_id.strip()
        else _default_run_id("risk_tensor_materialize", normalized_report_date)
    )
    return {
        "report_date": normalized_report_date,
        "duckdb_path": str(Path(duckdb_path) if duckdb_path is not None else settings.duckdb_path),
        "governance_dir": str(
            Path(governance_dir)
            if governance_dir is not None
            else settings.governance_path
        ),
        "run_id": resolved_run_id,
    }


def _normalize_iso_date(value: str, *, field_name: str) -> str:
    text = str(value or "").strip()[:10]
    if not text:
        raise ValueError(f"{field_name} is required.")
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{field_name} must be YYYY-MM-DD.") from exc
    return text


def _default_run_id(job_name: str, report_date: str) -> str:
    stamp = datetime.now(UTC).isoformat()
    return f"{job_name}:{report_date}:{stamp}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the risk tensor task-level materialization wrapper.",
    )
    parser.add_argument("--report-date", required=True)
    parser.add_argument("--duckdb-path")
    parser.add_argument("--governance-dir")
    parser.add_argument("--run-id")
    parser.add_argument("--enqueue", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        result = run_risk_tensor_materialize(
            report_date=args.report_date,
            duckdb_path=args.duckdb_path,
            governance_dir=args.governance_dir,
            run_id=args.run_id,
            enqueue=args.enqueue,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("status") in {"completed", "queued", "dry_run"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
