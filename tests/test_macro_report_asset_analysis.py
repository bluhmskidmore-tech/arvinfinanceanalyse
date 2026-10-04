from __future__ import annotations

from backend.app.services import macro_toolkit_analysis_service as macro_toolkit_analysis
from backend.app.services import macro_toolkit_route_support as macro_toolkit_support

from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

import backend.app.api.routes.macro_toolkit as macro_toolkit_route
from backend.app.schemas.macro_toolkit import (
    MacroToolkitAnalysisEnvelope,
    MacroToolkitScriptsEnvelope,
    MacroToolkitStrategySummariesEnvelope,
)
from backend.app.services import macro_report_asset_service, macro_toolkit_read_service
from backend.app.services.macro_toolkit_refresh_receipt_service import (
    MacroToolkitRefreshReceiptHealth,
)


@pytest.mark.excluded_surface_regression
@pytest.mark.surface_macro_toolkit
def test_macro_toolkit_read_service_builds_without_route_initialization(
    tmp_path: Path,
) -> None:
    code = '''
import builtins
import platform
import socket
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
import duckdb
platform.uname()  # Resolve Windows metadata before blocking application subprocesses.

def forbidden(*args, **kwargs):
    raise AssertionError("isolated read builders must not open a database, network or subprocess")

duckdb.connect = forbidden
socket.socket.connect = forbidden
subprocess.Popen.__init__ = forbidden
original_import = builtins.__import__
def import_without_http(name, *args, **kwargs):
    if name.startswith("backend.app.api") or name == "backend.app.main":
        raise AssertionError("read builders must not import HTTP composition")
    return original_import(name, *args, **kwargs)
builtins.__import__ = import_without_http

from backend.app.services import macro_toolkit_read_service as reads
from backend.app.services import macro_toolkit_route_support as support
from backend.app.services import macro_toolkit_service

root = Path(sys.argv[1])
reads.get_settings = lambda: SimpleNamespace(duckdb_path=root / "unused.duckdb", governance_path=root / "governance")
support.OUTPUT_DIR = root / "output"
support._analysis_indicators = lambda path: [{"key": "dr007", "latest_value": 1.8, "latest_date": "2026-07-20"}]
support._cffex_member_rank_status = lambda *args, **kwargs: {}
support._choice_stock_refresh_overview = lambda *args, **kwargs: {}
support.iter_toolkit_scripts = lambda: []
support._equity_strategy_summaries_with_context = lambda path: ([], None)
support.compute_equity_shadow_portfolio_report = lambda *args, **kwargs: {}
support._macro_etf_strategy_snapshot_for_toolkit = lambda **kwargs: {}
macro_toolkit_service.macro_model_readiness = lambda **kwargs: {"model_readiness": [], "readiness_summary": {}}

analysis = reads.build_macro_toolkit_analysis("core")
strategies = reads.build_macro_toolkit_strategy_summaries()
assert analysis["result"]["indicators"][0]["latest_value"] == 1.8
assert analysis["result"]["runtime_status"]["analysis_scope"] == "core"
assert strategies["result"]["strategy_summaries"] == []
assert not any(name.startswith("backend.app.api") for name in sys.modules)
'''
    completed = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


@pytest.mark.excluded_surface_regression
@pytest.mark.surface_macro_toolkit
def test_macro_toolkit_read_service_preserves_analysis_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    health = MacroToolkitRefreshReceiptHealth(
        status="ready",
        ready=True,
        cache_fingerprint="ready:service-entry",
        generated_at="2026-08-09T10:30:00+00:00",
        run_status="success",
        source_version="macro_toolkit_freshness_refresh_v3",
        missing_fields=(),
        warnings=(),
        latest_observation_dates={},
    )
    captured: dict[str, object] = {}

    def analysis_builder(detail: str, **kwargs: object) -> dict[str, object]:
        captured["detail"] = detail
        captured.update(kwargs)
        return {"result_kind": "macro_toolkit.analysis"}

    monkeypatch.setattr(
        macro_toolkit_read_service,
        "get_settings",
        lambda: SimpleNamespace(duckdb_path="unused.duckdb", governance_path="unused-governance"),
    )
    monkeypatch.setattr(macro_toolkit_read_service, "build_macro_toolkit_analysis_payload", analysis_builder)

    assert macro_toolkit_read_service.build_macro_toolkit_analysis(
        "full",
        history_limit=17,
        refresh_receipt_health=health,
    ) == {"result_kind": "macro_toolkit.analysis"}
    assert captured["detail"] == "full"
    assert captured["history_limit"] == 17
    assert captured["refresh_receipt_health"] is health


