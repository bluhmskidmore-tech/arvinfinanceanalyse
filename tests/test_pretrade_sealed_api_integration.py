from __future__ import annotations

import copy
import json
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.app.tasks.system_read_market_publication as market_publication
from backend.app.api.routes import market_data_livermore as livermore_route
from backend.app.governance.settings import get_settings
from backend.app.main import SystemReadPublicationMiddleware
from backend.app.observability.response_cache import market_home_response_cache
from backend.app.repositories.duckdb_migrations import _run_sql_slice
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.repositories.system_read_publication_repo import (
    SYSTEM_READ_GENERATION_HEADER,
    resolve_system_read_publication,
    system_read_scope,
)
from backend.app.repositories.user_scope_repo import UserScopeRepository
from backend.app.services import (
    livermore_signal_confluence_service as confluence_service,
)
from backend.app.services import livermore_candidate_history_service as history_service
from backend.app.tasks.system_read_publication import (
    publish_qualified_system_read_bootstrap,
)
from scripts.run_livermore_daily_pretrade_refresh import (
    run_livermore_daily_pretrade_refresh,
)
from tests.test_pretrade_producer_full_integration import (
    TARGET_DATE,
    _seed_actual_pretrade_database,
    _write_confirmed_choice_catalog,
)
from tests.test_system_read_market_publication import (
    REPORT_DATE,
    RUN_ID,
    _aggregate,
)
from tests.test_system_read_market_publication_integration import (
    _isolate_only_unrelated_financial_fixture_domains,
)
from tests.test_system_read_publication import (
    _bootstrap_settings_and_run,
    _forbid_source_ingest_and_financial_replay,
)


pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_livermore,
    pytest.mark.surface_market_data,
]


@pytest.fixture(autouse=True)
def _clear_process_caches() -> object:
    market_home_response_cache.invalidate()
    get_settings.cache_clear()
    yield
    market_home_response_cache.invalidate()
    get_settings.cache_clear()


def _append_actual_choice_terminal(settings: object) -> None:
    repository = GovernanceRepository(
        base_dir=Path(settings.governance_path),
        backend_mode="jsonl",
    )
    repository.append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "choice-run",
            "job_name": "choice-stock-daily-sealed-api-fixture",
            "cache_key": "choice-stock:daily",
            "status": "completed",
            "report_date": TARGET_DATE,
            "source_version": "sv_synthetic_target",
        },
    )
    repository.append(
        CACHE_MANIFEST_STREAM,
        {
            "run_id": "choice-run",
            "cache_key": "choice-stock:daily",
            "report_date": TARGET_DATE,
            "source_version": "sv_synthetic_target",
            "fact_tables": ["choice_stock_daily_observation"],
            "input_sources": ["choice_stock_daily_observation"],
        },
    )


def _append_remaining_market_facts(path: Path) -> None:
    with duckdb.connect(str(path)) as conn:
        conn.execute(
            "update choice_stock_daily_observation "
            "set source_version = 'sv_synthetic_target'"
        )
        _run_sql_slice(conn, "21_choice_stock.sql")
        conn.execute(
            "insert into choice_stock_concept_membership "
            "(as_of_date, stock_code, concept_code, concept_name, concept_source, "
            "field_key, source_version, vendor_version, rule_version, run_id) "
            "values (?, '000003.SZ', 'synthetic-concept', 'Synthetic Concept', 'choice', "
            "'concept_membership', 'choice_stock_concept_membership-synthetic-v1', "
            "'vv_synthetic_concept', 'rv_synthetic_concept', 'synthetic-concept-run')",
            [TARGET_DATE],
        )
        conn.execute(
            "insert into choice_stock_intraday_movement_event "
            "(as_of_date, event_time, stock_code, stock_name, concept_code, concept_name, "
            "event_type, event_title, pctchange, turn, field_key, raw_json, "
            "source_version, vendor_version, rule_version, run_id) "
            "values (?, '12:00:00', '000003.SZ', 'Synthetic Other Stock', "
            "'synthetic-concept', 'Synthetic Concept', 'synthetic_observation', "
            "'Synthetic neutral observation', 0.0, 0.0, 'intraday_movement', '{}', "
            "'choice_stock_intraday_movement_event-synthetic-v1', "
            "'vv_synthetic_movement', 'rv_synthetic_movement', 'synthetic-movement-run')",
            [TARGET_DATE],
        )
        for table_name, date_column in (
            ("stock_limit_price_daily", "trade_date"),
            ("fact_commodity_futures_daily", "trade_date"),
            ("fact_cffex_member_rank_daily", "trade_date"),
        ):
            conn.execute(
                f'create table if not exists "{table_name}"('
                f'"{date_column}" date, value integer, source_version varchar)'
            )
            conn.execute(
                f'insert into "{table_name}" values (?, 1, ?)',
                [TARGET_DATE, f"{table_name}-synthetic-v1"],
            )
        conn.execute(
            "create table choice_news_event("
            "received_at timestamp, headline varchar, source_version varchar)"
        )
        conn.execute(
            "insert into choice_news_event values "
            "(?, 'sealed API synthetic news', 'news-synthetic-v1')",
            [f"{TARGET_DATE} 12:00:00"],
        )
        conn.execute(
            "create table fact_news_event("
            "pub_time timestamp, headline varchar, source_version varchar)"
        )
        conn.execute(
            "insert into fact_news_event values "
            "(?, 'sealed API synthetic news', 'news-synthetic-v1')",
            [f"{TARGET_DATE} 12:00:00"],
        )


