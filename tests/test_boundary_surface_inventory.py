from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pytest
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from tests.helpers import load_module


# Committed docs only — clean clones must pass without local `.omx/plans/` (often gitignored).
REQUIRED_AUTHORITY_DOCS = (
    "docs/CURRENT_BOUNDARY_HANDOFF_2026-04-10.md",
    "docs/DOCUMENT_AUTHORITY.md",
    "docs/architecture.md",
    "docs/IMPLEMENTATION_PLAN.md",
)

OPTIONAL_LOCAL_PLAN_DOCS = (
    ".omx/plans/ralplan-architecture-findings-repair-2026-05-01.md",
    ".omx/plans/prd-architecture-findings-repair.md",
    ".omx/plans/test-spec-architecture-findings-repair.md",
)


@dataclass(frozen=True)
class SurfaceCase:
    slug: str
    path: str
    method: Literal["GET", "POST"]
    params: dict[str, object] | None = None
    json: dict[str, object] | None = None
    expected_status: int = 503
    detail_substring: str = "reserved"
    side_effect_target: str | None = None
    side_effect_module: str | None = None
    side_effect_file: str | None = None


@dataclass(frozen=True)
class RouteAuthSurface:
    file_path: str
    line: int
    method: str
    path: str
    function: str
    reaches_authz: bool

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.method, self.file_path, self.path, self.function)


BACKEND_BOUNDARY_CASES: tuple[SurfaceCase, ...] = (
    SurfaceCase("agent.query", "/api/agent/query", "POST", json={"question": "ping"}, detail_substring="disabled"),
    SurfaceCase("preview.source-foundation", "/ui/preview/source-foundation", "GET"),
    SurfaceCase("preview.source-foundation.history", "/ui/preview/source-foundation/history", "GET", params={"limit": 5, "offset": 0}),
    SurfaceCase("preview.source-foundation.rows", "/ui/preview/source-foundation/zqtz/rows", "GET", params={"limit": 1, "offset": 0}),
    SurfaceCase("preview.source-foundation.traces", "/ui/preview/source-foundation/zqtz/traces", "GET", params={"limit": 1, "offset": 0}),
    SurfaceCase("preview.source-foundation.refresh", "/ui/preview/source-foundation/refresh", "POST", side_effect_target="refresh_source_preview", side_effect_module="backend.app.api.routes.source_preview", side_effect_file="backend/app/api/routes/source_preview.py"),
    SurfaceCase("preview.source-foundation.refresh-status", "/ui/preview/source-foundation/refresh-status", "GET"),
    SurfaceCase("news.ui.ingest", "/ui/news/tushare-npr/ingest", "POST", side_effect_target="ingest_tushare_npr_to_choice_news", side_effect_module="backend.app.api.routes.choice_news", side_effect_file="backend/app/api/routes/choice_news.py"),
    SurfaceCase("news.api.ingest", "/api/news/tushare-npr/ingest", "POST", side_effect_target="ingest_tushare_npr_to_choice_news", side_effect_module="backend.app.api.routes.choice_news", side_effect_file="backend/app/api/routes/choice_news.py"),
    SurfaceCase(
        "executive.risk-overview",
        "/ui/risk/overview",
        "GET",
        expected_status=403,
        detail_substring="not allowed",
    ),
    SurfaceCase(
        "executive.home.alerts",
        "/ui/home/alerts",
        "GET",
        expected_status=403,
        detail_substring="not allowed",
    ),
    SurfaceCase(
        "executive.home.contribution",
        "/ui/home/contribution",
        "GET",
        expected_status=403,
        detail_substring="not allowed",
    ),
)

FRONTEND_RESERVED_KEYS = (
    "cube-query",
    "risk-overview",
    "market-data",
    "news-events",
    "source-preview",
)

