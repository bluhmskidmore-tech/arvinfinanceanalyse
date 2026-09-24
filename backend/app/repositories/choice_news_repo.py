"""Read-only DuckDB access for ``choice_news_event`` (Choice news analytical surface)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

import duckdb

from backend.app.repositories.duckdb_repo import DuckDBRepository, read_only_connection

RELATION_CHOICE_NEWS_EVENT = "choice_news_event"

_CHOICE_NEWS_READ_RELATIONS = frozenset({RELATION_CHOICE_NEWS_EVENT})

StockMatchMode = Literal["best_effort", "visible_text"]

_CHOICE_NEWS_DISPLAY_HEADLINE_SQL = (
    "coalesce("
    "nullif(trim(json_extract_string(try_cast(payload_json as json), '$.headline')), ''), "
    "nullif(trim(json_extract_string(try_cast(payload_json as json), '$.title')), ''), "
    "nullif(trim(json_extract_string(try_cast(payload_json as json), '$.news_title')), ''), "
    "nullif(trim(json_extract_string(try_cast(payload_json as json), '$.subject')), '')"
    ") as display_headline"
)
_CHOICE_NEWS_DISPLAY_SUMMARY_SQL = (
    "coalesce("
    "nullif(trim(json_extract_string(try_cast(payload_json as json), '$.summary')), ''), "
    "nullif(trim(json_extract_string(try_cast(payload_json as json), '$.content')), ''), "
    "nullif(trim(json_extract_string(try_cast(payload_json as json), '$.text')), ''), "
    "nullif(trim(json_extract_string(try_cast(payload_json as json), '$.message')), ''), "
    "nullif(trim(json_extract_string(try_cast(payload_json as json), '$.description')), '')"
    ") as display_summary"
)

# 主干事件查询模板：执行与披露共用同一份（`?` 为绑定占位符，最后两个为 limit / offset）。
_CHOICE_NEWS_LATEST_EVENTS_SQL_TEMPLATE = (
    "select event_key, received_at, group_id, content_type, serial_id, request_id, "
    "error_code, error_msg, topic_code, item_index, payload_text, {payload_json_projection}, "
    "{display_headline_projection}, {display_summary_projection} "
    f"from {RELATION_CHOICE_NEWS_EVENT} {{where_clause}} "
    "order by received_at desc, topic_code asc, item_index asc "
    "limit ? offset ?"
)


@dataclass(frozen=True)
class ChoiceNewsLatestRaw:
    rows: list[tuple[object, ...]]
    total_rows: int
    excluded_future_rows: int
    source_unavailable: bool


@dataclass(frozen=True)
class ChoiceNewsBatchRaw:
    events_per_request: list[list[tuple[object, ...]]]
    excluded_future_rows: int
    source_unavailable: bool


def choice_news_latest_events_sql(
    *,
    where_clause: str,
    include_payload_json: bool,
) -> str:
    payload_json_projection = (
        "payload_json" if include_payload_json else "cast(null as varchar) as payload_json"
    )
    return _CHOICE_NEWS_LATEST_EVENTS_SQL_TEMPLATE.format(
        where_clause=where_clause,
        payload_json_projection=payload_json_projection,
        display_headline_projection=_CHOICE_NEWS_DISPLAY_HEADLINE_SQL,
        display_summary_projection=_CHOICE_NEWS_DISPLAY_SUMMARY_SQL,
    )


def choice_news_filters(
    group_id: str | None,
    topic_code: str | None,
    stock_filter_tokens: list[str],
    stock_match_mode: StockMatchMode,
    error_only: bool,
    received_from: str | None,
    received_to: str | None,
) -> tuple[str, list[object]]:
    filters: list[str] = []
    params: list[object] = []
    if group_id is not None:
        filters.append("group_id = ?")
        params.append(group_id)
    if topic_code is not None:
        filters.append("topic_code = ?")
        params.append(topic_code)
    if stock_filter_tokens:
        stock_clauses: list[str] = []
        for token in stock_filter_tokens:
            normalized_token = choice_news_stock_like_pattern(token)
            if stock_match_mode == "visible_text":
                stock_clauses.append("upper(coalesce(payload_text, '')) like ? escape '~'")
                params.append(normalized_token)
            else:
                stock_clauses.append(
                    "(upper(coalesce(payload_text, '')) like ? escape '~' or "
                    "upper(coalesce(payload_json, '')) like ? escape '~')"
                )
                params.extend([normalized_token, normalized_token])
        filters.append("(" + " or ".join(stock_clauses) + ")")
    if error_only:
        filters.append("error_code != 0")
    if received_from is not None:
        filters.append("received_at >= ?")
        params.append(received_from)
    if received_to is not None:
        filters.append("received_at <= ?")
        params.append(received_to)
    if not filters:
        return "", params
    return "where " + " and ".join(filters), params


def choice_news_stock_like_pattern(token: str) -> str:
    escaped_token = token.upper().replace("~", "~~").replace("%", "~%").replace("_", "~_")
    return f"%{escaped_token}%"


def choice_news_stock_filter_tokens(
    stock_code: str | None,
    stock_name: str | None = None,
) -> list[str]:
    if not stock_code:
        return []
    tokens = [stock_code]
    stem = stock_code.split(".", 1)[0]
    if len(stem) == 6 and stem.isdigit():
        tokens.append(stem)
    if stock_name:
        tokens.append(stock_name)
    return list(dict.fromkeys(tokens))


def choice_news_latest_sql_text(
    *,
    group_id: str | None = None,
    topic_code: str | None = None,
    stock_code: str | None = None,
    stock_name: str | None = None,
    stock_match_mode: StockMatchMode = "best_effort",
    include_payload_json: bool = True,
    error_only: bool = False,
    received_from: str | None = None,
    received_to: str | None = None,
) -> list[str]:
    """证据披露：返回主干只读语句（同一模板），不执行 SQL。"""
    normalized_stock_code = stock_code.strip().upper() if stock_code and stock_code.strip() else None
    normalized_stock_name = (
        stock_name.strip().upper()
        if normalized_stock_code is not None and stock_name and stock_name.strip()
        else None
    )
    where_clause, _params = choice_news_filters(
        group_id=group_id,
        topic_code=topic_code,
        stock_filter_tokens=choice_news_stock_filter_tokens(
            normalized_stock_code,
            normalized_stock_name,
        ),
        stock_match_mode=stock_match_mode,
        error_only=error_only,
        received_from=received_from,
        received_to=received_to or date.today().isoformat(),
    )
    sql = choice_news_latest_events_sql(
        where_clause=where_clause,
        include_payload_json=include_payload_json,
    )
    return [" ".join(sql.split())]


@dataclass(frozen=True)
class _BatchRequest:
    topic_code: str | None
    group_id: str | None
    limit: int


class ChoiceNewsRepository(DuckDBRepository):
    """Read-only ``choice_news_event`` queries via shared DuckDB helpers."""

    def fetch_latest(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        group_id: str | None = None,
        topic_code: str | None = None,
        stock_filter_tokens: list[str] | None = None,
        stock_match_mode: StockMatchMode = "best_effort",
        error_only: bool = False,
        received_from: str | None = None,
        received_to: str | None = None,
        include_payload_json: bool = True,
        as_of_date: str | None = None,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> ChoiceNewsLatestRaw:
        tokens = list(stock_filter_tokens or [])
        effective_as_of = as_of_date or date.today().isoformat()
        effective_received_to = received_to or effective_as_of

        if conn is not None:
            return self._fetch_latest_impl(
                conn,
                limit=limit,
                offset=offset,
                group_id=group_id,
                topic_code=topic_code,
                stock_filter_tokens=tokens,
                stock_match_mode=stock_match_mode,
                error_only=error_only,
                received_from=received_from,
                received_to=effective_received_to,
                include_payload_json=include_payload_json,
                as_of_date=effective_as_of,
            )

        if self.guard_path_exists and not Path(self.path).exists():
            return ChoiceNewsLatestRaw(
                rows=[],
                total_rows=0,
                excluded_future_rows=0,
                source_unavailable=True,
            )

        try:
            with read_only_connection(self.path) as scoped:
                return self._fetch_latest_impl(
                    scoped,
                    limit=limit,
                    offset=offset,
                    group_id=group_id,
                    topic_code=topic_code,
                    stock_filter_tokens=tokens,
                    stock_match_mode=stock_match_mode,
                    error_only=error_only,
                    received_from=received_from,
                    received_to=effective_received_to,
                    include_payload_json=include_payload_json,
                    as_of_date=effective_as_of,
                )
        except (OSError, duckdb.Error):
            return ChoiceNewsLatestRaw(
                rows=[],
                total_rows=0,
                excluded_future_rows=0,
                source_unavailable=True,
            )

    def fetch_latest_batch(
        self,
        *,
        topic_requests: list[tuple[str, int]],
        group_requests: list[tuple[str, int]],
        as_of_date: str | None = None,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> ChoiceNewsBatchRaw:
        effective_as_of = as_of_date or date.today().isoformat()
        requests: list[_BatchRequest] = [
            _BatchRequest(topic_code=code, group_id=None, limit=limit)
            for code, limit in topic_requests
        ]
        requests.extend(
            _BatchRequest(topic_code=None, group_id=gid, limit=limit)
            for gid, limit in group_requests
        )

        if conn is not None:
            return self._fetch_latest_batch_impl(conn, requests, effective_as_of)

        if self.guard_path_exists and not Path(self.path).exists():
            return ChoiceNewsBatchRaw(
                events_per_request=[[] for _ in requests],
                excluded_future_rows=0,
                source_unavailable=True,
            )

        try:
            with read_only_connection(self.path) as scoped:
                return self._fetch_latest_batch_impl(scoped, requests, effective_as_of)
        except (OSError, duckdb.Error):
            return ChoiceNewsBatchRaw(
                events_per_request=[[] for _ in requests],
                excluded_future_rows=0,
                source_unavailable=True,
            )

    def _fetch_latest_impl(
        self,
        conn: duckdb.DuckDBPyConnection,
        *,
        limit: int,
        offset: int,
        group_id: str | None,
        topic_code: str | None,
        stock_filter_tokens: list[str],
        stock_match_mode: StockMatchMode,
        error_only: bool,
        received_from: str | None,
        received_to: str | None,
        include_payload_json: bool,
        as_of_date: str,
    ) -> ChoiceNewsLatestRaw:
        if not self._choice_news_table_present(conn):
            return ChoiceNewsLatestRaw(
                rows=[],
                total_rows=0,
                excluded_future_rows=0,
                source_unavailable=True,
            )

        where_clause, params = choice_news_filters(
            group_id=group_id,
            topic_code=topic_code,
            stock_filter_tokens=stock_filter_tokens,
            stock_match_mode=stock_match_mode,
            error_only=error_only,
            received_from=received_from,
            received_to=received_to,
        )
        future_where_clause, future_params = choice_news_filters(
            group_id=group_id,
            topic_code=topic_code,
            stock_filter_tokens=stock_filter_tokens,
            stock_match_mode=stock_match_mode,
            error_only=error_only,
            received_from=received_from,
            received_to=None,
        )
        future_filter = " and " if future_where_clause else "where "
        future_row = conn.execute(
            f"""
            select count(*)
            from {RELATION_CHOICE_NEWS_EVENT}
            {future_where_clause}
            {future_filter}try_cast(substr(cast(received_at as varchar), 1, 10) as date) > ?::date
            """,
            [*future_params, as_of_date],
        ).fetchone()
        excluded_future_rows = int(future_row[0]) if future_row is not None else 0
        total_row = conn.execute(
            f"select count(*) from {RELATION_CHOICE_NEWS_EVENT} {where_clause}",
            params,
        ).fetchone()
        total_rows = int(total_row[0]) if total_row is not None else 0
        rows = conn.execute(
            choice_news_latest_events_sql(
                where_clause=where_clause,
                include_payload_json=include_payload_json,
            ),
            [*params, limit, offset],
        ).fetchall()
        return ChoiceNewsLatestRaw(
            rows=list(rows),
            total_rows=total_rows,
            excluded_future_rows=excluded_future_rows,
            source_unavailable=False,
        )

    def _fetch_latest_batch_impl(
        self,
        conn: duckdb.DuckDBPyConnection,
        requests: list[_BatchRequest],
        as_of_date: str,
    ) -> ChoiceNewsBatchRaw:
        if not self._choice_news_table_present(conn):
            return ChoiceNewsBatchRaw(
                events_per_request=[[] for _ in requests],
                excluded_future_rows=0,
                source_unavailable=True,
            )

        events_per_request: list[list[tuple[object, ...]]] = [[] for _ in requests]
        excluded_future_rows = 0
        for index, request in enumerate(requests):
            where_clause, params = choice_news_filters(
                group_id=request.group_id,
                topic_code=request.topic_code,
                stock_filter_tokens=[],
                stock_match_mode="best_effort",
                error_only=False,
                received_from=None,
                received_to=as_of_date,
            )
            future_where_clause, future_params = choice_news_filters(
                group_id=request.group_id,
                topic_code=request.topic_code,
                stock_filter_tokens=[],
                stock_match_mode="best_effort",
                error_only=False,
                received_from=None,
                received_to=None,
            )
            future_filter = " and " if future_where_clause else "where "
            future_row = conn.execute(
                f"""
                select count(*)
                from {RELATION_CHOICE_NEWS_EVENT}
                {future_where_clause}
                {future_filter}try_cast(substr(cast(received_at as varchar), 1, 10) as date) > ?::date
                """,
                [*future_params, as_of_date],
            ).fetchone()
            excluded_future_rows += int(future_row[0]) if future_row is not None else 0
            rows = conn.execute(
                choice_news_latest_events_sql(
                    where_clause=where_clause,
                    include_payload_json=True,
                ),
                [*params, request.limit, 0],
            ).fetchall()
            events_per_request[index] = list(rows)
        return ChoiceNewsBatchRaw(
            events_per_request=events_per_request,
            excluded_future_rows=excluded_future_rows,
            source_unavailable=False,
        )

    @staticmethod
    def _choice_news_table_present(conn: duckdb.DuckDBPyConnection) -> bool:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        return RELATION_CHOICE_NEWS_EVENT in tables and RELATION_CHOICE_NEWS_EVENT in _CHOICE_NEWS_READ_RELATIONS
