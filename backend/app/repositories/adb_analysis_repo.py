from __future__ import annotations

from datetime import date
from typing import Any

import duckdb
import pandas as pd

from backend.app.repositories.duckdb_repo import DuckDBRepository, read_only_connection

RELATION_FACT_FORMAL_ZQTZ_BALANCE_DAILY = "fact_formal_zqtz_balance_daily"
RELATION_FACT_FORMAL_TYW_BALANCE_DAILY = "fact_formal_tyw_balance_daily"
RELATION_ZQTZ_BOND_DAILY_SNAPSHOT = "zqtz_bond_daily_snapshot"
RELATION_TYW_INTERBANK_DAILY_SNAPSHOT = "tyw_interbank_daily_snapshot"

_ADB_READ_RELATIONS = frozenset(
    {
        RELATION_FACT_FORMAL_ZQTZ_BALANCE_DAILY,
        RELATION_FACT_FORMAL_TYW_BALANCE_DAILY,
        RELATION_ZQTZ_BOND_DAILY_SNAPSHOT,
        RELATION_TYW_INTERBANK_DAILY_SNAPSHOT,
    }
)

OPTIONAL_ZQTZ_CLASSIFIER_COLUMNS = (
    "instrument_code",
    "instrument_name",
    "business_type_primary",
    "business_type_final",
    "sub_type",
    "currency_code",
    "accounting_basis",
)


