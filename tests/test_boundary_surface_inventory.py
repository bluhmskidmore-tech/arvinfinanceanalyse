from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Literal

import pytest
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from backend.app.security.route_policy import (
    ADMIN_SCOPE_ACTIONS,
    POLICY_SCOPE_SEMANTICS,
    RoutePolicySemantics,
)
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
    authz_scopes: frozenset[tuple[str, str]]

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.method, self.file_path, self.path, self.function)


BACKEND_BOUNDARY_CASES: tuple[SurfaceCase, ...] = (
    SurfaceCase(
        "agent.query",
        "/api/agent/query",
        "POST",
        json={"question": "ping"},
        expected_status=404,
        detail_substring="not found",
    ),
    SurfaceCase("preview.source-foundation", "/ui/preview/source-foundation", "GET"),
    SurfaceCase("preview.source-foundation.history", "/ui/preview/source-foundation/history", "GET", params={"limit": 5, "offset": 0}),
    SurfaceCase("preview.source-foundation.rows", "/ui/preview/source-foundation/zqtz/rows", "GET", params={"limit": 1, "offset": 0}),
    SurfaceCase("preview.source-foundation.traces", "/ui/preview/source-foundation/zqtz/traces", "GET", params={"limit": 1, "offset": 0}),
    SurfaceCase("preview.source-foundation.refresh", "/ui/preview/source-foundation/refresh", "POST", side_effect_target="refresh_source_preview", side_effect_module="backend.app.api.routes.source_preview", side_effect_file="backend/app/api/routes/source_preview.py"),
    SurfaceCase("preview.source-foundation.refresh-status", "/ui/preview/source-foundation/refresh-status", "GET"),
    # 保留 ingest 端点授权先于保留判断：无 import scope 的身份 fail-closed 为 403；
    # 授权后仍由 _raise_choice_news_reserved_surface 返回 503 reserved。
    SurfaceCase(
        "news.ui.ingest",
        "/ui/news/tushare-npr/ingest",
        "POST",
        expected_status=403,
        detail_substring="not allowed",
    ),
    SurfaceCase(
        "news.api.ingest",
        "/api/news/tushare-npr/ingest",
        "POST",
        expected_status=403,
        detail_substring="not allowed",
    ),
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

PUBLIC_OR_ECHO_READ_POLICIES = {
    ("GET", "backend/app/api/routes/health.py", "/live", "live"): RoutePolicySemantics(
        policy_class="public",
        owner="Platform health owner",
        reason="Liveness probe returns only service status.",
    ),
    ("GET", "backend/app/api/routes/health.py", "", "health"): RoutePolicySemantics(
        policy_class="public",
        owner="Platform health owner",
        reason="Basic health probe returns only service status.",
    ),
    ("GET", "backend/app/api/routes/health.py", "/ready", "ready"): RoutePolicySemantics(
        policy_class="public",
        owner="Platform health owner",
        reason="Readiness probe returns dependency health only, not governed business data.",
    ),
}

READ_LIKE_POST_SURFACES = {
    ("POST", "backend/app/api/routes/agent.py", "/query", "query_agent"),
    ("POST", "backend/app/api/routes/agent.py", "/runs", "create_agent_run_endpoint"),
    ("POST", "backend/app/api/routes/cube_query.py", "/query", "cube_query"),
    (
        "POST",
        "backend/app/api/routes/ledger_pnl.py",
        "/ledger-pnl/candidate-financial-indicators/revalidate",
        "revalidate_candidate_financial_indicators",
    ),
}

PUBLIC_OR_ECHO_READ_SURFACES = set(PUBLIC_OR_ECHO_READ_POLICIES)

CAPABILITY_PROBE_READ_SURFACES = {
    ("GET", "backend/app/api/routes/balance_analysis.py", "/current-user", "current_user")
}

# Choice news ingest 保留端点现已在函数体内先调用 ensure_user_allowed
# (choice_news.data/import) 再抛 503 reserved，不再属于"未接授权门"的例外面。
RESERVED_WRITE_POLICIES: dict[tuple[str, str, str, str], RoutePolicySemantics] = {}

RESERVED_WRITE_SURFACES = set(RESERVED_WRITE_POLICIES)

RESERVED_HELPER_SCOPES = {
    ("choice_news.data", "import"),
}

_GATED_TOP_LEVEL_ROUTE_MODULES = {"agent"}
_NESTED_ROUTE_MODULES = {"agent_workspace"}

# Governance classifications are pinned by name, never by registry size: a count
# cannot tell an added router from a deleted or renamed one, so it only ever gets
# its number bumped. These entries fail loudly when a governance-critical router
# is dropped or moved to a different claim boundary.
PINNED_ROUTER_GROUPS = {
    "cube_query": "support",
    "health": "support",
    "liability_analytics": "analytical_compatibility",
    "macro_etf_strategy": "macro_market",
    "macro_toolkit": "macro_market",
    "pnl": "formal_mainline",
    "source_preview": "preview",
}

REQUIRED_ROUTE_GROUPS = {
    "formal_mainline",
    "analytical_compatibility",
    "preview",
    "macro_market",
    "support",
}

# Routes reach the scope store either directly or through the shared
# `backend/app/api/deps.ensure_read_allowed` guard, which pins action="read".
_AUTHZ_CALL_NAMES = frozenset({"ensure_user_allowed", "ensure_read_allowed"})


def _load_api_registry(
    monkeypatch: pytest.MonkeyPatch,
    *,
    agent_enabled: bool,
):
    monkeypatch.setenv("MOSS_AGENT_ENABLED", str(agent_enabled).lower())
    get_settings.cache_clear()
    for module_name in tuple(sys.modules):
        if module_name == "backend.app.api" or module_name.startswith("backend.app.api."):
            sys.modules.pop(module_name, None)
    return load_module("backend.app.api", "backend/app/api/__init__.py")


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


def _create_empty_scope_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sqlite_path = tmp_path / "boundary-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    repo_module = load_module(
        "backend.app.repositories.user_scope_repo",
        "backend/app/repositories/user_scope_repo.py",
    )
    repo_module.UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}")


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


