"""stock_limit_price_daily 摄入任务合成库测试（不触网、不碰生产库）。

覆盖：schema 幂等建表、mock 客户端写入+幂等 delete+insert、行级硬校验拒绝、
写后 DQ 告警、dry-run 零调用零写入、部分日期失败的降级语义、vendor 白名单守卫。
"""

from __future__ import annotations

import re

import duckdb
import pytest

from backend.app.tasks.stock_limit_price_ingest import (
    RULE_VERSION,
    STOCK_LIMIT_PRICE_VENDOR_VERSION_PATTERNS,
    TABLE_NAME,
    StockLimitPriceUnknownVendorVersionError,
    assert_stock_limit_price_vendor_version,
    ensure_stock_limit_price_daily_schema,
    ingest_stock_limit_prices,
)


class _MockStkLimitClient:
    """list[dict] payload 的 mock vendor 客户端；可注入永久失败日期。"""

    def __init__(
        self,
        payload_by_compact_date: dict[str, list[dict[str, object]]],
        *,
        failing_compact_dates: frozenset[str] = frozenset(),
    ) -> None:
        self._payload_by_compact_date = payload_by_compact_date
        self._failing_compact_dates = failing_compact_dates
        self.calls: list[str] = []

    def stk_limit(self, *, trade_date: str, fields: str) -> list[dict[str, object]]:
        assert "up_limit" in fields and "down_limit" in fields and "pre_close" in fields
        self.calls.append(trade_date)
        if trade_date in self._failing_compact_dates:
            raise RuntimeError("synthetic vendor outage")
        return list(self._payload_by_compact_date.get(trade_date, []))


def _new_synthetic_db(tmp_path) -> str:
    db_path = tmp_path / "synthetic.duckdb"
    duckdb.connect(str(db_path)).close()
    return str(db_path)


def _fetch_all_rows(db_path: str) -> list[tuple]:
    conn = duckdb.connect(db_path, read_only=True)
    try:
        return conn.execute(
            f"""
            select trade_date, stock_code, up_limit, down_limit, pre_close,
                   vendor_version, rule_version
            from {TABLE_NAME}
            order by trade_date, stock_code
            """
        ).fetchall()
    finally:
        conn.close()


def test_ensure_schema_is_idempotent() -> None:
    conn = duckdb.connect(":memory:")
    try:
        ensure_stock_limit_price_daily_schema(conn)
        ensure_stock_limit_price_daily_schema(conn)
        columns = {
            str(row[1])
            for row in conn.execute(f"pragma table_info('{TABLE_NAME}')").fetchall()
        }
    finally:
        conn.close()
    assert {
        "trade_date",
        "stock_code",
        "up_limit",
        "down_limit",
        "pre_close",
        "source_version",
        "vendor_version",
        "rule_version",
        "run_id",
    } <= columns


def test_ingest_writes_rows_and_repeat_run_is_idempotent(tmp_path) -> None:
    db_path = _new_synthetic_db(tmp_path)
    payload = {
        "20260105": [
            {"ts_code": "000001.SZ", "trade_date": "20260105", "pre_close": 10.0, "up_limit": 11.0, "down_limit": 9.0},
            {"ts_code": "600000.SH", "trade_date": "20260105", "pre_close": 8.0, "up_limit": 8.8, "down_limit": 7.2},
        ],
        "20260106": [
            {"ts_code": "000001.SZ", "trade_date": "20260106", "pre_close": 11.0, "up_limit": 12.1, "down_limit": 9.9},
        ],
    }
    client = _MockStkLimitClient(payload)

    result = ingest_stock_limit_prices(
        duckdb_path=db_path,
        start_date="2026-01-05",
        end_date="2026-01-06",
        client=client,
        retry_sleep_seconds=0.0,
    )
    assert result["status"] == "completed"
    assert result["inserted_row_count"] == 3
    assert result["written_date_count"] == 2
    assert result["failed_dates"] == []
    assert result["dq"]["status"] == "passed"

    repeat = ingest_stock_limit_prices(
        duckdb_path=db_path,
        start_date="2026-01-05",
        end_date="2026-01-06",
        client=_MockStkLimitClient(payload),
        retry_sleep_seconds=0.0,
    )
    assert repeat["status"] == "completed"

    rows = _fetch_all_rows(db_path)
    assert len(rows) == 3
    assert rows[0][:5] == ("2026-01-05", "000001.SZ", 11.0, 9.0, 10.0)
    assert {row[6] for row in rows} == {RULE_VERSION}
    for row in rows:
        vendor_version = str(row[5])
        assert any(
            re.match(pattern, vendor_version)
            for pattern in STOCK_LIMIT_PRICE_VENDOR_VERSION_PATTERNS
        ), vendor_version


def test_ingest_rejects_invalid_rows_and_reports_dq_warnings(tmp_path) -> None:
    db_path = _new_synthetic_db(tmp_path)
    payload = {
        "20260105": [
            # 合法行
            {"ts_code": "000001.SZ", "trade_date": "20260105", "pre_close": 10.0, "up_limit": 11.0, "down_limit": 9.0},
            # up <= down：行级硬校验拒绝，不落表
            {"ts_code": "000002.SZ", "trade_date": "20260105", "pre_close": 10.0, "up_limit": 9.0, "down_limit": 11.0},
            # 非正数值：拒绝
            {"ts_code": "000003.SZ", "trade_date": "20260105", "pre_close": 10.0, "up_limit": -1.0, "down_limit": 0.0},
            # 比例越界（up/pre_close - 1 = 100% > 50%）：可落表但写后抽检告警
            {"ts_code": "000004.SZ", "trade_date": "20260105", "pre_close": 10.0, "up_limit": 20.0, "down_limit": 5.0},
        ],
    }
    result = ingest_stock_limit_prices(
        duckdb_path=db_path,
        start_date="2026-01-05",
        client=_MockStkLimitClient(payload),
        retry_sleep_seconds=0.0,
    )
    assert result["status"] == "completed_with_warnings"
    assert result["inserted_row_count"] == 2
    assert result["skipped_invalid_row_count"] == 2
    dq = result["dq"]
    assert dq["hard_violation_count"] == 0
    assert dq["ratio_out_of_band_count"] == 1
    assert dq["issues"]
    assert len(_fetch_all_rows(db_path)) == 2


