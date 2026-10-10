from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Final, Literal

import duckdb
from backend.app.core_finance.fixed_income_version_set import FIXED_INCOME_VERSION_SET
from backend.app.core_finance.risk_tensor import PortfolioRiskTensor
from backend.app.repositories.duckdb_migrations import (
    apply_pending_migrations_on_connection,
    ensure_risk_tensor_legacy_columns,
)
from backend.app.repositories.duckdb_read_context import resolve_effective_read_path
from backend.app.repositories.duckdb_repo import read_only_connection
from backend.app.repositories.fact_load_gates import commit_report_date_purge
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from backend.app.repositories.task_write_guard import require_repository_task_write_scope

# 与 bond_analytics_materialize.CACHE_KEY 对齐；只读路径不得 import tasks。
BOND_ANALYTICS_CACHE_KEY = FIXED_INCOME_VERSION_SET.bond_analytics.cache_key

FACT_TABLE = "fact_formal_risk_tensor_daily"
TYW_LIABILITY_FACT_TABLE = "fact_formal_tyw_balance_daily"

_TYW_LIABILITY_AVAILABLE: Final = "available"
_TYW_LIABILITY_MISSING_TABLE: Final = "missing_table"
_TYW_LIABILITY_UNAVAILABLE: Final = "unavailable"


@dataclass(frozen=True)
class TywLiabilityLineageState:
    """Readability and lineage observed for one formal TYW liability snapshot.

    An empty, successfully-read snapshot is materially different from a missing
    table or an unavailable database: the former verifies a zero-liability
    input, while the latter cannot support a risk-tensor freshness decision.
    """

    availability: Literal["available", "missing_table", "unavailable"]
    row_count: int
    source_version: str = ""
    rule_version: str = ""


