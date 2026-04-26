from __future__ import annotations

from collections import defaultdict
import json
from dataclasses import dataclass

import duckdb

from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection
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

    def list_report_date_lineage_rows(self) -> list[dict[str, object]]:
        _ensure_risk_tensor_gross_columns(self.path)
        conn = _connect_read_only(self.path)
        if conn is None:
            return []
        try:
            if not _table_exists(conn, FACT_TABLE):
                return []
            rows = conn.execute(
                f"""
                select cast(report_date as varchar) as report_date,
                       upstream_source_version,
                       coalesce(liability_source_version, '') as liability_source_version,
                       coalesce(liability_rule_version, '') as liability_rule_version
                from {FACT_TABLE}
                order by cast(report_date as varchar) desc
                """
            ).fetchall()
            columns = [
                "report_date",
                "upstream_source_version",
                "liability_source_version",
                "liability_rule_version",
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
    """Baseline DDL is versioned in `duckdb_migrations` (also run at API/worker startup)."""
    apply_pending_migrations_on_connection(conn)


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


def load_latest_bond_analytics_lineage_by_report_date(
    *,
    governance_dir: str,
) -> dict[str, dict[str, str]]:
    lineage_by_report_date: dict[str, dict[str, str]] = {}
    for row in GovernanceRepository(base_dir=governance_dir).read_all(CACHE_BUILD_RUN_STREAM):
        if (
            str(row.get("cache_key")) != BOND_ANALYTICS_CACHE_KEY
            or str(row.get("job_name")) != "bond_analytics_materialize"
            or str(row.get("status")) != "completed"
        ):
            continue
        report_date = str(row.get("report_date") or "").strip()
        if not report_date:
            continue
        lineage_by_report_date[report_date] = {
            "source_version": str(row.get("source_version") or "").strip(),
            "rule_version": str(row.get("rule_version") or "").strip(),
            "cache_version": str(row.get("cache_version") or "").strip(),
            "vendor_version": str(row.get("vendor_version") or "vv_none").strip() or "vv_none",
        }
    return lineage_by_report_date


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


def load_current_tyw_liability_lineage_by_report_date(
    *,
    duckdb_path: str,
) -> dict[str, dict[str, str]]:
    conn = _connect_read_only(duckdb_path)
    if conn is None:
        return {}
    try:
        if not _table_exists(conn, "fact_formal_tyw_balance_daily"):
            return {}
        rows = conn.execute(
            """
            select cast(report_date as varchar) as report_date,
                   source_version,
                   rule_version
            from fact_formal_tyw_balance_daily
            where position_scope = 'liability'
              and currency_basis = 'CNY'
              and (
                coalesce(trim(source_version), '') <> ''
                or coalesce(trim(rule_version), '') <> ''
              )
            order by report_date, source_version, rule_version
            """
        ).fetchall()
        source_versions_by_date: defaultdict[str, set[str]] = defaultdict(set)
        rule_versions_by_date: defaultdict[str, set[str]] = defaultdict(set)
        for report_date, source_version, rule_version in rows:
            report_date_text = str(report_date or "").strip()
            if not report_date_text:
                continue
            source_version_text = str(source_version or "").strip()
            rule_version_text = str(rule_version or "").strip()
            if source_version_text:
                source_versions_by_date[report_date_text].add(source_version_text)
            if rule_version_text:
                rule_versions_by_date[report_date_text].add(rule_version_text)

        report_dates = set(source_versions_by_date) | set(rule_versions_by_date)
        return {
            report_date: {
                "source_version": "__".join(sorted(source_versions_by_date[report_date])),
                "rule_version": "__".join(sorted(rule_versions_by_date[report_date])),
            }
            for report_date in report_dates
        }
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
