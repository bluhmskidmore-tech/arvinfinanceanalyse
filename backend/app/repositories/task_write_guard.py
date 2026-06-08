from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_TASK_WRITE_SCOPE: ContextVar[str | None] = ContextVar("repository_task_write_scope", default=None)


@contextmanager
def repository_task_write_scope(task_module: str) -> Iterator[None]:
    normalized = str(task_module or "").strip()
    if not normalized.startswith("backend.app.tasks."):
        raise PermissionError("Repository task write scope must be opened by backend.app.tasks.")
    token = _TASK_WRITE_SCOPE.set(normalized)
    try:
        yield
    finally:
        _TASK_WRITE_SCOPE.reset(token)


def require_repository_task_write_scope(writer_name: str) -> None:
    scope = _TASK_WRITE_SCOPE.get()
    if scope is None:
        raise PermissionError(f"{writer_name} requires repository task write scope.")
