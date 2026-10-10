from __future__ import annotations

import copy
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from backend.app.core_finance.adjusted_returns import ensure_stock_adjustment_factor_schema
from backend.app.core_finance.livermore_stock_candidates import (
    FORMULA_VERSION as STOCK_CANDIDATE_FORMULA_VERSION,
)
from backend.app.core_finance.matched_baseline import (
    FORMULA_VERSION as MATCHED_BASELINE_FORMULA_VERSION,
)
from backend.app.governance.stock_analysis_calendar_receipt import (
    build_stock_analysis_calendar_receipt,
)
from backend.app.repositories.duckdb_migrations import register_all
from backend.app.repositories.duckdb_schema_registry import DuckDBSchemaRegistry
from backend.app.tasks import stock_analysis_current_rule_cohort_bundle_producer as producer
from backend.app.tasks import stock_analysis_current_rule_cohort_evidence as collector

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]

NOW = "2026-08-23T12:00:00+08:00"
EVALUATION_AS_OF_DATE = "2026-08-31"
OWNER_APPROVAL_ID = "OWNER-D6B-INTEGRATION-001"
OBS_SOURCE_VERSION = "sv_obs_integration"
OBS_VENDOR_VERSION = "vv_choice"
OBS_RULE_VERSION = "rv_obs_integration"
OBS_RUN_ID = "run_obs_integration"
FACTOR_SOURCE_VERSION = "sv_factor_integration"
FACTOR_VENDOR_VERSION = "vv_choice"
FACTOR_RULE_VERSION = "rv_factor_integration"
FACTOR_RUN_ID = "run_factor_integration"


def _canonical_sha(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest().upper()


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _write(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return path


def _base_database(tmp_path: Path) -> Path:
    path = tmp_path / "target.duckdb"
    registry = DuckDBSchemaRegistry(db_path=str(path))
    register_all(registry)
    registry.apply_pending()
    return path


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


def _version_tuple() -> dict[str, object]:
    return {
        "candidate_rule_version": "rv_candidate_history_current",
        "stock_candidate_selection_formula_version": STOCK_CANDIDATE_FORMULA_VERSION,
        "candidate_outcome_formula_version": "fv_livermore_candidate_forward_close_dual_adjust_v2",
        "execution_formula_version": "fv_livermore_candidate_execution_dual_adjust_v5",
        "matched_baseline_formula_version": MATCHED_BASELINE_FORMULA_VERSION,
        "market_gate_rule_version": "rv_market_gate_current_v2",
        "signal_confluence_rule_version": "rv_signal_confluence_current_v4",
        "macro_formula_version": "fv_macro_bundle_current_v1",
        "candidate_source_version": "sv_candidate_current",
        "execution_source_version": "sv_execution_current",
        "matched_baseline_source_version": "sv_matched_baseline_current",
        "macro_source_version": "sv_macro_current",
        "theme_overlay_fingerprint": "overlay-fingerprint-integration",
        "choice_catalog_fingerprint": "catalog-fingerprint-integration",
        "stock_candidate_selection_policy": "exp3b",
        "decision_metric_basis": "net_next_open_adj",
        "coverage_authority_mode": producer.CURRENT_RULE_COVERAGE_AUTHORITY_MODE,
        "strict_coverage": True,
        "fallback_covered": False,
    }


def _source_receipt() -> dict[str, object]:
    return {
        "schema_version": 1,
        "receipt_kind": "pit_source_availability_v1",
        "captured_at": NOW,
        "sources": [
            {
                "table": "choice_stock_daily_observation",
                "source_version": OBS_SOURCE_VERSION,
                "vendor_version": OBS_VENDOR_VERSION,
                "rule_version": OBS_RULE_VERSION,
                "run_id": OBS_RUN_ID,
                "available_at": "2026-08-20",
            },
            {
                "table": "stock_adjustment_factor",
                "source_version": FACTOR_SOURCE_VERSION,
                "vendor_version": FACTOR_VENDOR_VERSION,
                "rule_version": FACTOR_RULE_VERSION,
                "run_id": FACTOR_RUN_ID,
                "available_at": "2026-08-20",
            },
        ],
    }


def _trade_dates() -> list[str]:
    start = date(2026, 7, 1)
    return [(start + timedelta(days=index)).isoformat() for index in range(21)]


def _calendar_receipt(trade_dates: list[str]) -> dict[str, object]:
    return build_stock_analysis_calendar_receipt(
        calendar_rows=[
            {
                "exchange": "SSE",
                "cal_date": trade_date,
                "is_open": 1,
                "pretrade_date": None if index == 0 else trade_dates[index - 1],
            }
            for index, trade_date in enumerate(trade_dates)
        ],
        request_start_date=trade_dates[0],
        request_end_date=trade_dates[-1],
        fetched_at=NOW,
        authority_status="approved",
        owner_approval_id=OWNER_APPROVAL_ID,
    )


def _runner_result(*, trade_date: str, candidate_codes: list[str], status: str) -> dict[str, object]:
    count = len(candidate_codes)
    return {
        "status": status,
        "status_reason": (
            "current_rule_candidates_present"
            if status == collector.SIGNAL_STATUS
            else "policy_active_zero_signal"
        ),
        "requested_as_of_date": trade_date,
        "resolved_as_of_date": trade_date,
        "requested_matches_resolved": True,
        "market_state": "WARM",
        "selection_policy": "exp3b",
        "stock_candidate_formula_version": STOCK_CANDIDATE_FORMULA_VERSION,
        "rule_tuple_matches": True,
        "candidate_count": count,
        "candidate_item_count": count,
        "accepted_candidate_count": count,
        "candidate_count_matches_items": True,
        "candidate_codes": list(candidate_codes),
        "accepted_candidate_codes": list(candidate_codes),
        "unique_candidate_codes": sorted(candidate_codes),
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
                "formula_version": STOCK_CANDIDATE_FORMULA_VERSION,
                "candidate_count": len(items),
                "insufficient_history_count": 0,
                "input_stock_count": 200,
                "excluded_stock_count": 0,
                "items": items,
            },
            "unsupported_outputs": [],
        },
        {
            "quality_flag": "ok",
            "vendor_status": "ok",
            "fallback_mode": "none",
            "source_version": "sv_selection",
            "vendor_version": "vv_selection",
            "tables_used": ["choice_stock_daily_observation"],
            "evidence_rows": len(items),
        },
    )


