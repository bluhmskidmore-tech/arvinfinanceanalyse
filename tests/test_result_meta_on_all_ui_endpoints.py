"""Cross-endpoint contracts for UI JSON envelopes: result_meta + result, basis semantics."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import duckdb
import pytest
from fastapi import FastAPI
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


def _stub_result_meta(result_kind: str) -> dict[str, Any]:
    meta = {key: None for key in REQUIRED_RESULT_META_KEYS}
    meta.update(
        {
            "trace_id": f"tr_{result_kind.replace('.', '_')}",
            "basis": "analytical",
            "formal_use_allowed": False,
            "scenario_flag": False,
            "result_kind": result_kind,
            "quality_flag": "ok",
            "source_version": "sv_result_meta_contract",
            "vendor_version": "vv_none",
            "rule_version": "rv_result_meta_contract",
            "cache_version": "cv_result_meta_contract",
            "vendor_status": "ok",
            "fallback_mode": "none",
            "evidence_rows": 0,
            "tables_used": [],
            "filters_applied": {},
            "sql_executed": [],
        }
    )
    return meta


def _stub_executive_payload(result_kind: str) -> dict[str, Any]:
    return {"result_meta": _stub_result_meta(result_kind), "result": {}}


def _executive_contract_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    module = load_module(
        "tests._result_meta_exec.executive_contract",
        "backend/app/api/routes/executive.py",
    )
    monkeypatch.setattr(
        module,
        "executive_overview",
        lambda report_date=None: _stub_executive_payload("executive.overview"),
    )
    monkeypatch.setattr(
        module,
        "executive_summary",
        lambda report_date=None: _stub_executive_payload("executive.summary"),
    )
    monkeypatch.setattr(
        module,
        "executive_pnl_attribution",
        lambda report_date=None: _stub_executive_payload("executive.pnl-attribution"),
    )
    app = FastAPI()
    app.include_router(module.router)
    return TestClient(app)


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
        ("/ui/pnl/product-category/dates", {}),
        ("/ui/balance-movement-analysis/dates", {}),
        ("/ui/balance-analysis/dates", {}),
        ("/ui/preview/macro-foundation", {}),
        ("/ui/macro/choice-series/latest", {}),
        ("/ui/market-data/fx/formal-status", {}),
        ("/ui/market-data/fx/analytical", {}),
        ("/ui/market-data/livermore", {}),
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

    if path in {"/ui/home/overview", "/ui/home/summary", "/ui/pnl/attribution"}:
        client = _executive_contract_client(monkeypatch)
    else:
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
    client = _executive_contract_client(monkeypatch)

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
        "/ui/news/choice-events/latest",
        "/ui/preview/source-foundation",
        "/ui/preview/source-foundation/history",
        "/ui/preview/source-foundation/zqtz/rows",
        "/ui/preview/source-foundation/zqtz/traces",
        "/ui/home/contribution",
        "/ui/home/alerts",
        "/ui/risk/overview",
    ),
)
def test_excluded_ui_surfaces_fail_closed_without_governed_result_meta(
    path, tmp_path, monkeypatch
):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    sys.modules.pop("backend.app.main", None)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    params = {"limit": 1, "offset": 0} if path.endswith(("/rows", "/traces")) else None
    response = client.get(path, params=params)
    assert response.status_code == 503, path
    body = response.json()
    assert "result_meta" not in body, path
    assert "reserved" in str(body.get("detail", "")).lower(), path
    get_settings.cache_clear()


def test_macro_vendor_surfaces_emit_governed_envelopes(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    sys.modules.pop("backend.app.main", None)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    for path in (
        "/ui/preview/macro-foundation",
        "/ui/macro/choice-series/latest",
        "/ui/market-data/fx/formal-status",
        "/ui/market-data/fx/analytical",
    ):
        response = client.get(path)
        assert response.status_code == 200, path
        meta = _assert_json_envelope(response.json(), path=path)
        _assert_basis_consistency(meta, path=path)
    get_settings.cache_clear()


def test_source_preview_surfaces_fail_closed_instead_of_emitting_analytical_meta(
    tmp_path, monkeypatch
):
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
        response = client.get(path, params=params)
        assert response.status_code == 503, path
        assert "result_meta" not in response.json(), path
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
    assert "disabled" in str(body.get("detail", "")).lower()
    assert "result_meta" not in body
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


def test_source_preview_refresh_status_now_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    sys.modules.pop("backend.app.main", None)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    r = client.get("/ui/preview/source-foundation/refresh-status")
    assert r.status_code == 503
    body = r.json()
    assert "result_meta" not in body
    assert "reserved" in str(body.get("detail", "")).lower()
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
