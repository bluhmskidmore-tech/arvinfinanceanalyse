from __future__ import annotations

from pathlib import Path


def test_kpi_route_stays_a_thin_http_boundary():
    source = Path("backend/app/api/routes/kpi.py").read_text(encoding="utf-8")

    assert "kpi_workbench_service" in source
    assert "KpiRepository" not in source
    assert "_session_factory" not in source
    assert "session.commit" not in source
    assert "_compute_completion_ratio" not in source
    assert "_compute_score_value" not in source
