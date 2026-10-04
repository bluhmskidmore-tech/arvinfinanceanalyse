from __future__ import annotations

import inspect
import json
import os
import sys
from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.helpers import load_module

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]


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


def _ready_pretrade_qualification(module: Any, strategy_envelope: dict[str, Any]) -> dict[str, Any]:
    strategy_result = strategy_envelope["result"]
    return {
        "schema": "pretrade_qualification/v1",
        "status": "ready",
        "reason": None,
        "producer_run_id": "pretrade:test",
        "target_date": strategy_result["as_of_date"],
        "stock_candidate_policy": module.EXECUTION_STOCK_CANDIDATE_POLICY,
        "evidence_sha256": "a" * 64,
        "input_snapshot": {"sha256": "b" * 64},
        "outputs": {
            "strategy_payload_sha256": module.canonical_pretrade_output_sha256(strategy_result),
        },
    }


def test_build_stock_analysis_workbench_envelope_wraps_livermore_strategy_as_observational_contract() -> (
    None
):
    module = load_module(
        "backend.app.services.stock_analysis_workbench_service",
        "backend/app/services/stock_analysis_workbench_service.py",
    )

    strategy_envelope = _strategy_envelope()
    envelope = module.build_stock_analysis_workbench_envelope(
        strategy_envelope=strategy_envelope,
        pretrade_qualification=_ready_pretrade_qualification(module, strategy_envelope),
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


def test_workbench_unavailable_qualification_removes_decision_hints_but_keeps_observations() -> None:
    module = load_module(
        "backend.app.services.stock_analysis_workbench_service",
        "backend/app/services/stock_analysis_workbench_service.py",
    )
    strategy_envelope = _strategy_envelope()

    result = module.build_stock_analysis_workbench_envelope(
        strategy_envelope=strategy_envelope,
        requested_as_of_date="2026-06-26",
        pretrade_qualification={
            "schema": "pretrade_qualification/v1",
            "status": "unavailable",
            "reason": "signal_confluence_not_completed",
        },
    )["result"]

    assert result["pretrade_qualification"]["status"] == "unavailable"
    assert result["pretrade_qualification"]["reason"] == "signal_confluence_not_completed"
    assert len(result["pretrade_qualification"]["strategy_payload_sha256"]) == 64
    assert len(result["pretrade_qualification"]["workbench_projection_sha256"]) == 64
    assert result["first_screen"]["review_queue"][0]["stock_code"] == "000001.SZ"
    assert result["first_screen"]["risk_exit_snapshot"] == []
    assert result["first_screen"]["sector_snapshot"][0]["sector_code"] == "801010"
    assert "stock_candidates" not in result["modules"]["main"]["result"]
    assert "risk_exit" not in result["modules"]["main"]["result"]
    assert result["decision_summary"]["can_review_candidates"] is False
    assert result["issues"][0] == {
        "severity": "warning",
        "code": "pretrade_qualification_unavailable",
        "message": "signal_confluence_not_completed",
        "source_module": "pretrade_qualification",
    }
    assert result["page_question"]["answer_state"] == "blocked"


def test_workbench_keeps_authoritative_observation_queue_when_pretrade_is_unavailable() -> None:
    module = load_module(
        "backend.app.services.stock_analysis_workbench_service",
        "backend/app/services/stock_analysis_workbench_service.py",
    )
    strategy_envelope = _strategy_envelope()
    strategy_result = strategy_envelope["result"]
    strategy_result.update(
        {
            "stock_candidates": {"items": []},
            "factor_screen_candidates": {
                "items": [
                    {"stock_code": "000001.SZ", "stock_name": "平安银行", "rank": 1}
                ]
            },
            "hybrid_fusion_candidates": {
                "items": [
                    {"stock_code": "600000.SH", "stock_name": "浦发银行", "rank": 1}
                ]
            },
            "uptrend_momentum_candidates": {
                "items": [
                    {"stock_code": "000002.SZ", "stock_name": "万科A", "rank": 1}
                ]
            },
            "fresh_trend_watchlist": {
                "items": [
                    {"stock_code": "000333.SZ", "stock_name": "美的集团", "rank": 1}
                ]
            },
            "mean_reversion_candidates": {
                "items": [
                    {"stock_code": "600036.SH", "stock_name": "招商银行", "rank": 1}
                ]
            },
            "theme_breakout": {
                "items": [
                    {
                        "theme_key": "bank",
                        "theme_name": "银行",
                        "rank": 1,
                        "source_kind": "current_overlay",
                        "items": [
                            {
                                "stock_code": "601398.SH",
                                "stock_name": "工商银行",
                                "rank": 1,
                            }
                        ],
                    }
                ]
            },
            "risk_exit": {
                "items": [
                    {"stock_code": "000001.SZ", "reason": "execution_only_exit_hint"}
                ],
                "watch_items": [],
            },
            "rule_readiness": [
                {"key": key, "status": "ready", "missing_inputs": []}
                for key in ("market_gate", "sector_rank", "stock_pivot", "risk_exit")
            ],
            "module_states": [
                {
                    "key": key,
                    "state": "ready",
                    "render_mode": "primary",
                    "source_date": "2026-06-26",
                    "excludes_from_primary": False,
                }
                for key in (
                    "factor_screen_candidates",
                    "uptrend_momentum_candidates",
                    "fresh_trend_watchlist",
                    "mean_reversion_candidates",
                    "theme_breakout",
                )
            ]
            + [
                {
                    "key": "hybrid_fusion",
                    "state": "blocked",
                    "render_mode": "evidence_only",
                    "source_date": "2026-06-26",
                    "excludes_from_primary": True,
                }
            ],
        }
    )

    result = module.build_stock_analysis_workbench_envelope(
        strategy_envelope=strategy_envelope,
        requested_as_of_date="2026-06-26",
        pretrade_qualification={
            "schema": "pretrade_qualification/v1",
            "status": "unavailable",
            "reason": "system_read_generation_missing",
        },
        top_k=10,
    )["result"]

    assert result["pretrade_qualification"]["status"] == "unavailable"
    assert result["pretrade_qualification"]["reason"] == "system_read_generation_missing"
    assert result["formal_use_allowed"] is False
    assert [
        row["source_module"] for row in result["first_screen"]["review_queue"]
    ] == [
        "factor_screen_candidates",
        "uptrend_momentum_candidates",
        "fresh_trend_watchlist",
        "mean_reversion_candidates",
        "theme_breakout",
    ]
    assert result["decision_summary"]["can_review_candidates"] is True
    assert result["decision_summary"]["review_queue_count"] == 5
    assert result["page_question"]["answer_state"] == "limited_review"
    assert result["first_screen"]["risk_exit_snapshot"] == []
    assert "stock_candidates" not in result["modules"]["main"]["result"]
    assert "risk_exit" not in result["modules"]["main"]["result"]


def test_workbench_ready_empty_preserves_observations_but_not_pretrade_hints() -> None:
    module = load_module(
        "backend.app.services.stock_analysis_workbench_service",
        "backend/app/services/stock_analysis_workbench_service.py",
    )
    strategy_envelope = _strategy_envelope()
    qualification = _ready_pretrade_qualification(module, strategy_envelope)
    qualification["status"] = "ready_empty"

    result = module.build_stock_analysis_workbench_envelope(
        strategy_envelope=strategy_envelope,
        requested_as_of_date="2026-06-26",
        pretrade_qualification=qualification,
    )["result"]

    assert result["pretrade_qualification"]["status"] == "ready_empty"
    assert result["first_screen"]["review_queue"][0]["stock_code"] == "000001.SZ"
    assert "stock_candidates" not in result["modules"]["main"]["result"]
    assert result["decision_summary"]["review_queue_count"] == 1


def test_workbench_rejects_ready_evidence_for_a_different_strategy_projection() -> None:
    module = load_module(
        "backend.app.services.stock_analysis_workbench_service",
        "backend/app/services/stock_analysis_workbench_service.py",
    )
    strategy_envelope = _strategy_envelope()
    strategy_envelope["result"]["rule_readiness"] = [
        {"key": key, "status": "ready", "missing_inputs": []}
        for key in ("market_gate", "sector_rank", "stock_pivot", "risk_exit")
    ]
    qualification = _ready_pretrade_qualification(module, strategy_envelope)
    qualification["outputs"]["strategy_payload_sha256"] = "f" * 64

    result = module.build_stock_analysis_workbench_envelope(
        strategy_envelope=strategy_envelope,
        requested_as_of_date="2026-06-26",
        pretrade_qualification=qualification,
    )["result"]

    assert result["pretrade_qualification"]["status"] == "unavailable"
    assert result["pretrade_qualification"]["reason"] == "pretrade_strategy_projection_mismatch"
    assert result["first_screen"]["review_queue"][0]["stock_code"] == "000001.SZ"
    assert result["decision_summary"]["can_review_candidates"] is True
    assert "stock_candidates" not in result["modules"]["main"]["result"]


def test_workbench_meta_error_still_blocks_research_when_pretrade_is_unavailable() -> None:
    module = load_module(
        "backend.app.services.stock_analysis_workbench_service",
        "backend/app/services/stock_analysis_workbench_service.py",
    )
    strategy_envelope = _strategy_envelope()
    strategy_envelope["result_meta"]["quality_flag"] = "error"
    strategy_envelope["result"]["rule_readiness"] = [
        {"key": key, "status": "ready", "missing_inputs": []}
        for key in ("market_gate", "sector_rank", "stock_pivot", "risk_exit")
    ]

    result = module.build_stock_analysis_workbench_envelope(
        strategy_envelope=strategy_envelope,
        requested_as_of_date="2026-06-26",
        pretrade_qualification={
            "schema": "pretrade_qualification/v1",
            "status": "unavailable",
            "reason": "system_read_generation_missing",
        },
    )["result"]

    assert result["first_screen"]["review_queue"][0]["stock_code"] == "000001.SZ"
    assert result["modules"]["main"]["status"] == "error"
    assert result["decision_summary"]["can_review_candidates"] is False
    assert result["page_question"]["answer_state"] == "blocked"
    assert next(
        issue for issue in result["issues"] if issue["code"] == "module_error"
    )["severity"] == "blocking"


def test_stock_analysis_workbench_integrates_exact_replay_closure_json_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module(
        "backend.app.services.stock_analysis_workbench_service",
        "backend/app/services/stock_analysis_workbench_service.py",
    )
    expected = module.empty_current_rule_replay_closure(
        selection_status="no_active_certified",
        data_availability="no_data",
        status="insufficient",
        primary_blocker_code="no_active_certified_cohort",
        reason_codes=["no_active_certified_cohort"],
        tables_used=[
            "stock_analysis_current_rule_cohort_manifest",
            "stock_analysis_current_rule_replay_fact",
            "stock_analysis_current_rule_date_certificate",
        ],
    )
    reader_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        module,
        "livermore_strategy_envelope_from_catalog",
        lambda **_kwargs: _strategy_envelope(),
    )

    def fake_reader(**kwargs: object) -> dict[str, object]:
        reader_calls.append(dict(kwargs))
        return expected

    monkeypatch.setattr(module, "read_current_rule_replay_closure", fake_reader)

    envelope = module.stock_analysis_workbench_envelope(
        duckdb_path="fixture.duckdb",
        as_of_date="2026-06-26",
        choice_stock_catalog_file=object(),
    )

    assert envelope["result"]["replay_closure"] == expected
    assert envelope["result"]["contract_status"] == "observational_only"
    assert envelope["result"]["formal_use_allowed"] is False
    assert reader_calls == [
        {
            "duckdb_path": "fixture.duckdb",
            "page_as_of_date": "2026-06-26",
        }
    ]
    assert envelope["result_meta"]["tables_used"] == [
        "choice_stock_daily_observation",
        "stock_analysis_current_rule_cohort_manifest",
        "stock_analysis_current_rule_replay_fact",
        "stock_analysis_current_rule_date_certificate",
    ]


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
    stock_alpha = rows[0]
    assert stock_alpha["source_module"] == "stock_candidates"
    assert stock_alpha["rank"] == 1
    assert stock_alpha["theme_memberships"] == [
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


def _theme_container(members: list[tuple[int, str, str]]) -> dict[str, object]:
    return {
        "items": [
            {
                "rank": 1,
                "theme_key": "concept:T1",
                "theme_name": "Theme one",
                "source_kind": "real_concept",
                "items": [
                    {"rank": rank, "stock_code": code, "stock_name": name}
                    for rank, code, name in members
                ],
            }
        ]
    }


def test_candidate_queue_reserves_tail_slots_for_theme_candidates() -> None:
    """题材保底：top_k 被前置源占满时，队尾 2 席换成题材行（top_k 的 1/5 封顶 2）。"""
    module = load_module(
        "backend.app.services.stock_analysis_workbench_service",
        "backend/app/services/stock_analysis_workbench_service.py",
    )
    result = {
        "factor_screen_candidates": {
            "items": [
                {"stock_code": f"6001{i:02d}.SH", "stock_name": f"Factor {i}", "rank": i + 1}
                for i in range(30)
            ]
        },
        "theme_breakout": _theme_container(
            [(1, "300001.SZ", "Theme A"), (2, "300002.SZ", "Theme B"), (3, "300003.SZ", "Theme C")]
        ),
    }

    rows = module._candidate_queue(result, top_k=10)

    assert len(rows) == 10
    assert [row["source_module"] for row in rows[:8]] == ["factor_screen_candidates"] * 8
    assert [row["rank"] for row in rows[:8]] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert [(row["source_module"], row["stock_code"]) for row in rows[8:]] == [
        ("theme_breakout", "300001.SZ"),
        ("theme_breakout", "300002.SZ"),
    ]


def test_candidate_queue_theme_reservation_skips_stocks_already_queued() -> None:
    """题材成员与已入队股票同码时不重复占位（题材归属走 membership 继承），席位给下一只。"""
    module = load_module(
        "backend.app.services.stock_analysis_workbench_service",
        "backend/app/services/stock_analysis_workbench_service.py",
    )
    result = {
        "factor_screen_candidates": {
            "items": [
                {"stock_code": f"6002{i:02d}.SH", "stock_name": f"Factor {i}", "rank": i + 1}
                for i in range(10)
            ]
        },
        "theme_breakout": _theme_container(
            [(1, "600200.SH", "Dup with factor"), (2, "300009.SZ", "Theme only")]
        ),
    }

    rows = module._candidate_queue(result, top_k=10)

    assert len(rows) == 10
    codes = [str(row["stock_code"]) for row in rows]
    assert len(codes) == len(set(codes))
    assert (rows[-1]["source_module"], rows[-1]["stock_code"]) == ("theme_breakout", "300009.SZ")
    dup_row = next(row for row in rows if row["stock_code"] == "600200.SH")
    assert dup_row["source_module"] == "factor_screen_candidates"
    assert dup_row["theme_memberships"]


def test_candidate_queue_small_top_k_skips_theme_reservation() -> None:
    """top_k < 5 时不保底（top_k // 5 == 0），避免小队列被题材挤占。"""
    module = load_module(
        "backend.app.services.stock_analysis_workbench_service",
        "backend/app/services/stock_analysis_workbench_service.py",
    )
    result = {
        "factor_screen_candidates": {
            "items": [
                {"stock_code": f"6003{i:02d}.SH", "stock_name": f"Factor {i}", "rank": i + 1}
                for i in range(6)
            ]
        },
        "theme_breakout": _theme_container([(1, "300010.SZ", "Theme only")]),
    }

    rows = module._candidate_queue(result, top_k=4)

    assert [(row["source_module"], row["stock_code"]) for row in rows] == [
        ("factor_screen_candidates", "600300.SH"),
        ("factor_screen_candidates", "600301.SH"),
        ("factor_screen_candidates", "600302.SH"),
        ("factor_screen_candidates", "600303.SH"),
    ]


def test_candidate_queue_passes_factor_screen_breakout_geometry_fields_through() -> None:
    """多因子候选的观察位几何字段(pattern/pattern_code/distance_to_breakout_pct/close/
    breakout_level)必须原样进入 workbench first_screen.review_queue 行;
    缺 K 线候选的 None 也必须保留(不得被清洗成 0 或删除)。"""
    module = load_module(
        "backend.app.services.stock_analysis_workbench_service",
        "backend/app/services/stock_analysis_workbench_service.py",
    )
    result = {
        "factor_screen_candidates": {
            "items": [
                {
                    "rank": 1,
                    "stock_code": "600021.SH",
                    "stock_name": "Geometry",
                    "score": 0.9,
                    "close": 103.0,
                    "breakout_level": 100.0,
                    "distance_to_breakout_pct": 3.0,
                    "pattern": "突破（参考）",
                    "pattern_code": "breakout",
                },
                {
                    "rank": 2,
                    "stock_code": "600022.SH",
                    "stock_name": "MissingKline",
                    "score": 0.8,
                    "close": None,
                    "breakout_level": None,
                    "distance_to_breakout_pct": None,
                    "pattern": None,
                    "pattern_code": None,
                },
            ]
        },
    }

    rows = module._candidate_queue(result, top_k=10)

    assert [(row["source_module"], row["stock_code"]) for row in rows] == [
        ("factor_screen_candidates", "600021.SH"),
        ("factor_screen_candidates", "600022.SH"),
    ]
    geometry_row = rows[0]
    assert geometry_row["pattern"] == "突破（参考）"
    assert geometry_row["pattern_code"] == "breakout"
    assert geometry_row["distance_to_breakout_pct"] == 3.0
    assert geometry_row["close"] == 103.0
    assert geometry_row["breakout_level"] == 100.0
    missing_row = rows[1]
    assert missing_row["pattern"] is None
    assert missing_row["pattern_code"] is None
    assert missing_row["distance_to_breakout_pct"] is None
    assert missing_row["close"] is None
    assert missing_row["breakout_level"] is None


def test_candidate_queue_passes_breakout_geometry_fields_through_for_all_observation_sources() -> None:
    """动量/新趋势/超跌/融合四个扩展源的观察位几何字段(pattern/pattern_code/
    distance_to_breakout_pct/close/breakout_level)与停牌披露字段
    (price_as_of_date/price_stale)必须原样进入 review_queue 行;
    缺 K 线候选的 None 也必须保留(不得被清洗成 0 或删除)。"""
    module = load_module(
        "backend.app.services.stock_analysis_workbench_service",
        "backend/app/services/stock_analysis_workbench_service.py",
    )
    result = {
        "hybrid_fusion_candidates": {
            "items": [
                {
                    "rank": 1,
                    "stock_code": "600001.SH",
                    "stock_name": "Fusion Stale",
                    "fusion_score": 0.8,
                    "close": 98.0,
                    "breakout_level": 100.0,
                    "distance_to_breakout_pct": -2.0,
                    "pattern": "回踩（参考）",
                    "pattern_code": "pullback",
                    "price_as_of_date": "2026-06-10",
                    "price_stale": True,
                }
            ]
        },
        "uptrend_momentum_candidates": {
            "items": [
                {
                    "rank": 1,
                    "stock_code": "000001.SZ",
                    "stock_name": "Momentum Geometry",
                    "close": 160.0,
                    "breakout_level": 155.0,
                    "distance_to_breakout_pct": 3.2258,
                    "pattern": "突破（参考）",
                    "pattern_code": "breakout",
                }
            ]
        },
        "fresh_trend_watchlist": {
            "items": [
                {
                    "rank": 1,
                    "stock_code": "300001.SZ",
                    "stock_name": "Fresh MissingKline",
                    "close": 50.0,
                    "breakout_level": None,
                    "distance_to_breakout_pct": None,
                    "pattern": None,
                    "pattern_code": None,
                }
            ]
        },
        "mean_reversion_candidates": {
            "items": [
                {
                    "rank": 1,
                    "stock_code": "000002.SZ",
                    "stock_name": "Reversion Geometry",
                    "close": 84.52,
                    "breakout_level": 100.0,
                    "distance_to_breakout_pct": -15.48,
                    "pattern": "回踩（参考）",
                    "pattern_code": "pullback",
                }
            ]
        },
    }

    rows = module._candidate_queue(result, top_k=10)
    by_source = {str(row["source_module"]): row for row in rows}

    assert set(by_source) == {
        "hybrid_fusion_candidates",
        "uptrend_momentum_candidates",
        "fresh_trend_watchlist",
        "mean_reversion_candidates",
    }
    fusion_row = by_source["hybrid_fusion_candidates"]
    assert fusion_row["pattern"] == "回踩（参考）"
    assert fusion_row["pattern_code"] == "pullback"
    assert fusion_row["distance_to_breakout_pct"] == -2.0
    assert fusion_row["price_as_of_date"] == "2026-06-10"
    assert fusion_row["price_stale"] is True
    momentum_row = by_source["uptrend_momentum_candidates"]
    assert momentum_row["close"] == 160.0
    assert momentum_row["breakout_level"] == 155.0
    assert momentum_row["pattern"] == "突破（参考）"
    assert momentum_row["pattern_code"] == "breakout"
    fresh_row = by_source["fresh_trend_watchlist"]
    assert fresh_row["close"] == 50.0
    assert fresh_row["breakout_level"] is None
    assert fresh_row["distance_to_breakout_pct"] is None
    assert fresh_row["pattern"] is None
    assert fresh_row["pattern_code"] is None
    reversion_row = by_source["mean_reversion_candidates"]
    assert reversion_row["distance_to_breakout_pct"] == -15.48
    assert reversion_row["pattern"] == "回踩（参考）"
    assert reversion_row["pattern_code"] == "pullback"


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


@pytest.mark.parametrize(
    ("requested_date", "resolver_date", "expected_strategy_date", "expected_resolver_calls"),
    [
        (None, "2026-06-24", "2026-06-24", 1),
        ("2026-06-26", "2026-06-24", "2026-06-26", 0),
    ],
)
def test_stock_analysis_workbench_envelope_resolves_only_omitted_dates(
    monkeypatch: pytest.MonkeyPatch,
    requested_date: str | None,
    resolver_date: str,
    expected_strategy_date: str,
    expected_resolver_calls: int,
) -> None:
    module = load_module(
        "backend.app.services.stock_analysis_workbench_service",
        "backend/app/services/stock_analysis_workbench_service.py",
    )
    resolver_calls: list[dict[str, object]] = []
    strategy_calls: list[dict[str, object]] = []
    build_calls: list[dict[str, object]] = []
    replay_calls: list[dict[str, object]] = []
    sentinel = {"result": {"route": "/stock-analysis"}}
    strategy_envelope = _strategy_envelope()
    strategy_envelope["result"]["as_of_date"] = expected_strategy_date
    strategy_envelope["result"]["requested_as_of_date"] = expected_strategy_date
    strategy_envelope["result_meta"]["filters_applied"] = {
        "as_of_date": expected_strategy_date,
        "requested_as_of_date": expected_strategy_date,
    }

    def fake_resolver(**kwargs: object) -> str | None:
        resolver_calls.append(dict(kwargs))
        return resolver_date

    def fake_strategy(**kwargs: object) -> dict[str, Any]:
        strategy_calls.append(dict(kwargs))
        return strategy_envelope

    def fake_build(**kwargs: object) -> dict[str, object]:
        build_calls.append(dict(kwargs))
        return sentinel

    def fake_replay_reader(**kwargs: object) -> dict[str, object]:
        replay_calls.append(dict(kwargs))
        return {"status": "ready"}

    monkeypatch.setattr(module, "latest_complete_stock_analysis_date", fake_resolver)
    monkeypatch.setattr(module, "livermore_strategy_envelope_from_catalog", fake_strategy)
    monkeypatch.setattr(module, "read_current_rule_replay_closure", fake_replay_reader)
    monkeypatch.setattr(module, "build_stock_analysis_workbench_envelope", fake_build)

    result = module.stock_analysis_workbench_envelope(
        duckdb_path="fixture.duckdb",
        as_of_date=requested_date,
        choice_stock_catalog_file="choice-stock.json",
    )

    assert result is sentinel
    assert len(resolver_calls) == expected_resolver_calls
    assert strategy_calls[0]["as_of_date"] == expected_strategy_date
    assert replay_calls[0]["page_as_of_date"] == expected_strategy_date
    assert build_calls[0]["requested_as_of_date"] == requested_date
    projected_strategy = build_calls[0]["strategy_envelope"]
    assert isinstance(projected_strategy, dict)
    assert projected_strategy["result"]["requested_as_of_date"] == requested_date
    assert projected_strategy["result_meta"]["filters_applied"]["requested_as_of_date"] == requested_date


def test_latest_complete_stock_analysis_date_selects_newest_common_complete_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.services import market_data_livermore_service as service

    coverage_calls: list[str] = []
    observations = [
        SimpleNamespace(trade_date=date(2026, 6, 24)),
        SimpleNamespace(trade_date=date(2026, 6, 25)),
        SimpleNamespace(trade_date=date(2026, 6, 26)),
    ]

    monkeypatch.setattr(
        service,
        "_load_broad_index_history",
        lambda **_kwargs: (observations, ["fact_choice_macro_daily"]),
    )

    def fake_coverage(**kwargs: object) -> SimpleNamespace:
        candidate_date = str(kwargs["as_of_date"])
        coverage_calls.append(candidate_date)
        return SimpleNamespace(full_coverage=candidate_date == "2026-06-24")

    monkeypatch.setattr(service, "load_choice_stock_materialization_coverage", fake_coverage)

    assert (
        service.latest_complete_stock_analysis_date(duckdb_path="missing-fixture.duckdb")
        == "2026-06-24"
    )
    assert coverage_calls == ["2026-06-26", "2026-06-25", "2026-06-24"]


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
        pretrade_qualification=_ready_pretrade_qualification(module, strategy_envelope),
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
        pretrade_qualification=_ready_pretrade_qualification(module, strategy_envelope),
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
        pretrade_qualification=_ready_pretrade_qualification(module, strategy_envelope),
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
        pretrade_qualification=_ready_pretrade_qualification(module, strategy_envelope),
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
        pretrade_qualification=_ready_pretrade_qualification(module, strategy_envelope),
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
        pretrade_qualification=_ready_pretrade_qualification(module, strategy_envelope),
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
        pretrade_qualification=_ready_pretrade_qualification(module, strategy_envelope),
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
    # `sys.modules` lookup by name (rather than `from ... import ...`) is
    # required here: earlier tests in this file reload
    # `stock_analysis_workbench_service` via `load_module`, which swaps
    # `sys.modules[...]` without updating the parent package's attribute, so
    # a plain `from backend.app.services import stock_analysis_workbench_service`
    # would silently resolve to a stale pre-reload module object.
    workbench_module = sys.modules[route_module.stock_analysis_workbench_envelope.__module__]

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
                "rule_version": "rv_stock_analysis_workbench_v2",
                "cache_version": "cv_stock_analysis_workbench_v2",
                "quality_flag": "ok",
                "vendor_status": "ok",
                "fallback_mode": "none",
                "tables_used": [],
                "evidence_rows": 0,
                "source_surface": "market_data",
            },
            "result": {"route": "/stock-analysis"},
        }

    # The stock-analysis-workbench cache wrapper (route_support) re-resolves
    # `stock_analysis_workbench_envelope` from its defining module on every
    # call (so it always calls through to the latest `load_module`-reloaded
    # service instance), so the endpoint-level stub must be installed on that
    # module rather than on the route module's unused re-exported copy.
    monkeypatch.setattr(
        workbench_module,
        "stock_analysis_workbench_envelope",
        fake_workbench,
        raising=False,
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


def test_stock_analysis_workbench_endpoint_passes_through_candidate_liquidity_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lock daily_amount / liquidity_floor_pass pass-through (true / false / null tri-state)."""
    route_module = load_module(
        "backend.app.api.routes.market_data_livermore",
        "backend/app/api/routes/market_data_livermore.py",
    )
    workbench_module = sys.modules[route_module.stock_analysis_workbench_envelope.__module__]
    route_support_module = sys.modules[
        route_module._cached_stock_analysis_workbench.__module__
    ]

    strategy_envelope = _strategy_envelope()
    strategy_envelope["result"]["stock_candidates"] = {
        "items": [
            {
                "rank": 1,
                "stock_code": "000001.SZ",
                "stock_name": "平安银行",
                "daily_amount": 260_000_000.0,
                "liquidity_floor_pass": True,
            },
            {
                "rank": 2,
                "stock_code": "000002.SZ",
                "stock_name": "万科A",
                "daily_amount": 120_000_000.0,
                "liquidity_floor_pass": False,
            },
            {
                "rank": 3,
                "stock_code": "000003.SZ",
                "stock_name": "缺流动性数据",
                "daily_amount": None,
                "liquidity_floor_pass": None,
            },
        ],
    }
    monkeypatch.setattr(
        workbench_module,
        "livermore_strategy_envelope_from_catalog",
        lambda **_kwargs: strategy_envelope,
    )
    monkeypatch.setattr(
        workbench_module,
        "livermore_attested_strategy_envelope_from_catalog",
        lambda **_kwargs: strategy_envelope,
    )
    monkeypatch.setattr(
        workbench_module,
        "current_system_read_context",
        lambda: SimpleNamespace(pretrade_availability={}),
    )
    monkeypatch.setattr(
        workbench_module,
        "qualify_sealed_pretrade_read",
        lambda **_kwargs: _ready_pretrade_qualification(
            workbench_module, strategy_envelope
        ),
    )
    monkeypatch.setattr(
        workbench_module,
        "read_current_rule_replay_closure",
        lambda **_kwargs: {"status": "ready"},
    )
    monkeypatch.setattr(
        route_support_module,
        "_selected_pretrade_external_read",
        lambda **_kwargs: (
            _ready_pretrade_qualification(workbench_module, strategy_envelope),
            None,
            "2026-06-26",
            "pretrade:test",
        ),
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
        params={"as_of_date": "2026-06-26", "top_k": 3},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    expected = [
        ("000001.SZ", 260_000_000.0, True),
        ("000002.SZ", 120_000_000.0, False),
        ("000003.SZ", None, None),
    ]
    main_items = result["modules"]["main"]["result"]["stock_candidates"]["items"]
    assert [
        (item["stock_code"], item["daily_amount"], item["liquidity_floor_pass"])
        for item in main_items
    ] == expected
    review_rows = [
        row
        for row in result["first_screen"]["review_queue"]
        if row["source_module"] == "stock_candidates"
    ]
    assert [
        (row["stock_code"], row["daily_amount"], row["liquidity_floor_pass"])
        for row in review_rows
    ] == expected
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
    from importlib import import_module

    route_module = load_module(
        "backend.app.api.routes.market_data_livermore",
        "backend/app/api/routes/market_data_livermore.py",
    )
    service_module = import_module("backend.app.services.market_data_livermore_service")
    catalog = tmp_path / "choice-stock.json"
    monkeypatch.setattr(service_module, "livermore_data_version", lambda _path: "db-v1")

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


def test_stock_analysis_workbench_cache_key_changes_after_database_promotion(
    tmp_path,
) -> None:
    route_module = load_module(
        "backend.app.api.routes.market_data_livermore",
        "backend/app/api/routes/market_data_livermore.py",
    )
    database = tmp_path / "fixture.duckdb"
    catalog = tmp_path / "choice-stock.json"
    database.write_bytes(b"duckdb-fixture")
    catalog.write_text("{}", encoding="utf-8")
    os.utime(database, ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_000))

    first = route_module._stock_analysis_workbench_cache_key(
        duckdb_path=str(database),
        catalog_file=catalog,
        as_of_date="2026-06-30",
        include=None,
        sector_window_days=20,
        top_k=10,
    )

    os.utime(database, ns=(1_700_000_001_000_000_000, 1_700_000_001_000_000_000))
    second = route_module._stock_analysis_workbench_cache_key(
        duckdb_path=str(database),
        catalog_file=catalog,
        as_of_date="2026-06-30",
        include=None,
        sector_window_days=20,
        top_k=10,
    )

    assert first != second
    assert "::data_version=1700000001000000000:" in second
    assert "::rule_version=rv_stock_analysis_workbench_v2" in second
    assert "::cache_version=cv_stock_analysis_workbench_v2" in second


def test_stock_kline_analysis_cache_key_changes_after_database_promotion(
    tmp_path,
) -> None:
    route_module = load_module(
        "backend.app.api.routes.market_data_livermore",
        "backend/app/api/routes/market_data_livermore.py",
    )
    database = tmp_path / "fixture.duckdb"
    database.write_bytes(b"duckdb-fixture")
    os.utime(database, ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_000))

    first = route_module._stock_kline_analysis_cache_key(
        duckdb_path=str(database),
        stock_code="000001.SZ",
        as_of_date="2026-06-30",
        lookback=240,
    )

    os.utime(database, ns=(1_700_000_001_000_000_000, 1_700_000_001_000_000_000))
    second = route_module._stock_kline_analysis_cache_key(
        duckdb_path=str(database),
        stock_code="000001.SZ",
        as_of_date="2026-06-30",
        lookback=240,
    )

    assert first != second
    assert "::data_version=1700000001000000000:" in second


def test_duckdb_backed_cache_keys_include_data_version() -> None:
    route_support = load_module(
        "backend.app.services.market_data_livermore_route_support",
        "backend/app/services/market_data_livermore_route_support.py",
    )
    cache_key_functions = [
        (name, function)
        for name, function in inspect.getmembers(route_support, inspect.isfunction)
        if function.__module__ == route_support.__name__
        and name.endswith("_cache_key")
        and "duckdb_path" in inspect.signature(function).parameters
    ]

    assert len(cache_key_functions) >= 6, [name for name, _function in cache_key_functions]

    for name, function in cache_key_functions:
        kwargs: dict[str, object] = {}
        for parameter in inspect.signature(function).parameters.values():
            if parameter.default is not inspect.Parameter.empty:
                kwargs[parameter.name] = parameter.default
            elif parameter.name == "catalog_file":
                kwargs[parameter.name] = "choice-stock.json"
            elif "None" in str(parameter.annotation):
                kwargs[parameter.name] = None
            elif str(parameter.annotation) in {"int", "<class 'int'>"}:
                kwargs[parameter.name] = 1
            else:
                kwargs[parameter.name] = "x"

        assert "::data_version=" in function(**kwargs), name


def test_stock_analysis_workbench_envelope_versions_replay_closure_contract_v2() -> None:
    module = load_module(
        "backend.app.services.stock_analysis_workbench_service",
        "backend/app/services/stock_analysis_workbench_service.py",
    )

    strategy_envelope = _strategy_envelope()
    envelope = module.build_stock_analysis_workbench_envelope(
        strategy_envelope=strategy_envelope,
        pretrade_qualification=_ready_pretrade_qualification(module, strategy_envelope),
        requested_as_of_date="2026-06-26",
    )

    assert envelope["result_meta"]["rule_version"] == "rv_stock_analysis_workbench_v2"
    assert envelope["result_meta"]["cache_version"] == "cv_stock_analysis_workbench_v2"
    assert "replay_closure" in envelope["result"]


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
    from importlib import import_module

    route_module = load_module(
        "backend.app.api.routes.market_data_livermore",
        "backend/app/api/routes/market_data_livermore.py",
    )
    service_module = import_module("backend.app.services.market_data_livermore_service")
    monkeypatch.setattr(service_module, "livermore_data_version", lambda _path: "db-v1")
    monkeypatch.setattr(service_module, "livermore_business_inputs_version", lambda: "inputs-v1")
    common = {
        "duckdb_path": "fixture.duckdb",
        "catalog_file": "choice-stock.json",
        "as_of_date": "2026-07-16",
    }

    first = route_module._livermore_signal_confluence_cache_key(**common)
    monkeypatch.setattr(service_module, "livermore_business_inputs_version", lambda: "inputs-v2")
    second = route_module._livermore_signal_confluence_cache_key(**common)

    assert first != second
    assert "::business_inputs=inputs-v2" in second


def test_stock_analysis_workbench_cache_key_normalizes_default_include(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from importlib import import_module

    route_module = load_module(
        "backend.app.api.routes.market_data_livermore",
        "backend/app/api/routes/market_data_livermore.py",
    )
    catalog = tmp_path / "choice-stock.json"
    catalog.write_text("{}", encoding="utf-8")
    service_module = import_module("backend.app.services.market_data_livermore_service")
    monkeypatch.setattr(service_module, "livermore_data_version", lambda _path: "db-v1")

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
                "rule_version": "rv_stock_kline_analysis_observation_v2",
                "cache_version": "cv_stock_kline_analysis_observation_v2",
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
