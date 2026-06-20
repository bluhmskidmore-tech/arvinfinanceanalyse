from __future__ import annotations

from pathlib import Path

from scripts.check_portfolio_home_business_owner_approval import DEFAULT_TEMPLATE
from scripts.portfolio_home_krd_contract_decision_export import (
    DEFAULT_OUTPUT_DIR as DEFAULT_KRD_EXPORT_DIR,
    build_current_status as build_krd_export_current_status,
)
from scripts.portfolio_home_manifest_consistency import resolve_docs_path
from scripts.portfolio_home_maturity_remediation_export import (
    DEFAULT_OUTPUT_DIR as DEFAULT_MATURITY_EXPORT_DIR,
    build_current_status as build_maturity_export_current_status,
)


ROOT = Path(__file__).resolve().parents[1]


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def append_unique(target: list[str], values: list[object]) -> None:
    for value in values:
        item = str(value)
        if item not in target:
            target.append(item)


def artifact_missing_blocker(artifact: str) -> str:
    name = Path(artifact.replace("\\", "/")).name
    if name.endswith(".csv"):
        return f"{name[:-4]}_csv_missing"
    if name.endswith(".json"):
        return f"{name[:-5]}_json_missing"
    if name.endswith(".md"):
        return f"{name[:-3]}_md_missing"
    return f"{name}_missing"


def required_exact_bucket_schema(summary: dict[str, object]) -> bool:
    exact = _dict(summary.get("exact_bucket_schema_evidence"))
    return exact.get("status") != "not_required"


def required_nearest_bucket_approval(summary: dict[str, object]) -> bool:
    nearest = _dict(summary.get("nearest_bucket_approval_evidence"))
    return nearest.get("status") != "not_required"


def required_maturity_scoped_exclusion(summary: dict[str, object]) -> bool:
    scoped = _dict(summary.get("maturity_scoped_exclusion_evidence"))
    return scoped.get("status") != "not_required"


def is_exact_bucket_schema_artifact(artifact: str) -> bool:
    return artifact.replace("\\", "/").endswith("/exact_bucket_schema_evidence.json")


def is_nearest_bucket_approval_artifact(artifact: str) -> bool:
    return artifact.replace("\\", "/").endswith("/nearest_bucket_approval_evidence.json")


def is_maturity_scoped_exclusion_artifact(artifact: str) -> bool:
    return artifact.replace("\\", "/").endswith("/maturity_scoped_exclusion_evidence.json")


def artifact_required_now(artifact: str, summary: dict[str, object]) -> bool:
    if is_exact_bucket_schema_artifact(artifact):
        return required_exact_bucket_schema(summary)
    if is_nearest_bucket_approval_artifact(artifact):
        return required_nearest_bucket_approval(summary)
    if is_maturity_scoped_exclusion_artifact(artifact):
        return required_maturity_scoped_exclusion(summary)
    return True


def artifact_row(
    *,
    artifact: str,
    docs_root: Path,
    required_now: bool,
    current_blockers: list[str],
) -> dict[str, object]:
    path = resolve_docs_path(artifact, docs_root, ROOT)
    exists = path.exists()
    blockers: list[str] = []
    if required_now and not exists:
        blockers = list(current_blockers) if current_blockers else [artifact_missing_blocker(artifact)]
    return {
        "artifact": artifact,
        "status": "not_required" if not required_now else "present" if exists else "missing",
        "exists": exists,
        "required_now": required_now,
        "blockers": blockers,
    }


def artifact_paths(closure_matrix: list[object]) -> list[str]:
    paths: list[str] = []
    for row in closure_matrix:
        if not isinstance(row, dict):
            continue
        artifacts = row.get("decision_artifacts", [])
        if not isinstance(artifacts, list):
            continue
        for artifact in artifacts:
            path = str(artifact)
            if path and path not in paths:
                paths.append(path)
    return paths


def artifact_presence_report(
    *,
    docs_root: Path,
    closure_matrix: list[object],
    artifact_current_summary: dict[str, object],
    report_date: str | None = None,
) -> dict[str, object]:
    summary = {key: _dict(value) for key, value in artifact_current_summary.items()}
    blockers: list[str] = []
    for key in (
        "krd",
        "maturity",
        "business_owner_approval_template",
        "exact_bucket_schema_evidence",
        "nearest_bucket_approval_evidence",
        "maturity_scoped_exclusion_evidence",
    ):
        status = summary.get(key, {})
        append_unique(blockers, _list(status.get("current_blockers")))

    artifact_rows: list[dict[str, object]] = []
    for artifact in artifact_paths(closure_matrix):
        required_now = artifact_required_now(artifact, summary)
        exact_blockers = (
            _list(summary.get("exact_bucket_schema_evidence", {}).get("current_blockers"))
            if is_exact_bucket_schema_artifact(artifact)
            else []
        )
        nearest_blockers = (
            _list(summary.get("nearest_bucket_approval_evidence", {}).get("current_blockers"))
            if is_nearest_bucket_approval_artifact(artifact)
            else []
        )
        scoped_blockers = (
            _list(summary.get("maturity_scoped_exclusion_evidence", {}).get("current_blockers"))
            if is_maturity_scoped_exclusion_artifact(artifact)
            else []
        )
        row = artifact_row(
            artifact=artifact,
            docs_root=docs_root,
            required_now=required_now,
            current_blockers=[
                str(blocker)
                for blocker in [*exact_blockers, *nearest_blockers, *scoped_blockers]
            ],
        )
        append_unique(blockers, _list(row.get("blockers")))
        artifact_rows.append(row)

    current = not blockers
    return {
        "status": "current" if current else "stale",
        "current": current,
        "blockers": blockers,
        "artifact_current_summary": artifact_current_summary,
        "artifact_rows": artifact_rows,
    }


