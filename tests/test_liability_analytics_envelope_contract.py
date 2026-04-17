from __future__ import annotations

from pathlib import Path

from tests.test_liability_analytics_api import _build_client


def test_liability_analytics_excluded_routes_do_not_emit_governed_envelopes(
    tmp_path: Path, monkeypatch
) -> None:
    client = _build_client(tmp_path, monkeypatch)

    for path, params in (
        ("/api/risk/buckets", {"report_date": "2026-01-31"}),
        ("/api/analysis/yield_metrics", {"report_date": "2026-01-31"}),
        ("/api/analysis/liabilities/counterparty", {"report_date": "2026-01-31", "top_n": "10"}),
        ("/api/liabilities/monthly", {"year": "2026"}),
    ):
        response = client.get(path, params=params)
        assert response.status_code == 503, path
        body = response.json()
        assert "result_meta" not in body, path
        assert "result" not in body, path
