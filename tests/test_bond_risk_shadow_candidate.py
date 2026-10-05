from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from backend.app.core_finance.fixed_income_version_set import FIXED_INCOME_VERSION_SET
from backend.app.tasks.formal_compute_runtime import _manifest_min_lineage
from tests.helpers import load_module
from tests.test_bond_analytics_materialize_flow import (
    REPORT_DATE as DEFAULT_RUNNER_REPORT_DATE,
)
from tests.test_bond_analytics_materialize_flow import (
    _seed_bond_snapshot_rows,
    seed_yield_curves_for_bond_analytics_tests,
)


def _load_module():
    return load_module(
        "scripts.bond_risk_shadow_candidate",
        "scripts/bond_risk_shadow_candidate.py",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _file_state(path: Path) -> tuple[str, int, tuple[int, int]]:
    stat = path.stat()
    return _sha256(path), stat.st_size, (stat.st_dev, stat.st_ino)


def _seed_source_db(path: Path) -> None:
    conn = duckdb.connect(str(path))
    try:
        conn.execute(
            """
            create table fact_formal_bond_analytics_daily (
                report_date varchar,
                instrument_code varchar,
                portfolio_name varchar,
                cost_center varchar,
                accounting_class varchar,
                maturity_date date,
                metric integer
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_bond_analytics_daily values
            ('2026-05-31', 'B1', 'P1', 'C1', 'AC', '2030-01-01', 10),
            ('2026-05-30', 'B0', 'P0', 'C0', 'AC', '2029-01-01', 9)
            """
        )
        conn.execute(
            """
            create unique index uq_fact_formal_bond_analytics_daily_natural_key
            on fact_formal_bond_analytics_daily (
                coalesce(cast(report_date as varchar), '__moss_null__'),
                coalesce(cast(instrument_code as varchar), '__moss_null__'),
                coalesce(cast(portfolio_name as varchar), '__moss_null__'),
                coalesce(cast(cost_center as varchar), '__moss_null__'),
                coalesce(cast(accounting_class as varchar), '__moss_null__'),
                coalesce(cast(maturity_date as varchar), '__moss_null__')
            )
            """
        )
        conn.execute(
            """
            create table fact_formal_risk_tensor_daily (
                report_date varchar,
                metric integer,
                source_version varchar,
                rule_version varchar,
                cache_version varchar,
                upstream_source_version varchar,
                upstream_rule_version varchar,
                upstream_cache_version varchar,
                liability_source_version varchar,
                liability_rule_version varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_risk_tensor_daily values
            ('2026-05-31', 20, '', 'rv_source_risk', 'cv_source_risk', '', '', '', '', ''),
            ('2026-05-30', 19, '', 'rv_source_risk', 'cv_source_risk', '', '', '', '', '')
            """
        )
        conn.execute(
            """
            create unique index uq_fact_formal_risk_tensor_daily_natural_key
            on fact_formal_risk_tensor_daily (
                coalesce(cast(report_date as varchar), '__moss_null__')
            )
            """
        )
        conn.execute(
            """
            create table dim_static_control (
                id integer not null,
                label varchar default 'stable',
                metric integer default 0,
                constraint pk_dim_static_control primary key(id),
                constraint ck_dim_static_control_metric check (metric >= 0)
            )
            """
        )
        conn.execute(
            "insert into dim_static_control (id, label, metric) values (1, 'stable', 0)"
        )
        conn.execute(
            "create index idx_shadow_dim_static_control on dim_static_control (id)"
        )
        conn.execute(
            "create view vw_shadow_control as select id, label, metric from dim_static_control"
        )
        conn.execute("create schema alt")
        conn.execute("create table alt.shadow_aux as select * from dim_static_control")
        conn.execute("create index idx_alt_shadow_aux on alt.shadow_aux (id)")
        conn.execute("create schema empty_shadow")
        conn.execute("create sequence shadow_seq start 1")
        conn.execute("create type shadow_mood as enum ('calm', 'stress')")
        conn.execute("create macro shadow_add1(x) as x + 1")
    finally:
        conn.close()


def _read_metrics(path: Path, table_name: str) -> list[tuple[str, str, int]]:
    conn = duckdb.connect(str(path), read_only=True)
    try:
        return conn.execute(
            f"""
            select cast(report_date as varchar), instrument_code, metric
            from "{table_name}"
            order by 1, 2
            """
        ).fetchall()
    finally:
        conn.close()


def _patch_settings(module, monkeypatch: pytest.MonkeyPatch, live_path: Path) -> None:
    settings = SimpleNamespace(
        environment="development",
        governance_backend="jsonl",
        source_preview_governance_backend="jsonl",
        duckdb_path=str(live_path),
    )
    monkeypatch.setattr(module, "get_settings", lambda: settings)
    monkeypatch.setenv("MOSS_ENVIRONMENT", "development")
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    monkeypatch.setenv("MOSS_SOURCE_PREVIEW_GOVERNANCE_BACKEND", "jsonl")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(live_path))


def _schema_pass_receipt(module) -> dict[str, object]:
    payload = {
        "receipt_schema": "moss.duckdb-schema-current/v1",
        "status": "passed",
        "target": {
            "database_role": "duckdb-main",
            "read_only": True,
        },
        "registry": {
            "source_digest": {
                "kind": "registry_sources",
                "algorithm": "sha256",
                "sha256": "1" * 64,
            },
            "schema_fingerprint": {
                "kind": "governed_catalog_subset",
                "algorithm": "sha256",
                "expected_sha256": "2" * 64,
                "observed_sha256": "2" * 64,
            },
        },
        "findings": [],
    }
    payload["receipt_sha256"] = module._sha256_json(
        {key: value for key, value in payload.items() if key != "receipt_sha256"}
    )
    return payload


def _runtime_result(
    module,
    *,
    task_name: str,
    run_id: str,
    report_date: str,
    source_version: str,
) -> dict[str, object]:
    if task_name == "bond":
        descriptor = module.BOND_ANALYTICS_MODULE
        job_name = "bond_analytics_materialize"
    else:
        descriptor = module.RISK_TENSOR_MODULE
        job_name = "risk_tensor_materialize"
    payload = {
        "run": {
            "run_id": run_id,
            "job_name": job_name,
            "report_date": report_date,
            "status": "completed",
            "lock": descriptor.lock_key,
            "queued_at": "2026-08-31T00:00:00Z",
            "started_at": "2026-08-31T00:00:01Z",
            "finished_at": "2026-08-31T00:00:02Z",
        },
        "lineage": {
            "cache_key": descriptor.cache_key,
            "cache_version": descriptor.stable_output_version,
            "source_version": source_version,
            "vendor_version": descriptor.vendor_version,
            "rule_version": descriptor.rule_version,
            "basis": descriptor.basis,
            "module_name": descriptor.module_name,
            "result_kind_family": descriptor.result_kind_family,
            "run_id": run_id,
            "report_date": report_date,
            "input_sources": list(descriptor.input_sources),
            "fact_tables": list(descriptor.fact_tables),
        },
        "error": None,
        "result": {"row_count": 1},
    }
    return {
        "status": "completed",
        "cache_key": descriptor.cache_key,
        "cache_version": descriptor.stable_output_version,
        "run_id": run_id,
        "report_date": report_date,
        "source_version": source_version,
        "rule_version": descriptor.rule_version,
        "vendor_version": descriptor.vendor_version,
        "lock": descriptor.lock_key,
        "payload": payload,
        "row_count": 1,
    }


