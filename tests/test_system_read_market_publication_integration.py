from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import duckdb
import pytest

import backend.app.tasks.system_read_market_publication as market_publication
import backend.app.tasks.system_read_publication as system_read_publication
from backend.app.repositories.financial_result_publication_repo import (
    read_publication_pointer,
)
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.repositories.system_read_publication_repo import (
    current_system_read_context,
    resolve_system_read_publication,
    system_read_scope,
    system_read_publication_root,
)
from backend.app.services.pretrade_checklist_service import pretrade_checklist_envelope
from backend.app.services.pretrade_qualification import (
    build_completed_pretrade_qualification,
    canonical_pretrade_output_sha256,
    capture_pretrade_candidate_identity,
    capture_pretrade_input_snapshot,
    qualify_sealed_pretrade_read,
)
from backend.app.tasks.financial_result_publication import FinancialPublicationInvalid
from backend.app.tasks.system_read_publication import (
    _BOOTSTRAP_RESULT_CACHE_KEYS,
    publish_qualified_system_read_bootstrap,
)
from tests.test_system_read_market_publication import REPORT_DATE, RUN_ID, _aggregate
from tests.test_system_read_publication import (
    _bootstrap_settings_and_run,
    _core_step_receipts,
    _forbid_source_ingest_and_financial_replay,
)
from tests.test_pretrade_checklist import AS_OF, TODAY_FRESH, _build_synthetic_db
from tests.test_pretrade_qualification_contract import (
    _add_required_source_inputs,
    _completed_evidence,
)


pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_market_data,
]


def _isolate_only_unrelated_financial_fixture_domains(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = system_read_publication._manifest_matches_current_facts

    def scoped_match(
        conn: duckdb.DuckDBPyConnection,
        *,
        manifest: Mapping[str, object],
        **kwargs: object,
    ) -> bool | None:
        cache_key = str(manifest.get("cache_key") or "")
        if (
            cache_key in _BOOTSTRAP_RESULT_CACHE_KEYS
            and cache_key != "source_preview.foundation"
        ):
            return True
        return original(conn, manifest=manifest, **kwargs)

    monkeypatch.setattr(
        system_read_publication,
        "_manifest_matches_current_facts",
        scoped_match,
    )


def _append_market_facts(source: Path) -> None:
    point_tables = (
        ("choice_stock_universe", "as_of_date"),
        ("choice_stock_sector_membership", "as_of_date"),
        ("choice_stock_daily_observation", "trade_date"),
        ("choice_stock_limit_quality", "as_of_date"),
        ("choice_stock_factor_snapshot", "as_of_date"),
        ("choice_stock_concept_membership", "as_of_date"),
        ("choice_stock_intraday_movement_event", "as_of_date"),
        ("stock_adjustment_factor", "trade_date"),
        ("stock_limit_price_daily", "trade_date"),
        ("fact_livermore_gate_supplement_daily", "trade_date"),
        ("livermore_position_snapshot", "as_of_date"),
        ("livermore_candidate_history", "snapshot_as_of_date"),
        ("livermore_stock_candidate_universe_history", "snapshot_as_of_date"),
        ("livermore_candidate_execution_history", "signal_date"),
        ("fact_commodity_futures_daily", "trade_date"),
        ("fact_cffex_member_rank_daily", "trade_date"),
    )
    with duckdb.connect(str(source)) as conn:
        for table_name, date_column in point_tables:
            source_version = (
                "choice-source-v1"
                if table_name == "choice_stock_daily_observation"
                else f"{table_name}-v1"
            )
            conn.execute(
                f'create table "{table_name}"('
                f'"{date_column}" date, value integer, source_version varchar)'
            )
            conn.execute(
                f'insert into "{table_name}" values (?, 1, ?)',
                [REPORT_DATE, source_version],
            )
        conn.execute(
            "create table fact_choice_macro_daily("
            "trade_date date, series_id varchar, value double, source_version varchar)"
        )
        conn.executemany(
            "insert into fact_choice_macro_daily values (?, ?, 1.0, ?)",
            [
                (REPORT_DATE, series_id, "macro-source-v1")
                for series_id in (
                    "CA.CSI300",
                    "CA.CSI300_PCT_CHG",
                    "CA.CSI300_PE",
                )
            ],
        )
        conn.execute(
            "create table choice_news_event("
            "received_at timestamp, headline varchar, source_version varchar)"
        )
        conn.execute(
            "insert into choice_news_event values "
            "('2026-09-15 12:00:00', 'qualified market news', 'news-source-v1')"
        )
        conn.execute(
            "create table fact_news_event("
            "pub_time timestamp, headline varchar, source_version varchar)"
        )
        conn.execute(
            "insert into fact_news_event values "
            "('2026-09-15 12:00:00', 'qualified market news', 'news-source-v1')"
        )


def _append_choice_terminal(governance_path: Path) -> None:
    repository = GovernanceRepository(base_dir=governance_path, backend_mode="jsonl")
    repository.append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "choice-run",
            "job_name": "choice-stock-daily-fixture",
            "cache_key": "choice-stock:daily",
            "status": "completed",
            "report_date": REPORT_DATE,
            "source_version": "choice-source-v1",
        },
    )
    repository.append(
        CACHE_MANIFEST_STREAM,
        {
            "run_id": "choice-run",
            "cache_key": "choice-stock:daily",
            "report_date": REPORT_DATE,
            "source_version": "choice-source-v1",
            "fact_tables": ["choice_stock_daily_observation"],
            "input_sources": ["choice_stock_daily_observation"],
        },
    )


