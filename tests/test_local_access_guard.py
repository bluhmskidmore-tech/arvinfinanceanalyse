from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, get_auth_context
from tests.helpers import load_module


@pytest.fixture
def local_app(monkeypatch, tmp_path, request):
    monkeypatch.setenv("MOSS_ENVIRONMENT", "development")
    local_only_api = getattr(request, "param", True)
    monkeypatch.setenv("MOSS_LOCAL_ONLY_API", "1" if local_only_api else "0")
    if not local_only_api:
        import sys
        monkeypatch.setattr(sys, "argv", ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0"])
    monkeypatch.setenv("MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS", "1")
    monkeypatch.setenv("MOSS_SYSTEM_READ_PUBLICATION_ENABLED", "0")
    monkeypatch.setenv("MOSS_FINANCIAL_PUBLICATION_ENABLED", "0")
    monkeypatch.setenv("MOSS_AGENT_ENABLED", "0")
    monkeypatch.setenv("MOSS_AGENT_DEV_SCOPE_BYPASS", "0")
    monkeypatch.setenv("MOSS_CORS_ORIGINS", "http://localhost:5888,http://127.0.0.1:5888,http://[::1]:5888")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "isolated.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    monkeypatch.setenv("MOSS_GOVERNANCE_SQL_DSN", f"sqlite:///{tmp_path / 'scope.db'}")
    monkeypatch.delenv("MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST", raising=False)
    monkeypatch.delenv("MOSS_USER_ID", raising=False)
    monkeypatch.delenv("MOSS_USER_ROLE", raising=False)
    get_settings.cache_clear()
    app = load_module("backend.app.main", "backend/app/main.py").app
    reached = []

    def probe(auth: Annotated[AuthContext, Depends(get_auth_context)]):
        reached.append(True)
        return asdict(auth)

    app.add_api_route("/__local_boundary_probe__", probe, methods=["GET", "POST"])
    yield app, reached
    get_settings.cache_clear()


def _client(app, *, peer="127.0.0.1", server="127.0.0.1"):
    if ":" in server:
        # This locked TestClient cannot parse a bracketed IPv6 URL with a port.
        # Supply the equivalent ASGI socket address without changing dependencies.
        async def ipv6_server(scope, receive, send):
            await app({**scope, "server": (server, 7888)}, receive, send)
        return TestClient(ipv6_server, client=(peer, 50000), base_url="http://127.0.0.1:7888", headers={"Host": f"[{server}]:7888"})
    return TestClient(app, client=(peer, 50000), base_url=f"http://{server}:7888")


@pytest.mark.parametrize("address", ["127.0.0.1", "::1"])
def test_development_allows_real_loopback_peer_and_host(local_app, address):
    app, reached = local_app
    response = _client(app, peer=address, server=address).get("/__local_boundary_probe__")
    assert response.status_code == 200
    assert response.json()["user_id"] == "anonymous"
    assert response.json()["role"] == "viewer"
    assert reached == [True]


@pytest.mark.parametrize("peer,server", [("10.0.0.5", "127.0.0.1"), ("127.0.0.1", "10.0.0.5")])
def test_development_rejects_remote_peer_or_bound_server_before_handler(local_app, peer, server):
    app, reached = local_app
    response = _client(app, peer=peer, server=server).get("/__local_boundary_probe__")
    assert response.status_code == 403
    assert reached == []


@pytest.mark.parametrize("missing_addresses", [("client",), ("server",), ("client", "server")])
def test_development_rejects_missing_socket_addresses_before_handler(local_app, missing_addresses):
    app, reached = local_app

    async def missing_socket_app(scope, receive, send):
        await app({**scope, **dict.fromkeys(missing_addresses)}, receive, send)

    response = _client(missing_socket_app).get("/__local_boundary_probe__")
    assert response.status_code == 403
    assert reached == []


def test_non_loopback_server_is_rejected_even_with_local_host_header(local_app):
    app, reached = local_app
    response = _client(app, server="10.0.0.5").get("/__local_boundary_probe__", headers={"Host": "127.0.0.1:7888"})
    assert response.status_code == 403
    assert reached == []


def test_loopback_host_with_different_api_port_is_rejected(local_app):
    app, reached = local_app
    response = _client(app).get("/__local_boundary_probe__", headers={"Host": "localhost:5888"})
    assert response.status_code == 403
    assert reached == []


@pytest.mark.parametrize("host", ["attacker.example", "127.0.0.1.attacker.example", "localhost.attacker.example"])
def test_development_rejects_non_local_host_before_handler(local_app, host):
    app, reached = local_app
    response = _client(app).get("/__local_boundary_probe__", headers={"Host": host})
    assert response.status_code == 403
    assert reached == []


@pytest.mark.parametrize("origin", ["https://malicious.example", "null", "http://attacker@localhost:5888", "http://localhost:5888/evil", "http://localhost:0", "http://localhost:99999", "http://localhost:5888#fragment"])
def test_development_rejects_untrusted_simple_post_origin_before_handler(local_app, origin):
    app, reached = local_app
    response = _client(app).post("/__local_boundary_probe__", headers={"Origin": origin})
    assert response.status_code == 403
    assert reached == []


def test_development_preserves_allowed_frontend_origin(local_app):
    app, reached = local_app
    response = _client(app).post("/__local_boundary_probe__", headers={"Origin": "http://localhost:5888"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5888"
    assert reached == [True]


@pytest.mark.parametrize("port", [5890, 5891, 9999])
def test_local_source_proxy_ports_do_not_expand_cross_origin_response_policy(local_app, port):
    app, reached = local_app
    origin = f"http://127.0.0.1:{port}"
    response = _client(app).post("/__local_boundary_probe__", headers={"Origin": origin, "Referer": f"{origin}/ui"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
    assert reached == [True]


@pytest.mark.parametrize("referer", ["https://malicious.example/path", "http://attacker@localhost:5888/path", "http://localhost:0/path", "http://localhost:5888.attacker/path"])
def test_development_rejects_external_or_malformed_referrer_before_handler(local_app, referer):
    app, reached = local_app
    response = _client(app).get("/__local_boundary_probe__", headers={"Referer": referer})
    assert response.status_code == 403
    assert reached == []


@pytest.mark.parametrize("method", ["get", "post"])
def test_cross_site_browser_without_origin_or_referrer_is_rejected(local_app, method):
    app, reached = local_app
    response = getattr(_client(app), method)("/__local_boundary_probe__", headers={"Sec-Fetch-Site": "cross-site"})
    assert response.status_code == 403
    assert reached == []


@pytest.mark.parametrize("host", ["attacker@localhost:7888", "localhost:7888/path", "localhost:7888#fragment", "localhost:0", "localhost:99999", "localhost:"])
def test_development_rejects_malformed_host_before_handler(local_app, host):
    app, reached = local_app
    response = _client(app).get("/__local_boundary_probe__", headers={"Host": host})
    assert response.status_code == 403
    assert reached == []


@pytest.mark.parametrize("headers", [[("Host", "localhost:7888"), ("Host", "127.0.0.1:7888")], [("Origin", "http://localhost:5888"), ("Origin", "https://malicious.example")], [("Referer", "http://localhost:5888/"), ("Referer", "https://malicious.example/")]])
def test_development_rejects_duplicate_authority_headers(local_app, headers):
    app, reached = local_app
    response = _client(app).get("/__local_boundary_probe__", headers=headers)
    assert response.status_code == 403
    assert reached == []


def test_production_proxy_contract_is_not_changed():
    from fastapi import FastAPI
    from backend.app.security.local_access import LocalDevelopmentAccessMiddleware
    app = FastAPI()
    app.add_middleware(LocalDevelopmentAccessMiddleware, environment="production", local_only_api=True)
    app.add_api_route("/probe", lambda: {"reached": True})
    response = TestClient(app, client=("10.0.0.5", 50000), base_url="https://app.example").get("/probe", headers={"Forwarded": "for=10.0.0.5", "Origin": "https://app.example"})
    assert response.status_code == 200
    assert response.json() == {"reached": True}


@pytest.mark.parametrize("local_app", [False], indirect=True)
def test_general_development_container_proxy_contract_is_preserved(local_app):
    # Actual main startup accepts Compose's 0.0.0.0 CLI bind when policy is off.
    # The container's non-loopback peer and proxy headers also reach the route.
    app, reached = local_app
    response = _client(app, peer="172.20.0.3", server="172.20.0.2").get(
        "/__local_boundary_probe__",
        headers={"Host": "backend:8000", "Origin": "http://localhost:5888", "X-Forwarded-For": "172.20.0.3"},
    )
    assert response.status_code == 200
    assert reached == [True]


@pytest.mark.parametrize("header,value", [
    ("Forwarded", "for=127.0.0.1;host=localhost"),
    ("X-Forwarded-For", "127.0.0.1"),
    ("X-Forwarded-Host", "localhost:7888"),
    ("X-Real-IP", "127.0.0.1"),
])
def test_development_rejects_proxy_identity_inputs_before_handler(local_app, header, value):
    app, reached = local_app
    response = _client(app).get("/__local_boundary_probe__", headers={header: value})
    assert response.status_code == 403
    assert reached == []


def test_local_forged_identity_headers_cannot_replace_existing_actor(local_app):
    app, reached = local_app
    response = _client(app).get("/__local_boundary_probe__", headers={"X-User-Id": "forged-user", "X-User-Role": "admin"})
    assert response.status_code == 200
    assert response.json()["user_id"] == "anonymous"
    assert response.json()["role"] == "viewer"
    assert response.json()["identity_source"] == "fallback"
    assert reached == [True]
