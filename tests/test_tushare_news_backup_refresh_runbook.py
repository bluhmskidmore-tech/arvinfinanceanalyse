from __future__ import annotations

from tests.helpers import ROOT, load_module


RUNBOOK_PATH = ROOT / "docs" / "tushare_news_backup_refresh_runbook.md"
SCHEDULER_HANDOFF_PATH = ROOT / "docs" / "templates" / "tushare_news_backup_refresh_scheduler_handoff.md"
GO_LIVE_CHECKLIST_PATH = ROOT / "docs" / "templates" / "tushare_news_backup_refresh_go_live_checklist.md"
TIMER_ENABLEMENT_PACKET_PATH = (
    ROOT / "docs" / "templates" / "tushare_news_backup_timer_enablement_packet.md"
)
HANDOFF_PATH = ROOT / "docs" / "handoff" / "2026-06-03-tushare-news-backup-refresh-handoff.md"
GO_LIVE_EVIDENCE_PATH = (
    ROOT / "docs" / "handoff" / "2026-06-03-tushare-news-backup-refresh-go-live-evidence.md"
)
TIMER_PREFLIGHT_STATUS_PATH = (
    ROOT / "docs" / "handoff" / "2026-06-03-tushare-news-backup-timer-preflight-status.md"
)


def _load_preflight_module():
    return load_module(
        "scripts.tushare_news_backup_timer_preflight",
        "scripts/tushare_news_backup_timer_preflight.py",
    )


def test_tushare_news_backup_refresh_runbook_documents_operator_contract() -> None:
    runbook = RUNBOOK_PATH.read_text(encoding="utf-8")

    assert "scripts/refresh_tushare_news_backup.py" in runbook
    assert "--dry-run" in runbook
    assert "--enqueue" in runbook
    assert "MOSS_TUSHARE_TOKEN" in runbook
    assert "ingest_tushare_news_to_choice_news" in runbook
    assert "current_backup_state.status" in runbook
    assert "latest_received_at" in runbook
    assert "error_rows" in runbook
    assert "blank_payload_rows" in runbook
    assert "tushare.major_news" in runbook
    assert "tushare.news.sina" in runbook
    assert "tushare.npr" in runbook
    assert "/ui/news/tushare-npr/ingest" in runbook
    assert "/api/news/tushare-npr/ingest" in runbook
    assert "reserved" in runbook.lower()
    assert "docs/templates/tushare_news_backup_refresh_scheduler_handoff.md" in runbook
    assert "docs/templates/tushare_news_backup_refresh_go_live_checklist.md" in runbook
    assert "docs/templates/tushare_news_backup_timer_enablement_packet.md" in runbook
    assert "docs/handoff/2026-06-03-tushare-news-backup-timer-preflight-status.md" in runbook
    assert "scripts/tushare_news_backup_timer_preflight.py" in runbook
    assert "--stage all" in runbook
    assert "--stage pre-enable" in runbook
    assert "--stage post-enable" in runbook
    assert "timer enablement packet is filled" in runbook
    assert "actual install commands" in runbook
    assert "browser evidence JSON confirms" in runbook
    assert "Go-live evidence must no longer say `not enabled`" in runbook
    assert "Timer evidence in go-live bundle" in runbook
    assert "next_actions" in runbook


def test_tushare_news_backup_refresh_scheduler_handoff_keeps_scheduling_out_of_page_path() -> None:
    handoff = SCHEDULER_HANDOFF_PATH.read_text(encoding="utf-8")

    assert "scripts/refresh_tushare_news_backup.py" in handoff
    assert "--dry-run" in handoff
    assert "--enqueue" in handoff
    assert "MOSS_TUSHARE_TOKEN" in handoff
    assert "Windows Task Scheduler" in handoff
    assert "cron" in handoff
    assert "single writer" in handoff
    assert "/ui/news/choice-events/latest" in handoff
    assert "/ui/news/tushare-npr/ingest" in handoff
    assert "/api/news/tushare-npr/ingest" in handoff
    assert "Do not schedule the homepage" in handoff
    assert "scripts/tushare_news_backup_timer_preflight.py" in handoff
    assert "--stage all" in handoff
    assert "--stage pre-enable" in handoff
    assert "--stage post-enable" in handoff
    assert "preflight returns `blocked`" in handoff
    assert "docs/templates/tushare_news_backup_timer_enablement_packet.md" in handoff


