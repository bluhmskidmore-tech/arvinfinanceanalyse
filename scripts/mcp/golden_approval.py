from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def golden_sample_readiness(
    bundle: dict[str, Any],
    contract_status: str,
    *,
    repo_root: Path,
    bundle_text: str,
) -> dict[str, Any]:
    anchors = list(bundle.get("golden_samples") or [])
    scope_status = _golden_sample_scope_status(anchors, contract_status, bundle_text)
    evidence = [_approval_evidence(str(anchor), repo_root) for anchor in anchors]
    return {
        "status": scope_status,
        "approval_status": _aggregate_approval_status(evidence),
        "anchors": anchors,
        "approval_evidence": evidence,
    }


def _golden_sample_scope_status(anchors: list[Any], contract_status: str, bundle_text: str) -> str:
    if not anchors:
        return "missing"
    if contract_status != "formal_or_governed":
        text = bundle_text.casefold()
        if "dto" in text or "page headline" in text or "page-level dto" in text:
            return "page_dto_only"
        return "supporting_or_fragment_only"
    return "formal_sample"


def _approval_evidence(anchor: str, repo_root: Path) -> dict[str, str]:
    sample_dir = _golden_sample_directory(anchor, repo_root)
    approval_path = sample_dir / "approval.md"
    status = "missing_approval_artifact"
    if approval_path.is_file():
        text = approval_path.read_text(encoding="utf-8")
        parsed_status = _markdown_field(text, "Status")
        status = parsed_status.casefold() if parsed_status else "invalid_approval_artifact"
        if status == "approved":
            required_signoff = (
                _markdown_field(text, "Owner"),
                _markdown_field(text, "Approver"),
                _markdown_field(text, "Approved at"),
            )
            if any(not value or value.casefold() in {"tbd", "pending"} for value in required_signoff):
                status = "invalid_approval_artifact"
    return {
        "sample_id": sample_dir.name,
        "approval_path": approval_path.relative_to(repo_root).as_posix(),
        "status": status,
    }


def _golden_sample_directory(anchor: str, repo_root: Path) -> Path:
    relative = Path(anchor)
    if len(relative.parts) == 1:
        relative = Path("tests") / "golden_samples" / relative
    path = repo_root / relative
    return path if path.suffix == "" else path.parent


def _markdown_field(text: str, field: str) -> str | None:
    match = re.search(rf"^- {re.escape(field)}:\s*`?([^`\r\n]+)`?\s*$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def _aggregate_approval_status(evidence: list[dict[str, str]]) -> str:
    if not evidence:
        return "missing"
    statuses = {item["status"] for item in evidence}
    if statuses == {"approved"}:
        return "approved"
    if statuses & {"missing_approval_artifact", "invalid_approval_artifact"}:
        return "invalid_or_missing_approval"
    if len(statuses) == 1:
        return next(iter(statuses))
    return "mixed_approval_status"