from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb


@dataclass
class ChoiceNewsRepository:
    path: str

    def fetch_events(
        self,
        *,
        limit: int,
        offset: int,
        group_id: str | None = None,
        topic_code: str | None = None,
        error_only: bool = False,
        received_from: str | None = None,
        received_to: str | None = None,
        paginate: bool = True,
    ) -> tuple[bool, int, list[tuple[object, ...]]]:
        duckdb_file = Path(self.path)
        if not duckdb_file.exists():
            return False, 0, []

        try:
            conn = duckdb.connect(str(duckdb_file), read_only=True)
        except duckdb.Error:
            return False, 0, []

        try:
            tables = {row[0] for row in conn.execute("show tables").fetchall()}
            if "choice_news_event" not in tables:
                return False, 0, []

            where_clause, params = _choice_news_filters(
                group_id=group_id,
                topic_code=topic_code,
                error_only=error_only,
                received_from=received_from,
                received_to=received_to,
            )

            base_select = """
                select event_key, received_at, group_id, content_type, serial_id, request_id, error_code, error_msg, topic_code, item_index, payload_text, payload_json
                from choice_news_event
            """
            if paginate:
                total_rows = int(
                    conn.execute(
                        f"select count(*) from choice_news_event {where_clause}",
                        params,
                    ).fetchone()[0]
                )
                rows = conn.execute(
                    base_select
                    + where_clause
                    + """
                        order by received_at desc, topic_code asc, item_index asc
                        limit ? offset ?
                    """,
                    [*params, limit, offset],
                ).fetchall()
                return True, total_rows, rows

            rows = conn.execute(
                base_select
                + where_clause
                + """
                    order by received_at desc, topic_code asc, item_index asc
                """,
                params,
            ).fetchall()
            return True, len(rows), rows
        except duckdb.Error:
            return False, 0, []
        finally:
            conn.close()


def _choice_news_filters(
    *,
    group_id: str | None,
    topic_code: str | None,
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
    return " where " + " and ".join(filters), params
