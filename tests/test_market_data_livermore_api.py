from __future__ import annotations

import builtins
import logging
import sys
from datetime import date, timedelta
from types import SimpleNamespace

import duckdb
import pytest
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.repositories.choice_client import ChoiceClient
from backend.app.repositories.choice_stock_adapter import ChoiceStockReadiness
from tests.helpers import load_module


def _perf_records(caplog, endpoint: str):
    return [
        record
        for record in caplog.records
        if record.name == "backend.app.api.perf" and getattr(record, "endpoint", None) == endpoint
    ]


def _seed_choice_macro_history(
    duckdb_path: str,
    *,
    start: date,
    closes: list[float],
    quality_flag: str = "ok",
) -> None:
    conn = duckdb.connect(duckdb_path, read_only=False)
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
        rows = []
        for offset, close in enumerate(closes):
            trade_date = (start + timedelta(days=offset)).isoformat()
            rows.append(
                (
                    "CA.CSI300",
                    "沪深300指数收盘价",
                    trade_date,
                    close,
                    "daily",
                    "index",
                    "sv_choice_macro_csi300",
                    "vv_tushare_csi300",
                    "rv_choice_macro_public_history_v1",
                    quality_flag,
                    f"choice_macro_refresh:{trade_date}",
                )
            )
        conn.executemany(
            "insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    finally:
        conn.close()


def _write_csv(path, content: str) -> None:
    path.write_text(content.strip() + "\n", encoding="utf-8-sig")


def _ready_choice_stock_readiness() -> ChoiceStockReadiness:
    return ChoiceStockReadiness(
        ready=True,
        status="ready",
        catalog_path="unit-test-choice-stock-catalog.json",
        missing_input_families=[],
        unconfirmed_fields=[],
        optional_input_status={
            "concept_membership": "catalog_unconfirmed",
            "intraday_movement": "catalog_unconfirmed",
        },
        message="Choice stock catalog is confirmed for unit tests.",
    )


def _seed_choice_stock_replay_coverage(conn: duckdb.DuckDBPyConnection, *, trade_date: str) -> None:
    conn.execute(
        """
        create table if not exists choice_stock_request_audit (
          as_of_date varchar,
          input_family varchar,
          field_key varchar,
          status varchar,
          row_count integer
        )
        """
    )
    conn.execute(
        """
        create table if not exists choice_stock_universe (
          as_of_date varchar,
          stock_code varchar,
          field_key varchar
        )
        """
    )
    conn.execute(
        """
        create table if not exists choice_stock_sector_membership (
          as_of_date varchar,
          stock_code varchar,
          field_key varchar
        )
        """
    )
    conn.execute(
        """
        create table if not exists choice_stock_limit_quality (
          as_of_date varchar,
          stock_code varchar,
          field_key varchar
        )
        """
    )
    conn.execute(
        """
        create table if not exists choice_stock_daily_observation (
          trade_date varchar,
          stock_code varchar,
          field_keys_json varchar,
          pctchange double,
          turn double,
          amplitude double,
          open_value double,
          high_value double,
          low_value double,
          close_value double,
          volume double,
          amount double,
          tradestatus varchar,
          highlimit double,
          lowlimit double
        )
        """
    )
    conn.executemany(
        "insert into choice_stock_request_audit values (?, ?, ?, ?, ?)",
        [
            (trade_date, "stock_universe", "a_share_universe_sector_001004", "completed", 1),
            (trade_date, "sector_membership", "sw2021_industry_membership", "completed", 1),
            (trade_date, "sector_strength", "daily_return_turnover_amplitude", "completed", 1),
            (trade_date, "stock_ohlcv", "daily_ohlcv_amount", "completed", 1),
            (trade_date, "stock_status", "daily_trade_status", "completed", 1),
            (trade_date, "limit_up_quality", "daily_limit_flags", "completed", 1),
            (trade_date, "limit_up_quality", "point_in_time_limit_streaks", "completed", 1),
        ],
    )
    conn.execute(
        "insert into choice_stock_universe values (?, ?, ?)",
        [trade_date, "000001.SZ", "a_share_universe_sector_001004"],
    )
    conn.execute(
        "insert into choice_stock_sector_membership values (?, ?, ?)",
        [trade_date, "000001.SZ", "sw2021_industry_membership"],
    )
    conn.execute(
        "insert into choice_stock_limit_quality values (?, ?, ?)",
        [trade_date, "000001.SZ", "point_in_time_limit_streaks"],
    )
    conn.execute(
        """
        insert into choice_stock_daily_observation values
        (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            trade_date,
            "000001.SZ",
            '["daily_return_turnover_amplitude","daily_ohlcv_amount","daily_trade_status","daily_limit_flags"]',
            0.01,
            1.2,
            0.8,
            10.0,
            10.5,
            9.8,
            10.2,
            1000.0,
            10000.0,
            "trading",
            11.0,
            9.0,
        ],
    )


def _seed_minimal_factor_snapshot(conn: duckdb.DuckDBPyConnection, *, as_of_date: str) -> None:
    conn.execute(
        """
        create table if not exists choice_stock_factor_snapshot (
          as_of_date varchar,
          stock_code varchar,
          pe double,
          pb double,
          ps double,
          roe double,
          gross_margin double,
          three_month_return double,
          twelve_month_return double,
          volatility double,
          dividend_yield double,
          industry varchar
        )
        """
    )
    conn.execute(
        "insert into choice_stock_factor_snapshot values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            as_of_date,
            "688001.SH",
            18.0,
            1.2,
            2.1,
            0.16,
            0.35,
            0.22,
            0.41,
            0.19,
            0.015,
            "电子",
        ],
    )


def _ensure_livermore_candidate_history_test_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Registry DDL omits universe history; create it before materialize schema ensure."""
    conn.execute(
        """
        create table if not exists livermore_stock_candidate_universe_history (
          snapshot_as_of_date varchar,
          stock_code varchar,
          stock_name varchar,
          sector_code varchar,
          sector_name varchar,
          sector_rank integer,
          selection_close double,
          close_strength double,
          gap_norm double,
          breakout_extension_norm double,
          abnormal_turnover double,
          breakout_level double,
          ema10 double,
          ma20 double,
          ma60 double,
          ma120 double,
          forward_trade_date_1d varchar,
          forward_trade_date_5d varchar,
          forward_trade_date_20d varchar,
          return_1d double,
          return_5d double,
          return_20d double,
          market_state varchar,
          data_status varchar,
          formula_version varchar,
          source_version varchar,
          vendor_version varchar,
          rule_version varchar,
          run_id varchar
        )
        """
    )
    from backend.app.tasks.livermore_candidate_history_materialize import (
        ensure_livermore_candidate_history_schema,
    )

    ensure_livermore_candidate_history_schema(conn)


def _build_client(tmp_path, monkeypatch, *, choice_stock_catalog_file=None) -> TestClient:
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(tmp_path / "data_input"))
    sqlite_path = tmp_path / "auth-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    catalog_path = choice_stock_catalog_file or tmp_path / "missing-choice-stock-catalog.json"
    monkeypatch.setenv("MOSS_CHOICE_STOCK_CATALOG_FILE", str(catalog_path))
    get_settings.cache_clear()
    from backend.app.repositories.user_scope_repo import UserScopeRepository

    UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
        user_id="*",
        role=None,
        resource="market_data.livermore_position_snapshot",
        action="import",
    )
    for mod in ("backend.app.main", "backend.app.api"):
        sys.modules.pop(mod, None)
    return TestClient(load_module("backend.app.main", "backend/app/main.py").app)


def test_livermore_signal_confluence_loader_reraises_nested_missing_dependency(monkeypatch) -> None:
    from backend.app.api.routes import market_data_livermore as route_module

    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "backend.app.services.macro_adversarial_signal_service":
            raise ModuleNotFoundError("No module named 'pandas'", name="pandas")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(ModuleNotFoundError) as excinfo:
        route_module.load_macro_adversarial_signal_payload()

    assert excinfo.value.name == "pandas"


def test_livermore_signal_confluence_route_extracts_backtest_window_summary(monkeypatch) -> None:
    from backend.app.api.routes import market_data_livermore as route_module

    expected_summary = {
        "status": "partial",
        "replay_dates_completed": 1,
        "replay_dates_pending": 1,
        "replay_dates_unsupported": 0,
        "replay_dates_proxy_only": 0,
        "completed_rows": 2,
        "pending_rows": 1,
        "unsupported_rows": 0,
        "proxy_only_rows": 0,
        "included_completed_stats_dates": ["2026-05-06"],
        "date_reasons": [],
    }

    monkeypatch.setattr(
        route_module,
        "livermore_candidate_history_envelope",
        lambda **_kwargs: {
            "result": {
                "summary": {"row_count": 99},
                "backtest_window_summary": expected_summary,
            }
        },
    )

    assert route_module.livermore_candidate_history_backtest_window_summary(
        duckdb_path="unused.duckdb",
        stock_code=None,
        snapshot_from="2026-05-06",
        snapshot_to="2026-05-06",
    ) == expected_summary


def test_livermore_signal_confluence_route_rejects_plain_candidate_summary(monkeypatch) -> None:
    from backend.app.api.routes import market_data_livermore as route_module

    monkeypatch.setattr(
        route_module,
        "livermore_candidate_history_envelope",
        lambda **_kwargs: {"result": {"summary": {"status": "partial", "replay_dates_completed": 1}}},
    )

    summary = route_module.livermore_candidate_history_backtest_window_summary(
        duckdb_path="unused.duckdb",
        stock_code=None,
        snapshot_from="2026-05-06",
        snapshot_to="2026-05-06",
    )

    assert summary["status"] == "unsupported"
    assert summary["replay_dates_completed"] == 0


