from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any, cast

import duckdb
from backend.app.core_finance.field_normalization import tradable_status_sql_condition
from backend.app.core_finance.livermore_sector_rank import SectorRankConstituent
from backend.app.repositories.choice_stock_units import (
    amount_rmb_sql,
    scale_unknown_sql,
    volume_shares_sql,
)
from backend.app.repositories.duckdb_repo import DuckDBRepository, read_only_connection

logger = logging.getLogger(__name__)

RELATION_CHOICE_STOCK_DAILY_OBSERVATION = "choice_stock_daily_observation"
RELATION_CHOICE_STOCK_FACTOR_SNAPSHOT = "choice_stock_factor_snapshot"
RELATION_CHOICE_STOCK_SECTOR_MEMBERSHIP = "choice_stock_sector_membership"
RELATION_CHOICE_STOCK_UNIVERSE = "choice_stock_universe"
RELATION_CHOICE_STOCK_LIMIT_QUALITY = "choice_stock_limit_quality"
RELATION_CHOICE_STOCK_CONCEPT_MEMBERSHIP = "choice_stock_concept_membership"
RELATION_CHOICE_STOCK_CONCEPT_MEMBERSHIP_INTERVAL = "choice_stock_concept_membership_interval"
RELATION_CHOICE_STOCK_INTRADAY_MOVEMENT_EVENT = "choice_stock_intraday_movement_event"
RELATION_LIVERMORE_POSITION_SNAPSHOT = "livermore_position_snapshot"
RELATION_FACT_CHOICE_MACRO_DAILY = "fact_choice_macro_daily"
RELATION_CHOICE_MARKET_SNAPSHOT = "choice_market_snapshot"

_MARKET_READ_RELATIONS = frozenset(
    {
        RELATION_CHOICE_STOCK_DAILY_OBSERVATION,
        RELATION_CHOICE_STOCK_FACTOR_SNAPSHOT,
        RELATION_CHOICE_STOCK_SECTOR_MEMBERSHIP,
        RELATION_LIVERMORE_POSITION_SNAPSHOT,
    }
)

# Relations readable by the Livermore strategy read surface. Any table name that
# reaches a FROM/JOIN/PRAGMA clause must come from this whitelist.
_STRATEGY_READ_RELATIONS = frozenset(
    {
        RELATION_CHOICE_STOCK_DAILY_OBSERVATION,
        RELATION_CHOICE_STOCK_FACTOR_SNAPSHOT,
        RELATION_CHOICE_STOCK_SECTOR_MEMBERSHIP,
        RELATION_CHOICE_STOCK_UNIVERSE,
        RELATION_CHOICE_STOCK_LIMIT_QUALITY,
        RELATION_CHOICE_STOCK_CONCEPT_MEMBERSHIP,
        RELATION_CHOICE_STOCK_INTRADAY_MOVEMENT_EVENT,
        RELATION_LIVERMORE_POSITION_SNAPSHOT,
        RELATION_FACT_CHOICE_MACRO_DAILY,
        RELATION_CHOICE_MARKET_SNAPSHOT,
    }
)
_STRATEGY_READ_DATE_COLUMNS = frozenset({"as_of_date", "trade_date"})

TABLE_OBS = RELATION_CHOICE_STOCK_DAILY_OBSERVATION
TABLE_FACTOR = RELATION_CHOICE_STOCK_FACTOR_SNAPSHOT
TABLE_MEMBERSHIP = RELATION_CHOICE_STOCK_SECTOR_MEMBERSHIP


def _warn_duckdb_query_failed(
    stage: str,
    *,
    exc: BaseException,
    tables: object = None,
    as_of_date: str | date | None = None,
) -> str:
    if isinstance(tables, (list, tuple, set, frozenset)):
        table_text = ",".join(str(item) for item in tables) or "-"
    elif tables:
        table_text = str(tables)
    else:
        table_text = "-"
    date_text = (
        as_of_date.isoformat()
        if isinstance(as_of_date, date)
        else (str(as_of_date) if as_of_date else "-")
    )
    summary = str(exc).strip().replace("\n", " ")[:300] or exc.__class__.__name__
    logger.warning(
        "livermore_duckdb_query_failed stage=%s tables=%s as_of_date=%s error=%s",
        stage,
        table_text,
        date_text,
        summary,
    )
    return (
        f"DuckDB query failed stage={stage} tables={table_text} "
        f"as_of_date={date_text} error={summary}"
    )


def open_livermore_read_connection(duckdb_path: str) -> duckdb.DuckDBPyConnection | None:
    """Open a read-only DuckDB connection for Livermore reads; ``None`` when unavailable.

    Callers own the returned connection and must close it. Mirrors the degrade-to-empty
    behaviour the Livermore read path relies on instead of raising on open failure.
    """
    try:
        return duckdb.connect(str(duckdb_path), read_only=True)
    except duckdb.Error as exc:
        _warn_duckdb_query_failed(
            "open_livermore_read_connection",
            exc=exc,
            tables="-",
            as_of_date=None,
        )
        return None


@contextmanager
def livermore_shared_read_only_connection(
    duckdb_path: str,
) -> Iterator[duckdb.DuckDBPyConnection | None]:
    """Open one read-only connection for a request and reuse it across loaders.

    Yields ``None`` (instead of raising) when the file is missing or cannot be
    opened, so each loader can fall back to its own connection or degrade to an
    empty result. The connection closes when the ``with`` block exits, keeping
    the file-lock window short for separate writer processes.
    """
    path = Path(duckdb_path)
    if not path.exists():
        yield None
        return
    conn = open_livermore_read_connection(str(path))
    if conn is None:
        yield None
        return
    try:
        yield conn
    finally:
        conn.close()


