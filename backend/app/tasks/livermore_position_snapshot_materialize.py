from __future__ import annotations

import csv
import hashlib
import json
import uuid
from collections.abc import Sequence
from datetime import date
from pathlib import Path

import duckdb
from backend.app.governance.settings import get_settings
from backend.app.schema_registry.duckdb_loader import REGISTRY_DIR, parse_registry_sql_text

RULE_VERSION = "rv_livermore_position_snapshot_v1"
FACT_SOURCE = "livermore_position_snapshot"
DEFAULT_SOURCE_SYSTEM = "livermore_position_snapshot_csv"
ACTIVE_POSITION_STATUS = "ACTIVE"
INACTIVE_POSITION_STATUSES = {"CLOSED", "EXITED"}
VALID_POSITION_STATUSES = {ACTIVE_POSITION_STATUS, *INACTIVE_POSITION_STATUSES}
_REQUIRED_HEADERS = ("as_of_date", "stock_code", "stock_name", "entry_cost")
_INSERT_COLUMNS = (
    "as_of_date",
    "stock_code",
    "stock_name",
    "entry_cost",
    "bars_since_entry",
    "entry_date",
    "position_quantity",
    "position_status",
    "source_system",
    "source_file_hash",
    "source_row_no",
    "source_version",
    "vendor_version",
    "rule_version",
    "run_id",
)


def ensure_livermore_position_snapshot_schema(conn: duckdb.DuckDBPyConnection) -> None:
    text = (REGISTRY_DIR / "22_livermore_position_snapshot.sql").read_text(encoding="utf-8")
    for statement in parse_registry_sql_text(text):
        conn.execute(statement)


def materialize_livermore_position_snapshot(
    *,
    as_of_date: str | date,
    csv_path: str,
    duckdb_path: str | None,
) -> dict[str, object]:
    resolved_as_of_date = _normalize_date(as_of_date)
    csv_file = Path(csv_path)
    if not csv_file.exists():
        raise FileNotFoundError(f"Livermore position snapshot CSV not found: {csv_file}")

    source_file_hash = _source_file_hash(csv_file)
    with csv_file.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        _validate_required_headers(reader.fieldnames)
        latest_by_code: dict[str, dict[str, object]] = {}
        for source_row_no, raw_row in enumerate(reader, start=2):
            row_as_of_date = _normalize_date(raw_row.get("as_of_date"))
            if row_as_of_date != resolved_as_of_date:
                continue
            stock_code = _normalize_stock_code(raw_row.get("stock_code"), source_row_no=source_row_no)
            entry_date = _optional_date(raw_row.get("entry_date"))
            bars_since_entry = _optional_positive_int(
                raw_row.get("bars_since_entry"),
                field_name="bars_since_entry",
            )
            if bars_since_entry is None and entry_date is None:
                raise ValueError(
                    "Livermore position snapshot CSV requires bars_since_entry or entry_date "
                    f"for stock_code {stock_code}."
                )
            position_status = _position_status(raw_row.get("position_status"), source_row_no=source_row_no)
            latest_by_code[stock_code] = {
                "as_of_date": row_as_of_date,
                "stock_code": stock_code,
                "stock_name": _text(raw_row.get("stock_name")) or stock_code,
                "entry_cost": _positive_float_value(raw_row.get("entry_cost"), field_name="entry_cost"),
                "bars_since_entry": bars_since_entry,
                "entry_date": entry_date,
                "position_quantity": _optional_float(raw_row.get("position_quantity"), field_name="position_quantity"),
                "position_status": position_status,
                "source_system": _text(raw_row.get("source_system")) or DEFAULT_SOURCE_SYSTEM,
                "source_file_hash": source_file_hash,
                "source_row_no": source_row_no,
            }

    rows = [latest_by_code[stock_code] for stock_code in sorted(latest_by_code)]
    if not rows:
        raise ValueError(
            f"Livermore position snapshot CSV has no rows for as_of_date {resolved_as_of_date}."
        )

    duckdb_file = Path(str(duckdb_path or get_settings().duckdb_path))
    duckdb_file.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(duckdb_file), read_only=False)
    transaction_started = False
    try:
        ensure_livermore_position_snapshot_schema(conn)
        rows = [_resolve_bars_since_entry(conn, row) for row in rows if row["position_status"] == ACTIVE_POSITION_STATUS]
        if not rows:
            raise ValueError(
                f"Livermore position snapshot CSV has no active rows for as_of_date {resolved_as_of_date}."
            )
        source_version = _build_source_version(
            {
                "as_of_date": resolved_as_of_date,
                "fact_source": FACT_SOURCE,
                "source_file_hash": source_file_hash,
                "rows": rows,
            }
        )
        vendor_version = f"vv_livermore_position_csv_{source_version.removeprefix('sv_livermore_position_')}"
        run_id = f"livermore_position_snapshot:{resolved_as_of_date}:{uuid.uuid4().hex[:12]}"
        conn.execute("begin transaction")
        transaction_started = True
        conn.execute(
            "delete from livermore_position_snapshot where as_of_date = ?",
            [resolved_as_of_date],
        )
        placeholders = ", ".join("?" for _ in _INSERT_COLUMNS)
        conn.executemany(
            f"""
            insert into livermore_position_snapshot ({", ".join(_INSERT_COLUMNS)})
            values ({placeholders})
            """,
            [
                tuple(
                    source_version if column == "source_version"
                    else vendor_version if column == "vendor_version"
                    else RULE_VERSION if column == "rule_version"
                    else run_id if column == "run_id"
                    else row[column]
                    for column in _INSERT_COLUMNS
                )
                for row in rows
            ],
        )
        conn.execute("commit")
        transaction_started = False
    except Exception:
        if transaction_started:
            conn.execute("rollback")
        raise
    finally:
        conn.close()

    return {
        "status": "completed",
        "fact_source": FACT_SOURCE,
        "as_of_date": resolved_as_of_date,
        "row_count": len(rows),
        "run_id": run_id,
        "source_file_hash": source_file_hash,
        "source_systems": sorted({str(row["source_system"]) for row in rows if row["source_system"]}),
        "source_version": source_version,
        "vendor_version": vendor_version,
        "csv_path": str(csv_file),
    }


