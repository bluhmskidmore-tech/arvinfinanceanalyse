from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.repositories.user_scope_repo import UserScopeRepository
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from tests.helpers import load_module

LIABILITY_ANALYTICS_READ_HEADERS = {"X-User-Id": "liability-read-user", "X-User-Role": "viewer"}

_LIABILITY_ANALYTICS_READ_CASES: tuple[tuple[str, dict[str, str]], ...] = (
    ("/api/risk/buckets", {"report_date": "2026-01-31"}),
    ("/api/analysis/yield_metrics", {"report_date": "2026-01-31"}),
    ("/api/analysis/yield-by-period", {"year": "2026", "period_type": "monthly"}),
    ("/api/analysis/liabilities/counterparty", {"report_date": "2026-01-31", "top_n": "10"}),
    ("/api/liabilities/monthly", {"year": "2026"}),
    ("/ui/liability/business-context", {}),
    ("/api/analysis/liabilities/cockpit-warnings", {"report_date": "2026-01-31"}),
    ("/api/analysis/liabilities/contribution-split", {"report_date": "2026-01-31"}),
)


def _configure_liability_scope_store(tmp_path: Path, monkeypatch, *, grant_read_scope: bool) -> None:
    sqlite_path = tmp_path / "liability-analytics-read-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    if grant_read_scope:
        UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
            user_id="*",
            role=None,
            resource="liability_analytics",
            action="read",
        )


def _build_client(tmp_path: Path, monkeypatch, *, grant_read_scope: bool = True) -> TestClient:
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "liability.duckdb"))
    _configure_liability_scope_store(tmp_path, monkeypatch, grant_read_scope=grant_read_scope)
    main_mod = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_mod.app)
    client.headers.update(LIABILITY_ANALYTICS_READ_HEADERS)
    return client


def test_liability_analytics_read_surfaces_require_explicit_read_scope(tmp_path: Path, monkeypatch) -> None:
    client = _build_client(tmp_path, monkeypatch, grant_read_scope=False)

    for path, params in _LIABILITY_ANALYTICS_READ_CASES:
        response = client.get(path, params=params or None)
        assert response.status_code == 403, f"{path}: {response.status_code} {response.text}"


def test_liability_analytics_routes_fail_closed_while_surface_remains_reserved(
    tmp_path: Path, monkeypatch
) -> None:
    client = _build_client(tmp_path, monkeypatch)

    for path, params in (
        ("/api/risk/buckets", {"report_date": "2026-01-31"}),
        ("/api/analysis/yield_metrics", {"report_date": "2026-01-31"}),
        ("/api/analysis/yield-by-period", {"year": "2026", "period_type": "monthly"}),
        ("/api/analysis/liabilities/counterparty", {"report_date": "2026-01-31", "top_n": "10"}),
        ("/api/liabilities/monthly", {"year": "2026"}),
    ):
        response = client.get(path, params=params)
        assert response.status_code == 200, path
        body = response.json()
        assert "result_meta" in body, path
        assert "result" in body, path
        assert body["result_meta"].get("basis") == "analytical", path


def test_liability_analytics_routes_still_validate_invalid_report_date(
    tmp_path: Path, monkeypatch
) -> None:
    client = _build_client(tmp_path, monkeypatch)

    for path in (
        "/api/risk/buckets",
        "/api/analysis/yield_metrics",
        "/api/analysis/liabilities/counterparty",
    ):
        response = client.get(path, params={"report_date": "2026-99-99"})
        assert response.status_code == 422, path
        assert "invalid report_date" in response.json()["detail"].lower(), path


def test_liability_analytics_monthly_route_still_validates_year_bounds(
    tmp_path: Path, monkeypatch
) -> None:
    client = _build_client(tmp_path, monkeypatch)

    response = client.get("/api/liabilities/monthly", params={"year": "1999"})
    assert response.status_code == 422


def test_yield_by_period_returns_envelope_with_empty_periods_on_empty_db(
    tmp_path: Path, monkeypatch
) -> None:
    client = _build_client(tmp_path, monkeypatch)

    response = client.get("/api/analysis/yield-by-period", params={"year": "2026", "period_type": "monthly"})
    assert response.status_code == 200
    body = response.json()
    assert body["result_meta"]["result_kind"] == "liability_analytics.yield_by_period"
    assert body["result"]["year"] == 2026
    assert body["result"]["period_type"] == "monthly"
    assert body["result"]["periods"] == []


