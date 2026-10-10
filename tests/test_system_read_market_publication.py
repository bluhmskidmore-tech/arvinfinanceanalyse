from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace

import pytest
import duckdb

import backend.app.tasks.system_read_market_publication as market_publication
from backend.app.tasks.financial_result_publication import (
    FinancialPublicationInvalid,
    FinancialPublicationReceipt,
)
from backend.app.services.pretrade_qualification import (
    build_completed_pretrade_qualification,
    canonical_pretrade_output_sha256,
    capture_pretrade_input_snapshot,
    unavailable_pretrade_qualification,
)


pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_market_data,
]


REPORT_DATE = "2026-09-15"
RUN_ID = "market-daily:2026-09-15:test"


def _ready_pretrade_qualification() -> dict[str, object]:
    conn = duckdb.connect(":memory:")
    try:
        for table_name, date_column in (
            ("choice_stock_universe", "as_of_date"),
            ("choice_stock_sector_membership", "as_of_date"),
            ("choice_stock_daily_observation", "trade_date"),
            ("choice_stock_limit_quality", "as_of_date"),
            ("choice_stock_factor_snapshot", "as_of_date"),
            ("stock_adjustment_factor", "trade_date"),
            ("fact_livermore_gate_supplement_daily", "trade_date"),
        ):
            conn.execute(f"create table {table_name} ({date_column} date)")
            conn.execute(f"insert into {table_name} values (?)", [REPORT_DATE])
        conn.execute(
            "create table fact_choice_macro_daily (trade_date date, series_id varchar)"
        )
        conn.executemany(
            "insert into fact_choice_macro_daily values (?, ?)",
            [
                (REPORT_DATE, "CA.CSI300"),
                (REPORT_DATE, "CA.CSI300_PCT_CHG"),
                (REPORT_DATE, "CA.CSI300_PE"),
            ],
        )
        snapshot = capture_pretrade_input_snapshot(
            conn,
            target_date=REPORT_DATE,
            stock_candidate_policy="mainboard_only",
        )
    finally:
        conn.close()
    return build_completed_pretrade_qualification(
        producer_result={
            "status": "completed",
            "run_id": f"{RUN_ID}:livermore_pretrade_candidates:child",
            "snapshot_as_of_date": REPORT_DATE,
            "strategy_payload_sha256": "a" * 64,
            "candidate_history_sha256": "b" * 64,
            "row_count": 1,
            "stock_candidate_policy": "mainboard_only",
            "rule_version": "synthetic-candidate-v1",
        },
        input_snapshot_before=snapshot,
        input_snapshot_after=snapshot,
        confluence_payload={
            "status": "completed",
            "rows": 1,
            "canonical_output_sha256": canonical_pretrade_output_sha256(
                {"rows": 1}
            ),
        },
        export_payload={"as_of_date": REPORT_DATE, "rows": 1},
        rule_identity={
            "candidate_rule_version": "synthetic-candidate-v1",
            "checklist_rule_version": "synthetic-checklist-v1",
            "export_rule_version": "synthetic-export-v1",
            "lookback_days": 60,
            "signal_confluence_contract": "synthetic-confluence-v1",
            "stale_calendar_days": 5,
            "stock_candidate_policy": "mainboard_only",
            "strategy_calculation_mode": "historical_backfill",
            "top_n": 20,
        },
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "progress\n"
            + json.dumps(
                {
                    "status": "completed",
                    "target_date": "2026-01-02",
                    "nested": {"status": "ready"},
                }
            ),
            {
                "status": "completed",
                "target_date": "2026-01-02",
                "nested": {"status": "ready"},
            },
        ),
        (
            "progress\n"
            + json.dumps(
                {"status": "completed", "nested": {"status": "ready"}},
                indent=2,
            ),
            {"status": "completed", "nested": {"status": "ready"}},
        ),
        (
            "progress\n"
            + json.dumps({"status": "running", "nested": {"step": 1}})
            + "\nfinished\n"
            + json.dumps({"status": "completed", "nested": {"step": 2}}),
            {"status": "completed", "nested": {"step": 2}},
        ),
    ],
)
def test_extract_json_object_returns_last_complete_top_level_result(
    raw: str, expected: dict[str, object]
) -> None:
    assert market_publication._extract_json_object(raw) == expected


