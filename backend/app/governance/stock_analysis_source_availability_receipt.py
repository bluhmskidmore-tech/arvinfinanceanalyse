from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb

SCHEMA_VERSION = 1
RECEIPT_KIND = "pit_source_availability_v1"
ATTESTATION_KIND = "capture_time_database_observation"
AVAILABLE_AT_SEMANTICS = "utc_capture_date_only"
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def build_stock_analysis_source_availability_receipt(
    *,
    duckdb_path: str | Path,
    table_whitelist: Mapping[str, str],
    captured_at: str | None = None,
) -> dict[str, Any]:
    """Capture source tuples that are observable in DuckDB at one UTC instant.

    ``available_at`` is deliberately the UTC capture date. The receipt does not
    claim or infer when any source row was originally ingested.
    """

    target = Path(duckdb_path).resolve()
    if not target.is_file():
        raise ValueError("duckdb_path must be an existing file")
    normalized_whitelist = _normalize_table_whitelist(table_whitelist)
    captured = _normalize_captured_at(captured_at)
    available_at = captured[:10]

    database_sha256_before = _file_sha256(target)
    sources: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    conn = duckdb.connect(str(target), read_only=True)
    try:
        for table, date_column in normalized_whitelist:
            table_sources, table_summary = _scan_source_table(
                conn=conn,
                table=table,
                date_column=date_column,
                available_at=available_at,
            )
            sources.extend(table_sources)
            tables.append(table_summary)
    finally:
        conn.close()

    database_sha256_after = _file_sha256(target)
    if database_sha256_after != database_sha256_before:
        raise RuntimeError("DuckDB changed while source availability was captured")

    sources.sort(
        key=lambda item: (
            item["table"],
            item["source_version"],
            item["vendor_version"],
            item["rule_version"],
            item["run_id"],
        )
    )
    receipt: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "receipt_kind": RECEIPT_KIND,
        "captured_at": captured,
        "attestation": {
            "kind": ATTESTATION_KIND,
            "available_at_semantics": AVAILABLE_AT_SEMANTICS,
            "historical_ingestion_time_inferred": False,
        },
        "database": {
            "path": str(target),
            "sha256_before": database_sha256_before,
            "sha256_after": database_sha256_after,
            "unchanged": True,
        },
        "table_whitelist": [
            {"table": table, "date_column": date_column} for table, date_column in normalized_whitelist
        ],
        "tables": tables,
        "sources": sources,
    }
    receipt["canonical_receipt_sha256"] = _receipt_sha256(receipt)
    return receipt


