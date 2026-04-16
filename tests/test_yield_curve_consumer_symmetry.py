"""
Single-point parity between curve consumers (see docs/CURRENT_EXECUTION_UPDATE_2026-04-12.md).

`_resolve_curve_for_service` must use `format_yield_curve_latest_fallback_warning` from
`yield_curve_repo` so fallback warnings stay single-sourced.
"""

from __future__ import annotations

from tests.helpers import ROOT


def test_pnl_bridge_and_bond_analytics_import_shared_fallback_formatter():
    paths = [
        ROOT / "backend" / "app" / "services" / "pnl_bridge_service.py",
        ROOT / "backend" / "app" / "services" / "bond_analytics_service.py",
    ]
    needle = "format_yield_curve_latest_fallback_warning"
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert needle in text, path
        assert "from backend.app.repositories.yield_curve_repo import" in text
    repo_text = (ROOT / "backend" / "app" / "repositories" / "yield_curve_repo.py").read_text(encoding="utf-8")
    assert "def format_yield_curve_latest_fallback_warning" in repo_text


_CORRUPT_LINEAGE_SUBSTRING = (
    "Corrupt or inconsistent {curve_type} curve snapshot lineage for trade_date="
)


def test_pnl_bridge_and_bond_analytics_share_corrupt_lineage_error_template():
    paths = [
        ROOT / "backend" / "app" / "services" / "pnl_bridge_service.py",
        ROOT / "backend" / "app" / "services" / "bond_analytics_service.py",
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert text.count(_CORRUPT_LINEAGE_SUBSTRING) == 2, path
