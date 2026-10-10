#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import duckdb

from backend.app.core_finance.adjusted_returns import normalize_duckdb_path
from backend.app.core_finance.livermore_risk_exit import FORMULA_VERSION

TABLE_EXECUTION_HIST = "livermore_candidate_execution_history"
REPORT_PATH = ROOT / "docs/pnl/2026-07-risk-exit-validation.md"


def validate_risk_exit_rules(
    *,
    duckdb_path: str | Path,
    report_path: str | Path = REPORT_PATH,
) -> dict[str, Any]:
    path = normalize_duckdb_path(duckdb_path)
    resolved_report = Path(report_path)
    if not resolved_report.is_absolute():
        resolved_report = ROOT / resolved_report
    if not path.exists():
        report = _blocked_report(path, "DuckDB file not found")
        _write_report(resolved_report, report)
        return report

    conn = duckdb.connect(str(path), read_only=True)
    try:
        tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
        if TABLE_EXECUTION_HIST not in tables:
            report = _blocked_report(path, f"{TABLE_EXECUTION_HIST} is not materialized")
        else:
            report = _execution_history_summary(conn, path)
    finally:
        conn.close()
    _write_report(resolved_report, report)
    return report


def _blocked_report(path: Path, reason: str) -> dict[str, Any]:
    return {
        "status": "blocked",
        "duckdb_path": str(path),
        "formula_version": FORMULA_VERSION,
        "reason": reason,
        "rules": {},
        "activation_condition": (
            "R3 remains observation-only. Promote only in a later batch if avg improves by at least "
            "0.3pp versus R2 and p10 does not deteriorate."
        ),
    }


def _execution_history_summary(conn: duckdb.DuckDBPyConnection, path: Path) -> dict[str, Any]:
    rows = conn.execute(
        f"""
        select signal_kind, count(*)::integer,
               avg(return_20d_net_adj),
               sum(case when return_20d_net_adj > 0 then 1 else 0 end)::integer
        from {TABLE_EXECUTION_HIST}
        where entry_executable = true
        group by signal_kind
        order by signal_kind
        """
    ).fetchall()
    rules = {
        str(signal_kind or "unknown"): {
            "R0_T20_hold": {
                "n": int(n or 0),
                "avg": None if avg_return is None else float(avg_return),
                "win": None if not n else int(wins or 0) / int(n),
                "note": "R1/R2/R3 path simulation requires entry-level post-entry OHLCV history; current report records the execution-table baseline.",
            }
        }
        for signal_kind, n, avg_return, wins in rows
    }
    return {
        "status": "completed" if rules else "empty",
        "duckdb_path": str(path),
        "formula_version": FORMULA_VERSION,
        "rules": rules,
        "activation_condition": (
            "R3 remains observation-only. Promote only in a later batch if avg improves by at least "
            "0.3pp versus R2 and p10 does not deteriorate."
        ),
    }


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 2026-07 Risk Exit Validation",
        "",
        f"- status: {report['status']}",
        f"- formula_version: {report['formula_version']}",
        f"- activation_condition: {report['activation_condition']}",
    ]
    if report.get("reason"):
        lines.append(f"- reason: {report['reason']}")
    lines.extend(["", "```json", json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), "```", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Livermore risk-exit rules in observation mode.")
    parser.add_argument("--db-path", "--duckdb-path", dest="duckdb_path", default="data/moss.duckdb")
    parser.add_argument("--report-path", default=str(REPORT_PATH))
    args = parser.parse_args(argv)
    result = validate_risk_exit_rules(duckdb_path=args.duckdb_path, report_path=args.report_path)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
