from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from typing import Any

import duckdb
from backend.app.core_finance.field_normalization import tradable_status_sql_condition
from backend.app.repositories.choice_stock_units import (
    amount_rmb_sql,
    scale_unknown_sql,
    volume_shares_sql,
)
from backend.app.repositories.duckdb_repo import DuckDBRepository, read_only_connection

logger = logging.getLogger(__name__)

RELATION_CHOICE_MARKET_SNAPSHOT = "choice_market_snapshot"
RELATION_FACT_CHOICE_MACRO_DAILY = "fact_choice_macro_daily"
RELATION_PHASE1_MACRO_VENDOR_CATALOG = "phase1_macro_vendor_catalog"
RELATION_CHOICE_STOCK_DAILY_OBSERVATION = "choice_stock_daily_observation"
RELATION_CHOICE_STOCK_FACTOR_SNAPSHOT = "choice_stock_factor_snapshot"
RELATION_CHOICE_STOCK_SECTOR_MEMBERSHIP = "choice_stock_sector_membership"
RELATION_CHOICE_NEWS_EVENT = "choice_news_event"
RELATION_VW_EXTERNAL_MACRO_DAILY = "vw_external_macro_daily"

_MARKET_READ_RELATIONS = frozenset(
    {
        RELATION_CHOICE_MARKET_SNAPSHOT,
        RELATION_FACT_CHOICE_MACRO_DAILY,
        RELATION_PHASE1_MACRO_VENDOR_CATALOG,
        RELATION_CHOICE_STOCK_DAILY_OBSERVATION,
        RELATION_CHOICE_STOCK_FACTOR_SNAPSHOT,
        RELATION_CHOICE_STOCK_SECTOR_MEMBERSHIP,
        RELATION_CHOICE_NEWS_EVENT,
        RELATION_VW_EXTERNAL_MACRO_DAILY,
    }
)

_DEXTER_SERIES_COLUMNS_BY_RELATION = {
    RELATION_FACT_CHOICE_MACRO_DAILY: frozenset(
        {
            "series_id",
            "series_name",
            "trade_date",
            "value_numeric",
            "frequency",
            "unit",
            "source_version",
            "vendor_version",
            "rule_version",
            "quality_flag",
            "run_id",
        }
    ),
    RELATION_CHOICE_MARKET_SNAPSHOT: frozenset(
        {
            "series_id",
            "series_name",
            "trade_date",
            "value_numeric",
            "frequency",
            "unit",
            "source_version",
            "vendor_version",
            "rule_version",
            "run_id",
        }
    ),
    RELATION_VW_EXTERNAL_MACRO_DAILY: frozenset(
        {
            "series_id",
            "vendor_name",
            "domain",
            "trade_date",
            "value_numeric",
            "frequency",
            "unit",
            "source_version",
            "vendor_version",
            "rule_version",
            "ingest_batch_id",
            "raw_zone_path",
        }
    ),
}

CHOICE_NEWS_EVENTS_SQL = """
            select event_key, received_at, group_id, content_type, serial_id, request_id, error_code,
                   error_msg, topic_code, item_index, payload_text, payload_json
            from choice_news_event
            where coalesce(error_code, 0) = 0
            order by received_at desc, topic_code asc, item_index asc
            limit ?
            """


@dataclass(frozen=True)
class StockKlineReadResult:
    end_trade_date: date | None
    rows: list[dict[str, Any]]
    unit_warnings: list[str]
    source_unavailable: bool = False


