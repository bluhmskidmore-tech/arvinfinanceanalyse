from __future__ import annotations

import json
import shutil
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.routes import balance_analysis as balance_routes
from backend.app.repositories.financial_result_publication_repo import (
    canonical_json_bytes,
    invalidate_financial_generation,
    open_financial_generation,
    sha256_bytes,
)
from backend.app.services import balance_analysis_publication_service as publication_reader
from backend.app.tasks.balance_analysis_overview_publication import (
    publish_balance_analysis_overview,
)
from tests.fixtures.balance_analysis import (
    balance_analysis_shared_materialized_read_seed as balance_analysis_shared_materialized_read_seed,
)
from tests.fixtures.balance_analysis import (
    balance_analysis_shared_materialized_seed,  # noqa: F401
)
from tests.test_balance_analysis_overview_publication import (
    _settings,
    _synthetic_sealed_overview,
)

pytestmark = [pytest.mark.integration, pytest.mark.materialize]


def _overview_only_dependencies(conn) -> dict[str, str]:
    rows = conn.execute(
        f"select distinct dependency_versions_json from {publication_reader.BALANCE_ANALYSIS_OVERVIEW_TABLE}"
    ).fetchall()
    assert len(rows) == 1
    return json.loads(rows[0][0])


def _basis_envelope(report_date: str = "2026-08-31") -> dict:
    return {
        "result_meta": {
            "trace_id": "basis-publication-test", "source_version": "sv-test",
            "rule_version": "rv-test", "cache_version": "cv-test",
            "filters_applied": {"report_date": report_date},
        },
        "result": {
            "report_date": report_date, "position_scope": "all",
            "currency_basis": "CNY", "rows": [],
        },
        "data_source": "balance_analysis_facts",
        "calibration": {
            "position_scope": "all", "currency_basis": "CNY",
            "source_families": ["zqtz", "tyw"], "tyw_amount_semantics": "synthetic",
            "data_basis": "formal_facts", "calibration_note": "synthetic",
        },
    }


def test_basis_explicit_generation_does_not_silently_read_live_facts(
    tmp_path: Path, monkeypatch,
) -> None:
    from backend.app.governance.settings import Settings

    settings = Settings(
        balance_analysis_publication_enabled=True,
        balance_analysis_publication_root=str(tmp_path / "missing-publication"),
    )
    monkeypatch.setattr(balance_routes, "get_settings", lambda: settings)
    monkeypatch.setattr(balance_routes, "_ensure_balance_analysis_read_allowed", lambda _auth: None)
    monkeypatch.setattr(
        balance_routes,
        "balance_analysis_basis_breakdown_envelope",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("live facts were read")),
    )
    app = FastAPI()
    app.include_router(balance_routes.router)
    response = TestClient(app, raise_server_exceptions=False).get(
        "/ui/balance-analysis/summary-by-basis",
        params={"report_date": "2026-08-31", "generation": "missing-generation"},
    )
    assert response.status_code == 409


def test_overview_only_generation_is_not_complete_portfolio_publication(
    tmp_path: Path, monkeypatch,
) -> None:
    settings, _generation = _synthetic_sealed_overview(
        monkeypatch,
        tmp_path,
        report_dates=["2025-12-31"],
        zqtz_versions=None,
        tyw_versions=None,
        with_basis=False,
    )
    status = publication_reader.balance_analysis_publication_status(settings)
    assert status["available"] is False
    assert status["report_dates"] == []
    assert "basis" in status["reason"]