def test_tushare_news_backup_refresh_go_live_checklist_requires_evidence_before_timer_enablement() -> None:
    checklist = GO_LIVE_CHECKLIST_PATH.read_text(encoding="utf-8")

    assert "MOSS_TUSHARE_TOKEN" in checklist
    assert "credential owner" in checklist.lower()
    assert "schedule owner" in checklist.lower()
    assert "dry-run evidence" in checklist.lower()
    assert "first-run evidence" in checklist.lower()
    assert "post-run dry-run" in checklist.lower()
    assert "page evidence" in checklist.lower()
    assert "latest_received_at" in checklist
    assert "error_rows" in checklist
    assert "blank_payload_rows" in checklist
    assert "/ui/news/choice-events/latest" in checklist
    assert "/ui/news/tushare-npr/ingest" in checklist
    assert "/api/news/tushare-npr/ingest" in checklist
    assert "rollback owner" in checklist.lower()
    assert "Do not enable the timer" in checklist
    assert "scripts/tushare_news_backup_timer_preflight.py" in checklist
    assert "--stage all" in checklist
    assert "--stage pre-enable" in checklist
    assert "--stage post-enable" in checklist
    assert "returns `pass`" in checklist
    assert "External timer enablement: enabled" in checklist
    assert "Timer evidence in go-live bundle" in checklist
    assert "docs/templates/tushare_news_backup_timer_enablement_packet.md" in checklist
    assert "Timer enablement packet" in checklist


def test_tushare_news_backup_timer_enablement_packet_is_ops_fillable_not_executable() -> None:
    packet = TIMER_ENABLEMENT_PACKET_PATH.read_text(encoding="utf-8")

    assert "Timer Enablement Packet" in packet
    assert "This packet does not enable the timer" in packet
    assert "Credential owner: `<team/person>`" in packet
    assert "Schedule owner: `<team/person>`" in packet
    assert "Timer host: `<hostname>`" in packet
    assert "Python executable: `<absolute python path>`" in packet
    assert "DuckDB path: `data/moss.duckdb`" in packet
    assert "Log path: `<absolute log path>`" in packet
    assert "Refresh window: `<local time and timezone>`" in packet
    assert "Windows Task Scheduler command draft" in packet
    assert "Cron command draft" in packet
    assert "scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina" in packet
    assert "scripts/refresh_tushare_news_backup.py --duckdb-path data/moss.duckdb --news-src sina --dry-run" in packet
    assert "scripts/tushare_news_backup_timer_preflight.py" in packet
    assert "--stage all" in packet
    assert "--stage pre-enable" in packet
    assert "--stage post-enable" in packet
    assert "preflight must return `pass` before enablement" in packet
    assert "External timer enablement: enabled" in packet
    assert "Timer evidence in go-live bundle" in packet
    assert "timer_enablement_packet_filled" in packet
    assert "No `schtasks /Create` command is provided" in packet
    assert "No `crontab` install command is provided" in packet
    assert "POST /ui/news/tushare-npr/ingest" in packet
    assert "POST /api/news/tushare-npr/ingest" in packet
    assert "/ui/news/choice-events/latest" in packet
    assert "Rollback owner: `<team/person>`" in packet


def test_tushare_news_backup_refresh_handoff_records_delivery_scope_and_verification() -> None:
    handoff = HANDOFF_PATH.read_text(encoding="utf-8")

    assert "buildHomeMacroBriefingModel.ts" in handoff
    assert "backend/app/tasks/choice_news.py" in handoff
    assert "scripts/refresh_tushare_news_backup.py" in handoff
    assert "docs/templates/tushare_news_backup_refresh_scheduler_handoff.md" in handoff
    assert "docs/templates/tushare_news_backup_refresh_go_live_checklist.md" in handoff
    assert "MOSS_TUSHARE_TOKEN" in handoff
    assert "current_backup_state.status" in handoff
    assert "latest_received_at" in handoff
    assert "error_rows" in handoff
    assert "blank_payload_rows" in handoff
    assert "/ui/news/choice-events/latest" in handoff
    assert "/ui/news/tushare-npr/ingest" in handoff
    assert "/api/news/tushare-npr/ingest" in handoff
    assert "No real Tushare call" in handoff
    assert "npm run debt:audit" in handoff


