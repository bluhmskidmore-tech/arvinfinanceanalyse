"""Independent MS-005 fail-closed regressions with synthetic registered storage.

The real on-connection service, factor scoring, fusion scoring, history SQL,
price-basis verification and geometry run unchanged. Explicit partial coverage
keeps unrelated materialization and stock/theme/risk branches out of scope.
MOSS_GEOMETRY_REVIEW_SOURCE optionally isolates the frozen baseline module;
it never rolls back the shared production source.
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
import socket
import sys
from datetime import date, timedelta
from types import SimpleNamespace

import duckdb
import pytest

from backend.app.core_finance.adjusted_returns import SIGNAL_PRICE_ADJUSTMENT_MODE
from backend.app.core_finance.breakout_geometry import BREAKOUT_GEOMETRY_FIELD_KEYS
from backend.app.repositories.choice_stock_adapter import (
    STOCK_FACTOR_INPUT_RULE_VERSION,
    ChoiceStockReadiness,
)
from backend.app.schema_registry.duckdb_loader import REGISTRY_DIR, parse_registry_sql_text
from backend.app.services import market_data_livermore_service as current_service

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_livermore]

AS_OF = "2026-10-06"
CODE = "SYNTH_REVIEW_001"
NATIVE = "vv_choice_stock_20261006_aaaaaaaaaaaa"
TUSHARE = "vv_choice_tushare_stock_20261006_aaaaaaaaaaaa"
PRICE_FIELDS = set(BREAKOUT_GEOMETRY_FIELD_KEYS) | {
    "price_as_of_date", "price_stale", "breakout_geometry_unavailable_reason",
}
DISCLOSURE_FIELDS = {
    "breakout_geometry", "price_adjustment_mode", "price_history_status",
    "price_history_unavailable_count", "price_history_unavailable_reasons",
}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def deny(*args, **kwargs):
        pytest.fail("Geometry regression must not access a provider or network")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)


@pytest.fixture(scope="module")
def service():
    source = os.getenv("MOSS_GEOMETRY_REVIEW_SOURCE")
    if not source:
        return current_service
    name = "moss_independent_geometry_review_baseline"
    spec = importlib.util.spec_from_file_location(name, source)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _dates(count=56, lag=0):
    end = date.fromisoformat(AS_OF) - timedelta(days=lag)
    return [(end - timedelta(days=count - 1 - i)).isoformat() for i in range(count)]


def _schema(conn):
    for filename in ("21_choice_stock.sql", "27_choice_stock_factor_snapshot.sql", "30_stock_adjustment_factor.sql"):
        for statement in parse_registry_sql_text((REGISTRY_DIR / filename).read_text(encoding="utf-8")):
            conn.execute(statement)


def _factor_snapshot(conn, code=CODE, snapshot_date=AS_OF, generation="G1", index=1):
    conn.execute(
        "insert into choice_stock_factor_snapshot "
        "(as_of_date,stock_code,pe,pb,ps,roe,gross_margin,three_month_return,twelve_month_return,"
        "volatility,dividend_yield,industry,source_version,vendor_version,rule_version,run_id) "
        "values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [snapshot_date, code, 10 + index / 100, 1.2, 2.5, 0.15, 0.30, 0.05, 0.12, 0.20, 0.03,
         f"Synthetic industry {index}", f"synthetic_{generation}_snapshot", "synthetic_factor_vendor",
         STOCK_FACTOR_INPUT_RULE_VERSION, f"synthetic_{generation}_snapshot_run"],
    )


def _observations(conn, *, code=CODE, days=None, generation="G1", vendor=TUSHARE,
                  split=True, price=100.0, turn=2.0, status="1", factors=True):
    days = days or _dates()
    observations, adjustment = [], []
    for i, day in enumerate(days):
        final_split = split and i == len(days) - 1
        close = price / 2 if final_split else price
        observations.append([day, code, close, 100000, 1_000_000_000, turn, status,
                             f"synthetic_{generation}_price", vendor, f"synthetic_{generation}_daily_run"])
        adjustment.append([code, day, 2 if final_split else 1, f"synthetic_{generation}_adjustment", f"synthetic_{generation}_factor_run"])
    conn.executemany(
        "insert into choice_stock_daily_observation "
        "(trade_date,stock_code,close_value,volume,amount,turn,tradestatus,source_version,vendor_version,run_id) "
        "values (?,?,?,?,?,?,?,?,?,?)", observations,
    )
    if factors:
        conn.executemany("insert into stock_adjustment_factor values (?,?,?,?,?)", adjustment)


def _audit(conn, *, generation="G1", code=CODE, options=None, source=None, run=None,
           start=None, end=AS_OF, status="completed"):
    conn.execute(
        "insert into choice_stock_request_audit "
        "(run_id,as_of_date,input_family,field_key,call,vendor_indicator,request_arguments_json,"
        "request_options_json,status,source_version) values (?,?,?,?,?,?,?,?,?,?)",
        [run or f"synthetic_{generation}_daily_run", AS_OF, "stock_ohlcv", "daily_ohlcv_amount", "csd",
         "OPEN,HIGH,LOW,CLOSE", json.dumps([code, "OPEN,HIGH,LOW,CLOSE", start or _dates()[0], end]),
         json.dumps({"AdjustFlag": "1"} if options is None else options), status,
         source or f"synthetic_{generation}_price"],
    )


def _database(tmp_path, *, label="G1", mutate=None, snapshot_date=AS_OF, **history):
    path = tmp_path / f"synthetic_{label}.duckdb"
    with duckdb.connect(str(path)) as conn:
        _schema(conn)
        _factor_snapshot(conn, snapshot_date=snapshot_date, generation=label)
        _observations(conn, generation=label, **history)
        if mutate:
            mutate(conn)
    return path


def _outputs(service, path, *, active_path=None, state="WARM", conn=None):
    coverage = SimpleNamespace(as_of_date=AS_OF, full_coverage=False, status="partial",
                               completed_request_items=[], missing_request_items=[], message="Synthetic partial coverage")
    readiness = ChoiceStockReadiness(ready=True, status="ready", catalog_path="synthetic-only",
                                    missing_input_families=[], message="Synthetic readiness")
    kwargs = dict(duckdb_path=str(active_path or path), as_of_date=AS_OF, market_state=state,
                  stock_readiness=readiness, backfill_mode=False, stock_candidate_policy=None,
                  macro_score=0.5, stock_coverage=coverage, sector_coverage=coverage)
    if conn is not None:
        return service._load_choice_stock_outputs_on_conn(conn, **kwargs)
    with duckdb.connect(str(path), read_only=True) as selected:
        return service._load_choice_stock_outputs_on_conn(selected, **kwargs)


def _payloads(output):
    assert output.stock_candidates_payload is None
    assert output.uptrend_momentum_payload is None
    assert output.fresh_trend_watchlist_payload is None
    assert output.mean_reversion_payload is None
    assert output.theme_breakout_payload is None
    factor, fusion = output.factor_screen_payload, output.hybrid_fusion_payload
    assert factor is not None and fusion is not None
    return factor, fusion


def _item(payload):
    assert payload["candidate_count"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["stock_code"] == CODE
    return payload["items"][0]


def _assert_unavailable(payload, reason):
    item = _item(payload)
    assert all(item[key] is None for key in BREAKOUT_GEOMETRY_FIELD_KEYS)
    assert payload["price_adjustment_mode"] == SIGNAL_PRICE_ADJUSTMENT_MODE
    assert payload["price_history_status"] == "unavailable"
    assert payload["price_history_unavailable_count"] == 1
    assert payload["price_history_unavailable_reasons"] == {CODE: reason}


def _non_geometry(payload):
    return {key: [{k: v for k, v in row.items() if k not in PRICE_FIELDS} for row in value]
            if key == "items" else value for key, value in payload.items() if key not in DISCLOSURE_FIELDS}


def test_real_factor_only_split_uses_verified_geometry_and_lineage(service, tmp_path):
    result = _outputs(service, _database(tmp_path))
    for payload in _payloads(result):
        item = _item(payload)
        assert item["close"] == 50
        assert item["breakout_level"] == 50
        assert item["distance_to_breakout_pct"] == 0
        assert item["pattern_code"] == "consolidation"
        assert payload["price_history_status"] == "available"
        assert payload["breakout_geometry"]["price_adjustment_mode"] == SIGNAL_PRICE_ADJUSTMENT_MODE
    assert {"synthetic_G1_price", "synthetic_G1_adjustment"} <= set(result.source_versions)
    assert TUSHARE in result.vendor_versions
    assert "stock_adjustment_factor" in result.tables_used
    assert "synthetic_G1_adjustment" not in result.vendor_versions


def test_selected_connection_owns_prices_factors_audits_and_lifetime(service, tmp_path, monkeypatch):
    g1 = _database(tmp_path, label="G1", vendor=NATIVE, mutate=lambda c: _audit(c))
    g9 = _database(tmp_path, label="G9", vendor=NATIVE, price=900, mutate=lambda c: _audit(c, generation="G9", options={"AdjustFlag": "2"}))
    def forbidden_open(*args, **kwargs):
        pytest.fail("Geometry reopened an active database instead of the supplied G1 connection")
    monkeypatch.setattr(service, "open_livermore_read_connection", forbidden_open)
    with duckdb.connect(str(g1), read_only=True) as selected:
        result = _outputs(service, g1, active_path=g9, conn=selected)
        assert selected.execute("select 42").fetchone() == (42,)
        for payload in _payloads(result):
            assert _item(payload)["breakout_level"] == 50
            assert payload["price_history_status"] == "available"
        assert "choice_stock_request_audit" in result.tables_used
        assert {"synthetic_G1_price", "synthetic_G1_adjustment"} <= set(result.source_versions)
        assert not any("G9" in source for source in result.source_versions)


@pytest.mark.parametrize("mutation,reason", [
    ("delete from stock_adjustment_factor where trade_date = '2026-10-06'", "adjustment_factor_missing"),
    ("insert into stock_adjustment_factor select * from stock_adjustment_factor where trade_date = '2026-10-06'", "adjustment_factor_duplicate"),
    ("update stock_adjustment_factor set adj_factor = 0 where trade_date = '2026-10-06'", "adjustment_factor_nonpositive_or_nonfinite"),
    ("update stock_adjustment_factor set adj_factor = -1 where trade_date = '2026-10-06'", "adjustment_factor_nonpositive_or_nonfinite"),
    ("update stock_adjustment_factor set adj_factor = 'nan'::double where trade_date = '2026-10-06'", "adjustment_factor_nonpositive_or_nonfinite"),
    ("update stock_adjustment_factor set adj_factor = 'inf'::double where trade_date = '2026-10-06'", "adjustment_factor_nonpositive_or_nonfinite"),
    ("drop table stock_adjustment_factor", "adjustment_factor_table_missing"),
    ("insert into choice_stock_daily_observation select * from choice_stock_daily_observation where trade_date = '2026-10-06'", "price_window_date_invalid"),
    ("update choice_stock_daily_observation set close_value = NULL where trade_date = '2026-10-06'", "raw_price_nonpositive_or_nonfinite"),
    ("update choice_stock_daily_observation set close_value = 0 where trade_date = '2026-10-06'", "raw_price_nonpositive_or_nonfinite"),
    ("update choice_stock_daily_observation set close_value = -1 where trade_date = '2026-10-06'", "raw_price_nonpositive_or_nonfinite"),
    ("update choice_stock_daily_observation set close_value = 'nan'::double where trade_date = '2026-10-06'", "raw_price_nonpositive_or_nonfinite"),
    ("update choice_stock_daily_observation set close_value = 'inf'::double where trade_date = '2026-10-06'", "raw_price_nonpositive_or_nonfinite"),
], ids=["factor-missing", "factor-duplicate", "factor-zero", "factor-negative", "factor-nan", "factor-infinity", "factor-table-missing", "observation-duplicate", "close-null", "close-zero", "close-negative", "close-nan", "close-infinity"])
def test_invalid_price_or_factor_does_not_change_real_admission(service, tmp_path, mutation, reason):
    path = _database(tmp_path, mutate=lambda c: c.execute(mutation))
    for payload in _payloads(_outputs(service, path)):
        _assert_unavailable(payload, reason)


@pytest.mark.parametrize("audit_kwargs", [
    None,
    {"options": {"AdjustFlag": "2"}},
    {"source": "synthetic_wrong_source"},
    {"run": "synthetic_wrong_run"},
    {"code": "SYNTH_OTHER_CODE"},
    {"end": "2026-10-05"},
    {"status": "failed"},
    {"options": {"AdjustFlag": "1", "adjustflag": "1"}},
], ids=["audit-absent", "adjusted-not-raw", "wrong-source", "wrong-run", "wrong-code", "window-not-covered", "audit-failed", "ambiguous-adjustflag"])
def test_native_basis_requires_matching_historical_evidence(service, tmp_path, audit_kwargs):
    path = _database(tmp_path, vendor=NATIVE, mutate=(lambda c: _audit(c, **audit_kwargs)) if audit_kwargs is not None else None)
    for payload in _payloads(_outputs(service, path)):
        _assert_unavailable(payload, "price_basis_unconfirmed_or_mixed")


def test_duplicate_choice_audits_fail_closed(service, tmp_path):
    def duplicate(conn):
        _audit(conn)
        _audit(conn)
    path = _database(tmp_path, vendor=NATIVE, mutate=duplicate)
    for payload in _payloads(_outputs(service, path)):
        _assert_unavailable(payload, "price_basis_unconfirmed_or_mixed")


def test_stale_history_cannot_supply_strategy_day_anchor(service, tmp_path):
    path = _database(tmp_path, days=_dates(56, lag=1))
    for payload in _payloads(_outputs(service, path)):
        _assert_unavailable(payload, "price_window_date_invalid")
        assert payload["breakout_geometry"]["price_as_of_date"] == AS_OF


@pytest.mark.parametrize("history", [{"turn": None}, {"status": "0"}], ids=["null-turn-kept", "nontrading-status-kept"])
def test_verified_price_window_keeps_existing_calendar_choice(service, tmp_path, history):
    path = _database(tmp_path, **history)
    for payload in _payloads(_outputs(service, path)):
        item = _item(payload)
        assert item["breakout_level"] == 50
        assert item["distance_to_breakout_pct"] == 0
        assert payload["price_history_status"] == "available"


def test_55_observations_are_verified_but_geometry_unavailable(service, tmp_path):
    path = _database(tmp_path, days=_dates(55))
    for payload in _payloads(_outputs(service, path)):
        assert all(_item(payload)[key] is None for key in BREAKOUT_GEOMETRY_FIELD_KEYS)
        assert payload["price_history_status"] == "available"
        assert payload["price_history_unavailable_reasons"] == {}


def test_future_observations_and_factors_cannot_change_window_or_lineage(service, tmp_path):
    def future(conn):
        _observations(conn, days=["2026-10-07"], generation="FUTURE", price=9_999_999)
    path = _database(tmp_path, mutate=future)
    output = _outputs(service, path)
    for payload in _payloads(output):
        assert _item(payload)["breakout_level"] == 50
        assert _item(payload)["close"] == 50
    assert not any("FUTURE" in source for source in output.source_versions)


def test_factor_snapshot_date_does_not_replace_signal_price_day(service, tmp_path):
    path = _database(tmp_path, snapshot_date="2026-10-05")
    factor, fusion = _payloads(_outputs(service, path))
    assert factor["as_of_date"] == factor["factor_snapshot_as_of_date"] == "2026-10-05"
    assert fusion["as_of_date"] == AS_OF
    for payload in (factor, fusion):
        assert payload["breakout_geometry"]["price_as_of_date"] == AS_OF
        assert _item(payload)["close"] == _item(payload)["breakout_level"] == 50


def test_real_scoring_rank_coverage_and_policy_fields_are_geometry_independent(service, tmp_path):
    constant = _database(tmp_path, label="CONSTANT", split=False, price=50)
    split = _database(tmp_path, label="SPLIT")
    invalid = _database(tmp_path, label="INVALID", mutate=lambda c: c.execute("delete from stock_adjustment_factor"))
    outputs = [_outputs(service, path) for path in (constant, split, invalid)]
    for index in (0, 1):
        payloads = [_payloads(output)[index] for output in outputs]
        assert _non_geometry(payloads[0]) == _non_geometry(payloads[1]) == _non_geometry(payloads[2])
    assert all(output.factor_screen_block_reason == outputs[0].factor_screen_block_reason for output in outputs)
    assert all(output.hybrid_fusion_block_reason == outputs[0].hybrid_fusion_block_reason for output in outputs)
    assert all(output.evidence_rows == outputs[0].evidence_rows for output in outputs)
    assert _payloads(outputs[0])[0]["observation_only"] is True


@pytest.mark.parametrize("state", ["OFF", "HOT", "OVERHEAT", "NO_DATA"])
def test_market_state_gates_match_real_core_without_geometry_influence(service, tmp_path, state):
    path = _database(tmp_path)
    output = _outputs(service, path, state=state)
    with duckdb.connect(str(path), read_only=True) as conn:
        load = service._load_factor_screen_rows(duckdb_path=str(path), as_of_date=AS_OF, conn=conn)
    expected = service.compute_factor_screen_candidates(as_of_date=AS_OF, market_state=state, rows=load.rows).payload
    actual = output.factor_screen_payload
    assert actual is not None
    for key in expected:
        assert _non_geometry(actual)[key] == expected[key]
    if output.hybrid_fusion_payload is not None:
        expected_fusion = service.compute_hybrid_fusion_candidates(as_of_date=AS_OF, market_state=state,
            sector_rank_payload=None, stock_candidates_payload=None, factor_screen_payload=expected,
            theme_breakout_payload=None, macro_score=0.5, thresholds=service.load_hybrid_fusion_thresholds()).payload
        assert _non_geometry(output.hybrid_fusion_payload) == expected_fusion


def test_factor_and_fusion_disclosures_use_each_real_candidate_set(service, tmp_path, monkeypatch):
    """Factor top-11 includes one valid code outside fusion's real top-10."""
    path = tmp_path / "synthetic_disjoint_disclosure.duckdb"
    with duckdb.connect(str(path)) as conn:
        _schema(conn)
        for index in range(110):
            code = f"SYNTH_POOL_{index:03}"
            _factor_snapshot(conn, code=code, index=index + 1)
            _observations(conn, code=code, days=[AS_OF], factors=False, split=False)
        load = service._load_factor_screen_rows(duckdb_path=str(path), as_of_date=AS_OF, conn=conn)
        factor = service.compute_factor_screen_candidates(as_of_date=AS_OF, market_state="WARM", rows=load.rows).payload
        fusion = service.compute_hybrid_fusion_candidates(as_of_date=AS_OF, market_state="WARM",
            sector_rank_payload=None, stock_candidates_payload=None, factor_screen_payload=factor,
            theme_breakout_payload=None, macro_score=0.5, thresholds=service.load_hybrid_fusion_thresholds()).payload
        factor_codes = {row["stock_code"] for row in factor["items"]}
        fusion_codes = {row["stock_code"] for row in fusion["items"]}
        assert len(factor_codes) == 11 and len(fusion_codes) == 10
        valid_code, = factor_codes - fusion_codes
        conn.execute("delete from choice_stock_daily_observation where stock_code = ?", [valid_code])
        _observations(conn, code=valid_code)
    calls = []
    real_load = service._load_signal_stock_histories
    def record_real_load(**kwargs):
        calls.append((kwargs["stock_codes"], kwargs["trading_only"]))
        return real_load(**kwargs)
    monkeypatch.setattr(service, "_load_signal_stock_histories", record_real_load)
    result_factor, result_fusion = _payloads(_outputs(service, path))
    assert {row["stock_code"] for row in result_factor["items"]} == factor_codes
    assert {row["stock_code"] for row in result_fusion["items"]} == fusion_codes
    assert result_factor["price_history_status"] == "partial"
    assert result_fusion["price_history_status"] == "unavailable"
    assert result_factor["price_history_unavailable_count"] == result_fusion["price_history_unavailable_count"] == 10
    assert set(result_factor["price_history_unavailable_reasons"]) == fusion_codes
    assert set(result_fusion["price_history_unavailable_reasons"]) == fusion_codes
    good, = [row for row in result_factor["items"] if row["stock_code"] == valid_code]
    assert good["breakout_level"] == 50
    assert calls == [(sorted(factor_codes | fusion_codes), False)]
    assert all(row["breakout_level"] is None for row in result_fusion["items"])


