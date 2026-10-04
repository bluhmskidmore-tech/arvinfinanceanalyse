from __future__ import annotations

from types import SimpleNamespace

from backend.app.tasks.pnl_materialize import compose_formal_pnl_source_version


def _row(source_version: str) -> SimpleNamespace:
    return SimpleNamespace(source_version=source_version)


def test_formal_pnl_source_version_is_sorted_deduplicated_union() -> None:
    formal_fi_rows = [_row("source-c"), _row("source-a"), _row("")]
    bridge_rows = [_row("source-b"), _row("source-a")]

    assert compose_formal_pnl_source_version(formal_fi_rows, bridge_rows) == (
        "source-a__source-b__source-c"
    )


def test_formal_pnl_source_version_uses_existing_empty_partition_identity() -> None:
    assert compose_formal_pnl_source_version([], []) == "sv_pnl_empty"
    assert compose_formal_pnl_source_version([_row("")], [_row("")]) == "sv_pnl_empty"