def _literal_keyword(call: ast.Call, name: str) -> str | None:
    for keyword in call.keywords:
        if keyword.arg == name and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
            return keyword.value.value
    return None


def _literal_argument(call: ast.Call, index: int, name: str) -> str | None:
    if len(call.args) > index:
        candidate = call.args[index]
        if isinstance(candidate, ast.Constant) and isinstance(candidate.value, str):
            return candidate.value
    return _literal_keyword(call, name)


def _name_keyword(call: ast.Call, name: str) -> str | None:
    for keyword in call.keywords:
        if keyword.arg == name and isinstance(keyword.value, ast.Name):
            return keyword.value.id
    return None


def _assignment_bindings(node: ast.AST) -> dict[str, ast.expr]:
    bindings: dict[str, ast.expr] = {}
    for child in ast.walk(node):
        if isinstance(child, ast.Assign):
            for target in child.targets:
                if isinstance(target, ast.Name):
                    bindings[target.id] = child.value
        elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name) and child.value is not None:
            bindings[child.target.id] = child.value
    return bindings


def _literal_values(
    node: ast.expr,
    bindings: dict[str, ast.expr],
    seen: frozenset[str] = frozenset(),
) -> set[object]:
    """Resolve literal policy declarations; unknown expressions stay unknown."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value}
    if isinstance(node, ast.Name) and node.id in bindings and node.id not in seen:
        return _literal_values(bindings[node.id], bindings, seen | {node.id})
    if isinstance(node, ast.IfExp):
        return _literal_values(node.body, bindings, seen) | _literal_values(node.orelse, bindings, seen)
    if isinstance(node, ast.Tuple | ast.List):
        alternatives = [_literal_values(item, bindings, seen) for item in node.elts]
        return set(product(*alternatives))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "tuple" and len(node.args) == 1:
        return _literal_values(node.args[0], bindings, seen)
    if isinstance(node, ast.GeneratorExp) and len(node.generators) == 1:
        generator = node.generators[0]
        if generator.ifs or generator.is_async:
            return set()
        if isinstance(generator.target, ast.Name):
            values: set[object] = set()
            for sequence in _literal_values(generator.iter, bindings, seen):
                if not isinstance(sequence, tuple):
                    continue
                for item in sequence:
                    if isinstance(item, str):
                        values.update(_literal_values(
                            node.elt,
                            {**bindings, generator.target.id: ast.Constant(value=item)},
                            seen,
                        ))
            return {tuple(values)} if values else set()
    return set()


def _ensure_user_allowed_scopes(
    node: ast.AST,
    module_bindings: dict[str, ast.expr] | None = None,
) -> frozenset[tuple[str, str]]:
    bindings = {**(module_bindings or {}), **_assignment_bindings(node)}
    scopes: set[tuple[str, str]] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        func_name = ""
        if isinstance(child.func, ast.Name):
            func_name = child.func.id
        elif isinstance(child.func, ast.Attribute):
            func_name = child.func.attr
        if func_name == "ensure_read_allowed":
            resource = _literal_argument(child, 1, "resource")
            if resource:
                scopes.add((resource, "read"))
            continue
        if func_name != "ensure_user_allowed":
            continue
        resource = _literal_keyword(child, "resource")
        action = _literal_keyword(child, "action")
        if resource and action:
            scopes.add((resource, action))
        elif func_name == "ensure_user_allowed":
            keywords = {keyword.arg: keyword.value for keyword in child.keywords}
            if "resource" in keywords and "action" in keywords:
                scopes.update(
                    (resource_value, action_value)
                    for resource_value in _literal_values(keywords["resource"], bindings)
                    for action_value in _literal_values(keywords["action"], bindings)
                    if isinstance(resource_value, str) and isinstance(action_value, str)
                )
    for child in ast.walk(node):
        if not isinstance(child, ast.For) or not isinstance(child.target, ast.Tuple):
            continue
        if not all(isinstance(target, ast.Name) for target in child.target.elts):
            continue
        for sequence in _literal_values(child.iter, bindings):
            if not isinstance(sequence, tuple):
                continue
            for values in sequence:
                if not isinstance(values, tuple) or len(values) != len(child.target.elts):
                    continue
                loop_bindings = {
                    target.id: ast.Constant(value=value)
                    for target, value in zip(child.target.elts, values, strict=True)
                    if isinstance(target, ast.Name) and isinstance(value, str)
                }
                for statement in child.body:
                    scopes.update(_ensure_user_allowed_scopes(statement, {**bindings, **loop_bindings}))
    return frozenset(scopes)


def _ensure_user_allowed_parameterized_actions(node: ast.AST) -> dict[str, str]:
    actions: dict[str, str] = {}
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        func_name = ""
        if isinstance(child.func, ast.Name):
            func_name = child.func.id
        elif isinstance(child.func, ast.Attribute):
            func_name = child.func.attr
        if func_name != "ensure_user_allowed":
            continue
        resource = _literal_keyword(child, "resource")
        action_name = _name_keyword(child, "action")
        if resource and action_name:
            actions[action_name] = resource
    return actions


def _scopes_from_parameterized_helper_calls(
    node: ast.AST,
    parameterized_actions_by_function: dict[str, dict[str, str]],
) -> frozenset[tuple[str, str]]:
    scopes: set[tuple[str, str]] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        func_name = ""
        if isinstance(child.func, ast.Name):
            func_name = child.func.id
        elif isinstance(child.func, ast.Attribute):
            func_name = child.func.attr
        action_resources = parameterized_actions_by_function.get(func_name)
        if not action_resources:
            continue
        for action_param, resource in action_resources.items():
            action = _literal_keyword(child, action_param)
            if action:
                scopes.add((resource, action))
    return frozenset(scopes)


def _route_method(decorator: ast.expr) -> str | None:
    target = decorator.func if isinstance(decorator, ast.Call) else decorator
    if isinstance(target, ast.Attribute) and target.attr in {"get", "post", "put", "patch", "delete"}:
        return target.attr.upper()
    return None


def _route_path(decorator: ast.expr) -> str:
    if isinstance(decorator, ast.Call) and decorator.args and isinstance(decorator.args[0], ast.Constant):
        return str(decorator.args[0].value)
    return ""


def _module_policy_bindings(tree: ast.Module) -> dict[str, ast.expr]:
    return _assignment_bindings(ast.Module(
        body=[node for node in tree.body if isinstance(node, ast.Assign | ast.AnnAssign)],
        type_ignores=[],
    ))


def _imported_route_guards(tree: ast.Module) -> dict[str, tuple[ast.AST, dict[str, ast.expr]]]:
    guards: dict[str, tuple[ast.AST, dict[str, ast.expr]]] = {}
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or not (node.module or "").startswith("backend.app.api.routes."):
            continue
        source_path = Path(str(node.module).replace(".", "/") + ".py")
        if not source_path.is_file():
            continue
        source_tree = ast.parse(source_path.read_text(encoding="utf-8"))
        definitions = {
            child.name: child
            for child in source_tree.body
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef)
        }
        for alias in node.names:
            definition = definitions.get(alias.name)
            if definition is not None and _call_names(definition) & _AUTHZ_CALL_NAMES:
                guards[alias.asname or alias.name] = (definition, _module_policy_bindings(source_tree))
    return guards


def _route_auth_surfaces() -> list[RouteAuthSurface]:
    surfaces: list[RouteAuthSurface] = []
    route_root = Path("backend/app/api/routes")
    for path in sorted(route_root.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        local_functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        }
        imported_guards = _imported_route_guards(tree)
        functions = {**{name: node for name, (node, _bindings) in imported_guards.items()}, **local_functions}
        module_bindings = _module_policy_bindings(tree)
        direct_authz = {name for name, node in functions.items() if _call_names(node) & _AUTHZ_CALL_NAMES}
        authz_closure = set(direct_authz)
        authz_scopes_by_function = {
            name: _ensure_user_allowed_scopes(
                node,
                imported_guards[name][1] if name in imported_guards else module_bindings,
            )
            for name, node in functions.items()
        }
        parameterized_actions_by_function = {
            name: _ensure_user_allowed_parameterized_actions(node)
            for name, node in functions.items()
        }
        for name, node in functions.items():
            helper_scopes = _scopes_from_parameterized_helper_calls(
                node,
                parameterized_actions_by_function,
            )
            if helper_scopes:
                authz_scopes_by_function[name] = frozenset(
                    set(authz_scopes_by_function[name]) | set(helper_scopes)
                )
        changed = True
        while changed:
            changed = False
            for name, node in functions.items():
                if name not in authz_closure and _call_names(node) & authz_closure:
                    authz_closure.add(name)
                    changed = True
                called_scopes = frozenset(
                    scope
                    for called_name in _call_names(node)
                    for scope in authz_scopes_by_function.get(called_name, frozenset())
                )
                if called_scopes and not called_scopes <= authz_scopes_by_function[name]:
                    authz_scopes_by_function[name] = frozenset(
                        set(authz_scopes_by_function[name]) | set(called_scopes)
                    )
                    changed = True

        file_path = path.as_posix()
        for name, node in local_functions.items():
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
                        authz_scopes=authz_scopes_by_function[name],
                    )
                )
    return surfaces


@pytest.mark.parametrize(
    ("permissions", "expected"),
    [
        (
            '(("formal_pnl", "refresh"),)',
            frozenset({("formal_pnl", "refresh")}),
        ),
        (
            'tuple((resource, "refresh") for resource in ("formal_pnl", "bond_analytics"))',
            frozenset({("formal_pnl", "refresh"), ("bond_analytics", "refresh")}),
        ),
        (
            'tuple((resource, "refresh") for resource in ("formal_pnl",) if False)',
            frozenset(),
        ),
        (
            'tuple((resource, "refresh") for resource in ("formal_pnl",) if unverified_predicate(resource))',
            frozenset(),
        ),
        (
            'tuple((resource, "refresh") async for resource in ("formal_pnl",))',
            frozenset(),
        ),
        ("unverified_permissions()", frozenset()),
    ],
)
def test_authorization_scope_scan_requires_resolved_literal_permissions(permissions, expected):
    tree = ast.parse(
        f"async def authorize(auth):\n"
        f"    permissions = {permissions}\n"
        "    for resource, action in permissions:\n"
        "        ensure_user_allowed(auth=auth, resource=resource, action=action)\n"
    )

    assert _ensure_user_allowed_scopes(tree.body[0]) == expected


def test_imported_route_guard_scan_checks_the_helper_body():
    tree = ast.parse(
        "from backend.app.api.routes.data_health import _ensure_data_health_read_allowed\n"
        "from backend.app.api.routes.data_updates import _public_run\n"
    )

    guards = _imported_route_guards(tree)

    assert set(guards) == {"_ensure_data_health_read_allowed"}
    guard, bindings = guards["_ensure_data_health_read_allowed"]
    assert _ensure_user_allowed_scopes(guard, bindings) == frozenset({("data_health", "read")})


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


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize(
    ("environment", "client_host", "user_id", "grant_read", "expected_status"),
    [
        ("production", "127.0.0.1", "anonymous", False, 403),
        ("development", "198.51.100.7", "anonymous", False, 403),
        ("development", "127.0.0.1", "named-viewer", False, 403),
        ("development", "127.0.0.1", "anonymous", False, 200),
        ("production", "127.0.0.1", "scoped-viewer", True, 200),
    ],
)
def test_system_read_publication_enforces_data_health_read_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    enabled: bool,
    environment: str,
    client_host: str,
    user_id: str,
    grant_read: bool,
    expected_status: int,
) -> None:
    from types import SimpleNamespace

    from backend.app.repositories.user_scope_repo import UserScopeRepository
    from fastapi import FastAPI

    route = load_module(
        "backend.app.api.routes.system_read_publication",
        "backend/app/api/routes/system_read_publication.py",
    )
    dsn = f"sqlite:///{(tmp_path / 'publication-scope.db').as_posix()}"
    repo = UserScopeRepository(dsn)
    if grant_read:
        repo.grant_scope(user_id=user_id, role=None, resource="data_health", action="read")
    settings = SimpleNamespace(
        environment=environment,
        governance_sql_dsn=dsn,
        postgres_dsn=dsn,
        system_read_publication_enabled=enabled,
    )
    context_reads: list[bool] = []

    def publication_context():
        context_reads.append(True)
        return SimpleNamespace(
            generation="publication-test-generation",
            coverage_dates={"formal_pnl": ("2026-03-31",)},
        )

    monkeypatch.setattr(route, "current_system_read_context", publication_context)
    monkeypatch.delenv("MOSS_USER_ID", raising=False)
    monkeypatch.delenv("MOSS_USER_ROLE", raising=False)
    monkeypatch.delenv(ROLE_HEADER_TRUST_ENV, raising=False)
    if user_id != "anonymous":
        monkeypatch.setenv("MOSS_USER_ID", user_id)
    app = FastAPI()
    app.include_router(route.router)
    app.dependency_overrides[route.get_settings] = lambda: settings
    # Keep the real identity dependency so the local anonymous case proves
    # that Request.client supplies the loopback evidence used by the guard.
    client = TestClient(app, client=(client_host, 12345))

    response = client.get("/api/system-read-publication")

    assert response.status_code == expected_status
    if expected_status == 403:
        assert response.json() == {"detail": "User is not allowed to read data_health."}
        assert context_reads == []
    else:
        assert response.json() == {
            "enabled": enabled,
            "generation": "publication-test-generation" if enabled else None,
            "coverage_dates": {"formal_pnl": ["2026-03-31"]} if enabled else {},
        }
        assert context_reads == ([True] if enabled else [])


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


def test_backend_authorized_routes_expose_stable_resource_action_policy() -> None:
    missing_policy = [
        surface
        for surface in _route_auth_surfaces()
        if surface.reaches_authz
        and surface.key not in PUBLIC_OR_ECHO_READ_SURFACES
        and surface.key not in RESERVED_WRITE_SURFACES
        and not surface.authz_scopes
    ]

    assert missing_policy == []


def test_backend_route_exceptions_expose_explicit_policy_semantics() -> None:
    unauthenticated_surfaces = {
        surface.key
        for surface in _route_auth_surfaces()
        if not surface.reaches_authz
    }

    assert unauthenticated_surfaces == set(PUBLIC_OR_ECHO_READ_POLICIES) | set(RESERVED_WRITE_POLICIES)
    assert [
        key
        for key, policy in PUBLIC_OR_ECHO_READ_POLICIES.items()
        if policy.policy_class != "public" or policy.state != "active" or not policy.owner
    ] == []
    assert [
        key
        for key, policy in RESERVED_WRITE_POLICIES.items()
        if policy.policy_class != "admin" or policy.state != "reserved" or not policy.owner
    ] == []


@pytest.mark.parametrize(
    "route_key",
    tuple(PUBLIC_OR_ECHO_READ_POLICIES),
    ids=lambda route_key: f"{route_key[0]} {route_key[2] or '/'}",
)
def test_public_or_echo_routes_do_not_return_governed_result_meta(
    route_key: tuple[str, str, str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    method, _file_path, path, _function = route_key
    client = _build_client(tmp_path, monkeypatch)
    repository_checks: list[str] = []
    if path == "/ready":
        endpoint = next(route.endpoint for route in client.app.routes if route.path == "/health/ready")
        health_globals = endpoint.__globals__["ready_health_payload"].__globals__

        def synthetic_repository(component: str):
            class SyntheticRepository:
                def __init__(self, *_args: object, **_kwargs: object) -> None:
                    pass

                def healthcheck(self) -> dict[str, object]:
                    repository_checks.append(component)
                    return {"ok": False, "private_test_diagnostic": "synthetic unavailable dependency"}

            return SyntheticRepository

        for repository, component in (
            ("PostgresRepository", "postgresql"),
            ("DuckDBRepository", "duckdb"),
            ("RedisRepository", "redis"),
            ("ObjectStoreRepository", "object_store"),
        ):
            monkeypatch.setitem(health_globals, repository, synthetic_repository(component))

    response = client.get(f"/health{path}" if path in {"", "/live", "/ready"} else "/ui/balance-analysis/current-user")
    payload = response.json()

    assert method == "GET"
    # `/health/ready` self-reports dependency degradation as 503 (e7531a33), and this
    # isolated client has no live dependencies. Derive the expected status from the
    # payload so the probe's status code must agree with its own verdict, instead of
    # widening the guard to accept any of several numbers.
    assert response.status_code == (503 if payload.get("status") == "degraded" else 200)
    assert "result_meta" not in payload
    if path == "/ready":
        assert repository_checks == ["postgresql", "duckdb", "redis", "object_store"]
        assert payload["status"] == "degraded"
        assert {component: payload["checks"][component] for component in repository_checks} == {
            component: {"ok": False} for component in repository_checks
        }
    get_settings.cache_clear()


def test_backend_authorized_routes_expose_explicit_policy_semantics() -> None:
    used_scope_semantics = {
        scope
        for surface in _route_auth_surfaces()
        for scope in surface.authz_scopes
    }
    missing_scope_semantics = [
        (surface.key, resource, action)
        for surface in _route_auth_surfaces()
        for resource, action in surface.authz_scopes
        if (resource, action) not in POLICY_SCOPE_SEMANTICS
    ]
    public_scoped_routes = [
        (surface.key, resource, action)
        for surface in _route_auth_surfaces()
        for resource, action in surface.authz_scopes
        if POLICY_SCOPE_SEMANTICS[(resource, action)].policy_class == "public"
    ]
    ownerless_semantics = [
        (resource, action)
        for (resource, action), policy in POLICY_SCOPE_SEMANTICS.items()
        if not policy.owner.strip()
    ]
    unused_scope_semantics = [
        scope
        for scope in POLICY_SCOPE_SEMANTICS
        if scope not in used_scope_semantics and scope not in RESERVED_HELPER_SCOPES
    ]
    invalid_reserved_helper_semantics = [
        scope
        for scope in RESERVED_HELPER_SCOPES
        if scope not in POLICY_SCOPE_SEMANTICS
        or POLICY_SCOPE_SEMANTICS[scope].policy_class != "admin"
        or POLICY_SCOPE_SEMANTICS[scope].state != "reserved"
    ]

    assert missing_scope_semantics == []
    assert public_scoped_routes == []
    assert ownerless_semantics == []
    assert unused_scope_semantics == []
    assert invalid_reserved_helper_semantics == []


def test_backend_policy_taxonomy_matches_audit_contract() -> None:
    allowed_policy_classes = {"public", "internal", "admin"}
    unexpected_scope_classes = [
        (resource, action, policy.policy_class)
        for (resource, action), policy in POLICY_SCOPE_SEMANTICS.items()
        if policy.policy_class not in allowed_policy_classes
    ]
    unexpected_exception_classes = [
        (key, policy.policy_class)
        for key, policy in {
            **PUBLIC_OR_ECHO_READ_POLICIES,
            **RESERVED_WRITE_POLICIES,
        }.items()
        if policy.policy_class not in allowed_policy_classes
    ]

    assert unexpected_scope_classes == []
    assert unexpected_exception_classes == []


def test_backend_policy_classes_match_resource_action_semantics() -> None:
    read_scope_misclassified_as_admin = [
        (resource, action)
        for (resource, action), policy in POLICY_SCOPE_SEMANTICS.items()
        if action == "read" and policy.policy_class == "admin"
    ]
    admin_action_without_admin_class = [
        (resource, action, policy.policy_class)
        for (resource, action), policy in POLICY_SCOPE_SEMANTICS.items()
        if action in ADMIN_SCOPE_ACTIONS and policy.policy_class != "admin"
    ]

    assert read_scope_misclassified_as_admin == []
    assert admin_action_without_admin_class == []


@pytest.mark.parametrize("agent_enabled", (False, True), ids=("agent-disabled", "agent-enabled"))
def test_api_router_registry_classifies_every_included_router(
    monkeypatch: pytest.MonkeyPatch,
    agent_enabled: bool,
) -> None:
    api_module = _load_api_registry(monkeypatch, agent_enabled=agent_enabled)

    registry = tuple(api_module.ROUTE_REGISTRY)
    declared_groups = set(api_module.ROUTE_GROUP_METADATA)
    route_groups = {entry.group for entry in registry}
    entries_by_name = {entry.name: entry for entry in registry}
    unnamed = [index for index, entry in enumerate(registry) if not entry.name.strip()]
    missing_tags = [entry.name for entry in registry if not entry.tags]
    missing_owner = [entry.name for entry in registry if not entry.owner.strip()]
    ungrouped = [
        (entry.name, entry.group)
        for entry in registry
        if entry.group not in declared_groups
    ]
    misclassified = {
        name: entries_by_name[name].group if name in entries_by_name else "<absent from registry>"
        for name, expected_group in PINNED_ROUTER_GROUPS.items()
        if name not in entries_by_name or entries_by_name[name].group != expected_group
    }

    assert registry
    assert unnamed == []
    assert missing_tags == []
    assert missing_owner == []
    assert ungrouped == []
    assert misclassified == {}
    assert len(entries_by_name) == len(registry)
    assert len({id(entry.router) for entry in registry}) == len(registry)
    assert route_groups >= REQUIRED_ROUTE_GROUPS
    if agent_enabled:
        assert "agent_experimental" in route_groups
        assert entries_by_name["agent"].group == "agent_experimental"
    else:
        assert "agent_experimental" not in route_groups
        assert "agent" not in entries_by_name
    assert "agent_workspace" not in entries_by_name


def test_api_router_registry_agent_gate_adds_only_the_agent_router(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    disabled = {
        entry.name: entry.group
        for entry in _load_api_registry(monkeypatch, agent_enabled=False).ROUTE_REGISTRY
    }
    enabled = {
        entry.name: entry.group
        for entry in _load_api_registry(monkeypatch, agent_enabled=True).ROUTE_REGISTRY
    }

    assert set(enabled) - set(disabled) == {"agent"}
    assert set(disabled) - set(enabled) == set()
    assert {name: group for name, group in enabled.items() if name != "agent"} == disabled
    assert enabled["agent"] == "agent_experimental"


@pytest.mark.parametrize("agent_enabled", (False, True), ids=("agent-disabled", "agent-enabled"))
def test_api_router_registry_covers_every_route_module_file(
    monkeypatch: pytest.MonkeyPatch,
    agent_enabled: bool,
) -> None:
    api_module = _load_api_registry(monkeypatch, agent_enabled=agent_enabled)

    route_modules = {
        path.stem
        for path in Path("backend/app/api/routes").glob("*.py")
        if path.name != "__init__.py"
    }
    registered_modules = {
        entry.name.rsplit("_ui", maxsplit=1)[0].rsplit("_api", maxsplit=1)[0]
        for entry in api_module.ROUTE_REGISTRY
    }

    top_level_route_modules = route_modules - _NESTED_ROUTE_MODULES
    expected_unregistered = _GATED_TOP_LEVEL_ROUTE_MODULES if not agent_enabled else set()

    assert sorted(top_level_route_modules - registered_modules) == sorted(expected_unregistered)
    assert registered_modules <= top_level_route_modules
    assert _NESTED_ROUTE_MODULES.isdisjoint(registered_modules)


@pytest.mark.parametrize("agent_enabled", (False, True), ids=("agent-disabled", "agent-enabled"))
def test_api_route_groups_expose_claim_boundary_metadata(
    monkeypatch: pytest.MonkeyPatch,
    agent_enabled: bool,
) -> None:
    api_module = _load_api_registry(monkeypatch, agent_enabled=agent_enabled)

    registry = tuple(api_module.ROUTE_REGISTRY)
    route_groups = {entry.group for entry in registry}
    group_metadata = dict(api_module.ROUTE_GROUP_METADATA)
    missing_group_metadata = sorted(route_groups - set(group_metadata))
    extra_group_metadata = sorted(set(group_metadata) - route_groups)
    incomplete_metadata = [
        group
        for group, metadata in group_metadata.items()
        if not metadata.label.strip()
        or not metadata.claim_boundary.strip()
        or not metadata.risk_boundary.strip()
        or not metadata.owner.strip()
    ]

    assert missing_group_metadata == []
    assert extra_group_metadata == ([] if agent_enabled else ["agent_experimental"])
    assert incomplete_metadata == []
    assert group_metadata["formal_mainline"].claim_boundary != group_metadata["preview"].claim_boundary
    assert "certified" not in group_metadata["agent_experimental"].claim_boundary.lower()


def test_route_scope_audit_documents_backend_api_route_groups() -> None:
    route_scope_doc = Path("docs/audits/2026-06-06-route-scope-classification.md").read_text(
        encoding="utf-8"
    )

    for required in (
        "Backend API Router Grouping Boundary",
        "backend/app/api/__init__.py",
        "ROUTE_REGISTRY",
        "ROUTE_GROUP_METADATA",
        "`formal_mainline`",
        "`preview`",
        "`macro_market`",
        "`agent_experimental`",
        "`support`",
        "registration alone is not route certification",
        "tool isolation, evidence strength separation, and confirmation-token controls",
    ):
        assert required in route_scope_doc


@pytest.mark.parametrize("agent_enabled", (False, True), ids=("agent-disabled", "agent-enabled"))
def test_api_router_registry_matches_included_route_surface(
    monkeypatch: pytest.MonkeyPatch,
    agent_enabled: bool,
) -> None:
    api_module = _load_api_registry(monkeypatch, agent_enabled=agent_enabled)

    registry = tuple(api_module.ROUTE_REGISTRY)
    registered_route_count = sum(len(entry.router.routes) for entry in registry)
    group_route_counts = {
        group: sum(len(entry.router.routes) for entry in registry if entry.group == group)
        for group in {entry.group for entry in registry}
    }

    assert len(api_module.router.routes) == registered_route_count
    if agent_enabled:
        assert group_route_counts["formal_mainline"] > group_route_counts["agent_experimental"]
    else:
        assert "agent_experimental" not in group_route_counts
    assert group_route_counts["macro_market"] > 0
    assert group_route_counts["preview"] > 0


def test_api_router_includes_only_registered_entries() -> None:
    tree = ast.parse(Path("backend/app/api/__init__.py").read_text(encoding="utf-8"))
    include_calls = [
        call
        for call in ast.walk(tree)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == "include_router"
    ]

    assert len(include_calls) == 1
    include_call = include_calls[0]
    assert isinstance(include_call.func.value, ast.Name)
    assert include_call.func.value.id == "router"
    assert len(include_call.args) == 1
    assert isinstance(include_call.args[0], ast.Attribute)
    assert isinstance(include_call.args[0].value, ast.Name)
    assert include_call.args[0].value.id == "entry"
    assert include_call.args[0].attr == "router"


def test_backend_read_and_mutation_routes_use_expected_policy_actions() -> None:
    read_like_wrong_action = [
        surface
        for surface in _route_auth_surfaces()
        if (surface.method == "GET" or surface.key in READ_LIKE_POST_SURFACES)
        and surface.key not in PUBLIC_OR_ECHO_READ_SURFACES
        and surface.key not in CAPABILITY_PROBE_READ_SURFACES
        and "read" not in {action for _resource, action in surface.authz_scopes}
    ]
    mutation_wrong_action = [
        surface
        for surface in _route_auth_surfaces()
        if surface.method in {"POST", "PUT", "PATCH", "DELETE"}
        and surface.key not in READ_LIKE_POST_SURFACES
        and surface.key not in RESERVED_WRITE_SURFACES
        and not ({action for _resource, action in surface.authz_scopes} - {"read"})
    ]

    assert read_like_wrong_action == []
    assert mutation_wrong_action == []


@pytest.mark.parametrize("case", BACKEND_BOUNDARY_CASES, ids=lambda case: case.slug)
def test_backend_boundary_surfaces_fail_closed_without_governed_result_meta(
    case: SurfaceCase,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if case.expected_status == 403:
        _create_empty_scope_store(tmp_path, monkeypatch)
        monkeypatch.setenv("MOSS_ENVIRONMENT", "development")
        monkeypatch.setenv("MOSS_USER_ID", "boundary-no-scope-user")
        monkeypatch.setenv("MOSS_USER_ROLE", "viewer")
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
