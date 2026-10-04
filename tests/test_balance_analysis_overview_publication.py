from __future__ import annotations

import json
import shutil
import threading
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest
from fastapi import HTTPException, Response

from backend.app.api.routes import balance_analysis as balance_routes
from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.governance.settings import Settings
from backend.app.repositories.financial_result_publication_repo import (
    canonical_json_bytes,
    read_publication_pointer,
    sha256_bytes,
)
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.repositories.source_manifest_repo import (
    AUG31_SOURCE_MANIFEST_DEPENDENCY_KEY,
    SourceManifestRepository,
    selected_aug31_source_manifest_hash,
)
from backend.app.schemas.balance_analysis import BalanceAnalysisOverviewEnvelope
from backend.app.security.auth_context import AuthContext
from backend.app.services import balance_analysis_publication_service as publication_reader
from backend.app.services.balance_analysis_publication_service import (
    BALANCE_ANALYSIS_PORTFOLIO_CONTRACT_VERSION,
    BalanceAnalysisPublicationConflict,
    balance_analysis_publication_status,
    read_published_balance_analysis_overview,
)
from backend.app.tasks.balance_analysis_overview_publication import (
    BalanceAnalysisPublicationNotReady,
    BalanceAnalysisSnapshotCohortStale,
    _reject_historical_current_regression,
    invalidate_balance_analysis_publications_before_fact_change,
    publish_balance_analysis_overview,
)
from backend.app.tasks.financial_result_publication import invalidate_financial_generation
from tests.fixtures.balance_analysis import (
    balance_analysis_shared_materialized_read_seed as balance_analysis_shared_materialized_read_seed,
)
from tests.fixtures.balance_analysis import (
    balance_analysis_shared_materialized_seed,  # noqa: F401
)
from tests.test_balance_analysis_materialize_flow import (
    _patch_skip_fx_refresh,
    _seed_aug31_balance_sources,
)

pytestmark = [pytest.mark.integration, pytest.mark.materialize]


def _settings(seed, publication_root: Path, *, enabled: bool = True) -> Settings:
    return Settings(
        duckdb_path=str(seed.duckdb_path),
        governance_path=seed.governance_dir,
        balance_analysis_publication_enabled=enabled,
        balance_analysis_publication_root=str(publication_root),
    )


def _seed_synthetic_aug31_manifests(governance_dir: Path) -> str:
    SourceManifestRepository(
        governance_repo=GovernanceRepository(base_dir=governance_dir)
    ).add_many(
        [
            {
                "source_family": family,
                "report_date": "2026-08-31",
                "source_file": f"synthetic-{family}.xls",
                "source_version": f"sv-{family}",
                "ingest_batch_id": f"ib-{family}",
                "archived_path": f"/synthetic/{family}.xls",
            }
            for family in ("zqtz", "tyw")
        ]
    )
    return selected_aug31_source_manifest_hash(governance_dir)


def _synthetic_sealed_overview(
    monkeypatch,
    tmp_path: Path,
    *,
    report_dates: list[str],
    zqtz_versions: str | None,
    tyw_versions: str | None,
    bind_manifest_hash: bool = True,
    with_basis: bool = True,
) -> tuple[Settings, str]:
    from backend.app.services.balance_analysis_service import RULE_VERSION

    dependencies = {
        "balance.rule_version": RULE_VERSION,
        "balance.publication_contract_version": BALANCE_ANALYSIS_PORTFOLIO_CONTRACT_VERSION,
    }
    if zqtz_versions is not None:
        dependencies["balance.zqtz.rule_versions"] = zqtz_versions
    if tyw_versions is not None:
        dependencies["balance.tyw.rule_versions"] = tyw_versions
    governance_dir = tmp_path / "governance"
    if "2026-08-31" in report_dates and bind_manifest_hash:
        dependencies[AUG31_SOURCE_MANIFEST_DEPENDENCY_KEY] = (
            _seed_synthetic_aug31_manifests(governance_dir)
        )
    generation = "synthetic-sealed-generation"
    resolved = SimpleNamespace(
        generation=generation,
        manifest_sha256="synthetic-manifest-digest",
        manifest={
            "sealed_payload": {
                "coverage_dates": {
                    "balance_analysis_overview": report_dates,
                    **({"balance_analysis_basis_breakdown": report_dates} if with_basis else {}),
                },
                "dependency_versions": dependencies,
            }
        },
    )

    class _SyntheticConnection:
        def execute(self, _sql, _parameters):
            return self

        def fetchone(self):
            return ("{}", "unused-digest", json.dumps(dependencies))

        def fetchall(self):
            return [
                (scope, currency) for scope in ("asset", "liability", "all")
                for currency in ("native", "CNY")
            ]

    @contextmanager
    def open_generation(*_args, **_kwargs):
        yield _SyntheticConnection(), resolved

    monkeypatch.setattr(publication_reader, "open_financial_generation", open_generation)
    monkeypatch.setattr(
        publication_reader,
        "resolve_financial_generation",
        lambda *_args, **_kwargs: resolved,
    )
    monkeypatch.setattr(
        publication_reader,
        "_validated_overview_envelope",
        lambda **kwargs: {"result": {"report_date": kwargs["report_date"]}},
    )
    settings = Settings(
        governance_path=governance_dir,
        balance_analysis_publication_enabled=True,
        balance_analysis_publication_root=str(tmp_path / "synthetic-publication"),
    )
    return settings, generation


@pytest.mark.parametrize(
    ("zqtz_versions", "tyw_versions"),
    [
        ('["rv_snapshot_zqtz_tyw_v1"]', '["rv_snapshot_zqtz_tyw_v3"]'),
        ('["rv_snapshot_zqtz_tyw_v2"]', '["rv_snapshot_zqtz_tyw_v3"]'),
        ('["rv_snapshot_zqtz_tyw_v3"]', '["rv_snapshot_zqtz_tyw_v1"]'),
        ('["rv_snapshot_zqtz_tyw_v3"]', '["rv_snapshot_zqtz_tyw_v2"]'),
        ('["rv_snapshot_zqtz_tyw_v3","rv_snapshot_zqtz_tyw_v2"]', '["rv_snapshot_zqtz_tyw_v3"]'),
        ('[]', '["rv_snapshot_zqtz_tyw_v3"]'),
        (None, '["rv_snapshot_zqtz_tyw_v3"]'),
        ('["rv_snapshot_zqtz_tyw_v3"]', '["rv_snapshot_zqtz_tyw_v2__locf"]'),
        ('["rv_snapshot_zqtz_tyw_v3"]', '["rv_snapshot_zqtz_tyw_v3__locf"]'),
    ],
)
def test_august_2026_sealed_overview_rejects_incompatible_snapshot_versions(
    monkeypatch,
    tmp_path: Path,
    zqtz_versions: str | None,
    tyw_versions: str | None,
) -> None:
    settings, generation = _synthetic_sealed_overview(
        monkeypatch,
        tmp_path,
        report_dates=["2026-08-31"],
        zqtz_versions=zqtz_versions,
        tyw_versions=tyw_versions,
    )

    with pytest.raises(BalanceAnalysisPublicationConflict, match="snapshot rule version"):
        read_published_balance_analysis_overview(
            settings,
            report_date="2026-08-31",
            position_scope="all",
            currency_basis="CNY",
            generation=generation,
        )


@pytest.mark.parametrize(
    "legacy_rule_version",
    ("rv_snapshot_zqtz_tyw_v1", "rv_snapshot_zqtz_tyw_v2"),
)
def test_august_2026_sealed_overview_accepts_v3_and_older_date_keeps_legacy_rule(
    monkeypatch,
    tmp_path: Path,
    legacy_rule_version: str,
) -> None:
    current = '["rv_snapshot_zqtz_tyw_v3"]'
    settings, generation = _synthetic_sealed_overview(
        monkeypatch,
        tmp_path,
        report_dates=["2026-08-31"],
        zqtz_versions=current,
        tyw_versions=current,
    )
    assert read_published_balance_analysis_overview(
        settings,
        report_date="2026-08-31",
        position_scope="all",
        currency_basis="CNY",
        generation=generation,
    ).generation == generation

    legacy = f'["{legacy_rule_version}"]'
    settings, generation = _synthetic_sealed_overview(
        monkeypatch,
        tmp_path,
        report_dates=["2026-07-31"],
        zqtz_versions=legacy,
        tyw_versions=legacy,
    )
    assert read_published_balance_analysis_overview(
        settings,
        report_date="2026-07-31",
        position_scope="all",
        currency_basis="CNY",
        generation=generation,
    ).generation == generation