PUBLIC_OR_ECHO_READ_SURFACES = {
    ("GET", "backend/app/api/routes/health.py", "/live", "live"),
    ("GET", "backend/app/api/routes/health.py", "", "health"),
    ("GET", "backend/app/api/routes/health.py", "/ready", "ready"),
    ("GET", "backend/app/api/routes/balance_analysis.py", "/current-user", "current_user"),
}

READ_LIKE_POST_SURFACES = {
    ("POST", "backend/app/api/routes/agent.py", "/query", "query_agent"),
    ("POST", "backend/app/api/routes/agent.py", "/runs", "create_agent_run_endpoint"),
    ("POST", "backend/app/api/routes/cube_query.py", "/query", "cube_query"),
}

RESERVED_WRITE_SURFACES = {
    ("POST", "backend/app/api/routes/choice_news.py", "/tushare-npr/ingest", "tushare_npr_ingest_ui"),
    ("POST", "backend/app/api/routes/choice_news.py", "/tushare-npr/ingest", "tushare_npr_ingest_api"),
}


def _build_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(tmp_path / "archive"))
    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(tmp_path / "data_input"))
    monkeypatch.setenv("MOSS_AGENT_ENABLED", "false")
    monkeypatch.setenv("MOSS_AGENT_PROVIDER", "local")
    get_settings.cache_clear()
    for mod in ("backend.app.main", "backend.app.api"):
        sys.modules.pop(mod, None)
    return TestClient(load_module("backend.app.main", "backend/app/main.py").app)


def _grant_scope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, resource: str, action: str) -> None:
    sqlite_path = tmp_path / "boundary-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    repo_module = load_module(
        "backend.app.repositories.user_scope_repo",
        "backend/app/repositories/user_scope_repo.py",
    )
    repo_module.UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
        user_id="*",
        role=None,
        resource=resource,
        action=action,
    )


def _call_case(client: TestClient, case: SurfaceCase):
    if case.method == "GET":
        return client.get(case.path, params=case.params)
    return client.post(case.path, params=case.params, json=case.json)


def _patch_side_effect_target(
    monkeypatch: pytest.MonkeyPatch,
    *,
    module_name: str,
    file_path: str,
    attr_path: str,
) -> None:
    module = load_module(module_name, file_path)

    def fail(*_args: object, **_kwargs: object) -> object:
        raise AssertionError(f"{attr_path} should not be called for reserved boundary route.")

    target = module
    parts = attr_path.split(".")
    for part in parts[:-1]:
        target = getattr(target, part)
    monkeypatch.setattr(target, parts[-1], fail)


def _call_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        if isinstance(child.func, ast.Name):
            names.add(child.func.id)
        elif isinstance(child.func, ast.Attribute):
            names.add(child.func.attr)
    return names


def _route_method(decorator: ast.expr) -> str | None:
    target = decorator.func if isinstance(decorator, ast.Call) else decorator
    if isinstance(target, ast.Attribute) and target.attr in {"get", "post", "put", "patch", "delete"}:
        return target.attr.upper()
    return None


def _route_path(decorator: ast.expr) -> str:
    if isinstance(decorator, ast.Call) and decorator.args and isinstance(decorator.args[0], ast.Constant):
        return str(decorator.args[0].value)
    return ""


def _route_auth_surfaces() -> list[RouteAuthSurface]:
    surfaces: list[RouteAuthSurface] = []
    route_root = Path("backend/app/api/routes")
    for path in sorted(route_root.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        }
        direct_authz = {
            name
            for name, node in functions.items()
            if "ensure_user_allowed" in _call_names(node)
        }
        authz_closure = set(direct_authz)
        changed = True
        while changed:
            changed = False
            for name, node in functions.items():
                if name in authz_closure:
                    continue
                if _call_names(node) & authz_closure:
                    authz_closure.add(name)
                    changed = True

        file_path = path.as_posix()
        for name, node in functions.items():
            calls = _call_names(node)
            reaches_authz = name in authz_closure or bool(calls & authz_closure)
            for decorator in node.decorator_list:
                method = _route_method(decorator)
                if method is None:
                    continue
                surfaces.append(
                    RouteAuthSurface(
                        file_path=file_path,
                        line=node.lineno,
                        method=method,
                        path=_route_path(decorator),
                        function=name,
                        reaches_authz=reaches_authz,
                    )
                )
    return surfaces


