from __future__ import annotations

import hashlib
import json
from pathlib import Path

import duckdb
import pytest

from backend.app.governance.stock_analysis_calendar_approval_decision import (
    validate_stock_analysis_calendar_approval_decision,
)
from backend.app.governance.stock_analysis_calendar_receipt import (
    validate_stock_analysis_calendar_receipt,
)
from backend.app.governance.stock_analysis_current_rule_version_tuple import (
    validate_stock_analysis_current_rule_version_tuple,
)
from backend.app.governance.stock_analysis_source_availability_receipt import (
    validate_stock_analysis_source_availability_receipt,
)
from tests.helpers import load_module

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]


def _load_module():
    return load_module(
        "scripts.stock_analysis_current_rule_evidence_inputs",
        "scripts/stock_analysis_current_rule_evidence_inputs.py",
    )


def _write_json(path: Path, payload: object) -> Path:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return path


def _calendar_rows() -> list[dict[str, object]]:
    return [
        {
            "exchange": "SSE",
            "cal_date": "20260101",
            "is_open": 0,
            "pretrade_date": "20251231",
        },
        {
            "exchange": "SSE",
            "cal_date": "20260102",
            "is_open": 1,
            "pretrade_date": "20251231",
        },
        {
            "exchange": "SSE",
            "cal_date": "20260103",
            "is_open": 0,
            "pretrade_date": "20260102",
        },
    ]


