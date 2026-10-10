from __future__ import annotations

import copy
import json
import os
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pytest

from backend.app.governance.settings import get_settings
from backend.app.repositories.choice_stock_adapter import STOCK_FACTOR_INPUT_RULE_VERSION
from backend.app.repositories.duckdb_migrations import _run_sql_slice
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.services import livermore_candidate_history_service as history_service
from backend.app.services import (
    livermore_signal_confluence_service as confluence_service,
)
from backend.app.services import market_data_livermore_service as livermore_service
from backend.app.services import stock_analysis_workbench_service as workbench_service
from backend.app.services.pretrade_qualification import qualify_pretrade_read_view
from backend.app.tasks import livermore_candidate_history_materialize as candidate_task
from scripts.run_livermore_daily_pretrade_refresh import (
    run_livermore_daily_pretrade_refresh,
)
from tests.test_market_data_livermore_api import (
    _seed_choice_macro_history,
    _seed_livermore_replay_window,
)


pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_livermore,
]


TARGET_DATE = "2026-05-20"
STOCK_CODE = "688001.SH"
UI_FIXTURE_ROOT = Path(
    ".codex-tmp/system-online-pretrade-20260915/ui-fixtures-v2"
)


def _write_confirmed_choice_catalog(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "catalog_version": "synthetic-pretrade-integration-v1",
                "vendor_name": "choice",
                "generated_from": "synthetic fixture",
                "fields": [
                    {
                        "input_family": family,
                        "field_key": field_key,
                        "vendor_indicator": f"fixture_{field_key}",
                        "confirmed": True,
                        "confirmation_source": "synthetic fixture",
                        "confirmed_at": "2026-05-20T00:00:00Z",
                    }
                    for family, field_key in (
                        ("sector_membership", "sw2021_industry_membership"),
                        ("sector_strength", "daily_return_turnover_amplitude"),
                        ("stock_universe", "a_share_universe_sector_001004"),
                        ("stock_ohlcv", "daily_ohlcv_amount"),
                        ("stock_status", "daily_trade_status"),
                        ("limit_up_quality", "daily_limit_flags"),
                    )
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _seed_actual_pretrade_database(path: Path, *, ready_candidate: bool) -> None:
    target_day = date.fromisoformat(TARGET_DATE)
    completed_dates = [
        (target_day - timedelta(days=offset)).isoformat()
        for offset in range(20, 130)
    ]
    pending_dates = [
        (target_day - timedelta(days=offset)).isoformat()
        for offset in range(1, 20)
    ]
    _seed_choice_macro_history(
        str(path),
        start=date(2026, 3, 17),
        closes=[3200.0 + offset * 8 for offset in range(65)],
    )
    with duckdb.connect(str(path), read_only=False) as conn:
        _seed_livermore_replay_window(
            conn,
            completed_snapshot_dates=completed_dates,
            evaluation_date=TARGET_DATE,
            stocks_per_completed_date=5,
            pending_snapshot_dates=pending_dates,
        )
        point_in_time_requests = {
            "a_share_universe_sector_001004": (
                "sector", "001004", ["001004", TARGET_DATE], {},
            ),
            "sw2021_industry_membership": (
                "css", "SW2021,SW2021CODE", [STOCK_CODE, "SW2021,SW2021CODE"],
                {"EndDate": TARGET_DATE, "Classification": "1"},
            ),
            "point_in_time_limit_streaks": (
                "css", "ISSURGEDLIMIT,ISDECLINELIMIT,HLIMITEDAYS,LLIMITEDDAYS",
                [STOCK_CODE, "ISSURGEDLIMIT,ISDECLINELIMIT,HLIMITEDAYS,LLIMITEDDAYS"],
                {"TradeDate": TARGET_DATE},
            ),
        }
        required_requests = (
            ("stock_universe", "a_share_universe_sector_001004"),
            ("sector_membership", "sw2021_industry_membership"),
            ("sector_strength", "daily_return_turnover_amplitude"),
            ("stock_ohlcv", "daily_ohlcv_amount"),
            ("stock_status", "daily_trade_status"),
            ("limit_up_quality", "daily_limit_flags"),
            ("limit_up_quality", "point_in_time_limit_streaks"),
        )
        audit_rows = []
        for family, field_key in required_requests:
            call, indicator, arguments, options = point_in_time_requests.get(
                field_key, ("csd", "", [], {}),
            )
            audit_rows.append((
                TARGET_DATE, family, field_key, "completed", 3, call, indicator,
                json.dumps(arguments), json.dumps(options), "sv_synthetic_target", "vv_synthetic_target",
            ))
        conn.executemany(
            "insert into choice_stock_request_audit "
            "(as_of_date, input_family, field_key, status, row_count, call, vendor_indicator, "
            "request_arguments_json, request_options_json, source_version, vendor_version) "
            "values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            audit_rows,
        )
        conn.execute(
            "alter table choice_stock_daily_observation add column source_version varchar"
        )
        conn.execute(
            "alter table choice_stock_daily_observation add column vendor_version varchar"
        )
        conn.execute(
            "update choice_stock_daily_observation set "
            "source_version = 'sv_synthetic_replay', "
            "vendor_version = 'vv_choice_stock_20260520_0123456789ab'"
        )
        for statement in (
            "alter table choice_stock_universe add column stock_name varchar",
            "alter table choice_stock_universe add column source_version varchar",
            "alter table choice_stock_universe add column vendor_version varchar",
            "alter table choice_stock_sector_membership add column sw2021code varchar",
            "alter table choice_stock_sector_membership add column sw2021 varchar",
            "alter table choice_stock_sector_membership add column source_version varchar",
            "alter table choice_stock_sector_membership add column vendor_version varchar",
            "alter table choice_stock_limit_quality add column issurgedlimit boolean",
            "alter table choice_stock_limit_quality add column isdeclinelimit boolean",
            "alter table choice_stock_limit_quality add column hlimitedays integer",
            "alter table choice_stock_limit_quality add column llimitedays integer",
            "alter table choice_stock_limit_quality add column source_version varchar",
            "alter table choice_stock_limit_quality add column vendor_version varchar",
        ):
            conn.execute(statement)
        conn.execute(
            "update choice_stock_universe set stock_name = 'Synthetic Candidate', "
            "source_version = 'sv_synthetic_universe', "
            "vendor_version = 'vv_synthetic_universe'"
        )
        conn.execute(
            "update choice_stock_sector_membership set sw2021code = '801080', "
            "sw2021 = 'Electronics', source_version = 'sv_synthetic_sector', "
            "vendor_version = 'vv_synthetic_sector'"
        )
        conn.execute(
            "update choice_stock_limit_quality set issurgedlimit = false, "
            "isdeclinelimit = false, hlimitedays = 0, llimitedays = 0, "
            "source_version = 'sv_synthetic_limit', "
            "vendor_version = 'vv_synthetic_limit'"
        )
        _run_sql_slice(conn, "27_choice_stock_factor_snapshot.sql")
        conn.execute(
            "insert into choice_stock_factor_snapshot "
            "(as_of_date, stock_code, pe, pb, ps, roe, gross_margin, three_month_return, "
            "twelve_month_return, volatility, dividend_yield, industry, "
            "source_version, vendor_version, rule_version, run_id) values "
            "(?, ?, 18.0, 1.2, 2.1, 0.16, 0.35, 0.22, 0.41, 0.19, 0.015, 'electronics', "
            "'sv_synthetic_factor', 'vv_choice_stock_20260520_0123456789ab', ?, 'synthetic-factor-run')",
            [TARGET_DATE, STOCK_CODE, STOCK_FACTOR_INPUT_RULE_VERSION],
        )
        conn.executemany(
            "insert into choice_stock_factor_snapshot "
            "(as_of_date, stock_code, pe, pb, ps, roe, gross_margin, three_month_return, "
            "twelve_month_return, volatility, dividend_yield, industry, "
            "source_version, vendor_version, rule_version, run_id) values "
            "(?, ?, 18.0, 1.2, 2.1, 0.16, 0.35, 0.22, 0.41, 0.19, 0.015, 'peer', "
            "'sv_synthetic_factor', 'vv_choice_stock_20260520_0123456789ab', ?, 'synthetic-factor-run')",
            [
                (TARGET_DATE, code, STOCK_FACTOR_INPUT_RULE_VERSION)
                for code in ("000001.SZ", "000002.SZ")
            ],
        )
        conn.execute(
            "insert into choice_stock_universe values (?, ?, ?, ?, ?, ?)",
            [
                TARGET_DATE,
                STOCK_CODE,
                "a_share_universe_sector_001004",
                "Synthetic Candidate",
                "sv_synthetic_universe",
                "vv_synthetic_universe",
            ],
        )
        conn.execute(
            "insert into choice_stock_sector_membership values (?, ?, ?, ?, ?, ?, ?)",
            [
                TARGET_DATE,
                STOCK_CODE,
                "sw2021_industry_membership",
                "801080",
                "Electronics",
                "sv_synthetic_sector",
                "vv_synthetic_sector",
            ],
        )
        conn.execute(
            "insert into choice_stock_limit_quality values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                TARGET_DATE,
                STOCK_CODE,
                "point_in_time_limit_streaks",
                False,
                False,
                0,
                0,
                "sv_synthetic_limit",
                "vv_synthetic_limit",
            ],
        )
        for index, (stock_code, sector_code, sector_name) in enumerate(
            (
                ("000001.SZ", "801010", "Agriculture"),
                ("000002.SZ", "801020", "Mining"),
            ),
            start=1,
        ):
            conn.execute(
                "insert into choice_stock_universe values (?, ?, ?, ?, ?, ?)",
                [
                    TARGET_DATE,
                    stock_code,
                    "a_share_universe_sector_001004",
                    f"Synthetic Peer {index}",
                    "sv_synthetic_universe",
                    "vv_synthetic_universe",
                ],
            )
            conn.execute(
                "insert into choice_stock_sector_membership values (?, ?, ?, ?, ?, ?, ?)",
                [
                    TARGET_DATE,
                    stock_code,
                    "sw2021_industry_membership",
                    sector_code,
                    sector_name,
                    "sv_synthetic_sector",
                    "vv_synthetic_sector",
                ],
            )
            conn.execute(
                "insert into choice_stock_limit_quality values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    TARGET_DATE,
                    stock_code,
                    "point_in_time_limit_streaks",
                    False,
                    False,
                    0,
                    0,
                    "sv_synthetic_limit",
                    "vv_synthetic_limit",
                ],
            )
        observation_rows = []
        for offset in range(130):
            trade_date = (target_day - timedelta(days=offset)).isoformat()
            close_value = 20.0 - offset * 0.1 if ready_candidate else 10.6
            prior_close = close_value - 0.1 if ready_candidate else 10.6
            is_target = offset == 0
            observation_rows.append(
                (
                    trade_date,
                    STOCK_CODE,
                    '["daily_return_turnover_amplitude","daily_ohlcv_amount",'
                    '"daily_trade_status","daily_limit_flags"]',
                    (close_value / prior_close) - 1.0 if ready_candidate else 0.0,
                    5.2 if is_target else 1.5,
                    1.0,
                    19.95 if is_target and ready_candidate else close_value - 0.05,
                    close_value + (0.001 if ready_candidate else 0.2),
                    close_value - (0.3 if ready_candidate else 0.8),
                    close_value,
                    1_000_000.0,
                    240_000_000.0 if ready_candidate else 1_000_000.0,
                    "trading",
                    prior_close * 1.1,
                    prior_close * 0.9,
                    "sv_synthetic_target",
                    "vv_choice_stock_20260520_0123456789ab",
                )
            )
        conn.executemany(
            "insert into choice_stock_daily_observation ("
            "trade_date, stock_code, field_keys_json, pctchange, turn, amplitude, "
            "open_value, high_value, low_value, close_value, volume, amount, "
            "tradestatus, highlimit, lowlimit, source_version, vendor_version) values "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            observation_rows,
        )
        conn.execute(
            "create table if not exists stock_adjustment_factor "
            "(stock_code varchar, trade_date varchar, adj_factor double)"
        )
        conn.execute(
            "insert into stock_adjustment_factor "
            "(stock_code, trade_date, adj_factor) "
            "select distinct stock_code, trade_date, 1.0 "
            "from choice_stock_daily_observation",
        )
        conn.execute(
            "create table if not exists fact_livermore_gate_supplement_daily "
            "(trade_date varchar, breadth_5d double, limit_up_quality_ok boolean)"
        )
        conn.execute(
            "insert into fact_livermore_gate_supplement_daily "
            "(trade_date, breadth_5d, limit_up_quality_ok) values (?, ?, true)",
            [TARGET_DATE, -0.2 if ready_candidate else 0.2],
        )
        _run_sql_slice(conn, "22_livermore_position_snapshot.sql")
        conn.execute(
            "insert into livermore_position_snapshot "
            "(as_of_date, position_status) values (?, 'ACTIVE')",
            [TARGET_DATE],
        )
        conn.executemany(
            "insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "CA.CSI300_PCT_CHG",
                    "CSI300 daily return",
                    TARGET_DATE,
                    0.01,
                    "daily",
                    "%",
                    "sv_choice_macro",
                    "vv_choice_macro",
                    "rv_choice_macro",
                    "ok",
                    "choice_macro_refresh:2026-05-20",
                ),
                (
                    "CA.CSI300_PE",
                    "CSI300 PE",
                    TARGET_DATE,
                    12.0,
                    "daily",
                    "x",
                    "sv_choice_macro",
                    "vv_choice_macro",
                    "rv_choice_macro",
                    "ok",
                    "choice_macro_refresh:2026-05-20",
                ),
                (
                    "EMM00166466",
                    "China 10Y yield",
                    TARGET_DATE,
                    2.2,
                    "daily",
                    "%",
                    "sv_rates",
                    "vv_rates",
                    "rv_rates",
                    "ok",
                    "rates_refresh:2026-05-20",
                ),
                (
                    "M0017126",
                    "Manufacturing PMI",
                    "2026-04-01",
                    51.0,
                    "monthly",
                    "index",
                    "backfill_macro_v1",
                    "vv_pmi_fixture",
                    "rv_backfill_macro_v1",
                    "ok",
                    "backfill_macro_v1:20260430T000000Z",
                ),
                (
                    "M5525763",
                    "Social financing stock YoY",
                    "2026-03-01",
                    8.0,
                    "monthly",
                    "%",
                    "backfill_macro_v1",
                    "vv_credit_fixture",
                    "rv_backfill_macro_v1",
                    "ok",
                    "backfill_macro_v1:20260331T000000Z",
                ),
                (
                    "M5525763",
                    "Social financing stock YoY",
                    "2026-04-01",
                    8.5,
                    "monthly",
                    "%",
                    "backfill_macro_v1",
                    "vv_credit_fixture",
                    "rv_backfill_macro_v1",
                    "ok",
                    "backfill_macro_v1:20260430T000000Z",
                ),
            ],
        )


