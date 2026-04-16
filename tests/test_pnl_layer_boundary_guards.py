from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_APP = ROOT / "backend" / "app"
PNL_CORE_FILE = BACKEND_APP / "core_finance" / "pnl.py"
CORE_FINANCE_INIT = BACKEND_APP / "core_finance" / "__init__.py"

FORBIDDEN_IMPORT_ROOTS = (
    BACKEND_APP / "api",
    BACKEND_APP / "repositories",
)

PNL_CORE_MODULE = "backend.app.core_finance.pnl"
PNL_PACKAGE_MODULE = "backend.app.core_finance"

# PnL-specific private helpers must not be duplicated outside the core module.
PNL_PRIVATE_HELPER_NAMES = (
    "_normalize_fi_invest_type",
    "_normalize_nonstd_signed_amount",
    "_entry_in_scope",
)


def _py_files_under(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(directory.rglob("*.py"))


def _read_py_source(path: Path) -> str:
    # utf-8-sig strips a leading BOM if present (some editors add U+FEFF).
    return path.read_text(encoding="utf-8-sig")


def _pnl_public_names_reexported_via_core_finance_init() -> frozenset[str]:
    """Names pulled from `core_finance.pnl` and re-exported by `core_finance/__init__.py`.

    This stays aligned with the package surface without hard-coding a duplicate symbol list.
    Only `ImportFrom` the pnl submodule is considered, so future non-PnL exports from
    `__init__.py` do not widen this guard.
    """
    text = _read_py_source(CORE_FINANCE_INIT)
    tree = ast.parse(text, filename=str(CORE_FINANCE_INIT))
    names: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        from_pnl = node.module == PNL_CORE_MODULE or (
            node.level == 1 and node.module == "pnl"
        )
        if not from_pnl:
            continue
        for alias in node.names:
            if alias.name == "*":
                raise AssertionError(
                    f"{CORE_FINANCE_INIT}: star-import from pnl prevents deriving the PnL entrypoint set"
                )
            names.add(alias.name)
    if not names:
        raise AssertionError(
            f"Expected {CORE_FINANCE_INIT} to re-export symbols from {PNL_CORE_MODULE} "
            "(or relative .pnl); found none."
        )
    return frozenset(names)


PNL_REEXPORTED_VIA_PACKAGE_INIT = _pnl_public_names_reexported_via_core_finance_init()


def _violations_for_imports(path: Path) -> list[str]:
    text = _read_py_source(path)
    tree = ast.parse(text, filename=str(path))
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name == PNL_CORE_MODULE or name.startswith(f"{PNL_CORE_MODULE}."):
                    out.append(f"{path}: forbidden import of {name}")
                if name == PNL_PACKAGE_MODULE:
                    bound_name = alias.asname or name.rsplit(".", 1)[-1]
                    if bound_name == "pnl":
                        out.append(f"{path}: forbidden package import alias {name} as {bound_name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            if node.module == PNL_CORE_MODULE:
                out.append(f"{path}: forbidden ImportFrom {node.module}")
            if node.module == PNL_PACKAGE_MODULE:
                imported = {alias.name for alias in node.names}
                if "pnl" in imported:
                    out.append(f"{path}: forbidden ImportFrom {node.module} import pnl")
                if any(alias.name == "*" for alias in node.names):
                    out.append(f"{path}: forbidden ImportFrom {node.module} import *")
                else:
                    bad = imported & PNL_REEXPORTED_VIA_PACKAGE_INIT
                    if bad:
                        out.append(
                            f"{path}: forbidden ImportFrom {node.module} "
                            f"import PnL entrypoints {sorted(bad)}"
                        )
    return out


def test_pnl_core_module_file_exists():
    assert PNL_CORE_FILE.is_file(), f"Missing formal PnL core module: {PNL_CORE_FILE}"


def test_api_and_repositories_do_not_import_core_finance_pnl():
    """Thin layers must not import `core_finance.pnl` or PnL symbols re-exported by `core_finance`."""
    violations: list[str] = []
    for base in FORBIDDEN_IMPORT_ROOTS:
        for path in _py_files_under(base):
            violations.extend(_violations_for_imports(path))
    assert not violations, "PnL formal entrypoints leaked into API/repositories:\n" + "\n".join(violations)


def test_pnl_private_helpers_are_not_redefined_outside_core_pnl_module():
    """Formal PnL normalization helpers must stay centralized in core_finance/pnl.py."""
    offenders: list[str] = []
    for path in _py_files_under(BACKEND_APP):
        if path.resolve() == PNL_CORE_FILE.resolve():
            continue
        tree = ast.parse(_read_py_source(path), filename=str(path))
        defined = {
            node.name
            for node in tree.body
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef)
        }
        for name in PNL_PRIVATE_HELPER_NAMES:
            if name in defined:
                offenders.append(f"{path}: redefines {name}")
    assert not offenders, "PnL private helpers duplicated outside core module:\n" + "\n".join(offenders)
