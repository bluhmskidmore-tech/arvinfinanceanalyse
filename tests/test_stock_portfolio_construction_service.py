from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.app.api.routes import market_data_livermore as route_module
from backend.app.services import stock_analysis_workbench_service as workbench_service
from backend.app.services import stock_portfolio_construction_service as service


pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_livermore,
]


def _workbench_envelope(*, closure_status: str = "ready") -> dict[str, object]:
    ready = closure_status == "ready"
    return {
        "result_meta": {
            "basis": "analytical",
            "source_version": "sv_workbench_test",
            "vendor_version": "vv_test",
            "rule_version": "rv_workbench_test",
            "cache_version": "cv_workbench_test",
            "quality_flag": "ok",
            "vendor_status": "ok",
            "fallback_mode": "none",
            "as_of_date": "2026-08-24",
            "tables_used": ["choice_stock_daily_observation"],
            "evidence_rows": 1,
        },
        "result": {
            "page_id": "GAP-STOCK-ANALYSIS-PAGE",
            "route": "/stock-analysis",
            "as_of_date": "2026-08-24",
            "replay_closure": {
                "status": closure_status,
                "selection_status": "unique_active_certified" if ready else "no_active_certified",
                "data_availability": "fresh" if ready else "unsupported",
                "primary_blocker_code": None if ready else "controlled_schema_unavailable",
                "reason_codes": ["current_rule_cohort_ready"]
                if ready
                else ["controlled_schema_unavailable"],
                "evaluation_as_of_date": "2026-08-24",
                "cohort_id": "cohort-test" if ready else None,
                "versions": {},
                "sources": {},
            },
            "modules": {
                "main": {
                    "status": "ready",
                    "result": {
                        "as_of_date": "2026-08-24",
                        "stock_candidates": {
                            "items": [
                                {
                                    "stock_code": "000001.SZ",
                                    "stock_name": "测试股",
                                    "sector_name": "银行",
                                    "rank": 1,
                                    "selection_close": 10.0,
                                    "score": 0.8,
                                    "signal_kind": "stock_candidate",
                                }
                            ],
                            "position_size_hint": {
                                "items": [
                                    {
                                        "stock_code": "000001.SZ",
                                        "equal_weight": 0.25,
                                        "raw_weight": 0.2,
                                        "stop_distance_pct": 0.1,
                                        "stop_basis": "ema10_stop_ref",
                                        "capped": False,
                                    }
                                ]
                            },
                        },
                    },
                }
            },
        },
    }


def test_ready_source_exposes_preview_target_and_calls_risk_with_explicit_lines() -> None:
    calls: list[list[dict[str, object]]] = []

    def fake_risk_builder(target_lines: list[dict[str, object]]) -> dict[str, object]:
        calls.append(target_lines)
        return {
            "data_status": "complete",
            "reason_codes": [],
            "target_weight_sum_ratio": Decimal("0.25"),
            "hhi_ratio": Decimal("1"),
            "limit_gate": {
                "status": "blocked_missing_approved_policy",
                "reason_code": "missing_approved_policy",
                "approved_policy_present": False,
            },
            "observation_only": True,
            "formal_use_allowed": False,
        }

    envelope = service.stock_portfolio_construction_envelope(
        portfolio_id="SHADOW-STOCK-RESEARCH",
        workbench_envelope=_workbench_envelope(),
        risk_builder=fake_risk_builder,
    )

    result = envelope["result"]
    assert result["page_id"] == "GAP-STOCK-ANALYSIS-PORTFOLIO"
    assert result["route"] == "/stock-analysis/portfolio"
    assert result["basis"] == "analytical"
    assert result["contract_status"] == "proposal_only"
    assert result["formal_use_allowed"] is False
    assert result["trading_instruction_allowed"] is False
    assert result["execution_approval_allowed"] is False
    assert result["source_gate"]["source"] == "replay_closure"
    assert result["source_gate"]["status"] == "ready"
    assert result["target"]["status"] == "reference_preview"
    assert result["target"]["items"][0]["status"] == "reference_preview"
    assert result["target"]["items"][0]["target_weight"] == 0.25
    assert result["rebalance"]["status"] == "blocked_missing_scoped_positions"
    assert result["rebalance"]["current_positions"] == []
    assert result["rebalance"]["legacy_position_snapshot_used"] is False
    assert calls == [
        [
            {
                "stock_code": "000001.SZ",
                "sector_name": "银行",
                "target_weight": 0.25,
            }
        ]
    ]
    assert result["risk_snapshot"]["measurement_basis"] == "reference_preview"


