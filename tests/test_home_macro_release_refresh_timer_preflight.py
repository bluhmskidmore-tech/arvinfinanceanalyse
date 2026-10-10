from __future__ import annotations

from pathlib import Path

from scripts.home_macro_release_refresh_timer_preflight import run_preflight

ROOT = Path(__file__).resolve().parents[1]


def test_repository_packet_is_repo_complete_but_ops_blocked_until_fields_are_filled() -> None:
    result = run_preflight(
        checklist_path=ROOT / "docs/templates/home_macro_release_refresh_go_live_checklist.md",
        packet_path=ROOT / "docs/templates/home_macro_release_refresh_timer_enablement_packet.md",
        evidence_path=ROOT / "docs/handoff/2026-07-16-home-macro-release-context-timer-preflight-status.md",
    )

    assert result["repo_status"] == "repo-complete"
    assert result["ops_status"] == "blocked"
    assert set(result["missing_fields"]) >= {
        "owner",
        "timer_host",
        "write_window",
        "log_path",
        "rollback",
        "first_scheduled_run_evidence",
    }


def test_preflight_becomes_ready_only_when_all_external_evidence_is_present(tmp_path: Path) -> None:
    checklist = tmp_path / "checklist.md"
    packet = tmp_path / "packet.md"
    evidence = tmp_path / "evidence.md"
    checklist.write_text(
        "Owner: Macro Ops\nRollback: disable external timer and alert Macro Ops\n",
        encoding="utf-8",
    )
    packet.write_text(
        "Timer host: ops-host-1\nWrite window: Asia/Shanghai 10:30 and 18:30\nLog path: D:/logs/home-macro.log\n",
        encoding="utf-8",
    )
    evidence.write_text("First scheduled run evidence: run-20260717-1030\n", encoding="utf-8")

    result = run_preflight(
        checklist_path=checklist,
        packet_path=packet,
        evidence_path=evidence,
    )

    assert result["ops_status"] == "ready"
    assert result["missing_fields"] == []


def test_enablement_packet_never_contains_scheduler_install_commands() -> None:
    text = (
        ROOT / "docs/templates/home_macro_release_refresh_timer_enablement_packet.md"
    ).read_text(encoding="utf-8").lower()

    assert "schtasks /create" not in text
    assert "crontab " not in text
    assert "--enqueue" in text
