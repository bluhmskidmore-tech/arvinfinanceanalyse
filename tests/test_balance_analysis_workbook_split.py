from __future__ import annotations

import importlib
from pathlib import Path

from backend.app.governance.settings import get_settings
from tests.helpers import load_module
from tests.test_balance_analysis_workbook_contract import _seed_workbook_snapshot_and_fx_tables


def _materialize_balance_rows(tmp_path: Path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    _seed_workbook_snapshot_and_fx_tables(str(duckdb_path))

    task_mod = load_module(
        "backend.app.tasks.balance_analysis_materialize",
        "backend/app/tasks/balance_analysis_materialize.py",
    )
    monkeypatch.setattr(task_mod.materialize_fx_mid_for_report_date, "fn", lambda **kwargs: None)
    task_mod.materialize_balance_analysis_facts.fn(
        report_date="2025-12-31",
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    repo_mod = load_module(
        "backend.app.repositories.balance_analysis_repo",
        "backend/app/repositories/balance_analysis_repo.py",
    )
    service_mod = load_module(
        "backend.app.services.balance_analysis_workbook_service",
        "backend/app/services/balance_analysis_workbook_service.py",
    )
    repo = repo_mod.BalanceAnalysisRepository(str(duckdb_path))
    zqtz_rows = [
        service_mod._to_formal_zqtz_fact_row(row)
        for row in repo.fetch_formal_zqtz_rows(
            report_date="2025-12-31",
            position_scope="all",
            currency_basis="native",
        )
    ]
    tyw_rows = [
        service_mod._to_formal_tyw_fact_row(row)
        for row in repo.fetch_formal_tyw_rows(
            report_date="2025-12-31",
            position_scope="all",
            currency_basis="native",
        )
    ]
    zqtz_currency_rows = [
        service_mod._to_formal_zqtz_fact_row(row)
        for row in repo.fetch_formal_zqtz_rows(
            report_date="2025-12-31",
            position_scope="all",
            currency_basis="CNY",
        )
    ]
    return zqtz_rows, tyw_rows, zqtz_currency_rows


def test_split_builder_matches_legacy_workbook_payload(tmp_path, monkeypatch):
    zqtz_rows, tyw_rows, zqtz_currency_rows = _materialize_balance_rows(tmp_path, monkeypatch)
    legacy_mod = load_module(
        "backend.app.core_finance.balance_analysis_workbook",
        "backend/app/core_finance/balance_analysis_workbook.py",
    )
    split_mod = importlib.import_module("backend.app.core_finance.balance_workbook.builder")

    kwargs = {
        "report_date": zqtz_rows[0].report_date,
        "position_scope": "all",
        "currency_basis": "native",
        "zqtz_rows": zqtz_rows,
        "tyw_rows": tyw_rows,
        "zqtz_currency_rows": zqtz_currency_rows,
    }

    assert legacy_mod.build_balance_analysis_workbook_payload(**kwargs) == split_mod.build_balance_analysis_workbook_payload(
        **kwargs
    )


def test_split_helpers_match_legacy_helper_tables(tmp_path, monkeypatch):
    zqtz_rows, tyw_rows, _zqtz_currency_rows = _materialize_balance_rows(tmp_path, monkeypatch)
    legacy_mod = load_module(
        "backend.app.core_finance.balance_analysis_workbook",
        "backend/app/core_finance/balance_analysis_workbook.py",
    )
    bond_tables_mod = importlib.import_module("backend.app.core_finance.balance_workbook._bond_tables")
    analysis_tables_mod = importlib.import_module("backend.app.core_finance.balance_workbook._analysis_tables")

    assert legacy_mod._build_bond_business_type_table(zqtz_rows) == bond_tables_mod._build_bond_business_type_table(
        zqtz_rows
    )
    assert legacy_mod._build_interest_mode_table(zqtz_rows) == analysis_tables_mod._build_interest_mode_table(
        zqtz_rows
    )
    assert legacy_mod._build_campisi_table(zqtz_rows) == analysis_tables_mod._build_campisi_table(zqtz_rows)
    assert legacy_mod._build_counterparty_type_table(tyw_rows) == analysis_tables_mod._build_counterparty_type_table(
        tyw_rows
    )