def _candidate_source_evidence(
    *, signal_date: str, exit_price_5d: float, exit_price_20d: float
) -> dict[str, object]:
    def leaf(*, source_version: str, vendor_version: str, rule_version: str, run_id: str) -> dict[str, object]:
        return {
            "availability_status": "available",
            "available_at": "2026-08-20",
            "source_version": source_version,
            "vendor_version": vendor_version,
            "rule_version": rule_version,
            "run_id": run_id,
        }

    signal = date.fromisoformat(signal_date)
    observation = {
        "table": "choice_stock_daily_observation",
        **{
            point: {
                "trade_date": (signal + timedelta(days=days)).isoformat(),
                **leaf(
                    source_version=OBS_SOURCE_VERSION,
                    vendor_version=OBS_VENDOR_VERSION,
                    rule_version=OBS_RULE_VERSION,
                    run_id=OBS_RUN_ID,
                ),
            }
            for point, days in (("entry", 1), ("exit_5d", 5), ("exit_20d", 20))
        },
    }
    limit_price = {
        "table": "stock_limit_price_daily",
        "entry": None,
        "entry_source": "observation_cast",
    }
    for horizon, exit_price in (("5d", exit_price_5d), ("20d", exit_price_20d)):
        exit_observation = observation[f"exit_{horizon}"]
        limit_price[f"exit_{horizon}"] = None
        limit_price[f"exit_{horizon}_source"] = "observation_cast"
        limit_price[f"exit_{horizon}_decisions"] = [{
            "trade_date": exit_observation["trade_date"],
            "decision": "sellable",
            "close_value": exit_price,
            "up_limit": exit_price * 1.1,
            "down_limit": exit_price * 0.9,
            "limit_down_flag": False,
            "limit_price_source": "observation_cast",
            "source": None,
            "observation": dict(exit_observation),
        }]
    return {
        "observation": observation,
        "adjustment_factor": {
            "table": "stock_adjustment_factor",
            "entry": leaf(
                source_version=FACTOR_SOURCE_VERSION,
                vendor_version=FACTOR_VENDOR_VERSION,
                rule_version=FACTOR_RULE_VERSION,
                run_id=FACTOR_RUN_ID,
            ),
            "exit_5d": leaf(
                source_version=FACTOR_SOURCE_VERSION,
                vendor_version=FACTOR_VENDOR_VERSION,
                rule_version=FACTOR_RULE_VERSION,
                run_id=FACTOR_RUN_ID,
            ),
            "exit_20d": leaf(
                source_version=FACTOR_SOURCE_VERSION,
                vendor_version=FACTOR_VENDOR_VERSION,
                rule_version=FACTOR_RULE_VERSION,
                run_id=FACTOR_RUN_ID,
            ),
        },
        "limit_price": limit_price,
    }


