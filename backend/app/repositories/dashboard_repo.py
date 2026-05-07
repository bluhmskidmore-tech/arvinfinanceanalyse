"""Read-only aggregates for unified dashboard KPIs (bond facts + formal TYW balance)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import duckdb

from backend.app.repositories.bond_analytics_repo import FACT_TABLE
from backend.app.repositories.duckdb_repo import DuckDBRepository

TYW_FACT = "fact_formal_tyw_balance_daily"

_BOND_YTM_NORM = (
    "(case when ytm is null then null "
    "when ytm > 1 and ytm <= 100 then ytm / 100.0 else ytm end)"
)
_TYW_RATE_NORM = (
    "(case when funding_cost_rate is null then null "
    "when funding_cost_rate > 1 then funding_cost_rate / 100.0 "
    "else funding_cost_rate end)"
)
_ASSET_PRED = (
    "(instr(lower(coalesce(position_side, '')), 'asset') > 0 "
    "OR instr(coalesce(position_side, ''), '资产') > 0)"
)


def _table_exists_conn(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
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


@dataclass
class DashboardRepository(DuckDBRepository):
    guard_path_exists: bool = True

    def list_merged_report_dates(self) -> list[str]:
        if self.guard_path_exists and not Path(self.path).exists():
            return []
        conn = duckdb.connect(self.path, read_only=True)
        try:
            parts: list[str] = []
            if _table_exists_conn(conn, FACT_TABLE):
                parts.append(f"select cast(report_date as varchar) as d from {FACT_TABLE}")
            if _table_exists_conn(conn, TYW_FACT):
                parts.append(
                    f"select cast(report_date as varchar) as d from {TYW_FACT} "
                    "where currency_basis = 'CNY'"
                )
            if not parts:
                return []
            inner = " union ".join(parts)
            rows = conn.execute(f"select distinct d from ({inner}) t order by d desc").fetchall()
            return [str(r[0]) for r in rows if r[0] is not None]
        finally:
            conn.close()

    def fetch_bond_core_metrics(
        self,
        report_date: str,
    ) -> tuple[Decimal, Decimal | None, list[tuple[str, Decimal, Decimal | None]]]:
        """Portfolio total MV, weighted YTM (fraction), top-3 bond_type rows."""
        if self.guard_path_exists and not Path(self.path).exists():
            return Decimal("0"), None, []
        conn = duckdb.connect(self.path, read_only=True)
        try:
            if not _table_exists_conn(conn, FACT_TABLE):
                return Decimal("0"), None, []
            row = conn.execute(
                f"""
                select
                  coalesce(sum(market_value), 0),
                  sum(({_BOND_YTM_NORM}) * market_value)
                    / nullif(sum(market_value), 0)
                from {FACT_TABLE}
                where cast(report_date as varchar) = ?
                """,
                [report_date],
            ).fetchone()
            tot = Decimal(str(row[0] or 0))
            wy = None if row[1] is None else Decimal(str(row[1]))

            rows3 = conn.execute(
                f"""
                select
                  cast(bond_type as varchar) as bt,
                  coalesce(sum(market_value), 0) as smv,
                  sum(({_BOND_YTM_NORM}) * market_value) / nullif(sum(market_value), 0) as wytm
                from {FACT_TABLE}
                where cast(report_date as varchar) = ?
                  and bond_type is not null
                  and trim(cast(bond_type as varchar)) <> ''
                group by bond_type
                order by smv desc
                limit 3
                """,
                [report_date],
            ).fetchall()
            top3 = [
                (
                    str(r[0]) if r[0] else "",
                    Decimal(str(r[1] or 0)),
                    None if r[2] is None else Decimal(str(r[2])),
                )
                for r in rows3
            ]
            return tot, wy, top3
        finally:
            conn.close()

    def fetch_tyw_core_metrics(
        self,
        report_date: str,
        *,
        asset_side: bool,
    ) -> tuple[Decimal, Decimal | None, list[tuple[str, Decimal, Decimal | None]]]:
        """Principal total + funding-cost weighted avg + top-3 counterparty rows (CNY formal TYW)."""
        if self.guard_path_exists and not Path(self.path).exists():
            return Decimal("0"), None, []
        conn = duckdb.connect(self.path, read_only=True)
        try:
            if not _table_exists_conn(conn, TYW_FACT):
                return Decimal("0"), None, []
            side_sql = _ASSET_PRED if asset_side else f"NOT ({_ASSET_PRED})"
            row = conn.execute(
                f"""
                select
                  coalesce(sum(coalesce(principal_amount, 0)), 0),
                  sum(({_TYW_RATE_NORM}) * coalesce(principal_amount, 0))
                    / nullif(sum(coalesce(principal_amount, 0)), 0)
                from {TYW_FACT}
                where cast(report_date as varchar) = ?
                  and currency_basis = 'CNY'
                  and ({side_sql})
                """,
                [report_date],
            ).fetchone()
            tot = Decimal(str(row[0] or 0))
            wr = None if row[1] is None else Decimal(str(row[1]))

            rows3 = conn.execute(
                f"""
                select
                  cast(counterparty_name as varchar) as cp,
                  coalesce(sum(coalesce(principal_amount, 0)), 0) as spr,
                  sum(({_TYW_RATE_NORM}) * coalesce(principal_amount, 0))
                    / nullif(sum(coalesce(principal_amount, 0)), 0) as wr
                from {TYW_FACT}
                where cast(report_date as varchar) = ?
                  and currency_basis = 'CNY'
                  and ({side_sql})
                  and counterparty_name is not null
                  and trim(cast(counterparty_name as varchar)) <> ''
                group by counterparty_name
                order by spr desc
                limit 3
                """,
                [report_date],
            ).fetchall()
            top3 = [
                (
                    str(r[0]) if r[0] else "",
                    Decimal(str(r[1] or 0)),
                    None if r[2] is None else Decimal(str(r[2])),
                )
                for r in rows3
            ]
            return tot, wr, top3
        finally:
            conn.close()
