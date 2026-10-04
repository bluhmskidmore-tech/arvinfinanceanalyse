"""Non-expanding storage regression guards for existing source previews."""

from collections import Counter

import duckdb
import pytest

from backend.app.repositories import source_preview_repo

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_source_preview,
]

FAMILIES = ("zqtz", "tyw", "pnl", "pnl_514", "pnl_516", "pnl_517")
TABLES = (
    "phase1_source_preview_summary",
    "phase1_source_preview_groups",
    "phase1_zqtz_preview_rows",
    "phase1_tyw_preview_rows",
    "phase1_pnl_preview_rows",
    "phase1_nonstd_pnl_preview_rows",
    "phase1_zqtz_rule_traces",
    "phase1_tyw_rule_traces",
    "phase1_pnl_rule_traces",
    "phase1_nonstd_pnl_rule_traces",
)


def _preview_payload(batch_id, version="sv_original", *, repeated_traces=1):
    common = {
        "ingest_batch_id": batch_id,
        "row_locator": 2,
        "report_date": "2026-08-31",
        "manual_review_needed": False,
        "source_version": version,
        "rule_version": "rule_中文'1",
    }
    rows = [
        dict(
            common,
            source_family="zqtz",
            business_type_primary="债券投资",
            business_type_final="现券'投资",
            asset_group="债券类",
            instrument_code="001234",
            instrument_name="测试'债券",
            account_category=None,
            manual_review_needed=True,
        ),
        dict(
            common,
            source_family="tyw",
            business_type_primary="同业业务",
            product_group="存放类",
            institution_category="银行",
            special_nature=None,
            counterparty_name="测试'机构",
            investment_portfolio="组合甲",
        ),
        dict(
            common,
            source_family="pnl",
            instrument_code="000001",
            invest_type_raw="H",
            portfolio_name="组合'乙",
            cost_center=None,
            currency="RMB",
        ),
    ]
    for index, family in enumerate(FAMILIES[3:]):
        rows.append(
            dict(
                common,
                source_family=family,
                journal_type=f"记账'{index}",
                product_type="非标资产",
                asset_code=f"000{index}",
                account_code=None,
                dc_flag_raw="D",
                raw_amount=("12345678901234567890123456789.0123456789", "0", None)[index],
                manual_review_needed=index == 1,
            )
        )
    summaries = [
        {
            "ingest_batch_id": batch_id,
            "batch_created_at": "2026-09-15T09:00:00+08:00",
            "source_family": family,
            "report_date": "2026-08-31",
            "report_start_date": None,
            "report_end_date": "2026-08-31",
            "report_granularity": "day",
            "source_file": f"来源'{family}.xls",
            "total_rows": 1,
            "manual_review_count": int(rows[index]["manual_review_needed"]),
            "source_version": version,
            "rule_version": common["rule_version"],
            "preview_mode": "tabular",
            "group_counts": {"分组'甲": 1},
        }
        for index, family in enumerate(FAMILIES)
    ]
    traces = [
        {
            "source_family": family,
            "ingest_batch_id": batch_id,
            "row_locator": 2,
            "trace_step": 1,
            "field_name": "原始'字段",
            "field_value": None if family == "tyw" else "原值'中文",
            "derived_label": "标签'甲",
            "manual_review_needed": family == "zqtz",
        }
        for family in FAMILIES
    ]
    traces[:1] = [dict(traces[0]) for _ in range(repeated_traces)]
    return summaries, rows, traces


def _record_counts(records):
    return Counter(tuple(sorted(record.items())) for record in records)


def _stored_tables(duckdb_path, batch_id=None):
    result = {}
    with duckdb.connect(str(duckdb_path), read_only=True) as conn:
        for table in TABLES:
            query = f"select * from {table}"
            params = []
            if batch_id is not None:
                query += " where ingest_batch_id = ?"
                params.append(batch_id)
            cursor = conn.execute(query, params)
            columns = [column[0] for column in cursor.description]
            result[table] = _record_counts(dict(zip(columns, row)) for row in cursor.fetchall())
    return result


