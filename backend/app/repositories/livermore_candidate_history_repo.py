from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import duckdb
from backend.app.core_finance.field_normalization import tradable_status_sql_condition
from backend.app.core_finance.matched_baseline import MATCHED_BASELINE_TABLE
from backend.app.repositories.duckdb_repo import DuckDBRepository

RELATION_LIVERMORE_CANDIDATE_HISTORY = "livermore_candidate_history"
RELATION_LIVERMORE_CANDIDATE_EXECUTION_HISTORY = "livermore_candidate_execution_history"
RELATION_CHOICE_STOCK_DAILY_OBSERVATION = "choice_stock_daily_observation"
RELATION_STOCK_ADJUSTMENT_FACTOR = "stock_adjustment_factor"
RELATION_FACT_CHOICE_MACRO_DAILY = "fact_choice_macro_daily"
RELATION_CHOICE_MARKET_SNAPSHOT = "choice_market_snapshot"

_CANDIDATE_HISTORY_READ_RELATIONS = frozenset(
    {
        RELATION_LIVERMORE_CANDIDATE_HISTORY,
        RELATION_LIVERMORE_CANDIDATE_EXECUTION_HISTORY,
        RELATION_CHOICE_STOCK_DAILY_OBSERVATION,
        RELATION_STOCK_ADJUSTMENT_FACTOR,
        RELATION_FACT_CHOICE_MACRO_DAILY,
        RELATION_CHOICE_MARKET_SNAPSHOT,
        MATCHED_BASELINE_TABLE,
    }
)

CANDIDATE_HISTORY_SELECT_COLUMNS = (
    "snapshot_as_of_date",
    "stock_code",
    "stock_name",
    "candidate_rank",
    "sector_code",
    "sector_name",
    "selection_close",
    "forward_trade_date_1d",
    "forward_trade_date_5d",
    "forward_trade_date_10d",
    "forward_trade_date_20d",
    "return_1d",
    "return_5d",
    "return_10d",
    "return_20d",
    "return_1d_adj",
    "return_5d_adj",
    "return_10d_adj",
    "return_20d_adj",
    "data_status",
    "formula_version",
    "source_version",
    "vendor_version",
    "rule_version",
    "run_id",
    "signal_kind",
    "theme_key",
    "theme_name",
    "theme_source_kind",
    "theme_rank",
    "stock_rank_in_theme",
    "sector_rank",
    "market_state",
    "abnormal_turnover",
    "gap_norm",
    "breakout_extension_norm",
    "breakout_level",
    "ema10",
    "ma20",
    "ma60",
    "ma120",
    "strength_pctchange",
    "strength_turn",
    "strength_amplitude",
    "close_strength",
    "closed_up_limit",
    "signal_evidence_json",
)

CANDIDATE_EXECUTION_SELECT_COLUMNS = (
    "signal_date",
    "stock_code",
    "signal_kind",
    "market_state",
    "entry_executable",
    "entry_block_reason",
    "entry_date",
    "exit_date_5d",
    "return_1d_net_adj",
    "return_5d_gross_adj",
    "return_5d_net_adj",
    "return_10d_net_adj",
    "return_20d_net_adj",
)

MATCHED_BASELINE_SELECT_COLUMNS = (
    "signal_date",
    "candidate_stock_code",
    "signal_kind",
    "control_stock_code",
    "control_group",
    "control_return_1d_net_adj",
    "control_return_5d_net_adj",
    "control_return_10d_net_adj",
    "control_return_20d_net_adj",
    "control_entry_executable",
    "seed",
    "formula_version",
    "run_id",
)


