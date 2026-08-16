"""CFFEX 会员持仓排名——表结构常量与只读查询的中立下沉层。

背景：`core_finance` 是纯计算层，不得 `import backend.app.repositories`（见
`docs/plans/tech-debt-remediation/E4-reverse-deps-reanchor.md` #2/#3）。但
`macro/toolkit` 下的 WindPy 兼容层（`WindPy.py`）与拥挤度分析脚本
（`scripts/crowding_cn.py`）需要直接读取中金所会员持仓排名表/视图。

本模块是这些只读事实（表名/视图名 + 归一化/查询函数）的唯一定义处；
`backend.app.repositories.cffex_member_rank_repo` 从本模块 re-export 同名
符号以保持对外接口不变，其余写路径（schema 建表、写入、行构造等）仍留在
repositories 层。
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

TABLE_NAME = "fact_cffex_member_rank_daily"
VIEW_NAME = "vw_cffex_member_rank_daily"


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


def normalize_trade_date(value: str) -> str:
    raw = str(value or "").strip()
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    return raw[:10]


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
