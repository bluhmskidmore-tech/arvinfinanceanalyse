"""ADB 快照回退外币行的 CNY 归一（calc_rules §12.4 / §14）。

formal 表缺日回退到快照时，快照存的是原币金额：
- 外币行必须按当日 formal FX 中间价折算为 CNY 后才能并入 CNY 口径加权；
- formal FX fail-closed（§7.1），缺当日中间价的外币行必须剔除并披露，禁止原币混入；
- 人民币口径行（CNY/CNX/空）原样保留。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from backend.app.governance.settings import get_settings
from backend.app.repositories.snapshot_repo import ensure_snapshot_tables
from backend.app.services.adb_analysis_service import _load_adb_raw_data

pytestmark = [pytest.mark.integration]

FORMAL_DATE = "2026-03-02"
SNAPSHOT_DATE = "2026-03-03"
USD_MID_RATE = Decimal("7.2")


def _seed_common(conn: duckdb.DuckDBPyConnection) -> None:
    ensure_snapshot_tables(conn)
    conn.execute(
        """
        insert into fact_formal_zqtz_balance_daily (
          report_date, position_scope, currency_basis, market_value_amount,
          ytm_value, coupon_rate, asset_class, bond_type, is_issuance_like,
          source_version, rule_version
        ) values (?, 'asset', 'CNY', ?, 2.4, 2.5, '债券类', '国债', false, 'sv-formal', 'rv-formal')
        """,
        [FORMAL_DATE, Decimal("100000000")],
    )


def _insert_zqtz_snapshot_row(
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: str,
    instrument_code: str,
    currency_code: str,
    market_value_native: Decimal,
) -> None:
    conn.execute(
        """
        insert into zqtz_bond_daily_snapshot (
          report_date, instrument_code, instrument_name, currency_code,
          market_value_native, coupon_rate, ytm_value, asset_class, bond_type,
          is_issuance_like, source_version, rule_version
        ) values (?, ?, ?, ?, ?, 2.5, 2.4, '债券类', '国债', false, 'sv-snap', 'rv-snap')
        """,
        [report_date, instrument_code, instrument_code, currency_code, market_value_native],
    )


def _insert_usd_mid_rate(conn: duckdb.DuckDBPyConnection, trade_date: str) -> None:
    conn.execute(
        """
        insert into fx_daily_mid (
          trade_date, base_currency, quote_currency, mid_rate, source_name,
          is_business_day, is_carry_forward, source_version, observed_trade_date
        ) values (?, 'USD', 'CNY', ?, 'test-fx', true, false, 'sv-fx', ?)
        """,
        [trade_date, USD_MID_RATE, trade_date],
    )


def _snapshot_day_market_values(bonds_df: pd.DataFrame) -> list[float]:
    day_mask = pd.to_datetime(bonds_df["report_date"]).dt.strftime("%Y-%m-%d") == SNAPSHOT_DATE
    return sorted(float(v) for v in bonds_df.loc[day_mask, "market_value"])


def test_snapshot_fallback_converts_foreign_rows_with_daily_mid_rate(tmp_path: Path) -> None:
    db_path = tmp_path / "adb-fx-convert.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        _seed_common(conn)
        _insert_zqtz_snapshot_row(
            conn,
            report_date=SNAPSHOT_DATE,
            instrument_code="B-CNY",
            currency_code="CNY",
            market_value_native=Decimal("50000000"),
        )
        _insert_zqtz_snapshot_row(
            conn,
            report_date=SNAPSHOT_DATE,
            instrument_code="B-USD",
            currency_code="USD",
            market_value_native=Decimal("10000000"),
        )
        _insert_usd_mid_rate(conn, SNAPSHOT_DATE)
    finally:
        conn.close()

    bonds_df, _ib_df, _sv, _rv, basis, tables, fx_summary = _load_adb_raw_data(
        str(db_path), date(2026, 3, 2), date(2026, 3, 3)
    )

    assert basis == "formal+snapshot_calendar"
    assert "zqtz_bond_daily_snapshot" in tables
    # USD 行按当日中间价折算：10_000_000 * 7.2 = 72_000_000；CNY 行原样。
    assert _snapshot_day_market_values(bonds_df) == [50000000.0, 72000000.0]
    assert fx_summary["converted_rows"] == 1
    assert fx_summary["dropped_rows"] == 0
    assert fx_summary["converted_by_currency"] == {"USD": 1}


def test_snapshot_fallback_drops_foreign_rows_without_fx_and_discloses(tmp_path: Path) -> None:
    db_path = tmp_path / "adb-fx-drop.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        _seed_common(conn)
        _insert_zqtz_snapshot_row(
            conn,
            report_date=SNAPSHOT_DATE,
            instrument_code="B-CNY",
            currency_code="CNY",
            market_value_native=Decimal("50000000"),
        )
        # 中文币名走 normalize_currency_code 归一（美元 -> USD）；无当日中间价。
        _insert_zqtz_snapshot_row(
            conn,
            report_date=SNAPSHOT_DATE,
            instrument_code="B-USD-CN",
            currency_code="美元",
            market_value_native=Decimal("10000000"),
        )
    finally:
        conn.close()

    bonds_df, _ib_df, _sv, _rv, _basis, _tables, fx_summary = _load_adb_raw_data(
        str(db_path), date(2026, 3, 2), date(2026, 3, 3)
    )

    # formal FX fail-closed：缺当日中间价的外币行剔除，禁止原币金额混入 CNY 加权。
    assert _snapshot_day_market_values(bonds_df) == [50000000.0]
    assert fx_summary["converted_rows"] == 0
    assert fx_summary["dropped_rows"] == 1
    assert fx_summary["dropped_by_currency"]["USD"]["rows"] == 1
    assert fx_summary["dropped_by_currency"]["USD"]["native_amount"] == 10000000.0


def test_tyw_snapshot_fallback_converts_foreign_principal(tmp_path: Path) -> None:
    """formal TYW 表存在但无行（快照整段回退）：USD 本金按当日中间价折算。

    注意不构造 formal 行 + 快照行混合：混合时既有的 concrete-scope 过滤会把
    position_scope 为中文侧别的快照行丢弃（既有行为，与 FX 折算无关）。
    """
    db_path = tmp_path / "adb-fx-tyw.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        ensure_snapshot_tables(conn)
        conn.execute(
            """
            insert into tyw_interbank_daily_snapshot (
              report_date, position_id, product_type, position_side, currency_code,
              principal_native, funding_cost_rate, source_version, rule_version
            ) values (?, 'TYW-USD', '同业存放', '负债', 'USD', ?, 1.8, 'sv-snap', 'rv-snap')
            """,
            [SNAPSHOT_DATE, Decimal("5000000")],
        )
        _insert_usd_mid_rate(conn, SNAPSHOT_DATE)
    finally:
        conn.close()

    _bonds_df, ib_df, _sv, _rv, _basis, tables, fx_summary = _load_adb_raw_data(
        str(db_path), date(2026, 3, 2), date(2026, 3, 3)
    )

    assert "tyw_interbank_daily_snapshot" in tables
    day_mask = pd.to_datetime(ib_df["report_date"]).dt.strftime("%Y-%m-%d") == SNAPSHOT_DATE
    # USD 本金按当日中间价折算：5_000_000 * 7.2 = 36_000_000。
    assert sorted(float(v) for v in ib_df.loc[day_mask, "amount"]) == [36000000.0]
    assert fx_summary["converted_rows"] == 1
    assert fx_summary["converted_by_currency"] == {"USD": 1}


def test_cny_only_snapshot_fallback_keeps_payload_free_of_fx_disclosure(tmp_path: Path) -> None:
    db_path = tmp_path / "adb-fx-cny-only.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        _seed_common(conn)
        _insert_zqtz_snapshot_row(
            conn,
            report_date=SNAPSHOT_DATE,
            instrument_code="B-CNY",
            currency_code="CNY",
            market_value_native=Decimal("50000000"),
        )
    finally:
        conn.close()

    bonds_df, _ib_df, _sv, _rv, _basis, _tables, fx_summary = _load_adb_raw_data(
        str(db_path), date(2026, 3, 2), date(2026, 3, 3)
    )

    assert _snapshot_day_market_values(bonds_df) == [50000000.0]
    assert fx_summary["converted_rows"] == 0
    assert fx_summary["dropped_rows"] == 0


def test_comparison_envelope_discloses_snapshot_fx_conversion(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "adb-fx-envelope.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        _seed_common(conn)
        _insert_zqtz_snapshot_row(
            conn,
            report_date=SNAPSHOT_DATE,
            instrument_code="B-CNY",
            currency_code="CNY",
            market_value_native=Decimal("50000000"),
        )
        _insert_zqtz_snapshot_row(
            conn,
            report_date=SNAPSHOT_DATE,
            instrument_code="B-USD",
            currency_code="USD",
            market_value_native=Decimal("10000000"),
        )
        # USD 折算有汇率；EUR 无当日中间价 -> 剔除并披露。
        _insert_zqtz_snapshot_row(
            conn,
            report_date=SNAPSHOT_DATE,
            instrument_code="B-EUR",
            currency_code="EUR",
            market_value_native=Decimal("2000000"),
        )
        _insert_usd_mid_rate(conn, SNAPSHOT_DATE)
    finally:
        conn.close()

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    from backend.app.services import adb_analysis_service

    adb_analysis_service.clear_adb_comparison_cache()
    try:
        envelope = adb_analysis_service.adb_comparison_envelope(
            FORMAL_DATE, SNAPSHOT_DATE, top_n=10
        )
    finally:
        adb_analysis_service.clear_adb_comparison_cache()

    assert envelope["result_meta"]["fallback_mode"] == "latest_snapshot"
    disclosure = envelope["result"]["snapshot_fx_conversion"]
    assert disclosure["converted_rows"] == 1
    assert disclosure["dropped_rows"] == 1
    assert disclosure["converted_by_currency"] == {"USD": 1}
    assert disclosure["dropped_by_currency"]["EUR"]["rows"] == 1
    note = envelope["calibration"]["calibration_note"]
    assert "快照外币行已按当日中间价折算为人民币（1 行）" in note
    assert "缺当日中间价的外币快照行已剔除（1 行）" in note