def test_tushare_news_backup_refresh_go_live_evidence_records_first_operator_refresh() -> None:
    evidence = GO_LIVE_EVIDENCE_PATH.read_text(encoding="utf-8")

    assert "current_backup_state.status" in evidence
    assert "status = completed" in evidence
    assert "fetched = 1203" in evidence
    assert "inserted = 1203" in evidence
    assert "purged_expired = 97" in evidence
    assert "tushare.major_news" in evidence
    assert "2026-06-03T19:43:00+00:00" in evidence
    assert "tushare.news.sina" in evidence
    assert "2026-06-03T20:19:24+00:00" in evidence
    assert "error_rows` is `0`" in evidence
    assert "blank_payload_rows` is `0`" in evidence
    assert "Page Evidence" in evidence
    assert "2026-06-03T12:45:10.381Z" in evidence
    assert "frontend/.codex-tmp/tushare-news-backup-home-page-evidence-2026-06-03.png" in evidence
    assert "frontend/.codex-tmp/tushare-news-backup-home-page-evidence-2026-06-03.json" in evidence
    assert "来源：Tushare 宏观快讯（Choice 不可用或偏旧兜底）" in evidence
    assert "来源状态：Tushare 兜底" in evidence
    assert "刷新：随页面查询读取已落库数据" in evidence
    assert "hasAutoUpdateCopy`: `false" in evidence
    assert "hasReservedIngestWriteRequest`: `false" in evidence
    assert "/ui/news/choice-events/latest" in evidence
    assert "/ui/news/tushare-npr/ingest" in evidence
    assert "/api/news/tushare-npr/ingest" in evidence
    assert "External timer enablement: not enabled" in evidence
    assert "scripts/tushare_news_backup_timer_preflight.py" in evidence
    assert "`pass` verdict" in evidence
    assert "schedule owner" in evidence.lower()
    assert "rollback owner" in evidence.lower()


def test_tushare_news_backup_timer_preflight_status_records_current_blockers_and_next_actions() -> None:
    status = TIMER_PREFLIGHT_STATUS_PATH.read_text(encoding="utf-8")

    assert "Tushare News Backup Timer Preflight Status" in status
    assert "External timer is not enabled" in status
    assert "--stage all" in status
    assert "pre-enable" in status
    assert "post-enable" in status
    assert "owners_filled" in status
    assert "boundary_confirmation_filled" in status
    assert "timer_enablement_packet_filled" in status
    assert "page_acceptance_signoff_filled" in status
    assert "enable_timer_decision_yes" in status
    assert "timer_evidence_filled" in status
    assert "post_enable_evidence_confirms_timer_enabled" in status
    assert "next_actions" in status
    assert "docs/templates/tushare_news_backup_refresh_go_live_checklist.md" in status
    assert "docs/templates/tushare_news_backup_timer_enablement_packet.md" in status
    assert "docs/handoff/2026-06-03-tushare-news-backup-refresh-go-live-evidence.md" in status
    assert "Do not enable the timer" in status


def test_tushare_news_backup_timer_preflight_status_matches_current_preflight_report() -> None:
    status = TIMER_PREFLIGHT_STATUS_PATH.read_text(encoding="utf-8")
    module = _load_preflight_module()

    pre_enable = module.build_timer_preflight_report(repo_root=ROOT, stage="pre-enable")
    post_enable = module.build_timer_preflight_report(repo_root=ROOT, stage="post-enable")

    assert pre_enable["verdict"] == "blocked"
    assert post_enable["verdict"] == "blocked"

    for item in pre_enable["blocking_items"]:
        assert f"`{item}`" in status

    for item in post_enable["blocking_items"]:
        assert f"`{item}`" in status

    for action in pre_enable["next_actions"] + post_enable["next_actions"]:
        assert f"`{action['gate']}`" in status
        assert f"`{action['path']}`" in status
        assert action["action"] in status
