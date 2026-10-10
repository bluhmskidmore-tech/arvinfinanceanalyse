from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

from backend.app.schemas.release_control import canonical_sha256

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REGISTRY_PATH = ROOT / "config" / "exact_numeric_compat_registry.v1.json"
ALLOWED_EXCEPTION_RULES = frozenset(
    {"raw_text_number_cast", "decimal_like", "literal_div_1e8"}
)
_PLACEHOLDER_VALUES = frozenset({"pending", "tbd", "todo", "unknown", "n/a", "na"})
_REGISTRY_FIELDS = frozenset(
    {
        "schema_version",
        "policy_version",
        "release_eligible",
        "controlled_pages",
        "controlled_paths",
        "active_exceptions",
        "pending_migrations",
    }
)


def _normalized_repo_relative_path(value: Any, *, repo_root: Path) -> str:
    raw = str(value or "").strip().replace("\\", "/")
    if not raw:
        raise ValueError("path is required")
    candidate = Path(raw)
    if candidate.is_absolute():
        raise ValueError(f"path must be repository-relative: {raw}")
    if any(part in ("", ".", "..") for part in candidate.parts):
        raise ValueError(f"path must be normalized: {raw}")
    normalized = candidate.as_posix()
    absolute = (repo_root / candidate).resolve(strict=False)
    repo_absolute = repo_root.resolve(strict=False)
    if absolute != repo_absolute and repo_absolute not in absolute.parents:
        raise ValueError(f"path escapes repository: {raw}")
    if not absolute.exists():
        raise ValueError(f"path does not exist: {raw}")
    return normalized


def _normalized_page(value: Any, *, field_name: str) -> str:
    page = str(value or "").strip()
    if not page:
        raise ValueError(f"{field_name} must be non-empty")
    return page


def _normalized_count(value: Any, *, field_name: str) -> int:
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _validate_exception_entry(
    entry: Mapping[str, Any],
    *,
    controlled_pages: set[str],
    controlled_paths: set[str],
    require_owner_and_expiry: bool,
    today: date,
) -> dict[str, Any]:
    if not isinstance(entry, Mapping):
        raise ValueError("exception entry must be an object")
    allowed_fields = {"path", "page", "rule", "count", "reason"}
    if require_owner_and_expiry:
        allowed_fields.update({"owner", "expires_on"})
    unexpected_fields = sorted(set(entry) - allowed_fields)
    if unexpected_fields:
        raise ValueError(
            f"exception entry has unsupported fields: {unexpected_fields}"
        )
    page = _normalized_page(entry.get("page"), field_name="page")
    if page not in controlled_pages:
        raise ValueError(f"exception page is not controlled: {page}")
    path = str(entry.get("path") or "")
    if path not in controlled_paths:
        raise ValueError(f"exception path is not controlled: {path}")
    rule = str(entry.get("rule") or "").strip()
    if rule not in ALLOWED_EXCEPTION_RULES:
        raise ValueError(f"exception rule is invalid: {rule}")
    reason = str(entry.get("reason") or "").strip()
    if not reason:
        raise ValueError("exception reason is required")
    normalized: dict[str, Any] = {
        "path": path,
        "page": page,
        "rule": rule,
        "count": _normalized_count(entry.get("count"), field_name="count"),
        "reason": reason,
    }
    if require_owner_and_expiry:
        owner = str(entry.get("owner") or "").strip()
        if not owner:
            raise ValueError("active exception owner is required")
        if owner.casefold() in _PLACEHOLDER_VALUES:
            raise ValueError("active exception owner must not be a placeholder")
        expires_on = str(entry.get("expires_on") or "").strip()
        if not expires_on:
            raise ValueError("active exception expires_on is required")
        try:
            expiry_date = date.fromisoformat(expires_on)
        except ValueError as exc:
            raise ValueError("active exception expires_on must be ISO-8601") from exc
        if expiry_date < today:
            raise ValueError(f"active exception expired on {expires_on}")
        normalized["owner"] = owner
        normalized["expires_on"] = expires_on
    return normalized


