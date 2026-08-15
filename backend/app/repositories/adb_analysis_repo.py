from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
from backend.app.core_finance.fx_calendar import is_cfets_fx_non_business_day
from backend.app.core_finance.fx_rates import is_valid_fx_mid_rate
from backend.app.repositories.currency_codes import normalize_currency_code
from backend.app.repositories.duckdb_repo import DuckDBRepository, read_only_connection

RELATION_FACT_FORMAL_ZQTZ_BALANCE_DAILY = "fact_formal_zqtz_balance_daily"
RELATION_FACT_FORMAL_TYW_BALANCE_DAILY = "fact_formal_tyw_balance_daily"
RELATION_ZQTZ_BOND_DAILY_SNAPSHOT = "zqtz_bond_daily_snapshot"
RELATION_TYW_INTERBANK_DAILY_SNAPSHOT = "tyw_interbank_daily_snapshot"
RELATION_PRODUCT_CATEGORY_PNL_CANONICAL_FACT = "product_category_pnl_canonical_fact"

_ADB_READ_RELATIONS = frozenset(
    {
        RELATION_FACT_FORMAL_ZQTZ_BALANCE_DAILY,
        RELATION_FACT_FORMAL_TYW_BALANCE_DAILY,
        RELATION_ZQTZ_BOND_DAILY_SNAPSHOT,
        RELATION_TYW_INTERBANK_DAILY_SNAPSHOT,
        RELATION_PRODUCT_CATEGORY_PNL_CANONICAL_FACT,
    }
)


def _dict_from_row(description: list[tuple], row: tuple) -> dict[str, object]:
    return {str(column[0]): value for column, value in zip(description, row, strict=True)}


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

    def lookup_formal_fx_rate(self, *, report_date: str, base_currency: str) -> Decimal:
        """Resolve one governed CNY mid-rate for ADB snapshot fallback.

        Business-day observations must be direct. Carry-forward is accepted only on
        a confirmed CFETS non-business day and must point to an earlier trade date.
        """
        base = normalize_currency_code(base_currency)
        if base in {"", "CNY", "CNX", "RMB"}:
            return Decimal("1")

        with read_only_connection(self.path) as conn:
            row = conn.execute(
                """
                select mid_rate,
                       is_business_day,
                       is_carry_forward,
                       cast(observed_trade_date as varchar)
                from fx_daily_mid
                where trade_date = ?
                  and upper(base_currency) = upper(?)
                  and upper(quote_currency) = 'CNY'
                limit 1
                """,
                [report_date, base],
            ).fetchone()

        if row is None or row[0] is None:
            raise ValueError(
                f"Missing formal fx rate for base_currency={base} report_date={report_date}"
            )
        try:
            rate = Decimal(str(row[0]))
        except InvalidOperation as exc:
            raise ValueError(
                f"Invalid formal fx rate for base_currency={base} report_date={report_date}: "
                "mid_rate must be finite and greater than zero."
            ) from exc
        if not is_valid_fx_mid_rate(rate):
            raise ValueError(
                f"Invalid formal fx rate for base_currency={base} report_date={report_date}: "
                "mid_rate must be finite and greater than zero."
            )

        business_day = bool(row[1])
        carry_forward = bool(row[2])
        observed_trade_date = str(row[3]) if row[3] is not None else None
        if business_day:
            if carry_forward:
                raise ValueError(
                    f"Invalid formal fx metadata for base_currency={base} report_date={report_date}: "
                    "business-day row cannot be carry-forward."
                )
            return rate

        if not carry_forward or observed_trade_date is None:
            raise ValueError(
                f"Invalid formal fx carry-forward metadata for base_currency={base} "
                f"report_date={report_date}: non-business-day row must carry forward an "
                "observed prior trade date."
            )
        if date.fromisoformat(observed_trade_date) >= date.fromisoformat(report_date):
            raise ValueError(
                f"Invalid formal fx carry-forward metadata for base_currency={base} "
                f"report_date={report_date}: observed_trade_date={observed_trade_date} "
                "must be before report_date."
            )
        if not is_cfets_fx_non_business_day(
            report_date,
            base_currency=base,
            quote_currency="CNY",
        ):
            raise ValueError(
                f"Invalid formal fx carry-forward metadata for base_currency={base} "
                f"report_date={report_date}: carry-forward is only allowed for confirmed "
                "non-business-day rows."
            )
        return rate

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

    def fetch_accounting_basis_rows(
        self,
        report_date: str,
        currency: str,
    ) -> list[dict[str, object]]:
        """会计计量分桶（141/142/143/1440101/144020 前缀）单快照日行；表或库缺失时返回空。"""
        if not Path(self.path).exists():
            return []
        with read_only_connection(self.path) as conn:
            if not self.table_exists(conn, RELATION_PRODUCT_CATEGORY_PNL_CANONICAL_FACT):
                return []
            cursor = conn.execute(
                f"""
                select
                  account_code,
                  daily_avg_balance,
                  source_version,
                  rule_version
                from {RELATION_PRODUCT_CATEGORY_PNL_CANONICAL_FACT}
                where report_date = ?
                  and currency = ?
                  and (
                    account_code like '141%'
                    or account_code like '142%'
                    or account_code like '143%'
                    or account_code like '1440101%'
                    or account_code like '144020%'
                  )
                """,
                [report_date, currency],
            )
            description = list(cursor.description or [])
            return [_dict_from_row(description, row) for row in cursor.fetchall()]

    def fetch_accounting_basis_trend_rows(
        self,
        start_date: str,
        end_date: str,
        currency: str,
    ) -> list[dict[str, object]]:
        """会计计量分桶区间行（含 report_date 列）；表或库缺失时返回空。"""
        if not Path(self.path).exists():
            return []
        with read_only_connection(self.path) as conn:
            if not self.table_exists(conn, RELATION_PRODUCT_CATEGORY_PNL_CANONICAL_FACT):
                return []
            cursor = conn.execute(
                f"""
                select
                  report_date,
                  account_code,
                  daily_avg_balance,
                  source_version,
                  rule_version
                from {RELATION_PRODUCT_CATEGORY_PNL_CANONICAL_FACT}
                where report_date >= ?
                  and report_date <= ?
                  and currency = ?
                  and (
                    account_code like '141%'
                    or account_code like '142%'
                    or account_code like '143%'
                    or account_code like '1440101%'
                    or account_code like '144020%'
                  )
                order by report_date, account_code
                """,
                [start_date, end_date, currency],
            )
            description = list(cursor.description or [])
            return [_dict_from_row(description, row) for row in cursor.fetchall()]

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
              currency_code,
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
