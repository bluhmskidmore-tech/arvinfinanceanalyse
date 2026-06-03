from __future__ import annotations

from tests.helpers import ROOT


RUNBOOK_PATH = ROOT / "docs" / "tushare_news_backup_refresh_runbook.md"
SCHEDULER_HANDOFF_PATH = ROOT / "docs" / "templates" / "tushare_news_backup_refresh_scheduler_handoff.md"
GO_LIVE_CHECKLIST_PATH = ROOT / "docs" / "templates" / "tushare_news_backup_refresh_go_live_checklist.md"
HANDOFF_PATH = ROOT / "docs" / "handoff" / "2026-06-03-tushare-news-backup-refresh-handoff.md"


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
