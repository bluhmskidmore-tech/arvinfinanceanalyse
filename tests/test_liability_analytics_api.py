from __future__ import annotations

import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.repositories.user_scope_repo import UserScopeRepository
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from tests.helpers import load_module

# Marker split: fail-closed/scope/validation/batch-wiring guards ->
# excluded_surface_regression; yield/NIM feature semantics ->
# excluded_surface_acceptance (per-test below).
pytestmark = [pytest.mark.surface_liability_analytics]

LIABILITY_ANALYTICS_READ_HEADERS = {"X-User-Id": "liability-read-user", "X-User-Role": "viewer"}

_LIABILITY_ANALYTICS_READ_CASES: tuple[tuple[str, dict[str, str]], ...] = (
    ("/api/risk/buckets", {"report_date": "2026-01-31"}),
    ("/api/analysis/yield_metrics", {"report_date": "2026-01-31"}),
    ("/api/analysis/yield-by-period", {"year": "2026", "period_type": "monthly"}),
    ("/api/analysis/liabilities/counterparty", {"report_date": "2026-01-31", "top_n": "10"}),
    ("/api/liabilities/monthly", {"year": "2026"}),
    ("/api/liabilities/monthly", {"year": "2026", "detail_level": "summary"}),
    ("/api/liabilities/monthly/detail", {"month": "2026-01"}),
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


@pytest.mark.excluded_surface_regression
def test_liability_analytics_read_surfaces_require_explicit_read_scope(tmp_path: Path, monkeypatch) -> None:
    client = _build_client(tmp_path, monkeypatch, grant_read_scope=False)

    for path, params in _LIABILITY_ANALYTICS_READ_CASES:
        response = client.get(path, params=params or None)
        assert response.status_code == 403, f"{path}: {response.status_code} {response.text}"


@pytest.mark.excluded_surface_regression
def test_liability_analytics_read_surface_allows_development_fallback_without_explicit_scope(
    tmp_path: Path, monkeypatch
) -> None:
    """development 环境 + 匿名 viewer 回退身份可读（与 balance_analysis / positions 读路由对齐）。

    显式头部身份缺 scope 时仍 403，由上面的契约测试锁定。
    """
    from fastapi import FastAPI

    route_mod = load_module(
        "backend.app.api.routes.liability_analytics",
        "backend/app/api/routes/liability_analytics.py",
    )
    monkeypatch.setattr(
        route_mod,
        "liability_risk_buckets_payload",
        lambda duckdb_path, report_date: {
            "result_meta": {"result_kind": "liability_analytics.risk_buckets"},
            "report_date": report_date or "",
        },
    )
    sqlite_path = tmp_path / "liability-dev-fallback.db"
    monkeypatch.setenv("MOSS_ENVIRONMENT", "development")
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv("MOSS_GOVERNANCE_SQL_DSN", "")
    monkeypatch.delenv("MOSS_USER_ID", raising=False)
    monkeypatch.delenv("MOSS_USER_ROLE", raising=False)
    monkeypatch.delenv(ROLE_HEADER_TRUST_ENV, raising=False)
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(route_mod.router)
    # dev fallback 额外要求 loopback 客户端（P1 安全收紧）；TestClient 默认
    # client host 是非 IP 的 "testclient"，显式设置为 127.0.0.1 以满足该判定。
    client = TestClient(app, client=("127.0.0.1", 12345))

    response = client.get("/api/risk/buckets")

    assert response.status_code == 200
    assert response.json()["result_meta"]["result_kind"] == "liability_analytics.risk_buckets"


@pytest.mark.excluded_surface_regression
def test_liability_analytics_routes_keep_live_compatibility_surface_analytical(
    tmp_path: Path, monkeypatch
) -> None:
    client = _build_client(tmp_path, monkeypatch)

    for path, params in (
        ("/api/risk/buckets", {"report_date": "2026-01-31"}),
        ("/api/analysis/yield_metrics", {"report_date": "2026-01-31"}),
        ("/api/analysis/yield-by-period", {"year": "2026", "period_type": "monthly"}),
        ("/api/analysis/liabilities/counterparty", {"report_date": "2026-01-31", "top_n": "10"}),
        ("/api/liabilities/monthly", {"year": "2026"}),
        ("/api/liabilities/monthly", {"year": "2026", "detail_level": "summary"}),
        ("/api/liabilities/monthly/detail", {"month": "2026-01"}),
    ):
        response = client.get(path, params=params)
        assert response.status_code == 200, path
        body = response.json()
        assert "result_meta" in body, path
        assert "result" in body, path
        assert body["result_meta"].get("basis") == "analytical", path


@pytest.mark.excluded_surface_regression
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


@pytest.mark.excluded_surface_regression
def test_liability_analytics_monthly_route_still_validates_year_bounds(
    tmp_path: Path, monkeypatch
) -> None:
    client = _build_client(tmp_path, monkeypatch)

    response = client.get("/api/liabilities/monthly", params={"year": "1999"})
    assert response.status_code == 422


@pytest.mark.excluded_surface_regression
def test_liability_monthly_default_stays_full_while_summary_and_detail_are_explicit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client = _build_client(tmp_path, monkeypatch)

    full = client.get("/api/liabilities/monthly", params={"year": "2026"})
    summary = client.get(
        "/api/liabilities/monthly",
        params={"year": "2026", "detail_level": "summary"},
    )
    detail = client.get("/api/liabilities/monthly/detail", params={"month": "2026-01"})

    assert full.status_code == 200
    assert full.json()["result_meta"]["result_kind"] == "liability_analytics.monthly"
    assert summary.status_code == 200
    assert summary.json()["result_meta"]["result_kind"] == "liability_analytics.monthly_summary"
    assert summary.json()["result"]["months"] == []
    assert detail.status_code == 200
    assert detail.json()["result_meta"]["result_kind"] == "liability_analytics.monthly_detail"
    assert detail.json()["result"] == {
        "year": 2026,
        "selected_month": "2026-01",
        "detail": None,
    }


@pytest.mark.excluded_surface_regression
def test_liability_monthly_split_routes_validate_mode_and_month(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client = _build_client(tmp_path, monkeypatch)

    invalid_mode = client.get(
        "/api/liabilities/monthly",
        params={"year": "2026", "detail_level": "compact"},
    )
    invalid_month = client.get(
        "/api/liabilities/monthly/detail",
        params={"month": "2026-13"},
    )

    assert invalid_mode.status_code == 422
    assert invalid_month.status_code == 422


@pytest.mark.excluded_surface_regression
def test_monthly_service_uses_daily_totals_for_comparison_year(monkeypatch) -> None:
    service_mod = load_module(
        "backend.app.services.liability_analytics_service_monthly_comparison_totals",
        "backend/app/services/liability_analytics_service.py",
    )
    captured: dict[str, object] = {}

    class Repo:
        def __init__(self, _duckdb_path: str) -> None:
            pass

        def fetch_zqtz_liability_rows_for_year(self, year: int):
            assert year == 2026
            return [{"report_date": "2026-01-31", "source_version": "sv_z_current"}]

        def fetch_tyw_liability_rows_for_year(self, year: int):
            assert year == 2026
            return [{"report_date": "2026-01-31", "source_version": "sv_t_current"}]

        def fetch_zqtz_liability_daily_totals_for_year(self, year: int):
            assert year == 2025
            return [{"report_date": "2025-01-31", "source_version": "sv_z_compare"}]

        def fetch_tyw_liability_daily_totals_for_year(self, year: int):
            assert year == 2025
            return [{"report_date": "2025-01-31", "source_version": "sv_t_compare"}]

    def fake_compute(year, zqtz_rows, tyw_rows):
        captured.update(year=year, zqtz_rows=zqtz_rows, tyw_rows=tyw_rows)
        return {
            "year": year,
            "months": [],
            "ytd_avg_total_liabilities": 0.0,
            "ytd_avg_liability_cost": None,
        }

    monkeypatch.setattr(service_mod, "LiabilityAnalyticsRepository", Repo)
    monkeypatch.setattr(service_mod, "compute_liabilities_monthly", fake_compute)

    service_mod.liabilities_monthly_payload(duckdb_path="unused.duckdb", year=2026)

    assert captured["year"] == 2026
    assert [row["source_version"] for row in captured["zqtz_rows"]] == [
        "sv_z_compare",
        "sv_z_current",
    ]
    assert [row["source_version"] for row in captured["tyw_rows"]] == [
        "sv_t_compare",
        "sv_t_current",
    ]


@pytest.mark.excluded_surface_regression
def test_monthly_summary_lineage_expands_compacted_daily_versions() -> None:
    service_mod = load_module(
        "backend.app.services.liability_analytics_service_monthly_summary_lineage",
        "backend/app/services/liability_analytics_service.py",
    )

    rows = [
        {"source_version": "sv_b|sv_a", "rule_version": "rv_2|rv_1"},
        {"source_version": "sv_a", "rule_version": "rv_1"},
    ]

    assert service_mod._expand_compacted_lineage(rows) == [
        {"source_version": "sv_a"},
        {"source_version": "sv_b"},
        {"rule_version": "rv_1"},
        {"rule_version": "rv_2"},
    ]


@pytest.mark.excluded_surface_regression
def test_risk_buckets_disclose_missing_maturity_rows_in_quality_metadata(monkeypatch) -> None:
    service_mod = load_module(
        "backend.app.services.liability_analytics_service_missing_maturity",
        "backend/app/services/liability_analytics_service.py",
    )

    class Repo:
        def __init__(self, _duckdb_path: str) -> None:
            pass

        def resolve_latest_report_date(self):
            return "2026-01-31"

        def fetch_zqtz_rows(self, _report_date: str):
            return [{"source_version": "sv_zqtz", "rule_version": "rv_zqtz"}]

        def fetch_tyw_rows(self, _report_date: str):
            return [{"source_version": "sv_tyw", "rule_version": "rv_tyw"}]

    monkeypatch.setattr(service_mod, "LiabilityAnalyticsRepository", Repo)
    monkeypatch.setattr(
        service_mod,
        "compute_liability_risk_buckets",
        lambda *_args: {
            "report_date": "2026-01-31",
            "liabilities_structure": [],
            "liabilities_term_buckets": [],
            "interbank_liabilities_structure": [],
            "interbank_liabilities_term_buckets": [],
            "issued_liabilities_structure": [],
            "issued_liabilities_term_buckets": [],
            "missing_maturity_count": 2,
        },
    )

    envelope = service_mod.liability_risk_buckets_payload(
        duckdb_path="unused.duckdb",
        report_date="2026-01-31",
    )

    assert envelope["result"]["missing_maturity_count"] == 2
    assert envelope["result_meta"]["quality_flag"] == "warning"
    assert envelope["result_meta"]["filters_applied"] == {"missing_maturity_count": 2}


@pytest.mark.excluded_surface_acceptance
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


@pytest.mark.excluded_surface_acceptance
def test_yield_metrics_payload_adds_backend_nim_stress_from_official_nim(
    tmp_path: Path,
    monkeypatch,
) -> None:
    service_mod = load_module(
        "backend.app.services.liability_analytics_service_nim_stress",
        "backend/app/services/liability_analytics_service.py",
    )

    class Repo:
        def __init__(self, _duckdb_path: str) -> None:
            pass

        def resolve_latest_report_date(self):
            return "2026-01-31"

        def fetch_zqtz_yield_rows(self, report_date: str):
            return [{"report_date": report_date, "source_version": "sv_zqtz"}]

        def fetch_tyw_rows(self, report_date: str):
            return [{"report_date": report_date, "source_version": "sv_tyw"}]

        def list_report_dates(self):
            return ["2026-01-31"]

        def fetch_yield_rows_for_dates(self, dates):
            return (
                {d: [{"report_date": d, "source_version": "sv_zqtz"}] for d in dates},
                {d: [{"report_date": d, "source_version": "sv_tyw"}] for d in dates},
            )

    def fake_compute(report_date, _zqtz_rows, _tyw_rows):
        return {
            "report_date": report_date,
            "kpi": {
                "asset_yield": 0.031,
                "liability_cost": 0.018,
                "market_liability_cost": 0.021,
                "nim": 0.010,
            },
        }

    monkeypatch.setattr(service_mod, "LiabilityAnalyticsRepository", Repo)
    monkeypatch.setattr(service_mod, "compute_liability_yield_metrics", fake_compute)

    envelope = service_mod.liability_yield_metrics_payload(
        duckdb_path=str(tmp_path / "liability.duckdb"),
        report_date="2026-01-31",
    )

    stress = envelope["result"]["kpi"]["nim_stress"]
    assert stress["nim_stressed"]["unit"] == "pct"
    assert stress["nim_stressed"]["raw"] == pytest.approx(0.005)
    assert stress["delta_bp"]["unit"] == "bp"
    assert stress["delta_bp"]["raw"] == pytest.approx(-50)


@pytest.mark.excluded_surface_regression
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


@pytest.mark.excluded_surface_regression
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


@pytest.mark.excluded_surface_regression
def test_yield_history_falls_back_when_batch_fetch_fails(monkeypatch, caplog) -> None:
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

    with caplog.at_level(logging.DEBUG, logger=service_mod.logger.name):
        history = service_mod._build_yield_history_series(repo, "2026-01-31", max_points=2)

    assert repo.single_zqtz_calls == ["2026-01-30", "2026-01-31"]
    assert repo.single_tyw_calls == ["2026-01-30", "2026-01-31"]
    assert seen == ["2026-01-30", "2026-01-31"]
    # 逐日回退成功时无缺口，但批量预取失败必须留分级日志（数据缺口 → debug）。
    assert history.skipped_dates == []
    batch_records = [
        record
        for record in caplog.records
        if "liability yield history batch prefetch falls back" in record.getMessage()
    ]
    assert len(batch_records) == 1
    assert batch_records[0].levelno == logging.DEBUG
    assert "RuntimeError" in batch_records[0].getMessage()
    assert "batch unavailable" in batch_records[0].getMessage()


@pytest.mark.excluded_surface_regression
def test_yield_history_skipped_dates_are_logged_and_marked(monkeypatch, caplog) -> None:
    """逐日计算失败不再静默 continue：日志分级可见，且跳过日期透出到序列元数据。"""
    service_mod = load_module(
        "backend.app.services.liability_analytics_service_history_skip_disclosure",
        "backend/app/services/liability_analytics_service.py",
    )

    class Repo:
        def list_report_dates(self):
            return ["2026-01-31", "2026-01-30", "2026-01-29"]

        def fetch_yield_rows_for_dates(self, dates):
            return (
                {d: [{"zqtz": d}] for d in dates},
                {d: [{"tyw": d}] for d in dates},
            )

        def fetch_zqtz_yield_rows(self, report_date: str):
            raise AssertionError("batch prefetch already covered all dates")

        def fetch_tyw_rows(self, report_date: str):
            raise AssertionError("batch prefetch already covered all dates")

    def flaky_compute(report_date, zqtz_rows, tyw_rows):
        if report_date == "2026-01-30":
            raise KeyError("kpi input missing for 2026-01-30")
        return {"kpi": {"asset_yield": 0.01, "liability_cost": 0.02, "market_liability_cost": 0.03, "nim": 0.04}}

    monkeypatch.setattr(service_mod, "compute_liability_yield_metrics", flaky_compute)

    with caplog.at_level(logging.DEBUG, logger=service_mod.logger.name):
        history = service_mod._build_yield_history_series(Repo(), "2026-01-31", max_points=3)

    assert [point["date"] for point in history] == ["2026-01-29", "2026-01-31"]
    assert history.skipped_dates == ["2026-01-30"]
    skip_records = [
        record
        for record in caplog.records
        if "liability yield history skips one date" in record.getMessage()
    ]
    assert len(skip_records) == 1
    # KeyError 属程序缺陷类，必须升 warning 与数据缺口区分。
    assert skip_records[0].levelno == logging.WARNING
    message = skip_records[0].getMessage()
    assert "2026-01-30" in message
    assert "KeyError" in message


@pytest.mark.excluded_surface_regression
def test_yield_metrics_envelope_discloses_history_skips(tmp_path: Path, monkeypatch) -> None:
    """历史序列有跳过日期时，信封 quality_flag 降 warning 且 filters_applied 披露数量。"""
    service_mod = load_module(
        "backend.app.services.liability_analytics_service_history_skip_envelope",
        "backend/app/services/liability_analytics_service.py",
    )

    class Repo:
        def __init__(self, _duckdb_path: str) -> None:
            pass

        def resolve_latest_report_date(self):
            return "2026-01-31"

        def fetch_zqtz_yield_rows(self, report_date: str):
            return [{"report_date": report_date, "source_version": "sv_zqtz"}]

        def fetch_tyw_rows(self, report_date: str):
            return [{"report_date": report_date, "source_version": "sv_tyw"}]

        def list_report_dates(self):
            return ["2026-01-31", "2026-01-30", "2026-01-29"]

        def fetch_yield_rows_for_dates(self, dates):
            return (
                {d: [{"report_date": d, "source_version": "sv_zqtz"}] for d in dates},
                {d: [{"report_date": d, "source_version": "sv_tyw"}] for d in dates},
            )

    def flaky_compute(report_date, _zqtz_rows, _tyw_rows):
        if report_date == "2026-01-30":
            raise RuntimeError("history compute failed for 2026-01-30")
        return {
            "report_date": report_date,
            "kpi": {
                "asset_yield": 0.031,
                "liability_cost": 0.018,
                "market_liability_cost": 0.021,
                "nim": 0.010,
            },
        }

    monkeypatch.setattr(service_mod, "LiabilityAnalyticsRepository", Repo)
    monkeypatch.setattr(service_mod, "compute_liability_yield_metrics", flaky_compute)

    envelope = service_mod.liability_yield_metrics_payload(
        duckdb_path=str(tmp_path / "liability.duckdb"),
        report_date="2026-01-31",
    )

    meta = envelope["result_meta"]
    assert meta["quality_flag"] == "warning"
    assert meta["filters_applied"] == {
        "history_skipped_date_count": 1,
        "history_skipped_dates": ["2026-01-30"],
    }
    history_dates = [point["date"] for point in envelope["result"]["history"]]
    assert history_dates == ["2026-01-29", "2026-01-31"]


@pytest.mark.excluded_surface_regression
def test_yield_metrics_envelope_stays_ok_without_history_skips(tmp_path: Path, monkeypatch) -> None:
    service_mod = load_module(
        "backend.app.services.liability_analytics_service_history_ok_envelope",
        "backend/app/services/liability_analytics_service.py",
    )

    class Repo:
        def __init__(self, _duckdb_path: str) -> None:
            pass

        def resolve_latest_report_date(self):
            return "2026-01-31"

        def fetch_zqtz_yield_rows(self, report_date: str):
            return [{"report_date": report_date, "source_version": "sv_zqtz"}]

        def fetch_tyw_rows(self, report_date: str):
            return [{"report_date": report_date, "source_version": "sv_tyw"}]

        def list_report_dates(self):
            return ["2026-01-31", "2026-01-30"]

        def fetch_yield_rows_for_dates(self, dates):
            return (
                {d: [{"report_date": d, "source_version": "sv_zqtz"}] for d in dates},
                {d: [{"report_date": d, "source_version": "sv_tyw"}] for d in dates},
            )

    def healthy_compute(report_date, _zqtz_rows, _tyw_rows):
        return {
            "report_date": report_date,
            "kpi": {
                "asset_yield": 0.031,
                "liability_cost": 0.018,
                "market_liability_cost": 0.021,
                "nim": 0.010,
            },
        }

    monkeypatch.setattr(service_mod, "LiabilityAnalyticsRepository", Repo)
    monkeypatch.setattr(service_mod, "compute_liability_yield_metrics", healthy_compute)

    envelope = service_mod.liability_yield_metrics_payload(
        duckdb_path=str(tmp_path / "liability.duckdb"),
        report_date="2026-01-31",
    )

    assert envelope["result_meta"]["quality_flag"] == "ok"
    assert envelope["result_meta"]["fallback_mode"] == "none"
    assert envelope["result_meta"]["requested_report_date"] == "2026-01-31"
    assert envelope["result_meta"]["resolved_report_date"] == "2026-01-31"
    assert envelope["result_meta"]["filters_applied"] == {}
    assert [point["date"] for point in envelope["result"]["history"]] == [
        "2026-01-30",
        "2026-01-31",
    ]


@pytest.mark.excluded_surface_regression
def test_yield_metrics_unknown_report_date_stays_200_with_warning_envelope(
    tmp_path: Path, monkeypatch
) -> None:
    client = _build_client(tmp_path, monkeypatch)

    response = client.get("/api/analysis/yield_metrics", params={"report_date": "2020-01-15"})

    assert response.status_code == 200
    body = response.json()
    meta = body["result_meta"]
    assert meta["quality_flag"] == "warning"
    assert meta["fallback_mode"] == "none"
    assert meta["requested_report_date"] == "2020-01-15"
    assert meta["resolved_report_date"] == "2020-01-15"
    assert body["result"]["history"] == []
    kpi = body["result"]["kpi"]
    for field in ("asset_yield", "liability_cost", "market_liability_cost", "nim"):
        value = kpi[field]
        raw = value.get("raw") if isinstance(value, dict) else value
        assert raw is None, field


@pytest.mark.excluded_surface_regression
def test_yield_metrics_catalog_date_keeps_ok_and_no_fallback(tmp_path: Path, monkeypatch) -> None:
    service_mod = load_module(
        "backend.app.services.liability_analytics_service_catalog_ok_envelope",
        "backend/app/services/liability_analytics_service.py",
    )

    class Repo:
        def __init__(self, _duckdb_path: str) -> None:
            pass

        def resolve_latest_report_date(self):
            return "2026-01-31"

        def fetch_zqtz_yield_rows(self, report_date: str):
            return [{"report_date": report_date, "source_version": "sv_zqtz"}]

        def fetch_tyw_rows(self, report_date: str):
            return [{"report_date": report_date, "source_version": "sv_tyw"}]

        def list_report_dates(self):
            return ["2026-01-31", "2026-01-30"]

        def fetch_yield_rows_for_dates(self, dates):
            return (
                {d: [{"report_date": d, "source_version": "sv_zqtz"}] for d in dates},
                {d: [{"report_date": d, "source_version": "sv_tyw"}] for d in dates},
            )

    def healthy_compute(report_date, _zqtz_rows, _tyw_rows):
        return {
            "report_date": report_date,
            "kpi": {
                "asset_yield": 0.031,
                "liability_cost": 0.018,
                "market_liability_cost": 0.021,
                "nim": 0.010,
            },
        }

    monkeypatch.setattr(service_mod, "LiabilityAnalyticsRepository", Repo)
    monkeypatch.setattr(service_mod, "compute_liability_yield_metrics", healthy_compute)

    envelope = service_mod.liability_yield_metrics_payload(
        duckdb_path=str(tmp_path / "liability.duckdb"),
        report_date="2026-01-31",
    )

    meta = envelope["result_meta"]
    assert meta["quality_flag"] == "ok"
    assert meta["fallback_mode"] == "none"
    assert meta["requested_report_date"] == "2026-01-31"
    assert meta["resolved_report_date"] == "2026-01-31"


@pytest.mark.excluded_surface_regression
def test_yield_metrics_empty_request_date_discloses_latest_snapshot_fallback(
    tmp_path: Path, monkeypatch
) -> None:
    service_mod = load_module(
        "backend.app.services.liability_analytics_service_empty_date_fallback",
        "backend/app/services/liability_analytics_service.py",
    )

    class Repo:
        def __init__(self, _duckdb_path: str) -> None:
            pass

        def resolve_latest_report_date(self):
            return "2026-01-31"

        def fetch_zqtz_yield_rows(self, report_date: str):
            return [{"report_date": report_date, "source_version": "sv_zqtz"}]

        def fetch_tyw_rows(self, report_date: str):
            return [{"report_date": report_date, "source_version": "sv_tyw"}]

        def list_report_dates(self):
            return ["2026-01-31"]

        def fetch_yield_rows_for_dates(self, dates):
            return (
                {d: [{"report_date": d, "source_version": "sv_zqtz"}] for d in dates},
                {d: [{"report_date": d, "source_version": "sv_tyw"}] for d in dates},
            )

    def healthy_compute(report_date, _zqtz_rows, _tyw_rows):
        return {
            "report_date": report_date,
            "kpi": {
                "asset_yield": 0.031,
                "liability_cost": 0.018,
                "market_liability_cost": 0.021,
                "nim": 0.010,
            },
        }

    monkeypatch.setattr(service_mod, "LiabilityAnalyticsRepository", Repo)
    monkeypatch.setattr(service_mod, "compute_liability_yield_metrics", healthy_compute)

    envelope = service_mod.liability_yield_metrics_payload(
        duckdb_path=str(tmp_path / "liability.duckdb"),
        report_date=None,
    )

    meta = envelope["result_meta"]
    assert meta["quality_flag"] == "ok"
    assert meta["fallback_mode"] == "latest_snapshot"
    assert meta["requested_report_date"] is None
    assert meta["resolved_report_date"] == "2026-01-31"
    assert envelope["result"]["report_date"] == "2026-01-31"


@pytest.mark.excluded_surface_regression
def test_yield_metrics_date_absent_from_catalog_sets_warning_without_latest_fallback(
    tmp_path: Path, monkeypatch
) -> None:
    service_mod = load_module(
        "backend.app.services.liability_analytics_service_absent_catalog_date",
        "backend/app/services/liability_analytics_service.py",
    )

    class Repo:
        def __init__(self, _duckdb_path: str) -> None:
            pass

        def resolve_latest_report_date(self):
            return "2026-01-31"

        def fetch_zqtz_yield_rows(self, _report_date: str):
            return []

        def fetch_tyw_rows(self, _report_date: str):
            return []

        def list_report_dates(self):
            return ["2026-01-31"]

        def fetch_yield_rows_for_dates(self, _dates):
            return ({}, {})

    monkeypatch.setattr(service_mod, "LiabilityAnalyticsRepository", Repo)

    envelope = service_mod.liability_yield_metrics_payload(
        duckdb_path=str(tmp_path / "liability.duckdb"),
        report_date="2020-01-15",
    )

    meta = envelope["result_meta"]
    assert meta["quality_flag"] == "warning"
    assert meta["fallback_mode"] == "none"
    assert meta["requested_report_date"] == "2020-01-15"
    assert meta["resolved_report_date"] == "2020-01-15"
    assert envelope["result"]["history"] == []