def test_blocked_source_keeps_reference_row_but_withholds_target_weight() -> None:
    calls: list[list[dict[str, object]]] = []

    def fake_risk_builder(target_lines: list[dict[str, object]]) -> dict[str, object]:
        calls.append(target_lines)
        return {"data_status": "complete", "reason_codes": []}

    envelope = service.stock_portfolio_construction_envelope(
        portfolio_id="SHADOW-STOCK-RESEARCH",
        workbench_envelope=_workbench_envelope(closure_status="insufficient"),
        risk_builder=fake_risk_builder,
    )

    result = envelope["result"]
    item = result["target"]["items"][0]
    assert result["source_gate"]["status"] == "blocked"
    assert result["source_gate"]["primary_blocker_code"] == "controlled_schema_unavailable"
    assert result["target"]["status"] == "blocked_source_gate"
    assert item["status"] == "reference_preview"
    assert item["reference_weight"] == 0.25
    assert item["target_weight"] is None
    assert item["target_block_reason"] == "controlled_schema_unavailable"
    assert result["rebalance"]["status"] == "blocked_missing_scoped_positions"
    assert calls[0][0]["target_weight"] == 0.25
    assert result["risk_snapshot"]["measurement_basis"] == "reference_preview"


def test_observation_queue_does_not_unlock_portfolio_when_pretrade_is_unavailable() -> None:
    strategy_result = {
        "as_of_date": "2026-08-24",
        "market_gate": {"state": "WARM"},
        "sector_rank": {"items": []},
        "stock_candidates": {
            "items": [
                {
                    "stock_code": "000001.SZ",
                    "stock_name": "测试股",
                    "sector_name": "银行",
                    "rank": 1,
                }
            ],
            "position_size_hint": {
                "items": [
                    {
                        "stock_code": "000001.SZ",
                        "equal_weight": 0.25,
                    }
                ]
            },
        },
        "risk_exit": {
            "items": [{"stock_code": "000001.SZ", "reason": "execution_only_exit_hint"}],
            "watch_items": [],
        },
        "rule_readiness": [
            {"key": key, "status": "ready", "missing_inputs": []}
            for key in ("market_gate", "sector_rank", "stock_pivot", "risk_exit")
        ],
        "data_gaps": [],
        "diagnostics": [],
        "supported_outputs": ["market_gate", "sector_rank", "stock_candidates", "risk_exit"],
        "unsupported_outputs": [],
    }
    strategy_envelope = {
        "result_meta": {
            "basis": "analytical",
            "source_version": "sv_workbench_test",
            "vendor_version": "vv_test",
            "rule_version": "rv_workbench_test",
            "cache_version": "cv_workbench_test",
            "quality_flag": "ok",
            "vendor_status": "ok",
            "fallback_mode": "none",
            "as_of_date": "2026-08-24",
            "tables_used": ["choice_stock_daily_observation"],
            "evidence_rows": 1,
        },
        "result": strategy_result,
    }
    workbench = workbench_service.build_stock_analysis_workbench_envelope(
        strategy_envelope=strategy_envelope,
        requested_as_of_date="2026-08-24",
        replay_closure={
            "status": "ready",
            "selection_status": "unique_active_certified",
            "data_availability": "fresh",
            "primary_blocker_code": None,
            "reason_codes": ["current_rule_cohort_ready"],
            "evaluation_as_of_date": "2026-08-24",
        },
        pretrade_qualification={
            "schema": "pretrade_qualification/v1",
            "status": "unavailable",
            "reason": "system_read_generation_missing",
        },
    )

    workbench_result = workbench["result"]
    assert workbench_result["decision_summary"]["can_review_candidates"] is True
    assert workbench_result["first_screen"]["review_queue"][0]["stock_code"] == "000001.SZ"
    assert "position_size_hint" not in workbench_result["first_screen"]["review_queue"][0]
    assert "stock_candidates" not in workbench_result["modules"]["main"]["result"]
    assert workbench_result["first_screen"]["risk_exit_snapshot"] == []

    portfolio = service.stock_portfolio_construction_envelope(
        portfolio_id="SHADOW-STOCK-RESEARCH",
        workbench_envelope=workbench,
    )["result"]

    assert portfolio["target"]["status"] == "blocked_no_candidates"
    assert portfolio["target"]["items"] == []
    assert portfolio["target"]["candidate_count"] == 0


def test_ready_source_with_failed_main_module_still_withholds_target_weight() -> None:
    calls: list[list[dict[str, object]]] = []

    def fake_risk_builder(target_lines: list[dict[str, object]]) -> dict[str, object]:
        calls.append(target_lines)
        return {"data_status": "complete", "reason_codes": []}

    workbench = _workbench_envelope()
    main_module = workbench["result"]["modules"]["main"]
    main_module["status"] = "error"

    envelope = service.stock_portfolio_construction_envelope(
        portfolio_id="SHADOW-STOCK-RESEARCH",
        workbench_envelope=workbench,
        risk_builder=fake_risk_builder,
    )

    result = envelope["result"]
    item = result["target"]["items"][0]
    assert result["source_gate"]["status"] == "ready"
    assert result["target"]["status"] == "blocked_main_module"
    assert result["target"]["block_reason"] == "blocked_main_module"
    assert item["reference_weight"] == 0.25
    assert item["target_weight"] is None
    assert item["target_block_reason"] == "blocked_main_module"
    assert calls[0][0]["target_weight"] == 0.25


