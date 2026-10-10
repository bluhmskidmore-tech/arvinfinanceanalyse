from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from statistics import mean
from types import SimpleNamespace

import duckdb
import pytest

from backend.app.tasks import stock_analysis_current_rule_cohort_evidence as module

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]

OBS_SOURCE_VERSION = "sv-obs"
OBS_VENDOR_VERSION = "vv-choice"
OBS_RULE_VERSION = "rv-obs"
OBS_RUN_ID = "run-obs"
FACTOR_SOURCE_VERSION = "sv-factor"
FACTOR_VENDOR_VERSION = "vv-choice"
FACTOR_RULE_VERSION = "rv-factor"
FACTOR_RUN_ID = "run-factor"


def _ready_readiness() -> SimpleNamespace:
    payload = {
        "ready": True,
        "status": "ready",
        "catalog_path": "catalog.json",
        "message": "ready",
    }
    return SimpleNamespace(
        ready=True,
        status="ready",
        model_dump=lambda mode="json": dict(payload),
    )


def _source_receipt() -> dict[str, object]:
    return {
        "schema_version": 1,
        "receipt_kind": "pit_source_availability_v1",
        "captured_at": "2026-01-31T12:00:00+08:00",
        "sources": [
            {
                "table": "choice_stock_daily_observation",
                "source_version": OBS_SOURCE_VERSION,
                "vendor_version": OBS_VENDOR_VERSION,
                "rule_version": OBS_RULE_VERSION,
                "run_id": OBS_RUN_ID,
                "available_at": "2026-01-31",
            },
            {
                "table": "stock_adjustment_factor",
                "source_version": FACTOR_SOURCE_VERSION,
                "vendor_version": FACTOR_VENDOR_VERSION,
                "rule_version": FACTOR_RULE_VERSION,
                "run_id": FACTOR_RUN_ID,
                "available_at": "2026-01-31",
            },
        ],
    }


def _version_tuple() -> dict[str, object]:
    return {
        "candidate_rule_version": "rv_candidate_history_current",
        "stock_candidate_selection_formula_version": "rv_livermore_stock_candidates_bundle_v7",
        "candidate_outcome_formula_version": "fv_livermore_candidate_forward_close_dual_adjust_v2",
        "execution_formula_version": "fv_livermore_candidate_execution_dual_adjust_v5",
        "matched_baseline_formula_version": "fv_livermore_matched_baseline_v4",
        "market_gate_rule_version": "rv_market_gate_current_v2",
        "signal_confluence_rule_version": "rv_signal_confluence_current_v4",
        "macro_formula_version": "fv_macro_bundle_current_v1",
        "candidate_source_version": "sv_candidate_current",
        "execution_source_version": "sv_execution_current",
        "matched_baseline_source_version": "sv_matched_baseline_current",
        "macro_source_version": "sv_macro_current",
        "theme_overlay_fingerprint": "theme-overlay-v1",
        "choice_catalog_fingerprint": "catalog-v1",
        "stock_candidate_selection_policy": "exp3b",
        "decision_metric_basis": "net_next_open_adj",
        "coverage_authority_mode": module.CURRENT_RULE_COVERAGE_AUTHORITY_MODE,
        "strict_coverage": True,
        "fallback_covered": False,
    }


def _runner_result(
    *,
    trade_date: str,
    candidate_codes: list[str],
    status: str = module.SIGNAL_STATUS,
) -> dict[str, object]:
    count = len(candidate_codes)
    return {
        "trade_date": trade_date,
        "status": status,
        "status_reason": (
            "current_rule_candidates_present"
            if status == module.SIGNAL_STATUS
            else "policy_active_zero_signal"
        ),
        "requested_as_of_date": trade_date,
        "resolved_as_of_date": trade_date,
        "requested_matches_resolved": True,
        "market_state": "WARM",
        "selection_policy": "exp3b",
        "stock_candidate_formula_version": "rv_livermore_stock_candidates_bundle_v7",
        "rule_tuple_matches": True,
        "candidate_count": count,
        "candidate_item_count": count,
        "accepted_candidate_count": count,
        "candidate_count_matches_items": True,
        "candidate_codes": list(candidate_codes),
        "accepted_candidate_codes": list(candidate_codes),
        "unique_candidate_codes": list(candidate_codes),
        "duplicate_candidate_codes": [],
        "stock_candidate_block_reason": None,
        "future_business_date_violations": [],
        "future_availability_violations": [],
        "blockers": [],
    }


