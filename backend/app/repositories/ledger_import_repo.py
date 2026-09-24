from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection
from backend.app.repositories.task_write_guard import require_repository_task_write_scope
from backend.app.schema_registry.duckdb_loader import REGISTRY_DIR, parse_registry_sql_text

LEDGER_IMPORT_LOCK = LockDefinition(
    key="lock:duckdb:ledger-import",
    ttl_seconds=120,
)

SNAPSHOT_COLUMNS = (
    "batch_id",
    "row_no",
    "as_of_date",
    "position_key",
    "direction",
    "bond_code",
    "bond_name",
    "counterparty_cif_no",
    "portfolio",
    "business_type",
    "credit_customer_attribute",
    "business_type_1",
    "account_category_std",
    "cost_center",
    "asset_class_std",
    "risk_mitigation",
    "face_amount",
    "fair_value",
    "amortized_cost",
    "accrued_interest",
    "interest_method",
    "coupon_rate",
    "interest_start_date",
    "maturity_date",
    "interest_rate_benchmark_code",
    "interest_rate_reset_frequency",
    "counterparty_industry",
    "counterparty_name_cn",
    "credit_customer_id",
    "credit_customer_no",
    "credit_customer_rating",
    "credit_customer_industry",
    "interest_receivable_payable",
    "currency",
    "credit_customer_name",
    "manual_impairment_adjustment",
    "channel",
    "legal_customer_name",
    "legal_customer_id",
    "group_customer_name",
    "group_customer_id",
    "principal_overdue_flag",
    "interest_overdue_flag",
    "quantity",
    "latest_face_value",
    "principal_overdue_days",
    "interest_overdue_days",
    "yield_to_maturity",
    "option_or_special_maturity_date",
    "source_version",
    "rule_version",
)


def ensure_ledger_import_tables(conn: duckdb.DuckDBPyConnection) -> None:
    text = (REGISTRY_DIR / "19_ledger_import.sql").read_text(encoding="utf-8")
    for statement in parse_registry_sql_text(text):
        conn.execute(statement)


