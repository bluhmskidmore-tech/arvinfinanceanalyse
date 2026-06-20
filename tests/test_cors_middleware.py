"""Verify CORS trust-boundary behavior on API responses."""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

ALLOWED_ORIGIN = "http://localhost:5888"
DISALLOWED_ORIGIN = "https://malicious.example"


@pytest.fixture
def client():
    return TestClient(app)


def test_cors_preflight(client):
    """OPTIONS request from allowed origin returns CORS headers."""
    response = client.options(
        "/health/live",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers


def test_cors_simple_request(client):
    """GET from allowed origin includes Access-Control-Allow-Origin."""
    response = client.get(
        "/health/live",
        headers={"Origin": ALLOWED_ORIGIN},
    )
    assert "access-control-allow-origin" in response.headers
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


def test_cors_preflight_rejects_disallowed_origin(client):
    """Preflight from a non-whitelisted origin is rejected without allow-origin."""
    response = client.options(
        "/health/live",
        headers={
            "Origin": DISALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_cors_simple_request_omits_allow_origin_for_disallowed_origin(client):
    """Simple requests from a non-whitelisted origin do not gain CORS access."""
    response = client.get(
        "/health/live",
        headers={"Origin": DISALLOWED_ORIGIN},
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_cors_preflight_allows_mutation_route_with_auth_headers(client):
    """Mutation-route preflight accepts explicit auth headers from an allowed origin."""
    response = client.options(
        "/api/kpi/metrics",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization, X-User-Id, X-User-Role, Content-Type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    allow_headers = response.headers.get("access-control-allow-headers", "").lower()
    assert "authorization" in allow_headers
    assert "x-user-id" in allow_headers
    assert "x-user-role" in allow_headers
    assert "content-type" in allow_headers


def test_cors_preflight_rejects_unknown_request_headers(client):
    """Allowed origins do not get arbitrary request headers whitelisted."""
    response = client.options(
        "/api/kpi/metrics",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-User-Id, X-Anything",
        },
    )
    assert response.status_code == 400
    allow_headers = response.headers.get("access-control-allow-headers", "").lower()
    assert "x-anything" not in allow_headers
