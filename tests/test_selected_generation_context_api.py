"""MS-017 independent synthetic consumer and registered-route regressions.

Real DuckDB reads, real services, original registered routes/response models,
publication middleware, and SQLite scope grants are exercised. Only paths,
bindings, and inbound identity are test-supplied. No provider calls or startup
jobs run; this bounded harness is not production authentication or UI QA.
"""
from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.routes import executive as home_routes
from backend.app.main import SystemReadPublicationMiddleware
from backend.app.repositories.duckdb_read_context import (
    DuckDBReadSelection, DuckDBReadSelectionError, active_read_scope,
    current_duckdb_read_selection, duckdb_read_scope,
)
from backend.app.repositories.financial_result_publication_repo import (
    canonical_json_bytes, sha256_bytes, sha256_file,
)
from backend.app.repositories.home_macro_release_context_repo import HomeMacroReleaseContextRepository
from backend.app.repositories.system_read_publication_repo import (
    SYSTEM_READ_GENERATION_HEADER, system_read_publication_root,
)
from backend.app.repositories.user_scope_repo import UserScopeRepository
from backend.app.schemas.home_macro_release_context import HomeMacroReleaseContextEnvelope
from backend.app.security.auth_context import AuthContext, get_auth_context
from backend.app.services.home_macro_release_context_service import (
    HomeMacroReleaseContextService, clear_home_macro_release_context_runtime_cache,
)
from tests.test_system_online_read_boundary import _bundle, _seal_generation, _settings, _write_pointer


DAY = date(2026, 9, 30)
HOME_URL = "/ui/home/macro-release-context?start_date=2026-09-30&end_date=2026-10-06"


def _seed(path: Path, number: int) -> None:
    with duckdb.connect(str(path)) as conn:
        conn.execute("""CREATE TABLE fact_choice_macro_daily(
            series_id VARCHAR, series_name VARCHAR, trade_date VARCHAR,
            value_numeric DOUBLE, frequency VARCHAR, unit VARCHAR,
            source_version VARCHAR, vendor_version VARCHAR, rule_version VARCHAR,
            quality_flag VARCHAR, run_id VARCHAR)""")
        for series, current, previous in (("synthetic.context", number * 10.0, number * 10.0 - 1),
                                           ("M0017126", 50.2, 49.9)):
            for day, value in (("2026-09-30", current), ("2026-08-31", previous)):
                # Equal pulse dates/values deliberately leave only publisher identity different.
                conn.execute("INSERT INTO fact_choice_macro_daily VALUES (?, ?, ?, ?, 'monthly', 'index', ?, ?, 'rv_synthetic', 'ok', ?)",
                             [series, series, day, value, f"sv_macro_G{number}",
                              "vv_nbs_pmi_release_G1" if number == 1 else "vv_tushare_G2",
                              f"synthetic-G{number}-20260930T000000Z"])


def _bindings(path: Path) -> Path:
    path.write_text(json.dumps({"rule_version": "rv_synthetic_context", "groups": [{
        "indicator_key": "synthetic_context", "title": "Synthetic macro context", "region": "CN",
        "category": "activity", "importance": "high", "priority": 1, "availability": "automatic",
        "publisher_name": "Synthetic publisher", "vendor_name": None, "metrics": [{
            "metric_key": "synthetic_index", "label": "Synthetic index", "cadence": "monthly",
            "display_unit": "index", "change_unit": "index_point", "precision": 1,
            "table": "fact_choice_macro_daily", "series_id": "synthetic.context",
        }],
    }]}), encoding="utf-8")
    return path


@pytest.fixture
def chain(tmp_path):
    active, snapshot = tmp_path / "active.duckdb", tmp_path / "G1.duckdb"
    _seed(active, 2)
    _seed(snapshot, 1)
    clear_home_macro_release_context_runtime_cache()
    yield SimpleNamespace(active=active, snapshot=snapshot, bindings=_bindings(tmp_path / "bindings.json"),
                          selection=DuckDBReadSelection(active, snapshot, "G1"))
    clear_home_macro_release_context_runtime_cache()


def _home(chain):
    return HomeMacroReleaseContextService(
        repository=HomeMacroReleaseContextRepository(chain.active), bindings_path=chain.bindings,
    ).build_envelope(window_start_date=DAY, window_end_date=date(2026, 10, 6))