def _prepare_real_market_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[object, object, dict[str, object], Path]:
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    monkeypatch.setattr(
        "backend.app.tasks.pnl_by_business_page_publication."
        "require_current_pnl_by_business_governance",
        lambda *_args, **_kwargs: None,
    )
    _isolate_only_unrelated_financial_fixture_domains(monkeypatch)
    _forbid_source_ingest_and_financial_replay(monkeypatch)
    settings = _bootstrap_settings_and_run(tmp_path)
    first = publish_qualified_system_read_bootstrap(
        settings,
        data_update_run_id="data-update-run",
        required_date_tables=(
            ("fact_result", "report_date", 1),
            ("phase1_source_preview_summary", "report_date", 2),
        ),
    )
    source = Path(settings.duckdb_path)
    _append_market_facts(source)
    _append_choice_terminal(Path(settings.governance_path))
    payload = _aggregate()
    pretrade = next(
        child
        for child in payload["children"]
        if child["name"] == "livermore_pretrade_candidates"
    )
    # This isolates publication, not producer correctness. Bind its synthetic
    # completion to this actual fixture DB so the reader validation is not mocked.
    with duckdb.connect(str(source), read_only=True) as conn:
        input_snapshot = capture_pretrade_input_snapshot(
            conn, target_date=REPORT_DATE, stock_candidate_policy="mainboard_only"
        )
        candidate_identity = capture_pretrade_candidate_identity(
            conn, target_date=REPORT_DATE
        )
    qualification = build_completed_pretrade_qualification(
        producer_result={
            "status": "completed",
            "run_id": pretrade["run_id"],
            "snapshot_as_of_date": REPORT_DATE,
            "stock_candidate_policy": "mainboard_only",
            "rule_version": pretrade["result"]["pretrade_qualification"][
                "rule_identity"
            ]["candidate_rule_version"],
            "strategy_payload_sha256": canonical_pretrade_output_sha256(
                {"fixture": "strategy"}
            ),
            "candidate_history_sha256": candidate_identity,
            "row_count": 1,
        },
        input_snapshot_before=input_snapshot,
        input_snapshot_after=input_snapshot,
        confluence_payload={
            "status": "completed",
            "canonical_output_sha256": canonical_pretrade_output_sha256(
                {"fixture": "confluence"}
            ),
        },
        export_payload={"as_of_date": REPORT_DATE, "fixture": "export"},
        rule_identity=pretrade["result"]["pretrade_qualification"]["rule_identity"],
    )
    pretrade["result"]["pretrade_qualification"] = qualification
    payload["pretrade_availability"] = qualification
    payload["source_cut"] = market_publication._capture_source_cut(settings, payload)
    receipt_path = tmp_path / "market-aggregate.json"
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")
    return settings, first, payload, receipt_path