def test_fusion_only_code_is_verified_on_caller_connection(service, tmp_path, monkeypatch):
    """A controlled fusion source admits a code absent from the factor snapshot."""
    fusion_only = "SYNTH_FUSION_ONLY"
    path = _database(tmp_path)
    with duckdb.connect(str(path)) as conn:
        _observations(conn, code=fusion_only)
    marker = {"coverage_scope": "synthetic-preserved"}
    monkeypatch.setattr(service, "compute_hybrid_fusion_candidates", lambda **kwargs: SimpleNamespace(
        payload={"as_of_date": AS_OF, "candidate_count": 1, "selection_research": marker,
                 "items": [{"stock_code": fusion_only, "synthetic_score": 7.0}]},
    ))
    calls = []
    real_load = service._load_signal_stock_histories
    def record_real_load(**kwargs):
        calls.append(kwargs)
        return real_load(**kwargs)
    monkeypatch.setattr(service, "_load_signal_stock_histories", record_real_load)
    with duckdb.connect(str(path), read_only=True) as conn:
        factor, fusion = _payloads(_outputs(service, path, conn=conn))
        assert len(calls) == 1
        assert calls[0]["conn"] is conn
        assert calls[0]["stock_codes"] == sorted([CODE, fusion_only])
        assert calls[0]["trading_only"] is False
        assert conn.execute("SELECT 1").fetchone() == (1,)
    assert {item["stock_code"] for item in factor["items"]} == {CODE}
    assert fusion["selection_research"] == marker
    assert fusion["items"][0]["synthetic_score"] == 7.0
    assert fusion["items"][0]["close"] == fusion["items"][0]["breakout_level"] == 50.0
    assert fusion["price_history_status"] == "available"