def test_one_generation_seals_overview_and_basis_for_all_filters(
    tmp_path: Path, monkeypatch, balance_analysis_shared_materialized_read_seed,
) -> None:
    seed = balance_analysis_shared_materialized_read_seed
    settings = _settings(seed, tmp_path / "publication")
    before = (seed.duckdb_path.stat().st_size, seed.duckdb_path.stat().st_mtime_ns)
    receipt = publish_balance_analysis_overview(
        settings,
        report_date="2025-12-31",
        run_id="overview-with-basis",
        expected_previous_generation=None,
    )
    with open_financial_generation(
        Path(settings.balance_analysis_publication_root), generation=receipt.generation,
        reader_api_version=publication_reader.BALANCE_ANALYSIS_PUBLICATION_API_VERSION,
        reader_schema_version=publication_reader.BALANCE_ANALYSIS_PUBLICATION_SCHEMA_VERSION,
    ) as (conn, resolved):
        coverage = resolved.manifest["sealed_payload"]["coverage_dates"]
        assert coverage["balance_analysis_basis_breakdown"] == ["2025-12-31"]
        assert conn.execute("select count(*) from balance_analysis_basis_breakdown_envelope").fetchone() == (6,)

    # A sealed read must work even if the active fact database is unavailable.
    settings = settings.model_copy(update={"duckdb_path": tmp_path / "not-active.duckdb"})
    for scope in ("asset", "liability", "all"):
        for currency in ("native", "CNY"):
            arguments = {
                "report_date": "2025-12-31", "position_scope": scope,
                "currency_basis": currency, "generation": receipt.generation,
            }
            overview = publication_reader.read_published_balance_analysis_overview(settings, **arguments)
            basis = publication_reader.read_published_balance_analysis_basis_breakdown(settings, **arguments)
            for envelope in (overview.envelope, basis.envelope):
                filters = envelope["result_meta"]["filters_applied"]
                assert filters["generation"] == receipt.generation
                assert filters["manifest_sha256"] == receipt.manifest_sha256
                assert filters["serving_mode"] == "published"
                assert filters["report_date"] == "2025-12-31"
            for measure in ("market_value_amount", "amortized_cost_amount", "accrued_interest_amount"):
                assert sum(Decimal(row[measure]) for row in basis.envelope["result"]["rows"]) == Decimal(
                    overview.envelope["result"][f"total_{measure}"]
                )
            assert sum(row["detail_row_count"] for row in basis.envelope["result"]["rows"]) == overview.envelope["result"]["detail_row_count"]
    monkeypatch.setattr(balance_routes, "get_settings", lambda: settings)
    monkeypatch.setattr(balance_routes, "_ensure_balance_analysis_read_allowed", lambda _auth: None)
    app = FastAPI()
    app.include_router(balance_routes.router)
    client = TestClient(app)
    for route in ("overview", "summary-by-basis"):
        response = client.get(
            f"/ui/balance-analysis/{route}",
            params={"report_date": "2025-12-31", "generation": receipt.generation},
        )
        assert response.status_code == 200
        assert response.headers["X-Balance-Analysis-Generation"] == receipt.generation
        assert response.json()["result_meta"]["filters_applied"]["manifest_sha256"] == receipt.manifest_sha256

    invalidate_financial_generation(
        Path(settings.balance_analysis_publication_root),
        generation=receipt.generation, reason="test source replaced",
    )
    assert publication_reader.balance_analysis_publication_status(settings)["available"] is False
    for route in ("overview", "summary-by-basis"):
        response = client.get(
            f"/ui/balance-analysis/{route}",
            params={"report_date": "2025-12-31", "generation": receipt.generation},
        )
        assert response.status_code == 409
    assert not Path(settings.duckdb_path).exists()
    assert (seed.duckdb_path.stat().st_size, seed.duckdb_path.stat().st_mtime_ns) == before


def test_basis_legacy_consumer_keeps_live_read_without_generation(tmp_path: Path, monkeypatch) -> None:
    from backend.app.governance.settings import Settings

    monkeypatch.setattr(balance_routes, "get_settings", lambda: Settings(governance_path=tmp_path))
    monkeypatch.setattr(balance_routes, "_ensure_balance_analysis_read_allowed", lambda _auth: None)
    calls = []

    def live(**kwargs):
        calls.append(kwargs)
        return _basis_envelope()

    monkeypatch.setattr(balance_routes, "balance_analysis_basis_breakdown_envelope", live)
    app = FastAPI()
    app.include_router(balance_routes.router)
    client = TestClient(app)
    assert client.get("/ui/balance-analysis/summary-by-basis", params={"report_date": "2026-08-31"}).status_code == 200
    assert len(calls) == 1
    pinned = client.get(
        "/ui/balance-analysis/summary-by-basis",
        params={"report_date": "2026-08-31", "generation": "generation"},
    )
    assert pinned.status_code == 503
    assert len(calls) == 1


@pytest.mark.parametrize("contract_version", [None, "balance-analysis-portfolio/v1"])
def test_old_portfolio_contract_is_rejected_even_with_both_coverages(
    tmp_path: Path, monkeypatch, contract_version: str | None,
) -> None:
    settings, generation = _synthetic_sealed_overview(
        monkeypatch, tmp_path, report_dates=["2025-12-31"],
        zqtz_versions=None, tyw_versions=None,
    )
    resolved = publication_reader.resolve_financial_generation(None)
    dependencies = resolved.manifest["sealed_payload"]["dependency_versions"]
    if contract_version is None:
        dependencies.pop("balance.publication_contract_version")
    else:
        dependencies["balance.publication_contract_version"] = contract_version
    status = publication_reader.balance_analysis_publication_status(settings)
    assert status["available"] is False
    assert "contract version" in status["reason"]
    with pytest.raises(publication_reader.BalanceAnalysisPublicationConflict, match="contract version"):
        publication_reader.read_published_balance_analysis_overview(
            settings, report_date="2025-12-31", position_scope="all",
            currency_basis="CNY", generation=generation,
        )