def test_market_adapter_publishes_real_full_generation_and_preserves_pnl(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, first, _payload, receipt_path = _prepare_real_market_publication(
        tmp_path, monkeypatch
    )
    first_resolved = resolve_system_read_publication(settings, first.generation)
    first_bundle = first_resolved.manifest["sealed_payload"]["system_read_bundle"]

    publication = market_publication.publish_aggregate(
        settings,
        receipt_path=receipt_path,
        run_id=RUN_ID,
        report_date=REPORT_DATE,
    )

    pointer = read_publication_pointer(
        system_read_publication_root(settings), require_valid=True
    )
    assert pointer is not None
    assert pointer["generation"] == publication["generation"]
    resolved = resolve_system_read_publication(settings, publication["generation"])
    bundle = resolved.manifest["sealed_payload"]["system_read_bundle"]
    assert bundle["writer_run_id"] == RUN_ID
    assert bundle["workflow"] == "market_daily"
    assert bundle["data_update_run_id"] is None
    assert bundle["global_run_id"] is None
    assert bundle["pnl_generation"] == first_bundle["pnl_generation"]
    assert bundle["pnl_manifest_sha256"] == first_bundle["pnl_manifest_sha256"]
    with system_read_scope(settings, publication["generation"]):
        context = current_system_read_context()
        assert context is not None
        qualified = qualify_sealed_pretrade_read(
            evidence=context.pretrade_availability,
            target_date=REPORT_DATE,
            stock_candidate_policy="mainboard_only",
        )
        assert qualified["status"] == "ready"
    assert {
        (item["run_id"], item["cache_key"], item["report_date"])
        for item in bundle["terminal_references"]
    } >= {("choice-run", "choice-stock:daily", REPORT_DATE)}
    with duckdb.connect(str(resolved.database_path), read_only=True) as conn:
        assert conn.execute(
            "select count(*) from choice_stock_daily_observation"
        ).fetchone() == (1,)
        assert conn.execute(
            "select count(*) from fact_choice_macro_daily"
        ).fetchone() == (3,)
        assert conn.execute(
            "select payload_sha256 from fact_pnl_by_business_page_envelope "
            "where report_date = ?",
            [REPORT_DATE],
        ).fetchone() == ("payload-current",)
    assert json.loads(receipt_path.read_text(encoding="utf-8"))["status"] == "completed"


def test_market_adapter_rejects_external_source_change_after_full_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, first, payload, receipt_path = _prepare_real_market_publication(
        tmp_path, monkeypatch
    )
    choice = next(
        child
        for child in payload["children"]
        if child["name"] == "choice_stock_daily_refresh"
    )
    external_receipt = choice["external_receipt"]
    assert isinstance(external_receipt, dict)
    external_path = tmp_path / "choice-external-receipt.json"
    external_path.write_text(json.dumps(external_receipt), encoding="utf-8")
    choice["external_receipt_path"] = str(external_path.resolve())
    choice["external_receipt_sha256"] = market_publication._sha256_bytes(
        market_publication._canonical_bytes(external_receipt)
    )
    payload["source_cut"] = market_publication._capture_source_cut(settings, payload)
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")
    pointer_before = read_publication_pointer(
        system_read_publication_root(settings), require_valid=True
    )
    real_publish = system_read_publication.publish_financial_result
    observed_stages: list[str] = []

    def publish_with_source_change(**kwargs: object):
        original_stage = kwargs.get("on_stage")

        def on_stage(stage: str) -> None:
            if callable(original_stage):
                original_stage(stage)
            observed_stages.append(stage)
            if stage == "candidate_sealed":
                external_path.write_text(
                    json.dumps(
                        {**external_receipt, "warnings": ["changed after copy"]}
                    ),
                    encoding="utf-8",
                )

        return real_publish(**{**kwargs, "on_stage": on_stage})

    monkeypatch.setattr(
        system_read_publication,
        "publish_financial_result",
        publish_with_source_change,
    )

    with pytest.raises(FinancialPublicationInvalid, match="changed after completion"):
        market_publication.publish_aggregate(
            settings,
            receipt_path=receipt_path,
            run_id=RUN_ID,
            report_date=REPORT_DATE,
        )

    assert "candidate_sealed" in observed_stages
    assert (
        read_publication_pointer(
            system_read_publication_root(settings), require_valid=True
        )
        == pointer_before
    )
    assert resolve_system_read_publication(settings).generation == first.generation
    assert (
        json.loads(receipt_path.read_text(encoding="utf-8"))["status"]
        == "publication_failed"
    )


def test_sealed_existing_rows_do_not_authorize_pretrade_without_producer_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real full snapshot cannot turn legacy candidate rows into attestation."""
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    monkeypatch.setattr(
        "backend.app.tasks.pnl_by_business_page_publication."
        "require_current_pnl_by_business_governance",
        lambda *_args, **_kwargs: None,
    )
    _isolate_only_unrelated_financial_fixture_domains(monkeypatch)
    _forbid_source_ingest_and_financial_replay(monkeypatch)
    settings = _bootstrap_settings_and_run(tmp_path)
    _build_synthetic_db(Path(settings.duckdb_path))
    publication = publish_qualified_system_read_bootstrap(
        settings,
        data_update_run_id="data-update-run",
        required_date_tables=(
            ("fact_result", "report_date", 1),
            ("phase1_source_preview_summary", "report_date", 2),
        ),
    )

    with system_read_scope(settings, publication.generation):
        envelope = pretrade_checklist_envelope(
            duckdb_path=settings.duckdb_path,
            as_of_date=AS_OF,
            today=TODAY_FRESH,
        )

    assert envelope is not None
    result = envelope["result"]
    assert result["as_of_date"] == AS_OF
    assert result["checklist_status"] == "unavailable"
    assert result["qualification"]["status"] == "unavailable"
    assert result["items"] == []
    assert result["position_size_hint"] is None
    assert envelope["result_meta"]["formal_use_allowed"] is False


@pytest.mark.parametrize("empty_result", [False, True])
def test_sealed_checklist_reader_recovers_qualified_fixture_ready_and_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, empty_result: bool
) -> None:
    """Test real sealing and API projection, not the independent producer contract."""
    from importlib import import_module

    from backend.app.agent.schemas.agent_request import AgentQueryRequest
    from backend.app.governance.settings import get_settings
    from backend.app.repositories.system_read_publication_repo import (
        current_system_read_context as selected_pretrade_context,
        system_read_scope as selected_pretrade_scope,
    )
    from backend.app.services.agent_service import _pretrade_checklist_payload

    pretrade_checklist_service = import_module(
        "backend.app.services.pretrade_checklist_service"
    )

    # Other tests reload these modules separately. Use the same real context as
    # the Agent's deferred imports, without replacing qualification or outputs.
    monkeypatch.setattr(
        pretrade_checklist_service,
        "current_system_read_context",
        selected_pretrade_context,
    )
    checklist_envelope = pretrade_checklist_service.pretrade_checklist_envelope
    initial_context = selected_pretrade_context()

    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    monkeypatch.setattr(
        "backend.app.tasks.pnl_by_business_page_publication."
        "require_current_pnl_by_business_governance",
        lambda *_args, **_kwargs: None,
    )
    _isolate_only_unrelated_financial_fixture_domains(monkeypatch)
    _forbid_source_ingest_and_financial_replay(monkeypatch)
    settings = _bootstrap_settings_and_run(tmp_path)
    settings.choice_stock_catalog_file = get_settings().choice_stock_catalog_file
    monkeypatch.setattr(
        "backend.app.governance.settings.get_settings", lambda: settings
    )
    source = Path(settings.duckdb_path)
    _build_synthetic_db(source)
    _add_required_source_inputs(source)
    if empty_result:
        with duckdb.connect(str(source)) as conn:
            conn.execute("delete from livermore_candidate_history")
    first = publish_qualified_system_read_bootstrap(
        settings,
        data_update_run_id="data-update-run",
        required_date_tables=(
            ("fact_result", "report_date", 1),
            ("phase1_source_preview_summary", "report_date", 2),
        ),
    )
    with selected_pretrade_scope(settings, first.generation):
        first_context = selected_pretrade_context()
        assert first_context is not None
        assert first_context.generation == first.generation
        unavailable = checklist_envelope(
            duckdb_path=settings.duckdb_path, as_of_date=AS_OF, today=TODAY_FRESH
        )
    assert selected_pretrade_context() is initial_context
    assert unavailable["result"]["checklist_status"] == "unavailable"

    def agent_request(generation: str) -> AgentQueryRequest:
        return AgentQueryRequest(
            question="今天盘前该做什么",
            filters={"as_of_date": AS_OF},
            page_context={
                "page_id": "GAP-STOCK-ANALYSIS-PAGE",
                "current_filters": {
                    "system_read_generation": generation,
                    # Caller metadata is not authority, even when it says ready.
                    "pretrade_qualification_status": "ready",
                },
            },
        )

    unavailable_agent = _pretrade_checklist_payload(
        agent_request(first.generation), settings.duckdb_path
    )
    assert "盘前操作清单不可用" in unavailable_agent["answer"]
    assert unavailable_agent["row_count"] == 0
    assert unavailable_agent["formal_use_allowed"] is False
    assert not any(card["type"] == "table" for card in unavailable_agent["cards"])
    evidence = _completed_evidence(source, empty_result=empty_result)
    run_id = "synthetic-reader-completion-fixture"

    def source_identity(conn: duckdb.DuckDBPyConnection) -> dict[str, str]:
        return {
            "candidate_identity": capture_pretrade_candidate_identity(
                conn, target_date=AS_OF
            ),
            "input_identity": capture_pretrade_input_snapshot(
                conn,
                target_date=AS_OF,
                stock_candidate_policy=evidence["stock_candidate_policy"],
            )["sha256"],
        }

    completed = system_read_publication.publish_preserved_system_read_generation(
        settings,
        writer_run_id=run_id,
        workflow="market_daily",
        report_date=AS_OF,
        writer_receipt={
            "status": "completed",
            "run_id": run_id,
            "workflow": "market_daily",
            "report_date": AS_OF,
        },
        changed_table_coverage=(("choice_stock_universe", "as_of_date", AS_OF, 1),),
        changed_source_validator=source_identity,
        pretrade_availability=evidence,
    )
    with selected_pretrade_scope(settings, completed.generation):
        completed_context = selected_pretrade_context()
        assert completed_context is not None
        assert completed_context.generation == completed.generation
        assert completed_context.pretrade_availability["evidence_sha256"] == (
            evidence["evidence_sha256"]
        )
        sealed_artifacts_before = {
            path: path.read_bytes()
            for path in (
                completed_context.publication.manifest_path,
                completed_context.publication.database_path,
            )
        }
        envelope = checklist_envelope(
            duckdb_path=settings.duckdb_path, today=TODAY_FRESH
        )
    assert selected_pretrade_context() is initial_context
    assert envelope is not None
    result = envelope["result"]
    assert result["qualification"]["status"] == (
        "ready_empty" if empty_result else "ready"
    )
    assert result["checklist_status"] == ("empty" if empty_result else "ok")
    assert result["qualification"]["evidence_sha256"] == evidence["evidence_sha256"]
    assert bool(result["items"]) is (not empty_result)
    assert envelope["result_meta"]["formal_use_allowed"] is False
    completed_agent = _pretrade_checklist_payload(
        agent_request(completed.generation), settings.duckdb_path
    )
    assert "盘前操作清单不可用" not in completed_agent["answer"]
    assert completed_agent["row_count"] == len(result["items"])
    assert (
        completed_agent["filters_applied"]["system_read_generation"]
        == completed.generation
    )
    assert completed_agent["formal_use_allowed"] is False
    if empty_result:
        assert completed_agent["filters_applied"]["checklist_status"] == "empty"
        assert not any(card["type"] == "table" for card in completed_agent["cards"])

    forged_agent = _pretrade_checklist_payload(
        agent_request("system-read-2026-08-07-00000000000000000000"),
        settings.duckdb_path,
    )
    assert "盘前操作清单不可用" in forged_agent["answer"]
    assert forged_agent["row_count"] == 0
    assert not any(card["type"] == "table" for card in forged_agent["cards"])
    assert selected_pretrade_context() is initial_context
    assert {
        path: path.read_bytes() for path in sealed_artifacts_before
    } == sealed_artifacts_before


def _complete_weekend_aggregate(
    settings: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[str, str, Path]:
    """Exercise the scheduler receipt API without running any external vendor."""
    weekend = "2026-09-19"
    run_id = f"market-daily:{weekend}:independent-fixture"
    receipt_path = tmp_path / "weekend-aggregate.json"
    monkeypatch.setattr(market_publication, "_now", lambda: f"{weekend}T12:00:00+00:00")
    market_publication.begin_aggregate(
        receipt_path=receipt_path, run_id=run_id, report_date=weekend
    )
    choice_result = {
        "status": "skipped_non_trading_day",
        "as_of_date": weekend,
        "as_of_date_explicit": False,
        "no_write": True,
        "database_write_scope": [],
        "governance_write_scope": [],
    }
    independent_results = {
        "choice_stock_daily_refresh": choice_result,
        "macro_toolkit_freshness": {
            "status": "success",
            "report_date": weekend,
            "steps": [
                {"step": step, "status": "success"}
                for step in sorted(market_publication._EXPECTED_FRESHNESS_STEPS)
            ],
            "latest_observation_dates": {
                "fact_commodity_futures_daily": weekend,
                "fact_cffex_member_rank_daily": REPORT_DATE,
            },
        },
        "tushare_news_backup": {
            "status": "completed",
            "inserted": 1,
            "purged_expired": 0,
            "purged_expired_warehouse": 0,
        },
        "macro_toolkit_daily_chain": {
            "status": "completed",
            "chain": {
                "readiness_after": {
                    "observation_only": True,
                    "formal_use_allowed": False,
                }
            },
        },
    }
    upstream_name = "choice_stock_daily_refresh"
    upstream_run_id = f"{run_id}:{upstream_name}:child"
    upstream_status = "skipped_non_trading_day"
    for child_name in market_publication.REQUIRED_CHILDREN:
        if child_name not in independent_results:
            child_run_id = f"{run_id}:{child_name}:not-executed"
            market_publication.skip_child(
                receipt_path=receipt_path,
                run_id=run_id,
                report_date=weekend,
                child_name=child_name,
                child_run_id=child_run_id,
                reason="Direct prerequisite performed no trading-day write.",
                upstream_child_name=upstream_name,
                upstream_child_run_id=upstream_run_id,
                upstream_status=upstream_status,
            )
            upstream_name = child_name
            upstream_run_id = child_run_id
            upstream_status = "not_executed"
            continue
        result = independent_results[child_name]
        child_run_id = f"{run_id}:{child_name}:child"
        market_publication.start_child(
            receipt_path=receipt_path,
            run_id=run_id,
            report_date=weekend,
            child_name=child_name,
            child_run_id=child_run_id,
        )
        output_path = tmp_path / f"{child_name}-stdout.json"
        output_path.write_text(json.dumps(result), encoding="utf-8")
        external_path = None
        if child_name != "tushare_news_backup":
            external_path = tmp_path / f"{child_name}-receipt.json"
            external_path.write_text(
                json.dumps(
                    {
                        "status": result["status"],
                        "generated_at": market_publication._now(),
                        "warnings": [],
                        "result": result,
                    }
                ),
                encoding="utf-8",
            )
        market_publication.finish_child(
            receipt_path=receipt_path,
            run_id=run_id,
            report_date=weekend,
            child_name=child_name,
            child_run_id=child_run_id,
            exit_code=0,
            output_path=output_path,
            external_receipt_path=external_path,
        )
    market_publication.complete_business(
        settings, receipt_path=receipt_path, run_id=run_id, report_date=weekend
    )
    return weekend, run_id, receipt_path


def test_weekend_independent_publication_seals_unavailable_pretrade_without_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, _bootstrap, _payload, weekday_receipt = _prepare_real_market_publication(
        tmp_path, monkeypatch
    )
    source = Path(settings.duckdb_path)
    first = market_publication.publish_aggregate(
        settings, receipt_path=weekday_receipt, run_id=RUN_ID, report_date=REPORT_DATE
    )
    first_resolved = resolve_system_read_publication(settings)
    first_bundle = first_resolved.manifest["sealed_payload"]["system_read_bundle"]
    assert first_bundle["pretrade_availability"]["status"] == "ready"
    # Qualified prior rows predate this weekend; only independent facts change.
    with duckdb.connect(str(source)) as conn:
        conn.execute(
            "insert into fact_commodity_futures_daily values "
            "('2026-09-19', 2, 'weekend-independent-fixture')"
        )
        conn.execute(
            "insert into fact_choice_macro_daily values "
            "('2026-09-19', 'CA.CSI300', 2.0, 'weekend-independent-fixture')"
        )
        conn.execute(
            "insert into choice_news_event values "
            "('2026-09-19 11:59:00', 'independent update', 'weekend-news-fixture')"
        )
        conn.execute(
            "insert into fact_news_event values "
            "('2026-09-19 11:59:00', 'independent update', 'weekend-news-fixture')"
        )
    weekend, run_id, receipt_path = _complete_weekend_aggregate(
        settings, tmp_path, monkeypatch
    )
    result = market_publication.publish_aggregate(
        settings, receipt_path=receipt_path, run_id=run_id, report_date=weekend
    )
    assert result["generation"] != first["generation"]
    resolved = resolve_system_read_publication(settings)
    bundle = resolved.manifest["sealed_payload"]["system_read_bundle"]
    assert bundle["pretrade_availability"]["status"] == "unavailable"
    assert bundle["pnl_generation"] == first_bundle["pnl_generation"]
    assert bundle["pnl_manifest_sha256"] == first_bundle["pnl_manifest_sha256"]
    with duckdb.connect(str(resolved.database_path), read_only=True) as conn:
        assert conn.execute("select count(*) from choice_news_event").fetchone() == (2,)
        assert conn.execute(
            "select count(*) from fact_choice_macro_daily"
        ).fetchone() == (4,)
        assert conn.execute(
            "select count(*) from choice_stock_daily_observation"
        ).fetchone() == (1,)
    with system_read_scope(settings, resolved.generation):
        envelope = pretrade_checklist_envelope(
            duckdb_path=settings.duckdb_path, as_of_date=weekend, today=weekend
        )
    assert envelope["result"]["checklist_status"] == "unavailable"
    assert envelope["result"]["items"] == []
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "completed"
    source_before_resume = source.stat()

    def forbid_republication(*_args: object, **_kwargs: object) -> None:
        pytest.fail("A completed matching aggregate must not re-run publication.")

    monkeypatch.setattr(market_publication, "publish_aggregate", forbid_republication)
    with pytest.raises(FinancialPublicationInvalid, match="not recoverable"):
        market_publication.recover_or_publish(
            settings, receipt_path=receipt_path, run_id=run_id, report_date=weekend
        )
    assert resolve_system_read_publication(settings).generation == resolved.generation
    assert (
        json.loads(receipt_path.read_text(encoding="utf-8"))["children"]
        == receipt["children"]
    )
    assert source.stat().st_size == source_before_resume.st_size
    assert source.stat().st_mtime_ns == source_before_resume.st_mtime_ns

    preserved = system_read_publication.publish_preserved_system_read_generation(
        settings,
        writer_run_id="balance-after-weekend-fixture",
        data_update_run_id="balance-after-weekend-fixture",
        workflow="balance_daily",
        report_date=REPORT_DATE,
        writer_receipt={
            "status": "completed",
            "run_id": "balance-after-weekend-fixture",
            "workflow": "balance_daily",
            "report_date": REPORT_DATE,
        },
        changed_table_coverage=(("fact_result", "report_date", REPORT_DATE, 1),),
    )
    balance_bundle = resolve_system_read_publication(
        settings, preserved.generation
    ).manifest["sealed_payload"]["system_read_bundle"]
    assert balance_bundle["pretrade_availability"] == bundle["pretrade_availability"]
    lineage_run_ids = {
        item["cache_key"]: item["run_id"]
        for item in first_bundle["terminal_references"]
    }
    core_steps = tuple(
        {
            **step,
            "result": {
                **step["result"],
                **(
                    {"run_id": lineage_run_ids[step["result"]["cache_key"]]}
                    if "cache_key" in step["result"]
                    else {}
                ),
            },
        }
        for step in _core_step_receipts()
    )
    core_arguments = {
        "report_date": REPORT_DATE,
        "data_update_run_id": "core-after-weekend-fixture",
        "global_run_id": "global-after-weekend-fixture",
        "step_receipts": core_steps,
        "pnl_generation": first_bundle["pnl_generation"],
        "pnl_manifest_sha256": first_bundle["pnl_manifest_sha256"],
        "required_date_tables": (
            ("fact_result", "report_date", 1),
            ("phase1_source_preview_summary", "report_date", 2),
        ),
    }
    # Simulate a core preflight that captured ready before the weekend writer won.
    # The real under-lock check must reject that stale qualification/pointer pair.
    with monkeypatch.context() as stale_context:
        stale_context.setattr(
            system_read_publication,
            "_current_system_bundle",
            lambda _root: (
                first_bundle,
                (first_resolved.generation, first_resolved.manifest_sha256),
            ),
        )
        with pytest.raises(
            FinancialPublicationInvalid, match="generation changed before publication"
        ):
            system_read_publication.publish_system_read_generation(
                settings, **core_arguments
            )
    assert resolve_system_read_publication(settings).generation == preserved.generation
    core = system_read_publication.publish_system_read_generation(
        settings, **core_arguments
    )
    core_bundle = resolve_system_read_publication(settings, core.generation).manifest[
        "sealed_payload"
    ]["system_read_bundle"]
    assert core_bundle["pretrade_availability"] == bundle["pretrade_availability"]
    assert core_bundle["pnl_generation"] == first_bundle["pnl_generation"]
    assert core_bundle["pnl_manifest_sha256"] == first_bundle["pnl_manifest_sha256"]
