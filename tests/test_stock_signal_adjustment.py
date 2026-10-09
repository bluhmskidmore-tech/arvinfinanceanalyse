"""Synthetic price-history and factor/fusion geometry dependency regressions.

Strategy admission upgrades, request-plan changes, factor rule gating and
walk-forward behavior from the live stock line are outside this public join.
"""
from __future__ import annotations

import json
import socket
from datetime import date, timedelta

import duckdb
import pytest

from backend.app.core_finance.adjusted_returns import signal_price_history
from backend.app.repositories.choice_stock_adapter import (
    stock_daily_price_basis,
    stock_daily_price_basis_evidence,
)
from backend.app.services import market_data_livermore_service as service

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_livermore]

RAW_VENDOR = "vv_choice_tushare_stock_20251231_0123456789ab"
NATIVE_VENDOR = "vv_choice_stock_20260630_0123456789ab"
CODE = "600000.SH"
AS_OF = "2025-12-31"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def deny(*args, **kwargs):
        pytest.fail("Price-history regressions must not access a provider or network")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)


def _dates(count: int, *, end: str = AS_OF) -> list[str]:
    anchor = date.fromisoformat(end)
    return [(anchor - timedelta(days=count - 1 - index)).isoformat() for index in range(count)]


def _history(raw: list[float], factors: list[float], *, dates: list[str] | None = None):
    days = dates or _dates(len(raw))
    return signal_price_history(raw_prices=raw, trade_dates=days, price_bases=["raw"] * len(raw),
                                factor_rows=list(zip(days, factors, strict=True)), signal_date=days[-1])


def test_no_corporate_action_leaves_the_entire_price_window_unchanged():
    raw = [10.0, 10.4, 10.2, 10.6]
    actual = _history(raw, [3.0] * len(raw))
    assert actual.unavailable_reason == ""
    assert list(actual.closes) == raw
    assert actual.closes[-1] == actual.raw_closes[-1]


@pytest.mark.parametrize("bad_factor", [0.0, -1.0, float("nan"), float("inf"), None, True, "invalid"])
def test_any_bad_factor_blocks_the_full_window(bad_factor):
    result = _history([10.0] * 4, [1.0, bad_factor, 1.0, 1.0])
    assert result.closes == ()
    assert result.unavailable_reason == "adjustment_factor_nonpositive_or_nonfinite"


@pytest.mark.parametrize("bad_price", [0.0, -1.0, float("nan"), float("inf"), None, True, "invalid"])
def test_any_bad_raw_price_blocks_the_full_window(bad_price):
    result = _history([10.0, bad_price, 10.0], [1.0] * 3)
    assert result.closes == ()
    assert result.unavailable_reason == "raw_price_nonpositive_or_nonfinite"


def test_missing_duplicate_and_future_factors_are_not_filled_or_ignored():
    days = _dates(3)
    kwargs = dict(raw_prices=[10.0] * 3, trade_dates=days, price_bases=["raw"] * 3, signal_date=AS_OF)
    missing = signal_price_history(**kwargs, factor_rows=[(days[0], 1.0), (days[2], 1.0)])
    duplicate = signal_price_history(**kwargs, factor_rows=[(day, 1.0) for day in days] + [(days[1], 1.0)])
    future = signal_price_history(**kwargs, factor_rows=[(day, 1.0) for day in days] + [("2026-01-01", 2.0)])
    assert missing.unavailable_reason == "adjustment_factor_missing"
    assert duplicate.unavailable_reason == "adjustment_factor_duplicate"
    assert future.unavailable_reason == "adjustment_factor_after_signal_date"


@pytest.mark.parametrize("days", [["2025-12-30", "2025-12-30"], ["2025-12-31", "2025-12-30"],
                                 ["2025-12-29", "2025-12-30"], ["bad", "2025-12-31"]])
def test_dates_must_be_ordered_unique_and_end_on_the_signal_date(days):
    result = signal_price_history(raw_prices=[10.0, 10.0], trade_dates=days, price_bases=["raw", "raw"],
                                  factor_rows=[], signal_date=AS_OF)
    assert result.unavailable_reason == "price_window_date_invalid"


