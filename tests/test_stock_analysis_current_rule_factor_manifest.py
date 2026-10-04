from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import duckdb
import pytest

from backend.app.core_finance.livermore_stock_candidates import (
    EXP3B_STOCK_CANDIDATE_POLICY,
)
from backend.app.core_finance.livermore_stock_candidates import (
    FORMULA_VERSION as STOCK_CANDIDATE_FORMULA_VERSION,
)
from backend.app.core_finance.matched_baseline import (
    FORMULA_VERSION as MATCHED_BASELINE_FORMULA_VERSION,
)
from backend.app.governance.stock_analysis_current_rule_certificate import (
    ALLOWED_DECISION_METRIC_BASIS,
    CURRENT_RULE_COVERAGE_AUTHORITY_MODE,
)
from backend.app.governance import stock_analysis_current_rule_version_tuple as version_module
from backend.app.governance.stock_analysis_source_availability_receipt import (
    build_stock_analysis_source_availability_receipt,
)
from backend.app.services.livermore_signal_confluence_service import (
    LIVERMORE_SIGNAL_CONFLUENCE_RULE_VERSION,
)
from backend.app.tasks import livermore_candidate_history_materialize as execution_task
from backend.app.tasks import stock_analysis_current_rule_factor_manifest as module

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]

SOURCE_VERSION = "factor-source-v1"
RUN_ID = "factor-run-v1"
EVALUATION = "2026-01-31"
CREATED_AT = "2026-01-31T12:00:00Z"
SHA_A = "A" * 64
SHA_B = "B" * 64


def _version_tuple() -> dict[str, object]:
    return {
        "candidate_rule_version": execution_task.RULE_VERSION,
        "stock_candidate_selection_formula_version": STOCK_CANDIDATE_FORMULA_VERSION,
        "candidate_outcome_formula_version": execution_task.FORMULA_VERSION,
        "execution_formula_version": execution_task.EXECUTION_FORMULA_VERSION,
        "matched_baseline_formula_version": MATCHED_BASELINE_FORMULA_VERSION,
        "market_gate_rule_version": version_module._market_gate_contract_fingerprint(),
        "signal_confluence_rule_version": LIVERMORE_SIGNAL_CONFLUENCE_RULE_VERSION,
        "macro_formula_version": version_module._macro_formula_contract_fingerprint(),
        "candidate_source_version": "1" * 64,
        "execution_source_version": "2" * 64,
        "matched_baseline_source_version": "3" * 64,
        "macro_source_version": "4" * 64,
        "theme_overlay_fingerprint": "5" * 64,
        "choice_catalog_fingerprint": "6" * 64,
        "stock_candidate_selection_policy": EXP3B_STOCK_CANDIDATE_POLICY,
        "decision_metric_basis": ALLOWED_DECISION_METRIC_BASIS,
        "coverage_authority_mode": CURRENT_RULE_COVERAGE_AUTHORITY_MODE,
        "strict_coverage": True,
        "fallback_covered": False,
    }


def _source_receipt(
    db_path: Path,
    *,
    available_at: str = EVALUATION,
) -> dict[str, object]:
    return build_stock_analysis_source_availability_receipt(
        duckdb_path=db_path,
        table_whitelist={"stock_adjustment_factor": "trade_date"},
        captured_at=f"{available_at}T12:00:00Z",
    )


def _runner(
    trade_date: str,
    codes: list[str],
    *,
    status: str = module.SIGNAL_STATUS,
) -> dict[str, object]:
    accepted = list(codes) if status == module.SIGNAL_STATUS else []
    return {
        "trade_date": trade_date,
        "status": status,
        "status_reason": {
            module.SIGNAL_STATUS: "current_rule_candidates_present",
            module.ZERO_STATUS: "policy_active_zero_signal",
            module.POLICY_INACTIVE_STATUS: "selection_policy_inactive",
            module.UNSUPPORTED_STATUS: "stock_candidates_payload_missing",
            module.LOADER_ERROR_STATUS: "loader_exception",
        }[status],
        "requested_as_of_date": trade_date,
        "resolved_as_of_date": trade_date,
        "requested_matches_resolved": True,
        "selection_policy": EXP3B_STOCK_CANDIDATE_POLICY,
        "stock_candidate_formula_version": STOCK_CANDIDATE_FORMULA_VERSION,
        "rule_tuple_matches": True,
        "accepted_candidate_count": len(accepted),
        "accepted_candidate_codes": accepted,
        "future_business_date_violations": [],
        "future_availability_violations": [],
        "blockers": [],
    }


