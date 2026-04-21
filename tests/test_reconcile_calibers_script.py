"""Tests for reconcile_calibers skeleton script."""

from __future__ import annotations

from pathlib import Path

from backend.app.core_finance.calibers import list_caliber_rules

from tests.helpers import load_module

ROOT = Path(__file__).resolve().parents[1]


def _load_mod():
    return load_module(
        "backend.scripts.reconcile_calibers",
        "backend/scripts/reconcile_calibers.py",
    )


def test_main_writes_dated_markdown(tmp_path: Path) -> None:
    mod = _load_mod()
    dest = tmp_path / "caliber-reconciliation-2026-04-21.md"
    try:
        code = mod.main(
            [
                "--date",
                "2026-04-21",
                f"--output-dir={tmp_path.as_posix()}",
            ]
        )
        assert code == 0
        assert dest.is_file()
        text = dest.read_text(encoding="utf-8")
        assert "2026-04-21" in text
    finally:
        if dest.is_file():
            dest.unlink()


def test_report_mentions_all_5_rule_ids(tmp_path: Path) -> None:
    mod = _load_mod()
    dest = tmp_path / "caliber-reconciliation-2026-04-21.md"
    try:
        mod.main(
            [
                "--date",
                "2026-04-21",
                f"--output-dir={tmp_path.as_posix()}",
            ]
        )
        text = dest.read_text(encoding="utf-8")
        for r in list_caliber_rules():
            assert r.rule_id in text
    finally:
        if dest.is_file():
            dest.unlink()
