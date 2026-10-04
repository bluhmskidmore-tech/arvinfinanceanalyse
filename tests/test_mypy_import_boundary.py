"""Imported repository scripts must be adjudicated, never silently discarded."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _checker():
    path = Path(__file__).resolve().parents[1] / "scripts/check_mypy_baseline.py"
    name = "mypy_import_boundary_checker"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("path", [
    "backend/app/example.py",
    "backend/scripts/backfill_example.py",
    "scripts/run_example.py",
])
def test_imported_repository_error_is_new_debt(tmp_path: Path, path: str):
    checker = _checker()
    source = tmp_path / path
    source.parent.mkdir(parents=True)
    source.write_text("answer: int = 'wrong'\n", encoding="utf-8")
    lines = {path: [f"{path}:1:1: error: Incompatible types in assignment  [assignment]"]}

    current = checker.build_diagnostics(lines, tmp_path)
    new, removed = checker.compare_diagnostics([], current)

    assert len(new) == 1
    assert new[0].path == path
    assert removed == []


@pytest.mark.parametrize("path", [
    "../outside.py",
    "backend/../outside.py",
    "scripts/../../outside.py",
    "scripts//example.py",
    "scripts/example.txt",
])
def test_import_boundary_still_rejects_untrustworthy_paths(tmp_path: Path, path: str):
    checker = _checker()
    with pytest.raises(checker.EvidenceError):
        checker._normalized_path(path, tmp_path)


def test_import_boundary_rejects_absolute_path_outside_repository(tmp_path: Path):
    checker = _checker()
    with pytest.raises(checker.EvidenceError, match="outside repository"):
        checker._normalized_path(str(tmp_path.parent / "outside.py"), tmp_path)


def test_same_count_cannot_move_an_error_to_another_function(tmp_path: Path):
    checker = _checker()
    path = "backend/app/example.py"
    source = tmp_path / path
    source.parent.mkdir(parents=True)
    source.write_text("def first():\n    return missing\n", encoding="utf-8")
    lines = {path: [f'{path}:2:12: error: Name "missing" is not defined  [name-defined]']}
    previous = checker.build_diagnostics(lines, tmp_path)

    source.write_text("def second():\n    return missing\n", encoding="utf-8")
    current = checker.build_diagnostics(lines, tmp_path)
    new, removed = checker.compare_diagnostics(previous, current)

    assert len(previous) == len(current) == 1
    assert len(new) == len(removed) == 1
    assert new[0].scope != removed[0].scope


def test_an_additional_identical_statement_is_additional_debt(tmp_path: Path):
    checker = _checker()
    path = "backend/app/example.py"
    source = tmp_path / path
    source.parent.mkdir(parents=True)
    source.write_text("value: int = 'wrong'\n", encoding="utf-8")
    first = f"{path}:1:1: error: Incompatible types in assignment  [assignment]"
    previous = checker.build_diagnostics({path: [first]}, tmp_path)

    source.write_text("value: int = 'wrong'\nvalue: int = 'wrong'\n", encoding="utf-8")
    second = first.replace(":1:1:", ":2:1:")
    current = checker.build_diagnostics({path: [first, second]}, tmp_path)
    new, removed = checker.compare_diagnostics(previous, current)

    assert len(new) == 1
    assert new[0].statement_occurrence == 2
    assert removed == []
