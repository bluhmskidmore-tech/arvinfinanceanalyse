from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection
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
        duckdb_file = Path(self.path)
        duckdb_file.parent.mkdir(parents=True, exist_ok=True)
        conn = duckdb.connect(str(duckdb_file), read_only=False)
        try:
            with acquire_lock(
                LEDGER_IMPORT_LOCK,
                base_dir=duckdb_file.parent,
                timeout_seconds=30,
            ):
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

    def list_batches(self, *, limit: int = 20) -> list[dict[str, Any]]:
        duckdb_file = Path(self.path)
        duckdb_file.parent.mkdir(parents=True, exist_ok=True)
        conn = duckdb.connect(str(duckdb_file), read_only=False)
        try:
            apply_pending_migrations_on_connection(conn)
            ensure_ledger_import_tables(conn)
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
