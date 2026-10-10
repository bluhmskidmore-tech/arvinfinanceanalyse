from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Final


class DuckDBReadSelectionError(RuntimeError):
    """Raised when an immutable online-read selection cannot be honored."""


class DuckDBOnlineReadRequiredError(DuckDBReadSelectionError):
    """Raised instead of falling back to the active writer database."""


def _canonical_path(path: str | os.PathLike[str]) -> str:
    return str(Path(path).resolve())


def _path_identity(path: str | os.PathLike[str]) -> str:
    return os.path.normcase(_canonical_path(path))


@dataclass(frozen=True)
class DuckDBReadSelection:
    """One validated, immutable choice of physical database for an active path."""

    active_path: str | os.PathLike[str]
    snapshot_path: str | os.PathLike[str]
    generation: str

    def __post_init__(self) -> None:
        active_path = _canonical_path(self.active_path)
        snapshot_path = _canonical_path(self.snapshot_path)
        generation = str(self.generation or "").strip()
        if not generation:
            raise DuckDBReadSelectionError("DuckDB read generation must not be empty.")
        if _path_identity(active_path) == _path_identity(snapshot_path):
            raise DuckDBReadSelectionError(
                "DuckDB snapshot path must be distinct from the active database path."
            )
        if not Path(snapshot_path).is_file():
            raise DuckDBReadSelectionError("DuckDB snapshot database is unavailable.")
        object.__setattr__(self, "active_path", active_path)
        object.__setattr__(self, "snapshot_path", snapshot_path)
        object.__setattr__(self, "generation", generation)


@dataclass(frozen=True)
class _DuckDBReadContext:
    selection: DuckDBReadSelection | None = None
    required_active_identity: str | None = None


_DEFAULT_CONTEXT: Final = _DuckDBReadContext()
_READ_CONTEXT: ContextVar[_DuckDBReadContext] = ContextVar(
    "duckdb_read_context",
    default=_DEFAULT_CONTEXT,
)
_INHERIT: Final = object()


def current_duckdb_read_selection() -> DuckDBReadSelection | None:
    return _READ_CONTEXT.get().selection


def resolve_effective_read_path(path: str | os.PathLike[str]) -> str:
    """Resolve ``path`` against the selection fixed in the current task context."""

    requested_path = os.fspath(path)
    requested_identity = _path_identity(requested_path)
    context = _READ_CONTEXT.get()
    selection = context.selection
    if selection is not None and requested_identity == _path_identity(selection.active_path):
        snapshot_path = str(selection.snapshot_path)
        if not Path(snapshot_path).is_file():
            raise DuckDBReadSelectionError(
                f"DuckDB snapshot generation {selection.generation!r} is unavailable."
            )
        return snapshot_path
    if context.required_active_identity == requested_identity:
        raise DuckDBOnlineReadRequiredError(
            "An immutable DuckDB read selection is required for the active database."
        )
    return requested_path


@contextmanager
def duckdb_read_scope(
    selection: DuckDBReadSelection | None | object = _INHERIT,
    *,
    required_online: bool | None = None,
    active_path: str | os.PathLike[str] | None = None,
) -> Iterator[DuckDBReadSelection | None]:
    """Fix, clear, or override the immutable selection for one task/CLI scope.

    Omitting ``selection`` inherits the outer choice. Passing ``None`` explicitly
    clears it. ``required_online=True`` makes a matching active-path read fail
    closed when no usable selection exists. The outer context is restored on exit.
    """

    outer = _READ_CONTEXT.get()
    selection_was_explicit = selection is not _INHERIT
    if selection is _INHERIT:
        effective_selection = outer.selection
    elif selection is None or isinstance(selection, DuckDBReadSelection):
        effective_selection = selection
    else:
        raise DuckDBReadSelectionError("DuckDB read selection has an invalid type.")

    explicit_active_identity = _path_identity(active_path) if active_path is not None else None
    if effective_selection is not None and explicit_active_identity is not None:
        if explicit_active_identity != _path_identity(effective_selection.active_path):
            raise DuckDBReadSelectionError(
                "Required active path does not match the DuckDB read selection."
            )

    if required_online is True:
        required_active_identity = explicit_active_identity
        if required_active_identity is None and effective_selection is not None:
            required_active_identity = _path_identity(effective_selection.active_path)
        if required_active_identity is None:
            raise DuckDBReadSelectionError(
                "required_online=True needs an active path or a read selection."
            )
    elif required_online is False:
        required_active_identity = None
    elif selection_was_explicit and effective_selection is not None:
        required_active_identity = (
            _path_identity(effective_selection.active_path)
            if outer.required_active_identity is not None
            else None
        )
    else:
        required_active_identity = outer.required_active_identity

    context = _DuckDBReadContext(
        selection=effective_selection,
        required_active_identity=required_active_identity,
    )
    token = _READ_CONTEXT.set(context)
    try:
        yield effective_selection
    finally:
        _READ_CONTEXT.reset(token)


@contextmanager
def active_read_scope() -> Iterator[None]:
    """Run a task/CLI block against the active database, ignoring inheritance."""

    with duckdb_read_scope(None, required_online=False):
        yield None