def _expected_tables(summaries, rows, traces):
    expected = {table: [] for table in TABLES}
    for summary in summaries:
        expected["phase1_source_preview_summary"].append(
            {key: value for key, value in summary.items() if key != "group_counts"}
        )
        for label, count in summary["group_counts"].items():
            expected["phase1_source_preview_groups"].append(
                {
                    "ingest_batch_id": summary["ingest_batch_id"],
                    "source_family": summary["source_family"],
                    "group_label": label,
                    "row_count": count,
                    "source_version": summary["source_version"],
                }
            )
    for records, suffix in ((rows, "preview_rows"), (traces, "rule_traces")):
        for record in records:
            family = record["source_family"]
            table_family = "nonstd_pnl" if family in FAMILIES[3:] else family
            stored_record = dict(record)
            if family in {"zqtz", "tyw"}:
                del stored_record["source_family"]
            expected[f"phase1_{table_family}_{suffix}"].append(stored_record)
    return {table: _record_counts(records) for table, records in expected.items()}


def test_preview_write_preserves_all_fields_and_duplicate_traces_across_batches(tmp_path):
    duckdb_path = tmp_path / "preview.duckdb"
    payload = _preview_payload("batch'当前", repeated_traces=501)

    source_preview_repo._write_preview_tables(str(duckdb_path), *payload)

    assert _stored_tables(duckdb_path) == _expected_tables(*payload)
    with duckdb.connect(str(duckdb_path), read_only=True) as conn:
        assert conn.execute("select count(*) from phase1_zqtz_rule_traces").fetchone() == (501,)
        assert conn.execute(
            "select raw_amount from phase1_nonstd_pnl_preview_rows where source_family = 'pnl_514'"
        ).fetchone() == ("12345678901234567890123456789.0123456789",)


def test_preview_rerun_replaces_only_current_batch(tmp_path):
    duckdb_path = tmp_path / "preview.duckdb"
    historical = _preview_payload("batch-history", "sv_history", repeated_traces=2)
    original = _preview_payload("batch-current", repeated_traces=3)
    source_preview_repo._write_preview_tables(str(duckdb_path), *historical)
    source_preview_repo._write_preview_tables(str(duckdb_path), *original)
    before_history = _stored_tables(duckdb_path, "batch-history")
    replacement = _preview_payload("batch-current", "sv_replacement", repeated_traces=501)
    replacement[0][0]["group_counts"] = {"替换'分组": 1}
    replacement[1][0]["instrument_name"] = "替换'债券"

    source_preview_repo._write_preview_tables(str(duckdb_path), *replacement)

    assert _stored_tables(duckdb_path, "batch-history") == before_history
    assert _stored_tables(duckdb_path, "batch-current") == _expected_tables(*replacement)
    with duckdb.connect(str(duckdb_path), read_only=True) as conn:
        assert conn.execute(
            "select distinct ingest_batch_id from phase1_source_preview_summary order by ingest_batch_id"
        ).fetchall() == [("batch-current",), ("batch-history",)]


def test_preview_later_insert_failure_rolls_back_deletes_and_all_prior_writes(tmp_path):
    duckdb_path = tmp_path / "preview.duckdb"
    source_preview_repo._write_preview_tables(str(duckdb_path), *_preview_payload("batch-history"))
    source_preview_repo._write_preview_tables(str(duckdb_path), *_preview_payload("batch-current"))
    before = _stored_tables(duckdb_path)
    replacement = _preview_payload("batch-current", "sv_failed", repeated_traces=501)
    # Invalid data follows 500 valid records in the same trace table. Its failure
    # must restore both the overwritten batch and writes to earlier tables.
    replacement[2][500]["trace_step"] = "invalid-step"

    with pytest.raises(duckdb.ConversionException, match="invalid-step"):
        source_preview_repo._write_preview_tables(str(duckdb_path), *replacement)

    assert _stored_tables(duckdb_path) == before
