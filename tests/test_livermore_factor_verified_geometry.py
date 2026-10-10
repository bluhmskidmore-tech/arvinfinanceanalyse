"""MS-005: real factor admission/scoring and caller-owned synthetic DuckDB reads.

Partial coverage intentionally disables unrelated strategy/materialization paths.
The synthetic observation dates are supplied bars, not an exchange calendar.
No provider, real data, full HTTP/materialization acceptance, or policy changes.
"""
from __future__ import annotations

import socket
from datetime import date, timedelta
from types import SimpleNamespace

import duckdb
import pytest

from backend.app.core_finance.adjusted_returns import SIGNAL_PRICE_ADJUSTMENT_MODE
from backend.app.core_finance.breakout_geometry import BREAKOUT_GEOMETRY_FIELD_KEYS
from backend.app.repositories.choice_stock_adapter import STOCK_FACTOR_INPUT_RULE_VERSION, ChoiceStockReadiness
from backend.app.schema_registry.duckdb_loader import REGISTRY_DIR, parse_registry_sql_text
from backend.app.services import market_data_livermore_service as service

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_livermore]

DAY = date(2026, 10, 6)
CODE = "SYN001.SZ"
VENDOR = "vv_choice_tushare_stock_20261006_aaaaaaaaaaaa"
NATIVE_VENDOR = "vv_choice_stock_20261006_bbbbbbbbbbbb"
GEOMETRY_KEYS = set(BREAKOUT_GEOMETRY_FIELD_KEYS) | {
    "price_as_of_date", "price_stale", "breakout_geometry_unavailable_reason",
}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def deny(*args, **kwargs):
        pytest.fail("Geometry regression must not access a provider or network")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)


def _seed(path, *, count=56, split=True, tag="g1", codes=(CODE,), vendor=VENDOR,
          anchor=DAY, null_turn=False, tradestatus="1", snapshot_day=None):
    snapshot_day = snapshot_day or DAY - timedelta(days=1)
    with duckdb.connect(str(path)) as conn:
        for filename, table in (
            ("21_choice_stock.sql", "choice_stock_daily_observation"),
            ("27_choice_stock_factor_snapshot.sql", "choice_stock_factor_snapshot"),
            ("30_stock_adjustment_factor.sql", "stock_adjustment_factor"),
        ):
            statements = parse_registry_sql_text((REGISTRY_DIR / filename).read_text(encoding="utf-8"))
            statement = next(text for text in statements if text.startswith(f"create table if not exists {table} ("))
            conn.execute(statement)
        for code in codes:
            conn.execute("""insert into choice_stock_factor_snapshot
                (as_of_date, stock_code, pe, pb, ps, roe, gross_margin,
                 three_month_return, twelve_month_return, volatility, dividend_yield,
                 industry, source_version, vendor_version, rule_version, run_id)
                values (?, ?, 10, 1, 2, .15, .30, .1, .2, .15, .03, ?, ?, ?, ?, ?)
            """, [str(snapshot_day), code, f"synthetic-industry-{code}", f"sv_synthetic_snapshot_{tag}",
                  f"vv_synthetic_snapshot_{tag}", STOCK_FACTOR_INPUT_RULE_VERSION, f"synthetic_snapshot_{tag}"])
            days = [anchor - timedelta(days=count - 1 - index) for index in range(count)]
            conn.executemany("""insert into choice_stock_daily_observation
                (stock_code, trade_date, close_value, turn, amount, volume,
                 tradestatus, source_version, vendor_version, run_id)
                values (?, ?, ?, ?, ?, 1000000, ?, ?, ?, ?)
            """, [(code, str(day), 50.0 if split and day == anchor else 100.0,
                   None if null_turn and day == days[0] else 2.0,
                   1e9 if vendor == NATIVE_VENDOR else 1e6, tradestatus,
                   f"sv_synthetic_price_{tag}", vendor, f"synthetic_price_{tag}") for day in days])
            conn.executemany("""insert into stock_adjustment_factor
                (stock_code, trade_date, adj_factor, source_version, run_id) values (?, ?, ?, ?, ?)
            """, [(code, str(day), 2.0 if split and day == anchor else 1.0,
                   f"sv_synthetic_adjustment_{tag}", f"synthetic_adjustment_{tag}") for day in days])
    return path


