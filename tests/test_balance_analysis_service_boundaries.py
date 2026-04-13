from __future__ import annotations

from tests.helpers import load_module
from tests.test_balance_analysis_api import _configure_and_materialize


def test_balance_analysis_service_outward_envelopes_do_not_use_snapshot_repo_readers(
    tmp_path,
    monkeypatch,
):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.balance_analysis_service",
        "backend/app/services/balance_analysis_service.py",
    )
    repo_mod = load_module(
        "backend.app.repositories.balance_analysis_repo",
        "backend/app/repositories/balance_analysis_repo.py",
    )

    def fail_snapshot_read(*args, **kwargs):
        raise AssertionError("outward balance-analysis path must not read snapshot tables directly")

    monkeypatch.setattr(repo_mod.BalanceAnalysisRepository, "load_zqtz_snapshot_rows", fail_snapshot_read)
    monkeypatch.setattr(repo_mod.BalanceAnalysisRepository, "load_tyw_snapshot_rows", fail_snapshot_read)

    detail_payload = service_mod.balance_analysis_detail_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2025-12-31",
        position_scope="all",
        currency_basis="CNY",
    )
    overview_payload = service_mod.balance_analysis_overview_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2025-12-31",
        position_scope="all",
        currency_basis="CNY",
    )
    summary_payload = service_mod.balance_analysis_summary_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2025-12-31",
        position_scope="all",
        currency_basis="CNY",
        limit=50,
        offset=0,
    )
    workbook_payload = service_mod.balance_analysis_workbook_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2025-12-31",
        position_scope="all",
        currency_basis="CNY",
    )
    basis_payload = service_mod.balance_analysis_basis_breakdown_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2025-12-31",
        position_scope="all",
        currency_basis="CNY",
    )

    assert detail_payload["result_meta"]["result_kind"] == "balance-analysis.detail"
    assert overview_payload["result_meta"]["result_kind"] == "balance-analysis.overview"
    assert summary_payload["result_meta"]["result_kind"] == "balance-analysis.summary"
    assert workbook_payload["result_meta"]["result_kind"] == "balance-analysis.workbook"
    assert basis_payload["result_meta"]["result_kind"] == "balance-analysis.basis-breakdown"


def test_balance_analysis_service_paths_do_not_call_replace_formal_balance_rows(
    tmp_path,
    monkeypatch,
):
    """Guard: formal fact writes stay in tasks; service envelopes are read-only."""
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.balance_analysis_service",
        "backend/app/services/balance_analysis_service.py",
    )
    repo_mod = load_module(
        "backend.app.repositories.balance_analysis_repo",
        "backend/app/repositories/balance_analysis_repo.py",
    )

    calls: list[object] = []

    def _capture_replace(self, **kwargs):
        calls.append(kwargs)
        return None

    monkeypatch.setattr(
        repo_mod.BalanceAnalysisRepository,
        "replace_formal_balance_rows",
        _capture_replace,
    )

    service_mod.balance_analysis_overview_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2025-12-31",
        position_scope="all",
        currency_basis="CNY",
    )
    service_mod.balance_analysis_detail_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2025-12-31",
        position_scope="all",
        currency_basis="CNY",
    )

    assert calls == []
