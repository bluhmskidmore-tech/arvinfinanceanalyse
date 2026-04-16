from __future__ import annotations

import json

from tests.helpers import load_module


def test_executive_surfaces_do_not_emit_shell_demo_markers(tmp_path, monkeypatch):
    module = load_module(
        "backend.app.services.executive_service",
        "backend/app/services/executive_service.py",
    )
    monkeypatch.setattr(module, "get_settings", lambda: type("Settings", (), {"duckdb_path": tmp_path / "missing.duckdb"})())

    payloads = [
        module.executive_overview(),
        module.executive_pnl_attribution(),
        module.executive_risk_overview(),
        module.executive_contribution(),
        module.executive_alerts(),
    ]

    rendered = json.dumps(payloads, ensure_ascii=False)

    assert "shell" not in rendered.lower()
    assert "demo" not in rendered.lower()
    assert "演示" not in rendered
    assert "sv_exec_dashboard_shell_demo" not in rendered
    assert all(payload["result_meta"]["source_version"] != "sv_exec_dashboard_v1" for payload in payloads)
