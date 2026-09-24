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


def _ensure_user_allowed_scopes(node: ast.AST) -> frozenset[tuple[str, str]]:
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
        direct_authz = {name for name, node in functions.items() if _call_names(node) & _AUTHZ_CALL_NAMES}
        authz_closure = set(direct_authz)
        authz_scopes_by_function = {
            name: _ensure_user_allowed_scopes(node)
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
                if name in authz_closure:
                    continue
                if _call_names(node) & authz_closure:
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
                        authz_scopes=authz_scopes_by_function[name],
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

    response = client.get(f"/health{path}" if path in {"", "/live", "/ready"} else "/ui/balance-analysis/current-user")
    payload = response.json()

    assert method == "GET"
    # `/health/ready` self-reports dependency degradation as 503 (e7531a33), and this
    # isolated client has no live dependencies. Derive the expected status from the
    # payload so the probe's status code must agree with its own verdict, instead of
    # widening the guard to accept any of several numbers.
    assert response.status_code == (503 if payload.get("status") == "degraded" else 200)
    assert "result_meta" not in payload
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
