from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import duckdb  # noqa: E402

from backend.app.core_finance.adjusted_returns import (  # noqa: E402
    STOCK_ADJUSTMENT_FACTOR_TABLE,
    ensure_stock_adjustment_factor_schema,
    normalize_duckdb_path,
)
from backend.app.governance.settings import get_settings  # noqa: E402
from backend.app.repositories.tushare_adapter import (  # noqa: E402
    import_tushare_pro,
    resolve_tushare_token_with_settings_fallback,
)


def backfill_stock_adjustment_factor(
    *,
    duckdb_path: str | Path,
    start_date: str | None = None,
    end_date: str | None = None,
    codes: list[str] | None = None,
    dry_run: bool = False,
    client: object | None = None,
    target_backup_path: str | Path | None = None,
    governance_lock: bool = False,
) -> dict[str, object]:
    resolved_path = normalize_duckdb_path(duckdb_path)
    if not resolved_path.exists():
        raise FileNotFoundError(f"DuckDB file not found: {resolved_path}")

    conn = duckdb.connect(str(resolved_path), read_only=dry_run)
    try:
        if not dry_run:
            ensure_stock_adjustment_factor_schema(conn)
        selected_codes = _select_codes(conn, explicit_codes=codes)
        selected_dates = _select_dates(conn, start_date=start_date, end_date=end_date)
    finally:
        conn.close()

    if dry_run:
        return {
            "status": "dry_run",
            "duckdb_path": str(resolved_path),
            "start_date": selected_dates[0] if selected_dates else start_date,
            "end_date": selected_dates[-1] if selected_dates else end_date,
            "code_count": len(selected_codes),
            "date_count": len(selected_dates),
            "selected_codes_preview": selected_codes[:10],
            "selected_dates_preview": selected_dates[:10],
            "would_call_tushare": bool(selected_codes and selected_dates),
        }

    if not selected_codes or not selected_dates:
        return {
            "status": "noop",
            "duckdb_path": str(resolved_path),
            "code_count": len(selected_codes),
            "date_count": len(selected_dates),
            "inserted_count": 0,
        }

    write_safety = _write_safety_guard(
        target_backup_path=target_backup_path,
        governance_lock=governance_lock,
    )
    rows = _fetch_tushare_adj_factor_rows(
        client or _DefaultTushareAdjustmentClient(),
        stock_codes=selected_codes,
        trade_dates=selected_dates,
    )
    source_version = _source_version(rows)
    run_id = f"stock_adjustment_factor:{selected_dates[0]}:{selected_dates[-1]}:{uuid.uuid4().hex[:12]}"

    conn = duckdb.connect(str(resolved_path), read_only=False)
    try:
        ensure_stock_adjustment_factor_schema(conn)
        conn.execute("begin transaction")
        for row in rows:
            conn.execute(
                f"delete from {STOCK_ADJUSTMENT_FACTOR_TABLE} where trade_date = ? and stock_code = ?",
                [row["trade_date"], row["stock_code"]],
            )
        if rows:
            conn.executemany(
                f"""
                insert into {STOCK_ADJUSTMENT_FACTOR_TABLE}
                (stock_code, trade_date, adj_factor, source_version, run_id)
                values (?, ?, ?, ?, ?)
                """,
                [
                    (
                        row["stock_code"],
                        row["trade_date"],
                        row["adj_factor"],
                        source_version,
                        run_id,
                    )
                    for row in rows
                ],
            )
        conn.execute("commit")
    except Exception:
        conn.execute("rollback")
        raise
    finally:
        conn.close()

    result: dict[str, object] = {
        "status": "partial_completed" if len(rows) < len(selected_codes) * len(selected_dates) else "completed",
        "factor_write_status": "completed",
        "duckdb_path": str(resolved_path),
        "start_date": selected_dates[0],
        "end_date": selected_dates[-1],
        "code_count": len(selected_codes),
        "date_count": len(selected_dates),
        "requested_cell_count": len(selected_codes) * len(selected_dates),
        "returned_cell_count": len(rows),
        "missing_vendor_cell_count": len(selected_codes) * len(selected_dates) - len(rows),
        "inserted_count": len(rows),
        "source_version": source_version,
        "run_id": run_id,
        "write_safety": write_safety,
    }
    if rows:
        from backend.app.tasks.livermore_candidate_outcome_maturity import (
            mature_livermore_candidate_outcomes,
        )

        maturity_evaluation_date = max(str(row["trade_date"]) for row in rows)
        try:
            maturity_payload = mature_livermore_candidate_outcomes(
                resolved_path,
                evaluation_as_of_date=maturity_evaluation_date,
            )
        except Exception as exc:
            maturity_payload = {"status": "failed", "error": str(exc)}
        if maturity_payload.get("status") != "completed":
            maturity_payload = dict(maturity_payload)
            maturity_payload.setdefault(
                "error",
                str(maturity_payload.get("reason") or "outcome maturity did not complete"),
            )
            result["status"] = "partial_completed"
        result["outcome_maturity"] = maturity_payload
    return result