@dataclass(frozen=True)
class TywLiabilityLineageSnapshot:
    """One read of TYW liability lineage, reusable across report dates."""

    availability: Literal["available", "missing_table", "unavailable"]
    by_report_date: dict[str, TywLiabilityLineageState]

    def for_report_date(self, report_date: str) -> TywLiabilityLineageState:
        if self.availability != _TYW_LIABILITY_AVAILABLE:
            return TywLiabilityLineageState(
                availability=self.availability,
                row_count=0,
            )
        return self.by_report_date.get(
            report_date,
            TywLiabilityLineageState(
                availability=_TYW_LIABILITY_AVAILABLE,
                row_count=0,
            ),
        )


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

    def list_report_date_lineage_rows(self) -> list[dict[str, object]]:
        conn = _connect_read_only(self.path)
        if conn is None:
            return []
        try:
            if not _table_exists(conn, FACT_TABLE):
                return []
            table_columns = _table_columns(conn, FACT_TABLE)
            upstream_source_version = _column_or_default(
                table_columns,
                "upstream_source_version",
                "''",
            )
            upstream_rule_version = _column_or_default(
                table_columns,
                "upstream_rule_version",
                "''",
                coalesce=True,
            )
            upstream_cache_version = _column_or_default(
                table_columns,
                "upstream_cache_version",
                "''",
                coalesce=True,
            )
            cache_version = _column_or_default(
                table_columns,
                "cache_version",
                "''",
                coalesce=True,
            )
            stored_rule_version = _column_or_default(
                table_columns,
                "rule_version",
                "''",
                coalesce=True,
            )
            liability_source_version = _column_or_default(
                table_columns,
                "liability_source_version",
                "''",
                coalesce=True,
            )
            liability_rule_version = _column_or_default(
                table_columns,
                "liability_rule_version",
                "''",
                coalesce=True,
            )
            duration_scope_columns = {
                field_name: _column_or_default(
                    table_columns,
                    field_name,
                    "cast(null as integer)"
                    if field_name == "duration_excluded_count"
                    else "cast(null as decimal(24, 8))",
                )
                for field_name in (
                    "rate_risk_market_value",
                    "rate_risk_dv01",
                    "rate_risk_modified_duration",
                    "duration_excluded_market_value",
                    "duration_excluded_count",
                )
            }
            rows = conn.execute(
                f"""
                select cast(report_date as varchar) as report_date,
                       {upstream_source_version},
                       {upstream_rule_version},
                       {upstream_cache_version},
                       {liability_source_version},
                       {liability_rule_version},
                       {stored_rule_version},
                       {cache_version},
                       {duration_scope_columns['rate_risk_market_value']},
                       {duration_scope_columns['rate_risk_dv01']},
                       {duration_scope_columns['rate_risk_modified_duration']},
                       {duration_scope_columns['duration_excluded_market_value']},
                       {duration_scope_columns['duration_excluded_count']}
                from {FACT_TABLE}
                order by cast(report_date as varchar) desc
                """
            ).fetchall()
            columns = [
                "report_date",
                "upstream_source_version",
                "upstream_rule_version",
                "upstream_cache_version",
                "liability_source_version",
                "liability_rule_version",
                "rule_version",
                "cache_version",
                "rate_risk_market_value",
                "rate_risk_dv01",
                "rate_risk_modified_duration",
                "duration_excluded_market_value",
                "duration_excluded_count",
            ]
            return [dict(zip(columns, row, strict=True)) for row in rows]
        finally:
            conn.close()

    def replace_risk_tensor_row(
        self,
        *,
        report_date: str,
        tensor: PortfolioRiskTensor,
        source_version: str,
        upstream_source_version: str,
        upstream_rule_version: str,
        upstream_cache_version: str,
        liability_source_version: str,
        liability_rule_version: str,
        rule_version: str,
        cache_version: str,
        trace_id: str,
    ) -> None:
        require_repository_task_write_scope("replace_risk_tensor_row")
        conn = duckdb.connect(self.path, read_only=False)
        transaction_started = False
        try:
            conn.execute("begin transaction")
            transaction_started = True
            ensure_risk_tensor_table(conn)
            conn.execute("commit")
            transaction_started = False

            commit_report_date_purge(
                conn, tables=(FACT_TABLE,), report_date=report_date
            )

            conn.execute("begin transaction")
            transaction_started = True
            conn.execute(
                f"""
                insert into {FACT_TABLE} (
                    report_date,
                    portfolio_dv01,
                    regulatory_dv01,
                    krd_1y,
                    krd_3y,
                    krd_5y,
                    krd_7y,
                    krd_10y,
                    krd_30y,
                    cs01,
                    portfolio_convexity,
                    portfolio_modified_duration,
                    rate_risk_market_value,
                    rate_risk_dv01,
                    rate_risk_modified_duration,
                    duration_excluded_market_value,
                    duration_excluded_count,
                    missing_maturity_market_value,
                    missing_maturity_count,
                    fund_no_maturity_market_value,
                    fund_no_maturity_count,
                    unknown_maturity_market_value,
                    unknown_maturity_count,
                    matured_outstanding_market_value,
                    matured_outstanding_count,
                    nonpositive_duration_market_value,
                    nonpositive_duration_count,
                    missing_liability_maturity_principal_amount,
                    missing_liability_maturity_count,
                    floating_rate_proxy_market_value,
                    floating_rate_proxy_count,
                    payment_frequency_fallback_market_value,
                    payment_frequency_fallback_count,
                    bullet_value_date_fallback_market_value,
                    bullet_value_date_fallback_count,
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
                    upstream_rule_version,
                    upstream_cache_version,
                    liability_source_version,
                    liability_rule_version,
                    rule_version,
                    cache_version,
                    trace_id
                ) values (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                [
                    report_date,
                    tensor.portfolio_dv01,
                    tensor.regulatory_dv01,
                    tensor.krd_1y,
                    tensor.krd_3y,
                    tensor.krd_5y,
                    tensor.krd_7y,
                    tensor.krd_10y,
                    tensor.krd_30y,
                    tensor.cs01,
                    tensor.portfolio_convexity,
                    tensor.portfolio_modified_duration,
                    tensor.rate_risk_market_value,
                    tensor.rate_risk_dv01,
                    tensor.rate_risk_modified_duration,
                    tensor.duration_excluded_market_value,
                    tensor.duration_excluded_count,
                    tensor.missing_maturity_market_value,
                    tensor.missing_maturity_count,
                    tensor.fund_no_maturity_market_value,
                    tensor.fund_no_maturity_count,
                    tensor.unknown_maturity_market_value,
                    tensor.unknown_maturity_count,
                    tensor.matured_outstanding_market_value,
                    tensor.matured_outstanding_count,
                    tensor.nonpositive_duration_market_value,
                    tensor.nonpositive_duration_count,
                    tensor.missing_liability_maturity_principal_amount,
                    tensor.missing_liability_maturity_count,
                    tensor.floating_rate_proxy_market_value,
                    tensor.floating_rate_proxy_count,
                    tensor.payment_frequency_fallback_market_value,
                    tensor.payment_frequency_fallback_count,
                    tensor.bullet_value_date_fallback_market_value,
                    tensor.bullet_value_date_fallback_count,
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
                    upstream_rule_version,
                    upstream_cache_version,
                    liability_source_version,
                    liability_rule_version,
                    rule_version,
                    cache_version,
                    trace_id,
                ],
            )
            conn.execute("commit")
            transaction_started = False
        except Exception:
            if transaction_started:
                try:
                    conn.execute("rollback")
                except Exception:  # noqa: BLE001, S110 - rollback failure must preserve the original write exception raised below.
                    pass
            raise
        finally:
            conn.close()

    def fetch_risk_tensor_history(
        self,
        report_date: str,
        periods: int,
        *,
        rule_version: str | None = None,
    ) -> list[dict[str, object]]:
        conn = _connect_read_only(self.path)
        if conn is None:
            return []
        try:
            if not _table_exists(conn, FACT_TABLE):
                return []
            table_columns = _table_columns(conn, FACT_TABLE)
            if rule_version is not None and "rule_version" not in table_columns:
                return []
            regulatory_dv01 = _column_or_default(
                table_columns,
                "regulatory_dv01",
                "cast(null as decimal(24, 8))",
            )
            upstream_source_version = _column_or_default(
                table_columns,
                "upstream_source_version",
                "''",
                coalesce=True,
            )
            upstream_rule_version = _column_or_default(
                table_columns,
                "upstream_rule_version",
                "''",
                coalesce=True,
            )
            upstream_cache_version = _column_or_default(
                table_columns,
                "upstream_cache_version",
                "''",
                coalesce=True,
            )
            liability_source_version = _column_or_default(
                table_columns,
                "liability_source_version",
                "''",
                coalesce=True,
            )
            liability_rule_version = _column_or_default(
                table_columns,
                "liability_rule_version",
                "''",
                coalesce=True,
            )
            cache_version = _column_or_default(
                table_columns,
                "cache_version",
                "''",
                coalesce=True,
            )
            rate_risk_market_value = _column_or_default(
                table_columns,
                "rate_risk_market_value",
                "cast(null as decimal(24, 8))",
            )
            rate_risk_dv01 = _column_or_default(
                table_columns,
                "rate_risk_dv01",
                "cast(null as decimal(24, 8))",
            )
            rate_risk_modified_duration = _column_or_default(
                table_columns,
                "rate_risk_modified_duration",
                "cast(null as decimal(24, 8))",
            )
            duration_excluded_market_value = _column_or_default(
                table_columns,
                "duration_excluded_market_value",
                "cast(null as decimal(24, 8))",
            )
            duration_excluded_count = _column_or_default(
                table_columns,
                "duration_excluded_count",
                "cast(null as integer)",
            )
            where_clauses = ["cast(report_date as varchar) <= ?"]
            parameters: list[object] = [report_date]
            if rule_version is not None:
                where_clauses.append("rule_version = ?")
                parameters.append(rule_version)
            parameters.append(periods)
            rows = conn.execute(
                f"""
                select cast(report_date as varchar) as report_date,
                       portfolio_dv01,
                       {regulatory_dv01},
                       portfolio_modified_duration,
                       portfolio_convexity,
                       cs01,
                       issuer_concentration_hhi,
                       issuer_top5_weight,
                       liquidity_gap_30d,
                       {upstream_source_version},
                       {upstream_rule_version},
                       {upstream_cache_version},
                       {liability_source_version},
                       {liability_rule_version},
                       rule_version,
                       {cache_version},
                       {rate_risk_market_value},
                       {rate_risk_dv01},
                       {rate_risk_modified_duration},
                       {duration_excluded_market_value},
                       {duration_excluded_count}
                from {FACT_TABLE}
                where {' and '.join(where_clauses)}
                order by cast(report_date as varchar) desc
                limit ?
                """,
                parameters,
            ).fetchall()
            columns = [
                "report_date",
                "portfolio_dv01",
                "regulatory_dv01",
                "portfolio_modified_duration",
                "portfolio_convexity",
                "cs01",
                "issuer_concentration_hhi",
                "issuer_top5_weight",
                "liquidity_gap_30d",
                "upstream_source_version",
                "upstream_rule_version",
                "upstream_cache_version",
                "liability_source_version",
                "liability_rule_version",
                "rule_version",
                "cache_version",
                "rate_risk_market_value",
                "rate_risk_dv01",
                "rate_risk_modified_duration",
                "duration_excluded_market_value",
                "duration_excluded_count",
            ]
            return [dict(zip(columns, row, strict=True)) for row in rows]
        finally:
            conn.close()

    def fetch_risk_tensor_row(self, report_date: str) -> dict[str, object] | None:
        conn = _connect_read_only(self.path)
        if conn is None:
            return None
        try:
            if not _table_exists(conn, FACT_TABLE):
                return None
            table_columns = _table_columns(conn, FACT_TABLE)
            asset_cashflow_30d = _column_or_default(
                table_columns,
                "asset_cashflow_30d",
                "cast(0 as decimal(24, 8))",
                coalesce=True,
            )
            asset_cashflow_90d = _column_or_default(
                table_columns,
                "asset_cashflow_90d",
                "cast(0 as decimal(24, 8))",
                coalesce=True,
            )
            liability_cashflow_30d = _column_or_default(
                table_columns,
                "liability_cashflow_30d",
                "cast(0 as decimal(24, 8))",
                coalesce=True,
            )
            liability_cashflow_90d = _column_or_default(
                table_columns,
                "liability_cashflow_90d",
                "cast(0 as decimal(24, 8))",
                coalesce=True,
            )
            liability_source_version = _column_or_default(
                table_columns,
                "liability_source_version",
                "''",
                coalesce=True,
            )
            liability_rule_version = _column_or_default(
                table_columns,
                "liability_rule_version",
                "''",
                coalesce=True,
            )
            upstream_rule_version = _column_or_default(
                table_columns,
                "upstream_rule_version",
                "''",
                coalesce=True,
            )
            upstream_cache_version = _column_or_default(
                table_columns,
                "upstream_cache_version",
                "''",
                coalesce=True,
            )
            regulatory_dv01 = _column_or_default(
                table_columns,
                "regulatory_dv01",
                "cast(null as decimal(24, 8))",
            )
            duration_scope_columns = {
                field_name: _column_or_default(
                    table_columns,
                    field_name,
                    "cast(null as integer)"
                    if field_name == "duration_excluded_count"
                    else "cast(null as decimal(24, 8))",
                )
                for field_name in (
                    "rate_risk_market_value",
                    "rate_risk_dv01",
                    "rate_risk_modified_duration",
                    "duration_excluded_market_value",
                    "duration_excluded_count",
                )
            }
            projection_quality_columns = {
                field_name: _column_or_default(
                    table_columns,
                    field_name,
                    "cast(null as integer)"
                    if field_name.endswith("_count")
                    else "cast(null as decimal(24, 8))",
                )
                for field_name in (
                    "missing_maturity_market_value",
                    "missing_maturity_count",
                    "fund_no_maturity_market_value",
                    "fund_no_maturity_count",
                    "unknown_maturity_market_value",
                    "unknown_maturity_count",
                    "matured_outstanding_market_value",
                    "matured_outstanding_count",
                    "nonpositive_duration_market_value",
                    "nonpositive_duration_count",
                    "missing_liability_maturity_principal_amount",
                    "missing_liability_maturity_count",
                    "floating_rate_proxy_market_value",
                    "floating_rate_proxy_count",
                    "payment_frequency_fallback_market_value",
                    "payment_frequency_fallback_count",
                    "bullet_value_date_fallback_market_value",
                    "bullet_value_date_fallback_count",
                )
            }
            row = conn.execute(
                f"""
                select report_date,
                       portfolio_dv01,
                       {regulatory_dv01},
                       krd_1y,
                       krd_3y,
                       krd_5y,
                       krd_7y,
                       krd_10y,
                       krd_30y,
                       cs01,
                       portfolio_convexity,
                       portfolio_modified_duration,
                       {duration_scope_columns['rate_risk_market_value']},
                       {duration_scope_columns['rate_risk_dv01']},
                       {duration_scope_columns['rate_risk_modified_duration']},
                       {duration_scope_columns['duration_excluded_market_value']},
                       {duration_scope_columns['duration_excluded_count']},
                       {projection_quality_columns['missing_maturity_market_value']},
                       {projection_quality_columns['missing_maturity_count']},
                       {projection_quality_columns['fund_no_maturity_market_value']},
                       {projection_quality_columns['fund_no_maturity_count']},
                       {projection_quality_columns['unknown_maturity_market_value']},
                       {projection_quality_columns['unknown_maturity_count']},
                       {projection_quality_columns['matured_outstanding_market_value']},
                       {projection_quality_columns['matured_outstanding_count']},
                       {projection_quality_columns['nonpositive_duration_market_value']},
                       {projection_quality_columns['nonpositive_duration_count']},
                       {projection_quality_columns['missing_liability_maturity_principal_amount']},
                       {projection_quality_columns['missing_liability_maturity_count']},
                       {projection_quality_columns['floating_rate_proxy_market_value']},
                       {projection_quality_columns['floating_rate_proxy_count']},
                       {projection_quality_columns['payment_frequency_fallback_market_value']},
                       {projection_quality_columns['payment_frequency_fallback_count']},
                       {projection_quality_columns['bullet_value_date_fallback_market_value']},
                       {projection_quality_columns['bullet_value_date_fallback_count']},
                       issuer_concentration_hhi,
                       issuer_top5_weight,
                       {asset_cashflow_30d},
                       {asset_cashflow_90d},
                       {liability_cashflow_30d},
                       {liability_cashflow_90d},
                       liquidity_gap_30d,
                       liquidity_gap_90d,
                       liquidity_gap_30d_ratio,
                       total_market_value,
                       bond_count,
                       quality_flag,
                       warnings_json,
                       source_version,
                       upstream_source_version,
                       {upstream_rule_version},
                       {upstream_cache_version},
                       {liability_source_version},
                       {liability_rule_version},
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
                "regulatory_dv01",
                "krd_1y",
                "krd_3y",
                "krd_5y",
                "krd_7y",
                "krd_10y",
                "krd_30y",
                "cs01",
                "portfolio_convexity",
                "portfolio_modified_duration",
                "rate_risk_market_value",
                "rate_risk_dv01",
                "rate_risk_modified_duration",
                "duration_excluded_market_value",
                "duration_excluded_count",
                "missing_maturity_market_value",
                "missing_maturity_count",
                "fund_no_maturity_market_value",
                "fund_no_maturity_count",
                "unknown_maturity_market_value",
                "unknown_maturity_count",
                "matured_outstanding_market_value",
                "matured_outstanding_count",
                "nonpositive_duration_market_value",
                "nonpositive_duration_count",
                "missing_liability_maturity_principal_amount",
                "missing_liability_maturity_count",
                "floating_rate_proxy_market_value",
                "floating_rate_proxy_count",
                "payment_frequency_fallback_market_value",
                "payment_frequency_fallback_count",
                "bullet_value_date_fallback_market_value",
                "bullet_value_date_fallback_count",
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
                "upstream_rule_version",
                "upstream_cache_version",
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


    def fetch_campisi_decision_risk_tensor_aggregate(
        self,
        report_date: str,
        *,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> tuple[bool, list[dict[str, Any]]]:
        if conn is not None:
            return self._fetch_campisi_decision_risk_tensor_aggregate_impl(conn, report_date)
        try:
            with read_only_connection(self.path) as scoped:
                return self._fetch_campisi_decision_risk_tensor_aggregate_impl(scoped, report_date)
        except (OSError, duckdb.Error):
            return False, []

    def _fetch_campisi_decision_risk_tensor_aggregate_impl(
        self,
        conn: duckdb.DuckDBPyConnection,
        report_date: str,
    ) -> tuple[bool, list[dict[str, Any]]]:
        if not _table_exists(conn, FACT_TABLE):
            return False, []
        rows = _campisi_decision_duckdb_rows(
            conn,
            """
            select
                sum(coalesce(portfolio_dv01, 0)) as portfolio_dv01,
                sum(coalesce(cs01, 0)) as cs01,
                sum(coalesce(total_market_value, 0)) as total_market_value,
                sum(coalesce(bond_count, 0)) as bond_count,
                max(quality_flag) as quality_flag
            from fact_formal_risk_tensor_daily
            where cast(report_date as date) = cast(? as date)
            """,
            [report_date],
        )
        return True, rows




def _campisi_decision_duckdb_rows(
    conn: duckdb.DuckDBPyConnection,
    sql: str,
    params: list[Any] | tuple[Any, ...] = (),
) -> list[dict[str, Any]]:
    cursor = conn.execute(sql, params)
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]


def ensure_risk_tensor_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Baseline DDL is versioned in `duckdb_migrations` (also run at API/worker startup)."""
    apply_pending_migrations_on_connection(conn)
    ensure_risk_tensor_legacy_columns(conn)


def load_latest_bond_analytics_lineage(
    *,
    governance_dir: str,
    report_date: str,
) -> dict[str, str] | None:
    latest = None
    for row in GovernanceRepository(base_dir=governance_dir).read_by_cache_keys(
        CACHE_BUILD_RUN_STREAM,
        [BOND_ANALYTICS_CACHE_KEY],
    ):
        if (
            str(row.get("cache_key")) == BOND_ANALYTICS_CACHE_KEY
            and str(row.get("job_name")) == "bond_analytics_materialize"
            and str(row.get("report_date")) == report_date
        ):
            latest = row
    if latest is None or str(latest.get("status")) != "completed":
        return None
    return {
        "source_version": str(latest.get("source_version") or "").strip(),
        "rule_version": str(latest.get("rule_version") or "").strip(),
        "cache_version": str(latest.get("cache_version") or "").strip(),
        "vendor_version": str(latest.get("vendor_version") or "vv_none").strip() or "vv_none",
    }


def load_latest_bond_analytics_lineage_by_report_date(
    *,
    governance_dir: str,
) -> dict[str, dict[str, str]]:
    latest_by_report_date: dict[str, dict[str, object]] = {}
    for row in GovernanceRepository(base_dir=governance_dir).read_by_cache_keys(
        CACHE_BUILD_RUN_STREAM,
        [BOND_ANALYTICS_CACHE_KEY],
    ):
        if (
            str(row.get("cache_key")) != BOND_ANALYTICS_CACHE_KEY
            or str(row.get("job_name")) != "bond_analytics_materialize"
        ):
            continue
        report_date = str(row.get("report_date") or "").strip()
        if not report_date:
            continue
        latest_by_report_date[report_date] = row

    lineage_by_report_date: dict[str, dict[str, str]] = {}
    for report_date, latest in latest_by_report_date.items():
        if str(latest.get("status")) != "completed":
            continue
        lineage_by_report_date[report_date] = {
            "source_version": str(latest.get("source_version") or "").strip(),
            "rule_version": str(latest.get("rule_version") or "").strip(),
            "cache_version": str(latest.get("cache_version") or "").strip(),
            "vendor_version": str(latest.get("vendor_version") or "vv_none").strip() or "vv_none",
        }
    return lineage_by_report_date


def load_current_tyw_liability_lineage_state(
    *,
    duckdb_path: str,
    report_date: str,
) -> TywLiabilityLineageState:
    """Read one TYW liability snapshot without collapsing unavailable into zero."""

    conn = _connect_read_only(duckdb_path)
    if conn is None:
        return TywLiabilityLineageState(
            availability=_TYW_LIABILITY_UNAVAILABLE,
            row_count=0,
        )
    try:
        if not _table_exists(conn, TYW_LIABILITY_FACT_TABLE):
            return TywLiabilityLineageState(
                availability=_TYW_LIABILITY_MISSING_TABLE,
                row_count=0,
            )
        row = conn.execute(
            f"""
            select count(*) as row_count,
                   list(distinct coalesce(trim(source_version), '')) as source_versions,
                   list(distinct coalesce(trim(rule_version), '')) as rule_versions
            from {TYW_LIABILITY_FACT_TABLE}
            where report_date = ?
              and position_scope = 'liability'
              and currency_basis = 'CNY'
            """,
            [report_date],
        ).fetchone()
    except duckdb.Error:
        return TywLiabilityLineageState(
            availability=_TYW_LIABILITY_UNAVAILABLE,
            row_count=0,
        )
    finally:
        conn.close()

    # An aggregate without GROUP BY returns one row even for an empty snapshot.
    assert row is not None
    row_count, source_values, rule_values = row
    # Keep Python's Unicode whitespace normalization after SQL deduplication.
    source_versions = sorted({str(value or "").strip() for value in source_values or []})
    rule_versions = sorted({str(value or "").strip() for value in rule_values or []})
    return TywLiabilityLineageState(
        availability=_TYW_LIABILITY_AVAILABLE,
        row_count=int(row_count),
        source_version="__".join(value for value in source_versions if value),
        rule_version="__".join(value for value in rule_versions if value),
    )


def load_current_tyw_liability_lineage_snapshot_by_report_date(
    *,
    duckdb_path: str,
) -> TywLiabilityLineageSnapshot:
    """Read TYW liability lineage once for date-list and history freshness checks."""

    conn = _connect_read_only(duckdb_path)
    if conn is None:
        return TywLiabilityLineageSnapshot(
            availability=_TYW_LIABILITY_UNAVAILABLE,
            by_report_date={},
        )
    try:
        if not _table_exists(conn, TYW_LIABILITY_FACT_TABLE):
            return TywLiabilityLineageSnapshot(
                availability=_TYW_LIABILITY_MISSING_TABLE,
                by_report_date={},
            )
        rows = conn.execute(
            f"""
            with liability_rows as (
              select cast(report_date as varchar) as report_date,
                     coalesce(trim(source_version), '') as source_version,
                     coalesce(trim(rule_version), '') as rule_version
              from {TYW_LIABILITY_FACT_TABLE}
              where position_scope = 'liability'
                and currency_basis = 'CNY'
            ),
            report_dates as (
              select report_date, count(*) as row_count
              from liability_rows
              where report_date <> ''
              group by report_date
            ),
            source_versions as (
              select report_date,
                     string_agg(source_version, '__' order by source_version) as source_version
              from (
                select distinct report_date, source_version
                from liability_rows
                where report_date <> '' and source_version <> ''
              )
              group by report_date
            ),
            rule_versions as (
              select report_date,
                     string_agg(rule_version, '__' order by rule_version) as rule_version
              from (
                select distinct report_date, rule_version
                from liability_rows
                where report_date <> '' and rule_version <> ''
              )
              group by report_date
            )
            select report_dates.report_date,
                   report_dates.row_count,
                   coalesce(source_versions.source_version, '') as source_version,
                   coalesce(rule_versions.rule_version, '') as rule_version
            from report_dates
            left join source_versions using (report_date)
            left join rule_versions using (report_date)
            order by report_dates.report_date
            """
        ).fetchall()
    except duckdb.Error:
        return TywLiabilityLineageSnapshot(
            availability=_TYW_LIABILITY_UNAVAILABLE,
            by_report_date={},
        )
    finally:
        conn.close()

    return TywLiabilityLineageSnapshot(
        availability=_TYW_LIABILITY_AVAILABLE,
        by_report_date={
            str(report_date): TywLiabilityLineageState(
                availability=_TYW_LIABILITY_AVAILABLE,
                row_count=int(row_count),
                source_version=str(source_version or ""),
                rule_version=str(rule_version or ""),
            )
            for report_date, row_count, source_version, rule_version in rows
        },
    )


def load_current_tyw_liability_source_version(
    *,
    duckdb_path: str,
    report_date: str,
) -> str:
    return load_current_tyw_liability_lineage_state(
        duckdb_path=duckdb_path,
        report_date=report_date,
    ).source_version


def load_current_tyw_liability_lineage_by_report_date(
    *,
    duckdb_path: str,
) -> dict[str, dict[str, str]]:
    snapshot = load_current_tyw_liability_lineage_snapshot_by_report_date(
        duckdb_path=duckdb_path,
    )
    if snapshot.availability != _TYW_LIABILITY_AVAILABLE:
        return {}
    return {
        report_date: {
            "source_version": state.source_version,
            "rule_version": state.rule_version,
        }
        for report_date, state in snapshot.by_report_date.items()
    }


def load_current_tyw_liability_rule_version(
    *,
    duckdb_path: str,
    report_date: str,
) -> str:
    return load_current_tyw_liability_lineage_state(
        duckdb_path=duckdb_path,
        report_date=report_date,
    ).rule_version


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


def _table_columns(conn: duckdb.DuckDBPyConnection, table_name: str) -> set[str]:
    rows = conn.execute(
        """
        select column_name
        from information_schema.columns
        where table_name = ?
        """,
        [table_name],
    ).fetchall()
    return {str(row[0]) for row in rows}


def _column_or_default(
    columns: set[str],
    column_name: str,
    default_sql: str,
    *,
    coalesce: bool = False,
) -> str:
    if column_name not in columns:
        return f"{default_sql} as {column_name}"
    if coalesce:
        return f"coalesce({column_name}, {default_sql}) as {column_name}"
    return column_name


def _connect_read_only(path: str) -> duckdb.DuckDBPyConnection | None:
    path = resolve_effective_read_path(path)
    try:
        return duckdb.connect(path, read_only=True)
    except duckdb.IOException:
        return None
