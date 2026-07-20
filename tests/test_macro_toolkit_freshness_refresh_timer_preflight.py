from __future__ import annotations

from pathlib import Path

from scripts.macro_toolkit_freshness_refresh_timer_preflight import run_preflight

ROOT = Path(__file__).resolve().parents[1]


def test_macro_toolkit_freshness_timer_preflight_repo_complete() -> None:
    result = run_preflight(
        checklist_path=ROOT / "docs/templates/macro_toolkit_freshness_refresh_go_live_checklist.md",
        packet_path=ROOT / "docs/templates/macro_toolkit_freshness_refresh_timer_enablement_packet.md",
        evidence_path=ROOT / "docs/handoff/2026-07-20-macro-toolkit-freshness-timer-preflight-status.md",
    )
    assert result["repo_status"] == "repo-complete"
    assert result["packet_safe"] is True
    assert "schtasks /create" not in (
        ROOT / "docs/templates/macro_toolkit_freshness_refresh_timer_enablement_packet.md"
    ).read_text(encoding="utf-8").lower()