class AdbAnalysisRepository(DuckDBRepository):
    """Read-only ADB formal balance and snapshot tables via shared DuckDB helpers."""

    @staticmethod
    def table_exists(
        conn: duckdb.DuckDBPyConnection,
        name: str,
    ) -> bool:
        """Detect physical tables reliably (DuckDB ``information_schema`` casing/catalog quirks)."""
        if name not in _ADB_READ_RELATIONS:
            return False
        try:
            row = conn.execute(
                """
                select 1 from duckdb_tables()
                where lower(table_name) = lower(?)
                limit 1
                """,
                [name],
            ).fetchone()
            if row is not None:
                return True
        except duckdb.Error:
            pass
        row = conn.execute(
            """
            select 1 from information_schema.tables
            where lower(table_name) = lower(?) limit 1
            """,
            [name],
        ).fetchone()
        return row is not None

    @staticmethod
    def column_exists(
        conn: duckdb.DuckDBPyConnection,
        table: str,
        column: str,
    ) -> bool:
        if table not in _ADB_READ_RELATIONS:
            return False
        try:
            row = conn.execute(
                """
                select 1 from information_schema.columns
                where lower(table_name) = lower(?) and lower(column_name) = lower(?)
                limit 1
                """,
                [table, column],
            ).fetchone()
            return row is not None
        except duckdb.Error:
            return False

    @classmethod
    def select_list_zqtz_formal(cls, conn: duckdb.DuckDBPyConnection) -> str:
        table = RELATION_FACT_FORMAL_ZQTZ_BALANCE_DAILY
        base = [
            "report_date",
            "position_scope",
            "market_value_amount",
            "ytm_value",
            "coupon_rate",
            "asset_class",
            "bond_type",
            "is_issuance_like",
            "source_version",
            "rule_version",
        ]
        parts = list(base)
        for col in OPTIONAL_ZQTZ_CLASSIFIER_COLUMNS:
            if cls.column_exists(conn, table, col):
                parts.append(col)
            else:
                parts.append(f"cast(null as varchar) as {col}")
        return ",\n                  ".join(parts)

    @classmethod
    def select_list_zqtz_snapshot(cls, conn: duckdb.DuckDBPyConnection) -> str:
        table = RELATION_ZQTZ_BOND_DAILY_SNAPSHOT
        header = [
            "report_date",
            "case when is_issuance_like then 'liability' else 'asset' end as position_scope",
            "market_value_native as market_value_amount",
            "ytm_value",
            "coupon_rate",
            "asset_class",
            "bond_type",
            "is_issuance_like",
            "source_version",
            "rule_version",
        ]
        parts = list(header)
        for col in OPTIONAL_ZQTZ_CLASSIFIER_COLUMNS:
            if cls.column_exists(conn, table, col):
                parts.append(col)
            else:
                parts.append(f"cast(null as varchar) as {col}")
        return ",\n                      ".join(parts)

    def fetch_formal_zqtz_df(
        self,
        start_date: date,
        end_date: date,
        *,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> pd.DataFrame:
        if conn is not None:
            return self._fetch_formal_zqtz_df_impl(conn, start_date, end_date)
        with read_only_connection(self.path) as scoped:
            return self._fetch_formal_zqtz_df_impl(scoped, start_date, end_date)

    def fetch_formal_tyw_df(
        self,
        start_date: date,
        end_date: date,
        *,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> pd.DataFrame:
        if conn is not None:
            return self._fetch_formal_tyw_df_impl(conn, start_date, end_date)
        with read_only_connection(self.path) as scoped:
            return self._fetch_formal_tyw_df_impl(scoped, start_date, end_date)

    def snapshot_report_dates(
        self,
        table_name: str,
        start_date: date,
        end_date: date,
        *,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> set[str]:
        if conn is not None:
            return self._snapshot_report_dates_impl(conn, table_name, start_date, end_date)
        with read_only_connection(self.path) as scoped:
            return self._snapshot_report_dates_impl(scoped, table_name, start_date, end_date)

    def fetch_zqtz_snapshot_df(
        self,
        start_date: date,
        end_date: date,
        missing_dates: list[str],
        *,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> pd.DataFrame:
        if not missing_dates:
            return pd.DataFrame()
        if conn is not None:
            return self._fetch_zqtz_snapshot_df_impl(conn, start_date, end_date, missing_dates)
        with read_only_connection(self.path) as scoped:
            return self._fetch_zqtz_snapshot_df_impl(scoped, start_date, end_date, missing_dates)

    def fetch_tyw_snapshot_df(
        self,
        start_date: date,
        end_date: date,
        missing_dates: list[str],
        *,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> pd.DataFrame:
        if not missing_dates:
            return pd.DataFrame()
        if conn is not None:
            return self._fetch_tyw_snapshot_df_impl(conn, start_date, end_date, missing_dates)
        with read_only_connection(self.path) as scoped:
            return self._fetch_tyw_snapshot_df_impl(scoped, start_date, end_date, missing_dates)

    def date_coverage_for_table(
        self,
        table: str,
        start_date: date,
        end_date: date,
        *,
        currency_basis: str | None = None,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> dict[str, Any]:
        if conn is not None:
            return self._date_coverage_for_table_impl(
                conn,
                table=table,
                start_date=start_date,
                end_date=end_date,
                currency_basis=currency_basis,
            )
        with read_only_connection(self.path) as scoped:
            return self._date_coverage_for_table_impl(
                scoped,
                table=table,
                start_date=start_date,
                end_date=end_date,
                currency_basis=currency_basis,
            )

    @classmethod
    def _fetch_formal_zqtz_df_impl(
        cls,
        conn: duckdb.DuckDBPyConnection,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        return conn.execute(
            f"""
            select
              {cls.select_list_zqtz_formal(conn)}
            from {RELATION_FACT_FORMAL_ZQTZ_BALANCE_DAILY}
            where cast(report_date as date) between ? and ?
              and currency_basis = 'CNY'
            """,
            [start_date, end_date],
        ).fetchdf()

    @staticmethod
    def _fetch_formal_tyw_df_impl(
        conn: duckdb.DuckDBPyConnection,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        return conn.execute(
            """
            select
              report_date,
              position_scope,
              position_side,
              principal_amount,
              funding_cost_rate,
              product_type,
              source_version,
              rule_version
            from fact_formal_tyw_balance_daily
            where cast(report_date as date) between ? and ?
              and currency_basis = 'CNY'
            """,
            [start_date, end_date],
        ).fetchdf()

    @classmethod
    def _snapshot_report_dates_impl(
        cls,
        conn: duckdb.DuckDBPyConnection,
        table_name: str,
        start_date: date,
        end_date: date,
    ) -> set[str]:
        if table_name not in _ADB_READ_RELATIONS:
            return set()
        if not cls.table_exists(conn, table_name):
            return set()
        rows = conn.execute(
            f"""
            select distinct strftime(try_cast(report_date as date), '%Y-%m-%d')
            from {table_name}
            where try_cast(report_date as date) between ? and ?
            """,
            [start_date, end_date],
        ).fetchall()
        return {str(row[0]) for row in rows if row[0]}

    @classmethod
    def _fetch_zqtz_snapshot_df_impl(
        cls,
        conn: duckdb.DuckDBPyConnection,
        start_date: date,
        end_date: date,
        missing_dates: list[str],
    ) -> pd.DataFrame:
        placeholders = ", ".join(["?"] * len(missing_dates))
        zqtz_snap_sql = (
            f"""
            select
              {cls.select_list_zqtz_snapshot(conn)}
            from {RELATION_ZQTZ_BOND_DAILY_SNAPSHOT}
            where cast(report_date as date) between ? and ?
              and strftime(try_cast(report_date as date), '%Y-%m-%d') in ({placeholders})
            """
        )
        return conn.execute(
            zqtz_snap_sql,
            [start_date, end_date, *missing_dates],
        ).fetchdf()

    @staticmethod
    def _fetch_tyw_snapshot_df_impl(
        conn: duckdb.DuckDBPyConnection,
        start_date: date,
        end_date: date,
        missing_dates: list[str],
    ) -> pd.DataFrame:
        placeholders = ", ".join(["?"] * len(missing_dates))
        tyw_snap_sql = f"""
            select
              report_date,
              coalesce(position_side, 'all') as position_scope,
              position_side,
              principal_native as principal_amount,
              funding_cost_rate,
              product_type,
              source_version,
              rule_version
            from {RELATION_TYW_INTERBANK_DAILY_SNAPSHOT}
            where cast(report_date as date) between ? and ?
              and strftime(try_cast(report_date as date), '%Y-%m-%d') in ({placeholders})
            """
        return conn.execute(
            tyw_snap_sql,
            [start_date, end_date, *missing_dates],
        ).fetchdf()

    @staticmethod
    def _date_coverage_for_table_impl(
        conn: duckdb.DuckDBPyConnection,
        *,
        table: str,
        start_date: date,
        end_date: date,
        currency_basis: str | None = None,
    ) -> dict[str, Any]:
        if table not in _ADB_READ_RELATIONS:
            return {"dates_count": 0, "dates": [], "error": "table_not_found"}
        try:
            currency_clause = " AND currency_basis = ?" if currency_basis is not None else ""
            params: list[Any] = [start_date, end_date]
            if currency_basis is not None:
                params.append(currency_basis)
            rows = conn.execute(
                f"SELECT DISTINCT cast(report_date as varchar) FROM {table} "
                f"WHERE cast(report_date as date) BETWEEN ? AND ?{currency_clause} ORDER BY 1",
                params,
            ).fetchall()
            dates = [row[0] for row in rows if row[0]]
            return {"dates_count": len(dates), "dates": dates}
        except duckdb.Error:
            return {"dates_count": 0, "dates": [], "error": "table_not_found"}
