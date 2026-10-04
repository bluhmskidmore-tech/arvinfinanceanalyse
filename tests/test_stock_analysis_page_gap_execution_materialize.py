from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import duckdb
import pytest

from backend.app.tasks import stock_analysis_page_gap_execution_materialize as module
from backend.app.tasks import (
    stock_analysis_page_gap_factor_manifest as factor_manifest_task,
)
from backend.app.tasks import stock_analysis_page_gap_factor_write as factor_write_task
from backend.app.tasks import stock_analysis_page_gap_manifest as page_task
from backend.app.governance import (
    stock_analysis_page_gap_factor_vendor_receipt as vendor_receipt_task,
)

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_livermore,
]

CREATED_AT = "2026-08-24T12:00:00Z"
SIGNAL_KINDS = (
    "stock_candidate",
    "theme_breakout",
    "hybrid_fusion",
    "market_state",
    "sector_rotation",
    "limit_breakout",
    "volume_breakout",
)


def _create_execution_schema(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table livermore_candidate_execution_history (
          signal_date varchar,
          stock_code varchar,
          stock_name varchar,
          signal_kind varchar,
          candidate_rank integer,
          market_state varchar,
          signal_close double,
          entry_date varchar,
          entry_price double,
          entry_price_kind varchar,
          entry_executable boolean,
          entry_block_reason varchar,
          entry_ex_div boolean,
          exit_date_1d varchar,
          exit_price_1d double,
          return_1d_gross double,
          return_1d_net double,
          return_1d_gross_adj double,
          return_1d_net_adj double,
          exit_date_5d varchar,
          exit_price_5d double,
          return_5d_gross double,
          return_5d_net double,
          return_5d_gross_adj double,
          return_5d_net_adj double,
          exit_date_10d varchar,
          exit_price_10d double,
          return_10d_gross double,
          return_10d_net double,
          return_10d_gross_adj double,
          return_10d_net_adj double,
          exit_date_20d varchar,
          exit_price_20d double,
          return_20d_gross double,
          return_20d_net double,
          return_20d_gross_adj double,
          return_20d_net_adj double,
          buy_cost_bps double,
          sell_cost_bps double,
          slippage_bps double,
          price_adjustment_mode varchar,
          data_status varchar,
          formula_version varchar,
          run_id varchar,
          evidence_json varchar
        )
        """
    )
    conn.execute(
        """
        create table stock_adjustment_factor (
          stock_code varchar,
          trade_date varchar,
          adj_factor double,
          source_version varchar,
          run_id varchar
        )
        """
    )


def _execution_row(
    *,
    stock_code: str,
    signal_kind: str,
    candidate_rank: int,
    adjusted: bool = False,
    data_status: str = "complete",
) -> tuple[object, ...]:
    base_price = 10.0 + candidate_rank
    adjusted_values = (0.01, 0.009, 0.02, 0.019, 0.03, 0.029, 0.04, 0.039)
    if not adjusted:
        adjusted_values = (None,) * 8
    return (
        "2026-01-02",
        stock_code,
        f"股票{candidate_rank}",
        signal_kind,
        candidate_rank,
        "bull",
        base_price - 0.1,
        "2026-01-05",
        base_price,
        "next_open",
        True,
        None,
        False,
        "2026-01-06",
        base_price * 1.01,
        0.01,
        0.008,
        adjusted_values[0],
        adjusted_values[1],
        "2026-01-09",
        base_price * 1.02,
        0.02,
        0.018,
        adjusted_values[2],
        adjusted_values[3],
        "2026-01-16",
        base_price * 1.03,
        0.03,
        0.028,
        adjusted_values[4],
        adjusted_values[5],
        "2026-02-02",
        base_price * 1.04,
        0.04,
        0.038,
        adjusted_values[6],
        adjusted_values[7],
        10.0,
        20.0,
        5.0,
        "adj_factor_ratio",
        data_status,
        "fv_livermore_candidate_execution_dual_adjust_v5",
        f"execution-run-{candidate_rank}",
        json.dumps({"seed": candidate_rank}, ensure_ascii=False),
    )


def _prepare_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> dict[str, Any]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "materialize.duckdb"
    trusted_root = tmp_path / "evidence"
    backups_root = tmp_path / "backups"
    trusted_root.mkdir()
    backups_root.mkdir()
    with duckdb.connect(str(db_path)) as conn:
        _create_execution_schema(conn)
        for index, signal_kind in enumerate(SIGNAL_KINDS, start=1):
            stock_code = "600001.SH" if index == 2 else f"{600000 + index:06d}.SH"
            conn.execute(
                "insert into livermore_candidate_execution_history values ("
                + ",".join("?" for _ in range(45))
                + ")",
                _execution_row(
                    stock_code=stock_code,
                    signal_kind=signal_kind,
                    candidate_rank=index,
                    data_status="pending" if index == len(SIGNAL_KINDS) else "complete",
                ),
            )
        conn.execute(
            "insert into livermore_candidate_execution_history values ("
            + ",".join("?" for _ in range(45))
            + ")",
            _execution_row(
                stock_code="600099.SH",
                signal_kind="non_target",
                candidate_rank=99,
                adjusted=True,
            ),
        )

    page_manifest = page_task.build_stock_analysis_page_gap_manifest(
        duckdb_path=db_path,
        evaluation_as_of_date="2026-08-24",
        created_at=CREATED_AT,
    )
    valid, errors = page_task.validate_stock_analysis_page_gap_manifest(page_manifest)
    assert valid, errors
    assert page_manifest["summary"]["unique_execution_key_count"] == 7
    assert page_manifest["summary"]["page_gap_view_count_before"] == 28
    page_path = trusted_root / "page-manifest.json"
    page_path.write_text(
        json.dumps(page_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    h0 = module._file_sha256(db_path)
    backup_path = backups_root / "factor-prewrite.duckdb"
    shutil.copyfile(db_path, backup_path)
    assert module._file_sha256(backup_path) == h0

    target_cells = sorted(
        [
            {"stock_code": item["stock_code"], "trade_date": item["trade_date"]}
            for item in page_manifest["missing_factor_cells"]
        ],
        key=lambda item: (item["trade_date"], item["stock_code"]),
    )
    factor_rows: list[dict[str, Any]] = []
    with duckdb.connect(str(db_path)) as conn:
        for index, cell in enumerate(target_cells, start=1):
            factor = 1.0 + index / 10000.0
            conn.execute(
                "insert into stock_adjustment_factor values (?, ?, ?, ?, ?)",
                [
                    cell["stock_code"],
                    cell["trade_date"],
                    factor,
                    "vendor-capture-v1",
                    "factor-run-v1",
                ],
            )
            factor_rows.append(
                {
                    "requested_trade_date": cell["trade_date"],
                    "stock_code": cell["stock_code"],
                    "trade_date": cell["trade_date"],
                    "adj_factor": factor,
                }
            )
    factor_rows.sort(key=lambda item: (item["trade_date"], item["stock_code"]))
    h1 = module._file_sha256(db_path)
    page_summary = page_manifest["summary"]
    page_binding = {
        "path": str(page_path.resolve()),
        "file_sha256": module._file_sha256(page_path),
        "canonical_manifest_sha256": page_manifest["canonical_manifest_sha256"],
        "manifest_kind": page_manifest["manifest_kind"],
        "page_id": page_manifest["page_id"],
        "page_route": page_manifest["page_route"],
        "page_metric_key": page_manifest["page_metric_key"],
        "database_path": str(db_path.resolve()),
        "database_sha256": h0,
        "page_gap_view_count": page_summary["page_gap_view_count_before"],
        "missing_factor_cell_count": page_summary["unique_missing_factor_cell_count"],
    }
    factor_manifest_path = trusted_root / "factor-manifest.json"
    factor_manifest = {
        "page_manifest_binding": page_binding,
        "database": {"path": str(db_path.resolve()), "sha256_before": h0},
        "canonical_manifest_sha256": "E" * 64,
        "manifest_kind": factor_manifest_task.MANIFEST_KIND,
        "status": "gaps_found",
    }
    factor_manifest_path.write_text(json.dumps(factor_manifest), encoding="utf-8")
    factor_manifest_file_sha = module._file_sha256(factor_manifest_path)
    target_rows_sha = module._canonical_json_sha256(factor_rows)
    vendor_path = trusted_root / "vendor-receipt.json"
    vendor_receipt = {
        "database": {"path": str(db_path.resolve()), "sha256_before": h0},
        "canonical_receipt_sha256": "F" * 64,
        "receipt_kind": vendor_receipt_task.RECEIPT_KIND,
        "status": vendor_receipt_task.READY_STATUS,
        "returned_cells_sha256": target_rows_sha,
        "returned_cell_count": len(target_cells),
        "proposed_source_version": "vendor-capture-v1",
        "proposed_run_id": "factor-run-v1",
    }
    vendor_path.write_text(json.dumps(vendor_receipt), encoding="utf-8")
    vendor_file_sha = module._file_sha256(vendor_path)
    approval_scope_sha = vendor_receipt_task.factor_approval_scope_sha256(
        factor_manifest_file_sha256=factor_manifest_file_sha,
        factor_manifest_canonical_sha256=factor_manifest["canonical_manifest_sha256"],
        page_manifest_file_sha256=page_binding["file_sha256"],
        page_manifest_canonical_sha256=page_binding["canonical_manifest_sha256"],
        vendor_receipt_file_sha256=vendor_file_sha,
        vendor_receipt_canonical_sha256=vendor_receipt["canonical_receipt_sha256"],
        database_sha256_before=h0,
        returned_cells_sha256=target_rows_sha,
        target_cell_count=len(target_cells),
        source_version="vendor-capture-v1",
        run_id="factor-run-v1",
    )
    factor_receipt = factor_write_task._build_write_receipt(
        executed_at=CREATED_AT,
        approval_reference="approved-factor-write",
        approval_scope_sha256=approval_scope_sha,
        page_manifest=page_manifest,
        page_manifest_path=page_path.resolve(),
        page_manifest_file_sha256=page_binding["file_sha256"],
        factor_manifest=factor_manifest,
        factor_manifest_path=factor_manifest_path.resolve(),
        factor_manifest_file_sha256=factor_manifest_file_sha,
        vendor_receipt=vendor_receipt,
        vendor_receipt_path=vendor_path.resolve(),
        vendor_receipt_file_sha256=vendor_file_sha,
        database_path=db_path.resolve(),
        database_sha_before=h0,
        database_sha_after=h1,
        backup_path=backup_path.resolve(),
        backup_sha256=h0,
        target_rows=factor_rows,
        source_version="vendor-capture-v1",
        run_id="factor-run-v1",
    )
    valid_receipt, receipt_errors = (
        factor_write_task.validate_stock_analysis_page_gap_factor_write_receipt(
            factor_receipt
        )
    )
    assert valid_receipt, receipt_errors
    factor_receipt_path = trusted_root / "factor-write-receipt.json"
    factor_receipt_path.write_text(
        json.dumps(factor_receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "db_path": db_path,
        "trusted_root": trusted_root,
        "page_path": page_path,
        "factor_receipt_path": factor_receipt_path,
        "backup_path": backup_path,
        "page_manifest": page_manifest,
        "factor_receipt": factor_receipt,
        "h0": h0,
        "h1": h1,
    }


def _plan(context: dict[str, Any]) -> dict[str, Any]:
    return (
        module.build_stock_analysis_page_gap_execution_materialization_plan_from_files(
            duckdb_path=context["db_path"],
            trusted_evidence_root=context["trusted_root"],
            page_manifest_file=context["page_path"],
            factor_write_receipt_file=context["factor_receipt_path"],
            created_at=CREATED_AT,
        )
    )


def _live(
    context: dict[str, Any],
    *,
    output_name: str = "materialization-receipt.json",
    expected_scope: str | None = None,
) -> dict[str, Any]:
    plan = _plan(context)
    return module.materialize_stock_analysis_page_gap_execution_history(
        duckdb_path=context["db_path"],
        trusted_evidence_root=context["trusted_root"],
        page_manifest_file=context["page_path"],
        factor_write_receipt_file=context["factor_receipt_path"],
        write_receipt_file=output_name,
        executed_at=CREATED_AT,
        approval_reference="user-approved-exact-materialization-scope",
        expected_materialization_approval_scope_sha256=(
            expected_scope or plan["approval_scope_sha256"]
        ),
        allow_write=True,
    )


def test_dry_run_ties_all_signal_kinds_and_horizons_without_writing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _prepare_context(monkeypatch, tmp_path)
    before = module._file_sha256(context["db_path"])

    plan = _plan(context)

    assert plan["status"] == module.READY_STATUS
    assert plan["database_write_executed"] is False
    assert plan["read_only"] is True
    assert plan["summary"]["target_execution_key_count"] == 7
    assert plan["summary"]["clearable_execution_key_count"] == 7
    assert plan["summary"]["target_gap_horizon_count"] == 28
    assert plan["summary"]["clearable_gap_horizon_count"] == 28
    assert plan["summary"]["projected_page_gap_view_count_after"] == 0
    assert plan["summary"]["projected_horizon_gap_counts_after"] == [
        {"value": label, "count": 0} for label in ("1d", "5d", "10d", "20d")
    ]
    assert {item["value"] for item in plan["summary"]["signal_kind_counts"]} == set(
        SIGNAL_KINDS
    )
    assert plan["rollback_anchor"]["sha256"] == context["h0"]
    assert plan["rollback_anchor"]["second_backup_created"] is False
    assert plan["database"]["factor_write_after_sha256"] == context["h1"]
    assert plan["historical_availability_proven"] is False
    assert plan["certification_allowed"] is False
    valid, errors = (
        module.validate_stock_analysis_page_gap_execution_materialization_plan(plan)
    )
    assert valid, errors
    assert module._file_sha256(context["db_path"]) == before


def test_live_updates_only_exact_missing_adjusted_fields_and_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _prepare_context(monkeypatch, tmp_path)
    with duckdb.connect(str(context["db_path"]), read_only=True) as conn:
        before_rows = conn.execute(
            "select * from livermore_candidate_execution_history order by stock_code"
        ).fetchall()
        columns = [
            row[1]
            for row in conn.execute(
                "pragma table_info('livermore_candidate_execution_history')"
            ).fetchall()
        ]

    receipt = _live(context)

    assert receipt["status"] == module.COMPLETED_STATUS
    assert receipt["database_write_executed"] is True
    assert receipt["target_execution_key_count"] == 7
    assert receipt["target_gap_horizon_count"] == 28
    assert receipt["target_rows_deleted"] == 0
    assert receipt["non_target_rows_changed"] == 0
    assert receipt["verification"]["page_gap_view_count_after"] == 0
    assert receipt["verification"]["horizon_gap_counts_after"] == {
        "1d": 0,
        "5d": 0,
        "10d": 0,
        "20d": 0,
    }
    assert receipt["historical_availability_proven"] is False
    assert receipt["certification_allowed"] is False
    assert module._file_sha256(context["backup_path"]) == context["h0"]

    with duckdb.connect(str(context["db_path"]), read_only=True) as conn:
        after_rows = conn.execute(
            "select * from livermore_candidate_execution_history order by stock_code"
        ).fetchall()
    before_payloads = [dict(zip(columns, row, strict=True)) for row in before_rows]
    after_payloads = [dict(zip(columns, row, strict=True)) for row in after_rows]
    assert len(before_payloads) == len(after_payloads) == 8
    for before, after in zip(before_payloads, after_payloads, strict=True):
        if before["stock_code"] == "600099.SH":
            assert after == before
            continue
        for column in columns:
            if column.startswith("return_") and column.endswith(
                ("_gross_adj", "_net_adj")
            ):
                assert after[column] is not None
            elif column == "evidence_json":
                evidence = json.loads(after[column])
                assert evidence["seed"] == before_payloads.index(before) + 1
                trace = evidence[module.EVIDENCE_TRACE_KEY]
                assert (
                    trace["approval_scope_sha256"] == receipt["approval_scope_sha256"]
                )
                assert trace["historical_availability_proven"] is False
            else:
                assert after[column] == before[column]


def test_scope_mismatch_blocks_before_pending_or_database_write(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _prepare_context(monkeypatch, tmp_path)
    before = module._file_sha256(context["db_path"])
    output = context["trusted_root"] / "wrong-scope.json"

    with pytest.raises(
        module.PageGapExecutionMaterializeError,
        match="approval scope SHA does not match",
    ):
        _live(context, output_name=output.name, expected_scope="F" * 64)

    assert module._file_sha256(context["db_path"]) == before
    assert output.exists() is False


def test_current_database_hash_drift_blocks_dry_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _prepare_context(monkeypatch, tmp_path)
    with duckdb.connect(str(context["db_path"])) as conn:
        conn.execute(
            "update livermore_candidate_execution_history set market_state = 'drifted' "
            "where stock_code = '600099.SH'"
        )

    with pytest.raises(
        module.PageGapExecutionMaterializeError,
        match="current DuckDB SHA does not match",
    ):
        _plan(context)


def test_partial_materialization_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _prepare_context(monkeypatch, tmp_path)
    with duckdb.connect(str(context["db_path"])) as conn:
        conn.execute(
            "update livermore_candidate_execution_history "
            "set return_1d_gross_adj = 0.1, return_1d_net_adj = 0.09 "
            "where stock_code = '600001.SH'"
        )

    with pytest.raises(module.PageGapExecutionMaterializeError):
        _plan(context)


def test_transaction_failure_rolls_back_and_preserves_pending_intent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _prepare_context(monkeypatch, tmp_path)
    original_apply = module._apply_exact_target_updates

    def _update_then_fail(*args: Any, **kwargs: Any) -> dict[Any, Any]:
        original_apply(*args, **kwargs)
        raise RuntimeError("simulated failure after updates")

    monkeypatch.setattr(module, "_apply_exact_target_updates", _update_then_fail)
    output = context["trusted_root"] / "pending-after-failure.json"
    with pytest.raises(RuntimeError, match="simulated failure"):
        _live(context, output_name=output.name)

    pending = json.loads(output.read_text(encoding="utf-8"))
    assert pending["intent_kind"] == module.PENDING_INTENT_KIND
    assert pending["status"] == module.PENDING_STATUS
    assert pending["database_write_executed"] is False
    with duckdb.connect(str(context["db_path"]), read_only=True) as conn:
        remaining = conn.execute(
            "select count(*) from livermore_candidate_execution_history "
            "where return_1d_net is not null and return_1d_net_adj is null"
        ).fetchone()[0]
    assert remaining == 7


def test_already_complete_dry_run_and_live_replay_are_noop(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _prepare_context(monkeypatch, tmp_path)
    first = _live(context, output_name="first-receipt.json")
    completed_sha = module._file_sha256(context["db_path"])

    second_plan = _plan(context)
    assert second_plan["status"] == module.ALREADY_COMPLETE_STATUS
    assert second_plan["summary"]["pending_update_field_count"] == 0
    assert second_plan["approval_scope_sha256"] == first["approval_scope_sha256"]

    replay = _live(context, output_name="replay-receipt.json")
    assert replay["status"] == module.ALREADY_COMPLETE_STATUS
    assert replay["database_write_executed"] is False
    assert replay["updated_execution_key_count"] == 0
    assert module._file_sha256(context["db_path"]) == completed_sha


def test_plan_validator_detects_target_scope_tamper(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _prepare_context(monkeypatch, tmp_path)
    plan = _plan(context)
    plan["targets"][0]["horizons"][0]["computed_adjusted_net"] += 0.01
    plan["canonical_plan_sha256"] = module._plan_sha256(plan)

    valid, errors = (
        module.validate_stock_analysis_page_gap_execution_materialization_plan(plan)
    )

    assert valid is False
    assert "plan.target_scope.calculation_outputs_sha256 mismatch" in errors


def test_calculation_output_digest_is_part_of_independent_approval_scope() -> None:
    kwargs = {
        "page_manifest_canonical_sha256": "A" * 64,
        "page_manifest_file_sha256": "B" * 64,
        "factor_write_receipt_canonical_sha256": "C" * 64,
        "factor_write_receipt_file_sha256": "D" * 64,
        "factor_database_sha256_after": "E" * 64,
        "target_execution_keys_sha256": "F" * 64,
        "target_horizons_sha256": "1" * 64,
        "target_execution_key_count": 2446,
        "target_gap_horizon_count": 5022,
    }

    first = module._materialization_approval_scope_sha256(
        **kwargs,
        calculation_outputs_sha256="2" * 64,
    )
    changed_output = module._materialization_approval_scope_sha256(
        **kwargs,
        calculation_outputs_sha256="3" * 64,
    )

    assert first != changed_output


def test_factor_target_row_digest_and_backup_mismatch_block(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _prepare_context(monkeypatch, tmp_path)
    receipt = json.loads(context["factor_receipt_path"].read_text(encoding="utf-8"))
    receipt["target_rows_sha256"] = "A" * 64
    context["factor_receipt_path"].write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(
        module.PageGapExecutionMaterializeError, match="factor write receipt failed"
    ):
        _plan(context)

    context = _prepare_context(monkeypatch, tmp_path / "backup-case")
    context["backup_path"].write_bytes(b"tampered")
    with pytest.raises(module.PageGapExecutionMaterializeError, match="backup SHA"):
        _plan(context)


def test_final_receipt_replace_detects_wrong_leaf_and_preserves_replacement(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "pending.json"
    pending = {"status": "pending"}
    final = {"status": "complete"}
    module._write_json_exclusive(path, payload=pending)
    replacement_text = "replacement-owned-by-another-process"

    def _swap_wrong_leaf(source: str | Path, destination: str | Path) -> None:
        source_path = Path(source)
        destination_path = Path(destination)
        source_path.unlink()
        destination_path.unlink()
        destination_path.write_text(replacement_text, encoding="utf-8")

    monkeypatch.setattr(module.os, "replace", _swap_wrong_leaf)

    with pytest.raises(
        module.PageGapExecutionMaterializeError,
        match="identity does not match generated temporary receipt",
    ):
        module._replace_json_atomically_preserving_existing(
            path,
            payload=final,
            expected_existing=pending,
        )

    assert path.read_text(encoding="utf-8") == replacement_text


def test_final_receipt_failure_cleanup_preserves_replacement_temp_leaf(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "pending.json"
    pending = {"status": "pending"}
    final = {"status": "complete"}
    module._write_json_exclusive(path, payload=pending)
    replacement_text = "temporary-leaf-owned-by-another-process"
    replacement_source = tmp_path / "outsider.tmp"
    replacement_source.write_text(replacement_text, encoding="utf-8")
    captured_temp_path: list[Path] = []
    original_load_json_object = module._load_json_object

    def _replace_temp_before_readback(
        candidate: Path, *, field_name: str
    ) -> dict[str, Any]:
        if field_name != "temporary final receipt":
            return original_load_json_object(candidate, field_name=field_name)
        module.os.replace(replacement_source, candidate)
        captured_temp_path.append(candidate)
        return {"status": "replacement"}

    monkeypatch.setattr(module, "_load_json_object", _replace_temp_before_readback)

    with pytest.raises(
        module.PageGapExecutionMaterializeError,
        match="temporary final receipt readback mismatch",
    ):
        module._replace_json_atomically_preserving_existing(
            path,
            payload=final,
            expected_existing=pending,
        )

    assert json.loads(path.read_text(encoding="utf-8")) == pending
    assert len(captured_temp_path) == 1
    assert captured_temp_path[0].read_text(encoding="utf-8") == replacement_text
