from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from backend.app.schemas.materialize import CacheManifestRecord
from backend.app.schemas.stock_analysis_theme_overlay import (
    ThemeOverlayArchiveDocument,
    ThemeOverlayMember,
    ThemeOverlayObservationAnchor,
    canonical_theme_overlay_document_bytes,
)
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)

CHOICE_STOCK_OBSERVATION_CACHE_KEY = "choice_stock.history_and_factor_snapshot"
CHOICE_STOCK_OBSERVATION_CACHE_VERSION = "choice_stock_refresh_v1"
CHOICE_STOCK_OBSERVATION_RULE_VERSION = "rv_choice_stock_materialization_front_layer_v1"
THEME_OVERLAY_CACHE_KEY = "stock-analysis.theme-overlay.tushare-ths-current"
THEME_OVERLAY_CACHE_VERSION = "stock_analysis_theme_overlay_v1"
THEME_OVERLAY_RULE_VERSION = "rv_stock_analysis_theme_overlay_archive_v1"
BACKFILL_DISABLED_FINGERPRINT = hashlib.sha256(b"theme-overlay:backfill-disabled:v1").hexdigest()


@dataclass(frozen=True)
class ThemeOverlayManifestAccessor:
    base_dir: Path | str
    sql_dsn: str = ""
    backend_mode: str = "jsonl"

    def read_latest_manifest(
        self,
        cache_key: str,
        *,
        report_date: str | None = None,
    ) -> dict[str, object] | None:
        cache_key_text = str(cache_key or "").strip()
        if not cache_key_text:
            return None
        report_date_text = str(report_date or "").strip()
        backend_mode = str(self.backend_mode or "jsonl").strip() or "jsonl"
        if backend_mode not in {"jsonl", "sql-shadow", "sql-authority"}:
            raise ValueError(f"Unsupported governance backend mode: {backend_mode}")

        if backend_mode != "sql-authority":
            target = Path(self.base_dir).resolve() / "cache_manifest.jsonl"
            if not target.is_file():
                return None
            stat = target.stat()
            signature = (stat.st_mtime_ns, stat.st_size)
            latest_by_key, latest_by_key_date = _cached_jsonl_manifest_index(
                str(target),
                *signature,
            )
            stat_after = target.stat()
            if (stat_after.st_mtime_ns, stat_after.st_size) != signature:
                raise ValueError("cache manifest changed during indexed read")
            serialized = (
                latest_by_key_date.get((cache_key_text, report_date_text))
                if report_date_text
                else latest_by_key.get(cache_key_text)
            )
            if serialized is None:
                return None
            row = json.loads(serialized)
            if not isinstance(row, dict):
                raise ValueError("cache manifest row must be an object")
            return row
        else:
            sql_dsn = str(self.sql_dsn or "").strip()
            if not sql_dsn:
                raise ValueError("sql_dsn is required for sql-authority reads")
            if sql_dsn.startswith("postgresql://"):
                sql_dsn = "postgresql+psycopg://" + sql_dsn[len("postgresql://") :]
            url = make_url(sql_dsn)
            sqlite_path: Path | None = None
            sqlite_signature: tuple[int, int] | None = None
            if url.get_backend_name() == "sqlite":
                database = str(url.database or "").strip()
                if not database or database == ":memory:":
                    raise ValueError("SQLite sql-authority requires a file-backed database")
                sqlite_path = Path(database).resolve()
                if not sqlite_path.is_file():
                    return None
                wal_path = Path(f"{sqlite_path}-wal")
                if wal_path.is_file() and wal_path.stat().st_size > 0:
                    raise ValueError("uncheckpointed SQLite WAL prevents immutable authority read")
                sqlite_stat = sqlite_path.stat()
                sqlite_signature = (sqlite_stat.st_mtime_ns, sqlite_stat.st_size)
                immutable_uri = f"{sqlite_path.as_uri()}?mode=ro&immutable=1"

                def sqlite_read_only_connection() -> sqlite3.Connection:
                    return sqlite3.connect(immutable_uri, uri=True)

                engine = create_engine(
                    "sqlite://",
                    creator=sqlite_read_only_connection,
                    future=True,
                    poolclass=NullPool,
                )
            else:
                engine = create_engine(sql_dsn, future=True, poolclass=NullPool)
            try:
                with engine.connect() as connection:
                    payload_rows = connection.execute(
                        text(
                            "select cache_key, payload_json from cache_manifest "
                            "where cache_key = :cache_key order by row_id desc"
                        ),
                        {"cache_key": cache_key_text},
                    ).fetchall()
            finally:
                engine.dispose()
            if sqlite_path is not None and sqlite_signature is not None:
                wal_path = Path(f"{sqlite_path}-wal")
                sqlite_stat = sqlite_path.stat()
                if (sqlite_stat.st_mtime_ns, sqlite_stat.st_size) != sqlite_signature:
                    raise ValueError("SQLite authority changed during immutable read")
                if wal_path.is_file() and wal_path.stat().st_size > 0:
                    raise ValueError("uncheckpointed SQLite WAL appeared during immutable authority read")
            for column_cache_key, payload_json in payload_rows:
                row = json.loads(str(payload_json))
                if not isinstance(row, dict):
                    raise ValueError("cache manifest row must be an object")
                column_key_text = str(column_cache_key or "").strip()
                payload_key_text = str(row.get("cache_key") or "").strip()
                if column_key_text != cache_key_text or payload_key_text != column_key_text:
                    raise ValueError("cache manifest SQL identity mismatch")
                if report_date_text and str(row.get("report_date") or "").strip() != report_date_text:
                    continue
                return row
            return None


