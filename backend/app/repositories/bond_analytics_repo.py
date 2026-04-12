from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import duckdb

from backend.app.core_finance.bond_analytics.read_models import (
    build_krd_distribution,
    summarize_accounting_audit,
    summarize_credit,
    summarize_portfolio_risk,
)
from backend.app.core_finance.bond_analytics.engine import BondAnalyticsRow


FACT_TABLE = "fact_formal_bond_analytics_daily"
SNAPSHOT_TABLE = "zqtz_bond_daily_snapshot"


@dataclass
class BondAnalyticsRepository:
    path: str

    def list_report_dates(self) -> list[str]:
        conn = _connect_read_only(self.path)
        if conn is None:
            return []
        try:
            if not _table_exists(conn, FACT_TABLE):
                return []
            rows = conn.execute(
                f"""
                select distinct cast(report_date as varchar)
                from {FACT_TABLE}
                order by cast(report_date as varchar) desc
                """
            ).fetchall()
            return [str(row[0]) for row in rows]
        finally:
            conn.close()

    def load_snapshot_rows(self, report_date: str) -> list[dict[str, object]]:
        conn = _connect_read_only(self.path)
        if conn is None:
            return []
        try:
            if not _table_exists(conn, SNAPSHOT_TABLE):
                return []
            rows = conn.execute(
                f"""
                select report_date, instrument_code, instrument_name, portfolio_name, cost_center,
                       account_category, asset_class, bond_type, issuer_name, industry_name, rating,
                       currency_code, face_value_native, market_value_native, amortized_cost_native,
                       accrued_interest_native, coupon_rate, ytm_value, maturity_date, next_call_date,
                       overdue_days, is_issuance_like, interest_mode, source_version, rule_version,
                       ingest_batch_id, trace_id
                from {SNAPSHOT_TABLE}
                where report_date = ?
                order by instrument_code, portfolio_name, cost_center, currency_code
                """,
                [report_date],
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
                "issuer_name",
                "industry_name",
                "rating",
                "currency_code",
                "face_value_native",
                "market_value_native",
                "amortized_cost_native",
                "accrued_interest_native",
                "coupon_rate",
                "ytm_value",
                "maturity_date",
                "next_call_date",
                "overdue_days",
                "is_issuance_like",
                "interest_mode",
                "source_version",
                "rule_version",
                "ingest_batch_id",
                "trace_id",
            ]
            return [dict(zip(columns, row, strict=True)) for row in rows]
        finally:
            conn.close()

    def replace_bond_analytics_rows(
        self,
        *,
        report_date: str,
        rows: list[BondAnalyticsRow],
    ) -> None:
        conn = duckdb.connect(self.path, read_only=False)
        try:
            conn.execute("begin transaction")
            ensure_bond_analytics_tables(conn)
            conn.execute(
                f"delete from {FACT_TABLE} where report_date = ?",
                [report_date],
            )
            if rows:
                conn.executemany(
                    f"""
                    insert into {FACT_TABLE} values (
                      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    [
                        (
                            row.report_date.isoformat(),
                            row.instrument_code,
                            row.instrument_name,
                            row.portfolio_name,
                            row.cost_center,
                            row.asset_class_raw,
                            row.asset_class_std,
                            row.bond_type,
                            row.issuer_name,
                            row.industry_name,
                            row.rating,
                            row.accounting_class,
                            row.accounting_rule_id,
                            row.currency_code,
                            row.face_value,
                            row.market_value,
                            row.amortized_cost,
                            row.accrued_interest,
                            row.coupon_rate,
                            row.ytm,
                            row.maturity_date.isoformat() if row.maturity_date else None,
                            row.years_to_maturity,
                            row.tenor_bucket,
                            row.macaulay_duration,
                            row.modified_duration,
                            row.convexity,
                            row.dv01,
                            row.is_credit,
                            row.spread_dv01,
                            row.source_version,
                            row.rule_version,
                            row.ingest_batch_id,
                            row.trace_id,
                        )
                        for row in rows
                    ],
                )
            conn.execute("commit")
        except Exception:
            conn.execute("rollback")
            raise
        finally:
            conn.close()

    def fetch_bond_analytics_rows(
        self,
        *,
        report_date: str,
        asset_class: str = "all",
        accounting_class: str = "all",
    ) -> list[dict[str, object]]:
        conn = _connect_read_only(self.path)
        if conn is None:
            return []
        try:
            if not _table_exists(conn, FACT_TABLE):
                return []
            where_parts = ["report_date = ?"]
            params: list[object] = [report_date]
            if asset_class != "all":
                where_parts.append("asset_class_std = ?")
                params.append(asset_class)
            if accounting_class != "all":
                where_parts.append("accounting_class = ?")
                params.append(accounting_class)
            rows = conn.execute(
                f"""
                select report_date, instrument_code, instrument_name, portfolio_name, cost_center,
                       asset_class_raw, asset_class_std, bond_type, issuer_name, industry_name, rating,
                       accounting_class, accounting_rule_id, currency_code, face_value, market_value,
                       amortized_cost, accrued_interest, coupon_rate, ytm, maturity_date,
                       years_to_maturity, tenor_bucket, macaulay_duration, modified_duration,
                       convexity, dv01, is_credit, spread_dv01, source_version, rule_version,
                       ingest_batch_id, trace_id
                from {FACT_TABLE}
                where {' and '.join(where_parts)}
                order by instrument_code
                """,
                params,
            ).fetchall()
            columns = [
                "report_date",
                "instrument_code",
                "instrument_name",
                "portfolio_name",
                "cost_center",
                "asset_class_raw",
                "asset_class_std",
                "bond_type",
                "issuer_name",
                "industry_name",
                "rating",
                "accounting_class",
                "accounting_rule_id",
                "currency_code",
                "face_value",
                "market_value",
                "amortized_cost",
                "accrued_interest",
                "coupon_rate",
                "ytm",
                "maturity_date",
                "years_to_maturity",
                "tenor_bucket",
                "macaulay_duration",
                "modified_duration",
                "convexity",
                "dv01",
                "is_credit",
                "spread_dv01",
                "source_version",
                "rule_version",
                "ingest_batch_id",
                "trace_id",
            ]
            return [dict(zip(columns, row, strict=True)) for row in rows]
        finally:
            conn.close()

    def fetch_portfolio_risk_summary(
        self,
        *,
        report_date: str,
    ) -> dict[str, object]:
        rows = self.fetch_bond_analytics_rows(report_date=report_date)
        return summarize_portfolio_risk(rows)

    def fetch_krd_distribution(
        self,
        *,
        report_date: str,
    ) -> list[dict[str, object]]:
        rows = self.fetch_bond_analytics_rows(report_date=report_date)
        return build_krd_distribution(rows)

    def fetch_credit_summary(
        self,
        *,
        report_date: str,
    ) -> dict[str, object]:
        all_rows = self.fetch_bond_analytics_rows(report_date=report_date)
        credit_rows = self.fetch_bond_analytics_rows(report_date=report_date, asset_class="credit")
        return summarize_credit(credit_rows, total_rows=all_rows)

    def fetch_accounting_audit(
        self,
        *,
        report_date: str,
    ) -> list[dict[str, object]]:
        rows = self.fetch_bond_analytics_rows(report_date=report_date)
        return summarize_accounting_audit(rows)["rows"]


def ensure_bond_analytics_tables(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        f"""
        create table if not exists {FACT_TABLE} (
            report_date         varchar,
            instrument_code     varchar,
            instrument_name     varchar,
            portfolio_name      varchar,
            cost_center         varchar,
            asset_class_raw     varchar,
            asset_class_std     varchar,
            bond_type           varchar,
            issuer_name         varchar,
            industry_name       varchar,
            rating              varchar,
            accounting_class    varchar,
            accounting_rule_id  varchar,
            currency_code       varchar,
            face_value          decimal(24, 8),
            market_value        decimal(24, 8),
            amortized_cost      decimal(24, 8),
            accrued_interest    decimal(24, 8),
            coupon_rate         decimal(18, 8),
            ytm                 decimal(18, 8),
            maturity_date       date,
            years_to_maturity   decimal(18, 8),
            tenor_bucket        varchar,
            macaulay_duration   decimal(18, 8),
            modified_duration   decimal(18, 8),
            convexity           decimal(18, 8),
            dv01                decimal(24, 8),
            is_credit           boolean,
            spread_dv01         decimal(24, 8),
            source_version      varchar,
            rule_version        varchar,
            ingest_batch_id     varchar,
            trace_id            varchar
        )
        """
    )


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


def _connect_read_only(path: str) -> duckdb.DuckDBPyConnection | None:
    try:
        return duckdb.connect(path, read_only=True)
    except duckdb.IOException:
        return None


def _decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _empty_risk_summary() -> dict[str, object]:
    return {
        "bond_count": 0,
        "total_market_value": Decimal("0"),
        "portfolio_duration": Decimal("0"),
        "portfolio_modified_duration": Decimal("0"),
        "portfolio_convexity": Decimal("0"),
        "portfolio_dv01": Decimal("0"),
    }


def _empty_credit_summary() -> dict[str, object]:
    return {
        "total_market_value": Decimal("0"),
        "credit_bond_count": 0,
        "credit_market_value": Decimal("0"),
        "weighted_avg_spread_duration": Decimal("0"),
        "weighted_avg_ytm": Decimal("0"),
        "spread_dv01": Decimal("0"),
        "oci_credit_exposure": Decimal("0"),
        "oci_spread_dv01": Decimal("0"),
        "tpl_spread_dv01": Decimal("0"),
    }