def _aggregate() -> dict[str, object]:
    started_at = "2026-09-15T11:59:59+00:00"
    generated_at = "2026-09-15T12:00:00+00:00"
    completed_at = "2026-09-15T12:00:01+00:00"
    pretrade_qualification = _ready_pretrade_qualification()
    choice_result = {
        "status": "success",
        "as_of_date": REPORT_DATE,
        "history_start_date": REPORT_DATE,
        "refresh": {
            "status": "completed",
            "report_date": REPORT_DATE,
            "run_id": "choice-run",
            "cache_key": "choice-stock:daily",
            "theme_overlay_mode": "archive",
            "theme_overlay_status": "completed",
        },
        "gate_supplement": {"status": "completed"},
        "position_snapshot_rollforward": {"status": "noop"},
    }
    factor_result = {
        "status": "completed",
        "trade_date": REPORT_DATE,
        "table": "stock_adjustment_factor",
        "required_cells_covered": True,
    }
    limit_run_id = f"{RUN_ID}:stock_limit_price_daily_refresh:child"
    limit_result = {
        "status": "completed_with_warnings",
        "start_date": REPORT_DATE,
        "end_date": REPORT_DATE,
        "required_cells_covered": True,
        "failed_dates": [],
        "dq": {"hard_violation_count": 0, "ratio_out_of_band_count": 1},
    }
    results = {
        "choice_stock_daily_refresh": (
            choice_result,
            {
                "status": "success",
                "generated_at": generated_at,
                "warnings": [],
                "result": choice_result,
            },
        ),
        "stock_adjustment_factor_daily_refresh": (
            factor_result,
            {"status": "completed", "generated_at": generated_at, "result": factor_result},
        ),
        "stock_limit_price_daily_refresh": (
            limit_result,
            {
                "status": "completed_with_warnings",
                "generated_at": generated_at,
                "run_id": limit_run_id,
                "result": limit_result,
            },
        ),
        "livermore_pretrade_candidates": (
            {
                "status": "completed",
                "target_date": REPORT_DATE,
                "local_state": {"ready": True, "missing": []},
                "pretrade_qualification": pretrade_qualification,
            },
            None,
        ),
        "macro_toolkit_freshness": (
            {
                "status": "success",
                "report_date": REPORT_DATE,
                "steps": [
                    {"step": step, "status": "success"}
                    for step in sorted(market_publication._EXPECTED_FRESHNESS_STEPS)
                ],
                "latest_observation_dates": {
                    "fact_commodity_futures_daily": REPORT_DATE,
                    "fact_cffex_member_rank_daily": REPORT_DATE,
                },
            },
            {"status": "success", "generated_at": generated_at, "result": {}},
        ),
        "tushare_news_backup": (
            {
                "status": "completed",
                "inserted": 1,
                "purged_expired": 0,
                "purged_expired_warehouse": 0,
            },
            None,
        ),
        "macro_toolkit_daily_chain": (
            {
                "status": "completed",
                "chain": {
                    "readiness_after": {
                        "observation_only": True,
                        "formal_use_allowed": False,
                    }
                },
            },
            {"status": "completed", "generated_at": generated_at, "result": {}},
        ),
    }
    children: list[dict[str, object]] = []
    for name in market_publication.REQUIRED_CHILDREN:
        child_run_id = (
            limit_run_id if name == "stock_limit_price_daily_refresh" else f"{RUN_ID}:{name}:child"
        )
        result, external = results[name]
        if external is not None and external.get("result") == {}:
            external = {**external, "result": result}
        children.append(
            {
                "name": name,
                "run_id": child_run_id,
                "status": "success",
                "exit_code": 0,
                "output_sha256": "1" * 64,
                "started_at": started_at,
                "completed_at": completed_at,
                "result": result,
                "external_receipt": external,
                "external_receipt_path": None,
                "external_receipt_sha256": None,
            }
        )
    observations = [
        {
            "table_name": "choice_stock_daily_observation",
            "date_column": "trade_date",
            "start_date": REPORT_DATE,
            "end_date": REPORT_DATE,
            "present": True,
            "row_count": 2,
            "content_hash_xor": "10",
            "content_hash_sum": "20",
            "schema_sha256": "2" * 64,
            "required": True,
        }
    ]
    payload = {
        "schema_version": market_publication.SCHEMA_VERSION,
        "run_id": RUN_ID,
        "workflow": market_publication.WORKFLOW,
        "report_date": REPORT_DATE,
        "status": "business_completed",
        "children": children,
        "source_cut": {
            "captured_at": "2026-09-15T12:00:00+00:00",
            "observations": observations,
            "sha256": market_publication._sha256_bytes(
                market_publication._canonical_bytes(observations)
            ),
        },
        "pretrade_availability": pretrade_qualification,
    }
    return payload


