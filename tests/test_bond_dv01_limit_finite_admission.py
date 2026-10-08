"""Bounded DV01 writer admission through real parser, task, JSONL and reader.

Every amount, database and governance stream here is synthetic and test-owned.
The broker is inert and network calls are denied; no business limits are chosen.
"""
from __future__ import annotations

import csv
import importlib
import json
import os
import socket
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

pytestmark = pytest.mark.integration

DAY = "2026-09-30"
CLASSES = ("AC", "OCI", "TPL", "all")
FIELDS = ("limit_dv01", "warning_dv01", "hedge_target_dv01")


def config_rows(values=("100", "80", "60"), *, version="new"):
    return [
        {
            "accounting_class": name,
            **dict(zip(FIELDS, values, strict=True)),
            "limit_source": f"synthetic-{version}",
            "limit_source_version": f"sv-{version}",
            "limit_rule_version": f"rv-{version}",
            "limit_effective_date": DAY,
        }
        for name in CLASSES
    ]


@pytest.fixture
def task(tmp_path, monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("Live network access is forbidden in synthetic DV01 tests")

    for key in tuple(os.environ):
        if key.startswith("MOSS_"):
            monkeypatch.delenv(key)
    values = {
        "CLOUD_SYNTHETIC": "1", "ENVIRONMENT": "development",
        "GOVERNANCE_BACKEND": "jsonl", "AGENT_ENABLED": "false",
        "LOCAL_ONLY_API": "true", "OBJECT_STORE_MODE": "local",
        "DUCKDB_PATH": str(tmp_path / "synthetic.duckdb"),
        "GOVERNANCE_PATH": str(tmp_path / "governance"),
        "POSTGRES_DSN": f"sqlite:///{tmp_path / 'synthetic.sqlite'}",
        "GOVERNANCE_SQL_DSN": f"sqlite:///{tmp_path / 'synthetic.sqlite'}",
        "JOB_STATE_DSN": f"sqlite:///{tmp_path / 'jobs.sqlite'}",
        "DATA_INPUT_ROOT": str(tmp_path / "raw"),
        "LOCAL_ARCHIVE_PATH": str(tmp_path / "archive"),
        "PRODUCT_CATEGORY_SOURCE_DIR": str(tmp_path / "product-category"),
        "FINANCIAL_PUBLICATION_ROOT": str(tmp_path / "financial"),
        "BALANCE_ANALYSIS_PUBLICATION_ROOT": str(tmp_path / "balance"),
        "SYSTEM_READ_PUBLICATION_ENABLED": "false",
        "SKIP_STARTUP_STORAGE_MIGRATIONS": "1",
        "SKIP_POSTGRES_MIGRATIONS": "1", "SKIP_STORAGE_READINESS_CHECKS": "1",
    }
    for key, value in values.items():
        monkeypatch.setenv(f"MOSS_{key}", value)
    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, deny)
    for name in ("create_connection", "getaddrinfo"):
        monkeypatch.setattr(socket, name, deny)
    from backend.app.governance.settings import get_settings
    from dramatiq.brokers.stub import StubBroker

    get_settings.cache_clear()
    module = importlib.import_module("backend.app.tasks.bond_dv01_limit_config_import")
    assert isinstance(module.import_bond_dv01_limit_config.broker, StubBroker)
    assert module.import_bond_dv01_limit_config.fn is module._import_bond_dv01_limit_config
    yield module
    get_settings.cache_clear()


