from __future__ import annotations

import logging
import sys
from datetime import date, timedelta
from types import SimpleNamespace

import duckdb
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.repositories.choice_client import ChoiceClient
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
    unsupported_keys = {row["key"] for row in result["unsupported_outputs"]}
    assert unsupported_keys == {"sector_rank", "stock_candidates", "risk_exit"}
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
    get_settings.cache_clear()


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
    confluence_payload = {
        "as_of_date": "2026-04-06",
        "macro_context": {
            "status": "supportive",
            "composite_score": -0.45,
            "multiplier": 1.0,
        },
        "strategy_context": {
            "market_gate_state": "WARM",
            "market_gate_exposure": 0.4,
            "allows_new_entry_observations": True,
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
        *, as_of_date: str, livermore_payload: dict[str, object], macro_payload: dict[str, object]
    ) -> dict[str, object]:
        calls["confluence"] = {
            "as_of_date": as_of_date,
            "livermore_payload": livermore_payload,
            "macro_payload": macro_payload,
        }
        return confluence_payload

    monkeypatch.setattr(route_module, "get_settings", lambda: settings)
    monkeypatch.setattr(route_module, "load_choice_stock_readiness", lambda _path: stock_readiness)
    monkeypatch.setattr(route_module, "livermore_strategy_envelope", fake_livermore_strategy_envelope)
    monkeypatch.setattr(route_module, "get_macro_bond_linkage", fake_get_macro_bond_linkage)
    monkeypatch.setattr(
        route_module,
        "build_livermore_signal_confluence",
        fake_build_livermore_signal_confluence,
    )

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
    assert payload["result_meta"]["filters_applied"] == {
        "requested_as_of_date": "2026-04-10",
        "as_of_date": "2026-04-06",
    }
    assert payload["result_meta"]["tables_used"] == [
        "fact_choice_macro_daily",
        "yield_curve_daily",
    ]
    assert payload["result_meta"]["evidence_rows"] == 105
    assert payload["result"] == confluence_payload
    assert calls["livermore"] == {
        "duckdb_path": str(settings.duckdb_path),
        "as_of_date": "2026-04-10",
        "stock_readiness": stock_readiness,
    }
    assert calls["macro_report_date"] == "2026-04-06"
    assert calls["confluence"] == {
        "as_of_date": "2026-04-06",
        "livermore_payload": livermore_envelope["result"],
        "macro_payload": macro_envelope["result"],
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
