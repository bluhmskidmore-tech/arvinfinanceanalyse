"""Input and persisted-result checks for the product-category materializer.

This is deliberately a per-year comparison, not a second computation engine.
Changed years are rebuilt from original source facts by the existing task.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from types import CodeType, FunctionType
from typing import TypedDict

import duckdb

REFRESH_STATE_VERSION = 1
PRODUCT_CATEGORY_TABLES = (
    "product_category_pnl_canonical_fact",
    "product_category_pnl_formal_read_model",
    "product_category_pnl_scenario_read_model",
)


class StoredState(TypedDict):
    schema: str
    years: dict[str, dict[str, object]]


def input_signature(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, default=_signature_value, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _signature_value(value: object) -> object:
    if isinstance(value, CodeType):
        # marshal's reference flags depend on interpreter object sharing. Hash
        # explicit code attributes instead so executing a function cannot change
        # the signature of its otherwise unchanged loaded implementation.
        return {
            "code": value.co_code.hex(),
            "constants": value.co_consts,
            "names": value.co_names,
            "variables": value.co_varnames,
            "free_variables": value.co_freevars,
            "cell_variables": value.co_cellvars,
            "argument_count": value.co_argcount,
            "positional_only_count": value.co_posonlyargcount,
            "keyword_only_count": value.co_kwonlyargcount,
            "flags": value.co_flags,
            "exceptions": value.co_exceptiontable.hex(),
        }
    return sorted(value, key=str) if isinstance(value, (set, frozenset)) else str(value)


def _implementation_files_signature() -> str:
    app_dir = Path(__file__).resolve().parents[1]
    paths = (
        "core_finance/product_category_pnl.py",
        "core_finance/field_normalization.py",
        "core_finance/config/product_category_contract.py",
        "core_finance/config/product_category_mapping.py",
        "core_finance/config/classification_rules.py",
        "config/product_category_mapping.py",
        "repositories/product_category_pnl_repo.py",
        "services/product_category_source_service.py",
        "services/source_file_hash.py",
        "tasks/product_category_pnl.py",
        "tasks/product_category_refresh_state.py",
        "schema_registry/duckdb/08_product_category_pnl.sql",
    )
    digest = hashlib.sha256()
    for relative_path in paths:
        digest.update(relative_path.encode("utf-8"))
        digest.update(hashlib.sha256((app_dir / relative_path).read_bytes()).digest())
    return digest.hexdigest()


_LOADED_FILES_SIGNATURE = _implementation_files_signature()


def implementation_signature() -> str:
    """Certify loaded code and reject a worker whose files changed after import.

    The runtime code digest also distinguishes a module imported before this task
    from the replacement that a subsequently restarted worker would execute.
    """
    current = _implementation_files_signature()
    if current != _LOADED_FILES_SIGNATURE:
        raise RuntimeError("Product-category implementation changed after worker import; restart the worker before refreshing.")
    digest = hashlib.sha256(current.encode("ascii"))
    for module_name in (
        "backend.app.core_finance.product_category_pnl",
        "backend.app.core_finance.field_normalization",
        "backend.app.core_finance.config.product_category_mapping",
        "backend.app.core_finance.config.classification_rules",
        "backend.app.repositories.product_category_pnl_repo",
        "backend.app.services.product_category_source_service",
        "backend.app.services.source_file_hash",
        "backend.app.tasks.product_category_pnl",
        __name__,
    ):
        module = sys.modules[module_name]
        digest.update(module_name.encode("utf-8"))
        for name, value in sorted(vars(module).items()):
            if isinstance(value, FunctionType) and value.__module__ == module_name:
                digest.update(name.encode("utf-8"))
                digest.update(input_signature(value.__code__).encode("ascii"))
            elif (
                name.isupper()
                and module_name != "backend.app.core_finance.config.product_category_mapping"
                and isinstance(value, (str, int, float, bool, Decimal, tuple, list, set, frozenset, dict))
            ):
                # Resolved mapping/config values are fingerprinted per year so
                # changing one year's FTP does not invalidate unrelated years.
                digest.update(name.encode("utf-8"))
                digest.update(input_signature(value).encode("ascii"))
    return digest.hexdigest()


def stored_state(
    connection: duckdb.DuckDBPyConnection,
    years: Sequence[str],
) -> StoredState:
    """Hash every stored value, independent of insertion order, with bounded memory."""
    by_year: dict[str, dict[str, object]] = {year: {} for year in years}
    schemas: dict[str, object] = {}
    empty_signature = hashlib.sha256().hexdigest()
    for table in PRODUCT_CATEGORY_TABLES:
        schemas[table] = connection.execute(f"describe {table}").fetchall()
        for tables in by_year.values():
            tables[table] = {"count": 0, "sha256": empty_signature}
        rows = connection.execute(
            f"""
            select coalesce(substr(report_date, 1, 4), '<invalid>') as report_year,
                   sha256(to_json(stored_row)) as row_hash
            from {table} as stored_row
            order by report_year, row_hash
            """
        )
        current_year: str | None = None
        digest = hashlib.sha256()
        count = 0
        while batch := rows.fetchmany(2048):
            for year, row_hash in batch:
                if current_year is not None and year != current_year:
                    by_year.setdefault(current_year, {})[table] = {"count": count, "sha256": digest.hexdigest()}
                    digest = hashlib.sha256()
                    count = 0
                current_year = str(year)
                digest.update(str(row_hash).encode("ascii"))
                count += 1
        if current_year is not None:
            by_year.setdefault(current_year, {})[table] = {"count": count, "sha256": digest.hexdigest()}
    for tables in by_year.values():
        for table in PRODUCT_CATEGORY_TABLES:
            tables.setdefault(table, {"count": 0, "sha256": empty_signature})
    return {"schema": input_signature(schemas), "years": by_year}


def reusable_years(
    *,
    manifest: Mapping[str, object] | None,
    previous_run: Mapping[str, object] | None,
    inputs: Mapping[str, str],
    stored: Mapping[str, object],
    implementation: str,
    rule_version: str,
) -> set[str]:
    if not manifest or not previous_run or previous_run.get("status") != "completed":
        return set()
    if manifest.get("run_id") != previous_run.get("run_id") or manifest.get("rule_version") != rule_version:
        return set()
    lineage = manifest.get("lineage")
    if not isinstance(lineage, dict):
        return set()
    state = lineage.get("product_category_refresh")
    if not isinstance(state, dict) or state.get("version") != REFRESH_STATE_VERSION:
        return set()
    if state.get("implementation") != implementation:
        return set()
    old_stored = state.get("stored")
    old_inputs = state.get("inputs")
    if not isinstance(old_stored, dict) or not isinstance(old_inputs, dict):
        return set()
    if old_stored.get("schema") != stored.get("schema"):
        return set()
    old_years = old_stored.get("years")
    current_years = stored.get("years")
    if not isinstance(old_years, dict) or not isinstance(current_years, dict):
        return set()
    return {
        year
        for year, fingerprint in inputs.items()
        if old_inputs.get(year) == fingerprint
        and year in old_years
        and old_years[year] == current_years.get(year)
    }
