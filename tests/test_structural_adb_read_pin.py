"""ADB read guards must check the selected database, including valid empty stores.

All databases, values and identities are synthetic temporary fixtures. Real
repository queries, calculations and envelopes run without a database mock.
These tests preserve existing observed-day and CNX accounting contracts; they
do not qualify those business definitions or any production financial result.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.routes import adb_analysis as routes
from backend.app.main import SystemReadPublicationMiddleware
from backend.app.repositories import adb_analysis_repo as repo_module
from backend.app.repositories.adb_analysis_repo import AdbAnalysisRepository
from backend.app.repositories.duckdb_read_context import (
    DuckDBOnlineReadRequiredError,
    DuckDBReadSelection,
    DuckDBReadSelectionError,
    active_read_scope,
    duckdb_read_scope,
)
from backend.app.services import adb_analysis_service as adb
from backend.app.repositories.financial_result_publication_repo import canonical_json_bytes, sha256_bytes, sha256_file
from backend.app.repositories.system_read_publication_repo import SYSTEM_READ_GENERATION_HEADER, system_read_publication_root
from backend.app.repositories.user_scope_repo import UserScopeRepository
from backend.app.security.auth_context import AuthContext, get_auth_context
from tests.test_system_online_read_boundary import _bundle, _seal_generation, _settings, _write_pointer

START, END = date(2026, 9, 28), date(2026, 9, 30)
READERS = ("accounting", "accounting_trend", "raw", "calculate", "coverage", "candidates",
           "repo_accounting", "repo_accounting_trend")


def _insert(conn, table, row):
    conn.execute(f"INSERT INTO {table} ({', '.join(row)}) VALUES ({', '.join('?' for _ in row)})",
                 list(row.values()))


def _seed(path, number, *, empty=False, schema=True):
    with duckdb.connect(str(path)) as conn:
        if not schema:
            return
        sql = Path(__file__).resolve().parents[1] / "backend/app/schema_registry/duckdb/05_balance_analysis.sql"
        for statement in sql.read_text(encoding='utf-8').split("-- MOSS:STMT"):
            if statement.strip():
                conn.execute(statement)
        conn.execute("""CREATE TABLE zqtz_bond_daily_snapshot (
            report_date VARCHAR, market_value_native DECIMAL(24, 8), ytm_value DOUBLE,
            coupon_rate DOUBLE, asset_class VARCHAR, bond_type VARCHAR, is_issuance_like BOOLEAN,
            currency_code VARCHAR, source_version VARCHAR, rule_version VARCHAR)""")
        conn.execute("""CREATE TABLE product_category_pnl_canonical_fact (
            report_date VARCHAR, account_code VARCHAR, currency VARCHAR,
            daily_avg_balance DECIMAL(24, 8), source_version VARCHAR, rule_version VARCHAR)""")
        if empty:
            return
        _insert(conn, "fact_formal_zqtz_balance_daily", {
            "report_date": f"2026-09-{27 + number}", "instrument_code": "SYNTHETIC",
            "position_scope": "asset", "currency_basis": "CNY", "currency_code": "CNY",
            "market_value_amount": number * 1000, "ytm_value": 3, "coupon_rate": 3,
            "asset_class": "treasury", "bond_type": "treasury", "is_issuance_like": False,
            "source_version": f"sv_formal_G{number}", "rule_version": "rv_synthetic_formal",
        })
        _insert(conn, "zqtz_bond_daily_snapshot", {
            "report_date": END.isoformat(), "market_value_native": number * 1000,
            "ytm_value": 3, "coupon_rate": 3, "asset_class": "treasury", "bond_type": "treasury",
            "is_issuance_like": False, "currency_code": "CNY",
            "source_version": f"sv_snapshot_G{number}", "rule_version": "rv_synthetic_snapshot",
        })
        for account, currency, amount in (("142001", "CNX", number * 3000),
                                           ("142001", "CNY", 900000), ("14402001", "CNX", 400000)):
            _insert(conn, "product_category_pnl_canonical_fact", {
                "report_date": END.isoformat(), "account_code": account, "currency": currency,
                "daily_avg_balance": amount, "source_version": f"sv_accounting_G{number}",
                "rule_version": "rv_synthetic_accounting",
            })


@pytest.fixture
def chain(tmp_path, monkeypatch):
    active, snapshot = tmp_path / "active.duckdb", tmp_path / "G1.duckdb"
    _seed(active, 2)
    _seed(snapshot, 1)
    settings = SimpleNamespace(duckdb_path=active)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(active))
    monkeypatch.setattr(adb, "get_settings", lambda: settings)
    adb.clear_adb_comparison_cache()
    adb.clear_adb_insights_cache()
    yield SimpleNamespace(active=active, snapshot=snapshot, settings=settings,
                          selection=DuckDBReadSelection(active, snapshot, "G1"))
    adb.clear_adb_comparison_cache()
    adb.clear_adb_insights_cache()


def _read(reader, path):
    path = str(path)
    if reader == "accounting":
        return adb._load_accounting_basis_daily_average(path, END)
    if reader == "accounting_trend":
        return adb._load_accounting_basis_daily_average_trend(path, START, END)
    if reader == "raw":
        return adb._load_adb_raw_data(path, START, END)
    if reader == "calculate":
        return adb.calculate_adb(path, START, END)
    if reader == "coverage":
        return adb.adb_coverage_diagnostics(START.isoformat(), END.isoformat())
    if reader == "candidates":
        return adb.adb_backfill_candidate_dates(START.isoformat(), END.isoformat())
    repo = AdbAnalysisRepository(path=path)
    if reader == "repo_accounting":
        return repo.fetch_accounting_basis_rows(END.isoformat(), "CNX")
    return repo.fetch_accounting_basis_trend_rows(START.isoformat(), END.isoformat(), "CNX")


def _assert_result(reader, result, number):
    formal_day = f"2026-09-{27 + number}"
    if reader in {"accounting", "accounting_trend"}:
        payload, sources, rules, evidence = result
        if reader == "accounting_trend":
            assert len(payload) == 1
            payload = payload[0]
        assert payload["daily_avg_total"] == number * 3000
        assert payload["currency_basis"] == "CNX"
        assert payload["rows"][0]["daily_avg_balance"] == number * 3000
        assert payload["rows"][0]["daily_avg_pct"] == 100
        assert sources == [f"sv_accounting_G{number}"]
        assert rules == ["rv_synthetic_accounting"] and evidence == 1
    elif reader == "raw":
        bonds, interbank, sources, rules, basis, tables, fx = result
        assert list(bonds["market_value"]) == [number * 1000, number * 1000]
        assert {d.date().isoformat() for d in bonds["report_date"]} == {formal_day, END.isoformat()}
        assert interbank.empty
        assert set(sources) == {f"sv_formal_G{number}", f"sv_snapshot_G{number}"}
        assert set(rules) == {"rv_synthetic_formal", "rv_synthetic_snapshot"}
        assert basis == "formal+snapshot_calendar"
        assert "zqtz_bond_daily_snapshot" in tables
        assert fx["converted_rows"] == fx["dropped_rows"] == 0
    elif reader == "calculate":
        payload, sources, rules, tables = result
        # Existing ADB contract: two observed days in a three-calendar-day window.
        assert payload["summary"]["total_avg_assets"] == number * 1000
        assert payload["summary"]["end_spot_assets"] == number * 1000
        assert payload["summary"]["total_avg_liabilities"] == 0
        assert len(payload["trend"]) == 3
        assert set(sources) == {f"sv_formal_G{number}", f"sv_snapshot_G{number}"}
        assert set(rules) == {"rv_synthetic_formal", "rv_synthetic_snapshot"}
        assert "zqtz_bond_daily_snapshot" in tables
    elif reader == "coverage":
        assert result["formal_tables"]["formal_zqtz"]["dates"] == [formal_day]
        assert result["snapshot_tables"]["zqtz_snapshot"]["dates"] == [END.isoformat()]
        assert result["missing_dates"] == [END.isoformat()]
        assert result["calendar_days"] == 3
    elif reader == "candidates":
        assert result == {"snapshot_dates": [END.isoformat()], "formal_dates": [formal_day],
                          "missing_dates": [END.isoformat()]}
    else:
        assert len(result) == 2  # The loader, rather than repository, excludes 144020 controls.
        assert {row["source_version"] for row in result} == {f"sv_accounting_G{number}"}
        assert next(row for row in result if row["account_code"] == "142001")["daily_avg_balance"] == number * 3000


@pytest.mark.parametrize("reader", READERS)
def test_adb_pin_and_explicit_active_controls(chain, reader):
    _assert_result(reader, _read(reader, chain.active), 2)
    with duckdb_read_scope(chain.selection, required_online=True):
        _assert_result(reader, _read(reader, chain.active), 1)
        with active_read_scope():
            _assert_result(reader, _read(reader, chain.active), 2)
        _assert_result(reader, _read(reader, chain.active), 1)


@pytest.mark.parametrize("reader", READERS)
def test_adb_selected_generation_does_not_require_active_file(chain, reader):
    chain.active.unlink()
    with duckdb_read_scope(chain.selection, required_online=True):
        _assert_result(reader, _read(reader, chain.active), 1)
    assert not chain.active.exists()


@pytest.mark.parametrize("reader", READERS)
@pytest.mark.parametrize("active_present", [False, True])
@pytest.mark.parametrize("missing", ["pin", "snapshot"])
def test_adb_unavailable_selection_never_becomes_empty_or_live(chain, reader, active_present, missing):
    if not active_present:
        chain.active.unlink()
    selection = chain.selection if missing == "snapshot" else None
    error = DuckDBReadSelectionError if missing == "snapshot" else DuckDBOnlineReadRequiredError
    with duckdb_read_scope(selection, required_online=True, active_path=chain.active):
        if missing == "snapshot":
            chain.snapshot.unlink()
        with pytest.raises(error):
            _read(reader, chain.active)
    assert chain.active.exists() is active_present


def _assert_empty(reader, result):
    if reader == "accounting":
        assert result[0]["daily_avg_total"] == 0 and result[1:] == ([], [], 0)
        assert all(row["daily_avg_pct"] is None for row in result[0]["rows"])
    elif reader == "accounting_trend":
        assert result == ([], [], [], 0)
    elif reader == "raw":
        assert result[0].empty and result[1].empty and result[2] == result[3] == []
    elif reader == "calculate":
        assert result[0] == adb._empty_adb_response() and result[1] == result[2] == []
    elif reader == "coverage":
        assert result["snapshot_date_count"] == result["formal_date_count"] == result["missing_count"] == 0
        assert result["missing_dates"] == []
    elif reader == "candidates":
        assert result == {"snapshot_dates": [], "formal_dates": [], "missing_dates": []}
    else:
        assert result == []


@pytest.mark.parametrize("reader", READERS)
@pytest.mark.parametrize("schema", [False, True])
def test_adb_valid_empty_snapshot_remains_empty(chain, reader, schema, tmp_path):
    empty = tmp_path / "empty.duckdb"
    _seed(empty, 1, empty=True, schema=schema)
    chain.active.unlink()
    with duckdb_read_scope(DuckDBReadSelection(chain.active, empty, "empty"), required_online=True):
        _assert_empty(reader, _read(reader, chain.active))


@pytest.mark.parametrize("reader", READERS)
def test_adb_unbound_missing_file_contract_is_preserved(chain, reader):
    chain.active.unlink()
    if reader in {"coverage", "candidates"}:
        with pytest.raises(FileNotFoundError):
            _read(reader, chain.active)
    else:
        _assert_empty(reader, _read(reader, chain.active))
    assert not chain.active.exists()


@pytest.mark.parametrize("reader", READERS)
def test_adb_revalidates_snapshot_after_outer_existence_check(chain, reader, monkeypatch):
    if reader in {"accounting", "accounting_trend"}:
        name = "fetch_accounting_basis_rows" if reader == "accounting" else "fetch_accounting_basis_trend_rows"
        original = getattr(AdbAnalysisRepository, name)

        def lose_before_query(repo, *args, **kwargs):
            chain.snapshot.unlink()
            return original(repo, *args, **kwargs)

        monkeypatch.setattr(AdbAnalysisRepository, name, lose_before_query)
    elif reader.startswith("repo_"):
        original = repo_module.read_only_connection

        @contextmanager
        def lose_before_connect(*args, **kwargs):
            chain.snapshot.unlink()
            with original(*args, **kwargs) as conn:
                yield conn

        monkeypatch.setattr(repo_module, "read_only_connection", lose_before_connect)
    else:
        original = AdbAnalysisRepository.scoped_connection

        @contextmanager
        def lose_before_scope(repo):
            chain.snapshot.unlink()
            with original(repo) as conn:
                yield conn

        monkeypatch.setattr(AdbAnalysisRepository, "scoped_connection", lose_before_scope)
    with duckdb_read_scope(chain.selection, required_online=True):
        with pytest.raises(DuckDBReadSelectionError):
            _read(reader, chain.active)


@pytest.mark.parametrize("envelope", ["daily", "comparison", "monthly", "insights"])
def test_adb_public_envelopes_keep_pin_when_active_is_missing(chain, envelope):
    chain.active.unlink()
    with duckdb_read_scope(chain.selection, required_online=True):
        if envelope == "daily":
            result = adb.adb_envelope_for_dates(START.isoformat(), END.isoformat())
            assert result["result"]["summary"]["total_avg_assets"] == 1000
        elif envelope == "comparison":
            result = adb.adb_comparison_envelope(START.isoformat(), END.isoformat())
            assert result["result"]["total_avg_assets"] == 1000
            assert result["result"]["accounting_basis_daily_avg"]["daily_avg_total"] == 3000
        elif envelope == "monthly":
            result = adb.adb_monthly_envelope(2026)
            assert result["result"]["accounting_basis_daily_avg_trend"][0]["daily_avg_total"] == 3000
        else:
            result = adb.adb_insights_envelope(START.isoformat(), END.isoformat())
        meta = result["result_meta"]
        assert meta["basis"] == "analytical" and meta["formal_use_allowed"] is False
        assert "sv_formal_G1" in meta["source_version"] and "sv_snapshot_G1" in meta["source_version"]
        assert "G2" not in meta["source_version"]


def test_adb_selection_can_be_created_with_no_active_database(chain):
    chain.active.unlink()
    selection = DuckDBReadSelection(chain.active, chain.snapshot, "G1")
    with duckdb_read_scope(selection, required_online=True):
        for reader in READERS:
            _assert_result(reader, _read(reader, chain.active), 1)
    assert not chain.active.exists()


def test_adb_real_routes_keep_generation_values_source_and_permissions(tmp_path, monkeypatch):
    # Existing publication fixture supplies the real middleware contract. Only
    # settings and inbound identity are supplied; SQLite grants remain real.
    settings = _settings(tmp_path)
    _seed(Path(settings.duckdb_path), 2)
    settings.governance_sql_dsn = f"sqlite:///{tmp_path / 'synthetic-scopes.sqlite'}"
    settings.postgres_dsn = settings.governance_sql_dsn
    scopes = UserScopeRepository(settings.governance_sql_dsn)
    try:
        scopes.grant_scope(user_id="synthetic-reader", role="viewer", resource="adb_analysis", action="read",
                           operator="synthetic-test", reason="Isolated test-only read permission")
    finally:
        scopes.engine.dispose()
    pnl_root = Path(settings.financial_publication_root)
    pnl_digest = _seal_generation(pnl_root, "pnl-synthetic", "SYNTHETIC")
    _write_pointer(pnl_root, "pnl-synthetic", [("pnl-synthetic", pnl_digest)])
    root = system_read_publication_root(settings)
    generations = []
    for number in (1, 2):
        generation = f"system-read-2026-09-15-{str(number) * 20}"
        _seal_generation(root, generation, f"synthetic-G{number}",
                         system_read_bundle=_bundle(settings, "pnl-synthetic", pnl_digest))
        database = root / "generations" / f"{generation}.duckdb"
        _seed(database, number)
        manifest_path = root / "generations" / f"{generation}.manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        manifest["database"].update(size_bytes=database.stat().st_size, sha256=sha256_file(database))
        content = canonical_json_bytes(manifest)
        manifest_path.write_bytes(content)
        generations.append((generation, sha256_bytes(content)))
    _write_pointer(root, generations[1][0], [generations[1], generations[0]])
    monkeypatch.setenv("MOSS_DUCKDB_PATH", settings.duckdb_path)
    # Earlier tests may reload settings; patch the module used by route-local imports.
    settings_module = importlib.import_module("backend.app.governance.settings")
    monkeypatch.setattr(settings_module, "get_settings", lambda: settings)
    monkeypatch.setattr(adb, "get_settings", lambda: settings)
    adb.clear_adb_comparison_cache()
    adb.clear_adb_insights_cache()
    app = FastAPI()
    app.add_middleware(SystemReadPublicationMiddleware, settings_provider=lambda: settings)
    app.include_router(routes.router)
    reader = lambda: AuthContext(user_id="synthetic-reader", role="viewer", identity_source="synthetic-test")
    app.dependency_overrides[get_auth_context] = reader
    Path(settings.duckdb_path).unlink()
    try:
        with TestClient(app) as client:
            for number in (1, 2, 1):
                generation = generations[number - 1][0]
                for endpoint in ("", "/comparison", "/monthly", "/coverage"):
                    response = client.get(
                        f"/api/analysis/adb{endpoint}",
                        params={"start_date": START.isoformat(), "end_date": END.isoformat(), "year": 2026},
                        headers={SYSTEM_READ_GENERATION_HEADER: generation},
                    )
                    assert response.status_code == 200, response.text
                    assert response.headers[SYSTEM_READ_GENERATION_HEADER] == generation
                    body = response.json()
                    if endpoint == "/coverage":
                        _assert_result("coverage", body, number)
                        continue
                    meta, payload = body["result_meta"], body["result"]
                    assert meta["basis"] == "analytical" and meta["formal_use_allowed"] is False
                    assert f"sv_formal_G{number}" in meta["source_version"]
                    assert f"sv_snapshot_G{number}" in meta["source_version"]
                    if endpoint == "":
                        assert payload["summary"]["total_avg_assets"] == number * 1000
                    elif endpoint == "/comparison":
                        assert payload["total_avg_assets"] == number * 1000
                        assert payload["accounting_basis_daily_avg"]["daily_avg_total"] == number * 3000
                    else:
                        assert payload["accounting_basis_daily_avg_trend"][0]["daily_avg_total"] == number * 3000
                app.dependency_overrides[get_auth_context] = lambda: AuthContext(
                    user_id="synthetic-no-grant", role="viewer", identity_source="synthetic-test")
                denied = client.get("/api/analysis/adb", params={"start_date": START.isoformat(), "end_date": END.isoformat()},
                                    headers={SYSTEM_READ_GENERATION_HEADER: generation})
                assert denied.status_code == 403
                app.dependency_overrides[get_auth_context] = reader
            (root / "generations" / f"{generations[0][0]}.duckdb").unlink()
            unavailable = client.get("/api/analysis/adb", params={"start_date": START.isoformat(), "end_date": END.isoformat()},
                                     headers={SYSTEM_READ_GENERATION_HEADER: generations[0][0]})
            assert unavailable.status_code == 503
            assert SYSTEM_READ_GENERATION_HEADER not in unavailable.headers
    finally:
        adb.clear_adb_comparison_cache()
        adb.clear_adb_insights_cache()
    assert not Path(settings.duckdb_path).exists()
