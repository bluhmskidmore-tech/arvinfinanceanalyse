from __future__ import annotations

from decimal import Decimal
from importlib import import_module
from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient

from backend.app.core_finance.pnl_independent_reconciliation import (
    IndependentPnlComponentReference,
    IndependentPnlReference,
)
from backend.app.governance.settings import get_settings
from backend.app.repositories.pnl_independent_reference_repo import (
    PnlIndependentReferenceRepository,
    read_formal_fact_dependency_binding,
)
from backend.app.repositories.pnl_precompute_state import (
    invalidate_pnl_by_business_precompute_on_connection,
)
from backend.app.repositories.user_scope_repo import UserScopeRepository
from tests.helpers import load_module
from tests.test_pnl_api_contract import _materialize_three_pnl_dates


@pytest.fixture
def overview_context(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{(tmp_path / 'scope.db').as_posix()}")
    get_settings.cache_clear()
    UserScopeRepository(get_settings().postgres_dsn).grant_scope(
        user_id="*", role=None, resource="pnl", action="read"
    )
    governance = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    yield client, tmp_path / "moss.duckdb", Path(governance)
    get_settings.cache_clear()


def _reference(binding, *, interest: str = "12.50") -> IndependentPnlReference:
    # Fixed expectations are independent of the API's computed totals. Workbook
    # parsing, raw-cell mutations and cross-period replay are covered separately.
    values = {
        "interest_income_514": interest,
        "fair_value_change_516": "96.75",
        "capital_gain_517": "1.75",
        "manual_adjustment": "0.50",
    }
    return IndependentPnlReference(
        report_date="2025-12-31",
        currency_basis="CNY",
        ledger_currency_code="CNX",
        source_version="sv_independent_synthetic_ledger",
        rule_version="rv_independent_synthetic_ledger",
        formal_source_version=binding.formal_source_version,
        formal_rule_version=binding.formal_rule_version,
        approved_adjustment_version=binding.approved_adjustment_version,
        formal_dependency_revision=binding.formal_dependency_revision,
        formal_dependency_protocol_version=binding.formal_dependency_protocol_version,
        adjustment_stage=binding.adjustment_stage,
        components={
            key: IndependentPnlComponentReference(
                status="ready", value_yuan=Decimal(value),
                evidence_refs=(f"synthetic-ledger:{key}",),
            )
            for key, value in values.items()
        },
    )


def _get_overview(client: TestClient) -> dict:
    response = client.get("/api/pnl/overview", params={"report_date": "2025-12-31"})
    assert response.status_code == 200
    return response.json()


def test_actual_overview_reads_prepared_reference_and_reports_pending_pass_fail(
    overview_context, monkeypatch
):
    reference_service = import_module("backend.app.services.pnl_independent_reference_service")

    client, database, governance = overview_context
    binding = read_formal_fact_dependency_binding(database, report_date="2025-12-31")
    assert binding is not None
    repository = PnlIndependentReferenceRepository(governance)

    def forbid_source_parsing(*_args, **_kwargs):
        pytest.fail("A read request must not parse or hash the independent source workbook")

    monkeypatch.setattr(reference_service, "build_ledger_only_facts", forbid_source_parsing)
    monkeypatch.setattr(reference_service, "sha256_file", forbid_source_parsing)
    pending = _get_overview(client)
    assert pending["result"]["reconciliation_checks"]["independent_ledger"]["status"] == "pending"
    assert pending["result"]["reconciliation_checks"]["internal_arithmetic"]["breached"] is False

    repository.store_prepared(_reference(binding))
    matched = _get_overview(client)
    assert matched["result"]["reconciliation_checks"]["independent_ledger"]["status"] == "pass"
    assert matched["result"]["total_pnl"] == "111.50"

    repository.store_prepared(_reference(binding, interest="13.50"))
    mismatch = _get_overview(client)
    assert mismatch["result"]["reconciliation_checks"]["independent_ledger"]["status"] == "fail"
    assert mismatch["result"]["reconciliation_checks"]["internal_arithmetic"]["breached"] is False
    assert mismatch["result_meta"]["formal_use_allowed"] is False

    with duckdb.connect(str(database)) as connection:
        connection.execute("BEGIN TRANSACTION")
        invalidate_pnl_by_business_precompute_on_connection(
            connection, changed_report_dates=["2025-12-31"], reason="synthetic_reimport"
        )
        connection.execute("COMMIT")
    stale_reference = _get_overview(client)
    assert stale_reference["result"]["reconciliation_checks"]["independent_ledger"]["status"] == "pending"

    # Other contract fixtures reload the canonical module. Match the route's
    # import lookup so the concurrency injection reaches the live service.
    pnl_service = import_module("backend.app.services.pnl_service")

    binding = read_formal_fact_dependency_binding(database, report_date="2025-12-31")
    assert binding is not None
    repository.store_prepared(_reference(binding))
    read_totals = pnl_service.PnlRepository.overview_totals

    def write_between_total_read_and_revision_check(self, report_date):
        totals = read_totals(self, report_date)
        with duckdb.connect(str(database)) as connection:
            connection.execute("BEGIN TRANSACTION")
            invalidate_pnl_by_business_precompute_on_connection(
                connection, changed_report_dates=[report_date], reason="synthetic_concurrent_commit"
            )
            connection.execute("COMMIT")
        return totals

    monkeypatch.setattr(
        pnl_service.PnlRepository, "overview_totals", write_between_total_read_and_revision_check
    )
    changed_during_read = _get_overview(client)
    check = changed_during_read["result"]["reconciliation_checks"]["independent_ledger"]
    assert check["status"] == "pending"
    assert "changed while overview was read" in check["reason"]
    assert changed_during_read["result_meta"]["formal_use_allowed"] is False
    assert changed_during_read["result_meta"]["quality_flag"] == "stale"