def test_status_only_advertises_dates_covered_by_both_envelopes(tmp_path: Path, monkeypatch) -> None:
    settings, _generation = _synthetic_sealed_overview(
        monkeypatch, tmp_path, report_dates=["2025-11-30", "2025-12-31"],
        zqtz_versions=None, tyw_versions=None,
    )
    resolved = publication_reader.resolve_financial_generation(None)
    resolved.manifest["sealed_payload"]["coverage_dates"]["balance_analysis_basis_breakdown"] = ["2025-12-31"]
    assert publication_reader.balance_analysis_publication_status(settings)["report_dates"] == ["2025-12-31"]


@pytest.mark.parametrize("case", ["digest", "noncanonical", "shape", "report_date", "scope", "currency"])
def test_basis_payload_validation_rejects_corrupt_or_wrong_identity(case: str) -> None:
    envelope = _basis_envelope()
    if case == "shape":
        envelope["result"]["unexpected"] = 1
    elif case == "report_date":
        envelope["result"]["report_date"] = "2025-12-31"
    elif case == "scope":
        envelope["result"]["position_scope"] = "asset"
    elif case == "currency":
        envelope["result"]["currency_basis"] = "native"
    payload = json.dumps(envelope) if case == "noncanonical" else canonical_json_bytes(envelope).decode("utf-8")
    with pytest.raises(publication_reader.BalanceAnalysisPublicationConflict):
        publication_reader._validated_basis_breakdown_envelope(
            payload_json=payload,
            payload_sha256="wrong" if case == "digest" else sha256_bytes(payload.encode("utf-8")),
            report_date="2026-08-31", position_scope="all", currency_basis="CNY",
        )


def test_basis_quality_failure_prevents_publishing_partial_overview(
    tmp_path: Path, monkeypatch, balance_analysis_shared_materialized_read_seed,
) -> None:
    from backend.app.tasks import balance_analysis_overview_publication as task

    settings = _settings(balance_analysis_shared_materialized_read_seed, tmp_path / "publication")
    monkeypatch.setattr(
        task, "_balance_analysis_basis_breakdown_envelope_uncached",
        lambda **_kwargs: {"result_meta": {
            "basis": "formal", "formal_use_allowed": True,
            "quality_flag": "stale", "fallback_mode": "none",
        }},
    )
    with pytest.raises(task.BalanceAnalysisPublicationNotReady, match="basis_breakdown is not eligible"):
        task.publish_balance_analysis_overview(
            settings, report_date="2025-12-31", run_id="bad-basis-quality",
            expected_previous_generation=None,
        )
    assert not (Path(settings.balance_analysis_publication_root) / "current.json").exists()