def _weekend_aggregate() -> dict[str, object]:
    report_date = "2026-09-13"
    payload = _aggregate()
    payload["report_date"] = report_date
    choice = _child(payload, "choice_stock_daily_refresh")
    choice["started_at"] = "2026-09-13T11:59:59+00:00"
    choice["completed_at"] = "2026-09-13T12:00:01+00:00"
    choice_result = {
        "status": "skipped_non_trading_day",
        "as_of_date": report_date,
        "as_of_date_explicit": False,
        "no_write": True,
        "database_write_scope": [],
        "governance_write_scope": [],
        "reason": "default date is a weekend",
    }
    choice["result"] = choice_result
    choice["external_receipt"] = {
        "status": "skipped_non_trading_day",
        "generated_at": "2026-09-13T12:00:00+00:00",
        "warnings": [],
        "result": choice_result,
    }
    chain = {
        "stock_adjustment_factor_daily_refresh": "choice_stock_daily_refresh",
        "stock_limit_price_daily_refresh": "stock_adjustment_factor_daily_refresh",
        "livermore_pretrade_candidates": "stock_limit_price_daily_refresh",
    }
    for child_name, upstream_name in chain.items():
        child = _child(payload, child_name)
        child["run_id"] = f"{RUN_ID}:{child_name}:not-executed"
        child["status"] = "not_executed"
        child["exit_code"] = None
        child["output_sha256"] = None
        child["external_receipt"] = None
        child["result"] = {
            "status": "not_executed",
            "aggregate_run_id": RUN_ID,
            "upstream_child_name": upstream_name,
            "upstream_child_run_id": _child(payload, upstream_name)["run_id"],
            "upstream_status": (
                "skipped_non_trading_day"
                if upstream_name == "choice_stock_daily_refresh"
                else "not_executed"
            ),
            "no_write": True,
        }
    freshness = _child(payload, "macro_toolkit_freshness")["result"]
    freshness["report_date"] = report_date
    freshness["latest_observation_dates"] = {
        "fact_commodity_futures_daily": report_date,
        "fact_cffex_member_rank_daily": report_date,
    }
    observations = [
        {
            "table_name": "fact_choice_macro_daily",
            "date_column": "trade_date",
            "start_date": report_date,
            "end_date": report_date,
            "present": True,
            "row_count": 3,
            "content_hash_xor": "10",
            "content_hash_sum": "20",
            "schema_sha256": "2" * 64,
            "required": True,
        }
    ]
    payload["source_cut"] = {
        "captured_at": "2026-09-13T12:00:00+00:00",
        "observations": observations,
        "sha256": market_publication._sha256_bytes(
            market_publication._canonical_bytes(observations)
        ),
    }
    payload["pretrade_availability"] = unavailable_pretrade_qualification(
        "choice_default_weekend_no_write_pretrade_not_executed"
    )
    return payload


def _settings(tmp_path: Path, *, enabled: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        system_read_publication_enabled=enabled,
        duckdb_path=tmp_path / "moss.duckdb",
    )


