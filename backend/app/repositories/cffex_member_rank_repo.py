from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
from backend.app.core_finance.macro.toolkit.cffex_member_rank_shared import (
    TABLE_NAME,
    VIEW_NAME,
    load_member_rank_frame,
    normalize_cffex_contract,
    normalize_trade_date,
)
from backend.app.repositories.duckdb_read_context import resolve_effective_read_path
from backend.app.repositories.task_write_guard import require_repository_task_write_scope
from backend.app.schema_registry.duckdb_loader import REGISTRY_DIR, parse_registry_sql_text

__all__ = [
    "TABLE_NAME",
    "VIEW_NAME",
    "RULE_VERSION",
    "DEFAULT_CFFEX_CONTRACTS",
    "CffexMemberRankRow",
    "ensure_cffex_member_rank_schema",
    "normalize_cffex_contract",
    "normalize_cffex_sources",
    "normalize_trade_date",
    "product_code_from_contract",
    "table_stats",
    "load_member_rank_frame",
    "replace_member_rank_rows",
    "rows_from_records",
]

RULE_VERSION = "rv_cffex_member_rank_choice_tushare_v1"
DEFAULT_CFFEX_CONTRACTS = ("TS.CFE", "TF.CFE", "T.CFE", "TL.CFE")


@dataclass(frozen=True)
class CffexMemberRankRow:
    trade_date: str
    contract: str
    product_code: str
    exchange: str
    member_name: str
    source_vendor: str
    source_row_no: int | None = None
    volume: float | None = None
    volume_change: float | None = None
    long_holding: float | None = None
    long_change: float | None = None
    short_holding: float | None = None
    short_change: float | None = None
    source_version: str | None = None
    vendor_version: str | None = None
    rule_version: str = RULE_VERSION
    ingest_batch_id: str | None = None
    raw_payload_json: str | None = None


def ensure_cffex_member_rank_schema(conn: duckdb.DuckDBPyConnection) -> None:
    text = (REGISTRY_DIR / "24_cffex_member_rank.sql").read_text(encoding="utf-8")
    for statement in parse_registry_sql_text(text):
        conn.execute(statement)


def normalize_cffex_sources(sources: Iterable[object]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(str(source).strip().lower() for source in sources if str(source).strip())
    )


def product_code_from_contract(contract: str) -> str:
    code = normalize_cffex_contract(contract).split(".", 1)[0]
    letters = "".join(ch for ch in code if ch.isalpha())
    return letters or code


def table_stats(duckdb_path: str | Path) -> dict[str, object]:
    path = Path(resolve_effective_read_path(duckdb_path))
    if not path.exists():
        return _empty_stats("missing_database")
    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error:
        return _empty_stats("unreadable_database")
    try:
        if not _table_exists(conn, TABLE_NAME):
            return _empty_stats("missing_table")
        row_count = int(conn.execute(f"select count(*) from {TABLE_NAME}").fetchone()[0])
        if row_count == 0:
            return _empty_stats("empty_table", materialized=True)
        latest_trade_date = conn.execute(f"select max(trade_date) from {TABLE_NAME}").fetchone()[0]
        sources = [
            str(row[0])
            for row in conn.execute(
                f"select distinct source_vendor from {TABLE_NAME} order by source_vendor"
            ).fetchall()
        ]
        contracts = [
            str(row[0])
            for row in conn.execute(f"select distinct contract from {TABLE_NAME} order by contract").fetchall()
        ]
        return {
            "materialized": True,
            "status": "ok",
            "row_count": row_count,
            "latest_trade_date": str(latest_trade_date) if latest_trade_date else None,
            "contracts": contracts,
            "source_vendors": sources,
        }
    except duckdb.Error as exc:
        return {
            **_empty_stats("query_failed"),
            "detail": str(exc),
        }
    finally:
        conn.close()


