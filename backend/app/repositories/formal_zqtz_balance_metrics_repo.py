from __future__ import annotations

from dataclasses import dataclass

import duckdb


@dataclass
class FormalZqtzBalanceMetricsRepository:
    """DuckDB reads of formal zqtz balance aggregates outside the balance_analysis service boundary."""

    path: str

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
