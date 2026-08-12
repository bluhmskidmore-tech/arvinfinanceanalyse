"""Ingest numeric daily limit prices (Tushare ``stk_limit``) into ``stock_limit_price_daily``.

数值涨跌停价专用链路：``choice_stock_daily_observation`` 的 ``highlimit`` /
``lowlimit`` 是 Choice "是/否" 标志而非价格（契约 docs/data_contracts.md §4.10
"highlimit/lowlimit 覆盖缺口" 段），choice_native 代际（2026-01-05 起）没有可解析
的数值涨跌停价。本任务按交易日调用 Tushare ``stk_limit`` 接口，把数值价格落入
独立表 ``stock_limit_price_daily``（40_stock_limit_price_daily.sql），供
``backend/app/core_finance/portfolio_paths.py`` 等消费端优先读取。

写入规范：
- 幂等 delete+insert（按 trade_date 粒度，事务内完成）。
- vendor_version 自成白名单（``vv_tushare_stk_limit_*``）：本表独立于
  choice_stock_units 的两代单位换算，但沿用同一代际守卫理念——未知 vendor
  模式禁止落表。
- 写后 DQ：数值为正、up_limit > down_limit（硬校验行写前即拒绝，写后复核），
  并对 up/down 相对 pre_close 的涨跌幅做合理带抽检（仅告警，不回滚）。

API/services 不得导入本模块执行（DuckDB 写路径，仅 tasks/scripts 使用）。
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid
from datetime import date, timedelta
from pathlib import Path

import duckdb
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.governance.settings import get_settings
from backend.app.repositories.tushare_adapter import (
    import_tushare_pro,
    resolve_tushare_token_with_settings_fallback,
)
from backend.app.schema_registry.duckdb_loader import REGISTRY_DIR, parse_registry_sql_text

logger = logging.getLogger(__name__)

TABLE_NAME = "stock_limit_price_daily"
RULE_VERSION = "rv_stock_limit_price_daily_v1"
STOCK_LIMIT_PRICE_LOCK = LockDefinition(
    key="lock:duckdb:stock-limit-price-daily",
    ttl_seconds=900,
)

# 本表 vendor 模式自成白名单：未知模式一律拒绝写入（代际守卫理念与
# choice_stock_daily_observation 的 DAILY_OBSERVATION_VENDOR_VERSION_PATTERNS 一致，
# 但两份白名单互不混用——本表不经两代单位换算）。
STOCK_LIMIT_PRICE_VENDOR_VERSION_PATTERNS = (
    r"^vv_tushare_stk_limit_\d{8}_[0-9a-f]{12}$",
)

TUSHARE_STK_LIMIT_FIELDS = "trade_date,ts_code,pre_close,up_limit,down_limit"
# 交易日历近似源：该表已落地的 trade_date 视为交易日，用于区分
# "交易日空响应（数据缺口，告警）" 与 "非交易日空响应（正常）"。
OBSERVATION_CALENDAR_TABLE = "choice_stock_daily_observation"
FETCH_RETRY_ATTEMPTS = 3
# 写后 DQ 合理带：A 股涨跌停比例区间约 ST 5% ~ 新股/北交所 44%（含 30% 板），
# 上限放宽到 50%；|ratio| 超带或方向不对（up<=pre_close / down>=pre_close）计入告警。
DQ_RATIO_MAX = 0.5
DQ_RATIO_SAMPLE_ROWS_PER_DATE = 200


class StockLimitPriceUnknownVendorVersionError(ValueError):
    """vendor_version 不在 stock_limit_price_daily 已知模式白名单内。"""


def ensure_stock_limit_price_daily_schema(conn: duckdb.DuckDBPyConnection) -> None:
    text = (REGISTRY_DIR / "40_stock_limit_price_daily.sql").read_text(encoding="utf-8")
    for statement in parse_registry_sql_text(text):
        conn.execute(statement)


def assert_stock_limit_price_vendor_version(vendor_version: object) -> None:
    normalized = str(vendor_version or "").strip()
    if not normalized or not any(
        re.match(pattern, normalized) for pattern in STOCK_LIMIT_PRICE_VENDOR_VERSION_PATTERNS
    ):
        raise StockLimitPriceUnknownVendorVersionError(
            f"vendor_version {vendor_version!r} is not in the known stock_limit_price_daily "
            "vendor whitelist (vv_tushare_stk_limit_*). Register the pattern in "
            "STOCK_LIMIT_PRICE_VENDOR_VERSION_PATTERNS before writing."
        )


class _DefaultTushareStkLimitClient:
    """真实 Tushare pro 客户端；测试与 dry-run 注入 mock 代替。"""

    def __init__(self) -> None:
        token = resolve_tushare_token_with_settings_fallback(get_settings())
        if not token:
            raise RuntimeError(
                "MOSS_TUSHARE_TOKEN or settings.tushare_token is required for stk_limit ingest."
            )
        self._api = import_tushare_pro().pro_api(token)

    def stk_limit(self, **kwargs: object) -> object:
        return self._api.stk_limit(**kwargs)


def ingest_stock_limit_prices(
    *,
    duckdb_path: str | Path,
    start_date: str,
    end_date: str | None = None,
    client: object | None = None,
    dry_run: bool = False,
    run_id: str | None = None,
    retry_attempts: int = FETCH_RETRY_ATTEMPTS,
    retry_sleep_seconds: float = 1.0,
    dq_ratio_sample_rows_per_date: int = DQ_RATIO_SAMPLE_ROWS_PER_DATE,
) -> dict[str, object]:
    """按日期范围拉取 Tushare stk_limit 并幂等写入 stock_limit_price_daily。

    ``dry_run=True`` 时不调用 vendor、不写库，仅返回执行计划与现有覆盖行数。
    单日拉取失败重试 ``retry_attempts`` 次后记入 ``failed_dates`` 并继续其余日期
    （部分成功返回 ``partial_completed``）；全部日期失败则抛出异常。
    """
    start_text = _normalize_date_text(start_date, option_name="start_date")
    end_text = (
        _normalize_date_text(end_date, option_name="end_date") if end_date else start_text
    )
    if end_text < start_text:
        raise ValueError(f"end_date {end_text} is before start_date {start_text}")
    trade_dates = _calendar_dates(start_text, end_text)
    path = Path(duckdb_path)

    if dry_run:
        return _dry_run_plan(path, start_text=start_text, end_text=end_text, trade_dates=trade_dates)

    if not path.is_file():
        raise FileNotFoundError(f"DuckDB file not found: {path}")
    effective_run = run_id or f"stock_limit_price:{start_text}:{end_text}:{uuid.uuid4().hex[:12]}"
    vendor_client = client if client is not None else _DefaultTushareStkLimitClient()

    date_results: list[dict[str, object]] = []
    failed_dates: list[str] = []
    rows_by_date: dict[str, list[dict[str, object]]] = {}
    skipped_invalid_total = 0
    for trade_date_text in trade_dates:
        compact = trade_date_text.replace("-", "")
        try:
            payload = _fetch_stk_limit_with_retry(
                vendor_client,
                trade_date_compact=compact,
                retry_attempts=retry_attempts,
                retry_sleep_seconds=retry_sleep_seconds,
            )
        except Exception as exc:
            failed_dates.append(trade_date_text)
            date_results.append(
                {
                    "trade_date": trade_date_text,
                    "status": "fetch_failed",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        rows, skipped_invalid = _normalize_vendor_rows(payload, expected_trade_date=trade_date_text)
        skipped_invalid_total += skipped_invalid
        if not rows:
            date_results.append(
                {
                    "trade_date": trade_date_text,
                    "status": "empty",
                    "row_count": 0,
                    "skipped_invalid_row_count": skipped_invalid,
                }
            )
            continue
        vendor_version = _vendor_version(compact, run_id=effective_run)
        assert_stock_limit_price_vendor_version(vendor_version)
        source_version = _source_version(rows)
        for row in rows:
            row["source_version"] = source_version
            row["vendor_version"] = vendor_version
        rows_by_date[trade_date_text] = rows
        date_results.append(
            {
                "trade_date": trade_date_text,
                "status": "fetched",
                "row_count": len(rows),
                "skipped_invalid_row_count": skipped_invalid,
                "vendor_version": vendor_version,
                "source_version": source_version,
            }
        )

    if failed_dates and not rows_by_date:
        msg = (
            f"stk_limit ingest failed for all {len(failed_dates)} requested dates "
            f"({start_text}..{end_text}); nothing was written."
        )
        raise RuntimeError(msg)

    inserted_row_count = 0
    dq: dict[str, object] = {"status": "skipped", "issues": []}
    if rows_by_date:
        with acquire_lock(STOCK_LIMIT_PRICE_LOCK, base_dir=path.parent):
            conn = duckdb.connect(str(path), read_only=False)
            try:
                ensure_stock_limit_price_daily_schema(conn)
                inserted_row_count = _replace_rows_by_date(
                    conn, rows_by_date, run_id=effective_run
                )
                dq = _run_post_write_dq(
                    conn,
                    start_date=start_text,
                    end_date=end_text,
                    ratio_sample_rows_per_date=dq_ratio_sample_rows_per_date,
                )
            finally:
                conn.close()
    issues = list(dq.get("issues") or [])
    if skipped_invalid_total:
        issues.append(
            f"{skipped_invalid_total} vendor rows rejected before write "
            "(nonpositive limits, up_limit <= down_limit, or malformed rows)"
        )

    # 空响应区分：以 choice_stock_daily_observation 已落地日期作为交易日历近似，
    # 交易日拿到空 stk_limit 响应是数据缺口（告警）；非交易日空响应是正常噪音。
    # 日历不可得（observation 表缺失）时 empty_trade_date_count 为 None。
    empty_dates = [
        str(result["trade_date"])
        for result in date_results
        if result.get("status") == "empty"
    ]
    empty_trade_date_count: int | None = None
    if empty_dates:
        empty_trade_date_count = _count_observation_trade_dates(path, empty_dates)
        if empty_trade_date_count:
            issues.append(
                f"{empty_trade_date_count} trade dates (per {OBSERVATION_CALENDAR_TABLE}) "
                "returned an empty stk_limit response; numeric limit prices are still "
                "missing for those dates"
            )
    dq["issues"] = issues
    if issues and dq.get("status") in {"passed", "skipped"}:
        dq["status"] = "issues_found"

    if failed_dates:
        status = "partial_completed"
    elif issues:
        status = "completed_with_warnings"
    else:
        status = "completed"
    for issue in issues:
        logger.warning("stk_limit ingest DQ issue run_id=%s: %s", effective_run, issue)
    return {
        "status": status,
        "table": TABLE_NAME,
        "rule_version": RULE_VERSION,
        "run_id": effective_run,
        "start_date": start_text,
        "end_date": end_text,
        "requested_date_count": len(trade_dates),
        "written_date_count": len(rows_by_date),
        "inserted_row_count": inserted_row_count,
        "skipped_invalid_row_count": skipped_invalid_total,
        "empty_date_count": len(empty_dates),
        "empty_trade_date_count": empty_trade_date_count,
        "failed_dates": failed_dates,
        "date_results": date_results,
        "dq": dq,
    }


def _dry_run_plan(
    path: Path,
    *,
    start_text: str,
    end_text: str,
    trade_dates: list[str],
) -> dict[str, object]:
    existing_row_count: int | None = None
    existing_date_count: int | None = None
    if path.is_file():
        conn = duckdb.connect(str(path), read_only=True)
        try:
            if _table_exists(conn, TABLE_NAME):
                row = conn.execute(
                    f"""
                    select count(*), count(distinct trade_date)
                    from {TABLE_NAME}
                    where trade_date >= ? and trade_date <= ?
                    """,
                    [start_text, end_text],
                ).fetchone()
                existing_row_count = int(row[0])
                existing_date_count = int(row[1])
            else:
                existing_row_count = 0
                existing_date_count = 0
        finally:
            conn.close()
    return {
        "status": "dry_run",
        "table": TABLE_NAME,
        "rule_version": RULE_VERSION,
        "duckdb_path": str(path),
        "duckdb_file_exists": path.is_file(),
        "start_date": start_text,
        "end_date": end_text,
        "requested_date_count": len(trade_dates),
        "requested_dates_preview": trade_dates[:10],
        "existing_row_count_in_range": existing_row_count,
        "existing_date_count_in_range": existing_date_count,
        "would_call_tushare": bool(trade_dates),
    }


def _fetch_stk_limit_with_retry(
    client: object,
    *,
    trade_date_compact: str,
    retry_attempts: int,
    retry_sleep_seconds: float,
) -> object:
    attempts = max(int(retry_attempts), 1)
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return client.stk_limit(
                trade_date=trade_date_compact,
                fields=TUSHARE_STK_LIMIT_FIELDS,
            )
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "stk_limit fetch failed trade_date=%s attempt=%s/%s: %s",
                trade_date_compact,
                attempt,
                attempts,
                exc,
            )
            if attempt < attempts and retry_sleep_seconds > 0:
                time.sleep(retry_sleep_seconds * attempt)
    assert last_exc is not None
    raise last_exc


def _normalize_vendor_rows(
    payload: object,
    *,
    expected_trade_date: str,
) -> tuple[list[dict[str, object]], int]:
    """规范化 vendor 行并做行级硬校验（数值为正、up>down），坏行拒绝落表。"""
    rows_by_code: dict[str, dict[str, object]] = {}
    skipped = 0
    for record in _records_from_tabular_payload(payload):
        stock_code = str(record.get("ts_code") or "").strip().upper()
        trade_date_text = _normalize_compact_date(record.get("trade_date"))
        up_limit = _float_or_none(record.get("up_limit"))
        down_limit = _float_or_none(record.get("down_limit"))
        pre_close = _positive_float_or_none(record.get("pre_close"))
        if not stock_code or trade_date_text != expected_trade_date:
            skipped += 1
            continue
        if up_limit is None or down_limit is None or up_limit <= 0 or down_limit <= 0:
            skipped += 1
            continue
        if up_limit <= down_limit:
            skipped += 1
            continue
        if stock_code in rows_by_code:
            skipped += 1
            continue
        rows_by_code[stock_code] = {
            "trade_date": trade_date_text,
            "stock_code": stock_code,
            "up_limit": up_limit,
            "down_limit": down_limit,
            "pre_close": pre_close,
        }
    rows = sorted(rows_by_code.values(), key=lambda row: str(row["stock_code"]))
    return rows, skipped


def _replace_rows_by_date(
    conn: duckdb.DuckDBPyConnection,
    rows_by_date: dict[str, list[dict[str, object]]],
    *,
    run_id: str,
) -> int:
    inserted = 0
    conn.execute("begin transaction")
    try:
        for trade_date_text in sorted(rows_by_date):
            conn.execute(
                f"delete from {TABLE_NAME} where trade_date = ?",
                [trade_date_text],
            )
            rows = rows_by_date[trade_date_text]
            conn.executemany(
                f"""
                insert into {TABLE_NAME} (
                  trade_date, stock_code, up_limit, down_limit, pre_close,
                  source_version, vendor_version, rule_version, run_id
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        row["trade_date"],
                        row["stock_code"],
                        row["up_limit"],
                        row["down_limit"],
                        row["pre_close"],
                        row["source_version"],
                        row["vendor_version"],
                        RULE_VERSION,
                        run_id,
                    )
                    for row in rows
                ],
            )
            inserted += len(rows)
        conn.execute("commit")
    except Exception:
        conn.execute("rollback")
        raise
    return inserted


