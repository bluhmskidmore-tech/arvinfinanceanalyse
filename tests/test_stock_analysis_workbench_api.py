from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.helpers import load_module


def _strategy_envelope() -> dict[str, Any]:
    return {
        "result_meta": {
            "trace_id": "tr_livermore_strategy_test",
            "basis": "analytical",
            "result_kind": "market_data.livermore",
            "formal_use_allowed": False,
            "scenario_flag": False,
            "source_version": "sv_livermore_test",
            "vendor_version": "vv_livermore_test",
            "rule_version": "rv_livermore_strategy_v1",
            "cache_version": "cv_livermore_strategy_v1",
            "quality_flag": "ok",
            "vendor_status": "ok",
            "fallback_mode": "none",
            "tables_used": ["choice_stock_daily_observation"],
            "evidence_rows": 7,
            "filters_applied": {"as_of_date": "2026-06-26"},
            "source_surface": "market_data",
        },
        "result": {
            "as_of_date": "2026-06-26",
            "requested_as_of_date": "2026-06-26",
            "basis": "analytical",
            "market_gate": {"state": "WARM", "passed": 2, "required": 3},
            "sector_rank": {
                "items": [
                    {
                        "sector_code": "801010",
                        "sector_name": "银行",
                        "rank": 1,
                        "score": 0.82,
                    },
                ],
            },
            "stock_candidates": {
                "items": [
                    {"stock_code": "000001.SZ", "stock_name": "平安银行", "rank": 1},
                ],
            },
            "risk_exit": {"items": [], "watch_items": []},
            "data_gaps": [],
            "diagnostics": [],
            "supported_outputs": ["market_gate", "sector_rank", "stock_candidates"],
            "unsupported_outputs": [],
        },
    }


def test_build_stock_analysis_workbench_envelope_wraps_livermore_strategy_as_observational_contract() -> (
    None
):
    module = load_module(
        "backend.app.services.stock_analysis_workbench_service",
        "backend/app/services/stock_analysis_workbench_service.py",
    )

    envelope = module.build_stock_analysis_workbench_envelope(
        strategy_envelope=_strategy_envelope(),
        requested_as_of_date="2026-06-26",
        include="main,signal_confluence",
        sector_window_days=20,
        top_k=2,
    )

    meta = envelope["result_meta"]
    result = envelope["result"]

    assert meta["result_kind"] == "market_data.stock_analysis.workbench"
    assert meta["basis"] == "analytical"
    assert meta["formal_use_allowed"] is False
    assert meta["source_surface"] == "market_data"
    assert meta["source_version"] == "sv_livermore_test"
    assert meta["tables_used"] == ["choice_stock_daily_observation"]
    assert meta["evidence_rows"] == 7

    assert result["page_id"] == "GAP-STOCK-ANALYSIS-PAGE"
    assert result["route"] == "/stock-analysis"
    assert result["contract_status"] == "observational_only"
    assert result["formal_use_allowed"] is False
    assert result["as_of_date"] == "2026-06-26"
    assert result["decision_summary"]["gate_state"] == "WARM"
    assert result["decision_summary"]["top_review_stock_code"] == "000001.SZ"
    assert result["first_screen"]["review_queue"][0]["stock_name"] == "平安银行"
    assert result["first_screen"]["sector_snapshot"][0]["sector_name"] == "银行"
    assert result["modules"]["main"]["status"] == "ready"
    assert result["modules"]["signal_confluence"]["status"] == "deferred"
    assert result["links"]["stock_detail"] == "/ui/market-data/livermore/stock-detail"
    assert (
        result["links"]["kline_analysis"]
        == "/ui/market-data/stock-analysis/kline-analysis"
    )
    assert result["endpoint_evidence"][0]["endpoint"] == "/ui/market-data/livermore"

    serialized = json.dumps(result, ensure_ascii=False)
    assert "买入建议" not in serialized
    assert "卖出建议" not in serialized
    assert "下单" not in serialized


