"""Contract tests for bond-analytics HTTP API (envelope + core result fields)."""
from __future__ import annotations

import asyncio
from typing import Any

import httpx
from httpx import ASGITransport

from backend.app.main import app


REPORT_DATE = "2026-03-31"

_BOND_ANALYTICS_CASES: list[tuple[str, dict[str, str]]] = [
    (
        "/api/bond-analytics/return-decomposition",
        {"report_date": REPORT_DATE, "period_type": "MoM"},
    ),
    (
        "/api/bond-analytics/benchmark-excess",
        {
            "report_date": REPORT_DATE,
            "period_type": "MoM",
            "benchmark_id": "CDB_INDEX",
        },
    ),
    (
        "/api/bond-analytics/krd-curve-risk",
        {"report_date": REPORT_DATE},
    ),
    (
        "/api/bond-analytics/credit-spread-migration",
        {"report_date": REPORT_DATE},
    ),
    (
        "/api/bond-analytics/action-attribution",
        {"report_date": REPORT_DATE, "period_type": "MoM"},
    ),
    (
        "/api/bond-analytics/accounting-class-audit",
        {"report_date": REPORT_DATE},
    ),
]


def _assert_envelope(payload: dict[str, Any]) -> None:
    assert "result_meta" in payload
    assert "result" in payload
    meta = payload["result_meta"]
    for key in ("trace_id", "basis", "source_version", "rule_version"):
        assert key in meta, f"result_meta missing {key!r}"
        assert meta[key] not in (None, ""), f"result_meta.{key} must be non-empty"

    result = payload["result"]
    for key in ("report_date", "computed_at", "warnings"):
        assert key in result, f"result missing {key!r}"


async def _check_all_endpoints() -> None:
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for path, params in _BOND_ANALYTICS_CASES:
            response = await client.get(path, params=params)
            assert response.status_code == 200, (
                f"{path} {params} -> {response.status_code}: {response.text}"
            )
            payload = response.json()
            _assert_envelope(payload)


def test_bond_analytics_endpoints_envelope_and_result_shape() -> None:
    """Six bond-analytics routes return 200 + result_meta/result with required keys."""
    asyncio.run(_check_all_endpoints())


def test_bond_analytics_each_path_distinct_contract() -> None:
    """Sanity: each configured path is exercised once."""
    paths = [p for p, _ in _BOND_ANALYTICS_CASES]
    assert len(paths) == len(set(paths)) == 6
