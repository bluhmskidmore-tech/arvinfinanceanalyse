from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path

from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.repositories.stock_analysis_theme_overlay_archive_repo import (
    StockAnalysisThemeOverlayArchiveRepository,
)
from backend.app.schemas.materialize import CacheManifestRecord
from backend.app.schemas.stock_analysis_theme_overlay import (
    ThemeOverlayArchiveResult,
    ThemeOverlayMember,
    ThemeOverlayObservationAnchor,
    build_theme_overlay_archive_document,
    utc_datetime_text,
)
from backend.app.tasks.choice_stock_observation_manifest import (
    ChoiceStockObservationManifestChangedError,
    choice_stock_observation_manifest_guard,
    require_exact_choice_stock_observation_manifest,
)

CHOICE_STOCK_OBSERVATION_CACHE_KEY = "choice_stock.history_and_factor_snapshot"
THEME_OVERLAY_CACHE_KEY = "stock-analysis.theme-overlay.tushare-ths-current"
THEME_OVERLAY_CACHE_VERSION = "stock_analysis_theme_overlay_v1"
RULE_VERSION = "rv_stock_analysis_theme_overlay_archive_v1"


def archive_tushare_ths_current_overlay(
    *,
    governance_dir: str | Path,
    archive_root: str | Path,
    load_members: Callable[[], Sequence[Mapping[str, object]]],
    run_id: str,
    source_version: str,
    vendor_version: str,
    membership_observed_at: datetime | None = None,
    dry_run: bool = False,
    governance_repo: GovernanceRepository | None = None,
    observation_manifest_override: Mapping[str, object] | None = None,
    expected_observation_manifest: Mapping[str, object] | None = None,
) -> ThemeOverlayArchiveResult:
    run_id = _required_text("run_id", run_id)
    source_version = _required_text("source_version", source_version)
    vendor_version = _required_text("vendor_version", vendor_version)
    observed_at_value = membership_observed_at or datetime.now(UTC)
    if observed_at_value.tzinfo is None or observed_at_value.utcoffset() is None:
        raise ValueError("membership_observed_at must be timezone-aware")
    observed_at = observed_at_value.astimezone(UTC)

    if observation_manifest_override is not None and not dry_run:
        raise ValueError("observation_manifest_override is allowed only for dry_run")

    if observation_manifest_override is not None:
        observation_manifest = dict(observation_manifest_override)
    elif governance_repo is None:
        governance_path = Path(governance_dir)
        if not governance_path.is_dir():
            return _result(
                status="source_unavailable",
                run_id=run_id,
                membership_observed_at=observed_at,
                message=(
                    "Choice-stock observation governance directory is unavailable; "
                    f"expected manifest key {CHOICE_STOCK_OBSERVATION_CACHE_KEY}."
                ),
            )
        governance_repo = GovernanceRepository(base_dir=governance_dir)
        observation_manifest = governance_repo.read_latest_manifest(CHOICE_STOCK_OBSERVATION_CACHE_KEY)
    else:
        observation_manifest = governance_repo.read_latest_manifest(CHOICE_STOCK_OBSERVATION_CACHE_KEY)
    if observation_manifest is None:
        return _result(
            status="source_unavailable",
            run_id=run_id,
            membership_observed_at=observed_at,
            message=f"Missing cache manifest for {CHOICE_STOCK_OBSERVATION_CACHE_KEY}.",
        )

    try:
        anchor = _observation_anchor(
            observation_manifest,
            membership_observed_at=observed_at,
        )
    except (KeyError, TypeError, ValueError) as exc:
        return _result(
            status="source_unavailable",
            run_id=run_id,
            membership_observed_at=observed_at,
            message=f"Invalid choice-stock observation manifest: {exc}",
        )
    if anchor.report_date > observed_at.date():
        return _result(
            status="source_unavailable",
            run_id=run_id,
            membership_observed_at=observed_at,
            message=(
                f"Observation manifest report_date {anchor.report_date.isoformat()} is after membership_observed_at."
            ),
        )
    expected_anchor: ThemeOverlayObservationAnchor | None = None
    if expected_observation_manifest is not None:
        try:
            require_exact_choice_stock_observation_manifest(
                actual_manifest=observation_manifest,
                expected_manifest=expected_observation_manifest,
            )
        except ChoiceStockObservationManifestChangedError as exc:
            return _result(
                status="source_unavailable",
                run_id=run_id,
                membership_observed_at=observed_at,
                observed_market_date=anchor.report_date,
                message=(f"Choice-stock observation manifest changed before theme overlay archive: {exc}"),
            )
        expected_anchor = anchor
    commit_expected_manifest: Mapping[str, object] | None = None
    if not dry_run:
        expected_anchor = anchor
        commit_expected_manifest = dict(observation_manifest)

    try:
        members = _canonical_members(load_members())
    except Exception as exc:
        return _result(
            status="source_failed",
            run_id=run_id,
            membership_observed_at=observed_at,
            observed_market_date=anchor.report_date,
            message=f"Tushare THS current-membership source failed: {exc}",
        )
    if not members:
        return _result(
            status="empty_source",
            run_id=run_id,
            membership_observed_at=observed_at,
            observed_market_date=anchor.report_date,
            message="Tushare THS current-membership source returned no members.",
        )
    if not dry_run and expected_anchor is not None and governance_repo is not None:
        refreshed_manifest = governance_repo.read_latest_manifest(CHOICE_STOCK_OBSERVATION_CACHE_KEY)
        try:
            if refreshed_manifest is None:
                raise ValueError("latest observation manifest is missing")
            refreshed_anchor = _observation_anchor(
                refreshed_manifest,
                membership_observed_at=observed_at,
            )
        except (KeyError, TypeError, ValueError) as exc:
            return _result(
                status="source_unavailable",
                run_id=run_id,
                membership_observed_at=observed_at,
                observed_market_date=anchor.report_date,
                message=(f"Choice-stock observation anchor became invalid during theme overlay source load: {exc}"),
            )
        if refreshed_anchor != expected_anchor:
            return _result(
                status="source_unavailable",
                run_id=run_id,
                membership_observed_at=observed_at,
                observed_market_date=anchor.report_date,
                message="Choice-stock observation anchor changed during theme overlay source load.",
            )

    document = build_theme_overlay_archive_document(
        members=members,
        observation_anchor=anchor,
        membership_observed_at=observed_at,
        run_id=run_id,
        source_version=source_version,
        vendor_version=vendor_version,
        rule_version=RULE_VERSION,
    )
    if dry_run:
        return _result(
            status="dry_run",
            run_id=run_id,
            membership_observed_at=observed_at,
            observed_market_date=anchor.report_date,
            member_count=len(document.members),
            content_hash=document.content_hash,
            lineage_hash=document.lineage_hash,
        )

    manifest = CacheManifestRecord(
        cache_key=THEME_OVERLAY_CACHE_KEY,
        cache_version=THEME_OVERLAY_CACHE_VERSION,
        source_version=source_version,
        vendor_version=vendor_version,
        rule_version=RULE_VERSION,
        basis="observational_current_overlay",
        module_name="stock_analysis_theme_overlay",
        result_kind_family="stock-analysis-theme-overlay",
        run_id=run_id,
        report_date=anchor.report_date.isoformat(),
        input_sources=[
            "tushare.ths_index",
            "tushare.ths_member",
            "choice_stock_daily_observation",
        ],
        fact_tables=[],
        lineage={
            "source_kind": document.source_kind,
            "membership_observed_at": utc_datetime_text(document.membership_observed_at),
            "observed_market_date": document.observed_market_date.isoformat(),
            "point_in_time": False,
            "historical_use_allowed": False,
            "member_count": len(document.members),
            "content_hash": document.content_hash,
            "lineage_hash": document.lineage_hash,
            "observation_anchor": document.observation_anchor.model_dump(mode="json"),
        },
        created_at=utc_datetime_text(observed_at),
    ).model_dump()
    if governance_repo is None:
        raise ValueError("governance_repo is required for a non-dry-run archive")
    assert commit_expected_manifest is not None
    try:
        archived_path = StockAnalysisThemeOverlayArchiveRepository(
            archive_root=Path(archive_root),
            governance_repo=governance_repo,
        ).archive(
            document=document,
            manifest_payload=manifest,
            commit_guard=lambda: choice_stock_observation_manifest_guard(
                governance_repo=governance_repo,
                expected_manifest=commit_expected_manifest,
            ),
        )
    except ChoiceStockObservationManifestChangedError as exc:
        return _result(
            status="source_unavailable",
            run_id=run_id,
            membership_observed_at=observed_at,
            observed_market_date=anchor.report_date,
            message=(f"Choice-stock observation manifest changed before overlay commit: {exc}"),
        )
    return _result(
        status="completed",
        run_id=run_id,
        membership_observed_at=observed_at,
        observed_market_date=anchor.report_date,
        member_count=len(document.members),
        content_hash=document.content_hash,
        lineage_hash=document.lineage_hash,
        archived_path=str(archived_path),
        manifest_written=True,
    )


