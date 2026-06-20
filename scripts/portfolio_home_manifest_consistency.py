from __future__ import annotations

import csv
from decimal import Decimal
import json
from pathlib import Path


def resolve_docs_path(path: str, docs_root: Path, root: Path) -> Path:
    normalized = path.replace("\\", "/")
    if normalized.startswith("docs/"):
        return docs_root / normalized[len("docs/") :]
    return root / path


def decimal_sum(rows: list[dict[str, object]], key: str) -> str:
    total = sum((Decimal(str(row.get(key) or "0")) for row in rows), Decimal("0"))
    return format(total.quantize(Decimal("0.00000001")), "f")


def int_value(payload: dict[str, object], key: str) -> int:
    return int(payload.get(key) or 0)


def str_value(payload: dict[str, object], key: str) -> str:
    return str(payload.get(key) or "0")


def _manifest(path: str, *, docs_root: Path, root: Path) -> dict[str, object] | None:
    resolved = resolve_docs_path(path, docs_root, root)
    if not resolved.exists():
        return None
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _csv_rows(path: str, *, docs_root: Path, root: Path) -> list[dict[str, str]] | None:
    resolved = resolve_docs_path(path, docs_root, root)
    if not resolved.exists():
        return None
    with resolved.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _fields_blank(rows: list[dict[str, str]], fields: list[str]) -> bool:
    for row in rows:
        for field in fields:
            if (row.get(field) or "").strip():
                return False
    return True


def _append_mismatch(
    blockers: list[str],
    *,
    prefix: str,
    field: str,
    expected: object,
    actual: object,
) -> None:
    if actual != expected:
        blockers.append(f"{prefix}_{field}_mismatch")


def krd_manifest_consistency(
    *,
    scorecard: dict[str, object],
    report_date: str,
    docs_root: Path,
    root: Path,
) -> dict[str, object]:
    path = f"docs/portfolio/krd-contract-decision/{report_date}/manifest.json"
    gates = scorecard["gates"]
    assert isinstance(gates, dict)
    krd = gates["krd_contract"]
    assert isinstance(krd, dict)
    summary_rows = krd.get("krd_remap_summary", [])
    assert isinstance(summary_rows, list)
    summary = [row for row in summary_rows if isinstance(row, dict)]
    expected_export_status = "clean" if krd.get("status") == "clean" else "decision_required"
    expected_remap_tenor_count = len(summary)
    expected_nonzero_dv01_rows = sum(int_value(row, "nonzero_dv01_rows") for row in summary)
    expected_dv01_sum = decimal_sum(summary, "dv01_sum")

    manifest = _manifest(path, docs_root=docs_root, root=root)
    export_summary = manifest.get("export_summary", {}) if isinstance(manifest, dict) else {}
    acceptance_criteria = manifest.get("acceptance_criteria", {}) if isinstance(manifest, dict) else {}
    assert isinstance(export_summary, dict)
    assert isinstance(acceptance_criteria, dict)
    actual_report_date = manifest.get("report_date") if isinstance(manifest, dict) else None
    actual_export_status = manifest.get("export_status") if isinstance(manifest, dict) else None
    actual_remap_tenor_count = export_summary.get("remap_tenor_count")
    actual_nonzero_dv01_rows = export_summary.get("nonzero_dv01_rows")
    actual_dv01_sum = export_summary.get("dv01_sum")
    expected_generated_owner_fields_must_be_blank = True
    actual_generated_owner_fields_must_be_blank = acceptance_criteria.get(
        "generated_owner_fields_must_be_blank"
    )
    summary_csv_path = f"docs/portfolio/krd-contract-decision/{report_date}/krd_remap_summary.csv"
    detail_csv_path = f"docs/portfolio/krd-contract-decision/{report_date}/krd_remap_detail.csv"
    summary_csv_rows = _csv_rows(summary_csv_path, docs_root=docs_root, root=root)
    detail_csv_rows = _csv_rows(detail_csv_path, docs_root=docs_root, root=root)
    summary_row_count = len(summary_csv_rows) if summary_csv_rows is not None else None
    detail_row_count = len(detail_csv_rows) if detail_csv_rows is not None else None
    owner_fields_blank = (
        summary_csv_rows is not None
        and detail_csv_rows is not None
        and _fields_blank(summary_csv_rows, ["risk_owner_decision", "decision_notes"])
        and _fields_blank(detail_csv_rows, ["risk_owner_decision", "decision_notes"])
    )

    blockers: list[str] = []
    if manifest is None:
        blockers.append("krd_contract_decision_manifest_missing")
    else:
        _append_mismatch(
            blockers,
            prefix="krd_contract_decision_manifest",
            field="report_date",
            expected=report_date,
            actual=actual_report_date,
        )
        _append_mismatch(
            blockers,
            prefix="krd_contract_decision_manifest",
            field="export_status",
            expected=expected_export_status,
            actual=actual_export_status,
        )
        _append_mismatch(
            blockers,
            prefix="krd_contract_decision_manifest",
            field="remap_tenor_count",
            expected=expected_remap_tenor_count,
            actual=actual_remap_tenor_count,
        )
        _append_mismatch(
            blockers,
            prefix="krd_contract_decision_manifest",
            field="nonzero_dv01_rows",
            expected=expected_nonzero_dv01_rows,
            actual=actual_nonzero_dv01_rows,
        )
        _append_mismatch(
            blockers,
            prefix="krd_contract_decision_manifest",
            field="dv01_sum",
            expected=expected_dv01_sum,
            actual=actual_dv01_sum,
        )
        _append_mismatch(
            blockers,
            prefix="krd_contract_decision_manifest",
            field="generated_owner_fields_must_be_blank",
            expected=expected_generated_owner_fields_must_be_blank,
            actual=actual_generated_owner_fields_must_be_blank,
        )
        _append_mismatch(
            blockers,
            prefix="krd_contract_decision_manifest",
            field="summary_csv_row_count",
            expected=expected_remap_tenor_count,
            actual=summary_row_count,
        )
        _append_mismatch(
            blockers,
            prefix="krd_contract_decision_manifest",
            field="detail_csv_row_count",
            expected=expected_nonzero_dv01_rows,
            actual=detail_row_count,
        )
        if not owner_fields_blank:
            blockers.append("krd_contract_decision_manifest_owner_decision_fields_not_blank")

    return {
        "name": "krd_contract_decision_manifest",
        "status": "consistent" if not blockers else "blocked",
        "path": path,
        "expected_report_date": report_date,
        "actual_report_date": actual_report_date,
        "expected_export_status": expected_export_status,
        "actual_export_status": actual_export_status,
        "expected_remap_tenor_count": expected_remap_tenor_count,
        "actual_remap_tenor_count": actual_remap_tenor_count,
        "expected_nonzero_dv01_rows": expected_nonzero_dv01_rows,
        "actual_nonzero_dv01_rows": actual_nonzero_dv01_rows,
        "expected_dv01_sum": expected_dv01_sum,
        "actual_dv01_sum": actual_dv01_sum,
        "expected_generated_owner_fields_must_be_blank": expected_generated_owner_fields_must_be_blank,
        "actual_generated_owner_fields_must_be_blank": actual_generated_owner_fields_must_be_blank,
        "csv_checks": {
            "summary_row_count": summary_row_count,
            "detail_row_count": detail_row_count,
            "owner_decision_fields_blank": owner_fields_blank,
        },
        "blockers": blockers,
    }


