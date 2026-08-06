from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import sys
from pathlib import Path
from typing import cast

import pytest

ROOT = Path(__file__).resolve().parents[1]


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
    typed_loader = cast(importlib.abc.Loader, typed_spec.loader)

    if module_name == "backend.app.main":
        _purge_backend_main_import_chain()

    module = importlib.util.module_from_spec(typed_spec)
    sys.modules[module_name] = module
    try:
        typed_loader.exec_module(module)
    except Exception:
        if sys.modules.get(module_name) is module:
            sys.modules.pop(module_name, None)
        raise
    return module
