from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
import pytest

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from backend.app.services.advanced_attribution_service import (
    ADVANCED_ATTRIBUTION_RESULT_KIND,
)
from tests.helpers import load_module
from backend.app.schemas.common_numeric import numeric_from_raw


def _numeric_fields(fields):
    return {key: numeric_from_raw(raw=Decimal(value), unit="yuan", sign_aware=True).model_dump(mode="json") for key, value in fields.items()}


def _return_fields(fields):
    from backend.app.services.bond_analytics_service import _bond_analytics_api_payload

    return _bond_analytics_api_payload(_numeric_fields(fields))


def test_real_bridge_numeric_preserves_zero_and_blocks_missing_effects(monkeypatch):
    from decimal import Decimal

    from backend.app.schemas.pnl_bridge import PnlBridgeSummarySchema
    from backend.app.services import advanced_attribution_service as service

    fields = {name: Decimal("0") for name in PnlBridgeSummarySchema._NUMERIC_FIELDS}
    fields["total_actual_pnl"] = Decimal("1234567890123.12345678")
    summary = PnlBridgeSummarySchema(
        **fields, row_count=1, ok_count=0, warning_count=1, error_count=0,
        quality_flag="warning",
        treasury_curve_availability={"status": "unavailable", "applicable_rows": 1, "unavailable_rows": 1, "reasons": ["curve_unavailable"]},
        credit_spread_availability={"status": "partial", "applicable_rows": 2, "unavailable_rows": 1, "reasons": ["curve_unavailable"]},
    ).model_dump(mode="json")
    monkeypatch.setattr(service, "get_return_decomposition", lambda *args, **kwargs: {"result": {}})
    monkeypatch.setattr(service, "pnl_bridge_envelope", lambda **kwargs: {"result": {"summary": summary}})
    result = service.advanced_attribution_bundle_envelope(report_date="2026-04-30", duckdb_path="synthetic.duckdb", governance_dir="synthetic-governance")["result"]
    assert result["summary"]["actual_pnl"] == "1234567890123.12345678"
    assert result["summary"]["residual"] == "0"
    assert "quality_flag" not in result["available_components"]
    assert "treasury_curve" not in result["available_components"]
    assert "credit_spread" not in result["available_components"]
    assert "treasury_curve" in result["blocked_components"]
    assert "credit_spread" in result["blocked_components"]


@pytest.mark.parametrize("mode", ["missing", "empty", "exception"])
def test_advanced_attribution_all_missing_is_not_ready(monkeypatch, mode):
    from backend.app.schemas.pnl_bridge import PnlBridgeSummarySchema
    from backend.app.services import advanced_attribution_service as service

    fields = {name: numeric_from_raw(raw=None if mode == "missing" else Decimal("0"), unit="yuan", sign_aware=True) for name in PnlBridgeSummarySchema._NUMERIC_FIELDS}
    summary = PnlBridgeSummarySchema(**fields, row_count=0 if mode == "empty" else 1, ok_count=0, warning_count=1, error_count=0, quality_flag="warning").model_dump(mode="json")

    def return_missing(*args, **kwargs):
        assert kwargs == {"duckdb_path": "synthetic.duckdb", "governance_dir": "synthetic-governance"}
        raise RuntimeError("synthetic return unavailable")

    def bridge_missing(**kwargs):
        if mode == "exception":
            raise RuntimeError("synthetic bridge unavailable")
        return {"result": {"summary": summary}}

    monkeypatch.setattr(service, "get_return_decomposition", return_missing)
    monkeypatch.setattr(service, "pnl_bridge_envelope", bridge_missing)
    result = service.advanced_attribution_bundle_envelope(report_date="2026-04-30", duckdb_path="synthetic.duckdb", governance_dir="synthetic-governance")["result"]
    assert result["status"] == "not_ready"
    assert result["summary"] == {}
    assert result["available_components"] == []
    assert "treasury_curve" in result["blocked_components"]


def test_return_market_zero_without_bridge_availability_is_blocked(monkeypatch):
    from backend.app.services import advanced_attribution_service as service

    monkeypatch.setattr(service, "get_return_decomposition", lambda *args, **kwargs: {"result": {**_return_fields({"carry": "0", "roll_down": "0", "rate_effect": "0", "spread_effect": "0"}), "bond_count": 1}})

    def bridge_unavailable(**kwargs):
        raise RuntimeError("synthetic bridge unavailable")

    monkeypatch.setattr(service, "pnl_bridge_envelope", bridge_unavailable)
    result = service.advanced_attribution_bundle_envelope(report_date="2026-04-30", duckdb_path="synthetic.duckdb", governance_dir="synthetic-governance")["result"]
    assert result["summary"] == {"carry": "0.00000000"}
    assert result["available_components"] == ["carry"]
    assert {"roll_down", "rate_effect", "spread_effect"} <= set(result["blocked_components"])


def _seed_balance_read_scope(tmp_path, monkeypatch) -> None:
    sqlite_path = tmp_path / "balance-analysis-read-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    repo_mod = load_module(
        "backend.app.repositories.user_scope_repo",
        "backend/app/repositories/user_scope_repo.py",
    )
    repo_mod.UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
        user_id="*",
        role=None,
        resource="balance_analysis",
        action="read",
    )
    from backend.app.services import advanced_attribution_service as service

    monkeypatch.setattr(service, "get_return_decomposition", lambda *args, **kwargs: {"result": {**_return_fields({"carry": "10"}), "bond_count": 1}})
    monkeypatch.setattr(service, "pnl_bridge_envelope", lambda **kwargs: {"result": {}})


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


