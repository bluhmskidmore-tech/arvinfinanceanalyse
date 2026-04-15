from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

IB_ASSET_PREDICATE = (
    "(instr(lower(coalesce(position_side, '')), 'asset') > 0 "
    "or instr(coalesce(position_side, ''), '资产') > 0)"
)


@dataclass
class LiabilityAnalyticsRepository:
    path: str

    def _connect(self) -> duckdb.DuckDBPyConnection | None:
        if not Path(self.path).exists():
            return None
        return duckdb.connect(self.path, read_only=True)

    def _table_exists(self, conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
        row = conn.execute(
            """
            select 1
            from information_schema.tables
            where table_name = ?
            limit 1
            """,
            [table_name],
        ).fetchone()
        return row is not None

    @staticmethod
    def _fetch_dict_rows(
        conn: duckdb.DuckDBPyConnection,
        query: str,
        params: list[object] | None = None,
    ) -> list[dict[str, Any]]:
        cursor = conn.execute(query, params or [])
        columns = [item[0] for item in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def resolve_latest_report_date(self) -> str | None:
        conn = self._connect()
        if conn is None:
            return None
        try:
            candidates: list[str] = []
            if self._table_exists(conn, "zqtz_bond_daily_snapshot"):
                row = conn.execute(
                    "select cast(max(report_date) as varchar) from zqtz_bond_daily_snapshot"
                ).fetchone()
                if row and row[0]:
                    candidates.append(str(row[0]))
            if self._table_exists(conn, "tyw_interbank_daily_snapshot"):
                row = conn.execute(
                    "select cast(max(report_date) as varchar) from tyw_interbank_daily_snapshot"
                ).fetchone()
                if row and row[0]:
                    candidates.append(str(row[0]))
            if not candidates:
                return None
            return max(candidates)
        finally:
            conn.close()

    def fetch_zqtz_rows(self, report_date: str) -> list[dict[str, Any]]:
        conn = self._connect()
        if conn is None:
            return []
        try:
            if not self._table_exists(conn, "zqtz_bond_daily_snapshot"):
                return []
            return self._fetch_dict_rows(
                conn,
                """
                select report_date, instrument_code, instrument_name, asset_class, bond_type, is_issuance_like,
                       face_value_native, market_value_native, amortized_cost_native,
                       coupon_rate, ytm_value, maturity_date
                from zqtz_bond_daily_snapshot
                where report_date = ?::date
                """,
                [report_date],
            )
        finally:
            conn.close()

    def fetch_tyw_rows(self, report_date: str) -> list[dict[str, Any]]:
        conn = self._connect()
        if conn is None:
            return []
        try:
            if not self._table_exists(conn, "tyw_interbank_daily_snapshot"):
                return []
            return self._fetch_dict_rows(
                conn,
                f"""
                select report_date, position_id, product_type, position_side, counterparty_name,
                       core_customer_type, principal_native, funding_cost_rate, maturity_date,
                       case when {IB_ASSET_PREDICATE} then true else false end as is_asset_side
                from tyw_interbank_daily_snapshot
                where report_date = ?::date
                """,
                [report_date],
            )
        finally:
            conn.close()

    def fetch_zqtz_liability_rows_for_year(self, year: int) -> list[dict[str, Any]]:
        conn = self._connect()
        if conn is None:
            return []
        try:
            if not self._table_exists(conn, "zqtz_bond_daily_snapshot"):
                return []
            return self._fetch_dict_rows(
                conn,
                """
                select report_date, instrument_code, instrument_name, asset_class, bond_type,
                       face_value_native, market_value_native, amortized_cost_native,
                       coupon_rate, maturity_date
                from zqtz_bond_daily_snapshot
                where report_date between ?::date and ?::date
                  and coalesce(is_issuance_like, false)
                """,
                [f"{year:04d}-01-01", f"{year:04d}-12-31"],
            )
        finally:
            conn.close()

    def fetch_tyw_liability_rows_for_year(self, year: int) -> list[dict[str, Any]]:
        conn = self._connect()
        if conn is None:
            return []
        try:
            if not self._table_exists(conn, "tyw_interbank_daily_snapshot"):
                return []
            return self._fetch_dict_rows(
                conn,
                f"""
                select report_date, position_id, product_type, position_side, counterparty_name,
                       core_customer_type, principal_native, funding_cost_rate, maturity_date
                from tyw_interbank_daily_snapshot
                where report_date between ?::date and ?::date
                  and not ({IB_ASSET_PREDICATE})
                """,
                [f"{year:04d}-01-01", f"{year:04d}-12-31"],
            )
        finally:
            conn.close()
