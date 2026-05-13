"""Read-only aggregates for unified dashboard KPIs (bond facts + formal TYW balance)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import duckdb

from backend.app.repositories.bond_analytics_repo import FACT_TABLE
from backend.app.repositories.duckdb_repo import DuckDBRepository

ZQTZ_FACT = "fact_formal_zqtz_balance_daily"
TYW_FACT = "fact_formal_tyw_balance_daily"

_BOND_YTM_NORM = (
    "(case when ytm is null then null "
    "when ytm > 1 and ytm <= 100 then ytm / 100.0 else ytm end)"
)
_ZQTZ_YTM_NORM = (
    "(case when ytm_value is null then null "
    "when ytm_value > 1 and ytm_value <= 100 then ytm_value / 100.0 else ytm_value end)"
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


CoreMetricResult = tuple[Decimal, Decimal | None, list[tuple[str, Decimal, Decimal | None]], bool]


def _normalize_dates(report_dates: list[str]) -> list[str]:
    dates: list[str] = []
    seen: set[str] = set()
    for raw in report_dates:
        d = str(raw or "").strip()
        if not d or d in seen:
            continue
        seen.add(d)
        dates.append(d)
    return dates


def _empty_core_metric_result() -> CoreMetricResult:
    return Decimal("0"), None, [], False


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
            if _table_exists_conn(conn, ZQTZ_FACT):
                parts.append(
                    f"select cast(report_date as varchar) as d from {ZQTZ_FACT} "
                    "where currency_basis = 'CNY' and position_scope = 'asset'"
                )
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
    ) -> CoreMetricResult:
        """CNY formal bond balance total MV, weighted YTM, top-3 bond_type rows."""
        if self.guard_path_exists and not Path(self.path).exists():
            return Decimal("0"), None, [], False
        conn = duckdb.connect(self.path, read_only=True)
        try:
            if _table_exists_conn(conn, ZQTZ_FACT):
                balance_rows = conn.execute(
                    f"""
                    select count(*)
                    from {ZQTZ_FACT}
                    where currency_basis = 'CNY'
                      and position_scope = 'asset'
                    """
                ).fetchone()
                if balance_rows and balance_rows[0]:
                    row = conn.execute(
                        f"""
                        select
                          count(*),
                          coalesce(sum(market_value_amount), 0),
                          sum(({_ZQTZ_YTM_NORM}) * market_value_amount)
                            / nullif(sum(market_value_amount), 0)
                        from {ZQTZ_FACT}
                        where cast(report_date as varchar) = ?
                          and currency_basis = 'CNY'
                          and position_scope = 'asset'
                        """,
                        [report_date],
                    ).fetchone()
                    has_rows = bool(row and row[0])
                    tot = Decimal(str(row[1] or 0))
                    wy = None if row[2] is None else Decimal(str(row[2]))

                    rows3 = conn.execute(
                        f"""
                        select
                          cast(bond_type as varchar) as bt,
                          coalesce(sum(market_value_amount), 0) as smv,
                          sum(({_ZQTZ_YTM_NORM}) * market_value_amount)
                            / nullif(sum(market_value_amount), 0) as wytm
                        from {ZQTZ_FACT}
                        where cast(report_date as varchar) = ?
                          and currency_basis = 'CNY'
                          and position_scope = 'asset'
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
                    if has_rows:
                        return tot, wy, top3, True

            if not _table_exists_conn(conn, FACT_TABLE):
                return Decimal("0"), None, [], False
            row = conn.execute(
                f"""
                select
                  count(*),
                  coalesce(sum(market_value), 0),
                  sum(({_BOND_YTM_NORM}) * market_value)
                    / nullif(sum(market_value), 0)
                from {FACT_TABLE}
                where cast(report_date as varchar) = ?
                """,
                [report_date],
            ).fetchone()
            has_rows = bool(row and row[0])
            tot = Decimal(str(row[1] or 0))
            wy = None if row[2] is None else Decimal(str(row[2]))

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
            return tot, wy, top3, has_rows
        finally:
            conn.close()

    def fetch_bond_core_metrics_for_dates(self, report_dates: list[str]) -> dict[str, CoreMetricResult]:
        """Batch variant of fetch_bond_core_metrics, preserving the same source preference."""
        dates = _normalize_dates(report_dates)
        if not dates:
            return {}
        results = {d: _empty_core_metric_result() for d in dates}
        if self.guard_path_exists and not Path(self.path).exists():
            return results

        conn = duckdb.connect(self.path, read_only=True)
        try:
            placeholders = ", ".join(["?"] * len(dates))
            if _table_exists_conn(conn, ZQTZ_FACT):
                balance_rows = conn.execute(
                    f"""
                    select count(*)
                    from {ZQTZ_FACT}
                    where currency_basis = 'CNY'
                      and position_scope = 'asset'
                    """
                ).fetchone()
                if balance_rows and balance_rows[0]:
                    rows = conn.execute(
                        f"""
                        select
                          cast(report_date as varchar) as d,
                          count(*) as row_count,
                          coalesce(sum(market_value_amount), 0) as smv,
                          sum(({_ZQTZ_YTM_NORM}) * market_value_amount)
                            / nullif(sum(market_value_amount), 0) as wytm
                        from {ZQTZ_FACT}
                        where cast(report_date as varchar) in ({placeholders})
                          and currency_basis = 'CNY'
                          and position_scope = 'asset'
                        group by cast(report_date as varchar)
                        """,
                        dates,
                    ).fetchall()
                    for row in rows:
                        d = str(row[0])
                        if d in results:
                            results[d] = (
                                Decimal(str(row[2] or 0)),
                                None if row[3] is None else Decimal(str(row[3])),
                                [],
                                bool(row[1]),
                            )

                    rows3 = conn.execute(
                        f"""
                        with grouped as (
                          select
                            cast(report_date as varchar) as d,
                            cast(bond_type as varchar) as bt,
                            coalesce(sum(market_value_amount), 0) as smv,
                            sum(({_ZQTZ_YTM_NORM}) * market_value_amount)
                              / nullif(sum(market_value_amount), 0) as wytm
                          from {ZQTZ_FACT}
                          where cast(report_date as varchar) in ({placeholders})
                            and currency_basis = 'CNY'
                            and position_scope = 'asset'
                            and bond_type is not null
                            and trim(cast(bond_type as varchar)) <> ''
                          group by cast(report_date as varchar), cast(bond_type as varchar)
                        ),
                        ranked as (
                          select *, row_number() over (partition by d order by smv desc) as rn
                          from grouped
                        )
                        select d, bt, smv, wytm
                        from ranked
                        where rn <= 3
                        order by d desc, smv desc
                        """,
                        dates,
                    ).fetchall()
                    tops: dict[str, list[tuple[str, Decimal, Decimal | None]]] = {}
                    for row in rows3:
                        tops.setdefault(str(row[0]), []).append(
                            (
                                str(row[1]) if row[1] else "",
                                Decimal(str(row[2] or 0)),
                                None if row[3] is None else Decimal(str(row[3])),
                            )
                        )
                    for d, top3 in tops.items():
                        if d in results:
                            tot, wy, _, has_rows = results[d]
                            results[d] = (tot, wy, top3, has_rows)
                    fallback_dates = [d for d in dates if not results[d][3]]
                else:
                    fallback_dates = dates
            else:
                fallback_dates = dates

            if not _table_exists_conn(conn, FACT_TABLE):
                return results

            if not fallback_dates:
                return results

            placeholders = ", ".join(["?"] * len(fallback_dates))
            rows = conn.execute(
                f"""
                select
                  cast(report_date as varchar) as d,
                  count(*) as row_count,
                  coalesce(sum(market_value), 0) as smv,
                  sum(({_BOND_YTM_NORM}) * market_value) / nullif(sum(market_value), 0) as wytm
                from {FACT_TABLE}
                where cast(report_date as varchar) in ({placeholders})
                group by cast(report_date as varchar)
                """,
                fallback_dates,
            ).fetchall()
            for row in rows:
                d = str(row[0])
                if d in results:
                    results[d] = (
                        Decimal(str(row[2] or 0)),
                        None if row[3] is None else Decimal(str(row[3])),
                        [],
                        bool(row[1]),
                    )

            rows3 = conn.execute(
                f"""
                with grouped as (
                  select
                    cast(report_date as varchar) as d,
                    cast(bond_type as varchar) as bt,
                    coalesce(sum(market_value), 0) as smv,
                    sum(({_BOND_YTM_NORM}) * market_value) / nullif(sum(market_value), 0) as wytm
                  from {FACT_TABLE}
                  where cast(report_date as varchar) in ({placeholders})
                    and bond_type is not null
                    and trim(cast(bond_type as varchar)) <> ''
                  group by cast(report_date as varchar), cast(bond_type as varchar)
                ),
                ranked as (
                  select *, row_number() over (partition by d order by smv desc) as rn
                  from grouped
                )
                select d, bt, smv, wytm
                from ranked
                where rn <= 3
                order by d desc, smv desc
                """,
                fallback_dates,
            ).fetchall()
            tops: dict[str, list[tuple[str, Decimal, Decimal | None]]] = {}
            for row in rows3:
                tops.setdefault(str(row[0]), []).append(
                    (
                        str(row[1]) if row[1] else "",
                        Decimal(str(row[2] or 0)),
                        None if row[3] is None else Decimal(str(row[3])),
                    )
                )
            for d, top3 in tops.items():
                if d in results:
                    tot, wy, _, has_rows = results[d]
                    results[d] = (tot, wy, top3, has_rows)
            return results
        finally:
            conn.close()

    def fetch_tyw_core_metrics(
        self,
        report_date: str,
        *,
        asset_side: bool,
    ) -> CoreMetricResult:
        """Principal total + funding-cost weighted avg + top-3 counterparty rows (CNY formal TYW)."""
        if self.guard_path_exists and not Path(self.path).exists():
            return Decimal("0"), None, [], False
        conn = duckdb.connect(self.path, read_only=True)
        try:
            if not _table_exists_conn(conn, TYW_FACT):
                return Decimal("0"), None, [], False
            side_sql = _ASSET_PRED if asset_side else f"NOT ({_ASSET_PRED})"
            row = conn.execute(
                f"""
                select
                  count(*),
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
            has_rows = bool(row and row[0])
            tot = Decimal(str(row[1] or 0))
            wr = None if row[2] is None else Decimal(str(row[2]))

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
            return tot, wr, top3, has_rows
        finally:
            conn.close()

    def fetch_tyw_core_metrics_for_dates(
        self,
        report_dates: list[str],
        *,
        asset_side: bool,
    ) -> dict[str, CoreMetricResult]:
        dates = _normalize_dates(report_dates)
        if not dates:
            return {}
        results = {d: _empty_core_metric_result() for d in dates}
        if self.guard_path_exists and not Path(self.path).exists():
            return results

        conn = duckdb.connect(self.path, read_only=True)
        try:
            if not _table_exists_conn(conn, TYW_FACT):
                return results
            side_sql = _ASSET_PRED if asset_side else f"NOT ({_ASSET_PRED})"
            placeholders = ", ".join(["?"] * len(dates))
            rows = conn.execute(
                f"""
                select
                  cast(report_date as varchar) as d,
                  count(*) as row_count,
                  coalesce(sum(coalesce(principal_amount, 0)), 0) as spr,
                  sum(({_TYW_RATE_NORM}) * coalesce(principal_amount, 0))
                    / nullif(sum(coalesce(principal_amount, 0)), 0) as wr
                from {TYW_FACT}
                where cast(report_date as varchar) in ({placeholders})
                  and currency_basis = 'CNY'
                  and ({side_sql})
                group by cast(report_date as varchar)
                """,
                dates,
            ).fetchall()
            for row in rows:
                d = str(row[0])
                if d in results:
                    results[d] = (
                        Decimal(str(row[2] or 0)),
                        None if row[3] is None else Decimal(str(row[3])),
                        [],
                        bool(row[1]),
                    )

            rows3 = conn.execute(
                f"""
                with grouped as (
                  select
                    cast(report_date as varchar) as d,
                    cast(counterparty_name as varchar) as cp,
                    coalesce(sum(coalesce(principal_amount, 0)), 0) as spr,
                    sum(({_TYW_RATE_NORM}) * coalesce(principal_amount, 0))
                      / nullif(sum(coalesce(principal_amount, 0)), 0) as wr
                  from {TYW_FACT}
                  where cast(report_date as varchar) in ({placeholders})
                    and currency_basis = 'CNY'
                    and ({side_sql})
                    and counterparty_name is not null
                    and trim(cast(counterparty_name as varchar)) <> ''
                  group by cast(report_date as varchar), cast(counterparty_name as varchar)
                ),
                ranked as (
                  select *, row_number() over (partition by d order by spr desc) as rn
                  from grouped
                )
                select d, cp, spr, wr
                from ranked
                where rn <= 3
                order by d desc, spr desc
                """,
                dates,
            ).fetchall()
            tops: dict[str, list[tuple[str, Decimal, Decimal | None]]] = {}
            for row in rows3:
                tops.setdefault(str(row[0]), []).append(
                    (
                        str(row[1]) if row[1] else "",
                        Decimal(str(row[2] or 0)),
                        None if row[3] is None else Decimal(str(row[3])),
                    )
                )
            for d, top3 in tops.items():
                if d in results:
                    tot, wr, _, has_rows = results[d]
                    results[d] = (tot, wr, top3, has_rows)
            return results
        finally:
            conn.close()
