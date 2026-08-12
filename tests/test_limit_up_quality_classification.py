"""Golden samples for the limit-up seal/break classification (market gate condition 4).

Covers the board bands (main / ChiNext / STAR / Beijing / ST), the vendor flag
semantics (是 / 否 / blank / legacy numeric payload), the out-of-band guard for
rows that no board band governs, and the three-state
``limit_up_quality_ok`` contract. Also pins the end-to-end materialize path
where ST names come from ``choice_stock_universe``.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb

from backend.app.core_finance.market_breadth import (
    LIMIT_RATIO_BEIJING,
    LIMIT_RATIO_GROWTH_BOARD,
    LIMIT_RATIO_MAIN_BOARD,
    LIMIT_RATIO_MAIN_BOARD_ST,
    LIMIT_TOUCH_BROKEN,
    LIMIT_TOUCH_NO_TOUCH,
    LIMIT_TOUCH_OUT_OF_BAND,
    LIMIT_TOUCH_SEALED,
    LIMIT_TOUCH_UNCLASSIFIED,
    LimitUpObservation,
    MarketBreadthDaily,
    classify_limit_touch,
    compute_limit_up_quality_ok,
    derive_limit_up_price,
    derive_previous_close,
    is_st_name,
    resolve_limit_ratio,
    summarize_limit_up_day,
)
from backend.app.tasks.market_breadth_materialize import materialize_market_breadth_daily

# ---------------------------------------------------------------------------
# board bands
# ---------------------------------------------------------------------------


def test_board_bands_by_stock_code() -> None:
    assert resolve_limit_ratio("600000.SH") == LIMIT_RATIO_MAIN_BOARD
    assert resolve_limit_ratio("000001.SZ") == LIMIT_RATIO_MAIN_BOARD
    assert resolve_limit_ratio("300750.SZ") == LIMIT_RATIO_GROWTH_BOARD
    assert resolve_limit_ratio("301707.SZ") == LIMIT_RATIO_GROWTH_BOARD
    assert resolve_limit_ratio("688981.SH") == LIMIT_RATIO_GROWTH_BOARD
    assert resolve_limit_ratio("689009.SH") == LIMIT_RATIO_GROWTH_BOARD
    assert resolve_limit_ratio("830799.BJ") == LIMIT_RATIO_BEIJING
    assert resolve_limit_ratio("430139.BJ") == LIMIT_RATIO_BEIJING
    assert resolve_limit_ratio("920002.BJ") == LIMIT_RATIO_BEIJING
    # Unusable code -> no band, the row cannot be classified.
    assert resolve_limit_ratio("") is None
    assert resolve_limit_ratio("N/A") is None


def test_main_board_st_band_and_growth_board_st_exemption() -> None:
    assert is_st_name("*ST帅电") is True
    assert is_st_name("ST美克") is True
    assert is_st_name("贵州茅台") is False
    # A mid-name ST must not halve a normal stock's band.
    assert is_st_name("科大讯TEST") is False

    assert resolve_limit_ratio("600107.SH", stock_name="*ST尔雅") == LIMIT_RATIO_MAIN_BOARD_ST
    # ChiNext / STAR ST names keep the 20% board cap.
    assert resolve_limit_ratio("300156.SZ", stock_name="*ST环球") == LIMIT_RATIO_GROWTH_BOARD
    assert resolve_limit_ratio("688158.SH", stock_name="ST虹软") == LIMIT_RATIO_GROWTH_BOARD


def test_st_band_is_dropped_when_the_row_moves_wider_than_it() -> None:
    """Vendor name snapshots lag 摘帽, so a wider move proves the ST cap is gone."""
    assert (
        resolve_limit_ratio("600337.SH", stock_name="ST美克", pctchange=4.8)
        == LIMIT_RATIO_MAIN_BOARD_ST
    )
    assert (
        resolve_limit_ratio("600337.SH", stock_name="ST美克", pctchange=9.8859)
        == LIMIT_RATIO_MAIN_BOARD
    )
    assert (
        resolve_limit_ratio("600337.SH", stock_name="ST美克", pctchange=-9.9)
        == LIMIT_RATIO_MAIN_BOARD
    )


def test_limit_price_is_rounded_half_up_to_a_tick() -> None:
    assert derive_previous_close(11.0, 10.0) == 10.0
    # 4.15 * 1.10 = 4.565 -> 4.57 (half-up, not banker's rounding)
    assert derive_limit_up_price(4.15, LIMIT_RATIO_MAIN_BOARD) == 4.57
    assert derive_limit_up_price(10.0, LIMIT_RATIO_MAIN_BOARD) == 11.0
    assert derive_limit_up_price(10.0, LIMIT_RATIO_GROWTH_BOARD) == 12.0
    assert derive_limit_up_price(10.0, LIMIT_RATIO_BEIJING) == 13.0
    assert derive_limit_up_price(10.0, LIMIT_RATIO_MAIN_BOARD_ST) == 10.5


# ---------------------------------------------------------------------------
# per-row classification
# ---------------------------------------------------------------------------


def _observation(
    stock_code: str,
    *,
    limit_flag: str | None = "否",
    pctchange: float | None = None,
    close_value: float | None = None,
    high_value: float | None = None,
    stock_name: str | None = None,
) -> LimitUpObservation:
    return LimitUpObservation(
        stock_code=stock_code,
        limit_flag=limit_flag,
        pctchange=pctchange,
        close_value=close_value,
        high_value=high_value,
        stock_name=stock_name,
    )


def test_sealed_comes_from_the_vendor_flag() -> None:
    sealed = _observation(
        "600000.SH", limit_flag="是", pctchange=10.0, close_value=11.0, high_value=11.0
    )
    assert classify_limit_touch(sealed) == LIMIT_TOUCH_SEALED


def test_broken_board_on_each_board_band() -> None:
    # Main board: prev_close 10.00 -> limit 11.00, touched intraday, closed lower.
    main = _observation(
        "600000.SH", pctchange=5.0, close_value=10.5, high_value=11.0
    )
    assert classify_limit_touch(main) == LIMIT_TOUCH_BROKEN

    # ChiNext 20%: prev_close 10.00 -> limit 12.00.
    growth = _observation("300750.SZ", pctchange=5.0, close_value=10.5, high_value=12.0)
    assert classify_limit_touch(growth) == LIMIT_TOUCH_BROKEN
    assert classify_limit_touch(
        _observation("300750.SZ", pctchange=5.0, close_value=10.5, high_value=11.0)
    ) == LIMIT_TOUCH_NO_TOUCH

    # Beijing 30%: prev_close 10.00 -> limit 13.00.
    beijing = _observation("830799.BJ", pctchange=5.0, close_value=10.5, high_value=13.0)
    assert classify_limit_touch(beijing) == LIMIT_TOUCH_BROKEN
    assert classify_limit_touch(
        _observation("830799.BJ", pctchange=5.0, close_value=10.5, high_value=12.0)
    ) == LIMIT_TOUCH_NO_TOUCH

    # Main-board ST 5%: prev_close 10.00 -> limit 10.50.
    st = _observation(
        "600107.SH", pctchange=2.0, close_value=10.2, high_value=10.5, stock_name="*ST尔雅"
    )
    assert classify_limit_touch(st) == LIMIT_TOUCH_BROKEN
    assert classify_limit_touch(
        _observation(
            "600107.SH", pctchange=2.0, close_value=10.2, high_value=10.4, stock_name="*ST尔雅"
        )
    ) == LIMIT_TOUCH_NO_TOUCH


def test_blank_flag_is_not_sealed_but_still_derivable() -> None:
    """A blank Choice flag means "no limit regime reported", never "sealed"."""
    at_limit = _observation(
        "600000.SH", limit_flag="", pctchange=10.0, close_value=11.0, high_value=11.0
    )
    assert classify_limit_touch(at_limit) == LIMIT_TOUCH_BROKEN
    below = _observation(
        "600000.SH", limit_flag=None, pctchange=-3.47, close_value=28.09, high_value=28.75
    )
    assert classify_limit_touch(below) == LIMIT_TOUCH_NO_TOUCH


def test_missing_pctchange_or_high_cannot_be_classified() -> None:
    assert (
        classify_limit_touch(_observation("600000.SH", close_value=10.0, high_value=11.0))
        == LIMIT_TOUCH_UNCLASSIFIED
    )
    assert (
        classify_limit_touch(_observation("600000.SH", pctchange=5.0, close_value=10.5))
        == LIMIT_TOUCH_UNCLASSIFIED
    )
    # A suspended row keeps its sealed flag authoritative even without pctchange.
    assert (
        classify_limit_touch(_observation("600000.SH", limit_flag="是", close_value=10.0))
        == LIMIT_TOUCH_SEALED
    )


def test_legacy_numeric_flag_payload_is_unclassified() -> None:
    """Pre-2026 landings put Tushare prices in the flag column; flag semantics do not apply."""
    assert (
        classify_limit_touch(
            _observation(
                "600000.SH",
                limit_flag="11.00",
                pctchange=10.0,
                close_value=11.0,
                high_value=11.0,
            )
        )
        == LIMIT_TOUCH_UNCLASSIFIED
    )


def test_row_outside_its_board_band_is_reported_not_counted_as_broken() -> None:
    """A first-day new listing has no cap, so its high must not read as a broken board."""
    new_listing = _observation(
        "688828.SH", pctchange=419.4628, close_value=110.23, high_value=118.0
    )
    assert classify_limit_touch(new_listing) == LIMIT_TOUCH_OUT_OF_BAND

    summary = summarize_limit_up_day([new_listing])
    assert summary.out_of_band_count == 1
    assert summary.broken_count == 0


# ---------------------------------------------------------------------------
# day summary + three-state quality
# ---------------------------------------------------------------------------


def _quality(sealed: int, broken: int) -> bool | None:
    return compute_limit_up_quality_ok(
        MarketBreadthDaily(
            trade_date=date(2026, 8, 11),
            advancing_count=0,
            declining_count=0,
            limit_up_sealed_count=sealed,
            limit_up_broken_count=broken,
        )
    )


def test_day_summary_counts_every_outcome_and_keeps_contradictions_visible() -> None:
    observations = [
        # sealed and consistent with the derivation
        _observation("600000.SH", limit_flag="是", pctchange=10.0, close_value=11.0, high_value=11.0),
        # sealed while the derivation disagrees -> must surface as evidence
        _observation("600001.SH", limit_flag="是", pctchange=3.0, close_value=10.3, high_value=10.3),
        # broken board
        _observation("600002.SH", pctchange=5.0, close_value=10.5, high_value=11.0),
        # quiet row
        _observation("600003.SH", pctchange=1.0, close_value=10.1, high_value=10.2),
        # blank flag, quiet
        _observation("600004.SH", limit_flag="", pctchange=1.0, close_value=10.1, high_value=10.2),
        # outside any band
        _observation("688828.SH", pctchange=419.4628, close_value=110.23, high_value=118.0),
        # legacy numeric payload
        _observation("600005.SH", limit_flag="11.00", pctchange=1.0, close_value=10.1, high_value=10.2),
        # missing pctchange
        _observation("600006.SH", close_value=10.0, high_value=10.0),
    ]
    summary = summarize_limit_up_day(observations)

    assert summary.sealed_count == 2
    assert summary.broken_count == 1
    assert summary.no_touch_count == 2
    assert summary.out_of_band_count == 1
    assert summary.unclassified_count == 2
    assert summary.absent_flag_count == 1
    assert summary.sealed_without_derived_touch_count == 1
    assert summary.evaluable is True


def test_day_without_any_flag_basis_is_not_evaluable() -> None:
    summary = summarize_limit_up_day(
        [
            _observation(
                "600000.SH", limit_flag="11.00", pctchange=1.0, close_value=10.1, high_value=10.2
            )
        ]
    )
    assert summary.evaluable is False
    assert summary.unclassified_count == 1


def test_quality_is_three_state() -> None:
    assert _quality(60, 35) is True
    assert _quality(102, 143) is False
    assert _quality(5, 5) is False
    assert _quality(0, 0) is None


# ---------------------------------------------------------------------------
# materialize path: ST names resolved from the universe snapshot
# ---------------------------------------------------------------------------


def _seed_st_scenario(duckdb_path: Path) -> None:
    """Five trade dates; the last one has one ST board and one ChiNext board."""
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table if not exists choice_stock_daily_observation (
              trade_date varchar, stock_code varchar, open_value double, high_value double,
              low_value double, close_value double, volume double, amount double,
              pctchange double, turn double, amplitude double, tradestatus varchar,
              highlimit varchar, lowlimit varchar, field_keys_json varchar,
              source_version varchar, vendor_version varchar, rule_version varchar, run_id varchar
            )
            """
        )
        conn.execute(
            """
            create table if not exists choice_stock_universe (
              as_of_date varchar, stock_code varchar, stock_name varchar, field_key varchar,
              source_version varchar, vendor_version varchar, rule_version varchar, run_id varchar
            )
            """
        )
        rows: list[tuple[object, ...]] = []

        def add(trade_date: str, code: str, pct: float, close: float, high: float, flag: str) -> None:
            rows.append(
                (
                    trade_date, code, close, high, close, close, 1000.0, 10000.0,
                    pct, 1.0, 2.0, "正常交易", flag, "否", "[]",
                    "sv_test", "vv_test", "rv_test", "run_test",
                )
            )

        trade_dates = ["2026-08-05", "2026-08-06", "2026-08-07", "2026-08-10", "2026-08-11"]
        for trade_date in trade_dates:
            add(trade_date, "600001.SH", 1.0, 10.1, 10.2, "否")
            add(trade_date, "600107.SH", 1.0, 10.1, 10.2, "否")
            add(trade_date, "300750.SZ", 1.0, 10.1, 10.2, "否")
        # 2026-08-11: main-board ST breaks its 5% board, ChiNext seals its 20% board.
        rows = [row for row in rows if not (row[0] == "2026-08-11" and row[1] != "600001.SH")]
        add("2026-08-11", "600107.SH", 2.0, 10.2, 10.5, "否")
        add("2026-08-11", "300750.SZ", 20.0, 12.0, 12.0, "是")

        conn.executemany(
            "insert into choice_stock_daily_observation values "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.executemany(
            "insert into choice_stock_universe values (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-08-01", "600001.SH", "浦发银行", "fk", "sv", "vv", "rv", "run"),
                ("2026-08-01", "600107.SH", "*ST尔雅", "fk", "sv", "vv", "rv", "run"),
                ("2026-08-01", "300750.SZ", "宁德时代", "fk", "sv", "vv", "rv", "run"),
            ],
        )
    finally:
        conn.close()


def test_materialize_uses_universe_names_for_the_st_band(tmp_path: Path) -> None:
    db = tmp_path / "moss.duckdb"
    _seed_st_scenario(db)

    result = materialize_market_breadth_daily(
        duckdb_path=str(db),
        as_of_date=date(2026, 8, 11),
        lookback_days=30,
        min_observations_per_day=1,
    )

    assert result["status"] == "completed"
    assert result["limit_up_st_name_source"] == "choice_stock_universe"
    assert result["limit_up_st_named_count"] == 1
    # ST board broken at 5% (10.00 -> 10.50), ChiNext board sealed by flag.
    assert result["limit_up_sealed_count"] == 1
    assert result["limit_up_broken_count"] == 1
    assert result["limit_up_quality_available"] is True

    conn = duckdb.connect(str(db), read_only=True)
    try:
        supplement = conn.execute(
            "select limit_up_quality_ok from fact_livermore_gate_supplement_daily "
            "where trade_date = '2026-08-11'"
        ).fetchone()
    finally:
        conn.close()
    # sealed 1 == broken 1 -> a tie is not positive.
    assert supplement == (False,)