def _assert_home(envelope, number):
    payload = envelope.model_dump(mode="json") if isinstance(envelope, HomeMacroReleaseContextEnvelope) else envelope
    meta, result = payload["result_meta"], payload["result"]
    assert meta["basis"] == "analytical"
    assert meta["formal_use_allowed"] is False
    assert meta["as_of_date"] == DAY.isoformat()
    assert meta["date_basis"] == "macro_observation_period"
    item = result["history_items"][0]
    assert item["observation_date"] == DAY.isoformat()
    assert item["previous_observation_date"] == "2026-08-31"
    metric = item["metrics"][0]
    assert (metric["actual_value"], metric["previous_value"], metric["change_value"]) == (number * 10.0, number * 10.0 - 1, 1.0)
    assert (metric["display_unit"], metric["change_unit"], metric["precision"]) == ("index", "index_point", 1)
    assert item["source_status"] == "ready"
    vendor = "NBS official artifact" if number == 1 else "Tushare"
    assert f"Vendor evidence: {vendor}." in item["notes"]
    tokens = sorted(f"fact_choice_macro_daily|synthetic.context|{day}|sv_macro_G{number}"
                    for day in ("2026-08-31", "2026-09-30"))
    digest = hashlib.sha256(json.dumps(tokens, separators=(",", ":")).encode()).hexdigest()[:16]
    assert meta["source_version"] == f"sv_home_macro_release_context_{digest}"


@pytest.mark.excluded_surface_regression
@pytest.mark.surface_executive
class TestHomeMacroSelectedGeneration:
    def test_ordinary_active_control(self, chain):
        _assert_home(_home(chain), 2)

    def test_service_g1_g2_g1_with_hot_cache(self, chain, monkeypatch):
        original = HomeMacroReleaseContextService._build_envelope_uncached
        builds = []

        def observed(service, **kwargs):
            selection = current_duckdb_read_selection()
            builds.append(selection.generation if selection else "active")
            return original(service, **kwargs)

        monkeypatch.setattr(HomeMacroReleaseContextService, "_build_envelope_uncached", observed)
        with duckdb_read_scope(chain.selection, required_online=True):
            _assert_home(_home(chain), 1)
            with active_read_scope():
                _assert_home(_home(chain), 2)
            _assert_home(_home(chain), 1)
            _assert_home(_home(chain), 1)
        assert builds == ["G1", "active"]
        _assert_home(_home(chain), 2)
        assert builds == ["G1", "active"]

    def test_service_valid_selected_store_survives_absent_active(self, chain):
        chain.active.unlink()
        with duckdb_read_scope(chain.selection, required_online=True):
            _assert_home(_home(chain), 1)
        assert not chain.active.exists()

    @pytest.mark.parametrize("missing", ["required_selection", "deleted_snapshot"])
    def test_service_missing_pin_fails_closed_even_after_cache_warmup(self, chain, missing):
        _home(chain)
        selection = chain.selection if missing == "deleted_snapshot" else None
        with duckdb_read_scope(selection, required_online=True, active_path=chain.active):
            if missing == "deleted_snapshot":
                _home(chain)
                chain.snapshot.unlink()
            with pytest.raises(DuckDBReadSelectionError):
                _home(chain)

    def test_real_route_g1_g2_g1_values_lineage_and_hot_cache(self, route_chain, monkeypatch):
        original = HomeMacroReleaseContextService._build_envelope_uncached
        builds = []

        def observed(service, **kwargs):
            builds.append(current_duckdb_read_selection().generation)
            return original(service, **kwargs)

        monkeypatch.setattr(HomeMacroReleaseContextService, "_build_envelope_uncached", observed)
        with TestClient(route_chain.app) as client:
            for number in (1, 2, 1):
                generation = route_chain.generations[number]
                response = client.get(HOME_URL, headers={SYSTEM_READ_GENERATION_HEADER: generation})
                assert response.status_code == 200, response.text
                assert response.headers[SYSTEM_READ_GENERATION_HEADER] == generation
                _assert_home(response.json(), number)
        assert builds == [route_chain.generations[1], route_chain.generations[2]]
        route = next(route for route in route_chain.app.routes if getattr(route, "path", None) == HOME_URL.split("?")[0])
        assert route.response_model is HomeMacroReleaseContextEnvelope

    def test_real_route_absent_active_and_deleted_selected_store(self, route_chain):
        route_chain.active.unlink()
        with TestClient(route_chain.app) as client:
            headers = {SYSTEM_READ_GENERATION_HEADER: route_chain.generations[1]}
            response = client.get(HOME_URL, headers=headers)
            assert response.status_code == 200, response.text
            _assert_home(response.json(), 1)
            route_chain.snapshots[1].unlink()
            rejected = client.get(HOME_URL, headers=headers)
            assert rejected.status_code == 503
            assert SYSTEM_READ_GENERATION_HEADER not in rejected.headers
        assert not route_chain.active.exists()

    def test_real_route_scope_and_query_guards(self, route_chain):
        with TestClient(route_chain.app) as client:
            headers = {SYSTEM_READ_GENERATION_HEADER: route_chain.generations[1]}
            route_chain.app.dependency_overrides[get_auth_context] = lambda: AuthContext(user_id="synthetic-no-grant", role="viewer", identity_source="synthetic-test")
            rejected = client.get(HOME_URL, headers=headers)
            assert rejected.status_code == 403
            assert "not allowed" in rejected.json()["detail"]
            route_chain.app.dependency_overrides[get_auth_context] = _reader
            assert client.get(HOME_URL + "&history_limit=0", headers=headers).status_code == 422
            assert client.get("/ui/home/macro-release-context?start_date=2026-10-06&end_date=2026-09-30", headers=headers).status_code == 422
            assert client.get("/ui/home/alerts", headers=headers).status_code == 503


