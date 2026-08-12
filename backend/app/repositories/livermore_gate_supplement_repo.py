from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

import duckdb

from backend.app.core_finance.livermore_strategy import MarketGateSupplement
from backend.app.repositories.duckdb_repo import DuckDBRepository, read_only_connection
from backend.app.schema_registry.duckdb_loader import REGISTRY_DIR, parse_registry_sql_text

TABLE_NAME = "fact_livermore_gate_supplement_daily"
RELATION_FACT_MARKET_BREADTH_DAILY = "fact_market_breadth_daily"
RELATION_FACT_CHOICE_MACRO_DAILY = "fact_choice_macro_daily"
RELATION_CHOICE_MARKET_SNAPSHOT = "choice_market_snapshot"

_GATE_SUPPLEMENT_READ_RELATIONS = frozenset(
    {
        TABLE_NAME,
        RELATION_FACT_MARKET_BREADTH_DAILY,
        RELATION_FACT_CHOICE_MACRO_DAILY,
        RELATION_CHOICE_MARKET_SNAPSHOT,
    }
)

BROAD_INDEX_SERIES_ID = "CA.CSI300"
PCT_CHG_SERIES_ID = "CA.CSI300_PCT_CHG"
_BREADTH_WINDOW = 5


def ensure_livermore_gate_supplement_schema(conn: duckdb.DuckDBPyConnection) -> None:
    text = (REGISTRY_DIR / "23_livermore_gate_supplement.sql").read_text(encoding="utf-8")
    for statement in parse_registry_sql_text(text):
        conn.execute(statement)