def _drop_bootstrap_market_placeholders(path: Path) -> None:
    table_names = (
        "choice_stock_request_audit",
        "choice_stock_universe",
        "choice_stock_sector_membership",
        "choice_stock_daily_observation",
        "choice_stock_limit_quality",
        "choice_stock_factor_snapshot",
        "choice_stock_concept_membership",
        "choice_stock_intraday_movement_event",
        "stock_adjustment_factor",
        "stock_limit_price_daily",
        "fact_livermore_gate_supplement_daily",
        "fact_choice_macro_daily",
        "choice_market_snapshot",
        "livermore_monitor_append",
        "livermore_gate_history",
        "livermore_position_snapshot",
        "livermore_candidate_history",
        "livermore_stock_candidate_universe_history",
        "livermore_candidate_execution_history",
    )
    with duckdb.connect(str(path)) as conn:
        for table_name in table_names:
            conn.execute(f'drop table if exists "{table_name}"')


def _replace_fixture_identity(value: object, *, run_id: str) -> object:
    if isinstance(value, dict):
        return {
            key: _replace_fixture_identity(item, run_id=run_id)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_replace_fixture_identity(item, run_id=run_id) for item in value]
    if isinstance(value, str):
        return value.replace(REPORT_DATE, TARGET_DATE).replace(RUN_ID, run_id)
    return value