def test_yield_history_uses_batch_repo_fetch(monkeypatch) -> None:
    service_mod = load_module(
        "backend.app.services.liability_analytics_service_history_batch",
        "backend/app/services/liability_analytics_service.py",
    )

    class Repo:
        def __init__(self) -> None:
            self.batch_calls: list[list[str]] = []
            self.single_zqtz_calls: list[str] = []
            self.single_tyw_calls: list[str] = []

        def list_report_dates(self):
            return ["2026-01-31", "2026-01-30", "2026-01-29"]

        def fetch_yield_rows_for_dates(self, dates):
            self.batch_calls.append(list(dates))
            return (
                {d: [{"report_date": d, "zqtz": d}] for d in dates},
                {d: [{"report_date": d, "tyw": d}] for d in dates},
            )

        def fetch_zqtz_yield_rows(self, report_date: str):
            self.single_zqtz_calls.append(report_date)
            return []

        def fetch_tyw_rows(self, report_date: str):
            self.single_tyw_calls.append(report_date)
            return []

    repo = Repo()
    seen: list[tuple[str, list[dict[str, str]], list[dict[str, str]]]] = []

    def fake_compute(report_date, zqtz_rows, tyw_rows):
        seen.append((report_date, zqtz_rows, tyw_rows))
        return {
            "kpi": {
                "asset_yield": float(report_date[-2:]),
                "liability_cost": 0.01,
                "market_liability_cost": 0.02,
                "nim": 0.03,
            }
        }

    monkeypatch.setattr(service_mod, "compute_liability_yield_metrics", fake_compute)

    history = service_mod._build_yield_history_series(repo, "2026-01-31", max_points=3)

    assert repo.batch_calls == [["2026-01-31", "2026-01-30", "2026-01-29"]]
    assert repo.single_zqtz_calls == []
    assert repo.single_tyw_calls == []
    assert [point["date"] for point in history] == ["2026-01-29", "2026-01-30", "2026-01-31"]
    assert [item[0] for item in seen] == ["2026-01-29", "2026-01-30", "2026-01-31"]


def test_yield_history_falls_back_per_missing_batch_date(monkeypatch) -> None:
    service_mod = load_module(
        "backend.app.services.liability_analytics_service_history_partial_batch",
        "backend/app/services/liability_analytics_service.py",
    )

    class Repo:
        def __init__(self) -> None:
            self.single_zqtz_calls: list[str] = []
            self.single_tyw_calls: list[str] = []

        def list_report_dates(self):
            return ["2026-01-31", "2026-01-30"]

        def fetch_yield_rows_for_dates(self, dates):
            return (
                {"2026-01-31": [{"source": "batch-zqtz"}]},
                {"2026-01-30": [{"source": "batch-tyw"}]},
            )

        def fetch_zqtz_yield_rows(self, report_date: str):
            self.single_zqtz_calls.append(report_date)
            return [{"source": f"single-zqtz-{report_date}"}]

        def fetch_tyw_rows(self, report_date: str):
            self.single_tyw_calls.append(report_date)
            return [{"source": f"single-tyw-{report_date}"}]

    repo = Repo()
    seen: dict[str, tuple[list[dict[str, str]], list[dict[str, str]]]] = {}

    def fake_compute(report_date, zqtz_rows, tyw_rows):
        seen[report_date] = (zqtz_rows, tyw_rows)
        return {"kpi": {"asset_yield": 0.01, "liability_cost": 0.02, "market_liability_cost": 0.03, "nim": 0.04}}

    monkeypatch.setattr(service_mod, "compute_liability_yield_metrics", fake_compute)

    service_mod._build_yield_history_series(repo, "2026-01-31", max_points=2)

    assert repo.single_zqtz_calls == ["2026-01-30"]
    assert repo.single_tyw_calls == ["2026-01-31"]
    assert seen["2026-01-31"] == (
        [{"source": "batch-zqtz"}],
        [{"source": "single-tyw-2026-01-31"}],
    )
    assert seen["2026-01-30"] == (
        [{"source": "single-zqtz-2026-01-30"}],
        [{"source": "batch-tyw"}],
    )


def test_yield_history_falls_back_when_batch_fetch_fails(monkeypatch) -> None:
    service_mod = load_module(
        "backend.app.services.liability_analytics_service_history_batch_failure",
        "backend/app/services/liability_analytics_service.py",
    )

    class Repo:
        def __init__(self) -> None:
            self.single_zqtz_calls: list[str] = []
            self.single_tyw_calls: list[str] = []

        def list_report_dates(self):
            return ["2026-01-31", "2026-01-30"]

        def fetch_yield_rows_for_dates(self, dates):
            raise RuntimeError("batch unavailable")

        def fetch_zqtz_yield_rows(self, report_date: str):
            self.single_zqtz_calls.append(report_date)
            return [{"source": f"single-zqtz-{report_date}"}]

        def fetch_tyw_rows(self, report_date: str):
            self.single_tyw_calls.append(report_date)
            return [{"source": f"single-tyw-{report_date}"}]

    repo = Repo()
    seen: list[str] = []

    def fake_compute(report_date, zqtz_rows, tyw_rows):
        seen.append(report_date)
        return {"kpi": {"asset_yield": 0.01, "liability_cost": 0.02, "market_liability_cost": 0.03, "nim": 0.04}}

    monkeypatch.setattr(service_mod, "compute_liability_yield_metrics", fake_compute)

    service_mod._build_yield_history_series(repo, "2026-01-31", max_points=2)

    assert repo.single_zqtz_calls == ["2026-01-30", "2026-01-31"]
    assert repo.single_tyw_calls == ["2026-01-30", "2026-01-31"]
    assert seen == ["2026-01-30", "2026-01-31"]
