"""Cross-endpoint contracts for UI JSON envelopes: result_meta + result, basis semantics."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import duckdb
import pytest
from fastapi.testclient import TestClient

from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.governance.settings import get_settings
from backend.app.repositories.balance_analysis_repo import ensure_balance_analysis_tables
from backend.app.repositories.governance_repo import CACHE_MANIFEST_STREAM, GovernanceRepository
from backend.app.tasks.balance_analysis_materialize import CACHE_KEY, RULE_VERSION
from tests.helpers import load_module


def _required_result_meta_keys() -> frozenset[str]:
    meta = load_module(
        "backend.app.schemas.result_meta",
        "backend/app/schemas/result_meta.py",
    ).ResultMeta.model_fields.keys()
    return frozenset(meta)


REQUIRED_RESULT_META_KEYS = _required_result_meta_keys()


def _assert_json_envelope(payload: dict[str, Any], *, path: str) -> dict[str, Any]:
    assert "result_meta" in payload, path
    assert "result" in payload, path
    meta = payload["result_meta"]
    assert isinstance(meta, dict), path
    missing = REQUIRED_RESULT_META_KEYS - meta.keys()
    assert not missing, f"{path} missing result_meta keys: {sorted(missing)}"
    assert isinstance(payload["result"], (dict, list)), path
    return meta


def _assert_basis_consistency(meta: dict[str, Any], *, path: str) -> None:
    basis = meta.get("basis")
    formal_ok = meta.get("formal_use_allowed")
    scenario_flag = meta.get("scenario_flag")
    assert basis in ("formal", "analytical", "scenario"), path
    assert isinstance(formal_ok, bool), path
    assert isinstance(scenario_flag, bool), path
    if basis == "scenario":
        assert scenario_flag is True, path
    if basis == "formal":
        assert formal_ok is True, path
    if basis == "analytical":
        assert formal_ok is False, path


def _seed_balance_analysis_dates_contract_surface(tmp_path: Path) -> None:
    """Empty formal fact tables + manifest so /ui/balance-analysis/dates can return 200."""
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        ensure_balance_analysis_tables(conn)
    finally:
        conn.close()
    GovernanceRepository(base_dir=str(governance_dir)).append(
        CACHE_MANIFEST_STREAM,
        {
            "cache_key": CACHE_KEY,
            "source_version": "sv_contract_seed",
            "vendor_version": "vv_none",
            "rule_version": RULE_VERSION,
        },
    )


@pytest.mark.parametrize(
    "path,params",
    [
        ("/ui/home/overview", {}),
        ("/ui/home/summary", {}),
        ("/ui/pnl/attribution", {}),
        ("/ui/preview/macro-foundation", {}),
        ("/ui/macro/choice-series/latest", {}),
        ("/ui/market-data/fx/formal-status", {}),
        ("/ui/market-data/fx/analytical", {}),
        ("/ui/news/choice-events/latest", {}),
        ("/ui/preview/source-foundation", {}),
        ("/ui/preview/source-foundation/history", {}),
        ("/ui/preview/source-foundation/zqtz/rows", {"limit": 1, "offset": 0}),
        ("/ui/preview/source-foundation/zqtz/traces", {"limit": 1, "offset": 0}),
        ("/ui/pnl/product-category/dates", {}),
        ("/ui/balance-analysis/dates", {}),
        ("/ui/qdb-gl-monthly-analysis/dates", {}),
    ],
)
def test_ui_get_json_envelopes_include_result_meta_and_result(path, params, tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(tmp_path / "archive"))
    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(tmp_path / "data_input"))
    if path == "/ui/balance-analysis/dates":
        _seed_balance_analysis_dates_contract_surface(tmp_path)
    get_settings.cache_clear()

    for mod in (
        "backend.app.main",
        "backend.app.api",
    ):
        sys.modules.pop(mod, None)

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get(path, params=params or None)
    assert response.status_code == 200, f"{path} -> {response.status_code} {response.text}"
    meta = _assert_json_envelope(response.json(), path=path)
    _assert_basis_consistency(meta, path=path)
    get_settings.cache_clear()


def test_executive_surfaces_are_analytical_placeholder_friendly(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    sys.modules.pop("backend.app.main", None)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    for path in (
        "/ui/home/overview",
        "/ui/home/summary",
        "/ui/pnl/attribution",
    ):
        meta = _assert_json_envelope(client.get(path).json(), path=path)
        assert meta["basis"] == "analytical"
        assert meta["formal_use_allowed"] is False
        assert meta["scenario_flag"] is False
        assert str(meta["result_kind"]).startswith("executive.")
    get_settings.cache_clear()


@pytest.mark.parametrize(
    "path",
    (
        "/ui/home/contribution",
        "/ui/home/alerts",
        "/ui/risk/overview",
    ),
)
def test_executive_governed_exclusion_surfaces_fail_closed_with_explicit_503(
    path, tmp_path, monkeypatch
):
    """These executive routes are currently outside the repo-wide Phase 2 cutover.

    They should fail closed with an explicit 503 instead of pretending to be landed
    governed surfaces when no governed backing data exists.
    """
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    sys.modules.pop("backend.app.main", None)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get(path)
    assert response.status_code == 503, path
    body = response.json()
    assert "result_meta" not in body, path
    assert "not backed by governed data yet" in str(body.get("detail", "")).lower(), path
    get_settings.cache_clear()


def test_fx_formal_status_vs_analytical_basis_contract(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    sys.modules.pop("backend.app.main", None)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    formal = _assert_json_envelope(
        client.get("/ui/market-data/fx/formal-status").json(),
        path="/ui/market-data/fx/formal-status",
    )
    assert formal["basis"] == "formal"
    assert formal["formal_use_allowed"] is True
    assert formal["scenario_flag"] is False
    assert formal["result_kind"] == "fx.formal.status"

    analytical = _assert_json_envelope(
        client.get("/ui/market-data/fx/analytical").json(),
        path="/ui/market-data/fx/analytical",
    )
    assert analytical["basis"] == "analytical"
    assert analytical["formal_use_allowed"] is False
    assert analytical["scenario_flag"] is False
    assert analytical["result_kind"] == "fx.analytical.groups"
    get_settings.cache_clear()


def test_source_preview_surfaces_are_analytical_not_formal(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    sys.modules.pop("backend.app.main", None)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    for path, params in (
        ("/ui/preview/source-foundation", {}),
        ("/ui/preview/source-foundation/history", {"limit": 5, "offset": 0}),
        (
            "/ui/preview/source-foundation/zqtz/rows",
            {"limit": 1, "offset": 0},
        ),
    ):
        meta = _assert_json_envelope(client.get(path, params=params).json(), path=path)
        assert meta["basis"] == "analytical"
        assert meta["formal_use_allowed"] is False
        assert meta["scenario_flag"] is False
        assert str(meta["result_kind"]).startswith("preview.")
    get_settings.cache_clear()


def test_agent_post_disabled_stub_is_explicit_not_live_envelope(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_AGENT_ENABLED", "false")
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    get_settings.cache_clear()
    sys.modules.pop("backend.app.main", None)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.post(
        "/api/agent/query",
        json=AgentQueryRequest(
            question="ping",
            basis="analytical",
            filters={},
        ).model_dump(mode="json"),
    )
    assert response.status_code == 503
    body = response.json()
    assert body.get("enabled") is False
    assert "disabled" in str(body.get("detail", "")).lower() or body.get("phase") == "phase1"
    assert "result_meta" not in body
    assert "AgentEnvelope" not in str(body)
    get_settings.cache_clear()


def test_product_category_scenario_request_sets_scenario_basis(tmp_path, monkeypatch):
    from tests.test_product_category_pnl_flow import _write_month_pair

    data_root = tmp_path / "data_input"
    source_dir = data_root / "pnl_\u603b\u8d26\u5bf9\u8d26-\u65e5\u5747"
    source_dir.mkdir(parents=True)
    _write_month_pair(source_dir, "202601", january=True)

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_PRODUCT_CATEGORY_SOURCE_DIR", str(source_dir))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    task_module = sys.modules.get("backend.app.tasks.product_category_pnl")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.product_category_pnl",
            "backend/app/tasks/product_category_pnl.py",
        )
    task_module.materialize_product_category_pnl.fn(
        duckdb_path=str(duckdb_path),
        source_dir=str(source_dir),
        governance_dir=str(governance_dir),
    )

    sys.modules.pop("backend.app.main", None)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    formal = client.get(
        "/ui/pnl/product-category",
        params={"report_date": "2026-01-31", "view": "monthly"},
    ).json()
    formal_meta = _assert_json_envelope(formal, path="product-category formal")
    assert formal_meta["basis"] == "formal"
    assert formal_meta["formal_use_allowed"] is True
    assert formal_meta["scenario_flag"] is False

    scenario = client.get(
        "/ui/pnl/product-category",
        params={
            "report_date": "2026-01-31",
            "view": "monthly",
            "scenario_rate_pct": "2.5",
        },
    ).json()
    scen_meta = _assert_json_envelope(scenario, path="product-category scenario")
    assert scen_meta["basis"] == "scenario"
    assert scen_meta["formal_use_allowed"] is False
    assert scen_meta["scenario_flag"] is True
    get_settings.cache_clear()


def test_known_exceptions_source_preview_refresh_status_is_action_json_flat(
    tmp_path, monkeypatch
):
    """Matches frontend `requestActionJson` for refresh polling; not a result_meta envelope."""
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    sys.modules.pop("backend.app.main", None)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    r = client.get("/ui/preview/source-foundation/refresh-status")
    assert r.status_code == 200
    body = r.json()
    assert "result_meta" not in body
    assert body.get("status") == "idle"
    assert body.get("job_name") == "source_preview_refresh"
    get_settings.cache_clear()


def test_known_exceptions_balance_analysis_auth_action_routes_are_flat(tmp_path, monkeypatch):
    """These routes use action-json (flat) shape for frontend client compatibility; not full envelopes."""
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    sys.modules.pop("backend.app.main", None)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    r = client.get("/ui/balance-analysis/current-user")
    assert r.status_code == 200
    body = r.json()
    assert "result_meta" not in body
    assert "user_id" in body
    get_settings.cache_clear()
