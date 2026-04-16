"""Verify CORS headers are present on API responses."""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_cors_preflight(client):
    """OPTIONS request from allowed origin returns CORS headers."""
    response = client.options(
        "/health/live",
        headers={
            "Origin": "http://localhost:5888",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers


def test_cors_simple_request(client):
    """GET from allowed origin includes Access-Control-Allow-Origin."""
    response = client.get(
        "/health/live",
        headers={"Origin": "http://localhost:5888"},
    )
    assert "access-control-allow-origin" in response.headers
