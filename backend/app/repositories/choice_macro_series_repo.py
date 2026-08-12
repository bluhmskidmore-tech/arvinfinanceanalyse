from __future__ import annotations

from decimal import Decimal

import duckdb

from backend.app.repositories.duckdb_repo import DuckDBRepository, read_only_connection

RELATION_FACT_CHOICE_MACRO_DAILY = "fact_choice_macro_daily"
RELATION_CHOICE_MARKET_SNAPSHOT = "choice_market_snapshot"
RELATION_PHASE1_MACRO_VENDOR_CATALOG = "phase1_macro_vendor_catalog"

_CHOICE_MACRO_READ_RELATIONS = (
    RELATION_FACT_CHOICE_MACRO_DAILY,
    RELATION_CHOICE_MARKET_SNAPSHOT,
)

DR007_SERIES_ID = "CA.DR007"

_CHOICE_CREDIT_3Y_SERIES = {
    "EMM00166657": "AAA",
    "EMM00166681": "AA",
}

_ALIAS_BY_RELATION = {
    RELATION_FACT_CHOICE_MACRO_DAILY: "fact",
    RELATION_CHOICE_MARKET_SNAPSHOT: "snap",
}


class ChoiceMacroSeriesRepository(DuckDBRepository):
    """Read-only Choice macro series (DR007, credit 3Y yields) via shared DuckDB helpers."""

    def dr007_on_or_before(
        self,
        trade_date: str,
        *,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> tuple[float | None, str | None]:
        if conn is not None:
            return self._dr007_on_or_before_impl(conn, trade_date)
        try:
            with read_only_connection(self.path) as scoped:
                return self._dr007_on_or_before_impl(scoped, trade_date)
        except (OSError, duckdb.Error):
            return None, None

    def dr007_on_or_before_many(
        self,
        trade_dates: list[str],
        *,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> dict[str, tuple[float | None, str | None]]:
        requested = [str(trade_date) for trade_date in dict.fromkeys(trade_dates) if str(trade_date or "")]
        if not requested:
            return {}
        out = {trade_date: (None, None) for trade_date in requested}
        if conn is not None:
            return self._dr007_on_or_before_many_impl(conn, requested, out)
        try:
            with read_only_connection(self.path) as scoped:
                return self._dr007_on_or_before_many_impl(scoped, requested, out)
        except (OSError, duckdb.Error):
            return out

    def credit_3y_yields_on_or_before(
        self,
        trade_date: str,
        *,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> dict[str, Decimal]:
        if conn is not None:
            return self._credit_3y_yields_on_or_before_impl(conn, trade_date)
        try:
            with read_only_connection(self.path) as scoped:
                return self._credit_3y_yields_on_or_before_impl(scoped, trade_date)
        except (OSError, duckdb.Error):
            return {}

    def _dr007_on_or_before_impl(
        self,
        conn: duckdb.DuckDBPyConnection,
        trade_date: str,
    ) -> tuple[float | None, str | None]:
        for relation_name in _CHOICE_MACRO_READ_RELATIONS:
            value, resolved_date = self._choice_macro_value_on_or_before(
                conn=conn,
                relation_name=relation_name,
                series_id=DR007_SERIES_ID,
                trade_date=trade_date,
            )
            if value is not None:
                return value, resolved_date
        return None, None

    def _dr007_on_or_before_many_impl(
        self,
        conn: duckdb.DuckDBPyConnection,
        requested: list[str],
        out: dict[str, tuple[float | None, str | None]],
    ) -> dict[str, tuple[float | None, str | None]]:
        for relation_name in _CHOICE_MACRO_READ_RELATIONS:
            values = self._choice_macro_values_on_or_before_many(
                conn=conn,
                relation_name=relation_name,
                series_id=DR007_SERIES_ID,
                trade_dates=[trade_date for trade_date, value in out.items() if value[0] is None],
            )
            for trade_date, value in values.items():
                if value[0] is not None:
                    out[trade_date] = value
        return out

    def _credit_3y_yields_on_or_before_impl(
        self,
        conn: duckdb.DuckDBPyConnection,
        trade_date: str,
    ) -> dict[str, Decimal]:
        rows: list[tuple[object, object, object]] = []
        has_catalog = self._macro_relation_exists(conn, RELATION_PHASE1_MACRO_VENDOR_CATALOG)
        if self._macro_relation_exists(conn, RELATION_FACT_CHOICE_MACRO_DAILY):
            rows.extend(
                self._choice_rows_for_relation(
                    conn,
                    RELATION_FACT_CHOICE_MACRO_DAILY,
                    _ALIAS_BY_RELATION[RELATION_FACT_CHOICE_MACRO_DAILY],
                    trade_date,
                    has_catalog,
                )
            )
        if self._macro_relation_exists(conn, RELATION_CHOICE_MARKET_SNAPSHOT):
            rows.extend(
                self._choice_rows_for_relation(
                    conn,
                    RELATION_CHOICE_MARKET_SNAPSHOT,
                    _ALIAS_BY_RELATION[RELATION_CHOICE_MARKET_SNAPSHOT],
                    trade_date,
                    has_catalog,
                )
            )

        out: dict[str, Decimal] = {}
        for series_id, series_name, value in rows:
            rating = self._choice_credit_rating_for_3y(series_id, series_name)
            if rating is not None:
                out[rating] = Decimal(str(value))
        return out

    @staticmethod
    def _macro_table_exists(conn: duckdb.DuckDBPyConnection, relation_name: str) -> bool:
        if relation_name not in _CHOICE_MACRO_READ_RELATIONS:
            return False
        try:
            row = conn.execute(
                """
                select count(*)
                from information_schema.tables
                where table_name = ?
                """,
                [relation_name],
            ).fetchone()
        except duckdb.Error:
            return False
        return bool(row and row[0])

    @staticmethod
    def _macro_relation_exists(conn: duckdb.DuckDBPyConnection, relation_name: str) -> bool:
        allowed = {
            RELATION_FACT_CHOICE_MACRO_DAILY,
            RELATION_CHOICE_MARKET_SNAPSHOT,
            RELATION_PHASE1_MACRO_VENDOR_CATALOG,
        }
        if relation_name not in allowed:
            return False
        row = conn.execute(
            """
            select 1
            from information_schema.tables
            where table_name = ?
            union all
            select 1
            from information_schema.views
            where table_name = ?
            limit 1
            """,
            [relation_name, relation_name],
        ).fetchone()
        return row is not None

    @staticmethod
    def _choice_macro_value_on_or_before(
        *,
        conn: duckdb.DuckDBPyConnection,
        relation_name: str,
        series_id: str,
        trade_date: str,
    ) -> tuple[float | None, str | None]:
        if relation_name not in _CHOICE_MACRO_READ_RELATIONS:
            return None, None
        if not ChoiceMacroSeriesRepository._macro_table_exists(conn, relation_name):
            return None, None
        try:
            row = conn.execute(
                f"""
                select value_numeric, cast(trade_date as varchar)
                from {relation_name}
                where series_id = ?
                  and cast(trade_date as varchar) <= ?
                  and value_numeric is not null
                order by cast(trade_date as varchar) desc
                limit 1
                """,
                [series_id, trade_date],
            ).fetchone()
        except duckdb.Error:
            return None, None
        if row is None:
            return None, None
        return float(row[0]), str(row[1])

    @staticmethod
    def _choice_macro_values_on_or_before_many(
        *,
        conn: duckdb.DuckDBPyConnection,
        relation_name: str,
        series_id: str,
        trade_dates: list[str],
    ) -> dict[str, tuple[float | None, str | None]]:
        requested = [str(trade_date) for trade_date in dict.fromkeys(trade_dates) if str(trade_date or "")]
        if not requested or not ChoiceMacroSeriesRepository._macro_table_exists(conn, relation_name):
            return {}
        requested_sql = " union all ".join("select ? as requested_trade_date" for _ in requested)
        try:
            rows = conn.execute(
                f"""
                with requested as (
                  {requested_sql}
                ), ranked as (
                  select
                    r.requested_trade_date,
                    m.value_numeric,
                    cast(m.trade_date as varchar) as resolved_trade_date,
                    row_number() over (
                      partition by r.requested_trade_date
                      order by cast(m.trade_date as varchar) desc
                    ) as row_num
                  from requested r
                  left join {relation_name} m
                    on m.series_id = ?
                   and cast(m.trade_date as varchar) <= r.requested_trade_date
                   and m.value_numeric is not null
                )
                select requested_trade_date, value_numeric, resolved_trade_date
                from ranked
                where row_num = 1
                """,
                [*requested, series_id],
            ).fetchall()
        except duckdb.Error:
            return {}
        return {
            str(requested_trade_date): (
                float(value) if value is not None else None,
                str(resolved_date) if resolved_date not in (None, "") else None,
            )
            for requested_trade_date, value, resolved_date in rows
        }

    @staticmethod
    def _choice_rows_for_relation(
        conn: duckdb.DuckDBPyConnection,
        relation_name: str,
        alias: str,
        trade_date: str,
        has_catalog: bool,
    ) -> list[tuple[object, object, object]]:
        if relation_name not in _CHOICE_MACRO_READ_RELATIONS:
            return []
        if has_catalog:
            return conn.execute(
                f"""
                select {alias}.series_id, coalesce(nullif(cat.series_name, ''), {alias}.series_name), {alias}.value_numeric
                from {relation_name} as {alias}
                left join {RELATION_PHASE1_MACRO_VENDOR_CATALOG} as cat
                  on cat.series_id = {alias}.series_id
                where {alias}.trade_date = (
                  select max(trade_date)
                  from {relation_name}
                  where trade_date <= ?
                )
                  and {alias}.value_numeric is not null
                """,
                [trade_date],
            ).fetchall()
        return conn.execute(
            f"""
            select series_id, series_name, value_numeric
            from {relation_name}
            where trade_date = (
              select max(trade_date)
              from {relation_name}
              where trade_date <= ?
            )
              and value_numeric is not null
            """,
            [trade_date],
        ).fetchall()

    @staticmethod
    def _choice_credit_rating_for_3y(series_id: object, series_name: object) -> str | None:
        rating = _CHOICE_CREDIT_3Y_SERIES.get(str(series_id or "").strip())
        if rating is not None:
            return rating
        text = str(series_name or "").upper().replace(" ", "")
        if ":3Y" not in text and ":3" not in text:
            return None
        if "(AA+)" in text:
            return "AA+"
        if "(AAA)" in text:
            return "AAA"
        if "(AA)" in text:
            return "AA"
        return None