def summary_from_export_status(status: dict[str, object]) -> dict[str, object]:
    blockers = _list(status.get("current_blockers"))
    return {
        "status": status.get("status"),
        "current": status.get("current"),
        "current_blockers": blockers,
    }


def template_presence(template_path: Path) -> dict[str, object]:
    exists = template_path.exists()
    return {
        "status": "present" if exists else "missing",
        "current": exists,
        "current_blockers": [] if exists else ["business_owner_approval_template_missing"],
    }


def exact_bucket_schema_presence(intake_summary: dict[str, object]) -> dict[str, object]:
    exact = _dict(intake_summary.get("exact_bucket_schema_evidence"))
    status = exact.get("status")
    blockers = _list(exact.get("blockers"))
    if status == "not_required":
        return {
            "status": "not_required",
            "current": True,
            "current_blockers": [],
        }
    return {
        "status": status,
        "current": bool(exact.get("valid")) and not blockers,
        "current_blockers": blockers,
    }


def nearest_bucket_approval_presence(intake_summary: dict[str, object]) -> dict[str, object]:
    nearest = _dict(intake_summary.get("nearest_bucket_approval_evidence"))
    status = nearest.get("status")
    blockers = _list(nearest.get("blockers"))
    if status == "not_required":
        return {
            "status": "not_required",
            "current": True,
            "current_blockers": [],
        }
    return {
        "status": status,
        "current": bool(nearest.get("valid")) and not blockers,
        "current_blockers": blockers,
    }


def maturity_scoped_exclusion_presence(intake_summary: dict[str, object]) -> dict[str, object]:
    scoped = _dict(intake_summary.get("maturity_scoped_exclusion_evidence"))
    status = scoped.get("status")
    blockers = _list(scoped.get("blockers"))
    if status == "not_required":
        return {
            "status": "not_required",
            "current": True,
            "current_blockers": [],
        }
    return {
        "status": status,
        "current": bool(scoped.get("valid")) and not blockers,
        "current_blockers": blockers,
    }


def artifact_current_summary(
    *,
    duckdb_path: Path,
    report_date: str,
    template_path: Path = DEFAULT_TEMPLATE,
    docs_root: Path,
    intake_summary: dict[str, object],
) -> dict[str, object]:
    krd_status = build_krd_export_current_status(
        duckdb_path=duckdb_path,
        report_date=report_date,
        output_dir=docs_root / DEFAULT_KRD_EXPORT_DIR.relative_to(ROOT / "docs"),
    )
    maturity_status = build_maturity_export_current_status(
        duckdb_path=duckdb_path,
        report_date=report_date,
        output_dir=docs_root / DEFAULT_MATURITY_EXPORT_DIR.relative_to(ROOT / "docs"),
    )
    krd_summary = summary_from_export_status(krd_status)
    maturity_summary = summary_from_export_status(maturity_status)
    if not krd_summary.get("current"):
        krd_blockers = _list(krd_summary["current_blockers"])
        append_unique(krd_blockers, ["krd_contract_decision_export_stale"])
        krd_summary["current_blockers"] = krd_blockers
    if not maturity_summary.get("current"):
        maturity_blockers = _list(maturity_summary["current_blockers"])
        append_unique(maturity_blockers, ["maturity_remediation_export_stale"])
        maturity_summary["current_blockers"] = maturity_blockers

    return {
        "krd": krd_summary,
        "maturity": maturity_summary,
        "business_owner_approval_template": template_presence(template_path),
        "exact_bucket_schema_evidence": exact_bucket_schema_presence(intake_summary),
        "nearest_bucket_approval_evidence": nearest_bucket_approval_presence(
            intake_summary,
        ),
        "maturity_scoped_exclusion_evidence": maturity_scoped_exclusion_presence(
            intake_summary,
        ),
    }


def closure_artifact_presence_summary(report: dict[str, object]) -> dict[str, object]:
    summary = report.get("artifact_current_summary", {})
    assert isinstance(summary, dict)
    return {
        "status": report.get("status"),
        "current": report.get("current"),
        "blockers": report.get("blockers", []),
        "artifact_current_summary": summary,
    }
