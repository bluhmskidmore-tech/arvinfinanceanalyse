"""Strong, read-only verifier for the 2026-07-31 Decimal precision backfill.

The verifier intentionally does not know how a backfill is performed.  It opens
the before/after DuckDB files with ``read_only=True``, snapshots their schema and
all base-table rows, and then permits changes only in the target-date slice of
the six tables named by the runbook.  Every row is serialized with explicit
type tags before hashing; Decimal values are represented by their Decimal tuple
so trailing zeroes (and therefore scale) are never lost through a float cast.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import heapq
import json
import math
import os
import struct
import sys
import tempfile
import uuid
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Sequence

import duckdb


VERIFIER_VERSION = "1"
DEFAULT_REPORT_DATE = dt.date(2026, 7, 31)
TARGET_DATE_TABLES = frozenset(
    {
        "zqtz_bond_daily_snapshot",
        "tyw_interbank_daily_snapshot",
        "fact_formal_zqtz_balance_daily",
        "fact_formal_tyw_balance_daily",
        "fact_formal_bond_analytics_daily",
        "fact_formal_risk_tensor_daily",
    }
)
FROZEN_TABLES = frozenset({"fx_daily_mid", "fact_formal_yield_curve_daily"})
# Naming aliases make the policy easy to discover for callers and tests.
ALLOWED_DELTA_TABLES = TARGET_DATE_TABLES
TARGET_DATE_TABLE_KEYS = frozenset(f"main.{table}" for table in TARGET_DATE_TABLES)
FROZEN_TABLE_KEYS = frozenset(f"main.{table}" for table in FROZEN_TABLES)
_CHUNK_SIZE = 4_096
_ALLOWED_REPORT_DATE_TYPES = frozenset({"DATE", "VARCHAR"})


class VerifierError(RuntimeError):
    """Raised when an input cannot be verified safely."""


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    ordinal_position: int
    duckdb_type: str
    is_nullable: str | None

    def as_receipt(self) -> dict[str, object]:
        return {
            "name": self.name,
            "ordinal_position": self.ordinal_position,
            "duckdb_type": self.duckdb_type,
            "is_nullable": self.is_nullable,
        }


@dataclass(frozen=True)
class TableSpec:
    schema: str
    name: str
    table_type: str
    columns: tuple[ColumnSpec, ...]

    @property
    def key(self) -> str:
        return f"{self.schema}.{self.name}"

    def as_receipt(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "table": self.name,
            "table_type": self.table_type,
            "columns": [column.as_receipt() for column in self.columns],
        }


@dataclass(frozen=True)
class DigestSummary:
    row_count: int
    table_sha256: str

    def as_receipt(self) -> dict[str, object]:
        return {"row_count": self.row_count, "table_sha256": self.table_sha256}


def _frame(tag: bytes, payload: bytes) -> bytes:
    """Frame one typed value so concatenation cannot be ambiguous."""

    if len(tag) != 1:
        raise ValueError("canonical type tags must be one byte")
    return tag + len(payload).to_bytes(8, byteorder="big", signed=False) + payload


def canonical_serialize(value: Any) -> bytes:
    """Serialize a DuckDB scalar/container without a lossy numeric conversion.

    The returned bytes are an implementation contract for this verifier, not a
    user-facing representation.  In particular, Decimal uses ``as_tuple`` and
    therefore preserves the exponent (scale) and trailing zeroes.
    """

    if value is None:
        return _frame(b"N", b"")
    if isinstance(value, bool):
        return _frame(b"B", b"1" if value else b"0")
    if isinstance(value, Decimal):
        sign, digits, exponent = value.as_tuple()
        payload = json.dumps(
            {
                "sign": sign,
                "digits": list(digits),
                "exponent": exponent,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return _frame(b"D", payload)
    if isinstance(value, int):
        return _frame(b"I", str(value).encode("ascii"))
    if isinstance(value, float):
        if math.isnan(value):
            payload = b"nan"
        elif math.isinf(value):
            payload = b"+inf" if value > 0 else b"-inf"
        else:
            payload = struct.pack(">d", value)
        return _frame(b"F", payload)
    if isinstance(value, dt.datetime):
        return _frame(b"T", value.isoformat(timespec="microseconds").encode("ascii"))
    if isinstance(value, dt.date):
        return _frame(b"A", value.isoformat().encode("ascii"))
    if isinstance(value, dt.time):
        return _frame(b"U", value.isoformat(timespec="microseconds").encode("ascii"))
    if isinstance(value, dt.timedelta):
        payload = json.dumps(
            {
                "days": value.days,
                "seconds": value.seconds,
                "microseconds": value.microseconds,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
        return _frame(b"X", payload)
    if isinstance(value, str):
        return _frame(b"S", value.encode("utf-8"))
    if isinstance(value, (bytes, bytearray, memoryview)):
        return _frame(b"Y", bytes(value))
    if isinstance(value, uuid.UUID):
        return _frame(b"G", value.bytes)
    if isinstance(value, list):
        payload = b"".join(canonical_serialize(item) for item in value)
        return _frame(b"L", payload)
    if isinstance(value, tuple):
        payload = b"".join(canonical_serialize(item) for item in value)
        return _frame(b"Q", payload)
    if isinstance(value, dict):
        entries = []
        for key, item in value.items():
            entries.append(canonical_serialize(key) + canonical_serialize(item))
        payload = b"".join(sorted(entries))
        return _frame(b"M", payload)
    raise VerifierError(f"unsupported DuckDB value type: {type(value)!r}")


def canonical_row_serialize(values: Sequence[Any]) -> bytes:
    """Serialize one row in explicit schema column order."""

    return _frame(b"R", b"".join(canonical_serialize(value) for value in values))


def canonical_row_digest(values: Sequence[Any]) -> bytes:
    """Return the raw SHA-256 digest for one canonical row."""

    return hashlib.sha256(canonical_row_serialize(values)).digest()


class _SpoolSorter:
    """Bounded-memory external sorter for raw row digests."""

    def __init__(self, root: Path, label: str) -> None:
        self._root = root
        self._label = label
        self._buffer: list[bytes] = []
        self._chunks: list[Path] = []
        self._count = 0
        self._finished: DigestSummary | None = None

    def add(self, digest: bytes) -> None:
        self._buffer.append(digest)
        self._count += 1
        if len(self._buffer) >= _CHUNK_SIZE:
            self._flush()

    def _flush(self) -> None:
        if not self._buffer:
            return
        path = self._root / f"{self._label}-{len(self._chunks):06d}.bin"
        with path.open("wb") as handle:
            for digest in sorted(self._buffer):
                handle.write(digest)
        self._chunks.append(path)
        self._buffer.clear()

    def finish(self) -> DigestSummary:
        if self._finished is not None:
            return self._finished
        self._flush()
        table_hasher = hashlib.sha256()
        try:
            if self._chunks:
                streams = [path.open("rb") for path in self._chunks]
                try:
                    for digest in heapq.merge(
                        *(_iter_digest_records(stream) for stream in streams)
                    ):
                        table_hasher.update(digest)
                finally:
                    for stream in streams:
                        stream.close()
        finally:
            for path in self._chunks:
                try:
                    path.unlink()
                except FileNotFoundError:
                    continue
            self._chunks.clear()
        self._finished = DigestSummary(self._count, table_hasher.hexdigest())
        return self._finished


def _iter_digest_records(stream: Any):
    """Yield fixed-width raw digest records from a binary chunk stream."""

    digest_size = hashlib.sha256().digest_size
    while True:
        chunk = stream.read(digest_size)
        if not chunk:
            break
        if len(chunk) != digest_size:
            raise VerifierError("corrupt digest spool chunk")
        yield chunk


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _collect_inventory(conn: duckdb.DuckDBPyConnection) -> dict[str, TableSpec]:
    """Collect only persistent base tables and their explicit column order/types."""

    table_rows = conn.execute(
        """
        select table_schema, table_name, table_type
        from information_schema.tables
        where table_type = 'BASE TABLE'
          and table_schema not in ('information_schema', 'pg_catalog')
        order by table_schema, table_name
        """
    ).fetchall()
    inventory: dict[str, TableSpec] = {}
    for schema, table, table_type in table_rows:
        columns = conn.execute(
            """
            select column_name, ordinal_position, data_type, is_nullable
            from information_schema.columns
            where table_schema = ? and table_name = ?
            order by ordinal_position
            """,
            [schema, table],
        ).fetchall()
        if not columns:
            raise VerifierError(f"table has no schema columns: {schema}.{table}")
        spec = TableSpec(
            schema=str(schema),
            name=str(table),
            table_type=str(table_type),
            columns=tuple(
                ColumnSpec(
                    name=str(column[0]),
                    ordinal_position=int(column[1]),
                    duckdb_type=str(column[2]),
                    is_nullable=None if column[3] is None else str(column[3]),
                )
                for column in columns
            ),
        )
        inventory[spec.key] = spec
    return inventory


def _parse_iso_date(value: Any, *, table: str, column: str) -> dt.date | None:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        raise VerifierError(
            f"{table}.{column} must not contain a time component: {value!r}"
        )
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text != value:
            raise VerifierError(
                f"{table}.{column} must be an exact ISO date without surrounding whitespace: {value!r}"
            )
        try:
            parsed = dt.date.fromisoformat(text)
        except ValueError as exc:
            try:
                dt.datetime.fromisoformat(text)
            except ValueError:
                pass
            else:
                raise VerifierError(
                    f"{table}.{column} must not contain a time component: {value!r}"
                ) from exc
            raise VerifierError(
                f"{table}.{column} contains non-ISO date value {value!r}"
            ) from exc
        if parsed.isoformat() != text:
            raise VerifierError(
                f"{table}.{column} must be canonical YYYY-MM-DD, got {value!r}"
            )
        return parsed
    raise VerifierError(
        f"{table}.{column} contains unsupported date value type {type(value)!r}"
    )


def _summarize_table(
    conn: duckdb.DuckDBPyConnection,
    spec: TableSpec,
    *,
    temp_root: Path,
    side: str,
    report_date: dt.date,
) -> dict[str, object]:
    columns = ", ".join(_quote_identifier(column.name) for column in spec.columns)
    table_ref = f"{_quote_identifier(spec.schema)}.{_quote_identifier(spec.name)}"
    cursor = conn.execute(f"select {columns} from {table_ref}")
    full = _SpoolSorter(temp_root, f"{side}-{spec.schema}-{spec.name}-full")
    # Policy is schema-qualified on purpose: an ``alt.zqtz_bond_daily_snapshot``
    # table is an out-of-scope table and must not inherit main's allowance.
    is_target_table = spec.key in TARGET_DATE_TABLE_KEYS
    target = (
        _SpoolSorter(temp_root, f"{side}-{spec.schema}-{spec.name}-target")
        if is_target_table
        else None
    )
    non_target = (
        _SpoolSorter(temp_root, f"{side}-{spec.schema}-{spec.name}-non-target")
        if is_target_table
        else None
    )
    report_date_index = None
    if is_target_table:
        report_date_index = next(
            (
                index
                for index, column in enumerate(spec.columns)
                if column.name == "report_date"
            ),
            None,
        )
        if report_date_index is None:
            raise VerifierError(f"target table lacks report_date: {spec.key}")
        report_date_type = spec.columns[report_date_index].duckdb_type.upper()
        if report_date_type not in _ALLOWED_REPORT_DATE_TYPES:
            raise VerifierError(
                f"target table {spec.key}.report_date has unsupported type "
                f"{report_date_type!r}; expected DATE or canonical VARCHAR"
            )

    while True:
        rows = cursor.fetchmany(2_048)
        if not rows:
            break
        for row in rows:
            digest = canonical_row_digest(row)
            full.add(digest)
            if report_date_index is not None:
                row_date = _parse_iso_date(
                    row[report_date_index], table=spec.key, column="report_date"
                )
                if row_date == report_date:
                    assert target is not None
                    target.add(digest)
                else:
                    assert non_target is not None
                    non_target.add(digest)

    result: dict[str, object] = {
        "schema": spec.schema,
        "table": spec.name,
        "columns": [column.as_receipt() for column in spec.columns],
        "full": full.finish().as_receipt(),
    }
    if target is not None and non_target is not None:
        result["target_date"] = {
            "date": report_date.isoformat(),
            **target.finish().as_receipt(),
        }
        result["non_target"] = non_target.finish().as_receipt()
    return result


def _file_fingerprint(path: Path) -> dict[str, object]:
    hasher = hashlib.sha256()
    byte_count = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            hasher.update(chunk)
            byte_count += len(chunk)
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "bytes": byte_count,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": hasher.hexdigest(),
    }


def _snapshot_database(
    path: Path,
    *,
    temp_root: Path,
    side: str,
    report_date: dt.date,
    fingerprint_fn: Callable[[Path], dict[str, object]] | None = None,
) -> dict[str, object]:
    if not path.is_file():
        raise VerifierError(f"DuckDB file does not exist: {path}")
    fingerprint = fingerprint_fn or _file_fingerprint
    fingerprint_before = fingerprint(path)
    inventory: dict[str, TableSpec]
    tables: dict[str, dict[str, object]] = {}
    conn = duckdb.connect(str(path), read_only=True)
    try:
        inventory = _collect_inventory(conn)
        for key in sorted(inventory):
            tables[key] = _summarize_table(
                conn,
                inventory[key],
                temp_root=temp_root,
                side=side,
                report_date=report_date,
            )
    finally:
        conn.close()
    fingerprint_after = fingerprint(path)
    return {
        "fingerprint": fingerprint_after,
        "fingerprint_before": fingerprint_before,
        "fingerprint_after": fingerprint_after,
        "fingerprint_stable": fingerprint_before == fingerprint_after,
        "inventory": inventory,
        "tables": tables,
    }


def _inventory_receipt(inventory: dict[str, TableSpec]) -> list[dict[str, object]]:
    return [inventory[key].as_receipt() for key in sorted(inventory)]


def _inventory_equal(
    before: dict[str, TableSpec], after: dict[str, TableSpec]
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    before_keys = set(before)
    after_keys = set(after)
    if before_keys != after_keys:
        missing = sorted(before_keys - after_keys)
        added = sorted(after_keys - before_keys)
        if missing:
            errors.append(f"schema/table inventory missing tables: {missing}")
        if added:
            errors.append(f"schema/table inventory added tables: {added}")
    for key in sorted(before_keys & after_keys):
        left = before[key]
        right = after[key]
        left_columns = [
            (c.name, c.ordinal_position, c.duckdb_type, c.is_nullable)
            for c in left.columns
        ]
        right_columns = [
            (c.name, c.ordinal_position, c.duckdb_type, c.is_nullable)
            for c in right.columns
        ]
        if left.table_type != right.table_type or left_columns != right_columns:
            errors.append(f"schema drift in {key}")
    return not errors, errors


def _summary_pair_equal(
    before: dict[str, object] | None, after: dict[str, object] | None
) -> bool:
    if before is None or after is None:
        return before == after
    return before.get("row_count") == after.get("row_count") and before.get(
        "table_sha256"
    ) == after.get("table_sha256")


def _compare_snapshots(
    before: dict[str, object], after: dict[str, object]
) -> tuple[list[str], dict[str, dict[str, object]]]:
    before_tables = before["tables"]
    after_tables = after["tables"]
    assert isinstance(before_tables, dict)
    assert isinstance(after_tables, dict)
    errors: list[str] = []
    comparisons: dict[str, dict[str, object]] = {}
    for key in sorted(set(before_tables) | set(after_tables)):
        left = before_tables.get(key)
        right = after_tables.get(key)
        if left is None or right is None:
            # Inventory comparison emits the detailed missing/added table error.
            continue
        assert isinstance(left, dict)
        assert isinstance(right, dict)
        full_before = left.get("full")
        full_after = right.get("full")
        if key in TARGET_DATE_TABLE_KEYS:
            non_before = left.get("non_target")
            non_after = right.get("non_target")
            unchanged = _summary_pair_equal(non_before, non_after)
            changed = not _summary_pair_equal(full_before, full_after)
            comparisons[key] = {
                "delta_policy": "target_date_only",
                "allowed": unchanged,
                "full_changed": changed,
                "before": left,
                "after": right,
            }
            if not unchanged:
                errors.append(f"non-target-date rows changed in {key}")
        else:
            unchanged = _summary_pair_equal(full_before, full_after)
            comparisons[key] = {
                "delta_policy": "table_unchanged",
                "allowed": unchanged,
                "full_changed": not unchanged,
                "before": left,
                "after": right,
            }
            if not unchanged:
                errors.append(f"unexpected table change in {key}")
    return errors, comparisons


def _verifier_source_sha256() -> str:
    try:
        return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    except OSError:
        return ""


def _write_receipt(path: Path, receipt: dict[str, object]) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)


def verify_databases(
    baseline_path: str | Path,
    current_path: str | Path,
    report_date: str | dt.date = DEFAULT_REPORT_DATE,
    *,
    receipt_path: str | Path | None = None,
    temp_dir: str | Path | None = None,
    fingerprint_fn: Callable[[Path], dict[str, object]] | None = None,
) -> dict[str, object]:
    """Compare two DuckDB files and return a machine-readable verification receipt."""

    baseline = Path(baseline_path).expanduser().resolve()
    current = Path(current_path).expanduser().resolve()
    if isinstance(report_date, dt.datetime):
        target_date = report_date.date()
    elif isinstance(report_date, dt.date):
        target_date = report_date
    else:
        target_date = _parse_iso_date(
            report_date, table="<argument>", column="report_date"
        )
        if target_date is None:
            raise VerifierError("report_date cannot be null")

    receipt: dict[str, object] = {
        "schema_version": 1,
        "verifier_version": VERIFIER_VERSION,
        "verifier_source_sha256": _verifier_source_sha256(),
        "status": "fail",
        "verdict": "FAIL",
        "report_date": target_date.isoformat(),
        "allowed_target_date_tables": sorted(TARGET_DATE_TABLES),
        "allowed_target_date_table_keys": sorted(TARGET_DATE_TABLE_KEYS),
        "frozen_tables": sorted(FROZEN_TABLES),
        "frozen_table_keys": sorted(FROZEN_TABLE_KEYS),
        "all_other_base_tables_policy": "unchanged_full_table_digest",
        "algorithm": {
            "canonical_serialization": "typed length-framed UTF-8/binary bytes; Decimal as sign+digits+exponent tuple",
            "row_digest": "SHA256(canonical_row_bytes)",
            "table_digest": "SHA256(concatenated raw row digests sorted by byte order)",
            "schema_inventory": "BASE TABLE table schema/name/type plus ordered column name/type/nullability",
            "inventory_scope": "BASE TABLE only; views/indexes/constraints require the runner schema-registry gate",
        },
        "baseline": {"path": str(baseline)},
        "current": {"path": str(current)},
        "temp_dir": None,
        "checks": {
            "fingerprint": {"status": "not_checked"},
            "inventory": {"status": "not_checked"},
            "tables": {},
        },
        "errors": [],
    }

    errors: list[str] = []
    if os.path.normcase(str(baseline)) == os.path.normcase(str(current)):
        errors.append("baseline and current DuckDB paths must be distinct")
    tmp_base = Path(temp_dir).expanduser().resolve() if temp_dir is not None else None
    if tmp_base is not None:
        tmp_base.mkdir(parents=True, exist_ok=True)

    try:
        with tempfile.TemporaryDirectory(
            prefix="decimal-verifier-", dir=str(tmp_base) if tmp_base else None
        ) as temp_name:
            temp_root = Path(temp_name)
            receipt["temp_dir"] = str(temp_root)
            before = _snapshot_database(
                baseline,
                temp_root=temp_root,
                side="baseline",
                report_date=target_date,
                fingerprint_fn=fingerprint_fn,
            )
            after = _snapshot_database(
                current,
                temp_root=temp_root,
                side="current",
                report_date=target_date,
                fingerprint_fn=fingerprint_fn,
            )
            receipt["baseline"].update(
                {
                    "fingerprint": before["fingerprint"],
                    "fingerprint_before": before["fingerprint_before"],
                    "fingerprint_after": before["fingerprint_after"],
                    "fingerprint_stable": before["fingerprint_stable"],
                    "inventory": _inventory_receipt(before["inventory"]),
                }
            )
            receipt["current"].update(
                {
                    "fingerprint": after["fingerprint"],
                    "fingerprint_before": after["fingerprint_before"],
                    "fingerprint_after": after["fingerprint_after"],
                    "fingerprint_stable": after["fingerprint_stable"],
                    "inventory": _inventory_receipt(after["inventory"]),
                }
            )
            fingerprint_errors = []
            if not before["fingerprint_stable"]:
                fingerprint_errors.append(
                    "baseline DuckDB fingerprint changed during read-only scan"
                )
            if not after["fingerprint_stable"]:
                fingerprint_errors.append(
                    "current DuckDB fingerprint changed during read-only scan"
                )
            errors.extend(fingerprint_errors)
            receipt["checks"]["fingerprint"] = {
                "status": "pass" if not fingerprint_errors else "fail",
                "errors": fingerprint_errors,
                "baseline_stable": before["fingerprint_stable"],
                "current_stable": after["fingerprint_stable"],
            }
            inventory_ok, inventory_errors = _inventory_equal(
                before["inventory"], after["inventory"]
            )
            errors.extend(inventory_errors)
            receipt["checks"]["inventory"] = {
                "status": "pass" if inventory_ok else "fail",
                "errors": inventory_errors,
            }
            if inventory_ok:
                table_errors, comparisons = _compare_snapshots(before, after)
                errors.extend(table_errors)
                receipt["checks"]["tables"] = comparisons
            else:
                receipt["checks"]["tables"] = {}
    except Exception as exc:  # fail closed and still emit machine JSON
        errors.append(f"verification error: {type(exc).__name__}: {exc}")

    receipt["errors"] = errors
    if not errors:
        receipt["status"] = "pass"
        receipt["verdict"] = "PASS"
    else:
        receipt["status"] = "fail"
        receipt["verdict"] = "FAIL"

    if receipt_path is not None:
        try:
            resolved_receipt_path = Path(receipt_path).expanduser().resolve()
            receipt["receipt_path"] = str(resolved_receipt_path)
            if os.path.normcase(str(resolved_receipt_path)) in {
                os.path.normcase(str(baseline)),
                os.path.normcase(str(current)),
            }:
                raise VerifierError(
                    "receipt path must not overwrite either DuckDB input"
                )
            _write_receipt(resolved_receipt_path, receipt)
        except Exception as exc:  # receipt durability is part of the evidence contract
            receipt["status"] = "fail"
            receipt["verdict"] = "FAIL"
            errors.append(f"receipt write error: {type(exc).__name__}: {exc}")
            receipt["errors"] = errors
    return receipt


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline",
        "--baseline-db",
        "--before",
        dest="baseline",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--current",
        "--current-db",
        "--after",
        dest="current",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--report-date",
        "--target-date",
        default=DEFAULT_REPORT_DATE.isoformat(),
        help="Target date (ISO YYYY-MM-DD).",
    )
    parser.add_argument(
        "--receipt", "--receipt-path", "--output", dest="receipt", type=Path
    )
    parser.add_argument(
        "--temp-dir",
        type=Path,
        help="Parent for controlled external-sort temporary files.",
    )
    return parser


# Short aliases keep the script convenient to import from focused tests without
# hiding the descriptive public function used by the CLI.
verify = verify_databases


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        receipt = verify_databases(
            args.baseline,
            args.current,
            report_date=args.report_date,
            receipt_path=args.receipt,
            temp_dir=args.temp_dir,
        )
    except Exception as exc:
        receipt = {
            "schema_version": 1,
            "verifier_version": VERIFIER_VERSION,
            "status": "fail",
            "verdict": "FAIL",
            "errors": [f"verification error: {type(exc).__name__}: {exc}"],
        }
        if args.receipt is not None:
            try:
                _write_receipt(args.receipt, receipt)
            except Exception as write_exc:
                receipt["errors"].append(
                    f"receipt write error: {type(write_exc).__name__}: {write_exc}"
                )
    print(
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
    return 0 if receipt.get("status") == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