def test_ingest_dry_run_calls_no_vendor_and_writes_nothing(tmp_path) -> None:
    db_path = _new_synthetic_db(tmp_path)
    client = _MockStkLimitClient({})
    result = ingest_stock_limit_prices(
        duckdb_path=db_path,
        start_date="20260105",
        end_date="20260107",
        client=client,
        dry_run=True,
    )
    assert result["status"] == "dry_run"
    assert result["requested_date_count"] == 3
    assert result["existing_row_count_in_range"] == 0
    assert result["would_call_tushare"] is True
    assert client.calls == []
    conn = duckdb.connect(db_path, read_only=True)
    try:
        tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
    finally:
        conn.close()
    assert TABLE_NAME not in tables


def test_ingest_flags_empty_response_on_landed_trade_dates(tmp_path) -> None:
    """交易日(observation 已落地)空响应记告警;非交易日空响应是正常噪音。"""
    db_path = _new_synthetic_db(tmp_path)
    conn = duckdb.connect(db_path)
    try:
        conn.execute(
            "create table choice_stock_daily_observation (trade_date varchar, stock_code varchar, close_value double)"
        )
        # 2026-01-06 是已落地交易日;2026-01-07 不是(周末/假日噪音)
        conn.execute(
            "insert into choice_stock_daily_observation values ('2026-01-06', '000001.SZ', 10.0)"
        )
    finally:
        conn.close()
    payload = {
        "20260105": [
            {"ts_code": "000001.SZ", "trade_date": "20260105", "pre_close": 10.0, "up_limit": 11.0, "down_limit": 9.0},
        ],
    }
    result = ingest_stock_limit_prices(
        duckdb_path=db_path,
        start_date="2026-01-05",
        end_date="2026-01-07",
        client=_MockStkLimitClient(payload),
        retry_sleep_seconds=0.0,
    )
    assert result["status"] == "completed_with_warnings"
    assert result["empty_date_count"] == 2
    assert result["empty_trade_date_count"] == 1
    assert any("empty stk_limit response" in issue for issue in result["dq"]["issues"])


def test_ingest_empty_dates_without_observation_calendar_stay_unflagged(tmp_path) -> None:
    db_path = _new_synthetic_db(tmp_path)
    payload = {
        "20260105": [
            {"ts_code": "000001.SZ", "trade_date": "20260105", "pre_close": 10.0, "up_limit": 11.0, "down_limit": 9.0},
        ],
    }
    result = ingest_stock_limit_prices(
        duckdb_path=db_path,
        start_date="2026-01-05",
        end_date="2026-01-06",
        client=_MockStkLimitClient(payload),
        retry_sleep_seconds=0.0,
    )
    # observation 日历不可得:仅暴露计数字段,不告警
    assert result["status"] == "completed"
    assert result["empty_date_count"] == 1
    assert result["empty_trade_date_count"] is None


def test_ingest_partial_failure_keeps_successful_dates(tmp_path) -> None:
    db_path = _new_synthetic_db(tmp_path)
    payload = {
        "20260105": [
            {"ts_code": "000001.SZ", "trade_date": "20260105", "pre_close": 10.0, "up_limit": 11.0, "down_limit": 9.0},
        ],
    }
    client = _MockStkLimitClient(payload, failing_compact_dates=frozenset({"20260106"}))
    result = ingest_stock_limit_prices(
        duckdb_path=db_path,
        start_date="2026-01-05",
        end_date="2026-01-06",
        client=client,
        retry_attempts=2,
        retry_sleep_seconds=0.0,
    )
    assert result["status"] == "partial_completed"
    assert result["failed_dates"] == ["2026-01-06"]
    assert result["inserted_row_count"] == 1
    # 重试次数生效：失败日期被调用 retry_attempts 次
    assert client.calls.count("20260106") == 2
    assert len(_fetch_all_rows(db_path)) == 1


def test_ingest_raises_when_all_dates_fail(tmp_path) -> None:
    db_path = _new_synthetic_db(tmp_path)
    client = _MockStkLimitClient({}, failing_compact_dates=frozenset({"20260105"}))
    with pytest.raises(RuntimeError, match="failed for all"):
        ingest_stock_limit_prices(
            duckdb_path=db_path,
            start_date="2026-01-05",
            client=client,
            retry_attempts=1,
            retry_sleep_seconds=0.0,
        )


def test_vendor_version_whitelist_guard() -> None:
    assert_stock_limit_price_vendor_version("vv_tushare_stk_limit_20260105_0123456789ab")
    for bad in ("", None, "vv_choice_stock_20260105_0123456789ab", "vv_tushare_stk_limit_2026"):
        with pytest.raises(StockLimitPriceUnknownVendorVersionError):
            assert_stock_limit_price_vendor_version(bad)
