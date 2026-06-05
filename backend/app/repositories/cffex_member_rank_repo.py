from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
from backend.app.schema_registry.duckdb_loader import REGISTRY_DIR, parse_registry_sql_text

TABLE_NAME = "fact_cffex_member_rank_daily"
VIEW_NAME = "vw_cffex_member_rank_daily"
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


def normalize_cffex_contract(contract: str) -> str:
    raw = str(contract or "").strip().upper()
    if not raw:
        return "T.CFE"
    raw = raw.replace(".CFFEX", ".CFE")
    if raw.startswith("CFFEX."):
        raw = f"{raw.split('.', 1)[1]}.CFE"
    elif raw.startswith("CFE."):
        raw = f"{raw.split('.', 1)[1]}.CFE"
    elif "." not in raw:
        raw = f"{raw}.CFE"
    return raw


def product_code_from_contract(contract: str) -> str:
    code = normalize_cffex_contract(contract).split(".", 1)[0]
    letters = "".join(ch for ch in code if ch.isalpha())
    return letters or code


def normalize_trade_date(value: str) -> str:
    raw = str(value or "").strip()
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    return raw[:10]


def table_stats(duckdb_path: str | Path) -> dict[str, object]:
    path = Path(duckdb_path)
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


def load_member_rank_frame(
    duckdb_path: str | Path,
    *,
    trade_date: str,
    contract: str,
) -> pd.DataFrame:
    path = Path(duckdb_path)
    if not path.exists():
        return _empty_rank_frame()
    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error:
        return _empty_rank_frame()
    try:
        if not _table_exists(conn, TABLE_NAME):
            return _empty_rank_frame()
        source = VIEW_NAME if _table_exists(conn, VIEW_NAME) else TABLE_NAME
        frame = conn.execute(
            f"""
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
              created_at
            from {source}
            where trade_date = ? and contract = ?
            """,
            [normalize_trade_date(trade_date), normalize_cffex_contract(contract)],
        ).fetchdf()
    except duckdb.Error:
        return _empty_rank_frame()
    finally:
        conn.close()
    return frame


def replace_member_rank_rows(conn: duckdb.DuckDBPyConnection, rows: list[CffexMemberRankRow]) -> int:
    if not rows:
        return 0
    ensure_cffex_member_rank_schema(conn)
    keys = {
        (row.trade_date, row.contract, row.source_vendor)
        for row in rows
        if row.trade_date and row.contract and row.source_vendor
    }
    for trade_date, contract, source_vendor in keys:
        conn.execute(
            f"delete from {TABLE_NAME} where trade_date = ? and contract = ? and source_vendor = ?",
            [trade_date, contract, source_vendor],
        )
    conn.executemany(
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
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [_row_values(row) for row in rows],
    )
    return len(rows)


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


def _empty_rank_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "trade_date",
            "contract",
            "product_code",
            "exchange",
            "member_name",
            "source_vendor",
            "source_row_no",
            "volume",
            "volume_change",
            "long_holding",
            "long_change",
            "short_holding",
            "short_change",
            "source_version",
            "vendor_version",
            "rule_version",
            "ingest_batch_id",
            "created_at",
        ]
    )
