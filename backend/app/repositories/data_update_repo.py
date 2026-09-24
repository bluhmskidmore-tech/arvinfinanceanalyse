"""Operational update receipts and read-only financial date checks."""

from __future__ import annotations

from pathlib import Path

from backend.app.repositories.duckdb_repo import read_only_connection
from backend.app.repositories.governance_repo import GovernanceRepository

RUN_STREAM = "data_update_run"
DATE_TABLES = (
    ("balance", "正式余额", "fact_formal_zqtz_balance_daily", "report_date"),
    ("interbank", "同业余额", "fact_formal_tyw_balance_daily", "report_date"),
    ("pnl", "正式损益", "fact_formal_pnl_fi", "report_date"),
    ("bond", "债券分析", "fact_formal_bond_analytics_daily", "report_date"),
    ("risk", "风险张量", "fact_formal_risk_tensor_daily", "report_date"),
)


def latest_runs(governance_dir: str | Path) -> list[dict[str, object]]:
    records = GovernanceRepository(base_dir=governance_dir).read_all(RUN_STREAM)
    runs: dict[str, dict[str, object]] = {}
    for record in records:
        run_id = str(record.get("run_id") or "")
        if run_id:
            runs[run_id] = record
    return sorted(runs.values(), key=lambda row: str(row.get("submitted_at") or ""), reverse=True)


def save_run(governance_dir: str | Path, run: dict[str, object]) -> dict[str, object]:
    GovernanceRepository(base_dir=governance_dir).append(RUN_STREAM, run)
    return run


def financial_dates(duckdb_path: str | Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [{"key": key, "label": label, "as_of_date": None, "status": "missing"} for key, label, _, _ in DATE_TABLES]
    if not Path(duckdb_path).is_file():
        return rows
    try:
        with read_only_connection(str(duckdb_path), retries=1) as conn:
            tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
            for row, (_, _, table, column) in zip(rows, DATE_TABLES, strict=True):
                if table in tables:
                    # Identifiers come exclusively from the constant table above.
                    result = conn.execute(f'SELECT MAX("{column}") FROM "{table}"').fetchone()
                    if result is None:
                        raise RuntimeError(f"{table} MAX query returned no row")
                    value = result[0]
                    row.update(
                        as_of_date=str(value)[:10] if value is not None else None,
                        status="available" if value is not None else "missing",
                    )
    except Exception:
        # A lock/open/schema failure is never presented as an empty table.
        return [{**row, "as_of_date": None, "status": "error"} for row in rows]
    return rows


def verify_daily_balance_date(duckdb_path: str | Path, report_date: str) -> None:
    """Verify the requested partition, not MAX(date), including on historical reruns."""
    with read_only_connection(str(duckdb_path), retries=1) as conn:
        for key, label, table, column in DATE_TABLES:
            if key == "pnl":
                continue
            result = conn.execute(f'SELECT COUNT(*) FROM "{table}" WHERE "{column}" = ?', [report_date]).fetchone()
            if result is None:
                raise RuntimeError(f"{table} COUNT query returned no row")
            count = result[0]
            if not count:
                raise ValueError(f"{label}缺少报告日 {report_date} 的结果，更新未通过核验。")
