"""Contract tests for `backend.app.schemas.qdb_gl_contract`."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.schemas.qdb_gl_contract import (
    QdbGlBaselineBinding,
    QdbGlBaselineValidationEvidence,
    QdbGlContractCheck,
    QdbGlContractFinding,
    QdbGlLineage,
)


def _minimal_lineage(**overrides: object) -> QdbGlLineage:
    base = dict(
        source_file="f.xlsx",
        source_kind="unknown",
        source_version="sv1",
        rule_version="rv1",
        trace_id="tr1",
    )
    base.update(overrides)
    return QdbGlLineage(**base)


@pytest.mark.parametrize("kind", ["ledger_reconciliation", "average_balance", "unknown"])
def test_qdb_gl_lineage_accepts_source_kind_literals(kind: str) -> None:
    lin = _minimal_lineage(source_kind=kind)
    assert lin.source_kind == kind


def test_qdb_gl_lineage_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        QdbGlLineage(
            source_file="x",
            source_kind="unknown",
            source_version="s",
            rule_version="r",
            trace_id="t",
            unexpected=True,  # type: ignore[arg-type]
        )


def test_qdb_gl_contract_finding_optional_location_defaults_none() -> None:
    f = QdbGlContractFinding(message="m")
    assert f.sheet_name is None
    assert f.row_locator is None
    assert f.cell_ref is None


@pytest.mark.parametrize("status", ["pass", "fail", "not_applicable"])
def test_qdb_gl_contract_check_status_and_default_findings(status: str) -> None:
    c = QdbGlContractCheck(check_id="c1", status_label=status)  # type: ignore[arg-type]
    assert c.findings == []


def test_qdb_gl_contract_check_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        QdbGlContractCheck(check_id="c", status_label="pass", extra_field=1)  # type: ignore[arg-type]


def test_qdb_gl_baseline_binding_accepts_path_and_requires_fields() -> None:
    p = Path("ledger.xlsx")
    b = QdbGlBaselineBinding(
        source_kind="ledger_reconciliation",
        report_month="202602",
        path=p,
        source_version="sv",
    )
    assert b.path == p
    assert isinstance(b.path, Path)


def test_qdb_gl_baseline_binding_missing_required_raises() -> None:
    with pytest.raises(ValidationError):
        QdbGlBaselineBinding(
            source_kind="ledger_reconciliation",
            report_month="202602",
            path=Path("x"),
        )


def test_qdb_gl_baseline_validation_evidence_combinations_and_defaults() -> None:
    lin = _minimal_lineage(source_kind="ledger_reconciliation")
    for binding in ("bound", "rejected"):
        for label in ("pass", "fail"):
            ev = QdbGlBaselineValidationEvidence(
                binding_status=binding,  # type: ignore[arg-type]
                source_kind="ledger_reconciliation",
                admissible=True,
                status_label=label,  # type: ignore[arg-type]
                source_version="sv",
                rule_version="rv",
                trace_id="tr",
                lineage=lin,
            )
            assert ev.bound_currency_groups == []
            assert ev.checks == []
            assert ev.report_month is None


def test_qdb_gl_baseline_validation_evidence_forbids_extra_fields() -> None:
    lin = _minimal_lineage()
    with pytest.raises(ValidationError):
        QdbGlBaselineValidationEvidence(
            binding_status="bound",
            source_kind="unknown",
            admissible=False,
            status_label="fail",
            source_version="s",
            rule_version="r",
            trace_id="t",
            lineage=lin,
            not_allowed=123,  # type: ignore[arg-type]
        )


def test_extra_forbid_rejects_unknown_top_level_field_on_lineage() -> None:
    """Explicit negative test for model_config extra='forbid'."""
    with pytest.raises(ValidationError) as exc:
        QdbGlLineage.model_validate(
            {
                "source_file": "a",
                "source_kind": "unknown",
                "source_version": "s",
                "rule_version": "r",
                "trace_id": "t",
                "ghost": True,
            }
        )
    assert "ghost" in str(exc.value).lower() or "extra" in str(exc.value).lower()
