from __future__ import annotations

from datetime import date

from backend.app.services import stock_official_evidence_service as service


def test_stock_official_evidence_service_preserves_lane_split_and_future_exclusions() -> None:
    calls: list[dict[str, object]] = []

    def repo(**kwargs):
        calls.append(kwargs)
        return {
            "table_available": {
                "official_announcement": {
                    "available": True,
                    "fact_table": "fact_stock_official_disclosure",
                    "sync_status_table": "stock_official_disclosure_sync_status",
                },
                "financial_report": {
                    "available": True,
                    "fact_table": "fact_stock_official_disclosure",
                    "sync_status_table": "stock_official_disclosure_sync_status",
                },
            },
            "sync_status": {
                "status": "ready",
                "coverage_start_date": "2024-10-07",
                "covered_through_date": "2026-04-10",
                "last_success_at": "2026-04-10T09:30:00Z",
                "vendor_version": "vv_tushare_stock_official_20260410",
            },
            "announcements": [
                {
                    "disclosure_key": "ann-1-key",
                    "source_id": "ann-1",
                    "stock_code": "000001.SZ",
                    "stock_name": "Ping An Bank",
                    "title": "Shareholder meeting notice",
                    "publish_date": "2026-04-02",
                    "document_url": "https://example.test/ann-1",
                    "ingested_at": "2026-04-10T09:00:00Z",
                    "source_version": "sv_ann_20260410",
                    "vendor_version": "vv_tushare_stock_official_20260410",
                },
                {
                    "source_id": "ann-future",
                    "stock_code": "000001.SZ",
                    "stock_name": "Ping An Bank",
                    "title": "Future announcement",
                    "publish_date": "2026-04-11",
                    "document_url": "https://example.test/future",
                },
            ],
            "financial_reports": [
                {
                    "source_id": "fin-1",
                    "stock_code": "000001.SZ",
                    "stock_name": "Ping An Bank",
                    "title": "2025 annual report",
                    "publish_date": "2026-03-20",
                    "report_period": "2025-12-31",
                    "document_url": "https://example.test/fin-1",
                    "ingested_at": "2026-04-10T09:05:00Z",
                    "source_version": "sv_fin_20260410",
                    "vendor_version": "vv_tushare_stock_official_20260410",
                }
            ],
            "excluded_future_rows": 2,
            "latest_ingested_at": "2026-04-10T09:30:00Z",
            "source_versions": {
                "official_announcement": ["sv_ann_20260410", "sv_ann_20260410"],
                "financial_report": ["sv_fin_20260410"],
            },
        }

    envelope = service.stock_official_evidence_envelope(
        duckdb_path="unused.duckdb",
        stock_code="000001.SZ",
        as_of_date=date(2026, 4, 10),
        limit_per_type=5,
        list_stock_official_disclosures_fn=repo,
    )

    assert calls == [
        {
            "duckdb_path": "unused.duckdb",
            "stock_code": "000001.SZ",
            "as_of_date": date(2026, 4, 10),
            "limit_per_type": 5,
        }
    ]
    meta = envelope["result_meta"]
    result = envelope["result"]
    assert result["state"] == "ok"
    assert result["as_of_date"] == "2026-04-10"
    assert result["requested_as_of_date"] == "2026-04-10"
    assert result["date_basis"] == "publish_date_lte_requested_as_of_date"
    assert result["excluded_future_rows"] == 3
    assert result["source_statuses"]["official_announcement"]["status"] == "ready"
    assert result["source_statuses"]["official_announcement"]["latest_publish_date"] == "2026-04-02"
    assert result["source_statuses"]["financial_report"]["status"] == "ready"
    assert result["source_statuses"]["financial_report"]["latest_publish_date"] == "2026-03-20"
    assert result["announcements"][0]["source_type"] == "official_announcement"
    assert result["announcements"][0]["event_key"] == "ann-1-key"
    assert result["announcements"][0]["source_label"] == service._LANE_SPECS[0]["label"]
    assert result["financial_reports"][0]["report_period"] == "2025-12-31"
    assert any("Excluded 3 future-dated row(s)" in warning for warning in result["warnings"])
    assert meta["quality_flag"] == "ok"
    assert meta["vendor_status"] == "ok"
    assert meta["fallback_mode"] == "none"
    assert meta["vendor_version"] == "vv_tushare_stock_official_20260410"
    assert meta["source_version"] == "sv_ann_20260410__sv_fin_20260410"
    assert meta["tables_used"] == [
        "fact_stock_official_disclosure",
        "stock_official_disclosure_sync_status",
    ]
    assert meta["evidence_rows"] == 2
    assert meta["formal_use_allowed"] is False


