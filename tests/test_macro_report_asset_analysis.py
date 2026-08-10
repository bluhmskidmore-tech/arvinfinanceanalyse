from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import backend.app.api.routes.macro_toolkit as macro_toolkit_route
from backend.app.services import macro_report_asset_service


def test_macro_toolkit_analysis_includes_fail_closed_report_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "output"
    expected_report_bundle = {
        "status": "ready",
        "reason": None,
        "basis": "analytical",
        "observation_only": True,
        "formal_use_allowed": False,
        "artifacts": [],
        "warnings": ["fixture"],
    }
    monkeypatch.setattr(macro_toolkit_route, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(
        macro_toolkit_route,
        "get_settings",
        lambda: SimpleNamespace(duckdb_path=tmp_path / "moss.duckdb", governance_path=tmp_path / "governance.db"),
    )
    monkeypatch.setattr(macro_toolkit_route, "_analysis_indicators", lambda _path: [])
    monkeypatch.setattr(macro_toolkit_route, "_output_files", lambda: [])
    monkeypatch.setattr(macro_toolkit_route, "_latest_indicator_date", lambda _items: "2026-07-20")
    monkeypatch.setattr(
        macro_toolkit_route.macro_toolkit_service,
        "macro_model_readiness",
        lambda **_kwargs: {"model_readiness": [], "readiness_summary": {}},
    )
    monkeypatch.setattr(macro_toolkit_route, "_analysis_runtime_status", lambda detail: {"analysis_scope": detail})
    monkeypatch.setattr(macro_toolkit_route, "_analysis_signal_cards", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(macro_toolkit_route, "_hason_macro_strategy_summary", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(macro_toolkit_route, "_analysis_conclusion", lambda *_args: {})
    monkeypatch.setattr(macro_toolkit_route, "_analysis_warnings", lambda *_args: [])
    monkeypatch.setattr(macro_toolkit_route, "_analysis_data_health", lambda **_kwargs: {})
    monkeypatch.setattr(macro_toolkit_route, "_cffex_member_rank_status", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(macro_toolkit_route, "_choice_stock_refresh_overview", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        macro_toolkit_route,
        "_envelope",
        lambda _result_kind, result, **_kwargs: result,
    )
    monkeypatch.setattr(
        macro_report_asset_service,
        "load_report_bundle",
        lambda bundle_dir: expected_report_bundle
        if bundle_dir == output_dir / macro_report_asset_service.BUNDLE_DIRNAME
        else pytest.fail(f"unexpected report bundle directory: {bundle_dir}"),
    )

    result = macro_toolkit_route._build_macro_toolkit_analysis("core")

    assert result["report_bundle"] == expected_report_bundle


def test_core_and_full_analysis_share_conclusion_without_hiding_full_signal_cards(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    indicators = [{"key": "dr007", "latest_value": 1.8}]
    output_files = [{"name": "final_signal.csv", "modified_at": "2026-07-20T08:00:00+00:00"}]
    full_block_calls: list[str] = []

    def build_full_blocks(*_args, **_kwargs):
        full_block_calls.append("full")
        return (
            {
                "status": "available",
                "risk_level": "red",
                "risk_name": "high",
                "risk_score": 90,
                "triggered_rules": ["fixture"],
            },
            [
                {
                    "key": "crisis_score_cn",
                    "score": 80,
                    "tone": "negative",
                    "headline": "stress",
                    "result": {"regime": "stress"},
                    "evidence": ["fixture"],
                    "warnings": [],
                }
            ],
            [],
        )

    monkeypatch.setattr(macro_toolkit_route, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(
        macro_toolkit_route,
        "get_settings",
        lambda: SimpleNamespace(duckdb_path=tmp_path / "moss.duckdb", governance_path=tmp_path / "governance.db"),
    )
    monkeypatch.setattr(macro_toolkit_route, "_analysis_indicators", lambda _path: indicators)
    monkeypatch.setattr(macro_toolkit_route, "_output_files", lambda: output_files)
    monkeypatch.setattr(macro_toolkit_route, "_latest_indicator_date", lambda _items: "2026-07-20")
    monkeypatch.setattr(
        macro_toolkit_route.macro_toolkit_service,
        "macro_model_readiness",
        lambda **_kwargs: {"model_readiness": [], "readiness_summary": {}},
    )
    monkeypatch.setattr(
        macro_toolkit_route.macro_report_asset_service,
        "load_report_bundle",
        lambda _bundle_dir: {},
    )
    monkeypatch.setattr(macro_toolkit_route, "_build_macro_toolkit_full_analysis_blocks", build_full_blocks)
    monkeypatch.setattr(macro_toolkit_route, "_source_checks_for_aliases", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(macro_toolkit_route, "_source_checks", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(macro_toolkit_route, "_capability_plan", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(macro_toolkit_route, "_analysis_runtime_status", lambda detail: {"analysis_scope": detail})
    monkeypatch.setattr(macro_toolkit_route, "_hason_macro_strategy_summary", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(macro_toolkit_route, "_analysis_data_health", lambda **_kwargs: {})
    monkeypatch.setattr(macro_toolkit_route, "_cffex_member_rank_status", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(macro_toolkit_route, "_choice_stock_refresh_overview", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(macro_toolkit_route, "_envelope", lambda _result_kind, result, **_kwargs: result)

    core = macro_toolkit_route._build_macro_toolkit_analysis("core")
    assert full_block_calls == []

    full = macro_toolkit_route._build_macro_toolkit_analysis("full")
    core_cards = {str(card["key"]): card for card in core["signal_cards"]}
    full_cards = {str(card["key"]): card for card in full["signal_cards"]}

    assert full_block_calls == ["full"]
    assert core_cards["crisis_score_cn"]["tone"] == "neutral"
    assert full_cards["crisis_score_cn"]["tone"] == "negative"
    assert core_cards["a_share_stampede_risk"]["tone"] == "missing"
    assert full_cards["a_share_stampede_risk"]["tone"] == "negative"
    assert core["conclusion"]["tone"] == "positive"
    assert full["conclusion"] == core["conclusion"]
    basis = full["conclusion"]["basis"]
    basis_cards = {str(card["key"]): card for card in basis["signal_cards"]}
    assert basis["source"] == "core_signal_cards"
    assert basis_cards["crisis_score_cn"]["tone"] == "neutral"
    assert basis_cards["a_share_stampede_risk"]["tone"] == "missing"
