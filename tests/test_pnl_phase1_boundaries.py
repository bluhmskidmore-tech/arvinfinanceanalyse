from __future__ import annotations

"""
PnL domain scaffolding vs Phase 1 boundary.

`/ui/pnl/attribution` and core `pnl` modules are thin slices / start-pack code present in the repo.
Their existence does **not** imply repo-wide Phase 2 formal finance cutover (see `docs/IMPLEMENTATION_PLAN.md`).
"""

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import app


def test_existing_ui_pnl_attribution_placeholder_remains_available_during_pnl_domain_scaffolding():
    client = TestClient(app)

    response = client.get("/ui/pnl/attribution")

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "analytical"
    assert payload["result_meta"]["formal_use_allowed"] is False
    assert payload["result_meta"]["result_kind"] == "executive.pnl-attribution"


def test_ui_pnl_attribution_placeholder_contract_does_not_claim_formal_pnl_ownership():
    client = TestClient(app)

    payload = client.get("/ui/pnl/attribution").json()

    assert payload["result_meta"]["scenario_flag"] is False
    assert payload["result"]["title"]
    assert "segments" in payload["result"]
    assert "total" in payload["result"]


def test_product_category_pnl_slice_modules_exist_as_local_thin_slice_not_repo_wide_phase2():
    """Files exist as an independent product slice; not evidence of global phase promotion."""
    root = Path(__file__).resolve().parents[1]

    assert (root / "backend/app/api/routes/product_category_pnl.py").exists()
    assert (root / "backend/app/services/product_category_pnl_service.py").exists()
    assert (root / "backend/app/core_finance/product_category_pnl.py").exists()


def test_phase1_pnl_http_and_core_modules_exist():
    root = Path(__file__).resolve().parents[1]

    assert (root / "backend/app/api/routes/pnl.py").exists()
    assert (root / "backend/app/services/pnl_service.py").exists()
    assert (root / "backend/app/schemas/pnl.py").exists()
    assert (root / "backend/app/core_finance/pnl.py").is_file()
