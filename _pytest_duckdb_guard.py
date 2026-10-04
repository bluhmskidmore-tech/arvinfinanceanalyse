"""Fail closed when pytest code tries to open an unowned DuckDB file."""

from __future__ import annotations

import inspect
import json
import os
import sys
import tempfile
import threading
import uuid
import weakref
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from pathlib import Path
from types import ModuleType
from typing import Any

import duckdb
import pytest

_MODULE_PATH = Path(__file__).resolve()
_DEFAULT_REPO_ROOT = _MODULE_PATH.parent
_MEMORY_DATABASE = ":memory:"
_EXPECTED_DENIAL_DEPTH: ContextVar[int] = ContextVar(
    "pytest_duckdb_expected_denial_depth",
    default=0,
)


class PytestDuckDBIsolationViolation(BaseException):
    """A pytest process attempted to open a file it does not own."""


class _DuckDBConnectGuard:
    def __init__(
        self,
        *,
        native_connect: Callable[..., Any],
        repo_root: Path,
        protected_paths: tuple[Path, ...] | None = None,
        run_id: str | None = None,
    ) -> None:
        self.native_connect = native_connect
        self.repo_root = repo_root.resolve()
        configured_protected = protected_paths or (
            self.repo_root / "data" / "moss.duckdb",
        )
        self.protected_paths = tuple(
            self._canonical_path(path) for path in configured_protected
        )
        self.run_id = run_id or f"pytest-{os.getpid()}-{uuid.uuid4().hex}"
        self.phase = "plugin_import"
        self.allowed_roots: list[Path] = []
        self.attempts: list[dict[str, object]] = []
        self._lock = threading.Lock()
        self._receipt_path: Path | None = None
        self._persisted_attempt_count = 0
        self._owned_connections: weakref.WeakKeyDictionary[
            object, tuple[str, str]
        ] = weakref.WeakKeyDictionary()

    @staticmethod
    def _canonical_path(path: os.PathLike[str] | str) -> Path:
        candidate = Path(os.fspath(path)).expanduser()
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        return candidate.resolve(strict=False)

    @staticmethod
    def _path_key(path: Path) -> str:
        return os.path.normcase(str(path))

    @classmethod
    def _is_within(cls, path: Path, root: Path) -> bool:
        path_key = cls._path_key(path)
        root_key = cls._path_key(root)
        try:
            return os.path.commonpath((path_key, root_key)) == root_key
        except ValueError:
            return False

    @staticmethod
    def _same_existing_file(left: Path, right: Path) -> bool:
        try:
            return left.exists() and right.exists() and os.path.samefile(left, right)
        except OSError:
            return False

    def set_phase(self, phase: str) -> None:
        self.phase = phase

    def register_temp_root(self, root: os.PathLike[str] | str) -> Path:
        canonical = self._canonical_path(root)
        repository_data = self.repo_root / "data"
        forbidden_exact_roots = {
            self._path_key(self.repo_root),
            self._path_key(self.repo_root / ".codex-tmp"),
            self._path_key(Path.cwd().resolve()),
            self._path_key(Path(tempfile.gettempdir()).resolve()),
        }
        if (
            self._path_key(canonical) in forbidden_exact_roots
            or self._is_within(canonical, repository_data)
        ):
            raise PytestDuckDBIsolationViolation(
                f"pytest DuckDB guard refused a broad or protected temp root: {canonical}"
            )
        for protected in self.protected_paths:
            if self._is_within(protected, canonical):
                raise PytestDuckDBIsolationViolation(
                    "pytest DuckDB guard refused a temp root containing a protected database: "
                    f"{canonical}"
                )
        with self._lock:
            if all(self._path_key(item) != self._path_key(canonical) for item in self.allowed_roots):
                self.allowed_roots.append(canonical)
            if canonical.is_dir():
                receipt_path = canonical / "pytest-duckdb-guard-attempts.jsonl"
                if self._receipt_path != receipt_path:
                    self._receipt_path = receipt_path
                    self._persisted_attempt_count = 0
                elif not receipt_path.exists():
                    self._persisted_attempt_count = 0
                self._persist_locked()
        return canonical

    @staticmethod
    def _database_argument(args: tuple[object, ...], kwargs: Mapping[str, object]) -> object:
        if args:
            return args[0]
        return kwargs.get("database", _MEMORY_DATABASE)

    @staticmethod
    def _access_mode(args: tuple[object, ...], kwargs: Mapping[str, object]) -> str:
        read_only = args[1] if len(args) > 1 else kwargs.get("read_only", False)
        return "read_only" if read_only is True else "read_write_or_default"

    def _callsite(self) -> str:
        for frame_info in inspect.stack(context=0)[2:]:
            candidate = Path(frame_info.filename).resolve(strict=False)
            if candidate == _MODULE_PATH:
                continue
            try:
                label = candidate.relative_to(self.repo_root).as_posix()
            except ValueError:
                label = candidate.name
            return f"{label}:{frame_info.lineno}"
        return "unknown"

    def _record(
        self,
        *,
        target_classification: str,
        canonical_path: str,
        access: str,
        decision: str,
    ) -> dict[str, object]:
        attempt: dict[str, object] = {
            "pid": os.getpid(),
            "run_id": self.run_id,
            "phase": self.phase,
            "callsite": self._callsite(),
            "target_classification": target_classification,
            "canonical_path": canonical_path,
            "access": access,
            "decision": decision,
            "expected_denial": _EXPECTED_DENIAL_DEPTH.get() > 0,
        }
        with self._lock:
            self.attempts.append(attempt)
            self._persist_locked()
        return attempt

    def _persist_locked(self) -> None:
        if self._receipt_path is None:
            return
        self._receipt_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._receipt_path.exists():
            self._persisted_attempt_count = 0
        pending = self.attempts[self._persisted_attempt_count :]
        if not pending:
            return
        with self._receipt_path.open("a", encoding="utf-8", newline="\n") as receipt:
            for attempt in pending:
                receipt.write(json.dumps(attempt, ensure_ascii=True, sort_keys=True) + "\n")
        self._persisted_attempt_count = len(self.attempts)

    def persist_attempts(self) -> Path:
        with self._lock:
            if self._receipt_path is None:
                candidates = [root for root in self.allowed_roots if root.is_dir()]
                root = candidates[-1] if candidates else self.allowed_roots[-1]
                root.mkdir(parents=True, exist_ok=True)
                self._receipt_path = root / "pytest-duckdb-guard-attempts.jsonl"
                self._persisted_attempt_count = 0
            self._persist_locked()
            return self._receipt_path

    def unexpected_denials(self) -> tuple[dict[str, object], ...]:
        return tuple(
            attempt
            for attempt in self.attempts
            if attempt["decision"] == "deny" and attempt["expected_denial"] is False
        )

    def _deny(
        self,
        *,
        target_classification: str,
        canonical_path: str,
        access: str,
    ) -> None:
        self._record(
            target_classification=target_classification,
            canonical_path=canonical_path,
            access=access,
            decision="deny",
        )
        raise PytestDuckDBIsolationViolation(
            "pytest DuckDB guard denied an unowned database path "
            f"({target_classification}, {access}): {canonical_path}"
        )

    def require_owned_path(
        self,
        database: object,
        *,
        access: str,
        allow_memory: bool = False,
    ) -> tuple[str, str]:
        if allow_memory and database == _MEMORY_DATABASE:
            self._record(
                target_classification="memory",
                canonical_path=_MEMORY_DATABASE,
                access=access,
                decision="allow",
            )
            return "memory", _MEMORY_DATABASE
        try:
            canonical = self._canonical_path(os.fspath(database))  # type: ignore[arg-type]
        except (TypeError, ValueError, OSError):
            self._deny(
                target_classification="unknown",
                canonical_path="<unresolved>",
                access=access,
            )

        for protected in self.protected_paths:
            if self._path_key(canonical) == self._path_key(protected):
                self._deny(
                    target_classification="protected_database",
                    canonical_path=str(canonical),
                    access=access,
                )
            if self._same_existing_file(canonical, protected):
                self._deny(
                    target_classification="protected_database_alias",
                    canonical_path=str(canonical),
                    access=access,
                )

        if any(self._is_within(canonical, root) for root in self.allowed_roots):
            self._record(
                target_classification="owned_temp",
                canonical_path=str(canonical),
                access=access,
                decision="allow",
            )
            return "owned_temp", str(canonical)

        self._deny(
            target_classification="outside_owned_temp",
            canonical_path=str(canonical),
            access=access,
        )

    def connect(self, *args: object, **kwargs: object) -> Any:
        database = self._database_argument(args, kwargs)
        access = self._access_mode(args, kwargs)
        classification, canonical_path = self.require_owned_path(
            database,
            access=access,
            allow_memory=True,
        )
        connection = self.native_connect(*args, **kwargs)
        try:
            with self._lock:
                self._owned_connections[connection] = (classification, canonical_path)
        except TypeError:
            # DuckDBPyConnection supports weak keys. A test double or future native
            # object that does not is allowed for direct use but cannot be trusted as
            # a borrowed publication connection.
            pass
        return connection

    def require_owned_connection(self, connection: object, *, access: str) -> str:
        try:
            with self._lock:
                identity = self._owned_connections.get(connection)
        except TypeError:
            identity = None
        if identity is None:
            self._deny(
                target_classification="untracked_connection",
                canonical_path="<untracked-connection>",
                access=access,
            )
        classification, canonical_path = identity
        self._record(
            target_classification=f"{classification}_connection",
            canonical_path=canonical_path,
            access=access,
            decision="allow",
        )
        return canonical_path