def _execution_payload(*, trade_date: str, stock_code: str, ordinal: int) -> dict[str, object]:
    signal = date.fromisoformat(trade_date)
    entry_date = (signal + timedelta(days=1)).isoformat()
    exit_5d = (signal + timedelta(days=5)).isoformat()
    exit_20d = (signal + timedelta(days=20)).isoformat()
    entry_price = 10.0 + ordinal / 10.0
    exit_price_5d = entry_price + 0.5
    exit_price_20d = entry_price + 1.0
    return {
        "stock_code": stock_code,
        "entry_date": entry_date,
        "entry_price": entry_price,
        "entry_price_kind": "next_open",
        "entry_executable": True,
        "exit_date_5d": exit_5d,
        "exit_price_5d": exit_price_5d,
        "return_5d_net_adj": 0.04 + ordinal / 1000.0,
        "exit_date_20d": exit_20d,
        "exit_price_20d": exit_price_20d,
        "return_20d_net_adj": 0.09 + ordinal / 1000.0,
        "price_adjustment_mode": "adj_factor_ratio",
        "data_status": "complete",
    }


def _candidate_pit_from_execution(execution: dict[str, object]) -> dict[str, object]:
    return {
        "entry": {
            "trade_date": execution["entry_date"],
            "price": execution["entry_price"],
            "price_kind": execution["entry_price_kind"],
            "usable": True,
            "executable": True,
        },
        "horizons": {
            "5d": {
                "trade_date": execution["exit_date_5d"],
                "price": execution["exit_price_5d"],
                "net_adj_return": execution["return_5d_net_adj"],
                "usable": True,
            },
            "20d": {
                "trade_date": execution["exit_date_20d"],
                "price": execution["exit_price_20d"],
                "net_adj_return": execution["return_20d_net_adj"],
                "usable": True,
            },
        },
        "failure_reason": None,
        "source_evidence": _candidate_source_evidence(
            signal_date=(date.fromisoformat(str(execution["entry_date"])) - timedelta(days=1)).isoformat(),
            exit_price_5d=float(execution["exit_price_5d"]),
            exit_price_20d=float(execution["exit_price_20d"]),
        ),
    }