class LivermoreMarketReadRepository(DuckDBRepository):
    """Read-only Livermore stock/sector/position market tables via shared DuckDB helpers."""

    def list_table_names(
        self,
        *,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> set[str]:
        if conn is not None:
            return {row[0] for row in conn.execute("show tables").fetchall()}
        with self.scoped_connection() as scoped:
            if scoped is None:
                return set()
            return {row[0] for row in scoped.execute("show tables").fetchall()}

    def resolve_stock_end_trade_date(
        self,
        *,
        stock_code: str,
        as_of_date: date | None,
        conn: duckdb.DuckDBPyConnection,
    ) -> date | None:
        if TABLE_OBS not in _MARKET_READ_RELATIONS:
            return None
        # close_value 非空：native 空串状态视为可交易后，供应商预填的
        # 全空占位行不得把锚定日拖向未来。
        if as_of_date is not None:
            row = conn.execute(
                f"""
                select max(trade_date) as mx
                from {TABLE_OBS}
                where stock_code = ?
                  and trade_date <= ?
                  and close_value is not null
                  and {tradable_status_sql_condition('tradestatus')}
                """,
                [stock_code, as_of_date.isoformat()],
            ).fetchone()
        else:
            row = conn.execute(
                f"""
                select max(trade_date) as mx
                from {TABLE_OBS}
                where stock_code = ?
                  and close_value is not null
                  and {tradable_status_sql_condition('tradestatus')}
                """,
                [stock_code],
            ).fetchone()
        if row is None or row[0] is None:
            return None
        raw = str(row[0]).strip()
        if not raw:
            return None
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            return None

    def fetch_candles(
        self,
        *,
        stock_code: str,
        end_trade_date: date,
        lookback: int,
        conn: duckdb.DuckDBPyConnection,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        if TABLE_OBS not in _MARKET_READ_RELATIONS:
            return [], []
        upper = end_trade_date.isoformat()

        # close_value 非空：与锚定日查询同口径，供应商预填的全空占位行
        # （native 代际 tradestatus='' 且 close NULL）不得占用 lookback
        # 名额输出空蜡烛。
        def execute(
            volume_projection: str,
            amount_projection: str,
            volume_unknown_projection: str,
            amount_unknown_projection: str,
            vendor_projection: str,
        ) -> list[dict[str, Any]]:
            result = conn.execute(
                f"""
                select
                  trade_date,
                  open_value,
                  high_value,
                  low_value,
                  close_value,
                  {volume_projection},
                  {amount_projection},
                  source_version,
                  {vendor_projection},
                  {volume_unknown_projection},
                  {amount_unknown_projection}
                from {TABLE_OBS}
                where stock_code = ?
                  and trade_date <= ?
                  and close_value is not null
                  and {tradable_status_sql_condition('tradestatus')}
                order by trade_date desc
                limit ?
                """,
                [stock_code, upper, lookback],
            )
            cols = [d[0] for d in result.description]
            return [dict(zip(cols, row, strict=True)) for row in result.fetchall()]

        warnings: list[str] = []
        try:
            rows = execute(
                volume_shares_sql(alias="volume"),
                amount_rmb_sql(alias="amount"),
                scale_unknown_sql("volume", alias="_volume_scale_unknown"),
                scale_unknown_sql("amount", alias="_amount_scale_unknown"),
                "vendor_version",
            )
        except duckdb.BinderException as exc:
            if "vendor_version" not in str(exc).casefold():
                raise
            logger.warning(
                "%s missing vendor_version; stock-detail amount/volume cannot be scaled, "
                "output as NULL (fail-closed)",
                TABLE_OBS,
            )
            warnings.append("vendor_version_column_missing_null_units")
            rows = execute(
                "cast(null as double) as volume",
                "cast(null as double) as amount",
                "false as _volume_scale_unknown",
                "false as _amount_scale_unknown",
                "cast(null as varchar) as vendor_version",
            )

        volume_unknown_count = sum(bool(row.pop("_volume_scale_unknown", False)) for row in rows)
        amount_unknown_count = sum(bool(row.pop("_amount_scale_unknown", False)) for row in rows)
        if volume_unknown_count:
            logger.warning(
                "%s has %d stock-detail rows with volume but null vendor_version; "
                "normalized volume is null",
                TABLE_OBS,
                volume_unknown_count,
            )
            warnings.append("volume_unit_scale_unknown")
        if amount_unknown_count:
            logger.warning(
                "%s has %d stock-detail rows with amount but null vendor_version; "
                "normalized amount is null",
                TABLE_OBS,
                amount_unknown_count,
            )
            warnings.append("amount_unit_scale_unknown")
        return rows, warnings

    def fetch_factor_row(
        self,
        *,
        stock_code: str,
        end_as_of: str,
        conn: duckdb.DuckDBPyConnection,
    ) -> dict[str, Any] | None:
        if TABLE_FACTOR not in _MARKET_READ_RELATIONS:
            return None
        result = conn.execute(
            f"""
            select
              as_of_date,
              pe,
              pb,
              roe,
              dividend_yield,
              source_version,
              vendor_version
            from {TABLE_FACTOR}
            where stock_code = ?
              and as_of_date <= ?
            order by as_of_date desc
            limit 1
            """,
            [stock_code, end_as_of],
        )
        row = result.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in result.description]
        return dict(zip(cols, row, strict=True))

    def resolve_global_end_trade_date(
        self,
        *,
        as_of_date: date | None,
        conn: duckdb.DuckDBPyConnection,
    ) -> date | None:
        if TABLE_OBS not in _MARKET_READ_RELATIONS:
            return None
        if as_of_date is not None:
            row = conn.execute(
                f"""
                select max(cast(trade_date as date)) as mx
                from {TABLE_OBS}
                where cast(trade_date as date) <= cast(? as date)
                """,
                [as_of_date.isoformat()],
            ).fetchone()
        else:
            row = conn.execute(
                f"""
                select max(cast(trade_date as date)) as mx
                from {TABLE_OBS}
                """,
            ).fetchone()
        if row is None or row[0] is None:
            return None
        raw = row[0]
        if hasattr(raw, "isoformat"):
            return cast(date, raw)
        text = str(raw).strip()[:10]
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None

    def fetch_trade_dates_in_range(
        self,
        *,
        end_inclusive: date,
        start_inclusive: date,
        limit_last_n: int,
        conn: duckdb.DuckDBPyConnection,
    ) -> list[date]:
        if TABLE_OBS not in _MARKET_READ_RELATIONS:
            return []
        rows = conn.execute(
            f"""
            select distinct cast(trade_date as date) as d
            from {TABLE_OBS}
            where cast(trade_date as date) <= ?
              and cast(trade_date as date) >= ?
            order by d desc
            """,
            [end_inclusive.isoformat(), start_inclusive.isoformat()],
        ).fetchall()
        out: list[date] = []
        for row in rows:
            if row[0] is None:
                continue
            raw = row[0]
            if hasattr(raw, "isoformat"):
                d = cast(date, raw)
            else:
                try:
                    d = date.fromisoformat(str(raw).strip()[:10])
                except ValueError:
                    continue
            out.append(d)
            if len(out) >= limit_last_n:
                break
        return list(reversed(out))

    def load_sector_rank_constituents(
        self,
        *,
        as_of_date: str,
        conn: duckdb.DuckDBPyConnection,
    ) -> tuple[list[SectorRankConstituent], list[str], list[str]]:
        if (
            TABLE_MEMBERSHIP not in _MARKET_READ_RELATIONS
            or TABLE_OBS not in _MARKET_READ_RELATIONS
        ):
            return [], [], []
        membership_snapshot_date = self.latest_table_date_on_or_before(
            table_name=TABLE_MEMBERSHIP,
            column_name="as_of_date",
            as_of_date=as_of_date,
            conn=conn,
        )
        if membership_snapshot_date is None:
            return [], [], []
        try:
            rows = conn.execute(
                f"""
                select
                  membership.stock_code,
                  membership.sw2021code,
                  membership.sw2021,
                  daily.pctchange,
                  daily.turn,
                  daily.amplitude,
                  membership.source_version,
                  membership.vendor_version,
                  daily.source_version,
                  daily.vendor_version
                from {TABLE_MEMBERSHIP} membership
                join {TABLE_OBS} daily
                  on daily.stock_code = membership.stock_code
                 and cast(daily.trade_date as date) = cast(? as date)
                where membership.as_of_date = ?
                """,
                [as_of_date, membership_snapshot_date],
            ).fetchall()
        except duckdb.Error as exc:
            _warn_duckdb_query_failed(
                "load_sector_rank_constituents",
                exc=exc,
                tables=[TABLE_MEMBERSHIP, TABLE_OBS],
                as_of_date=as_of_date,
            )
            return [], [], []

        constituents = [
            SectorRankConstituent(
                stock_code=str(row[0] or ""),
                sector_code=str(row[1] or ""),
                sector_name=str(row[2] or ""),
                pctchange=row[3],
                turn=row[4],
                amplitude=row[5],
            )
            for row in rows
        ]
        source_versions = [str(value) for row in rows for value in (row[6], row[8]) if value]
        vendor_versions = [str(value) for row in rows for value in (row[7], row[9]) if value]
        return constituents, source_versions, vendor_versions

    def latest_table_date_on_or_before(
        self,
        *,
        table_name: str,
        column_name: str,
        as_of_date: str,
        conn: duckdb.DuckDBPyConnection,
    ) -> str | None:
        if table_name not in _MARKET_READ_RELATIONS:
            return None
        try:
            row = conn.execute(
                f"""
                select max({column_name})
                from {table_name}
                where cast({column_name} as date) <= cast(? as date)
                """,
                [as_of_date],
            ).fetchone()
        except duckdb.Error as exc:
            _warn_duckdb_query_failed(
                "latest_table_date_on_or_before",
                exc=exc,
                tables=table_name,
                as_of_date=as_of_date,
            )
            return None
        return str(row[0]) if row and row[0] else None

    def position_active_max_date(
        self,
        *,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> str | None:
        if conn is not None:
            return self._position_active_max_date_impl(conn)
        if self.guard_path_exists and not Path(self.path).exists():
            return None
        try:
            with read_only_connection(self.path) as scoped:
                return self._position_active_max_date_impl(scoped)
        except (OSError, duckdb.Error) as exc:
            _warn_duckdb_query_failed(
                "position_active_max_date",
                exc=exc,
                tables=RELATION_LIVERMORE_POSITION_SNAPSHOT,
            )
            return None

    def _position_active_max_date_impl(
        self,
        conn: duckdb.DuckDBPyConnection,
    ) -> str | None:
        if RELATION_LIVERMORE_POSITION_SNAPSHOT not in _MARKET_READ_RELATIONS:
            return None
        try:
            exists = conn.execute(
                """
                select 1
                from information_schema.tables
                where table_schema = 'main' and table_name = ?
                limit 1
                """,
                [RELATION_LIVERMORE_POSITION_SNAPSHOT],
            ).fetchone()
            if exists is None:
                return None
            row = conn.execute(
                f"""
                select max(cast(as_of_date as date))
                from {RELATION_LIVERMORE_POSITION_SNAPSHOT}
                where upper(coalesce(position_status, 'ACTIVE')) = 'ACTIVE'
                """
            ).fetchone()
        except duckdb.Error as exc:
            _warn_duckdb_query_failed(
                "position_active_max_date_impl",
                exc=exc,
                tables=RELATION_LIVERMORE_POSITION_SNAPSHOT,
            )
            return None
        if not row or row[0] is None:
            return None
        value = row[0]
        return value.isoformat() if hasattr(value, "isoformat") else str(value)[:10]


class LivermoreStrategyReadRepository(DuckDBRepository):
    """Read-only Livermore strategy inputs (Choice stock / macro / position tables).

    Every query method takes an injected ``conn`` so one request can reuse a single
    read-only connection across all strategy loaders. Table and date-column names
    that reach a FROM/JOIN/PRAGMA clause are constrained to the module whitelists.
    """

    # ---- catalog probes ---------------------------------------------------

    def list_table_names(self, *, conn: duckdb.DuckDBPyConnection) -> set[str]:
        return {str(row[0]) for row in conn.execute("show tables").fetchall()}

    def table_columns(
        self,
        *,
        table_name: str,
        conn: duckdb.DuckDBPyConnection,
    ) -> set[str]:
        if table_name not in _STRATEGY_READ_RELATIONS:
            return set()
        try:
            return {
                str(row[1])
                for row in conn.execute(f"pragma table_info('{table_name}')").fetchall()
            }
        except duckdb.Error as exc:
            _warn_duckdb_query_failed(
                "table_columns",
                exc=exc,
                tables=table_name,
            )
            return set()

    def table_has_columns(
        self,
        *,
        table_name: str,
        columns: list[str],
        conn: duckdb.DuckDBPyConnection,
    ) -> bool:
        return set(columns).issubset(self.table_columns(table_name=table_name, conn=conn))

    def latest_snapshot_date_on_or_before(
        self,
        *,
        table_name: str,
        column_name: str,
        as_of_date: str,
        conn: duckdb.DuckDBPyConnection,
    ) -> str | None:
        if (
            table_name not in _STRATEGY_READ_RELATIONS
            or column_name not in _STRATEGY_READ_DATE_COLUMNS
        ):
            return None
        try:
            row = conn.execute(
                f"""
            select max({column_name})
            from {table_name}
            where cast({column_name} as date) <= cast(? as date)
            """,
                [as_of_date],
            ).fetchone()
        except duckdb.Error as exc:
            _warn_duckdb_query_failed(
                "latest_snapshot_date_on_or_before",
                exc=exc,
                tables=table_name,
                as_of_date=as_of_date,
            )
            return None
        return str(row[0]) if row and row[0] else None

    def count_distinct_stock_codes(
        self,
        *,
        table_name: str,
        date_column: str,
        as_of_date: str,
        conn: duckdb.DuckDBPyConnection,
    ) -> int:
        if (
            table_name not in _STRATEGY_READ_RELATIONS
            or date_column not in _STRATEGY_READ_DATE_COLUMNS
        ):
            return 0
        try:
            row = conn.execute(
                f"""
            select count(distinct stock_code)
            from {table_name}
            where cast({date_column} as date) = cast(? as date)
            """,
                [as_of_date],
            ).fetchone()
        except duckdb.Error as exc:
            _warn_duckdb_query_failed(
                "count_distinct_stock_codes",
                exc=exc,
                tables=table_name,
                as_of_date=as_of_date,
            )
            return 0
        return int(row[0]) if row and row[0] is not None else 0

    # ---- broad index history ---------------------------------------------

    def fetch_broad_index_history_rows(
        self,
        *,
        series_id: str,
        as_of_date: date | None,
        history_limit: int,
        include_macro_daily: bool,
        include_market_snapshot: bool,
        conn: duckdb.DuckDBPyConnection,
    ) -> list[tuple[Any, ...]]:
        queries: list[str] = []
        params: list[object] = []
        date_filter = "and cast(trade_date as date) <= ?" if as_of_date is not None else ""
        if include_macro_daily:
            queries.append(
                f"""
                select
                  cast(trade_date as date) as trade_date,
                  cast(value_numeric as double) as close_value,
                  coalesce(source_version, '') as source_version,
                  coalesce(vendor_version, '') as vendor_version,
                  coalesce(quality_flag, 'ok') as quality_flag,
                  0 as source_rank
                from {RELATION_FACT_CHOICE_MACRO_DAILY}
                where series_id = ?
                  and value_numeric is not null
                  {date_filter}
                """
            )
            params.append(series_id)
            if as_of_date is not None:
                params.append(as_of_date.isoformat())
        if include_market_snapshot:
            queries.append(
                f"""
                select
                  cast(trade_date as date) as trade_date,
                  cast(value_numeric as double) as close_value,
                  coalesce(source_version, '') as source_version,
                  coalesce(vendor_version, '') as vendor_version,
                  'ok' as quality_flag,
                  1 as source_rank
                from {RELATION_CHOICE_MARKET_SNAPSHOT}
                where series_id = ?
                  and value_numeric is not null
                  {date_filter}
                """
            )
            params.append(series_id)
            if as_of_date is not None:
                params.append(as_of_date.isoformat())
        if not queries:
            return []
        return conn.execute(
            f"""
            with unioned as (
              {" union all ".join(queries)}
            ),
            deduped as (
              select
                trade_date,
                close_value,
                source_version,
                vendor_version,
                quality_flag,
                row_number() over (
                  partition by trade_date
                  order by source_rank asc, source_version desc
                ) as rn
              from unioned
            )
            select
              trade_date,
              close_value,
              source_version,
              vendor_version,
              quality_flag
            from deduped
            where rn = 1
            order by trade_date desc
            limit {history_limit}
            """,
            params,
        ).fetchall()

    # ---- cycle input evidence --------------------------------------------

    def fetch_cycle_macro_ranked_rows(
        self,
        *,
        series_ids: list[str],
        as_of_date: str,
        conn: duckdb.DuckDBPyConnection,
    ) -> list[tuple[Any, ...]]:
        placeholders = ", ".join("?" for _ in series_ids)
        return conn.execute(
            f"""
                with ranked as (
                  select
                    series_id,
                    trade_date,
                    value_numeric,
                    coalesce(source_version, '') as source_version,
                    coalesce(vendor_version, '') as vendor_version,
                    coalesce(rule_version, '') as rule_version,
                    coalesce(frequency, '') as frequency,
                    coalesce(unit, '') as unit,
                    coalesce(quality_flag, '') as quality_flag,
                    coalesce(run_id, '') as run_id,
                    row_number() over (
                      partition by series_id
                      order by try_cast(trade_date as date) desc
                    ) as rn
                  from {RELATION_FACT_CHOICE_MACRO_DAILY}
                  where series_id in ({placeholders})
                    and try_cast(trade_date as date) <= cast(? as date)
                    and value_numeric is not null
                )
                select series_id, trade_date, value_numeric, source_version, vendor_version, rule_version, frequency, unit, quality_flag, run_id
                from ranked
                where rn <= 5
                order by series_id, try_cast(trade_date as date)
                """,
            [*series_ids, as_of_date],
        ).fetchall()

    def fetch_turnover_evidence_row(
        self,
        *,
        as_of_date: str,
        conn: duckdb.DuckDBPyConnection,
    ) -> tuple[Any, ...] | None:
        return conn.execute(
            f"""
                select count(*) as row_count, count(distinct stock_code) as stock_count, coalesce(max(source_version), '')
                from {RELATION_CHOICE_STOCK_DAILY_OBSERVATION}
                where cast(trade_date as date) <= cast(? as date)
                  and cast(trade_date as date) >= cast(? as date) - interval 20 day
                  and turn is not null
                """,
            [as_of_date, as_of_date],
        ).fetchone()

    def fetch_latest_observation_trade_date_row(
        self,
        *,
        as_of_date: str,
        conn: duckdb.DuckDBPyConnection,
    ) -> tuple[Any, ...] | None:
        return conn.execute(
            f"""
                select max(cast(trade_date as date))
                from {RELATION_CHOICE_STOCK_DAILY_OBSERVATION}
                where cast(trade_date as date) <= cast(? as date)
                """,
            [as_of_date],
        ).fetchone()

    def fetch_valuation_evidence_row(
        self,
        *,
        as_of_date: str,
        has_source_version: bool,
        conn: duckdb.DuckDBPyConnection,
    ) -> tuple[Any, ...] | None:
        valuation_source_expr = (
            "coalesce(max(source_version), '')" if has_source_version else "''"
        )
        return conn.execute(
            f"""
                select as_of_date, count(*) as row_count, {valuation_source_expr}
                from {RELATION_CHOICE_STOCK_FACTOR_SNAPSHOT}
                where cast(as_of_date as date) <= ?
                  and pe is not null
                  and pb is not null
                group by as_of_date
                order by cast(as_of_date as date) desc
                limit 1
                """,
            [as_of_date],
        ).fetchone()

    # ---- sector rank inputs ----------------------------------------------

    def fetch_sector_rank_input_rows(
        self,
        *,
        as_of_date: str,
        membership_snapshot_date: str,
        universe_snapshot_date: str | None,
        conn: duckdb.DuckDBPyConnection,
    ) -> list[tuple[Any, ...]]:
        stock_name_expr = (
            "coalesce(universe.stock_name, membership.stock_code)"
            if universe_snapshot_date is not None
            else "membership.stock_code"
        )
        universe_join = (
            f"""
            left join {RELATION_CHOICE_STOCK_UNIVERSE} universe
              on universe.stock_code = membership.stock_code
             and universe.as_of_date = ?
            """
            if universe_snapshot_date is not None
            else ""
        )
        params: list[object] = [as_of_date]
        if universe_snapshot_date is not None:
            params.append(universe_snapshot_date)
        params.append(membership_snapshot_date)
        return conn.execute(
            f"""
            select
              membership.stock_code,
              {stock_name_expr} as stock_name,
              membership.sw2021code,
              membership.sw2021,
              daily.pctchange,
              daily.turn,
              daily.amplitude,
              membership.source_version,
              membership.vendor_version,
              daily.source_version,
              daily.vendor_version
            from {RELATION_CHOICE_STOCK_SECTOR_MEMBERSHIP} membership
            join {RELATION_CHOICE_STOCK_DAILY_OBSERVATION} daily
              on daily.stock_code = membership.stock_code
             and cast(daily.trade_date as date) = cast(? as date)
            {universe_join}
            where membership.as_of_date = ?
            """,
            params,
        ).fetchall()

    # ---- stock candidate inputs ------------------------------------------

    def fetch_latest_factor_snapshot_date(
        self,
        *,
        as_of_date: str,
        conn: duckdb.DuckDBPyConnection,
    ) -> tuple[Any, ...] | None:
        return conn.execute(
            f"""
                select max(as_of_date)
                from {RELATION_CHOICE_STOCK_FACTOR_SNAPSHOT}
                where as_of_date <= ?
                """,
            [as_of_date],
        ).fetchone()

    def fetch_stock_candidate_current_rows(
        self,
        *,
        as_of_date: str,
        universe_snapshot_date: str,
        membership_snapshot_date: str,
        limit_snapshot_date: str,
        factor_snapshot_date: str | None,
        has_observation_vendor_version: bool,
        has_observation_amount: bool,
        conn: duckdb.DuckDBPyConnection,
    ) -> list[tuple[Any, ...]]:
        factor_select = (
            """
              f.pe,
              f.pb,
              f.ps,
              f.roe,
              f.gross_margin,
              f.three_month_return,
              f.twelve_month_return,
              f.volatility,
              f.dividend_yield
            """
            if factor_snapshot_date is not None
            else """
              null as pe,
              null as pb,
              null as ps,
              null as roe,
              null as gross_margin,
              null as three_month_return,
              null as twelve_month_return,
              null as volatility,
              null as dividend_yield
            """
        )
        factor_join = (
            f"""
            left join {RELATION_CHOICE_STOCK_FACTOR_SNAPSHOT} f
              on f.stock_code = universe.stock_code
             and f.as_of_date = ?
            """
            if factor_snapshot_date is not None
            else ""
        )
        # amount 两代 vendor 单位口径（契约 docs/data_contracts.md §4.10）经共享
        # helper 归一化为元；vendor_version 为 NULL 时无法定标 fail-closed 输出 NULL。
        # 观察表缺 amount 或 vendor_version 列时同样 fail-closed 输出 NULL，
        # 避免主查询 Binder Error 被上层静默吞掉。
        daily_amount_select = (
            amount_rmb_sql(table_alias="daily", alias="amount")
            if has_observation_vendor_version and has_observation_amount
            else "cast(null as double) as amount"
        )
        daily_vendor_select = (
            "daily.vendor_version" if has_observation_vendor_version else "cast(null as varchar)"
        )
        # 告警计数须与 fail-closed 语义一致:仅统计"amount 非空且 vendor_version 为
        # NULL"(真正无法定标)的行,而非任何 vendor_version 为 NULL 的行。
        daily_amount_scale_unknown_select = (
            scale_unknown_sql("amount", table_alias="daily", alias="_amount_scale_unknown")
            if has_observation_vendor_version and has_observation_amount
            else "false as _amount_scale_unknown"
        )
        params: list[object] = [membership_snapshot_date, as_of_date, limit_snapshot_date]
        if factor_snapshot_date is not None:
            params.append(factor_snapshot_date)
        params.append(universe_snapshot_date)
        return conn.execute(
            f"""
            select
              universe.stock_code,
              universe.stock_name,
              membership.sw2021code,
              membership.sw2021,
              daily.open_value,
              daily.high_value,
              daily.low_value,
              daily.close_value,
              daily.turn,
              daily.highlimit,
              daily.lowlimit,
              limits.issurgedlimit,
              universe.source_version,
              universe.vendor_version,
              membership.source_version,
              membership.vendor_version,
              daily.source_version,
              {daily_vendor_select},
              limits.source_version,
              limits.vendor_version,
              {factor_select},
              {daily_amount_select},
              {daily_amount_scale_unknown_select}
            from {RELATION_CHOICE_STOCK_UNIVERSE} universe
            join {RELATION_CHOICE_STOCK_SECTOR_MEMBERSHIP} membership
              on membership.stock_code = universe.stock_code
             and membership.as_of_date = ?
            join {RELATION_CHOICE_STOCK_DAILY_OBSERVATION} daily
              on daily.stock_code = universe.stock_code
             and cast(daily.trade_date as date) = cast(? as date)
            join {RELATION_CHOICE_STOCK_LIMIT_QUALITY} limits
              on limits.stock_code = universe.stock_code
             and limits.as_of_date = ?
            {factor_join}
            where universe.as_of_date = ?
            """,
            params,
        ).fetchall()

    def fetch_stock_candidate_history_rows(
        self,
        *,
        stock_codes: list[str],
        as_of_date: str,
        history_window: int,
        conn: duckdb.DuckDBPyConnection,
    ) -> list[tuple[Any, ...]]:
        placeholders = ",".join("?" for _ in stock_codes)
        return conn.execute(
            f"""
                with ranked_history as (
                  select
                    stock_code,
                    close_value,
                    turn,
                    trade_date,
                    row_number() over (
                      partition by stock_code
                      order by cast(trade_date as date) desc
                    ) as rn
                  from {RELATION_CHOICE_STOCK_DAILY_OBSERVATION}
                  where stock_code in ({placeholders})
                    and cast(trade_date as date) <= cast(? as date)
                )
                select stock_code, close_value, turn, trade_date
                from ranked_history
                where rn <= ?
                order by stock_code asc, rn desc
                """,
            [*stock_codes, as_of_date, history_window],
        ).fetchall()

    def fetch_dual_stock_history_rows(
        self,
        *,
        stock_codes: list[str],
        want_candidate_flags: list[bool],
        want_trading_flags: list[bool],
        as_of_date: str,
        history_window: int,
        conn: duckdb.DuckDBPyConnection,
    ) -> list[tuple[Any, ...]]:
        params: list[object] = [
            stock_codes,
            want_candidate_flags,
            want_trading_flags,
            as_of_date,
            history_window,
            history_window,
        ]
        return conn.execute(
            f"""
        with targets as (
          select
            unnest(?::varchar[]) as stock_code,
            unnest(?::boolean[]) as want_candidate,
            unnest(?::boolean[]) as want_trading
        ),
        base_history as (
          select
            daily.stock_code,
            daily.close_value,
            daily.turn,
            {amount_rmb_sql(table_alias="daily", alias="amount")},
            {volume_shares_sql(table_alias="daily", alias="volume")},
            targets.want_candidate,
            targets.want_trading,
            cast(daily.trade_date as date) as trade_day,
            {tradable_status_sql_condition('daily.tradestatus')} as is_trading
          from {RELATION_CHOICE_STOCK_DAILY_OBSERVATION} daily
          join targets on targets.stock_code = daily.stock_code
          where cast(daily.trade_date as date) <= cast(? as date)
        ),
        ranked_history as (
          select
            stock_code,
            close_value,
            turn,
            amount,
            volume,
            want_candidate,
            want_trading,
            is_trading,
            row_number() over (
              partition by stock_code
              order by trade_day desc
            ) as candidate_rn,
            count(*) filter (
              where is_trading
            ) over (
              partition by stock_code
              order by trade_day desc
              rows between unbounded preceding and current row
            ) as trading_rn
          from base_history
        ),
        tagged_history as (
          select
            *,
            want_candidate and candidate_rn <= ? as include_candidate,
            want_trading and is_trading and trading_rn <= ? as include_trading
          from ranked_history
        )
        select
          stock_code,
          list(close_value order by candidate_rn desc)
            filter (where include_candidate) as candidate_closes,
          list(turn order by candidate_rn desc)
            filter (where include_candidate) as candidate_turns,
          list(close_value order by trading_rn desc)
            filter (where include_trading) as trading_closes,
          list(amount order by trading_rn desc)
            filter (where include_trading) as trading_amounts,
          list(volume order by trading_rn desc)
            filter (where include_trading) as trading_volumes
        from tagged_history
        where include_candidate or include_trading
        group by stock_code
        """,
            params,
        ).fetchall()

    # ---- trading-stock snapshot inputs ------------------------------------

    def fetch_trading_stock_current_rows(
        self,
        *,
        as_of_date: str,
        universe_snapshot_date: str,
        membership_snapshot_date: str,
        conn: duckdb.DuckDBPyConnection,
    ) -> list[tuple[Any, ...]]:
        return conn.execute(
            f"""
            select
              daily.stock_code,
              coalesce(nullif(trim(universe.stock_name), ''), daily.stock_code) as stock_name,
              coalesce(nullif(trim(membership.sw2021code), ''), '') as sector_code,
              coalesce(nullif(trim(membership.sw2021), ''), '') as sector_name,
              daily.close_value,
              daily.low_value,
              daily.high_value,
              {volume_shares_sql(table_alias="daily", alias="volume")},
              daily.pctchange,
              daily.turn,
              daily.amplitude
            from {RELATION_CHOICE_STOCK_DAILY_OBSERVATION} daily
            left join {RELATION_CHOICE_STOCK_UNIVERSE} universe
              on universe.stock_code = daily.stock_code
             and universe.as_of_date = ?
            left join {RELATION_CHOICE_STOCK_SECTOR_MEMBERSHIP} membership
              on membership.stock_code = daily.stock_code
             and membership.as_of_date = ?
            where cast(daily.trade_date as date) = cast(? as date)
              and {tradable_status_sql_condition('daily.tradestatus')}
            """,
            [universe_snapshot_date, membership_snapshot_date, as_of_date],
        ).fetchall()

    def fetch_trading_stock_history_rows(
        self,
        *,
        stock_codes: list[str],
        as_of_date: str,
        history_window: int,
        conn: duckdb.DuckDBPyConnection,
    ) -> list[tuple[Any, ...]]:
        placeholders = ",".join("?" for _ in stock_codes)
        return conn.execute(
            f"""
                with ranked_history as (
                  select
                    stock_code,
                    close_value,
                    {amount_rmb_sql(alias="amount")},
                    {volume_shares_sql(alias="volume")},
                    row_number() over (
                      partition by stock_code
                      order by cast(trade_date as date) desc
                    ) as rn
                  from {RELATION_CHOICE_STOCK_DAILY_OBSERVATION}
                  where stock_code in ({placeholders})
                    and cast(trade_date as date) <= cast(? as date)
                    and {tradable_status_sql_condition('tradestatus')}
                )
                select stock_code, close_value, amount, volume
                from ranked_history
                where rn <= ?
                order by stock_code asc, rn desc
                """,
            [*stock_codes, as_of_date, history_window],
        ).fetchall()

    def fetch_concept_membership_pairs(
        self,
        *,
        stock_codes: list[str],
        concept_snapshot_date: str,
        conn: duckdb.DuckDBPyConnection,
    ) -> list[tuple[Any, ...]]:
        placeholders = ",".join("?" for _ in stock_codes)
        return conn.execute(
            f"""
                    select stock_code, concept_name
                    from {RELATION_CHOICE_STOCK_CONCEPT_MEMBERSHIP}
                    where stock_code in ({placeholders})
                      and as_of_date = ?
                    order by stock_code asc, concept_name asc
                    """,
            [*stock_codes, concept_snapshot_date],
        ).fetchall()

    def fetch_limit_quality_hlimitedays(
        self,
        *,
        stock_codes: list[str],
        limit_snapshot_date: str,
        conn: duckdb.DuckDBPyConnection,
    ) -> list[tuple[Any, ...]]:
        placeholders = ",".join("?" for _ in stock_codes)
        return conn.execute(
            f"""
                    select stock_code, hlimitedays
                    from {RELATION_CHOICE_STOCK_LIMIT_QUALITY}
                    where stock_code in ({placeholders})
                      and as_of_date = ?
                    """,
            [*stock_codes, limit_snapshot_date],
        ).fetchall()

    # ---- mean-reversion / momentum / watchlist inputs ---------------------

    def fetch_price_volume_current_rows(
        self,
        *,
        as_of_date: str,
        universe_snapshot_date: str,
        membership_snapshot_date: str,
        conn: duckdb.DuckDBPyConnection,
    ) -> list[tuple[Any, ...]]:
        return conn.execute(
            f"""
            select
              daily.stock_code,
              coalesce(nullif(trim(universe.stock_name), ''), daily.stock_code) as stock_name,
              coalesce(nullif(trim(membership.sw2021code), ''), '') as sector_code,
              coalesce(nullif(trim(membership.sw2021), ''), '') as sector_name,
              daily.close_value,
              daily.low_value,
              daily.high_value,
              {volume_shares_sql(table_alias="daily", alias="volume")}
            from {RELATION_CHOICE_STOCK_DAILY_OBSERVATION} daily
            left join {RELATION_CHOICE_STOCK_UNIVERSE} universe
              on universe.stock_code = daily.stock_code
             and universe.as_of_date = ?
            left join {RELATION_CHOICE_STOCK_SECTOR_MEMBERSHIP} membership
              on membership.stock_code = daily.stock_code
             and membership.as_of_date = ?
            where cast(daily.trade_date as date) = cast(? as date)
              and {tradable_status_sql_condition('daily.tradestatus')}
            """,
            [universe_snapshot_date, membership_snapshot_date, as_of_date],
        ).fetchall()

    def fetch_close_volume_history_rows(
        self,
        *,
        stock_codes: list[str],
        as_of_date: str,
        conn: duckdb.DuckDBPyConnection,
    ) -> list[tuple[Any, ...]]:
        placeholders = ",".join("?" for _ in stock_codes)
        return conn.execute(
            f"""
            select stock_code, close_value, {volume_shares_sql(alias="volume")}
            from {RELATION_CHOICE_STOCK_DAILY_OBSERVATION}
            where stock_code in ({placeholders})
              and cast(trade_date as date) <= cast(? as date)
              and {tradable_status_sql_condition('tradestatus')}
            order by stock_code asc, cast(trade_date as date) asc
            """,
            [*stock_codes, as_of_date],
        ).fetchall()

    def fetch_dated_close_history_rows(
        self,
        *,
        stock_codes: list[str],
        start_trade_date: str,
        end_trade_date: str,
        conn: duckdb.DuckDBPyConnection,
    ) -> list[tuple[Any, ...]]:
        """Trade-date-stamped close history for a bounded stock set and date window.

        Unlike ``fetch_close_volume_history_rows`` this keeps ``trade_date`` on each
        row so callers can align several stocks onto one trading-calendar axis and
        detect suspended (missing) sessions instead of silently compacting them.
        """
        if not stock_codes:
            return []
        placeholders = ",".join("?" for _ in stock_codes)
        return conn.execute(
            f"""
            select
              stock_code,
              cast(trade_date as date) as trade_date,
              close_value,
              pctchange,
              source_version,
              vendor_version
            from {RELATION_CHOICE_STOCK_DAILY_OBSERVATION}
            where stock_code in ({placeholders})
              and cast(trade_date as date) >= cast(? as date)
              and cast(trade_date as date) <= cast(? as date)
              and {tradable_status_sql_condition('tradestatus')}
              and close_value is not null
            order by stock_code asc, cast(trade_date as date) asc
            """,
            [*stock_codes, start_trade_date, end_trade_date],
        ).fetchall()

    def fetch_price_flow_current_rows(
        self,
        *,
        as_of_date: str,
        universe_snapshot_date: str,
        membership_snapshot_date: str,
        conn: duckdb.DuckDBPyConnection,
    ) -> list[tuple[Any, ...]]:
        return conn.execute(
            f"""
            select
              daily.stock_code,
              coalesce(nullif(trim(universe.stock_name), ''), daily.stock_code) as stock_name,
              coalesce(nullif(trim(membership.sw2021code), ''), '') as sector_code,
              coalesce(nullif(trim(membership.sw2021), ''), '') as sector_name,
              daily.close_value,
              daily.pctchange,
              daily.turn,
              daily.amplitude
            from {RELATION_CHOICE_STOCK_DAILY_OBSERVATION} daily
            left join {RELATION_CHOICE_STOCK_UNIVERSE} universe
              on universe.stock_code = daily.stock_code
             and universe.as_of_date = ?
            left join {RELATION_CHOICE_STOCK_SECTOR_MEMBERSHIP} membership
              on membership.stock_code = daily.stock_code
             and membership.as_of_date = ?
            where cast(daily.trade_date as date) = cast(? as date)
              and {tradable_status_sql_condition('daily.tradestatus')}
            """,
            [universe_snapshot_date, membership_snapshot_date, as_of_date],
        ).fetchall()

    def fetch_close_amount_history_rows(
        self,
        *,
        stock_codes: list[str],
        as_of_date: str,
        conn: duckdb.DuckDBPyConnection,
    ) -> list[tuple[Any, ...]]:
        placeholders = ",".join("?" for _ in stock_codes)
        return conn.execute(
            f"""
            select stock_code, close_value, {amount_rmb_sql(alias="amount")}
            from {RELATION_CHOICE_STOCK_DAILY_OBSERVATION}
            where stock_code in ({placeholders})
              and cast(trade_date as date) <= cast(? as date)
              and {tradable_status_sql_condition('tradestatus')}
            order by stock_code asc, cast(trade_date as date) asc
            """,
            [*stock_codes, as_of_date],
        ).fetchall()

    # ---- factor screen ----------------------------------------------------

    def fetch_factor_screen_rows(
        self,
        *,
        snapshot_as_of_date: object,
        universe_snapshot_date: str | None,
        sector_snapshot_date: str | None,
        has_universe: bool,
        has_sector: bool,
        has_amount_source: bool,
        conn: duckdb.DuckDBPyConnection,
    ) -> list[tuple[Any, ...]]:
        stock_name_expr = "COALESCE(u.stock_name, f.stock_code)" if has_universe else "f.stock_code"
        universe_join = (
            f"""
            LEFT JOIN (
                SELECT stock_code, stock_name
                FROM {RELATION_CHOICE_STOCK_UNIVERSE}
                WHERE as_of_date = ?
            ) u ON f.stock_code = u.stock_code
            """
            if has_universe
            else ""
        )
        sector_code_expr = "COALESCE(s.sw2021code, '')" if has_sector else "''"
        sector_name_expr = (
            "COALESCE(s.sw2021, f.industry, '')" if has_sector else "COALESCE(f.industry, '')"
        )
        sector_join = (
            f"""
            LEFT JOIN (
                SELECT stock_code, sw2021code, sw2021
                FROM {RELATION_CHOICE_STOCK_SECTOR_MEMBERSHIP}
                WHERE as_of_date = ?
            ) s ON f.stock_code = s.stock_code
            """
            if has_sector
            else ""
        )
        # v3 流动性地板输入：近 20 日均成交额 = 每股截至快照日最近 20 个观测 bar 的
        # 成交额均值(元)。amount 必须经 choice_stock_units.amount_rmb_sql 按 vendor
        # 代际归一化为元(契约 §4.10,严禁 raw amount)：tushare 代际(千元)×1000,
        # choice_native 代际(元)透传；vendor 无法定标的观测日输出 NULL,不计入均值,
        # 全窗口无可定标观测则均值为 NULL。表/列缺失时同样输出 NULL(不猜单位),
        # 由 compute_factor_screen_candidates 按 fail-closed 剔除并计数。
        avg_amount_expr = "liq.avg_amount_20d" if has_amount_source else "CAST(NULL AS DOUBLE)"
        liquidity_join = (
            f"""
            LEFT JOIN (
                SELECT stock_code, AVG(amount_rmb) AS avg_amount_20d
                FROM (
                    SELECT
                        obs.stock_code,
                        {amount_rmb_sql(table_alias="obs", alias="amount_rmb")},
                        row_number() OVER (
                            PARTITION BY obs.stock_code
                            ORDER BY CAST(obs.trade_date AS DATE) DESC
                        ) AS rn
                    FROM {RELATION_CHOICE_STOCK_DAILY_OBSERVATION} obs
                    WHERE CAST(obs.trade_date AS DATE) <= CAST(? AS DATE)
                      AND obs.stock_code IN (
                        SELECT stock_code
                        FROM {RELATION_CHOICE_STOCK_FACTOR_SNAPSHOT}
                        WHERE as_of_date = ?
                      )
                ) ranked
                WHERE rn <= 20
                GROUP BY stock_code
            ) liq ON f.stock_code = liq.stock_code
            """
            if has_amount_source
            else ""
        )
        params: list[object] = []
        if has_universe:
            params.append(universe_snapshot_date)
        if has_sector:
            params.append(sector_snapshot_date)
        if has_amount_source:
            params.extend([snapshot_as_of_date, snapshot_as_of_date])
        params.append(snapshot_as_of_date)

        return conn.execute(
            f"""
            SELECT
                f.stock_code,
                {stock_name_expr} AS stock_name,
                f.pe, f.pb, f.ps, f.roe, f.gross_margin,
                f.three_month_return, f.twelve_month_return,
                f.volatility, f.dividend_yield,
                f.industry,
                {sector_code_expr} AS sector_code,
                {sector_name_expr} AS sector_name,
                {avg_amount_expr} AS avg_amount_20d
            FROM {RELATION_CHOICE_STOCK_FACTOR_SNAPSHOT} f
            {universe_join}
            {sector_join}
            {liquidity_join}
            WHERE f.as_of_date = ?
        """,
            params,
        ).fetchall()

    # ---- theme breakout ---------------------------------------------------

    def fetch_theme_breakout_rows(
        self,
        *,
        as_of_date: str,
        universe_snapshot_date: str,
        membership_snapshot_date: str,
        limit_snapshot_date: str | None,
        has_limit_quality: bool,
        conn: duckdb.DuckDBPyConnection,
    ) -> list[tuple[Any, ...]]:
        limit_select = (
            "coalesce(cast(limits.issurgedlimit as varchar), '') as issurgedlimit, "
            "limits.source_version, limits.vendor_version"
            if has_limit_quality
            else "'' as issurgedlimit, '' as limit_source_version, '' as limit_vendor_version"
        )
        limit_join = (
            f"""
            left join {RELATION_CHOICE_STOCK_LIMIT_QUALITY} limits
              on limits.stock_code = universe.stock_code
             and limits.as_of_date = ?
            """
            if has_limit_quality
            else ""
        )
        params: list[object] = [membership_snapshot_date, as_of_date]
        if has_limit_quality:
            params.append(limit_snapshot_date)
        params.append(universe_snapshot_date)
        return conn.execute(
            f"""
            select
              universe.stock_code,
              universe.stock_name,
              membership.sw2021code,
              membership.sw2021,
              daily.open_value,
              daily.high_value,
              daily.low_value,
              daily.close_value,
              daily.pctchange,
              daily.turn,
              daily.amplitude,
              {limit_select},
              universe.source_version,
              universe.vendor_version,
              membership.source_version,
              membership.vendor_version,
              daily.source_version,
              daily.vendor_version
            from {RELATION_CHOICE_STOCK_UNIVERSE} universe
            join {RELATION_CHOICE_STOCK_SECTOR_MEMBERSHIP} membership
              on membership.stock_code = universe.stock_code
             and membership.as_of_date = ?
            join {RELATION_CHOICE_STOCK_DAILY_OBSERVATION} daily
              on daily.stock_code = universe.stock_code
             and cast(daily.trade_date as date) = cast(? as date)
            {limit_join}
            where universe.as_of_date = ?
            order by universe.stock_code asc
            """,
            params,
        ).fetchall()

    def fetch_theme_concept_rows(
        self,
        *,
        as_of_date: str,
        conn: duckdb.DuckDBPyConnection,
    ) -> list[tuple[Any, ...]]:
        return conn.execute(
            f"""
                select
                  stock_code,
                  concept_code,
                  concept_name,
                  concept_source,
                  source_version,
                  vendor_version
                from {RELATION_CHOICE_STOCK_CONCEPT_MEMBERSHIP}
                where as_of_date = ?
                order by stock_code asc, concept_code asc, concept_name asc
                """,
            [as_of_date],
        ).fetchall()

    def fetch_theme_concept_interval_rows(
        self,
        *,
        as_of_date: str,
        conn: duckdb.DuckDBPyConnection,
    ) -> list[tuple[Any, ...]]:
        """As-of join on the SCD interval read model: valid_from <= date < valid_to.

        Open intervals (valid_to IS NULL) cover every date at or after
        valid_from; dates before a stock's first observed snapshot match no
        rows by construction (fail-closed for historical replay).
        """
        return conn.execute(
            f"""
                select
                  stock_code,
                  concept_code,
                  concept_name,
                  concept_source,
                  source_version,
                  vendor_version
                from {RELATION_CHOICE_STOCK_CONCEPT_MEMBERSHIP_INTERVAL}
                where valid_from <= ?
                  and (valid_to is null or valid_to > ?)
                order by stock_code asc, concept_code asc, concept_name asc
                """,
            [as_of_date, as_of_date],
        ).fetchall()

    def fetch_intraday_movement_rows(
        self,
        *,
        as_of_date: str,
        conn: duckdb.DuckDBPyConnection,
    ) -> list[tuple[Any, ...]]:
        return conn.execute(
            f"""
                select
                  stock_code,
                  concept_code,
                  concept_name,
                  event_time,
                  event_title,
                  source_version,
                  vendor_version
                from {RELATION_CHOICE_STOCK_INTRADAY_MOVEMENT_EVENT}
                where as_of_date = ?
                order by stock_code asc, concept_code asc, event_time asc
                """,
            [as_of_date],
        ).fetchall()

    # ---- risk exit --------------------------------------------------------

    def fetch_active_position_rows(
        self,
        *,
        as_of_date: str,
        conn: duckdb.DuckDBPyConnection,
    ) -> list[tuple[Any, ...]]:
        return conn.execute(
            f"""
            select
              stock_code,
              stock_name,
              entry_cost,
              bars_since_entry,
              source_version,
              vendor_version
            from {RELATION_LIVERMORE_POSITION_SNAPSHOT}
            where as_of_date = ?
              and upper(coalesce(position_status, 'ACTIVE')) = 'ACTIVE'
            order by stock_code asc
            """,
            [as_of_date],
        ).fetchall()

    def fetch_position_close_volume_history_rows(
        self,
        *,
        stock_codes: list[str],
        as_of_date: str,
        conn: duckdb.DuckDBPyConnection,
    ) -> list[tuple[Any, ...]]:
        placeholders = ",".join("?" for _ in stock_codes)
        return conn.execute(
            f"""
            select stock_code, close_value, {volume_shares_sql(alias="volume")}, source_version, vendor_version
            from {RELATION_CHOICE_STOCK_DAILY_OBSERVATION}
            where stock_code in ({placeholders})
              and cast(trade_date as date) <= cast(? as date)
            order by stock_code asc, cast(trade_date as date) asc
            """,
            [*stock_codes, as_of_date],
        ).fetchall()

    def fetch_position_row_counts(
        self,
        *,
        as_of_date: str,
        conn: duckdb.DuckDBPyConnection,
    ) -> tuple[Any, ...] | None:
        return conn.execute(
            f"""
            select
              count(*)::integer,
              sum(case when upper(coalesce(position_status, 'ACTIVE')) = 'ACTIVE' then 1 else 0 end)::integer
            from {RELATION_LIVERMORE_POSITION_SNAPSHOT}
            where as_of_date = ?
            """,
            [as_of_date],
        ).fetchone()

    def fetch_latest_active_position_date_row(
        self,
        *,
        conn: duckdb.DuckDBPyConnection,
    ) -> tuple[Any, ...] | None:
        return conn.execute(
            f"""
                select max(as_of_date)
                from {RELATION_LIVERMORE_POSITION_SNAPSHOT}
                where upper(coalesce(position_status, 'ACTIVE')) = 'ACTIVE'
                """
        ).fetchone()

    def fetch_active_position_close_history_count_row(
        self,
        *,
        as_of_date: str,
        conn: duckdb.DuckDBPyConnection,
    ) -> tuple[Any, ...] | None:
        return conn.execute(
            f"""
            select count(*)::integer
            from {RELATION_CHOICE_STOCK_DAILY_OBSERVATION} daily
            join {RELATION_LIVERMORE_POSITION_SNAPSHOT} position
              on position.stock_code = daily.stock_code
            where position.as_of_date = ?
              and upper(coalesce(position.position_status, 'ACTIVE')) = 'ACTIVE'
              and cast(daily.trade_date as date) <= cast(? as date)
              and daily.close_value is not null
            """,
            [as_of_date, as_of_date],
        ).fetchone()


# Connection-injected read surface: every method above requires an explicit
# ``conn``, so this shared instance intentionally binds no database path.
LIVERMORE_STRATEGY_READS = LivermoreStrategyReadRepository(path="")