def _result(
    *,
    status: str,
    run_id: str,
    membership_observed_at: datetime,
    observed_market_date: date | None = None,
    member_count: int = 0,
    content_hash: str | None = None,
    lineage_hash: str | None = None,
    archived_path: str | None = None,
    manifest_written: bool = False,
    message: str | None = None,
) -> ThemeOverlayArchiveResult:
    return ThemeOverlayArchiveResult(
        status=status,
        run_id=run_id,
        observation_cache_key=CHOICE_STOCK_OBSERVATION_CACHE_KEY,
        cache_key=THEME_OVERLAY_CACHE_KEY,
        membership_observed_at=membership_observed_at,
        observed_market_date=observed_market_date,
        member_count=member_count,
        content_hash=content_hash,
        lineage_hash=lineage_hash,
        archived_path=archived_path,
        manifest_written=manifest_written,
        message=message,
    )


def _canonical_members(
    members: Sequence[Mapping[str, object]],
) -> tuple[ThemeOverlayMember, ...]:
    allowed_fields = {"stock_code", "stock_name", "theme_key", "theme_name"}
    merged: dict[tuple[str, str], dict[str, str | None]] = {}
    for index, member in enumerate(members):
        if not isinstance(member, Mapping):
            raise ValueError(f"member[{index}] must be a mapping")
        unexpected_fields = set(member) - allowed_fields
        if unexpected_fields:
            raise ValueError(f"member[{index}] has unexpected fields: {sorted(unexpected_fields)}")
        stock_code = _required_text("stock_code", member.get("stock_code")).upper()
        theme_key = _required_text("theme_key", member.get("theme_key")).upper()
        identity = (stock_code, theme_key)
        incoming = {
            "stock_name": _optional_text(member.get("stock_name")),
            "theme_name": _optional_text(member.get("theme_name")),
        }
        current = merged.setdefault(
            identity,
            {"stock_name": None, "theme_name": None},
        )
        for label_field, incoming_value in incoming.items():
            current_value = current[label_field]
            if current_value and incoming_value and current_value != incoming_value:
                raise ValueError(f"{label_field} conflict for stock_code={stock_code}, theme_key={theme_key}")
            current[label_field] = current_value or incoming_value

    return tuple(
        ThemeOverlayMember(
            stock_code=stock_code,
            stock_name=labels["stock_name"],
            theme_key=theme_key,
            theme_name=labels["theme_name"] or "",
        )
        for (stock_code, theme_key), labels in sorted(merged.items())
    )