def load_exact_numeric_compat_registry(
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
) -> dict[str, Any]:
    path = Path(registry_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    repo_root = ROOT

    if not isinstance(payload, Mapping):
        raise ValueError("exact numeric compat registry must be an object")
    unexpected_fields = sorted(set(payload) - _REGISTRY_FIELDS)
    if unexpected_fields:
        raise ValueError(
            f"exact numeric compat registry has unsupported fields: {unexpected_fields}"
        )

    if payload.get("schema_version") != "exact-numeric-compat-registry/v1":
        raise ValueError("unsupported exact numeric compat registry schema_version")

    policy_version = str(payload.get("policy_version") or "").strip()
    if not policy_version:
        raise ValueError("policy_version is required")

    release_eligible = payload.get("release_eligible")
    if not isinstance(release_eligible, bool):
        raise ValueError("release_eligible must be a boolean")

    controlled_pages_raw = payload.get("controlled_pages")
    if not isinstance(controlled_pages_raw, list) or not controlled_pages_raw:
        raise ValueError("controlled_pages must be a non-empty list")
    controlled_pages = [
        _normalized_page(page, field_name="controlled_pages[]")
        for page in controlled_pages_raw
    ]
    if len(controlled_pages) != len(set(controlled_pages)):
        raise ValueError("controlled_pages must be unique")

    controlled_paths_raw = payload.get("controlled_paths")
    if not isinstance(controlled_paths_raw, list) or not controlled_paths_raw:
        raise ValueError("controlled_paths must be a non-empty list")
    controlled_paths = [
        _normalized_repo_relative_path(path_value, repo_root=repo_root)
        for path_value in controlled_paths_raw
    ]
    if len(controlled_paths) != len(set(controlled_paths)):
        raise ValueError("controlled_paths must be unique")

    today = date.today()
    controlled_pages_set = set(controlled_pages)
    controlled_paths_set = set(controlled_paths)

    active_raw = payload.get("active_exceptions")
    if not isinstance(active_raw, list):
        raise ValueError("active_exceptions must be a list")
    active_exceptions = [
        _validate_exception_entry(
            entry,
            controlled_pages=controlled_pages_set,
            controlled_paths=controlled_paths_set,
            require_owner_and_expiry=True,
            today=today,
        )
        for entry in active_raw
    ]

    pending_raw = payload.get("pending_migrations")
    if not isinstance(pending_raw, list):
        raise ValueError("pending_migrations must be a list")
    pending_migrations = [
        _validate_exception_entry(
            entry,
            controlled_pages=controlled_pages_set,
            controlled_paths=controlled_paths_set,
            require_owner_and_expiry=False,
            today=today,
        )
        for entry in pending_raw
    ]

    exception_keys = [
        (entry["path"], entry["rule"])
        for entry in [*active_exceptions, *pending_migrations]
    ]
    if len(exception_keys) != len(set(exception_keys)):
        raise ValueError("compat registry path/rule entries must be unique")

    if pending_migrations and release_eligible:
        raise ValueError(
            "release_eligible must stay false while pending_migrations remain"
        )

    return {
        "schema_version": "exact-numeric-compat-registry/v1",
        "policy_version": policy_version,
        "release_eligible": release_eligible,
        "controlled_pages": controlled_pages,
        "controlled_paths": controlled_paths,
        "active_exceptions": active_exceptions,
        "pending_migrations": pending_migrations,
    }


def exact_numeric_compat_registry_sha256(
    registry: Mapping[str, Any] | None = None,
    *,
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
) -> str:
    payload = (
        load_exact_numeric_compat_registry(registry_path)
        if registry is None
        else dict(registry)
    )
    return canonical_sha256(payload)


def build_exact_numeric_policy_binding(
    registry: Mapping[str, Any],
    *,
    rehearsal_only: bool,
) -> dict[str, Any]:
    registry_sha256 = exact_numeric_compat_registry_sha256(registry)
    return {
        "policy_version": registry["policy_version"],
        "controlled_pages": list(registry["controlled_pages"]),
        "controlled_paths": list(registry["controlled_paths"]),
        "compat_registry_sha256": registry_sha256,
        "release_eligible": bool(registry["release_eligible"]),
        "rehearsal_only": rehearsal_only,
    }


def build_exact_numeric_policy(
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    *,
    rehearsal_only: bool = False,
) -> dict[str, Any]:
    registry = load_exact_numeric_compat_registry(registry_path)
    binding = build_exact_numeric_policy_binding(
        registry,
        rehearsal_only=rehearsal_only,
    )
    return {
        **binding,
        "policy_sha256": canonical_sha256(binding),
        "active_exception_count": len(registry["active_exceptions"]),
        "pending_migration_count": len(registry["pending_migrations"]),
    }
