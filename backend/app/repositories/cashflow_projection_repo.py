from __future__ import annotations

from dataclasses import dataclass

import duckdb


FACT_TYW_TABLE = "fact_formal_tyw_balance_daily"
FACT_ZQTZ_TABLE = "fact_formal_zqtz_balance_daily"


@dataclass(slots=True)
class CashflowProjectionRepository:
    path: str

    def fetch_formal_zqtz_rows(
        self,
        *,
        report_date: str,
        position_scope: str = "all",
        currency_basis: str = "CNY",
    ) -> list[dict[str, object]]:
        conn = _connect_read_only(self.path)
        if conn is None:
            return []
        try:
            if not _table_exists(conn, FACT_ZQTZ_TABLE):
                return []
            where_parts = ["report_date = ?", "currency_basis = ?"]
            params: list[object] = [report_date, currency_basis]
            if position_scope != "all":
                where_parts.append("position_scope = ?")
                params.append(position_scope)
            rows = conn.execute(
                f"""
                select
                  report_date,
                  instrument_code,
                  instrument_name,
                  portfolio_name,
                  cost_center,
                  account_category,
                  asset_class,
                  bond_type,
                  sub_type,
                  business_type_primary,
                  issuer_name,
                  industry_name,
                  rating,
                  invest_type_std,
                  accounting_basis,
                  position_scope,
                  currency_basis,
                  currency_code,
                  face_value_amount,
                  market_value_amount,
                  amortized_cost_amount,
                  accrued_interest_amount,
                  coupon_rate,
                  ytm_value,
                  maturity_date,
                  interest_mode,
                  is_issuance_like,
                  overdue_principal_days,
                  overdue_interest_days,
                  value_date,
                  customer_attribute,
                  source_version,
                  rule_version,
                  ingest_batch_id,
                  trace_id
                from {FACT_ZQTZ_TABLE}
                where {' and '.join(where_parts)}
                order by instrument_code, portfolio_name, cost_center
                """,
                params,
            ).fetchall()
            columns = [
                "report_date",
                "instrument_code",
                "instrument_name",
                "portfolio_name",
                "cost_center",
                "account_category",
                "asset_class",
                "bond_type",
                "sub_type",
                "business_type_primary",
                "issuer_name",
                "industry_name",
                "rating",
                "invest_type_std",
                "accounting_basis",
                "position_scope",
                "currency_basis",
                "currency_code",
                "face_value_amount",
                "market_value_amount",
                "amortized_cost_amount",
                "accrued_interest_amount",
                "coupon_rate",
                "ytm_value",
                "maturity_date",
                "interest_mode",
                "is_issuance_like",
                "overdue_principal_days",
                "overdue_interest_days",
                "value_date",
                "customer_attribute",
                "source_version",
                "rule_version",
                "ingest_batch_id",
                "trace_id",
            ]
            return [dict(zip(columns, row, strict=True)) for row in rows]
        finally:
            conn.close()

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