def test_stock_official_evidence_service_marks_valid_empty_as_missing() -> None:
    envelope = service.stock_official_evidence_envelope(
        duckdb_path="unused.duckdb",
        stock_code="600000.SH",
        as_of_date=date(2026, 4, 10),
        limit_per_type=10,
        list_stock_official_disclosures_fn=lambda **_kwargs: {
            "table_available": True,
            "sync_status": {
                "status": "ready",
                "coverage_start_date": "2024-10-07",
                "covered_through_date": "2026-04-10",
                "last_success_at": "2026-04-10T08:00:00Z",
                "source_version": "sv_sync_empty",
            },
            "announcements": [],
            "financial_reports": [],
            "excluded_future_rows": 0,
            "source_versions": {},
        },
    )

    meta = envelope["result_meta"]
    result = envelope["result"]
    assert result["state"] == "missing"
    assert result["as_of_date"] == "2026-04-10"
    assert result["source_statuses"]["official_announcement"]["status"] == "empty"
    assert result["source_statuses"]["financial_report"]["status"] == "empty"
    assert result["warnings"] == []
    assert meta["quality_flag"] == "ok"
    assert meta["vendor_status"] == "ok"
    assert meta["fallback_mode"] == "none"
    assert meta["vendor_version"] == "vv_tushare_stock_official_disclosure"
    assert meta["source_version"] == "sv_sync_empty"
    assert meta["tables_used"] == [
        "fact_stock_official_disclosure",
        "stock_official_disclosure_sync_status",
    ]
    assert meta["evidence_rows"] == 0


def test_stock_official_evidence_service_does_not_call_narrow_empty_window_complete() -> None:
    envelope = service.stock_official_evidence_envelope(
        duckdb_path="unused.duckdb",
        stock_code="600000.SH",
        as_of_date=date(2026, 4, 10),
        limit_per_type=10,
        list_stock_official_disclosures_fn=lambda **_kwargs: {
            "table_available": True,
            "sync_status": {
                "status": "empty",
                "coverage_start_date": "2026-03-11",
                "covered_through_date": "2026-04-10",
                "last_success_at": "2026-04-10T08:00:00Z",
            },
            "announcements": [],
            "financial_reports": [],
            "excluded_future_rows": 0,
            "source_versions": ["sv_ann_empty", "sv_fin_empty"],
        },
    )

    result = envelope["result"]
    meta = envelope["result_meta"]
    assert result["state"] == "unavailable"
    assert result["source_statuses"]["official_announcement"]["status"] == "unavailable"
    assert result["source_statuses"]["official_announcement"]["coverage_start_date"] == "2026-03-11"
    assert any("indexed coverage window insufficient; absence not established" in warning for warning in result["warnings"])
    assert meta["quality_flag"] == "warning"
    assert meta["vendor_status"] == "ok"
    assert meta["vendor_version"] == "vv_tushare_stock_official_disclosure"


def test_stock_official_evidence_service_accepts_full_empty_coverage_and_rejects_historical_gap() -> None:
    def repo(**kwargs):
        return {
            "table_available": True,
            "sync_status": {
                "status": "empty",
                "coverage_start_date": "2024-10-07",
                "covered_through_date": "2026-04-10",
            },
            "announcements": [],
            "financial_reports": [],
            "excluded_future_rows": 0,
            "source_versions": ["sv_empty"],
        }

    current = service.stock_official_evidence_envelope(
        duckdb_path="unused.duckdb",
        stock_code="600000.SH",
        as_of_date=date(2026, 4, 10),
        limit_per_type=10,
        list_stock_official_disclosures_fn=repo,
    )
    assert current["result"]["state"] == "missing"
    assert current["result"]["source_statuses"]["official_announcement"]["status"] == "empty"

    historical = service.stock_official_evidence_envelope(
        duckdb_path="unused.duckdb",
        stock_code="600000.SH",
        as_of_date=date(2025, 1, 1),
        limit_per_type=10,
        list_stock_official_disclosures_fn=repo,
    )
    assert historical["result"]["state"] == "unavailable"
    assert historical["result"]["source_statuses"]["financial_report"]["status"] == "unavailable"