@pytest.mark.excluded_surface_regression
@pytest.mark.surface_macro_toolkit
def test_macro_toolkit_read_service_builds_analysis_coverage() -> None:
    coverage = macro_toolkit_read_service.build_macro_toolkit_analysis_coverage(
        indicators=[
            {"latest_value": 1.8},
            {"latest_value": None},
            {"latest_value": 102.4},
        ],
        output_files=[{"name": "signal.csv"}, {"name": "risk.csv"}],
        script_count=7,
    )

    assert coverage == {
        "indicator_count": 3,
        "hit_count": 2,
        "hit_rate": 0.6667,
        "script_count": 7,
        "output_file_count": 2,
    }


@pytest.mark.excluded_surface_regression
@pytest.mark.surface_macro_toolkit
def test_macro_toolkit_primary_routes_declare_response_models() -> None:
    response_models = {
        route.path: route.response_model
        for route in macro_toolkit_route.router.routes
    }

    assert response_models["/ui/macro/toolkit/scripts"] is MacroToolkitScriptsEnvelope
    assert response_models["/ui/macro/toolkit/analysis"] is MacroToolkitAnalysisEnvelope
    assert (
        response_models["/ui/macro/toolkit/analysis/strategy-summaries"]
        is MacroToolkitStrategySummariesEnvelope
    )


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
    monkeypatch.setattr(macro_toolkit_support, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(
        macro_toolkit_read_service,
        "get_settings",
        lambda: SimpleNamespace(duckdb_path=tmp_path / "moss.duckdb", governance_path=tmp_path / "governance.db"),
    )
    monkeypatch.setattr(macro_toolkit_support, "_analysis_indicators", lambda _path: [])
    monkeypatch.setattr(macro_toolkit_support, "_output_files", lambda: [])
    monkeypatch.setattr(macro_toolkit_route, "_output_files", lambda: [])
    monkeypatch.setattr(macro_toolkit_support, "_latest_indicator_date", lambda _items: "2026-07-20")
    monkeypatch.setattr(
        macro_toolkit_route.macro_toolkit_service,
        "macro_model_readiness",
        lambda **_kwargs: {"model_readiness": [], "readiness_summary": {}},
    )
    monkeypatch.setattr(macro_toolkit_support, "_analysis_runtime_status", lambda detail: {"analysis_scope": detail})
    monkeypatch.setattr(macro_toolkit_support, "_analysis_signal_cards", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(macro_toolkit_support, "_hason_macro_strategy_summary", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(macro_toolkit_support, "_analysis_conclusion", lambda *_args: {})
    monkeypatch.setattr(macro_toolkit_support, "_analysis_warnings", lambda *_args: [])
    monkeypatch.setattr(macro_toolkit_analysis, "_analysis_data_health", lambda **_kwargs: {})
    monkeypatch.setattr(macro_toolkit_support, "_cffex_member_rank_status", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(macro_toolkit_route, "_cffex_member_rank_status", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(macro_toolkit_support, "_choice_stock_refresh_overview", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(macro_toolkit_route, "_choice_stock_refresh_overview", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        macro_toolkit_support,
        "_envelope",
        lambda _result_kind, result, **_kwargs: result,
    )
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

    result = macro_toolkit_read_service.build_macro_toolkit_analysis("core")

    assert result["report_bundle"] == expected_report_bundle


def test_analysis_route_uses_one_receipt_snapshot_for_cache_key_and_builder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    health = MacroToolkitRefreshReceiptHealth(
        status="ready",
        ready=True,
        cache_fingerprint="ready:fixture",
        generated_at="2026-08-09T10:30:00+00:00",
        run_status="success",
        source_version="macro_toolkit_freshness_refresh_v3",
        missing_fields=(),
        warnings=(),
        latest_observation_dates={"CA.CSI300": "2026-08-08"},
    )
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        macro_toolkit_route,
        "get_settings",
        lambda: SimpleNamespace(
            duckdb_path=tmp_path / "moss.duckdb",
            governance_path=tmp_path / "governance.db",
        ),
    )
    monkeypatch.setattr(
        macro_toolkit_route,
        "_ensure_macro_toolkit_read_allowed",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        macro_toolkit_route.macro_toolkit_refresh_receipt_service,
        "load_macro_toolkit_refresh_receipt_health",
        lambda: health,
    )

    def fake_build(detail: str, **kwargs: object) -> dict[str, object]:
        captured["detail"] = detail
        captured.update(kwargs)
        return {"result_kind": "macro_toolkit.analysis"}

    def fake_get_or_build(key: str, builder) -> dict[str, object]:
        captured["cache_key"] = key
        return builder()

    monkeypatch.setattr(macro_toolkit_read_service, "build_macro_toolkit_analysis", fake_build)
    monkeypatch.setattr(
        macro_toolkit_route.market_home_response_cache,
        "get_or_build",
        fake_get_or_build,
    )

    result = macro_toolkit_route.macro_toolkit_analysis(
        object(),
        detail="core",
        history_limit=None,
    )

    assert result == {"result_kind": "macro_toolkit.analysis"}
    assert "ready:fixture" in str(captured["cache_key"])
    assert captured["detail"] == "core"
    assert captured["refresh_receipt_health"] is health


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

    monkeypatch.setattr(macro_toolkit_support, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(
        macro_toolkit_read_service,
        "get_settings",
        lambda: SimpleNamespace(duckdb_path=tmp_path / "moss.duckdb", governance_path=tmp_path / "governance.db"),
    )
    monkeypatch.setattr(macro_toolkit_support, "_analysis_indicators", lambda _path: indicators)
    monkeypatch.setattr(macro_toolkit_support, "_output_files", lambda: output_files)
    monkeypatch.setattr(macro_toolkit_route, "_output_files", lambda: output_files)
    monkeypatch.setattr(macro_toolkit_support, "_latest_indicator_date", lambda _items: "2026-07-20")
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
    monkeypatch.setattr(macro_toolkit_read_service, "_build_macro_toolkit_full_analysis_blocks", build_full_blocks)
    monkeypatch.setattr(macro_toolkit_support, "_source_checks_for_aliases", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(macro_toolkit_support, "_source_checks", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(macro_toolkit_route, "_source_checks", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(macro_toolkit_support, "_capability_plan", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(macro_toolkit_route, "_capability_plan", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(macro_toolkit_support, "_analysis_runtime_status", lambda detail: {"analysis_scope": detail})
    monkeypatch.setattr(macro_toolkit_support, "_hason_macro_strategy_summary", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(macro_toolkit_analysis, "_analysis_data_health", lambda **_kwargs: {})
    monkeypatch.setattr(macro_toolkit_support, "_cffex_member_rank_status", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(macro_toolkit_route, "_cffex_member_rank_status", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(macro_toolkit_support, "_choice_stock_refresh_overview", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(macro_toolkit_route, "_choice_stock_refresh_overview", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(macro_toolkit_support, "_envelope", lambda _result_kind, result, **_kwargs: result)
    monkeypatch.setattr(macro_toolkit_route, "_envelope", lambda _result_kind, result, **_kwargs: result)

    core = macro_toolkit_read_service.build_macro_toolkit_analysis("core")
    assert full_block_calls == []

    full = macro_toolkit_read_service.build_macro_toolkit_analysis("full")
    core_cards = {str(card["key"]): card for card in core["signal_cards"]}
    full_cards = {str(card["key"]): card for card in full["signal_cards"]}

    assert full_block_calls == ["full"]
    assert core_cards["crisis_score_cn"]["tone"] == "neutral"
    assert full_cards["crisis_score_cn"]["tone"] == "negative"
    assert core_cards["a_share_stampede_risk"]["tone"] == "missing"
    assert full_cards["a_share_stampede_risk"]["tone"] == "negative"
    assert core["conclusion"]["tone"] == "missing"
    assert core["conclusion"]["stance"] == "暂不判断"
    assert full["conclusion"] == core["conclusion"]
    basis = full["conclusion"]["basis"]
    basis_cards = {str(card["key"]): card for card in basis["signal_cards"]}
    assert basis["source"] == "core_signal_cards"
    assert basis_cards == {"liquidity": {"key": "liquidity", "tone": "positive"}}
    assert basis["directional_coverage"] == {
        "expected_count": 3,
        "valid_count": 1,
        "missing_keys": ["credit", "risk_appetite"],
        "status": "insufficient",
    }
    assert "outputs" in core_cards and "outputs" in full_cards

    blocked_health = MacroToolkitRefreshReceiptHealth(
        status="blocked",
        ready=False,
        cache_fingerprint="blocked:fixture",
        generated_at="2026-08-09T10:30:00+00:00",
        run_status="failed",
        source_version="macro_toolkit_freshness_refresh_v3",
        missing_fields=("receipt.status",),
        warnings=(),
        latest_observation_dates={},
    )
    blocked = macro_toolkit_read_service.build_macro_toolkit_analysis(
        "core",
        refresh_receipt_health=blocked_health,
    )

    assert blocked["signal_cards"] == core["signal_cards"]
    assert blocked["indicators"] == core["indicators"]
    assert blocked["conclusion"]["tone"] == "missing"
    assert blocked["conclusion"]["stance"] == "数据不足"
    assert blocked["primary_signal"]["selection_status"] == "blocked"
    assert blocked["primary_signal"]["key"] is None
    assert blocked["conclusion"]["basis"]["refresh_receipt"]["ready"] is False
    assert blocked["data_health"]["refresh_receipt"]["status"] == "blocked"
    assert any("方向性结论已关闭" in warning for warning in blocked["warnings"])