def test_theme_breakout_nested_stocks_expand_and_merge_theme_memberships_without_cross_module_dedupe() -> (
    None
):
    module = load_module(
        "backend.app.services.stock_analysis_workbench_service",
        "backend/app/services/stock_analysis_workbench_service.py",
    )
    result = {
        "stock_candidates": {
            "items": [{"stock_code": "000001.SZ", "stock_name": "Alpha", "rank": 1}]
        },
        "theme_breakout": {
            "items": [
                {
                    "rank": 1,
                    "theme_key": "concept:C1",
                    "theme_name": "Theme one",
                    "source_kind": "tushare_current_overlay",
                    "items": [
                        {"rank": 2, "stock_code": "000001.SZ", "stock_name": "Alpha"},
                        {"rank": 1, "stock_code": "000002.SZ", "stock_name": "Beta"},
                    ],
                },
                {
                    "rank": 2,
                    "theme_key": "concept:C2",
                    "theme_name": "Theme two",
                    "source_kind": "tushare_current_overlay",
                    "items": [
                        {"rank": 1, "stock_code": "000001.SZ", "stock_name": "Alpha"},
                    ],
                },
            ]
        },
    }

    rows = module._candidate_queue(result, top_k=10)

    assert [(row["source_module"], row["stock_code"]) for row in rows] == [
        ("stock_candidates", "000001.SZ"),
        ("theme_breakout", "000001.SZ"),
        ("theme_breakout", "000002.SZ"),
    ]
    theme_alpha = rows[1]
    assert theme_alpha["theme_key"] == "concept:C1"
    assert theme_alpha["theme_name"] == "Theme one"
    assert theme_alpha["theme_rank"] == 1
    assert theme_alpha["source_kind"] == "tushare_current_overlay"
    assert theme_alpha["member_rank"] == 2
    assert theme_alpha["theme_memberships"] == [
        {
            "theme_key": "concept:C1",
            "theme_name": "Theme one",
            "rank": 1,
            "source_kind": "tushare_current_overlay",
            "member_rank": 2,
        },
        {
            "theme_key": "concept:C2",
            "theme_name": "Theme two",
            "rank": 2,
            "source_kind": "tushare_current_overlay",
            "member_rank": 1,
        },
    ]


def test_candidate_queue_skips_modules_excluded_from_primary() -> None:
    module = load_module(
        "backend.app.services.stock_analysis_workbench_service",
        "backend/app/services/stock_analysis_workbench_service.py",
    )
    result = {
        "module_states": [
            {
                "key": "factor_screen_candidates",
                "render_mode": "evidence_only",
                "excludes_from_primary": True,
            },
            {
                "key": "fresh_trend_watchlist",
                "render_mode": "primary",
                "excludes_from_primary": False,
            },
        ],
        "factor_screen_candidates": {
            "items": [{"stock_code": "600062.SH", "stock_name": "Evidence only"}],
        },
        "fresh_trend_watchlist": {
            "items": [{"stock_code": "000001.SZ", "stock_name": "Primary candidate"}],
        },
    }

    rows = module._candidate_queue(result, top_k=1)

    assert [(row["source_module"], row["stock_code"]) for row in rows] == [
        ("fresh_trend_watchlist", "000001.SZ"),
    ]


def test_theme_breakout_member_rank_falls_back_to_nested_list_order() -> None:
    module = load_module(
        "backend.app.services.stock_analysis_workbench_service",
        "backend/app/services/stock_analysis_workbench_service.py",
    )
    result = {
        "theme_breakout": {
            "items": [
                {
                    "rank": 1,
                    "theme_key": "concept:C1",
                    "theme_name": "Theme one",
                    "source_kind": "tushare_current_overlay",
                    "items": [
                        {"stock_code": "000002.SZ", "stock_name": "Beta"},
                        {"stock_code": "000001.SZ", "stock_name": "Alpha"},
                    ],
                }
            ]
        }
    }

    rows = module._candidate_queue(result, top_k=10)

    assert [(row["stock_code"], row["member_rank"]) for row in rows] == [
        ("000002.SZ", 1),
        ("000001.SZ", 2),
    ]


def test_workbench_passes_overlay_reader_to_livermore_strategy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module(
        "backend.app.services.stock_analysis_workbench_service",
        "backend/app/services/stock_analysis_workbench_service.py",
    )
    reader = object()
    calls: list[object] = []

    def fake_strategy(**kwargs: object) -> dict[str, Any]:
        calls.append(kwargs.get("theme_overlay_reader"))
        return _strategy_envelope()

    monkeypatch.setattr(
        module, "livermore_strategy_envelope_from_catalog", fake_strategy
    )

    module.stock_analysis_workbench_envelope(
        duckdb_path="missing.duckdb",
        as_of_date="2026-06-26",
        choice_stock_catalog_file="missing.json",
        theme_overlay_reader=reader,
    )

    assert calls == [reader]


