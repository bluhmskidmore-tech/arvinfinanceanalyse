from __future__ import annotations

import sys
from datetime import date, timedelta

import duckdb
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from tests.helpers import load_module


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


def _build_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
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
    unsupported_keys = {row["key"] for row in result["unsupported_outputs"]}
    assert unsupported_keys == {"sector_rank", "stock_candidates", "risk_exit"}
    gap_by_family = {row["input_family"]: row for row in result["data_gaps"]}
    assert gap_by_family["breadth"]["status"] == "missing"
    assert gap_by_family["limit_up_quality"]["status"] == "missing"
    assert gap_by_family["sector_strength"]["status"] == "missing"
    assert gap_by_family["stock_universe"]["status"] == "missing"
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