def validate_stock_analysis_source_availability_receipt(
    receipt: Mapping[str, object],
) -> tuple[bool, tuple[str, ...]]:
    errors: list[str] = []
    if not isinstance(receipt, Mapping):
        return False, ("receipt must be a mapping",)
    payload = dict(receipt)
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"receipt.schema_version must equal {SCHEMA_VERSION}")
    if payload.get("receipt_kind") != RECEIPT_KIND:
        errors.append(f"receipt.receipt_kind must equal {RECEIPT_KIND}")

    captured_at: str | None = None
    try:
        captured_at = _normalize_captured_at(payload.get("captured_at"))
    except (TypeError, ValueError) as exc:
        errors.append(str(exc))

    attestation = payload.get("attestation")
    if not isinstance(attestation, Mapping):
        errors.append("receipt.attestation must be a mapping")
    else:
        if attestation.get("kind") != ATTESTATION_KIND:
            errors.append(f"receipt.attestation.kind must equal {ATTESTATION_KIND}")
        if attestation.get("available_at_semantics") != AVAILABLE_AT_SEMANTICS:
            errors.append(f"receipt.attestation.available_at_semantics must equal {AVAILABLE_AT_SEMANTICS}")
        if attestation.get("historical_ingestion_time_inferred") is not False:
            errors.append("receipt.attestation.historical_ingestion_time_inferred must be false")

    database = payload.get("database")
    if not isinstance(database, Mapping):
        errors.append("receipt.database must be a mapping")
    else:
        before = _optional_sha256(database.get("sha256_before"))
        after = _optional_sha256(database.get("sha256_after"))
        if before is None:
            errors.append("receipt.database.sha256_before must be an uppercase sha256")
        if after is None:
            errors.append("receipt.database.sha256_after must be an uppercase sha256")
        if before is not None and after is not None and before != after:
            errors.append("receipt database hashes must be unchanged")
        if database.get("unchanged") is not True:
            errors.append("receipt.database.unchanged must be true")
        if not _optional_text(database.get("path")):
            errors.append("receipt.database.path must be non-empty")

    raw_sources = payload.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        errors.append("receipt.sources must be a non-empty list")
    else:
        seen: set[tuple[str, str, str, str, str]] = set()
        expected_available_at = captured_at[:10] if captured_at is not None else None
        for index, raw_source in enumerate(raw_sources):
            if not isinstance(raw_source, Mapping):
                errors.append(f"receipt.sources[{index}] must be a mapping")
                continue
            table = _optional_text(raw_source.get("table"))
            source_version = _optional_text(raw_source.get("source_version"))
            run_id = _optional_text(raw_source.get("run_id"))
            if table is None:
                errors.append(f"receipt.sources[{index}].table must be non-empty")
            if source_version is None:
                errors.append(f"receipt.sources[{index}].source_version must be non-empty")
            if run_id is None:
                errors.append(f"receipt.sources[{index}].run_id must be non-empty")
            if table is not None and source_version is not None and run_id is not None:
                key = (
                    table,
                    source_version,
                    _optional_text(raw_source.get("vendor_version")) or "",
                    _optional_text(raw_source.get("rule_version")) or "",
                    run_id,
                )
                if key in seen:
                    errors.append("receipt.sources contains a duplicate source tuple")
                seen.add(key)
            if expected_available_at is not None:
                if raw_source.get("available_at") != expected_available_at:
                    errors.append(f"receipt.sources[{index}].available_at must equal UTC capture date")
            _validate_source_counts_and_dates(
                raw_source,
                index=index,
                errors=errors,
            )

    actual_hash = _optional_sha256(payload.get("canonical_receipt_sha256"))
    if actual_hash is None:
        errors.append("receipt.canonical_receipt_sha256 must be an uppercase sha256")
    elif actual_hash != _receipt_sha256(payload):
        errors.append("canonical_receipt_sha256 mismatch")
    return not errors, tuple(errors)