def test_livermore_api_returns_analytical_envelope_and_missing_input_diagnostics(
    tmp_path, monkeypatch
) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_macro_history(
        str(duckdb_path),
        start=date(2026, 2, 1),
        closes=[3200.0 + day * 8 for day in range(65)],
    )
    client = _build_client(tmp_path, monkeypatch)

    response = client.get("/ui/market-data/livermore")

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "analytical"
    assert payload["result_meta"]["formal_use_allowed"] is False
    assert payload["result_meta"]["result_kind"] == "market_data.livermore"
    result = payload["result"]
    assert result["basis"] == "analytical"
    assert result["strategy_name"] == "Livermore A-Share Defended Trend"
    assert result["requested_as_of_date"] is None
    assert result["as_of_date"] == "2026-04-06"
    assert result["market_gate"]["state"] == "WARM"
    assert result["supported_outputs"] == ["market_gate"]
    assert "stock_candidates" not in result
    unsupported_by_key = {row["key"]: row for row in result["unsupported_outputs"]}
    assert "Choice stock catalog is missing" in unsupported_by_key["sector_rank"]["reason"]
    assert "Choice stock catalog is missing" in unsupported_by_key["stock_candidates"]["reason"]
    assert "Choice stock catalog is missing" in unsupported_by_key["mean_reversion_candidates"]["reason"]
    assert "choice_stock_factor_snapshot" in unsupported_by_key["factor_screen_candidates"]["reason"]
    assert "Choice stock catalog is missing" in unsupported_by_key["theme_breakout"]["reason"]
    assert "hybrid fusion" in unsupported_by_key["hybrid_fusion"]["reason"].lower()
    assert "candidate source" in unsupported_by_key["hybrid_fusion"]["reason"].lower()
    unsupported_keys = {row["key"] for row in result["unsupported_outputs"]}
    assert unsupported_keys == {
        "sector_rank",
        "stock_candidates",
        "mean_reversion_candidates",
        "factor_screen_candidates",
        "theme_breakout",
        "hybrid_fusion",
        "risk_exit",
    }
    gap_by_family = {row["input_family"]: row for row in result["data_gaps"]}
    assert gap_by_family["breadth"]["status"] == "missing"
    assert gap_by_family["limit_up_quality"]["status"] == "missing"
    assert gap_by_family["sector_strength"]["status"] == "missing"
    assert "Choice stock catalog is missing" in gap_by_family["sector_strength"]["evidence"]
    assert gap_by_family["stock_universe"]["status"] == "missing"
    assert "Choice stock catalog is missing" in gap_by_family["stock_universe"]["evidence"]
    assert gap_by_family["position_risk"]["status"] == "missing"
    readiness_by_key = {row["key"]: row for row in result["rule_readiness"]}
    assert readiness_by_key["market_gate"]["status"] == "partial"
    assert readiness_by_key["sector_rank"]["status"] == "missing"
    assert readiness_by_key["stock_pivot"]["status"] == "blocked"
    assert readiness_by_key["risk_exit"]["status"] == "blocked"
    diag_codes = {row["code"] for row in result["diagnostics"]}
    assert "LIVERMORE_BREADTH_MISSING" in diag_codes
    assert "LIVERMORE_LIMIT_UP_QUALITY_MISSING" in diag_codes
    assert "LIVERMORE_SECTOR_INPUTS_MISSING" in diag_codes
    assert "LIVERMORE_STOCK_INPUTS_MISSING" in diag_codes
    assert "LIVERMORE_RISK_INPUTS_MISSING" in diag_codes
    diag_by_code = {row["code"]: row for row in result["diagnostics"]}
    assert "Choice stock catalog is missing" in diag_by_code["LIVERMORE_STOCK_INPUTS_MISSING"]["message"]
    get_settings.cache_clear()


def test_livermore_api_marks_hybrid_fusion_unsupported_when_gate_is_pending_data(
    tmp_path, monkeypatch
) -> None:
    from backend.app.services.market_data_livermore_service import livermore_strategy_envelope

    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_macro_history(
        str(duckdb_path),
        start=date(2026, 2, 1),
        closes=[3200.0 + day * 8 for day in range(65)],
    )
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        _seed_minimal_factor_snapshot(conn, as_of_date="2026-04-06")
    finally:
        conn.close()

    envelope = livermore_strategy_envelope(
        duckdb_path=str(duckdb_path),
        stock_readiness=_ready_choice_stock_readiness(),
    )

    result = envelope["result"]
    assert result["market_gate"]["state"] == "WARM"
    assert "factor_screen_candidates" in result["supported_outputs"]
    assert "hybrid_fusion" in result["supported_outputs"]
    hybrid = result["hybrid_fusion_candidates"]
    assert hybrid["candidate_count"] >= 1
    assert len(hybrid["items"]) >= 1
    get_settings.cache_clear()


def test_livermore_api_embeds_cycle_rotation_framework_without_trade_claims(
    tmp_path, monkeypatch
) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_macro_history(
        str(duckdb_path),
        start=date(2026, 2, 1),
        closes=[3200.0 + day * 8 for day in range(65)],
    )
    client = _build_client(tmp_path, monkeypatch)

    response = client.get("/ui/market-data/livermore")

    assert response.status_code == 200
    framework = response.json()["result"]["cycle_rotation_framework"]
    assert framework["strategy_name"] == "A-share cycle rotation research framework"
    assert framework["observation_only"] is True
    assert framework["score_formula"] == (
        "CycleScore = 0.30 Macro + 0.35 Industry + 0.20 MarketFlow + 0.15 ValuationSupport"
    )
    assert "LifeCourtScore" in framework["lifecourt_formula"]
    assert framework["fusion_policy"]["conflict_policy"] == "cycle_filter_life_overlay"
    assert framework["lifecourt_overlay"]["implementation_stage"] == "proxy_reconstruction"
    layer_by_key = {row["key"]: row for row in framework["layers"]}
    assert set(layer_by_key) == {
        "macro_direction",
        "industry_cycle",
        "market_flow",
        "valuation_support",
        "execution_constraints",
    }
    assert layer_by_key["macro_direction"]["weight"] == 0.30
    assert "PMI" in layer_by_key["macro_direction"]["missing_inputs"]
    assert "credit_impulse" in layer_by_key["macro_direction"]["missing_inputs"]
    assert layer_by_key["execution_constraints"]["status"] == "verification_pending"
    assert any("industry cap" in item for item in framework["constraints"])
    serialized = str(framework).lower()
    assert "buy" not in serialized
    assert "sell" not in serialized
    assert "order" not in serialized
    get_settings.cache_clear()


def test_livermore_api_marks_landed_cycle_inputs_available_without_fabricating_missing_sources(
    tmp_path, monkeypatch
) -> None:
    from backend.app.services.market_data_livermore_service import livermore_strategy_envelope

    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_macro_history(
        str(duckdb_path),
        start=date(2026, 2, 1),
        closes=[3200.0 + day * 8 for day in range(110)],
    )
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.executemany(
            "insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "CA.CSI300_PE",
                    "CSI300 PE",
                    "2026-05-08",
                    14.5,
                    "daily",
                    "x",
                    "sv_pe",
                    "vv_pe",
                    "rv_choice_macro",
                    "ok",
                    "run-pe",
                ),
                (
                    "EMM00166466",
                    "China 10Y treasury yield",
                    "2026-05-08",
                    2.1,
                    "daily",
                    "%",
                    "sv_cn10y",
                    "vv_cn10y",
                    "rv_choice_macro",
                    "ok",
                    "run-cn10y",
                ),
                (
                    "M0017126",
                    "Manufacturing PMI",
                    "2026-04-01",
                    51.2,
                    "monthly",
                    "index",
                    "sv_pmi",
                    "vv_pmi",
                    "rv_choice_macro",
                    "ok",
                    "run-pmi",
                ),
                (
                    "M5525763",
                    "Social financing YoY",
                    "2026-03-01",
                    8.4,
                    "monthly",
                    "%",
                    "sv_sf",
                    "vv_sf",
                    "rv_choice_macro",
                    "ok",
                    "run-sf-1",
                ),
                (
                    "M5525763",
                    "Social financing YoY",
                    "2026-04-01",
                    9.1,
                    "monthly",
                    "%",
                    "sv_sf",
                    "vv_sf",
                    "rv_choice_macro",
                    "ok",
                    "run-sf-2",
                ),
            ],
        )
        conn.execute(
            """
            create table fact_livermore_gate_supplement_daily (
              trade_date varchar,
              breadth_5d double,
              limit_up_quality_ok boolean,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            "insert into fact_livermore_gate_supplement_daily values (?, ?, ?, ?, ?, ?, ?)",
            ["2026-05-08", 1.0, False, "sv_t", "vv_t", "rv_t", "run_t"],
        )
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              close_value double,
              turn double,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-05-07", "000001.SZ", 10.0, 1.1, "sv_obs", "vv_obs", "rv_obs", "run-obs"),
                ("2026-05-08", "000001.SZ", 10.2, 1.3, "sv_obs", "vv_obs", "rv_obs", "run-obs"),
            ],
        )
        conn.execute(
            """
            create table choice_stock_factor_snapshot (
              as_of_date varchar,
              stock_code varchar,
              pe double,
              pb double,
              ps double,
              roe double,
              gross_margin double,
              three_month_return double,
              twelve_month_return double,
              volatility double,
              dividend_yield double,
              industry varchar
            )
            """
        )
        conn.executemany(
            "insert into choice_stock_factor_snapshot values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "2026-05-08",
                    f"60000{i}.SH",
                    10.0 + i,
                    1.1 + i * 0.1,
                    0.8 + i * 0.05,
                    0.08 + i * 0.01,
                    0.25 + i * 0.02,
                    0.01 + i * 0.01,
                    0.05 + i * 0.02,
                    0.18 + i * 0.01,
                    0.01 + i * 0.002,
                    "electronics",
                )
                for i in range(1, 8)
            ],
        )
    finally:
        conn.close()

    envelope = livermore_strategy_envelope(
        duckdb_path=str(duckdb_path),
        as_of_date="2026-05-08",
        stock_readiness=_ready_choice_stock_readiness(),
    )

    result = envelope["result"]
    layer_by_key = {row["key"]: row for row in result["cycle_rotation_framework"]["layers"]}
    assert "price_spread" in layer_by_key["macro_direction"]["available_inputs"]
    assert "price_spread" not in layer_by_key["macro_direction"]["missing_inputs"]
    assert "PMI" in layer_by_key["macro_direction"]["available_inputs"]
    assert "credit_impulse" in layer_by_key["macro_direction"]["available_inputs"]
    assert result["cycle_rotation_framework"]["macro_layer"]["ready"] is True
    assert result["cycle_rotation_framework"]["macro_layer"]["macro_score"] is not None
    assert result["hybrid_fusion_candidates"]["macro_score"] is not None
    assert "turnover_persistence" in layer_by_key["market_flow"]["available_inputs"]
    assert "turnover_persistence" not in layer_by_key["market_flow"]["missing_inputs"]
    assert "northbound_flow" in layer_by_key["market_flow"]["missing_inputs"]
    assert "valuation_percentile_history" in layer_by_key["valuation_support"]["available_inputs"]
    assert "valuation_percentile_history" not in layer_by_key["valuation_support"]["missing_inputs"]
    assert "earnings_revision" in layer_by_key["valuation_support"]["missing_inputs"]
    gap_by_family = {row["input_family"]: row for row in result["data_gaps"]}
    assert gap_by_family["price_spread"]["status"] == "ready"
    assert "CA.CSI300_PE" in gap_by_family["price_spread"]["evidence"]
    assert gap_by_family["PMI"]["status"] == "ready"
    assert gap_by_family["credit_impulse"]["status"] == "ready"
    assert gap_by_family["macro_score"]["status"] == "ready"
    assert gap_by_family["turnover_persistence"]["status"] == "ready"
    assert gap_by_family["valuation_percentile_history"]["status"] == "ready"
    assert "fact_choice_macro_daily" in envelope["result_meta"]["tables_used"]
    assert "choice_stock_daily_observation" in envelope["result_meta"]["tables_used"]
    assert "choice_stock_factor_snapshot" in envelope["result_meta"]["tables_used"]
    get_settings.cache_clear()


def test_cycle_proxy_backtest_api_happy_path(tmp_path) -> None:
    from backend.app.services.livermore_candidate_history_service import (
        livermore_candidate_history_cycle_proxy_backtest_envelope,
    )

    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _ensure_livermore_candidate_history_test_schema(conn)
        conn.executemany(
            """
            insert into livermore_candidate_history (
              snapshot_as_of_date, stock_code, stock_name, candidate_rank,
              selection_close, forward_trade_date_1d, forward_trade_date_5d, forward_trade_date_20d,
              return_1d, return_5d, return_20d, data_status,
              formula_version, source_version, vendor_version, rule_version, run_id, signal_kind, signal_evidence_json
            ) values (?, ?, ?, ?, 10.0, ?, ?, ?, ?, ?, ?, 'complete', 'fv1', 'sv_proxy', 'vv_proxy', 'rv_proxy', ?, 'stock_candidate', ?)
            """,
            [
                (
                    "2026-05-01",
                    "000001.SZ",
                    "Proxy A",
                    1,
                    "2026-05-02",
                    "2026-05-08",
                    "2026-05-29",
                    0.10,
                    0.12,
                    0.20,
                    "run-1",
                    '{"market_state":"WARM"}',
                ),
                (
                    "2026-05-02",
                    "000002.SZ",
                    "Proxy B",
                    1,
                    "2026-05-03",
                    "2026-05-09",
                    "2026-05-30",
                    0.20,
                    0.18,
                    0.10,
                    "run-2",
                    '{"market_state":"HOT"}',
                ),
            ],
        )
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-01")
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-05-02")
    finally:
        conn.close()

    body = livermore_candidate_history_cycle_proxy_backtest_envelope(
        duckdb_path=str(db_path),
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-02",
    )
    assert body["result_meta"]["rule_version"] == "rv_livermore_cycle_proxy_backtest_v1"
    assert body["result"]["status"] == "proxy"
    assert body["result"]["summary"]["sample_days"] == 1
    assert body["result"]["summary"]["cumulative_return"] == 0.12


def test_candidate_history_portfolio_backtest_api_happy_path(tmp_path) -> None:
    from backend.app.services.livermore_candidate_history_service import (
        livermore_candidate_history_portfolio_backtest_envelope,
    )

    db_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _ensure_livermore_candidate_history_test_schema(conn)
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              close_value double
            )
            """
        )
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?, ?)",
            [
                ("2026-05-01", "000001.SZ", 100.0),
                ("2026-05-02", "000001.SZ", 105.0),
            ],
        )
        conn.execute(
            """
            insert into livermore_candidate_history (
              snapshot_as_of_date, stock_code, stock_name, candidate_rank,
              selection_close, data_status, formula_version, source_version,
              vendor_version, rule_version, run_id, signal_kind, signal_evidence_json
            ) values (
              '2026-05-01', '000001.SZ', 'Proxy A', 1,
              100.0, 'pending', 'fv1', 'sv_portfolio', 'vv_portfolio',
              'rv_portfolio', 'run-1', 'stock_candidate', '{"market_state":"WARM"}'
            )
            """
        )
    finally:
        conn.close()

    body = livermore_candidate_history_portfolio_backtest_envelope(
        duckdb_path=str(db_path),
        snapshot_from="2026-05-01",
        snapshot_to="2026-05-02",
    )
    assert body["result_meta"]["rule_version"] == "rv_livermore_candidate_history_portfolio_backtest_v1"
    assert body["result"]["status"] == "portfolio_proxy"
    assert body["result"]["summary"]["invested_rebalance_count"] == 1
    assert body["result"]["summary"]["cumulative_return"] > 0


