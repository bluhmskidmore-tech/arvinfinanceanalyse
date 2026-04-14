"""Contract: static SQL registry matches versioned DuckDB migrations (user tables only)."""

from __future__ import annotations

import duckdb
import pytest

from backend.app.schema_registry.duckdb_loader import (
    apply_registry_sql,
    load_manifest,
    main_schema_fingerprint,
    resolve_ensure,
)

_MANIFEST_ENTRIES = load_manifest()["files"]


def test_registry_full_apply_matches_ensure_chain_fingerprint() -> None:
    conn_reg = duckdb.connect(":memory:")
    try:
        apply_registry_sql(conn_reg)
        fp_reg = main_schema_fingerprint(conn_reg, exclude_meta_tables=True)
    finally:
        conn_reg.close()

    conn_ens = duckdb.connect(":memory:")
    try:
        for entry in _MANIFEST_ENTRIES:
            resolve_ensure(entry)(conn_ens)
        fp_ens = main_schema_fingerprint(conn_ens, exclude_meta_tables=True)
    finally:
        conn_ens.close()

    assert fp_reg == fp_ens
