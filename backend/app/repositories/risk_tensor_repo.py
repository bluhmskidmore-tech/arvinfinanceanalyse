from __future__ import annotations

import json
from dataclasses import dataclass

import duckdb

from backend.app.core_finance.risk_tensor import PortfolioRiskTensor
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from backend.app.tasks.bond_analytics_materialize import CACHE_KEY as BOND_ANALYTICS_CACHE_KEY

FACT_TABLE = "fact_formal_risk_tensor_daily"

_GROSS_CASHFLOW_COLUMNS = (
    "asset_cashflow_30d",
    "asset_cashflow_90d",
    "liability_cashflow_30d",
    "liability_cashflow_90d",
)
_LINEAGE_COLUMNS = ("liability_source_version", "liability_rule_version")


def _ensure_risk_tensor_gross_columns(path: str) -> None:
    try:
        conn = duckdb.connect(path, read_only=False)
    except duckdb.IOException:
        return
    try:
        if not _table_exists(conn, FACT_TABLE):
            return
        for column in _GROSS_CASHFLOW_COLUMNS:
            conn.execute(
                f"alter table {FACT_TABLE} add column if not exists {column} decimal(24, 8)"
            )
        for column in _LINEAGE_COLUMNS:
            conn.execute(
                f"alter table {FACT_TABLE} add column if not exists {column} varchar"
            )
    finally:
        conn.close()