class LivermoreCandidateHistoryRepository(DuckDBRepository):
    """Read-only access to candidate-history and replay-support relations."""

    @contextmanager
    def _connection(
        self,
        conn: duckdb.DuckDBPyConnection | None,
    ) -> Iterator[duckdb.DuckDBPyConnection | None]:
        if conn is not None:
            yield conn
            return
        with self.scoped_connection() as scoped:
            yield scoped

    def list_table_names(
        self,
        *,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> set[str]:
        with self._connection(conn) as active:
            if active is None:
                return set()
            return {str(row[0]) for row in active.execute("show tables").fetchall()}

    def table_columns(
        self,
        table_name: str,
        *,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> set[str]:
        if table_name not in _CANDIDATE_HISTORY_READ_RELATIONS:
            return set()
        with self._connection(conn) as active:
            if active is None:
                return set()
            return {str(row[1]).lower() for row in active.execute(f"pragma table_info('{table_name}')").fetchall()}

    @staticmethod
    def select_list(available_columns: set[str]) -> str:
        parts: list[str] = []
        for column in CANDIDATE_HISTORY_SELECT_COLUMNS:
            if column.lower() in available_columns:
                parts.append(column)
            elif column == "signal_kind":
                parts.append("'stock_candidate' as signal_kind")
            else:
                parts.append(f"null as {column}")
        return ", ".join(parts)

    @staticmethod
    def execution_select_list(available_columns: set[str]) -> str:
        parts: list[str] = []
        for column in CANDIDATE_EXECUTION_SELECT_COLUMNS:
            if column.lower() in available_columns:
                parts.append(column)
            elif column == "signal_kind":
                parts.append("'stock_candidate' as signal_kind")
            else:
                parts.append(f"null as {column}")
        return ", ".join(parts)

    @staticmethod
    def matched_baseline_select_list(available_columns: set[str]) -> str:
        parts: list[str] = []
        for column in MATCHED_BASELINE_SELECT_COLUMNS:
            if column.lower() in available_columns:
                parts.append(column)
            elif column == "signal_kind":
                parts.append("'stock_candidate' as signal_kind")
            else:
                parts.append(f"null as {column}")
        return ", ".join(parts)

    @staticmethod
    def candidate_history_filter(
        *,
        stock_code: str | None,
        snapshot_from: str | None,
        snapshot_to: str,
    ) -> tuple[str, list[object]]:
        where_clauses: list[str] = []
        bindings: list[object] = []
        if stock_code:
            where_clauses.append("stock_code = ?")
            bindings.append(stock_code)
        if snapshot_from:
            where_clauses.append("snapshot_as_of_date >= ?")
            bindings.append(snapshot_from[:10])
        where_clauses.append("try_cast(snapshot_as_of_date as date) <= cast(? as date)")
        bindings.append(snapshot_to)
        return f"where {' AND '.join(where_clauses)}", bindings

    def fetch_history_slice_rows(
        self,
        *,
        available_columns: set[str],
        sql_where: str,
        filter_bindings: list[object],
        limit: int,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> list[tuple[Any, ...]]:
        with self._connection(conn) as active:
            if active is None:
                return []
            return active.execute(
                f"""
                select {self.select_list(available_columns)}
                from {RELATION_LIVERMORE_CANDIDATE_HISTORY}
                {sql_where}
                order by snapshot_as_of_date desc, candidate_rank asc
                limit ?
                """,
                [*filter_bindings, limit],
            ).fetchall()

    def fetch_history_window_rows(
        self,
        *,
        stock_code: str | None,
        snapshot_from: str | None,
        snapshot_to: str | None,
        available_columns: set[str],
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> list[tuple[Any, ...]]:
        where_clauses: list[str] = []
        bindings: list[object] = []
        if stock_code:
            where_clauses.append("stock_code = ?")
            bindings.append(stock_code)
        if snapshot_from:
            where_clauses.append("snapshot_as_of_date >= ?")
            bindings.append(snapshot_from)
        if snapshot_to:
            where_clauses.append("snapshot_as_of_date <= ?")
            bindings.append(snapshot_to)
        sql_where = f"where {' AND '.join(where_clauses)}" if where_clauses else ""
        with self._connection(conn) as active:
            if active is None:
                return []
            return active.execute(
                f"""
                select {self.select_list(available_columns)}
                from {RELATION_LIVERMORE_CANDIDATE_HISTORY}
                {sql_where}
                order by snapshot_as_of_date asc, candidate_rank asc
                """,
                bindings,
            ).fetchall()

    def fetch_execution_window_rows(
        self,
        *,
        stock_code: str | None,
        snapshot_from: str | None,
        snapshot_to: str | None,
        available_columns: set[str],
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> list[tuple[Any, ...]]:
        where_clauses: list[str] = []
        bindings: list[object] = []
        if stock_code:
            where_clauses.append("stock_code = ?")
            bindings.append(stock_code)
        if snapshot_from:
            where_clauses.append("signal_date >= ?")
            bindings.append(snapshot_from[:10])
        if snapshot_to:
            where_clauses.append("signal_date <= ?")
            bindings.append(snapshot_to[:10])
        sql_where = f"where {' AND '.join(where_clauses)}" if where_clauses else ""
        with self._connection(conn) as active:
            if active is None:
                return []
            return active.execute(
                f"""
                select {self.execution_select_list(available_columns)}
                from {RELATION_LIVERMORE_CANDIDATE_EXECUTION_HISTORY}
                {sql_where}
                order by signal_date asc, stock_code asc
                """,
                bindings,
            ).fetchall()

    def fetch_matched_baseline_window_rows(
        self,
        *,
        stock_code: str | None,
        snapshot_from: str | None,
        snapshot_to: str | None,
        available_columns: set[str],
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> list[tuple[Any, ...]]:
        where_clauses: list[str] = []
        bindings: list[object] = []
        if stock_code:
            where_clauses.append("candidate_stock_code = ?")
            bindings.append(stock_code)
        if snapshot_from:
            where_clauses.append("signal_date >= ?")
            bindings.append(snapshot_from[:10])
        if snapshot_to:
            where_clauses.append("signal_date <= ?")
            bindings.append(snapshot_to[:10])
        sql_where = f"where {' AND '.join(where_clauses)}" if where_clauses else ""
        with self._connection(conn) as active:
            if active is None:
                return []
            return active.execute(
                f"""
                select {self.matched_baseline_select_list(available_columns)}
                from {MATCHED_BASELINE_TABLE}
                {sql_where}
                order by signal_date asc, candidate_stock_code asc, control_stock_code asc
                """,
                bindings,
            ).fetchall()

    def fetch_observation_trade_dates_after(
        self,
        *,
        min_snapshot_date: str,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> list[tuple[Any, ...]]:
        with self._connection(conn) as active:
            if active is None:
                return []
            return active.execute(
                f"""
                select distinct trade_date
                from {RELATION_CHOICE_STOCK_DAILY_OBSERVATION}
                where trade_date > ?
                  and close_value is not null
                """,
                [min_snapshot_date],
            ).fetchall()

    def fetch_forward_maturity_observation_rows(
        self,
        *,
        min_snapshot_date: str,
        evaluation_as_of_date: str,
        stock_codes: set[str],
        has_trade_status: bool,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
        status_select = "tradestatus" if has_trade_status else "null as tradestatus"
        valid_status_sql = (
            f"and {tradable_status_sql_condition('tradestatus')}" if has_trade_status else ""
        )
        code_placeholders = ", ".join("?" for _ in stock_codes)
        with self._connection(conn) as active:
            if active is None:
                return [], []
            rows = active.execute(
                f"""
                with latest_revisions as (
                  select
                    trade_date,
                    stock_code,
                    close_value,
                    {status_select},
                    row_number() over (
                      partition by
                        upper(trim(cast(stock_code as varchar))),
                        try_cast(trade_date as date)
                      order by rowid desc
                    ) as revision_rank
                  from {RELATION_CHOICE_STOCK_DAILY_OBSERVATION}
                  where try_cast(trade_date as date) > cast(? as date)
                    and try_cast(trade_date as date) <= cast(? as date)
                    and upper(trim(cast(stock_code as varchar))) in ({code_placeholders})
                )
                select trade_date, stock_code, close_value, tradestatus
                from latest_revisions
                where revision_rank = 1
                order by trade_date, stock_code
                """,
                [min_snapshot_date, evaluation_as_of_date, *sorted(stock_codes)],
            ).fetchall()
            market_rows = active.execute(
                f"""
                with latest_revisions as (
                  select
                    trade_date,
                    stock_code,
                    close_value,
                    {status_select},
                    row_number() over (
                      partition by
                        upper(trim(cast(stock_code as varchar))),
                        try_cast(trade_date as date)
                      order by rowid desc
                    ) as revision_rank
                  from {RELATION_CHOICE_STOCK_DAILY_OBSERVATION}
                  where try_cast(trade_date as date) > cast(? as date)
                    and try_cast(trade_date as date) <= cast(? as date)
                )
                select distinct try_cast(trade_date as date)
                from latest_revisions
                where revision_rank = 1
                  and try_cast(close_value as double) > 0
                  and isfinite(try_cast(close_value as double))
                  {valid_status_sql}
                order by 1
                """,
                [min_snapshot_date, evaluation_as_of_date],
            ).fetchall()
        return rows, market_rows

    @staticmethod
    def _filtered_maturity_sql(
        *,
        available_columns: set[str],
        sql_where: str,
    ) -> str:
        def date_expr(column: str) -> str:
            return f"try_cast({column} as date)" if column in available_columns else "cast(null as date)"

        def number_expr(column: str) -> str:
            return f"try_cast({column} as double)" if column in available_columns else "cast(null as double)"

        stock_expr = (
            "upper(trim(cast(stock_code as varchar)))" if "stock_code" in available_columns else "cast(null as varchar)"
        )
        return f"""
            select
              rowid as candidate_rowid,
              {date_expr("snapshot_as_of_date")} as snapshot_date,
              {stock_expr} as stock_code,
              {date_expr("forward_trade_date_1d")} as stored_date_1d,
              {date_expr("forward_trade_date_5d")} as stored_date_5d,
              {date_expr("forward_trade_date_10d")} as stored_date_10d,
              {date_expr("forward_trade_date_20d")} as stored_date_20d,
              {number_expr("return_1d")} as raw_return_1d,
              {number_expr("return_5d")} as raw_return_5d,
              {number_expr("return_10d")} as raw_return_10d,
              {number_expr("return_20d")} as raw_return_20d,
              {number_expr("return_1d_adj")} as adjusted_return_1d,
              {number_expr("return_5d_adj")} as adjusted_return_5d,
              {number_expr("return_10d_adj")} as adjusted_return_10d,
              {number_expr("return_20d_adj")} as adjusted_return_20d
            from {RELATION_LIVERMORE_CANDIDATE_HISTORY}
            {sql_where}
        """

    def fetch_filtered_maturity_overview(
        self,
        *,
        available_columns: set[str],
        sql_where: str,
        filter_bindings: list[object],
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> tuple[Any, ...] | None:
        filtered_sql = self._filtered_maturity_sql(
            available_columns=available_columns,
            sql_where=sql_where,
        )
        with self._connection(conn) as active:
            if active is None:
                return None
            return active.execute(
                f"with filtered as ({filtered_sql}) select count(*)::bigint, max(snapshot_date) from filtered",
                filter_bindings,
            ).fetchone()

    def fetch_all_filtered_maturity_rows(
        self,
        *,
        available_columns: set[str],
        observation_columns: set[str],
        sql_where: str,
        filter_bindings: list[object],
        evaluation_as_of_date: str,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> list[tuple[Any, ...]]:
        filtered_sql = self._filtered_maturity_sql(
            available_columns=available_columns,
            sql_where=sql_where,
        )
        has_trade_status = "tradestatus" in observation_columns
        latest_status_select = (
            "first(cast(o.tradestatus as varchar) order by o.rowid desc)"
            if has_trade_status
            else "cast(null as varchar)"
        )
        scoped_valid_status_sql = (
            tradable_status_sql_condition("o.trade_status") if has_trade_status else "true"
        )
        market_status_sql = (
            f"and {tradable_status_sql_condition('trade_status')}" if has_trade_status else ""
        )
        explicit_halt_sql = (
            # 空串/NULL 在共享语义下视为可交易，因此"非可交易"即显式停牌。
            f"not {tradable_status_sql_condition('o.trade_status')}"
            if has_trade_status
            else "false"
        )
        with self._connection(conn) as active:
            if active is None:
                return []
            return active.execute(
                f"""
                with filtered as materialized ({filtered_sql}),
                candidate_bounds as (
                  select min(snapshot_date) as minimum_snapshot_date
                  from filtered
                  where snapshot_date is not null
                ),
                candidate_stocks as (
                  select stock_code, min(snapshot_date) as minimum_snapshot_date
                  from filtered
                  where stock_code is not null and snapshot_date is not null
                  group by stock_code
                ),
                market_latest_observations as materialized (
                  select
                    upper(trim(cast(o.stock_code as varchar))) as stock_code,
                    try_cast(o.trade_date as date) as trade_date,
                    first(try_cast(o.close_value as double) order by o.rowid desc) as close_value,
                    {latest_status_select} as trade_status
                  from {RELATION_CHOICE_STOCK_DAILY_OBSERVATION} o
                  cross join candidate_bounds bounds
                  where bounds.minimum_snapshot_date is not null
                    and try_cast(o.trade_date as date) > bounds.minimum_snapshot_date
                    and try_cast(o.trade_date as date) <= cast(? as date)
                  group by 1, 2
                ),
                market_dates as (
                  select distinct trade_date
                  from market_latest_observations
                  where close_value > 0
                    and isfinite(close_value)
                    {market_status_sql}
                ),
                market_counts as (
                  select f.candidate_rowid, count(m.trade_date)::bigint as market_count
                  from filtered f
                  left join market_dates m
                    on f.snapshot_date is not null and m.trade_date > f.snapshot_date
                  group by f.candidate_rowid
                ),
                candidate_observation_revisions as materialized (
                  select
                    upper(trim(cast(o.stock_code as varchar))) as stock_code,
                    try_cast(o.trade_date as date) as trade_date,
                    first(try_cast(o.close_value as double) order by o.rowid desc) as close_value,
                    {latest_status_select} as trade_status
                  from {RELATION_CHOICE_STOCK_DAILY_OBSERVATION} o
                  join candidate_stocks stocks
                    on stocks.stock_code = upper(trim(cast(o.stock_code as varchar)))
                   and try_cast(o.trade_date as date) > stocks.minimum_snapshot_date
                  where try_cast(o.trade_date as date) is not null
                    and try_cast(o.trade_date as date) <= cast(? as date)
                  group by 1, 2
                ),
                candidate_observations as materialized (
                  select
                    o.stock_code,
                    o.trade_date,
                    (
                      o.close_value > 0
                      and isfinite(o.close_value)
                      and {scoped_valid_status_sql}
                    ) as valid_close,
                    ({explicit_halt_sql}) as explicit_halt
                  from candidate_observation_revisions o
                ),
                valid_observations as (
                  select
                    f.candidate_rowid,
                    o.trade_date,
                    row_number() over (
                      partition by f.candidate_rowid
                      order by o.trade_date
                    ) as bar_number
                  from filtered f
                  join candidate_observations o
                    on o.stock_code = f.stock_code
                   and f.snapshot_date is not null
                   and o.trade_date > f.snapshot_date
                   and o.valid_close
                  qualify bar_number <= 20
                ),
                targets as (
                  select
                    candidate_rowid,
                    count(*)::bigint as stock_valid_bar_count,
                    max(case when bar_number = 1 then trade_date end) as target_1d,
                    max(case when bar_number = 5 then trade_date end) as target_5d,
                    max(case when bar_number = 10 then trade_date end) as target_10d,
                    max(case when bar_number = 20 then trade_date end) as target_20d
                  from valid_observations
                  group by candidate_rowid
                ),
                halt_flags as (
                  select
                    f.candidate_rowid,
                     max(case when o.explicit_halt then 1 else 0 end)::integer as explicit_halt
                  from filtered f
                  left join candidate_observations o
                    on o.stock_code = f.stock_code
                   and f.snapshot_date is not null
                   and o.trade_date > f.snapshot_date
                  group by f.candidate_rowid
                ),
                horizon_rows as (
                  select
                    f.candidate_rowid,
                    f.snapshot_date,
                    h.horizon,
                    h.bar_count,
                    case h.horizon
                      when '1d' then f.stored_date_1d when '5d' then f.stored_date_5d
                      when '10d' then f.stored_date_10d else f.stored_date_20d end as stored_date,
                    case h.horizon
                      when '1d' then f.raw_return_1d when '5d' then f.raw_return_5d
                      when '10d' then f.raw_return_10d else f.raw_return_20d end as raw_return,
                    case h.horizon
                      when '1d' then f.adjusted_return_1d when '5d' then f.adjusted_return_5d
                      when '10d' then f.adjusted_return_10d else f.adjusted_return_20d end as adjusted_return,
                    case h.horizon
                      when '1d' then t.target_1d when '5d' then t.target_5d
                      when '10d' then t.target_10d else t.target_20d end as expected_target,
                    coalesce(t.stock_valid_bar_count, 0) as stock_valid_bar_count,
                    coalesce(m.market_count, 0) as market_count,
                    coalesce(hf.explicit_halt, 0) as explicit_halt
                  from filtered f
                  cross join (values ('1d', 1), ('5d', 5), ('10d', 10), ('20d', 20)) h(horizon, bar_count)
                  left join targets t on t.candidate_rowid = f.candidate_rowid
                  left join market_counts m on m.candidate_rowid = f.candidate_rowid
                  left join halt_flags hf on hf.candidate_rowid = f.candidate_rowid
                ),
                classified as (
                  select
                    horizon,
                    snapshot_date,
                    case
                      when stored_date is not null and stored_date = expected_target
                           and raw_return is not null and isfinite(raw_return)
                        then case
                          when adjusted_return is not null and isfinite(adjusted_return) then 'complete'
                          else 'raw_matured_adjustment_missing' end
                      when market_count < bar_count then 'natural_pending'
                      when explicit_halt = 1 and stock_valid_bar_count < bar_count then 'partial_halt'
                      else 'matured_missing_bar'
                    end as status
                  from horizon_rows
                )
                select horizon, status, count(*)::bigint, max(snapshot_date)
                from classified
                group by horizon, status
                order by horizon, status
                """,
                [*filter_bindings, evaluation_as_of_date, evaluation_as_of_date],
            ).fetchall()

    def latest_observation_trade_date(
        self,
        *,
        on_or_before: str,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> Any | None:
        with self._connection(conn) as active:
            if active is None:
                return None
            row = active.execute(
                f"""
                select max(try_cast(trade_date as date))
                from {RELATION_CHOICE_STOCK_DAILY_OBSERVATION}
                where try_cast(trade_date as date) <= cast(? as date)
                """,
                [on_or_before],
            ).fetchone()
            return row[0] if row else None

    def fetch_replay_trade_dates(
        self,
        *,
        snapshot_from: str | None,
        snapshot_to: str | None,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> list[tuple[Any, ...]]:
        where_clauses: list[str] = []
        bindings: list[object] = []
        if snapshot_from:
            where_clauses.append("trade_date >= ?")
            bindings.append(snapshot_from)
        if snapshot_to:
            where_clauses.append("trade_date <= ?")
            bindings.append(snapshot_to)
        sql_where = f"where {' AND '.join(where_clauses)}" if where_clauses else ""
        with self._connection(conn) as active:
            if active is None:
                return []
            return active.execute(
                f"""
                select distinct trade_date
                from {RELATION_CHOICE_STOCK_DAILY_OBSERVATION}
                {sql_where}
                order by trade_date asc
                """,
                bindings,
            ).fetchall()

    def fetch_portfolio_close_rows(
        self,
        *,
        stock_codes: list[str],
        start_date: str,
        snapshot_to: str | None,
        has_adjustment_factor: bool,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> list[tuple[Any, ...]]:
        placeholders = ", ".join("?" for _ in stock_codes)
        where_to = "and d.trade_date <= ?" if snapshot_to else ""
        adj_select = (
            """
              case
                when af.adj_factor is not null and af.adj_factor > 0
                then d.close_value * af.adj_factor
                else null
              end as adj_close_value,
              af.adj_factor
            """
            if has_adjustment_factor
            else """
              cast(null as double) as adj_close_value,
              cast(null as double) as adj_factor
            """
        )
        adj_join = (
            f"""
            left join {RELATION_STOCK_ADJUSTMENT_FACTOR} af
              on af.stock_code = d.stock_code
             and af.trade_date = d.trade_date
            """
            if has_adjustment_factor
            else ""
        )
        bindings: list[object] = [*stock_codes, start_date]
        if snapshot_to:
            bindings.append(snapshot_to)
        with self._connection(conn) as active:
            if active is None:
                return []
            return active.execute(
                f"""
                select
                  d.trade_date,
                  d.stock_code,
                  d.close_value,
                  {adj_select}
                from {RELATION_CHOICE_STOCK_DAILY_OBSERVATION} d
                {adj_join}
                where d.stock_code in ({placeholders})
                  and d.trade_date >= ?
                  {where_to}
                order by d.trade_date asc, d.stock_code asc
                """,
                bindings,
            ).fetchall()

    def has_adjustment_factor(
        self,
        *,
        tables: set[str] | None = None,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> bool:
        table_names = tables if tables is not None else self.list_table_names(conn=conn)
        if RELATION_STOCK_ADJUSTMENT_FACTOR not in table_names:
            return False
        columns = self.table_columns(RELATION_STOCK_ADJUSTMENT_FACTOR, conn=conn)
        return {"stock_code", "trade_date", "adj_factor"}.issubset(columns)

    def fetch_benchmark_rows(
        self,
        *,
        table_name: str,
        series_id: str,
        start_date: str,
        end_date: str,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> list[tuple[Any, ...]]:
        if table_name not in {
            RELATION_CHOICE_MARKET_SNAPSHOT,
            RELATION_FACT_CHOICE_MACRO_DAILY,
        }:
            return []
        with self._connection(conn) as active:
            if active is None:
                return []
            return active.execute(
                f"""
                select trade_date, value_numeric
                from {table_name}
                where series_id = ?
                  and value_numeric is not null
                  and cast(trade_date as date) >= ?
                  and cast(trade_date as date) <= ?
                order by cast(trade_date as date) asc
                """,
                [series_id, start_date, end_date],
            ).fetchall()

    def latest_history_snapshot_date(
        self,
        *,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> Any | None:
        with self._connection(conn) as active:
            if active is None:
                return None
            row = active.execute(
                f"select max(snapshot_as_of_date) from {RELATION_LIVERMORE_CANDIDATE_HISTORY}"
            ).fetchone()
            return row[0] if row else None
