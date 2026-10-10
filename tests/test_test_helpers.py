from __future__ import annotations

import importlib
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace

import pytest

from tests import helpers


@pytest.fixture
def package_source(tmp_path, monkeypatch):
    package_name = "_test_helpers_package"
    package_dir = tmp_path / package_name
    package_dir.mkdir()
    init_path = package_dir / "__init__.py"
    init_path.write_text("", encoding="utf-8")
    module_path = package_dir / "worker.py"
    module_path.write_text('def marker():\n    return "original"\n', encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(helpers, "ROOT", tmp_path)
    assert not any(name == package_name or name.startswith(f"{package_name}.") for name in sys.modules)
    try:
        yield SimpleNamespace(
            package_name=package_name,
            module_name=f"{package_name}.worker",
            relative_path=f"{package_name}/worker.py",
            init_path=init_path,
            module_path=module_path,
        )
    finally:
        for name in list(sys.modules):
            if name == package_name or name.startswith(f"{package_name}."):
                sys.modules.pop(name, None)


def test_load_module_imports_parent_and_binds_child(package_source):
    module = helpers.load_module(package_source.module_name, package_source.relative_path)

    parent = importlib.import_module(package_source.package_name)
    assert parent.worker is module
    assert importlib.import_module(package_source.module_name) is module


def test_load_module_rebinds_parent_when_replacing_existing_module(package_source):
    previous = importlib.import_module(package_source.module_name)
    parent = importlib.import_module(package_source.package_name)

    module = helpers.load_module(package_source.module_name, package_source.relative_path)

    assert module is not previous
    assert parent.worker is module
    assert sys.modules[package_source.module_name] is module


def test_string_monkeypatch_targets_latest_loaded_module(package_source, monkeypatch):
    previous = importlib.import_module(package_source.module_name)
    module = helpers.load_module(package_source.module_name, package_source.relative_path)

    monkeypatch.setattr(f"{package_source.module_name}.marker", lambda: "patched")

    assert module.marker() == "patched"
    assert previous.marker() == "original"


def test_failed_load_preserves_previous_module_and_parent_binding(package_source):
    previous = importlib.import_module(package_source.module_name)
    parent = importlib.import_module(package_source.package_name)
    package_source.module_path.write_text('raise RuntimeError("execution failed")\n', encoding="utf-8")

    with pytest.raises(RuntimeError, match="execution failed"):
        helpers.load_module(package_source.module_name, package_source.relative_path)

    assert sys.modules[package_source.module_name] is previous
    assert parent.worker is previous


def test_failed_first_load_leaves_no_child_binding(package_source):
    parent = importlib.import_module(package_source.package_name)
    package_source.module_path.write_text('raise RuntimeError("execution failed")\n', encoding="utf-8")

    with pytest.raises(RuntimeError, match="execution failed"):
        helpers.load_module(package_source.module_name, package_source.relative_path)

    assert package_source.module_name not in sys.modules
    assert not hasattr(parent, "worker")


def test_load_module_keeps_alias_without_importable_parent(package_source):
    alias_name = f"{package_source.package_name}.private.worker"

    module = helpers.load_module(alias_name, package_source.relative_path)

    assert module.marker() == "original"
    assert sys.modules[alias_name] is module
    assert f"{package_source.package_name}.private" not in sys.modules


def test_parent_dependency_import_error_is_not_treated_as_missing_parent(package_source):
    package_source.init_path.write_text("import _test_helpers_missing_dependency\n", encoding="utf-8")

    with pytest.raises(ModuleNotFoundError) as caught:
        helpers.load_module(package_source.module_name, package_source.relative_path)

    assert caught.value.name == "_test_helpers_missing_dependency"
    assert package_source.module_name not in sys.modules


def test_parent_binds_actual_module_published_during_execution(package_source):
    package_source.module_path.write_text(
        "import sys\n"
        "from types import ModuleType\n"
        "replacement = ModuleType(__name__)\n"
        "replacement.marker = lambda: 'replacement'\n"
        "sys.modules[__name__] = replacement\n",
        encoding="utf-8",
    )

    module = helpers.load_module(package_source.module_name, package_source.relative_path)

    parent = importlib.import_module(package_source.package_name)
    assert module.marker() == "replacement"
    assert sys.modules[package_source.module_name] is module
    assert parent.worker is module


def test_concurrent_import_waits_for_loaded_module_execution(package_source):
    parent = importlib.import_module(package_source.package_name)
    parent.started = Event()
    parent.release = Event()
    import_finished = Event()
    package_source.module_path.write_text(
        f"from {package_source.package_name} import started, release\n"
        "started.set()\n"
        "assert release.wait(5)\n"
        "answer = 42\n",
        encoding="utf-8",
    )

    def import_concurrently():
        try:
            return importlib.import_module(package_source.module_name)
        finally:
            import_finished.set()

    with ThreadPoolExecutor(max_workers=2) as executor:
        loading = executor.submit(helpers.load_module, package_source.module_name, package_source.relative_path)
        try:
            assert parent.started.wait(5)
            importing = executor.submit(import_concurrently)
            assert not import_finished.wait(0.1)
        finally:
            parent.release.set()
        module = loading.result(timeout=5)
        imported = importing.result(timeout=5)

    assert imported is module
    assert imported.answer == 42
    assert parent.worker is module