def _run_post_write_dq(
    conn: duckdb.DuckDBPyConnection,
    *,
    start_date: str,
    end_date: str,
    ratio_sample_rows_per_date: int,
) -> dict[str, object]:
    """写后 DQ：正性/序关系全量复核 + pre_close 涨跌幅合理带抽检（仅告警）。"""
    issues: list[str] = []
    hard_violation_count = int(
        conn.execute(
            f"""
            select count(*)
            from {TABLE_NAME}
            where trade_date >= ? and trade_date <= ?
              and (
                up_limit is null or down_limit is null
                or up_limit <= 0 or down_limit <= 0
                or up_limit <= down_limit
              )
            """,
            [start_date, end_date],
        ).fetchone()[0]
    )
    if hard_violation_count:
        issues.append(
            f"{hard_violation_count} rows violate positivity/order invariants "
            "(up_limit > down_limit > 0) after write"
        )
    sampled = conn.execute(
        f"""
        with sampled as (
          select
            up_limit / pre_close - 1 as up_ratio,
            down_limit / pre_close - 1 as down_ratio,
            row_number() over (partition by trade_date order by stock_code) as rn
          from {TABLE_NAME}
          where trade_date >= ? and trade_date <= ?
            and pre_close is not null and pre_close > 0
        )
        select
          count(*) as sampled_count,
          sum(
            case
              when up_ratio <= 0 or up_ratio > ? then 1
              when down_ratio >= 0 or down_ratio < -? then 1
              else 0
            end
          ) as out_of_band_count
        from sampled
        where rn <= ?
        """,
        [start_date, end_date, DQ_RATIO_MAX, DQ_RATIO_MAX, max(int(ratio_sample_rows_per_date), 1)],
    ).fetchone()
    ratio_sampled_count = int(sampled[0] or 0)
    ratio_out_of_band_count = int(sampled[1] or 0)
    if ratio_out_of_band_count:
        issues.append(
            f"{ratio_out_of_band_count}/{ratio_sampled_count} sampled rows have "
            f"up/down limit ratios outside (0, {DQ_RATIO_MAX:.0%}] of pre_close"
        )
    return {
        "status": "issues_found" if issues else "passed",
        "hard_violation_count": hard_violation_count,
        "ratio_sampled_count": ratio_sampled_count,
        "ratio_out_of_band_count": ratio_out_of_band_count,
        "issues": issues,
    }


