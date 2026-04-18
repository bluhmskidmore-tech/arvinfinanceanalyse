from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _purge_backend_main_import_chain() -> None:
    for loaded_name in list(sys.modules):
        if loaded_name == "backend.app.main":
            sys.modules.pop(loaded_name, None)


def load_module(module_name: str, relative_path: str):
    path = ROOT / relative_path
    if not path.exists():
        pytest.fail(f"Missing expected module file: {path}")

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.fail(f"Failed to create import spec for {path}")

    if module_name == "backend.app.main":
        _purge_backend_main_import_chain()

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
