from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.routes.macro_etf_strategy import router as macro_etf_strategy_router
from backend.app.core_finance.macro.macro_etf_strategy import (
    DEFAULT_CONFIG,
    DEFAULT_MACRO_STATE,
    build_macro_etf_strategy_snapshot,
    compute_macro_score,
)
from backend.app.governance.settings import get_settings
from backend.app.services.macro_etf_strategy_service import macro_etf_strategy_envelope


def test_macro_score_and_target_weights_follow_imported_strategy_inputs() -> None:
    payload = build_macro_etf_strategy_snapshot(
        config=DEFAULT_CONFIG,
        macro_state=DEFAULT_MACRO_STATE,
        as_of_date=date(2026, 7, 3),
    )

    assert compute_macro_score(DEFAULT_MACRO_STATE) == 0.19
    assert payload["boundary"] == "observation_only"
    assert payload["execution_enabled"] is False
    assert payload["macro"]["score"] == 0.19
    assert payload["position"]["target_total_weight"] == 0.6975
    assert payload["position"]["target_weights"] == {
        "512480": 0.156938,
        "159819": 0.156938,
        "512400": 0.174375,
        "512000": 0.104625,
        "510880": 0.104625,
    }
    assert payload["order_draft"]["draft_status"] == "blocked"
    assert payload["order_draft"]["quote_status"] == "quotes_missing"


def test_order_draft_uses_quotes_and_stays_manual_review_only() -> None:
    quotes = {
        code: {"price": 1.0, "prev_close": 1.0, "volume": 1000000}
        for code in DEFAULT_CONFIG["universe"]
    }
    payload = build_macro_etf_strategy_snapshot(
        config=DEFAULT_CONFIG,
        macro_state=DEFAULT_MACRO_STATE,
        as_of_date=date(2026, 7, 3),
        quotes=quotes,
        portfolio_state={"cash": 200000.0, "holdings": {}},
    )

    draft = payload["order_draft"]
    assert draft["draft_status"] == "ready"
    assert draft["execution_policy"] == "manual_review_only"
    assert draft["order_count"] == 5
    assert {order["side"] for order in draft["orders"]} == {"BUY"}
    assert draft["orders"][0]["shares"] == 34800
    assert all(order["notional"] <= DEFAULT_CONFIG["max_single_order_pct"] * draft["nav"] for order in draft["orders"])


def test_service_envelope_marks_missing_quotes_without_generating_orders(tmp_path: Path) -> None:
    cfg_path = tmp_path / "macro_etf_strategy.json"
    macro_path = tmp_path / "macro_etf_macro_state.json"
    cfg_path.write_text(json.dumps(DEFAULT_CONFIG), encoding="utf-8")
    macro_path.write_text(json.dumps(DEFAULT_MACRO_STATE), encoding="utf-8")

    envelope = macro_etf_strategy_envelope(
        as_of_date="2026-07-03",
        config_path=cfg_path,
        macro_state_path=macro_path,
    )

    assert envelope["result_meta"]["result_kind"] == "market_data.macro_etf_strategy"
    assert envelope["result_meta"]["basis"] == "analytical"
    assert envelope["result_meta"]["formal_use_allowed"] is False
    assert envelope["result_meta"]["source_surface"] == "market_data"
    assert envelope["result_meta"]["quality_flag"] == "warning"
    assert envelope["result"]["order_draft"]["orders"] == []
    assert envelope["result"]["data_status"]["quote_status"] == "quotes_missing"


def test_macro_etf_strategy_endpoint_returns_standard_envelope(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(tmp_path / "data_input"))
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(macro_etf_strategy_router)
    client = TestClient(app)

    response = client.get("/ui/market-data/macro-etf-strategy", params={"as_of_date": "2026-07-03"})

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) >= {"result_meta", "result"}
    assert payload["result_meta"]["result_kind"] == "market_data.macro_etf_strategy"
    assert payload["result"]["boundary"] == "observation_only"
    assert payload["result"]["order_draft"]["execution_policy"] == "manual_review_only"
    get_settings.cache_clear()
