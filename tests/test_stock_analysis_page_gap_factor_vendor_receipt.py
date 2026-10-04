from __future__ import annotations

import copy
from pathlib import Path

import pytest

from backend.app.governance import (
    stock_analysis_current_rule_factor_vendor_receipt as current_rule_receipt,
)
from backend.app.governance import (
    stock_analysis_page_gap_factor_vendor_receipt as receipt_task,
)


def _factor_manifest(tmp_path: Path) -> dict[str, object]:
    database_path = str((tmp_path / "moss.duckdb").resolve())
    page_path = str((tmp_path / "page.json").resolve())
    cells = [
        {"stock_code": "000001.SZ", "trade_date": "2026-01-05"},
        {"stock_code": "600000.SH", "trade_date": "2026-01-05"},
        {"stock_code": "000002.SZ", "trade_date": "2026-01-06"},
    ]
    target_sha = current_rule_receipt._canonical_json_sha256(cells)
    return {
        "manifest_kind": "stock_analysis_page_gap_factor_manifest_v1",
        "status": "gaps_found",
        "remediation_only": True,
        "strict_exact_date_lookup": True,
        "carry_forward_allowed": False,
        "fallback_allowed": False,
        "write_allowed": False,
        "historical_availability_proven": False,
        "certification_allowed": False,
        "downstream_materialization_allowed": False,
        "blockers": [],
        "target_cells": cells,
        "target_cell_count": len(cells),
        "target_cells_sha256": target_sha,
        "requested_unique_date_count": 2,
        "canonical_manifest_sha256": "A" * 64,
        "database": {
            "path": database_path,
            "sha256_before": "B" * 64,
            "sha256_after": "B" * 64,
            "unchanged": True,
            "read_only": True,
        },
        "page_manifest_binding": {
            "path": page_path,
            "file_sha256": "C" * 64,
            "canonical_manifest_sha256": "D" * 64,
            "manifest_kind": "stock_analysis_page_gap_manifest_v1",
            "page_id": "GAP-STOCK-ANALYSIS-PAGE",
            "page_route": "/stock-analysis",
            "page_metric_key": "data_health.adjustment_factor_gap",
            "database_path": database_path,
            "database_sha256": "B" * 64,
            "page_gap_view_count": 4,
            "missing_factor_cell_count": 3,
        },
    }


def _returned_cells() -> list[dict[str, object]]:
    return [
        {
            "requested_trade_date": "2026-01-05",
            "stock_code": "000001.SZ",
            "trade_date": "2026-01-05",
            "adj_factor": 1.01,
        },
        {
            "requested_trade_date": "2026-01-05",
            "stock_code": "600000.SH",
            "trade_date": "2026-01-05",
            "adj_factor": 2.02,
        },
        {
            "requested_trade_date": "2026-01-06",
            "stock_code": "000002.SZ",
            "trade_date": "2026-01-06",
            "adj_factor": 3.03,
        },
    ]


def _build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, object]:
    monkeypatch.setattr(
        receipt_task.factor_manifest_task,
        "validate_stock_analysis_page_gap_factor_manifest",
        lambda manifest: (True, ()),
    )
    return receipt_task.build_stock_analysis_page_gap_factor_vendor_receipt(
        reviewed_factor_manifest=_factor_manifest(tmp_path),
        reviewed_factor_manifest_path=tmp_path / "factor.json",
        reviewed_factor_manifest_file_sha256="E" * 64,
        returned_cells=_returned_cells(),
        captured_at="2026-08-24T10:00:00Z",
        database_sha256_before="B" * 64,
        database_sha256_after="B" * 64,
    )


def test_builds_dynamic_exact_set_receipt_with_approval_scope(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    receipt = _build(monkeypatch, tmp_path)

    assert receipt["status"] == receipt_task.READY_STATUS
    assert receipt["requested_cell_count"] == 3
    assert receipt["returned_cell_count"] == 3
    assert receipt["requested_unique_date_count"] == 2
    assert receipt["vendor_call_count"] == 2
    assert receipt["write_allowed"] is False
    assert receipt["historical_availability_proven"] is False
    assert receipt["certification_allowed"] is False
    assert receipt["downstream_materialization_executed"] is False
    assert isinstance(receipt["canonical_receipt_sha256"], str)
    valid, errors = receipt_task.validate_stock_analysis_page_gap_factor_vendor_receipt(
        receipt,
        reviewed_factor_manifest=_factor_manifest(tmp_path),
        reviewed_factor_manifest_path=tmp_path / "factor.json",
        reviewed_factor_manifest_file_sha256="E" * 64,
    )
    assert valid, errors


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("write_allowed", True),
        ("historical_availability_proven", True),
        ("certification_allowed", True),
        ("downstream_materialization_executed", True),
    ],
)
def test_validator_rejects_boundary_escalation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    field_name: str,
    value: object,
) -> None:
    receipt = _build(monkeypatch, tmp_path)
    tampered = copy.deepcopy(receipt)
    tampered[field_name] = value
    tampered["canonical_receipt_sha256"] = receipt_task._receipt_sha256(tampered)

    valid, errors = receipt_task.validate_stock_analysis_page_gap_factor_vendor_receipt(
        tampered,
        reviewed_factor_manifest=_factor_manifest(tmp_path),
    )

    assert not valid
    assert any(field_name in error for error in errors)


def test_validator_rejects_scope_or_page_binding_tamper(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    receipt = _build(monkeypatch, tmp_path)
    tampered = copy.deepcopy(receipt)
    tampered["page_manifest_binding"]["file_sha256"] = "F" * 64  # type: ignore[index]
    tampered["canonical_receipt_sha256"] = receipt_task._receipt_sha256(tampered)

    valid, errors = receipt_task.validate_stock_analysis_page_gap_factor_vendor_receipt(
        tampered,
        reviewed_factor_manifest=_factor_manifest(tmp_path),
    )

    assert not valid
    assert any("page_manifest_binding" in error for error in errors)


def test_builder_rejects_missing_or_wrong_date_rows(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        receipt_task.factor_manifest_task,
        "validate_stock_analysis_page_gap_factor_manifest",
        lambda manifest: (True, ()),
    )
    rows = _returned_cells()[:-1]
    with pytest.raises(ValueError, match="exactly equal"):
        receipt_task.build_stock_analysis_page_gap_factor_vendor_receipt(
            reviewed_factor_manifest=_factor_manifest(tmp_path),
            reviewed_factor_manifest_path=tmp_path / "factor.json",
            reviewed_factor_manifest_file_sha256="E" * 64,
            returned_cells=rows,
            captured_at="2026-08-24T10:00:00Z",
            database_sha256_before="B" * 64,
            database_sha256_after="B" * 64,
        )


def test_shared_normalization_and_hash_dependencies_are_locked() -> None:
    assert receipt_task._exact_cell_receipt._normalize_requested_cells is (
        current_rule_receipt._normalize_requested_cells
    )
    assert receipt_task._exact_cell_receipt._normalize_returned_cells is (
        current_rule_receipt._normalize_returned_cells
    )
    assert receipt_task._exact_cell_receipt._canonical_json_sha256 is (
        current_rule_receipt._canonical_json_sha256
    )