def _observation_anchor(
    manifest: Mapping[str, object],
    *,
    membership_observed_at: datetime,
) -> ThemeOverlayObservationAnchor:
    fact_tables = manifest.get("fact_tables")
    if not isinstance(fact_tables, list) or "choice_stock_daily_observation" not in fact_tables:
        raise ValueError("Observation manifest does not govern choice_stock_daily_observation.")
    created_at = _manifest_created_at(
        manifest.get("created_at"),
        membership_observed_at=membership_observed_at,
    )
    return ThemeOverlayObservationAnchor(
        cache_key=CHOICE_STOCK_OBSERVATION_CACHE_KEY,
        report_date=date.fromisoformat(str(manifest["report_date"])),
        created_at=created_at,
        source_version=_required_text("source_version", manifest["source_version"]),
        vendor_version=_required_text("vendor_version", manifest["vendor_version"]),
        rule_version=_required_text("rule_version", manifest["rule_version"]),
        run_id=str(manifest.get("run_id") or "") or None,
    )


def _manifest_created_at(
    value: object,
    *,
    membership_observed_at: datetime,
) -> datetime:
    text = _required_text("created_at", value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("created_at must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("created_at must be timezone-aware")
    normalized = parsed.astimezone(UTC)
    if normalized > membership_observed_at:
        raise ValueError("created_at must not be after membership_observed_at")
    return normalized


def _required_text(field_name: str, value: object) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} must not be blank")
    return text


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None
