from __future__ import annotations

from pathlib import Path

from tests.helpers import ROOT, load_module


def test_adb_api_route_keeps_calculation_outside_api_layer() -> None:
    route_source = (ROOT / "backend/app/api/routes/adb_analysis.py").read_text(encoding="utf-8")

    assert "adb_analysis_service.adb_comparison_envelope" in route_source
    assert "calculate_adb" not in route_source
    assert "get_adb_comparison" not in route_source
    assert "duckdb" not in route_source.lower()
    assert "backend.app.core_finance.adb_analysis" not in route_source
    assert "backend.app.repositories.adb_repo" not in route_source


def test_adb_service_source_declares_repo_and_core_finance_seams() -> None:
    service_source = (ROOT / "backend/app/services/adb_analysis_service.py").read_text(encoding="utf-8")

    assert "backend.app.repositories.adb_repo" in service_source
    assert "backend.app.core_finance.adb_analysis" in service_source
    assert "_load_adb_raw_data(" not in service_source
    assert service_source.count("def calculate_adb(") == 1


def test_adb_service_comparison_delegates_repository_and_core_finance(monkeypatch) -> None:
    service_mod = load_module(
        "backend.app.services.adb_analysis_service",
        "backend/app/services/adb_analysis_service.py",
    )

    calls: list[tuple[str, object]] = []

    class FakeRepo:
        def __init__(self, duckdb_path: str) -> None:
            calls.append(("repo_init", duckdb_path))

        def load_raw_data(self, start_date, end_date):
            calls.append(("load_raw_data", (start_date, end_date)))
            return [], [], ["sv-adb"], ["rv-adb"]

    def fake_build_adb_comparison_payload(**kwargs):
        calls.append(("build_adb_comparison_payload", kwargs))
        return {
            "report_date": "2025-06-03",
            "start_date": "2025-06-03",
            "end_date": "2025-06-03",
            "num_days": 1,
            "simulated": True,
            "detail": "Average balances are simulated from a single snapshot; treat deltas as indicative only.",
            "total_spot_assets": 0.0,
            "total_avg_assets": 0.0,
            "total_spot_liabilities": 0.0,
            "total_avg_liabilities": 0.0,
            "asset_yield": None,
            "liability_cost": None,
            "net_interest_margin": None,
            "assets_breakdown": [],
            "liabilities_breakdown": [],
        }

    monkeypatch.setattr(service_mod, "AdbRepository", FakeRepo)
    monkeypatch.setattr(service_mod, "build_adb_comparison_payload", fake_build_adb_comparison_payload)

    payload = service_mod.adb_comparison_envelope("2025-06-03", "2025-06-03", top_n=5)

    assert payload["result"]["report_date"] == "2025-06-03"
    assert payload["result_meta"]["quality_flag"] == "warning"
    assert [name for name, _value in calls] == [
        "repo_init",
        "load_raw_data",
        "build_adb_comparison_payload",
    ]
