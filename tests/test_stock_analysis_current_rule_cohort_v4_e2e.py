"""A source-backed lifecycle check for the current-rule v4 cohort."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import duckdb
import pytest

from backend.app.core_finance.matched_baseline import _control_execution_pit_proof
from backend.app.tasks import stock_analysis_current_rule_cohort_materialize as task
from tests.test_stock_analysis_current_rule_cohort_materialize import (
    NOW,
    _approval,
    _base_database,
    _bundle_artifacts,
    _file_sha,
    _reseal_bundle_payload,
    _write,
)

pytestmark = [pytest.mark.excluded_surface_acceptance, pytest.mark.surface_livermore]


def _source_backed_bundle(tmp_path: Path) -> tuple[Path, dict[str, Path | str]]:
    """Extend the on-disk lifecycle fixture with real observations and core proofs."""
    target = _base_database(tmp_path)
    bundle_ref = _bundle_artifacts(tmp_path, target=target, cohort_id="v4-source-backed")
    bundle_path = Path(bundle_ref["bundle_path"])
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    validated = task._load_and_validate_bundle(bundle_path)
    source_index = {
        (table, source, vendor or None, rule or None, run): available
        for (table, source, vendor, rule, run), available
        in validated.source_availability_index.items()
    }

    # The same 20 eligible controls can serve all five candidates on a signal
    # date. This keeps the source fixture small while preserving 100 distinct
    # candidate facts, 20 dates, and 20 independent controls per fact.
    codes: dict[tuple[str, str], float] = {}
    for fact in payload["facts"]:
        signal_date = fact["signal_date"]
        codes[(fact["stock_code"], signal_date)] = 10.0
        for index, control in enumerate(fact["control_pit_proof"]["controls"]):
            control_code = f"CONTROL-{signal_date}-{index:02d}.SZ"
            control["control_stock_code"] = control_code
            codes[(control_code, signal_date)] = 9.0

    conn = duckdb.connect(str(target))
    try:
        conn.execute(
            "create table if not exists choice_stock_daily_observation ("
            "trade_date varchar, stock_code varchar, open_value double, close_value double, "
            "tradestatus varchar, highlimit varchar, lowlimit varchar, source_version varchar, "
            "vendor_version varchar, rule_version varchar, run_id varchar)"
        )
        conn.execute(
            "create table if not exists stock_adjustment_factor ("
            "stock_code varchar, trade_date varchar, adj_factor double, source_version varchar, "
            "run_id varchar, vendor_version varchar, rule_version varchar)"
        )
        factor_columns = {
            row[1] for row in conn.execute("pragma table_info('stock_adjustment_factor')").fetchall()
        }
        for column in ("vendor_version", "rule_version"):
            if column not in factor_columns:
                conn.execute(f"alter table stock_adjustment_factor add column {column} varchar")
        conn.execute(
            "create temporary table synthetic_codes "
            "(stock_code varchar, signal_date varchar, open_price double)"
        )
        conn.executemany(
            "insert into synthetic_codes values (?, ?, ?)",
            [(code, signal_date, price) for (code, signal_date), price in codes.items()],
        )
        conn.execute(
            """
            insert into choice_stock_daily_observation
                (trade_date, stock_code, open_value, close_value, tradestatus,
                 highlimit, lowlimit, source_version, vendor_version, rule_version, run_id)
            select strftime(cast(signal_date as date) + day_index * interval '1 day', '%Y-%m-%d'),
                   stock_code, open_price, open_price, 'Trading', '12', '8',
                   'sv_obs_proven', 'vv_choice', 'rv_source_v1', 'source-run-observation'
            from synthetic_codes cross join range(1, 21) as days(day_index)
            """
        )
        conn.execute(
            """
            insert into stock_adjustment_factor
                (stock_code, trade_date, adj_factor, source_version, run_id,
                 vendor_version, rule_version)
            select stock_code,
                   strftime(cast(signal_date as date) + day_index * interval '1 day', '%Y-%m-%d'),
                   1.0, 'sv_factor_proven', 'source-run-factor', 'vv_choice', 'rv_source_v1'
            from synthetic_codes cross join range(1, 21) as days(day_index)
            """
        )
        assert len(codes) == 500
        assert conn.execute(
            "select count(*) from choice_stock_daily_observation"
        ).fetchone()[0] == 10_000
        assert conn.execute(
            "select count(*) from stock_adjustment_factor"
        ).fetchone()[0] == 10_000

        proofs: dict[tuple[str, str], dict[str, object]] = {}
        for code, signal_date in codes:
            proof = _control_execution_pit_proof(
                conn,
                stock_code=code,
                signal_date=signal_date,
                evaluation_as_of_date=payload["evaluation_as_of_date"],
                source_availability_index=source_index,
            )
            assert proof["failure_reason"] is None, (code, signal_date, proof)
            proofs[(code, signal_date)] = proof
    finally:
        conn.close()

    for fact in payload["facts"]:
        signal_date = fact["signal_date"]
        candidate = proofs[(fact["stock_code"], signal_date)]
        fact["entry_date"] = candidate["entry"]["trade_date"]
        fact["entry_price"] = candidate["entry"]["price"]
        fact["entry_executable"] = candidate["entry"]["executable"]
        for horizon in ("5d", "20d"):
            result = candidate["horizons"][horizon]
            fact[f"exit_date_{horizon}"] = result["trade_date"]
            fact[f"exit_price_{horizon}"] = result["price"]
            fact[f"return_{horizon}_net_adj"] = result["net_adj_return"]
        fact["evidence"]["candidate_source_evidence"] = candidate["source_evidence"]

        control_returns: dict[str, list[float]] = {"5d": [], "20d": []}
        for control in fact["control_pit_proof"]["controls"]:
            proof = proofs[(control["control_stock_code"], signal_date)]
            control["control_entry_date"] = proof["entry"]["trade_date"]
            control["control_entry_price"] = proof["entry"]["price"]
            control["control_entry_executable"] = proof["entry"]["executable"]
            control["control_entry_usable"] = proof["entry"]["usable"]
            for horizon in ("5d", "20d"):
                result = proof["horizons"][horizon]
                control[f"control_exit_date_{horizon}"] = result["trade_date"]
                control[f"control_exit_price_{horizon}"] = result["price"]
                control[f"control_return_{horizon}_net_adj"] = result["net_adj_return"]
                control[f"control_return_{horizon}_usable"] = result["usable"]
                control_returns[horizon].append(result["net_adj_return"])
            control["source_evidence"] = proof["source_evidence"]
        for horizon in ("5d", "20d"):
            fact[f"matched_alpha_{horizon}"] = (
                fact[f"return_{horizon}_net_adj"]
                - sum(control_returns[horizon]) / len(control_returns[horizon])
            )

    payload = _reseal_bundle_payload(payload, target=target)
    _write(bundle_path, payload)
    bundle_ref["bundle_sha"] = str(payload["canonical_bundle_sha256"])
    return target, bundle_ref


def test_v4_source_backed_dry_run_materialize_and_promote(tmp_path: Path) -> None:
    target, bundle = _source_backed_bundle(tmp_path)
    bundle_path = Path(bundle["bundle_path"])
    before_sha = _file_sha(target)
    dry_path = tmp_path / "dry-run.json"
    dry = task.build_stock_analysis_current_rule_cohort_dry_run(
        duckdb_path=target,
        bundle_path=bundle_path,
        receipt_path=dry_path,
        created_at=NOW,
    )
    assert dry_path.is_file()
    assert json.loads(dry_path.read_text(encoding="utf-8")) == dry
    assert dry["status"] == "dry_run_completed"
    assert dry["database_unchanged"] is True
    assert dry["target_database_sha256_after"] == before_sha == _file_sha(target)
    assert dry["summary"]["completed_dates"] == 20
    assert dry["summary"]["matched_entry_count"] == 100

    backup = tmp_path / "before-materialize.duckdb"
    shutil.copy2(target, backup)
    material_approval = _approval(
        tmp_path / "materialize-approval.json",
        operation="materialize",
        bundle=bundle,
        target_sha=before_sha,
        extra={"dry_run_receipt_sha256": dry["canonical_receipt_sha256"]},
    )
    material_path = tmp_path / "materialize.json"
    material = task.materialize_stock_analysis_current_rule_cohort(
        duckdb_path=target,
        bundle_path=bundle_path,
        dry_run_receipt_path=dry_path,
        approval_artifact_path=material_approval,
        target_backup_path=backup,
        receipt_path=material_path,
        allow_write=True,
        created_at=NOW,
    )
    assert material_path.is_file()
    assert json.loads(material_path.read_text(encoding="utf-8")) == material
    assert material["status"] == task.MATERIALIZED_STATUS
    assert material["dry_run_receipt_sha256"] == dry["canonical_receipt_sha256"]
    assert material["backup_sha256"] == before_sha

    promote_approval = _approval(
        tmp_path / "promote-approval.json",
        operation="promote",
        bundle=bundle,
        target_sha=_file_sha(target),
        extra={"materialize_receipt_sha256": material["canonical_receipt_sha256"]},
    )
    promote_path = tmp_path / "promotion.json"
    promoted = task.promote_stock_analysis_current_rule_cohort(
        duckdb_path=target,
        bundle_path=bundle_path,
        materialize_receipt_path=material_path,
        approval_artifact_path=promote_approval,
        receipt_path=promote_path,
        allow_write=True,
        created_at=NOW,
    )
    assert promote_path.is_file()
    assert json.loads(promote_path.read_text(encoding="utf-8")) == promoted
    assert promoted["status"] == task.CERTIFIED_STATUS
    assert promoted["materialize_receipt_sha256"] == material["canonical_receipt_sha256"]

    conn = duckdb.connect(str(target), read_only=True)
    try:
        manifest = conn.execute(
            f"select cohort_status, is_active, completed_dates, matched_entry_count, notes_json "
            f"from {task.MANIFEST_TABLE} where cohort_id = ?",
            [bundle["cohort_id"]],
        ).fetchone()
        assert manifest is not None
        assert manifest[:4] == (task.CERTIFIED_STATUS, True, 20, 100)
        assert conn.execute(f"select count(*) from {task.FACT_TABLE}").fetchone()[0] == 100
        assert conn.execute(f"select count(*) from {task.CERTIFICATE_TABLE}").fetchone()[0] == 20
        notes = json.loads(manifest[4])
        assert notes["materialize_receipt_path"] == str(material_path.resolve())
        assert notes["materialize_receipt_sha256"] == material["canonical_receipt_sha256"]
        assert conn.execute(
            f"select count(*) from {task.MANIFEST_TABLE} where is_active = true"
        ).fetchone()[0] == 1
    finally:
        conn.close()
