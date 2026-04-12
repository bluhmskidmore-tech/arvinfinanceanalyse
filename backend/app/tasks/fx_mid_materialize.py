from __future__ import annotations

import csv
import hashlib
import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import duckdb

from backend.app.repositories.choice_client import ChoiceClient
from backend.app.repositories.currency_codes import normalize_currency_code
from backend.app.tasks.broker import register_actor_once

CHOICE_USDCNY_SERIES_CODE = "EMM00058124"
CHOICE_SOURCE_NAME = "CFETS"
CHOICE_REQUEST_TIMEOUT_SECONDS = 5
CHOICE_FX_LOOKBACK_DAYS = 7


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


def _build_choice_source_version(payload: dict[str, object]) -> str:
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    return f"sv_fx_choice_{digest}"


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


def _replace_fx_mid_rows(
    *,
    duckdb_path: str,
    rows: list[tuple[object, ...]],
) -> None:
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


def _normalize_choice_trade_date(value: object) -> str:
    return str(value or "").strip().replace("/", "-").split(" ", 1)[0]


def _extract_choice_mid_rate(
    *,
    result: object,
    vendor_code: str,
) -> tuple[str, Decimal] | None:
    if result.__class__.__name__ == "DataFrame":
        rows = result.loc[[vendor_code]] if vendor_code in result.index else None
        if rows is None or len(rows) == 0:
            return None
        latest = rows.iloc[-1]
        value = latest["RESULT"]
        if value in (None, ""):
            return None
        return _normalize_choice_trade_date(latest["DATES"]), Decimal(str(value))

    codes = [str(code) for code in getattr(result, "Codes", [])]
    if vendor_code not in codes:
        return None
    dates = [_normalize_choice_trade_date(item) for item in getattr(result, "Dates", [])]
    if not dates:
        return None
    data = getattr(result, "Data", {})
    values = data.get(vendor_code, [])
    indicator_values = values[0] if values else []
    if not indicator_values:
        return None
    return dates[-1], Decimal(str(indicator_values[-1]))


def _fetch_choice_fx_mid_rows_for_report_date(report_date: str) -> list[tuple[object, ...]]:
    requested_date = date.fromisoformat(report_date)
    client = ChoiceClient()

    for offset in range(CHOICE_FX_LOOKBACK_DAYS + 1):
        query_date = (requested_date - timedelta(days=offset)).isoformat()
        result = client.edb(
            [CHOICE_USDCNY_SERIES_CODE],
            options=(
                f"IsLatest=0,StartDate={query_date},EndDate={query_date},"
                f"Ispandas=1,RECVtimeout={CHOICE_REQUEST_TIMEOUT_SECONDS}"
            ),
        )
        extracted = _extract_choice_mid_rate(result=result, vendor_code=CHOICE_USDCNY_SERIES_CODE)
        if extracted is None:
            continue
        trade_date, mid_rate = extracted
        if not trade_date:
            continue
        source_version = _build_choice_source_version(
            {
                "series_code": CHOICE_USDCNY_SERIES_CODE,
                "requested_report_date": report_date,
                "observed_trade_date": trade_date,
                "mid_rate": format(mid_rate, "f"),
            }
        )
        is_business_day = trade_date == report_date
        return [
            (
                report_date,
                "USD",
                "CNY",
                mid_rate,
                CHOICE_SOURCE_NAME,
                is_business_day,
                not is_business_day,
                source_version,
            )
        ]
    return []


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

    _replace_fx_mid_rows(duckdb_path=duckdb_path, rows=rows)

    return {
        "status": "completed",
        "row_count": len(rows),
        "source_version": source_version,
        "csv_path": str(csv_file),
    }


def _materialize_fx_mid_for_report_date(
    *,
    report_date: str,
    duckdb_path: str,
    data_input_root: str,
    official_csv_path: str = "",
    explicit_csv_path: str = "",
) -> dict[str, object]:
    csv_path = resolve_fx_mid_csv_path(
        official_csv_path=official_csv_path,
        explicit_csv_path=explicit_csv_path,
        data_input_root=Path(data_input_root),
    )

    if official_csv_path.strip() or explicit_csv_path.strip():
        payload = _materialize_fx_mid_rows(
            csv_path=str(csv_path),
            duckdb_path=duckdb_path,
        )
        return {
            **payload,
            "source_kind": "csv",
        }

    choice_error: Exception | None = None
    try:
        choice_rows = _fetch_choice_fx_mid_rows_for_report_date(report_date)
    except Exception as exc:
        choice_error = exc
        choice_rows = []

    if choice_rows:
        _replace_fx_mid_rows(duckdb_path=duckdb_path, rows=choice_rows)
        return {
            "status": "completed",
            "row_count": len(choice_rows),
            "source_version": str(choice_rows[0][7]),
            "source_kind": "choice",
            "report_date": report_date,
            "series_code": CHOICE_USDCNY_SERIES_CODE,
        }

    if csv_path is not None:
        payload = _materialize_fx_mid_rows(
            csv_path=str(csv_path),
            duckdb_path=duckdb_path,
        )
        return {
            **payload,
            "source_kind": "csv",
            "choice_error": str(choice_error) if choice_error is not None else "",
        }

    return {
        "status": "skipped",
        "row_count": 0,
        "source_kind": "none",
        "choice_error": str(choice_error) if choice_error is not None else "",
        "report_date": report_date,
    }


materialize_fx_mid_rows = register_actor_once(
    "materialize_fx_mid_rows",
    _materialize_fx_mid_rows,
)

materialize_fx_mid_for_report_date = register_actor_once(
    "materialize_fx_mid_for_report_date",
    _materialize_fx_mid_for_report_date,
)
