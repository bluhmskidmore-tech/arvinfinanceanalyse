from __future__ import annotations

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