def _records_from_tabular_payload(payload: object) -> list[dict[str, object]]:
    if payload is None:
        return []
    to_dict = getattr(payload, "to_dict", None)
    if callable(to_dict):
        records = to_dict(orient="records")
        return [record for record in records if isinstance(record, dict)]
    if isinstance(payload, list):
        return [record for record in payload if isinstance(record, dict)]
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return [record for record in data if isinstance(record, dict)]
    return []


def _calendar_dates(start_text: str, end_text: str) -> list[str]:
    start = date.fromisoformat(start_text)
    end = date.fromisoformat(end_text)
    out: list[str] = []
    current = start
    while current <= end:
        out.append(current.isoformat())
        current += timedelta(days=1)
    return out


def _normalize_date_text(value: object, *, option_name: str) -> str:
    text = _normalize_compact_date(value)
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValueError(f"{option_name} must be a valid YYYY-MM-DD or YYYYMMDD date") from exc


def _normalize_compact_date(value: object) -> str:
    text = str(value or "").strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text[:10] if len(text) >= 10 else text


def _vendor_version(trade_date_compact: str, *, run_id: str) -> str:
    digest = hashlib.sha256(f"{run_id}:{trade_date_compact}".encode()).hexdigest()[:12]
    return f"vv_tushare_stk_limit_{trade_date_compact}_{digest}"


