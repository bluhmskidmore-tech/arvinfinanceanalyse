from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path
from typing import Any

import pytest


SYNC_WRAPPER_CONTRACTS = (
    (
        "backend.app.tasks.accounting_asset_movement",
        "refresh_accounting_asset_movement_window_sync",
        "_refresh_accounting_asset_movement_window",
        {
            "report_dates": ["2026-01-31", "2026-02-28"],
            "anchor_report_date": "2026-02-28",
            "duckdb_path": "test-output/movement.duckdb",
            "governance_dir": "test-output/governance",
            "currency_basis": "CNX",
            "product_category_refreshed_dates": ["2026-01-31"],
            "formal_balance_refreshed_dates": ["2026-02-28"],
            "run_id": "run-movement",
        },
    ),
    (
        "backend.app.tasks.product_category_pnl",
        "materialize_product_category_pnl_sync",
        "_materialize_product_category_pnl",
        {
            "duckdb_path": "test-output/product.duckdb",
            "source_dir": "test-output/product-source",
            "governance_dir": "test-output/governance",
            "run_id": "run-product",
        },
    ),
    (
        "backend.app.tasks.formal_balance_pipeline",
        "run_formal_balance_pipeline_sync",
        "_run_formal_balance_pipeline",
        {
            "report_date": "2026-02-28",
            "start_date": "2026-02-01",
            "end_date": "2026-02-28",
            "data_root": "test-output/data_input",
            "duckdb_path": "test-output/formal.duckdb",
            "governance_dir": "test-output/governance",
            "archive_dir": "test-output/archive",
            "fx_source_path": "test-output/fx.csv",
        },
    ),
)


def _module_tree(module_name: str) -> ast.Module:
    module = importlib.import_module(module_name)
    source = Path(module.__file__).read_text(encoding="utf-8-sig")
    return ast.parse(source)


def _top_level_function(tree: ast.Module, name: str) -> ast.FunctionDef:
    matches = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    assert matches, f"{name} must be an explicit top-level function, not an alias."
    return matches[0]


def _assigned_top_level_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                names.add(target.id)
    return names


@pytest.mark.parametrize(
    ("module_name", "public_name", "private_name", "_sample_kwargs"),
    SYNC_WRAPPER_CONTRACTS,
)
def test_task_sync_exports_are_explicit_public_wrappers(
    module_name: str,
    public_name: str,
    private_name: str,
    _sample_kwargs: dict[str, Any],
) -> None:
    tree = _module_tree(module_name)

    wrapper = _top_level_function(tree, public_name)
    assert public_name not in _assigned_top_level_names(tree)

    assert not any(
        arg.arg == "_impl"
        for arg in [*wrapper.args.posonlyargs, *wrapper.args.args, *wrapper.args.kwonlyargs]
    )
    assert len(wrapper.body) == 1
    return_node = wrapper.body[0]
    assert isinstance(return_node, ast.Return)
    assert isinstance(return_node.value, ast.Call)
    assert isinstance(return_node.value.func, ast.Name)
    assert return_node.value.func.id == private_name


@pytest.mark.parametrize(
    ("module_name", "public_name", "private_name", "_sample_kwargs"),
    SYNC_WRAPPER_CONTRACTS,
)
def test_task_sync_wrappers_preserve_private_implementation_signatures(
    module_name: str,
    public_name: str,
    private_name: str,
    _sample_kwargs: dict[str, Any],
) -> None:
    module = importlib.import_module(module_name)

    assert inspect.signature(getattr(module, public_name)) == inspect.signature(
        getattr(module, private_name)
    )


@pytest.mark.parametrize(
    ("module_name", "public_name", "private_name", "sample_kwargs"),
    SYNC_WRAPPER_CONTRACTS,
)
def test_task_sync_wrappers_delegate_to_module_global_private_implementations(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    public_name: str,
    private_name: str,
    sample_kwargs: dict[str, Any],
) -> None:
    module = importlib.import_module(module_name)
    sentinel = object()
    calls: list[dict[str, Any]] = []

    def fake_private(*args: Any, **kwargs: Any) -> object:
        calls.append({"args": args, "kwargs": kwargs})
        return sentinel

    monkeypatch.setattr(module, private_name, fake_private)

    result = getattr(module, public_name)(**sample_kwargs)

    assert result is sentinel
    assert calls == [{"args": (), "kwargs": sample_kwargs}]