@lru_cache(maxsize=2)
def _cached_jsonl_manifest_index(
    target_path: str,
    expected_mtime_ns: int,
    expected_size: int,
) -> tuple[dict[str, str], dict[tuple[str, str], str]]:
    target = Path(target_path)
    stat_before = target.stat()
    expected_signature = (expected_mtime_ns, expected_size)
    if (stat_before.st_mtime_ns, stat_before.st_size) != expected_signature:
        raise ValueError("cache manifest changed before indexed read")
    latest_by_key: dict[str, str] = {}
    latest_by_key_date: dict[tuple[str, str], str] = {}
    for line in target.read_text(encoding="utf-8").splitlines():
        serialized = line.strip()
        if not serialized:
            continue
        row = json.loads(serialized)
        if not isinstance(row, dict):
            raise ValueError("cache manifest row must be an object")
        cache_key = str(row.get("cache_key") or "").strip()
        if not cache_key:
            continue
        latest_by_key[cache_key] = serialized
        report_date = str(row.get("report_date") or "").strip()
        if report_date:
            latest_by_key_date[(cache_key, report_date)] = serialized
    stat_after = target.stat()
    if (stat_after.st_mtime_ns, stat_after.st_size) != expected_signature:
        raise ValueError("cache manifest changed during index build")
    return latest_by_key, latest_by_key_date


@dataclass(frozen=True)
class ThemeOverlayReadResult:
    status: str
    reason: str
    fingerprint: str
    members: tuple[ThemeOverlayMember, ...] = ()
    report_date: str | None = None
    source_kind: str = "tushare_ths_current_overlay"
    concept_source_kind: str = "tushare_current_overlay"
    run_id: str = ""
    source_version: str = ""
    vendor_version: str = ""
    rule_version: str = THEME_OVERLAY_RULE_VERSION
    membership_observed_at: str | None = None
    manifest_created_at: str | None = None
    point_in_time: bool = False
    historical_use_allowed: bool = False

    @property
    def available(self) -> bool:
        return self.status == "available"