def test_verified_price_query_failure_does_not_borrow_raw_geometry(service, tmp_path, monkeypatch):
    path = _database(tmp_path)
    def fail_query(**kwargs):
        raise duckdb.BinderException("synthetic verified history query failure")
    monkeypatch.setattr(service.LIVERMORE_STRATEGY_READS, "fetch_signal_stock_history_rows", fail_query)
    for payload in _payloads(_outputs(service, path)):
        _assert_unavailable(payload, "price_history_query_failed")


def test_existing_close_conflict_preserves_close_and_clears_dependent_geometry(service):
    payload = {"items": [{"stock_code": CODE, "close": 99, "breakout_level": 777,
                          "distance_to_breakout_pct": 12, "pattern": "old", "pattern_code": "old", "score": 0.5,
                          "price_as_of_date": "2026-10-01", "price_stale": True}]}
    result = service._attach_signal_breakout_geometry(payload, close_histories={CODE: (50,) * 56}, as_of_date=AS_OF)
    row = result["items"][0]
    assert row["close"] == 99 and row["score"] == 0.5
    assert all(row[key] is None for key in PRICE_FIELDS - {
        "close", "price_as_of_date", "price_stale", "breakout_geometry_unavailable_reason",
    })
    assert row["price_as_of_date"] is None and row["price_stale"] is None
    assert row["breakout_geometry_unavailable_reason"] == "geometry_fields_unavailable"
    assert payload["items"][0]["breakout_level"] == 777
    assert payload["items"][0]["price_stale"] is True


