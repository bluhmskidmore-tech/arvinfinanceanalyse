from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import duckdb
import pytest

from backend.app.core_finance.macro.dual_frequency_equity import (
    build_dual_frequency_equity_snapshot,
)
from backend.app.repositories.dual_frequency_equity_repo import (
    load_dual_frequency_equity_history,
)


def _seed_full_history(path: Path) -> None:
    conn = duckdb.connect(str(path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              trade_date varchar,
              value_numeric double,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
        conn.executemany(
            """
            insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "CA.CSI300",
                    "2026-01-02",
                    100.0,
                    "index-source-v1",
                    "index-vendor-v1",
                    "index-rule-v1",
                    "ok",
                    "index:20260102T010000Z",
                ),
                (
                    "CA.CSI300",
                    "2026-01-05",
                    999.0,
                    "index-source-old",
                    "index-vendor-old",
                    "index-rule-old",
                    "ok",
                    "index:20260105T000000Z",
                ),
                (
                    "CA.CSI300",
                    "2026-01-05",
                    102.0,
                    "index-source-v2",
                    "index-vendor-v2",
                    "index-rule-v2",
                    "ok",
                    "index:20260105T010000Z",
                ),
                (
                    "CA.CSI300",
                    "2026-01-06",
                    104.0,
                    "index-source-v2",
                    "index-vendor-v2",
                    "index-rule-v2",
                    "ok",
                    "index:20260106T010000Z",
                ),
                (
                    "CA.CSI300",
                    "2026-01-07",
                    106.0,
                    "index-source-v2",
                    "index-vendor-v2",
                    "index-rule-v2",
                    "ok",
                    "index:20260107T010000Z",
                ),
                (
                    "OTHER",
                    "2026-01-07",
                    1.0,
                    "other-source",
                    "other-vendor",
                    "other-rule",
                    "ok",
                    "other:20260107T010000Z",
                ),
            ],
        )
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              amount double,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        stock_rows: list[tuple[object, ...]] = []
        for trade_date, first_amount, second_amount in [
            ("2026-01-02", 10.0, 20.0),
            ("2026-01-05", 100.0, 200.0),
            ("2026-01-06", 300.0, 400.0),
            ("2026-01-07", 500.0, 600.0),
        ]:
            stock_rows.extend(
                [
                    (
                        trade_date,
                        "000001.SZ",
                        first_amount,
                        "stock-source-v2",
                        # 消费端按 vendor 显式定标(fail-closed),夹具须用合法 native 模式
                        "vv_choice_stock_20260107_0123456789ab",
                        "stock-rule-v2",
                        f"stock:{trade_date.replace('-', '')}T010000Z",
                    ),
                    (
                        trade_date,
                        "000002.SZ",
                        second_amount,
                        "stock-source-v2",
                        # 消费端按 vendor 显式定标(fail-closed),夹具须用合法 native 模式
                        "vv_choice_stock_20260107_0123456789ab",
                        "stock-rule-v2",
                        f"stock:{trade_date.replace('-', '')}T010000Z",
                    ),
                ]
            )
        stock_rows.append(
            (
                "2026-01-05",
                "000001.SZ",
                9_999.0,
                "stock-source-old",
                "vv_choice_stock_20260105_0123456789ff",
                "stock-rule-old",
                "stock:20260105T000000Z",
            )
        )
        conn.executemany(
            """
            insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?)
            """,
            stock_rows,
        )
    finally:
        conn.close()


def _seed_cross_vendor_generation_history(path: Path) -> None:
    """Seed index + market-amount rows straddling the tushare/choice_native
    vendor boundary (docs/data_contracts.md §4.10): tushare-era amount is in
    RMB thousands, choice_native-era amount is already in RMB.
    """

    conn = duckdb.connect(str(path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              trade_date varchar,
              value_numeric double,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
        conn.executemany(
            """
            insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "CA.CSI300",
                    "2025-12-31",
                    3900.0,
                    "index-source-v1",
                    "index-vendor-v1",
                    "index-rule-v1",
                    "ok",
                    "index:20251231T010000Z",
                ),
                (
                    "CA.CSI300",
                    "2026-01-05",
                    3950.0,
                    "index-source-v2",
                    "index-vendor-v2",
                    "index-rule-v2",
                    "ok",
                    "index:20260105T010000Z",
                ),
            ],
        )
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              amount double,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        conn.executemany(
            """
            insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "2025-12-31",
                    "000001.SZ",
                    100.0,  # 千元, tushare 代际
                    "stock-source-tushare",
                    "vv_choice_tushare_stock_20251231_001",
                    "stock-rule-v1",
                    "stock:20251231T010000Z",
                ),
                (
                    "2025-12-31",
                    "000002.SZ",
                    200.0,  # 千元, tushare 代际
                    "stock-source-tushare",
                    "vv_choice_tushare_stock_20251231_001",
                    "stock-rule-v1",
                    "stock:20251231T010000Z",
                ),
                (
                    "2025-12-31",
                    "000003.SZ",
                    999_999.0,  # vendor 无法定标, 应 fail-closed 排除
                    "stock-source-unknown",
                    None,
                    "stock-rule-v1",
                    "stock:20251231T020000Z",
                ),
                (
                    "2026-01-05",
                    "000001.SZ",
                    500_000.0,  # 元, choice_native 代际
                    "stock-source-native",
                    "vv_choice_stock_20260105_001",
                    "stock-rule-v2",
                    "stock:20260105T010000Z",
                ),
                (
                    "2026-01-05",
                    "000002.SZ",
                    600_000.0,  # 元, choice_native 代际
                    "stock-source-native",
                    "vv_choice_stock_20260105_001",
                    "stock-rule-v2",
                    "stock:20260105T010000Z",
                ),
            ],
        )
    finally:
        conn.close()


def _seed_index_only(path: Path) -> None:
    conn = duckdb.connect(str(path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              trade_date varchar,
              value_numeric double,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_choice_macro_daily values
              ('CA.CSI300', '2026-01-02', 100.0, 'sv', 'vv', 'rv', 'ok', 'run-1'),
              ('CA.CSI300', '2026-01-05', 101.0, 'sv', 'vv', 'rv', 'ok', 'run-2')
            """
        )
    finally:
        conn.close()