def _load(conn, path, *, state="WARM", macro_score=.5):
    coverage = SimpleNamespace(full_coverage=False)
    return service._load_choice_stock_outputs_on_conn(
        conn, duckdb_path=str(path), as_of_date=str(DAY), market_state=state,
        stock_readiness=ChoiceStockReadiness(ready=True, status="ready", catalog_path="synthetic",
                                           missing_input_families=[], message="synthetic partial coverage"),
        backfill_mode=False, stock_candidate_policy=None, macro_score=macro_score,
        sector_coverage=coverage, stock_coverage=coverage,
    )


def _payloads(output):
    assert output.stock_candidates_payload is None
    assert output.uptrend_momentum_payload is None
    assert output.fresh_trend_watchlist_payload is None
    assert output.mean_reversion_payload is None
    assert output.theme_breakout_payload is None
    assert output.factor_screen_payload is not None
    assert output.hybrid_fusion_payload is not None
    return output.factor_screen_payload, output.hybrid_fusion_payload


def _assert_geometry(payload, *, close=50., breakout=50., distance=0., pattern="consolidation"):
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert (item["close"], item["breakout_level"], item["distance_to_breakout_pct"], item["pattern_code"]) == (
        close, breakout, distance, pattern,
    )


def _assert_unavailable(payload, reason):
    assert len(payload["items"]) == 1, "Unavailable geometry must not remove admitted candidates"
    assert all(payload["items"][0][key] is None for key in BREAKOUT_GEOMETRY_FIELD_KEYS)
    assert payload["price_history_status"] == "unavailable"
    assert payload["price_history_unavailable_count"] == 1
    assert payload["price_history_unavailable_reasons"] == {CODE: reason}


def test_factor_only_split_uses_verified_prices_after_real_scoring(tmp_path):
    path = _seed(tmp_path / "split.duckdb")
    with duckdb.connect(str(path), read_only=True) as conn:
        output = _load(conn, path)
        assert conn.execute("select 1").fetchone() == (1,), "Caller owns connection after return"
    for payload in _payloads(output):
        _assert_geometry(payload)
        assert payload["price_history_status"] == "available"
        assert payload["price_adjustment_mode"] == SIGNAL_PRICE_ADJUSTMENT_MODE
        assert payload["breakout_geometry"]["price_adjustment_mode"] == SIGNAL_PRICE_ADJUSTMENT_MODE
        assert payload["breakout_geometry"]["price_as_of_date"] == str(DAY)
    factor = output.factor_screen_payload
    assert factor["as_of_date"] == factor["factor_snapshot_as_of_date"] == str(DAY - timedelta(days=1))
    assert factor["observation_only"] is True
    assert factor["coverage_count"] == 1
    assert factor["coverage_denominator"] is None
    assert output.hybrid_fusion_payload["items"][0]["trade_eligible"] is False


def test_price_and_adjustment_source_lineage_comes_from_supplied_connection(tmp_path, monkeypatch):
    selected = _seed(tmp_path / "selected.duckdb", tag="selected")
    active = _seed(tmp_path / "active.duckdb", tag="active", split=False,
                   vendor="vv_choice_tushare_stock_20261006_cccccccccccc")
    def reject_reopen(*args, **kwargs):
        pytest.fail("A caller-owned connection must not reopen the active path")
    monkeypatch.setattr(service, "open_livermore_read_connection", reject_reopen)
    with duckdb.connect(str(selected), read_only=True) as conn:
        output = _load(conn, active)
    assert set(output.source_versions) == {"sv_synthetic_price_selected", "sv_synthetic_adjustment_selected"}
    assert set(output.vendor_versions) == {VENDOR}, "The adjustment table has no vendor identity"
    assert "stock_adjustment_factor" in output.tables_used
    for payload in _payloads(output):
        _assert_geometry(payload)


