from __future__ import annotations

import re

from tests.helpers import ROOT, load_module


def _catalog_capture_ready_exec_sample_ids() -> list[str]:
    catalog = (ROOT / "docs" / "golden_sample_catalog.md").read_text(encoding="utf-8")
    pattern = re.compile(
        r"^\| `(?P<sample_id>GS-EXEC-[A-Z-]+)` \| .*? \| `capture-ready` \|",
        re.MULTILINE,
    )
    return [match.group("sample_id") for match in pattern.finditer(catalog)]


def test_golden_sample_catalog_exec_rows_match_release_gate_sample_ids():
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )

    assert _catalog_capture_ready_exec_sample_ids() == module.EXECUTIVE_RELEASE_SAMPLE_IDS


def test_release_suite_gates_exec_contract_and_drift_checks():
    module = load_module(
        "scripts.backend_release_suite",
        "scripts/backend_release_suite.py",
    )

    assert "tests/test_executive_release_contract.py" in module.RELEASE_SUITE_TESTS
    assert "tests/test_golden_sample_release_matrix.py" in module.RELEASE_SUITE_TESTS
