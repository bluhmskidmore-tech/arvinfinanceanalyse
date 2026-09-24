from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import cast

import pytest

ROOT = Path(__file__).resolve().parents[1]

try:  # CPython's per-module import lock; absent on alternative interpreters.
    from importlib._bootstrap import _ModuleLockManager  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - non-CPython fallback
    _ModuleLockManager = None  # type: ignore[assignment]


@contextmanager
def _module_import_lock(module_name: str) -> Iterator[None]:
    """Hold the interpreter's import lock for *module_name* while it executes.

    Degrades to a no-op when the lock is unavailable or when acquiring it would
    deadlock, matching how ``importlib`` itself tolerates re-entrant imports.
    """

    if _ModuleLockManager is None:
        yield
        return

    manager = _ModuleLockManager(module_name)
    try:
        manager.__enter__()
    except Exception:
        yield
        return
    try:
        yield
    finally:
        manager.__exit__(None, None, None)


def _exec_and_publish(spec: importlib.machinery.ModuleSpec, module_name: str):
    """Execute *spec* into ``sys.modules`` using CPython's own publish protocol.

    ``importlib``'s "import a source file directly" recipe publishes the empty
    module to ``sys.modules`` before ``exec_module`` without setting
    ``spec._initializing``. ``importlib._bootstrap._find_and_load`` then takes
    its fast path for any concurrent importer of the same name and hands back
    the still-empty module, surfacing as ``ImportError: cannot import name ...``.
    Setting ``_initializing`` before publishing (and holding the module lock)
    makes concurrent importers wait for the executed module instead.
    """

    loader = cast(importlib.abc.Loader, spec.loader)
    module = importlib.util.module_from_spec(spec)
    previous = sys.modules.get(module_name)
    spec._initializing = True  # must precede the sys.modules publish
    try:
        sys.modules[module_name] = module
        try:
            loader.exec_module(module)
        except BaseException:
            if sys.modules.get(module_name) is module:
                if previous is None:
                    sys.modules.pop(module_name, None)
                else:
                    sys.modules[module_name] = previous
            raise
        return sys.modules.get(module_name, module)
    finally:
        spec._initializing = False


def _purge_backend_main_import_chain() -> None:
    for loaded_name in list(sys.modules):
        if loaded_name == "backend.app.main":
            sys.modules.pop(loaded_name, None)
            continue
        if loaded_name == "backend.app.governance.settings":
            sys.modules.pop(loaded_name, None)
            continue
        if loaded_name == "backend.app.api" or loaded_name.startswith("backend.app.api."):
            sys.modules.pop(loaded_name, None)


def load_module(module_name: str, relative_path: str):
    path = ROOT / relative_path
    if not path.exists():
        pytest.fail(f"Missing expected module file: {path}")

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    if module_name.startswith("backend.app.api.routes."):
        _purge_backend_main_import_chain()
        return importlib.import_module(module_name)

    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.fail(f"Failed to create import spec for {path}")
    typed_spec = cast(importlib.machinery.ModuleSpec, spec)

    if module_name == "backend.app.main":
        _purge_backend_main_import_chain()

    with _module_import_lock(module_name):
        return _exec_and_publish(typed_spec, module_name)
