from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
from backend.app.repositories.task_write_guard import require_repository_task_write_scope
from backend.app.schema_registry.duckdb_loader import REGISTRY_DIR, parse_registry_sql_text

DISCLOSURE_TABLE = "fact_stock_official_disclosure"
SYNC_STATUS_TABLE = "stock_official_disclosure_sync_status"
DISCLOSURE_TABLES = [DISCLOSURE_TABLE, SYNC_STATUS_TABLE]
EVIDENCE_COVERAGE_LOOKBACK_DAYS = 550
_ANNOUNCEMENT_LANE = "official_announcement"
_FINANCIAL_REPORT_LANE = "financial_report"
_LANES = (_ANNOUNCEMENT_LANE, _FINANCIAL_REPORT_LANE)


def ensure_stock_official_disclosure_tables(conn: duckdb.DuckDBPyConnection) -> None:
    text = (REGISTRY_DIR / "39_stock_official_disclosure.sql").read_text(encoding="utf-8")
    for statement in parse_registry_sql_text(text):
        conn.execute(statement)


def upsert_stock_official_disclosures(
    conn: duckdb.DuckDBPyConnection,
    *,
    rows: list[dict[str, object]],
) -> int:
    require_repository_task_write_scope("upsert_stock_official_disclosures")
    ensure_stock_official_disclosure_tables(conn)
    deduped: dict[str, dict[str, object]] = {}
    for row in rows:
        key = _text(row.get("disclosure_key"))
        if key:
            for field in ("received_at", "ingested_at"):
                value = row.get(field)
                if isinstance(value, datetime) and value.tzinfo is None:
                    raise ValueError(f"{field} must include an explicit timezone.")
            deduped[key] = dict(row)
    if not deduped:
        return 0
    # A pre-v38 snapshot may contain a legacy disclosure_key derived from
    # mutable title/source-id fields. Remove such aliases by exact
    # stock_code+document_url inside the caller's task transaction before the
    # canonical URL-based key is upserted. Different URLs remain independent.
    for row in deduped.values():
        conn.execute(
            f"delete from {DISCLOSURE_TABLE} "
            "where stock_code = ? and document_url = ? and disclosure_key <> ?",
            [row["stock_code"], row["document_url"], row["disclosure_key"]],
        )
    conn.executemany(
        f"""
        insert into {DISCLOSURE_TABLE} (
          disclosure_key,
          stock_code,
          stock_name,
          evidence_type,
          publish_date,
          report_period,
          title,
          document_url,
          source_id,
          source_label,
          source_version,
          vendor_version,
          received_at,
          ingested_at,
          run_id,
          raw_json
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        on conflict (disclosure_key) do update set
          stock_code = excluded.stock_code,
          stock_name = excluded.stock_name,
          evidence_type = excluded.evidence_type,
          publish_date = excluded.publish_date,
          report_period = excluded.report_period,
          title = excluded.title,
          document_url = excluded.document_url,
          source_id = excluded.source_id,
          source_label = excluded.source_label,
          source_version = excluded.source_version,
          vendor_version = excluded.vendor_version,
          received_at = excluded.received_at,
          ingested_at = excluded.ingested_at,
          run_id = excluded.run_id,
          raw_json = excluded.raw_json
        """,
        [
            (
                row["disclosure_key"],
                row["stock_code"],
                row["stock_name"],
                row["evidence_type"],
                row["publish_date"],
                row.get("report_period"),
                row["title"],
                row["document_url"],
                row["source_id"],
                row["source_label"],
                row["source_version"],
                row["vendor_version"],
                row.get("received_at"),
                row["ingested_at"],
                row["run_id"],
                row["raw_json"],
            )
            for row in deduped.values()
        ],
    )
    return len(deduped)


def get_stock_official_disclosure_sync_status(
    conn: duckdb.DuckDBPyConnection,
    *,
    stock_code: str,
) -> dict[str, object] | None:
    row = conn.execute(
        f"""
        select
          stock_code,
          requested_from_date,
          covered_through_date,
          last_attempt_at,
          last_success_at,
          status,
          fetched_count,
          upserted_count,
          error,
          run_id,
          source_version
        from {SYNC_STATUS_TABLE}
        where stock_code = ?
        """,
        [stock_code],
    ).fetchone()
    if row is None:
        return None
    return {
        "stock_code": _text(row[0]),
        "requested_from_date": _date_text(row[1]),
        "coverage_start_date": _date_text(row[1]),
        "covered_through_date": _date_text(row[2]),
        "last_attempt_at": _timestamp_text(row[3]),
        "last_success_at": _timestamp_text(row[4]),
        "status": _text(row[5]),
        "fetched_count": int(row[6] or 0),
        "upserted_count": int(row[7] or 0),
        "error_message": _text(row[8]) or None,
        "run_id": _text(row[9]),
        "source_version": _text(row[10]),
    }


