from __future__ import annotations

from dataclasses import dataclass

import duckdb


FACT_TYW_TABLE = "fact_formal_tyw_balance_daily"


@dataclass(slots=True)
class CashflowProjectionRepository:
    path: str

    def fetch_formal_tyw_liability_rows(
        self,
        *,
        report_date: str,
        currency_basis: str = "CNY",
    ) -> list[dict[str, object]]:
        conn = _connect_read_only(self.path)
        if conn is None:
            return []
        try:
            if not _table_exists(conn, FACT_TYW_TABLE):
                return []
            rows = conn.execute(
                f"""
                select
                  report_date,
                  position_id,
                  product_type,
                  position_side,
                  counterparty_name,
                  currency_code,
                  principal_amount,
                  funding_cost_rate,
                  maturity_date,
                  source_version,
                  rule_version
                from {FACT_TYW_TABLE}
                where report_date = ?
                  and position_scope = 'liability'
                  and currency_basis = ?
                order by position_id
                """,
                [report_date, currency_basis],
            ).fetchall()
            columns = [
                "report_date",
                "position_id",
                "product_type",
                "position_side",
                "counterparty_name",
                "currency_code",
                "principal_amount",
                "funding_cost_rate",
                "maturity_date",
                "source_version",
                "rule_version",
            ]
            return [dict(zip(columns, row, strict=True)) for row in rows]
        finally:
            conn.close()


def _connect_read_only(path: str) -> duckdb.DuckDBPyConnection | None:
    try:
        return duckdb.connect(path, read_only=True)
    except duckdb.IOException:
        return None


def _table_exists(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
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