def test_livermore_api_missing_stock_catalog_does_not_call_choice_stock_api(tmp_path, monkeypatch) -> None:
    def fail_choice_call(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("Choice stock API should not be called while catalog is missing.")

    monkeypatch.setattr(ChoiceClient, "css", fail_choice_call)
    monkeypatch.setattr(ChoiceClient, "csd", fail_choice_call)
    client = _build_client(tmp_path, monkeypatch)

    response = client.get("/ui/market-data/livermore")

    assert response.status_code == 200
    result = response.json()["result"]
    assert "stock_candidates" not in result
    assert any("Choice stock catalog is missing" in row["reason"] for row in result["unsupported_outputs"])
    get_settings.cache_clear()


def test_livermore_api_incomplete_stock_catalog_stays_fail_closed(tmp_path, monkeypatch) -> None:
    catalog_path = tmp_path / "choice_stock_catalog.json"
    catalog_path.write_text(
        '{"catalog_version":"test_empty","vendor_name":"choice","generated_from":"unit_test","fields":[]}',
        encoding="utf-8",
    )
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_macro_history(
        str(duckdb_path),
        start=date(2026, 2, 1),
        closes=[3200.0 + day * 5 for day in range(65)],
    )
    client = _build_client(tmp_path, monkeypatch, choice_stock_catalog_file=catalog_path)

    response = client.get("/ui/market-data/livermore")

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["supported_outputs"] == ["market_gate"]
    assert "stock_candidates" not in result
    unsupported_by_key = {row["key"]: row for row in result["unsupported_outputs"]}
    assert "Choice stock catalog is incomplete" in unsupported_by_key["stock_candidates"]["reason"]
    assert "Choice stock catalog is incomplete" in unsupported_by_key["mean_reversion_candidates"]["reason"]
    get_settings.cache_clear()


def test_livermore_strategy_default_execution_policy_uses_exp3b_for_stock_candidates(monkeypatch) -> None:
    from backend.app.services import market_data_livermore_service as service

    seen_policies: list[str] = []

    monkeypatch.setattr(
        service,
        "_load_sector_rank_inputs",
        lambda **_kwargs: ([object()], ["choice_stock_sector_membership"], [], []),
    )
    monkeypatch.setattr(
        service,
        "compute_sector_rank",
        lambda **_kwargs: SimpleNamespace(
            ready=True,
            payload={"items": [{"rank": 1, "sector_code": "801001", "sector_name": "AI"}]},
        ),
    )
    monkeypatch.setattr(
        service,
        "_load_stock_candidate_snapshots",
        lambda **_kwargs: ([SimpleNamespace(limit_ratio=0.1)], ["choice_stock_daily_observation"], [], []),
    )

    def fake_compute_stock_candidates(**kwargs):
        seen_policies.append(kwargs["policy_name"])
        return SimpleNamespace(
            payload={"selection_policy": kwargs["policy_name"], "candidate_count": 0, "items": []}
        )

    monkeypatch.setattr(service, "compute_stock_candidates", fake_compute_stock_candidates)
    monkeypatch.setattr(
        service,
        "_load_factor_screen_rows",
        lambda **_kwargs: service._FactorScreenLoadResult(
            rows=[],
            snapshot_as_of_date=None,
            tables_used=[],
            unavailable_reason="factor rows unavailable in policy unit test.",
        ),
    )
    monkeypatch.setattr(
        service,
        "_load_theme_breakout_snapshots",
        lambda **_kwargs: ([], [], [], [], service._ThemeBreakoutEvidenceProvenance()),
    )
    monkeypatch.setattr(service, "_load_risk_exit_snapshots", lambda **_kwargs: ([], [], [], []))
    monkeypatch.setattr(service, "_risk_exit_input_block_reason", lambda **_kwargs: "")

    outputs = service._load_choice_stock_outputs(
        duckdb_path="unused.duckdb",
        as_of_date="2026-05-13",
        market_state="OVERHEAT",
        stock_readiness=_ready_choice_stock_readiness(),
        backfill_mode=True,
    )

    assert seen_policies == ["exp3b"]
    assert outputs.stock_candidates_payload is not None
    assert outputs.stock_candidates_payload["selection_policy"] == "exp3b"


def test_livermore_strategy_explicit_stock_candidate_policy_overrides_execution_default(monkeypatch) -> None:
    from backend.app.services import market_data_livermore_service as service

    seen_policies: list[str] = []

    monkeypatch.setattr(
        service,
        "_load_sector_rank_inputs",
        lambda **_kwargs: ([object()], ["choice_stock_sector_membership"], [], []),
    )
    monkeypatch.setattr(
        service,
        "compute_sector_rank",
        lambda **_kwargs: SimpleNamespace(
            ready=True,
            payload={"items": [{"rank": 1, "sector_code": "801001", "sector_name": "AI"}]},
        ),
    )
    monkeypatch.setattr(
        service,
        "_load_stock_candidate_snapshots",
        lambda **_kwargs: ([SimpleNamespace(limit_ratio=0.1)], ["choice_stock_daily_observation"], [], []),
    )

    def fake_compute_stock_candidates(**kwargs):
        seen_policies.append(kwargs["policy_name"])
        return SimpleNamespace(
            payload={"selection_policy": kwargs["policy_name"], "candidate_count": 1, "items": []}
        )

    monkeypatch.setattr(service, "compute_stock_candidates", fake_compute_stock_candidates)
    monkeypatch.setattr(
        service,
        "_load_factor_screen_rows",
        lambda **_kwargs: service._FactorScreenLoadResult(
            rows=[],
            snapshot_as_of_date=None,
            tables_used=[],
            unavailable_reason="factor rows unavailable in policy unit test.",
        ),
    )
    monkeypatch.setattr(
        service,
        "_load_theme_breakout_snapshots",
        lambda **_kwargs: ([], [], [], [], service._ThemeBreakoutEvidenceProvenance()),
    )
    monkeypatch.setattr(service, "_load_risk_exit_snapshots", lambda **_kwargs: ([], [], [], []))
    monkeypatch.setattr(service, "_risk_exit_input_block_reason", lambda **_kwargs: "")

    outputs = service._load_choice_stock_outputs(
        duckdb_path="unused.duckdb",
        as_of_date="2026-05-13",
        market_state="OVERHEAT",
        stock_readiness=_ready_choice_stock_readiness(),
        backfill_mode=True,
        stock_candidate_policy="default",
    )

    assert seen_policies == ["default"]
    assert outputs.stock_candidates_payload is not None
    assert outputs.stock_candidates_payload["selection_policy"] == "default"


def test_livermore_strategy_default_execution_pauses_theme_breakout_in_overheat(monkeypatch) -> None:
    from backend.app.services import market_data_livermore_service as service

    called = False

    monkeypatch.setattr(
        service,
        "_load_sector_rank_inputs",
        lambda **_kwargs: ([object()], ["choice_stock_sector_membership"], [], []),
    )
    monkeypatch.setattr(
        service,
        "compute_sector_rank",
        lambda **_kwargs: SimpleNamespace(
            ready=True,
            payload={"items": [{"rank": 1, "sector_code": "801001", "sector_name": "AI"}]},
        ),
    )
    monkeypatch.setattr(service, "_load_stock_candidate_snapshots", lambda **_kwargs: ([], [], [], []))
    monkeypatch.setattr(
        service,
        "compute_stock_candidates",
        lambda **kwargs: SimpleNamespace(payload={"selection_policy": kwargs["policy_name"], "items": []}),
    )
    monkeypatch.setattr(
        service,
        "_load_factor_screen_rows",
        lambda **_kwargs: service._FactorScreenLoadResult(
            rows=[],
            snapshot_as_of_date=None,
            tables_used=[],
            unavailable_reason="factor rows unavailable in policy unit test.",
        ),
    )
    monkeypatch.setattr(
        service,
        "_load_theme_breakout_snapshots",
        lambda **_kwargs: ([SimpleNamespace(stock_code="000001.SZ")], ["choice_stock_daily_observation"], [], [], service._ThemeBreakoutEvidenceProvenance()),
    )

    def fake_compute_theme_breakout(**_kwargs):
        nonlocal called
        called = True
        return SimpleNamespace(payload={"items": [{"theme_key": "concept:C1", "items": [{"stock_code": "000001.SZ"}]}]})

    monkeypatch.setattr(service, "compute_theme_breakout", fake_compute_theme_breakout)
    monkeypatch.setattr(service, "_load_risk_exit_snapshots", lambda **_kwargs: ([], [], [], []))
    monkeypatch.setattr(service, "_risk_exit_input_block_reason", lambda **_kwargs: "")

    outputs = service._load_choice_stock_outputs(
        duckdb_path="unused.duckdb",
        as_of_date="2026-05-13",
        market_state="OVERHEAT",
        stock_readiness=_ready_choice_stock_readiness(),
        backfill_mode=True,
    )

    assert called is False
    assert outputs.theme_breakout_payload is None
    supported, unsupported = service._build_supported_outputs(
        "OVERHEAT",
        stock_readiness=_ready_choice_stock_readiness(),
        stock_outputs=outputs,
    )
    assert "theme_breakout" not in supported
    assert "OVERHEAT" in {row["key"]: row["reason"] for row in unsupported}["theme_breakout"]


def test_livermore_api_returns_explicit_no_data_state(tmp_path, monkeypatch) -> None:
    client = _build_client(tmp_path, monkeypatch)

    response = client.get("/ui/market-data/livermore")

    assert response.status_code == 200
    payload = response.json()
    result = payload["result"]
    assert result["market_gate"]["state"] == "NO_DATA"
    assert result["supported_outputs"] == []
    assert any(row["key"] == "market_gate" for row in result["unsupported_outputs"])
    assert any(row["code"] == "LIVERMORE_BROAD_INDEX_NO_DATA" for row in result["diagnostics"])
    readiness_by_key = {row["key"]: row for row in result["rule_readiness"]}
    assert "broad_index_history" in readiness_by_key["market_gate"]["missing_inputs"]
    get_settings.cache_clear()


def test_livermore_stock_detail_logs_api_perf(tmp_path, monkeypatch, caplog) -> None:
    client = _build_client(tmp_path, monkeypatch)

    with caplog.at_level(logging.INFO, logger="backend.app.api.perf"):
        response = client.get(
            "/ui/market-data/livermore/stock-detail",
            params={"stock_code": "000001.SZ", "lookback": 5},
        )

    assert response.status_code == 200
    records = _perf_records(caplog, "/ui/market-data/livermore/stock-detail")
    assert records
    record = records[-1]
    assert record.getMessage() == "moss_api_perf"
    assert getattr(record, "duration_ms") >= 0
    assert getattr(record, "result_kind") == "market_data.livermore.stock_detail"
    assert getattr(record, "trace_id")
    assert getattr(record, "duckdb_statement_count") is None
    get_settings.cache_clear()


def test_livermore_api_returns_explicit_stale_state_and_requested_date_resolution(
    tmp_path, monkeypatch
) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_macro_history(
        str(duckdb_path),
        start=date(2026, 2, 1),
        closes=[3200.0 + day * 6 for day in range(65)],
        quality_flag="stale",
    )
    client = _build_client(tmp_path, monkeypatch)

    response = client.get(
        "/ui/market-data/livermore",
        params={"as_of_date": "2026-04-10"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["quality_flag"] == "stale"
    assert payload["result_meta"]["vendor_status"] == "vendor_stale"
    assert payload["result_meta"]["fallback_mode"] == "latest_snapshot"
    result = payload["result"]
    assert result["requested_as_of_date"] == "2026-04-10"
    assert result["as_of_date"] == "2026-04-06"
    assert result["market_gate"]["state"] == "STALE"
    condition_by_key = {row["key"]: row for row in result["market_gate"]["conditions"]}
    assert condition_by_key["csi300_close_gt_ma60"]["status"] == "stale"
    assert any(row["code"] == "LIVERMORE_BROAD_INDEX_STALE" for row in result["diagnostics"])
    get_settings.cache_clear()


def test_livermore_api_factor_screen_uses_snapshot_date_and_degrades_without_enrichment_tables(
    tmp_path, monkeypatch
) -> None:
    from backend.app.services.market_data_livermore_service import livermore_strategy_envelope

    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_macro_history(
        str(duckdb_path),
        start=date(2026, 2, 1),
        closes=[3200.0 + day * 8 for day in range(110)],
    )
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_livermore_gate_supplement_daily (
              trade_date varchar,
              breadth_5d double,
              limit_up_quality_ok boolean,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            "insert into fact_livermore_gate_supplement_daily values (?, ?, ?, ?, ?, ?, ?)",
            ["2026-05-08", 1.0, False, "sv_t", "vv_t", "rv_t", "run_t"],
        )
        conn.execute(
            """
            create table choice_stock_factor_snapshot (
              as_of_date varchar,
              stock_code varchar,
              pe double,
              pb double,
              ps double,
              roe double,
              gross_margin double,
              three_month_return double,
              twelve_month_return double,
              volatility double,
              dividend_yield double,
              industry varchar
            )
            """
        )
        conn.executemany(
            "insert into choice_stock_factor_snapshot values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "2026-04-30",
                    f"60000{i}.SH",
                    10.0 + i,
                    1.1 + i * 0.1,
                    0.8 + i * 0.05,
                    0.08 + i * 0.01,
                    0.25 + i * 0.02,
                    0.01 + i * 0.01,
                    0.05 + i * 0.02,
                    0.18 + i * 0.01,
                    0.01 + i * 0.002,
                    "电力设备",
                )
                for i in range(1, 8)
            ],
        )
    finally:
        conn.close()

    envelope = livermore_strategy_envelope(
        duckdb_path=str(duckdb_path),
        as_of_date="2026-05-08",
        stock_readiness=_ready_choice_stock_readiness(),
    )

    result = envelope["result"]
    payload = result["factor_screen_candidates"]
    assert payload["as_of_date"] == "2026-04-30"
    assert payload["factor_snapshot_as_of_date"] == "2026-04-30"
    assert payload["observation_only"] is True
    assert payload["candidate_count"] >= 1
    assert payload["items"][0]["stock_name"].endswith(".SH")
    assert result["market_gate"]["state"] == "HOT"
    hybrid = result["hybrid_fusion_candidates"]
    assert hybrid["observation_only"] is True
    assert hybrid["candidate_count"] >= 1
    assert hybrid["items"][0]["stock_code"] == payload["items"][0]["stock_code"]
    assert hybrid["items"][0]["evidence"]["source_kinds"] == ["factor_screen"]
    assert "choice_stock_factor_snapshot" in envelope["result_meta"]["tables_used"]
    assert "choice_stock_universe" not in envelope["result_meta"]["tables_used"]
    assert "choice_stock_sector_membership" not in envelope["result_meta"]["tables_used"]
    assert result["supported_outputs"] == ["market_gate", "factor_screen_candidates", "hybrid_fusion"]
    unsupported_by_key = {row["key"]: row for row in result["unsupported_outputs"]}
    assert "factor_screen_candidates" not in unsupported_by_key
    assert "hybrid_fusion" not in unsupported_by_key


def test_livermore_api_factor_screen_reports_enrichment_tables_when_used(tmp_path, monkeypatch) -> None:
    from backend.app.services.market_data_livermore_service import livermore_strategy_envelope

    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_macro_history(
        str(duckdb_path),
        start=date(2026, 2, 1),
        closes=[3200.0 + day * 8 for day in range(110)],
    )
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table choice_stock_factor_snapshot (
              as_of_date varchar,
              stock_code varchar,
              pe double,
              pb double,
              ps double,
              roe double,
              gross_margin double,
              three_month_return double,
              twelve_month_return double,
              volatility double,
              dividend_yield double,
              industry varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_universe (
              as_of_date varchar,
              stock_code varchar,
              stock_name varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_sector_membership (
              as_of_date varchar,
              stock_code varchar,
              sw2021code varchar,
              sw2021 varchar
            )
            """
        )
        factor_rows = [
            (
                "2026-04-30",
                f"60001{i}.SH",
                9.0 + i,
                1.0 + i * 0.1,
                0.7 + i * 0.05,
                0.09 + i * 0.01,
                0.28 + i * 0.02,
                0.02 + i * 0.01,
                0.06 + i * 0.02,
                0.16 + i * 0.01,
                0.012 + i * 0.002,
                "电子",
            )
            for i in range(1, 8)
        ]
        conn.executemany(
            "insert into choice_stock_factor_snapshot values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            factor_rows,
        )
        conn.executemany(
            "insert into choice_stock_universe values (?, ?, ?)",
            [
                ("2026-04-29", row[1], f"As-of Name {idx}")
                for idx, row in enumerate(factor_rows, start=1)
            ]
            + [
                ("2026-05-08", row[1], f"Future Name {idx}")
                for idx, row in enumerate(factor_rows, start=1)
            ],
        )
        conn.executemany(
            "insert into choice_stock_sector_membership values (?, ?, ?, ?)",
            [("2026-04-29", row[1], "801080", "Electronics") for row in factor_rows]
            + [("2026-05-08", row[1], "801999", "Future Sector") for row in factor_rows],
        )
    finally:
        conn.close()

    envelope = livermore_strategy_envelope(
        duckdb_path=str(duckdb_path),
        as_of_date="2026-05-08",
        stock_readiness=_ready_choice_stock_readiness(),
    )

    result = envelope["result"]
    payload = result["factor_screen_candidates"]
    assert payload["as_of_date"] == "2026-04-30"
    assert payload["factor_snapshot_as_of_date"] == "2026-04-30"
    assert payload["items"][0]["stock_name"].startswith("As-of Name")
    assert payload["items"][0]["sector_code"] == "801080"
    tables_used = envelope["result_meta"]["tables_used"]
    assert "choice_stock_factor_snapshot" in tables_used
    assert "choice_stock_universe" in tables_used
    assert "choice_stock_sector_membership" in tables_used


def test_livermore_sector_rank_loader_attaches_universe_stock_names(tmp_path) -> None:
    from backend.app.services.market_data_livermore_service import _load_sector_rank_inputs

    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table choice_stock_universe (
              as_of_date varchar,
              stock_code varchar,
              stock_name varchar,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_sector_membership (
              as_of_date varchar,
              stock_code varchar,
              sw2021code varchar,
              sw2021 varchar,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              pctchange double,
              turn double,
              amplitude double,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        conn.execute(
            "insert into choice_stock_universe values ('2026-05-08', '000001.SZ', 'Alpha Bank', 'sv_u', 'vv_u')"
        )
        conn.execute(
            "insert into choice_stock_universe values ('2026-05-09', '000001.SZ', 'Future Alpha', 'sv_u_future', 'vv_u_future')"
        )
        conn.executemany(
            "insert into choice_stock_sector_membership values (?, ?, ?, ?, ?, ?)",
            [
                ("2026-05-08", "000001.SZ", "801780", "Bank", "sv_s", "vv_s"),
                ("2026-05-08", "600000.SH", "801780", "Bank", "sv_s", "vv_s"),
            ],
        )
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-05-08", "000001.SZ", 4.0, 4.0, 4.0, "sv_d", "vv_d"),
                ("2026-05-08", "600000.SH", 5.0, 6.0, 5.0, "sv_d", "vv_d"),
            ],
        )
    finally:
        conn.close()

    rows, tables_used, source_versions, vendor_versions = _load_sector_rank_inputs(
        duckdb_path=str(duckdb_path),
        as_of_date="2026-05-08",
    )

    by_code = {row.stock_code: row for row in rows}
    assert by_code["000001.SZ"].stock_name == "Alpha Bank"
    assert by_code["600000.SH"].stock_name == "600000.SH"
    assert "Future Alpha" not in {row.stock_name for row in rows}
    assert "choice_stock_universe" in tables_used
    assert {"sv_d", "sv_s"} <= set(source_versions)
    assert {"vv_d", "vv_s"} <= set(vendor_versions)


def test_livermore_stock_candidate_loader_attaches_latest_factor_snapshot(tmp_path) -> None:
    from backend.app.services.market_data_livermore_service import _load_stock_candidate_snapshots

    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table choice_stock_universe (
              as_of_date varchar,
              stock_code varchar,
              stock_name varchar,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_sector_membership (
              as_of_date varchar,
              stock_code varchar,
              sw2021code varchar,
              sw2021 varchar,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              open_value double,
              high_value double,
              low_value double,
              close_value double,
              turn double,
              highlimit double,
              lowlimit double,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_limit_quality (
              as_of_date varchar,
              stock_code varchar,
              issurgedlimit varchar,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_factor_snapshot (
              as_of_date varchar,
              stock_code varchar,
              pe double,
              pb double,
              ps double,
              roe double,
              gross_margin double,
              three_month_return double,
              twelve_month_return double,
              volatility double,
              dividend_yield double,
              industry varchar
            )
            """
        )
        conn.execute(
            "insert into choice_stock_universe values ('2026-05-08', '000001.SZ', 'Alpha', 'sv_u', 'vv_u')"
        )
        conn.execute(
            "insert into choice_stock_universe values ('2026-05-09', '000001.SZ', 'Future Alpha', 'sv_u_future', 'vv_u_future')"
        )
        conn.execute(
            "insert into choice_stock_sector_membership values ('2026-05-08', '000001.SZ', '801001', 'AI', 'sv_s', 'vv_s')"
        )
        conn.execute(
            "insert into choice_stock_sector_membership values ('2026-05-09', '000001.SZ', '801999', 'Future AI', 'sv_s_future', 'vv_s_future')"
        )
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-05-07", "000001.SZ", 9.8, 10.1, 9.7, 10.0, 1.0, 11.0, 9.0, "sv_d", "vv_d"),
                ("2026-05-08", "000001.SZ", 10.2, 10.6, 10.1, 10.5, 1.4, 11.0, 9.0, "sv_d", "vv_d"),
            ],
        )
        conn.execute(
            "insert into choice_stock_limit_quality values ('2026-05-08', '000001.SZ', '否', 'sv_l', 'vv_l')"
        )
        conn.executemany(
            "insert into choice_stock_factor_snapshot values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-05-07", "000001.SZ", 12.0, 1.4, 1.8, 0.16, 0.32, 0.08, 0.18, 0.24, 0.025, "AI"),
                ("2026-05-09", "000001.SZ", 99.0, 9.9, 9.9, -0.10, -0.20, -0.30, -0.40, 0.90, 0.0, "AI"),
            ],
        )
    finally:
        conn.close()

    snapshots, tables_used, _source_versions, _vendor_versions = _load_stock_candidate_snapshots(
        duckdb_path=str(duckdb_path),
        as_of_date="2026-05-08",
        sector_rank_payload={"items": [{"rank": 1, "sector_code": "801001", "sector_name": "AI"}]},
    )

    assert "choice_stock_factor_snapshot" in tables_used
    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.stock_name == "Alpha"
    assert snapshot.sector_code == "801001"
    assert snapshot.pe == 12.0
    assert snapshot.pb == 1.4
    assert snapshot.ps == 1.8
    assert snapshot.roe == 0.16
    assert snapshot.gross_margin == 0.32
    assert snapshot.three_month_return == 0.08
    assert snapshot.twelve_month_return == 0.18
    assert snapshot.volatility == 0.24
    assert snapshot.dividend_yield == 0.025


