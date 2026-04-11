from __future__ import annotations

import sys

from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.services.pnl_service import PNL_CACHE_VERSION
from backend.app.tasks.pnl_materialize import PNL_RESULT_CACHE_VERSION
from tests.helpers import load_module


def _materialize_formal_anchor(tmp_path, monkeypatch) -> None:
    task_module = sys.modules.get("backend.app.tasks.pnl_materialize")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.pnl_materialize",
            "backend/app/tasks/pnl_materialize.py",
        )

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_FORMAL_PNL_ENABLED", "true")
    get_settings.cache_clear()

    task_module.materialize_pnl_facts.fn(
        report_date="2025-12-31",
        is_month_end=True,
        fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "240001.IB",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "invest_type_raw": "交易性金融资产",
                "interest_income_514": "12.50",
                "fair_value_change_516": "-3.25",
                "capital_gain_517": "1.75",
                "manual_adjustment": "0.50",
                "currency_basis": "CNY",
                "source_version": "sv_cache_gate_a",
                "rule_version": "rv_cache_gate_a",
                "ingest_batch_id": "batch_cache_gate_a",
                "trace_id": "trace_cache_gate_a",
                "approval_status": "approved",
                "event_semantics": "realized_formal",
                "realized_flag": True,
            }
        ],
        nonstd_rows_by_type={},
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )


def test_gate_a_formal_cache_metadata_anchor_remains_explicitly_formal(tmp_path, monkeypatch):
    _materialize_formal_anchor(tmp_path, monkeypatch)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get("/api/pnl/dates")

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["formal_use_allowed"] is True
    assert payload["result_meta"]["scenario_flag"] is False
    assert payload["result_meta"]["cache_version"] == PNL_CACHE_VERSION
    get_settings.cache_clear()


def test_gate_a_primary_cache_key_must_be_basis_scoped():
    task_module = load_module(
        "backend.app.tasks.pnl_materialize",
        "backend/app/tasks/pnl_materialize.py",
    )

    assert task_module.CACHE_KEY == "pnl:phase2:materialize:formal"
    assert task_module.PNL_FORMAL_BASIS in task_module.CACHE_KEY
    assert task_module.PNL_RESULT_CACHE_VERSION.startswith("cv_pnl_formal__")


def test_gate_a_lock_key_must_be_basis_scoped():
    task_module = load_module(
        "backend.app.tasks.pnl_materialize",
        "backend/app/tasks/pnl_materialize.py",
    )

    assert task_module.PNL_MATERIALIZE_LOCK.key == "lock:duckdb:formal:pnl:phase2:materialize"
    assert "formal" in task_module.PNL_MATERIALIZE_LOCK.key


def test_gate_a_cache_version_must_be_basis_scoped():
    service_module = load_module(
        "backend.app.services.pnl_service",
        "backend/app/services/pnl_service.py",
    )

    assert service_module.PNL_CACHE_VERSION == PNL_RESULT_CACHE_VERSION
    assert service_module.PNL_CACHE_VERSION.startswith("cv_pnl_formal")