def _append_jsonl(path: Path, record: dict[str, object]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _append_governance_success(
    module,
    governance_dir: Path,
    result: dict[str, object],
    *,
    running_source_version: str,
) -> None:
    payload = result["payload"]
    run = payload["run"]
    lineage = payload["lineage"]
    descriptor = (
        module.BOND_ANALYTICS_MODULE
        if result["cache_key"] == module.BOND_ANALYTICS_MODULE.cache_key
        else module.RISK_TENSOR_MODULE
    )
    assert running_source_version == descriptor.running_source_version
    build_path = governance_dir / "cache_build_run.jsonl"
    manifest_path = governance_dir / "cache_manifest.jsonl"
    queued = {
        "job_name": run["job_name"],
        "status": "queued",
        "cache_key": result["cache_key"],
        "cache_version": result["cache_version"],
        "run_id": result["run_id"],
        "report_date": result["report_date"],
        "source_version": running_source_version,
        "vendor_version": descriptor.vendor_version,
        "lock": descriptor.lock_key,
        "queued_at": run["queued_at"],
    }
    running = {
        **queued,
        "status": "running",
        "started_at": run["started_at"],
    }
    completed = {
        "job_name": run["job_name"],
        "status": "completed",
        "cache_key": result["cache_key"],
        "cache_version": result["cache_version"],
        "run_id": result["run_id"],
        "report_date": result["report_date"],
        "source_version": result["source_version"],
        "vendor_version": result["vendor_version"],
        "rule_version": result["rule_version"],
        "lock": descriptor.lock_key,
        "queued_at": run["queued_at"],
        "started_at": run["started_at"],
        "finished_at": run["finished_at"],
    }
    for record in (queued, running, completed):
        _append_jsonl(build_path, record)
    manifest_record = dict(lineage)
    manifest_record["lineage"] = _manifest_min_lineage(
        descriptor=descriptor,
        run_id=str(result["run_id"]),
        report_date=str(result["report_date"]),
        source_version=str(result["source_version"]),
        vendor_version=str(result["vendor_version"]),
    )
    _append_jsonl(manifest_path, manifest_record)


def _governed_result(
    module,
    *,
    task_name: str,
    run_id: str,
    report_date: str,
    governance_dir: Path,
    source_version: str,
    running_source_version: str,
) -> dict[str, object]:
    result = _runtime_result(
        module,
        task_name=task_name,
        run_id=run_id,
        report_date=report_date,
        source_version=source_version,
    )
    _append_governance_success(
        module,
        governance_dir,
        result,
        running_source_version=running_source_version,
    )
    return result


def _update_risk_target_rows(
    path: Path,
    module,
    *,
    source_version: str,
    upstream_source_version: str,
    upstream_rule_version: str,
    upstream_cache_version: str,
    risk_rule_version: str | None = None,
    risk_cache_version: str | None = None,
    liability_source_version: str = "sv_liability_v1",
    liability_rule_version: str = "rv_liability_v1",
    metric: int = 21,
) -> None:
    conn = duckdb.connect(str(path))
    try:
        conn.execute(
            """
            update fact_formal_risk_tensor_daily
            set metric = ?,
                source_version = ?,
                rule_version = ?,
                cache_version = ?,
                upstream_source_version = ?,
                upstream_rule_version = ?,
                upstream_cache_version = ?,
                liability_source_version = ?,
                liability_rule_version = ?
            where report_date = '2026-05-31'
            """,
            [
                metric,
                source_version,
                module.RISK_RULE_VERSION
                if risk_rule_version is None
                else risk_rule_version,
                module.RISK_CACHE_VERSION
                if risk_cache_version is None
                else risk_cache_version,
                upstream_source_version,
                upstream_rule_version,
                upstream_cache_version,
                liability_source_version,
                liability_rule_version,
            ],
        )
    finally:
        conn.close()


def _run_successful_shadow_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    output_name: str = "shadow-output",
) -> tuple[object, dict[str, object], Path, Path]:
    module = _load_module()
    live_path = tmp_path / "live.duckdb"
    source_path = tmp_path / "source.duckdb"
    _seed_source_db(live_path)
    _seed_source_db(source_path)
    _patch_settings(module, monkeypatch, live_path)

    def fake_bond_runner(**kwargs: object) -> dict[str, object]:
        conn = duckdb.connect(str(kwargs["duckdb_path"]))
        try:
            conn.execute(
                """
                update fact_formal_bond_analytics_daily
                set metric = 11
                where report_date = '2026-05-31' and instrument_code = 'B1'
                """
            )
        finally:
            conn.close()
        return _governed_result(
            module,
            task_name="bond",
            run_id=str(kwargs["run_id"]),
            report_date=str(kwargs["report_date"]),
            governance_dir=Path(str(kwargs["governance_dir"])),
            source_version="sv_bond_curve__sv_bond_holdings",
            running_source_version=module.BOND_ANALYTICS_MODULE.running_source_version,
        )

    def fake_risk_runner(**kwargs: object) -> dict[str, object]:
        _update_risk_target_rows(
            Path(str(kwargs["duckdb_path"])),
            module,
            source_version="sv_risk_tensor__sv_bond_curve__sv_bond_holdings__sv_liability_v1",
            upstream_source_version="sv_bond_curve__sv_bond_holdings",
            upstream_rule_version=module.BOND_RULE_VERSION,
            upstream_cache_version=module.BOND_CACHE_VERSION,
        )
        return _governed_result(
            module,
            task_name="risk",
            run_id=str(kwargs["run_id"]),
            report_date=str(kwargs["report_date"]),
            governance_dir=Path(str(kwargs["governance_dir"])),
            source_version="sv_risk_tensor__sv_bond_curve__sv_bond_holdings__sv_liability_v1",
            running_source_version=module.RISK_TENSOR_MODULE.running_source_version,
        )

    receipt = module.run_bond_risk_shadow_candidate(
        report_date="2026-05-31",
        source_duckdb_path=source_path,
        expected_source_sha256=_sha256(source_path),
        output_dir=tmp_path / output_name,
        bond_runner=fake_bond_runner,
        risk_runner=fake_risk_runner,
        schema_assert=lambda **kwargs: _schema_pass_receipt(module),
        run_id=f"{output_name}-run",
    )
    assert receipt["status"] == "completed"
    assert receipt["receipt_schema"] == module.RECEIPT_SCHEMA
    return module, receipt, live_path, source_path


def test_shadow_candidate_runs_on_isolated_copy_and_preserves_non_target_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    live_path = tmp_path / "live.duckdb"
    source_path = tmp_path / "source.duckdb"
    _seed_source_db(live_path)
    _seed_source_db(source_path)
    _patch_settings(module, monkeypatch, live_path)

    calls: list[dict[str, object]] = []

    def fake_schema_assert(*, duckdb_path: str) -> dict[str, object]:
        calls.append({"schema_assert": duckdb_path})
        return _schema_pass_receipt(module)

    def fake_bond_runner(**kwargs: object) -> dict[str, object]:
        calls.append({"bond": dict(kwargs)})
        conn = duckdb.connect(str(kwargs["duckdb_path"]))
        try:
            conn.execute(
                """
                update fact_formal_bond_analytics_daily
                set metric = 11
                where report_date = '2026-05-31' and instrument_code = 'B1'
                """
            )
        finally:
            conn.close()
        gov = Path(str(kwargs["governance_dir"]))
        result = _runtime_result(
            module,
            task_name="bond",
            run_id=str(kwargs["run_id"]),
            report_date=str(kwargs["report_date"]),
            source_version="sv_bond_curve__sv_bond_holdings",
        )
        _append_governance_success(
            module,
            gov,
            result,
            running_source_version=module.BOND_ANALYTICS_MODULE.running_source_version,
        )
        return result

    def fake_risk_runner(**kwargs: object) -> dict[str, object]:
        calls.append({"risk": dict(kwargs)})
        conn = duckdb.connect(str(kwargs["duckdb_path"]))
        try:
            conn.execute(
                """
                update fact_formal_risk_tensor_daily
                set metric = 21,
                    source_version = 'sv_risk_tensor__sv_bond_curve__sv_bond_holdings__sv_liability_v1',
                    rule_version = ?,
                    cache_version = ?,
                    upstream_source_version = 'sv_bond_curve__sv_bond_holdings',
                    upstream_rule_version = ?,
                    upstream_cache_version = ?,
                    liability_source_version = 'sv_liability_v1',
                    liability_rule_version = 'rv_liability_v1'
                where report_date = '2026-05-31'
                """,
                [
                    module.RISK_RULE_VERSION,
                    module.RISK_CACHE_VERSION,
                    module.BOND_RULE_VERSION,
                    module.BOND_CACHE_VERSION,
                ],
            )
        finally:
            conn.close()
        gov = Path(str(kwargs["governance_dir"]))
        result = _runtime_result(
            module,
            task_name="risk",
            run_id=str(kwargs["run_id"]),
            report_date=str(kwargs["report_date"]),
            source_version="sv_risk_tensor__sv_bond_curve__sv_bond_holdings__sv_liability_v1",
        )
        _append_governance_success(
            module,
            gov,
            result,
            running_source_version=module.RISK_TENSOR_MODULE.running_source_version,
        )
        return result

    output_dir = tmp_path / "shadow-output"
    receipt = module.run_bond_risk_shadow_candidate(
        report_date="2026-05-31",
        source_duckdb_path=source_path,
        expected_source_sha256=_sha256(source_path),
        output_dir=output_dir,
        bond_runner=fake_bond_runner,
        risk_runner=fake_risk_runner,
        schema_assert=fake_schema_assert,
        run_id="shadow-run-1",
    )

    assert receipt["status"] == "completed"
    assert receipt["shadow_only"] is True
    assert receipt["release_gate_eligible"] is False
    assert receipt["financial_golden_validated"] is False
    assert receipt["wp7_eligible"] is False
    assert receipt["evidence_class"] == "structural-shadow"
    assert receipt["receipt_persisted"] is True
    assert receipt["sealed"] is True
    assert receipt["source_unchanged"] is True
    assert receipt["configured_live_unchanged"] is True
    assert receipt["candidate_copy_binding"]["matched"] is True
    assert receipt["governance_validation"]["bond_analytics"]["cache_build_run"][
        "statuses"
    ] == [
        "queued",
        "running",
        "completed",
    ]
    assert (
        receipt["risk_candidate_lineage_validation"]["upstream_source_version"]
        == "sv_bond_curve__sv_bond_holdings"
    )
    assert receipt["risk_candidate_lineage_validation"]["source_version"] == (
        "sv_risk_tensor__sv_bond_curve__sv_bond_holdings__sv_liability_v1"
    )
    assert (
        receipt["risk_candidate_lineage_validation"]["rule_version"]
        == module.RISK_RULE_VERSION
    )
    assert (
        receipt["risk_candidate_lineage_validation"]["cache_version"]
        == module.RISK_CACHE_VERSION
    )
    version_fragment = receipt["fixed_income_version_fragment"]
    assert version_fragment["version_state"] == "configured_current"
    assert version_fragment["engine_rule_version"] == FIXED_INCOME_VERSION_SET.engine_rule_version
    assert version_fragment["bond_analytics"]["rule_version"] == (
        FIXED_INCOME_VERSION_SET.bond_analytics.rule_version
    )
    assert version_fragment["risk_tensor"]["rule_version"] == (
        FIXED_INCOME_VERSION_SET.risk_tensor.rule_version
    )
    assert version_fragment["runtime"]["bond_analytics"]["source_version"] == (
        "sv_bond_curve__sv_bond_holdings"
    )
    assert version_fragment["runtime"]["risk_tensor"]["upstream_lineage"] == {
        "source_version": "sv_bond_curve__sv_bond_holdings",
        "rule_version": module.BOND_RULE_VERSION,
        "cache_version": module.BOND_CACHE_VERSION,
    }
    assert version_fragment["runtime"]["risk_tensor"]["liability_lineage"] == {
        "source_version": "sv_liability_v1",
        "rule_version": "rv_liability_v1",
    }
    serialized_version_fragment = json.dumps(version_fragment, sort_keys=True)
    assert "approved" not in serialized_version_fragment
    assert "release_eligible" not in serialized_version_fragment
    assert calls[0] == {"schema_assert": str(source_path.resolve())}
    assert calls[1]["bond"]["use_existing_curves_only"] is True
    assert calls[1]["bond"]["duckdb_path"] == receipt["candidate_duckdb_path"]
    assert calls[1]["bond"]["governance_dir"] == receipt["candidate_governance_dir"]
    assert calls[2]["risk"]["duckdb_path"] == receipt["candidate_duckdb_path"]
    assert calls[2]["risk"]["governance_dir"] == receipt["candidate_governance_dir"]
    assert receipt["main_catalog_identity"]["matched"] is True
    assert receipt["persistent_catalog_identity"]["matched"] is True
    assert receipt["unexpected_drift"] == []
    assert {
        item["path"].split("\\")[-1].split("/")[-1]
        for item in receipt["governance_artifacts"]
    } == {
        "cache_build_run.jsonl",
        "cache_manifest.jsonl",
    }
    by_table = {item["table_name"]: item for item in receipt["table_identities"]}
    assert by_table["dim_static_control"]["full_table"]["matched"] is True
    assert (
        by_table["fact_formal_bond_analytics_daily"]["non_target_report_date"][
            "matched"
        ]
        is True
    )
    assert (
        by_table["fact_formal_bond_analytics_daily"]["target_report_date"]["matched"]
        is False
    )
    assert (
        by_table["fact_formal_risk_tensor_daily"]["non_target_report_date"]["matched"]
        is True
    )
    assert (
        by_table["fact_formal_risk_tensor_daily"]["target_report_date"]["matched"]
        is False
    )
    assert _read_metrics(source_path, "fact_formal_bond_analytics_daily") == [
        ("2026-05-30", "B0", 9),
        ("2026-05-31", "B1", 10),
    ]
    assert _read_metrics(
        Path(receipt["candidate_duckdb_path"]),
        "fact_formal_bond_analytics_daily",
    ) == [
        ("2026-05-30", "B0", 9),
        ("2026-05-31", "B1", 11),
    ]
    receipt_path = Path(receipt["receipt_path"])
    assert receipt_path.exists()
    assert not (output_dir / module.INCOMPLETE_MARKER).exists()
    assert (output_dir / module.SEALED_MARKER).exists()
    assert receipt["incomplete_marker_removed"] is True
    assert receipt["sealed_marker"]["path"] == str(
        (output_dir / module.SEALED_MARKER).resolve()
    )
    assert module.verify_shadow_candidate_receipt(receipt_path)["status"] == "verified"
    persisted = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert persisted == receipt