class _DefaultTushareAdjustmentClient:
    def __init__(self) -> None:
        token = resolve_tushare_token_with_settings_fallback(get_settings())
        if not token:
            raise RuntimeError("MOSS_TUSHARE_TOKEN or settings.tushare_token is required for adj_factor backfill.")
        self._api = import_tushare_pro().pro_api(token)

    def adj_factor(self, **kwargs: object) -> object:
        return self._api.adj_factor(**kwargs)


def _fetch_tushare_adj_factor_rows(
    client: object,
    *,
    stock_codes: list[str],
    trade_dates: list[str],
) -> list[dict[str, object]]:
    code_set = set(stock_codes)
    rows: list[dict[str, object]] = []
    for trade_date in trade_dates:
        frame = client.adj_factor(
            trade_date=trade_date.replace("-", ""),
            fields="ts_code,trade_date,adj_factor",
        )
        for record in _records_from_tabular_payload(frame):
            stock_code = str(record.get("ts_code") or "").strip().upper()
            if stock_code not in code_set:
                continue
            adj_factor = _float_or_none(record.get("adj_factor"))
            normalized_date = _normalize_compact_date(record.get("trade_date"))
            if adj_factor is None or not normalized_date:
                continue
            rows.append(
                {
                    "stock_code": stock_code,
                    "trade_date": normalized_date,
                    "adj_factor": adj_factor,
                }
            )
    return sorted(rows, key=lambda row: (str(row["trade_date"]), str(row["stock_code"])))


def _select_codes(conn: duckdb.DuckDBPyConnection, *, explicit_codes: list[str] | None) -> list[str]:
    if explicit_codes:
        return sorted({code.strip().upper() for code in explicit_codes if code.strip()})
    codes: set[str] = set()
    tables = _table_names(conn)
    for table, column in (
        ("livermore_candidate_history", "stock_code"),
        ("livermore_stock_candidate_universe_history", "stock_code"),
        ("livermore_candidate_execution_history", "stock_code"),
    ):
        if table not in tables or column not in _table_columns(conn, table):
            continue
        for row in conn.execute(f"select distinct {column} from {table} where {column} is not null").fetchall():
            code = str(row[0] or "").strip().upper()
            if code:
                codes.add(code)
    return sorted(codes)


