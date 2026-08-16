from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from pathlib import Path

from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.repositories.governance_repo import (
    CACHE_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.schemas.stock_analysis_theme_overlay import (
    ThemeOverlayArchiveDocument,
    canonical_theme_overlay_document_bytes,
    validate_theme_overlay_document_hashes,
)

THEME_OVERLAY_ARCHIVE_LOCK = LockDefinition(
    key="lock:archive:stock-analysis-theme-overlay",
    ttl_seconds=60,
)
THEME_OVERLAY_ARCHIVE_LOCK_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class StockAnalysisThemeOverlayArchiveRepository:
    archive_root: Path
    governance_repo: GovernanceRepository
    lock_timeout_seconds: float = THEME_OVERLAY_ARCHIVE_LOCK_TIMEOUT_SECONDS

    def archive(
        self,
        *,
        document: ThemeOverlayArchiveDocument,
        manifest_payload: dict[str, object],
        commit_guard: Callable[[], AbstractContextManager[object]] | None = None,
    ) -> Path:
        validate_theme_overlay_document_hashes(document)
        archive_root = self.archive_root.resolve()
        with acquire_lock(
            THEME_OVERLAY_ARCHIVE_LOCK,
            base_dir=archive_root,
            timeout_seconds=self.lock_timeout_seconds,
        ):
            # Lock order: archive, optional observation guard, governance batch.
            guard = commit_guard() if commit_guard is not None else nullcontext()
            with guard:
                return self._archive_locked(
                    archive_root=archive_root,
                    document=document,
                    manifest_payload=manifest_payload,
                )

    def _archive_locked(
        self,
        *,
        archive_root: Path,
        document: ThemeOverlayArchiveDocument,
        manifest_payload: dict[str, object],
    ) -> Path:
        overlay_dir = archive_root / "choice-stock-theme-overlay"
        files_dir = overlay_dir / "files"
        _validate_existing_path(overlay_dir, archive_root=archive_root)
        _validate_existing_path(files_dir, archive_root=archive_root)
        files_dir.mkdir(parents=True, exist_ok=True)
        resolved_files_dir = _resolve_within(files_dir, archive_root=archive_root)
        candidate_target = resolved_files_dir / f"theme-overlay__{document.content_hash}.json"
        _reject_symlink(candidate_target)
        target = _resolve_within(
            candidate_target,
            archive_root=archive_root,
        )
        if target.parent != resolved_files_dir:
            raise ValueError(f"archive target escapes files directory: {target}")
        payload = canonical_theme_overlay_document_bytes(document)

        created_target = False
        temporary_path: Path | None = None
        if target.exists():
            if target.read_bytes() != payload:
                raise ValueError(f"content-addressed archive mismatch for {target}")
        else:
            try:
                with tempfile.NamedTemporaryFile(
                    mode="wb",
                    dir=resolved_files_dir,
                    prefix=".theme-overlay-",
                    suffix=".tmp",
                    delete=False,
                ) as handle:
                    temporary_path = Path(handle.name)
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary_path, target)
                temporary_path = None
                created_target = True
            finally:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)

        manifest = dict(manifest_payload)
        lineage = dict(manifest.get("lineage") or {})
        lineage["archived_path"] = str(target)
        manifest["lineage"] = lineage
        try:
            self.governance_repo.append_many_atomic([(CACHE_MANIFEST_STREAM, manifest)])
        except Exception:
            if created_target:
                target.unlink(missing_ok=True)
            raise
        return target


def _validate_existing_path(path: Path, *, archive_root: Path) -> None:
    _reject_symlink(path)
    if path.exists():
        _resolve_within(path, archive_root=archive_root)


def _reject_symlink(path: Path) -> None:
    if path.is_symlink():
        raise ValueError(f"archive path must not be a symlink: {path}")


def _resolve_within(path: Path, *, archive_root: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(archive_root)
    except ValueError as exc:
        raise ValueError(f"archive path escapes archive root: {resolved}") from exc
    return resolved