@pytest.fixture
def chain(task, tmp_path):
    db = tmp_path / "synthetic.duckdb"
    schema = Path(__file__).resolve().parents[1] / "backend/app/schema_registry/duckdb/02_bond_analytics.sql"
    with duckdb.connect(str(db)) as conn:
        # Use the actual table schema; only the baseline query's columns need rows.
        for statement in schema.read_text(encoding="utf-8").split("-- MOSS:STMT"):
            if statement.strip():
                conn.execute(statement)
        conn.executemany(
            "insert into fact_formal_bond_analytics_daily "
            "(report_date, accounting_class, face_value, market_value, modified_duration, dv01) "
            "values (?, ?, 1000, 1000, 3, ?)",
            [(DAY, "AC", 50), (DAY, "OCI", 20), (DAY, "TPL", -10)],
        )
    repo = task.GovernanceRepository(base_dir=tmp_path / "governance", backend_mode="jsonl")
    repo.append_many_atomic([
        (task.DV01_LIMIT_CONFIG_STREAM, {**row, "report_date": DAY, "imported_at": "2026-09-30T00:00:00+00:00"})
        for row in config_rows(("200", "160", "120"), version="old")
    ])
    return SimpleNamespace(task=task, root=tmp_path, db=db, repo=repo,
                           stream=repo.base_dir / f"{task.DV01_LIMIT_CONFIG_STREAM}.jsonl")


def write_config(chain, rows, kind="json"):
    path = chain.root / f"input.{kind}"
    if kind == "csv":
        fields = list(dict.fromkeys(key for row in rows for key in row))
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    elif kind == "jsonl":
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    else:
        path.write_text(json.dumps(rows), encoding="utf-8")
    return path


def reader(chain):
    return chain.task.get_dv01_limit_config_status(date.fromisoformat(DAY))["result"]


def snapshot(chain):
    status = reader(chain)
    return (chain.stream.read_bytes(), chain.repo.read_all(chain.task.DV01_LIMIT_CONFIG_STREAM),
            {key: status[key] for key in ("rows", "acceptance_status", "configured_count", "invalid_count")})


def observe(chain, monkeypatch):
    events = {"preview": 0, "append": 0}
    actual_preview = chain.task._build_limit_utilization_preview
    actual_append = chain.task.GovernanceRepository.append_many_atomic

    def preview(*args, **kwargs):
        events["preview"] += 1
        return actual_preview(*args, **kwargs)

    def append(*args, **kwargs):
        events["append"] += 1
        return actual_append(*args, **kwargs)

    monkeypatch.setattr(chain.task, "_build_limit_utilization_preview", preview)
    monkeypatch.setattr(chain.task.GovernanceRepository, "append_many_atomic", append)
    return events


def run(chain, path, *, dry_run=False):
    return chain.task._import_bond_dv01_limit_config(
        config_path=str(path), governance_dir=str(chain.repo.base_dir), report_date=DAY, dry_run=dry_run,
    )


def assert_blocked(chain, result, before, events, *, row=None, fields=()):
    assert result["status"] == "blocked"
    assert result["import_readiness_status"] == "not_ready"
    assert result["records_written"] == 0
    assert result["limit_utilization_preview"]["rows"] == []
    assert result["validation_errors"]
    if row is not None:
        errors = [error for error in result["validation_errors"] if error.startswith(f"Row {row}:")]
        assert len(errors) == 1
        for field in fields:
            assert f"{field} must be" in errors[0]
    assert events == {"preview": 0, "append": 0}
    assert snapshot(chain) == before
    assert before[2]["acceptance_status"] == "ready"


@pytest.mark.parametrize("kind", ["csv", "json", "jsonl"])
@pytest.mark.parametrize("dry_run", [True, False], ids=["dry", "write"])
@pytest.mark.parametrize("mode", ["all-thresholds", "hard-only"])
def test_infinity_file_is_blocked_before_preview_or_append(chain, monkeypatch, kind, dry_run, mode):
    rows = config_rows(("Infinity", "Infinity", "Infinity") if mode == "all-thresholds" else ("Infinity", "80", "60"))
    before = snapshot(chain)
    events = observe(chain, monkeypatch)
    result = run(chain, write_config(chain, rows, kind), dry_run=dry_run)
    assert_blocked(chain, result, before, events, row=1, fields=FIELDS if mode == "all-thresholds" else FIELDS[:1])
    assert result["records_loaded"] == 4
    assert result["missing_accounting_classes"] == list(CLASSES)
    assert len([error for error in result["validation_errors"] if error.startswith("Row ")]) == 4