def _control_rows(*, trade_date: str, stock_code: str, candidate_rank: int) -> list[dict[str, object]]:
    signal = date.fromisoformat(trade_date)
    rows: list[dict[str, object]] = []
    for control_index in range(collector.CONTROL_COUNT):
        rows.append(
            {
                "control_stock_code": f"C{signal:%m%d}{candidate_rank:02d}{control_index:02d}.SZ",
                "candidate_stock_code": stock_code,
                "signal_date": trade_date,
                "signal_kind": "stock_candidate",
                "control_entry_date": (signal + timedelta(days=1)).isoformat(),
                "control_entry_price": 9.0 + candidate_rank / 10.0 + control_index / 100.0,
                "control_entry_price_kind": "open",
                "control_entry_executable": True,
                "control_entry_usable": True,
                "control_exit_date_5d": (signal + timedelta(days=5)).isoformat(),
                "control_exit_price_5d": 9.5 + candidate_rank / 10.0,
                "control_return_5d_net_adj": 0.02 + control_index / 1000.0,
                "control_return_5d_usable": True,
                "control_exit_date_20d": (signal + timedelta(days=20)).isoformat(),
                "control_exit_price_20d": 10.0 + candidate_rank / 10.0,
                "control_return_20d_net_adj": 0.06 + control_index / 1000.0,
                "control_return_20d_usable": True,
                "control_entry_failure_reason": None,
                "control_failure_reason_5d": None,
                "control_failure_reason_20d": None,
                "control_failure_reason": None,
                "formula_version": MATCHED_BASELINE_FORMULA_VERSION,
                "metric_basis": "net_next_open_adj",
                "price_adjustment_mode": "adj_factor_ratio",
                "evaluation_as_of_date": EVALUATION_AS_OF_DATE,
                "source_evidence": _candidate_source_evidence(
                    signal_date=trade_date,
                    exit_price_5d=9.5 + candidate_rank / 10.0,
                    exit_price_20d=10.0 + candidate_rank / 10.0,
                ),
            }
        )
    return rows


def _governed_run_id(
    *, trade_dates: list[str], calendar_receipt: dict[str, object], source_receipt: dict[str, object]
) -> str:
    return producer.derive_expected_stock_analysis_current_rule_governed_run_id(
        calendar_receipt_sha256=str(calendar_receipt["canonical_receipt_sha256"]),
        source_availability_receipt_sha256s=[_canonical_sha(source_receipt)],
        frozen_version_tuple=_version_tuple(),
        evaluation_as_of_date=EVALUATION_AS_OF_DATE,
        open_dates=trade_dates,
    )


def _seed_pit_source_rows(
    db_path: Path, execution_by_key: dict[tuple[str, str], dict[str, object]]
) -> None:
    observations = []
    factors = []
    for (trade_date, code), execution in execution_by_key.items():
        signal = date.fromisoformat(trade_date)
        rank = int(code[3:6])
        paths = [
            (code, execution["entry_price"], execution["exit_price_5d"], execution["exit_price_20d"]),
            *[
                (
                    control["control_stock_code"], control["control_entry_price"],
                    control["control_exit_price_5d"], control["control_exit_price_20d"],
                )
                for control in _control_rows(
                    trade_date=trade_date, stock_code=code, candidate_rank=rank
                )
            ],
        ]
        for stock_code, entry_price, exit_5d, exit_20d in paths:
            for day in range(1, 21):
                price_date = (signal + timedelta(days=day)).isoformat()
                close = exit_5d if day == 5 else exit_20d if day == 20 else entry_price
                observations.append((
                    price_date, stock_code, entry_price, close, close * 1.1, close * 0.9,
                    "trading", OBS_SOURCE_VERSION, OBS_VENDOR_VERSION, OBS_RULE_VERSION, OBS_RUN_ID,
                ))
                factors.append((
                    stock_code, price_date, 1.0, FACTOR_SOURCE_VERSION, FACTOR_VENDOR_VERSION,
                    FACTOR_RULE_VERSION, FACTOR_RUN_ID,
                ))
    with duckdb.connect(str(db_path), read_only=False) as conn:
        ensure_stock_adjustment_factor_schema(conn)
        conn.execute("alter table stock_adjustment_factor add column vendor_version varchar")
        conn.execute("alter table stock_adjustment_factor add column rule_version varchar")
        conn.execute("begin transaction")
        conn.executemany(
            "insert into choice_stock_daily_observation "
            "(trade_date, stock_code, open_value, close_value, highlimit, lowlimit, tradestatus, "
            "source_version, vendor_version, rule_version, run_id) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            observations,
        )
        conn.executemany(
            "insert into stock_adjustment_factor "
            "(stock_code, trade_date, adj_factor, source_version, vendor_version, rule_version, run_id) "
            "values (?, ?, ?, ?, ?, ?, ?)",
            factors,
        )
        conn.execute("commit")