def test_shadow_candidate_preflight_failure_does_not_persist_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    live_path = tmp_path / "live.duckdb"
    source_path = tmp_path / "source.duckdb"
    _seed_source_db(live_path)
    _seed_source_db(source_path)
    _patch_settings(module, monkeypatch, live_path)

    receipt = module.run_bond_risk_shadow_candidate(
        report_date="2026-05-31",
        source_duckdb_path=source_path,
        expected_source_sha256=_sha256(source_path),
        output_dir=tmp_path,
        schema_assert=lambda **kwargs: _schema_pass_receipt(module),
        run_id="shadow-run-preflight",
    )

    assert receipt["status"] == "failed"
    assert receipt["error"]["code"] == "source_inside_output_dir"
    assert receipt["receipt_persisted"] is False
    assert not Path(receipt["receipt_path"]).exists()


def test_shadow_candidate_rejects_live_samefile_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    live_path = tmp_path / "live.duckdb"
    source_link = tmp_path / "source-hardlink.duckdb"
    _seed_source_db(live_path)
    try:
        os.link(live_path, source_link)
    except OSError as exc:
        pytest.skip(f"hardlink unsupported: {exc}")
    _patch_settings(module, monkeypatch, live_path)

    output_dir = tmp_path / "samefile-output"
    receipt = module.run_bond_risk_shadow_candidate(
        report_date="2026-05-31",
        source_duckdb_path=source_link,
        expected_source_sha256=_sha256(source_link),
        output_dir=output_dir,
        schema_assert=lambda **kwargs: _schema_pass_receipt(module),
        run_id="shadow-run-samefile",
    )

    assert receipt["status"] == "failed"
    assert receipt["error"]["code"] == "source_matches_live_duckdb_path"
    assert receipt["receipt_persisted"] is False
    assert not output_dir.exists()


def test_shadow_candidate_validates_schema_receipt_strictly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    live_path = tmp_path / "live.duckdb"
    source_path = tmp_path / "source.duckdb"
    _seed_source_db(live_path)
    _seed_source_db(source_path)
    _patch_settings(module, monkeypatch, live_path)

    receipt = module.run_bond_risk_shadow_candidate(
        report_date="2026-05-31",
        source_duckdb_path=source_path,
        expected_source_sha256=_sha256(source_path),
        output_dir=tmp_path / "schema-output",
        schema_assert=lambda **kwargs: {
            **_schema_pass_receipt(module),
            "receipt_sha256": "3" * 64,
        },
        run_id="shadow-run-schema",
    )

    assert receipt["status"] == "failed"
    assert receipt["error"]["code"] == "schema_assertion_receipt_sha_mismatch"
    assert receipt["receipt_persisted"] is False


def test_shadow_candidate_blocks_alt_schema_object_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    live_path = tmp_path / "live.duckdb"
    source_path = tmp_path / "source.duckdb"
    _seed_source_db(live_path)
    _seed_source_db(source_path)
    _patch_settings(module, monkeypatch, live_path)

    def fake_bond_runner(**kwargs: object) -> dict[str, object]:
        conn = duckdb.connect(str(kwargs["duckdb_path"]))
        try:
            conn.execute("create schema alt2")
            conn.execute("create view alt2.vw_shadow_drift as select 1 as drift_value")
        finally:
            conn.close()
        return _governed_result(
            module,
            task_name="bond",
            run_id=str(kwargs["run_id"]),
            report_date=str(kwargs["report_date"]),
            governance_dir=Path(str(kwargs["governance_dir"])),
            source_version="sv_bond_shadow_v1",
            running_source_version=module.BOND_ANALYTICS_MODULE.running_source_version,
        )

    def fake_risk_runner(**kwargs: object) -> dict[str, object]:
        _update_risk_target_rows(
            Path(str(kwargs["duckdb_path"])),
            module,
            source_version="sv_risk_tensor__sv_bond_shadow_v1__sv_liability_v1",
            upstream_source_version="sv_bond_shadow_v1",
            upstream_rule_version=module.BOND_RULE_VERSION,
            upstream_cache_version=module.BOND_CACHE_VERSION,
        )
        return _governed_result(
            module,
            task_name="risk",
            run_id=str(kwargs["run_id"]),
            report_date=str(kwargs["report_date"]),
            governance_dir=Path(str(kwargs["governance_dir"])),
            source_version="sv_risk_tensor__sv_bond_shadow_v1__sv_liability_v1",
            running_source_version=module.RISK_TENSOR_MODULE.running_source_version,
        )

    receipt = module.run_bond_risk_shadow_candidate(
        report_date="2026-05-31",
        source_duckdb_path=source_path,
        expected_source_sha256=_sha256(source_path),
        output_dir=tmp_path / "alt-drift-output",
        bond_runner=fake_bond_runner,
        risk_runner=fake_risk_runner,
        schema_assert=lambda **kwargs: _schema_pass_receipt(module),
        run_id="shadow-run-alt-drift",
    )

    assert receipt["status"] == "failed"
    assert receipt["error"]["code"] == "shadow_candidate_identity_mismatch"
    assert receipt["receipt_persisted"] is True
    assert receipt["persistent_catalog_identity"]["matched"] is False
    assert "persistent_catalog" in receipt["unexpected_drift"]
    assert receipt["main_catalog_identity"]["matched"] is True
    assert not (Path(receipt["output_dir"]) / module.SEALED_MARKER).exists()


def test_shadow_candidate_blocks_main_view_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    live_path = tmp_path / "live.duckdb"
    source_path = tmp_path / "source.duckdb"
    _seed_source_db(live_path)
    _seed_source_db(source_path)
    _patch_settings(module, monkeypatch, live_path)

    def fake_bond_runner(**kwargs: object) -> dict[str, object]:
        conn = duckdb.connect(str(kwargs["duckdb_path"]))
        try:
            conn.execute(
                """
                create or replace view vw_shadow_control
                as select id, label, metric + 1 as metric from dim_static_control
                """
            )
        finally:
            conn.close()
        return _governed_result(
            module,
            task_name="bond",
            run_id=str(kwargs["run_id"]),
            report_date=str(kwargs["report_date"]),
            governance_dir=Path(str(kwargs["governance_dir"])),
            source_version="sv_bond_shadow_v1",
            running_source_version=module.BOND_ANALYTICS_MODULE.running_source_version,
        )

    def fake_risk_runner(**kwargs: object) -> dict[str, object]:
        _update_risk_target_rows(
            Path(str(kwargs["duckdb_path"])),
            module,
            source_version="sv_risk_tensor__sv_bond_shadow_v1__sv_liability_v1",
            upstream_source_version="sv_bond_shadow_v1",
            upstream_rule_version=module.BOND_RULE_VERSION,
            upstream_cache_version=module.BOND_CACHE_VERSION,
        )
        return _governed_result(
            module,
            task_name="risk",
            run_id=str(kwargs["run_id"]),
            report_date=str(kwargs["report_date"]),
            governance_dir=Path(str(kwargs["governance_dir"])),
            source_version="sv_risk_tensor__sv_bond_shadow_v1__sv_liability_v1",
            running_source_version=module.RISK_TENSOR_MODULE.running_source_version,
        )

    receipt = module.run_bond_risk_shadow_candidate(
        report_date="2026-05-31",
        source_duckdb_path=source_path,
        expected_source_sha256=_sha256(source_path),
        output_dir=tmp_path / "main-drift-output",
        bond_runner=fake_bond_runner,
        risk_runner=fake_risk_runner,
        schema_assert=lambda **kwargs: _schema_pass_receipt(module),
        run_id="shadow-run-main-drift",
    )

    assert receipt["status"] == "failed"
    assert receipt["error"]["code"] == "shadow_candidate_identity_mismatch"
    assert receipt["receipt_persisted"] is True
    assert receipt["persistent_catalog_identity"]["matched"] is False
    assert "persistent_catalog" in receipt["unexpected_drift"]


def test_shadow_candidate_blocks_empty_schema_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    live_path = tmp_path / "live.duckdb"
    source_path = tmp_path / "source.duckdb"
    _seed_source_db(live_path)
    _seed_source_db(source_path)
    _patch_settings(module, monkeypatch, live_path)

    def fake_bond_runner(**kwargs: object) -> dict[str, object]:
        conn = duckdb.connect(str(kwargs["duckdb_path"]))
        try:
            conn.execute("create schema empty_shadow_2")
        finally:
            conn.close()
        return _governed_result(
            module,
            task_name="bond",
            run_id=str(kwargs["run_id"]),
            report_date=str(kwargs["report_date"]),
            governance_dir=Path(str(kwargs["governance_dir"])),
            source_version="sv_bond_shadow_v1",
            running_source_version=module.BOND_ANALYTICS_MODULE.running_source_version,
        )

    def fake_risk_runner(**kwargs: object) -> dict[str, object]:
        _update_risk_target_rows(
            Path(str(kwargs["duckdb_path"])),
            module,
            source_version="sv_risk_tensor__sv_bond_shadow_v1__sv_liability_v1",
            upstream_source_version="sv_bond_shadow_v1",
            upstream_rule_version=module.BOND_RULE_VERSION,
            upstream_cache_version=module.BOND_CACHE_VERSION,
        )
        return _governed_result(
            module,
            task_name="risk",
            run_id=str(kwargs["run_id"]),
            report_date=str(kwargs["report_date"]),
            governance_dir=Path(str(kwargs["governance_dir"])),
            source_version="sv_risk_tensor__sv_bond_shadow_v1__sv_liability_v1",
            running_source_version=module.RISK_TENSOR_MODULE.running_source_version,
        )

    receipt = module.run_bond_risk_shadow_candidate(
        report_date="2026-05-31",
        source_duckdb_path=source_path,
        expected_source_sha256=_sha256(source_path),
        output_dir=tmp_path / "empty-schema-drift-output",
        bond_runner=fake_bond_runner,
        risk_runner=fake_risk_runner,
        schema_assert=lambda **kwargs: _schema_pass_receipt(module),
        run_id="shadow-run-empty-schema-drift",
    )

    assert receipt["status"] == "failed"
    assert receipt["error"]["code"] == "shadow_candidate_identity_mismatch"
    assert receipt["persistent_catalog_identity"]["matched"] is False
    assert "persistent_catalog" in receipt["unexpected_drift"]