def test_livermore_signal_confluence_api_returns_analytical_envelope_and_resolved_date_inputs(
    tmp_path, monkeypatch
) -> None:
    client = _build_client(tmp_path, monkeypatch)
    from backend.app.api.routes import market_data_livermore as route_module

    calls: dict[str, object] = {}
    settings = SimpleNamespace(
        duckdb_path=tmp_path / "moss.duckdb",
        choice_stock_catalog_file=tmp_path / "choice-stock-catalog.json",
    )
    conn = duckdb.connect(str(settings.duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              stock_code varchar
            )
            """
        )
        conn.execute(
            "insert into livermore_candidate_history values ('2026-04-06', '000001.SZ')"
        )
    finally:
        conn.close()
    stock_readiness = {"catalog_status": "ready"}
    livermore_envelope = {
        "result_meta": {
            "source_version": "sv_livermore",
            "vendor_version": "vv_livermore",
            "rule_version": "rv_livermore",
            "cache_version": "cv_livermore",
            "quality_flag": "ok",
            "vendor_status": "ok",
            "fallback_mode": "latest_snapshot",
            "tables_used": ["fact_choice_macro_daily"],
            "evidence_rows": 65,
        },
        "result": {
            "as_of_date": "2026-04-06",
            "requested_as_of_date": "2026-04-10",
            "market_gate": {"state": "WARM", "exposure": 0.4},
            "stock_candidates": {"items": [{"stock_code": "000001.SZ"}]},
            "risk_exit": {"items": []},
        },
    }
    replay_summary = {
        "status": "partial",
        "snapshot_from": "2026-04-06",
        "snapshot_to": "2026-04-06",
        "replay_dates_total": 1,
        "replay_dates_completed": 0,
        "replay_dates_pending": 1,
        "replay_dates_unsupported": 0,
        "replay_dates_proxy_only": 0,
        "completed_rows": 0,
        "pending_rows": 1,
        "unsupported_rows": 0,
        "proxy_only_rows": 0,
        "excluded_from_completed_stats_dates": ["2026-04-06"],
        "included_completed_stats_dates": [],
        "date_reasons": [
            {
                "trade_date": "2026-04-06",
                "status": "pending",
                "reason_code": "forward_returns_pending",
                "message": "Forward return bars are not available yet; exclude 2026-04-06 from completed forward-return statistics.",
                "affects_completed_stats": False,
                "signal_kinds": ["stock_candidate"],
            }
        ],
    }
    macro_envelope = {
        "result_meta": {
            "source_version": "sv_macro",
            "vendor_version": "vv_macro",
            "rule_version": "rv_macro",
            "cache_version": "cv_macro",
            "quality_flag": "warning",
            "vendor_status": "ok",
            "fallback_mode": "none",
            "tables_used": ["fact_choice_macro_daily", "yield_curve_daily"],
            "evidence_rows": 40,
        },
        "result": {
            "macro_environment": {"composite_score": -0.45},
            "warnings": [],
        },
    }
    adversarial_payload = {
        "status": "ok",
        "risk_gate": "allow",
    }
    adversarial_meta = {
        "source": {
            "version": "sv_adversarial",
            "status": "warning",
        },
        "vendor": {
            "version": "vv_adversarial",
            "status": "vendor_unavailable",
        },
        "tables": ["macro_adversarial_signal_snapshot"],
        "evidence": {
            "rows": 7,
        },
        "fallback_mode": "none",
    }
    confluence_payload = {
        "as_of_date": "2026-04-06",
        "macro_context": {
            "status": "supportive",
            "composite_score": -0.45,
            "multiplier": 1.0,
        },
        "adversarial_context": {
            "status": "ok",
            "risk_gate": "allow",
            "blocks_new_entry_observations": False,
            "diagnostics": [],
        },
        "strategy_context": {
            "market_gate_state": "WARM",
            "market_gate_exposure": 0.4,
            "allows_new_entry_observations": True,
        },
        "closed_loop_state": {
            "status": "open",
            "entry_observation_action": "observe_entry_setup",
        },
        "position_size_hint": 0.4,
        "entry_observations": [
            {
                "stock_code": "000001.SZ",
                "stock_name": "Alpha",
                "action": "observe_entry_setup",
                "trigger_price": 21.8,
                "current_price": 21.9,
                "invalidation_reference_price": 20.6,
            }
        ],
        "exit_observations": [],
        "diagnostics": [
            "Observation-only output. This service does not generate trading instructions."
        ],
        "disclaimer": "Observation-only output. This service does not generate trading instructions.",
    }

    def fake_livermore_strategy_envelope(
        *, duckdb_path: str, as_of_date: str | None = None, stock_readiness: object = None
    ) -> dict[str, object]:
        calls["livermore"] = {
            "duckdb_path": duckdb_path,
            "as_of_date": as_of_date,
            "stock_readiness": stock_readiness,
        }
        return livermore_envelope

    def fake_get_macro_bond_linkage(report_date: date) -> dict[str, object]:
        calls["macro_report_date"] = report_date.isoformat()
        return macro_envelope

    def fake_build_livermore_signal_confluence(
        *,
        as_of_date: str,
        livermore_payload: dict[str, object],
        macro_payload: dict[str, object],
        adversarial_payload: dict[str, object] | None = None,
        backtest_window_summary: dict[str, object] | None = None,
    ) -> dict[str, object]:
        calls["confluence"] = {
            "as_of_date": as_of_date,
            "livermore_payload": livermore_payload,
            "macro_payload": macro_payload,
            "adversarial_payload": adversarial_payload,
            "backtest_window_summary": backtest_window_summary,
        }
        return {
            **confluence_payload,
            "closed_loop_state": {
                **confluence_payload["closed_loop_state"],
                "replay_status": {
                    "window_status": "partial",
                    "has_decision_usable_completed_stats": False,
                    "completed_dates": 0,
                    "pending_dates": 1,
                    "unsupported_dates": 0,
                    "proxy_only_dates": 0,
                    "completed_candidate_rows": 0,
                    "pending_candidate_rows": 1,
                    "unsupported_candidate_rows": 0,
                    "proxy_only_candidate_rows": 0,
                    "included_completed_stats_dates": [],
                    "blocked_dates": [
                        {
                            "trade_date": "2026-04-06",
                            "status": "pending",
                            "reason_code": "forward_returns_pending",
                            "signal_kinds": ["stock_candidate"],
                        }
                    ],
                    "completed_zero_signal_dates": [],
                },
            },
        }

    def fake_load_macro_adversarial_signal_payload(*, output_dir=None):
        calls["adversarial_output_dir"] = output_dir
        return adversarial_payload, adversarial_meta

    monkeypatch.setattr(route_module, "get_settings", lambda: settings)
    monkeypatch.setattr(route_module, "load_choice_stock_readiness", lambda _path: stock_readiness)
    monkeypatch.setattr(route_module, "livermore_strategy_envelope", fake_livermore_strategy_envelope)
    monkeypatch.setattr(route_module, "get_macro_bond_linkage", fake_get_macro_bond_linkage)
    monkeypatch.setattr(
        route_module,
        "load_macro_adversarial_signal_payload",
        fake_load_macro_adversarial_signal_payload,
    )
    monkeypatch.setattr(
        route_module,
        "build_livermore_signal_confluence",
        fake_build_livermore_signal_confluence,
    )
    def fake_replay_summary(**kwargs: object) -> dict[str, object]:
        calls["replay_summary_kwargs"] = kwargs
        return replay_summary

    monkeypatch.setattr(route_module, "livermore_candidate_history_backtest_window_summary", fake_replay_summary)

    response = client.get(
        "/ui/market-data/livermore/signal-confluence",
        params={"as_of_date": "2026-04-10"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "analytical"
    assert payload["result_meta"]["result_kind"] == "market_data.livermore.signal_confluence"
    assert payload["result_meta"]["quality_flag"] == "warning"
    assert payload["result_meta"]["fallback_mode"] == "latest_snapshot"
    assert payload["result_meta"]["source_version"] == "sv_livermore__sv_macro__sv_adversarial"
    assert payload["result_meta"]["vendor_version"] == "vv_livermore__vv_macro__vv_adversarial"
    assert payload["result_meta"]["vendor_status"] == "vendor_unavailable"
    assert payload["result_meta"]["filters_applied"] == {
        "requested_as_of_date": "2026-04-10",
        "as_of_date": "2026-04-06",
    }
    assert payload["result_meta"]["tables_used"] == [
        "fact_choice_macro_daily",
        "yield_curve_daily",
        "macro_adversarial_signal_snapshot",
    ]
    assert payload["result_meta"]["evidence_rows"] == 112
    assert payload["result"]["as_of_date"] == confluence_payload["as_of_date"]
    assert payload["result"]["macro_context"] == confluence_payload["macro_context"]
    assert payload["result"]["adversarial_context"] == confluence_payload["adversarial_context"]
    assert payload["result"]["strategy_context"] == confluence_payload["strategy_context"]
    assert payload["result"]["position_size_hint"] == confluence_payload["position_size_hint"]
    assert payload["result"]["entry_observations"] == confluence_payload["entry_observations"]
    assert payload["result"]["exit_observations"] == confluence_payload["exit_observations"]
    assert payload["result"]["diagnostics"] == confluence_payload["diagnostics"]
    assert payload["result"]["disclaimer"] == confluence_payload["disclaimer"]
    assert payload["result"]["closed_loop_state"] == {
        **confluence_payload["closed_loop_state"],
        "replay_status": {
            "window_status": "partial",
            "has_decision_usable_completed_stats": False,
            "completed_dates": 0,
            "pending_dates": 1,
            "unsupported_dates": 0,
            "proxy_only_dates": 0,
            "completed_candidate_rows": 0,
            "pending_candidate_rows": 1,
            "unsupported_candidate_rows": 0,
            "proxy_only_candidate_rows": 0,
            "included_completed_stats_dates": [],
            "blocked_dates": [
                {
                    "trade_date": "2026-04-06",
                    "status": "pending",
                    "reason_code": "forward_returns_pending",
                    "signal_kinds": ["stock_candidate"],
                }
            ],
            "completed_zero_signal_dates": [],
        },
    }
    replay_evidence = payload["result"]["replay_evidence"]
    assert replay_evidence["status"] == "available"
    assert replay_evidence["snapshot_as_of_date"] == "2026-04-06"
    assert replay_evidence["row_count"] == 1
    assert replay_evidence["matched_entry_count"] == 1
    assert replay_evidence["sample_items"][0]["stock_code"] == "000001.SZ"
    assert calls["livermore"] == {
        "duckdb_path": str(settings.duckdb_path),
        "as_of_date": "2026-04-10",
        "stock_readiness": stock_readiness,
    }
    assert calls["macro_report_date"] == "2026-04-06"
    assert calls["adversarial_output_dir"] is None
    assert calls["confluence"] == {
        "as_of_date": "2026-04-06",
        "livermore_payload": livermore_envelope["result"],
        "macro_payload": macro_envelope["result"],
        "adversarial_payload": adversarial_payload,
        "backtest_window_summary": replay_summary,
    }
    assert calls["replay_summary_kwargs"] == {
        "duckdb_path": str(settings.duckdb_path),
        "stock_code": None,
        "snapshot_from": "2026-04-06",
        "snapshot_to": "2026-04-06",
    }
    get_settings.cache_clear()


def test_livermore_signal_confluence_api_uses_real_service_shape_with_macro_environment_score(
    tmp_path, monkeypatch
) -> None:
    client = _build_client(tmp_path, monkeypatch)
    from backend.app.api.routes import market_data_livermore as route_module

    settings = SimpleNamespace(
        duckdb_path=tmp_path / "moss.duckdb",
        choice_stock_catalog_file=tmp_path / "choice-stock-catalog.json",
    )
    livermore_envelope = {
        "result_meta": {
            "source_version": "sv_livermore",
            "vendor_version": "vv_livermore",
            "quality_flag": "ok",
            "vendor_status": "ok",
            "fallback_mode": "none",
            "tables_used": ["fact_choice_macro_daily"],
            "evidence_rows": 2,
        },
        "result": {
            "as_of_date": "2026-04-30",
            "market_gate": {"state": "HOT", "exposure": 0.75},
            "stock_candidates": {
                "items": [
                    {
                        "stock_code": "000001.SZ",
                        "stock_name": "Alpha",
                        "breakout_level": 21.8,
                        "close": 21.9,
                        "ema10": 20.6,
                    }
                ]
            },
            "risk_exit": {
                "watch_items": [
                    {
                        "stock_code": "000777.SZ",
                        "stock_name": "Watch Alpha",
                        "latest_close": 19.8,
                        "latest_ema10": 20.1,
                        "exit_watch_price": 20.1,
                        "triggered": True,
                    }
                ]
            },
        },
    }
    macro_envelope = {
        "result_meta": {
            "source_version": "sv_macro",
            "vendor_version": "vv_macro",
            "quality_flag": "ok",
            "vendor_status": "ok",
            "fallback_mode": "none",
            "tables_used": ["macro_bond_linkage"],
            "evidence_rows": 3,
        },
        "result": {
            "environment_score": {"composite_score": -0.45},
            "warnings": [],
        },
    }

    monkeypatch.setattr(route_module, "get_settings", lambda: settings)
    monkeypatch.setattr(route_module, "load_choice_stock_readiness", lambda _path: {"catalog_status": "ready"})
    monkeypatch.setattr(route_module, "livermore_strategy_envelope", lambda **_kwargs: livermore_envelope)
    monkeypatch.setattr(route_module, "get_macro_bond_linkage", lambda _report_date: macro_envelope)

    response = client.get(
        "/ui/market-data/livermore/signal-confluence",
        params={"as_of_date": "2026-04-30"},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["macro_context"]["status"] == "supportive"
    assert result["strategy_context"]["allows_new_entry_observations"] is True
    assert result["position_size_hint"] == 0.75
    assert result["entry_observations"][0]["action"] == "observe_entry_setup"
    assert result["entry_observations"][0]["trigger_price"] == 21.8
    assert result["entry_observations"][0]["invalidation_reference_price"] == 20.6
    assert result["exit_observations"][0]["action"] == "exit_triggered"
    assert result["exit_observations"][0]["exit_watch_price"] == 20.1
    assert result["exit_observations"][0]["triggered"] is True
    assert result["closed_loop_state"]["exit_gate"] == "triggered"
    get_settings.cache_clear()


def test_livermore_signal_confluence_api_smoke_loads_real_adversarial_overlay_and_candidate_history(
    tmp_path, monkeypatch
) -> None:
    client = _build_client(tmp_path, monkeypatch)
    from backend.app.api.routes import market_data_livermore as route_module
    from backend.app.services import macro_adversarial_signal_service

    output_dir = tmp_path / "macro_output"
    output_dir.mkdir()
    _write_csv(
        output_dir / "final_signal.csv",
        """
symbol,as_of_date,signal,position_scale,confidence,note,third_layer_pass
TL,2026-04-30,short,0.35,2,crowding block,false
""",
    )

    settings = SimpleNamespace(
        duckdb_path=tmp_path / "moss.duckdb",
        choice_stock_catalog_file=tmp_path / "choice-stock-catalog.json",
    )
    conn = duckdb.connect(str(settings.duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              stock_code varchar
            )
            """
        )
        conn.execute(
            "insert into livermore_candidate_history values ('2026-04-30', '000001.SZ')"
        )
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-04-30")
    finally:
        conn.close()

    livermore_envelope = {
        "result_meta": {
            "source_version": "sv_livermore",
            "vendor_version": "vv_livermore",
            "quality_flag": "ok",
            "vendor_status": "ok",
            "fallback_mode": "none",
            "tables_used": ["fact_choice_macro_daily"],
            "evidence_rows": 2,
        },
        "result": {
            "as_of_date": "2026-04-30",
            "market_gate": {"state": "HOT", "exposure": 0.8},
            "stock_candidates": {
                "items": [
                    {
                        "stock_code": "000001.SZ",
                        "stock_name": "Alpha",
                        "breakout_level": 21.8,
                        "close": 21.9,
                        "ema10": 20.6,
                    }
                ]
            },
            "risk_exit": {"watch_items": []},
        },
    }
    macro_envelope = {
        "result_meta": {
            "source_version": "sv_macro",
            "vendor_version": "vv_macro",
            "quality_flag": "ok",
            "vendor_status": "ok",
            "fallback_mode": "none",
            "tables_used": ["macro_bond_linkage"],
            "evidence_rows": 3,
        },
        "result": {
            "environment_score": {"composite_score": -0.45},
        },
    }

    monkeypatch.setattr(route_module, "get_settings", lambda: settings)
    monkeypatch.setattr(route_module, "load_choice_stock_readiness", lambda _path: {"catalog_status": "ready"})
    monkeypatch.setattr(route_module, "livermore_strategy_envelope", lambda **_kwargs: livermore_envelope)
    monkeypatch.setattr(route_module, "get_macro_bond_linkage", lambda _report_date: macro_envelope)
    monkeypatch.setattr(macro_adversarial_signal_service, "OUTPUT_DIR", output_dir)

    response = client.get(
        "/ui/market-data/livermore/signal-confluence",
        params={"as_of_date": "2026-04-30"},
    )

    assert response.status_code == 200
    payload = response.json()
    result = payload["result"]
    assert result["adversarial_context"]["status"] == "ok"
    assert result["adversarial_context"]["mode"] == "final_signal"
    assert result["adversarial_context"]["risk_gate"] == "block"
    assert result["adversarial_context"]["blocks_new_entry_observations"] is True
    assert result["entry_observations"][0]["action"] == "observe_only"
    closed_loop_state = result["closed_loop_state"]
    assert {"entry_gate", "exit_gate", "replay_status", "lineage_status"} <= set(closed_loop_state)
    assert closed_loop_state["entry_gate"] == "blocked"
    assert closed_loop_state["exit_gate"] == "missing"
    assert closed_loop_state["replay_status"]["window_status"] == "valid"
    assert closed_loop_state["replay_status"]["has_decision_usable_completed_stats"] is True
    assert closed_loop_state["replay_status"]["completed_dates"] == 1
    assert closed_loop_state["replay_status"]["completed_candidate_rows"] == 1
    assert closed_loop_state["lineage_status"] == "complete"
    replay_evidence = result["replay_evidence"]
    assert replay_evidence["status"] == "available"
    assert replay_evidence["snapshot_as_of_date"] == "2026-04-30"
    assert replay_evidence["row_count"] == 1
    assert replay_evidence["matched_entry_count"] == 1
    assert replay_evidence["sample_items"][0]["stock_code"] == "000001.SZ"
    result_meta = payload["result_meta"]
    assert result_meta["source_version"] == "sv_livermore__sv_macro__macro_toolkit.final_signal.csv"
    assert result_meta["vendor_version"] == "vv_livermore__vv_macro__macro_toolkit.local_csv"
    assert result_meta["tables_used"] == [
        "fact_choice_macro_daily",
        "macro_bond_linkage",
        "macro_toolkit_output.final_signal.csv",
    ]
    assert result_meta["evidence_rows"] == 6
    get_settings.cache_clear()


