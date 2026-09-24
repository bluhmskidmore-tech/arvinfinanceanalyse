from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import duckdb

from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection
from backend.app.repositories.stock_official_disclosure_repo import (
    get_stock_official_disclosure_sync_status,
    list_stock_official_disclosures,
    upsert_stock_official_disclosure_sync_status,
    upsert_stock_official_disclosures,
)
from backend.app.repositories.task_write_guard import repository_task_write_scope

SOURCE_LABEL = "\u4e0a\u5e02\u516c\u53f8\u516c\u544a\u539f\u6587\uff08Tushare\uff09"
STOCK_NAME = "\u62d3\u8346\u79d1\u6280"
REPORT_TITLE = "\u62d3\u8346\u79d1\u6280\u80a1\u4efd\u6709\u9650\u516c\u53f82025\u5e74\u5e74\u5ea6\u62a5\u544a"
NOTICE_TITLE = "\u5173\u4e8e2025\u5e74\u5e74\u5ea6\u62a5\u544a\u7684\u516c\u544a"
FUTURE_TITLE = "2026\u5e74\u534a\u5e74\u5ea6\u62a5\u544a"


def test_list_stock_official_disclosures_returns_lane_shaped_payload(tmp_path: Path) -> None:
    db_path = tmp_path / "stock-official.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        apply_pending_migrations_on_connection(conn)
        with repository_task_write_scope("backend.app.tasks.stock_official_disclosure_test"):
            upsert_stock_official_disclosures(
                conn,
                rows=[
                    {
                        "disclosure_key": "k_ann",
                        "stock_code": "688072.SH",
                        "stock_name": STOCK_NAME,
                        "evidence_type": "official_announcement",
                        "publish_date": "2026-06-15",
                        "report_period": None,
                        "title": NOTICE_TITLE,
                        "document_url": "https://example.com/ann.pdf",
                        "source_id": "ann-1",
                        "source_label": SOURCE_LABEL,
                        "source_version": "sv_ann_a",
                        "vendor_version": "vv_ann_a",
                        "received_at": None,
                        "ingested_at": datetime(2026, 6, 16, 9, 0, tzinfo=UTC),
                        "run_id": "run-1",
                        "raw_json": "{}",
                    },
                    {
                        "disclosure_key": "k_rep",
                        "stock_code": "688072.SH",
                        "stock_name": STOCK_NAME,
                        "evidence_type": "financial_report",
                        "publish_date": "2026-04-20",
                        "report_period": "2025-12-31",
                        "title": REPORT_TITLE,
                        "document_url": "https://example.com/report.pdf",
                        "source_id": "rep-1",
                        "source_label": SOURCE_LABEL,
                        "source_version": "sv_rep_a",
                        "vendor_version": "vv_rep_a",
                        "received_at": None,
                        "ingested_at": datetime(2026, 4, 21, 8, 0, tzinfo=UTC),
                        "run_id": "run-2",
                        "raw_json": "{}",
                    },
                    {
                        "disclosure_key": "k_future",
                        "stock_code": "688072.SH",
                        "stock_name": STOCK_NAME,
                        "evidence_type": "financial_report",
                        "publish_date": "2026-08-01",
                        "report_period": "2026-06-30",
                        "title": FUTURE_TITLE,
                        "document_url": "https://example.com/future.pdf",
                        "source_id": "rep-2",
                        "source_label": SOURCE_LABEL,
                        "source_version": "sv_rep_future",
                        "vendor_version": "vv_rep_future",
                        "received_at": None,
                        "ingested_at": datetime(2026, 8, 1, 8, 0, tzinfo=UTC),
                        "run_id": "run-3",
                        "raw_json": "{}",
                    },
                ],
            )
            upsert_stock_official_disclosure_sync_status(
                conn,
                stock_code="688072.SH",
                requested_from_date="2026-01-01",
                covered_through_date="2026-06-30",
                last_attempt_at=datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
                last_success_at=datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
                status="success",
                fetched_count=2,
                upserted_count=2,
                error_message=None,
                run_id="run-4",
                source_version="sv_sync",
            )
            sync = get_stock_official_disclosure_sync_status(conn, stock_code="688072.SH")
            assert sync is not None
            assert sync["last_attempt_at"] == "2026-07-01T10:00:00+00:00"
            assert sync["last_success_at"] == "2026-07-01T10:00:00+00:00"
    finally:
        conn.close()

    payload = list_stock_official_disclosures(
        duckdb_path=str(db_path),
        stock_code="688072.SH",
        as_of_date=date(2026, 7, 26),
        limit_per_type=5,
    )

    assert payload["table_available"]["official_announcement"]["available"] is True
    assert payload["table_available"]["financial_report"]["available"] is True
    assert payload["sync_status"]["official_announcement"]["status"] == "stale"
    assert payload["sync_status"]["official_announcement"]["covered_through_date"] == "2026-06-30"
    assert payload["source_versions"]["official_announcement"] == "sv_ann_a"
    assert payload["source_versions"]["financial_report"] == "sv_rep_a"
    assert payload["excluded_future_rows"] == 1
    assert payload["latest_publish_date"] == "2026-06-15"
    assert payload["announcements"][0]["event_key"] == payload["announcements"][0]["disclosure_key"]
    assert payload["financial_reports"][0]["vendor_version"] == "vv_rep_a"

def test_upsert_stock_official_disclosures_updates_indexed_classification(tmp_path: Path) -> None:
    db_path = tmp_path / "stock-official-reclassification.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        apply_pending_migrations_on_connection(conn)
        row = {
            "disclosure_key": "k_reclassified",
            "stock_code": "688758.SH",
            "stock_name": "\u8d5b\u5206\u79d1\u6280",
            "evidence_type": "official_announcement",
            "publish_date": "2026-04-22",
            "report_period": None,
            "title": "\u82cf\u5dde\u8d5b\u5206\u79d1\u6280\u80a1\u4efd\u6709\u9650\u516c\u53f82025\u5e74\u5e74\u5ea6\u62a5\u544a",
            "document_url": "https://example.com/reclassified-report.pdf",
            "source_id": "rep-reclassified",
            "source_label": SOURCE_LABEL,
            "source_version": "sv_before",
            "vendor_version": "vv_before",
            "received_at": None,
            "ingested_at": datetime(2026, 4, 22, 8, 0, tzinfo=UTC),
            "run_id": "run-before",
            "raw_json": "{}",
        }
        with repository_task_write_scope("backend.app.tasks.stock_official_disclosure_test"):
            upsert_stock_official_disclosures(conn, rows=[row])
            row.update(
                evidence_type="financial_report",
                report_period="2025-12-31",
                source_version="sv_after",
                vendor_version="vv_after",
                run_id="run-after",
            )
            upsert_stock_official_disclosures(conn, rows=[row])
        stored = conn.execute(
            """
            select evidence_type, report_period, source_version, vendor_version, run_id
            from fact_stock_official_disclosure
            where disclosure_key = 'k_reclassified'
            """
        ).fetchone()
    finally:
        conn.close()

    assert stored == (
        "financial_report",
        date(2025, 12, 31),
        "sv_after",
        "vv_after",
        "run-after",
    )