def test_stock_official_evidence_service_keeps_stale_rows_when_sync_failed() -> None:
    envelope = service.stock_official_evidence_envelope(
        duckdb_path="unused.duckdb",
        stock_code="300001.SZ",
        as_of_date=date(2026, 4, 10),
        limit_per_type=3,
        list_stock_official_disclosures_fn=lambda **_kwargs: {
            "table_available": True,
            "sync_status": {
                "status": "error",
                "covered_through_date": "2026-04-05",
                "last_success_at": "2026-04-05T09:00:00Z",
                "error_message": "latest tushare sync failed",
                "vendor_version": "vv_tushare_stock_official_20260405",
            },
            "announcements": [
                {
                    "source_id": "ann-stale",
                    "stock_code": "300001.SZ",
                    "stock_name": "Stale Alpha",
                    "title": "Trading halt notice",
                    "publish_date": "2026-04-04",
                    "source_version": "sv_ann_20260405",
                    "vendor_version": "vv_tushare_stock_official_20260405",
                }
            ],
            "financial_reports": [],
            "excluded_future_rows": 0,
            "source_versions": {"official_announcement": ["sv_ann_20260405"]},
        },
    )

    meta = envelope["result_meta"]
    result = envelope["result"]
    assert result["state"] == "partial"
    assert result["as_of_date"] == "2026-04-05"
    assert result["source_statuses"]["official_announcement"]["status"] == "stale"
    assert result["source_statuses"]["financial_report"]["status"] == "unavailable"
    assert result["announcements"][0]["title"] == "Trading halt notice"
    assert any("latest tushare sync failed" in warning for warning in result["warnings"])
    assert meta["quality_flag"] == "stale"
    assert meta["vendor_status"] == "vendor_stale"
    assert meta["fallback_mode"] == "latest_snapshot"
    assert meta["fallback_date"] == "2026-04-05"
    assert meta["vendor_version"] == "vv_tushare_stock_official_20260405"


def test_stock_official_evidence_service_marks_missing_tables_unavailable() -> None:
    envelope = service.stock_official_evidence_envelope(
        duckdb_path="unused.duckdb",
        stock_code="688001.SH",
        as_of_date=date(2026, 4, 10),
        limit_per_type=2,
        list_stock_official_disclosures_fn=lambda **_kwargs: {
            "table_available": {
                "official_announcement": {
                    "available": False,
                    "tables": [
                        "fact_stock_official_disclosure",
                        "stock_official_disclosure_sync_status",
                    ],
                },
                "financial_report": {
                    "available": False,
                    "tables": [
                        "fact_stock_official_disclosure",
                        "stock_official_disclosure_sync_status",
                    ],
                },
            },
            "sync_status": {},
            "announcements": [],
            "financial_reports": [],
            "excluded_future_rows": 0,
            "source_versions": {},
        },
    )

    meta = envelope["result_meta"]
    result = envelope["result"]
    assert result["state"] == "unavailable"
    assert result["source_statuses"]["official_announcement"]["status"] == "unavailable"
    assert result["source_statuses"]["financial_report"]["status"] == "unavailable"
    assert any("source table is unavailable" in warning for warning in result["warnings"])
    assert meta["quality_flag"] == "warning"
    assert meta["vendor_status"] == "vendor_unavailable"
    assert meta["fallback_mode"] == "none"
    assert meta["tables_used"] == []


def test_stock_official_evidence_service_lazy_repo_failure_stays_unavailable(monkeypatch) -> None:
    def unavailable_loader():
        raise ModuleNotFoundError("duckdb")

    monkeypatch.setattr(service, "_load_stock_official_disclosures", unavailable_loader)
    envelope = service.stock_official_evidence_envelope(
        duckdb_path="unused.duckdb",
        stock_code="688001.SH",
        as_of_date=date(2026, 4, 10),
        limit_per_type=2,
    )

    meta = envelope["result_meta"]
    result = envelope["result"]
    assert result["state"] == "unavailable"
    assert result["source_statuses"]["official_announcement"]["status"] == "unavailable"
    assert result["source_statuses"]["financial_report"]["status"] == "unavailable"
    assert any("ModuleNotFoundError" in warning for warning in result["warnings"])
    assert meta["vendor_status"] == "vendor_unavailable"
    assert meta["tables_used"] == []