def _native_audit(flag=1):
    return dict(input_family="stock_ohlcv", field_key="daily_ohlcv_amount", status="completed",
                source_version="sv_prices", call="csd", vendor_indicator="OPEN,HIGH,LOW,CLOSE,AMOUNT,VOLUME",
                request_options_json=json.dumps({"AdjustFlag": flag}),
                request_arguments_json=json.dumps([CODE, "OPEN,HIGH,LOW,CLOSE,AMOUNT,VOLUME", "2026-01-01", "2026-06-30"]))


def test_native_rows_require_their_historical_request_raw_price_evidence():
    kwargs = dict(vendor_version=NATIVE_VENDOR, stock_code=CODE, trade_date="2026-06-30", source_version="sv_prices")
    assert stock_daily_price_basis(**kwargs, request_audits=[_native_audit()]) == "raw"
    for audits in ([], [_native_audit(2)], [_native_audit(3)], [_native_audit(), _native_audit()]):
        assert stock_daily_price_basis(**kwargs, request_audits=audits) == "unconfirmed"
    audit = _native_audit()
    audit["request_options_json"] = "{}"
    assert stock_daily_price_basis(**kwargs, request_audits=[audit]) == "unconfirmed"


def test_unknown_or_mixed_price_basis_is_unavailable_even_with_complete_factors():
    days = _dates(3)
    result = signal_price_history(raw_prices=[10.0] * 3, trade_dates=days,
                                  price_bases=["raw", "unconfirmed", "raw"],
                                  factor_rows=[(day, 1.0) for day in days], signal_date=AS_OF)
    assert result.unavailable_reason == "price_basis_unconfirmed_or_mixed"


