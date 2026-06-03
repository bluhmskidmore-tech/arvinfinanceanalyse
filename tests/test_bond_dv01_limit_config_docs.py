from __future__ import annotations

import csv

from backend.app.services.bond_analytics_service import (
    DV01_LIMIT_CONFIG_CLASSES,
    DV01_LIMIT_CONFIG_REQUIRED_FIELDS,
)
from tests.helpers import ROOT


TEMPLATE_PATH = ROOT / "docs" / "templates" / "bond_dv01_limit_config_template.csv"
RUNBOOK_PATH = ROOT / "docs" / "BOND_DV01_LIMIT_CONFIG_RUNBOOK.md"


def test_bond_dv01_limit_config_template_matches_import_contract_without_fake_limits():
    with TEMPLATE_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    assert reader.fieldnames == list(DV01_LIMIT_CONFIG_REQUIRED_FIELDS)
    assert [row["accounting_class"] for row in rows] == list(DV01_LIMIT_CONFIG_CLASSES)
    for row in rows:
        assert row["limit_dv01"] == ""
        assert row["warning_dv01"] == ""
        assert row["hedge_target_dv01"] == ""
        assert row["limit_source"] == ""
        assert row["limit_source_version"] == ""
        assert row["limit_rule_version"] == ""
        assert row["limit_effective_date"] == ""


def test_bond_dv01_limit_config_runbook_documents_acceptance_flow():
    runbook = RUNBOOK_PATH.read_text(encoding="utf-8")

    assert "docs/templates/bond_dv01_limit_config_template.csv" in runbook
    assert "backend.app.tasks.bond_dv01_limit_config_import" in runbook
    assert "--reference-baseline" in runbook
    assert "--reference-baseline-csv" in runbook
    assert "business_limit_fields_blank" in runbook
    assert "--write-template" in runbook
    assert "--check-status" in runbook
    assert "--dry-run" in runbook
    assert "/api/bond-analytics/dv01-limit-config-status" in runbook
    assert "acceptance_status" in runbook
    assert "AC / OCI / TPL / all" in runbook
    assert "it cannot replace the direct `AC / OCI / TPL` rows for acceptance" in runbook