def _reader():
    return AuthContext(user_id="synthetic-reader", role="viewer", identity_source="synthetic-test")


def _published(root, number, settings, pnl_digest):
    generation = f"system-read-2026-09-15-{str(number) * 20}"
    _seal_generation(root, generation, f"synthetic-G{number}", system_read_bundle=_bundle(settings, "pnl-synthetic", pnl_digest))
    path = root / "generations" / f"{generation}.duckdb"
    _seed(path, number)
    manifest_path = root / "generations" / f"{generation}.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["database"].update(size_bytes=path.stat().st_size, sha256=sha256_file(path))
    content = canonical_json_bytes(manifest)
    manifest_path.write_bytes(content)
    return generation, sha256_bytes(content), path


@pytest.fixture
def route_chain(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    active = Path(settings.duckdb_path)
    _seed(active, 2)
    settings.environment = "test"
    settings.governance_sql_dsn = f"sqlite:///{tmp_path / 'synthetic-scopes.sqlite'}"
    settings.postgres_dsn = settings.governance_sql_dsn
    scopes = UserScopeRepository(settings.governance_sql_dsn)
    try:
        for resource in ("executive",):
            scopes.grant_scope(user_id="synthetic-reader", role="viewer", resource=resource, action="read",
                               operator="synthetic-test", reason="Isolated MS-017 contract regression")
    finally:
        scopes.engine.dispose()
    pnl_root = Path(settings.financial_publication_root)
    pnl_digest = _seal_generation(pnl_root, "pnl-synthetic", "SYNTHETIC")
    _write_pointer(pnl_root, "pnl-synthetic", [("pnl-synthetic", pnl_digest)])
    root = system_read_publication_root(settings)
    g1, g2 = (_published(root, number, settings, pnl_digest) for number in (1, 2))
    _write_pointer(root, g2[0], [g2[:2], g1[:2]])
    monkeypatch.setattr(home_routes, "get_settings", lambda: settings)
    monkeypatch.setattr(home_routes, "_HOME_MACRO_RELEASE_BINDINGS", _bindings(tmp_path / "bindings.json"))
    app = FastAPI()
    app.add_middleware(SystemReadPublicationMiddleware, settings_provider=lambda: settings)
    app.include_router(home_routes.router)
    app.dependency_overrides[get_auth_context] = _reader
    clear_home_macro_release_context_runtime_cache()
    yield SimpleNamespace(app=app, active=active, generations={1: g1[0], 2: g2[0]}, snapshots={1: g1[2], 2: g2[2]})
    clear_home_macro_release_context_runtime_cache()