def _select_dates(
    conn: duckdb.DuckDBPyConnection,
    *,
    start_date: str | None,
    end_date: str | None,
) -> list[str]:
    dates: set[str] = set()
    tables = _table_names(conn)
    for table, column in (
        ("livermore_candidate_history", "snapshot_as_of_date"),
        ("livermore_stock_candidate_universe_history", "snapshot_as_of_date"),
        ("livermore_candidate_execution_history", "signal_date"),
    ):
        if table not in tables or column not in _table_columns(conn, table):
            continue
        for row in conn.execute(
            f"""
            select distinct {column}
            from {table}
            where {column} is not null
              and (? is null or cast({column} as date) >= cast(? as date))
              and (? is null or cast({column} as date) <= cast(? as date))
            """,
            [start_date, start_date, end_date, end_date],
        ).fetchall():
            text = str(row[0] or "").strip()[:10]
            if text:
                dates.add(text)
    if not dates and start_date and end_date:
        dates.update(_calendar_dates(start_date[:10], end_date[:10]))
    return sorted(dates)


def _calendar_dates(start_date: str, end_date: str) -> list[str]:
    from datetime import date, timedelta

    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    dates: list[str] = []
    current = start
    while current <= end:
        dates.append(current.isoformat())
        current += timedelta(days=1)
    return dates


def _records_from_tabular_payload(payload: object) -> list[dict[str, object]]:
    if payload is None:
        return []
    to_dict = getattr(payload, "to_dict", None)
    if callable(to_dict):
        records = to_dict(orient="records")
        return [record for record in records if isinstance(record, dict)]
    if isinstance(payload, list):
        return [record for record in payload if isinstance(record, dict)]
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return [record for record in data if isinstance(record, dict)]
    return []


def _source_version(rows: list[dict[str, object]]) -> str:
    digest = hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:12]
    return f"sv_stock_adjustment_factor_{digest}"


def _write_safety_guard(
    *,
    target_backup_path: str | Path | None,
    governance_lock: bool,
) -> dict[str, object]:
    if governance_lock:
        return {"status": "governance_lock_acknowledged", "governance_lock": True, "target_backup_path": None}
    if target_backup_path is None:
        raise RuntimeError("stock_adjustment_factor write requires --target-backup-path or --governance-lock")
    backup = Path(target_backup_path)
    if not backup.exists():
        raise FileNotFoundError(f"target backup path does not exist: {backup}")
    return {
        "status": "target_backup_verified",
        "governance_lock": False,
        "target_backup_path": str(backup),
        "target_backup_sha256": _file_sha256(backup) if backup.is_file() else None,
    }


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _placeholders(values: list[object]) -> str:
    return ", ".join("?" for _ in values) or "null"


def _normalize_compact_date(value: object) -> str:
    text = str(value or "").strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text[:10] if len(text) >= 10 else ""


def _float_or_none(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _table_names(conn: duckdb.DuckDBPyConnection) -> set[str]:
    return {str(row[0]) for row in conn.execute("show tables").fetchall()}


def _table_columns(conn: duckdb.DuckDBPyConnection, table_name: str) -> set[str]:
    return {str(row[1]).lower() for row in conn.execute(f"pragma table_info('{table_name}')").fetchall()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill Tushare adj_factor into local DuckDB.")
    parser.add_argument("--db-path", "--duckdb-path", dest="duckdb_path", default="data/moss.duckdb")
    parser.add_argument("--start", "--start-date", dest="start_date", default=None)
    parser.add_argument("--end", "--end-date", dest="end_date", default=None)
    parser.add_argument("--codes", default="", help="Comma-separated stock codes; defaults to Livermore history codes.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--target-backup-path", default=None, help="Existing backup artifact required before non-dry-run writes.")
    parser.add_argument("--governance-lock", action="store_true", help="Acknowledge external backup/governance lock for non-dry-run writes.")
    args = parser.parse_args()

    codes = [item.strip() for item in args.codes.split(",") if item.strip()]
    try:
        result = backfill_stock_adjustment_factor(
            duckdb_path=args.duckdb_path,
            start_date=args.start_date,
            end_date=args.end_date,
            codes=codes or None,
            dry_run=args.dry_run,
            target_backup_path=args.target_backup_path,
            governance_lock=args.governance_lock,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if result.get("status") == "partial_completed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