def _validate_required_headers(fieldnames: Sequence[str] | None) -> None:
    actual_headers = {str(name).strip() for name in (fieldnames or []) if str(name).strip()}
    missing_headers = sorted(set(_REQUIRED_HEADERS) - actual_headers)
    if missing_headers:
        raise ValueError(
            "Livermore position snapshot CSV required headers missing: "
            + ", ".join(missing_headers)
        )


def _build_source_version(payload: dict[str, object]) -> str:
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:12]
    return f"sv_livermore_position_{digest}"


def _source_file_hash(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def _resolve_bars_since_entry(
    conn: duckdb.DuckDBPyConnection,
    row: dict[str, object],
) -> dict[str, object]:
    if row["bars_since_entry"] is not None:
        return row
    entry_date = str(row["entry_date"])
    bars_since_entry = _derive_bars_since_entry(
        conn,
        stock_code=str(row["stock_code"]),
        entry_date=entry_date,
        as_of_date=str(row["as_of_date"]),
    )
    if bars_since_entry is None:
        raise ValueError(
            "Livermore position snapshot CSV cannot derive bars_since_entry from entry_date "
            f"for stock_code {row['stock_code']}."
        )
    return {**row, "bars_since_entry": bars_since_entry}


def _derive_bars_since_entry(
    conn: duckdb.DuckDBPyConnection,
    *,
    stock_code: str,
    entry_date: str,
    as_of_date: str,
) -> int | None:
    tables = {row[0] for row in conn.execute("show tables").fetchall()}
    if "choice_stock_daily_observation" not in tables:
        return None
    row = conn.execute(
        """
        select count(distinct cast(trade_date as date))::integer
        from choice_stock_daily_observation
        where stock_code = ?
          and cast(trade_date as date) between cast(? as date) and cast(? as date)
        """,
        [stock_code, entry_date, as_of_date],
    ).fetchone()
    if row is None or int(row[0]) <= 0:
        return None
    return int(row[0])


def _normalize_date(value: object) -> str:
    if isinstance(value, date):
        return value.isoformat()
    text = _text(value).replace("/", "-")
    if len(text) == 8 and text.isdigit():
        text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return date.fromisoformat(text[:10]).isoformat()


def _optional_date(value: object) -> str | None:
    text = _text(value)
    if not text:
        return None
    return _normalize_date(text)


def _normalize_stock_code(value: object, *, source_row_no: int) -> str:
    stock_code = _text(value).upper()
    if not stock_code:
        raise ValueError(f"Livermore position snapshot CSV source row {source_row_no} requires stock_code.")
    if not (
        len(stock_code) == 9
        and stock_code[:6].isdigit()
        and stock_code[6] == "."
        and stock_code[7:] in {"SH", "SZ", "BJ"}
    ):
        raise ValueError(
            "Livermore position snapshot CSV requires A-share stock_code with .SH/.SZ/.BJ suffix; "
            f"got {stock_code} on source row {source_row_no}."
        )
    return stock_code


def _text(value: object) -> str:
    return str(value or "").strip()


def _float_value(value: object, *, field_name: str) -> float:
    text = _text(value)
    if not text:
        raise ValueError(f"Livermore position snapshot CSV field {field_name} is required.")
    return float(text)


def _positive_float_value(value: object, *, field_name: str) -> float:
    number = _float_value(value, field_name=field_name)
    if number <= 0:
        raise ValueError(f"Livermore position snapshot CSV field {field_name} must be positive.")
    return number


def _optional_float(value: object, *, field_name: str) -> float | None:
    text = _text(value)
    if not text:
        return None
    return float(text)


def _optional_int(value: object, *, field_name: str) -> int | None:
    text = _text(value)
    if not text:
        return None
    return int(float(text))


def _optional_positive_int(value: object, *, field_name: str) -> int | None:
    number = _optional_int(value, field_name=field_name)
    if number is not None and number <= 0:
        raise ValueError(f"Livermore position snapshot CSV field {field_name} must be positive.")
    return number


def _position_status(value: object, *, source_row_no: int) -> str:
    status = _text(value).upper() or ACTIVE_POSITION_STATUS
    if status not in VALID_POSITION_STATUSES:
        allowed = ", ".join(sorted(VALID_POSITION_STATUSES))
        raise ValueError(
            "Livermore position snapshot CSV field position_status must be one of "
            f"{allowed}; got {status} on source row {source_row_no}."
        )
    return status