@dataclass
class RiskTensorRepository:
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

    def replace_risk_tensor_row(
        self,
        *,
        report_date: str,
        tensor: PortfolioRiskTensor,
        source_version: str,
        upstream_source_version: str,
        liability_source_version: str,
        liability_rule_version: str,
        rule_version: str,
        cache_version: str,
        trace_id: str,
    ) -> None:
        conn = duckdb.connect(self.path, read_only=False)
        try:
            conn.execute("begin transaction")
            ensure_risk_tensor_table(conn)
            conn.execute(
                f"delete from {FACT_TABLE} where report_date = ?",
                [report_date],
            )
            conn.execute(
                f"""
                insert into {FACT_TABLE} (
                    report_date,
                    portfolio_dv01,
                    krd_1y,
                    krd_3y,
                    krd_5y,
                    krd_7y,
                    krd_10y,
                    krd_30y,
                    cs01,
                    portfolio_convexity,
                    portfolio_modified_duration,
                    issuer_concentration_hhi,
                    issuer_top5_weight,
                    asset_cashflow_30d,
                    asset_cashflow_90d,
                    liability_cashflow_30d,
                    liability_cashflow_90d,
                    liquidity_gap_30d,
                    liquidity_gap_90d,
                    liquidity_gap_30d_ratio,
                    total_market_value,
                    bond_count,
                    quality_flag,
                    warnings_json,
                    source_version,
                    upstream_source_version,
                    liability_source_version,
                    liability_rule_version,
                    rule_version,
                    cache_version,
                    trace_id
                ) values (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                [
                    report_date,
                    tensor.portfolio_dv01,
                    tensor.krd_1y,
                    tensor.krd_3y,
                    tensor.krd_5y,
                    tensor.krd_7y,
                    tensor.krd_10y,
                    tensor.krd_30y,
                    tensor.cs01,
                    tensor.portfolio_convexity,
                    tensor.portfolio_modified_duration,
                    tensor.issuer_concentration_hhi,
                    tensor.issuer_top5_weight,
                    tensor.asset_cashflow_30d,
                    tensor.asset_cashflow_90d,
                    tensor.liability_cashflow_30d,
                    tensor.liability_cashflow_90d,
                    tensor.liquidity_gap_30d,
                    tensor.liquidity_gap_90d,
                    tensor.liquidity_gap_30d_ratio,
                    tensor.total_market_value,
                    tensor.bond_count,
                    tensor.quality_flag,
                    json.dumps(tensor.warnings, ensure_ascii=False),
                    source_version,
                    upstream_source_version,
                    liability_source_version,
                    liability_rule_version,
                    rule_version,
                    cache_version,
                    trace_id,
                ],
            )
            conn.execute("commit")
        except Exception:
            conn.execute("rollback")
            raise
        finally:
            conn.close()

    def fetch_risk_tensor_row(self, report_date: str) -> dict[str, object] | None:
        _ensure_risk_tensor_gross_columns(self.path)
        conn = _connect_read_only(self.path)
        if conn is None:
            return None
        try:
            if not _table_exists(conn, FACT_TABLE):
                return None
            row = conn.execute(
                f"""
                select report_date,
                       portfolio_dv01,
                       krd_1y,
                       krd_3y,
                       krd_5y,
                       krd_7y,
                       krd_10y,
                       krd_30y,
                       cs01,
                       portfolio_convexity,
                       portfolio_modified_duration,
                       issuer_concentration_hhi,
                       issuer_top5_weight,
                       coalesce(asset_cashflow_30d, 0),
                       coalesce(asset_cashflow_90d, 0),
                       coalesce(liability_cashflow_30d, 0),
                       coalesce(liability_cashflow_90d, 0),
                       liquidity_gap_30d,
                       liquidity_gap_90d,
                       liquidity_gap_30d_ratio,
                       total_market_value,
                       bond_count,
                       quality_flag,
                       warnings_json,
                       source_version,
                       upstream_source_version,
                       coalesce(liability_source_version, ''),
                       coalesce(liability_rule_version, ''),
                       rule_version,
                       cache_version,
                       trace_id
                from {FACT_TABLE}
                where report_date = ?
                limit 1
                """,
                [report_date],
            ).fetchone()
            if row is None:
                return None
            columns = [
                "report_date",
                "portfolio_dv01",
                "krd_1y",
                "krd_3y",
                "krd_5y",
                "krd_7y",
                "krd_10y",
                "krd_30y",
                "cs01",
                "portfolio_convexity",
                "portfolio_modified_duration",
                "issuer_concentration_hhi",
                "issuer_top5_weight",
                "asset_cashflow_30d",
                "asset_cashflow_90d",
                "liability_cashflow_30d",
                "liability_cashflow_90d",
                "liquidity_gap_30d",
                "liquidity_gap_90d",
                "liquidity_gap_30d_ratio",
                "total_market_value",
                "bond_count",
                "quality_flag",
                "warnings_json",
                "source_version",
                "upstream_source_version",
                "liability_source_version",
                "liability_rule_version",
                "rule_version",
                "cache_version",
                "trace_id",
            ]
            payload = dict(zip(columns, row, strict=True))
            payload["warnings"] = json.loads(str(payload.pop("warnings_json") or "[]"))
            return payload
        finally:
            conn.close()


def ensure_risk_tensor_table(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        f"""
        create table if not exists {FACT_TABLE} (
            report_date                   varchar,
            portfolio_dv01                decimal(24, 8),
            krd_1y                        decimal(24, 8),
            krd_3y                        decimal(24, 8),
            krd_5y                        decimal(24, 8),
            krd_7y                        decimal(24, 8),
            krd_10y                       decimal(24, 8),
            krd_30y                       decimal(24, 8),
            cs01                          decimal(24, 8),
            portfolio_convexity           decimal(24, 8),
            portfolio_modified_duration   decimal(24, 8),
            issuer_concentration_hhi      decimal(24, 8),
            issuer_top5_weight            decimal(24, 8),
            asset_cashflow_30d            decimal(24, 8),
            asset_cashflow_90d            decimal(24, 8),
            liability_cashflow_30d        decimal(24, 8),
            liability_cashflow_90d        decimal(24, 8),
            liquidity_gap_30d             decimal(24, 8),
            liquidity_gap_90d             decimal(24, 8),
            liquidity_gap_30d_ratio       decimal(24, 8),
            total_market_value            decimal(24, 8),
            bond_count                    integer,
            quality_flag                  varchar,
            warnings_json                 varchar,
            source_version                varchar,
            upstream_source_version       varchar,
            liability_source_version      varchar,
            liability_rule_version        varchar,
            rule_version                  varchar,
            cache_version                 varchar,
            trace_id                      varchar
        )
        """
    )
    for column in _GROSS_CASHFLOW_COLUMNS:
        conn.execute(
            f"alter table {FACT_TABLE} add column if not exists {column} decimal(24, 8)"
        )
    for column in _LINEAGE_COLUMNS:
        conn.execute(
            f"alter table {FACT_TABLE} add column if not exists {column} varchar"
        )


def load_latest_bond_analytics_lineage(
    *,
    governance_dir: str,
    report_date: str,
) -> dict[str, str] | None:
    rows = [
        row
        for row in GovernanceRepository(base_dir=governance_dir).read_all(CACHE_BUILD_RUN_STREAM)
        if str(row.get("cache_key")) == BOND_ANALYTICS_CACHE_KEY
        and str(row.get("job_name")) == "bond_analytics_materialize"
        and str(row.get("status")) == "completed"
        and str(row.get("report_date")) == report_date
    ]
    if not rows:
        return None
    latest = rows[-1]
    return {
        "source_version": str(latest.get("source_version") or "").strip(),
        "rule_version": str(latest.get("rule_version") or "").strip(),
        "cache_version": str(latest.get("cache_version") or "").strip(),
        "vendor_version": str(latest.get("vendor_version") or "vv_none").strip() or "vv_none",
    }


def load_current_tyw_liability_source_version(
    *,
    duckdb_path: str,
    report_date: str,
) -> str:
    conn = _connect_read_only(duckdb_path)
    if conn is None:
        return ""
    try:
        if not _table_exists(conn, "fact_formal_tyw_balance_daily"):
            return ""
        rows = conn.execute(
            """
            select distinct source_version
            from fact_formal_tyw_balance_daily
            where report_date = ?
              and position_scope = 'liability'
              and currency_basis = 'CNY'
              and coalesce(trim(source_version), '') <> ''
            order by source_version
            """,
            [report_date],
        ).fetchall()
        return "__".join(str(row[0]).strip() for row in rows if str(row[0]).strip())
    finally:
        conn.close()


def load_current_tyw_liability_rule_version(
    *,
    duckdb_path: str,
    report_date: str,
) -> str:
    conn = _connect_read_only(duckdb_path)
    if conn is None:
        return ""
    try:
        if not _table_exists(conn, "fact_formal_tyw_balance_daily"):
            return ""
        rows = conn.execute(
            """
            select distinct rule_version
            from fact_formal_tyw_balance_daily
            where report_date = ?
              and position_scope = 'liability'
              and currency_basis = 'CNY'
              and coalesce(trim(rule_version), '') <> ''
            order by rule_version
            """,
            [report_date],
        ).fetchall()
        return "__".join(str(row[0]).strip() for row in rows if str(row[0]).strip())
    finally:
        conn.close()


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
