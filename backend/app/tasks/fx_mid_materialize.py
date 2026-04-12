from __future__ import annotations

import csv
import hashlib
from decimal import Decimal
from pathlib import Path

import duckdb

from backend.app.repositories.currency_codes import normalize_currency_code
from backend.app.tasks.broker import register_actor_once


def resolve_fx_mid_csv_path(
    *,
    official_csv_path: str = "",
    explicit_csv_path: str,
    data_input_root: Path,
) -> Path | None:
    official = Path(official_csv_path).expanduser() if str(official_csv_path).strip() else None
    if official is not None:
        if official.exists():
            return official
        raise FileNotFoundError(f"FX official CSV not found: {official}")

    explicit = Path(explicit_csv_path).expanduser() if str(explicit_csv_path).strip() else None
    if explicit is not None:
        if explicit.exists():
            return explicit
        raise FileNotFoundError(f"FX mid CSV not found: {explicit}")

    candidates = (
        data_input_root / "fx" / "fx_daily_mid.csv",
        data_input_root / "fx_daily_mid.csv",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _parse_bool(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "t", "yes", "y"}


def _validate_required_headers(fieldnames: list[str] | None) -> None:
    required_headers = {
        "trade_date",
        "base_currency",
        "quote_currency",
        "mid_rate",
        "source_name",
        "is_business_day",
        "is_carry_forward",
    }
    actual_headers = {str(name).strip() for name in (fieldnames or []) if str(name).strip()}
    missing_headers = sorted(required_headers - actual_headers)
    if missing_headers:
        raise ValueError(
            "FX mid CSV required headers missing: " + ", ".join(missing_headers)
        )


def _build_source_version(csv_path: Path) -> str:
    payload = csv_path.read_bytes()
    return f"sv_fx_{hashlib.sha256(payload).hexdigest()[:12]}"


def _ensure_fx_mid_table(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table if not exists fx_daily_mid (
          trade_date date,
          base_currency varchar,
          quote_currency varchar,
          mid_rate decimal(24, 8),
          source_name varchar,
          is_business_day boolean,
          is_carry_forward boolean,
          source_version varchar
        )
        """
    )


def _materialize_fx_mid_rows(
    *,
    csv_path: str,
    duckdb_path: str,
) -> dict[str, object]:
    csv_file = Path(csv_path)
    if not csv_file.exists():
        raise FileNotFoundError(f"FX mid CSV not found: {csv_file}")

    source_version = _build_source_version(csv_file)
    with csv_file.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        _validate_required_headers(reader.fieldnames)
        latest_by_key: dict[tuple[str, str, str], tuple[object, ...]] = {}
        for row in reader:
            normalized_row = (
                str(row["trade_date"]).strip(),
                normalize_currency_code(str(row["base_currency"])),
                normalize_currency_code(str(row["quote_currency"])),
                Decimal(str(row["mid_rate"]).strip()),
                str(row.get("source_name") or csv_file.stem).strip(),
                _parse_bool(str(row.get("is_business_day") or "")),
                _parse_bool(str(row.get("is_carry_forward") or "")),
                source_version,
            )
            latest_by_key[
                (
                    str(normalized_row[0]),
                    str(normalized_row[1]),
                    str(normalized_row[2]),
                )
            ] = normalized_row
        rows = list(latest_by_key.values())

    conn = duckdb.connect(duckdb_path, read_only=False)
    try:
        _ensure_fx_mid_table(conn)
        conn.execute("begin transaction")
        if rows:
            delete_keys = [(row[0], row[1], row[2]) for row in rows]
            conn.executemany(
                """
                delete from fx_daily_mid
                where trade_date = ?
                  and upper(base_currency) = upper(?)
                  and upper(quote_currency) = upper(?)
                """,
                delete_keys,
            )
            conn.executemany(
                """
                insert into fx_daily_mid values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        conn.execute("commit")
    except Exception:
        conn.execute("rollback")
        raise
    finally:
        conn.close()

    return {
        "status": "completed",
        "row_count": len(rows),
        "source_version": source_version,
        "csv_path": str(csv_file),
    }


materialize_fx_mid_rows = register_actor_once(
    "materialize_fx_mid_rows",
    _materialize_fx_mid_rows,
)
