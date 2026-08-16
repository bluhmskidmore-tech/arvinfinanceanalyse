"""Source version fingerprints must change when file content changes.

Guards the content-hash component of the service-level source versions:
same file name, same size, same mtime, different bytes must yield a
different source version (mirrors the fixed pattern covered by
tests/test_source_preview_flow.py for source_preview_parsers).
"""

from __future__ import annotations

import os
from pathlib import Path

from backend.app.services.pnl_source_service import (
    _build_source_version as build_pnl_source_version,
)
from backend.app.services.product_category_source_service import (
    _build_source_version as build_product_category_source_version,
)
from backend.app.services.qdb_gl_input_validation_service import (
    _build_source_version as build_qdb_gl_source_version,
)


def _rewrite_keeping_size_and_mtime(path: Path, content: bytes) -> None:
    original_stat = path.stat()
    path.write_bytes(content)
    os.utime(path, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    assert path.stat().st_size == original_stat.st_size
    assert path.stat().st_mtime_ns == original_stat.st_mtime_ns


def test_pnl_source_version_changes_when_content_changes_with_same_size_and_mtime(tmp_path: Path):
    source_path = tmp_path / "损益表202401.xls"
    source_path.write_bytes(b"first-content")

    first_version = build_pnl_source_version(source_path)
    stable_version = build_pnl_source_version(source_path)

    _rewrite_keeping_size_and_mtime(source_path, b"other-content")
    changed_version = build_pnl_source_version(source_path)

    assert stable_version == first_version
    assert first_version.startswith("sv_pnl_")
    assert changed_version != first_version


def test_qdb_gl_source_version_changes_when_content_changes_with_same_size_and_mtime(tmp_path: Path):
    source_path = tmp_path / "总账对账202401.xlsx"
    source_path.write_bytes(b"first-content")

    first_version = build_qdb_gl_source_version(source_path)
    stable_version = build_qdb_gl_source_version(source_path)

    _rewrite_keeping_size_and_mtime(source_path, b"other-content")
    changed_version = build_qdb_gl_source_version(source_path)

    assert stable_version == first_version
    assert first_version.startswith("sv_qdb_gl_")
    assert changed_version != first_version


def test_qdb_gl_source_version_for_missing_path_stays_stable(tmp_path: Path):
    missing_path = tmp_path / "总账对账209901.xlsx"

    first_version = build_qdb_gl_source_version(missing_path)
    stable_version = build_qdb_gl_source_version(missing_path)

    assert stable_version == first_version
    assert first_version.startswith("sv_qdb_gl_")


def test_product_category_source_version_changes_when_content_changes_with_same_size_and_mtime(
    tmp_path: Path,
):
    ledger_path = tmp_path / "总账对账202401.xlsx"
    avg_path = tmp_path / "日均202401.xlsx"
    ledger_path.write_bytes(b"ledger-content")
    avg_path.write_bytes(b"first-content")

    first_version = build_product_category_source_version(ledger_path, avg_path)
    stable_version = build_product_category_source_version(ledger_path, avg_path)

    _rewrite_keeping_size_and_mtime(avg_path, b"other-content")
    changed_version = build_product_category_source_version(ledger_path, avg_path)

    assert stable_version == first_version
    assert first_version.startswith("sv_product_category_")
    assert changed_version != first_version
