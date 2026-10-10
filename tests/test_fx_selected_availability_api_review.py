"""Independent synthetic selected-path availability regression review.

Exercise the registered FX route, actual publication middleware, scope repository,
read context and DuckDB queries. Settings and inbound identity are fixture inputs;
SQL, selectors, read-path resolution and service functions are never replaced.
Publication/context cache reuse is covered, not an FX response cache (none exists).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest
from fastapi.testclient import TestClient

from backend.app.repositories.duckdb_read_context import (
    DuckDBOnlineReadRequiredError,
    DuckDBReadSelection,
    DuckDBReadSelectionError,
    duckdb_read_scope,
)
from backend.app.repositories.financial_result_publication_repo import (
    canonical_json_bytes,
    generation_invalidation_path,
    sha256_bytes,
    sha256_file,
)
from backend.app.repositories.system_read_publication_repo import (
    SYSTEM_READ_GENERATION_HEADER,
    current_system_read_context,
    system_read_publication_root,
    system_read_scope,
)
from backend.app.security.auth_context import AuthContext, get_auth_context
from backend.app.services.macro_vendor_service import (
    FxAnalyticalReadError,
    fx_analytical_envelope,
    load_fx_analytical_payload,
)
from tests.test_fx_analytical_fallback_api import (
    DAY,
    ENDPOINT,
    USD_NAME,
    _app,
    _fallback_series,
    _observation,
    _only_point,
    _seed,
    _warnings,
)
from tests.test_system_online_read_boundary import _bundle, _seal_generation, _settings, _write_pointer

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_market_data]


def _series(number, style):
    if style == "fallback":
        return _fallback_series(f"review_G{number}", gap=number, value=6.0 + number)
    return [("synthetic-usd", USD_NAME, [
        _observation(DAY - timedelta(days=number), 6.0 + number, f"review_G{number}_selected"),
        _observation(DAY - timedelta(days=number + 1), 5.5 + number, f"review_G{number}_older"),
    ])]


def _published(root, number, settings, pnl_digest, *, style="fallback", storage="populated"):
    generation = f"system-read-2026-09-15-{str(number) * 20}"
    _seal_generation(root, generation, f"Synthetic independent FX G{number}",
                     system_read_bundle=_bundle(settings, "pnl-review", pnl_digest))
    database = root / "generations" / f"{generation}.duckdb"
    if storage in {"populated", "empty"}:
        _seed(database, _series(number, style) if storage == "populated" else [])
    elif storage == "broken_schema":
        with duckdb.connect(str(database)) as conn:
            conn.execute("CREATE TABLE fact_choice_macro_daily(wrong_column INTEGER)")
            conn.execute("CREATE TABLE phase1_macro_vendor_catalog(wrong_column INTEGER)")
    else:
        assert storage == "missing_schema"
    manifest_path = database.with_suffix(".manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["database"].update(size_bytes=database.stat().st_size, sha256=sha256_file(database))
    encoded = canonical_json_bytes(manifest)
    manifest_path.write_bytes(encoded)
    return generation, sha256_bytes(encoded)


def _published_chain(tmp_path, monkeypatch, *, style="fallback", storage="populated"):
    settings = _settings(tmp_path)
    active = Path(settings.duckdb_path)
    _seed(active, _fallback_series("review_ACTIVE_G9", value=9.9))
    pnl_root = Path(settings.financial_publication_root)
    pnl_digest = _seal_generation(pnl_root, "pnl-review", "Synthetic independent PnL")
    _write_pointer(pnl_root, "pnl-review", [("pnl-review", pnl_digest)])
    root = system_read_publication_root(settings)
    g1 = _published(root, 1, settings, pnl_digest, style=style, storage=storage)
    g2 = _published(root, 2, settings, pnl_digest, style=style, storage=storage)
    _write_pointer(root, g2[0], [g2, g1])
    return SimpleNamespace(settings=settings, active=active, root=root, g1=g1, g2=g2,
                           app=_app(settings, monkeypatch, publication=True))


def _request(client, generation):
    return client.get(ENDPOINT, headers={SYSTEM_READ_GENERATION_HEADER: generation})


def _assert_selected(response, generation, number, style="fallback"):
    assert response.status_code == 200, response.text
    assert response.headers[SYSTEM_READ_GENERATION_HEADER] == generation
    body = response.json()
    meta = body["result_meta"]
    assert meta["basis"] == "analytical"
    assert meta["formal_use_allowed"] is False
    assert meta["cache_version"] == "cv_fx_analytical_v1"
    assert meta["rule_version"] == "rv_fx_analytical_v1"
    point = _only_point(body)
    assert point["value_numeric"] == 6.0 + number
    assert point["trade_date"] == str(DAY - timedelta(days=number))
    assert point["source_version"] == meta["source_version"] == f"sv_synthetic_review_G{number}_selected"
    assert point["vendor_version"] == meta["vendor_version"] == f"vv_synthetic_review_G{number}_selected"
    assert point["recent_points"] == [
        {"trade_date": day, "value_numeric": value, "source_version": source,
         "vendor_version": vendor, "quality_flag": quality}
        for day, value, source, vendor, quality in _series(number, style)[0][2]
    ]
    assert point["latest_change"] == (None if style == "fallback" else 0.5)
    assert point["quality_flag"] == meta["quality_flag"] == ("warning" if style == "fallback" else "ok")
    assert meta["fallback_mode"] == "none"
    if style == "fallback":
        assert f"observed_date={DAY - timedelta(days=number)}" in " ".join(_warnings(body))
    else:
        assert _warnings(body) == []
    return body


@pytest.mark.parametrize("active_present", [True, False], ids=["active_present", "active_absent"])
@pytest.mark.parametrize("style", ["direct", "fallback"])
def test_registered_route_g1_g2_g1_preserves_exact_selected_payload(tmp_path, monkeypatch, active_present, style):
    chain = _published_chain(tmp_path, monkeypatch, style=style)
    if not active_present:
        chain.active.unlink()
    with TestClient(chain.app) as client:
        bodies = [_assert_selected(_request(client, generation), generation, number, style)
                  for number, generation in ((1, chain.g1[0]), (2, chain.g2[0]), (1, chain.g1[0]))]
    assert bodies[0]["result"] == bodies[2]["result"]
    # ResultMeta.generated_at is the per-request construction time, not lineage.
    assert {key: value for key, value in bodies[0]["result_meta"].items() if key != "generated_at"} == {
        key: value for key, value in bodies[2]["result_meta"].items() if key != "generated_at"}
    for body in bodies:
        assert datetime.fromisoformat(body["result_meta"]["generated_at"]).tzinfo is not None
    assert chain.active.exists() is active_present


def test_actual_publication_context_cache_survives_active_disappearance(tmp_path, monkeypatch):
    chain = _published_chain(tmp_path, monkeypatch)
    with TestClient(chain.app) as client:
        for number, generation in ((1, chain.g1[0]), (2, chain.g2[0])):
            _assert_selected(_request(client, generation), generation, number)
        contexts = []
        for generation in (chain.g1[0], chain.g2[0], chain.g1[0]):
            with system_read_scope(chain.settings, generation=generation):
                contexts.append(current_system_read_context())
        assert contexts[0] is contexts[2]
        assert contexts[0] is not contexts[1]
        chain.active.unlink()
        for number, generation in ((1, chain.g1[0]), (2, chain.g2[0]), (1, chain.g1[0])):
            _assert_selected(_request(client, generation), generation, number)
        with system_read_scope(chain.settings, generation=chain.g1[0]):
            assert current_system_read_context() is contexts[0]
    assert not chain.active.exists()


def test_current_pointer_without_header_uses_selected_store_with_absent_active(tmp_path, monkeypatch):
    chain = _published_chain(tmp_path, monkeypatch)
    chain.active.unlink()
    with TestClient(chain.app) as client:
        _assert_selected(client.get(ENDPOINT), chain.g2[0], 2)
    assert not chain.active.exists()


@pytest.mark.parametrize("active_present", [True, False], ids=["active_present", "active_absent"])
@pytest.mark.parametrize("reader", [fx_analytical_envelope, load_fx_analytical_payload], ids=["envelope", "payload"])
def test_required_selection_is_never_silently_empty(tmp_path, active_present, reader):
    active = tmp_path / "active.duckdb"
    if active_present:
        _seed(active, _series(9, "direct"))
    with duckdb_read_scope(None, required_online=True, active_path=active):
        with pytest.raises(DuckDBOnlineReadRequiredError, match="immutable DuckDB read selection is required"):
            reader(str(active))
    assert active.exists() is active_present


@pytest.mark.parametrize("active_present", [True, False], ids=["active_present", "active_absent"])
@pytest.mark.parametrize("reader", [fx_analytical_envelope, load_fx_analytical_payload], ids=["envelope", "payload"])
def test_selection_deleted_after_binding_remains_an_explicit_error(tmp_path, active_present, reader):
    active, selected = tmp_path / "active.duckdb", tmp_path / "selected.duckdb"
    _seed(selected, _series(1, "direct"))
    if active_present:
        _seed(active, _series(9, "direct"))
    selection = DuckDBReadSelection(active, selected, "synthetic-review-deleted")
    with duckdb_read_scope(selection, required_online=True):
        selected.unlink()
        with pytest.raises(DuckDBReadSelectionError, match="synthetic-review-deleted.*unavailable"):
            reader(str(active))
    assert active.exists() is active_present
    assert not selected.exists()


@pytest.mark.parametrize("active_present", [True, False], ids=["active_present", "active_absent"])
@pytest.mark.parametrize("failure", ["empty_header", "malformed", "unknown", "deleted_database",
                                    "deleted_manifest", "invalidated", "retention_removed"])
def test_warmed_publication_rejects_invalid_or_unavailable_selection(tmp_path, monkeypatch, active_present, failure):
    chain = _published_chain(tmp_path, monkeypatch)
    with TestClient(chain.app) as client:
        _assert_selected(_request(client, chain.g1[0]), chain.g1[0], 1)
        if not active_present:
            chain.active.unlink()
        requested = chain.g1[0]
        if failure == "empty_header":
            requested = ""
        elif failure == "malformed":
            requested = "../invalid-generation"
        elif failure == "unknown":
            requested = "system-read-2026-10-06-" + "f" * 20
        elif failure == "deleted_database":
            (chain.root / "generations" / f"{requested}.duckdb").unlink()
        elif failure == "deleted_manifest":
            (chain.root / "generations" / f"{requested}.manifest.json").unlink()
        elif failure == "invalidated":
            invalidation = generation_invalidation_path(chain.root, requested)
            invalidation.parent.mkdir(parents=True, exist_ok=True)
            invalidation.write_text(json.dumps({"reason": "Synthetic independent invalidation"}), encoding="utf-8")
        else:
            _write_pointer(chain.root, chain.g2[0], [chain.g2])
        response = _request(client, requested)
        assert response.status_code == 503, response.text
        assert response.json() == {"detail": "A valid system read publication is unavailable."}
        assert SYSTEM_READ_GENERATION_HEADER not in response.headers
    assert chain.active.exists() is active_present


@pytest.mark.parametrize("active_present", [True, False], ids=["active_present", "active_absent"])
@pytest.mark.parametrize("storage", ["empty", "missing_schema", "broken_schema"])
def test_selected_empty_and_query_warning_contracts_do_not_read_active(tmp_path, monkeypatch, active_present, storage):
    chain = _published_chain(tmp_path, monkeypatch, storage=storage)
    if not active_present:
        chain.active.unlink()
    with TestClient(chain.app) as client:
        response = _request(client, chain.g1[0])
    assert response.headers[SYSTEM_READ_GENERATION_HEADER] == chain.g1[0]
    body = response.json()
    if storage == "broken_schema":
        assert response.status_code == 503, response.text
        assert body["detail"]["code"] == "fx_analytical_read_failed"
        assert "DuckDB query failed surface=fx_analytical" in body["detail"]["message"]
    else:
        assert response.status_code == 200, response.text
        assert body["result"]["groups"] == []
        meta = body["result_meta"]
        assert meta["basis"] == "analytical"
        assert meta["formal_use_allowed"] is False
        assert meta["quality_flag"] == "warning"
        assert meta["vendor_version"] == "vv_none"
        assert meta["source_version"] == "sv_fx_analytical_empty"
        assert _warnings(body) == []
    assert chain.active.exists() is active_present


@pytest.mark.parametrize("active_present", [True, False], ids=["active_present", "active_absent"])
def test_selected_corrupt_file_retains_service_query_failure_warning(tmp_path, active_present):
    active, selected = tmp_path / "active.duckdb", tmp_path / "selected.duckdb"
    if active_present:
        _seed(active, _series(9, "direct"))
    selected.write_bytes(b"Synthetic independent invalid DuckDB")
    with duckdb_read_scope(DuckDBReadSelection(active, selected, "synthetic-corrupt"), required_online=True):
        with pytest.raises(FxAnalyticalReadError, match="DuckDB query failed surface=fx_analytical"):
            fx_analytical_envelope(str(active))
    assert active.exists() is active_present


def test_unbound_absent_store_remains_empty_without_creating_a_file(tmp_path, monkeypatch):
    active = tmp_path / "unbound-missing.duckdb"
    settings = SimpleNamespace(duckdb_path=str(active))
    with TestClient(_app(settings, monkeypatch)) as client:
        response = client.get(ENDPOINT)
    assert response.status_code == 200, response.text
    assert SYSTEM_READ_GENERATION_HEADER not in response.headers
    body = response.json()
    assert body["result"]["groups"] == []
    assert body["result_meta"]["source_version"] == "sv_fx_analytical_empty"
    assert _warnings(body) == []
    assert not active.exists()


@pytest.mark.parametrize("active_present", [True, False], ids=["active_present", "active_absent"])
def test_no_grant_cannot_read_valid_selected_snapshot(tmp_path, monkeypatch, active_present):
    chain = _published_chain(tmp_path, monkeypatch)
    if not active_present:
        chain.active.unlink()
    chain.app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        user_id="synthetic-independent-no-grant", role="viewer", identity_source="synthetic-test")
    with TestClient(chain.app) as client:
        response = _request(client, chain.g1[0])
    assert response.status_code == 403, response.text
    assert "not allowed" in response.json()["detail"]
    assert response.headers[SYSTEM_READ_GENERATION_HEADER] == chain.g1[0]
    assert chain.active.exists() is active_present


def test_selection_for_another_active_identity_does_not_supply_this_missing_store(tmp_path):
    missing, other, selected = (tmp_path / name for name in ("missing.duckdb", "other.duckdb", "selected.duckdb"))
    _seed(selected, _series(1, "direct"))
    with duckdb_read_scope(DuckDBReadSelection(other, selected, "synthetic-other"), required_online=True):
        body = fx_analytical_envelope(str(missing))
    assert body["result"]["groups"] == []
    assert body["result_meta"]["source_version"] == "sv_fx_analytical_empty"
    assert _warnings(body) == []
    assert not missing.exists()