def test_adjustment_sources_are_reported_separately_from_vendor_evidence(service, tmp_path):
    result = _outputs(service, _database(tmp_path, split=False))
    assert {"synthetic_G1_price", "synthetic_G1_adjustment"} <= set(result.source_versions)
    assert TUSHARE in result.vendor_versions
    assert "synthetic_G1_adjustment" not in result.vendor_versions
    assert "stock_adjustment_factor" in result.tables_used


@pytest.mark.parametrize("count,bad_index,expected_reason", [
    (130, 0, "raw_price_nonpositive_or_nonfinite"),
    (131, 0, ""),
    (131, 1, "raw_price_nonpositive_or_nonfinite"),
], ids=["oldest-retained-is-validated", "older-than-130-is-excluded", "boundary-130-is-validated"])
def test_verified_history_preserves_130_row_boundary(service, tmp_path, count, bad_index, expected_reason):
    days = _dates(count)
    path = _database(tmp_path, days=days, mutate=lambda conn: conn.execute(
        "update choice_stock_daily_observation set close_value = NULL where trade_date = ?", [days[bad_index]],
    ))
    for payload in _payloads(_outputs(service, path)):
        if expected_reason:
            _assert_unavailable(payload, expected_reason)
        else:
            assert payload["price_history_status"] == "available"
            assert _item(payload)["breakout_level"] == 50
            assert _item(payload)["close"] == 50