def test_old_committed_attempt_upgrades_to_new_generation_and_stays_idempotent(
    tmp_path: Path, monkeypatch, balance_analysis_shared_materialized_read_seed,
) -> None:
    from backend.app.tasks import balance_analysis_overview_publication as task

    seed = balance_analysis_shared_materialized_read_seed
    governance_path = tmp_path / "governance"
    shutil.copytree(seed.governance_dir, governance_path)
    settings = _settings(seed, tmp_path / "publication").model_copy(
        update={"governance_path": governance_path}
    )
    monkeypatch.setattr(task, "get_settings", lambda: settings)
    original_dependencies = task._active_dependency_snapshot
    original_plan = task._build_publication_plan
    dependencies = original_dependencies(
        duckdb_path=seed.duckdb_path, governance_dir=str(governance_path),
        report_date="2025-12-31",
    )
    source_build_run_id = dependencies["balance.build.run_id"]

    def old_dependencies(**kwargs):
        versions = original_dependencies(**kwargs)
        versions.pop("balance.publication_contract_version")
        return versions

    def old_plan(**kwargs):
        preparation = dict(kwargs["prepare_receipt"])
        preparation["records"] = 6
        preparation["quality_checks"] = [
            check for check in preparation["quality_checks"] if check["name"].startswith("overview_")
        ]
        plan = original_plan(**{**kwargs, "prepare_receipt": preparation})
        return replace(
            plan,
            tables=tuple(spec for spec in plan.tables if spec.name == task.BALANCE_ANALYSIS_OVERVIEW_TABLE),
            coverage_dates={task.BALANCE_ANALYSIS_OVERVIEW_COVERAGE_KEY: ("2025-12-31",)},
            source_dependency_validator=_overview_only_dependencies,
        )

    # Persist a real old-contract generation and its attempt/commit receipts.
    # Only the isolated publisher inputs are adjusted; the shared publisher,
    # pointer CAS and governance ledger execute normally.
    with monkeypatch.context() as legacy:
        legacy.setattr(task, "_active_dependency_snapshot", old_dependencies)
        legacy.setattr(task, "_build_publication_plan", old_plan)
        legacy.setattr(
            task, "_publication_generation",
            lambda report_date, run_id: f"balance-overview-{report_date.replace('-', '')}-{sha256_bytes(run_id.encode('utf-8'))[:16]}",
        )
        previous = task.publish_balance_analysis_overview_actor.fn(
            report_date="2025-12-31", source_build_run_id=source_build_run_id,
        )
    assert previous["status"] == "completed"
    assert previous["publication_attempt"] == 1
    with open_financial_generation(
        Path(settings.balance_analysis_publication_root), generation=previous["generation"],
        reader_api_version=publication_reader.BALANCE_ANALYSIS_PUBLICATION_API_VERSION,
        reader_schema_version=publication_reader.BALANCE_ANALYSIS_PUBLICATION_SCHEMA_VERSION,
    ) as (_conn, old):
        old_bytes = old.database_path.read_bytes()
        assert "balance_analysis_basis_breakdown" not in old.manifest["sealed_payload"]["coverage_dates"]
    assert publication_reader.balance_analysis_publication_status(settings)["available"] is False

    upgraded = task.publish_balance_analysis_overview_actor.fn(
        report_date="2025-12-31", source_build_run_id=source_build_run_id,
    )
    assert upgraded["status"] == "completed"
    assert upgraded["publication_attempt"] == 2
    assert upgraded["generation"] != previous["generation"]
    assert upgraded["expected_previous_generation"] == previous["generation"]
    assert old.database_path.read_bytes() == old_bytes
    repeated = task.publish_balance_analysis_overview_actor.fn(
        report_date="2025-12-31", source_build_run_id=source_build_run_id,
    )
    assert repeated["generation"] == upgraded["generation"]
    assert repeated["publication_attempt"] == 2
    assert repeated["recovered_after_commit"] is True
    assert publication_reader.balance_analysis_publication_status(settings)["generation"] == upgraded["generation"]


def test_status_and_both_readers_reject_sealed_missing_basis_table(
    tmp_path: Path, monkeypatch, balance_analysis_shared_materialized_read_seed,
) -> None:
    from backend.app.tasks import balance_analysis_overview_publication as task

    settings = _settings(balance_analysis_shared_materialized_read_seed, tmp_path / "publication")
    original_plan = task._build_publication_plan

    def incomplete_plan(**kwargs):
        plan = original_plan(**kwargs)
        # Keep the v2 dependency and both coverage declarations, but seal only
        # the overview table to prove readiness checks inspect actual contents.
        return replace(
            plan,
            tables=tuple(spec for spec in plan.tables if spec.name == task.BALANCE_ANALYSIS_OVERVIEW_TABLE),
            source_dependency_validator=_overview_only_dependencies,
        )

    monkeypatch.setattr(task, "_build_publication_plan", incomplete_plan)
    receipt = task.publish_balance_analysis_overview(
        settings, report_date="2025-12-31", run_id="sealed-half-package",
        expected_previous_generation=None,
    )
    assert publication_reader.balance_analysis_publication_status(settings)["available"] is False
    for read in (
        publication_reader.read_published_balance_analysis_overview,
        publication_reader.read_published_balance_analysis_basis_breakdown,
    ):
        with pytest.raises(publication_reader.BalanceAnalysisPublicationConflict, match="missing a required"):
            read(
                settings, report_date="2025-12-31", position_scope="all",
                currency_basis="CNY", generation=receipt.generation,
            )


def test_complete_portfolio_rows_rejects_missing_filter_combination(tmp_path: Path) -> None:
    import duckdb

    with duckdb.connect(str(tmp_path / "incomplete.duckdb")) as conn:
        for table in (
            publication_reader.BALANCE_ANALYSIS_OVERVIEW_TABLE,
            publication_reader.BALANCE_ANALYSIS_BASIS_BREAKDOWN_TABLE,
        ):
            conn.execute(f"create table {table} (report_date varchar, position_scope varchar, currency_basis varchar)")
            conn.executemany(
                f"insert into {table} values (?, ?, ?)",
                [("2025-12-31", scope, currency) for scope in ("asset", "liability", "all") for currency in ("native", "CNY")],
            )
        conn.execute(
            f"delete from {publication_reader.BALANCE_ANALYSIS_BASIS_BREAKDOWN_TABLE} where position_scope = 'asset' and currency_basis = 'native'"
        )
        with pytest.raises(publication_reader.BalanceAnalysisPublicationConflict, match="all overview/basis filter combinations"):
            publication_reader._require_complete_portfolio_rows(conn, report_date="2025-12-31")