class MarketReadRepository(DuckDBRepository):
    """Read-only market peripheral inputs behind a relation-name whitelist."""

    @contextmanager
    def _connection(
        self,
        conn: duckdb.DuckDBPyConnection | None,
    ) -> Iterator[duckdb.DuckDBPyConnection]:
        if conn is not None:
            yield conn
            return
        with read_only_connection(self.path) as scoped:
            yield scoped

    def available_relations(
        self,
        *,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> set[str]:
        with self._connection(conn) as scoped:
            return {
                str(row[0]) for row in scoped.execute("show tables").fetchall() if str(row[0]) in _MARKET_READ_RELATIONS
            }

    def relation_exists(
        self,
        relation_name: str,
        *,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> bool:
        if relation_name not in _MARKET_READ_RELATIONS:
            return False
        with self._connection(conn) as scoped:
            row = scoped.execute(
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

    def table_columns(
        self,
        relation_name: str,
        *,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> set[str]:
        if relation_name not in _MARKET_READ_RELATIONS:
            return set()
        with self._connection(conn) as scoped:
            return {str(row[1]).lower() for row in scoped.execute(f"pragma table_info('{relation_name}')").fetchall()}

    def fetch_ncd_proxy_rows(
        self,
        *,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> list[dict[str, object]]:
        with self._connection(conn) as scoped:
            rows: list[dict[str, object]] = []
            if self.relation_exists(RELATION_CHOICE_MARKET_SNAPSHOT, conn=scoped):
                rows.extend(
                    self._fetch_dict_rows(
                        scoped,
                        """
                        select
                          series_id,
                          series_name,
                          vendor_name,
                          cast(trade_date as timestamp) as trade_date,
                          cast(value_numeric as double) as value_numeric,
                          source_version,
                          vendor_version
                        from choice_market_snapshot
                        where value_numeric is not null
                          and (
                            lower(series_id) like '%shibor%'
                            or lower(series_name) like '%shibor%'
                          )
                        """,
                    )
                )
            if self.relation_exists(RELATION_FACT_CHOICE_MACRO_DAILY, conn=scoped):
                if self.relation_exists(RELATION_PHASE1_MACRO_VENDOR_CATALOG, conn=scoped):
                    fact_sql = """
                        select
                          f.series_id,
                          f.series_name,
                          c.vendor_name,
                          cast(f.trade_date as timestamp) as trade_date,
                          cast(f.value_numeric as double) as value_numeric,
                          f.source_version,
                          f.vendor_version
                        from fact_choice_macro_daily f
                        left join phase1_macro_vendor_catalog c on c.series_id = f.series_id
                        where f.value_numeric is not null
                          and (
                            lower(f.series_id) like '%shibor%'
                            or lower(f.series_name) like '%shibor%'
                          )
                    """
                else:
                    fact_sql = """
                        select
                          series_id,
                          series_name,
                          cast(null as varchar) as vendor_name,
                          cast(trade_date as timestamp) as trade_date,
                          cast(value_numeric as double) as value_numeric,
                          source_version,
                          vendor_version
                        from fact_choice_macro_daily
                        where value_numeric is not null
                          and (
                            lower(series_id) like '%shibor%'
                            or lower(series_name) like '%shibor%'
                          )
                    """
                rows.extend(self._fetch_dict_rows(scoped, fact_sql))
            return rows

    def ncd_proxy_tables_used(
        self,
        *,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> list[str]:
        with self._connection(conn) as scoped:
            available = {
                str(row[0])
                for row in scoped.execute(
                    """
                    select table_name
                    from information_schema.tables
                    where table_name in (
                      'choice_market_snapshot',
                      'fact_choice_macro_daily',
                      'phase1_macro_vendor_catalog'
                    )
                    """
                ).fetchall()
            }

        tables_used: list[str] = []
        if RELATION_CHOICE_MARKET_SNAPSHOT in available:
            tables_used.append(RELATION_CHOICE_MARKET_SNAPSHOT)
        if RELATION_FACT_CHOICE_MACRO_DAILY in available:
            tables_used.append(RELATION_FACT_CHOICE_MACRO_DAILY)
            if RELATION_PHASE1_MACRO_VENDOR_CATALOG in available:
                tables_used.append(RELATION_PHASE1_MACRO_VENDOR_CATALOG)
        return sorted(tables_used)

    def load_stock_kline(
        self,
        *,
        stock_code: str,
        as_of_date: date | None,
        lookback: int,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> StockKlineReadResult:
        try:
            with self._connection(conn) as scoped:
                end_trade_date = self._resolve_stock_kline_end_trade_date(
                    scoped,
                    stock_code=stock_code,
                    as_of_date=as_of_date,
                )
                if end_trade_date is None:
                    return StockKlineReadResult(None, [], [])
                rows, unit_warnings = self._fetch_stock_kline_candles(
                    scoped,
                    stock_code=stock_code,
                    end_trade_date=end_trade_date,
                    lookback=lookback,
                )
                return StockKlineReadResult(end_trade_date, rows, unit_warnings)
        except (OSError, duckdb.Error):
            return StockKlineReadResult(None, [], [], source_unavailable=True)

    def fetch_choice_news_events(
        self,
        *,
        limit: int,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> list[dict[str, Any]]:
        with self._connection(conn) as scoped:
            if RELATION_CHOICE_NEWS_EVENT not in self.available_relations(conn=scoped):
                return []
            rows = scoped.execute(CHOICE_NEWS_EVENTS_SQL, [limit]).fetchall()

        return [
            {
                "event_key": str(event_key),
                "received_at": str(received_at),
                "group_id": str(group_id),
                "content_type": str(content_type),
                "serial_id": int(serial_id),
                "request_id": int(request_id),
                "error_code": int(error_code),
                "error_msg": str(error_msg),
                "topic_code": str(topic_code),
                "item_index": int(item_index),
                "payload_text": payload_text,
                "payload_json": payload_json,
            }
            for event_key, received_at, group_id, content_type, serial_id, request_id, error_code, error_msg, topic_code, item_index, payload_text, payload_json in rows
        ]

    def fetch_dexter_stock_daily(
        self,
        *,
        stock_code: str,
        as_of_date: str,
        sql_executed: list[str],
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> tuple[dict[str, Any] | None, bool]:
        with self._connection(conn) as scoped:
            daily_columns = self.table_columns(
                RELATION_CHOICE_STOCK_DAILY_OBSERVATION,
                conn=scoped,
            )
            has_vendor_version = "vendor_version" in daily_columns
            if has_vendor_version:
                volume_projection = volume_shares_sql(alias="volume")
                amount_projection = amount_rmb_sql(alias="amount")
                vendor_projection = "vendor_version"
                volume_unknown_projection = scale_unknown_sql(
                    "volume",
                    alias="_volume_scale_unknown",
                )
                amount_unknown_projection = scale_unknown_sql(
                    "amount",
                    alias="_amount_scale_unknown",
                )
                volume_unit_projection = "'shares' as volume_unit"
                amount_unit_projection = "'CNY' as amount_unit"
            else:
                volume_projection = "cast(null as double) as volume"
                amount_projection = "cast(null as double) as amount"
                vendor_projection = "cast(null as varchar) as vendor_version"
                volume_unknown_projection = "false as _volume_scale_unknown"
                amount_unknown_projection = "false as _amount_scale_unknown"
                volume_unit_projection = "'unknown' as volume_unit"
                amount_unit_projection = "'unknown' as amount_unit"

            row = self._fetch_one(
                scoped,
                f"""
                select trade_date, stock_code, open_value, high_value, low_value, close_value,
                       {volume_projection}, {amount_projection}, pctchange, turn, amplitude, tradestatus,
                       highlimit, lowlimit, source_version, {vendor_projection}, rule_version, run_id,
                       {volume_unit_projection}, {amount_unit_projection},
                       {volume_unknown_projection}, {amount_unknown_projection}
                from choice_stock_daily_observation
                where stock_code = ?
                  and (? = '' or trade_date <= ?)
                order by trade_date desc
                limit 1
                """,
                [stock_code, as_of_date, as_of_date],
                sql_executed=sql_executed,
            )
            return row, has_vendor_version

    def fetch_dexter_stock_factor(
        self,
        *,
        stock_code: str,
        as_of_date: str,
        sql_executed: list[str],
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> dict[str, Any] | None:
        with self._connection(conn) as scoped:
            return self._fetch_one(
                scoped,
                """
                select as_of_date, stock_code, pe, pb, ps, roe, gross_margin,
                       three_month_return, twelve_month_return, volatility, dividend_yield,
                       industry, source_version, vendor_version, rule_version, run_id
                from choice_stock_factor_snapshot
                where stock_code = ?
                  and (? = '' or as_of_date <= ?)
                order by as_of_date desc
                limit 1
                """,
                [stock_code, as_of_date, as_of_date],
                sql_executed=sql_executed,
            )

    def fetch_dexter_stock_sector(
        self,
        *,
        stock_code: str,
        as_of_date: str,
        sql_executed: list[str],
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> dict[str, Any] | None:
        with self._connection(conn) as scoped:
            return self._fetch_one(
                scoped,
                """
                select as_of_date, stock_code, sw2021, sw2021code, field_key,
                       source_version, vendor_version, rule_version, run_id
                from choice_stock_sector_membership
                where stock_code = ?
                  and (? = '' or as_of_date <= ?)
                order by as_of_date desc
                limit 1
                """,
                [stock_code, as_of_date, as_of_date],
                sql_executed=sql_executed,
            )

    def fetch_dexter_stock_news(
        self,
        *,
        stock_code: str,
        as_of_date: str,
        sql_executed: list[str],
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> list[dict[str, Any]]:
        # as_of 截止对齐同链路 daily/factor/sector 的 <= as_of_date 口径，避免历史锚定
        # 请求注入未来新闻（前视偏差）。received_at 是 varchar 时间戳，按日期前缀截断
        # 比较（与 choice_news_repo 的未来行排除口径一致），无法解析的 received_at 在
        # 锚定时 fail-closed 排除。
        with self._connection(conn) as scoped:
            return self._fetch_all(
                scoped,
                """
                select event_key, received_at, group_id, content_type, topic_code,
                       item_index, payload_text, payload_json, error_code, error_msg
                from choice_news_event
                where coalesce(error_code, 0) = 0
                  and (topic_code = ? or payload_text ilike ?)
                  and (? = '' or try_cast(substr(cast(received_at as varchar), 1, 10) as date) <= try_cast(? as date))
                order by received_at desc, item_index asc
                limit 5
                """,
                [stock_code, f"%{stock_code}%", as_of_date, as_of_date],
                sql_executed=sql_executed,
            )

    def fetch_dexter_choice_macro_series(
        self,
        *,
        series_ids: list[str],
        as_of_date: str,
        sql_executed: list[str],
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> list[dict[str, Any]]:
        return self._fetch_dexter_latest_rows_by_series(
            relation_name=RELATION_FACT_CHOICE_MACRO_DAILY,
            select_columns=(
                "series_id",
                "series_name",
                "trade_date",
                "value_numeric",
                "frequency",
                "unit",
                "source_version",
                "vendor_version",
                "rule_version",
                "quality_flag",
                "run_id",
            ),
            series_ids=series_ids,
            as_of_date=as_of_date,
            sql_executed=sql_executed,
            conn=conn,
        )

    def fetch_dexter_choice_market_snapshots(
        self,
        *,
        series_ids: list[str],
        as_of_date: str,
        sql_executed: list[str],
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> list[dict[str, Any]]:
        return self._fetch_dexter_latest_rows_by_series(
            relation_name=RELATION_CHOICE_MARKET_SNAPSHOT,
            select_columns=(
                "series_id",
                "series_name",
                "trade_date",
                "value_numeric",
                "frequency",
                "unit",
                "source_version",
                "vendor_version",
                "rule_version",
                "run_id",
            ),
            series_ids=series_ids,
            as_of_date=as_of_date,
            sql_executed=sql_executed,
            conn=conn,
        )

    def fetch_dexter_external_macro_series(
        self,
        *,
        series_ids: list[str],
        as_of_date: str,
        sql_executed: list[str],
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> list[dict[str, Any]]:
        return self._fetch_dexter_latest_rows_by_series(
            relation_name=RELATION_VW_EXTERNAL_MACRO_DAILY,
            select_columns=(
                "series_id",
                "vendor_name",
                "domain",
                "trade_date",
                "value_numeric",
                "frequency",
                "unit",
                "source_version",
                "vendor_version",
                "rule_version",
                "ingest_batch_id",
                "raw_zone_path",
            ),
            series_ids=series_ids,
            as_of_date=as_of_date,
            sql_executed=sql_executed,
            conn=conn,
        )

    def fetch_dexter_macro_catalog(
        self,
        *,
        series_ids: list[str],
        sql_executed: list[str],
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> list[dict[str, Any]]:
        where_sql, params = _series_filter_sql(series_ids)
        with self._connection(conn) as scoped:
            return self._fetch_all(
                scoped,
                f"""
                select series_id, series_name, vendor_name, vendor_version, frequency, unit,
                       vendor_series_code, catalog_version, theme, is_core, refresh_tier,
                       fetch_mode, fetch_granularity, policy_note
                from phase1_macro_vendor_catalog
                {where_sql}
                order by series_id
                limit 20
                """,
                params,
                sql_executed=sql_executed,
            )

    def _fetch_dexter_latest_rows_by_series(
        self,
        *,
        relation_name: str,
        select_columns: tuple[str, ...],
        series_ids: list[str],
        as_of_date: str,
        sql_executed: list[str],
        conn: duckdb.DuckDBPyConnection | None,
    ) -> list[dict[str, Any]]:
        allowed_columns = _DEXTER_SERIES_COLUMNS_BY_RELATION.get(relation_name)
        if allowed_columns is None or any(column not in allowed_columns for column in select_columns):
            return []
        where_sql, params = _series_filter_sql(series_ids, as_of_date=as_of_date)
        columns = ", ".join(select_columns)
        with self._connection(conn) as scoped:
            return self._fetch_all(
                scoped,
                f"""
                select {columns}
                from (
                  select {columns},
                         row_number() over (partition by series_id order by trade_date desc) as rn
                  from {relation_name}
                  {where_sql}
                )
                where rn = 1
                order by series_id
                limit 20
                """,
                params,
                sql_executed=sql_executed,
            )

    @staticmethod
    def _fetch_dict_rows(
        conn: duckdb.DuckDBPyConnection,
        sql: str,
    ) -> list[dict[str, object]]:
        try:
            cursor = conn.execute(sql)
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        except duckdb.Error:
            return []

    @staticmethod
    def _resolve_stock_kline_end_trade_date(
        conn: duckdb.DuckDBPyConnection,
        *,
        stock_code: str,
        as_of_date: date | None,
    ) -> date | None:
        # close_value 非空：native 空串状态视为可交易后，供应商预填的
        # 全空占位行不得把 K 线锚定日拖向未来。
        if as_of_date is None:
            row = conn.execute(
                f"""
                select max(trade_date) as mx
                from {RELATION_CHOICE_STOCK_DAILY_OBSERVATION}
                where stock_code = ?
                  and close_value is not null
                  and {tradable_status_sql_condition('tradestatus')}
                """,
                [stock_code],
            ).fetchone()
        else:
            row = conn.execute(
                f"""
                select max(trade_date) as mx
                from {RELATION_CHOICE_STOCK_DAILY_OBSERVATION}
                where stock_code = ?
                  and trade_date <= ?
                  and close_value is not null
                  and {tradable_status_sql_condition('tradestatus')}
                """,
                [stock_code, as_of_date.isoformat()],
            ).fetchone()
        if row is None or row[0] is None:
            return None
        try:
            return date.fromisoformat(str(row[0]).strip()[:10])
        except ValueError:
            return None

    @staticmethod
    def _fetch_stock_kline_candles(
        conn: duckdb.DuckDBPyConnection,
        *,
        stock_code: str,
        end_trade_date: date,
        lookback: int,
    ) -> tuple[list[dict[str, Any]], list[str]]:
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
                  pctchange,
                  turn,
                  amplitude,
                  source_version,
                  {vendor_projection},
                  {volume_unknown_projection},
                  {amount_unknown_projection}
                from {RELATION_CHOICE_STOCK_DAILY_OBSERVATION}
                where stock_code = ?
                  and trade_date <= ?
                  and close_value is not null
                  and {tradable_status_sql_condition('tradestatus')}
                order by trade_date desc
                limit ?
                """,
                [stock_code, end_trade_date.isoformat(), lookback],
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
                "%s missing vendor_version; stock k-line amount/volume cannot be scaled, output as NULL (fail-closed)",
                RELATION_CHOICE_STOCK_DAILY_OBSERVATION,
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
                "%s has %d k-line rows with volume but null vendor_version; normalized volume is null",
                RELATION_CHOICE_STOCK_DAILY_OBSERVATION,
                volume_unknown_count,
            )
            warnings.append("volume_unit_scale_unknown")
        if amount_unknown_count:
            logger.warning(
                "%s has %d k-line rows with amount but null vendor_version; normalized amount is null",
                RELATION_CHOICE_STOCK_DAILY_OBSERVATION,
                amount_unknown_count,
            )
            warnings.append("amount_unit_scale_unknown")
        return rows, warnings

    @staticmethod
    def _fetch_one(
        conn: duckdb.DuckDBPyConnection,
        sql: str,
        params: list[Any],
        *,
        sql_executed: list[str] | None = None,
    ) -> dict[str, Any] | None:
        _record_sql_disclosure(sql, sql_executed)
        cursor = conn.execute(sql, params)
        row = cursor.fetchone()
        if row is None:
            return None
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row, strict=False))

    @staticmethod
    def _fetch_all(
        conn: duckdb.DuckDBPyConnection,
        sql: str,
        params: list[Any],
        *,
        sql_executed: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        _record_sql_disclosure(sql, sql_executed)
        cursor = conn.execute(sql, params)
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]


def _series_filter_sql(series_ids: list[str], *, as_of_date: str = "") -> tuple[str, list[Any]]:
    conditions: list[str] = []
    params: list[Any] = []
    if not series_ids:
        placeholders = ""
    else:
        placeholders = ", ".join(["?"] * len(series_ids))
        conditions.append(f"series_id in ({placeholders})")
        params.extend(series_ids)
    if as_of_date:
        conditions.append("trade_date <= ?")
        params.append(as_of_date)
    if not conditions:
        return "", []
    return f"where {' and '.join(conditions)}", params


def _record_sql_disclosure(sql: str, target: list[str] | None) -> None:
    if target is None:
        return
    statement = " ".join(str(sql or "").split())
    if statement.lower().startswith(("select", "with")):
        target.append(statement)
