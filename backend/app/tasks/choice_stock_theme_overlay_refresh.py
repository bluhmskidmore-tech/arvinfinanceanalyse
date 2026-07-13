from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.tasks.choice_stock_materialize import (
    load_tushare_ths_current_overlay_members,
    select_tushare_ths_current_overlay_probe_stock_codes,
)
from backend.app.tasks.choice_stock_observation_manifest import (
    ensure_choice_stock_observation_manifest,
    resolve_latest_committed_choice_stock_observation,
)
from backend.app.tasks.stock_analysis_theme_overlay_archive import (
    archive_tushare_ths_current_overlay,
)

ThemeOverlayRefreshMode = Literal["off", "dry_run", "archive"]


def refresh_choice_stock_theme_overlay(
    *,
    mode: ThemeOverlayRefreshMode,
    duckdb_path: str | Path | None = None,
    governance_dir: str | Path | None = None,
    archive_root: str | Path | None = None,
    expected_report_date: str | None = None,
    run_id: str | None = None,
    source_version: str | None = None,
    vendor_version: str | None = None,
    membership_observed_at: datetime | None = None,
    tushare_client: object | None = None,
    load_members: Callable[[], Sequence[Mapping[str, object]]] | None = None,
) -> dict[str, object]:
    """Capture current THS memberships without writing them into PIT Choice tables."""
    if mode not in {"off", "dry_run", "archive"}:
        raise ValueError("mode must be one of: off, dry_run, archive")
    if mode == "off":
        return {
            "mode": "off",
            "status": "off",
            "observation_status": "not_checked",
            "observation_manifest_written": False,
            "overlay_status": "not_run",
        }

    resolved_duckdb_path = _required_path("duckdb_path", duckdb_path)
    resolved_report_date = _required_text(
        "expected_report_date",
        expected_report_date,
    )
    resolved_run_id = _required_text("run_id", run_id)
    resolved_source_version = _required_text("source_version", source_version)
    resolved_vendor_version = _required_text("vendor_version", vendor_version)
    resolved_governance_dir: Path | None = None
    resolved_archive_root: Path | None = None
    if mode == "archive":
        resolved_governance_dir = _required_path("governance_dir", governance_dir)
        resolved_archive_root = _required_path("archive_root", archive_root)
    observed_at = membership_observed_at or datetime.now(UTC)
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("membership_observed_at must be timezone-aware")
    observed_at = observed_at.astimezone(UTC)

    governance_repo: GovernanceRepository | None = None
    try:
        observation = resolve_latest_committed_choice_stock_observation(
            duckdb_path=resolved_duckdb_path,
            expected_report_date=resolved_report_date,
        )
        if mode == "archive":
            assert resolved_governance_dir is not None
            governance_repo = GovernanceRepository(base_dir=resolved_governance_dir)
            observation_manifest, manifest_written = ensure_choice_stock_observation_manifest(
                governance_repo=governance_repo,
                observation=observation,
                created_at=observed_at,
                publish=True,
            )
            observation_status = "ready"
        else:
            observation_manifest, manifest_written = ensure_choice_stock_observation_manifest(
                governance_repo=None,
                observation=observation,
                created_at=observed_at,
                publish=False,
            )
            observation_status = "validated_in_memory"
    except Exception as exc:
        return {
            "mode": mode,
            "status": "source_unavailable",
            "observation_status": "source_unavailable",
            "observation_manifest_written": False,
            "overlay_status": "not_run",
            "message": str(exc),
        }

    source_failure: Exception | None = None
    members: Sequence[Mapping[str, object]] = ()
    try:
        if load_members is not None:
            members = load_members()
        else:
            stock_codes = sorted({stock_code for _trade_date, stock_code in observation.daily_by_key})
            probe_codes = select_tushare_ths_current_overlay_probe_stock_codes(
                observation.daily_by_key,
                as_of_date=observation.report_date,
                stock_codes=stock_codes,
            )
            members = (
                load_tushare_ths_current_overlay_members(
                    tushare_client,
                    as_of_date=observation.report_date,
                    stock_codes=probe_codes,
                )
                if probe_codes
                else ()
            )
    except Exception as exc:
        source_failure = exc

    def captured_members() -> Sequence[Mapping[str, object]]:
        if source_failure is not None:
            raise source_failure
        return members

    try:
        archive_result = archive_tushare_ths_current_overlay(
            governance_dir=str(governance_dir or ""),
            archive_root=str(resolved_archive_root or ""),
            load_members=captured_members,
            run_id=resolved_run_id,
            source_version=resolved_source_version,
            vendor_version=resolved_vendor_version,
            membership_observed_at=observed_at,
            dry_run=mode == "dry_run",
            governance_repo=governance_repo,
            observation_manifest_override=(observation_manifest if mode == "dry_run" else None),
            expected_observation_manifest=(observation_manifest if mode == "archive" else None),
        )
    except Exception as exc:
        failure_status = "archive_failed" if mode == "archive" else "dry_run_failed"
        return {
            "mode": mode,
            "status": failure_status,
            "observation_status": observation_status,
            "observation_manifest_written": manifest_written,
            "overlay_status": failure_status,
            "message": str(exc),
        }
    overlay_payload = archive_result.model_dump(mode="json")
    return {
        "mode": mode,
        "status": archive_result.status,
        "observation_status": observation_status,
        "observation_manifest_written": manifest_written,
        "overlay_status": archive_result.status,
        **{
            key: value
            for key, value in overlay_payload.items()
            if key not in {"status", "observation_cache_key", "cache_key"}
        },
    }


def _required_text(field_name: str, value: object) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} must not be blank")
    return text


def _required_path(field_name: str, value: object) -> Path:
    return Path(_required_text(field_name, value))