def _collect_ready_evidence(
    *, monkeypatch: pytest.MonkeyPatch, db_path: Path, trade_dates: list[str], governed_run_id: str
) -> dict[str, object]:
    candidate_codes_by_date: dict[str, list[str]] = {}
    execution_by_key: dict[tuple[str, str], dict[str, object]] = {}

    for index, trade_date in enumerate(trade_dates[:-1]):
        codes = [f"{index + 1:03d}{position + 1:03d}.SZ" for position in range(5)]
        candidate_codes_by_date[trade_date] = codes
        for ordinal, code in enumerate(codes, start=1):
            execution_by_key[(trade_date, code)] = _execution_payload(
                trade_date=trade_date,
                stock_code=code,
                ordinal=(index * 5) + ordinal,
            )
    candidate_codes_by_date[trade_dates[-1]] = []
    _seed_pit_source_rows(db_path, execution_by_key)

    def fake_loader(*, as_of_date, **kwargs):
        return _selection_payload(
            trade_date=as_of_date.isoformat(),
            candidate_codes=candidate_codes_by_date[as_of_date.isoformat()],
        )

    def fake_execution(_conn, *, stock_code: str, snapshot_as_of_date: str):
        return dict(execution_by_key[(snapshot_as_of_date, stock_code)])

    def fake_candidate_pit(_conn, *, stock_code: str, signal_date: str, **kwargs):
        return _candidate_pit_from_execution(
            dict(execution_by_key[(signal_date, stock_code)])
        )

    def fake_matched_baseline(_conn, *, candidate_rows, **kwargs):
        rows: list[dict[str, object]] = []
        for row in candidate_rows:
            rows.extend(
                _control_rows(
                    trade_date=str(row["signal_date"]),
                    stock_code=str(row["stock_code"]),
                    candidate_rank=int(row["candidate_rank"]),
                )
            )
        return rows

    monkeypatch.setattr(collector, "load_livermore_strategy_payload", fake_loader)
    monkeypatch.setattr(collector.execution_task, "_execution_returns_for_candidate", fake_execution)
    monkeypatch.setattr(collector, "_control_execution_pit_proof", fake_candidate_pit)
    monkeypatch.setattr(collector, "generate_matched_baseline_pit_proof_rows", fake_matched_baseline)

    runner_results = [
        _runner_result(
            trade_date=trade_date,
            candidate_codes=candidate_codes_by_date[trade_date],
            status=(
                collector.SIGNAL_STATUS
                if candidate_codes_by_date[trade_date]
                else collector.ZERO_STATUS
            ),
        )
        for trade_date in trade_dates
    ]
    return collector.collect_stock_analysis_current_rule_cohort_evidence(
        duckdb_path=db_path,
        evaluation_as_of_date=EVALUATION_AS_OF_DATE,
        governed_run_id=governed_run_id,
        runner_results=runner_results,
        source_availability_receipts=[_source_receipt()],
        frozen_version_tuple=_version_tuple(),
        choice_stock_readiness=_ready_readiness(),
    )


