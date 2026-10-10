from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import duckdb

import backend.app.tasks.tushare_stock_disclosure as task_module
from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection
from backend.app.repositories.stock_official_disclosure_repo import get_stock_official_disclosure_sync_status
from backend.app.repositories.task_write_guard import repository_task_write_scope
from backend.app.tasks.tushare_stock_disclosure import (
    ANNOUNCEMENT_TYPE,
    FINANCIAL_REPORT_TYPE,
    SOURCE_LABEL,
    _parse_timestamp,
    classify_disclosure_title,
    sync_stock_official_disclosures,
)

STOCK_NAME = "\u62d3\u8346\u79d1\u6280"
REPORT_TITLE = "\u62d3\u8346\u79d1\u6280\u80a1\u4efd\u6709\u9650\u516c\u53f82025\u5e74\u5e74\u5ea6\u62a5\u544a"
NOTICE_TITLE = "\u5173\u4e8e2025\u5e74\u5e74\u5ea6\u62a5\u544a\u7684\u516c\u544a"
HALF_REPORT_TITLE = "2026\u5e74\u534a\u5e74\u5ea6\u62a5\u544a"


class _FakeFrame:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def to_dict(self, orient: str) -> list[dict[str, object]]:
        if orient != "records":
            raise ValueError(orient)
        return list(self._rows)


class _FakePro:
    def __init__(self, rows_by_code: dict[str, list[dict[str, object]]]) -> None:
        self._rows_by_code = rows_by_code

    def anns_d(self, *, ts_code: str, start_date: str, end_date: str) -> _FakeFrame:
        assert start_date <= end_date
        return _FakeFrame(self._rows_by_code.get(ts_code, []))


class _PagedPro:
    def __init__(self, rows_by_code: dict[str, list[dict[str, object]]]) -> None:
        self._rows_by_code = rows_by_code
        self.calls: list[tuple[str, str, str]] = []

    def anns_d(self, *, ts_code: str, start_date: str, end_date: str) -> _FakeFrame:
        self.calls.append((ts_code, start_date, end_date))
        start = date.fromisoformat(f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}")
        end = date.fromisoformat(f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}")
        rows = [
            row
            for row in self._rows_by_code.get(ts_code, [])
            if start <= date.fromisoformat(str(row["ann_date"])[:4] + "-" + str(row["ann_date"])[4:6] + "-" + str(row["ann_date"])[6:]) <= end
        ]
        return _FakeFrame(rows[:2])


def _seed_sync_status(
    db_path: Path,
    *,
    coverage_start: str,
    covered_through: str,
    source_version: str = "sv_seed",
) -> None:
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        apply_pending_migrations_on_connection(conn)
        with repository_task_write_scope("backend.app.tasks.stock_official_disclosure_test"):
            from backend.app.repositories.stock_official_disclosure_repo import (
                upsert_stock_official_disclosure_sync_status,
            )

            upsert_stock_official_disclosure_sync_status(
                conn,
                stock_code="688072.SH",
                requested_from_date=coverage_start,
                covered_through_date=covered_through,
                last_attempt_at=datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
                last_success_at=datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
                status="success",
                fetched_count=1,
                upserted_count=1,
                error_message=None,
                run_id="run-seed",
                source_version=source_version,
            )
    finally:
        conn.close()