def test_sealed_status_excludes_only_blocked_august_date(
    monkeypatch,
    tmp_path: Path,
) -> None:
    legacy = '["rv_snapshot_zqtz_tyw_v1"]'
    settings, generation = _synthetic_sealed_overview(
        monkeypatch,
        tmp_path,
        report_dates=["2026-07-31", "2026-08-31"],
        zqtz_versions=legacy,
        tyw_versions=legacy,
    )
    status = balance_analysis_publication_status(settings)
    assert status["available"] is True
    assert status["generation"] == generation
    assert status["report_dates"] == ["2026-07-31"]
    assert status["quality_flag"] == "ok"

    settings, _ = _synthetic_sealed_overview(
        monkeypatch,
        tmp_path,
        report_dates=["2026-08-31"],
        zqtz_versions=legacy,
        tyw_versions=legacy,
    )
    status = balance_analysis_publication_status(settings)
    assert status["available"] is False
    assert status["report_dates"] == []
    assert status["quality_flag"] == "stale"


def test_august_pinned_read_and_status_fail_closed_on_source_manifest_lock_timeout(
    monkeypatch, tmp_path: Path,
) -> None:
    current = '["rv_snapshot_zqtz_tyw_v3"]'
    settings, generation = _synthetic_sealed_overview(
        monkeypatch,
        tmp_path,
        report_dates=["2026-08-31"],
        zqtz_versions=current,
        tyw_versions=current,
    )
    lock_calls = []

    def blocked_manifest_lock(*args, **kwargs):
        lock_calls.append((args, kwargs))
        raise TimeoutError("synthetic source manifest lock contention")

    monkeypatch.setattr(publication_reader, "acquire_lock", blocked_manifest_lock)
    with pytest.raises(BalanceAnalysisPublicationConflict, match="while it is locked"):
        read_published_balance_analysis_overview(
            settings,
            report_date="2026-08-31",
            position_scope="all",
            currency_basis="CNY",
            generation=generation,
        )
    status = balance_analysis_publication_status(settings)
    assert status["available"] is False
    assert status["report_dates"] == []
    assert status["quality_flag"] == "stale"
    assert "while it is locked" in str(status["reason"])
    assert len(lock_calls) == 2
    assert all(
        kwargs["base_dir"] == settings.governance_path
        and kwargs["timeout_seconds"] == 5.0
        for _args, kwargs in lock_calls
    )


def test_missing_august_source_manifest_hash_blocks_only_august_date(
    monkeypatch, tmp_path: Path
) -> None:
    current = '["rv_snapshot_zqtz_tyw_v3"]'
    settings, generation = _synthetic_sealed_overview(
        monkeypatch,
        tmp_path,
        report_dates=["2026-07-31", "2026-08-31"],
        zqtz_versions=current,
        tyw_versions=current,
        bind_manifest_hash=False,
    )
    status = balance_analysis_publication_status(settings)
    assert status["available"] is True
    assert status["report_dates"] == ["2026-07-31"]
    with pytest.raises(BalanceAnalysisPublicationConflict, match="digest is missing"):
        read_published_balance_analysis_overview(
            settings,
            report_date="2026-08-31",
            position_scope="all",
            currency_basis="CNY",
            generation=generation,
        )
    assert read_published_balance_analysis_overview(
        settings,
        report_date="2026-07-31",
        position_scope="all",
        currency_basis="CNY",
        generation=generation,
    ).generation == generation