@pytest.mark.parametrize("close", [100.0, 777.0], ids=["identical", "conflicting"])
def test_duplicate_observation_at_130_row_boundary_cannot_be_hidden(service, tmp_path, close):
    days = _dates(131)

    def duplicate(conn):
        conn.execute(
            "insert into choice_stock_daily_observation "
            "select * replace (? as close_value) from choice_stock_daily_observation where trade_date = ?",
            [close, days[1]],
        )

    path = _database(tmp_path, days=days, mutate=duplicate)
    for payload in _payloads(_outputs(service, path)):
        _assert_unavailable(payload, "price_window_date_invalid")


def test_null_observation_date_cannot_silently_shorten_verified_window(service, tmp_path):
    days = _dates(57)
    path = _database(tmp_path, days=days, mutate=lambda conn: conn.execute(
        "update choice_stock_daily_observation set trade_date = NULL where trade_date = ?",
        [days[20]],
    ))
    for payload in _payloads(_outputs(service, path)):
        assert _item(payload)["stock_code"] == CODE, "Invalid geometry must retain admitted candidates"
        assert payload["price_history_status"] == "unavailable"
        assert payload["price_history_unavailable_reasons"] == {CODE: "price_window_date_invalid"}
        assert all(_item(payload)[key] is None for key in BREAKOUT_GEOMETRY_FIELD_KEYS)
        assert _item(payload)["breakout_geometry_unavailable_reason"] == "price_window_date_invalid"


