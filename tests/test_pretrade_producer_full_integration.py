from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pytest

from backend.app.governance.settings import get_settings
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
        (date(2026, 4, 1) + timedelta(days=offset)).isoformat()
        for offset in range(20)
    ]
    completed_date_set = set(completed_dates)
    coverage_only_dates = [
        (target_day - timedelta(days=offset)).isoformat()
        for offset in range(1, 130)
        if (target_day - timedelta(days=offset)).isoformat()
        not in completed_date_set
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
            coverage_only_dates=coverage_only_dates,
        )
        conn.executemany(
            "insert into choice_stock_request_audit values (?, ?, ?, ?, ?)",
            [
                (
                    TARGET_DATE,
                    "stock_universe",
                    "a_share_universe_sector_001004",
                    "completed",
                    1,
                ),
                (
                    TARGET_DATE,
                    "sector_membership",
                    "sw2021_industry_membership",
                    "completed",
                    1,
                ),
                (
                    TARGET_DATE,
                    "sector_strength",
                    "daily_return_turnover_amplitude",
                    "completed",
                    1,
                ),
                (TARGET_DATE, "stock_ohlcv", "daily_ohlcv_amount", "completed", 1),
                (TARGET_DATE, "stock_status", "daily_trade_status", "completed", 1),
                (
                    TARGET_DATE,
                    "limit_up_quality",
                    "daily_limit_flags",
                    "completed",
                    1,
                ),
                (
                    TARGET_DATE,
                    "limit_up_quality",
                    "point_in_time_limit_streaks",
                    "completed",
                    1,
                ),
            ],
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
            "vendor_version = 'vv_synthetic_replay'"
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
        conn.execute(
            "create table choice_stock_factor_snapshot ("
            "as_of_date varchar, stock_code varchar, pe double, pb double, "
            "ps double, roe double, gross_margin double, three_month_return double, "
            "twelve_month_return double, volatility double, dividend_yield double, "
            "industry varchar)"
        )
        conn.execute(
            "insert into choice_stock_factor_snapshot values "
            "(?, ?, 18.0, 1.2, 2.1, 0.16, 0.35, 0.22, 0.41, 0.19, 0.015, 'electronics')",
            [TARGET_DATE, STOCK_CODE],
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
                    240_000_000.0,
                    "trading",
                    prior_close * 1.1,
                    prior_close * 0.9,
                    "sv_synthetic_target",
                    "vv_choice_stock_synthetic"
                    if ready_candidate
                    else "vv_synthetic_unscaled",
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
            "select distinct stock_code, ?, 1.0 "
            "from choice_stock_daily_observation where trade_date = ?",
            [TARGET_DATE, TARGET_DATE],
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
        conn.execute(
            "create table if not exists livermore_position_snapshot "
            "(as_of_date varchar, position_status varchar)"
        )
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
    output_paths = result["pretrade_output_paths"]
    assert all(Path(path).is_file() for path in output_paths.values())
    with duckdb.connect(str(db_path), read_only=True) as conn:
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