@dataclass(frozen=True)
class StockAnalysisThemeOverlayReader:
    archive_root: Path | str
    governance_repo: ThemeOverlayManifestAccessor

    def fingerprint(self, *, backfill_mode: bool = False) -> str:
        if backfill_mode:
            return BACKFILL_DISABLED_FINGERPRINT
        observation: dict[str, object] | None = None
        overlay: dict[str, object] | None = None
        raw: bytes | None = None
        try:
            observation, overlay = self._latest_manifests()
            if overlay is not None:
                raw = self._read_archive_bytes(overlay)
        except Exception as exc:  # Fail-closed fingerprint boundary.
            return _theme_overlay_fingerprint(
                observation=observation,
                overlay=overlay,
                raw=raw,
                error=exc,
            )
        return _theme_overlay_fingerprint(
            observation=observation,
            overlay=overlay,
            raw=raw,
        )

    def read(
        self,
        *,
        requested_as_of_date: str | None,
        effective_as_of_date: str | None,
        evaluation_time: datetime | None = None,
        backfill_mode: bool = False,
    ) -> ThemeOverlayReadResult:
        if backfill_mode:
            return ThemeOverlayReadResult(
                status="suppressed",
                reason="backfill_mode_suppresses_current_overlay",
                fingerprint=BACKFILL_DISABLED_FINGERPRINT,
            )
        observation: dict[str, object] | None = None
        overlay: dict[str, object] | None = None
        raw: bytes | None = None
        fingerprint = ""
        try:
            evaluated_at = _utc_datetime(evaluation_time or datetime.now(UTC), field_name="evaluation_time")
            observation, overlay = self._latest_manifests()
            if observation is None:
                raise ValueError("latest choice-stock observation manifest is missing")
            observation_manifest = _validate_observation_manifest(observation)
            observation_created_at = _utc_datetime_text(
                observation_manifest.get("created_at"),
                field_name="observation manifest created_at",
            )
            if observation_created_at > evaluated_at:
                raise ValueError("observation anchor created_at is after evaluation_time")
            if overlay is None:
                fingerprint = _theme_overlay_fingerprint(
                    observation=observation,
                    overlay=None,
                )
                return ThemeOverlayReadResult(
                    status="unavailable",
                    reason="current_overlay_missing_for_latest_observation",
                    fingerprint=fingerprint,
                    report_date=str(observation_manifest["report_date"]),
                )
            overlay_manifest = _validate_overlay_manifest(overlay)
            raw = self._read_archive_bytes(overlay_manifest)
            fingerprint = _theme_overlay_fingerprint(
                observation=observation,
                overlay=overlay,
                raw=raw,
            )
            document = ThemeOverlayArchiveDocument.model_validate_json(raw)
            if canonical_theme_overlay_document_bytes(document) != raw:
                raise ValueError("archive bytes are not canonical JSON")
            _validate_manifest_document_pair(
                observation_manifest=observation_manifest,
                overlay_manifest=overlay_manifest,
                document=document,
            )
            manifest_created_at = _utc_datetime_text(
                overlay_manifest.get("created_at"),
                field_name="overlay manifest created_at",
            )
            future_timestamps: list[str] = []
            if manifest_created_at > evaluated_at:
                future_timestamps.append("overlay manifest created_at is after evaluation_time")
            if document.membership_observed_at > evaluated_at:
                future_timestamps.append("membership_observed_at is after evaluation_time")
            if observation_created_at > evaluated_at:
                future_timestamps.append("observation anchor created_at is after evaluation_time")
            if future_timestamps:
                raise ValueError("; ".join(future_timestamps))

            report_date = str(observation_manifest["report_date"])
            if effective_as_of_date is None:
                return ThemeOverlayReadResult(
                    status="unavailable",
                    reason="current_overlay_hidden_without_resolved_market_date",
                    fingerprint=fingerprint,
                    report_date=report_date,
                )
            effective_date = _iso_date(effective_as_of_date, field_name="effective_as_of_date")
            requested_date = (
                effective_date
                if requested_as_of_date is None
                else _iso_date(requested_as_of_date, field_name="requested_as_of_date")
            )
            if effective_date != report_date or requested_date != report_date:
                return ThemeOverlayReadResult(
                    status="unavailable",
                    reason="current_overlay_hidden_for_noncurrent_request",
                    fingerprint=fingerprint,
                    report_date=report_date,
                )
            return ThemeOverlayReadResult(
                status="available",
                reason="current_overlay_available",
                fingerprint=fingerprint,
                members=document.members,
                report_date=report_date,
                source_kind=document.source_kind,
                run_id=document.run_id,
                source_version=document.source_version,
                vendor_version=document.vendor_version,
                rule_version=document.rule_version,
                membership_observed_at=document.membership_observed_at.isoformat(),
                manifest_created_at=manifest_created_at.isoformat(),
                point_in_time=document.point_in_time,
                historical_use_allowed=document.historical_use_allowed,
            )
        except Exception as exc:  # Repository boundary must never break the page.
            if not fingerprint:
                fingerprint = _theme_overlay_fingerprint(
                    observation=observation,
                    overlay=overlay,
                    raw=raw,
                    error=exc,
                )
            logger.exception("Theme overlay read failed")
            return ThemeOverlayReadResult(
                status="unavailable",
                reason="current_overlay_invalid",
                fingerprint=fingerprint,
            )

    def _latest_manifests(self) -> tuple[dict[str, object] | None, dict[str, object] | None]:
        observation = self.governance_repo.read_latest_manifest(
            CHOICE_STOCK_OBSERVATION_CACHE_KEY
        )
        if observation is None:
            return None, None
        observation_report_date = str(observation.get("report_date") or "").strip()
        if not observation_report_date:
            return observation, None
        overlay = self.governance_repo.read_latest_manifest(
            THEME_OVERLAY_CACHE_KEY,
            report_date=observation_report_date,
        )
        return observation, overlay

    def _read_archive_bytes(self, overlay_manifest: dict[str, object]) -> bytes:
        lineage = _required_mapping(overlay_manifest.get("lineage"), field_name="overlay lineage")
        archived_path = Path(_required_text(lineage.get("archived_path"), field_name="archived_path"))
        archive_root = Path(self.archive_root)
        if archive_root.is_symlink():
            raise ValueError("archive root must not be a symlink")
        resolved_root = archive_root.resolve()
        overlay_dir = archive_root / "choice-stock-theme-overlay"
        files_dir = overlay_dir / "files"
        for path, label in ((overlay_dir, "overlay directory"), (files_dir, "files directory")):
            if path.is_symlink():
                raise ValueError(f"{label} must not be a symlink")
        resolved_files = files_dir.resolve()
        try:
            resolved_files.relative_to(resolved_root)
        except ValueError as exc:
            raise ValueError("theme overlay files directory escapes archive root") from exc
        if archived_path.is_symlink():
            raise ValueError("theme overlay archive object must not be a symlink")
        resolved_archive = archived_path.resolve()
        try:
            resolved_archive.relative_to(resolved_files)
        except ValueError as exc:
            raise ValueError("archived_path escapes theme overlay files directory") from exc
        if resolved_archive.parent != resolved_files:
            raise ValueError("archived_path must be a direct child of the files directory")
        content_hash = _required_text(lineage.get("content_hash"), field_name="content_hash")
        if resolved_archive.name != f"theme-overlay__{content_hash}.json":
            raise ValueError("archived_path filename does not match content_hash")
        if not resolved_archive.is_file():
            raise ValueError("theme overlay archive object is missing")
        return resolved_archive.read_bytes()