@pytest.mark.parametrize("kind", ["csv", "json", "jsonl"])
@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("value", ["NaN", "sNaN", "+Infinity", " +iNf "])
def test_nonfinite_spelling_has_named_row_error(chain, monkeypatch, kind, field, value):
    rows = config_rows()
    rows[2][field] = value
    before = snapshot(chain)
    events = observe(chain, monkeypatch)
    result = run(chain, write_config(chain, rows, kind))
    assert_blocked(chain, result, before, events, row=3, fields=[field])
    assert result["configured_accounting_classes"] == ["AC", "OCI", "all"]
    assert result["missing_accounting_classes"] == ["TPL"]


@pytest.mark.parametrize("position", ["first", "later", "extra"])
@pytest.mark.parametrize("dry_run", [True, False], ids=["dry", "write"])
def test_mixed_batch_is_wholly_unwritten(chain, monkeypatch, position, dry_run):
    rows = config_rows()
    index = {"first": 0, "later": 3, "extra": 4}[position]
    if position == "extra":
        rows.append(dict(rows[0]))
    rows[index]["limit_dv01"] = "Infinity"
    before = snapshot(chain)
    events = observe(chain, monkeypatch)
    result = run(chain, write_config(chain, rows), dry_run=dry_run)
    assert_blocked(chain, result, before, events, row=index + 1, fields=["limit_dv01"])
    assert result["records_loaded"] == len(rows)
    if position == "extra":
        assert result["missing_accounting_classes"] == []
        assert result["configured_accounting_classes"] == list(CLASSES)
        assert "duplicate accounting_class: AC" in result["validation_errors"][0]


@pytest.mark.parametrize("entry", ["actor", "cli"])
@pytest.mark.parametrize("value", ["Infinity", "NaN", "sNaN"])
def test_registered_entry_points_return_structured_rejection(chain, monkeypatch, capsys, entry, value):
    rows = config_rows()
    rows[0]["limit_dv01"] = value
    path = write_config(chain, rows)
    before = snapshot(chain)
    events = observe(chain, monkeypatch)
    if entry == "actor":
        result = chain.task.import_bond_dv01_limit_config.fn(
            config_path=str(path), governance_dir=str(chain.repo.base_dir), report_date=DAY,
        )
    else:
        monkeypatch.setattr(sys, "argv", ["dv01-import", "--config-path", str(path),
                                        "--governance-dir", str(chain.repo.base_dir), "--report-date", DAY])
        chain.task.main()
        result = json.loads(capsys.readouterr().out)
    assert_blocked(chain, result, before, events, row=1, fields=["limit_dv01"])


@pytest.mark.parametrize("value", [
    pytest.param(float("inf"), id="float-inf"), pytest.param(float("nan"), id="float-nan"),
    pytest.param(Decimal("Infinity"), id="decimal-inf"), pytest.param(Decimal("NaN"), id="decimal-nan"),
    pytest.param(Decimal("sNaN"), id="decimal-snan"), pytest.param(" nan42 ", id="nan-payload"),
    pytest.param("+SNAN2", id="snan-payload"),
])
def test_native_and_decimal_nonfinite_helper_values_are_rejected(task, value):
    assert task._positive_decimal(value) is None


VALID = [
    pytest.param((100, 80, 60), ("100", "80", "60"), id="integer"),
    pytest.param(("100.1250", "80.050", "60.00"), ("100.1250", "80.050", "60.00"), id="decimal"),
    pytest.param((" 100 ", " 80 ", " 60 "), ("100", "80", "60"), id="whitespace"),
    pytest.param(("1e2", "8e1", "6e1"), ("100", "80", "60"), id="scientific"),
    pytest.param(("100", "100", "100"), ("100", "100", "100"), id="equality"),
]