@dataclass(slots=True)
class LedgerImportRepository:
    path: str

    def insert_import(
        self,
        *,
        file_name: str,
        file_hash: str,
        as_of_date: str,
        rows: list[dict[str, Any]],
        source_version: str,
        rule_version: str,
    ) -> dict[str, Any]:
        require_repository_task_write_scope("ledger_import.insert")
        duckdb_file = Path(self.path)
        duckdb_file.parent.mkdir(parents=True, exist_ok=True)
        # Acquire the named lock before opening the write connection so the
        # DuckDB writer handle is never held while waiting for the lock.
        with acquire_lock(
            LEDGER_IMPORT_LOCK,
            base_dir=duckdb_file.parent,
            timeout_seconds=30,
        ):
            conn = duckdb.connect(str(duckdb_file), read_only=False)
            try:
                apply_pending_migrations_on_connection(conn)
                ensure_ledger_import_tables(conn)
                existing = self._find_success_batch_by_hash(conn, file_hash)
                if existing is not None:
                    return {
                        **existing,
                        "file_name": file_name,
                        "status": "duplicate",
                        "duplicate_of_batch_id": existing["batch_id"],
                    }

                batch_id = self._next_batch_id(conn)
                created_at = conn.execute("select current_timestamp::varchar").fetchone()[0]
                conn.execute("begin transaction")
                try:
                    conn.execute(
                        """
                        insert into ledger_import_batch (
                          batch_id, file_name, file_hash, as_of_date, status, row_count,
                          error_count, source_version, rule_version, duplicate_of_batch_id, created_at
                        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            batch_id,
                            file_name,
                            file_hash,
                            as_of_date,
                            "success",
                            len(rows),
                            0,
                            source_version,
                            rule_version,
                            None,
                            created_at,
                        ],
                    )
                    conn.executemany(
                        """
                        insert into ledger_raw_row (
                          batch_id, row_no, raw_json, source_version, rule_version
                        ) values (?, ?, ?, ?, ?)
                        """,
                        [
                            [
                                batch_id,
                                int(row["row_no"]),
                                str(row["raw_json"]),
                                source_version,
                                rule_version,
                            ]
                            for row in rows
                        ],
                    )
                    placeholders = ", ".join("?" for _ in SNAPSHOT_COLUMNS)
                    conn.executemany(
                        f"""
                        insert into position_snapshot ({", ".join(SNAPSHOT_COLUMNS)})
                        values ({placeholders})
                        """,
                        [
                            [
                                batch_id if column == "batch_id" else row.get(column)
                                for column in SNAPSHOT_COLUMNS
                            ]
                            for row in rows
                        ],
                    )
                    conn.execute("commit")
                except Exception:
                    conn.execute("rollback")
                    raise

                return {
                    "batch_id": batch_id,
                    "file_name": file_name,
                    "file_hash": file_hash,
                    "as_of_date": as_of_date,
                    "status": "success",
                    "row_count": len(rows),
                    "error_count": 0,
                    "source_version": source_version,
                    "rule_version": rule_version,
                    "duplicate_of_batch_id": None,
                    "created_at": created_at,
                }
            finally:
                conn.close()

    def attest_classification_rule_versions(
        self,
        *,
        batch_ids: list[int],
        from_rule_versions: dict[int, str],
        target_rule_version: str,
        expected_immutable_evidence_digest: str,
    ) -> dict[str, int | bool]:
        """Atomically attest selected ledger rows after task-owned replay validation."""
        require_repository_task_write_scope("ledger_import.classification_backfill")
        if not batch_ids:
            raise ValueError("At least one batch id is required.")
        ordered_ids = sorted(set(int(value) for value in batch_ids))
        if len(ordered_ids) != len(batch_ids):
            raise ValueError("Duplicate batch ids are not allowed.")

        conn = duckdb.connect(str(Path(self.path)), read_only=False)
        try:
            conn.execute("begin transaction")
            try:
                before_evidence = classification_immutable_evidence(conn, ordered_ids)
                if before_evidence["digest"] != expected_immutable_evidence_digest:
                    raise RuntimeError("Backfill immutable preimage drifted before apply.")
                expected_rows = 0
                update_ids: list[int] = []
                update_expected_rows = 0
                for batch_id in ordered_ids:
                    expected_rule = from_rule_versions[batch_id]
                    batch = conn.execute(
                        "select rule_version, row_count from ledger_import_batch where batch_id = ?",
                        [batch_id],
                    ).fetchone()
                    if batch is None or str(batch[0]) != expected_rule:
                        raise RuntimeError(f"Batch {batch_id} rule version drifted before apply.")
                    expected_count = int(batch[1])
                    expected_rows += expected_count
                    if expected_rule != target_rule_version:
                        update_ids.append(batch_id)
                        update_expected_rows += expected_count
                    for table_name in ("ledger_raw_row", "position_snapshot"):
                        count, distinct_keys = conn.execute(
                            f"select count(*), count(distinct row_no) from {table_name} where batch_id = ? and rule_version = ?",
                            [batch_id, expected_rule],
                        ).fetchone()
                        if int(count) != expected_count or int(distinct_keys) != expected_count:
                            raise RuntimeError(f"Batch {batch_id} {table_name} count/key lineage drifted before apply.")
                    if not _classification_row_keys_tie(conn, batch_id):
                        raise RuntimeError(f"Batch {batch_id} raw/snapshot row keys drifted before apply.")

                placeholders = ", ".join("?" for _ in ordered_ids)
                if update_ids:
                    update_placeholders = ", ".join("?" for _ in update_ids)
                    params = [target_rule_version, *update_ids]
                    snapshot_updated = len(conn.execute(
                        f"update position_snapshot set rule_version = ? where batch_id in ({update_placeholders}) returning 1",
                        params,
                    ).fetchall())
                    raw_updated = len(conn.execute(
                        f"update ledger_raw_row set rule_version = ? where batch_id in ({update_placeholders}) returning 1",
                        params,
                    ).fetchall())
                    batch_updated = len(conn.execute(
                        f"update ledger_import_batch set rule_version = ? where batch_id in ({update_placeholders}) returning 1",
                        params,
                    ).fetchall())
                else:
                    snapshot_updated = raw_updated = batch_updated = 0
                if (snapshot_updated, raw_updated, batch_updated) != (
                    update_expected_rows, update_expected_rows, len(update_ids)
                ):
                    raise RuntimeError("Backfill update counts failed the atomic post-check.")
                current_batches = int(conn.execute(
                    f"select count(*) from ledger_import_batch where batch_id in ({placeholders}) and rule_version = ?",
                    [*ordered_ids, target_rule_version],
                ).fetchone()[0])
                if current_batches != len(ordered_ids):
                    raise RuntimeError("ledger_import_batch failed the rule-version post-check.")
                for batch_id in ordered_ids:
                    expected_count = int(conn.execute(
                        "select row_count from ledger_import_batch where batch_id = ?",
                        [batch_id],
                    ).fetchone()[0])
                    for table_name in ("position_snapshot", "ledger_raw_row"):
                        count, distinct_keys = conn.execute(
                            f"select count(*), count(distinct row_no) from {table_name} where batch_id = ? and rule_version = ?",
                            [batch_id, target_rule_version],
                        ).fetchone()
                        if int(count) != expected_count or int(distinct_keys) != expected_count:
                            raise RuntimeError(f"{table_name} failed the count/key/rule post-check.")
                    if not _classification_row_keys_tie(conn, batch_id):
                        raise RuntimeError(f"Batch {batch_id} raw/snapshot row keys failed the post-check.")
                after_evidence = classification_immutable_evidence(conn, ordered_ids)
                if after_evidence != before_evidence:
                    raise RuntimeError("Backfill changed immutable evidence; transaction rolled back.")
                conn.execute("commit")
            except Exception:
                conn.execute("rollback")
                raise
        finally:
            conn.close()
        return {
            "batches_updated": batch_updated,
            "raw_rows_updated": raw_updated,
            "snapshot_rows_updated": snapshot_updated,
            "position_snapshot_agg_unchanged": True,
        }
    def list_batches(self, *, limit: int = 20) -> list[dict[str, Any]]:
        duckdb_file = Path(self.path)
        if not duckdb_file.is_file():
            return []
        conn = duckdb.connect(str(duckdb_file), read_only=True)
        try:
            if not _table_exists(conn, "ledger_import_batch"):
                return []
            rows = conn.execute(
                """
                select
                  batch_id, file_name, file_hash, status, as_of_date, row_count,
                  error_count, created_at, source_version, rule_version
                from ledger_import_batch
                order by batch_id desc
                limit ?
                """,
                [limit],
            ).fetchall()
        finally:
            conn.close()
        return [
            {
                "batch_id": int(row[0]),
                "filename": str(row[1]),
                "file_hash": str(row[2]),
                "status": str(row[3]),
                "as_of_date": str(row[4]),
                "row_count": int(row[5]),
                "error_count": int(row[6]),
                "created_at": str(row[7]),
                "source_version": str(row[8]),
                "rule_version": str(row[9]),
            }
            for row in rows
        ]

    @staticmethod
    def _find_success_batch_by_hash(
        conn: duckdb.DuckDBPyConnection,
        file_hash: str,
    ) -> dict[str, Any] | None:
        row = conn.execute(
            """
            select
              batch_id, file_name, file_hash, as_of_date, status, row_count,
              error_count, source_version, rule_version, created_at
            from ledger_import_batch
            where file_hash = ? and status = 'success'
            order by batch_id asc
            limit 1
            """,
            [file_hash],
        ).fetchone()
        if row is None:
            return None
        return {
            "batch_id": int(row[0]),
            "file_name": str(row[1]),
            "file_hash": str(row[2]),
            "as_of_date": str(row[3]),
            "status": str(row[4]),
            "row_count": int(row[5]),
            "error_count": int(row[6]),
            "source_version": str(row[7]),
            "rule_version": str(row[8]),
            "created_at": str(row[9]),
        }

    @staticmethod
    def _next_batch_id(conn: duckdb.DuckDBPyConnection) -> int:
        row = conn.execute("select coalesce(max(batch_id), 0) + 1 from ledger_import_batch").fetchone()
        return int(row[0])


def _classification_row_keys_tie(conn: duckdb.DuckDBPyConnection, batch_id: int) -> bool:
    difference_count = conn.execute(
        """
        select count(*) from (
          (select row_no from ledger_raw_row where batch_id = ?
           except select row_no from position_snapshot where batch_id = ?)
          union all
          (select row_no from position_snapshot where batch_id = ?
           except select row_no from ledger_raw_row where batch_id = ?)
        )
        """,
        [batch_id, batch_id, batch_id, batch_id],
    ).fetchone()[0]
    return int(difference_count) == 0


def classification_immutable_evidence(
    conn: duckdb.DuckDBPyConnection,
    batch_ids: list[int],
) -> dict[str, Any]:
    placeholders = ", ".join("?" for _ in batch_ids)
    batch_columns = (
        "batch_id", "file_name", "file_hash", "as_of_date", "status", "row_count",
        "error_count", "source_version", "duplicate_of_batch_id", "created_at",
    )
    raw_columns = ("batch_id", "row_no", "raw_json", "source_version")
    snapshot_columns = tuple(column for column in SNAPSHOT_COLUMNS if column != "rule_version")
    agg_present = _table_exists(conn, "position_snapshot_agg")
    agg_rows = (
        conn.execute(
            f"select * from position_snapshot_agg where batch_id in ({placeholders}) order by batch_id, as_of_date",
            batch_ids,
        ).fetchall()
        if agg_present
        else []
    )
    evidence = {
        "batches": conn.execute(
            f"select {', '.join(batch_columns)} from ledger_import_batch where batch_id in ({placeholders}) order by batch_id",
            batch_ids,
        ).fetchall(),
        "raw": conn.execute(
            f"select {', '.join(raw_columns)} from ledger_raw_row where batch_id in ({placeholders}) order by batch_id, row_no",
            batch_ids,
        ).fetchall(),
        "snapshot": conn.execute(
            f"select {', '.join(snapshot_columns)} from position_snapshot where batch_id in ({placeholders}) order by batch_id, row_no",
            batch_ids,
        ).fetchall(),
        "position_snapshot_agg": agg_rows,
    }
    canonical = json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return {
        "digest": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "position_snapshot_agg": {
            "table_present": agg_present,
            "row_count": len(agg_rows),
            "digest": hashlib.sha256(
                json.dumps(agg_rows, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
            ).hexdigest(),
        },
    }


def _classification_immutable_evidence_digest(
    conn: duckdb.DuckDBPyConnection,
    batch_ids: list[int],
) -> str:
    return str(classification_immutable_evidence(conn, batch_ids)["digest"])

def _table_exists(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    row = conn.execute(
        """
        select 1
        from information_schema.tables
        where table_schema = 'main' and table_name = ?
        limit 1
        """,
        [table_name],
    ).fetchone()
    return row is not None
