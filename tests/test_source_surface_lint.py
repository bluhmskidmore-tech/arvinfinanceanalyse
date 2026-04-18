from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_SOURCE_SURFACES = {
    ROOT / "backend" / "app" / "services" / "executive_service.py": "executive_analytical",
    ROOT / "backend" / "app" / "services" / "pnl_attribution_service.py": "formal_attribution",
    ROOT / "backend" / "app" / "services" / "balance_analysis_service.py": "formal_balance",
    ROOT / "backend" / "app" / "services" / "liability_analytics_service.py": "formal_liability",
    ROOT / "backend" / "app" / "services" / "bond_analytics_service.py": "bond_analytics",
    ROOT / "backend" / "app" / "services" / "bond_dashboard_service.py": "bond_analytics",
    ROOT / "backend" / "app" / "services" / "risk_tensor_service.py": "risk_tensor",
    ROOT / "backend" / "app" / "services" / "cashflow_projection_service.py": "cashflow",
    ROOT / "backend" / "app" / "services" / "pnl_bridge_service.py": "pnl_bridge",
}


def test_governed_service_files_pin_expected_source_surface_literals() -> None:
    for path, literal in EXPECTED_SOURCE_SURFACES.items():
        src = path.read_text(encoding="utf-8")
        assert f'source_surface="{literal}"' in src, f"{path} missing source_surface={literal!r}"