def test_authority_inventory_lists_required_backend_and_frontend_surfaces() -> None:
    for doc in REQUIRED_AUTHORITY_DOCS:
        assert Path(doc).exists(), doc
    for doc in OPTIONAL_LOCAL_PLAN_DOCS:
        path = Path(doc)
        if path.exists():
            assert path.is_file(), doc

    backend_slugs = {case.slug for case in BACKEND_BOUNDARY_CASES}
    assert "agent.query" in backend_slugs
    assert "news.api.ingest" in backend_slugs
    assert "preview.source-foundation.refresh" in backend_slugs
    assert "executive.risk-overview" in backend_slugs
    assert "executive.home.alerts" in backend_slugs
    assert "executive.home.contribution" in backend_slugs
    assert set(FRONTEND_RESERVED_KEYS) == {
        "cube-query",
        "risk-overview",
        "market-data",
        "news-events",
        "source-preview",
    }


def test_backend_read_like_routes_reach_authorization_gate() -> None:
    missing = [
        surface
        for surface in _route_auth_surfaces()
        if (surface.method == "GET" or surface.key in READ_LIKE_POST_SURFACES)
        and surface.key not in PUBLIC_OR_ECHO_READ_SURFACES
        and not surface.reaches_authz
    ]

    assert missing == []


def test_backend_mutation_routes_are_authorized_or_explicitly_reserved() -> None:
    mutation_methods = {"POST", "PUT", "PATCH", "DELETE"}
    missing = [
        surface
        for surface in _route_auth_surfaces()
        if surface.method in mutation_methods
        and surface.key not in READ_LIKE_POST_SURFACES
        and surface.key not in RESERVED_WRITE_SURFACES
        and not surface.reaches_authz
    ]

    assert missing == []


@pytest.mark.parametrize("case", BACKEND_BOUNDARY_CASES, ids=lambda case: case.slug)
def test_backend_boundary_surfaces_fail_closed_without_governed_result_meta(
    case: SurfaceCase,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _build_client(tmp_path, monkeypatch)

    response = _call_case(client, case)

    assert response.status_code == case.expected_status, f"{case.path} -> {response.status_code} {response.text}"
    body = response.json()
    assert "result_meta" not in body, case.path
    assert case.detail_substring.lower() in str(body.get("detail", "")).lower(), case.path
    get_settings.cache_clear()


def test_choice_macro_refresh_status_returns_idle_without_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _grant_scope(tmp_path, monkeypatch, resource="macro_vendor", action="read")
    client = _build_client(tmp_path, monkeypatch)

    response = client.get("/ui/macro/choice-series/refresh-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "idle"
    assert payload["job_name"] == "choice_macro_refresh"
    assert payload["cache_key"] == "choice_macro.latest"
    get_settings.cache_clear()


@pytest.mark.parametrize(
    "case",
    tuple(case for case in BACKEND_BOUNDARY_CASES if case.side_effect_target is not None),
    ids=lambda case: case.slug,
)
def test_reserved_write_like_surfaces_prove_no_side_effects(
    case: SurfaceCase,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert case.side_effect_module is not None
    assert case.side_effect_file is not None
    assert case.side_effect_target is not None

    _patch_side_effect_target(
        monkeypatch,
        module_name=case.side_effect_module,
        file_path=case.side_effect_file,
        attr_path=case.side_effect_target,
    )
    client = _build_client(tmp_path, monkeypatch)

    response = _call_case(client, case)

    assert response.status_code == case.expected_status, f"{case.path} -> {response.status_code} {response.text}"
    assert "result_meta" not in response.json(), case.path
    get_settings.cache_clear()