def test_stock_analysis_workbench_logs_strategy_and_projection_timings(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    module = load_module(
        "backend.app.services.stock_analysis_workbench_service",
        "backend/app/services/stock_analysis_workbench_service.py",
    )
    sentinel = {"result": {"route": "/stock-analysis"}}
    caplog.set_level("INFO", logger=module.__name__)
    monkeypatch.setattr(
        module,
        "livermore_strategy_envelope_from_catalog",
        lambda **_kwargs: _strategy_envelope(),
    )
    monkeypatch.setattr(
        module,
        "build_stock_analysis_workbench_envelope",
        lambda **_kwargs: sentinel,
    )

    result = module.stock_analysis_workbench_envelope(
        duckdb_path="missing.duckdb",
        as_of_date="2026-06-26",
        choice_stock_catalog_file="missing.json",
    )

    assert result is sentinel
    messages = [record.message for record in caplog.records]
    assert any(
        "stock_analysis_workbench_timing stage=strategy_envelope" in message
        and "ms=" in message
        for message in messages
    )
    assert any(
        "stock_analysis_workbench_timing stage=workbench_projection" in message
        and "ms=" in message
        for message in messages
    )
    assert any(
        "stock_analysis_workbench_timing stage=total" in message and "ms=" in message
        for message in messages
    )


def test_ready_rule_chain_keeps_optional_data_gaps_in_limited_review() -> None:
    module = load_module(
        "backend.app.services.stock_analysis_workbench_service",
        "backend/app/services/stock_analysis_workbench_service.py",
    )
    strategy_envelope = _strategy_envelope()
    strategy_envelope["result"]["rule_readiness"] = [
        {"key": key, "status": "ready", "missing_inputs": []}
        for key in ("market_gate", "sector_rank", "stock_pivot", "risk_exit")
    ]
    strategy_envelope["result"]["data_gaps"] = [
        {
            "input_family": "PMI",
            "status": "missing",
            "evidence": "Optional macro component is not landed.",
        },
        {
            "input_family": "theme_taxonomy",
            "status": "partial",
            "evidence": "Theme evidence is partial.",
        },
    ]

    envelope = module.build_stock_analysis_workbench_envelope(
        strategy_envelope=strategy_envelope,
        requested_as_of_date="2026-06-26",
        top_k=2,
    )
    result = envelope["result"]

    assert result["page_question"]["answer_state"] == "limited_review"
    assert result["decision_summary"]["can_review_candidates"] is True
    assert result["decision_summary"]["primary_blocker"] is None
    assert [item["blocks_review"] for item in result["first_screen"]["data_gaps"]] == [
        False,
        False,
    ]
    assert all(
        "blocks_review" not in item for item in strategy_envelope["result"]["data_gaps"]
    )
    assert [(item["code"], item["severity"]) for item in result["issues"]] == [
        ("data_gap_missing", "warning"),
        ("data_gap_partial", "warning"),
    ]


@pytest.mark.parametrize(
    ("rule_readiness", "expected_code", "expected_blocker"),
    [
        (
            [],
            "rule_readiness_missing_market_gate",
            "Required rule readiness is missing: market_gate.",
        ),
        (
            [
                {"key": key, "status": "ready", "missing_inputs": []}
                for key in ("market_gate", "sector_rank", "stock_pivot")
            ],
            "rule_readiness_missing_risk_exit",
            "Required rule readiness is missing: risk_exit.",
        ),
        (
            [
                {"key": key, "status": "ready", "missing_inputs": []}
                for key in ("market_gate", "sector_rank", "stock_pivot")
            ]
            + [
                {
                    "key": "risk_exit",
                    "status": "blocked",
                    "summary": "Risk exit requires an ACTIVE position snapshot.",
                    "missing_inputs": ["position_snapshot"],
                }
            ],
            "rule_readiness_blocked_risk_exit",
            "Risk exit requires an ACTIVE position snapshot.",
        ),
    ],
)
def test_rule_readiness_is_fail_closed_with_a_specific_blocker(
    rule_readiness: list[dict[str, Any]],
    expected_code: str,
    expected_blocker: str,
) -> None:
    module = load_module(
        "backend.app.services.stock_analysis_workbench_service",
        "backend/app/services/stock_analysis_workbench_service.py",
    )
    strategy_envelope = _strategy_envelope()
    strategy_envelope["result"]["rule_readiness"] = rule_readiness

    result = module.build_stock_analysis_workbench_envelope(
        strategy_envelope=strategy_envelope,
        requested_as_of_date="2026-06-26",
        top_k=2,
    )["result"]

    assert result["page_question"]["answer_state"] == "blocked"
    assert result["decision_summary"]["can_review_candidates"] is False
    assert result["decision_summary"]["primary_blocker"] == expected_blocker
    assert result["issues"][0] == {
        "severity": "blocking",
        "code": expected_code,
        "message": expected_blocker,
        "source_module": "main",
    }


@pytest.mark.parametrize(
    "duplicate_statuses", [("blocked", "ready"), ("ready", "blocked")]
)
def test_duplicate_required_rule_readiness_is_fail_closed_regardless_of_order(
    duplicate_statuses: tuple[str, str],
) -> None:
    module = load_module(
        "backend.app.services.stock_analysis_workbench_service",
        "backend/app/services/stock_analysis_workbench_service.py",
    )
    strategy_envelope = _strategy_envelope()
    strategy_envelope["result"]["rule_readiness"] = [
        {"key": key, "status": "ready", "missing_inputs": []}
        for key in ("market_gate", "sector_rank", "stock_pivot")
    ] + [
        {
            "key": "risk_exit",
            "status": status,
            "summary": f"Risk exit row is {status}.",
            "missing_inputs": [] if status == "ready" else ["position_snapshot"],
        }
        for status in duplicate_statuses
    ]

    result = module.build_stock_analysis_workbench_envelope(
        strategy_envelope=strategy_envelope,
        requested_as_of_date="2026-06-26",
        top_k=2,
    )["result"]

    assert result["page_question"]["answer_state"] == "blocked"
    assert result["decision_summary"]["can_review_candidates"] is False
    assert (
        result["decision_summary"]["primary_blocker"]
        == "Duplicate rule readiness rows: risk_exit."
    )
    assert result["issues"][0]["code"] == "rule_readiness_duplicate_risk_exit"


@pytest.mark.parametrize(
    ("malformed_row", "expected_code", "expected_message"),
    [
        (
            {"status": "blocked"},
            "rule_readiness_missing_key",
            "Rule readiness row 4 is missing a non-empty key.",
        ),
        (
            "not-a-readiness-row",
            "rule_readiness_malformed_row",
            "Rule readiness row 4 must be an object.",
        ),
    ],
)
def test_malformed_rule_readiness_rows_are_fail_closed(
    malformed_row: object,
    expected_code: str,
    expected_message: str,
) -> None:
    module = load_module(
        "backend.app.services.stock_analysis_workbench_service",
        "backend/app/services/stock_analysis_workbench_service.py",
    )
    strategy_envelope = _strategy_envelope()
    strategy_envelope["result"]["rule_readiness"] = [
        {"key": key, "status": "ready", "missing_inputs": []}
        for key in ("market_gate", "sector_rank", "stock_pivot", "risk_exit")
    ] + [malformed_row]

    result = module.build_stock_analysis_workbench_envelope(
        strategy_envelope=strategy_envelope,
        requested_as_of_date="2026-06-26",
        top_k=2,
    )["result"]

    assert result["page_question"]["answer_state"] == "blocked"
    assert result["decision_summary"]["can_review_candidates"] is False
    assert result["decision_summary"]["primary_blocker"] == expected_message
    assert result["issues"][0] == {
        "severity": "blocking",
        "code": expected_code,
        "message": expected_message,
        "source_module": "main",
    }


def test_required_gap_without_status_is_unavailable_and_fail_closed() -> None:
    module = load_module(
        "backend.app.services.stock_analysis_workbench_service",
        "backend/app/services/stock_analysis_workbench_service.py",
    )
    strategy_envelope = _strategy_envelope()
    strategy_envelope["result"]["rule_readiness"] = [
        {"key": key, "status": "ready", "missing_inputs": []}
        for key in ("market_gate", "sector_rank", "stock_pivot", "risk_exit")
    ]
    strategy_envelope["result"]["data_gaps"] = [
        {
            "input_family": "position_risk",
            "evidence": "No ACTIVE A-share rows exist for 2026-06-26.",
        }
    ]

    result = module.build_stock_analysis_workbench_envelope(
        strategy_envelope=strategy_envelope,
        requested_as_of_date="2026-06-26",
        top_k=2,
    )["result"]

    assert result["first_screen"]["data_gaps"][0]["blocks_review"] is True
    assert result["page_question"]["answer_state"] == "blocked"
    assert result["decision_summary"]["can_review_candidates"] is False
    assert (
        result["decision_summary"]["primary_blocker"]
        == "No ACTIVE A-share rows exist for 2026-06-26."
    )
    assert result["issues"] == [
        {
            "severity": "blocking",
            "code": "data_gap_unavailable",
            "message": "No ACTIVE A-share rows exist for 2026-06-26.",
            "source_module": "main",
        }
    ]


@pytest.mark.parametrize(
    ("gap_overrides", "expected_code"),
    [
        ({"tier": "stale"}, "data_gap_stale"),
        ({"age_days": -1}, "data_gap_look_ahead"),
    ],
)
def test_ready_gap_with_invalid_freshness_is_fail_closed(
    gap_overrides: dict[str, object],
    expected_code: str,
) -> None:
    module = load_module(
        "backend.app.services.stock_analysis_workbench_service",
        "backend/app/services/stock_analysis_workbench_service.py",
    )
    strategy_envelope = _strategy_envelope()
    strategy_envelope["result"]["rule_readiness"] = [
        {"key": key, "status": "ready", "missing_inputs": []}
        for key in ("market_gate", "sector_rank", "stock_pivot", "risk_exit")
    ]
    strategy_envelope["result"]["data_gaps"] = [
        {
            "input_family": "turnover_persistence",
            "status": "ready",
            "evidence": "Freshness evidence violates the resolved trade date boundary.",
            **gap_overrides,
        }
    ]

    result = module.build_stock_analysis_workbench_envelope(
        strategy_envelope=strategy_envelope,
        requested_as_of_date="2026-06-26",
        top_k=2,
    )["result"]

    assert result["first_screen"]["data_gaps"][0]["blocks_review"] is True
    assert result["page_question"]["answer_state"] == "blocked"
    assert result["decision_summary"]["can_review_candidates"] is False
    assert result["decision_summary"]["primary_blocker"] == (
        "Freshness evidence violates the resolved trade date boundary."
    )
    assert result["issues"] == [
        {
            "severity": "blocking",
            "code": expected_code,
            "message": "Freshness evidence violates the resolved trade date boundary.",
            "source_module": "main",
        }
    ]


def test_required_position_gap_blocks_after_optional_gaps_without_promoting_them() -> (
    None
):
    module = load_module(
        "backend.app.services.stock_analysis_workbench_service",
        "backend/app/services/stock_analysis_workbench_service.py",
    )
    strategy_envelope = _strategy_envelope()
    strategy_envelope["result"]["rule_readiness"] = [
        {"key": key, "status": "ready", "missing_inputs": []}
        for key in ("market_gate", "sector_rank", "stock_pivot")
    ] + [
        {
            "key": "risk_exit",
            "status": "blocked",
            "summary": "Risk exit requires an ACTIVE A-share position snapshot.",
            "missing_inputs": ["position_snapshot"],
        }
    ]
    strategy_envelope["result"]["data_gaps"] = [
        {
            "input_family": "PMI",
            "status": "missing",
            "evidence": "Optional PMI input is not landed.",
        },
        {
            "input_family": "credit_impulse",
            "status": "missing",
            "evidence": "Optional credit input is not landed.",
        },
        {
            "input_family": "position_risk",
            "status": "missing",
            "evidence": "No ACTIVE A-share rows exist for 2026-06-26.",
        },
    ]

    result = module.build_stock_analysis_workbench_envelope(
        strategy_envelope=strategy_envelope,
        requested_as_of_date="2026-06-26",
        top_k=2,
    )["result"]

    assert result["page_question"]["answer_state"] == "blocked"
    assert result["decision_summary"]["can_review_candidates"] is False
    assert result["decision_summary"]["primary_blocker"] == (
        "Risk exit requires an ACTIVE A-share position snapshot."
    )
    assert [item["blocks_review"] for item in result["first_screen"]["data_gaps"]] == [
        False,
        False,
        True,
    ]
    assert [
        (item["code"], item["severity"], item["message"]) for item in result["issues"]
    ] == [
        (
            "rule_readiness_blocked_risk_exit",
            "blocking",
            "Risk exit requires an ACTIVE A-share position snapshot.",
        ),
        ("data_gap_missing", "warning", "Optional PMI input is not landed."),
        ("data_gap_missing", "warning", "Optional credit input is not landed."),
        (
            "data_gap_missing",
            "blocking",
            "No ACTIVE A-share rows exist for 2026-06-26.",
        ),
    ]


def test_stock_analysis_workbench_route_validates_date_and_delegates_to_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    route_module = load_module(
        "backend.app.api.routes.market_data_livermore",
        "backend/app/api/routes/market_data_livermore.py",
    )
    calls: list[dict[str, Any]] = []

    def fake_workbench(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {
            "result_meta": {
                "trace_id": "tr_stock_analysis_workbench_test",
                "basis": "analytical",
                "result_kind": "market_data.stock_analysis.workbench",
                "formal_use_allowed": False,
                "scenario_flag": False,
                "source_version": "sv_test",
                "vendor_version": "vv_test",
                "rule_version": "rv_stock_analysis_workbench_v1",
                "cache_version": "cv_stock_analysis_workbench_v1",
                "quality_flag": "ok",
                "vendor_status": "ok",
                "fallback_mode": "none",
                "tables_used": [],
                "evidence_rows": 0,
                "source_surface": "market_data",
            },
            "result": {"route": "/stock-analysis"},
        }

    monkeypatch.setattr(
        route_module, "stock_analysis_workbench_envelope", fake_workbench, raising=False
    )
    monkeypatch.setattr(
        route_module, "_ensure_livermore_read_allowed", lambda **_kwargs: None
    )
    route_module.market_home_response_cache.invalidate()

    app = FastAPI()
    app.include_router(route_module.router)
    app.dependency_overrides[route_module.get_auth_context] = lambda: (
        route_module.AuthContext(
            user_id="route-test",
            role="viewer",
            identity_source="test",
        )
    )
    client = TestClient(app)

    response = client.get(
        "/ui/market-data/stock-analysis/workbench",
        params={
            "as_of_date": "2026-06-26",
            "include": "main,signal_confluence",
            "sector_window_days": 30,
            "top_k": 3,
        },
    )

    assert response.status_code == 200
    assert response.json()["result"]["route"] == "/stock-analysis"
    assert "workbench;dur=" in response.headers["server-timing"]
    assert "overlay;dur=" in response.headers["server-timing"]
    assert 'cache;desc="produce";dur=' in response.headers["server-timing"]
    assert "wait;dur=0.000" in response.headers["server-timing"]
    assert calls
    assert calls[0]["as_of_date"] == "2026-06-26"
    assert calls[0]["include"] == "main,signal_confluence"
    assert calls[0]["sector_window_days"] == 30
    assert calls[0]["top_k"] == 3

    cached = client.get(
        "/ui/market-data/stock-analysis/workbench",
        params={
            "as_of_date": "2026-06-26",
            "include": "main,signal_confluence",
            "sector_window_days": 30,
            "top_k": 3,
        },
    )

    assert cached.status_code == 200
    assert "overlay;dur=" in cached.headers["server-timing"]
    assert 'cache;desc="hit";dur=' in cached.headers["server-timing"]
    assert "wait;dur=0.000" in cached.headers["server-timing"]
    assert len(calls) == 1

    invalid = client.get(
        "/ui/market-data/stock-analysis/workbench",
        params={"as_of_date": "bad-date"},
    )

    assert invalid.status_code == 422
    assert len(calls) == 1
    route_module.market_home_response_cache.invalidate()


def test_stock_analysis_workbench_server_timing_surfaces_inflight_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    route_module = load_module(
        "backend.app.api.routes.market_data_livermore",
        "backend/app/api/routes/market_data_livermore.py",
    )
    monkeypatch.setattr(route_module, "get_settings", lambda: object())
    monkeypatch.setattr(
        route_module, "_ensure_livermore_read_allowed", lambda **_kwargs: None
    )
    monkeypatch.setattr(
        route_module,
        "_cached_stock_analysis_workbench",
        lambda **_kwargs: (
            {"result": {"route": "/stock-analysis"}},
            "wait",
            0.0,
            1.25,
            8.5,
        ),
    )

    app = FastAPI()
    app.include_router(route_module.router)
    app.dependency_overrides[route_module.get_auth_context] = lambda: (
        route_module.AuthContext(
            user_id="route-test",
            role="viewer",
            identity_source="test",
        )
    )

    response = TestClient(app).get("/ui/market-data/stock-analysis/workbench")

    assert response.status_code == 200
    assert "overlay;dur=1.250" in response.headers["server-timing"]
    assert 'cache;desc="wait";dur=8.500' in response.headers["server-timing"]
    assert "wait;dur=8.500" in response.headers["server-timing"]
    assert "compute;dur=0.000" in response.headers["server-timing"]


def test_stock_analysis_workbench_cache_key_tracks_choice_catalog_version(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    route_module = load_module(
        "backend.app.api.routes.market_data_livermore",
        "backend/app/api/routes/market_data_livermore.py",
    )
    catalog = tmp_path / "choice-stock.json"
    monkeypatch.setattr(route_module, "livermore_data_version", lambda _path: "db-v1")

    catalog.write_text("{}", encoding="utf-8")
    first = route_module._stock_analysis_workbench_cache_key(
        duckdb_path="fixture.duckdb",
        catalog_file=catalog,
        as_of_date=None,
        include=None,
        sector_window_days=20,
        top_k=3,
    )

    catalog.write_text('{"version": 2}', encoding="utf-8")
    second = route_module._stock_analysis_workbench_cache_key(
        duckdb_path="fixture.duckdb",
        catalog_file=catalog,
        as_of_date=None,
        include=None,
        sector_window_days=20,
        top_k=3,
    )

    assert first != second
    assert "::catalog_version=" in second


@pytest.mark.parametrize(
    "changed_input",
    [
        "hybrid_fusion_strategy.yaml",
        "cycle_rotation_macro_official_availability.json",
        "cycle_rotation_macro_official_releases.json",
    ],
)
def test_livermore_business_input_signature_invalidates_all_cache_layers(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    changed_input: str,
) -> None:
    service_module = load_module(
        "backend.app.services.market_data_livermore_service",
        "backend/app/services/market_data_livermore_service.py",
    )
    input_path_attributes = {
        "hybrid_fusion_strategy.yaml": "DEFAULT_STRATEGY_YAML",
        "cycle_rotation_macro_official_availability.json": "_OFFICIAL_AVAILABILITY_MANIFEST_PATH",
        "cycle_rotation_macro_official_releases.json": "_OFFICIAL_RELEASES_MANIFEST_PATH",
    }
    input_paths = {}
    for filename, attribute in input_path_attributes.items():
        path = tmp_path / filename
        path.write_text(f"{filename}:v1", encoding="utf-8")
        os.utime(path, ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_000))
        input_paths[filename] = path
        monkeypatch.setattr(service_module, attribute, path)

    route_module = load_module(
        "backend.app.api.routes.market_data_livermore",
        "backend/app/api/routes/market_data_livermore.py",
    )
    duckdb_path = tmp_path / "fixture.duckdb"
    duckdb_path.write_bytes(b"duckdb-placeholder")
    catalog = tmp_path / "choice-stock.json"
    catalog.write_text("{}", encoding="utf-8")
    readiness = service_module.choice_stock_readiness_missing("fixture")

    def outer_key() -> str:
        return route_module._stock_analysis_workbench_cache_key(
            duckdb_path=str(duckdb_path),
            catalog_file=catalog,
            as_of_date=None,
            include=None,
            sector_window_days=20,
            top_k=3,
        )

    def direct_strategy_key() -> str:
        return route_module._livermore_strategy_cache_key(
            duckdb_path=str(duckdb_path),
            catalog_file=catalog,
            as_of_date=None,
        )

    def inner_key() -> tuple[object, ...] | None:
        return service_module._livermore_strategy_payload_cache_key(
            duckdb_path=str(duckdb_path),
            as_of_date=date(2026, 7, 16),
            stock_readiness=readiness,
            backfill_mode=False,
            stock_candidate_policy=None,
        )

    first_outer = outer_key()
    first_direct = direct_strategy_key()
    first_inner = inner_key()

    os.utime(
        input_paths[changed_input],
        ns=(1_700_000_001_000_000_000, 1_700_000_001_000_000_000),
    )
    touched_outer = outer_key()
    touched_direct = direct_strategy_key()
    touched_inner = inner_key()

    input_paths[changed_input].write_text(
        f"{changed_input}:v2",
        encoding="utf-8",
    )
    os.utime(
        input_paths[changed_input],
        ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_000),
    )
    second_outer = outer_key()
    second_direct = direct_strategy_key()
    second_inner = inner_key()

    assert (touched_outer, touched_direct, touched_inner) == (
        first_outer,
        first_direct,
        first_inner,
    )
    assert {
        "outer_workbench_key_changed": first_outer != second_outer,
        "direct_strategy_key_changed": first_direct != second_direct,
        "inner_strategy_payload_key_changed": first_inner != second_inner,
    } == {
        "outer_workbench_key_changed": True,
        "direct_strategy_key_changed": True,
        "inner_strategy_payload_key_changed": True,
    }


def test_signal_confluence_cache_key_invalidates_on_business_input_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    route_module = load_module(
        "backend.app.api.routes.market_data_livermore",
        "backend/app/api/routes/market_data_livermore.py",
    )
    monkeypatch.setattr(route_module, "livermore_data_version", lambda _path: "db-v1")
    monkeypatch.setattr(route_module, "livermore_business_inputs_version", lambda: "inputs-v1")
    common = {
        "duckdb_path": "fixture.duckdb",
        "catalog_file": "choice-stock.json",
        "as_of_date": "2026-07-16",
    }

    first = route_module._livermore_signal_confluence_cache_key(**common)
    monkeypatch.setattr(route_module, "livermore_business_inputs_version", lambda: "inputs-v2")
    second = route_module._livermore_signal_confluence_cache_key(**common)

    assert first != second
    assert "::business_inputs=inputs-v2" in second


def test_stock_analysis_workbench_cache_key_normalizes_default_include(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    route_module = load_module(
        "backend.app.api.routes.market_data_livermore",
        "backend/app/api/routes/market_data_livermore.py",
    )
    catalog = tmp_path / "choice-stock.json"
    catalog.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(route_module, "livermore_data_version", lambda _path: "db-v1")

    def cache_key(include: str | None) -> str:
        return route_module._stock_analysis_workbench_cache_key(
            duckdb_path="fixture.duckdb",
            catalog_file=catalog,
            as_of_date=None,
            include=include,
            sector_window_days=20,
            top_k=10,
        )

    default_keys = {
        cache_key(None),
        cache_key(""),
        cache_key("main,evidence_summary"),
        cache_key(" evidence_summary , main , main "),
    }

    assert len(default_keys) == 1
    assert cache_key("signal_confluence") != next(iter(default_keys))


def test_stock_analysis_workbench_cache_retention_avoids_time_only_recompute() -> None:
    route_module = load_module(
        "backend.app.api.routes.market_data_livermore",
        "backend/app/api/routes/market_data_livermore.py",
    )

    assert route_module.STOCK_ANALYSIS_WORKBENCH_CACHE_TTL_SECONDS >= 24 * 60 * 60


def test_stock_kline_analysis_route_validates_and_delegates_to_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    route_module = load_module(
        "backend.app.api.routes.market_data_livermore",
        "backend/app/api/routes/market_data_livermore.py",
    )
    calls: list[dict[str, Any]] = []

    def fake_kline(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {
            "result_meta": {
                "trace_id": "tr_stock_kline_analysis_test",
                "basis": "analytical",
                "result_kind": "market_data.stock_analysis.kline",
                "formal_use_allowed": False,
                "scenario_flag": False,
                "source_version": "sv_test",
                "vendor_version": "vv_test",
                "rule_version": "rv_stock_kline_analysis_observation_v1",
                "cache_version": "cv_stock_kline_analysis_observation_v1",
                "quality_flag": "ok",
                "vendor_status": "ok",
                "fallback_mode": "none",
                "tables_used": [],
                "evidence_rows": 0,
                "source_surface": "market_data",
            },
            "result": {
                "basis": "analytical",
                "state": "ok",
                "contract_status": "observational_only",
                "formal_use_allowed": False,
                "trading_instruction_allowed": False,
                "stock_code": "300604.SZ",
            },
        }

    monkeypatch.setattr(
        route_module, "stock_kline_analysis_envelope", fake_kline, raising=False
    )
    monkeypatch.setattr(
        route_module, "_ensure_livermore_read_allowed", lambda **_kwargs: None
    )
    monkeypatch.setattr(
        route_module.market_home_response_cache,
        "get_or_build",
        lambda _key, builder: builder(),
    )

    app = FastAPI()
    app.include_router(route_module.router)
    app.dependency_overrides[route_module.get_auth_context] = lambda: (
        route_module.AuthContext(
            user_id="route-test",
            role="viewer",
            identity_source="test",
        )
    )
    client = TestClient(app)

    response = client.get(
        "/ui/market-data/stock-analysis/kline-analysis",
        params={"stock_code": "300604.SZ", "as_of_date": "2026-06-26", "lookback": 61},
    )

    assert response.status_code == 200
    assert response.json()["result"]["contract_status"] == "observational_only"
    assert calls
    assert calls[0]["stock_code"] == "300604.SZ"
    assert calls[0]["as_of_date"].isoformat() == "2026-06-26"
    assert calls[0]["lookback"] == 61

    invalid_stock = client.get(
        "/ui/market-data/stock-analysis/kline-analysis",
        params={"stock_code": "bad/code", "lookback": 61},
    )
    invalid_date = client.get(
        "/ui/market-data/stock-analysis/kline-analysis",
        params={"stock_code": "300604.SZ", "as_of_date": "bad-date", "lookback": 61},
    )

    assert invalid_stock.status_code == 422
    assert invalid_date.status_code == 422
