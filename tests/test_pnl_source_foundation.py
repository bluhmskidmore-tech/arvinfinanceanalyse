from __future__ import annotations

from pathlib import Path

from tests.helpers import load_module


def test_pnl_source_rules_detect_all_planned_pnl_source_families():
    module = load_module(
        "backend.app.services.source_rules",
        "backend/app/services/source_rules.py",
    )

    cases = [
        ("FI损益202512.xls", "pnl"),
        ("FI损益202602.xls", "pnl"),
        ("非标514-20250101-1231.xlsx", "pnl_514"),
        ("非标516-20250101-1231.xlsx", "pnl_516"),
        ("非标517-20250101-1231.xlsx", "pnl_517"),
    ]

    for file_name, expected_family in cases:
        assert module.detect_source_family(file_name) == expected_family


def test_pnl_source_rules_extract_report_dates_from_fi_and_nonstd_file_names():
    module = load_module(
        "backend.app.services.source_rules",
        "backend/app/services/source_rules.py",
    )

    cases = [
        ("FI损益202512.xls", "2025-12-31"),
        ("FI损益202602.xls", "2026-02-28"),
        ("非标514-20250101-1231.xlsx", "2025-12-31"),
        ("非标516-20250101-1231.xlsx", "2025-12-31"),
        ("非标517-20260101-0228.xlsx", "2026-02-28"),
    ]

    for file_name, expected_report_date in cases:
        assert module.extract_report_date_from_name(file_name) == expected_report_date


def test_ingest_scan_enriches_manifest_rows_for_all_planned_pnl_source_families(tmp_path):
    ingest_module = load_module(
        "backend.app.services.ingest_service",
        "backend/app/services/ingest_service.py",
    )

    files = [
        ("pnl", "FI损益202512.xls"),
        ("pnl_514", "非标514-20250101-1231.xlsx"),
        ("pnl_516", "非标516-20250101-1231.xlsx"),
        ("pnl_517", "非标517-20250101-1231.xlsx"),
    ]

    data_root = tmp_path / "data_input"
    for directory, file_name in files:
        path = data_root / directory / file_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture")

    service = ingest_module.IngestService(data_root=data_root)
    rows = sorted(
        service.scan(),
        key=lambda row: Path(row["file_path"]).parent.name,
    )

    assert [row["source_family"] for row in rows] == ["pnl", "pnl_514", "pnl_516", "pnl_517"]
    assert [row["report_date"] for row in rows] == [
        "2025-12-31",
        "2025-12-31",
        "2025-12-31",
        "2025-12-31",
    ]