def test_advanced_attribution_accepts_stripped_valid_report_date(tmp_path, monkeypatch):
    _seed_balance_read_scope(tmp_path, monkeypatch)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get(
        "/ui/balance-analysis/advanced-attribution",
        params={"report_date": " 2025-12-31 "},
    )
    assert response.status_code == 200
    assert response.json()["result"]["report_date"] == "2025-12-31"


def test_advanced_attribution_endpoint_returns_analytical_partial_contract_when_upstreams_exist(tmp_path, monkeypatch):
    _seed_balance_read_scope(tmp_path, monkeypatch)
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
    assert result["status"] == "partial"
    assert isinstance(result["summary"], dict)
    assert isinstance(result["available_components"], list)
    assert len(result["available_components"]) >= 1
    assert isinstance(result["missing_inputs"], list)
    assert len(result["missing_inputs"]) >= 1
    assert isinstance(result["blocked_components"], list)
    assert len(result["blocked_components"]) >= 1
    assert isinstance(result["warnings"], list)
    assert len(result["warnings"]) >= 1
    assert "attribution" not in result


def test_advanced_attribution_endpoint_switches_to_scenario_contract_when_explicit_shocks_are_given(tmp_path, monkeypatch):
    _seed_balance_read_scope(tmp_path, monkeypatch)
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
    from backend.app.services.advanced_attribution_service import (
        advanced_attribution_bundle_envelope,
    )

    env = advanced_attribution_bundle_envelope(report_date="2025-06-30")
    assert env["result_meta"]["basis"] == "analytical"
    assert env["result_meta"]["basis"] != "formal"


def test_advanced_attribution_meta_can_be_scenario_but_never_formal():
    from backend.app.services.advanced_attribution_service import (
        advanced_attribution_bundle_envelope,
    )

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
        lambda report_date, period_type, asset_class, accounting_class, **kwargs: {
            "result": {**_return_fields({
                "carry": "10.00000000",
                "roll_down": "2.00000000",
                "rate_effect": "-1.00000000",
                "spread_effect": "0.50000000",
                "explained_pnl": "11.50000000",
            }),
                "warnings": ["curve-backed analytical summary"],
            }
        },
    )
    monkeypatch.setattr(
        service_mod,
        "pnl_bridge_envelope",
        lambda **kwargs: {
            "result": {
                "summary": {**_numeric_fields({
                    "total_carry": "9.00000000",
                    "total_roll_down": "1.50000000",
                    "total_treasury_curve": "-0.50000000",
                    "total_credit_spread": "0.00000000",
                    "total_explained_pnl": "10.00000000",
                    "total_actual_pnl": "10.20000000",
                    "total_residual": "0.20000000",
                }),
                    "quality_flag": "warning",
                    "roll_down_availability": {"status": "ok"},
                    "treasury_curve_availability": {"status": "ok"},
                    "credit_spread_availability": {"status": "ok"},
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
    assert result["status"] == "partial"
    assert result["mode"] == "analytical"
    assert result["upstream_summaries"]["return_decomposition"]["explained_pnl"] == "11.50000000"
    assert result["upstream_summaries"]["pnl_bridge"]["total_residual"] == "0.20000000"
    assert result["summary"]["carry"] == "10.00000000"
    assert result["summary"]["roll_down"] == "2.00000000"
    assert result["summary"]["rate_effect"] == "-1.00000000"
    assert result["summary"]["spread_effect"] == "0.50000000"
    assert result["summary"]["treasury_curve"] == "-0.50000000"
    assert result["summary"]["actual_pnl"] == "10.20000000"
    assert result["summary"]["residual"] == "0.20000000"
    assert "carry" in result["available_components"]
    assert "actual_pnl" in result["available_components"]
    assert "action_attribution" in result["blocked_components"]
    assert not any("status=not_ready" in warning for warning in result["warnings"])
    assert not any("no attribution figures are returned" in warning for warning in result["warnings"])


def test_governed_workbook_tables_exclude_advanced_attribution_bundle(tmp_path, monkeypatch):
    """Regression: advanced_attribution_bundle must not appear in workbook table keys."""
    from backend.app.governance.settings import get_settings

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    _seed_balance_read_scope(tmp_path, monkeypatch)

    from tests.test_balance_analysis_workbook_contract import (
        _seed_workbook_snapshot_and_fx_tables,
    )

    _seed_workbook_snapshot_and_fx_tables(str(duckdb_path))
    import duckdb

    with duckdb.connect(str(duckdb_path)) as conn:
        conn.execute("update fx_daily_mid set observed_trade_date = trade_date")

    # Registry contract suites can replace the registry while its runtime stays cached.
    # Reload the real runtime before the task so both use the current registry.
    runtime_mod = load_module(
        "backend.app.tasks.formal_compute_runtime",
        "backend/app/tasks/formal_compute_runtime.py",
    )
    task_mod = load_module(
        "backend.app.tasks.balance_analysis_materialize",
        "backend/app/tasks/balance_analysis_materialize.py",
    )
    assert task_mod.run_formal_materialize is runtime_mod.run_formal_materialize
    assert (
        runtime_mod.require_registered_formal_module(task_mod.BALANCE_ANALYSIS_MODULE)
        is task_mod.BALANCE_ANALYSIS_MODULE
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