def _write_json_exclusive(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")


@pytest.mark.parametrize(
    ("ready_candidate", "expected_status"),
    [(True, "ready"), (False, "ready_empty")],
    ids=("nonempty", "empty"),
)
def test_actual_pretrade_producer_closes_with_borrowed_connection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ready_candidate: bool,
    expected_status: str,
) -> None:
    db_path = tmp_path / "actual-pretrade.duckdb"
    output_dir = tmp_path / "pretrade-output"
    catalog_path = tmp_path / "synthetic-choice-catalog.json"
    _seed_actual_pretrade_database(db_path, ready_candidate=ready_candidate)
    _write_confirmed_choice_catalog(catalog_path)
    monkeypatch.setenv("MOSS_CHOICE_STOCK_CATALOG_FILE", str(catalog_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    get_settings.cache_clear()
    monkeypatch.setattr(
        confluence_service,
        "get_macro_environment_context",
        lambda *_args, **_kwargs: {
            "result_meta": {
                "source_version": "sv_synthetic_external_macro",
                "vendor_version": "vv_synthetic_external_macro",
                "quality_flag": "ok",
                "vendor_status": "ok",
                "fallback_mode": "none",
                "tables_used": ["synthetic_macro_context"],
                "evidence_rows": 1,
            },
            "result": {"environment_score": {"composite_score": 0.1}},
        },
    )
    monkeypatch.setattr(
        confluence_service,
        "load_macro_adversarial_signal_payload",
        lambda **_kwargs: (
            {"status": "ok", "risk_gate": "allow", "diagnostics": []},
            {
                "source_version": "sv_synthetic_adversarial",
                "vendor_version": "vv_synthetic_adversarial",
                "quality_flag": "ok",
                "vendor_status": "ok",
                "fallback_mode": "none",
                "tables_used": ["synthetic_adversarial_input"],
                "evidence_rows": 1,
            },
        ),
    )
    actual_confluence = confluence_service.livermore_signal_confluence_envelope
    borrowed_connections: list[duckdb.DuckDBPyConnection] = []
    captured_confluence_envelopes: list[dict[str, object]] = []
    actual_strategy_loader = candidate_task.load_livermore_strategy_payload_from_connection
    captured_strategies: list[dict[str, object]] = []

    def observe_strategy(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        payload, meta = actual_strategy_loader(*args, **kwargs)
        captured_strategies.append(payload)
        return payload, meta

    def observe_borrowed_connection(**kwargs: object) -> dict[str, object]:
        borrowed = kwargs.get("_conn")
        assert isinstance(borrowed, duckdb.DuckDBPyConnection)
        borrowed_connections.append(borrowed)
        envelope = actual_confluence(**kwargs)
        captured_confluence_envelopes.append(envelope)
        return envelope

    monkeypatch.setattr(
        confluence_service,
        "livermore_signal_confluence_envelope",
        observe_borrowed_connection,
    )
    monkeypatch.setattr(
        candidate_task,
        "load_livermore_strategy_payload_from_connection",
        observe_strategy,
    )
    try:
        result = run_livermore_daily_pretrade_refresh(
            duckdb_path=db_path,
            target_date=TARGET_DATE,
            output_dir=output_dir,
            stock_candidate_policy="exp3b",
            skip_upstream_probe=True,
            theme_overlay_mode="off",
            export_pretrade=True,
        )
    finally:
        get_settings.cache_clear()

    if result["status"] != "completed":
        pytest.fail(
            json.dumps(
                {
                    "result": result,
                    "market_gate": captured_strategies[-1].get("market_gate")
                    if captured_strategies
                    else None,
                    "stock_candidates": captured_strategies[-1].get("stock_candidates")
                    if captured_strategies
                    else None,
                },
                ensure_ascii=False,
                default=str,
                indent=2,
            )
        )
    assert borrowed_connections
    step_by_name = {step["name"]: step["result"] for step in result["steps"]}
    assert step_by_name["candidate_history"]["status"] in {"ok", "completed"}
    assert step_by_name["candidate_outcome_maturity"]["status"] == "completed"
    confluence = step_by_name["signal_confluence_closure"]
    assert confluence["status"] == "completed"
    assert confluence["replay"]["completed_dates"] >= 20
    assert confluence["replay"]["matched_entry_count"] >= 100
    assert confluence["replay"]["has_required_horizon_stats"] is True
    assert confluence["macro"]["authority_status"] == "ready"
    confluence_envelope = captured_confluence_envelopes[-1]
    assert confluence_envelope["result"]["as_of_date"] == TARGET_DATE
    qualification = result["pretrade_qualification"]
    assert qualification["status"] == expected_status, json.dumps(
        {
            "market_gate": captured_strategies[-1].get("market_gate"),
            "stock_candidates": captured_strategies[-1].get("stock_candidates"),
            "diagnostics": captured_strategies[-1].get("diagnostics"),
        },
        ensure_ascii=False,
        default=str,
        indent=2,
    )
    assert qualification["rule_identity"]["strategy_calculation_mode"] == (
        "historical_backfill"
    )
    assert step_by_name["candidate_history"]["empty_result"] is (
        not ready_candidate
    )
    assert step_by_name["candidate_history"]["input_coverage_status"] == "ready"
    output_paths = result["pretrade_output_paths"]
    assert all(Path(path).is_file() for path in output_paths.values())
    with duckdb.connect(str(db_path), read_only=True) as conn:
        if not ready_candidate:
            assert history_service._has_completed_zero_signal_receipt(
                duckdb_path=str(db_path), trade_date=TARGET_DATE, conn=conn,
            )
        requalified = qualify_pretrade_read_view(
            conn,
            evidence=qualification,
            target_date=TARGET_DATE,
            stock_candidate_policy="exp3b",
        )
    assert requalified == qualification

    captured_external_inputs = livermore_service.capture_livermore_external_inputs(
        catalog_path
    )
    workbench = workbench_service.stock_analysis_workbench_envelope(
        duckdb_path=str(db_path),
        as_of_date=TARGET_DATE,
        choice_stock_catalog_file=catalog_path,
        _pretrade_qualification=qualification,
        _captured_external_inputs=captured_external_inputs,
    )
    workbench_result = workbench["result"]
    workbench_qualification = workbench_result["pretrade_qualification"]
    assert workbench_qualification["status"] == expected_status
    assert workbench_qualification["strategy_payload_sha256"] == qualification[
        "outputs"
    ]["strategy_payload_sha256"]
    assert workbench_qualification["attested_strategy_payload_sha256"] == qualification[
        "outputs"
    ]["strategy_payload_sha256"]

    temp_artifact_dir = tmp_path / expected_status
    _write_json_exclusive(
        temp_artifact_dir / "confluence.json",
        confluence_envelope,
    )
    _write_json_exclusive(temp_artifact_dir / "workbench.json", workbench)
    if os.environ.get("MOSS_WRITE_SYNTHETIC_UI_FIXTURES") == "1":
        persistent_artifact_dir = UI_FIXTURE_ROOT / expected_status
        _write_json_exclusive(
            persistent_artifact_dir / "confluence.json",
            confluence_envelope,
        )
        _write_json_exclusive(
            persistent_artifact_dir / "workbench.json",
            workbench,
        )


@pytest.mark.parametrize("changed_evidence", (
    "missing_manifest", "missing_terminal", "failed_terminal", "run_id",
    "report_date", "rule_version", "formula_version", "policy",
    "incomplete_coverage", "strategy_inputs", "source_cut", "request_audit", "external_input",
    "nonempty_candidates",
))
def test_completed_zero_signal_receipt_rejects_changed_or_missing_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changed_evidence: str,
) -> None:
    db_path = tmp_path / "zero-signal.duckdb"
    governance_path = tmp_path / "governance"
    catalog_path = tmp_path / "choice-catalog.json"
    _seed_actual_pretrade_database(db_path, ready_candidate=False)
    _write_confirmed_choice_catalog(catalog_path)
    monkeypatch.setenv("MOSS_CHOICE_STOCK_CATALOG_FILE", str(catalog_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    get_settings.cache_clear()
    try:
        # Complete coverage alone cannot certify an unexecuted zero-row date.
        assert not history_service._has_completed_zero_signal_receipt(
            duckdb_path=str(db_path), trade_date=TARGET_DATE,
        )
        result = candidate_task.materialize_livermore_candidate_history(
            str(db_path), as_of_date=TARGET_DATE, stock_candidate_policy="exp3b",
        )
        assert result["status"] == "ok"
        assert result["empty_result"] is True
        # A fresh repository/connection must recover the actual task's receipt.
        assert history_service._has_completed_zero_signal_receipt(
            duckdb_path=str(db_path), trade_date=TARGET_DATE,
        )
        repository = GovernanceRepository(base_dir=governance_path, backend_mode="jsonl")
        cache_key = f"{history_service.ZERO_SIGNAL_CACHE_KEY}:exp3b"
        terminal = repository.read_latest_run(cache_key, report_date=TARGET_DATE)
        manifest = repository.read_latest_manifest(cache_key, report_date=TARGET_DATE)
        assert terminal is not None and manifest is not None

        if changed_evidence in {"missing_manifest", "missing_terminal"}:
            stream = (
                CACHE_MANIFEST_STREAM if changed_evidence == "missing_manifest"
                else CACHE_BUILD_RUN_STREAM
            )
            (governance_path / f"{stream}.jsonl").unlink()
        elif changed_evidence == "failed_terminal":
            repository.append(CACHE_BUILD_RUN_STREAM, {**terminal, "status": "failed"})
        elif changed_evidence in {"source_cut", "request_audit", "nonempty_candidates"}:
            with duckdb.connect(str(db_path)) as conn:
                if changed_evidence == "source_cut":
                    conn.execute(
                        "update choice_stock_daily_observation set close_value = '19.25' "
                        "where stock_code = ? and try_cast(trade_date as date) = cast(? as date)",
                        [STOCK_CODE, TARGET_DATE],
                    )
                elif changed_evidence == "request_audit":
                    conn.execute(
                        "update choice_stock_request_audit set request_options_json = '{}' "
                        "where as_of_date = ? and field_key = 'sw2021_industry_membership'",
                        [TARGET_DATE],
                    )
                else:
                    conn.execute(
                        "insert into livermore_candidate_history "
                        "select * replace(cast(? as date) as snapshot_as_of_date) "
                        "from livermore_candidate_history where snapshot_as_of_date <> ? limit 1",
                        [TARGET_DATE, TARGET_DATE],
                    )
        elif changed_evidence == "external_input":
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            catalog["catalog_version"] = "changed-after-production"
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
        else:
            altered = copy.deepcopy(manifest)
            producer = altered["lineage"]["producer_result"]
            if changed_evidence == "run_id":
                altered["run_id"] = "different-run"
            elif changed_evidence == "report_date":
                producer["snapshot_as_of_date"] = "2026-05-19"
            elif changed_evidence == "rule_version":
                producer["rule_version"] = "rv_stale"
            elif changed_evidence == "formula_version":
                producer["formula_version"] = "fv_stale"
            elif changed_evidence == "policy":
                producer["stock_candidate_policy"] = "exp3a"
            elif changed_evidence == "incomplete_coverage":
                producer["input_coverage_status"] = "incomplete"
            elif changed_evidence == "strategy_inputs":
                producer["zero_signal_input_status"] = "unavailable"
            # Recompute transport identities to exercise the semantic guards.
            altered["cache_version"] = "cv_livermore_zero_signal_" + (
                candidate_task.canonical_pretrade_output_sha256(altered["lineage"])
            )
            repository.append_many_atomic([
                (CACHE_BUILD_RUN_STREAM, {
                    **terminal, "run_id": altered["run_id"],
                    "cache_version": altered["cache_version"],
                }),
                (CACHE_MANIFEST_STREAM, altered),
            ])
        assert not history_service._has_completed_zero_signal_receipt(
            duckdb_path=str(db_path), trade_date=TARGET_DATE,
        ), changed_evidence
        summary = history_service.livermore_candidate_history_backtest_window_summary(
            duckdb_path=str(db_path), stock_code=None,
            snapshot_from=TARGET_DATE, snapshot_to=TARGET_DATE,
            evaluation_as_of_date=TARGET_DATE,
        )
        assert not any(
            reason["reason_code"] == "no_strategy_signals"
            for reason in summary["date_reasons"]
        )
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize("unavailable_input", (
    "missing_catalog", "unconfirmed_catalog", "factor_query_failed", "missing_factor_value",
))
def test_actual_zero_signal_producer_refuses_unavailable_strategy_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, unavailable_input: str,
) -> None:
    db_path = tmp_path / "unavailable-zero-signal.duckdb"
    governance_path = tmp_path / "governance"
    catalog_path = tmp_path / "choice-catalog.json"
    _seed_actual_pretrade_database(db_path, ready_candidate=False)
    _write_confirmed_choice_catalog(catalog_path)
    if unavailable_input == "missing_catalog":
        catalog_path.unlink()
    elif unavailable_input == "unconfirmed_catalog":
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        for field in catalog["fields"]:
            field["confirmed"] = False
        catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    elif unavailable_input == "missing_factor_value":
        with duckdb.connect(str(db_path)) as conn:
            conn.execute(
                "update choice_stock_factor_snapshot set pe = null where stock_code = '000001.SZ'",
            )
    else:
        def fail_factor_query(**_kwargs: object) -> list[object]:
            raise duckdb.Error("synthetic factor read failure")

        monkeypatch.setattr(
            livermore_service.LIVERMORE_STRATEGY_READS,
            "fetch_factor_screen_rows", fail_factor_query,
        )
    monkeypatch.setenv("MOSS_CHOICE_STOCK_CATALOG_FILE", str(catalog_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    get_settings.cache_clear()
    actual_strategy_loader = candidate_task.load_livermore_strategy_payload_from_connection
    captured_payloads = []

    def observe_strategy(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        payload, meta = actual_strategy_loader(*args, **kwargs)
        captured_payloads.append(payload)
        return payload, meta

    monkeypatch.setattr(candidate_task, "load_livermore_strategy_payload_from_connection", observe_strategy)
    try:
        result = candidate_task.materialize_livermore_candidate_history(
            str(db_path), as_of_date=TARGET_DATE, stock_candidate_policy="exp3b",
        )
        assert result["status"] == "partial"
        assert result["row_count"] == 0
        assert result["empty_result"] is False
        assert result["input_coverage_status"] == "ready"
        assert result["zero_signal_input_status"] == "unavailable"
        assert "no_strategy_signals" not in result["skipped"]
        if unavailable_input == "factor_query_failed":
            assert "strategy_query_or_diagnostics_failed" in result["skipped"]
            assert any(
                item["code"] == "LIVERMORE_DUCKDB_QUERY_FAILED"
                for item in captured_payloads[-1]["diagnostics"]
            )
        elif unavailable_input == "missing_factor_value":
            assert "factor_screen_candidates:strategy_factor_inputs_incomplete" in result["skipped"]
        else:
            assert "choice_stock_catalog_not_ready" in result["skipped"]
        repository = GovernanceRepository(base_dir=governance_path, backend_mode="jsonl")
        cache_key = f"{history_service.ZERO_SIGNAL_CACHE_KEY}:exp3b"
        assert repository.read_latest_manifest(cache_key, report_date=TARGET_DATE) is None
        terminal = repository.read_latest_run(cache_key, report_date=TARGET_DATE)
        assert terminal is not None and terminal["status"] == "failed"
        summary = history_service.livermore_candidate_history_backtest_window_summary(
            duckdb_path=str(db_path), stock_code=None,
            snapshot_from=TARGET_DATE, snapshot_to=TARGET_DATE,
            evaluation_as_of_date=TARGET_DATE,
        )
        assert not any(
            reason["reason_code"] == "no_strategy_signals"
            for reason in summary["date_reasons"]
        )
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize("prior_result", ("nonempty", "completed_zero", "incomplete_audit"))
def test_failed_zero_signal_attempt_preserves_rows_and_blocks_old_empty_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prior_result: str,
) -> None:
    db_path = tmp_path / "prior-result.duckdb"
    governance_path = tmp_path / "governance"
    catalog_path = tmp_path / "choice-catalog.json"
    _seed_actual_pretrade_database(db_path, ready_candidate=prior_result != "completed_zero")
    _write_confirmed_choice_catalog(catalog_path)
    monkeypatch.setenv("MOSS_CHOICE_STOCK_CATALOG_FILE", str(catalog_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    get_settings.cache_clear()
    try:
        first = candidate_task.materialize_livermore_candidate_history(
            str(db_path), as_of_date=TARGET_DATE, stock_candidate_policy="exp3b",
        )
        assert first["status"] == "ok"
        assert first["empty_result"] is (prior_result == "completed_zero")
        with duckdb.connect(str(db_path), read_only=True) as conn:
            before = history_service._zero_signal_source_profiles(conn, trade_date=TARGET_DATE)
        if prior_result == "nonempty":
            assert before["livermore_candidate_history"]["row_count"] > 0
            catalog_path.unlink()
        elif prior_result == "incomplete_audit":
            with duckdb.connect(str(db_path)) as conn:
                conn.execute(
                    "update choice_stock_daily_observation set close_value = 10.6, "
                    "open_value = 10.55, high_value = 10.8, low_value = 9.8, "
                    "pctchange = 0.0, amount = 1000000.0, highlimit = 11.66, lowlimit = 9.54 "
                    "where stock_code = ?", [STOCK_CODE],
                )
                conn.execute(
                    "delete from choice_stock_request_audit where as_of_date = ? "
                    "and field_key = 'daily_trade_status'", [TARGET_DATE],
                )
                if before["livermore_stock_candidate_universe_history"]["row_count"] == 0:
                    conn.execute(
                        "insert into livermore_stock_candidate_universe_history "
                        "(snapshot_as_of_date, stock_code, stock_name, source_version, vendor_version, rule_version, run_id) "
                        "values (?, '999999.SZ', 'Previous Synthetic Row', 'sv_previous', "
                        "'vv_previous', 'rv_previous', 'run_previous')", [TARGET_DATE],
                    )
            with duckdb.connect(str(db_path), read_only=True) as conn:
                before = history_service._zero_signal_source_profiles(conn, trade_date=TARGET_DATE)
            for table in (
                "livermore_candidate_history", "livermore_stock_candidate_universe_history",
                "livermore_candidate_execution_history",
            ):
                assert before[table]["row_count"] > 0
        else:
            assert history_service._has_completed_zero_signal_receipt(
                duckdb_path=str(db_path), trade_date=TARGET_DATE,
            )

            def fail_factor_query(**_kwargs: object) -> list[object]:
                raise duckdb.Error("synthetic subsequent factor read failure")

            monkeypatch.setattr(
                livermore_service.LIVERMORE_STRATEGY_READS,
                "fetch_factor_screen_rows", fail_factor_query,
            )
        failed = candidate_task.materialize_livermore_candidate_history(
            str(db_path), as_of_date=TARGET_DATE, stock_candidate_policy="exp3b",
        )
        assert failed["status"] == "partial"
        assert failed["empty_result"] is False
        if prior_result == "incomplete_audit":
            assert "choice_stock_materialization_coverage_incomplete" in failed["skipped"]
        with duckdb.connect(str(db_path), read_only=True) as conn:
            assert history_service._zero_signal_source_profiles(conn, trade_date=TARGET_DATE) == before
        repository = GovernanceRepository(base_dir=governance_path, backend_mode="jsonl")
        terminal = repository.read_latest_run(
            f"{history_service.ZERO_SIGNAL_CACHE_KEY}:exp3b", report_date=TARGET_DATE,
        )
        assert terminal is not None and terminal["status"] == "failed"
        assert not history_service._has_completed_zero_signal_receipt(
            duckdb_path=str(db_path), trade_date=TARGET_DATE,
        )
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize("policy_exclusion", ("ST", "nonpositive_pe"))
def test_actual_zero_signal_producer_accepts_complete_factor_inputs_excluded_by_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, policy_exclusion: str,
) -> None:
    db_path = tmp_path / "policy-excluded-zero.duckdb"
    governance_path = tmp_path / "governance"
    catalog_path = tmp_path / "choice-catalog.json"
    _seed_actual_pretrade_database(db_path, ready_candidate=False)
    _write_confirmed_choice_catalog(catalog_path)
    with duckdb.connect(str(db_path)) as conn:
        if policy_exclusion == "ST":
            conn.execute(
                "update choice_stock_universe set stock_name = 'ST Known Policy Exclusion' "
                "where stock_code = '000001.SZ'",
            )
        else:
            conn.execute(
                "update choice_stock_factor_snapshot set pe = 0 where stock_code = '000001.SZ'",
            )
    monkeypatch.setenv("MOSS_CHOICE_STOCK_CATALOG_FILE", str(catalog_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    get_settings.cache_clear()
    actual_strategy_loader = candidate_task.load_livermore_strategy_payload_from_connection
    captured_payloads = []

    def observe_strategy(*args: object, **kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        payload, meta = actual_strategy_loader(*args, **kwargs)
        captured_payloads.append(payload)
        return payload, meta

    monkeypatch.setattr(candidate_task, "load_livermore_strategy_payload_from_connection", observe_strategy)
    try:
        result = candidate_task.materialize_livermore_candidate_history(
            str(db_path), as_of_date=TARGET_DATE, stock_candidate_policy="exp3b",
        )
        factor = captured_payloads[-1]["factor_screen_candidates"]
        assert factor["coverage_count"] == factor["coverage_denominator"] == 3
        assert factor["liquidity_filter"]["evaluated_count"] == 2
        assert factor["liquidity_filter"]["missing_amount_count"] == 0
        assert result["status"] == "ok", result["skipped"]
        assert result["empty_result"] is True
        assert result["zero_signal_input_status"] == "ready"
        assert history_service._has_completed_zero_signal_receipt(
            duckdb_path=str(db_path), trade_date=TARGET_DATE,
        )
    finally:
        get_settings.cache_clear()