def _write(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _current_cut(receipt: Mapping[str, object]) -> dict[str, object]:
    return {
        **dict(receipt["source_cut"]),  # type: ignore[arg-type]
        "pretrade_availability": receipt["pretrade_availability"],
    }


def _child(payload: dict[str, object], name: str) -> dict[str, object]:
    return next(item for item in payload["children"] if item["name"] == name)  # type: ignore[index]


def test_publish_uses_real_aggregate_identity_and_never_calls_pnl(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    receipt_path = tmp_path / "aggregate.json"
    payload = _aggregate()
    _write(receipt_path, payload)
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        market_publication,
        "_capture_source_cut",
        lambda _settings, receipt: _current_cut(receipt),
    )
    monkeypatch.setattr(
        market_publication,
        "publish_preserved_system_read_generation",
        lambda _settings, **kwargs: calls.append(kwargs)
        or FinancialPublicationReceipt(
            status="completed",
            generation="gen-market",
            previous_generation="gen-core",
            database_path=tmp_path / "gen-market.duckdb",
            manifest_path=tmp_path / "manifest.json",
            manifest_sha256="4" * 64,
            pointer_path=tmp_path / "current.json",
            recovered_after_commit=False,
            resource_limits=None,
        ),
    )

    result = market_publication.publish_aggregate(
        _settings(tmp_path),
        receipt_path=receipt_path,
        run_id=RUN_ID,
        report_date=REPORT_DATE,
    )

    assert result["generation"] == "gen-market"
    assert calls[0]["writer_run_id"] == RUN_ID
    assert calls[0]["workflow"] == "market_daily"
    assert calls[0]["data_update_run_id"] is None
    assert calls[0]["changed_terminal_references"] == (
        ("choice-run", "choice-stock:daily", REPORT_DATE),
    )
    assert "pnl" not in json.dumps(calls, default=str).lower()


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda payload: _child(payload, "choice_stock_daily_refresh")[
                "external_receipt"
            ].update({"warnings": ["position roll-forward failed"]}),
            "unresolved late-step warnings",
        ),
        (
            lambda payload: _child(payload, "stock_limit_price_daily_refresh")[
                "result"
            ].update({"failed_dates": [REPORT_DATE]}),
            "complete required coverage",
        ),
        (
            lambda payload: _child(payload, "stock_adjustment_factor_daily_refresh")[
                "result"
            ].update({"trade_date": "2026-09-14"}),
            "date does not match",
        ),
    ],
)
def test_qualification_rejects_partial_or_mismatched_child_receipts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mutate,
    message: str,
) -> None:
    payload = _aggregate()
    mutate(payload)
    monkeypatch.setattr(
        market_publication,
        "_capture_source_cut",
        lambda _settings, receipt: _current_cut(receipt),
    )

    with pytest.raises(FinancialPublicationInvalid, match=message):
        market_publication.qualify_market_daily_receipt(_settings(tmp_path), payload)


def test_qualification_rejects_changed_external_receipt_hash(tmp_path: Path) -> None:
    payload = _aggregate()
    choice = _child(payload, "choice_stock_daily_refresh")
    external_path = tmp_path / "choice.json"
    _write(external_path, choice["external_receipt"])
    choice["external_receipt_path"] = str(external_path)
    choice["external_receipt_sha256"] = "0" * 64

    with pytest.raises(FinancialPublicationInvalid, match="changed after completion"):
        market_publication.qualify_market_daily_receipt(_settings(tmp_path), payload)


@pytest.mark.parametrize(
    ("counter", "value"),
    [
        ("purged_expired", None),
        ("inserted", -1),
        ("purged_expired_warehouse", "0"),
    ],
)
def test_qualification_rejects_missing_or_malformed_news_write_counters(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    counter: str,
    value: object,
) -> None:
    payload = _aggregate()
    news = _child(payload, "tushare_news_backup")["result"]
    if value is None:
        news.pop(counter)
    else:
        news[counter] = value
    monkeypatch.setattr(
        market_publication,
        "_capture_source_cut",
        lambda _settings, receipt: _current_cut(receipt),
    )

    with pytest.raises(FinancialPublicationInvalid, match=f"integer {counter}"):
        market_publication.qualify_market_daily_receipt(_settings(tmp_path), payload)


@pytest.mark.parametrize("missing_step", [None, "choice_policy_rate_7d"])
def test_qualification_requires_exact_normally_on_macro_freshness_steps(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    missing_step: str | None,
) -> None:
    payload = _aggregate()
    freshness = _child(payload, "macro_toolkit_freshness")["result"]
    if missing_step is None:
        freshness["steps"] = []
    else:
        freshness["steps"] = [
            step for step in freshness["steps"] if step["step"] != missing_step
        ]
    monkeypatch.setattr(
        market_publication,
        "_capture_source_cut",
        lambda _settings, receipt: _current_cut(receipt),
    )

    with pytest.raises(FinancialPublicationInvalid, match="normally-on step set"):
        market_publication.qualify_market_daily_receipt(_settings(tmp_path), payload)