def test_null_factor_date_cannot_be_discarded_from_verified_evidence(service, tmp_path):
    def undated_factor(conn):
        conn.execute(
            "insert into stock_adjustment_factor "
            "(stock_code, trade_date, adj_factor, source_version, run_id) "
            "values (?, NULL, 1, 'synthetic_undated_adjustment', 'synthetic_undated_run')",
            [CODE],
        )

    path = _database(tmp_path, mutate=undated_factor)
    for payload in _payloads(_outputs(service, path)):
        assert _item(payload)["stock_code"] == CODE, "Invalid geometry must retain admitted candidates"
        assert payload["price_history_status"] == "unavailable"
        assert payload["price_history_unavailable_reasons"] == {CODE: "adjustment_factor_date_invalid"}
        assert all(_item(payload)[key] is None for key in BREAKOUT_GEOMETRY_FIELD_KEYS)
        assert _item(payload)["breakout_geometry_unavailable_reason"] == "adjustment_factor_date_invalid"


@pytest.mark.parametrize("pool_index,field", [
    (0, "breakout_level"),
    (1, "breakout_level"),
    (0, "distance_to_breakout_pct"),
    (1, "distance_to_breakout_pct"),
], ids=["factor-positive-breakout", "fusion-positive-breakout", "factor-finite-distance", "fusion-finite-distance"])
def test_extreme_finite_verified_prices_never_emit_invalid_geometry(service, tmp_path, pool_index, field):
    def extreme_prices(conn):
        conn.execute("update stock_adjustment_factor set adj_factor = 1")
        conn.execute(
            "update choice_stock_daily_observation set close_value = ? where trade_date <> ?",
            [1e-307, AS_OF],
        )
        conn.execute(
            "update choice_stock_daily_observation set close_value = 50 where trade_date = ?",
            [AS_OF],
        )

    path = _database(tmp_path, mutate=extreme_prices)
    payload = _payloads(_outputs(service, path))[pool_index]
    value = _item(payload)[field]
    # Unavailable is permitted; a displayed number must obey the field contract.
    assert value is None or math.isfinite(value)
    if field == "breakout_level":
        assert value is None or value > 0