def replace_member_rank_rows(conn: duckdb.DuckDBPyConnection, rows: list[CffexMemberRankRow]) -> int:
    require_repository_task_write_scope("replace_member_rank_rows")
    if not rows:
        return 0
    _raise_on_duplicate_natural_keys(rows)
    ensure_cffex_member_rank_schema(conn)
    transaction_started = False
    try:
        conn.execute("begin transaction")
        transaction_started = True
        conn.execute(
            f"""
            create or replace temp table cffex_member_rank_stage as
            select
              trade_date,
              contract,
              product_code,
              exchange,
              member_name,
              source_vendor,
              source_row_no,
              volume,
              volume_change,
              long_holding,
              long_change,
              short_holding,
              short_change,
              source_version,
              vendor_version,
              rule_version,
              ingest_batch_id,
              raw_payload_json
            from {TABLE_NAME}
            where false
            """
        )
        conn.executemany(
            """
            insert into cffex_member_rank_stage
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [_row_values(row) for row in rows],
        )
        # DuckDB can reject delete/reinsert of persisted unique keys after a
        # reconnect. Update retained members in place, then remove absent ones.
        conn.execute(
            f"""
            insert into {TABLE_NAME} (
              trade_date,
              contract,
              product_code,
              exchange,
              member_name,
              source_vendor,
              source_row_no,
              volume,
              volume_change,
              long_holding,
              long_change,
              short_holding,
              short_change,
              source_version,
              vendor_version,
              rule_version,
              ingest_batch_id,
              raw_payload_json
            )
            select * from cffex_member_rank_stage
            on conflict (trade_date, contract, member_name, source_vendor) do update set
              product_code = excluded.product_code,
              exchange = excluded.exchange,
              source_row_no = excluded.source_row_no,
              volume = excluded.volume,
              volume_change = excluded.volume_change,
              long_holding = excluded.long_holding,
              long_change = excluded.long_change,
              short_holding = excluded.short_holding,
              short_change = excluded.short_change,
              source_version = excluded.source_version,
              vendor_version = excluded.vendor_version,
              rule_version = excluded.rule_version,
              ingest_batch_id = excluded.ingest_batch_id,
              raw_payload_json = excluded.raw_payload_json,
              created_at = now()
            """
        )
        keys = {
            (row.trade_date, row.contract, row.source_vendor)
            for row in rows
            if row.trade_date and row.contract and row.source_vendor
        }
        for trade_date, contract, source_vendor in keys:
            conn.execute(
                f"""
                delete from {TABLE_NAME} as target
                where target.trade_date = ?
                  and target.contract = ?
                  and target.source_vendor = ?
                  and not exists (
                    select 1
                    from cffex_member_rank_stage as stage
                    where stage.trade_date = target.trade_date
                      and stage.contract = target.contract
                      and stage.member_name = target.member_name
                      and stage.source_vendor = target.source_vendor
                  )
                """,
                [trade_date, contract, source_vendor],
            )
        conn.execute("drop table cffex_member_rank_stage")
        conn.execute("commit")
        transaction_started = False
    except Exception:
        if transaction_started:
            try:
                conn.execute("rollback")
            except Exception:  # noqa: S110 - rollback failure must not mask the insert error
                pass
        raise
    return len(rows)


def _raise_on_duplicate_natural_keys(rows: list[CffexMemberRankRow]) -> None:
    seen: set[tuple[str, str, str, str]] = set()
    for row in rows:
        key = (row.trade_date, row.contract, row.member_name, row.source_vendor)
        if key in seen:
            raise duckdb.ConstraintException(
                "Duplicate CFFEX member-rank input key "
                f"trade_date={row.trade_date!r}, contract={row.contract!r}, "
                f"member_name={row.member_name!r}, source_vendor={row.source_vendor!r}"
            )
        seen.add(key)


def rows_from_records(
    records: list[dict[str, Any]],
    *,
    source_vendor: str,
    requested_contract: str,
    ingest_batch_id: str,
    source_version: str,
    vendor_version: str,
) -> list[CffexMemberRankRow]:
    rows: list[CffexMemberRankRow] = []
    for index, record in enumerate(records, start=1):
        member_name = _first_text(record, "member_name", "member", "broker", "broker_name", "participant_name")
        trade_date = _first_text(record, "trade_date", "date", "trading_date")
        if not member_name or not trade_date:
            continue
        contract = normalize_cffex_contract(
            _first_text(record, "contract", "windcode", "symbol", "sec_code") or requested_contract
        )
        product_code = product_code_from_contract(contract)
        rows.append(
            CffexMemberRankRow(
                trade_date=normalize_trade_date(trade_date),
                contract=contract,
                product_code=product_code,
                exchange=_first_text(record, "exchange", "exchange_code") or "CFFEX",
                member_name=member_name,
                source_vendor=source_vendor,
                source_row_no=_first_int(record, "source_row_no", "rank", "ranking") or index,
                volume=_first_float(record, "volume", "vol", "transaction_volume"),
                volume_change=_first_float(record, "volume_change", "vol_chg", "transaction_volume_change"),
                long_holding=_first_float(record, "long_holding", "long_hld", "long", "long_position"),
                long_change=_first_float(record, "long_change", "long_chg", "long_position_change"),
                short_holding=_first_float(record, "short_holding", "short_hld", "short", "short_position"),
                short_change=_first_float(record, "short_change", "short_chg", "short_position_change"),
                source_version=source_version,
                vendor_version=vendor_version,
                ingest_batch_id=ingest_batch_id,
            )
        )
    return rows


def _row_values(row: CffexMemberRankRow) -> tuple[object, ...]:
    return (
        row.trade_date,
        row.contract,
        row.product_code,
        row.exchange,
        row.member_name,
        row.source_vendor,
        row.source_row_no,
        row.volume,
        row.volume_change,
        row.long_holding,
        row.long_change,
        row.short_holding,
        row.short_change,
        row.source_version,
        row.vendor_version,
        row.rule_version,
        row.ingest_batch_id,
        row.raw_payload_json,
    )


def _first_text(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = _lookup(record, key)
        if value is None:
            continue
        text = str(value).strip()
        if text and text.lower() != "nan":
            return text
    return ""


def _first_float(record: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = _lookup(record, key)
        if value is None or value == "":
            continue
        try:
            out = float(value)
        except (TypeError, ValueError):
            continue
        if pd.isna(out):
            continue
        return out
    return None


def _first_int(record: dict[str, Any], *keys: str) -> int | None:
    value = _first_float(record, *keys)
    return int(value) if value is not None else None


def _lookup(record: dict[str, Any], key: str) -> Any:
    if key in record:
        return record[key]
    lowered = key.lower()
    for current_key, value in record.items():
        if str(current_key).strip().lower() == lowered:
            return value
    return None


def _table_exists(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    try:
        return bool(
            conn.execute(
                """
                select count(*)
                from information_schema.tables
                where table_schema = 'main' and table_name = ?
                """,
                [table_name],
            ).fetchone()[0]
        )
    except duckdb.Error:
        return False


def _empty_stats(status: str, *, materialized: bool = False) -> dict[str, object]:
    return {
        "materialized": materialized,
        "status": status,
        "row_count": 0,
        "latest_trade_date": None,
        "contracts": [],
        "source_vendors": [],
    }
