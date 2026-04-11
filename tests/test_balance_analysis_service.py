from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import load_module
from tests.test_balance_analysis_api import _configure_and_materialize


def test_balance_analysis_overview_service_rejects_invalid_filters(tmp_path, monkeypatch):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.balance_analysis_service",
        "backend/app/services/balance_analysis_service.py",
    )

    with pytest.raises(ValueError, match="position_scope"):
        service_mod.balance_analysis_overview_envelope(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            report_date="2025-12-31",
            position_scope="wrong-scope",
            currency_basis="CNY",
        )

    with pytest.raises(ValueError, match="currency_basis"):
        service_mod.balance_analysis_overview_envelope(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            report_date="2025-12-31",
            position_scope="all",
            currency_basis="USD",
        )


def test_balance_analysis_service_uses_shared_formal_result_runtime_helper():
    path = Path(__file__).resolve().parents[1] / "backend" / "app" / "services" / "balance_analysis_service.py"
    src = path.read_text(encoding="utf-8")

    assert "backend.app.services.formal_result_runtime" in src
    assert "def _formal_result_meta" not in src


def test_balance_analysis_service_uses_persisted_cache_version_from_governance(
    tmp_path,
    monkeypatch,
):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.balance_analysis_service",
        "backend/app/services/balance_analysis_service.py",
    )

    monkeypatch.setattr(
        service_mod,
        "CACHE_VERSION",
        "cv_balance_analysis_formal__rv_future_bump",
    )

    payload = service_mod.balance_analysis_overview_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2025-12-31",
        position_scope="all",
        currency_basis="CNY",
    )

    assert (
        payload["result_meta"]["cache_version"]
        == "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1"
    )