@pytest.mark.parametrize("kind", ["csv", "json", "jsonl"])
@pytest.mark.parametrize(("values", "normalized"), VALID)
def test_finite_controls_keep_dry_run_metadata_append_and_reader(chain, monkeypatch, kind, values, normalized):
    rows = config_rows(values)
    rows.reverse()  # Input order is preserved on append; receipt/reader order remains canonical.
    for row in rows:
        row["limit_source"] = " synthetic-new "
        row["extra_note"] = "ignored synthetic disclosure"
    path = write_config(chain, rows, kind)
    before = snapshot(chain)
    events = observe(chain, monkeypatch)
    dry = run(chain, path, dry_run=True)
    assert dry["status"] == "validated" and dry["import_readiness_status"] == "ready_for_import"
    assert dry["records_written"] == 0 and dry["validation_errors"] == []
    assert len(dry["limit_utilization_preview"]["rows"]) == 4
    assert snapshot(chain) == before
    assert events == {"preview": 1, "append": 0}
    result = run(chain, path)
    assert result["status"] == "imported" and result["import_readiness_status"] == "accepted"
    assert result["records_loaded"] == result["records_written"] == 4
    assert result["configured_accounting_classes"] == list(CLASSES)
    assert result["missing_accounting_classes"] == result["validation_errors"] == []
    assert result["ignored_input_fields"] == ["extra_note"]
    assert result["missing_business_fields_by_class"] == {}
    assert events == {"preview": 2, "append": 1}
    stored = chain.repo.read_all(chain.task.DV01_LIMIT_CONFIG_STREAM)
    assert stored[:4] == before[1] and len(stored) == 8
    assert [row["accounting_class"] for row in stored[4:]] == list(reversed(CLASSES))
    for row in stored[4:]:
        assert tuple(row[field] for field in FIELDS) == normalized
        assert row["limit_source"] == "synthetic-new"
        assert row["limit_source_version"] == "sv-new" and row["limit_rule_version"] == "rv-new"
        assert row["report_date"] == row["limit_effective_date"] == DAY
        assert datetime.fromisoformat(row["imported_at"]).utcoffset().total_seconds() == 0
        assert set(row) == set(chain.task.DV01_LIMIT_CONFIG_REQUIRED_FIELDS) | {"report_date", "imported_at"}
    selected = reader(chain)
    assert selected["acceptance_status"] == "ready" and selected["configured_count"] == 4
    for row in selected["rows"]:
        assert tuple(Decimal(str(row[field]["raw"])) for field in FIELDS) == tuple(map(Decimal, normalized))
        assert row["limit_source_version"] == "sv-new" and row["limit_rule_version"] == "rv-new"


OLD_REJECTIONS = [
    pytest.param({"limit_dv01": "-Infinity"}, "limit_dv01 must be", id="negative-inf"),
    pytest.param({"limit_dv01": "-1"}, "limit_dv01 must be", id="negative"),
    pytest.param({"limit_dv01": 0}, "missing fields: limit_dv01", id="numeric-zero"),
    pytest.param({"limit_dv01": "0"}, "limit_dv01 must be", id="text-zero"),
    pytest.param({"limit_dv01": " "}, "missing fields: limit_dv01", id="blank"),
    pytest.param({"limit_dv01": "garbage"}, "limit_dv01 must be", id="malformed"),
    pytest.param({"limit_dv01": "1,000"}, "limit_dv01 must be", id="grouped-number"),
    pytest.param({"limit_effective_date": "2026-02-30"}, "limit_effective_date must be an ISO date", id="invalid-date"),
    pytest.param({"limit_source_version": ""}, "missing fields: limit_source_version", id="missing-version"),
    pytest.param({"warning_dv01": "101"}, "limit thresholds must satisfy", id="warning-above-hard"),
    pytest.param({"hedge_target_dv01": "81"}, "limit thresholds must satisfy", id="target-above-warning"),
    pytest.param({"accounting_class": "OTHER"}, "accounting_class must be", id="invalid-class"),
]


@pytest.mark.parametrize(("change", "message"), OLD_REJECTIONS)
def test_existing_rejections_keep_whole_file_block(chain, monkeypatch, change, message):
    rows = config_rows()
    rows[0].update(change)
    before = snapshot(chain)
    events = observe(chain, monkeypatch)
    result = run(chain, write_config(chain, rows))
    assert_blocked(chain, result, before, events, row=1)
    assert message in result["validation_errors"][0]