def test_shadow_candidate_blocks_default_and_constraint_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    live_path = tmp_path / "live.duckdb"
    source_path = tmp_path / "source.duckdb"
    _seed_source_db(live_path)
    _seed_source_db(source_path)
    _patch_settings(module, monkeypatch, live_path)

    def fake_bond_runner(**kwargs: object) -> dict[str, object]:
        conn = duckdb.connect(str(kwargs["duckdb_path"]))
        try:
            conn.execute("drop table alt.shadow_aux")
            conn.execute(
                """
                create table alt.shadow_aux (
                    id integer not null,
                    label varchar default 'rebound',
                    metric integer default 1,
                    constraint ck_alt_shadow_aux_metric check (metric >= -1)
                )
                """
            )
            conn.execute("insert into alt.shadow_aux select * from dim_static_control")
            conn.execute("create index idx_alt_shadow_aux on alt.shadow_aux (id)")
        finally:
            conn.close()
        return _governed_result(
            module,
            task_name="bond",
            run_id=str(kwargs["run_id"]),
            report_date=str(kwargs["report_date"]),
            governance_dir=Path(str(kwargs["governance_dir"])),
            source_version="sv_bond_shadow_v1",
            running_source_version=module.BOND_ANALYTICS_MODULE.running_source_version,
        )

    def fake_risk_runner(**kwargs: object) -> dict[str, object]:
        _update_risk_target_rows(
            Path(str(kwargs["duckdb_path"])),
            module,
            source_version="sv_risk_tensor__sv_bond_shadow_v1__sv_liability_v1",
            upstream_source_version="sv_bond_shadow_v1",
            upstream_rule_version=module.BOND_RULE_VERSION,
            upstream_cache_version=module.BOND_CACHE_VERSION,
        )
        return _governed_result(
            module,
            task_name="risk",
            run_id=str(kwargs["run_id"]),
            report_date=str(kwargs["report_date"]),
            governance_dir=Path(str(kwargs["governance_dir"])),
            source_version="sv_risk_tensor__sv_bond_shadow_v1__sv_liability_v1",
            running_source_version=module.RISK_TENSOR_MODULE.running_source_version,
        )

    receipt = module.run_bond_risk_shadow_candidate(
        report_date="2026-05-31",
        source_duckdb_path=source_path,
        expected_source_sha256=_sha256(source_path),
        output_dir=tmp_path / "default-constraint-drift-output",
        bond_runner=fake_bond_runner,
        risk_runner=fake_risk_runner,
        schema_assert=lambda **kwargs: _schema_pass_receipt(module),
        run_id="shadow-run-default-constraint-drift",
    )

    assert receipt["status"] == "failed"
    assert receipt["error"]["code"] == "shadow_candidate_identity_mismatch"
    assert receipt["persistent_catalog_identity"]["matched"] is False
    assert "persistent_catalog" in receipt["unexpected_drift"]


def test_shadow_candidate_rejects_simplified_governance_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    live_path = tmp_path / "live.duckdb"
    source_path = tmp_path / "source.duckdb"
    _seed_source_db(live_path)
    _seed_source_db(source_path)
    _patch_settings(module, monkeypatch, live_path)

    def fake_bond_runner(**kwargs: object) -> dict[str, object]:
        governance_dir = Path(str(kwargs["governance_dir"]))
        result = _runtime_result(
            module,
            task_name="bond",
            run_id=str(kwargs["run_id"]),
            report_date=str(kwargs["report_date"]),
            source_version="sv_bond_shadow_v1",
        )
        _append_jsonl(
            governance_dir / "cache_build_run.jsonl",
            {"job_name": "bond_analytics_materialize", "status": "completed"},
        )
        _append_jsonl(
            governance_dir / "cache_manifest.jsonl",
            {"run_id": result["run_id"]},
        )
        return result

    def fake_risk_runner(**kwargs: object) -> dict[str, object]:
        _update_risk_target_rows(
            Path(str(kwargs["duckdb_path"])),
            module,
            source_version="sv_risk_tensor__sv_bond_shadow_v1__sv_liability_v1",
            upstream_source_version="sv_bond_shadow_v1",
            upstream_rule_version=module.BOND_RULE_VERSION,
            upstream_cache_version=module.BOND_CACHE_VERSION,
        )
        return _governed_result(
            module,
            task_name="risk",
            run_id=str(kwargs["run_id"]),
            report_date=str(kwargs["report_date"]),
            governance_dir=Path(str(kwargs["governance_dir"])),
            source_version="sv_risk_tensor__sv_bond_shadow_v1__sv_liability_v1",
            running_source_version=module.RISK_TENSOR_MODULE.running_source_version,
        )

    receipt = module.run_bond_risk_shadow_candidate(
        report_date="2026-05-31",
        source_duckdb_path=source_path,
        expected_source_sha256=_sha256(source_path),
        output_dir=tmp_path / "simplified-governance-output",
        bond_runner=fake_bond_runner,
        risk_runner=fake_risk_runner,
        schema_assert=lambda **kwargs: _schema_pass_receipt(module),
        run_id="shadow-run-simplified-governance",
    )

    assert receipt["status"] == "failed"
    assert receipt["error"]["code"] == "governance_build_run_sequence_invalid"


def test_shadow_candidate_rejects_risk_upstream_field_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    live_path = tmp_path / "live.duckdb"
    source_path = tmp_path / "source.duckdb"
    _seed_source_db(live_path)
    _seed_source_db(source_path)
    _patch_settings(module, monkeypatch, live_path)

    def fake_bond_runner(**kwargs: object) -> dict[str, object]:
        return _governed_result(
            module,
            task_name="bond",
            run_id=str(kwargs["run_id"]),
            report_date=str(kwargs["report_date"]),
            governance_dir=Path(str(kwargs["governance_dir"])),
            source_version="sv_bond_curve__sv_bond_holdings",
            running_source_version=module.BOND_ANALYTICS_MODULE.running_source_version,
        )

    def fake_risk_runner(**kwargs: object) -> dict[str, object]:
        _update_risk_target_rows(
            Path(str(kwargs["duckdb_path"])),
            module,
            source_version="sv_risk_tensor__sv_bond_curve__sv_bond_holdings__sv_liability_v1",
            upstream_source_version="sv_bond_curve__sv_bond_holdings",
            upstream_rule_version="rv_wrong",
            upstream_cache_version=module.BOND_CACHE_VERSION,
        )
        return _governed_result(
            module,
            task_name="risk",
            run_id=str(kwargs["run_id"]),
            report_date=str(kwargs["report_date"]),
            governance_dir=Path(str(kwargs["governance_dir"])),
            source_version="sv_risk_tensor__sv_bond_curve__sv_bond_holdings__sv_liability_v1",
            running_source_version=module.RISK_TENSOR_MODULE.running_source_version,
        )

    receipt = module.run_bond_risk_shadow_candidate(
        report_date="2026-05-31",
        source_duckdb_path=source_path,
        expected_source_sha256=_sha256(source_path),
        output_dir=tmp_path / "risk-upstream-mismatch-output",
        bond_runner=fake_bond_runner,
        risk_runner=fake_risk_runner,
        schema_assert=lambda **kwargs: _schema_pass_receipt(module),
        run_id="shadow-run-risk-upstream-mismatch",
    )

    assert receipt["status"] == "failed"
    assert receipt["error"]["code"] == "risk_tensor_upstream_rule_version_mismatch"


