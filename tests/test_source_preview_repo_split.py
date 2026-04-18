from __future__ import annotations

from tests.helpers import load_module


def test_source_preview_repo_roundtrip_keeps_public_read_contract(tmp_path):
    preview_mod = load_module(
        "backend.app.repositories.source_preview_repo",
        "backend/app/repositories/source_preview_repo.py",
    )
    duckdb_path = tmp_path / "moss.duckdb"
    summaries = [
        {
            "ingest_batch_id": "batch-1",
            "batch_created_at": "2026-04-17T00:00:00Z",
            "source_family": "tyw",
            "report_date": "2025-12-31",
            "report_start_date": "2025-12-31",
            "report_end_date": "2025-12-31",
            "report_granularity": "day",
            "source_file": "TYWLSHOW-20251231.xls",
            "total_rows": 1,
            "manual_review_count": 0,
            "source_version": "sv_test_a",
            "rule_version": preview_mod.RULE_VERSION,
            "preview_mode": "tabular",
            "group_counts": {"存放类": 1},
        }
    ]
    row_records = [
        {
            "ingest_batch_id": "batch-1",
            "row_locator": 1,
            "report_date": "2025-12-31",
            "business_type_primary": "存放同业",
            "product_group": "存放类",
            "institution_category": "bank",
            "special_nature": "普通",
            "counterparty_name": "Counterparty A",
            "investment_portfolio": "回购自营",
            "manual_review_needed": False,
            "source_version": "sv_test_a",
            "rule_version": preview_mod.RULE_VERSION,
        }
    ]
    trace_records = [
        {
            "source_family": "tyw",
            "ingest_batch_id": "batch-1",
            "row_locator": 1,
            "trace_step": 1,
            "field_name": "产品类型",
            "field_value": "存放同业",
            "derived_label": "存放类",
            "manual_review_needed": False,
        }
    ]

    preview_mod._write_preview_tables(str(duckdb_path), summaries, row_records, trace_records)

    payload = preview_mod.load_source_preview_payload(str(duckdb_path))
    rows_page = preview_mod.load_preview_rows(str(duckdb_path), "tyw", limit=50, offset=0)
    traces_page = preview_mod.load_rule_traces(str(duckdb_path), "tyw", limit=50, offset=0)

    assert [source.source_family for source in payload.sources] == ["tyw"]
    assert payload.sources[0].source_version == "sv_test_a"
    assert rows_page.ingest_batch_id == "batch-1"
    assert rows_page.total_rows == 1
    assert rows_page.rows[0]["counterparty_name"] == "Counterparty A"
    assert traces_page.ingest_batch_id == "batch-1"
    assert traces_page.total_rows == 1
    assert traces_page.rows[0]["derived_label"] == "存放类"
    assert preview_mod.source_preview_payload_version(payload) == "sv_test_a"
    assert preview_mod.source_preview_batch_version(str(duckdb_path), "tyw", None) == "sv_test_a"


def test_source_preview_repo_helper_mappings_stay_stable():
    preview_mod = load_module(
        "backend.app.repositories.source_preview_repo",
        "backend/app/repositories/source_preview_repo.py",
    )

    assert preview_mod._row_table_name("zqtz") == "phase1_zqtz_preview_rows"
    assert preview_mod._row_table_name("pnl_516") == "phase1_nonstd_pnl_preview_rows"
    assert preview_mod._trace_table_name("tyw") == "phase1_tyw_rule_traces"
    assert preview_mod._trace_table_name("pnl_517") == "phase1_nonstd_pnl_rule_traces"
    assert preview_mod._join_source_versions(["", "sv_a", "sv_a", "sv_b"]) == "sv_a__sv_b"