def upsert_stock_official_disclosure_sync_status(
    conn: duckdb.DuckDBPyConnection,
    *,
    stock_code: str,
    requested_from_date: str,
    covered_through_date: str | None,
    last_attempt_at: datetime,
    last_success_at: datetime | None,
    status: str,
    fetched_count: int,
    upserted_count: int,
    error_message: str | None,
    run_id: str,
    source_version: str,
) -> None:
    require_repository_task_write_scope("upsert_stock_official_disclosure_sync_status")
    if not isinstance(last_attempt_at, datetime) or last_attempt_at.tzinfo is None:
        raise ValueError("last_attempt_at must include an explicit timezone.")
    if last_success_at is not None and (
        not isinstance(last_success_at, datetime) or last_success_at.tzinfo is None
    ):
        raise ValueError("last_success_at must include an explicit timezone.")
    ensure_stock_official_disclosure_tables(conn)
    conn.execute(
        f"""
        insert or replace into {SYNC_STATUS_TABLE} (
          stock_code,
          requested_from_date,
          covered_through_date,
          last_attempt_at,
          last_success_at,
          status,
          fetched_count,
          upserted_count,
          error,
          run_id,
          source_version
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            stock_code,
            requested_from_date,
            covered_through_date,
            last_attempt_at,
            last_success_at,
            status,
            int(fetched_count),
            int(upserted_count),
            error_message,
            run_id,
            source_version,
        ],
    )


def list_stock_official_disclosures(
    *,
    duckdb_path: str,
    stock_code: str,
    as_of_date: date,
    limit_per_type: int,
) -> dict[str, object]:
    table_available = {
        lane: {"available": False, "tables": list(DISCLOSURE_TABLES)}
        for lane in _LANES
    }
    sync_status = {
        lane: {
            "status": "unavailable",
            "coverage_start_date": None,
            "covered_through_date": None,
            "last_success_at": None,
            "error_message": None,
        }
        for lane in _LANES
    }
    result = {
        "table_available": table_available,
        "sync_status": sync_status,
        "announcements": [],
        "financial_reports": [],
        "excluded_future_rows": 0,
        "latest_publish_date": None,
        "latest_ingested_at": None,
        "source_versions": {
            _ANNOUNCEMENT_LANE: None,
            _FINANCIAL_REPORT_LANE: None,
        },
    }

    path = Path(duckdb_path)
    if not path.exists():
        return result

    conn = duckdb.connect(str(path), read_only=True)
    try:
        if not (_relation_exists(conn, DISCLOSURE_TABLE) and _relation_exists(conn, SYNC_STATUS_TABLE)):
            return result
        for lane in _LANES:
            result["table_available"][lane]["available"] = True

        normalized_code = _text(stock_code).upper()
        as_of_text = as_of_date.isoformat()
        limit_value = max(1, int(limit_per_type))
        future_row = conn.execute(
            f"select count(*) from {DISCLOSURE_TABLE} where stock_code = ? and publish_date > cast(? as date)",
            [normalized_code, as_of_text],
        ).fetchone()
        latest_row = conn.execute(
            f"""
            select max(cast(publish_date as varchar)), max(ingested_at)
            from {DISCLOSURE_TABLE}
            where stock_code = ?
              and publish_date <= cast(? as date)
            """,
            [normalized_code, as_of_text],
        ).fetchone()
        sync = get_stock_official_disclosure_sync_status(conn, stock_code=normalized_code)
        if sync is not None:
            lane_status = _lane_sync_status(sync, as_of_date=as_of_date)
            for lane in _LANES:
                result["sync_status"][lane] = dict(lane_status)

        result["announcements"] = _load_rows(
            conn,
            stock_code=normalized_code,
            evidence_type=_ANNOUNCEMENT_LANE,
            as_of_text=as_of_text,
            limit_value=limit_value,
        )
        result["financial_reports"] = _load_rows(
            conn,
            stock_code=normalized_code,
            evidence_type=_FINANCIAL_REPORT_LANE,
            as_of_text=as_of_text,
            limit_value=limit_value,
        )
        result["source_versions"][_ANNOUNCEMENT_LANE] = _source_version_scalar(
            conn,
            stock_code=normalized_code,
            evidence_type=_ANNOUNCEMENT_LANE,
            as_of_text=as_of_text,
        )
        result["source_versions"][_FINANCIAL_REPORT_LANE] = _source_version_scalar(
            conn,
            stock_code=normalized_code,
            evidence_type=_FINANCIAL_REPORT_LANE,
            as_of_text=as_of_text,
        )
        result["excluded_future_rows"] = int(future_row[0] or 0) if future_row is not None else 0
        if latest_row is not None:
            result["latest_publish_date"] = _text(latest_row[0]) or None
            result["latest_ingested_at"] = _timestamp_text(latest_row[1])
        return result
    finally:
        conn.close()


def _load_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    stock_code: str,
    evidence_type: str,
    as_of_text: str,
    limit_value: int,
) -> list[dict[str, object]]:
    rows = conn.execute(
        f"""
        select
          disclosure_key,
          stock_code,
          stock_name,
          evidence_type,
          publish_date,
          report_period,
          title,
          document_url,
          source_id,
          source_label,
          source_version,
          vendor_version,
          received_at,
          ingested_at,
          run_id,
          raw_json
        from {DISCLOSURE_TABLE}
        where stock_code = ?
          and evidence_type = ?
          and publish_date <= cast(? as date)
        order by publish_date desc, ingested_at desc, disclosure_key desc
        limit ?
        """,
        [stock_code, evidence_type, as_of_text, limit_value],
    ).fetchall()
    return [
        {
            "event_key": _text(row[0]),
            "disclosure_key": _text(row[0]),
            "stock_code": _text(row[1]),
            "stock_name": _text(row[2]),
            "evidence_type": _text(row[3]),
            "publish_date": _date_text(row[4]),
            "report_period": _date_text(row[5]),
            "title": _text(row[6]),
            "document_url": _text(row[7]),
            "source_id": _text(row[8]),
            "source_label": _text(row[9]),
            "source_version": _text(row[10]),
            "vendor_version": _text(row[11]),
            "received_at": _timestamp_text(row[12]),
            "ingested_at": _timestamp_text(row[13]),
            "run_id": _text(row[14]),
            "raw_json": _text(row[15]),
        }
        for row in rows
    ]


def _source_version_scalar(
    conn: duckdb.DuckDBPyConnection,
    *,
    stock_code: str,
    evidence_type: str,
    as_of_text: str,
) -> str | None:
    rows = conn.execute(
        f"""
        select distinct source_version
        from {DISCLOSURE_TABLE}
        where stock_code = ?
          and evidence_type = ?
          and publish_date <= cast(? as date)
          and coalesce(source_version, '') <> ''
        order by source_version
        """,
        [stock_code, evidence_type, as_of_text],
    ).fetchall()
    values = [_text(row[0]) for row in rows if _text(row[0])]
    return "__".join(values) or None


def _lane_sync_status(sync: dict[str, object], *, as_of_date: date) -> dict[str, object]:
    status = _text(sync.get("status")) or "unavailable"
    covered_text = _text(sync.get("covered_through_date")) or None
    covered = date.fromisoformat(covered_text) if covered_text else None
    if status in {"success", "empty"} and covered is not None and covered < as_of_date:
        status = "stale"
    return {
        "status": status,
        "coverage_start_date": _text(sync.get("coverage_start_date")) or None,
        "covered_through_date": covered_text,
        "last_success_at": _text(sync.get("last_success_at")) or None,
        "error_message": _text(sync.get("error_message")) or None,
        "source_version": _text(sync.get("source_version")) or None,
    }


def _relation_exists(conn: duckdb.DuckDBPyConnection, relation_name: str) -> bool:
    row = conn.execute(
        """
        select 1
        from information_schema.tables
        where table_schema = 'main' and table_name = ?
        limit 1
        """,
        [relation_name],
    ).fetchone()
    return row is not None


def _timestamp_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(UTC).isoformat()
        return value.isoformat()
    text = _text(value)
    return text or None


def _date_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = _text(value)
    return text or None


def _text(value: object) -> str:
    return str(value or "").strip()
