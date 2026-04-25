from __future__ import annotations

from dataclasses import dataclass

import duckdb

from backend.app.repositories.balance_analysis_repo import BalanceAnalysisRepository


def _table_exists(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    row = conn.execute(
        """
        select 1
        from information_schema.tables
        where table_schema = current_schema()
          and table_name = ?
        limit 1
        """,
        [table_name],
    ).fetchone()
    return row is not None


@dataclass
class FormalZqtzBalanceMetricsRepository:
    """
    Read-only aggregates over governed formal balance facts (no snapshot / preview tables).

    Used for narrow metrics consumers outside the main balance-analysis workbook API surface.
    The legacy zqtz-only methods remain available. Combined formal overview metrics
    (`fetch_formal_overview`) delegate to :class:`BalanceAnalysisRepository` so executive
    surfaces share the same aggregation semantics as the balance-analysis API.
    """

    path: str

    def list_report_dates(self, *, currency_basis: str = "CNY") -> list[str]:
        try:
            conn = duckdb.connect(self.path, read_only=True)
            try:
                rows = conn.execute(
                    """
                    select distinct cast(report_date as varchar)
                    from fact_formal_zqtz_balance_daily
                    where position_scope = 'asset'
                      and currency_basis = ?
                    order by cast(report_date as varchar) desc
                    """,
                    [currency_basis],
                ).fetchall()
            finally:
                conn.close()
        except duckdb.Error as exc:
            raise RuntimeError("Formal balance-analysis storage is unavailable.") from exc
        return [str(row[0]) for row in rows]

    def list_formal_overview_report_dates(
        self,
        *,
        position_scope: str = "asset",
        currency_basis: str = "CNY",
    ) -> list[str]:
        try:
            conn = duckdb.connect(self.path, read_only=True)
            try:
                if not _table_exists(conn, "fact_formal_tyw_balance_daily"):
                    return self.list_report_dates(currency_basis=currency_basis)
                rows = conn.execute(
                    """
                    with dates as (
                      select distinct cast(report_date as varchar) as report_date
                      from fact_formal_zqtz_balance_daily
                      where position_scope = ?
                        and currency_basis = ?
                      union
                      select distinct cast(report_date as varchar) as report_date
                      from fact_formal_tyw_balance_daily
                      where position_scope = ?
                        and currency_basis = ?
                    )
                    select report_date
                    from dates
                    order by report_date desc
                    """,
                    [position_scope, currency_basis, position_scope, currency_basis],
                ).fetchall()
            finally:
                conn.close()
        except duckdb.Error as exc:
            raise RuntimeError("Formal balance-analysis storage is unavailable.") from exc
        return [str(row[0]) for row in rows]

    def fetch_zqtz_asset_market_value(
        self,
        *,
        report_date: str,
        currency_basis: str = "CNY",
    ) -> dict[str, object] | None:
        try:
            conn = duckdb.connect(self.path, read_only=True)
            try:
                row = conn.execute(
                    """
                    select cast(report_date as varchar), coalesce(sum(market_value_amount), 0) as total_market_value_amount
                    from fact_formal_zqtz_balance_daily
                    where position_scope = 'asset'
                      and currency_basis = ?
                      and cast(report_date as varchar) = ?
                    group by report_date
                    """,
                    [currency_basis, report_date],
                ).fetchone()
            finally:
                conn.close()
        except duckdb.Error as exc:
            raise RuntimeError("Formal balance-analysis storage is unavailable.") from exc
        if row is None:
            return None
        return {
            "report_date": str(row[0]),
            "total_market_value_amount": row[1],
        }

    def fetch_formal_overview(
        self,
        *,
        report_date: str,
        position_scope: str = "asset",
        currency_basis: str = "CNY",
    ) -> dict[str, object] | None:
        try:
            conn = duckdb.connect(self.path, read_only=True)
            try:
                if not _table_exists(conn, "fact_formal_tyw_balance_daily"):
                    return None
            finally:
                conn.close()
        except duckdb.Error as exc:
            raise RuntimeError("Formal balance-analysis storage is unavailable.") from exc
        overview = BalanceAnalysisRepository(self.path).fetch_formal_overview(
            report_date=report_date,
            position_scope=position_scope,
            currency_basis=currency_basis,
        )
        detail = overview.get("detail_row_count")
        try:
            if detail is not None and int(detail) == 0:
                return None
        except (TypeError, ValueError):
            pass
        return overview

    def fetch_latest_zqtz_asset_market_value(
        self,
        *,
        currency_basis: str = "CNY",
    ) -> dict[str, object] | None:
        try:
            conn = duckdb.connect(self.path, read_only=True)
            try:
                rows = conn.execute(
                    """
                    select report_date, coalesce(sum(market_value_amount), 0) as total_market_value_amount
                    from fact_formal_zqtz_balance_daily
                    where position_scope = 'asset'
                      and currency_basis = ?
                    group by report_date
                    order by report_date desc
                    limit 1
                    """,
                    [currency_basis],
                ).fetchall()
            finally:
                conn.close()
        except duckdb.Error as exc:
            raise RuntimeError("Formal balance-analysis storage is unavailable.") from exc
        if not rows:
            return None
        return {
            "report_date": str(rows[0][0]),
            "total_market_value_amount": rows[0][1],
        }