def test_upstream_stale_metadata_is_preserved() -> None:
    workbench = _workbench_envelope()
    workbench["result_meta"].update(
        {
            "quality_flag": "stale",
            "vendor_status": "vendor_stale",
            "fallback_mode": "latest_snapshot",
        }
    )

    envelope = service.stock_portfolio_construction_envelope(
        portfolio_id="SHADOW-STOCK-RESEARCH",
        workbench_envelope=workbench,
        risk_builder=lambda _lines: {"data_status": "complete", "reason_codes": []},
    )

    assert envelope["result_meta"]["quality_flag"] == "stale"
    assert envelope["result_meta"]["vendor_status"] == "vendor_stale"
    assert envelope["result_meta"]["fallback_mode"] == "latest_snapshot"


def test_missing_sector_is_fail_closed_for_descriptive_risk() -> None:
    workbench = _workbench_envelope()
    candidate = workbench["result"]["modules"]["main"]["result"]["stock_candidates"]["items"][0]
    candidate.pop("sector_name")

    result = service.stock_portfolio_construction_envelope(
        portfolio_id="SHADOW-STOCK-RESEARCH",
        workbench_envelope=workbench,
    )["result"]

    risk_snapshot = result["risk_snapshot"]
    assert risk_snapshot["data_status"] == "unavailable"
    assert risk_snapshot["reason_codes"] == ["missing_sector_name"]
    assert risk_snapshot["sector_exposures"] is None


def test_unscoped_legacy_position_snapshot_is_not_used() -> None:
    workbench = _workbench_envelope()
    workbench["result"]["livermore_position_snapshot"] = {
        "items": [{"stock_code": "999999.SZ", "quantity": 100}],
    }

    result = service.stock_portfolio_construction_envelope(
        portfolio_id="SHADOW-STOCK-RESEARCH",
        workbench_envelope=workbench,
    )["result"]

    assert result["legacy_position_snapshot"]["used"] is False
    assert result["legacy_position_snapshot"]["status"] == "ignored_unscoped"
    assert result["rebalance"]["current_positions"] == []


@pytest.mark.parametrize("portfolio_id", ["LIVE-TEST", "SHADOW-", "SHADOW-OTHER"])
def test_portfolio_id_is_fixed_for_phase_2a(portfolio_id: str) -> None:
    with pytest.raises(ValueError, match="SHADOW-STOCK-RESEARCH"):
        service.stock_portfolio_construction_envelope(
            portfolio_id=portfolio_id,
            workbench_envelope=_workbench_envelope(),
        )


def test_as_of_date_is_validated() -> None:
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        service.stock_portfolio_construction_envelope(
            portfolio_id="SHADOW-STOCK-RESEARCH",
            workbench_envelope=_workbench_envelope(),
            as_of_date="2026-99-99",
        )


def test_route_reuses_cached_workbench_and_normalizes_portfolio_id(monkeypatch: pytest.MonkeyPatch) -> None:
    workbench = _workbench_envelope(closure_status="insufficient")
    cached_calls: list[dict[str, object]] = []
    envelope_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        route_module,
        "get_settings",
        lambda: SimpleNamespace(duckdb_path="fixture.duckdb", choice_stock_catalog_file="catalog.json"),
    )
    monkeypatch.setattr(route_module, "_ensure_livermore_read_allowed", lambda **_kwargs: None)

    def fake_cached(**kwargs: object) -> tuple[dict[str, object], str, float, float, float]:
        cached_calls.append(kwargs)
        return workbench, "hit", 0.0, 0.0, 0.0

    monkeypatch.setattr(route_module, "_cached_stock_analysis_workbench", fake_cached)

    def fake_envelope(**kwargs: object) -> dict[str, object]:
        envelope_calls.append(kwargs)
        return {"ok": True}

    monkeypatch.setattr(route_module, "stock_portfolio_construction_envelope", fake_envelope)

    output = route_module.stock_analysis_portfolio_construction(
        auth=object(),
        portfolio_id=" SHADOW-STOCK-RESEARCH ",
        as_of_date="2026-08-24",
    )

    assert output == {"ok": True}
    assert cached_calls == [
        {
            "settings": SimpleNamespace(duckdb_path="fixture.duckdb", choice_stock_catalog_file="catalog.json"),
            "as_of_date": "2026-08-24",
            "include": None,
            "sector_window_days": 20,
            "top_k": 10,
        }
    ]
    assert envelope_calls == [
        {
            "portfolio_id": "SHADOW-STOCK-RESEARCH",
            "workbench_envelope": workbench,
            "as_of_date": "2026-08-24",
        }
    ]


@pytest.mark.parametrize("portfolio_id", ["LIVE-TEST", "SHADOW-OTHER"])
def test_route_rejects_unsupported_portfolio_id(
    monkeypatch: pytest.MonkeyPatch,
    portfolio_id: str,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        route_module.stock_analysis_portfolio_construction(
            auth=object(),
            portfolio_id=portfolio_id,
            as_of_date=None,
        )

    assert exc_info.value.status_code == 422
