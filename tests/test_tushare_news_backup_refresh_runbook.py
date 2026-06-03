from __future__ import annotations

from tests.helpers import ROOT


RUNBOOK_PATH = ROOT / "docs" / "tushare_news_backup_refresh_runbook.md"


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