def _complete_actual_aggregate(
    settings: object,
    *,
    tmp_path: Path,
    run_id: str,
    producer_result: dict[str, object],
) -> Path:
    receipt_path = tmp_path / f"{run_id.replace(':', '-')}.json"
    market_publication.begin_aggregate(
        receipt_path=receipt_path,
        run_id=run_id,
        report_date=TARGET_DATE,
    )
    template = _replace_fixture_identity(_aggregate(), run_id=run_id)
    assert isinstance(template, dict)
    template_children = {
        str(item["name"]): item
        for item in template["children"]
        if isinstance(item, dict)
    }
    for child_name in market_publication.REQUIRED_CHILDREN:
        child_run_id = f"{run_id}:{child_name}:child"
        market_publication.start_child(
            receipt_path=receipt_path,
            run_id=run_id,
            report_date=TARGET_DATE,
            child_name=child_name,
            child_run_id=child_run_id,
        )
        template_child = template_children[child_name]
        result = (
            producer_result
            if child_name == "livermore_pretrade_candidates"
            else copy.deepcopy(template_child["result"])
        )
        if child_name == "choice_stock_daily_refresh":
            assert isinstance(result, dict)
            result["history_start_date"] = (
                date.fromisoformat(TARGET_DATE) - timedelta(days=129)
            ).isoformat()
        output_path = tmp_path / f"{child_name}-{run_id[-8:]}.json"
        output_path.write_text(
            json.dumps(result, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        external = copy.deepcopy(template_child.get("external_receipt"))
        external_path: Path | None = None
        if isinstance(external, dict) and child_name != "livermore_pretrade_candidates":
            external["result"] = result
            if child_name == "stock_limit_price_daily_refresh":
                external["run_id"] = child_run_id
            external_path = tmp_path / f"{child_name}-{run_id[-8:]}-receipt.json"
            external_path.write_text(
                json.dumps(external, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        market_publication.finish_child(
            receipt_path=receipt_path,
            run_id=run_id,
            report_date=TARGET_DATE,
            child_name=child_name,
            child_run_id=child_run_id,
            exit_code=0,
            output_path=output_path,
            external_receipt_path=external_path,
        )
    market_publication.complete_business(
        settings,
        receipt_path=receipt_path,
        run_id=run_id,
        report_date=TARGET_DATE,
    )
    return receipt_path


def _configure_actual_external_inputs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    catalog_path: Path,
) -> None:
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


def _test_app(settings: object) -> TestClient:
    app = FastAPI()
    app.include_router(livermore_route.router)
    app.add_middleware(
        SystemReadPublicationMiddleware,
        settings_provider=lambda: settings,
    )
    app.dependency_overrides[livermore_route.get_auth_context] = lambda: (
        livermore_route.AuthContext(
            user_id="sealed-api-test",
            role="viewer",
            identity_source="test",
            client_host="127.0.0.1",
        )
    )
    return TestClient(app)


@pytest.mark.parametrize(
    ("ready_candidate", "expected_status"),
    [(True, "ready"), (False, "ready_empty")],
    ids=("ready", "ready-empty"),
)
def test_actual_producer_evidence_survives_publication_and_public_api_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ready_candidate: bool,
    expected_status: str,
) -> None:
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    monkeypatch.setattr(
        "backend.app.tasks.pnl_by_business_page_publication."
        "require_current_pnl_by_business_governance",
        lambda *_args, **_kwargs: None,
    )
    _isolate_only_unrelated_financial_fixture_domains(monkeypatch)
    _forbid_source_ingest_and_financial_replay(monkeypatch)
    bootstrap_settings = _bootstrap_settings_and_run(tmp_path)
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(bootstrap_settings.governance_path))
    source = Path(bootstrap_settings.duckdb_path)
    catalog_path = tmp_path / "synthetic-choice-catalog.json"
    _write_confirmed_choice_catalog(catalog_path)
    auth_dsn = f"sqlite:///{(tmp_path / 'auth-scope.db').as_posix()}"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", auth_dsn)
    monkeypatch.setenv("MOSS_GOVERNANCE_SQL_DSN", auth_dsn)
    _configure_actual_external_inputs(monkeypatch, catalog_path=catalog_path)
    settings = get_settings().model_copy(
        update={
            "duckdb_path": str(source),
            "governance_path": Path(bootstrap_settings.governance_path),
            "financial_publication_root": bootstrap_settings.financial_publication_root,
            "system_read_publication_enabled": True,
            "local_archive_path": bootstrap_settings.local_archive_path,
            "choice_stock_catalog_file": catalog_path,
            "environment": "development",
            "governance_sql_dsn": auth_dsn,
            "postgres_dsn": auth_dsn,
        }
    )
    UserScopeRepository(auth_dsn).grant_scope(
        user_id="*",
        role=None,
        resource="market_data.livermore",
        action="read",
    )
    initial = publish_qualified_system_read_bootstrap(
        settings,
        data_update_run_id="data-update-run",
        required_date_tables=(
            ("fact_result", "report_date", 1),
            ("phase1_source_preview_summary", "report_date", 2),
        ),
    )
    _drop_bootstrap_market_placeholders(source)
    _seed_actual_pretrade_database(
        source,
        ready_candidate=ready_candidate,
    )
    _append_remaining_market_facts(source)

    producer_result = run_livermore_daily_pretrade_refresh(
        duckdb_path=source,
        target_date=TARGET_DATE,
        output_dir=tmp_path / "pretrade-output",
        stock_candidate_policy="exp3b",
        skip_upstream_probe=True,
        theme_overlay_mode="off",
        export_pretrade=True,
    )
    assert producer_result["status"] == "completed"
    producer_evidence = producer_result["pretrade_qualification"]
    assert producer_evidence["status"] == expected_status
    evidence_before_publication = copy.deepcopy(producer_evidence)
    _append_actual_choice_terminal(settings)
    monkeypatch.setattr(
        market_publication,
        "_now",
        lambda: f"{TARGET_DATE}T12:00:00+00:00",
    )
    run_id = f"market-daily:{TARGET_DATE}:sealed-api-{expected_status}"
    receipt_path = _complete_actual_aggregate(
        settings,
        tmp_path=tmp_path,
        run_id=run_id,
        producer_result=producer_result,
    )
    publication = market_publication.publish_aggregate(
        settings,
        receipt_path=receipt_path,
        run_id=run_id,
        report_date=TARGET_DATE,
    )
    assert publication["generation"] != initial.generation
    selected = resolve_system_read_publication(settings, publication["generation"])
    selected_bundle = selected.manifest["sealed_payload"]["system_read_bundle"]
    assert selected_bundle["pretrade_availability"] == evidence_before_publication
    assert producer_result["pretrade_qualification"] == evidence_before_publication
    if not ready_candidate:
        producer_step = next(
            step["result"] for step in producer_result["steps"]
            if step["name"] == "candidate_history"
        )
        frozen_streams = selected_bundle["governance_streams"]
        for stream in (CACHE_BUILD_RUN_STREAM, CACHE_MANIFEST_STREAM):
            matching_rows = [
                row for row in frozen_streams[stream]
                if row.get("run_id") == producer_step["run_id"]
            ]
            assert len(matching_rows) == 1
        # Removing live copies cannot cause a publication reader to seek new
        # evidence; the same completed receipt must be read from the seal.
        for stream in (CACHE_BUILD_RUN_STREAM, CACHE_MANIFEST_STREAM):
            (Path(settings.governance_path) / f"{stream}.jsonl").unlink()
        with system_read_scope(settings, generation=publication["generation"]):
            with duckdb.connect(str(selected.database_path), read_only=True) as conn:
                assert history_service._has_completed_zero_signal_receipt(
                    duckdb_path=str(source), trade_date=TARGET_DATE, conn=conn,
                )

    monkeypatch.setattr(livermore_route, "get_settings", lambda: settings)
    market_home_response_cache.invalidate()
    client = _test_app(settings)
    request_path = "/ui/market-data/stock-analysis/workbench"
    request_params = {"as_of_date": TARGET_DATE, "top_k": 10}
    first = client.get(request_path, params=request_params)
    assert first.status_code == 200
    assert first.headers[SYSTEM_READ_GENERATION_HEADER] == publication["generation"]
    assert 'cache;desc="produce"' in first.headers["server-timing"]
    assert first.json()["result_meta"]["formal_use_allowed"] is False
    first_result = first.json()["result"]
    assert first_result["formal_use_allowed"] is False
    assert first_result["pretrade_qualification"]["status"] == expected_status
    assert first_result["pretrade_qualification"]["evidence_sha256"] == (
        evidence_before_publication["evidence_sha256"]
    )
    first_queue = first_result["first_screen"]["review_queue"]
    first_can_review = first_result["decision_summary"]["can_review_candidates"]
    assert bool(first_queue) is ready_candidate
    assert first_can_review is False

    selected_headers = {SYSTEM_READ_GENERATION_HEADER: publication["generation"]}
    cached = client.get(
        request_path,
        params=request_params,
        headers=selected_headers,
    )
    assert cached.status_code == 200
    assert cached.headers[SYSTEM_READ_GENERATION_HEADER] == publication["generation"]
    assert 'cache;desc="hit"' in cached.headers["server-timing"]
    assert cached.json() == first.json()

    catalog_payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog_payload["catalog_version"] = "synthetic-pretrade-integration-mutated"
    catalog_path.write_text(
        json.dumps(catalog_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    changed = client.get(
        request_path,
        params=request_params,
        headers=selected_headers,
    )
    assert changed.status_code == 200
    assert changed.headers[SYSTEM_READ_GENERATION_HEADER] == publication["generation"]
    assert 'cache;desc="produce"' in changed.headers["server-timing"]
    changed_result = changed.json()["result"]
    assert changed_result["pretrade_qualification"] == {
        "schema": "pretrade_qualification/v1",
        "status": "unavailable",
        "reason": "pretrade_qualification_external_inputs_changed",
        "producer_run_id": None,
        "target_date": None,
        "stock_candidate_policy": None,
        "evidence_sha256": None,
        "input_snapshot_sha256": None,
        "attested_strategy_payload_sha256": None,
        "strategy_payload_sha256": changed_result["pretrade_qualification"][
            "strategy_payload_sha256"
        ],
        "workbench_projection_sha256": changed_result["pretrade_qualification"][
            "workbench_projection_sha256"
        ],
    }
    assert bool(changed_result["first_screen"]["review_queue"]) is ready_candidate
    assert changed_result["decision_summary"]["can_review_candidates"] is False
    selected_after_change = resolve_system_read_publication(
        settings, publication["generation"]
    )
    assert selected_after_change.manifest_sha256 == selected.manifest_sha256
    assert (
        selected_after_change.manifest["sealed_payload"]["system_read_bundle"][
            "pretrade_availability"
        ]
        == evidence_before_publication
    )
    assert producer_result["pretrade_qualification"] == evidence_before_publication
