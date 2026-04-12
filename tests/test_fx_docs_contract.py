from __future__ import annotations

from tests.helpers import ROOT


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_acceptance_docs_capture_fx_multicurrency_backfill_and_analytical_split():
    acceptance = _read("docs/acceptance_tests.md")

    assert "Choice -> AkShare -> fail closed" in acceptance
    assert "historical backfill path exists" in acceptance
    assert "non-middle-rate FX observations (indices / swap curves) remain analytical-only" in acceptance


def test_runbook_and_data_contracts_share_vendor_first_fx_story():
    runbook = _read("docs/BALANCE_ANALYSIS_FX_SOURCE_RUNBOOK.md")
    contracts = _read("docs/data_contracts.md")

    assert "Choice catalog-driven middle-rate discovery" in runbook
    assert "Choice catalog-driven middle-rate discovery" in contracts
    assert "HKD -> CNY" in runbook
    assert "HKD -> CNY" in contracts