def fetch_market_gate_supplement(
    *,
    duckdb_path: str,
    trade_date: date,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> MarketGateSupplement | None:
    """Backward-compatible wrapper; prefers an injected connection when provided."""
    if conn is not None:
        return LivermoreGateSupplementRepository(duckdb_path)._fetch_for_trade_date_impl(
            conn, trade_date
        )
    path = Path(duckdb_path)
    if not path.is_file():
        return None
    return LivermoreGateSupplementRepository(str(path)).fetch_for_trade_date(trade_date)


class LivermoreGateSupplementRepository(DuckDBRepository):
    """Read-only Livermore gate-supplement inputs and fact table via shared DuckDB helpers."""

    def fetch_for_trade_date(
        self,
        trade_date: date,
        *,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> MarketGateSupplement | None:
        if conn is not None:
            return self._fetch_for_trade_date_impl(conn, trade_date)
        try:
            with read_only_connection(self.path) as scoped:
                return self._fetch_for_trade_date_impl(scoped, trade_date)
        except (OSError, duckdb.Error):
            return None

    def real_market_breadth_dates(
        self,
        trade_dates: list[str],
        *,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> set[str]:
        """Trade dates among ``trade_dates`` that already have a real row in
        ``fact_market_breadth_daily``. Never raises; empty set on unavailable DB/table.
        """
        if not trade_dates:
            return set()
        if conn is not None:
            return self._real_market_breadth_dates_impl(conn, trade_dates)
        if self.guard_path_exists and not Path(self.path).exists():
            return set()
        try:
            with read_only_connection(self.path) as scoped:
                return self._real_market_breadth_dates_impl(scoped, trade_dates)
        except (OSError, duckdb.Error):
            return set()

    def load_csi300_daily_returns(
        self,
        *,
        end_date: date,
        lookback_days: int,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> list[dict[str, Any]]:
        """Load CSI300 close + pct_chg from landed macro tables."""
        if conn is not None:
            return self._load_csi300_daily_returns_impl(conn, end_date, lookback_days)
        if self.guard_path_exists and not Path(self.path).exists():
            return []
        try:
            with read_only_connection(self.path) as scoped:
                return self._load_csi300_daily_returns_impl(scoped, end_date, lookback_days)
        except (OSError, duckdb.Error):
            return []

    def max_trade_date(
        self,
        *,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> str | None:
        if conn is not None:
            return self._max_trade_date_impl(conn)
        if self.guard_path_exists and not Path(self.path).exists():
            return None
        try:
            with read_only_connection(self.path) as scoped:
                return self._max_trade_date_impl(scoped)
        except (OSError, duckdb.Error):
            return None

    def _fetch_for_trade_date_impl(
        self,
        conn: duckdb.DuckDBPyConnection,
        trade_date: date,
    ) -> MarketGateSupplement | None:
        try:
            row = conn.execute(
                """
                select 1
                from information_schema.tables
                where table_schema = 'main' and table_name = ?
                limit 1
                """,
                [TABLE_NAME],
            ).fetchone()
            if row is None:
                return None
            hit = conn.execute(
                f"""
                select breadth_5d, limit_up_quality_ok
                from {TABLE_NAME}
                where trade_date = ?
                """,
                [trade_date.isoformat()],
            ).fetchone()
        except duckdb.Error:
            return None

        if not hit:
            return None
        b_raw, lim_raw = hit[0], hit[1]
        breadth = float(b_raw) if b_raw is not None else None
        lim_ok: bool | None
        if lim_raw is None:
            lim_ok = None
        else:
            lim_ok = bool(lim_raw)
        return MarketGateSupplement(
            trade_date=trade_date,
            breadth_5d=breadth,
            limit_up_quality_ok=lim_ok,
        )

    def _real_market_breadth_dates_impl(
        self,
        conn: duckdb.DuckDBPyConnection,
        trade_dates: list[str],
    ) -> set[str]:
        try:
            tables = {row[0] for row in conn.execute("show tables").fetchall()}
            if RELATION_FACT_MARKET_BREADTH_DAILY not in tables:
                return set()
            placeholders = ", ".join("?" for _ in trade_dates)
            rows = conn.execute(
                "select distinct cast(trade_date as varchar) "
                f"from {RELATION_FACT_MARKET_BREADTH_DAILY} "
                f"where cast(trade_date as varchar) in ({placeholders})",
                trade_dates,
            ).fetchall()
            return {str(row[0]) for row in rows}
        except duckdb.Error:
            return set()

    def _load_csi300_daily_returns_impl(
        self,
        conn: duckdb.DuckDBPyConnection,
        end_date: date,
        lookback_days: int,
    ) -> list[dict[str, Any]]:
        try:
            tables = {row[0] for row in conn.execute("show tables").fetchall()}
            close_rows = self._query_series_history(
                conn, tables, BROAD_INDEX_SERIES_ID, end_date, lookback_days
            )
            pct_chg_rows = self._query_series_history(
                conn, tables, PCT_CHG_SERIES_ID, end_date, lookback_days
            )
        except duckdb.Error:
            return []

        pct_chg_by_date: dict[str, float] = {}
        for row in pct_chg_rows:
            pct_chg_by_date[row["trade_date"]] = row["value"]

        result: list[dict[str, Any]] = []
        sorted_close = sorted(close_rows, key=lambda r: r["trade_date"])
        for i, row in enumerate(sorted_close):
            td = row["trade_date"]
            pct = pct_chg_by_date.get(td)
            if pct is None and i > 0:
                prev_close = sorted_close[i - 1]["value"]
                if prev_close and prev_close > 0:
                    pct = (row["value"] - prev_close) / prev_close * 100
            result.append(
                {
                    "trade_date": td,
                    "close": row["value"],
                    "pct_chg": pct,
                }
            )
        return result

    def _max_trade_date_impl(self, conn: duckdb.DuckDBPyConnection) -> str | None:
        try:
            exists = conn.execute(
                """
                select 1
                from information_schema.tables
                where table_schema = 'main' and table_name = ?
                limit 1
                """,
                [TABLE_NAME],
            ).fetchone()
            if exists is None:
                return None
            row = conn.execute(f"select max(trade_date) from {TABLE_NAME}").fetchone()
        except duckdb.Error:
            return None
        if not row or row[0] is None:
            return None
        value = row[0]
        return value.isoformat() if hasattr(value, "isoformat") else str(value)[:10]

    def _query_series_history(
        self,
        conn: duckdb.DuckDBPyConnection,
        tables: set[str],
        series_id: str,
        end_date: date,
        lookback_days: int,
    ) -> list[dict[str, Any]]:
        queries: list[str] = []
        params: list[object] = []
        lookback_extra = lookback_days + _BREADTH_WINDOW + 10

        if RELATION_FACT_CHOICE_MACRO_DAILY in tables:
            queries.append(
                f"""
            select
              cast(trade_date as date) as trade_date,
              cast(value_numeric as double) as value_numeric,
              0 as src_rank
            from {RELATION_FACT_CHOICE_MACRO_DAILY}
            where series_id = ?
              and value_numeric is not null
              and cast(trade_date as date) <= ?
              and cast(trade_date as date) >= ?
        """
            )
            params.extend(
                [
                    series_id,
                    end_date.isoformat(),
                    _offset_date(end_date, lookback_extra),
                ]
            )

        if RELATION_CHOICE_MARKET_SNAPSHOT in tables:
            queries.append(
                f"""
            select
              cast(trade_date as date) as trade_date,
              cast(value_numeric as double) as value_numeric,
              1 as src_rank
            from {RELATION_CHOICE_MARKET_SNAPSHOT}
            where series_id = ?
              and value_numeric is not null
              and cast(trade_date as date) <= ?
              and cast(trade_date as date) >= ?
        """
            )
            params.extend(
                [
                    series_id,
                    end_date.isoformat(),
                    _offset_date(end_date, lookback_extra),
                ]
            )

        if not queries:
            return []

        sql = f"""
        with unioned as (
          {" union all ".join(queries)}
        ),
        deduped as (
          select
            trade_date,
            value_numeric,
            row_number() over (
              partition by trade_date
              order by src_rank asc
            ) as rn
          from unioned
        )
        select trade_date, value_numeric
        from deduped
        where rn = 1
        order by trade_date asc
    """
        rows = conn.execute(sql, params).fetchall()
        return [
            {"trade_date": str(row[0]), "value": float(row[1])}
            for row in rows
            if row[0] is not None and row[1] is not None
        ]


def _offset_date(d: date, days: int) -> str:
    return (d - timedelta(days=days)).isoformat()