def _theme_overlay_fingerprint(
    *,
    observation: dict[str, object] | None,
    overlay: dict[str, object] | None,
    raw: bytes | None = None,
    error: Exception | None = None,
) -> str:
    evidence: dict[str, object] = {
        "reader_contract": "theme-overlay-reader-v1",
        "observation_manifest": observation,
        "overlay_manifest": overlay,
    }
    if raw is not None:
        evidence["archive_sha256"] = hashlib.sha256(raw).hexdigest()
        evidence["archive_size"] = len(raw)
    if error is not None:
        evidence["error"] = f"{type(error).__name__}:{error}"
    encoded = json.dumps(
        evidence,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_observation_manifest(payload: dict[str, object]) -> dict[str, object]:
    manifest = CacheManifestRecord.model_validate(payload).model_dump()
    _expect_text(manifest, "cache_key", CHOICE_STOCK_OBSERVATION_CACHE_KEY)
    _expect_text(manifest, "cache_version", CHOICE_STOCK_OBSERVATION_CACHE_VERSION)
    _expect_text(manifest, "rule_version", CHOICE_STOCK_OBSERVATION_RULE_VERSION)
    _expect_text(manifest, "basis", "observational")
    _expect_text(manifest, "module_name", "choice_stock")
    _expect_text(manifest, "result_kind_family", "choice-stock-observation")
    if manifest.get("fact_tables") != ["choice_stock_daily_observation"]:
        raise ValueError("observation manifest fact_tables mismatch")
    report_date = _iso_date(manifest.get("report_date"), field_name="observation report_date")
    run_id = _required_text(manifest.get("run_id"), field_name="observation run_id")
    _required_text(manifest.get("source_version"), field_name="observation source_version")
    _required_text(manifest.get("vendor_version"), field_name="observation vendor_version")
    _utc_datetime_text(manifest.get("created_at"), field_name="observation created_at")
    lineage = _required_mapping(manifest.get("lineage"), field_name="observation lineage")
    if _required_text(lineage.get("refresh_run_id"), field_name="observation refresh_run_id") != run_id:
        raise ValueError("observation refresh_run_id mismatch")
    if _iso_date(lineage.get("daily_observation_report_date"), field_name="observation lineage date") != report_date:
        raise ValueError("observation lineage report_date mismatch")
    return manifest


def _validate_overlay_manifest(payload: dict[str, object]) -> dict[str, object]:
    manifest = CacheManifestRecord.model_validate(payload).model_dump()
    _expect_text(manifest, "cache_key", THEME_OVERLAY_CACHE_KEY)
    _expect_text(manifest, "cache_version", THEME_OVERLAY_CACHE_VERSION)
    _expect_text(manifest, "rule_version", THEME_OVERLAY_RULE_VERSION)
    _expect_text(manifest, "basis", "observational_current_overlay")
    _expect_text(manifest, "module_name", "stock_analysis_theme_overlay")
    _expect_text(manifest, "result_kind_family", "stock-analysis-theme-overlay")
    if manifest.get("fact_tables") != []:
        raise ValueError("overlay manifest must not claim fact tables")
    _iso_date(manifest.get("report_date"), field_name="overlay report_date")
    for field_name in ("run_id", "source_version", "vendor_version"):
        _required_text(manifest.get(field_name), field_name=f"overlay {field_name}")
    _utc_datetime_text(manifest.get("created_at"), field_name="overlay created_at")
    lineage = _required_mapping(manifest.get("lineage"), field_name="overlay lineage")
    if lineage.get("source_kind") != "tushare_ths_current_overlay":
        raise ValueError("overlay source_kind mismatch")
    if lineage.get("point_in_time") is not False:
        raise ValueError("overlay point_in_time must be false")
    if lineage.get("historical_use_allowed") is not False:
        raise ValueError("overlay historical_use_allowed must be false")
    for field_name in (
        "membership_observed_at",
        "observed_market_date",
        "content_hash",
        "lineage_hash",
        "archived_path",
    ):
        _required_text(lineage.get(field_name), field_name=f"overlay lineage {field_name}")
    _required_mapping(
        lineage.get("observation_anchor"),
        field_name="overlay lineage observation_anchor",
    )
    member_count = lineage.get("member_count")
    if isinstance(member_count, bool) or not isinstance(member_count, int) or member_count <= 0:
        raise ValueError("overlay lineage member_count must be positive")
    return manifest


def _validate_manifest_document_pair(
    *,
    observation_manifest: dict[str, object],
    overlay_manifest: dict[str, object],
    document: ThemeOverlayArchiveDocument,
) -> None:
    overlay_lineage = _required_mapping(overlay_manifest.get("lineage"), field_name="overlay lineage")
    report_date = str(observation_manifest["report_date"])
    exact_pairs = (
        (overlay_manifest.get("report_date"), report_date, "overlay report_date"),
        (overlay_manifest.get("run_id"), document.run_id, "overlay run_id"),
        (overlay_manifest.get("source_version"), document.source_version, "overlay source_version"),
        (overlay_manifest.get("vendor_version"), document.vendor_version, "overlay vendor_version"),
        (overlay_manifest.get("rule_version"), document.rule_version, "overlay rule_version"),
        (overlay_lineage.get("observed_market_date"), report_date, "observed_market_date"),
        (overlay_lineage.get("content_hash"), document.content_hash, "content_hash"),
        (overlay_lineage.get("lineage_hash"), document.lineage_hash, "lineage_hash"),
        (overlay_lineage.get("source_kind"), document.source_kind, "source_kind"),
    )
    for actual, expected, label in exact_pairs:
        if actual != expected:
            raise ValueError(f"manifest/document {label} mismatch")
    if overlay_lineage.get("member_count") != len(document.members):
        raise ValueError("manifest/document member_count mismatch")
    observed_at = _utc_datetime_text(
        overlay_lineage.get("membership_observed_at"),
        field_name="overlay membership_observed_at",
    )
    if observed_at != document.membership_observed_at:
        raise ValueError("manifest/document membership_observed_at mismatch")
    manifest_created_at = _utc_datetime_text(
        overlay_manifest.get("created_at"),
        field_name="overlay manifest created_at",
    )
    if manifest_created_at != document.membership_observed_at:
        raise ValueError("manifest created_at does not equal membership_observed_at")
    if document.observed_market_date.isoformat() != report_date:
        raise ValueError("document observed_market_date mismatch")
    if document.observed_market_date > document.membership_observed_at.date():
        raise ValueError("observed_market_date is after membership_observed_at date")

    anchor = document.observation_anchor
    manifest_anchor = ThemeOverlayObservationAnchor.model_validate(
        _required_mapping(
            overlay_lineage.get("observation_anchor"),
            field_name="overlay lineage observation_anchor",
        )
    )
    if manifest_anchor != anchor:
        raise ValueError("manifest/document observation_anchor mismatch")
    observation_pairs = (
        (anchor.cache_key, observation_manifest.get("cache_key"), "cache_key"),
        (anchor.report_date.isoformat(), report_date, "report_date"),
        (anchor.source_version, observation_manifest.get("source_version"), "source_version"),
        (anchor.vendor_version, observation_manifest.get("vendor_version"), "vendor_version"),
        (anchor.rule_version, observation_manifest.get("rule_version"), "rule_version"),
        (anchor.run_id, observation_manifest.get("run_id"), "run_id"),
    )
    for actual, expected, label in observation_pairs:
        if actual != expected:
            raise ValueError(f"document observation_anchor {label} mismatch")
    observation_created_at = _utc_datetime_text(
        observation_manifest.get("created_at"),
        field_name="observation created_at",
    )
    if anchor.created_at != observation_created_at:
        raise ValueError("document observation_anchor created_at mismatch")
    if anchor.created_at > document.membership_observed_at:
        raise ValueError("observation_anchor created_at is after membership_observed_at")


def _expect_text(payload: dict[str, object], field_name: str, expected: str) -> None:
    if _required_text(payload.get(field_name), field_name=field_name) != expected:
        raise ValueError(f"{field_name} must equal {expected}")


def _required_mapping(value: object, *, field_name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object")
    return value


def _required_text(value: object, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} must not be blank")
    return text


def _iso_date(value: object, *, field_name: str) -> str:
    text = _required_text(value, field_name=field_name)
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO date") from exc


def _utc_datetime_text(value: object, *, field_name: str) -> datetime:
    text = _required_text(value, field_name=field_name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be ISO-8601") from exc
    return _utc_datetime(parsed, field_name=field_name)


def _utc_datetime(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)