def test_livermore_signal_confluence_replay_evidence_counts_all_rows_while_sampling_five(
    tmp_path, monkeypatch
) -> None:
    client = _build_client(tmp_path, monkeypatch)
    from backend.app.api.routes import market_data_livermore as route_module
    from backend.app.services import macro_adversarial_signal_service

    output_dir = tmp_path / "macro_output"
    output_dir.mkdir()
    settings = SimpleNamespace(
        duckdb_path=tmp_path / "moss.duckdb",
        choice_stock_catalog_file=tmp_path / "choice-stock-catalog.json",
    )
    conn = duckdb.connect(str(settings.duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              stock_code varchar,
              candidate_rank integer
            )
            """
        )
        conn.executemany(
            "insert into livermore_candidate_history values (?, ?, ?)",
            [(("2026-04-30", f"00000{rank}.SZ", rank)) for rank in range(1, 7)],
        )
        _seed_choice_stock_replay_coverage(conn, trade_date="2026-04-30")
    finally:
        conn.close()

    livermore_envelope = {
        "result_meta": {
            "source_version": "sv_livermore",
            "vendor_version": "vv_livermore",
            "quality_flag": "ok",
            "vendor_status": "ok",
            "fallback_mode": "none",
            "tables_used": ["fact_choice_macro_daily"],
            "evidence_rows": 2,
        },
        "result": {
            "as_of_date": "2026-04-30",
            "market_gate": {"state": "HOT", "exposure": 0.8},
            "stock_candidates": {
                "items": [
                    {"stock_code": "000001.SZ", "stock_name": "Alpha"},
                    {"stock_code": "000006.SZ", "stock_name": "Zeta"},
                ]
            },
            "risk_exit": {"watch_items": []},
        },
    }
    macro_envelope = {
        "result_meta": {
            "source_version": "sv_macro",
            "vendor_version": "vv_macro",
            "quality_flag": "ok",
            "vendor_status": "ok",
            "fallback_mode": "none",
            "tables_used": ["macro_bond_linkage"],
            "evidence_rows": 3,
        },
        "result": {
            "environment_score": {"composite_score": -0.45},
        },
    }

    monkeypatch.setattr(route_module, "get_settings", lambda: settings)
    monkeypatch.setattr(route_module, "load_choice_stock_readiness", lambda _path: {"catalog_status": "ready"})
    monkeypatch.setattr(route_module, "livermore_strategy_envelope", lambda **_kwargs: livermore_envelope)
    monkeypatch.setattr(route_module, "get_macro_bond_linkage", lambda _report_date: macro_envelope)
    monkeypatch.setattr(macro_adversarial_signal_service, "OUTPUT_DIR", output_dir)

    response = client.get(
        "/ui/market-data/livermore/signal-confluence",
        params={"as_of_date": "2026-04-30"},
    )

    assert response.status_code == 200
    replay_evidence = response.json()["result"]["replay_evidence"]
    assert replay_evidence["status"] == "available"
    assert replay_evidence["row_count"] == 6
    assert replay_evidence["matched_entry_count"] == 2
    assert len(replay_evidence["sample_items"]) == 5
    assert replay_evidence["sample_items"][-1]["stock_code"] == "000005.SZ"
    get_settings.cache_clear()


def test_livermore_signal_confluence_api_keeps_core_result_meta_when_adversarial_overlay_is_missing(
    tmp_path, monkeypatch
) -> None:
    client = _build_client(tmp_path, monkeypatch)
    from backend.app.api.routes import market_data_livermore as route_module
    from backend.app.services import macro_adversarial_signal_service

    output_dir = tmp_path / "macro_output"
    output_dir.mkdir()
    settings = SimpleNamespace(
        duckdb_path=tmp_path / "moss.duckdb",
        choice_stock_catalog_file=tmp_path / "choice-stock-catalog.json",
    )
    livermore_envelope = {
        "result_meta": {
            "source_version": "sv_livermore",
            "vendor_version": "vv_livermore",
            "quality_flag": "ok",
            "vendor_status": "ok",
            "fallback_mode": "none",
            "tables_used": ["fact_choice_macro_daily"],
            "evidence_rows": 2,
        },
        "result": {
            "as_of_date": "2026-04-30",
            "market_gate": {"state": "WARM", "exposure": 0.5},
            "stock_candidates": {
                "items": [
                    {
                        "stock_code": "000001.SZ",
                        "stock_name": "Alpha",
                        "breakout_level": 21.8,
                        "close": 21.9,
                        "ema10": 20.6,
                    }
                ]
            },
            "risk_exit": {"watch_items": []},
        },
    }
    macro_envelope = {
        "result_meta": {
            "source_version": "sv_macro",
            "vendor_version": "vv_macro",
            "quality_flag": "ok",
            "vendor_status": "ok",
            "fallback_mode": "none",
            "tables_used": ["macro_bond_linkage"],
            "evidence_rows": 3,
        },
        "result": {
            "environment_score": {"composite_score": -0.1},
        },
    }

    monkeypatch.setattr(route_module, "get_settings", lambda: settings)
    monkeypatch.setattr(route_module, "load_choice_stock_readiness", lambda _path: {"catalog_status": "ready"})
    monkeypatch.setattr(route_module, "livermore_strategy_envelope", lambda **_kwargs: livermore_envelope)
    monkeypatch.setattr(route_module, "get_macro_bond_linkage", lambda _report_date: macro_envelope)
    monkeypatch.setattr(macro_adversarial_signal_service, "OUTPUT_DIR", output_dir)

    response = client.get(
        "/ui/market-data/livermore/signal-confluence",
        params={"as_of_date": "2026-04-30"},
    )

    assert response.status_code == 200
    payload = response.json()
    result = payload["result"]
    assert result["adversarial_context"]["status"] == "missing"
    assert result["adversarial_context"]["risk_gate"] == "missing"
    assert result["entry_observations"][0]["action"] == "observe_entry_setup"
    closed_loop_state = result["closed_loop_state"]
    assert {"entry_gate", "exit_gate", "replay_status", "lineage_status"} <= set(closed_loop_state)
    assert closed_loop_state["entry_gate"] == "open"
    assert closed_loop_state["exit_gate"] == "missing"
    assert closed_loop_state["replay_status"]["window_status"] == "unsupported"
    assert closed_loop_state["replay_status"]["has_decision_usable_completed_stats"] is False
    assert closed_loop_state["lineage_status"] == "missing"
    assert result["replay_evidence"] == {
        "status": "missing",
        "snapshot_as_of_date": "2026-04-30",
        "row_count": 0,
        "matched_entry_count": 0,
        "sample_items": [],
    }
    result_meta = payload["result_meta"]
    assert result_meta["source_version"] == "sv_livermore__sv_macro"
    assert result_meta["vendor_version"] == "vv_livermore__vv_macro"
    assert result_meta["quality_flag"] == "ok"
    assert result_meta["vendor_status"] == "ok"
    assert result_meta["fallback_mode"] == "none"
    assert result_meta["tables_used"] == ["fact_choice_macro_daily", "macro_bond_linkage"]
    assert result_meta["evidence_rows"] == 5
    get_settings.cache_clear()


def test_livermore_signal_confluence_api_rejects_invalid_as_of_date(tmp_path, monkeypatch) -> None:
    client = _build_client(tmp_path, monkeypatch)

    response = client.get(
        "/ui/market-data/livermore/signal-confluence",
        params={"as_of_date": "2026-04-99"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid as_of_date. Expected YYYY-MM-DD."
    get_settings.cache_clear()


def test_livermore_signal_confluence_api_preserves_stale_lineage(tmp_path, monkeypatch) -> None:
    client = _build_client(tmp_path, monkeypatch)
    from backend.app.api.routes import market_data_livermore as route_module

    settings = SimpleNamespace(
        duckdb_path=tmp_path / "moss.duckdb",
        choice_stock_catalog_file=tmp_path / "choice-stock-catalog.json",
    )
    livermore_envelope = {
        "result_meta": {
            "source_version": "sv_livermore",
            "vendor_version": "vv_livermore",
            "quality_flag": "stale",
            "vendor_status": "vendor_stale",
            "fallback_mode": "latest_snapshot",
            "tables_used": ["fact_choice_macro_daily"],
            "evidence_rows": 1,
        },
        "result": {
            "as_of_date": "2026-04-06",
            "market_gate": {"state": "STALE", "exposure": 0.0},
            "stock_candidates": {"items": []},
            "risk_exit": {"items": []},
        },
    }
    macro_envelope = {
        "result_meta": {
            "source_version": "sv_macro",
            "vendor_version": "vv_macro",
            "quality_flag": "ok",
            "vendor_status": "ok",
            "fallback_mode": "none",
            "tables_used": ["macro_bond_linkage"],
            "evidence_rows": 1,
        },
        "result": {
            "environment_score": {"composite_score": 0.0},
        },
    }

    monkeypatch.setattr(route_module, "get_settings", lambda: settings)
    monkeypatch.setattr(route_module, "load_choice_stock_readiness", lambda _path: {"catalog_status": "ready"})
    monkeypatch.setattr(route_module, "livermore_strategy_envelope", lambda **_kwargs: livermore_envelope)
    monkeypatch.setattr(route_module, "get_macro_bond_linkage", lambda _report_date: macro_envelope)

    response = client.get(
        "/ui/market-data/livermore/signal-confluence",
        params={"as_of_date": "2026-04-10"},
    )

    assert response.status_code == 200
    result_meta = response.json()["result_meta"]
    assert result_meta["quality_flag"] == "stale"
    assert result_meta["vendor_status"] == "vendor_stale"
    assert result_meta["fallback_mode"] == "latest_snapshot"
    get_settings.cache_clear()


def test_livermore_api_reads_gate_supplement_table_for_breadth_and_limit_up(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_choice_macro_history(
        str(duckdb_path),
        start=date(2026, 2, 1),
        closes=[3200.0 + day * 8 for day in range(65)],
    )
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    conn.execute(
        """
        create table if not exists fact_livermore_gate_supplement_daily (
          trade_date varchar not null,
          breadth_5d double,
          limit_up_quality_ok boolean,
          source_version varchar,
          vendor_version varchar,
          rule_version varchar,
          run_id varchar,
          primary key (trade_date)
        )
        """
    )
    conn.execute(
        "insert into fact_livermore_gate_supplement_daily values (?, ?, ?, ?, ?, ?, ?)",
        ["2026-04-06", 1.5, True, "sv_t", "vv_t", "rv_t", "run_t"],
    )
    conn.close()

    client = _build_client(tmp_path, monkeypatch)
    response = client.get("/ui/market-data/livermore")
    assert response.status_code == 200
    payload = response.json()
    result = payload["result"]
    assert result["market_gate"]["state"] == "OVERHEAT"
    assert result["market_gate"]["passed_conditions"] == 4
    gap_by_family = {row["input_family"]: row for row in result["data_gaps"]}
    assert gap_by_family["breadth"]["status"] == "ready"
    assert gap_by_family["limit_up_quality"]["status"] == "ready"
    readiness = {row["key"]: row for row in result["rule_readiness"]}
    assert readiness["market_gate"]["status"] == "ready"
    assert readiness["market_gate"]["missing_inputs"] == []
    diag_codes = {row["code"] for row in result["diagnostics"]}
    assert "LIVERMORE_BREADTH_MISSING" not in diag_codes
    assert "LIVERMORE_LIMIT_UP_QUALITY_MISSING" not in diag_codes
    assert "fact_livermore_gate_supplement_daily" in payload["result_meta"]["tables_used"]
    get_settings.cache_clear()


def test_livermore_gate_supplement_task_writes_rows(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection
    from backend.app.tasks.livermore_gate_supplement import materialize_livermore_gate_supplement_daily

    db = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db), read_only=False)
    apply_pending_migrations_on_connection(conn)
    conn.close()

    out = materialize_livermore_gate_supplement_daily.fn(
        duckdb_path=str(db),
        rows=[
            {"trade_date": "2026-04-01", "breadth_5d": 0.5, "limit_up_quality_ok": False},
        ],
        run_id="run-test-1",
    )
    assert out["status"] == "completed"
    conn = duckdb.connect(str(db), read_only=True)
    row = conn.execute(
        "select breadth_5d, limit_up_quality_ok from fact_livermore_gate_supplement_daily where trade_date = ?",
        ["2026-04-01"],
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == 0.5
    assert row[1] is False
    get_settings.cache_clear()


def test_livermore_position_snapshot_endpoint_materializes_and_checks_risk_inputs(
    tmp_path, monkeypatch
) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              stock_code varchar,
              trade_date varchar,
              close_value double,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        start = date(2026, 4, 18)
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?, ?, ?, ?)",
            [
                (
                    "000001.SZ",
                    (start + timedelta(days=offset)).isoformat(),
                    10.0 + offset,
                    "sv_daily",
                    "vv_daily",
                )
                for offset in range(13)
            ],
        )
    finally:
        conn.close()
    csv_path = tmp_path / "data_input" / "livermore" / "positions.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.write_text(
        "\n".join(
            [
                "as_of_date,stock_code,stock_name,entry_cost,bars_since_entry,position_quantity,position_status,source_system",
                "2026-04-30,000001.SZ,Alpha,10.5,6,10000,ACTIVE,unit_test_position_book",
            ]
        ),
        encoding="utf-8",
    )
    client = _build_client(tmp_path, monkeypatch)

    response = client.post(
        "/ui/market-data/livermore/position-snapshot",
        json={"as_of_date": "2026-04-30", "csv_path": str(csv_path)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["row_count"] == 1
    assert payload["risk_exit_input_status"] == "ready"
    assert payload["risk_exit_input_block_reason"] == ""
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        row = conn.execute(
            """
            select stock_code, entry_cost, bars_since_entry, position_status
            from livermore_position_snapshot
            where as_of_date = ?
            """,
            ["2026-04-30"],
        ).fetchone()
    finally:
        conn.close()
    assert row == ("000001.SZ", 10.5, 6, "ACTIVE")
    get_settings.cache_clear()


def test_livermore_position_snapshot_endpoint_rejects_csv_outside_input_root(
    tmp_path, monkeypatch
) -> None:
    outside_path = tmp_path / "positions.csv"
    outside_path.write_text(
        "\n".join(
            [
                "as_of_date,stock_code,stock_name,entry_cost,bars_since_entry,position_status",
                "2026-04-30,000001.SZ,Alpha,10.5,6,ACTIVE",
            ]
        ),
        encoding="utf-8",
    )
    client = _build_client(tmp_path, monkeypatch)

    response = client.post(
        "/ui/market-data/livermore/position-snapshot",
        json={"as_of_date": "2026-04-30", "csv_path": str(outside_path)},
    )

    assert response.status_code == 422
    assert "data_input/livermore" in response.json()["detail"]
    get_settings.cache_clear()


def test_livermore_position_snapshot_manual_endpoint_materializes_without_csv(
    tmp_path, monkeypatch
) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              stock_code varchar,
              trade_date varchar,
              close_value double,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        start = date(2026, 4, 18)
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?, ?, ?, ?)",
            [
                (
                    "000001.SZ",
                    (start + timedelta(days=offset)).isoformat(),
                    10.0 + offset,
                    "sv_daily",
                    "vv_daily",
                )
                for offset in range(13)
            ],
        )
    finally:
        conn.close()
    client = _build_client(tmp_path, monkeypatch)

    response = client.post(
        "/ui/market-data/livermore/position-snapshot/manual",
        json={
            "as_of_date": "2026-04-30",
            "positions": [
                {
                    "stock_code": "000001.SZ",
                    "stock_name": "Alpha",
                    "entry_cost": 10.5,
                    "bars_since_entry": 6,
                    "position_quantity": 10000,
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["input_mode"] == "manual"
    assert payload["csv_path"] is None
    assert payload["row_count"] == 1
    assert payload["risk_exit_input_status"] == "ready"
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        row = conn.execute(
            """
            select stock_code, stock_name, entry_cost, bars_since_entry, position_status, source_system
            from livermore_position_snapshot
            where as_of_date = ?
            """,
            ["2026-04-30"],
        ).fetchone()
    finally:
        conn.close()
    assert row == (
        "000001.SZ",
        "Alpha",
        10.5,
        6,
        "ACTIVE",
        "livermore_position_snapshot_manual",
    )
    get_settings.cache_clear()