def test_august_publication_rejects_legacy_snapshot_before_changing_current_pointer(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from backend.app.services.balance_analysis_service import RULE_VERSION
    from backend.app.tasks import balance_analysis_overview_publication as publication_task

    source = tmp_path / "synthetic-source.duckdb"
    duckdb.connect(str(source)).close()
    root = tmp_path / "balance-publication"
    settings = Settings(
        duckdb_path=str(source),
        governance_path=tmp_path / "governance",
        balance_analysis_publication_enabled=True,
        balance_analysis_publication_root=str(root),
    )
    _seed_synthetic_aug31_manifests(Path(settings.governance_path))
    current = '["rv_snapshot_zqtz_tyw_v3"]'
    versions: list[str | None] = [current, current]
    prepared_runs: list[str] = []

    def synthetic_dependencies(**_kwargs) -> dict[str, str]:
        result = {
            "balance.rule_version": RULE_VERSION,
            "balance.publication_contract_version": BALANCE_ANALYSIS_PORTFOLIO_CONTRACT_VERSION,
            "balance.build.run_id": "synthetic-balance-build",
            "balance.build.source_version": "synthetic-source-v1",
            "balance.build.rule_version": RULE_VERSION,
            "balance.build.finished_at": "2026-09-01T00:00:00+08:00",
        }
        for family, value in zip(("zqtz", "tyw"), versions, strict=True):
            if value is not None:
                result[f"balance.{family}.rule_versions"] = value
        return result

    def prepare_synthetic_stage(
        *,
        stage_path: Path,
        report_date: str,
        dependencies: dict[str, str],
        run_id: str,
        **_kwargs,
    ) -> dict[str, object]:
        prepared_runs.append(run_id)
        dependency_json = canonical_json_bytes(dependencies).decode("utf-8")
        rows = []
        checks = []
        for position_scope in ("asset", "liability", "all"):
            for currency_basis in ("native", "CNY"):
                envelope = BalanceAnalysisOverviewEnvelope.model_validate(
                    {
                        "result_meta": {
                            "trace_id": "synthetic-publication-test",
                            "source_version": "synthetic-source-v1",
                            "rule_version": RULE_VERSION,
                            "cache_version": "synthetic-cache-v1",
                        },
                        "result": {
                            "report_date": report_date,
                            "position_scope": position_scope,
                            "currency_basis": currency_basis,
                            "detail_row_count": 0,
                            "summary_row_count": 0,
                            "total_market_value_amount": "0",
                            "total_amortized_cost_amount": "0",
                            "total_accrued_interest_amount": "0",
                            "asset_total_market_value_amount": "0",
                            "liability_total_market_value_amount": "0",
                            "asset_total_amortized_cost_amount": "0",
                            "liability_total_amortized_cost_amount": "0",
                            "asset_total_accrued_interest_amount": "0",
                            "liability_total_accrued_interest_amount": "0",
                            "metric_definitions": [],
                        },
                        "data_source": "balance_analysis_facts",
                        "calibration": {
                            "position_scope": position_scope,
                            "currency_basis": currency_basis,
                            "source_families": ["zqtz", "tyw"],
                            "tyw_amount_semantics": "synthetic",
                            "data_basis": "formal_facts",
                            "calibration_note": "synthetic",
                        },
                    }
                ).model_dump(mode="json")
                payload_json = canonical_json_bytes(envelope).decode("utf-8")
                rows.append(
                    (
                        report_date,
                        position_scope,
                        currency_basis,
                        payload_json,
                        sha256_bytes(payload_json.encode("utf-8")),
                        dependency_json,
                        publication_task.BALANCE_ANALYSIS_PUBLICATION_SCHEMA_VERSION,
                    )
                )
                checks.append(
                    {"name": f"overview_{position_scope}_{currency_basis}", "status": "passed"}
                )
        conn = duckdb.connect(str(stage_path))
        try:
            conn.execute(
                f"""create table {publication_task.BALANCE_ANALYSIS_OVERVIEW_TABLE} (
                    report_date varchar not null,
                    position_scope varchar not null,
                    currency_basis varchar not null,
                    payload_json varchar not null,
                    payload_sha256 varchar not null,
                    dependency_versions_json varchar not null,
                    schema_version varchar not null,
                    primary key (report_date, position_scope, currency_basis)
                )"""
            )
            conn.executemany(
                f"insert into {publication_task.BALANCE_ANALYSIS_OVERVIEW_TABLE} values (?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
            conn.execute(
                f"create table {publication_task.BALANCE_ANALYSIS_BASIS_BREAKDOWN_TABLE} "
                f"as select * from {publication_task.BALANCE_ANALYSIS_OVERVIEW_TABLE} where false"
            )
            basis_rows = []
            for row in rows:
                basis_envelope = json.loads(row[3])
                basis_envelope["result"] = {
                    "report_date": row[0], "position_scope": row[1],
                    "currency_basis": row[2], "rows": [],
                }
                basis_json = canonical_json_bytes(basis_envelope).decode("utf-8")
                basis_rows.append((*row[:3], basis_json, sha256_bytes(basis_json.encode("utf-8")), *row[5:]))
            conn.executemany(
                f"insert into {publication_task.BALANCE_ANALYSIS_BASIS_BREAKDOWN_TABLE} values (?, ?, ?, ?, ?, ?, ?)",
                basis_rows,
            )
            conn.execute("checkpoint")
        finally:
            conn.close()
        return {
            "status": "completed",
            "name": "balance_analysis_overview_prepare",
            "run_id": run_id,
            "report_date": report_date,
            "records": len(rows),
            "dependency_versions": dependencies,
            "quality_checks": checks,
        }

    monkeypatch.setattr(publication_task, "_active_dependency_snapshot", synthetic_dependencies)
    monkeypatch.setattr(publication_task, "_build_stage_database", prepare_synthetic_stage)
    monkeypatch.setattr(
        publication_task, "_require_current_aug31_snapshot_cohort", lambda **_kwargs: None
    )
    first = publish_balance_analysis_overview(
        settings,
        report_date="2026-08-31",
        run_id="synthetic-v3-publication",
        expected_previous_generation=None,
    )
    assert first.status == "published"
    assert read_published_balance_analysis_overview(
        settings,
        report_date="2026-08-31",
        position_scope="all",
        currency_basis="CNY",
        generation=first.generation,
    ).generation == first.generation
    pointer_before = read_publication_pointer(root, require_valid=True)

    for index, (zqtz, tyw) in enumerate(
        (
            ('["rv_snapshot_zqtz_tyw_v1"]', current),
            (current, '["rv_snapshot_zqtz_tyw_v1"]'),
            ('["rv_snapshot_zqtz_tyw_v2"]', current),
            (current, '["rv_snapshot_zqtz_tyw_v2"]'),
            ('["rv_snapshot_zqtz_tyw_v3","rv_snapshot_zqtz_tyw_v2"]', current),
            (None, current),
            (current, '["rv_snapshot_zqtz_tyw_v2__locf"]'),
            (current, '["rv_snapshot_zqtz_tyw_v3__locf"]'),
        )
    ):
        versions[:] = [zqtz, tyw]
        with pytest.raises(publication_task.BalanceAnalysisPublicationNotReady, match="snapshot rule version"):
            publish_balance_analysis_overview(
                settings,
                report_date="2026-08-31",
                run_id=f"synthetic-invalid-publication-{index}",
                expected_previous_generation=first.generation,
            )
        assert read_publication_pointer(root, require_valid=True) == pointer_before
        assert prepared_runs == ["synthetic-v3-publication"]


def test_august_publication_rechecks_selected_snapshot_cohort_before_direct_and_actor_publish(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from backend.app.tasks import balance_analysis_materialize as materialize_task
    from backend.app.tasks import balance_analysis_overview_publication as publication_task

    source = tmp_path / "synthetic-balance.duckdb"
    governance_dir = tmp_path / "governance"
    root = tmp_path / "balance-publication"
    _seed_aug31_balance_sources(str(source), governance_dir)
    conn = duckdb.connect(str(source), read_only=False)
    try:
        for table in ("zqtz_bond_daily_snapshot", "tyw_interbank_daily_snapshot"):
            conn.execute(
                f"update {table} set rule_version = 'rv_snapshot_zqtz_tyw_v3'"
            )
    finally:
        conn.close()
    settings = Settings(
        duckdb_path=str(source),
        governance_path=governance_dir,
        balance_analysis_publication_enabled=True,
        balance_analysis_publication_root=str(root),
    )
    monkeypatch.setattr(materialize_task, "get_settings", lambda: settings)
    monkeypatch.setattr(publication_task, "get_settings", lambda: settings)
    _patch_skip_fx_refresh(materialize_task, monkeypatch)
    monkeypatch.setattr(
        materialize_task,
        "_dispatch_balance_overview_publication",
        lambda *_args, **_kwargs: None,
    )
    build = materialize_task.materialize_balance_analysis_facts.fn(
        report_date="2026-08-31",
        duckdb_path=str(source),
        governance_dir=str(governance_dir),
        run_id="synthetic-aug31-build-before-new-source",
    )
    assert build["status"] == "completed"
    first = publish_balance_analysis_overview(
        settings,
        report_date="2026-08-31",
        run_id="synthetic-aug31-publication-before-new-source",
        expected_previous_generation=None,
    )
    assert first.status == "published"
    pointer_before = read_publication_pointer(root, require_valid=True)

    extra_manifest = {
        "source_family": "tyw",
        "report_date": "2026-08-31",
        "source_file": "synthetic-tyw-extra.xls",
        "source_version": "sv-t-2",
        "ingest_batch_id": "ib-t-1",
        "archived_path": "/synthetic/tyw-extra.xls",
    }
    real_prepare_stage = publication_task._build_stage_database

    def prepare_then_append_manifest(**kwargs):
        receipt = real_prepare_stage(**kwargs)
        SourceManifestRepository(
            governance_repo=GovernanceRepository(base_dir=governance_dir)
        ).add_many([extra_manifest])
        return receipt

    monkeypatch.setattr(
        publication_task, "_build_stage_database", prepare_then_append_manifest
    )
    with pytest.raises(BalanceAnalysisPublicationNotReady, match="selected snapshot lineage"):
        publish_balance_analysis_overview(
            settings,
            report_date="2026-08-31",
            run_id="synthetic-aug31-manifest-appeared-during-stage",
            expected_previous_generation=first.generation,
        )
    assert read_publication_pointer(root, require_valid=True) == pointer_before
    monkeypatch.setattr(publication_task, "_build_stage_database", real_prepare_stage)

    conn = duckdb.connect(str(source), read_only=False)
    try:
        conn.execute(
            "insert into tyw_interbank_daily_snapshot "
            "select * replace ('pos-new' as position_id, 'sv-t-2' as source_version, "
            "'trace-new' as trace_id) "
            "from tyw_interbank_daily_snapshot where position_id = 'pos-1'"
        )
    finally:
        conn.close()

    with pytest.raises(BalanceAnalysisPublicationNotReady, match="snapshot cohort"):
        publish_balance_analysis_overview(
            settings,
            report_date="2026-08-31",
            run_id="synthetic-aug31-direct-after-new-source",
            expected_previous_generation=first.generation,
        )
    assert read_publication_pointer(root, require_valid=True) == pointer_before

    failed = publication_task.publish_balance_analysis_overview_actor.fn(
        report_date="2026-08-31",
        source_build_run_id="synthetic-aug31-build-before-new-source",
    )
    assert failed["status"] == "failed"
    assert failed["failure_category"] == "snapshot_cohort_stale"
    assert read_publication_pointer(root, require_valid=True) == pointer_before


def _materialized_aug31_settings(
    tmp_path: Path, monkeypatch, *, run_id: str | None = "synthetic-aug31-build"
) -> Settings:
    from backend.app.tasks import balance_analysis_materialize as materialize_task

    source = tmp_path / "synthetic-balance.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_aug31_balance_sources(str(source), governance_dir)
    conn = duckdb.connect(str(source), read_only=False)
    try:
        for table in ("zqtz_bond_daily_snapshot", "tyw_interbank_daily_snapshot"):
            conn.execute(f"update {table} set rule_version = 'rv_snapshot_zqtz_tyw_v3'")
    finally:
        conn.close()
    settings = Settings(
        duckdb_path=str(source),
        governance_path=governance_dir,
        balance_analysis_publication_enabled=True,
        balance_analysis_publication_root=str(tmp_path / "balance-publication"),
    )
    monkeypatch.setattr(materialize_task, "get_settings", lambda: settings)
    _patch_skip_fx_refresh(materialize_task, monkeypatch)
    monkeypatch.setattr(
        materialize_task,
        "_dispatch_balance_overview_publication",
        lambda *_args, **_kwargs: None,
    )
    build = materialize_task.materialize_balance_analysis_facts.fn(
        report_date="2026-08-31",
        duckdb_path=str(source),
        governance_dir=str(governance_dir),
        run_id=run_id,
    )
    assert build["status"] == "completed"
    return settings


def test_august_publication_accepts_current_build_without_explicit_run_id(
    tmp_path: Path, monkeypatch,
) -> None:
    settings = _materialized_aug31_settings(tmp_path, monkeypatch, run_id=None)
    published = publish_balance_analysis_overview(
        settings,
        report_date="2026-08-31",
        run_id="synthetic-generated-build-publication",
        expected_previous_generation=None,
    )
    assert published.status == "published"
    assert read_publication_pointer(
        Path(settings.balance_analysis_publication_root), require_valid=True
    )["generation"] == published.generation


@pytest.mark.parametrize(
    "recorded_guard", (None, "rv_snapshot_zqtz_tyw_v2")
)
def test_august_publication_rejects_completed_build_with_old_snapshot_guard(
    tmp_path: Path, monkeypatch, recorded_guard: str | None,
) -> None:
    from backend.app.tasks import balance_analysis_overview_publication as publication_task

    settings = _materialized_aug31_settings(tmp_path, monkeypatch)
    first = publish_balance_analysis_overview(
        settings,
        report_date="2026-08-31",
        run_id="synthetic-first-v3-publication",
        expected_previous_generation=None,
    )
    root = Path(settings.balance_analysis_publication_root)
    pointer_before = read_publication_pointer(root, require_valid=True)
    governance = GovernanceRepository(base_dir=settings.governance_path)
    identity = next(
        row
        for row in reversed(governance.read_all(publication_task.CACHE_BUILD_RUN_STREAM))
        if row.get("phase") == "materialize_run_identity"
        and row.get("run_id") == "synthetic-aug31-build"
    )
    old_identity = dict(identity)
    if recorded_guard is None:
        old_identity.pop("snapshot_rule_version_guard", None)
    else:
        old_identity["snapshot_rule_version_guard"] = recorded_guard
    governance.append(publication_task.CACHE_BUILD_RUN_STREAM, old_identity)

    with pytest.raises(BalanceAnalysisPublicationNotReady, match="snapshot rule guard"):
        publish_balance_analysis_overview(
            settings,
            report_date="2026-08-31",
            run_id="synthetic-old-guard-publication",
            expected_previous_generation=first.generation,
        )
    assert read_publication_pointer(root, require_valid=True) == pointer_before


def test_august_selected_manifest_change_during_stage_rejects_same_version_source(
    tmp_path: Path, monkeypatch
) -> None:
    from backend.app.tasks import balance_analysis_overview_publication as publication_task

    settings = _materialized_aug31_settings(tmp_path, monkeypatch)
    real_stage = publication_task._build_stage_database

    def stage_then_append_same_version(**kwargs):
        receipt = real_stage(**kwargs)
        SourceManifestRepository(
            governance_repo=GovernanceRepository(base_dir=settings.governance_path)
        ).add_many(
            [
                {
                    "source_family": "tyw",
                    "report_date": "2026-08-31",
                    "source_file": "synthetic-tyw-second-file.xls",
                    "source_version": "sv-t-1",
                    "ingest_batch_id": "ib-t-1",
                    "archived_path": "/synthetic/tyw-second-file.xls",
                }
            ]
        )
        return receipt

    monkeypatch.setattr(publication_task, "_build_stage_database", stage_then_append_same_version)
    with pytest.raises(BalanceAnalysisSnapshotCohortStale, match="source manifest changed"):
        publish_balance_analysis_overview(
            settings,
            report_date="2026-08-31",
            run_id="synthetic-aug31-same-version-append",
            expected_previous_generation=None,
        )
    assert read_publication_pointer(Path(settings.balance_analysis_publication_root)) is None


def test_august_manifest_append_waits_for_pointer_commit_then_revokes_pinned_generations(
    tmp_path: Path, monkeypatch
) -> None:
    from backend.app.repositories import source_manifest_repo as manifest_module
    from backend.app.tasks import balance_analysis_overview_publication as publication_task

    settings = _materialized_aug31_settings(tmp_path, monkeypatch)
    first = publish_balance_analysis_overview(
        settings,
        report_date="2026-08-31",
        run_id="synthetic-aug31-first",
        expected_previous_generation=None,
    )
    real_publish = publication_task.publish_financial_result
    append_lock_attempted = threading.Event()
    append_finished = threading.Event()
    append_errors: list[Exception] = []
    append_threads: list[threading.Thread] = []
    real_manifest_lock = manifest_module.acquire_lock

    @contextmanager
    def observed_manifest_lock(*args, **kwargs):
        append_lock_attempted.set()
        with real_manifest_lock(*args, **kwargs) as lock_path:
            yield lock_path

    monkeypatch.setattr(manifest_module, "acquire_lock", observed_manifest_lock)

    def append_manifest() -> None:
        try:
            SourceManifestRepository(
                governance_repo=GovernanceRepository(base_dir=settings.governance_path)
            ).add_many(
                [
                    {
                        "source_family": "tyw",
                        "report_date": "2026-08-31",
                        "source_file": "synthetic-tyw-after-cas.xls",
                        "source_version": "sv-t-after-cas",
                        "ingest_batch_id": "ib-t-1",
                        "archived_path": "/synthetic/tyw-after-cas.xls",
                    }
                ]
            )
        except Exception as exc:
            append_errors.append(exc)
        finally:
            append_finished.set()

    def publish_with_waiting_append(**kwargs):
        thread = threading.Thread(target=append_manifest, daemon=True)
        append_threads.append(thread)
        thread.start()
        assert append_lock_attempted.wait(timeout=1)
        assert not append_finished.wait(timeout=0.1)
        return real_publish(**kwargs)

    monkeypatch.setattr(publication_task, "publish_financial_result", publish_with_waiting_append)
    second = publish_balance_analysis_overview(
        settings,
        report_date="2026-08-31",
        run_id="synthetic-aug31-second",
        expected_previous_generation=first.generation,
    )
    for thread in append_threads:
        thread.join(timeout=5)
    assert append_finished.is_set()
    assert not append_errors
    assert second.status == "published"
    assert read_publication_pointer(Path(settings.balance_analysis_publication_root))["generation"] == second.generation
    for generation in (first.generation, second.generation):
        with pytest.raises(BalanceAnalysisPublicationConflict, match="source manifest is stale"):
            read_published_balance_analysis_overview(
                settings,
                report_date="2026-08-31",
                position_scope="all",
                currency_basis="CNY",
                generation=generation,
            )
    status = balance_analysis_publication_status(settings)
    assert status["available"] is False
    assert status["report_dates"] == []


def test_publish_and_strict_read_balance_overview_without_changing_active_database(
    tmp_path: Path,
    balance_analysis_shared_materialized_read_seed,
) -> None:
    seed = balance_analysis_shared_materialized_read_seed
    root = tmp_path / "balance-publication"
    settings = _settings(seed, root)
    before = (seed.duckdb_path.stat().st_size, seed.duckdb_path.stat().st_mtime_ns)

    receipt = publish_balance_analysis_overview(
        settings,
        report_date="2025-12-31",
        run_id="balance-overview-run-1",
        expected_previous_generation=None,
    )

    assert receipt.status == "published"
    published = read_published_balance_analysis_overview(
        settings,
        report_date="2025-12-31",
        position_scope="all",
        currency_basis="CNY",
        generation=receipt.generation,
    )
    assert published.generation == receipt.generation
    assert published.envelope["result_meta"]["formal_use_allowed"] is True
    assert published.envelope["result"]["report_date"] == "2025-12-31"
    assert (seed.duckdb_path.stat().st_size, seed.duckdb_path.stat().st_mtime_ns) == before

    status = balance_analysis_publication_status(settings)
    assert status == {
        "enabled": True,
        "available": True,
        "generation": receipt.generation,
        "report_dates": ["2025-12-31"],
        "manifest_sha256": receipt.manifest_sha256,
        "quality_flag": "ok",
        "reason": None,
    }


def test_same_publication_run_is_idempotent_after_pointer_commit(
    tmp_path: Path,
    balance_analysis_shared_materialized_read_seed,
) -> None:
    seed = balance_analysis_shared_materialized_read_seed
    root = tmp_path / "balance-publication"
    settings = _settings(seed, root)
    first = publish_balance_analysis_overview(
        settings,
        report_date="2025-12-31",
        run_id="balance-overview-idempotent",
        expected_previous_generation=None,
    )

    repeated = publish_balance_analysis_overview(
        settings,
        report_date="2025-12-31",
        run_id="balance-overview-idempotent",
        expected_previous_generation=None,
    )

    assert repeated.generation == first.generation
    assert repeated.recovered_after_commit is True


def test_same_run_recovers_candidate_sealed_before_pointer_commit(
    tmp_path: Path,
    balance_analysis_shared_materialized_read_seed,
    monkeypatch,
) -> None:
    from backend.app.tasks import balance_analysis_overview_publication as publication_task

    seed = balance_analysis_shared_materialized_read_seed
    root = tmp_path / "balance-publication"
    settings = _settings(seed, root)
    real_publish = publication_task.publish_financial_result
    fail_once = True

    def publish_with_fault(**kwargs):
        def on_stage(stage: str) -> None:
            nonlocal fail_once
            if stage == "before_pointer_commit" and fail_once:
                fail_once = False
                raise RuntimeError("fault after candidate seal")

        return real_publish(**kwargs, on_stage=on_stage)

    monkeypatch.setattr(publication_task, "publish_financial_result", publish_with_fault)
    with pytest.raises(RuntimeError, match="fault after candidate seal"):
        publication_task.publish_balance_analysis_overview(
            settings,
            report_date="2025-12-31",
            run_id="balance-overview-sealed-retry",
            expected_previous_generation=None,
        )

    recovered = publication_task.publish_balance_analysis_overview(
        settings,
        report_date="2025-12-31",
        run_id="balance-overview-sealed-retry",
        expected_previous_generation=None,
    )

    assert recovered.status == "published"
    assert recovered.previous_generation is None


def test_same_run_recovers_when_pointer_committed_before_receipt_is_returned(
    tmp_path: Path,
    balance_analysis_shared_materialized_read_seed,
    monkeypatch,
) -> None:
    from backend.app.tasks import balance_analysis_overview_publication as publication_task

    seed = balance_analysis_shared_materialized_read_seed
    root = tmp_path / "balance-publication"
    settings = _settings(seed, root)
    real_publish = publication_task.publish_financial_result
    fail_once = True

    def publish_with_fault(**kwargs):
        def on_stage(stage: str) -> None:
            nonlocal fail_once
            if stage == "pointer_committed" and fail_once:
                fail_once = False
                raise RuntimeError("receipt lost after pointer commit")

        return real_publish(**kwargs, on_stage=on_stage)

    monkeypatch.setattr(publication_task, "publish_financial_result", publish_with_fault)
    with pytest.raises(RuntimeError, match="receipt lost after pointer commit"):
        publication_task.publish_balance_analysis_overview(
            settings,
            report_date="2025-12-31",
            run_id="balance-overview-pointer-retry",
            expected_previous_generation=None,
        )

    recovered = publication_task.publish_balance_analysis_overview(
        settings,
        report_date="2025-12-31",
        run_id="balance-overview-pointer-retry",
        expected_previous_generation=None,
    )

    assert recovered.recovered_after_commit is True


def test_successful_materialize_dispatches_publication_with_source_build_identity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from backend.app.tasks import balance_analysis_materialize as materialize_task
    from backend.app.tasks import balance_analysis_overview_publication as publication_task

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    settings = Settings(
        duckdb_path=str(duckdb_path),
        governance_path=governance_dir,
        balance_analysis_publication_enabled=True,
        balance_analysis_publication_root=str(tmp_path / "balance-publication"),
    )
    monkeypatch.setattr(materialize_task, "get_settings", lambda: settings)
    monkeypatch.setattr(
        materialize_task,
        "run_formal_materialize",
        lambda **_kwargs: {
            "status": "completed",
            "run_id": "balance-build-1",
            "report_date": "2025-12-31",
        },
    )
    sent: dict[str, object] = {}

    class FakeActor:
        @staticmethod
        def send(**kwargs):
            sent.update(kwargs)
            return SimpleNamespace(message_id="message-1")

    monkeypatch.setattr(publication_task, "publish_balance_analysis_overview_actor", FakeActor())

    payload = materialize_task._materialize_balance_analysis_facts(
        report_date="2025-12-31",
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    assert sent == {
        "report_date": "2025-12-31",
        "source_build_run_id": "balance-build-1",
    }
    assert payload["overview_publication_dispatch"]["message_id"] == "message-1"
    receipts = [
        json.loads(line)
        for line in (governance_dir / "cache_build_run.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert receipts[-1]["job_name"] == "balance_analysis_overview_publication"
    assert receipts[-1]["status"] == "queued"
    assert receipts[-1]["source_build_run_id"] == "balance-build-1"


def test_publication_dispatch_failure_propagates_from_materialize_actor(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from backend.app.tasks import balance_analysis_materialize as materialize_task
    from backend.app.tasks import balance_analysis_overview_publication as publication_task

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    settings = Settings(
        duckdb_path=str(duckdb_path),
        governance_path=governance_dir,
        balance_analysis_publication_enabled=True,
        balance_analysis_publication_root=str(tmp_path / "balance-publication"),
    )
    monkeypatch.setattr(materialize_task, "get_settings", lambda: settings)
    monkeypatch.setattr(
        materialize_task,
        "run_formal_materialize",
        lambda **_kwargs: {
            "status": "completed",
            "run_id": "balance-build-dispatch-failure",
            "report_date": "2025-12-31",
        },
    )

    class FailingActor:
        @staticmethod
        def send(**_kwargs):
            raise RuntimeError("broker send failed")

    monkeypatch.setattr(
        publication_task,
        "publish_balance_analysis_overview_actor",
        FailingActor(),
    )

    with pytest.raises(RuntimeError, match="broker send failed"):
        materialize_task._materialize_balance_analysis_facts(
            report_date="2025-12-31",
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
        )

    receipts = [
        json.loads(line)
        for line in (governance_dir / "cache_build_run.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [item["status"] for item in receipts[-2:]] == ["queued", "failed"]
    assert receipts[-1]["failure_category"] == "publication_dispatch_failed"


def test_publisher_actor_rejects_stale_source_build_message(
    tmp_path: Path,
    balance_analysis_shared_materialized_read_seed,
    monkeypatch,
) -> None:
    from backend.app.tasks import balance_analysis_overview_publication as publication_task

    seed = balance_analysis_shared_materialized_read_seed
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    shutil.copy2(seed.duckdb_path, duckdb_path)
    shutil.copytree(seed.governance_dir, governance_dir)
    settings = Settings(
        duckdb_path=str(duckdb_path),
        governance_path=governance_dir,
        balance_analysis_publication_enabled=True,
        balance_analysis_publication_root=str(tmp_path / "balance-publication"),
    )
    monkeypatch.setattr(publication_task, "get_settings", lambda: settings)

    with pytest.raises(BalanceAnalysisPublicationNotReady, match="latest source build"):
        publication_task._publish_balance_analysis_overview_actor(
            report_date="2025-12-31",
            source_build_run_id="superseded-build-run",
        )

    receipts = [
        json.loads(line)
        for line in (governance_dir / "cache_build_run.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert receipts[-1]["job_name"] == "balance_analysis_overview_publication"
    assert receipts[-1]["status"] == "failed"


def test_publisher_actor_stops_retrying_august_snapshot_version_rejection(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from backend.app.services.balance_analysis_service import RULE_VERSION
    from backend.app.tasks import balance_analysis_overview_publication as publication_task

    source = tmp_path / "synthetic-source.duckdb"
    duckdb.connect(str(source)).close()
    governance_dir = tmp_path / "governance"
    root = tmp_path / "balance-publication"
    settings = Settings(
        duckdb_path=str(source),
        governance_path=governance_dir,
        balance_analysis_publication_enabled=True,
        balance_analysis_publication_root=str(root),
    )
    monkeypatch.setattr(publication_task, "get_settings", lambda: settings)
    monkeypatch.setattr(
        publication_task,
        "_active_dependency_snapshot",
        lambda **_kwargs: {
            "balance.rule_version": RULE_VERSION,
            "balance.zqtz.rule_versions": '["rv_snapshot_zqtz_tyw_v1"]',
            "balance.tyw.rule_versions": '["rv_snapshot_zqtz_tyw_v3"]',
        },
    )

    failed = publication_task.publish_balance_analysis_overview_actor.fn(
        report_date="2026-08-31",
        source_build_run_id="synthetic-v1-build",
    )
    assert failed["status"] == "failed"
    assert failed["failure_category"] == "snapshot_rule_incompatible"
    assert "snapshot rule version" in str(failed["error_message"])
    receipts = GovernanceRepository(base_dir=governance_dir).read_all(
        publication_task.CACHE_BUILD_RUN_STREAM
    )
    assert len(receipts) == 1
    assert receipts[0]["status"] == "failed"
    assert receipts[0]["failure_category"] == "snapshot_rule_incompatible"
    assert read_publication_pointer(root, require_valid=False) is None

    def transient_snapshot_failure(**_kwargs):
        raise RuntimeError("temporary dependency source unavailable")

    monkeypatch.setattr(
        publication_task,
        "_active_dependency_snapshot",
        transient_snapshot_failure,
    )
    with pytest.raises(RuntimeError, match="temporary dependency source unavailable"):
        publication_task.publish_balance_analysis_overview_actor.fn(
            report_date="2026-08-31",
            source_build_run_id="synthetic-transient-build",
        )
    receipts = GovernanceRepository(base_dir=governance_dir).read_all(
        publication_task.CACHE_BUILD_RUN_STREAM
    )
    assert len(receipts) == 2
    assert receipts[-1]["status"] == "failed"
    assert receipts[-1]["failure_category"] == "publication_failed"


@pytest.mark.parametrize(
    "lineage_variant", ("missing_manifest", "zqtz_v1", "zqtz_v2", "tyw_locf")
)
def test_publisher_actor_stops_retrying_august_invalid_selected_snapshot_lineage(
    tmp_path: Path,
    monkeypatch,
    lineage_variant: str,
) -> None:
    from backend.app.tasks import balance_analysis_overview_publication as publication_task

    source = tmp_path / "synthetic-source.duckdb"
    governance_dir = tmp_path / "governance"
    root = tmp_path / "balance-publication"
    _seed_aug31_balance_sources(str(source), governance_dir)
    conn = duckdb.connect(str(source), read_only=False)
    try:
        for table in ("zqtz_bond_daily_snapshot", "tyw_interbank_daily_snapshot"):
            conn.execute(f"update {table} set rule_version = 'rv_snapshot_zqtz_tyw_v3'")
        if lineage_variant == "zqtz_v1":
            conn.execute(
                "update zqtz_bond_daily_snapshot set rule_version = 'rv_snapshot_zqtz_tyw_v1'"
            )
        elif lineage_variant == "zqtz_v2":
            conn.execute(
                "update zqtz_bond_daily_snapshot set rule_version = 'rv_snapshot_zqtz_tyw_v2'"
            )
        elif lineage_variant == "tyw_locf":
            conn.execute(
                "update tyw_interbank_daily_snapshot "
                "set rule_version = 'rv_snapshot_zqtz_tyw_v3__locf'"
            )
    finally:
        conn.close()
    if lineage_variant == "missing_manifest":
        (governance_dir / "source_manifest.jsonl").unlink()

    settings = Settings(
        duckdb_path=str(source),
        governance_path=governance_dir,
        balance_analysis_publication_enabled=True,
        balance_analysis_publication_root=str(root),
    )
    monkeypatch.setattr(publication_task, "get_settings", lambda: settings)
    monkeypatch.setattr(
        publication_task,
        "_active_dependency_snapshot",
        lambda **_kwargs: {
            "balance.build.run_id": "synthetic-build",
            "balance.zqtz.rule_versions": '["rv_snapshot_zqtz_tyw_v3"]',
            "balance.tyw.rule_versions": '["rv_snapshot_zqtz_tyw_v3"]',
        },
    )

    failed = publication_task.publish_balance_analysis_overview_actor.fn(
        report_date="2026-08-31",
        source_build_run_id="synthetic-build",
    )
    assert failed["status"] == "failed"
    assert failed["failure_category"] == "snapshot_cohort_stale"
    receipts = GovernanceRepository(base_dir=governance_dir).read_all(
        publication_task.CACHE_BUILD_RUN_STREAM
    )
    assert len(receipts) == 1
    assert receipts[0]["failure_category"] == "snapshot_cohort_stale"
    assert read_publication_pointer(root, require_valid=False) is None


def test_actor_reserves_predecessor_at_execution_and_keeps_attempt_identity_stable(
    tmp_path: Path,
) -> None:
    from backend.app.tasks import balance_analysis_overview_publication as publication_task

    root = tmp_path / "balance-publication"
    root.mkdir()
    governance_dir = tmp_path / "governance"
    settings = Settings(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_path=governance_dir,
        balance_analysis_publication_enabled=True,
        balance_analysis_publication_root=str(root),
    )

    def write_pointer(generation: str) -> None:
        (root / "current.json").write_text(
            json.dumps(
                {
                    "protocol_version": "financial-result-publication/v1",
                    "generation": generation,
                    "manifest_sha256": "a" * 64,
                    "retained_generations": [
                        {"generation": generation, "manifest_sha256": "a" * 64}
                    ],
                    "validity": {"state": "valid"},
                }
            ),
            encoding="utf-8",
        )

    write_pointer("generation-zero")
    march = publication_task._resolve_or_reserve_publication_attempt(
        settings,
        publication_root=root,
        report_date="2026-03-31",
        source_build_run_id="build-march",
    )
    assert march.expected_previous_generation == "generation-zero"

    # A retry before pointer movement must retain the candidate's exact identity.
    assert publication_task._resolve_or_reserve_publication_attempt(
        settings,
        publication_root=root,
        report_date="2026-03-31",
        source_build_run_id="build-march",
    ) == march

    march_generation = publication_task._publication_generation(
        "2026-03-31", march.run_id
    )
    write_pointer(march_generation)
    # A receipt-loss retry after commit must also retain that same identity.
    assert publication_task._resolve_or_reserve_publication_attempt(
        settings,
        publication_root=root,
        report_date="2026-03-31",
        source_build_run_id="build-march",
    ) == march

    # April was queued while G0 was current, but reserves March only when its
    # actor executes. It can therefore advance instead of retrying a stale G0 CAS.
    april = publication_task._resolve_or_reserve_publication_attempt(
        settings,
        publication_root=root,
        report_date="2026-04-30",
        source_build_run_id="build-april",
    )
    assert april.number == 1
    assert april.expected_previous_generation == march_generation

    # If April had already reserved an attempt but another safe predecessor was
    # committed before its retry, the old immutable attempt is retained and a
    # new attempt receives a distinct generation identity.
    write_pointer("generation-concurrent-march")
    rebased_april = publication_task._resolve_or_reserve_publication_attempt(
        settings,
        publication_root=root,
        report_date="2026-04-30",
        source_build_run_id="build-april",
    )
    assert rebased_april.number == 2
    assert rebased_april.run_id != april.run_id
    assert rebased_april.expected_previous_generation == "generation-concurrent-march"

    GovernanceRepository(base_dir=governance_dir).append(
        "cache_build_run",
        {
            "status": "running",
            "phase": "publication_attempt_reserved",
            "publication_series_run_id": rebased_april.series_run_id,
            "publication_attempt": "two",
            "run_id": "malformed-attempt",
            "source_build_run_id": "build-april",
            "report_date": "2026-04-30",
        },
    )
    with pytest.raises(BalanceAnalysisPublicationNotReady, match="number is invalid"):
        publication_task._resolve_or_reserve_publication_attempt(
            settings,
            publication_root=root,
            report_date="2026-04-30",
            source_build_run_id="build-april",
        )


def test_materialize_same_run_replay_skips_fact_write_and_superseded_run_does_not_dispatch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from backend.app.tasks import balance_analysis_materialize as materialize_task
    from backend.app.tasks import balance_analysis_overview_publication as publication_task

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    settings = Settings(
        duckdb_path=str(duckdb_path),
        governance_path=governance_dir,
        balance_analysis_publication_enabled=True,
        balance_analysis_publication_root=str(tmp_path / "balance-publication"),
    )
    monkeypatch.setattr(materialize_task, "get_settings", lambda: settings)
    run_calls = 0

    def fake_run_formal_materialize(**kwargs):
        nonlocal run_calls
        run_calls += 1
        GovernanceRepository(base_dir=governance_dir).append(
            "cache_build_run",
            {
                "status": "completed",
                "job_name": "balance_analysis_materialize",
                "cache_key": materialize_task.CACHE_KEY,
                "cache_version": "cache-v1",
                "run_id": kwargs["run_id"],
                "report_date": "2025-12-31",
                "source_version": "source-v1",
                "rule_version": "rule-v1",
                "vendor_version": "vendor-v1",
                "lock": "balance-lock",
            },
        )
        return {
            "status": "completed",
            "run_id": kwargs["run_id"],
            "report_date": "2025-12-31",
        }

    monkeypatch.setattr(
        materialize_task,
        "run_formal_materialize",
        fake_run_formal_materialize,
    )
    sent: list[dict[str, object]] = []

    class FakeActor:
        @staticmethod
        def send(**kwargs):
            sent.append(dict(kwargs))
            return SimpleNamespace(message_id=f"message-{len(sent)}")

    monkeypatch.setattr(publication_task, "publish_balance_analysis_overview_actor", FakeActor())
    arguments = {
        "report_date": "2025-12-31",
        "duckdb_path": str(duckdb_path),
        "governance_dir": str(governance_dir),
        "run_id": "balance-build-r",
    }
    first = materialize_task._materialize_balance_analysis_facts(**arguments)
    replay = materialize_task._materialize_balance_analysis_facts(**arguments)

    assert run_calls == 1
    assert replay["idempotent_replay"] is True
    assert first["overview_publication_dispatch"]["message_id"] == "message-1"
    assert replay["overview_publication_dispatch"]["message_id"] == "message-2"
    assert sent == [
        {"report_date": "2025-12-31", "source_build_run_id": "balance-build-r"},
        {"report_date": "2025-12-31", "source_build_run_id": "balance-build-r"},
    ]

    with pytest.raises(RuntimeError, match="different identity"):
        materialize_task._materialize_balance_analysis_facts(
            **arguments,
            use_existing_fx_only=True,
        )

    GovernanceRepository(base_dir=governance_dir).append(
        "cache_build_run",
        {
            "status": "completed",
            "job_name": "balance_analysis_materialize",
            "cache_key": materialize_task.CACHE_KEY,
            "run_id": "balance-build-newer",
            "report_date": "2025-12-31",
        },
    )
    superseded = materialize_task._materialize_balance_analysis_facts(**arguments)
    assert superseded["overview_publication_dispatch"] == {
        "status": "superseded",
        "source_build_run_id": "balance-build-r",
        "latest_source_build_run_id": "balance-build-newer",
    }
    assert len(sent) == 2


def test_fact_change_invalidates_current_and_retained_even_while_read_flag_is_disabled(
    tmp_path: Path,
    balance_analysis_shared_materialized_read_seed,
) -> None:
    seed = balance_analysis_shared_materialized_read_seed
    root = tmp_path / "balance-publication"
    enabled = _settings(seed, root)
    first = publish_balance_analysis_overview(
        enabled,
        report_date="2025-12-31",
        run_id="balance-overview-run-1",
        expected_previous_generation=None,
    )
    second = publish_balance_analysis_overview(
        enabled,
        report_date="2025-12-31",
        run_id="balance-overview-run-2",
        expected_previous_generation=first.generation,
    )
    disabled = _settings(seed, root, enabled=False)

    invalidated = invalidate_balance_analysis_publications_before_fact_change(
        source_duckdb_path=seed.duckdb_path,
        report_dates=("2025-12-31",),
        reason="test historical replacement",
        settings=disabled,
    )

    assert set(invalidated) == {first.generation, second.generation}
    assert balance_analysis_publication_status(enabled)["available"] is False
    for generation in (first.generation, second.generation):
        with pytest.raises(BalanceAnalysisPublicationConflict):
            read_published_balance_analysis_overview(
                enabled,
                report_date="2025-12-31",
                position_scope="all",
                currency_basis="CNY",
                generation=generation,
            )


def test_retained_invalidation_succeeds_after_current_was_already_invalidated(
    tmp_path: Path,
    balance_analysis_shared_materialized_read_seed,
) -> None:
    seed = balance_analysis_shared_materialized_read_seed
    root = tmp_path / "balance-publication"
    settings = _settings(seed, root)
    first = publish_balance_analysis_overview(
        settings,
        report_date="2025-12-31",
        run_id="balance-overview-run-1",
        expected_previous_generation=None,
    )
    second = publish_balance_analysis_overview(
        settings,
        report_date="2025-12-31",
        run_id="balance-overview-run-2",
        expected_previous_generation=first.generation,
    )
    invalidate_financial_generation(
        root,
        generation=second.generation,
        reason="newer report date changed first",
    )

    invalidated = invalidate_balance_analysis_publications_before_fact_change(
        source_duckdb_path=seed.duckdb_path,
        report_dates=("2025-12-31",),
        reason="older retained report date changed later",
        settings=settings,
    )

    assert invalidated == (first.generation,)
    assert (root / "invalidations" / f"{first.generation}.json").is_file()


def test_historical_report_date_cannot_replace_current_publication(
    tmp_path: Path,
    balance_analysis_shared_materialized_read_seed,
) -> None:
    seed = balance_analysis_shared_materialized_read_seed
    root = tmp_path / "balance-publication"
    settings = _settings(seed, root)
    publish_balance_analysis_overview(
        settings,
        report_date="2025-12-31",
        run_id="balance-overview-run-1",
        expected_previous_generation=None,
    )

    with pytest.raises(BalanceAnalysisPublicationNotReady, match="historical"):
        _reject_historical_current_regression(root, "2025-11-30")


def test_publication_rejects_mixed_or_missing_fact_lineage(
    tmp_path: Path,
    balance_analysis_shared_materialized_read_seed,
) -> None:
    seed = balance_analysis_shared_materialized_read_seed
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    shutil.copy2(seed.duckdb_path, duckdb_path)
    shutil.copytree(seed.governance_dir, governance_dir)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update fact_formal_zqtz_balance_daily
            set rule_version = ''
            where rowid = (
              select min(rowid) from fact_formal_zqtz_balance_daily
              where cast(report_date as varchar) = '2025-12-31'
            )
            """
        )
    finally:
        conn.close()
    settings = Settings(
        duckdb_path=str(duckdb_path),
        governance_path=governance_dir,
        balance_analysis_publication_enabled=True,
        balance_analysis_publication_root=str(tmp_path / "balance-publication"),
    )

    with pytest.raises(BalanceAnalysisPublicationNotReady, match="complete and single-valued"):
        publish_balance_analysis_overview(
            settings,
            report_date="2025-12-31",
            run_id="balance-overview-run-mixed-lineage",
            expected_previous_generation=None,
        )


def test_other_duckdb_write_does_not_invalidate_configured_active_publication(
    tmp_path: Path,
    balance_analysis_shared_materialized_read_seed,
) -> None:
    seed = balance_analysis_shared_materialized_read_seed
    root = tmp_path / "balance-publication"
    settings = _settings(seed, root)
    receipt = publish_balance_analysis_overview(
        settings,
        report_date="2025-12-31",
        run_id="balance-overview-run-1",
        expected_previous_generation=None,
    )

    invalidated = invalidate_balance_analysis_publications_before_fact_change(
        source_duckdb_path=tmp_path / "unrelated.duckdb",
        report_dates=("2025-12-31",),
        reason="unrelated replay write",
        settings=settings,
    )

    assert invalidated == ()
    assert read_published_balance_analysis_overview(
        settings,
        report_date="2025-12-31",
        position_scope="all",
        currency_basis="CNY",
        generation=receipt.generation,
    ).generation == receipt.generation


def test_candidate_holds_writer_lock_and_waiting_fx_change_invalidates_it(
    tmp_path: Path,
    balance_analysis_shared_materialized_read_seed,
    monkeypatch,
) -> None:
    from backend.app.repositories import balance_analysis_publication_state as publication_state
    from backend.app.tasks import balance_analysis_overview_publication as publication_task
    from backend.app.tasks import fx_mid_materialize as fx_task

    seed = balance_analysis_shared_materialized_read_seed
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    root = tmp_path / "balance-publication"
    shutil.copy2(seed.duckdb_path, duckdb_path)
    shutil.copytree(seed.governance_dir, governance_dir)
    settings = Settings(
        duckdb_path=str(duckdb_path),
        governance_path=governance_dir,
        balance_analysis_publication_enabled=True,
        balance_analysis_publication_root=str(root),
    )
    monkeypatch.setattr(publication_task, "get_settings", lambda: settings)
    monkeypatch.setattr(publication_state, "get_settings", lambda: settings)
    real_publish = publication_task.publish_financial_result
    writer_started = threading.Event()
    writer_finished = threading.Event()
    writer_was_blocked = threading.Event()
    writer_threads: list[threading.Thread] = []

    def replace_fx_after_lock_release() -> None:
        writer_started.set()
        writer_lock = resolve_duckdb_writer_lock(duckdb_path)
        with acquire_lock(writer_lock, base_dir=duckdb_path.parent, timeout_seconds=5):
            fx_task._replace_fx_mid_rows(
                duckdb_path=str(duckdb_path),
                rows=[
                    (
                        "2025-12-31",
                        "USD",
                        "CNY",
                        "7.2",
                        "CFETS",
                        True,
                        False,
                        "sv_fx_after_candidate",
                        "choice",
                        "vv_fx_after_candidate",
                        "EMM00058124",
                        "2025-12-31",
                    )
                ],
            )
        writer_finished.set()

    def publish_with_concurrent_writer(**kwargs):
        def on_stage(stage: str) -> None:
            if stage != "candidate_sealed":
                return
            writer = threading.Thread(target=replace_fx_after_lock_release, daemon=True)
            writer_threads.append(writer)
            writer.start()
            assert writer_started.wait(timeout=1)
            if not writer_finished.wait(timeout=0.1):
                writer_was_blocked.set()

        return real_publish(**kwargs, on_stage=on_stage)

    monkeypatch.setattr(publication_task, "publish_financial_result", publish_with_concurrent_writer)
    receipt = publication_task.publish_balance_analysis_overview(
        settings,
        report_date="2025-12-31",
        run_id="balance-overview-race",
        expected_previous_generation=None,
    )
    for writer in writer_threads:
        writer.join(timeout=5)

    assert writer_was_blocked.is_set()
    assert writer_finished.is_set()
    with pytest.raises(BalanceAnalysisPublicationConflict):
        read_published_balance_analysis_overview(
            settings,
            report_date="2025-12-31",
            position_scope="all",
            currency_basis="CNY",
            generation=receipt.generation,
        )


def test_active_read_anchor_blocks_uncoordinated_writer_after_candidate_is_sealed(
    tmp_path: Path,
    balance_analysis_shared_materialized_read_seed,
    monkeypatch,
) -> None:
    from backend.app.tasks import balance_analysis_overview_publication as publication_task

    seed = balance_analysis_shared_materialized_read_seed
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    shutil.copy2(seed.duckdb_path, duckdb_path)
    shutil.copytree(seed.governance_dir, governance_dir)
    settings = Settings(
        duckdb_path=str(duckdb_path),
        governance_path=governance_dir,
        balance_analysis_publication_enabled=True,
        balance_analysis_publication_root=str(tmp_path / "balance-publication"),
    )
    real_publish = publication_task.publish_financial_result
    blocked_after_seal = False

    def publish_with_uncoordinated_writer(**kwargs):
        def on_stage(stage: str) -> None:
            nonlocal blocked_after_seal
            if stage != "candidate_sealed":
                return
            try:
                writer = duckdb.connect(str(duckdb_path), read_only=False)
            except duckdb.Error:
                blocked_after_seal = True
            else:
                writer.close()

        return real_publish(**kwargs, on_stage=on_stage)

    monkeypatch.setattr(publication_task, "publish_financial_result", publish_with_uncoordinated_writer)
    publication_task.publish_balance_analysis_overview(
        settings,
        report_date="2025-12-31",
        run_id="balance-overview-anchor",
        expected_previous_generation=None,
    )

    assert blocked_after_seal is True


def test_explicit_generation_never_falls_back_to_active_overview(monkeypatch) -> None:
    settings = Settings(
        balance_analysis_publication_enabled=True,
        balance_analysis_publication_root="published-balance",
    )
    monkeypatch.setattr(balance_routes, "get_settings", lambda: settings)
    monkeypatch.setattr(balance_routes, "_ensure_balance_analysis_read_allowed", lambda _auth: None)
    monkeypatch.setattr(
        balance_routes,
        "read_published_balance_analysis_overview",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            BalanceAnalysisPublicationConflict("revoked generation")
        ),
    )
    monkeypatch.setattr(
        balance_routes,
        "balance_analysis_overview_envelope",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("explicit generation fell back to the active database")
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        balance_routes.overview(
            auth=AuthContext(),
            response=Response(),
            report_date="2025-12-31",
            position_scope="all",
            currency_basis="CNY",
            generation="revoked-generation",
        )

    assert exc_info.value.status_code == 409


def test_balance_and_pnl_publication_roots_cannot_share_a_pointer(tmp_path: Path) -> None:
    root = tmp_path / "published"
    with pytest.raises(ValueError, match="must be separate"):
        Settings(
            financial_publication_root=str(root),
            balance_analysis_publication_root=str(root),
        )


def test_fx_replace_aborts_before_database_change_when_balance_invalidation_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from backend.app.repositories import balance_analysis_publication_state as publication_state
    from backend.app.tasks import fx_mid_materialize as fx_task

    duckdb_path = tmp_path / "moss.duckdb"
    observed: dict[str, object] = {}

    def fail_invalidation(*, source_duckdb_path, report_dates, reason, settings=None):
        observed.update(
            source_duckdb_path=source_duckdb_path,
            report_dates=report_dates,
            reason=reason,
            settings=settings,
        )
        raise RuntimeError("governance unavailable")

    monkeypatch.setattr(
        publication_state,
        "invalidate_balance_analysis_publications_before_fact_change",
        fail_invalidation,
    )

    with pytest.raises(RuntimeError, match="governance unavailable"):
        fx_task._replace_fx_mid_rows(
            duckdb_path=str(duckdb_path),
            rows=[
                (
                    "2025-12-31",
                    "USD",
                    "CNY",
                    "7.1",
                    "CFETS",
                    True,
                    False,
                    "sv_fx_test",
                    "choice",
                    "vv_fx_test",
                    "EMM00058124",
                    "2025-12-31",
                )
            ],
        )

    assert observed == {
        "source_duckdb_path": str(duckdb_path),
        "report_dates": ("2025-12-31",),
        "reason": "formal_fx_mid_replace",
        "settings": None,
    }
    assert not duckdb_path.exists()
