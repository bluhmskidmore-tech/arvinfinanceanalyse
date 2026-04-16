from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.schemas.research_run import ResearchRunManifest, ResearchWindow


RESEARCH_RUN_MANIFEST_STREAM = "research_run_manifest"


def build_research_run_manifest(
    *,
    run_kind: str,
    source_version: str,
    vendor_version: str,
    rule_version: str,
    parameters: dict[str, object] | None,
    window: dict[str, object],
    universe: dict[str, object] | None,
    code_version: str | None = None,
    code_ref: str | None = None,
) -> ResearchRunManifest:
    normalized_parameters = _normalize_json_value(parameters or {})
    normalized_universe = _normalize_json_value(universe or {})
    run_window = ResearchWindow.model_validate(window)
    created_at = datetime.now(timezone.utc)
    return ResearchRunManifest(
        run_id=f"research:{run_kind}:{created_at.isoformat()}:{uuid4().hex[:8]}",
        run_kind=run_kind,
        source_version=str(source_version or "").strip(),
        vendor_version=str(vendor_version or "").strip() or "vv_none",
        rule_version=str(rule_version or "").strip(),
        parameter_hash=_stable_parameter_hash(normalized_parameters),
        parameters=normalized_parameters,
        window=run_window,
        universe=normalized_universe,
        code_version=(str(code_version or "").strip() or None),
        code_ref=(str(code_ref or "").strip() or None),
        created_at=created_at,
    )


def record_research_run(
    *,
    repo: GovernanceRepository,
    manifest: ResearchRunManifest,
) -> None:
    repo.append(
        RESEARCH_RUN_MANIFEST_STREAM,
        manifest.model_dump(mode="json"),
    )


def _stable_parameter_hash(parameters: dict[str, object]) -> str:
    payload = json.dumps(
        parameters,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"ph_{digest}"


def _normalize_json_value(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): _normalize_json_value(inner)
            for key, inner in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_json_value(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc).isoformat()
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value