def _execution(*, pending_tail: bool = False) -> dict[str, object]:
    return {
        "entry_date": "2026-01-03",
        "exit_date_1d": "2026-01-03",
        "exit_date_5d": "2026-01-07",
        "exit_date_10d": None if pending_tail else "2026-01-12",
        "exit_date_20d": None if pending_tail else "2026-01-22",
        "data_status": "pending" if pending_tail else "complete",
    }


def _create_db(path: Path, rows: list[tuple[object, ...]]) -> None:
    conn = duckdb.connect(str(path))
    try:
        conn.execute(
            """
            create table stock_adjustment_factor (
              stock_code varchar,
              trade_date varchar,
              adj_factor double,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        if rows:
            conn.executemany(
                "insert into stock_adjustment_factor values (?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
    finally:
        conn.close()


def _rows(
    code: str = "000001.SZ",
    *,
    source_version: str = SOURCE_VERSION,
    run_id: str = RUN_ID,
) -> list[tuple[object, ...]]:
    return [
        (code, factor_date, 1.0, source_version, "", "", run_id)
        for factor_date in (
            "2026-01-02",
            "2026-01-03",
            "2026-01-07",
            "2026-01-12",
            "2026-01-22",
        )
    ]


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _build(
    monkeypatch: pytest.MonkeyPatch,
    db_path: Path,
    *,
    runners: list[dict[str, object]] | None = None,
    receipts: list[dict[str, object]] | None = None,
    execution_payload: dict[str, object] | None = None,
) -> dict[str, object]:
    monkeypatch.setattr(
        module.execution_task,
        "_execution_returns_for_candidate",
        lambda conn, *, stock_code, snapshot_as_of_date: (
            dict(execution_payload) if execution_payload is not None else _execution()
        ),
    )
    return module.build_stock_analysis_current_rule_factor_manifest(
        duckdb_path=db_path,
        evaluation_as_of_date=EVALUATION,
        governed_run_id="governed-run-1",
        runner_results=runners or [_runner("2026-01-02", ["000001.SZ"])],
        source_availability_receipts=(
            receipts if receipts is not None else [_source_receipt(db_path)]
        ),
        frozen_version_tuple=_version_tuple(),
        calendar_receipt_sha256=SHA_A,
        replay_plan_digest_version="stock-analysis-current-rule-replay-plan-v1",
        replay_plan_digest=SHA_B,
        created_at=CREATED_AT,
    )


def test_manifest_has_exact_six_roles_preserves_shared_physical_cell_and_db(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "ready.duckdb"
    _create_db(db_path, _rows())
    before = _file_sha(db_path)
    receipt = _source_receipt(db_path)

    manifest = _build(monkeypatch, db_path, receipts=[receipt])

    assert manifest["status"] == "ready"
    assert [cell["role"] for cell in manifest["candidate_cells"]] == list(module.CELL_ROLES)
    shared = [
        cell
        for cell in manifest["candidate_cells"]
        if cell["factor_date"] == "2026-01-03"
    ]
    assert [cell["role"] for cell in shared] == ["entry", "exit_1d"]
    assert manifest["missing_unique_cells"] == []
    assert manifest["summary"]["candidate_cell_count"] == 6
    assert manifest["database"]["sha256_before"] == before
    assert manifest["database"]["sha256_after"] == before
    assert manifest["source_availability_receipt_sha256s"] == [
        receipt["canonical_receipt_sha256"]
    ]
    valid, errors = module.validate_stock_analysis_current_rule_factor_manifest(manifest)
    assert valid, errors


def test_only_fresh_runner_accepted_candidates_are_used_not_history(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "runner-only.duckdb"
    _create_db(db_path, _rows("000002.SZ"))
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute("create table livermore_candidate_history (stock_code varchar)")
        conn.execute("insert into livermore_candidate_history values ('OLD999.SH')")
    finally:
        conn.close()
    calls: list[str] = []

    def fake_execution(conn, *, stock_code, snapshot_as_of_date):
        calls.append(stock_code)
        return _execution()

    monkeypatch.setattr(
        module.execution_task,
        "_execution_returns_for_candidate",
        fake_execution,
    )
    manifest = module.build_stock_analysis_current_rule_factor_manifest(
        duckdb_path=db_path,
        evaluation_as_of_date=EVALUATION,
        governed_run_id="run",
        runner_results=[_runner("2026-01-02", ["000002.SZ"])],
        source_availability_receipts=[_source_receipt(db_path)],
        frozen_version_tuple=_version_tuple(),
        calendar_receipt_sha256=SHA_A,
        replay_plan_digest_version="v1",
        replay_plan_digest=SHA_B,
        created_at=CREATED_AT,
    )
    assert calls == ["000002.SZ"]
    assert {cell["stock_code"] for cell in manifest["candidate_cells"]} == {"000002.SZ"}


def test_adjacent_factor_never_substitutes_for_missing_exact_date(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "no-carry.duckdb"
    rows = [row for row in _rows() if row[1] != "2026-01-07"]
    rows.append(("000001.SZ", "2026-01-08", 1.0, SOURCE_VERSION, "", "", RUN_ID))
    _create_db(db_path, rows)

    manifest = _build(monkeypatch, db_path)
    exit_5d = next(cell for cell in manifest["candidate_cells"] if cell["role"] == "exit_5d")
    assert manifest["status"] == "gaps_found"
    assert exit_5d["factor_date"] == "2026-01-07"
    assert exit_5d["status"] == "missing"
    assert manifest["carry_forward_allowed"] is False


def test_source_receipt_mismatch_is_present_but_unproven(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "unproven.duckdb"
    _create_db(db_path, _rows())
    receipt = _source_receipt(db_path)
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            "update stock_adjustment_factor set source_version = 'other-source'"
        )
    finally:
        conn.close()

    manifest = _build(monkeypatch, db_path, receipts=[receipt])
    assert manifest["status"] == "gaps_found"
    assert {cell["status"] for cell in manifest["candidate_cells"]} == {
        "present_source_unproven"
    }


def test_cells_bind_to_their_matching_receipt_and_validator_rejects_hash_tamper(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    early_dates = {"2026-01-02", "2026-01-03"}
    rows_a = [
        row
        for row in _rows(source_version="factor-source-a", run_id="factor-run-a")
        if row[1] in early_dates
    ]
    rows_b = [
        row
        for row in _rows(source_version="factor-source-b", run_id="factor-run-b")
        if row[1] not in early_dates
    ]
    receipt_a_db = tmp_path / "receipt-a.duckdb"
    receipt_b_db = tmp_path / "receipt-b.duckdb"
    target_db = tmp_path / "multi-receipt-target.duckdb"
    _create_db(receipt_a_db, rows_a)
    _create_db(receipt_b_db, rows_b)
    _create_db(target_db, rows_a + rows_b)
    receipt_a = _source_receipt(receipt_a_db)
    receipt_b = _source_receipt(receipt_b_db)

    manifest = _build(
        monkeypatch,
        target_db,
        receipts=[receipt_b, receipt_a],
    )

    assert manifest["status"] == "ready"
    expected_hash_by_role = {
        "signal": receipt_a["canonical_receipt_sha256"],
        "entry": receipt_a["canonical_receipt_sha256"],
        "exit_1d": receipt_a["canonical_receipt_sha256"],
        "exit_5d": receipt_b["canonical_receipt_sha256"],
        "exit_10d": receipt_b["canonical_receipt_sha256"],
        "exit_20d": receipt_b["canonical_receipt_sha256"],
    }
    assert {
        cell["role"]: cell["source_receipt_sha256"]
        for cell in manifest["candidate_cells"]
    } == expected_hash_by_role
    assert manifest["source_availability_receipt_sha256s"] == sorted(
        [receipt_a["canonical_receipt_sha256"], receipt_b["canonical_receipt_sha256"]]
    )

    tampered = copy.deepcopy(manifest)
    tampered["candidate_cells"][0]["source_receipt_sha256"] = "F" * 64
    tampered["canonical_manifest_sha256"] = module._canonical_sha256(tampered)
    valid, errors = module.validate_stock_analysis_current_rule_factor_manifest(tampered)
    assert valid is False
    assert any("source receipt hash is not bound" in error for error in errors)


def test_validator_rejects_usable_cell_with_future_availability_even_when_resealed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "usable-future-tamper.duckdb"
    _create_db(db_path, _rows())
    manifest = _build(monkeypatch, db_path)
    tampered = copy.deepcopy(manifest)
    tampered["candidate_cells"][0]["available_at"] = "2026-02-01"
    tampered["canonical_manifest_sha256"] = module._canonical_sha256(tampered)

    valid, errors = module.validate_stock_analysis_current_rule_factor_manifest(tampered)

    assert valid is False
    assert any("usable availability is after evaluation" in error for error in errors)


def test_conflicting_exact_cell_is_ambiguous(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "ambiguous.duckdb"
    rows = _rows()
    rows.append(("000001.SZ", "2026-01-02", 2.0, SOURCE_VERSION, "", "", RUN_ID))
    _create_db(db_path, rows)

    manifest = _build(monkeypatch, db_path)
    signal = next(cell for cell in manifest["candidate_cells"] if cell["role"] == "signal")
    assert signal["status"] == "ambiguous"
    assert signal["observed_row_count"] == 2
    assert signal["distinct_observation_count"] == 2


def test_unmatured_tail_dates_remain_null_without_fake_missing_cells(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "pending.duckdb"
    _create_db(db_path, _rows())

    manifest = _build(monkeypatch, db_path, execution_payload=_execution(pending_tail=True))
    tail = {
        cell["role"]: cell
        for cell in manifest["candidate_cells"]
        if cell["role"] in {"exit_10d", "exit_20d"}
    }
    assert {cell["status"] for cell in tail.values()} == {"date_unresolved"}
    assert all(cell["factor_date"] is None for cell in tail.values())
    assert manifest["status"] == "ready"
    assert manifest["summary"]["gap_cell_count"] == 0
    assert manifest["summary"]["unresolved_cell_count"] == 2
    assert {item["trade_date"] for item in manifest["missing_unique_cells"]}.isdisjoint(
        {"None", None}
    )
    valid, errors = module.validate_stock_analysis_current_rule_factor_manifest(manifest)
    assert valid, errors


def test_malformed_execution_role_date_blocks_with_candidate_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "malformed-role-date.duckdb"
    _create_db(db_path, _rows())
    execution = _execution()
    execution["exit_date_5d"] = "not-an-iso-date"

    manifest = _build(monkeypatch, db_path, execution_payload=execution)

    assert manifest["status"] == "blocked"
    assert manifest["candidate_cells"] == []
    assert manifest["blockers"] == [
        "execution_role_date_invalid:2026-01-02:000001.SZ:exit_5d"
    ]


def test_missing_physical_cell_is_deduplicated_across_entry_and_exit_1d_roles(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "dedupe.duckdb"
    _create_db(db_path, [row for row in _rows() if row[1] != "2026-01-03"])

    manifest = _build(monkeypatch, db_path)
    missing = [
        item
        for item in manifest["missing_unique_cells"]
        if item["trade_date"] == "2026-01-03"
    ]
    assert len(missing) == 1
    assert missing[0]["occurrence_count"] == 2
    assert [ref["role"] for ref in missing[0]["candidate_references"]] == [
        "entry",
        "exit_1d",
    ]


def test_hash_is_stable_for_runner_and_candidate_order(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "stable.duckdb"
    _create_db(db_path, _rows("000001.SZ") + _rows("000002.SZ"))
    runner_a = _runner("2026-01-02", ["000002.SZ", "000001.SZ"])
    runner_b = _runner("2026-01-05", [], status=module.ZERO_STATUS)

    first = _build(monkeypatch, db_path, runners=[runner_b, runner_a])
    second = _build(
        monkeypatch,
        db_path,
        runners=[runner_a | {"accepted_candidate_codes": list(reversed(runner_a["accepted_candidate_codes"]))}, runner_b],
    )
    assert first["canonical_manifest_sha256"] == second["canonical_manifest_sha256"]


def test_zero_and_policy_inactive_dates_disclose_without_cells_or_certification(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "disclosure.duckdb"
    _create_db(db_path, _rows())
    inactive_runner = _runner(
        "2026-01-03", [], status=module.POLICY_INACTIVE_STATUS
    )
    inactive_runner.update(
        {
            "rule_tuple_matches": None,
            "selection_policy": None,
            "stock_candidate_formula_version": None,
        }
    )
    runners = [
        _runner("2026-01-02", [], status=module.ZERO_STATUS),
        inactive_runner,
    ]

    manifest = _build(monkeypatch, db_path, runners=runners)
    assert manifest["status"] == "ready"
    assert manifest["candidate_cells"] == []
    assert manifest["summary"]["zero_signal_date_count"] == 1
    assert manifest["summary"]["policy_inactive_date_count"] == 1
    assert manifest["certification_allowed"] is False


def test_policy_inactive_runner_with_candidates_still_blocks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "inactive-with-candidate.duckdb"
    _create_db(db_path, _rows())
    runner = _runner("2026-01-03", [], status=module.POLICY_INACTIVE_STATUS)
    runner.update(
        {
            "rule_tuple_matches": None,
            "selection_policy": None,
            "stock_candidate_formula_version": None,
            "accepted_candidate_count": 1,
            "accepted_candidate_codes": ["000001.SZ"],
        }
    )

    manifest = _build(monkeypatch, db_path, runners=[runner])

    assert manifest["status"] == "blocked"
    assert manifest["candidate_cells"] == []
    assert any(
        blocker == "runner_non_signal_candidates_present:2026-01-03"
        for blocker in manifest["blockers"]
    )


@pytest.mark.parametrize("status", [module.UNSUPPORTED_STATUS, module.LOADER_ERROR_STATUS])
def test_unsupported_or_loader_runner_blocks_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    status: str,
) -> None:
    db_path = tmp_path / f"{status}.duckdb"
    _create_db(db_path, _rows())

    manifest = _build(monkeypatch, db_path, runners=[_runner("2026-01-02", [], status=status)])
    assert manifest["status"] == "blocked"
    assert any("runner_status_blocked" in blocker for blocker in manifest["blockers"])
    assert manifest["candidate_cells"] == []


def test_real_future_violation_blocks_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "future.duckdb"
    _create_db(db_path, _rows())
    runner = _runner("2026-01-02", ["000001.SZ"])
    runner["future_business_date_violations"] = [
        {"path": "payload.future_date", "key": "trade_date", "value": "2026-02-01"}
    ]

    manifest = _build(monkeypatch, db_path, runners=[runner])
    assert manifest["status"] == "blocked"
    assert manifest["candidate_cells"] == []


def test_tampered_formal_source_receipt_fails_closed_before_factor_scan(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "tampered-receipt.duckdb"
    _create_db(db_path, _rows())
    receipt = _source_receipt(db_path)
    receipt["sources"][0]["run_id"] = "tampered-run"

    manifest = _build(monkeypatch, db_path, receipts=[receipt])

    assert manifest["status"] == "blocked"
    assert manifest["candidate_cells"] == []
    assert any(
        "failed formal validation" in blocker
        and "canonical_receipt_sha256 mismatch" in blocker
        for blocker in manifest["blockers"]
    )


def test_validator_rejects_tampered_self_hash(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "tamper.duckdb"
    _create_db(db_path, _rows())
    manifest = _build(monkeypatch, db_path)
    tampered = copy.deepcopy(manifest)
    tampered["candidate_cells"][0]["adj_factor"] = 9.0

    valid, errors = module.validate_stock_analysis_current_rule_factor_manifest(tampered)
    assert valid is False
    assert "manifest.canonical_manifest_sha256 mismatch" in errors