@pytest.mark.parametrize("case,reason", [
    ("missing", "adjustment_factor_missing"),
    ("duplicate", "adjustment_factor_duplicate"),
    ("zero", "adjustment_factor_nonpositive_or_nonfinite"),
    ("negative", "adjustment_factor_nonpositive_or_nonfinite"),
    ("null", "adjustment_factor_nonpositive_or_nonfinite"),
    ("nan", "adjustment_factor_nonpositive_or_nonfinite"),
    ("infinity", "adjustment_factor_nonpositive_or_nonfinite"),
    ("table_missing", "adjustment_factor_table_missing"),
])
def test_invalid_adjustment_fails_closed_without_dropping_candidate(tmp_path, case, reason):
    path = _seed(tmp_path / "invalid.duckdb")
    with duckdb.connect(str(path)) as conn:
        if case == "table_missing":
            conn.execute("drop table stock_adjustment_factor")
        elif case == "missing":
            conn.execute("delete from stock_adjustment_factor where trade_date = ?", [str(DAY)])
        elif case == "duplicate":
            conn.execute("insert into stock_adjustment_factor select * from stock_adjustment_factor where trade_date = ?", [str(DAY)])
        else:
            value = {"zero": 0., "negative": -1., "null": None, "nan": float("nan"), "infinity": float("inf")}[case]
            conn.execute("update stock_adjustment_factor set adj_factor = ? where trade_date = ?", [value, str(DAY)])
    with duckdb.connect(str(path), read_only=True) as conn:
        output = _load(conn, path)
    for payload in _payloads(output):
        _assert_unavailable(payload, reason)


def test_native_amount_basis_does_not_prove_raw_price_basis(tmp_path):
    path = _seed(tmp_path / "native.duckdb", vendor=NATIVE_VENDOR)
    with duckdb.connect(str(path), read_only=True) as conn:
        output = _load(conn, path)
    for payload in _payloads(output):
        _assert_unavailable(payload, "price_basis_unconfirmed_or_mixed")


def test_missing_strategy_day_anchor_replaces_old_stale_geometry(tmp_path):
    path = _seed(tmp_path / "stale.duckdb", anchor=DAY - timedelta(days=1))
    with duckdb.connect(str(path), read_only=True) as conn:
        raw, dates, _ = service._load_candidate_close_histories(
            duckdb_path=str(path), as_of_date=str(DAY), stock_codes=[CODE], conn=conn)
        old = service.attach_breakout_geometry({"items": [{"stock_code": CODE}]},
            close_history_by_code=raw, price_as_of_date=str(DAY), last_trade_date_by_code=dates)
        assert old["items"][0]["price_stale"] is True
        assert old["items"][0]["price_as_of_date"] == str(DAY - timedelta(days=1))
        output = _load(conn, path)
    for payload in _payloads(output):
        _assert_unavailable(payload, "price_window_date_invalid")
        assert payload["breakout_geometry"]["price_as_of_date"] == str(DAY)


def test_null_turn_is_retained_by_verified_price_window(tmp_path):
    path = _seed(tmp_path / "null-turn.duckdb", null_turn=True)
    with duckdb.connect(str(path), read_only=True) as conn:
        raw, _, _ = service._load_candidate_close_histories(
            duckdb_path=str(path), as_of_date=str(DAY), stock_codes=[CODE], conn=conn)
        assert len(raw[CODE]) == 55, "Existing raw helper keeps its old null-turn semantics"
        output = _load(conn, path)
    for payload in _payloads(output):
        _assert_geometry(payload)


def test_nontrading_bar_is_retained_for_factor_and_fusion(tmp_path):
    path = _seed(tmp_path / "status.duckdb", tradestatus="0")
    with duckdb.connect(str(path), read_only=True) as conn:
        output = _load(conn, path)
    for payload in _payloads(output):
        _assert_geometry(payload)


def test_short_but_verified_history_does_not_invent_geometry(tmp_path):
    path = _seed(tmp_path / "short.duckdb", count=55)
    with duckdb.connect(str(path), read_only=True) as conn:
        output = _load(conn, path)
    for payload in _payloads(output):
        assert all(payload["items"][0][key] is None for key in BREAKOUT_GEOMETRY_FIELD_KEYS)
        assert payload["price_history_status"] == "available"
        assert payload["price_history_unavailable_reasons"] == {}