def test_shadow_candidate_failure_receipt_redacts_runner_message(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    live_path = tmp_path / "live.duckdb"
    source_path = tmp_path / "source.duckdb"
    _seed_source_db(live_path)
    _seed_source_db(source_path)
    _patch_settings(module, monkeypatch, live_path)

    def failing_bond_runner(**kwargs: object) -> dict[str, object]:
        raise RuntimeError("secret-token-123 raw rows should not leak")

    receipt = module.run_bond_risk_shadow_candidate(
        report_date="2026-05-31",
        source_duckdb_path=source_path,
        expected_source_sha256=_sha256(source_path),
        output_dir=tmp_path / "failure-output",
        bond_runner=failing_bond_runner,
        risk_runner=lambda **kwargs: _runtime_result(
            module,
            task_name="risk",
            run_id=str(kwargs["run_id"]),
            report_date=str(kwargs["report_date"]),
            source_version="sv_risk_tensor__sv_bond_shadow_v1",
        ),
        schema_assert=lambda **kwargs: _schema_pass_receipt(module),
        run_id="shadow-run-failure",
    )

    serialized = json.dumps(receipt, ensure_ascii=False, sort_keys=True)
    assert receipt["status"] == "failed"
    assert receipt["error"]["code"] == "shadow_candidate_unhandled_exception"
    assert receipt["receipt_persisted"] is True
    assert receipt["sealed"] is False
    assert "secret-token-123" not in serialized
    assert "raw rows should not leak" not in serialized


def test_shadow_candidate_validates_risk_lineage_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    live_path = tmp_path / "live.duckdb"
    source_path = tmp_path / "source.duckdb"
    _seed_source_db(live_path)
    _seed_source_db(source_path)
    _patch_settings(module, monkeypatch, live_path)

    def fake_bond_runner(**kwargs: object) -> dict[str, object]:
        return _runtime_result(
            module,
            task_name="bond",
            run_id=str(kwargs["run_id"]),
            report_date=str(kwargs["report_date"]),
            source_version="sv_bond_shadow_v1",
        )

    def fake_risk_runner(**kwargs: object) -> dict[str, object]:
        return _runtime_result(
            module,
            task_name="risk",
            run_id=str(kwargs["run_id"]),
            report_date=str(kwargs["report_date"]),
            source_version="sv_risk_tensor__sv_other",
        )

    receipt = module.run_bond_risk_shadow_candidate(
        report_date="2026-05-31",
        source_duckdb_path=source_path,
        expected_source_sha256=_sha256(source_path),
        output_dir=tmp_path / "lineage-output",
        bond_runner=fake_bond_runner,
        risk_runner=fake_risk_runner,
        schema_assert=lambda **kwargs: _schema_pass_receipt(module),
        run_id="shadow-run-lineage",
    )

    assert receipt["status"] == "failed"
    assert receipt["error"]["code"] == "risk_tensor_upstream_lineage_mismatch"
    assert receipt["receipt_persisted"] is True


def test_shadow_candidate_blocks_candidate_replaced_with_live_before_bond_runner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    live_path = tmp_path / "live.duckdb"
    source_path = tmp_path / "source.duckdb"
    _seed_source_db(live_path)
    _seed_source_db(source_path)
    _patch_settings(module, monkeypatch, live_path)
    source_before = _file_state(source_path)
    live_before = _file_state(live_path)
    bond_calls = 0
    risk_calls = 0
    original_assert = module._assert_execution_state

    def hooked_assert_execution_state(**kwargs: object) -> None:
        candidate_path = Path(str(kwargs["candidate_path"]))
        live_target = Path(str(kwargs["configured_live_path"]))
        if kwargs["stage"] == "before_bond_runner":
            candidate_path.unlink()
            os.link(live_target, candidate_path)
        original_assert(**kwargs)

    monkeypatch.setattr(
        module, "_assert_execution_state", hooked_assert_execution_state
    )

    def fake_bond_runner(**kwargs: object) -> dict[str, object]:
        nonlocal bond_calls
        bond_calls += 1
        return _runtime_result(
            module,
            task_name="bond",
            run_id=str(kwargs["run_id"]),
            report_date=str(kwargs["report_date"]),
            source_version="sv_bond_shadow_v1",
        )

    def fake_risk_runner(**kwargs: object) -> dict[str, object]:
        nonlocal risk_calls
        risk_calls += 1
        return _runtime_result(
            module,
            task_name="risk",
            run_id=str(kwargs["run_id"]),
            report_date=str(kwargs["report_date"]),
            source_version="sv_risk_tensor__sv_bond_shadow_v1",
        )

    receipt = module.run_bond_risk_shadow_candidate(
        report_date="2026-05-31",
        source_duckdb_path=source_path,
        expected_source_sha256=_sha256(source_path),
        output_dir=tmp_path / "candidate-live-swap-output",
        bond_runner=fake_bond_runner,
        risk_runner=fake_risk_runner,
        schema_assert=lambda **kwargs: _schema_pass_receipt(module),
        run_id="shadow-run-candidate-live-swap",
    )

    assert receipt["status"] == "failed"
    assert receipt["error"]["code"] == "candidate_identity_changed_before_bond_runner"
    assert bond_calls == 0
    assert risk_calls == 0
    assert _file_state(source_path) == source_before
    assert _file_state(live_path) == live_before


def test_shadow_candidate_blocks_candidate_replaced_with_source_before_risk_runner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    live_path = tmp_path / "live.duckdb"
    source_path = tmp_path / "source.duckdb"
    _seed_source_db(live_path)
    _seed_source_db(source_path)
    _patch_settings(module, monkeypatch, live_path)
    source_before = _file_state(source_path)
    live_before = _file_state(live_path)
    bond_calls = 0
    risk_calls = 0
    original_assert = module._assert_execution_state

    def hooked_assert_execution_state(**kwargs: object) -> None:
        candidate_path = Path(str(kwargs["candidate_path"]))
        source_target = Path(str(kwargs["source_path"]))
        if kwargs["stage"] == "before_risk_runner":
            candidate_path.unlink()
            os.link(source_target, candidate_path)
        original_assert(**kwargs)

    monkeypatch.setattr(
        module, "_assert_execution_state", hooked_assert_execution_state
    )

    def fake_bond_runner(**kwargs: object) -> dict[str, object]:
        nonlocal bond_calls
        bond_calls += 1
        return _runtime_result(
            module,
            task_name="bond",
            run_id=str(kwargs["run_id"]),
            report_date=str(kwargs["report_date"]),
            source_version="sv_bond_shadow_v1",
        )

    def fake_risk_runner(**kwargs: object) -> dict[str, object]:
        nonlocal risk_calls
        risk_calls += 1
        return _runtime_result(
            module,
            task_name="risk",
            run_id=str(kwargs["run_id"]),
            report_date=str(kwargs["report_date"]),
            source_version="sv_risk_tensor__sv_bond_shadow_v1",
        )

    receipt = module.run_bond_risk_shadow_candidate(
        report_date="2026-05-31",
        source_duckdb_path=source_path,
        expected_source_sha256=_sha256(source_path),
        output_dir=tmp_path / "candidate-source-swap-output",
        bond_runner=fake_bond_runner,
        risk_runner=fake_risk_runner,
        schema_assert=lambda **kwargs: _schema_pass_receipt(module),
        run_id="shadow-run-candidate-source-swap",
    )

    assert receipt["status"] == "failed"
    assert receipt["error"]["code"] == "candidate_identity_changed_before_risk_runner"
    assert bond_calls == 1
    assert risk_calls == 0
    assert _file_state(source_path) == source_before
    assert _file_state(live_path) == live_before


def test_shadow_candidate_blocks_output_dir_swap_before_candidate_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    live_path = tmp_path / "live.duckdb"
    source_path = tmp_path / "source.duckdb"
    _seed_source_db(live_path)
    _seed_source_db(source_path)
    _patch_settings(module, monkeypatch, live_path)
    source_before = _file_state(source_path)
    live_before = _file_state(live_path)
    original_guard = module._assert_output_dir_unchanged
    backup_dir = tmp_path / "shadow-output-original"

    def hooked_output_dir_guard(output_dir: Path, **kwargs: object) -> None:
        if kwargs["stage"] == "before_candidate_create" and output_dir.exists():
            output_dir.rename(backup_dir)
            output_dir.mkdir()
        original_guard(output_dir, **kwargs)

    monkeypatch.setattr(module, "_assert_output_dir_unchanged", hooked_output_dir_guard)
    output_dir = tmp_path / "shadow-output"

    receipt = module.run_bond_risk_shadow_candidate(
        report_date="2026-05-31",
        source_duckdb_path=source_path,
        expected_source_sha256=_sha256(source_path),
        output_dir=output_dir,
        schema_assert=lambda **kwargs: _schema_pass_receipt(module),
        run_id="shadow-run-output-swap",
    )

    assert receipt["status"] == "failed"
    assert (
        receipt["error"]["code"]
        == "output_dir_identity_changed_before_candidate_create"
    )
    assert receipt["receipt_persisted"] is False
    assert not (output_dir / module.CANDIDATE_FILENAME).exists()
    assert not (output_dir / module.RECEIPT_FILENAME).exists()
    assert _file_state(source_path) == source_before
    assert _file_state(live_path) == live_before


def test_spool_sorter_uses_bounded_read_fan_in(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "_CHUNK_SIZE", 1)
    monkeypatch.setattr(module, "_MERGE_FAN_IN", 2)
    sorter = module._SpoolSorter(tmp_path, "fanin")
    for value in [b"c" * 32, b"a" * 32, b"e" * 32, b"b" * 32, b"d" * 32]:
        sorter.add(value)

    active_readers = 0
    max_readers = 0
    original_open = Path.open

    class _TrackedReader:
        def __init__(self, handle):
            self._handle = handle

        def read(self, *args, **kwargs):
            return self._handle.read(*args, **kwargs)

        def close(self):
            nonlocal active_readers
            if not self._handle.closed:
                active_readers -= 1
            return self._handle.close()

        def __getattr__(self, name: str):
            return getattr(self._handle, name)

    def tracked_open(self: Path, mode: str = "r", *args, **kwargs):
        nonlocal active_readers, max_readers
        handle = original_open(self, mode, *args, **kwargs)
        if self.suffix == ".bin" and mode == "rb":
            active_readers += 1
            max_readers = max(max_readers, active_readers)
            return _TrackedReader(handle)
        return handle

    monkeypatch.setattr(Path, "open", tracked_open)

    summary = sorter.finish()

    assert summary.row_count == 5
    assert max_readers <= 2


def test_shadow_candidate_cli_prints_receipt_and_exit_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module()
    live_path = tmp_path / "live.duckdb"
    source_path = tmp_path / "source.duckdb"
    _seed_source_db(live_path)
    _seed_source_db(source_path)
    _patch_settings(module, monkeypatch, live_path)
    monkeypatch.setattr(
        module,
        "assert_duckdb_schema_current",
        lambda **kwargs: _schema_pass_receipt(module),
    )

    def cli_bond_runner(**kwargs: object) -> dict[str, object]:
        return _governed_result(
            module,
            task_name="bond",
            run_id=str(kwargs["run_id"]),
            report_date=str(kwargs["report_date"]),
            governance_dir=Path(str(kwargs["governance_dir"])),
            source_version="sv_bond_shadow_v1",
            running_source_version=module.BOND_ANALYTICS_MODULE.running_source_version,
        )

    def cli_risk_runner(**kwargs: object) -> dict[str, object]:
        _update_risk_target_rows(
            Path(str(kwargs["duckdb_path"])),
            module,
            source_version="sv_risk_tensor__sv_bond_shadow_v1__sv_liability_v1",
            upstream_source_version="sv_bond_shadow_v1",
            upstream_rule_version=module.BOND_RULE_VERSION,
            upstream_cache_version=module.BOND_CACHE_VERSION,
        )
        return _governed_result(
            module,
            task_name="risk",
            run_id=str(kwargs["run_id"]),
            report_date=str(kwargs["report_date"]),
            governance_dir=Path(str(kwargs["governance_dir"])),
            source_version="sv_risk_tensor__sv_bond_shadow_v1__sv_liability_v1",
            running_source_version=module.RISK_TENSOR_MODULE.running_source_version,
        )

    monkeypatch.setattr(
        module,
        "materialize_bond_analytics_facts",
        SimpleNamespace(fn=cli_bond_runner),
    )
    monkeypatch.setattr(
        module,
        "materialize_risk_tensor_facts",
        SimpleNamespace(fn=cli_risk_runner),
    )

    exit_code = module.main(
        [
            "--report-date",
            "2026-05-31",
            "--source-duckdb-path",
            str(source_path),
            "--expected-source-sha256",
            _sha256(source_path),
            "--output-dir",
            str(tmp_path / "cli-output"),
            "--run-id",
            "shadow-run-cli",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "completed"
    assert payload["run_id"] == "shadow-run-cli"
    assert payload["sealed"] is True


def test_shadow_candidate_verify_receipt_detects_missing_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module, receipt, _, _ = _run_successful_shadow_candidate(
        tmp_path,
        monkeypatch,
        output_name="verify-missing-marker",
    )
    marker_path = Path(receipt["sealed_marker"]["path"])
    marker_path.unlink()

    with pytest.raises(module.ShadowCandidateError, match="sealed_marker_missing"):
        module.verify_shadow_candidate_receipt(receipt["receipt_path"])


def test_shadow_candidate_verify_receipt_detects_residual_incomplete_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module, receipt, _, _ = _run_successful_shadow_candidate(
        tmp_path,
        monkeypatch,
        output_name="verify-incomplete-marker",
    )
    output_dir = Path(receipt["output_dir"])
    (output_dir / module.INCOMPLETE_MARKER).write_text("stale", encoding="utf-8")

    with pytest.raises(
        module.ShadowCandidateError, match="incomplete_marker_present_after_seal"
    ):
        module.verify_shadow_candidate_receipt(receipt["receipt_path"])


def test_shadow_candidate_verify_receipt_detects_candidate_tamper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module, receipt, _, _ = _run_successful_shadow_candidate(
        tmp_path,
        monkeypatch,
        output_name="verify-candidate-tamper",
    )
    candidate_path = Path(receipt["candidate_duckdb_path"])
    with candidate_path.open("ab") as handle:
        handle.write(b"tamper")

    with pytest.raises(
        module.ShadowCandidateError, match="candidate_final_scan_mismatch"
    ):
        module.verify_shadow_candidate_receipt(receipt["receipt_path"])


def test_shadow_candidate_verify_receipt_detects_receipt_tamper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module, receipt, _, _ = _run_successful_shadow_candidate(
        tmp_path,
        monkeypatch,
        output_name="verify-receipt-tamper",
    )
    receipt_path = Path(receipt["receipt_path"])
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload["sealed"] = False
    receipt_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    with pytest.raises(module.ShadowCandidateError, match="receipt_sha256_mismatch"):
        module.verify_shadow_candidate_receipt(receipt_path)


def test_shadow_candidate_verify_receipt_rejects_rehashed_version_fragment_tamper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module, receipt, _, _ = _run_successful_shadow_candidate(
        tmp_path,
        monkeypatch,
        output_name="verify-version-fragment-tamper",
    )
    receipt_path = Path(receipt["receipt_path"])
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload["fixed_income_version_fragment"]["engine_rule_version"] = (
        "rv_bond_analytics_engine_forged"
    )
    payload["canonical_receipt_sha256"] = module._receipt_sha256(payload)
    receipt_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    with pytest.raises(
        module.ShadowCandidateError,
        match="fixed_income_version_engine_rule_mismatch",
    ):
        module.verify_shadow_candidate_receipt(receipt_path)


def test_shadow_candidate_verify_receipt_rejects_rehashed_static_descriptor_tamper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module, receipt, _, _ = _run_successful_shadow_candidate(
        tmp_path,
        monkeypatch,
        output_name="verify-static-descriptor-tamper",
    )
    receipt_path = Path(receipt["receipt_path"])
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload["fixed_income_version_fragment"]["bond_analytics"]["input_sources"] = [
        "forged_source"
    ]
    payload["canonical_receipt_sha256"] = module._receipt_sha256(payload)
    receipt_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    with pytest.raises(
        module.ShadowCandidateError,
        match="fixed_income_version_bond_analytics_descriptor_mismatch",
    ):
        module.verify_shadow_candidate_receipt(receipt_path)


def test_shadow_candidate_verify_receipt_requires_versioned_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module, receipt, _, _ = _run_successful_shadow_candidate(
        tmp_path,
        monkeypatch,
        output_name="verify-receipt-schema",
    )
    receipt_path = Path(receipt["receipt_path"])
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload.pop("receipt_schema")
    payload["canonical_receipt_sha256"] = module._receipt_sha256(payload)
    receipt_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    with pytest.raises(
        module.ShadowCandidateError,
        match="receipt_schema_unsupported",
    ):
        module.verify_shadow_candidate_receipt(receipt_path)


def test_shadow_candidate_verify_receipt_detects_marker_tamper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module, receipt, _, _ = _run_successful_shadow_candidate(
        tmp_path,
        monkeypatch,
        output_name="verify-marker-tamper",
    )
    marker_path = Path(receipt["sealed_marker"]["path"])
    payload = json.loads(marker_path.read_text(encoding="utf-8"))
    payload["candidate_sha256"] = "0" * 64
    marker_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    with pytest.raises(
        module.ShadowCandidateError,
        match="sealed_marker_payload_sha_mismatch|sealed_marker_payload_mismatch",
    ):
        module.verify_shadow_candidate_receipt(receipt["receipt_path"])


def test_shadow_candidate_seal_failure_cleans_partial_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    live_path = tmp_path / "live.duckdb"
    source_path = tmp_path / "source.duckdb"
    _seed_source_db(live_path)
    _seed_source_db(source_path)
    _patch_settings(module, monkeypatch, live_path)
    original_create_marker = module._create_marker

    def breaking_create_marker(path: Path, **kwargs: object) -> dict[str, object]:
        marker = original_create_marker(path, **kwargs)
        if path.name == module.SEALED_MARKER:
            raise RuntimeError("post-marker failure")
        return marker

    monkeypatch.setattr(module, "_create_marker", breaking_create_marker)

    def fake_bond_runner(**kwargs: object) -> dict[str, object]:
        return _governed_result(
            module,
            task_name="bond",
            run_id=str(kwargs["run_id"]),
            report_date=str(kwargs["report_date"]),
            governance_dir=Path(str(kwargs["governance_dir"])),
            source_version="sv_bond_shadow_v1",
            running_source_version=module.BOND_ANALYTICS_MODULE.running_source_version,
        )

    def fake_risk_runner(**kwargs: object) -> dict[str, object]:
        _update_risk_target_rows(
            Path(str(kwargs["duckdb_path"])),
            module,
            source_version="sv_risk_tensor__sv_bond_shadow_v1__sv_liability_v1",
            upstream_source_version="sv_bond_shadow_v1",
            upstream_rule_version=module.BOND_RULE_VERSION,
            upstream_cache_version=module.BOND_CACHE_VERSION,
        )
        return _governed_result(
            module,
            task_name="risk",
            run_id=str(kwargs["run_id"]),
            report_date=str(kwargs["report_date"]),
            governance_dir=Path(str(kwargs["governance_dir"])),
            source_version="sv_risk_tensor__sv_bond_shadow_v1__sv_liability_v1",
            running_source_version=module.RISK_TENSOR_MODULE.running_source_version,
        )

    output_dir = tmp_path / "seal-failure-output"
    receipt = module.run_bond_risk_shadow_candidate(
        report_date="2026-05-31",
        source_duckdb_path=source_path,
        expected_source_sha256=_sha256(source_path),
        output_dir=output_dir,
        bond_runner=fake_bond_runner,
        risk_runner=fake_risk_runner,
        schema_assert=lambda **kwargs: _schema_pass_receipt(module),
        run_id="shadow-run-seal-failure",
    )

    assert receipt["status"] == "failed"
    assert receipt["quarantine_state"] == "quarantine"
    assert receipt["sealed"] is False
    assert not (output_dir / module.SEALED_MARKER).exists()


def test_shadow_candidate_cli_preflight_error_prints_redacted_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module()
    live_path = tmp_path / "live.duckdb"
    source_path = tmp_path / "source.duckdb"
    _seed_source_db(live_path)
    _seed_source_db(source_path)
    _patch_settings(module, monkeypatch, live_path)

    exit_code = module.main(
        [
            "--report-date",
            "2026-05-31",
            "--source-duckdb-path",
            str(source_path),
            "--expected-source-sha256",
            _sha256(source_path),
            "--output-dir",
            "relative-output",
            "--run-id",
            "shadow-run-cli-preflight",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["status"] == "failed"
    assert payload["error"]["code"] == "output_dir_must_be_absolute"
    assert payload["receipt_persisted"] is False


def test_shadow_candidate_blocks_production_environment_before_output_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    live_path = tmp_path / "live.duckdb"
    source_path = tmp_path / "source.duckdb"
    _seed_source_db(live_path)
    _seed_source_db(source_path)
    settings = SimpleNamespace(
        environment="production",
        governance_backend="jsonl",
        source_preview_governance_backend="jsonl",
        duckdb_path=str(live_path),
    )
    monkeypatch.setattr(module, "get_settings", lambda: settings)
    monkeypatch.setenv("MOSS_ENVIRONMENT", "production")
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    monkeypatch.setenv("MOSS_SOURCE_PREVIEW_GOVERNANCE_BACKEND", "jsonl")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(live_path))
    output_dir = tmp_path / "production-forbidden-output"

    receipt = module.run_bond_risk_shadow_candidate(
        report_date="2026-05-31",
        source_duckdb_path=source_path,
        expected_source_sha256=_sha256(source_path),
        output_dir=output_dir,
        run_id="shadow-run-production-forbidden",
    )

    assert receipt["status"] == "failed"
    assert receipt["error"]["code"] == "production_environment_forbidden"
    assert receipt["receipt_persisted"] is False
    assert not output_dir.exists()


def test_governance_fixture_matches_formal_runtime_min_lineage(tmp_path: Path) -> None:
    module = _load_module()
    governance_dir = tmp_path / "governance"
    governance_dir.mkdir()
    descriptor = module.BOND_ANALYTICS_MODULE
    result = _runtime_result(
        module,
        task_name="bond",
        run_id="runtime-contract-run",
        report_date="2026-05-31",
        source_version="sv_bond_contract",
    )

    _append_governance_success(
        module,
        governance_dir,
        result,
        running_source_version=descriptor.running_source_version,
    )

    manifest = json.loads(
        (governance_dir / "cache_manifest.jsonl").read_text(encoding="utf-8").strip()
    )
    expected_min_lineage = _manifest_min_lineage(
        descriptor=descriptor,
        run_id="runtime-contract-run",
        report_date="2026-05-31",
        source_version="sv_bond_contract",
        vendor_version=descriptor.vendor_version,
    )
    assert manifest["lineage"] == expected_min_lineage
    assert "cache_key" not in manifest["lineage"]
    assert "cache_version" not in manifest["lineage"]
    assert manifest["input_sources"] == list(descriptor.input_sources)
    assert manifest["fact_tables"] == list(descriptor.fact_tables)


def test_validator_accepts_real_formal_runtime_governance_contract(
    tmp_path: Path,
) -> None:
    module = _load_module()
    runtime_module = load_module(
        "backend.app.tasks.formal_compute_runtime",
        "backend/app/tasks/formal_compute_runtime.py",
    )
    descriptor = module.BOND_ANALYTICS_MODULE
    governance_dir = tmp_path / "real-runtime-governance"
    result = runtime_module.run_formal_materialize(
        descriptor=descriptor,
        job_name="bond_analytics_materialize",
        report_date="2026-05-31",
        governance_dir=str(governance_dir),
        lock_base_dir=str(tmp_path / "locks"),
        execute_materialization=lambda: {
            "source_version": "sv_real_runtime_bond",
            "vendor_version": descriptor.vendor_version,
            "payload": {"row_count": 1},
        },
        run_id="real-runtime-contract-run",
    )
    summary, _ = module._validate_task_result(
        "bond_analytics",
        result,
        descriptor=descriptor,
        expected_job_name="bond_analytics_materialize",
        expected_run_id="real-runtime-contract-run",
        expected_report_date="2026-05-31",
    )

    validation = module._validate_governance_records(
        governance_dir,
        result_summary=summary,
        result_raw=result,
        descriptor=descriptor,
    )

    assert validation["cache_build_run"]["statuses"] == [
        "queued",
        "running",
        "completed",
    ]
    assert validation["cache_manifest"]["record_count"] == 1


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("valid", None),
        ("missing_running", "governance_build_run_sequence_invalid"),
        ("duplicate_running", "governance_build_run_sequence_invalid"),
        ("out_of_order", "governance_build_run_sequence_invalid"),
        ("unknown_phase", "governance_build_run_phase_invalid"),
        ("unknown_phase_status", "governance_build_run_phase_invalid"),
        ("failed_phase", "governance_build_run_phase_invalid"),
        ("phase_before_running", "governance_build_run_phase_invalid"),
        ("phase_after_completed", "governance_build_run_phase_invalid"),
        ("running_disguised_as_phase", "governance_build_run_sequence_invalid"),
        ("completed_disguised_as_phase", "governance_build_run_phase_invalid"),
        ("missing_phase_started_at", "governance_build_run_phase_invalid"),
        ("missing_phase_finished_at", "governance_build_run_phase_invalid"),
        ("phase_cache_version", "governance_build_run_cache_version_mismatch"),
        ("phase_lock", "governance_build_run_lock_mismatch"),
        ("phase_source_version", "governance_build_run_running_source_version_mismatch"),
        ("phase_vendor_version", "governance_build_run_running_vendor_version_mismatch"),
        ("phase_rule_version", "governance_build_run_phase_rule_version_mismatch"),
        ("invalid_phase_null", "governance_build_run_phase_invalid"),
        ("invalid_phase_false", "governance_build_run_phase_invalid"),
        ("invalid_phase_zero", "governance_build_run_phase_invalid"),
        ("invalid_phase_empty_string", "governance_build_run_phase_invalid"),
        ("invalid_phase_empty_list", "governance_build_run_phase_invalid"),
        ("invalid_phase_empty_mapping", "governance_build_run_phase_invalid"),
        ("orphan_phase_status", "governance_build_run_phase_invalid"),
        ("orphan_phase_started_at", "governance_build_run_phase_invalid"),
        ("orphan_phase_finished_at", "governance_build_run_phase_invalid"),
        ("orphan_phase_elapsed_seconds", "governance_build_run_phase_invalid"),
        ("orphan_phase_unknown", "governance_build_run_phase_invalid"),
    ],
)
def test_governance_phase_records_preserve_strict_lifecycle_and_lineage_validation(
    tmp_path: Path,
    mutation: str,
    expected_code: str | None,
) -> None:
    module = _load_module()
    descriptor = module.BOND_ANALYTICS_MODULE
    result = _governed_result(
        module,
        task_name="bond",
        run_id="phase-contract-run",
        report_date="2026-05-31",
        governance_dir=tmp_path,
        source_version="sv_bond_contract",
        running_source_version=descriptor.running_source_version,
    )
    records = module._load_jsonl_records(
        tmp_path / "cache_build_run.jsonl",
        field_name="cache_build_run_stream",
    )
    queued, running, completed = records
    phase = {
        **running,
        "rule_version": descriptor.rule_version,
        "phase": "compute",
        "phase_status": "completed",
        "phase_started_at": running["started_at"],
        "phase_finished_at": completed["finished_at"],
    }
    records = [queued, running, phase, completed]
    if mutation == "missing_running":
        records.remove(running)
    elif mutation == "duplicate_running":
        records.insert(2, dict(running))
    elif mutation == "out_of_order":
        records[0], records[1] = records[1], records[0]
    elif mutation == "unknown_phase":
        phase["phase"] = "forged_phase"
    elif mutation == "unknown_phase_status":
        phase["phase_status"] = "forged_status"
    elif mutation == "failed_phase":
        phase["phase_status"] = "failed"
    elif mutation == "phase_before_running":
        records = [queued, phase, running, completed]
    elif mutation == "phase_after_completed":
        records = [queued, running, completed, phase]
    elif mutation == "running_disguised_as_phase":
        running["phase"] = "compute"
    elif mutation == "completed_disguised_as_phase":
        records.insert(3, {**phase, "status": "completed"})
    elif mutation.startswith("invalid_phase_"):
        invalid_phase_values = {
            "null": None,
            "false": False,
            "zero": 0,
            "empty_string": "",
            "empty_list": [],
            "empty_mapping": {},
        }
        running.update({
            "phase": invalid_phase_values[mutation.removeprefix("invalid_phase_")],
            "phase_status": "completed",
            "rule_version": "forged_rule",
        })
    elif mutation.startswith("orphan_phase_"):
        running[mutation.removeprefix("orphan_")] = "forged"
        running["rule_version"] = "forged_rule"
    elif mutation.startswith("missing_phase_"):
        phase.pop(mutation.removeprefix("missing_"))
    elif mutation.startswith("phase_"):
        phase[mutation.removeprefix("phase_")] = "forged"

    summary, _ = module._validate_task_result(
        "bond_analytics",
        result,
        descriptor=descriptor,
        expected_job_name="bond_analytics_materialize",
        expected_run_id="phase-contract-run",
        expected_report_date="2026-05-31",
    )
    arguments = {
        key: summary[key]
        for key in (
            "job_name", "run_id", "report_date", "cache_key", "cache_version",
            "source_version", "vendor_version", "rule_version",
        )
    }
    if expected_code is not None:
        with pytest.raises(module.ShadowCandidateError, match=f"^{expected_code}$"):
            module._validate_governance_build_run_records(
                records, descriptor=descriptor, **arguments,
            )
    else:
        validation = module._validate_governance_build_run_records(
            records, descriptor=descriptor, **arguments,
        )
        assert validation == {
            "record_count": 3,
            "statuses": ["queued", "running", "completed"],
        }


def test_default_bond_and_risk_runners_bind_persisted_lineage_end_to_end(
    tmp_path: Path,
) -> None:
    load_module(
        "backend.app.core_finance.module_registry",
        "backend/app/core_finance/module_registry.py",
    )
    load_module(
        "backend.app.tasks.formal_compute_runtime",
        "backend/app/tasks/formal_compute_runtime.py",
    )
    bond_task = load_module(
        "backend.app.tasks.bond_analytics_materialize",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    risk_task = load_module(
        "backend.app.tasks.risk_tensor_materialize",
        "backend/app/tasks/risk_tensor_materialize.py",
    )
    module = _load_module()
    candidate_path = tmp_path / "default-runner-candidate.duckdb"
    governance_dir = tmp_path / "default-runner-governance"
    run_id = "default-bond-risk-lineage-run"
    _seed_bond_snapshot_rows(str(candidate_path))
    seed_yield_curves_for_bond_analytics_tests(str(candidate_path))

    bond_result = bond_task.materialize_bond_analytics_facts.fn(
        report_date=DEFAULT_RUNNER_REPORT_DATE,
        duckdb_path=str(candidate_path),
        governance_dir=str(governance_dir),
        run_id=run_id,
        use_existing_curves_only=True,
    )
    risk_result = risk_task.materialize_risk_tensor_facts.fn(
        report_date=DEFAULT_RUNNER_REPORT_DATE,
        duckdb_path=str(candidate_path),
        governance_dir=str(governance_dir),
        run_id=run_id,
    )
    bond_summary, _ = module._validate_task_result(
        "bond_analytics",
        bond_result,
        descriptor=module.BOND_ANALYTICS_MODULE,
        expected_job_name="bond_analytics_materialize",
        expected_run_id=run_id,
        expected_report_date=DEFAULT_RUNNER_REPORT_DATE,
    )
    risk_summary, _ = module._validate_task_result(
        "risk_tensor",
        risk_result,
        descriptor=module.RISK_TENSOR_MODULE,
        expected_job_name="risk_tensor_materialize",
        expected_run_id=run_id,
        expected_report_date=DEFAULT_RUNNER_REPORT_DATE,
        required_bond_source_version=str(bond_summary["source_version"]),
    )
    module._validate_governance_records(
        governance_dir,
        result_summary=bond_summary,
        result_raw=bond_result,
        descriptor=module.BOND_ANALYTICS_MODULE,
    )
    module._validate_governance_records(
        governance_dir,
        result_summary=risk_summary,
        result_raw=risk_result,
        descriptor=module.RISK_TENSOR_MODULE,
    )

    persisted = module._validate_candidate_risk_upstream_lineage(
        candidate_path,
        report_date=DEFAULT_RUNNER_REPORT_DATE,
        bond_result=bond_summary,
        risk_result=risk_summary,
    )

    assert persisted["source_version"] == risk_result["source_version"]
    assert persisted["rule_version"] == risk_task.RULE_VERSION
    assert persisted["cache_version"] == risk_task.CACHE_VERSION


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("input_sources", "bond_analytics_payload_input_sources_mismatch"),
        ("fact_tables", "bond_analytics_payload_fact_tables_mismatch"),
        ("basis", "bond_analytics_payload_basis_mismatch"),
        ("module_name", "bond_analytics_payload_module_name_mismatch"),
        ("result_kind_family", "bond_analytics_payload_result_kind_family_mismatch"),
        ("job_name", "bond_analytics_job_name_mismatch"),
        ("top_level_lock", "bond_analytics_lock_mismatch"),
        ("run_lock", "bond_analytics_payload_lock_mismatch"),
    ],
)
def test_task_result_requires_real_descriptor_binding(
    mutation: str,
    expected_code: str,
) -> None:
    module = _load_module()
    result = _runtime_result(
        module,
        task_name="bond",
        run_id="descriptor-binding-run",
        report_date="2026-05-31",
        source_version="sv_bond_contract",
    )
    payload = result["payload"]
    lineage = payload["lineage"]
    if mutation in {"input_sources", "fact_tables"}:
        lineage[mutation] = ["forged"]
    elif mutation in {"basis", "module_name", "result_kind_family"}:
        lineage[mutation] = "forged"
    elif mutation == "job_name":
        payload["run"]["job_name"] = "forged_materialize"
    elif mutation == "top_level_lock":
        result["lock"] = "lock:forged"
    else:
        payload["run"]["lock"] = "lock:forged"

    with pytest.raises(module.ShadowCandidateError, match=expected_code):
        module._validate_task_result(
            "bond_analytics",
            result,
            descriptor=module.BOND_ANALYTICS_MODULE,
            expected_job_name="bond_analytics_materialize",
            expected_run_id="descriptor-binding-run",
            expected_report_date="2026-05-31",
        )


def test_governance_manifest_requires_descriptor_lists_at_top_level() -> None:
    module = _load_module()
    descriptor = module.BOND_ANALYTICS_MODULE
    result = _runtime_result(
        module,
        task_name="bond",
        run_id="manifest-list-run",
        report_date="2026-05-31",
        source_version="sv_bond_contract",
    )
    summary, _ = module._validate_task_result(
        "bond_analytics",
        result,
        descriptor=descriptor,
        expected_job_name="bond_analytics_materialize",
        expected_run_id="manifest-list-run",
        expected_report_date="2026-05-31",
    )
    lineage = result["payload"]["lineage"]
    manifest = dict(lineage)
    manifest["input_sources"] = ["forged"]
    manifest["lineage"] = _manifest_min_lineage(
        descriptor=descriptor,
        run_id="manifest-list-run",
        report_date="2026-05-31",
        source_version="sv_bond_contract",
        vendor_version=descriptor.vendor_version,
    )

    with pytest.raises(
        module.ShadowCandidateError,
        match="governance_manifest_input_sources_mismatch",
    ):
        module._validate_governance_manifest_records(
            [manifest],
            result_payload=result["payload"],
            result_summary=summary,
            descriptor=descriptor,
        )


def test_task_result_rejects_prefix_collision_in_composite_source_version() -> None:
    module = _load_module()
    result = _runtime_result(
        module,
        task_name="risk",
        run_id="prefix-collision-run",
        report_date="2026-05-31",
        source_version="sv_risk_tensor__sv_ab__sv_liability",
    )

    with pytest.raises(
        module.ShadowCandidateError,
        match="risk_tensor_upstream_lineage_mismatch",
    ):
        module._validate_task_result(
            "risk_tensor",
            result,
            descriptor=module.RISK_TENSOR_MODULE,
            expected_job_name="risk_tensor_materialize",
            expected_run_id="prefix-collision-run",
            expected_report_date="2026-05-31",
            required_bond_source_version="sv_a",
        )


def test_candidate_rows_reject_prefix_collision_in_composite_source_version(
    tmp_path: Path,
) -> None:
    module = _load_module()
    candidate_path = tmp_path / "candidate.duckdb"
    _seed_source_db(candidate_path)
    _update_risk_target_rows(
        candidate_path,
        module,
        source_version="sv_risk_tensor__sv_ab__sv_liability",
        upstream_source_version="sv_a",
        upstream_rule_version=module.BOND_RULE_VERSION,
        upstream_cache_version=module.BOND_CACHE_VERSION,
    )

    with pytest.raises(
        module.ShadowCandidateError,
        match="risk_tensor_source_version_mismatch",
    ):
        module._validate_candidate_risk_upstream_lineage(
            candidate_path,
            report_date="2026-05-31",
            bond_result={
                "source_version": "sv_a",
                "rule_version": module.BOND_RULE_VERSION,
                "cache_version": module.BOND_CACHE_VERSION,
            },
            risk_result={
                "source_version": "sv_risk_tensor__sv_a__sv_liability",
                "rule_version": module.RISK_RULE_VERSION,
                "cache_version": module.RISK_CACHE_VERSION,
            },
        )


@pytest.mark.parametrize(
    ("row_source_version", "row_rule_version", "row_cache_version", "expected_code"),
    [
        ("", None, None, "risk_tensor_source_version_mismatch"),
        (
            "sv_risk_tensor__sv_a__sv_liability_B",
            None,
            None,
            "risk_tensor_source_version_mismatch",
        ),
        (
            "sv_risk_tensor__sv_a__sv_liability_A",
            "rv_wrong",
            None,
            "risk_tensor_rule_version_mismatch",
        ),
        (
            "sv_risk_tensor__sv_a__sv_liability_A",
            None,
            "cv_wrong",
            "risk_tensor_cache_version_mismatch",
        ),
    ],
)
def test_candidate_risk_rows_bind_exactly_to_runtime_result(
    tmp_path: Path,
    row_source_version: str,
    row_rule_version: str | None,
    row_cache_version: str | None,
    expected_code: str,
) -> None:
    module = _load_module()
    candidate_path = tmp_path / "candidate-exact-lineage.duckdb"
    _seed_source_db(candidate_path)
    _update_risk_target_rows(
        candidate_path,
        module,
        source_version=row_source_version,
        upstream_source_version="sv_a",
        upstream_rule_version=module.BOND_RULE_VERSION,
        upstream_cache_version=module.BOND_CACHE_VERSION,
        risk_rule_version=row_rule_version,
        risk_cache_version=row_cache_version,
    )

    with pytest.raises(module.ShadowCandidateError, match=expected_code):
        module._validate_candidate_risk_upstream_lineage(
            candidate_path,
            report_date="2026-05-31",
            bond_result={
                "source_version": "sv_a",
                "rule_version": module.BOND_RULE_VERSION,
                "cache_version": module.BOND_CACHE_VERSION,
            },
            risk_result={
                "source_version": "sv_risk_tensor__sv_a__sv_liability_A",
                "rule_version": module.RISK_RULE_VERSION,
                "cache_version": module.RISK_CACHE_VERSION,
            },
        )


def test_candidate_risk_rows_require_liability_in_composite_source_version(
    tmp_path: Path,
) -> None:
    module = _load_module()
    candidate_path = tmp_path / "candidate-liability-lineage.duckdb"
    _seed_source_db(candidate_path)
    incomplete_source_version = "sv_risk_tensor__sv_a"
    _update_risk_target_rows(
        candidate_path,
        module,
        source_version=incomplete_source_version,
        upstream_source_version="sv_a",
        upstream_rule_version=module.BOND_RULE_VERSION,
        upstream_cache_version=module.BOND_CACHE_VERSION,
        liability_source_version="sv_liability_A",
        liability_rule_version="rv_liability_A",
    )

    with pytest.raises(
        module.ShadowCandidateError,
        match="risk_tensor_composite_source_version_mismatch",
    ):
        module._validate_candidate_risk_upstream_lineage(
            candidate_path,
            report_date="2026-05-31",
            bond_result={
                "source_version": "sv_a",
                "rule_version": module.BOND_RULE_VERSION,
                "cache_version": module.BOND_CACHE_VERSION,
            },
            risk_result={
                "source_version": incomplete_source_version,
                "rule_version": module.RISK_RULE_VERSION,
                "cache_version": module.RISK_CACHE_VERSION,
            },
        )


def test_persistent_catalog_compat_without_views_is_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    source_path = tmp_path / "duckdb-1-4-compatible.duckdb"
    _seed_source_db(source_path)
    original_columns = module._table_function_columns

    def columns_without_is_bound(conn, function_name: str) -> set[str]:
        return original_columns(conn, function_name) - {"is_bound"}

    monkeypatch.setattr(module, "_table_function_columns", columns_without_is_bound)
    conn = duckdb.connect(str(source_path), read_only=True)
    try:
        catalog = module._capture_persistent_catalog(conn)
    finally:
        conn.close()

    payload = catalog["payload"]
    assert payload["capture_capabilities"]["views_is_bound_available"] is False
    view = next(
        item for item in payload["views"] if item["view_name"] == "vw_shadow_control"
    )
    assert view["is_bound"] is None
    assert "vw_shadow_control" in view["sql"]


def test_persistent_catalog_enforces_total_metadata_row_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    source_path = tmp_path / "catalog-limit.duckdb"
    _seed_source_db(source_path)
    monkeypatch.setattr(module, "_MAX_CATALOG_ROWS_TOTAL", 1)
    conn = duckdb.connect(str(source_path), read_only=True)
    try:
        with pytest.raises(
            module.ShadowCandidateError,
            match="catalog_metadata_row_limit_exceeded",
        ):
            module._capture_persistent_catalog(conn)
    finally:
        conn.close()


@pytest.mark.parametrize("field_name", ["receipt", "sealed_marker"])
def test_json_object_reader_rejects_oversized_receipt_and_marker(
    tmp_path: Path,
    field_name: str,
) -> None:
    module = _load_module()
    path = tmp_path / f"{field_name}.json"
    path.write_bytes(json.dumps({"padding": "x" * 64}).encode("utf-8"))

    with pytest.raises(module.ShadowCandidateError, match=f"{field_name}_too_large"):
        module._load_json_object(path, field_name=field_name, max_bytes=16)


@pytest.mark.parametrize(
    ("limit_kind", "expected_code"),
    [
        ("total_bytes", "governance_stream_too_large"),
        ("line_bytes", "governance_stream_line_too_large"),
        ("line_count", "governance_stream_line_limit_exceeded"),
    ],
)
def test_jsonl_reader_enforces_resource_limits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    limit_kind: str,
    expected_code: str,
) -> None:
    module = _load_module()
    path = tmp_path / "governance.jsonl"
    line = json.dumps({"padding": "x" * 64}).encode("utf-8") + b"\n"
    if limit_kind == "total_bytes":
        monkeypatch.setattr(module, "_MAX_JSONL_TOTAL_BYTES", len(line) - 1)
        monkeypatch.setattr(module, "_MAX_JSONL_LINE_BYTES", len(line) + 1)
        path.write_bytes(line)
    elif limit_kind == "line_bytes":
        monkeypatch.setattr(module, "_MAX_JSONL_LINE_BYTES", len(line) - 1)
        path.write_bytes(line)
    else:
        monkeypatch.setattr(module, "_MAX_JSONL_LINES", 1)
        path.write_bytes(line + line)

    with pytest.raises(module.ShadowCandidateError, match=expected_code):
        module._load_jsonl_records(path, field_name="governance_stream")
