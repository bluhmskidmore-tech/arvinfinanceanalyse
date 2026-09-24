"""Three-way schema ledger consistency: disk SQL slices vs duckdb_migrations vs manifest.json.

Any newly introduced drift between the three ledgers must turn this suite red:
- a slice on disk that is neither referenced by the migration module nor in the
  lazy-ensure exemption ledger;
- a manifest that stops matching the on-disk slices one-to-one;
- a migration that references a slice file that does not exist;
- a new gap or duplicate in the slice numbering beyond the recorded history.

"Referenced by the migration module" is decided statically: every quoted
NN_*.sql string literal in backend/app/repositories/duckdb_migrations.py
(comment lines stripped) counts as a reference. This covers _run_sql_slice
calls, direct REGISTRY_DIR reads, and recovery-map constants alike.
"""

from __future__ import annotations

import re
from pathlib import Path

import duckdb

from backend.app.schema_registry.duckdb_loader import (
    REGISTRY_DIR,
    load_manifest,
    resolve_ensure,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_MIGRATIONS_SOURCE = (
    _REPO_ROOT / "backend" / "app" / "repositories" / "duckdb_migrations.py"
)

# Historical fact: slice number 26 was never issued. Migration v26 already ran
# 25_pnl_by_business_precompute.sql, so the file number was skipped and the
# numbering is frozen. Any other gap is new drift and must fail.
_HISTORICAL_MISSING_SLICE_NUMBERS = frozenset({26})

# Slices intentionally NOT wired into register_all; the schema is guaranteed
# by lazy ensure calls at runtime. Kept in sync with the lazy_ensure_exempt
# entries in manifest.json and the ledger note above register_all in
# duckdb_migrations.py. Growing this set is an explicit review decision.
_EXPECTED_LAZY_ENSURE_EXEMPT = frozenset(
    {
        "30_stock_adjustment_factor.sql",
        "31_livermore_matched_baseline.sql",
    }
)

# Tables created by the exempt slices, used to verify the registered lazy
# ensure entry points actually provision the schema.
_EXPECTED_LAZY_ENSURE_TABLES = frozenset(
    {
        "stock_adjustment_factor",
        "livermore_matched_baseline_history",
    }
)

_SQL_LITERAL = re.compile(r"[\"'](\d{2}_[a-z0-9_]+\.sql)[\"']")
_SLICE_NUMBER = re.compile(r"^(\d{2})_")


def _disk_slice_names() -> set[str]:
    return {path.name for path in REGISTRY_DIR.glob("*.sql")}


def _migration_referenced_slices() -> set[str]:
    referenced: set[str] = set()
    for line in _MIGRATIONS_SOURCE.read_text(encoding="utf-8").splitlines():
        code = line.split("#", 1)[0]
        referenced.update(_SQL_LITERAL.findall(code))
    return referenced


def _manifest_entries() -> list[dict]:
    return load_manifest()["files"]


def _lazy_exempt_paths() -> set[str]:
    return {
        entry["path"]
        for entry in _manifest_entries()
        if entry.get("lazy_ensure_exempt") is True
    }


def _slice_number(name: str) -> int:
    match = _SLICE_NUMBER.match(name)
    assert match is not None, f"slice file name without NN_ prefix: {name}"
    return int(match.group(1))


def test_every_disk_slice_is_registered_or_lazily_exempt() -> None:
    disk = _disk_slice_names()
    referenced = _migration_referenced_slices()
    exempt = _lazy_exempt_paths()

    assert exempt == set(_EXPECTED_LAZY_ENSURE_EXEMPT), (
        "lazy-ensure exemption ledger changed; update the expected set only "
        "as an explicit review decision"
    )
    assert referenced & exempt == set(), (
        "a slice is both referenced by duckdb_migrations and marked "
        "lazy_ensure_exempt; drop the stale exemption record"
    )

    unaccounted = disk - referenced - exempt
    assert unaccounted == set(), (
        "disk slices neither referenced by duckdb_migrations nor recorded as "
        f"lazy-ensure exempt: {sorted(unaccounted)}"
    )


def test_migration_referenced_slices_exist_on_disk() -> None:
    missing = _migration_referenced_slices() - _disk_slice_names()
    assert missing == set(), (
        f"duckdb_migrations references slice files missing on disk: {sorted(missing)}"
    )


def test_manifest_matches_disk_one_to_one() -> None:
    manifest_paths = [entry["path"] for entry in _manifest_entries()]

    assert len(manifest_paths) == len(set(manifest_paths)), "duplicate manifest entries"
    assert set(manifest_paths) == _disk_slice_names(), (
        "manifest.json and on-disk *.sql slices no longer match one-to-one"
    )

    numbers = [_slice_number(path) for path in manifest_paths]
    assert numbers == sorted(numbers), "manifest entries must stay in slice-number order"


def test_slice_numbering_gaps_match_recorded_history() -> None:
    disk = _disk_slice_names()
    numbers = [_slice_number(name) for name in disk]

    assert len(numbers) == len(set(numbers)), "duplicate slice numbers on disk"

    gaps = set(range(1, max(numbers) + 1)) - set(numbers)
    assert gaps == set(_HISTORICAL_MISSING_SLICE_NUMBERS), (
        "slice numbering gaps drifted from the recorded history "
        f"(expected only {sorted(_HISTORICAL_MISSING_SLICE_NUMBERS)}, got {sorted(gaps)})"
    )


def test_manifest_entries_declare_resolvable_ensure_symbols() -> None:
    for entry in _manifest_entries():
        assert entry.get("path"), f"manifest entry without path: {entry}"
        assert entry.get("ensure_module") and entry.get("ensure_symbol"), (
            f"manifest entry {entry['path']} lacks ensure_module/ensure_symbol"
        )
        assert callable(resolve_ensure(entry)), (
            f"manifest entry {entry['path']} ensure symbol is not callable"
        )


def test_lazy_exempt_entries_carry_reason_and_callsites() -> None:
    exempt_entries = [
        entry for entry in _manifest_entries() if entry.get("lazy_ensure_exempt") is True
    ]
    assert {entry["path"] for entry in exempt_entries} == set(_EXPECTED_LAZY_ENSURE_EXEMPT)
    for entry in exempt_entries:
        assert str(entry.get("lazy_ensure_reason", "")).strip(), (
            f"exempt slice {entry['path']} must record a reason"
        )
        callsites = entry.get("lazy_ensure_callsites")
        assert isinstance(callsites, list) and callsites, (
            f"exempt slice {entry['path']} must record its ensure callsites"
        )
        for callsite in callsites:
            assert (_REPO_ROOT / callsite).is_file(), (
                f"exempt slice {entry['path']} records a stale callsite: {callsite}"
            )


def test_lazy_exempt_ensures_provision_schema_idempotently(tmp_path) -> None:
    db_path = tmp_path / "lazy_exempt_consistency.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        exempt_entries = [
            entry
            for entry in _manifest_entries()
            if entry.get("lazy_ensure_exempt") is True
        ]
        for entry in exempt_entries:
            ensure = resolve_ensure(entry)
            ensure(conn)
            ensure(conn)  # lazy ensure paths must stay idempotent

        tables = {
            row[0]
            for row in conn.execute(
                "select table_name from information_schema.tables where table_schema = 'main'"
            ).fetchall()
        }
    finally:
        conn.close()

    assert set(_EXPECTED_LAZY_ENSURE_TABLES) <= tables