def test_constant_factor_preserves_geometry_and_real_candidate_scoring(tmp_path):
    path = _seed(tmp_path / "constant.duckdb", split=False)
    with duckdb.connect(str(path), read_only=True) as conn:
        rows = service._load_factor_screen_rows(duckdb_path=str(path), as_of_date=str(DAY), conn=conn)
        factor = service.compute_factor_screen_candidates(as_of_date=rows.snapshot_as_of_date,
            market_state="WARM", rows=rows.rows).payload
        fusion = service.compute_hybrid_fusion_candidates(as_of_date=str(DAY), market_state="WARM",
            sector_rank_payload=None, stock_candidates_payload=None, factor_screen_payload=factor,
            theme_breakout_payload=None, macro_score=.5).payload
        output = _load(conn, path)
    for payload, before in zip(_payloads(output), (factor, fusion), strict=True):
        _assert_geometry(payload, close=100., breakout=100.)
        assert [{key: value for key, value in item.items() if key not in GEOMETRY_KEYS}
                for item in payload["items"]] == before["items"]
        for key, value in before.items():
            if key != "items":
                assert payload[key] == value


def test_split_changes_only_geometry_not_admission_scores_or_ranks(tmp_path):
    split = _seed(tmp_path / "split.duckdb")
    constant = _seed(tmp_path / "constant.duckdb", split=False)
    with duckdb.connect(str(split), read_only=True) as conn:
        split_output = _load(conn, split)
    with duckdb.connect(str(constant), read_only=True) as conn:
        constant_output = _load(conn, constant)
    for left, right in zip(_payloads(split_output), _payloads(constant_output), strict=True):
        assert [{key: value for key, value in item.items() if key not in GEOMETRY_KEYS}
                for item in left["items"]] == [
            {key: value for key, value in item.items() if key not in GEOMETRY_KEYS} for item in right["items"]]


def test_future_prices_and_factors_are_not_used(tmp_path):
    path = _seed(tmp_path / "future.duckdb")
    with duckdb.connect(str(path)) as conn:
        conn.execute("""insert into stock_adjustment_factor values (?, ?, 999, 'future_factor', 'future_run')""",
                     [CODE, str(DAY + timedelta(days=1))])
        conn.execute("""insert into choice_stock_daily_observation
            (stock_code, trade_date, close_value, turn, amount, volume, vendor_version, source_version)
            values (?, ?, 99999, 2, 1000000, 1000000, ?, 'future_price')""",
                     [CODE, str(DAY + timedelta(days=1)), VENDOR])
    with duckdb.connect(str(path), read_only=True) as conn:
        output = _load(conn, path)
    for payload in _payloads(output):
        _assert_geometry(payload)
    assert not {"future_price", "future_factor"}.intersection(output.source_versions)


def test_missing_connection_does_not_reopen_for_verified_geometry(tmp_path, monkeypatch):
    path = _seed(tmp_path / "no-conn.duckdb")
    def reject_verified(*args, **kwargs):
        pytest.fail("Verified price loader requires the caller-owned connection")
    monkeypatch.setattr(service, "_load_signal_stock_histories", reject_verified)
    output = _load(None, path)
    for payload in _payloads(output):
        _assert_unavailable(payload, "price_window_missing")


def test_existing_close_conflict_stays_fail_closed():
    payload = {"items": [{"stock_code": CODE, "close": 51., "breakout_level": 999.,
                           "distance_to_breakout_pct": 99., "pattern": "stale", "pattern_code": "stale"}]}
    result = service._attach_signal_breakout_geometry(payload, close_histories={CODE: (50.,) * 56},
                                                      as_of_date=str(DAY))
    item = result["items"][0]
    assert item["close"] == 51.
    assert all(item[key] is None for key in GEOMETRY_KEYS - {
        "close", "price_as_of_date", "price_stale", "breakout_geometry_unavailable_reason",
    })
    assert payload["items"][0]["breakout_level"] == 999., "Input payload must be immutable"