_NATIVE_DUCKDB_CONNECT = duckdb.connect
_GUARD = _DuckDBConnectGuard(
    native_connect=_NATIVE_DUCKDB_CONNECT,
    repo_root=_DEFAULT_REPO_ROOT,
)
_INSTALL_LOCK = threading.Lock()
_INSTALLED = False


def _guarded_duckdb_connect(*args: object, **kwargs: object) -> Any:
    return _GUARD.connect(*args, **kwargs)


def install_pytest_duckdb_guard(*, repo_root: Path | None = None) -> None:
    """Install the process-local connect guard once, before test collection."""

    global _INSTALLED
    if repo_root is not None and repo_root.resolve() != _GUARD.repo_root:
        raise PytestDuckDBIsolationViolation(
            f"pytest DuckDB guard repo root changed after import: {repo_root.resolve()}"
        )
    with _INSTALL_LOCK:
        if _INSTALLED:
            return
        duckdb.connect = _guarded_duckdb_connect
        _INSTALLED = True


def register_pytest_duckdb_temp_root(root: os.PathLike[str] | str) -> Path:
    return _GUARD.register_temp_root(root)


def get_pytest_duckdb_guard_attempts() -> tuple[dict[str, object], ...]:
    return tuple(dict(attempt) for attempt in _GUARD.attempts)