def _scan_source_table(
    *,
    conn: duckdb.DuckDBPyConnection,
    table: str,
    date_column: str,
    available_at: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    columns = {str(row[1]) for row in conn.execute(f"pragma table_info('{table}')").fetchall()}
    if not columns:
        raise ValueError(f"whitelisted source table does not exist: {table}")
    missing = sorted({date_column, "source_version", "run_id"}.difference(columns))
    if missing:
        raise ValueError(f"whitelisted source table {table} is missing required columns: " + ", ".join(missing))

    quoted_table = _quote_identifier(table)
    quoted_date = _quote_identifier(date_column)
    source_version = _normalized_column_expression("source_version")
    run_id = _normalized_column_expression("run_id")
    vendor_version = _normalized_column_expression("vendor_version") if "vendor_version" in columns else "''"
    rule_version = _normalized_column_expression("rule_version") if "rule_version" in columns else "''"
    rows = conn.execute(
        f"""
        select
          {source_version} as source_version,
          {vendor_version} as vendor_version,
          {rule_version} as rule_version,
          {run_id} as run_id,
          count(*) as row_count,
          count(try_cast({quoted_date} as date)) as dated_row_count,
          min(try_cast({quoted_date} as date)) as min_observed_date,
          max(try_cast({quoted_date} as date)) as max_observed_date
        from {quoted_table}
        group by 1, 2, 3, 4
        order by 1, 2, 3, 4
        """
    ).fetchall()
    if not rows:
        raise ValueError(f"whitelisted source table is empty: {table}")

    sources: list[dict[str, Any]] = []
    total_row_count = 0
    table_min_date: str | None = None
    table_max_date: str | None = None
    for row in rows:
        normalized_source_version = _optional_text(row[0])
        normalized_run_id = _optional_text(row[3])
        if normalized_source_version is None or normalized_run_id is None:
            raise ValueError(f"whitelisted source table {table} contains blank source_version or run_id")
        row_count = int(row[4])
        dated_row_count = int(row[5])
        if dated_row_count != row_count:
            raise ValueError(f"whitelisted source table {table}.{date_column} contains null or invalid dates")
        min_date = _date_value(row[6], field_name=f"{table}.min_observed_date")
        max_date = _date_value(row[7], field_name=f"{table}.max_observed_date")
        if max_date < min_date:
            raise ValueError(f"whitelisted source table {table} has an invalid date range")
        total_row_count += row_count
        table_min_date = min(table_min_date, min_date) if table_min_date else min_date
        table_max_date = max(table_max_date, max_date) if table_max_date else max_date
        sources.append(
            {
                "table": table,
                "source_version": normalized_source_version,
                "vendor_version": _optional_text(row[1]) or "",
                "rule_version": _optional_text(row[2]) or "",
                "run_id": normalized_run_id,
                "available_at": available_at,
                "row_count": row_count,
                "min_observed_date": min_date,
                "max_observed_date": max_date,
            }
        )

    summary = {
        "table": table,
        "date_column": date_column,
        "row_count": total_row_count,
        "min_observed_date": table_min_date,
        "max_observed_date": table_max_date,
        "distinct_source_tuple_count": len(sources),
        "vendor_version_column_present": "vendor_version" in columns,
        "rule_version_column_present": "rule_version" in columns,
    }
    return sources, summary


def _normalize_table_whitelist(value: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, Mapping) or not value:
        raise ValueError("table_whitelist must be a non-empty mapping")
    normalized: list[tuple[str, str]] = []
    for raw_table, raw_date_column in value.items():
        table = _identifier(raw_table, field_name="table_whitelist table")
        date_column = _identifier(
            raw_date_column,
            field_name=f"table_whitelist[{table}] date column",
        )
        normalized.append((table, date_column))
    return tuple(sorted(normalized))


def _normalize_captured_at(value: object) -> str:
    if value is None:
        parsed = datetime.now(UTC)
    else:
        text = _optional_text(value)
        if text is None:
            raise ValueError("captured_at must be a non-empty UTC datetime")
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("captured_at must be an ISO datetime") from exc
        if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
            raise ValueError("captured_at must use UTC")
        if parsed > datetime.now(UTC):
            raise ValueError("captured_at must not be in the future")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _validate_source_counts_and_dates(
    source: Mapping[str, object],
    *,
    index: int,
    errors: list[str],
) -> None:
    row_count = source.get("row_count")
    if isinstance(row_count, bool) or not isinstance(row_count, int) or row_count <= 0:
        errors.append(f"receipt.sources[{index}].row_count must be a positive int")
    try:
        start = date.fromisoformat(str(source.get("min_observed_date") or ""))
    except ValueError:
        errors.append(f"receipt.sources[{index}].min_observed_date must be an ISO date")
        start = None
    try:
        end = date.fromisoformat(str(source.get("max_observed_date") or ""))
    except ValueError:
        errors.append(f"receipt.sources[{index}].max_observed_date must be an ISO date")
        end = None
    if start is not None and end is not None and end < start:
        errors.append(f"receipt.sources[{index}] date range is invalid")


def _normalized_column_expression(column: str) -> str:
    quoted = _quote_identifier(column)
    return f"coalesce(trim(cast({quoted} as varchar)), '')"


def _quote_identifier(value: str) -> str:
    return f'"{value}"'


def _identifier(value: object, *, field_name: str) -> str:
    normalized = _optional_text(value)
    if normalized is None or _IDENTIFIER_PATTERN.fullmatch(normalized) is None:
        raise ValueError(f"{field_name} must be a simple SQL identifier")
    return normalized


def _date_value(value: object, *, field_name: str) -> str:
    if isinstance(value, date):
        return value.isoformat()
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO date") from exc


def _optional_text(value: object) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _optional_sha256(value: object) -> str | None:
    normalized = _optional_text(value)
    if normalized is None:
        return None
    if len(normalized) != 64 or any(ch not in "0123456789ABCDEF" for ch in normalized):
        return None
    return normalized


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _receipt_sha256(receipt: Mapping[str, object]) -> str:
    payload = dict(receipt)
    payload.pop("canonical_receipt_sha256", None)
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest().upper()