def _source_version(rows: list[dict[str, object]]) -> str:
    digest = hashlib.sha256(
        json.dumps(rows, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:12]
    return f"sv_stock_limit_price_{digest}"


def _float_or_none(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in {float("inf"), float("-inf")}:
        return None
    return number


def _positive_float_or_none(value: object) -> float | None:
    number = _float_or_none(value)
    if number is None or number <= 0:
        return None
    return number


def _count_observation_trade_dates(path: Path, dates: list[str]) -> int | None:
    """在 observation 已落地日期中统计给定日期的命中数；表缺失返回 None。"""
    conn = duckdb.connect(str(path), read_only=True)
    try:
        if not _table_exists(conn, OBSERVATION_CALENDAR_TABLE):
            return None
        placeholders = ", ".join("?" for _date in dates)
        row = conn.execute(
            f"""
            select count(distinct cast(trade_date as varchar))
            from {OBSERVATION_CALENDAR_TABLE}
            where cast(trade_date as varchar) in ({placeholders})
            """,
            dates,
        ).fetchone()
        return int(row[0] or 0)
    finally:
        conn.close()


def _table_exists(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    return (
        conn.execute(
            """
            select 1
            from information_schema.tables
            where table_schema = 'main' and table_name = ?
            limit 1
            """,
            [table_name],
        ).fetchone()
        is not None
    )
