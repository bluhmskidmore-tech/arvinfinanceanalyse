"""IR-02/03/04 field-identity admission through real synthetic write chains.

No live data, provider, queue worker, or permissions are used. The registered
task bodies, parser, task-write scope, persistence and read-back remain real.
"""
from __future__ import annotations

import base64
import copy
import csv
import importlib
import io
import json
import os
import socket
from decimal import Decimal
from types import SimpleNamespace

import duckdb
import pandas as pd
import pytest
from openpyxl import Workbook

DAY = "2026-09-29"
NEXT = "2026-09-30"
OLD = "2026-09-28"
CODE = "000001.SZ"


@pytest.fixture
def synthetic(tmp_path, monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("Synthetic import contract forbids network access")

    for key in tuple(os.environ):
        if key.startswith("MOSS_"):
            monkeypatch.delenv(key)
    for key, value in {
        "CLOUD_SYNTHETIC": "1", "ENVIRONMENT": "test",
        "GOVERNANCE_BACKEND": "jsonl", "AGENT_ENABLED": "false",
        "DUCKDB_PATH": str(tmp_path / "synthetic.duckdb"),
        "GOVERNANCE_PATH": str(tmp_path / "governance"),
        "POSTGRES_DSN": f"sqlite:///{tmp_path / 'synthetic.sqlite'}",
        "GOVERNANCE_SQL_DSN": f"sqlite:///{tmp_path / 'synthetic.sqlite'}",
        "JOB_STATE_DSN": f"sqlite:///{tmp_path / 'jobs.sqlite'}",
        "SYSTEM_READ_PUBLICATION_ENABLED": "false",
        "SKIP_STARTUP_STORAGE_MIGRATIONS": "1", "SKIP_POSTGRES_MIGRATIONS": "1",
        "SKIP_STORAGE_READINESS_CHECKS": "1",
    }.items():
        monkeypatch.setenv(f"MOSS_{key}", value)
    for name in ("connect", "connect_ex", "sendto"):
        monkeypatch.setattr(socket.socket, name, deny)
    for name in ("create_connection", "getaddrinfo", "gethostbyname", "gethostbyaddr"):
        monkeypatch.setattr(socket, name, deny)
    from backend.app.governance.settings import get_settings
    get_settings.cache_clear()
    yield SimpleNamespace(root=tmp_path, db=tmp_path / "synthetic.duckdb", deny=deny)
    get_settings.cache_clear()


def config_rows():
    return [{"accounting_class": key, "limit_dv01": "100", "warning_dv01": "80",
             "hedge_target_dv01": "60", "limit_source": "synthetic-only",
             "limit_source_version": "sv-synthetic", "limit_rule_version": "rv-synthetic",
             "limit_effective_date": DAY}
            for key in ("AC", "OCI", "TPL", "all")]


def config_file(root, kind, *, field=None, duplicate_value="999", suffix_field=None):
    rows = config_rows()
    if field and field != "limit_dv01":
        for row in rows:
            row[field] = "100"
    path = root / f"input.{kind}"
    if kind == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        columns = list(rows[0])
        writer.writerow(columns + ([suffix_field or field] if field else []))
        for row in rows:
            writer.writerow(list(row.values()) + ([duplicate_value] if field else []))
        path.write_text(output.getvalue(), encoding="utf-8")
    else:
        # The duplicate occurs only in the last JSON/JSONL row: earlier rows
        # must not leak to governance when loading fails late in the file.
        encoded = [json.dumps(row) for row in rows]
        if field:
            encoded[-1] = encoded[-1][:-1] + f", {json.dumps(suffix_field or field)}: {json.dumps(duplicate_value)}}}"
        path.write_text("\n".join(encoded) if kind == "jsonl" else "[" + ",".join(encoded) + "]", encoding="utf-8")
    return path


@pytest.fixture
def dv01(synthetic):
    from dramatiq.brokers.stub import StubBroker
    task = importlib.import_module("backend.app.tasks.bond_dv01_limit_config_import")
    assert isinstance(task.import_bond_dv01_limit_config.broker, StubBroker)
    assert task.import_bond_dv01_limit_config.fn is task._import_bond_dv01_limit_config
    with duckdb.connect(str(synthetic.db)) as conn:
        conn.execute("create table synthetic_marker (value int)")
    task.import_bond_dv01_limit_config.fn(config_path=str(config_file(synthetic.root, "json")), report_date=DAY)
    stream = synthetic.root / "governance" / f"{task.DV01_LIMIT_CONFIG_STREAM}.jsonl"
    assert len(stream.read_text().splitlines()) == 4
    return SimpleNamespace(task=task, root=synthetic.root, stream=stream)


@pytest.mark.parametrize("kind", ["csv", "json", "jsonl"])
@pytest.mark.parametrize("field", ["limit_dv01", "unknown_note"])
@pytest.mark.parametrize("duplicate_value", ["100", "999"], ids=["identical", "conflicting"])
@pytest.mark.parametrize("dry_run", [False, True], ids=["write", "preview"])
def test_dv01_duplicate_fields_leave_governance_unchanged(dv01, kind, field, duplicate_value, dry_run):
    before = dv01.stream.read_bytes()
    result = dv01.task.import_bond_dv01_limit_config.fn(
        config_path=str(config_file(dv01.root, kind, field=field, duplicate_value=duplicate_value)),
        report_date=DAY, dry_run=dry_run,
    )
    after = dv01.stream.read_bytes()
    assert result["status"] == "blocked", f"result={result}; governance_changed={after != before}"
    assert result["records_written"] == 0
    assert any("duplicate" in error.lower() and field in error for error in result["validation_errors"])
    assert result["limit_utilization_preview"]["rows"] == []
    assert after == before


@pytest.mark.parametrize("kind", ["csv", "json", "jsonl"])
def test_dv01_distinct_whitespace_field_keeps_exact_header_compatibility(dv01, kind):
    path = config_file(dv01.root, kind, field="limit_dv01", suffix_field=" limit_dv01 ")
    result = dv01.task.import_bond_dv01_limit_config.fn(config_path=str(path), report_date=DAY)
    assert result["status"] == "imported" and result["records_written"] == 4
    stored = [json.loads(line) for line in dv01.stream.read_text().splitlines()]
    assert len(stored) == 8 and all(row["limit_dv01"] == "100" for row in stored)


def ledger_bytes(kind, *, duplicate_field=None, duplicate_value="999", whitespace=False, mixed_dates=False, blank_headers=False):
    headers = ["日期", "债券代号", "面值", "未知备注"]
    rows = [["synthetic-only"], headers, [DAY, "SYNTHETIC-A", "100", "100"],
            [NEXT if mixed_dates else DAY, "SYNTHETIC-B", "100", "100"]]
    if duplicate_field:
        headers.append(f" {duplicate_field}\t" if whitespace else duplicate_field)
        for row in rows[2:]:
            row.append(duplicate_value)
    if blank_headers:
        headers.extend(["", " \t"])
        for row in rows[2:]:
            row.extend(["ignored-first", "ignored-second"])
    if kind == "csv":
        output = io.StringIO()
        csv.writer(output).writerows(rows)
        return output.getvalue().encode("utf-8")
    workbook = Workbook()
    workbook.active.title = "ZQTZSHOW"
    for row in rows:
        workbook.active.append(row)
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def run_ledger(task, synthetic, content, kind, run_id):
    return task.run_ledger_import.fn(
        file_name=f"synthetic.{kind}", content_base64=base64.b64encode(content).decode("ascii"),
        duckdb_path=str(synthetic.db), governance_dir=str(synthetic.root / "governance"), run_id=run_id,
    )


def ledger_snapshot(path):
    with duckdb.connect(str(path), read_only=True) as conn:
        return {table: conn.execute(f"select * from {table} order by 1, 2").fetchall()
                for table in ("ledger_import_batch", "ledger_raw_row", "position_snapshot")}


@pytest.fixture
def ledger(synthetic):
    from dramatiq.brokers.stub import StubBroker
    task = importlib.import_module("backend.app.tasks.ledger_import")
    assert isinstance(task.run_ledger_import.broker, StubBroker)
    assert task.run_ledger_import.fn is task._run_ledger_import
    seed = run_ledger(task, synthetic, ledger_bytes("csv"), "csv", "synthetic-seed")
    assert seed["data"]["status"] == "success", seed
    return SimpleNamespace(task=task, synthetic=synthetic)


@pytest.mark.parametrize("kind", ["csv", "xlsx"])
@pytest.mark.parametrize("field", ["面值", "未知备注"])
@pytest.mark.parametrize("duplicate_value", ["100", "999"], ids=["identical", "conflicting"])
@pytest.mark.parametrize("whitespace", [False, True], ids=["exact", "stripped"])
def test_ledger_duplicate_fields_leave_all_business_tables_unchanged(ledger, kind, field, duplicate_value, whitespace):
    from backend.app.services.ledger_import_run_service import get_ledger_import_run_status
    from backend.app.services.ledger_import_service import parse_ledger_file
    before = ledger_snapshot(ledger.synthetic.db)
    before_bytes = ledger.synthetic.db.read_bytes()
    content = ledger_bytes(kind, duplicate_field=field, duplicate_value=duplicate_value, whitespace=whitespace)
    result = run_ledger(ledger.task, ledger.synthetic, content, kind, "synthetic-rejected")
    after = ledger_snapshot(ledger.synthetic.db)
    assert result["data"]["status"] == "failed", f"result={result}; business_tables_changed={after != before}"
    assert after == before
    assert ledger.synthetic.db.read_bytes() == before_bytes
    status = get_ledger_import_run_status(
        governance_dir=ledger.synthetic.root / "governance", governance_backend="jsonl",
        governance_sql_dsn="", run_id="synthetic-rejected",
    )
    assert status["status"] == "failed" and status["error_category"] == "invalid_file"
    with pytest.raises(ValueError) as error:
        parse_ledger_file(file_name=f"synthetic.{kind}", content=content)
    assert field in str(error.value) and "duplicate" in str(error.value).lower()
    assert "5" in str(error.value) and str(3 if field == "面值" else 4) in str(error.value)


@pytest.mark.parametrize("kind", ["csv", "xlsx"])
@pytest.mark.parametrize("blank_headers", [False, True], ids=["plain", "blank-columns"])
def test_ledger_valid_inputs_persist_raw_and_normalized_values(synthetic, kind, blank_headers):
    task = importlib.import_module("backend.app.tasks.ledger_import")
    result = run_ledger(task, synthetic, ledger_bytes(kind, blank_headers=blank_headers), kind, "synthetic-valid")
    assert result["data"]["status"] == "success" and result["data"]["row_count"] == 2
    with duckdb.connect(str(synthetic.db), read_only=True) as conn:
        rows = conn.execute("select face_amount, as_of_date from position_snapshot order by row_no").fetchall()
        raw = conn.execute("select raw_json from ledger_raw_row order by row_no").fetchall()
    assert [row[0] for row in rows] == [Decimal("100"), Decimal("100")]
    assert all(str(row[1]) == DAY for row in rows)
    assert all(json.loads(row[0])["未知备注"] == "100" for row in raw)
    assert all(set(json.loads(row[0])) == {"日期", "债券代号", "面值", "未知备注"} for row in raw)


@pytest.mark.parametrize("kind", ["csv", "xlsx"])
def test_ledger_existing_mixed_date_rejection_stays_atomic(ledger, kind):
    before = ledger_snapshot(ledger.synthetic.db)
    result = run_ledger(ledger.task, ledger.synthetic, ledger_bytes(kind, mixed_dates=True), kind, "synthetic-mixed")
    assert result["data"]["status"] == "failed"
    assert ledger_snapshot(ledger.synthetic.db) == before


class InertSupplier:
    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []

    def stk_limit(self, **kwargs):
        self.calls.append(kwargs)
        payload = self.payloads[kwargs["trade_date"]]
        if isinstance(payload, Exception):
            raise payload
        return copy.deepcopy(payload)


def stock_frame(day, *, duplicate_field=None, duplicate_value=12):
    columns = ["trade_date", "ts_code", "pre_close", "up_limit", "down_limit", "unknown_note"]
    values = [day.replace("-", ""), CODE, 10, 11, 9, 11]
    if duplicate_field:
        columns.append(duplicate_field)
        values.append(duplicate_value)
    return pd.DataFrame([values], columns=columns)


class RecordsAdapter:
    """Existing generic to_dict contract; columns need not be a pandas Index."""

    def __init__(self, columns_type, *, duplicate=False):
        self.columns = columns_type(["trade_date", "ts_code", "pre_close", "up_limit", "down_limit"]
                                    + (["up_limit"] if duplicate else []))
        self.values = [DAY.replace("-", ""), CODE, 10, 11, 9] + ([12] if duplicate else [])

    def to_dict(self, *, orient):
        assert orient == "records"
        return [dict(zip(self.columns, self.values, strict=True))]


def stock_snapshot(path):
    with duckdb.connect(str(path), read_only=True) as conn:
        return conn.execute("select * from stock_limit_price_daily order by trade_date, stock_code").fetchall()


@pytest.fixture
def stock(synthetic, monkeypatch):
    task = importlib.import_module("backend.app.tasks.stock_limit_price_ingest")
    monkeypatch.setattr(task, "_DefaultTushareStkLimitClient", synthetic.deny)
    with duckdb.connect(str(synthetic.db)) as conn:
        task.ensure_stock_limit_price_daily_schema(conn)
        conn.execute("create table choice_stock_daily_observation (trade_date varchar, stock_code varchar)")
        for day in (OLD, DAY, NEXT):
            conn.execute("insert into choice_stock_daily_observation values (?, ?)", [day, CODE])
            conn.execute("insert into stock_limit_price_daily values (?, ?, 110, 90, 100, 'seed-source', 'seed-vendor', 'seed-rule', 'seed-run')", [day, CODE])
    return SimpleNamespace(task=task, path=synthetic.db)


def run_stock(stock, payloads, *, strict=False):
    supplier = InertSupplier({day.replace("-", ""): payload for day, payload in payloads.items()})
    if strict:
        from backend.app.tasks.stock_limit_price_daily_refresh import refresh_stock_limit_prices_for_trade_date
        return refresh_stock_limit_prices_for_trade_date(
            duckdb_path=stock.path, trade_date=min(payloads), dry_run=False,
            client=supplier, run_id="synthetic-duplicate-fields",
        )
    return stock.task.ingest_stock_limit_prices(
        duckdb_path=stock.path, start_date=min(payloads), end_date=max(payloads),
        client=supplier, retry_attempts=1, retry_sleep_seconds=0,
        run_id="synthetic-duplicate-fields", require_observation_coverage=strict,
    )


@pytest.mark.excluded_surface_acceptance
@pytest.mark.surface_market_data
class TestStockDuplicateColumns:
    @pytest.mark.parametrize("columns_type", [list, tuple], ids=["list-columns", "tuple-columns"])
    def test_generic_adapter_valid_columns_keep_existing_ingestion_contract(self, stock, columns_type):
        result = run_stock(stock, {DAY: RecordsAdapter(columns_type)})
        assert result["status"] == "completed" and result["inserted_row_count"] == 1
        stored = stock_snapshot(stock.path)
        assert stored[1][2:5] == (11, 9, 10)
        assert stored[1][-1] == "synthetic-duplicate-fields"

    @pytest.mark.parametrize("columns_type", [list, tuple], ids=["list-columns", "tuple-columns"])
    def test_generic_adapter_duplicate_columns_reject_before_write(self, stock, columns_type):
        before = stock_snapshot(stock.path)
        before_bytes = stock.path.read_bytes()
        with pytest.raises(RuntimeError, match="(?i)duplicate.*up_limit"):
            run_stock(stock, {DAY: RecordsAdapter(columns_type, duplicate=True)})
        assert stock_snapshot(stock.path) == before
        assert stock.path.read_bytes() == before_bytes

    @pytest.mark.parametrize("field", ["up_limit", "unknown_note"])
    @pytest.mark.parametrize("duplicate_value", [11, 12], ids=["identical", "conflicting"])
    @pytest.mark.parametrize("mode", ["single", "strict", "later-date", "after-fetch-failure"])
    def test_duplicate_columns_abort_before_any_date_is_replaced(self, stock, field, duplicate_value, mode):
        before = stock_snapshot(stock.path)
        before_bytes = stock.path.read_bytes()
        duplicate = stock_frame(NEXT if mode in {"later-date", "after-fetch-failure"} else DAY,
                                duplicate_field=field, duplicate_value=duplicate_value)
        payloads = {DAY: duplicate}
        if mode in {"later-date", "after-fetch-failure"}:
            payloads = {DAY: stock_frame(DAY) if mode == "later-date" else RuntimeError("synthetic fetch failure"), NEXT: duplicate}
        error = None
        try:
            result = run_stock(stock, payloads, strict=mode == "strict")
        except (ValueError, RuntimeError) as exc:
            error = exc
            result = None
        after = stock_snapshot(stock.path)
        assert error is not None, f"result={result}; rows_changed={after != before}"
        assert "duplicate" in str(error).lower() and field in str(error)
        assert after == before
        assert stock.path.read_bytes() == before_bytes

    def test_valid_multidate_frames_keep_unknown_fields_and_whitespace_distinct(self, stock):
        frames = {day: stock_frame(day) for day in (DAY, NEXT)}
        for frame in frames.values():
            frame[" up_limit "] = 999
        result = run_stock(stock, frames)
        assert result["status"] == "completed" and result["inserted_row_count"] == 2
        stored = stock_snapshot(stock.path)
        assert stored[0][0] == OLD and stored[0][2] == 110
        assert all(row[2:5] == (11, 9, 10) for row in stored[1:])
        assert all(row[-1] == "synthetic-duplicate-fields" for row in stored[1:])

    def test_fetch_failure_retains_existing_partial_success_contract(self, stock):
        result = run_stock(stock, {DAY: RuntimeError("synthetic fetch failure"), NEXT: stock_frame(NEXT)})
        assert result["status"] == "partial_completed" and result["failed_dates"] == [DAY]
        stored = stock_snapshot(stock.path)
        assert stored[1][2] == 110 and stored[2][2] == 11
