from __future__ import annotations

from pathlib import Path

from scripts.home_macro_release_refresh_timer_preflight import run_preflight


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "docs/templates/home_macro_release_refresh_timer_enablement_packet.md"
HANDOFF = ROOT / "docs/templates/home_macro_release_refresh_scheduler_handoff.md"
CHECKLIST = ROOT / "docs/templates/home_macro_release_refresh_go_live_checklist.md"
STATUS = ROOT / "docs/handoff/2026-07-16-home-macro-release-context-timer-preflight-status.md"
NBS_EVIDENCE = ROOT / "docs/handoff/2026-07-17-nbs-gdp-fallback-evidence.md"


def test_nbs_outbound_allowlist_is_exact_and_timer_command_remains_enqueue_only() -> None:
    packet = PACKET.read_text(encoding="utf-8")

    assert "NBS allowed hosts: stats.gov.cn, www.stats.gov.cn" in packet
    assert "python scripts/home_macro_release_refresh.py --enqueue" in packet
    assert "schtasks /Create" not in packet
    assert "crontab " not in packet


def test_shadow_run_receipt_requires_official_lineage_and_selected_value_fields() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (HANDOFF, CHECKLIST, STATUS, NBS_EVIDENCE)
    )

    for field in (
        "release_url",
        "content_sha256",
        "nbs.macro.cn_gdp.quarterly",
        "selected_vendor",
        "value",
        "report_period",
        "run_id",
    ):
        assert field in text
    assert "single-writer" in text.lower()
    assert "disable NBS selection" in text
    assert "do not delete" in text.lower()


def test_repository_remains_complete_and_operations_remain_blocked() -> None:
    result = run_preflight(
        checklist_path=CHECKLIST,
        packet_path=PACKET,
        evidence_path=STATUS,
    )

    assert result["repo_status"] == "repo-complete"
    assert result["ops_status"] == "blocked"