def maturity_manifest_consistency(
    *,
    scorecard: dict[str, object],
    report_date: str,
    docs_root: Path,
    root: Path,
) -> dict[str, object]:
    path = f"docs/portfolio/maturity-remediation/{report_date}/manifest.json"
    gates = scorecard["gates"]
    assert isinstance(gates, dict)
    maturity = gates["maturity_remediation"]
    assert isinstance(maturity, dict)
    bond_summary = maturity.get("bond_missing_maturity_summary", {})
    tyw_summary = maturity.get("tyw_liability_missing_maturity_summary", {})
    assert isinstance(bond_summary, dict)
    assert isinstance(tyw_summary, dict)

    expected_export_status = "clean" if maturity.get("status") == "clean" else "blocked"
    expected_bond_rows = int_value(bond_summary, "missing_maturity_rows")
    expected_tyw_rows = int_value(tyw_summary, "missing_maturity_rows")
    expected_bond_market_value = str_value(bond_summary, "missing_maturity_market_value")
    expected_tyw_principal = str_value(tyw_summary, "missing_maturity_principal")

    manifest = _manifest(path, docs_root=docs_root, root=root)
    export_summary = manifest.get("export_summary", {}) if isinstance(manifest, dict) else {}
    acceptance_criteria = manifest.get("acceptance_criteria", {}) if isinstance(manifest, dict) else {}
    assert isinstance(export_summary, dict)
    assert isinstance(acceptance_criteria, dict)
    actual_report_date = manifest.get("report_date") if isinstance(manifest, dict) else None
    actual_export_status = manifest.get("export_status") if isinstance(manifest, dict) else None
    actual_bond_rows = export_summary.get("bond_missing_maturity_rows")
    actual_tyw_rows = export_summary.get("tyw_liability_missing_maturity_rows")
    actual_bond_market_value = export_summary.get("bond_missing_maturity_market_value")
    actual_tyw_principal = export_summary.get("tyw_liability_missing_maturity_principal")
    expected_generated_owner_fields_must_be_blank = True
    actual_generated_owner_fields_must_be_blank = acceptance_criteria.get(
        "generated_owner_fields_must_be_blank"
    )
    bond_csv_path = f"docs/portfolio/maturity-remediation/{report_date}/bond_missing_maturity.csv"
    tyw_csv_path = f"docs/portfolio/maturity-remediation/{report_date}/tyw_liability_missing_maturity.csv"
    bond_csv_rows = _csv_rows(bond_csv_path, docs_root=docs_root, root=root)
    tyw_csv_rows = _csv_rows(tyw_csv_path, docs_root=docs_root, root=root)
    bond_csv_row_count = len(bond_csv_rows) if bond_csv_rows is not None else None
    tyw_csv_row_count = len(tyw_csv_rows) if tyw_csv_rows is not None else None
    owner_fields_blank = (
        bond_csv_rows is not None
        and tyw_csv_rows is not None
        and _fields_blank(bond_csv_rows, ["proposed_maturity_date", "owner_decision", "owner_comment"])
        and _fields_blank(tyw_csv_rows, ["proposed_maturity_date", "owner_decision", "owner_comment"])
    )

    blockers: list[str] = []
    if manifest is None:
        blockers.append("maturity_remediation_manifest_missing")
    else:
        _append_mismatch(
            blockers,
            prefix="maturity_remediation_manifest",
            field="report_date",
            expected=report_date,
            actual=actual_report_date,
        )
        _append_mismatch(
            blockers,
            prefix="maturity_remediation_manifest",
            field="export_status",
            expected=expected_export_status,
            actual=actual_export_status,
        )
        _append_mismatch(
            blockers,
            prefix="maturity_remediation_manifest",
            field="bond_missing_maturity_rows",
            expected=expected_bond_rows,
            actual=actual_bond_rows,
        )
        _append_mismatch(
            blockers,
            prefix="maturity_remediation_manifest",
            field="tyw_liability_missing_maturity_rows",
            expected=expected_tyw_rows,
            actual=actual_tyw_rows,
        )
        _append_mismatch(
            blockers,
            prefix="maturity_remediation_manifest",
            field="bond_missing_maturity_market_value",
            expected=expected_bond_market_value,
            actual=actual_bond_market_value,
        )
        _append_mismatch(
            blockers,
            prefix="maturity_remediation_manifest",
            field="tyw_liability_missing_maturity_principal",
            expected=expected_tyw_principal,
            actual=actual_tyw_principal,
        )
        _append_mismatch(
            blockers,
            prefix="maturity_remediation_manifest",
            field="generated_owner_fields_must_be_blank",
            expected=expected_generated_owner_fields_must_be_blank,
            actual=actual_generated_owner_fields_must_be_blank,
        )
        _append_mismatch(
            blockers,
            prefix="maturity_remediation_manifest",
            field="bond_csv_row_count",
            expected=expected_bond_rows,
            actual=bond_csv_row_count,
        )
        _append_mismatch(
            blockers,
            prefix="maturity_remediation_manifest",
            field="tyw_liability_csv_row_count",
            expected=expected_tyw_rows,
            actual=tyw_csv_row_count,
        )
        if not owner_fields_blank:
            blockers.append("maturity_remediation_manifest_owner_fields_not_blank")

    return {
        "name": "maturity_remediation_manifest",
        "status": "consistent" if not blockers else "blocked",
        "path": path,
        "expected_report_date": report_date,
        "actual_report_date": actual_report_date,
        "expected_export_status": expected_export_status,
        "actual_export_status": actual_export_status,
        "expected_bond_missing_maturity_rows": expected_bond_rows,
        "actual_bond_missing_maturity_rows": actual_bond_rows,
        "expected_tyw_liability_missing_maturity_rows": expected_tyw_rows,
        "actual_tyw_liability_missing_maturity_rows": actual_tyw_rows,
        "expected_bond_missing_maturity_market_value": expected_bond_market_value,
        "actual_bond_missing_maturity_market_value": actual_bond_market_value,
        "expected_tyw_liability_missing_maturity_principal": expected_tyw_principal,
        "actual_tyw_liability_missing_maturity_principal": actual_tyw_principal,
        "expected_generated_owner_fields_must_be_blank": expected_generated_owner_fields_must_be_blank,
        "actual_generated_owner_fields_must_be_blank": actual_generated_owner_fields_must_be_blank,
        "csv_checks": {
            "bond_missing_maturity_row_count": bond_csv_row_count,
            "tyw_liability_missing_maturity_row_count": tyw_csv_row_count,
            "owner_fields_blank": owner_fields_blank,
        },
        "blockers": blockers,
    }


def manifest_consistency_checks(
    *,
    scorecard: dict[str, object],
    report_date: str,
    docs_root: Path,
    root: Path,
) -> list[dict[str, object]]:
    return [
        krd_manifest_consistency(
            scorecard=scorecard,
            report_date=report_date,
            docs_root=docs_root,
            root=root,
        ),
        maturity_manifest_consistency(
            scorecard=scorecard,
            report_date=report_date,
            docs_root=docs_root,
            root=root,
        ),
    ]


def consistency_blockers(checks: list[dict[str, object]]) -> list[str]:
    blockers: list[str] = []
    for check in checks:
        check_blockers = check.get("blockers", [])
        if isinstance(check_blockers, list):
            blockers.extend(str(blocker) for blocker in check_blockers)
    return blockers


def generated_owner_fields_boundaries(checks: list[dict[str, object]]) -> dict[str, object]:
    return {
        str(item.get("name")): item.get("actual_generated_owner_fields_must_be_blank")
        for item in checks
        if isinstance(item, dict)
    }
