from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.services.advanced_attribution_service import ADVANCED_ATTRIBUTION_RESULT_KIND
from tests.helpers import load_module


def test_advanced_attribution_rejects_invalid_report_date_with_422():
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    invalid_dates = (
        "not-a-date",
        "2025/12/31",
        "2025-13-01",
        "2025-02-30",
        "",
    )
    for bad in invalid_dates:
        response = client.get(
            "/ui/balance-analysis/advanced-attribution",
            params={"report_date": bad},
        )
        assert response.status_code == 422, f"expected 422 for report_date={bad!r}"
        detail = response.json().get("detail")
        assert detail is not None


def test_advanced_attribution_accepts_stripped_valid_report_date():
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get(
        "/ui/balance-analysis/advanced-attribution",
        params={"report_date": " 2025-12-31 "},
    )
    assert response.status_code == 200
    assert response.json()["result"]["report_date"] == "2025-12-31"


def test_advanced_attribution_endpoint_returns_analytical_not_ready_contract():
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get(
        "/ui/balance-analysis/advanced-attribution",
        params={"report_date": "2025-12-31"},
    )
    assert response.status_code == 200
    body = response.json()
    meta = body["result_meta"]
    assert meta["basis"] == "analytical"
    assert meta["formal_use_allowed"] is False
    assert meta["scenario_flag"] is False
    assert meta["result_kind"] == ADVANCED_ATTRIBUTION_RESULT_KIND

    result = body["result"]
    assert result["report_date"] == "2025-12-31"
    assert result["status"] == "not_ready"
    assert isinstance(result["missing_inputs"], list)
    assert len(result["missing_inputs"]) >= 1
    assert isinstance(result["blocked_components"], list)
    assert len(result["blocked_components"]) >= 1
    assert isinstance(result["warnings"], list)
    assert len(result["warnings"]) >= 1
    # No fake attribution figures
    assert "attribution" not in result
    assert "explained_pnl" not in result


def test_advanced_attribution_endpoint_switches_to_scenario_contract_when_explicit_shocks_are_given():
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get(
        "/ui/balance-analysis/advanced-attribution",
        params={
            "report_date": "2025-12-31",
            "treasury_shift_bp": 25,
            "scenario_name": "parallel_up_25bp",
        },
    )

    assert response.status_code == 200
    body = response.json()
    meta = body["result_meta"]
    assert meta["basis"] == "scenario"
    assert meta["formal_use_allowed"] is False
    assert meta["scenario_flag"] is True

    result = body["result"]
    assert result["report_date"] == "2025-12-31"
    assert result["status"] == "not_ready"
    assert result["mode"] == "scenario"
    assert result["scenario_name"] == "parallel_up_25bp"
    assert result["scenario_inputs"]["treasury_shift_bp"] == 25
    assert "roll_down" not in result
    assert "explained_pnl" not in result


def test_advanced_attribution_meta_basis_is_never_formal():
    from backend.app.services.advanced_attribution_service import advanced_attribution_bundle_envelope

    env = advanced_attribution_bundle_envelope(report_date="2025-06-30")
    assert env["result_meta"]["basis"] == "analytical"
    assert env["result_meta"]["basis"] != "formal"


def test_advanced_attribution_meta_can_be_scenario_but_never_formal():
    from backend.app.services.advanced_attribution_service import advanced_attribution_bundle_envelope

    env = advanced_attribution_bundle_envelope(
        report_date="2025-06-30",
        scenario_name="parallel_up_25bp",
        treasury_shift_bp=25,
    )
    assert env["result_meta"]["basis"] == "scenario"
    assert env["result_meta"]["basis"] != "formal"
    assert env["result_meta"]["scenario_flag"] is True


def test_advanced_attribution_analytical_mode_can_expose_upstream_summaries_without_claiming_completion(monkeypatch):
    service_mod = load_module(
        "backend.app.services.advanced_attribution_service",
        "backend/app/services/advanced_attribution_service.py",
    )

    monkeypatch.setattr(
        service_mod,
        "get_return_decomposition",
        lambda report_date, period_type, asset_class, accounting_class: {
            "result": {
                "carry": "10.00000000",
                "roll_down": "2.00000000",
                "rate_effect": "-1.00000000",
                "spread_effect": "0.50000000",
                "explained_pnl": "11.50000000",
                "warnings": ["curve-backed analytical summary"],
            }
        },
    )
    monkeypatch.setattr(
        service_mod,
        "pnl_bridge_envelope",
        lambda **kwargs: {
            "result": {
                "summary": {
                    "total_carry": "9.00000000",
                    "total_roll_down": "1.50000000",
                    "total_treasury_curve": "-0.50000000",
                    "total_credit_spread": "0.00000000",
                    "total_explained_pnl": "10.00000000",
                    "total_actual_pnl": "10.20000000",
                    "total_residual": "0.20000000",
                    "quality_flag": "warning",
                },
                "warnings": ["bridge-backed analytical summary"],
            }
        },
    )

    env = service_mod.advanced_attribution_bundle_envelope(
        report_date="2025-12-31",
        duckdb_path="test.duckdb",
        governance_dir="test-governance",
    )

    assert env["result_meta"]["basis"] == "analytical"
    assert env["result_meta"]["scenario_flag"] is False
    result = env["result"]
    assert result["status"] == "not_ready"
    assert result["mode"] == "analytical"
    assert result["upstream_summaries"]["return_decomposition"]["explained_pnl"] == "11.50000000"
    assert result["upstream_summaries"]["pnl_bridge"]["total_residual"] == "0.20000000"
    assert "explained_pnl" not in result
    assert "actual_pnl" not in result


def test_governed_workbook_tables_exclude_advanced_attribution_bundle(tmp_path, monkeypatch):
    """Regression: advanced_attribution_bundle must not appear in workbook table keys."""
    from backend.app.governance.settings import get_settings

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    from tests.test_balance_analysis_workbook_contract import _seed_workbook_snapshot_and_fx_tables

    _seed_workbook_snapshot_and_fx_tables(str(duckdb_path))

    task_mod = load_module(
        "backend.app.tasks.balance_analysis_materialize",
        "backend/app/tasks/balance_analysis_materialize.py",
    )
    # Seed already inserts fx_daily_mid; avoid live Choice/AkShare in CI/local without credentials.
    monkeypatch.setattr(task_mod.materialize_fx_mid_for_report_date, "fn", lambda **kwargs: None)
    task_mod.materialize_balance_analysis_facts.fn(
        report_date="2025-12-31",
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    wb = client.get(
        "/ui/balance-analysis/workbook",
        params={"report_date": "2025-12-31", "position_scope": "all", "currency_basis": "CNY"},
    )
    assert wb.status_code == 200
    table_keys = {t["key"] for t in wb.json()["result"]["tables"]}
    assert "advanced_attribution_bundle" not in table_keys

    adv = client.get(
        "/ui/balance-analysis/advanced-attribution",
        params={"report_date": "2025-12-31"},
    )
    assert adv.status_code == 200
    assert adv.json()["result_meta"]["result_kind"] == ADVANCED_ATTRIBUTION_RESULT_KIND

    get_settings.cache_clear()