def test_load_history_returns_bounded_ascending_rows_and_canonical_evidence(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "history.duckdb"
    _seed_full_history(duckdb_path)

    result = load_dual_frequency_equity_history(
        duckdb_path=duckdb_path,
        lookback_rows=3,
    )

    assert result["status"] == "ready"
    assert result["quality"] == "ok"
    assert result["warnings"] == []
    assert result["earliest_trade_date"] == "2026-01-05"
    assert result["latest_trade_date"] == "2026-01-07"
    assert result["effective_as_of_date"] == "2026-01-07"
    assert result["row_count"] == 3
    assert result["rows"] == [
        {"trade_date": "2026-01-05", "close": 102.0, "amount": 300.0},
        {"trade_date": "2026-01-06", "close": 104.0, "amount": 700.0},
        {"trade_date": "2026-01-07", "close": 106.0, "amount": 1_100.0},
    ]
    assert result["tables_used"] == [
        "fact_choice_macro_daily",
        "choice_stock_daily_observation",
    ]
    assert result["sources"]["index"]["source_versions"] == [
        "index-source-v2"
    ]
    amount_source = result["sources"]["market_amount"]
    assert amount_source["status"] == "ready"
    assert amount_source["quality"] == "ok"
    assert amount_source["valid_amount_observation_count"] == 6
    assert amount_source["null_amount_observation_count"] == 0
    assert amount_source["source_versions"] == ["stock-source-v2"]


def test_load_history_honors_as_of_date_before_applying_lookback(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "history.duckdb"
    _seed_full_history(duckdb_path)

    result = load_dual_frequency_equity_history(
        duckdb_path=duckdb_path,
        as_of_date="2026-01-05",
        lookback_rows=20,
    )

    assert result["status"] == "ready"
    assert result["requested_as_of_date"] == "2026-01-05"
    assert [row["trade_date"] for row in result["rows"]] == [
        "2026-01-02",
        "2026-01-05",
    ]
    assert result["latest_trade_date"] == "2026-01-05"


def test_load_history_missing_database_is_unavailable_without_creating_file(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "missing.duckdb"

    result = load_dual_frequency_equity_history(duckdb_path=duckdb_path)

    assert result["status"] == "unavailable"
    assert result["quality"] == "unavailable"
    assert result["rows"] == []
    assert result["tables_used"] == []
    assert result["warnings"] == ["missing_database"]
    assert not duckdb_path.exists()


def test_load_history_missing_index_table_is_unavailable(tmp_path: Path) -> None:
    duckdb_path = tmp_path / "empty.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    conn.execute("create table unrelated_table (value integer)")
    conn.close()

    result = load_dual_frequency_equity_history(duckdb_path=duckdb_path)

    assert result["status"] == "unavailable"
    assert result["rows"] == []
    assert result["warnings"] == ["missing_table:fact_choice_macro_daily"]


def test_load_history_missing_market_amount_table_keeps_index_rows_partial(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "index-only.duckdb"
    _seed_index_only(duckdb_path)

    result = load_dual_frequency_equity_history(duckdb_path=duckdb_path)

    assert result["status"] == "partial"
    assert result["quality"] == "degraded"
    assert result["rows"] == [
        {"trade_date": "2026-01-02", "close": 100.0, "amount": None},
        {"trade_date": "2026-01-05", "close": 101.0, "amount": None},
    ]
    assert result["tables_used"] == ["fact_choice_macro_daily"]
    assert "missing_table:choice_stock_daily_observation" in result["warnings"]
    assert "market_amount_missing_dates" in result["warnings"]
    assert result["sources"]["market_amount"]["missing_trade_date_count"] == 2


def test_load_history_missing_amount_column_keeps_index_rows_partial(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "missing-amount.duckdb"
    _seed_index_only(duckdb_path)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    conn.execute(
        """
        create table choice_stock_daily_observation (
          trade_date varchar,
          stock_code varchar
        )
        """
    )
    conn.execute(
        "insert into choice_stock_daily_observation values ('2026-01-02', '000001.SZ')"
    )
    conn.close()

    result = load_dual_frequency_equity_history(duckdb_path=duckdb_path)

    assert result["status"] == "partial"
    assert all(row["amount"] is None for row in result["rows"])
    assert (
        "missing_columns:choice_stock_daily_observation:amount"
        in result["warnings"]
    )
    assert "choice_stock_daily_observation" not in result["tables_used"]


def test_load_history_missing_stock_code_fails_closed_without_aggregating_amount(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "missing-stock-code.duckdb"
    _seed_index_only(duckdb_path)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    conn.execute(
        """
        create table choice_stock_daily_observation (
          trade_date varchar,
          amount double,
          source_version varchar,
          vendor_version varchar,
          rule_version varchar,
          run_id varchar
        )
        """
    )
    conn.executemany(
        """
        insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?)
        """,
        [
            ("2026-01-02", 10.0, "sv-old", "vv-old", "rv", "run-1"),
            ("2026-01-02", 999.0, "sv-new", "vv-new", "rv", "run-2"),
        ],
    )
    conn.close()

    result = load_dual_frequency_equity_history(duckdb_path=duckdb_path)

    assert result["status"] == "partial"
    assert result["quality"] == "degraded"
    assert result["rows"] == [
        {"trade_date": "2026-01-02", "close": 100.0, "amount": None},
        {"trade_date": "2026-01-05", "close": 101.0, "amount": None},
    ]
    assert (
        "missing_columns:choice_stock_daily_observation:stock_code"
        in result["warnings"]
    )
    assert "market_amount_missing_dates" in result["warnings"]
    assert "choice_stock_daily_observation" not in result["tables_used"]
    amount_source = result["sources"]["market_amount"]
    assert amount_source["status"] == "unavailable"
    assert amount_source["quality"] == "unavailable"
    assert amount_source["date_count"] == 0
    assert amount_source["valid_amount_observation_count"] == 0
    assert amount_source["missing_trade_date_count"] == 2


def test_load_history_exposes_null_amount_coverage_without_zero_fallback(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "null-amount.duckdb"
    _seed_index_only(duckdb_path)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    conn.execute(
        """
        create table choice_stock_daily_observation (
          trade_date varchar,
          stock_code varchar,
          amount double,
          source_version varchar,
          vendor_version varchar,
          rule_version varchar,
          run_id varchar
        )
        """
    )
    conn.executemany(
        """
        insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("2026-01-02", "000001.SZ", 10.0, "sv", "vv_choice_stock_20260102_0123456789ab", "rv", "run-1"),
            ("2026-01-02", "000002.SZ", None, "sv", "vv_choice_stock_20260102_0123456789ab", "rv", "run-1"),
        ],
    )
    conn.close()

    result = load_dual_frequency_equity_history(duckdb_path=duckdb_path)

    assert result["status"] == "partial"
    assert result["rows"] == [
        {"trade_date": "2026-01-02", "close": 100.0, "amount": 10.0},
        {"trade_date": "2026-01-05", "close": 101.0, "amount": None},
    ]
    amount_source = result["sources"]["market_amount"]
    assert amount_source["status"] == "ready"
    assert amount_source["quality"] == "degraded"
    assert amount_source["valid_amount_observation_count"] == 1
    assert amount_source["null_amount_observation_count"] == 1
    assert "market_amount_null_values_ignored" in result["warnings"]
    assert "market_amount_missing_dates" in result["warnings"]
    assert amount_source["missing_trade_date_count"] == 1


def test_load_history_normalizes_amount_across_vendor_generation_boundary(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "cross-vendor.duckdb"
    _seed_cross_vendor_generation_history(duckdb_path)

    result = load_dual_frequency_equity_history(duckdb_path=duckdb_path)

    assert result["rows"] == [
        {"trade_date": "2025-12-31", "close": 3900.0, "amount": 300_000.0},
        {"trade_date": "2026-01-05", "close": 3950.0, "amount": 1_100_000.0},
    ]

    amount_source = result["sources"]["market_amount"]
    assert amount_source["unit_normalization"] == "applied_via_vendor_generation"
    assert amount_source["scale_unknown_row_count"] == 1
    assert "market_amount_vendor_unscalable_rows_ignored" in result["warnings"]


def test_load_history_fails_closed_to_null_amount_when_vendor_version_column_missing(
    tmp_path: Path,
) -> None:
    duckdb_path = tmp_path / "no-vendor-column.duckdb"
    _seed_index_only(duckdb_path)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    conn.execute(
        """
        create table choice_stock_daily_observation (
          trade_date varchar,
          stock_code varchar,
          amount double,
          source_version varchar,
          rule_version varchar,
          run_id varchar
        )
        """
    )
    conn.executemany(
        """
        insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?)
        """,
        [
            ("2026-01-02", "000001.SZ", 100.0, "sv", "rv", "run-1"),
            ("2026-01-05", "000001.SZ", 200.0, "sv", "rv", "run-2"),
        ],
    )
    conn.close()

    result = load_dual_frequency_equity_history(duckdb_path=duckdb_path)

    assert result["rows"] == [
        {"trade_date": "2026-01-02", "close": 100.0, "amount": None},
        {"trade_date": "2026-01-05", "close": 101.0, "amount": None},
    ]
    amount_source = result["sources"]["market_amount"]
    assert amount_source["unit_normalization"] == "skipped_vendor_version_column_missing"
    assert amount_source["unit"] == "source_native_unit_unconfirmed"
    assert (
        "missing_evidence_columns:choice_stock_daily_observation:vendor_version"
        in result["warnings"]
    )
    # 单位归一化被跳过必须有专用告警,监控上与"仅缺证据列"区分严重度。
    assert "market_amount_unit_normalization_skipped" in result["warnings"]
    # fail-closed: 缺列时 amount 全 NULL,下游会剔除这些行(数据不足而非误判)。
    assert "market_amount_null_values_ignored" in result["warnings"]
    assert "market_amount_missing_dates" in result["warnings"]
    assert amount_source["missing_trade_date_count"] == 2


_REGRESSION_TUSHARE_DAYS = [
    date(2025, 11, 2) + timedelta(days=offset) for offset in range(60)
]
_REGRESSION_NATIVE_DAY = date(2026, 1, 5)


def _seed_cross_vendor_attack_regression_history(path: Path) -> None:
    """61 个观察日复刻审计场景(tmp-audit-mixed-units.md §5.4):

    - 60 天 tushare 代际:每天 2 只股票、各 500_000 千元 -> 全市场 1e9 元/日;
    - 2026-01-05 choice_native 代际:每只 650_000_000 元 -> 全市场 1.3e9 元。

    归一化后 2026-01-05 的 20 日量比约 1.28(defense);若把原始 amount 直接
    sum(千元与元混算),量比虚高到约 19.7,状态机会产生假 attack。
    """

    conn = duckdb.connect(str(path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              trade_date varchar,
              value_numeric double,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
        index_rows: list[tuple[object, ...]] = []
        for trade_day in _REGRESSION_TUSHARE_DAYS:
            index_rows.append(
                (
                    "CA.CSI300",
                    trade_day.isoformat(),
                    3900.0,
                    "index-source-v1",
                    "index-vendor-v1",
                    "index-rule-v1",
                    "ok",
                    f"index:{trade_day.strftime('%Y%m%d')}T010000Z",
                )
            )
        index_rows.append(
            (
                "CA.CSI300",
                _REGRESSION_NATIVE_DAY.isoformat(),
                3905.0,  # 20 日新高;5 日回报 0.13% 不满足 thrust 条件
                "index-source-v2",
                "index-vendor-v2",
                "index-rule-v2",
                "ok",
                "index:20260105T010000Z",
            )
        )
        conn.executemany(
            "insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?)",
            index_rows,
        )
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              amount double,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        stock_rows: list[tuple[object, ...]] = []
        for trade_day in _REGRESSION_TUSHARE_DAYS:
            run_id = f"stock:{trade_day.strftime('%Y%m%d')}T010000Z"
            for stock_code in ("000001.SZ", "000002.SZ"):
                stock_rows.append(
                    (
                        trade_day.isoformat(),
                        stock_code,
                        500_000.0,  # 千元, tushare 代际
                        "stock-source-tushare",
                        f"vv_choice_tushare_stock_{trade_day.strftime('%Y%m%d')}_001",
                        "stock-rule-v1",
                        run_id,
                    )
                )
        for stock_code in ("000001.SZ", "000002.SZ"):
            stock_rows.append(
                (
                    _REGRESSION_NATIVE_DAY.isoformat(),
                    stock_code,
                    650_000_000.0,  # 元, choice_native 代际
                    "stock-source-native",
                    "vv_choice_stock_20260105_001",
                    "stock-rule-v2",
                    "stock:20260105T010000Z",
                )
            )
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?)",
            stock_rows,
        )
    finally:
        conn.close()


def test_cross_vendor_boundary_does_not_fake_attack_on_2026_01_05(
    tmp_path: Path,
) -> None:
    """审计回归:2026-01-05(vendor 代际切换首日)不得因单位混算进入假 attack。"""

    duckdb_path = tmp_path / "attack-regression.duckdb"
    _seed_cross_vendor_attack_regression_history(duckdb_path)

    history = load_dual_frequency_equity_history(
        duckdb_path=duckdb_path,
        as_of_date=_REGRESSION_NATIVE_DAY,
    )

    assert history["row_count"] == 61
    assert history["rows"][0]["amount"] == 1_000_000_000.0
    assert history["rows"][-1] == {
        "trade_date": "2026-01-05",
        "close": 3905.0,
        "amount": 1_300_000_000.0,
    }

    snapshot = build_dual_frequency_equity_snapshot(
        daily_rows=history["rows"],
        slow_cap=1.0,
        as_of_date=_REGRESSION_NATIVE_DAY,
    )
    fast = snapshot["fast"]
    assert fast["status"] == "ready"
    assert fast["state"] == "defense"
    assert fast["last_transition"] is None
    assert [
        event for event in snapshot["events"] if event.get("event") == "enter_attack"
    ] == []
    # 归一化后量比 1.3e9 / ((19*1e9 + 1.3e9)/20) ~= 1.28,远低于 1.5 阈值
    # (快照指标按 8 位小数舍入,容差取 1e-6)
    assert fast["latest_metrics"]["amount_ratio_20"] == pytest.approx(
        1.3e9 / ((19 * 1.0e9 + 1.3e9) / 20), rel=1e-6
    )

    # 辨别力对照:同一场景若直接 sum 原始 amount(千元与元混算),
    # 量比虚高到约 19.7 并触发假 attack。该分支证明本测试能抓住回归。
    mixed_unit_rows = [
        {"trade_date": trade_day.isoformat(), "close": 3900.0, "amount": 1_000_000.0}
        for trade_day in _REGRESSION_TUSHARE_DAYS
    ]
    mixed_unit_rows.append(
        {"trade_date": "2026-01-05", "close": 3905.0, "amount": 1_300_000_000.0}
    )
    buggy_snapshot = build_dual_frequency_equity_snapshot(
        daily_rows=mixed_unit_rows,
        slow_cap=1.0,
        as_of_date=_REGRESSION_NATIVE_DAY,
    )
    assert buggy_snapshot["fast"]["state"] == "attack"
    assert buggy_snapshot["fast"]["latest_metrics"]["amount_ratio_20"] > 19.0