def test_sync_stock_official_disclosures_classifies_reports_conservatively(tmp_path: Path) -> None:
    db_path = tmp_path / "stock-official-task.duckdb"
    pro = _FakePro(
        {
            "688072.SH": [
                {
                    "ann_date": "20260420",
                    "name": STOCK_NAME,
                    "title": REPORT_TITLE,
                    "url": "https://example.com/report.pdf",
                    "ann_id": "rep-1",
                },
                {
                    "ann_date": "20260422",
                    "name": STOCK_NAME,
                    "title": NOTICE_TITLE,
                    "url": "https://example.com/notice.pdf",
                    "ann_id": "ann-1",
                },
                {
                    "ann_date": "20260420",
                    "name": STOCK_NAME,
                    "title": REPORT_TITLE,
                    "url": "https://example.com/report.pdf",
                    "ann_id": "rep-1",
                },
            ]
        }
    )

    payload = sync_stock_official_disclosures(
        duckdb_path=str(db_path),
        stock_codes=["688072.SH"],
        from_date="2026-01-01",
        to_date="2026-07-26",
        tushare_client=pro,
        run_id="run-task-1",
        now=datetime(2026, 7, 26, 12, 0, tzinfo=UTC),
    )

    assert payload["status"] == "completed"
    assert payload["fetched_count"] == 3
    assert payload["upserted_count"] == 2

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select title, evidence_type, report_period, source_label
            from fact_stock_official_disclosure
            order by title
            """
        ).fetchall()
    finally:
        conn.close()

    assert rows == [
        (NOTICE_TITLE, ANNOUNCEMENT_TYPE, None, SOURCE_LABEL),
        (REPORT_TITLE, FINANCIAL_REPORT_TYPE, date(2025, 12, 31), SOURCE_LABEL),
    ]


def test_sync_stock_official_disclosures_fails_closed_and_preserves_prior_coverage(tmp_path: Path) -> None:
    db_path = tmp_path / "stock-official-failure.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        apply_pending_migrations_on_connection(conn)
        with repository_task_write_scope("backend.app.tasks.stock_official_disclosure_test"):
            from backend.app.repositories.stock_official_disclosure_repo import upsert_stock_official_disclosure_sync_status

            upsert_stock_official_disclosure_sync_status(
                conn,
                stock_code="688072.SH",
                requested_from_date="2026-01-01",
                covered_through_date="2026-06-30",
                last_attempt_at=datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
                last_success_at=datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
                status="success",
                fetched_count=1,
                upserted_count=1,
                error_message=None,
                run_id="run-seed",
                source_version="sv_seed",
            )
    finally:
        conn.close()

    pro = _FakePro(
        {
            "688072.SH": [
                {
                    "ann_date": "20260720",
                    "name": STOCK_NAME,
                    "title": HALF_REPORT_TITLE,
                    "ann_id": "bad-1",
                }
            ]
        }
    )

    payload = sync_stock_official_disclosures(
        duckdb_path=str(db_path),
        stock_codes=["688072.SH"],
        from_date="2026-07-01",
        to_date="2026-07-26",
        tushare_client=pro,
        run_id="run-task-2",
        now=datetime(2026, 7, 26, 12, 0, tzinfo=UTC),
    )

    assert payload["status"] == "completed_with_errors"
    assert payload["results"][0]["status"] == "failed"

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        sync = get_stock_official_disclosure_sync_status(conn, stock_code="688072.SH")
    finally:
        conn.close()

    assert sync is not None
    assert sync["status"] == "failed"
    assert sync["coverage_start_date"] == "2026-01-01"
    assert sync["covered_through_date"] == "2026-06-30"
    assert sync["last_success_at"] == "2026-07-01T10:00:00+00:00"
    assert "20260701_20260726" in str(sync["source_version"])
    assert "20260101_20260726" not in str(sync["source_version"])
    assert "missing required title/date/url" in str(sync["error_message"])


def test_classify_disclosure_title_keeps_about_notice_outside_financial_reports() -> None:
    evidence_type, report_period = classify_disclosure_title(
        REPORT_TITLE,
        stock_name=STOCK_NAME,
        stock_code="688072.SH",
    )
    assert evidence_type == FINANCIAL_REPORT_TYPE
    assert report_period == date(2025, 12, 31)

    notice_type, notice_period = classify_disclosure_title(
        NOTICE_TITLE,
        stock_name=STOCK_NAME,
        stock_code="688072.SH",
    )
    assert notice_type == ANNOUNCEMENT_TYPE
    assert notice_period is None

    regional_report_type, regional_report_period = classify_disclosure_title(
        "\u82cf\u5dde\u8d5b\u5206\u79d1\u6280\u80a1\u4efd\u6709\u9650\u516c\u53f82025\u5e74\u5e74\u5ea6\u62a5\u544a",
        stock_name="\u8d5b\u5206\u79d1\u6280",
        stock_code="688758.SH",
    )
    assert regional_report_type == FINANCIAL_REPORT_TYPE
    assert regional_report_period == date(2025, 12, 31)

    legal_opinion_type, legal_opinion_period = classify_disclosure_title(
        "\u5317\u4eac\u67d0\u5f8b\u5e08\u4e8b\u52a1\u6240\u5173\u4e8e\u82cf\u5dde\u8d5b\u5206\u79d1\u6280\u80a1\u4efd\u6709\u9650\u516c\u53f82025\u5e74\u5e74\u5ea6\u62a5\u544a",
        stock_name="\u8d5b\u5206\u79d1\u6280",
        stock_code="688758.SH",
    )
    assert legal_opinion_type == ANNOUNCEMENT_TYPE
    assert legal_opinion_period is None


def test_parse_timestamp_preserves_explicit_timezone_instant() -> None:
    assert _parse_timestamp("2026-04-20T16:00:00+08:00") == datetime(
        2026, 4, 20, 8, 0, tzinfo=UTC
    )
    assert _parse_timestamp("2026-04-20T16:00:00") is None


def test_sync_uses_stable_url_identity_when_title_is_revised(tmp_path: Path) -> None:
    db_path = tmp_path / "stock-official-identity.duckdb"
    pro = _FakePro(
        {
            "688072.SH": [
                {
                    "ann_date": "20260420",
                    "name": STOCK_NAME,
                    "title": "Original announcement title",
                    "url": "https://example.com/notice.pdf",
                },
                {
                    "ann_date": "20260420",
                    "name": STOCK_NAME,
                    "title": "Corrected announcement title",
                    "url": "https://example.com/notice.pdf",
                    "ann_id": "notice-revised-source-id",
                },
                {
                    "ann_date": "20260420",
                    "name": STOCK_NAME,
                    "title": "Separate revised document",
                    "url": "https://example.com/notice-v2.pdf",
                },
            ]
        }
    )

    payload = sync_stock_official_disclosures(
        duckdb_path=str(db_path),
        stock_codes=["688072.SH"],
        from_date="2026-01-01",
        to_date="2026-07-26",
        tushare_client=pro,
        run_id="run-identity",
        now=datetime(2026, 7, 26, 12, 0, tzinfo=UTC),
    )

    assert payload["fetched_count"] == 3
    assert payload["upserted_count"] == 2
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = conn.execute(
            "select title, document_url, source_id "
            "from fact_stock_official_disclosure order by document_url"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 2
    assert rows[0][:2] == ("Separate revised document", "https://example.com/notice-v2.pdf")
    assert rows[0][2].startswith("derived_")
    assert rows[1] == (
        "Corrected announcement title",
        "https://example.com/notice.pdf",
        "notice-revised-source-id",
    )


def test_sync_replaces_legacy_key_for_same_url_atomically(tmp_path: Path) -> None:
    db_path = tmp_path / "stock-official-legacy-key.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        apply_pending_migrations_on_connection(conn)
        with repository_task_write_scope("backend.app.tasks.stock_official_disclosure_test"):
            from backend.app.repositories.stock_official_disclosure_repo import upsert_stock_official_disclosures

            assert upsert_stock_official_disclosures(
                conn,
                rows=[
                    {
                        "disclosure_key": "legacy-v38-key-with-title",
                        "stock_code": "688072.SH",
                        "stock_name": STOCK_NAME,
                        "evidence_type": ANNOUNCEMENT_TYPE,
                        "publish_date": "2026-04-20",
                        "report_period": None,
                        "title": "Original legacy title",
                        "document_url": "https://example.com/legacy-revised.pdf",
                        "source_id": "legacy-source-id",
                        "source_label": SOURCE_LABEL,
                        "source_version": "sv_old",
                        "vendor_version": "vv_old",
                        "received_at": None,
                        "ingested_at": datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
                        "run_id": "run-old",
                        "raw_json": "{}",
                    }
                ],
            ) == 1
    finally:
        conn.close()

    pro = _FakePro(
        {
            "688072.SH": [
                {
                    "ann_date": "20260420",
                    "name": STOCK_NAME,
                    "title": "Corrected legacy title",
                    "url": "https://example.com/legacy-revised.pdf",
                    "ann_id": "new-vendor-source-id",
                }
            ]
        }
    )
    payload = sync_stock_official_disclosures(
        duckdb_path=str(db_path),
        stock_codes=["688072.SH"],
        from_date="2026-01-01",
        to_date="2026-07-26",
        tushare_client=pro,
        run_id="run-new",
        now=datetime(2026, 7, 26, 12, 0, tzinfo=UTC),
    )
    assert payload["status"] == "completed"

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = conn.execute(
            "select disclosure_key, title, document_url "
            "from fact_stock_official_disclosure "
            "where stock_code = '688072.SH'"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 1
    assert rows[0][1:] == ("Corrected legacy title", "https://example.com/legacy-revised.pdf")
    assert rows[0][0] != "legacy-v38-key-with-title"
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        source_id = conn.execute(
            "select source_id from fact_stock_official_disclosure "
            "where stock_code = '688072.SH'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert source_id == "new-vendor-source-id"


def test_sync_preserves_wide_coverage_when_refreshing_subinterval(tmp_path: Path) -> None:
    db_path = tmp_path / "stock-official-coverage-subinterval.duckdb"
    _seed_sync_status(
        db_path,
        coverage_start="2026-01-01",
        covered_through="2026-06-30",
    )
    pro = _FakePro(
        {
            "688072.SH": [
                {
                    "ann_date": "20260315",
                    "name": STOCK_NAME,
                    "title": "Subinterval announcement",
                    "url": "https://example.com/subinterval.pdf",
                }
            ]
        }
    )

    payload = sync_stock_official_disclosures(
        duckdb_path=str(db_path),
        stock_codes=["688072.SH"],
        from_date="2026-03-01",
        to_date="2026-03-31",
        tushare_client=pro,
        run_id="run-subinterval",
        now=datetime(2026, 7, 26, 12, 0, tzinfo=UTC),
    )

    assert payload["status"] == "completed"
    assert "20260101_20260630" in str(payload["results"][0]["source_version"])
    assert "20260301_20260331" in str(payload["results"][0]["vendor_version"])
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        sync = get_stock_official_disclosure_sync_status(conn, stock_code="688072.SH")
        row_source_version = conn.execute(
            "select source_version from fact_stock_official_disclosure "
            "where document_url = 'https://example.com/subinterval.pdf'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert sync is not None
    assert sync["coverage_start_date"] == "2026-01-01"
    assert sync["covered_through_date"] == "2026-06-30"
    assert "20260301_20260331" in str(row_source_version)
    assert "20260101_20260630" not in str(row_source_version)


def test_sync_merges_adjacent_coverage_increment(tmp_path: Path) -> None:
    db_path = tmp_path / "stock-official-coverage-adjacent.duckdb"
    _seed_sync_status(
        db_path,
        coverage_start="2026-01-01",
        covered_through="2026-06-30",
    )
    pro = _FakePro(
        {
            "688072.SH": [
                {
                    "ann_date": "20260705",
                    "name": STOCK_NAME,
                    "title": "Adjacent announcement",
                    "url": "https://example.com/adjacent.pdf",
                }
            ]
        }
    )

    payload = sync_stock_official_disclosures(
        duckdb_path=str(db_path),
        stock_codes=["688072.SH"],
        from_date="2026-07-01",
        to_date="2026-07-15",
        tushare_client=pro,
        run_id="run-adjacent",
        now=datetime(2026, 7, 26, 12, 0, tzinfo=UTC),
    )

    assert payload["status"] == "completed"
    assert "20260101_20260715" in str(payload["results"][0]["source_version"])
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        sync = get_stock_official_disclosure_sync_status(conn, stock_code="688072.SH")
    finally:
        conn.close()
    assert sync is not None
    assert sync["coverage_start_date"] == "2026-01-01"
    assert sync["covered_through_date"] == "2026-07-15"


def test_sync_does_not_bridge_coverage_gap(tmp_path: Path) -> None:
    db_path = tmp_path / "stock-official-coverage-gap.duckdb"
    _seed_sync_status(
        db_path,
        coverage_start="2026-01-01",
        covered_through="2026-06-30",
    )
    pro = _FakePro(
        {
            "688072.SH": [
                {
                    "ann_date": "20260805",
                    "name": STOCK_NAME,
                    "title": "Gap announcement",
                    "url": "https://example.com/gap.pdf",
                }
            ]
        }
    )

    payload = sync_stock_official_disclosures(
        duckdb_path=str(db_path),
        stock_codes=["688072.SH"],
        from_date="2026-08-01",
        to_date="2026-08-10",
        tushare_client=pro,
        run_id="run-gap",
        now=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
    )

    assert payload["status"] == "completed"
    assert "20260801_20260810" in str(payload["results"][0]["source_version"])
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        sync = get_stock_official_disclosure_sync_status(conn, stock_code="688072.SH")
    finally:
        conn.close()
    assert sync is not None
    assert sync["coverage_start_date"] == "2026-08-01"
    assert sync["covered_through_date"] == "2026-08-10"


def test_sync_splits_capped_windows_and_marks_full_coverage(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(task_module, "ANNS_D_PAGE_LIMIT", 2)
    db_path = tmp_path / "stock-official-pagination.duckdb"
    rows = [
        {
            "ann_date": f"2026010{day}",
            "name": STOCK_NAME,
            "title": f"Announcement {day}",
            "url": f"https://example.com/{day}.pdf",
        }
        for day in range(1, 5)
    ]
    pro = _PagedPro({"688072.SH": rows})

    payload = sync_stock_official_disclosures(
        duckdb_path=str(db_path),
        stock_codes=["688072.SH"],
        from_date="2026-01-01",
        to_date="2026-01-04",
        tushare_client=pro,
        run_id="run-pagination",
        now=datetime(2026, 1, 5, 12, 0, tzinfo=UTC),
    )

    assert payload["status"] == "completed"
    assert payload["fetched_count"] == 4
    assert payload["upserted_count"] == 4
    assert pro.calls[0] == ("688072.SH", "20260101", "20260104")
    assert ("688072.SH", "20260101", "20260102") in pro.calls
    assert ("688072.SH", "20260103", "20260104") in pro.calls
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        sync = get_stock_official_disclosure_sync_status(conn, stock_code="688072.SH")
    finally:
        conn.close()
    assert sync is not None
    assert sync["status"] == "success"
    assert sync["covered_through_date"] == "2026-01-04"


def test_sync_fails_closed_when_single_day_is_capped(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(task_module, "ANNS_D_PAGE_LIMIT", 2)
    db_path = tmp_path / "stock-official-pagination-failure.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        apply_pending_migrations_on_connection(conn)
        with repository_task_write_scope("backend.app.tasks.stock_official_disclosure_test"):
            from backend.app.repositories.stock_official_disclosure_repo import upsert_stock_official_disclosure_sync_status

            upsert_stock_official_disclosure_sync_status(
                conn,
                stock_code="688072.SH",
                requested_from_date="2025-01-01",
                covered_through_date="2025-12-31",
                last_attempt_at=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
                last_success_at=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
                status="success",
                fetched_count=1,
                upserted_count=1,
                error_message=None,
                run_id="run-seed",
                source_version="sv_seed",
            )
    finally:
        conn.close()

    pro = _FakePro(
        {
            "688072.SH": [
                {
                    "ann_date": "20260102",
                    "name": STOCK_NAME,
                    "title": "Capped day row 1",
                    "url": "https://example.com/capped-1.pdf",
                },
                {
                    "ann_date": "20260102",
                    "name": STOCK_NAME,
                    "title": "Capped day row 2",
                    "url": "https://example.com/capped-2.pdf",
                },
            ]
        }
    )
    payload = sync_stock_official_disclosures(
        duckdb_path=str(db_path),
        stock_codes=["688072.SH"],
        from_date="2026-01-02",
        to_date="2026-01-02",
        tushare_client=pro,
        run_id="run-pagination-failure",
        now=datetime(2026, 1, 3, 12, 0, tzinfo=UTC),
    )

    assert payload["status"] == "completed_with_errors"
    assert payload["results"][0]["status"] == "failed"
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        sync = get_stock_official_disclosure_sync_status(conn, stock_code="688072.SH")
    finally:
        conn.close()
    assert sync is not None
    assert sync["status"] == "failed"
    assert sync["coverage_start_date"] == "2025-01-01"
    assert sync["covered_through_date"] == "2025-12-31"
    assert sync["last_success_at"] == "2026-01-01T10:00:00+00:00"
    assert "2-row limit" in str(sync["error_message"])