def get_pytest_duckdb_guard_receipt_path() -> Path:
    return _GUARD.persist_attempts()


def set_pytest_duckdb_guard_phase(phase: str) -> None:
    _GUARD.set_phase(phase)


def finalize_pytest_duckdb_guard() -> Path:
    receipt_path = _GUARD.persist_attempts()
    if _GUARD.unexpected_denials():
        raise PytestDuckDBIsolationViolation(
            "pytest DuckDB guard recorded an unexpected denied database attempt; "
            f"see {receipt_path}"
        )
    return receipt_path


_PUBLICATION_MODULE = "backend.app.tasks.financial_result_publication"
_ATTACH_GUARD_MARKER = "__pytest_duckdb_attach_guard__"


def _wrap_publication_attach_entrypoints(module: ModuleType) -> None:
    attached_name = "_build_candidate_from_attached_source"
    attached = getattr(module, attached_name, None)
    if callable(attached) and not getattr(attached, _ATTACH_GUARD_MARKER, False):

        @wraps(attached)
        def guarded_attached(*args: object, **kwargs: object) -> object:
            bound = inspect.signature(attached).bind(*args, **kwargs)
            _GUARD.require_owned_path(
                bound.arguments["source_path"],
                access="attach_read_only_source",
            )
            _GUARD.require_owned_path(
                bound.arguments["candidate_path"],
                access="attach_write_candidate",
            )
            return attached(*args, **kwargs)

        setattr(guarded_attached, _ATTACH_GUARD_MARKER, True)
        setattr(module, attached_name, guarded_attached)

    borrowed_name = "_build_candidate_from_existing_source_connection"
    borrowed = getattr(module, borrowed_name, None)
    if callable(borrowed) and not getattr(borrowed, _ATTACH_GUARD_MARKER, False):

        @wraps(borrowed)
        def guarded_borrowed(*args: object, **kwargs: object) -> object:
            bound = inspect.signature(borrowed).bind(*args, **kwargs)
            _GUARD.require_owned_connection(
                bound.arguments["source_connection"],
                access="attach_borrowed_source",
            )
            _GUARD.require_owned_path(
                bound.arguments["candidate_path"],
                access="attach_write_candidate",
            )
            return borrowed(*args, **kwargs)

        setattr(guarded_borrowed, _ATTACH_GUARD_MARKER, True)
        setattr(module, borrowed_name, guarded_borrowed)


def install_financial_publication_attach_guard() -> bool:
    module = sys.modules.get(_PUBLICATION_MODULE)
    if not isinstance(module, ModuleType):
        return False
    _wrap_publication_attach_entrypoints(module)
    return True


@contextmanager
def expect_pytest_duckdb_guard_denial() -> Iterator[None]:
    """Mark a deliberately asserted negative guard probe."""

    token = _EXPECTED_DENIAL_DEPTH.set(_EXPECTED_DENIAL_DEPTH.get() + 1)
    try:
        yield
    finally:
        _EXPECTED_DENIAL_DEPTH.reset(token)


def pytest_configure(config: Any) -> None:
    install_pytest_duckdb_guard(repo_root=_DEFAULT_REPO_ROOT)
    _GUARD.set_phase("collection")
    configured_basetemp = getattr(config.option, "basetemp", None)
    root = (
        Path(configured_basetemp)
        if configured_basetemp is not None
        else _DEFAULT_REPO_ROOT / ".codex-tmp" / f"pytest-basetemp-{os.getpid()}"
    )
    register_pytest_duckdb_temp_root(root)


def pytest_collection_finish() -> None:
    install_financial_publication_attach_guard()


def pytest_runtest_setup() -> None:
    _GUARD.set_phase("test")
    install_financial_publication_attach_guard()


@pytest.fixture(scope="session", autouse=True)
def _register_actual_pytest_basetemp(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[None]:
    register_pytest_duckdb_temp_root(tmp_path_factory.getbasetemp())
    yield


def pytest_sessionfinish(session: pytest.Session) -> None:
    _GUARD.persist_attempts()
    if _GUARD.unexpected_denials():
        session.exitstatus = int(pytest.ExitCode.TESTS_FAILED)


install_pytest_duckdb_guard(repo_root=_DEFAULT_REPO_ROOT)