def _create_input_database(path: Path) -> Path:
    conn = duckdb.connect(str(path))
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date date,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into choice_stock_daily_observation
            values ('2026-01-02', 'sv_choice_obs_v1', 'vv_choice_v1',
                    'rv_choice_v1', 'run-choice-v1')
            """
        )
        conn.execute(
            """
            create table stock_adjustment_factor (
              trade_date date,
              source_version varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into stock_adjustment_factor
            values ('2026-01-02', 'sv_adjustment_v1', 'run-adjustment-v1')
            """
        )
        conn.execute(
            """
            create table fact_choice_macro_daily (
              trade_date date,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_choice_macro_daily
            values ('2026-01-02', 'sv_macro_v1', 'vv_macro_v1',
                    'rv_macro_v1', 'run-macro-v1')
            """
        )
    finally:
        conn.close()
    return path


def _catalog(path: Path) -> Path:
    return _write_json(
        path,
        {
            "catalog_version": "choice-stock-test-v1",
            "vendor_name": "choice",
            "generated_from": "focused-test",
            "fields": [],
        },
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _run(
    module,
    *,
    tmp_path: Path,
    calendar_rows: list[dict[str, object]] | None = None,
    output_name: str = "evidence-inputs",
):
    database = _create_input_database(tmp_path / "moss.duckdb")
    calendar_path = _write_json(
        tmp_path / "calendar.json",
        calendar_rows if calendar_rows is not None else _calendar_rows(),
    )
    catalog_path = _catalog(tmp_path / "choice_catalog.json")
    output_dir = tmp_path / output_name
    return (
        module.run_current_rule_evidence_inputs_cli(
            duckdb_path=database,
            start_date="2026-01-01",
            end_date="2026-01-03",
            calendar_json=calendar_path,
            fetch_tushare_calendar=False,
            choice_catalog=catalog_path,
            output_dir=output_dir,
            owner_approval_id="OWNER-CALENDAR-20260823",
            captured_at="2026-01-03T12:00:00Z",
            approved_at="2026-01-03T12:00:00Z",
            recorded_at="2026-01-03T12:00:01Z",
            approved_by_label="workspace_owner",
            recorded_by_agent="focused-test-agent",
            approval_reference="owner-chat-approval-20260823",
            table_whitelist={
                "choice_stock_daily_observation": "trade_date",
                "stock_adjustment_factor": "trade_date",
                "fact_choice_macro_daily": "trade_date",
            },
        ),
        database,
        output_dir,
    )


def test_generates_four_validated_artifacts_and_preserves_duckdb(
    tmp_path: Path,
) -> None:
    module = _load_module()
    result, database, output_dir = _run(module, tmp_path=tmp_path)

    assert result["status"] == "ready"
    assert result["database_unchanged"] is True
    assert result["duckdb_sha256_before"] == result["duckdb_sha256_after"]
    assert result["duckdb_sha256_after"] == _sha256(database)
    assert set(path.name for path in output_dir.iterdir()) == {
        module.CALENDAR_RECEIPT_FILENAME,
        module.CALENDAR_DECISION_FILENAME,
        module.SOURCE_RECEIPT_FILENAME,
        module.VERSION_TUPLE_FILENAME,
    }

    payloads = {
        name: json.loads(Path(reference["path"]).read_text(encoding="utf-8"))
        for name, reference in result["artifacts"].items()
    }
    calendar = payloads["approved_calendar_receipt"]
    assert calendar["source_id"] == "tushare.trade_cal:SSE"
    assert calendar["semantics"] == "realized_calendar_as_observed"
    assert calendar["authority_status"] == "approved"
    assert calendar["owner_approval_id"] == "OWNER-CALENDAR-20260823"
    assert calendar["certification_allowed"] is True
    assert validate_stock_analysis_calendar_receipt(calendar)[0] is True

    decision = payloads["calendar_approval_decision"]
    assert decision["approval_mode"] == "local_human_attestation"
    assert decision["signature_status"] == "unsigned_local_record"
    assert decision["external_signature_verified"] is False
    assert decision["strict_coverage"] is True
    assert decision["fallback_covered"] is False
    assert validate_stock_analysis_calendar_approval_decision(
        decision,
        approved_calendar_receipt=calendar,
    )[0] is True

    source_receipt = payloads["source_availability_receipt"]
    assert source_receipt["database"]["unchanged"] is True
    assert source_receipt["attestation"]["historical_ingestion_time_inferred"] is False
    assert validate_stock_analysis_source_availability_receipt(source_receipt)[0] is True
    factor_source = next(
        source
        for source in source_receipt["sources"]
        if source["table"] == "stock_adjustment_factor"
    )
    assert factor_source["vendor_version"] == ""
    assert factor_source["rule_version"] == ""

    version_tuple = payloads["current_rule_version_tuple"]
    assert version_tuple["strict_coverage"] is True
    assert version_tuple["fallback_covered"] is False
    assert validate_stock_analysis_current_rule_version_tuple(version_tuple)[0] is True
    for reference in result["artifacts"].values():
        artifact_path = Path(reference["path"])
        assert artifact_path.parent == output_dir.resolve()
        assert reference["file_sha256"] == _sha256(artifact_path)


def test_missing_natural_day_calendar_coverage_fails_before_output(
    tmp_path: Path,
) -> None:
    module = _load_module()
    database = _create_input_database(tmp_path / "moss.duckdb")
    calendar_path = _write_json(tmp_path / "calendar.json", _calendar_rows()[:2])
    catalog_path = _catalog(tmp_path / "choice_catalog.json")
    output_dir = tmp_path / "blocked-output"
    database_sha = _sha256(database)

    with pytest.raises(ValueError, match="calendar_rows missing requested dates"):
        module.run_current_rule_evidence_inputs_cli(
            duckdb_path=database,
            start_date="2026-01-01",
            end_date="2026-01-03",
            calendar_json=calendar_path,
            fetch_tushare_calendar=False,
            choice_catalog=catalog_path,
            output_dir=output_dir,
            owner_approval_id="OWNER-CALENDAR-20260823",
            captured_at="2026-01-03T12:00:00Z",
            table_whitelist={
                "choice_stock_daily_observation": "trade_date",
                "stock_adjustment_factor": "trade_date",
                "fact_choice_macro_daily": "trade_date",
            },
        )

    assert output_dir.exists() is False
    assert _sha256(database) == database_sha


def test_existing_output_directory_is_never_overwritten(tmp_path: Path) -> None:
    module = _load_module()
    database = _create_input_database(tmp_path / "moss.duckdb")
    calendar_path = _write_json(tmp_path / "calendar.json", _calendar_rows())
    catalog_path = _catalog(tmp_path / "choice_catalog.json")
    output_dir = tmp_path / "existing-output"
    output_dir.mkdir()
    sentinel = output_dir / "owner-evidence.txt"
    sentinel.write_text("preserve", encoding="utf-8")

    with pytest.raises(ValueError, match="existing evidence is never overwritten"):
        module.run_current_rule_evidence_inputs_cli(
            duckdb_path=database,
            start_date="2026-01-01",
            end_date="2026-01-03",
            calendar_json=calendar_path,
            fetch_tushare_calendar=False,
            choice_catalog=catalog_path,
            output_dir=output_dir,
            owner_approval_id="OWNER-CALENDAR-20260823",
        )

    assert sentinel.read_text(encoding="utf-8") == "preserve"
    assert list(output_dir.iterdir()) == [sentinel]


def test_outer_duckdb_hash_guard_blocks_before_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    database = _create_input_database(tmp_path / "moss.duckdb")
    calendar_path = _write_json(tmp_path / "calendar.json", _calendar_rows())
    catalog_path = _catalog(tmp_path / "choice_catalog.json")
    output_dir = tmp_path / "hash-blocked-output"
    real_builder = module.build_stock_analysis_source_availability_receipt

    def _capture_then_mutate(**kwargs):
        receipt = real_builder(**kwargs)
        with database.open("ab") as stream:
            stream.write(b"external-change")
        return receipt

    monkeypatch.setattr(
        module,
        "build_stock_analysis_source_availability_receipt",
        _capture_then_mutate,
    )

    with pytest.raises(ValueError, match="DuckDB changed"):
        module.run_current_rule_evidence_inputs_cli(
            duckdb_path=database,
            start_date="2026-01-01",
            end_date="2026-01-03",
            calendar_json=calendar_path,
            fetch_tushare_calendar=False,
            choice_catalog=catalog_path,
            output_dir=output_dir,
            owner_approval_id="OWNER-CALENDAR-20260823",
            captured_at="2026-01-03T12:00:00Z",
            table_whitelist={
                "choice_stock_daily_observation": "trade_date",
                "stock_adjustment_factor": "trade_date",
                "fact_choice_macro_daily": "trade_date",
            },
        )

    assert output_dir.exists() is False


def test_main_redacts_exception_text_that_could_contain_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module()
    secret = "TEST-TUSHARE-TOKEN-MUST-NOT-LEAK"

    def _raise(**_kwargs):
        raise RuntimeError(f"vendor rejected token={secret}")

    monkeypatch.setattr(module, "run_current_rule_evidence_inputs_cli", _raise)
    exit_code = module.main(
        [
            "--duckdb-path",
            str(tmp_path / "unused.duckdb"),
            "--start-date",
            "2026-01-01",
            "--end-date",
            "2026-01-03",
            "--fetch-tushare-calendar",
            "--choice-catalog",
            str(tmp_path / "unused.json"),
            "--output-dir",
            str(tmp_path / "unused-output"),
            "--owner-approval-id",
            "OWNER-CALENDAR-20260823",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == module.EXIT_BLOCKED
    assert secret not in output
    assert json.loads(output)["status"] == "blocked"


def test_live_tushare_fetch_uses_sse_and_compact_request_dates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    calls: list[dict[str, object]] = []

    class _Frame:
        def to_dict(self, *, orient: str):
            assert orient == "records"
            return _calendar_rows()

    class _Client:
        def trade_cal(self, **kwargs):
            calls.append(kwargs)
            return _Frame()

    class _Tushare:
        @staticmethod
        def pro_api(token: str):
            assert token == "configured-secret"
            return _Client()

    monkeypatch.setattr(module, "get_settings", lambda: object())
    monkeypatch.setattr(
        module,
        "resolve_tushare_token_with_settings_fallback",
        lambda _settings: "configured-secret",
    )
    monkeypatch.setattr(module, "import_tushare_pro", lambda: _Tushare())

    rows = module._fetch_tushare_calendar_rows(
        start_date=module.date(2026, 1, 1),
        end_date=module.date(2026, 1, 3),
    )

    assert rows == _calendar_rows()
    assert calls == [
        {
            "exchange": "SSE",
            "start_date": "20260101",
            "end_date": "20260103",
            "fields": "exchange,cal_date,is_open,pretrade_date",
        }
    ]