@pytest.mark.parametrize("variant", ["missing-class", "duplicate-class", "missing-field", "json-object"])
def test_existing_completeness_and_container_controls(chain, monkeypatch, variant):
    rows = config_rows()
    if variant == "missing-class":
        rows.pop()
    elif variant == "duplicate-class":
        rows.append(dict(rows[0]))
    elif variant == "missing-field":
        del rows[1]["limit_rule_version"]
    before = snapshot(chain)
    events = observe(chain, monkeypatch)
    path = write_config(chain, rows)
    if variant == "json-object":
        path.write_text(json.dumps(rows[0]), encoding="utf-8")
    result = run(chain, path)
    assert_blocked(chain, result, before, events)
    if variant == "duplicate-class":
        assert result["validation_errors"] == ["Row 5: duplicate accounting_class: AC"]
    elif variant == "missing-field":
        assert result["missing_business_fields_by_class"] == {"OCI": ["limit_rule_version"]}
    elif variant == "json-object":
        assert result["records_loaded"] == 1
        assert result["missing_accounting_classes"] == ["OCI", "TPL", "all"]
    else:
        assert result["validation_errors"] == ["Missing direct DV01 limit config for classes: all"]


@pytest.mark.parametrize(("exposure", "status", "utilization"), [
    ("60", "within_target", "0.60000000"),
    ("60.00000001", "hedge_target_exceeded", "0.60000000"),
    ("80", "warning_breached", "0.80000000"),
    ("100", "hard_limit_breached", "1.00000000"),
    ("-100", "hard_limit_breached", "1.00000000"),
    ("33.33333333", "within_target", "0.33333333"),
])
def test_real_preview_retains_threshold_boundaries_and_quantization(chain, exposure, status, utilization):
    with duckdb.connect(str(chain.db)) as conn:
        conn.execute("update fact_formal_bond_analytics_daily set dv01 = ? where accounting_class = 'AC'", [exposure])
    before = snapshot(chain)
    result = run(chain, write_config(chain, config_rows()), dry_run=True)
    preview = result["limit_utilization_preview"]
    row = preview["rows"][0]
    assert row == {"accounting_class": "AC", "current_total_dv01": format(Decimal(exposure), ".8f"),
                   "limit_dv01": "100", "limit_utilization": utilization, "threshold_status": status}
    assert preview["basis"] == "abs(current_total_dv01) / limit_dv01"
    assert preview["source_table"] == "fact_formal_bond_analytics_daily"
    assert preview["report_date"] == DAY and len(preview["rows"]) == 4
    assert snapshot(chain) == before


def test_actual_atomic_append_rolls_back_after_partial_write(chain, monkeypatch):
    before = snapshot(chain)
    original = chain.task.GovernanceRepository._append_unlocked
    calls = []

    def fail_after_second_write(self, stream, payload):
        result = original(self, stream, payload)
        calls.append(payload["accounting_class"])
        if len(calls) == 2:
            raise OSError("synthetic partial append failure")
        return result

    monkeypatch.setattr(chain.task.GovernanceRepository, "_append_unlocked", fail_after_second_write)
    with pytest.raises(OSError, match="synthetic partial append failure"):
        run(chain, write_config(chain, config_rows()))
    assert calls == ["AC", "OCI"]
    assert snapshot(chain) == before


@pytest.mark.parametrize("value", ["Infinity", "NaN", "sNaN"])
def test_unchanged_reader_rejects_directly_seeded_legacy_nonfinite_hard_limit(chain, value):
    legacy = {**config_rows()[0], "limit_dv01": value}
    chain.repo.append(chain.task.DV01_LIMIT_CONFIG_STREAM, legacy)
    selected = reader(chain)
    assert selected["acceptance_status"] == "blocked"
    assert selected["invalid_accounting_classes"] == ["AC"]
    assert selected["invalid_count"] == 1 and selected["configured_count"] == 3
    assert selected["rows"][0]["status"] == "invalid"
