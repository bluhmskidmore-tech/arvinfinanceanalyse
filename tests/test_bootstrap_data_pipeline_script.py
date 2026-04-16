from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "backend" / "scripts" / "bootstrap_data_pipeline.py"


def test_bootstrap_data_pipeline_uses_existing_sync_task_entrypoints():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "materialize_bond_analytics_facts.fn(" in text
    assert "run_formal_balance_pipeline.fn(" in text
    assert "run_pnl_materialize_sync(" in text
    assert "materialize_product_category_pnl.fn(" in text
    assert "materialize_bond_analytics(" not in text
    assert "materialize_balance_analysis(" not in text
    assert "materialize_pnl(" not in text