@pytest.mark.parametrize("prior_price,signal_price,reason", [
    (1e-307, 50.0, "geometry_nonfinite_value"),
    (1e-7, 1e-7, "geometry_nonpositive_breakout_level"),
    (1.0, 1e-7, "geometry_nonpositive_close"),
], ids=["overflow-distance", "rounded-zero-breakout", "rounded-zero-close"])
def test_verified_geometry_failure_is_atomic_and_does_not_change_scoring(
    service, tmp_path, prior_price, signal_price, reason,
):
    baseline = _payloads(_outputs(service, _database(tmp_path, label="BASELINE")))

    def extreme_prices(conn):
        conn.execute("update stock_adjustment_factor set adj_factor = 1")
        conn.execute(
            "update choice_stock_daily_observation set close_value = ? where trade_date <> ?",
            [prior_price, AS_OF],
        )
        conn.execute(
            "update choice_stock_daily_observation set close_value = ? where trade_date = ?",
            [signal_price, AS_OF],
        )

    path = _database(tmp_path, label="EXTREME", mutate=extreme_prices)
    with duckdb.connect(str(path), read_only=True) as conn:
        result = _payloads(_outputs(service, path, conn=conn))
        assert conn.execute("select 42").fetchone() == (42,), "Caller retains its selected connection"
    for expected, payload in zip(baseline, result, strict=True):
        assert payload["price_history_status"] == "available"
        assert payload["price_history_unavailable_count"] == 0
        assert payload["price_history_unavailable_reasons"] == {}
        item = _item(payload)
        assert item["close"] is None or (math.isfinite(item["close"]) and item["close"] > 0)
        assert all(item[key] is None for key in BREAKOUT_GEOMETRY_FIELD_KEYS)
        assert item["price_as_of_date"] is None and item["price_stale"] is None
        assert item["breakout_geometry_unavailable_reason"] == reason
        assert _non_geometry(payload) == _non_geometry(expected)


def test_undated_other_codes_and_future_evidence_do_not_poison_selected_geometry(service, tmp_path):
    def outside_scope(conn):
        _observations(conn, code="SYNTH_UNSELECTED", days=[None], generation="UNSELECTED", split=False)
        _observations(conn, days=["2026-10-07"], generation="FUTURE", split=False)

    path = _database(tmp_path, mutate=outside_scope)
    with duckdb.connect(str(path), read_only=True) as conn:
        output = _outputs(service, path, conn=conn)
        assert conn.execute("select 42").fetchone() == (42,)
    for payload in _payloads(output):
        assert payload["price_history_status"] == "available"
        assert _item(payload)["breakout_level"] == _item(payload)["close"] == 50
    assert not any("UNSELECTED" in source or "FUTURE" in source for source in output.source_versions)
