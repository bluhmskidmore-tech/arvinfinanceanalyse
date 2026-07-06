from __future__ import annotations

from typing import Any

from tests.helpers import load_module


def _strategy_envelope() -> dict[str, Any]:
    return {
        "result_meta": {
            "trace_id": "tr_livermore_strategy_first_screen_test",
            "basis": "analytical",
            "result_kind": "market_data.livermore",
            "formal_use_allowed": False,
            "scenario_flag": False,
            "source_version": "sv_livermore_first_screen_test",
            "vendor_version": "vv_livermore_first_screen_test",
            "rule_version": "rv_livermore_strategy_v1",
            "cache_version": "cv_livermore_strategy_v1",
            "quality_flag": "ok",
            "vendor_status": "ok",
            "fallback_mode": "none",
            "tables_used": ["choice_stock_daily_observation"],
            "evidence_rows": 12,
            "filters_applied": {"as_of_date": "2026-06-26"},
            "source_surface": "market_data",
        },
        "result": {
            "as_of_date": "2026-06-26",
            "requested_as_of_date": "2026-06-26",
            "basis": "analytical",
            "market_gate": {"state": "WARM", "exposure": 0.4},
            "sector_rank": {
                "items": [
                    {"sector_code": "801010", "sector_name": "Banks", "rank": 1, "score": 0.82},
                    {"sector_code": "801020", "sector_name": "Software", "rank": 2, "score": 0.74},
                ],
            },
            "stock_candidates": {
                "items": [
                    {"stock_code": "000002.SZ", "stock_name": "Beta Bank", "rank": 2},
                    {"stock_code": "000001.SZ", "stock_name": "Alpha Bank", "rank": 1},
                ],
            },
            "factor_screen_candidates": {
                "items": [
                    {"stock_code": "000001.SZ", "stock_name": "Alpha Bank", "rank": 1, "score": 0.91},
                ],
            },
            "hybrid_fusion_candidates": {
                "items": [
                    {"stock_code": "600000.SH", "stock_name": "Fusion Bank", "rank": 1, "fusion_score": 0.88},
                ],
            },
            "uptrend_momentum_candidates": {
                "items": [
                    {"stock_code": "300001.SZ", "stock_name": "Momentum Tech", "rank": 1},
                ],
            },
            "risk_exit": {
                "items": [{"stock_code": "000777.SZ", "stock_name": "Exit One", "reason": "2d_below_ema10"}],
                "watch_items": [{"stock_code": "000888.SZ", "stock_name": "Watch One", "triggered": False}],
            },
            "data_gaps": [{"input_family": "news", "status": "partial", "evidence": "news link pending"}],
            "diagnostics": [{"severity": "warning", "code": "NEWS_LINK_PENDING", "message": "news link pending"}],
            "supported_outputs": ["market_gate", "sector_rank", "stock_candidates"],
            "unsupported_outputs": [{"key": "theme_breakout", "reason": "theme catalog pending"}],
        },
    }


def test_workbench_first_screen_contract_snapshot_preserves_current_shape() -> None:
    module = load_module(
        "backend.app.services.stock_analysis_workbench_service",
        "backend/app/services/stock_analysis_workbench_service.py",
    )

    envelope = module.build_stock_analysis_workbench_envelope(
        strategy_envelope=_strategy_envelope(),
        requested_as_of_date="2026-06-26",
        top_k=4,
    )

    first_screen = envelope["result"]["first_screen"]

    assert list(first_screen) == [
        "market_gate",
        "review_queue",
        "sector_snapshot",
        "risk_exit_snapshot",
        "data_gaps",
        "diagnostics",
        "supported_outputs",
        "unsupported_outputs",
    ]
    assert first_screen == {
        "market_gate": {"state": "WARM", "exposure": 0.4},
        "review_queue": [
            {
                "stock_code": "000002.SZ",
                "stock_name": "Beta Bank",
                "rank": 2,
                "source_module": "stock_candidates",
            },
            {
                "stock_code": "000001.SZ",
                "stock_name": "Alpha Bank",
                "rank": 1,
                "source_module": "stock_candidates",
            },
            {
                "stock_code": "000001.SZ",
                "stock_name": "Alpha Bank",
                "rank": 1,
                "score": 0.91,
                "source_module": "factor_screen_candidates",
            },
            {
                "stock_code": "600000.SH",
                "stock_name": "Fusion Bank",
                "rank": 1,
                "fusion_score": 0.88,
                "source_module": "hybrid_fusion_candidates",
            },
        ],
        "sector_snapshot": [
            {"sector_code": "801010", "sector_name": "Banks", "rank": 1, "score": 0.82},
            {"sector_code": "801020", "sector_name": "Software", "rank": 2, "score": 0.74},
        ],
        "risk_exit_snapshot": [
            {
                "stock_code": "000777.SZ",
                "stock_name": "Exit One",
                "reason": "2d_below_ema10",
                "source_module": "risk_exit",
                "risk_exit_bucket": "items",
            },
            {
                "stock_code": "000888.SZ",
                "stock_name": "Watch One",
                "triggered": False,
                "source_module": "risk_exit",
                "risk_exit_bucket": "watch_items",
            },
        ],
        "data_gaps": [{"input_family": "news", "status": "partial", "evidence": "news link pending"}],
        "diagnostics": [{"severity": "warning", "code": "NEWS_LINK_PENDING", "message": "news link pending"}],
        "supported_outputs": ["market_gate", "sector_rank", "stock_candidates"],
        "unsupported_outputs": [{"key": "theme_breakout", "reason": "theme catalog pending"}],
    }