def test_collector_producer_and_dry_run_form_a_closed_loop(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = _base_database(tmp_path)
    trusted_root = tmp_path / "trusted"
    output_root = tmp_path / "output"
    trusted_root.mkdir()
    output_root.mkdir()
    trade_dates = _trade_dates()
    calendar_receipt = _calendar_receipt(trade_dates)
    source_receipt = _source_receipt()
    calendar_path = _write(trusted_root / "calendar.json", calendar_receipt)
    source_path = _write(trusted_root / "source.json", source_receipt)
    governed_run_id = _governed_run_id(
        trade_dates=trade_dates,
        calendar_receipt=calendar_receipt,
        source_receipt=source_receipt,
    )

    collected = _collect_ready_evidence(
        monkeypatch=monkeypatch,
        db_path=db_path,
        trade_dates=trade_dates,
        governed_run_id=governed_run_id,
    )

    assert collected["status"] == "ready", collected["blockers"]
    assert collected["counts"]["completed_dates"] == 21
    assert collected["counts"]["completed_with_signals_dates"] == 20
    assert collected["counts"]["completed_no_signal_dates"] == 1
    assert collected["counts"]["matched_entry_count"] == 100
    before_sha = _file_sha(db_path)

    produced = producer.produce_stock_analysis_current_rule_cohort_bundle(
        duckdb_path=db_path,
        approved_calendar_receipt_path=calendar_path,
        source_availability_receipt_paths=[source_path],
        trusted_evidence_root=trusted_root,
        output_root=output_root,
        batch_name="integration-batch",
        cohort_id="cohort-integration",
        run_id="run-integration",
        governed_run_id=governed_run_id,
        evaluation_as_of_date=EVALUATION_AS_OF_DATE,
        frozen_version_tuple=_version_tuple(),
        date_evidence=collected["date_evidence"],
        created_at=NOW,
    )

    after_sha = _file_sha(db_path)
    assert before_sha == after_sha
    assert produced["governed_run_id"] == governed_run_id
    assert produced["summary"]["completed_dates"] == 21
    assert produced["summary"]["matched_entry_count"] == 100
    assert len(produced["zero_signal_certificate_paths"]) == 1

    bundle_path = Path(produced["bundle_path"])
    dry_run_path = Path(produced["dry_run_receipt_path"])
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    dry_run = json.loads(dry_run_path.read_text(encoding="utf-8"))

    assert bundle["summary"]["completed_dates"] == 21
    assert bundle["summary"]["matched_entry_count"] == 100
    assert bundle["facts"][0]["evidence"]["candidate_source_proven"] is True
    assert bundle["facts"][0]["evidence"]["candidate_source_evidence"]["adjustment_factor"][
        "exit_20d"
    ]["run_id"] == FACTOR_RUN_ID
    assert dry_run["status"] == "dry_run_completed"
    assert dry_run["database_unchanged"] is True
    assert dry_run["target_database_sha256_before"] == before_sha
    assert dry_run["target_database_sha256_after"] == after_sha


def test_producer_refuses_tampered_candidate_source_leaf_from_collector_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = _base_database(tmp_path)
    trusted_root = tmp_path / "trusted"
    output_root = tmp_path / "output"
    trusted_root.mkdir()
    output_root.mkdir()
    trade_dates = _trade_dates()
    calendar_receipt = _calendar_receipt(trade_dates)
    source_receipt = _source_receipt()
    calendar_path = _write(trusted_root / "calendar.json", calendar_receipt)
    source_path = _write(trusted_root / "source.json", source_receipt)
    governed_run_id = _governed_run_id(
        trade_dates=trade_dates,
        calendar_receipt=calendar_receipt,
        source_receipt=source_receipt,
    )

    collected = _collect_ready_evidence(
        monkeypatch=monkeypatch,
        db_path=db_path,
        trade_dates=trade_dates,
        governed_run_id=governed_run_id,
    )
    assert collected["status"] == "ready", collected["blockers"]
    broken = copy.deepcopy(collected["date_evidence"])
    del broken[0]["signal_facts"][0]["candidate_source_evidence"]["adjustment_factor"]["exit_20d"]

    with pytest.raises(
        producer.CurrentRuleCohortError,
        match=r"candidate source evidence\.adjustment_factor\.exit_20d",
    ):
        producer.produce_stock_analysis_current_rule_cohort_bundle(
            duckdb_path=db_path,
            approved_calendar_receipt_path=calendar_path,
            source_availability_receipt_paths=[source_path],
            trusted_evidence_root=trusted_root,
            output_root=output_root,
            batch_name="tampered-batch",
            cohort_id="cohort-tampered",
            run_id="run-tampered",
            governed_run_id=governed_run_id,
            evaluation_as_of_date=EVALUATION_AS_OF_DATE,
            frozen_version_tuple=_version_tuple(),
            date_evidence=broken,
            created_at=NOW,
        )

    assert not (output_root / "tampered-batch" / "bundle.json").exists()