def test_pre_cas_failure_keeps_pointer_and_marks_publication_only_retryable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    receipt_path = tmp_path / "aggregate.json"
    pointer_path = tmp_path / "current.json"
    pointer_path.write_text('{"generation":"gen-core"}', encoding="utf-8")
    payload = _aggregate()
    _write(receipt_path, payload)
    monkeypatch.setattr(
        market_publication,
        "_capture_source_cut",
        lambda _settings, receipt: _current_cut(receipt),
    )
    monkeypatch.setattr(
        market_publication,
        "publish_preserved_system_read_generation",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            FinancialPublicationInvalid("pre-CAS qualification failed")
        ),
    )

    with pytest.raises(FinancialPublicationInvalid, match="pre-CAS"):
        market_publication.publish_aggregate(
            _settings(tmp_path),
            receipt_path=receipt_path,
            run_id=RUN_ID,
            report_date=REPORT_DATE,
        )

    assert pointer_path.read_text(encoding="utf-8") == '{"generation":"gen-core"}'
    assert json.loads(receipt_path.read_text(encoding="utf-8"))["status"] == "publication_failed"


def test_post_cas_recovery_is_metadata_only_and_does_not_republish(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    receipt_path = tmp_path / "aggregate.json"
    _write(receipt_path, _aggregate())
    publish_calls: list[object] = []
    monkeypatch.setattr(
        market_publication,
        "recover_committed_system_read_publication",
        lambda *_args, **_kwargs: {
            "status": "completed",
            "generation": "gen-market",
            "writer_run_id": RUN_ID,
            "recovered_after_commit": True,
        },
    )
    monkeypatch.setattr(
        market_publication,
        "publish_preserved_system_read_generation",
        lambda *_args, **_kwargs: publish_calls.append(object()),
    )

    result = market_publication.recover_or_publish(
        _settings(tmp_path),
        receipt_path=receipt_path,
        run_id=RUN_ID,
        report_date=REPORT_DATE,
    )

    assert result["recovered_after_commit"] is True
    assert publish_calls == []
    assert json.loads(receipt_path.read_text(encoding="utf-8"))["status"] == "completed"


def test_flag_off_preserves_no_publication_behavior(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    receipt_path = tmp_path / "aggregate.json"
    _write(receipt_path, _aggregate())
    calls: list[object] = []
    monkeypatch.setattr(
        market_publication,
        "publish_preserved_system_read_generation",
        lambda *_args, **_kwargs: calls.append(object()),
    )

    result = market_publication.publish_aggregate(
        _settings(tmp_path, enabled=False),
        receipt_path=receipt_path,
        run_id=RUN_ID,
        report_date=REPORT_DATE,
    )

    assert result["status"] == "disabled"
    assert calls == []


def test_receipt_dataclass_class_is_rejected_before_receipt_write(tmp_path: Path) -> None:
    receipt_path = tmp_path / "publication.json"
    with pytest.raises(FinancialPublicationInvalid, match="invalid receipt"):
        market_publication._receipt_payload(FinancialPublicationReceipt)
    assert not receipt_path.exists()


def test_observation_only_macro_daily_degradation_does_not_block_market_cut(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    payload = _aggregate()
    child = _child(payload, "macro_toolkit_daily_chain")
    child["result"]["status"] = "degraded"
    child["external_receipt"]["status"] = "degraded"
    child["external_receipt"]["result"] = child["result"]
    monkeypatch.setattr(
        market_publication,
        "_capture_source_cut",
        lambda _settings, receipt: _current_cut(receipt),
    )

    writer_receipt, _coverage, _references, _pretrade = (
        market_publication.qualify_market_daily_receipt(_settings(tmp_path), payload)
    )

    assert writer_receipt["status"] == "completed"


def test_news_scope_binds_the_child_window_across_utc_dates_and_noop_is_explicit(
    tmp_path: Path,
) -> None:
    payload = _aggregate()
    news = _child(payload, "tushare_news_backup")
    news["started_at"] = "2026-09-14T23:55:00+00:00"
    news["completed_at"] = "2026-09-15T00:05:00+00:00"
    news["result"] = {
        "status": "completed",
        "inserted": 2,
        "purged_expired": 0,
        "purged_expired_warehouse": 0,
    }
    db_path = tmp_path / "news.duckdb"
    with duckdb.connect(str(db_path)) as conn:
        conn.execute("create table choice_news_event(received_at timestamp, value integer)")
        conn.execute(
            "insert into choice_news_event values ('2026-09-14 23:58:00', 1), ('2026-09-15 00:02:00', 2)"
        )
        conn.execute("create table fact_news_event(pub_time timestamp, value integer)")
        conn.execute(
            "insert into fact_news_event values ('2026-09-14 23:58:00', 1), ('2026-09-15 00:02:00', 2)"
        )
        specs = market_publication._source_scope_specs(
            conn, payload, market_publication._child_map(payload)
        )

    choice_news_specs = [item for item in specs if item[0] == "choice_news_event"]
    assert ("choice_news_event", "received_at", "2026-09-11", "2026-09-15", True) in choice_news_specs
    assert ("choice_news_event", "received_at", "2026-09-14", "2026-09-14", True) in choice_news_specs
    assert ("choice_news_event", "received_at", "2026-09-15", "2026-09-15", True) in choice_news_specs

    news["result"] = {
        "status": "completed",
        "inserted": 0,
        "purged_expired": 0,
        "purged_expired_warehouse": 0,
    }
    with duckdb.connect(str(db_path), read_only=True) as conn:
        noop_specs = market_publication._source_scope_specs(
            conn, payload, market_publication._child_map(payload)
        )
    assert not [item for item in noop_specs if item[0] in {"choice_news_event", "fact_news_event"}]


def test_writer_lock_validator_rejects_market_change_after_outer_qualification(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    payload = _aggregate()
    monkeypatch.setattr(
        market_publication,
        "_capture_source_cut",
        lambda _settings, receipt: _current_cut(receipt),
    )
    market_publication.qualify_market_daily_receipt(_settings(tmp_path), payload)
    changed_cut = {
        "observations": [
            {
                **payload["source_cut"]["observations"][0],
                "row_count": 3,
            }
        ],
        "pretrade_availability": payload["pretrade_availability"],
    }
    monkeypatch.setattr(
        market_publication,
        "_capture_source_cut_from_connection",
        lambda _conn, _receipt: changed_cut,
    )

    validator = market_publication._changed_source_validator(payload)
    with pytest.raises(FinancialPublicationInvalid, match="inside the publication writer lock"):
        validator(object())


def test_weekend_choice_no_write_keeps_independent_writers_publishable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    payload = _weekend_aggregate()
    monkeypatch.setattr(
        market_publication,
        "_capture_source_cut",
        lambda _settings, receipt: _current_cut(receipt),
    )

    writer_receipt, coverage, references, pretrade = (
        market_publication.qualify_market_daily_receipt(_settings(tmp_path), payload)
    )

    assert writer_receipt["status"] == "completed"
    assert references == ()
    assert pretrade == unavailable_pretrade_qualification(
        "choice_default_weekend_no_write_pretrade_not_executed"
    )
    assert {item[0] for item in coverage} == {"fact_choice_macro_daily"}


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: _child(payload, "choice_stock_daily_refresh")["result"].update(
            {"as_of_date_explicit": True}
        ),
        lambda payload: _child(payload, "choice_stock_daily_refresh")["result"].update(
            {"database_write_scope": ["choice_stock_daily_observation"]}
        ),
        lambda payload: _child(payload, "stock_limit_price_daily_refresh")["result"].update(
            {"upstream_child_run_id": "another-run"}
        ),
    ],
)
def test_weekend_choice_skip_rejects_explicit_partial_or_mismatched_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mutate,
) -> None:
    payload = _weekend_aggregate()
    mutate(payload)
    monkeypatch.setattr(
        market_publication,
        "_capture_source_cut",
        lambda _settings, receipt: _current_cut(receipt),
    )

    with pytest.raises(FinancialPublicationInvalid):
        market_publication.qualify_market_daily_receipt(_settings(tmp_path), payload)