def _selection_payload(*, trade_date: str, candidate_codes: list[str]) -> tuple[dict[str, object], dict[str, object]]:
    items = [
        {
            "stock_code": code,
            "stock_name": code,
            "rank": index + 1,
            "sector_code": "801001",
            "sector_name": "Bank",
            "selection_policy": "exp3b",
            "ema10": 10.0 + index,
            "ma20": 10.0 + index,
            "ma60": 10.0 + index,
            "ma120": 10.0 + index,
            "close_strength": 0.8,
            "closed_up_limit": False,
            "abnormal_turnover": 1.1,
            "gap_norm": 0.1,
            "breakout_extension_norm": 0.1,
            "breakout_level": 10.0,
        }
        for index, code in enumerate(candidate_codes)
    ]
    return (
        {
            "requested_as_of_date": trade_date,
            "as_of_date": trade_date,
            "market_gate": {"state": "WARM", "exposure": 0.5},
            "stock_candidates": {
                "selection_policy": "exp3b",
                "formula_version": "rv_livermore_stock_candidates_bundle_v7",
                "candidate_count": len(items),
                "insufficient_history_count": 0,
                "input_stock_count": 100,
                "excluded_stock_count": 0,
                "items": items,
            },
            "unsupported_outputs": [],
        },
        {
            "quality_flag": "ok",
            "vendor_status": "ok",
            "fallback_mode": "none",
            "source_version": "sv-selection",
            "vendor_version": "vv-selection",
            "tables_used": ["choice_stock_daily_observation"],
            "evidence_rows": len(items),
        },
    )


