from __future__ import annotations

import ast
import asyncio
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, date
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from backend.app.api.routes.system_read_publication import router as system_read_publication_router
from backend.app.governance.settings import get_settings
from backend.app.main import SystemReadPublicationMiddleware
from backend.app.observability.response_cache import TTLResponseCache
from backend.app.repositories import financial_result_publication_repo as publication_repo
from backend.app.repositories.cube_query_repo import CubeQueryRepository
from backend.app.repositories.duckdb_read_context import (
    DuckDBOnlineReadRequiredError,
    current_duckdb_read_selection,
)
from backend.app.repositories.duckdb_repo import read_only_connection
from backend.app.repositories.financial_result_publication_repo import (
    FINANCIAL_PUBLICATION_API_VERSION,
    FINANCIAL_PUBLICATION_SCHEMA_VERSION,
    PUBLICATION_MANIFEST_TABLE,
    PUBLICATION_PROTOCOL_VERSION,
    FinancialPublicationInvalid,
    FinancialPublicationUnavailable,
    canonical_json_bytes,
    generation_invalidation_path,
    sha256_bytes,
    sha256_file,
)
from backend.app.repositories.governance_repo import (
    AGENT_AUDIT_STREAM,
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.repositories.system_read_publication_repo import (
    SYSTEM_READ_API_VERSION,
    SYSTEM_READ_GENERATION_HEADER,
    SYSTEM_READ_SCHEMA_VERSION,
    active_system_read_scope,
    async_system_read_scope,
    current_system_read_context,
    current_system_read_publication,
    frozen_system_governance_rows,
    open_system_pnl_generation,
    resolve_system_read_publication,
    system_read_publication_root,
    system_read_scope,
)
from backend.app.repositories.user_scope_repo import UserScopeRepository
from backend.app.services import pnl_service
from backend.app.services.runtime_cache import InMemoryTTLCache
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV


def _seal_generation(
    root: Path,
    generation: str,
    sentinel: str,
    *,
    system_read_bundle: dict[str, object] | None = None,
    expires_at: str | None = None,
) -> str:
    generations = root / "generations"
    generations.mkdir(parents=True, exist_ok=True)
    database_path = generations / f"{generation}.duckdb"
    manifest_path = generations / f"{generation}.manifest.json"
    sealed_payload: dict[str, object] = {
        "protocol_version": PUBLICATION_PROTOCOL_VERSION,
        "generation": generation,
        "tables": [],
        "coverage_dates": {"sentinel": ["2026-09-15"]},
        "compatibility": {
            "supported_api_versions": [FINANCIAL_PUBLICATION_API_VERSION],
            "supported_schema_versions": [FINANCIAL_PUBLICATION_SCHEMA_VERSION],
        },
        "validity": {"state": "valid"},
    }
    if expires_at is not None:
        sealed_payload["validity"]["expires_at"] = expires_at
    if system_read_bundle is not None:
        sealed_payload["system_read_bundle"] = system_read_bundle
        sealed_payload["compatibility"] = {
            "supported_api_versions": [SYSTEM_READ_API_VERSION],
            "supported_schema_versions": [SYSTEM_READ_SCHEMA_VERSION],
        }
    sealed_payload_bytes = canonical_json_bytes(sealed_payload)
    sealed_payload_sha256 = sha256_bytes(sealed_payload_bytes)

    conn = duckdb.connect(str(database_path))
    try:
        conn.execute("CREATE TABLE sentinel(value VARCHAR)")
        conn.execute("INSERT INTO sentinel VALUES (?)", [sentinel])
        conn.execute(
            f'CREATE TABLE "{PUBLICATION_MANIFEST_TABLE}"('
            "protocol_version VARCHAR NOT NULL, generation VARCHAR NOT NULL, "
            "sealed_payload_json VARCHAR NOT NULL, sealed_payload_sha256 VARCHAR NOT NULL)"
        )
        conn.execute(
            f'INSERT INTO "{PUBLICATION_MANIFEST_TABLE}" VALUES (?, ?, ?, ?)',
            [
                PUBLICATION_PROTOCOL_VERSION,
                generation,
                sealed_payload_bytes.decode("utf-8"),
                sealed_payload_sha256,
            ],
        )
        conn.execute("CHECKPOINT")
    finally:
        conn.close()

    manifest = {
        "protocol_version": PUBLICATION_PROTOCOL_VERSION,
        "generation": generation,
        "sealed_payload": sealed_payload,
        "sealed_payload_sha256": sealed_payload_sha256,
        "database": {
            "file_name": database_path.name,
            "size_bytes": database_path.stat().st_size,
            "sha256": sha256_file(database_path),
        },
        "validity": sealed_payload["validity"],
        "compatibility": sealed_payload["compatibility"],
    }
    manifest_bytes = canonical_json_bytes(manifest)
    manifest_path.write_bytes(manifest_bytes)
    return sha256_bytes(manifest_bytes)


def _write_pointer(
    root: Path,
    current_generation: str,
    retained: list[tuple[str, str]],
) -> None:
    current_digest = next(digest for generation, digest in retained if generation == current_generation)
    pointer = {
        "protocol_version": PUBLICATION_PROTOCOL_VERSION,
        "generation": current_generation,
        "manifest_sha256": current_digest,
        "validity": {"state": "valid"},
        "retained_generations": [
            {"generation": generation, "manifest_sha256": digest}
            for generation, digest in retained
        ],
    }
    (root / "current.json").write_bytes(canonical_json_bytes(pointer))


def _settings(tmp_path: Path) -> SimpleNamespace:
    governance_path = tmp_path / "governance"
    financial_root = tmp_path / "pnl-publications"
    active = tmp_path / "active.duckdb"
    conn = duckdb.connect(str(active))
    try:
        conn.execute("CREATE TABLE sentinel(value VARCHAR)")
        conn.execute("INSERT INTO sentinel VALUES ('ACTIVE')")
    finally:
        conn.close()
    return SimpleNamespace(
        system_read_publication_enabled=True,
        governance_path=governance_path,
        financial_publication_root=str(financial_root),
        duckdb_path=str(active),
    )


def _bundle(settings: SimpleNamespace, pnl_generation: str, pnl_digest: str) -> dict[str, object]:
    return {
        "protocol_version": 1,
        "full_database": True,
        "active_database_identity": str(Path(settings.duckdb_path).resolve()),
        "governance_base_identity": str(Path(settings.governance_path).resolve()),
        "governance_streams": {
            "cache_build_run": [
                {
                    "run_id": "run-1",
                    "cache_key": "frozen-key",
                    "status": "completed",
                }
            ],
            "cache_manifest": [
                {
                    "run_id": "run-1",
                    "cache_key": "frozen-key",
                    "lineage": {"inputs": ["source-r0"]},
                }
            ],
        },
        "pnl_generation": pnl_generation,
        "pnl_manifest_sha256": pnl_digest,
        "data_update_run_id": "update-1",
        "global_run_id": "global-1",
        "workflow": "global-data-refresh",
        "report_date": "2026-09-15",
    }


def _publish_fixture(
    settings: SimpleNamespace, *, expires_at: str | None = None
) -> tuple[str, str]:
    pnl_root = Path(settings.financial_publication_root)
    pnl_digest = _seal_generation(pnl_root, "pnl-r0", "PNL")
    _write_pointer(pnl_root, "pnl-r0", [("pnl-r0", pnl_digest)])

    system_root = system_read_publication_root(settings)
    digest_r0 = _seal_generation(
        system_root,
        "system-read-2026-09-15-00000000000000000000",
        "R0",
        system_read_bundle=_bundle(settings, "pnl-r0", pnl_digest),
        expires_at=expires_at,
    )
    digest_r1 = _seal_generation(
        system_root,
        "system-read-2026-09-15-11111111111111111111",
        "R1",
        system_read_bundle=_bundle(settings, "pnl-r0", pnl_digest),
        expires_at=expires_at,
    )
    generation_r0 = "system-read-2026-09-15-00000000000000000000"
    generation_r1 = "system-read-2026-09-15-11111111111111111111"
    _write_pointer(system_root, generation_r1, [(generation_r1, digest_r1), (generation_r0, digest_r0)])
    return generation_r0, generation_r1


def test_system_read_scope_pins_complete_generation_and_restores_active(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    older_generation, current_generation = _publish_fixture(settings)

    resolved = resolve_system_read_publication(settings)
    assert resolved.generation == current_generation
    with system_read_scope(settings, generation=older_generation):
        assert current_system_read_publication() is not None
        assert current_system_read_publication().generation == older_generation
        context = current_system_read_context()
        assert context is not None
        assert context.pnl_publication.generation == "pnl-r0"
        assert dict(context.pretrade_availability) == {
            "schema": "pretrade_qualification/v1",
            "status": "unavailable",
            "reason": "legacy_system_read_bundle_has_no_pretrade_qualification",
        }
        assert context.governance_streams["cache_build_run"] == (
            {
                "run_id": "run-1",
                "cache_key": "frozen-key",
                "status": "completed",
            },
        )
        assert context.governance_streams["cache_manifest"] == (
            {
                "run_id": "run-1",
                "cache_key": "frozen-key",
                "lineage": {"inputs": ("source-r0",)},
            },
        )
        frozen_rows = frozen_system_governance_rows(
            settings.governance_path,
            "cache_manifest",
        )
        assert frozen_rows == [
            {
                "run_id": "run-1",
                "cache_key": "frozen-key",
                "lineage": {"inputs": ["source-r0"]},
            }
        ]
        frozen_rows[0]["run_id"] = "mutated-copy"
        assert frozen_system_governance_rows(
            settings.governance_path,
            "cache_manifest",
        ) == [
            {
                "run_id": "run-1",
                "cache_key": "frozen-key",
                "lineage": {"inputs": ["source-r0"]},
            }
        ]
        with read_only_connection(settings.duckdb_path) as conn:
            assert conn.execute("SELECT value FROM sentinel").fetchone() == ("R0",)

        with active_system_read_scope():
            assert current_system_read_context() is None
            assert frozen_system_governance_rows(
                settings.governance_path,
                "cache_manifest",
            ) is None
            with read_only_connection(settings.duckdb_path) as conn:
                assert conn.execute("SELECT value FROM sentinel").fetchone() == ("ACTIVE",)

        assert current_system_read_publication() is not None
        assert current_system_read_publication().generation == older_generation
        with read_only_connection(settings.duckdb_path) as conn:
            assert conn.execute("SELECT value FROM sentinel").fetchone() == ("R0",)

    assert current_system_read_context() is None
    with read_only_connection(settings.duckdb_path) as conn:
        assert conn.execute("SELECT value FROM sentinel").fetchone() == ("ACTIVE",)



@pytest.mark.parametrize("exit_mode", ["completed", "exception", "cancelled"])
def test_async_system_read_scope_restores_outer_pins_after_exit(
    tmp_path: Path, exit_mode: str
) -> None:
    settings = _settings(tmp_path)
    previous_generation, current_generation = _publish_fixture(settings)

    async def check_scope() -> None:
        outer_context = current_system_read_context()
        outer_selection = current_duckdb_read_selection()
        assert outer_context is not None and outer_context.generation == previous_generation
        assert outer_selection is not None and outer_selection.generation == previous_generation
        try:
            async with async_system_read_scope(settings) as publication:
                assert publication is not None and publication.generation == current_generation
                assert current_system_read_context().generation == current_generation
                assert current_duckdb_read_selection().generation == current_generation
                with read_only_connection(settings.duckdb_path) as conn:
                    assert conn.execute("SELECT value FROM sentinel").fetchone() == ("R1",)
                if exit_mode == "exception":
                    raise RuntimeError("Injected downstream failure")
                if exit_mode == "cancelled":
                    task = asyncio.current_task()
                    assert task is not None
                    task.cancel()
                    await asyncio.sleep(0)
        except RuntimeError as exc:
            assert exit_mode == "exception" and str(exc) == "Injected downstream failure"
        except asyncio.CancelledError:
            assert exit_mode == "cancelled"
        else:
            assert exit_mode == "completed"
        assert current_system_read_context() is outer_context
        assert current_duckdb_read_selection() is outer_selection

    with system_read_scope(settings, generation=previous_generation):
        asyncio.run(check_scope())
        assert current_system_read_context().generation == previous_generation
        assert current_duckdb_read_selection().generation == previous_generation
    assert current_system_read_context() is None
    assert current_duckdb_read_selection() is None


def test_system_read_resolver_rejects_invalid_pnl_reference(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    pnl_root = Path(settings.financial_publication_root)
    pnl_digest = _seal_generation(pnl_root, "pnl-r0", "PNL")
    _write_pointer(pnl_root, "pnl-r0", [("pnl-r0", pnl_digest)])
    system_root = system_read_publication_root(settings)
    system_digest = _seal_generation(
        system_root,
        "system-read-2026-09-15-00000000000000000000",
        "R0",
        system_read_bundle=_bundle(settings, "pnl-r0", "0" * 64),
    )
    system_generation = "system-read-2026-09-15-00000000000000000000"
    _write_pointer(system_root, system_generation, [(system_generation, system_digest)])

    with pytest.raises(FinancialPublicationInvalid, match="pointer does not match"):
        resolve_system_read_publication(settings)


def test_system_read_resolver_rejects_wrong_active_database_identity(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _publish_fixture(settings)
    other_active = tmp_path / "other-active.duckdb"
    conn = duckdb.connect(str(other_active))
    conn.close()
    mismatched_settings = SimpleNamespace(
        **{
            **vars(settings),
            "duckdb_path": str(other_active),
        }
    )

    with pytest.raises(FinancialPublicationInvalid, match="active database identity"):
        resolve_system_read_publication(mismatched_settings)


def test_governance_repository_freezes_only_lineage_allowlist_and_returns_copies(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    older_generation, _ = _publish_fixture(settings)
    repository = GovernanceRepository(base_dir=settings.governance_path)
    repository.append(
        CACHE_MANIFEST_STREAM,
        {"cache_key": "live-key", "lineage": {"inputs": ["live"]}},
    )
    repository.append(
        CACHE_BUILD_RUN_STREAM,
        {"run_id": "live-run", "cache_key": "live-key", "status": "completed"},
    )
    repository.append(AGENT_AUDIT_STREAM, {"event": "live-audit"})

    with system_read_scope(settings, generation=older_generation):
        manifests = repository.read_all(CACHE_MANIFEST_STREAM)
        assert [row["cache_key"] for row in manifests] == ["frozen-key"]
        manifests[0]["lineage"]["inputs"].append("mutated")
        assert repository.read_by_cache_keys(
            CACHE_MANIFEST_STREAM,
            ["frozen-key"],
        )[0]["lineage"] == {"inputs": ["source-r0"]}
        assert repository.read_latest_manifest("frozen-key")["run_id"] == "run-1"
        assert repository.read_latest_completed_run("frozen-key")["run_id"] == "run-1"
        assert repository.read_all(AGENT_AUDIT_STREAM)[0]["event"] == "live-audit"

    assert repository.read_all(CACHE_MANIFEST_STREAM)[0]["cache_key"] == "live-key"


def test_response_cache_isolated_by_pinned_system_generation(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    older_generation, current_generation = _publish_fixture(settings)
    cache = TTLResponseCache(default_ttl_seconds=60.0)

    with system_read_scope(settings, generation=older_generation):
        assert cache.get_or_build("shared", lambda: "R0") == "R0"
    with system_read_scope(settings, generation=current_generation):
        assert cache.get_or_build("shared", lambda: "R1") == "R1"
    with system_read_scope(settings, generation=older_generation):
        assert cache.get_or_build("shared", lambda: "wrong") == "R0"
    assert cache.get_or_build("shared", lambda: "ACTIVE") == "ACTIVE"


def test_runtime_cache_isolated_by_pinned_system_generation(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    older_generation, current_generation = _publish_fixture(settings)
    cache = InMemoryTTLCache[str, str](ttl_seconds=60.0)
    calls: list[str] = []

    def build() -> str:
        context = current_system_read_context()
        assert context is not None
        calls.append(context.generation)
        return context.generation

    with system_read_scope(settings, generation=older_generation):
        assert cache.get_or_set("shared", build) == older_generation
        assert cache.get_or_set("shared", build) == older_generation
    with system_read_scope(settings, generation=current_generation):
        assert cache.get_or_set("shared", build) == current_generation
    with active_system_read_scope():
        assert cache.get_or_set("shared", lambda: "active") == "active"

    assert calls == [older_generation, current_generation]


def test_runtime_cache_matching_invalidation_preserves_original_key_shape(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    older_generation, current_generation = _publish_fixture(settings)
    cache = InMemoryTTLCache[tuple[str, int], str](ttl_seconds=60.0)
    observed: list[tuple[str, int]] = []

    for generation in (older_generation, current_generation):
        with system_read_scope(settings, generation=generation):
            cache.set(("shared", 1), generation)

    def predicate(key: tuple[str, int]) -> bool:
        observed.append(key)
        return key[0] == "shared"

    cache.invalidate_matching(predicate)

    assert observed == [("shared", 1), ("shared", 1)]
    for generation in (older_generation, current_generation):
        with system_read_scope(settings, generation=generation):
            assert cache.get(("shared", 1)) == (False, None)


def test_pnl_analysis_input_cache_uses_effective_snapshot_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    older_generation, current_generation = _publish_fixture(settings)
    calls: list[tuple[str, str]] = []

    def fetch_pnl(self, *, year: int, as_of_date: str):
        context = current_system_read_context()
        assert context is not None
        calls.append(("pnl", context.generation))
        return [{"generation": context.generation, "year": year, "date": as_of_date}]

    def fetch_balance(self, *, start_date: str, end_date: str):
        context = current_system_read_context()
        assert context is not None
        calls.append(("balance", context.generation))
        return [{"generation": context.generation, "start": start_date, "end": end_date}]

    monkeypatch.setattr(pnl_service.PnlRepository, "fetch_by_business_analysis_pnl_rows", fetch_pnl)
    monkeypatch.setattr(
        pnl_service.PnlRepository,
        "fetch_by_business_analysis_balance_rows",
        fetch_balance,
    )
    pnl_service._clear_pnl_by_business_analysis_cache()
    try:
        with system_read_scope(settings, generation=older_generation):
            older = pnl_service._pnl_by_business_analysis_inputs(
                settings.duckdb_path, 2026, "2026-01-01", "2026-09-15"
            )
        with system_read_scope(settings, generation=current_generation):
            current = pnl_service._pnl_by_business_analysis_inputs(
                settings.duckdb_path, 2026, "2026-01-01", "2026-09-15"
            )
        with system_read_scope(settings, generation=older_generation):
            older_again = pnl_service._pnl_by_business_analysis_inputs(
                settings.duckdb_path, 2026, "2026-01-01", "2026-09-15"
            )
    finally:
        pnl_service._clear_pnl_by_business_analysis_cache()

    assert older[0][0]["generation"] == older_generation
    assert current[0][0]["generation"] == current_generation
    assert older_again == older
    assert calls == [
        ("pnl", older_generation),
        ("balance", older_generation),
        ("pnl", current_generation),
        ("balance", current_generation),
    ]


def test_native_home_warmup_thread_receives_copied_system_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.services import executive_service

    settings = _settings(tmp_path)
    _, current_generation = _publish_fixture(settings)
    settings.home_snapshot_prewarm_enabled = True
    observed: list[str | None] = []
    completed = threading.Event()

    def capture_context(**_kwargs: object) -> None:
        context = current_system_read_context()
        observed.append(context.generation if context is not None else None)
        completed.set()

    monkeypatch.setattr(executive_service, "_warm_home_snapshot_cache_quietly", capture_context)
    with system_read_scope(settings):
        assert executive_service.warm_home_snapshot_cache_if_configured(settings) is True

    assert completed.wait(timeout=5.0)
    assert observed == [current_generation]


def test_home_cache_fingerprint_uses_effective_snapshot_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.services import executive_service

    settings = _settings(tmp_path)
    older_generation, current_generation = _publish_fixture(settings)
    monkeypatch.setattr(executive_service, "get_settings", lambda: settings)

    with system_read_scope(settings, generation=older_generation):
        older_token = executive_service._home_data_version_token()
    with system_read_scope(settings, generation=current_generation):
        current_token = executive_service._home_data_version_token()

    assert older_token[0].endswith(f"{older_generation}.duckdb")
    assert current_token[0].endswith(f"{current_generation}.duckdb")
    assert older_token[0] != current_token[0]


def test_home_domain_date_fallback_does_not_swallow_required_online_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.services import executive_service

    settings = _settings(tmp_path)
    _, current_generation = _publish_fixture(settings)
    monkeypatch.setattr(executive_service, "get_settings", lambda: settings)

    def fail_required(_self):
        raise DuckDBOnlineReadRequiredError("snapshot disappeared")

    monkeypatch.setattr(
        executive_service.DashboardRepository,
        "list_domain_date_context",
        fail_required,
    )
    with system_read_scope(settings, generation=current_generation):
        with pytest.raises(DuckDBOnlineReadRequiredError, match="snapshot disappeared"):
            executive_service._list_domain_date_context()


def test_native_market_home_warmup_receives_pin_and_effective_snapshot_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.services import market_home_warmup_service

    settings = _settings(tmp_path)
    _, current_generation = _publish_fixture(settings)
    settings.market_home_prewarm_enabled = True
    observed: list[tuple[str | None, str]] = []
    completed = threading.Event()

    def capture_context(*, duckdb_path: str, **_kwargs: object) -> None:
        context = current_system_read_context()
        observed.append((context.generation if context is not None else None, duckdb_path))
        completed.set()

    monkeypatch.setattr(
        market_home_warmup_service,
        "_warm_market_home_cache_quietly",
        capture_context,
    )
    with system_read_scope(settings, generation=current_generation):
        assert market_home_warmup_service.warm_market_home_cache_if_configured(settings) is True

    assert completed.wait(timeout=5.0)
    assert observed[0][0] == current_generation
    assert observed[0][1].endswith(f"{current_generation}.duckdb")


def test_market_home_settings_view_and_direct_service_reads_use_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.repositories import (
        home_macro_release_context_repo,
        livermore_market_read_repo,
        macro_bond_linkage_repo,
        yield_curve_repo,
    )
    from backend.app.services import (
        macro_toolkit_service,
        macro_vendor_service,
        market_home_warmup_service,
    )

    settings = _settings(tmp_path)
    _, current_generation = _publish_fixture(settings)
    active_path = str(Path(settings.duckdb_path).resolve())
    recorded_read_paths: list[str] = []
    original_connect = duckdb.connect

    with system_read_scope(settings, generation=current_generation):
        context = current_system_read_context()
        assert context is not None
        snapshot_path = str(context.publication.database_path.resolve())
        read_settings = market_home_warmup_service._settings_for_effective_duckdb_path(
            settings,
            snapshot_path,
        )
        assert str(read_settings.duckdb_path) == snapshot_path
        assert str(Path(settings.duckdb_path).resolve()) == active_path

        def recording_connect(database: object, *args: object, **kwargs: object):
            if kwargs.get("read_only") is True:
                recorded_read_paths.append(str(Path(str(database)).resolve()))
            return original_connect(database, *args, **kwargs)

        monkeypatch.setattr(macro_vendor_service.duckdb, "connect", recording_connect)
        macro_vendor_service._load_macro_vendor_source_version(settings.duckdb_path, ["x"])
        macro_toolkit_service.commodity_futures_status(settings.duckdb_path)
        yield_curve_repo.YieldCurveRepository(settings.duckdb_path).fetch_curve(
            "2026-09-15",
            "treasury",
        )
        livermore_conn = livermore_market_read_repo.open_livermore_read_connection(snapshot_path)
        assert livermore_conn is not None
        livermore_conn.close()
        home_macro_release_context_repo.HomeMacroReleaseContextRepository(
            snapshot_path
        ).read_recent_observations(
            table="fact_choice_macro_daily",
            series_id="x",
            cutoff_date=date(2026, 9, 15),
            limit=1,
        )
        macro_bond_linkage_repo.MacroBondLinkageRepository(
            settings.duckdb_path,
            guard_path_exists=True,
        ).relation_exists("fact_choice_macro_daily")

    assert recorded_read_paths == [snapshot_path] * 6
    assert active_path not in recorded_read_paths


def test_market_home_direct_service_read_connections_resolve_effective_path() -> None:
    for relative_path in (
        "backend/app/services/macro_vendor_service.py",
        "backend/app/services/macro_toolkit_service.py",
    ):
        source = Path(relative_path).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=relative_path)
        read_connections = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "duckdb"
            and node.func.attr == "connect"
            and any(
                keyword.arg == "read_only"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
                for keyword in node.keywords
            )
        ]
        assert read_connections
        for connection in read_connections:
            assert connection.args
            assert "resolve_effective_read_path" in ast.dump(connection.args[0])


def test_home_thread_pool_submissions_copy_the_current_context() -> None:
    for relative_path in (
        "backend/app/services/executive_service.py",
        "backend/app/services/market_overview_service.py",
    ):
        source = Path(relative_path).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=relative_path)
        submissions = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "submit"
        ]
        assert submissions
        for submission in submissions:
            assert submission.args
            assert "copy_context" in ast.dump(submission.args[0])


def test_market_overview_component_threads_receive_independent_context_copies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.services import market_overview_service

    settings = _settings(tmp_path)
    _, current_generation = _publish_fixture(settings)
    observed: list[tuple[str, str | None]] = []

    def capture_component(name: str, **_kwargs: object):
        context = current_system_read_context()
        observed.append((name, context.generation if context is not None else None))
        return object()

    monkeypatch.setattr(market_overview_service, "_load_cached_component", capture_component)
    health = SimpleNamespace(cache_fingerprint="test")
    with system_read_scope(settings, generation=current_generation):
        components = market_overview_service._load_components(
            component_names={"choice_latest", "market_rates"},
            duckdb_path=settings.duckdb_path,
            refresh_receipt_health=health,
        )

    assert set(components) == {"choice_latest", "market_rates"}
    assert sorted(observed) == [
        ("choice_latest", current_generation),
        ("market_rates", current_generation),
    ]


def test_executive_home_domain_threads_receive_independent_context_copies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.services import executive_service

    settings = _settings(tmp_path)
    _, current_generation = _publish_fixture(settings)
    observed: list[tuple[str, str | None]] = []
    monkeypatch.setattr(executive_service, "get_settings", lambda: settings)
    monkeypatch.setattr(
        executive_service,
        "_read_cache_build_runs_for_executive_overview",
        lambda _governance_dir: [],
    )

    def failing_repository(name: str):
        def factory(_duckdb_path: str):
            context = current_system_read_context()
            observed.append((name, context.generation if context is not None else None))
            raise RuntimeError("context probe")

        return factory

    for repository_name in (
        "FormalZqtzBalanceMetricsRepository",
        "PnlRepository",
        "LiabilityAnalyticsRepository",
        "BondAnalyticsRepository",
    ):
        monkeypatch.setattr(
            executive_service,
            repository_name,
            failing_repository(repository_name),
        )

    with system_read_scope(settings, generation=current_generation):
        executive_service._compute_executive_overview(
            date_context={"balance": [], "pnl": [], "liability": [], "bond": []},
        )

    assert sorted(observed) == [
        ("BondAnalyticsRepository", current_generation),
        ("FormalZqtzBalanceMetricsRepository", current_generation),
        ("LiabilityAnalyticsRepository", current_generation),
        ("PnlRepository", current_generation),
    ]


def test_pinned_pnl_generation_does_not_follow_moved_pnl_pointer(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _, system_generation = _publish_fixture(settings)
    pnl_root = Path(settings.financial_publication_root)
    pnl_r1_digest = _seal_generation(pnl_root, "pnl-r1", "PNL-R1")
    _write_pointer(pnl_root, "pnl-r1", [("pnl-r1", pnl_r1_digest)])

    with system_read_scope(settings, generation=system_generation):
        with open_system_pnl_generation(settings, generation=None) as (conn, resolved):
            assert resolved.generation == "pnl-r0"
            assert conn.execute("SELECT value FROM sentinel").fetchone() == ("PNL",)
        with pytest.raises(FinancialPublicationUnavailable, match="does not match the pinned"):
            with open_system_pnl_generation(settings, generation="pnl-r1"):
                pass
        pnl_invalidation = generation_invalidation_path(pnl_root, "pnl-r0")
        pnl_invalidation.parent.mkdir(parents=True, exist_ok=True)
        pnl_invalidation.write_bytes(canonical_json_bytes({"reason": "test PnL revocation"}))
        with pytest.raises(FinancialPublicationUnavailable, match="invalidated"):
            with open_system_pnl_generation(settings, generation=None):
                pass

    with open_system_pnl_generation(settings, generation=None) as (conn, resolved):
        assert resolved.generation == "pnl-r1"
        assert conn.execute("SELECT value FROM sentinel").fetchone() == ("PNL-R1",)


def test_cached_system_context_still_rechecks_invalidation(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _, system_generation = _publish_fixture(settings)
    context_ids: list[int] = []
    for _ in range(2):
        with system_read_scope(settings, generation=system_generation):
            context = current_system_read_context()
            assert context is not None
            context_ids.append(id(context))
    assert context_ids[0] == context_ids[1]

    invalidation = generation_invalidation_path(
        system_read_publication_root(settings),
        system_generation,
    )
    invalidation.parent.mkdir(parents=True, exist_ok=True)
    invalidation.write_bytes(canonical_json_bytes({"reason": "test revocation"}))
    with pytest.raises(FinancialPublicationUnavailable, match="invalidated"):
        with system_read_scope(settings, generation=system_generation):
            pass


@pytest.mark.parametrize("explicit", [False, True], ids=["default", "explicit"])
@pytest.mark.parametrize("change", ["retained", "discarded", "invalidation", "expiry", "invalid_current"])
def test_system_scope_rechecks_fixed_generation_after_pnl_validation_wait(
    tmp_path: Path, monkeypatch, explicit: bool, change: str
) -> None:
    settings = _settings(tmp_path)
    _, selected_generation = _publish_fixture(settings, expires_at="2099-01-01T00:00:00+00:00")
    root = system_read_publication_root(settings)
    original_pointer = publication_repo.read_publication_pointer(root)
    selected_digest = original_pointer["manifest_sha256"]
    pnl_root = Path(settings.financial_publication_root)
    bundle = _bundle(settings, "pnl-r0", publication_repo.read_publication_pointer(pnl_root)["manifest_sha256"])
    new_generation = "system-read-2026-09-15-22222222222222222222"
    latest_generation = "system-read-2026-09-15-33333333333333333333"
    new_digest = _seal_generation(root, new_generation, "R2", system_read_bundle=bundle)
    latest_digest = _seal_generation(root, latest_generation, "R3", system_read_bundle=bundle)
    publication_repo.reset_financial_publication_validation_cache()
    pnl_validation_started = threading.Event()
    release_validation = threading.Event()
    pnl_waiter_joined = threading.Event()
    validation_calls: list[Path] = []
    original_validate = publication_repo._validate_database_artifact

    class ObservedFuture(Future):
        def result(self, *args, **kwargs):
            pnl_waiter_joined.set()
            return super().result(*args, **kwargs)

    def hold_pnl_validation(path: Path, manifest):
        validation_calls.append(path)
        if path.stem == "pnl-r0":
            pnl_validation_started.set()
            assert release_validation.wait(10), "Shared PnL validation was not released."
        original_validate(path, manifest)

    def read_system_scope() -> tuple[str, str]:
        with system_read_scope(settings, generation=selected_generation if explicit else None) as publication:
            assert publication is not None
            with read_only_connection(settings.duckdb_path) as conn:
                return publication.generation, conn.execute("SELECT value FROM sentinel").fetchone()[0]

    monkeypatch.setattr(publication_repo, "Future", ObservedFuture)
    monkeypatch.setattr(publication_repo, "_validate_database_artifact", hold_pnl_validation)
    with ThreadPoolExecutor(max_workers=2) as pool:
        owner = pool.submit(
            publication_repo.resolve_financial_generation, pnl_root, generation=None,
            reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
            reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
        )
        reader = None
        try:
            assert pnl_validation_started.wait(10)
            reader = pool.submit(read_system_scope)
            assert pnl_waiter_joined.wait(10), "The system reader must join PnL validation after resolving its system generation."
            if change == "retained":
                _write_pointer(root, new_generation, [(new_generation, new_digest), (selected_generation, selected_digest)])
            elif change == "discarded":
                _write_pointer(root, latest_generation, [(latest_generation, latest_digest), (new_generation, new_digest)])
            elif change == "invalidation":
                publication_repo.invalidate_financial_generation(root, generation=selected_generation, reason="Waiting system reader revoked")
            elif change == "expiry":
                real_datetime = publication_repo.datetime

                class ExpiredClock(real_datetime):
                    @classmethod
                    def now(cls, tz=None):
                        value = cls(2100, 1, 1, tzinfo=UTC)
                        return value if tz is not None else value.replace(tzinfo=None)

                monkeypatch.setattr(publication_repo, "datetime", ExpiredClock)
            else:
                original_pointer["validity"] = {"state": "invalid"}
                (root / "current.json").write_bytes(canonical_json_bytes(original_pointer))
        finally:
            release_validation.set()
        assert owner.result(timeout=10).generation == "pnl-r0"
        assert reader is not None
        if change == "retained" or (change == "invalid_current" and explicit):
            assert reader.result(timeout=10) == (selected_generation, "R1")
        else:
            message = {"discarded": "retention window", "invalidation": "invalidated", "expiry": "expired", "invalid_current": "not valid"}[change]
            with pytest.raises(FinancialPublicationUnavailable, match=message):
                reader.result(timeout=10)
    assert validation_calls.count(root / "generations" / f"{selected_generation}.duckdb") == 1
    assert validation_calls.count(pnl_root / "generations" / "pnl-r0.duckdb") == 1


def test_http_middleware_pins_retained_generation_and_keeps_liveness_live(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    auth_dsn = f"sqlite:///{(tmp_path / 'publication-reader-scope.db').as_posix()}"
    settings.environment = "production"
    settings.governance_sql_dsn = auth_dsn
    settings.postgres_dsn = auth_dsn
    monkeypatch.setenv("MOSS_USER_ID", "publication-reader")
    monkeypatch.setenv("MOSS_USER_ROLE", "viewer")
    UserScopeRepository(auth_dsn).grant_scope(
        user_id="publication-reader", role=None, resource="data_health", action="read",
    )
    older_generation, current_generation = _publish_fixture(settings)
    app = FastAPI()
    app.add_middleware(SystemReadPublicationMiddleware, settings_provider=lambda: settings)
    app.include_router(system_read_publication_router)
    app.dependency_overrides[get_settings] = lambda: settings

    @app.get("/business")
    def business() -> dict[str, str]:
        context = current_system_read_context()
        assert context is not None
        with read_only_connection(settings.duckdb_path) as conn:
            value = conn.execute("SELECT value FROM sentinel").fetchone()[0]
        return {"generation": context.generation, "value": value}

    @app.get("/health")
    def health() -> dict[str, str]:
        assert current_system_read_context() is None
        with read_only_connection(settings.duckdb_path) as conn:
            value = conn.execute("SELECT value FROM sentinel").fetchone()[0]
        return {"value": value}

    @app.get("/health/live")
    def health_live() -> dict[str, bool]:
        return {"live": current_system_read_context() is None}

    with TestClient(app) as client:
        handshake = client.get("/api/system-read-publication")
        assert handshake.status_code == 200
        assert handshake.json() == {
            "enabled": True,
            "generation": current_generation,
            "coverage_dates": {"sentinel": ["2026-09-15"]},
        }
        assert handshake.headers[SYSTEM_READ_GENERATION_HEADER] == current_generation

        retained_handshake = client.get(
            "/api/system-read-publication",
            headers={SYSTEM_READ_GENERATION_HEADER: older_generation},
        )
        assert retained_handshake.status_code == 200
        assert retained_handshake.json()["generation"] == older_generation
        assert retained_handshake.headers[SYSTEM_READ_GENERATION_HEADER] == older_generation

        current = client.get("/business")
        assert current.status_code == 200
        assert current.json() == {"generation": current_generation, "value": "R1"}
        assert current.headers[SYSTEM_READ_GENERATION_HEADER] == current_generation

        retained = client.get(
            "/business",
            headers={SYSTEM_READ_GENERATION_HEADER: older_generation},
        )
        assert retained.status_code == 200
        assert retained.json() == {"generation": older_generation, "value": "R0"}
        assert retained.headers[SYSTEM_READ_GENERATION_HEADER] == older_generation

        rejected = client.get(
            "/business",
            headers={SYSTEM_READ_GENERATION_HEADER: "not-retained"},
        )
        assert rejected.status_code == 503

        liveness = client.get("/health")
        assert liveness.status_code == 200
        assert liveness.json() == {"value": "ACTIVE"}
        assert SYSTEM_READ_GENERATION_HEADER not in liveness.headers
        live = client.get("/health/live")
        assert live.status_code == 200
        assert live.json() == {"live": True}
        assert SYSTEM_READ_GENERATION_HEADER not in live.headers


@pytest.mark.parametrize(
    ("environment", "client_host", "user_id", "requested_generation", "method", "path"),
    [
        (environment, client_host, user_id, generation, "GET", "/api/system-read-publication")
        for environment, client_host, user_id in (
            ("production", "127.0.0.1", None),
            ("development", "198.51.100.7", None),
            ("development", "127.0.0.1", "unscoped-reader"),
        )
        for generation in (None, "retained", "not-retained")
    ] + [
        ("production", "127.0.0.1", None, "not-retained", "HEAD", "/api/system-read-publication"),
        ("production", "127.0.0.1", None, "not-retained", "GET", "/api/system-read-publication/"),
    ],
)
def test_publication_handshake_denies_before_loading_or_disclosing_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    requested_generation: str | None,
    environment: str,
    client_host: str,
    user_id: str | None,
    method: str,
    path: str,
) -> None:
    settings = _settings(tmp_path)
    auth_dsn = f"sqlite:///{(tmp_path / 'publication-denied-scope.db').as_posix()}"
    settings.environment = environment
    settings.governance_sql_dsn = auth_dsn
    settings.postgres_dsn = auth_dsn
    UserScopeRepository(auth_dsn)
    monkeypatch.delenv("MOSS_USER_ID", raising=False)
    monkeypatch.delenv("MOSS_USER_ROLE", raising=False)
    monkeypatch.delenv(ROLE_HEADER_TRUST_ENV, raising=False)
    if user_id is not None:
        monkeypatch.setenv("MOSS_USER_ID", user_id)
    older_generation, _current_generation = _publish_fixture(settings)
    if requested_generation == "retained":
        requested_generation = older_generation
    middleware_globals = SystemReadPublicationMiddleware.__call__.__globals__
    resolver_globals = middleware_globals["async_system_read_scope"].__wrapped__.__globals__
    original_resolver = resolver_globals["_resolve_system_read_context"]
    publication_reads: list[str | None] = []

    def counted_resolver(*args: object, **kwargs: object):
        raw_generation = kwargs.get("generation")
        publication_reads.append(None if raw_generation is None else str(raw_generation))
        return original_resolver(*args, **kwargs)

    monkeypatch.setitem(resolver_globals, "_resolve_system_read_context", counted_resolver)
    app = FastAPI()
    app.add_middleware(SystemReadPublicationMiddleware, settings_provider=lambda: settings)
    app.include_router(system_read_publication_router)
    app.dependency_overrides[get_settings] = lambda: settings
    headers = {} if requested_generation is None else {
        SYSTEM_READ_GENERATION_HEADER: requested_generation,
    }

    with TestClient(app, client=(client_host, 12345)) as client:
        response = client.request(method, path, headers=headers, follow_redirects=False)

    assert response.status_code == 403
    if method == "HEAD":
        assert response.content == b""
    else:
        assert response.json() == {"detail": "User is not allowed to read data_health."}
    assert SYSTEM_READ_GENERATION_HEADER not in response.headers
    assert publication_reads == []


def test_publication_handshake_middleware_preserves_local_anonymous_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    auth_dsn = f"sqlite:///{(tmp_path / 'publication-local-scope.db').as_posix()}"
    settings.environment = "development"
    settings.governance_sql_dsn = auth_dsn
    settings.postgres_dsn = auth_dsn
    UserScopeRepository(auth_dsn)
    monkeypatch.delenv("MOSS_USER_ID", raising=False)
    monkeypatch.delenv("MOSS_USER_ROLE", raising=False)
    monkeypatch.delenv(ROLE_HEADER_TRUST_ENV, raising=False)
    older_generation, _current_generation = _publish_fixture(settings)
    app = FastAPI()
    app.add_middleware(SystemReadPublicationMiddleware, settings_provider=lambda: settings)
    app.include_router(system_read_publication_router)
    app.dependency_overrides[get_settings] = lambda: settings

    with TestClient(app, client=("127.0.0.1", 12345)) as client:
        response = client.get(
            "/api/system-read-publication",
            headers={SYSTEM_READ_GENERATION_HEADER: older_generation},
        )

    assert response.status_code == 200
    assert response.json() == {
        "enabled": True,
        "generation": older_generation,
        "coverage_dates": {"sentinel": ["2026-09-15"]},
    }
    assert response.headers[SYSTEM_READ_GENERATION_HEADER] == older_generation


def test_cube_post_reads_pinned_generation_and_other_posts_stay_live(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    older_generation, current_generation = _publish_fixture(settings)
    app = FastAPI()
    app.add_middleware(SystemReadPublicationMiddleware, settings_provider=lambda: settings)

    @app.post("/api/cube/query")
    def cube_read() -> dict[str, str]:
        return {"value": CubeQueryRepository(settings.duckdb_path).fetchall(
            "SELECT value FROM sentinel"
        )[0][0]}

    @app.post("/api/bond-analytics/refresh")
    def writer() -> dict[str, str]:
        assert current_system_read_context() is None
        return {"value": CubeQueryRepository(settings.duckdb_path).fetchall(
            "SELECT value FROM sentinel"
        )[0][0]}

    with TestClient(app) as client:
        for generation, value in [(older_generation, "R0"), (current_generation, "R1")]:
            response = client.post(
                "/api/cube/query", headers={SYSTEM_READ_GENERATION_HEADER: generation}
            )
            assert response.status_code == 200
            assert response.json() == {"value": value}
            assert response.headers[SYSTEM_READ_GENERATION_HEADER] == generation
        current = client.post("/api/cube/query")
        assert current.json() == {"value": "R1"}
        assert current.headers[SYSTEM_READ_GENERATION_HEADER] == current_generation
        assert client.post(
            "/api/cube/query", headers={SYSTEM_READ_GENERATION_HEADER: "not-retained"}
        ).status_code == 503
        live = client.post(
            "/api/bond-analytics/refresh",
            headers={SYSTEM_READ_GENERATION_HEADER: older_generation},
        )
        assert live.json() == {"value": "ACTIVE"}
        assert SYSTEM_READ_GENERATION_HEADER not in live.headers


def test_cube_repository_honors_existing_scope_and_rejects_unselected_online_reads(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    older_generation, _ = _publish_fixture(settings)
    repository = CubeQueryRepository(settings.duckdb_path)
    with system_read_scope(settings, generation=older_generation):
        assert repository.fetchall("SELECT value FROM sentinel") == [("R0",)]
    from backend.app.repositories.duckdb_read_context import duckdb_read_scope

    with duckdb_read_scope(None, required_online=True, active_path=settings.duckdb_path):
        with pytest.raises(DuckDBOnlineReadRequiredError):
            repository.fetchall("SELECT value FROM sentinel")


def test_http_middleware_reads_new_refresh_runs_live_and_keeps_other_gets_pinned(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    older_generation, _ = _publish_fixture(settings)
    repository = GovernanceRepository(base_dir=settings.governance_path)
    refresh_runs = {
        "/ui/balance-analysis/refresh-status": "balance-run-after-publication",
        "/api/bond-analytics/refresh-status": "bond-run-after-publication",
    }
    for run_id in refresh_runs.values():
        repository.append(
            CACHE_BUILD_RUN_STREAM,
            {
                "run_id": run_id,
                "cache_key": "live-refresh-status",
                "status": "completed",
            },
        )

    app = FastAPI()
    app.add_middleware(SystemReadPublicationMiddleware, settings_provider=lambda: settings)

    def live_refresh_status(run_id: str) -> dict[str, object]:
        assert current_system_read_context() is None
        records = [
            row
            for row in repository.read_all(CACHE_BUILD_RUN_STREAM)
            if row.get("run_id") == run_id
        ]
        assert records
        return records[-1]

    app.add_api_route(
        "/ui/balance-analysis/refresh-status",
        live_refresh_status,
        methods=["GET"],
    )
    app.add_api_route(
        "/api/bond-analytics/refresh-status",
        live_refresh_status,
        methods=["GET"],
    )

    @app.get("/business")
    def business() -> dict[str, list[str]]:
        assert current_system_read_context() is not None
        return {
            "run_ids": [
                str(row.get("run_id"))
                for row in repository.read_all(CACHE_BUILD_RUN_STREAM)
            ]
        }

    with TestClient(app) as client:
        for path, run_id in refresh_runs.items():
            response = client.get(
                path,
                params={"run_id": run_id},
                headers={SYSTEM_READ_GENERATION_HEADER: older_generation},
            )
            assert response.status_code == 200
            assert response.json()["run_id"] == run_id
            assert response.json()["status"] == "completed"
            assert SYSTEM_READ_GENERATION_HEADER not in response.headers

        retained = client.get(
            "/business",
            headers={SYSTEM_READ_GENERATION_HEADER: older_generation},
        )
        assert retained.status_code == 200
        assert retained.json() == {"run_ids": ["run-1"]}
        assert retained.headers[SYSTEM_READ_GENERATION_HEADER] == older_generation


def test_http_middleware_fails_closed_when_no_system_publication_exists(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    app = FastAPI()
    app.add_middleware(SystemReadPublicationMiddleware, settings_provider=lambda: settings)

    @app.get("/business")
    def business() -> dict[str, str]:
        return {"value": "must-not-run"}

    @app.get("/health/live")
    def health_live() -> dict[str, bool]:
        return {"live": current_system_read_context() is None}

    with TestClient(app) as client:
        response = client.get("/business")
        live = client.get("/health/live")

    assert response.status_code == 503
    assert response.json() == {"detail": "A valid system read publication is unavailable."}
    assert live.status_code == 200
    assert live.json() == {"live": True}
    assert SYSTEM_READ_GENERATION_HEADER not in live.headers


def test_http_middleware_keeps_pin_through_stream_body_and_control_post_is_live(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    _, current_generation = _publish_fixture(settings)
    app = FastAPI()
    app.add_middleware(SystemReadPublicationMiddleware, settings_provider=lambda: settings)

    @app.get("/stream")
    def stream() -> StreamingResponse:
        def body():
            context = current_system_read_context()
            assert context is not None
            yield context.generation
            with read_only_connection(settings.duckdb_path) as conn:
                yield ":" + conn.execute("SELECT value FROM sentinel").fetchone()[0]

        return StreamingResponse(body(), media_type="text/plain")

    @app.post("/control")
    def control() -> dict[str, str]:
        assert current_system_read_context() is None
        with read_only_connection(settings.duckdb_path) as conn:
            value = conn.execute("SELECT value FROM sentinel").fetchone()[0]
        return {"value": value}

    @app.get("/ui/balance-analysis/current-user")
    def current_user() -> dict[str, bool]:
        return {"live": current_system_read_context() is None}

    with TestClient(app) as client:
        streamed = client.get("/stream")
        assert streamed.status_code == 200
        assert streamed.text == f"{current_generation}:R1"
        assert streamed.headers[SYSTEM_READ_GENERATION_HEADER] == current_generation

        system_root = system_read_publication_root(settings)
        (system_root / "current.json").unlink()
        control = client.post("/control")
        assert control.status_code == 200
        assert control.json() == {"value": "ACTIVE"}
        current_user_response = client.get("/ui/balance-analysis/current-user")
        assert current_user_response.status_code == 200
        assert current_user_response.json() == {"live": True}
        assert SYSTEM_READ_GENERATION_HEADER not in current_user_response.headers