def _seed(path, *, split_on_signal_day=False):
    conn = duckdb.connect(str(path))
    service_schema = "backend/app/schema_registry/duckdb/21_choice_stock.sql"
    from pathlib import Path

    from backend.app.schema_registry.duckdb_loader import parse_registry_sql_text
    for statement in parse_registry_sql_text(Path(service_schema).read_text(encoding="utf-8")):
        conn.execute(statement)
    conn.execute("create table stock_adjustment_factor (stock_code varchar, trade_date varchar, adj_factor double, source_version varchar, run_id varchar)")
    days = _dates(130)
    rows = []
    factors = []
    for index, day in enumerate(days):
        factor = 2.0 if (index == 129 if split_on_signal_day else index >= 65) else 1.0
        wealth_close = 10.0 + index * 0.02
        raw_close = wealth_close / factor
        rows.append((day, CODE, raw_close - 0.03, raw_close + 0.01, raw_close - 0.05, raw_close,
                     100.0, 1000.0, 0.1, 2.0, 1.0, "Trading", str(raw_close * 1.1), str(raw_close * 0.9),
                     "[]", "sv_prices", RAW_VENDOR, "rule", "run"))
        factors.append((CODE, day, factor, "sv_adjustment", "factor_run"))
    conn.executemany("insert into choice_stock_daily_observation values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.executemany("insert into stock_adjustment_factor values (?,?,?,?,?)", factors)
    conn.execute("insert into choice_stock_universe values (?, ?, '示例', 'field', 'source', ?, 'rule', 'run')", [AS_OF, CODE, RAW_VENDOR])
    conn.execute("insert into choice_stock_sector_membership values (?, ?, '行业', 'S', 'field', 'source', ?, 'rule', 'run')", [AS_OF, CODE, RAW_VENDOR])
    conn.execute("insert into choice_stock_limit_quality values (?, ?, '', '', 0, 0, 'field', 'source', ?, 'rule', 'run')", [AS_OF, CODE, RAW_VENDOR])
    return conn

def test_duplicate_factor_does_not_multiply_or_shorten_price_observations(tmp_path):
    path = tmp_path / "duplicate.duckdb"
    conn = _seed(path)
    try:
        conn.execute("insert into stock_adjustment_factor select * from stock_adjustment_factor where trade_date = ?", [_dates(130)[60]])
        result = service._load_signal_stock_histories(conn=conn, stock_codes=[CODE], as_of_date=AS_OF, trading_only=True)[CODE]
        assert len(result.turnover) == 130
        assert result.prices.closes == ()
        assert result.prices.unavailable_reason == "adjustment_factor_duplicate"
    finally:
        conn.close()

def test_repository_excludes_future_factor_and_price_rows(tmp_path):
    path = tmp_path / "future.duckdb"
    conn = _seed(path)
    try:
        baseline = service._load_signal_stock_histories(conn=conn, stock_codes=[CODE], as_of_date=AS_OF, trading_only=True)
        conn.execute("insert into stock_adjustment_factor values (?, '2026-01-01', 999, 'future', 'future')", [CODE])
        conn.execute("insert into choice_stock_daily_observation select '2026-01-01', stock_code, open_value, high_value, low_value, 999, volume, amount, pctchange, turn, amplitude, tradestatus, highlimit, lowlimit, field_keys_json, 'future', vendor_version, rule_version, run_id from choice_stock_daily_observation where trade_date = ?", [AS_OF])
        actual = service._load_signal_stock_histories(conn=conn, stock_codes=[CODE], as_of_date=AS_OF, trading_only=True)
        assert actual == baseline
    finally:
        conn.close()

def test_adjusted_breakout_geometry_replaces_all_fields_on_one_scale():
    raw = [100.0] * 45 + [50.0] * 10 + [51.0]
    history = _history(raw, [1.0] * 45 + [2.0] * 11)
    payload = {"items": [{"stock_code": CODE, "close": 51.0, "breakout_level": 50.0,
                          "distance_to_breakout_pct": -49.0, "pattern": "old", "pattern_code": "old"}]}
    result = service._attach_signal_breakout_geometry(payload, close_histories={CODE: history.closes}, as_of_date=AS_OF)
    item = result["items"][0]
    assert item["breakout_level"] == 50.0
    assert item["distance_to_breakout_pct"] == 2.0
    assert item["pattern_code"] == "breakout"
    assert payload["items"][0]["distance_to_breakout_pct"] == -49.0

def test_partial_history_disclosure_keeps_the_missing_stock_reason():
    valid = service._SignalStockHistory(prices=_history([10.0, 11.0], [1.0, 1.0]))
    invalid = service._SignalStockHistory(prices=_history([10.0, 11.0], [1.0, 0.0]))
    disclosure = service._signal_history_disclosure({"GOOD": valid, "BAD": invalid}, stock_codes=["GOOD", "BAD"])
    assert disclosure["price_history_status"] == "partial"
    assert disclosure["price_history_unavailable_count"] == 1
    assert disclosure["price_history_unavailable_reasons"] == {"BAD": "adjustment_factor_nonpositive_or_nonfinite"}

def test_cached_native_evidence_keeps_source_membership_and_date_checks():
    evidence = stock_daily_price_basis_evidence(source_version="sv_prices", request_audits=[_native_audit()])
    kwargs = dict(vendor_version=NATIVE_VENDOR, stock_code=CODE, trade_date="2026-06-30", source_version="sv_prices",
                  request_audits=[], request_evidence=evidence)
    assert stock_daily_price_basis(**kwargs) == "raw"
    for change in ({"source_version": "wrong"}, {"stock_code": "wrong"},
                   {"trade_date": "2025-12-31"}, {"trade_date": "2026-07-01"}, {"trade_date": "invalid"}):
        assert stock_daily_price_basis(**{**kwargs, **change}) == "unconfirmed"

def test_missing_raw_flag_does_not_decode_the_large_request_arguments(monkeypatch):
    from backend.app.repositories import choice_stock_adapter as adapter
    audit = _native_audit()
    audit["request_options_json"] = "{}"
    original = adapter.json.loads
    parsed = []

    def counted_loads(value, **kwargs):
        parsed.append(value)
        return original(value, **kwargs)

    monkeypatch.setattr(adapter.json, "loads", counted_loads)
    assert stock_daily_price_basis(vendor_version=NATIVE_VENDOR, stock_code=CODE, trade_date="2026-06-30",
                                    source_version="sv_prices", request_audits=[audit]) == "unconfirmed"
    assert parsed == ["{}"]

def test_native_run_evidence_is_decoded_once_for_the_whole_signal_window(tmp_path, monkeypatch):
    from backend.app.repositories import choice_stock_adapter as adapter
    path = tmp_path / "cached-native.duckdb"
    conn = _seed(path)
    conn.execute("update choice_stock_daily_observation set vendor_version = ?", [NATIVE_VENDOR])
    args = json.dumps([CODE, "OPEN,HIGH,LOW,CLOSE,VOLUME,AMOUNT", _dates(130)[0], AS_OF])
    conn.execute("""insert into choice_stock_request_audit
        (run_id, input_family, field_key, call, vendor_indicator, request_arguments_json,
         request_options_json, status, source_version)
        values ('run','stock_ohlcv','daily_ohlcv_amount','csd','OPEN,HIGH,LOW,CLOSE,VOLUME,AMOUNT',
                ?, '{"AdjustFlag":1}', 'completed', 'sv_prices')""", [args])
    original = adapter.json.loads
    parsed = []

    def counted_loads(value, **kwargs):
        parsed.append(value)
        return original(value, **kwargs)

    monkeypatch.setattr(adapter.json, "loads", counted_loads)
    try:
        history = service._load_signal_stock_histories(conn=conn, stock_codes=[CODE], as_of_date=AS_OF, trading_only=True)[CODE]
        assert history.prices.unavailable_reason == ""
        assert len(history.prices.closes) == 130
        assert parsed == ['{"AdjustFlag":1}', args]
    finally:
        conn.close()


@pytest.mark.parametrize("raw,factors", [([100.0, 50.0], [1.0, 2.0]), ([62.5, 50.0], [1.0, 1.25])])
def test_corporate_action_history_has_one_price_scale_and_raw_signal_anchor(raw, factors):
    history = _history(raw, factors)
    assert history.unavailable_reason == ""
    assert history.closes == (50.0, 50.0)
    assert history.raw_closes == tuple(raw)
    assert history.factors == tuple(factors)


@pytest.mark.parametrize("factor_date", [None, "invalid", "2025-02-30"])
def test_malformed_factor_date_is_rejected_before_matching(factor_date):
    days = _dates(2)
    result = signal_price_history(
        raw_prices=[10.0, 10.0], trade_dates=days, price_bases=["raw", "raw"],
        factor_rows=[(days[0], 1.0), (days[1], 1.0), (factor_date, 1.0)], signal_date=AS_OF,
    )
    assert result.closes == ()
    assert result.unavailable_reason == "adjustment_factor_date_invalid"


@pytest.mark.parametrize("raw,dates,bases", [([], [], []), ([10.0], [], ["raw"]), ([10.0], [AS_OF], [])])
def test_empty_or_misaligned_history_is_unavailable(raw, dates, bases):
    result = signal_price_history(
        raw_prices=raw, trade_dates=dates, price_bases=bases, factor_rows=[], signal_date=AS_OF,
    )
    assert result.closes == ()
    assert result.unavailable_reason == "price_window_alignment_invalid"


@pytest.mark.parametrize("raw,factors", [([1e308, 10.0], [1e308, 1.0]), ([1.0, 10.0], [5e-324, 1e308])])
def test_nonfinite_or_underflowed_adjusted_price_is_rejected(raw, factors):
    history = _history(raw, factors)
    assert history.closes == ()
    assert history.unavailable_reason == "adjusted_price_nonpositive_or_nonfinite"


@pytest.mark.parametrize("options", [
    '{"AdjustFlag":2,"AdjustFlag":1}',
    '{"AdjustFlag":1,"AdjustFlag":1}',
    '[["AdjustFlag",1]]',
    '{"AdjustFlag":true}',
])
def test_duplicate_or_ambiguous_raw_flag_is_rejected_before_large_arguments(monkeypatch, options):
    from backend.app.repositories import choice_stock_adapter as adapter

    audit = _native_audit()
    audit["request_options_json"] = options
    original = adapter.json.loads
    parsed = []

    def counted_loads(value, **kwargs):
        parsed.append(value)
        return original(value, **kwargs)

    monkeypatch.setattr(adapter.json, "loads", counted_loads)
    assert stock_daily_price_basis(
        vendor_version=NATIVE_VENDOR, stock_code=CODE, trade_date="2026-06-30",
        source_version="sv_prices", request_audits=[audit],
    ) == "unconfirmed"
    assert parsed == [options]