def _create_read_only_db(path: Path, *, total_days: int = 45) -> None:
    conn = duckdb.connect(str(path))
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              open_value double,
              close_value double,
              highlimit double,
              lowlimit double,
              tradestatus varchar,
              amount double,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_universe (
              as_of_date varchar,
              stock_code varchar,
              stock_name varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_sector_membership (
              as_of_date varchar,
              stock_code varchar,
              sw2021code varchar,
              sw2021 varchar
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
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        start = date(2026, 1, 1)
        stocks = [f"{index:06d}.SZ" for index in range(1, 22)]
        observation_rows: list[tuple[object, ...]] = []
        factor_rows: list[tuple[object, ...]] = []
        universe_rows: list[tuple[object, ...]] = []
        sector_rows: list[tuple[object, ...]] = []
        for day_offset in range(total_days):
            trade_date = (start + timedelta(days=day_offset)).isoformat()
            for stock_index, stock_code in enumerate(stocks):
                open_price = 10.0 + stock_index * 0.1 + day_offset * 0.01
                close_price = open_price + 0.05
                observation_rows.append(
                    (
                        trade_date,
                        stock_code,
                        open_price,
                        close_price,
                        open_price * 1.10,
                        open_price * 0.90,
                        "交易",
                        1_000_000.0 + stock_index * 1_000.0,
                        OBS_SOURCE_VERSION,
                        OBS_VENDOR_VERSION,
                        OBS_RULE_VERSION,
                        OBS_RUN_ID,
                    )
                )
                factor_rows.append(
                    (
                        stock_code,
                        trade_date,
                        1.0,
                        FACTOR_SOURCE_VERSION,
                        FACTOR_VENDOR_VERSION,
                        FACTOR_RULE_VERSION,
                        FACTOR_RUN_ID,
                    )
                )
                universe_rows.append((trade_date, stock_code, stock_code))
                sector_rows.append((trade_date, stock_code, "801001", "Bank"))
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            observation_rows,
        )
        conn.executemany(
            "insert into stock_adjustment_factor values (?, ?, ?, ?, ?, ?, ?)",
            factor_rows,
        )
        conn.executemany(
            "insert into choice_stock_universe values (?, ?, ?)",
            universe_rows,
        )
        conn.executemany(
            "insert into choice_stock_sector_membership values (?, ?, ?, ?)",
            sector_rows,
        )
    finally:
        conn.close()


def test_collect_rebuilds_fact_and_matched_alpha_before_go_live_thresholds(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "ready.duckdb"
    _create_read_only_db(db_path)
    loader_calls: list[dict[str, object]] = []

    def fake_loader(*, duckdb_path: str, as_of_date, **kwargs):
        loader_calls.append(
            {
                "duckdb_path": duckdb_path,
                "as_of_date": as_of_date.isoformat(),
                **kwargs,
            }
        )
        return _selection_payload(trade_date=as_of_date.isoformat(), candidate_codes=["000001.SZ"])

    monkeypatch.setattr(module, "load_livermore_strategy_payload", fake_loader)

    result = module.collect_stock_analysis_current_rule_cohort_evidence(
        duckdb_path=db_path,
        evaluation_as_of_date="2026-01-31",
        governed_run_id="governed-run-1",
        runner_results=[_runner_result(trade_date="2026-01-02", candidate_codes=["000001.SZ"])],
        source_availability_receipts=[_source_receipt()],
        frozen_version_tuple=_version_tuple(),
        choice_stock_readiness=_ready_readiness(),
    )

    assert result["status"] == "blocked"
    assert "completed_dates_below_threshold" in result["blockers"]
    assert "matched_entry_count_below_threshold" in result["blockers"]
    assert len(result["facts"]) == 1
    fact = result["facts"][0]
    controls = fact["control_pit_proof"]["controls"]
    assert len(controls) == 20
    assert len({row["control_stock_code"] for row in controls}) == 20
    expected_alpha_5d = fact["return_5d_net_adj"] - mean(
        row["control_return_5d_net_adj"] for row in controls
    )
    expected_alpha_20d = fact["return_20d_net_adj"] - mean(
        row["control_return_20d_net_adj"] for row in controls
    )
    assert fact["matched_alpha_5d"] == expected_alpha_5d
    assert fact["matched_alpha_20d"] == expected_alpha_20d
    assert result["date_certificates"][0]["matched_entry_count"] == 1
    assert result["counts"]["completed_dates"] == 1
    assert result["counts"]["matched_entry_count"] == 1
    assert len(loader_calls) == 1
    assert loader_calls[0]["duckdb_path"] == str(db_path.resolve())
    assert loader_calls[0]["as_of_date"] == "2026-01-02"
    assert loader_calls[0]["backfill_mode"] is True
    assert loader_calls[0]["stock_candidate_policy"] == "exp3b"
    assert loader_calls[0]["theme_overlay_reader"] is None
    assert getattr(loader_calls[0]["stock_readiness"], "ready", None) is True


def test_collect_zero_signal_day_keeps_validated_runner_without_loader_call(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "zero.duckdb"
    _create_read_only_db(db_path)
    monkeypatch.setattr(
        module,
        "load_livermore_strategy_payload",
        lambda **kwargs: pytest.fail("signal loader must not run for zero-signal dates"),
    )

    result = module.collect_stock_analysis_current_rule_cohort_evidence(
        duckdb_path=db_path,
        evaluation_as_of_date="2026-01-31",
        governed_run_id="governed-run-1",
        runner_results=[
            _runner_result(
                trade_date="2026-01-03",
                candidate_codes=[],
                status=module.ZERO_STATUS,
            )
        ],
        source_availability_receipts=[_source_receipt()],
        frozen_version_tuple=_version_tuple(),
        choice_stock_readiness=_ready_readiness(),
    )

    assert result["status"] == "blocked"
    assert result["facts"] == []
    assert result["counts"]["completed_no_signal_dates"] == 1
    assert result["zero_signal_runner_results"]["2026-01-03"]["status"] == module.ZERO_STATUS
    assert result["date_certificates"][0]["certificate_status"] == module.CURRENT_RULE_ZERO_SIGNAL_CERTIFICATE_STATUS
    assert "completed_dates_below_threshold" in result["blockers"]
    assert "matched_entry_count_below_threshold" in result["blockers"]


def test_collect_blocks_future_execution_even_when_runner_is_clean(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "future.duckdb"
    _create_read_only_db(db_path)
    monkeypatch.setattr(
        module,
        "load_livermore_strategy_payload",
        lambda **kwargs: _selection_payload(
            trade_date=kwargs["as_of_date"].isoformat(),
            candidate_codes=["000001.SZ"],
        ),
    )
    receipt = _source_receipt()
    receipt["sources"][0]["available_at"] = "2026-01-12"
    receipt["sources"][1]["available_at"] = "2026-01-12"

    result = module.collect_stock_analysis_current_rule_cohort_evidence(
        duckdb_path=db_path,
        evaluation_as_of_date="2026-01-12",
        governed_run_id="governed-run-1",
        runner_results=[_runner_result(trade_date="2026-01-02", candidate_codes=["000001.SZ"])],
        source_availability_receipts=[receipt],
        frozen_version_tuple=_version_tuple(),
        choice_stock_readiness=_ready_readiness(),
    )

    assert result["status"] == "blocked"
    assert any("candidate_execution_after_evaluation" in blocker for blocker in result["blockers"])


def test_collect_blocks_with_sanitized_loader_error_detail(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "loader_error.duckdb"
    _create_read_only_db(db_path)

    def fake_loader(**kwargs):
        raise ValueError(
            "bad source receipt\n"
            "F:\\secret\\tokens.json "
            "/var/tmp/private-key.pem "
            + ("x" * 400)
        )

    monkeypatch.setattr(module, "load_livermore_strategy_payload", fake_loader)

    result = module.collect_stock_analysis_current_rule_cohort_evidence(
        duckdb_path=db_path,
        evaluation_as_of_date="2026-01-31",
        governed_run_id="governed-run-1",
        runner_results=[_runner_result(trade_date="2026-01-02", candidate_codes=["000001.SZ"])],
        source_availability_receipts=[_source_receipt()],
        frozen_version_tuple=_version_tuple(),
        choice_stock_readiness=_ready_readiness(),
    )

    assert result["status"] == "blocked"
    blocker = next(
        value
        for value in result["blockers"]
        if value.startswith("selection_loader_error:ValueError:")
    )
    assert "bad source receipt" in blocker
    assert "<path>" in blocker
    assert "F:\\secret\\tokens.json" not in blocker
    assert "/var/tmp/private-key.pem" not in blocker
    assert "\n" not in blocker
    assert "\r" not in blocker
    assert len(blocker) <= len("selection_loader_error:ValueError:") + module.LOADER_ERROR_MESSAGE_MAX_CHARS


def test_collect_blocks_when_completed_dates_and_matches_stay_at_19_and_99(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "narrow.duckdb"
    _create_read_only_db(db_path)
    source_receipt = _source_receipt()
    source_hash = hashlib.sha256(
        json.dumps(
            source_receipt,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest().upper()
    version_tuple = _version_tuple()
    runner_results: list[dict[str, object]] = []
    per_date_counts = [5] * 18 + [9]
    start = date(2026, 1, 2)
    for index, candidate_count in enumerate(per_date_counts):
        trade_date = (start + timedelta(days=index)).isoformat()
        runner_results.append(
            _runner_result(
                trade_date=trade_date,
                candidate_codes=[f"{position + 1:06d}.SZ" for position in range(candidate_count)],
            )
        )

    def fake_collect(**kwargs):
        runner_result = kwargs["runner_result"]
        trade_date = runner_result["trade_date"]
        candidate_count = int(runner_result["accepted_candidate_count"])
        facts = [
            {
                "signal_date": trade_date,
                "stock_code": f"{index + 1:06d}.SZ",
                "signal_kind": "stock_candidate",
            }
            for index in range(candidate_count)
        ]
        return {
            "facts": facts,
            "date_certificate": module._signal_date_certificate_row(
                trade_date=trade_date,
                fact_count=candidate_count,
                source_hashes=(source_hash,),
                version_tuple=version_tuple,
            ),
            "blockers": [],
        }

    monkeypatch.setattr(module, "_collect_signal_date_evidence", fake_collect)

    result = module.collect_stock_analysis_current_rule_cohort_evidence(
        duckdb_path=db_path,
        evaluation_as_of_date="2026-02-28",
        governed_run_id="governed-run-1",
        runner_results=runner_results,
        source_availability_receipts=[source_receipt],
        frozen_version_tuple=version_tuple,
        choice_stock_readiness=_ready_readiness(),
    )

    assert result["status"] == "blocked"
    assert result["counts"]["completed_dates"] == 19
    assert result["counts"]["matched_entry_count"] == 99
    assert "completed_dates_below_threshold" in result["blockers"]
    assert "matched_entry_count_below_threshold" in result["blockers"]


def test_collect_blocks_when_control_source_leaf_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "leaf.duckdb"
    _create_read_only_db(db_path)
    monkeypatch.setattr(
        module,
        "load_livermore_strategy_payload",
        lambda **kwargs: _selection_payload(
            trade_date=kwargs["as_of_date"].isoformat(),
            candidate_codes=["000001.SZ"],
        ),
    )
    original = module.generate_matched_baseline_pit_proof_rows

    def fake_generate(*args, **kwargs):
        rows = original(*args, **kwargs)
        del rows[0]["source_evidence"]["adjustment_factor"]["exit_20d"]
        return rows

    monkeypatch.setattr(module, "generate_matched_baseline_pit_proof_rows", fake_generate)

    result = module.collect_stock_analysis_current_rule_cohort_evidence(
        duckdb_path=db_path,
        evaluation_as_of_date="2026-01-31",
        governed_run_id="governed-run-1",
        runner_results=[_runner_result(trade_date="2026-01-02", candidate_codes=["000001.SZ"])],
        source_availability_receipts=[_source_receipt()],
        frozen_version_tuple=_version_tuple(),
        choice_stock_readiness=_ready_readiness(),
    )

    assert result["status"] == "blocked"
    assert any("control_source_leaf_missing" in blocker for blocker in result["blockers"])


def test_collect_blocks_when_control_source_tuple_drifts_from_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "mismatch.duckdb"
    _create_read_only_db(db_path)
    monkeypatch.setattr(
        module,
        "load_livermore_strategy_payload",
        lambda **kwargs: _selection_payload(
            trade_date=kwargs["as_of_date"].isoformat(),
            candidate_codes=["000001.SZ"],
        ),
    )
    original = module.generate_matched_baseline_pit_proof_rows

    def fake_generate(*args, **kwargs):
        rows = original(*args, **kwargs)
        rows[0]["source_evidence"]["observation"]["entry"]["run_id"] = "wrong-run"
        return rows

    monkeypatch.setattr(module, "generate_matched_baseline_pit_proof_rows", fake_generate)

    result = module.collect_stock_analysis_current_rule_cohort_evidence(
        duckdb_path=db_path,
        evaluation_as_of_date="2026-01-31",
        governed_run_id="governed-run-1",
        runner_results=[_runner_result(trade_date="2026-01-02", candidate_codes=["000001.SZ"])],
        source_availability_receipts=[_source_receipt()],
        frozen_version_tuple=_version_tuple(),
        choice_stock_readiness=_ready_readiness(),
    )

    assert result["status"] == "blocked"
    assert any("control_source_receipt_mismatch" in blocker for blocker in result["blockers"])


def test_collect_accepts_missing_optional_vendor_and_rule_source_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "optional-source-fields.duckdb"
    _create_read_only_db(db_path)
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute("alter table stock_adjustment_factor drop column vendor_version")
        conn.execute("alter table stock_adjustment_factor drop column rule_version")
    finally:
        conn.close()
    monkeypatch.setattr(
        module,
        "load_livermore_strategy_payload",
        lambda **kwargs: _selection_payload(
            trade_date=kwargs["as_of_date"].isoformat(),
            candidate_codes=["000001.SZ"],
        ),
    )
    receipt = _source_receipt()
    factor_source = receipt["sources"][1]
    factor_source.pop("vendor_version")
    factor_source.pop("rule_version")

    result = module.collect_stock_analysis_current_rule_cohort_evidence(
        duckdb_path=db_path,
        evaluation_as_of_date="2026-01-31",
        governed_run_id="governed-run-1",
        runner_results=[
            _runner_result(
                trade_date="2026-01-02",
                candidate_codes=["000001.SZ"],
            )
        ],
        source_availability_receipts=[receipt],
        frozen_version_tuple=_version_tuple(),
        choice_stock_readiness=_ready_readiness(),
    )

    assert len(result["facts"]) == 1
    assert not any(
        "control_source_metadata_missing" in blocker
        or "control_source_receipt_mismatch" in blocker
        for blocker in result["blockers"]
    )
    factor_evidence = result["facts"][0]["candidate_source_evidence"][
        "adjustment_factor"
    ]
    for leaf_name in ("entry", "exit_5d", "exit_20d"):
        assert factor_evidence[leaf_name]["vendor_version"] is None
        assert factor_evidence[leaf_name]["rule_version"] is None
        assert factor_evidence[leaf_name]["availability_status"] == "available"


def test_collect_is_deterministic_and_opens_duckdb_read_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "deterministic.duckdb"
    _create_read_only_db(db_path)
    monkeypatch.setattr(
        module,
        "load_livermore_strategy_payload",
        lambda **kwargs: _selection_payload(
            trade_date=kwargs["as_of_date"].isoformat(),
            candidate_codes=["000001.SZ"],
        ),
    )
    original_connect = module.duckdb.connect
    connect_calls: list[dict[str, object]] = []

    def wrapped_connect(*args, **kwargs):
        connect_calls.append(dict(kwargs))
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(module.duckdb, "connect", wrapped_connect)

    first = module.collect_stock_analysis_current_rule_cohort_evidence(
        duckdb_path=db_path,
        evaluation_as_of_date="2026-01-31",
        governed_run_id="governed-run-1",
        runner_results=[_runner_result(trade_date="2026-01-02", candidate_codes=["000001.SZ"])],
        source_availability_receipts=[_source_receipt()],
        frozen_version_tuple=_version_tuple(),
        choice_stock_readiness=_ready_readiness(),
    )
    second = module.collect_stock_analysis_current_rule_cohort_evidence(
        duckdb_path=db_path,
        evaluation_as_of_date="2026-01-31",
        governed_run_id="governed-run-1",
        runner_results=[_runner_result(trade_date="2026-01-02", candidate_codes=["000001.SZ"])],
        source_availability_receipts=[_source_receipt()],
        frozen_version_tuple=_version_tuple(),
        choice_stock_readiness=_ready_readiness(),
    )

    assert first == second
    assert connect_calls
    assert all(call.get("read_only") is True for call in connect_calls)


def test_collect_becomes_ready_once_twenty_dates_and_hundred_matches_are_present(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "ready-threshold.duckdb"
    _create_read_only_db(db_path)
    source_receipt = _source_receipt()
    source_hash = hashlib.sha256(
        json.dumps(
            source_receipt,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest().upper()
    version_tuple = _version_tuple()
    runner_results: list[dict[str, object]] = []
    start = date(2026, 1, 2)
    for index in range(20):
        trade_date = (start + timedelta(days=index)).isoformat()
        runner_results.append(
            _runner_result(
                trade_date=trade_date,
                candidate_codes=[f"{position + 1:06d}.SZ" for position in range(5)],
            )
        )

    def fake_collect(**kwargs):
        runner_result = kwargs["runner_result"]
        trade_date = runner_result["trade_date"]
        candidate_count = int(runner_result["accepted_candidate_count"])
        facts = [
            {
                "signal_date": trade_date,
                "stock_code": f"{index + 1:06d}.SZ",
                "signal_kind": "stock_candidate",
            }
            for index in range(candidate_count)
        ]
        return {
            "facts": facts,
            "date_certificate": module._signal_date_certificate_row(
                trade_date=trade_date,
                fact_count=candidate_count,
                source_hashes=(source_hash,),
                version_tuple=version_tuple,
            ),
            "blockers": [],
        }

    monkeypatch.setattr(module, "_collect_signal_date_evidence", fake_collect)

    result = module.collect_stock_analysis_current_rule_cohort_evidence(
        duckdb_path=db_path,
        evaluation_as_of_date="2026-02-28",
        governed_run_id="governed-run-1",
        runner_results=runner_results,
        source_availability_receipts=[source_receipt],
        frozen_version_tuple=version_tuple,
        choice_stock_readiness=_ready_readiness(),
    )

    assert result["status"] == "ready"
    assert result["counts"]["completed_dates"] == 20
    assert result["counts"]["matched_entry_count"] == 100


def test_collect_outputs_signal_fact_shape_compatible_with_producer_contract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "producer-shape.duckdb"
    _create_read_only_db(db_path)
    monkeypatch.setattr(
        module,
        "load_livermore_strategy_payload",
        lambda **kwargs: _selection_payload(
            trade_date=kwargs["as_of_date"].isoformat(),
            candidate_codes=["000001.SZ"],
        ),
    )

    result = module.collect_stock_analysis_current_rule_cohort_evidence(
        duckdb_path=db_path,
        evaluation_as_of_date="2026-01-31",
        governed_run_id="governed-run-1",
        runner_results=[_runner_result(trade_date="2026-01-02", candidate_codes=["000001.SZ"])],
        source_availability_receipts=[_source_receipt()],
        frozen_version_tuple=_version_tuple(),
        choice_stock_readiness=_ready_readiness(),
    )

    fact = result["facts"][0]
    candidate_source_evidence = fact["candidate_source_evidence"]
    assert set(candidate_source_evidence) == {"observation", "adjustment_factor", "limit_price"}
    for group_name in ("observation", "adjustment_factor"):
        group = candidate_source_evidence[group_name]
        assert group["table"]
        assert set(group).issuperset({"entry", "exit_5d", "exit_20d"})
        for leaf_name in ("entry", "exit_5d", "exit_20d"):
            leaf = group[leaf_name]
            assert leaf["availability_status"] == "available"
            assert leaf["available_at"] == "2026-01-31"
            assert leaf["source_version"]
            assert leaf["run_id"]
    assert "candidate_pit_evidence" not in fact
    assert fact["evidence"]["candidate_pit_summary"]["entry"]["usable"] is True


def test_collect_blocks_duplicate_runner_candidates_before_fact_assembly(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "duplicate.duckdb"
    _create_read_only_db(db_path)
    monkeypatch.setattr(
        module,
        "load_livermore_strategy_payload",
        lambda **kwargs: _selection_payload(
            trade_date=kwargs["as_of_date"].isoformat(),
            candidate_codes=["000001.SZ", "000001.SZ"],
        ),
    )
    runner = _runner_result(
        trade_date="2026-01-02",
        candidate_codes=["000001.SZ", "000001.SZ"],
    )
    runner["unique_candidate_codes"] = ["000001.SZ"]
    runner["duplicate_candidate_codes"] = ["000001.SZ"]

    result = module.collect_stock_analysis_current_rule_cohort_evidence(
        duckdb_path=db_path,
        evaluation_as_of_date="2026-01-31",
        governed_run_id="governed-run-1",
        runner_results=[runner],
        source_availability_receipts=[_source_receipt()],
        frozen_version_tuple=_version_tuple(),
        choice_stock_readiness=_ready_readiness(),
    )

    assert result["status"] == "blocked"
    assert any("runner_duplicate_candidate_codes_present" in blocker for blocker in result["blockers"])


def test_runner_candidate_keys_accept_sorted_unique_codes_for_ranked_candidates() -> None:
    runner = _runner_result(
        trade_date="2026-01-02",
        candidate_codes=["000002.SZ", "000001.SZ"],
    )
    runner["unique_candidate_codes"] = ["000001.SZ", "000002.SZ"]

    blockers = module._runner_candidate_key_blockers(
        runner_result=runner,
        trade_date="2026-01-02",
    )

    assert "runner_candidate_vs_accepted_codes_mismatch" not in blockers
    assert "runner_candidate_vs_unique_codes_mismatch" not in blockers


def test_runner_candidate_keys_block_different_unique_code_set() -> None:
    runner = _runner_result(
        trade_date="2026-01-02",
        candidate_codes=["000002.SZ", "000001.SZ"],
    )
    runner["unique_candidate_codes"] = ["000001.SZ", "000003.SZ"]

    blockers = module._runner_candidate_key_blockers(
        runner_result=runner,
        trade_date="2026-01-02",
    )

    assert "runner_candidate_vs_unique_codes_mismatch" in blockers


def test_collect_blocks_late_adjustment_availability_at_input_validation(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "late-adjustment.duckdb"
    _create_read_only_db(db_path)
    receipt = _source_receipt()
    receipt["sources"][1]["available_at"] = "2026-02-01"

    result = module.collect_stock_analysis_current_rule_cohort_evidence(
        duckdb_path=db_path,
        evaluation_as_of_date="2026-01-31",
        governed_run_id="governed-run-1",
        runner_results=[_runner_result(trade_date="2026-01-02", candidate_codes=["000001.SZ"])],
        source_availability_receipts=[receipt],
        frozen_version_tuple=_version_tuple(),
        choice_stock_readiness=_ready_readiness(),
    )

    assert result["status"] == "blocked"
    assert any("input_validation_failed" in blocker for blocker in result["blockers"])
