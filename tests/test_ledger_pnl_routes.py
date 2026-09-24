from __future__ import annotations

import sys
from copy import deepcopy
from functools import lru_cache
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from tests.helpers import load_module


LEDGER_PNL_READ_HEADERS = {
    "X-User-Id": "ledger-pnl-route-user",
    "X-User-Role": "viewer",
}


def _money(yuan: str) -> dict[str, str]:
    return {"yuan": yuan, "yi": "0.00"}


def _read_result_meta(result_kind: str) -> dict[str, Any]:
    return {
        "trace_id": f"tr_{result_kind.replace('.', '_').replace('-', '_')}_test",
        "basis": "ledger",
        "result_kind": result_kind,
        "formal_use_allowed": False,
        "source_version": "sv_current",
        "rule_version": f"rv_{result_kind.replace('.', '_').replace('-', '_')}_v1",
        "cache_version": f"cv_{result_kind.replace('.', '_').replace('-', '_')}_v1",
    }


def _data_envelope() -> dict[str, Any]:
    return {
        "result_meta": _read_result_meta("ledger_pnl.data"),
        "result": {
            "data_status": "ready",
            "report_date": "2026-06-30",
            "source_version": "sv_current",
            "items": [],
            "summary": {
                "total_pnl_cnx": _money("0"),
                "total_pnl_cny": _money("0"),
                "total_pnl": _money("0"),
                "count": 0,
            },
        },
    }


def _summary_envelope() -> dict[str, Any]:
    return {
        "result_meta": _read_result_meta("ledger_pnl.summary"),
        "result": {
            "data_status": "ready",
            "report_date": "2026-06-30",
            "source_version": "sv_current",
            "ledger_total_assets": _money("0"),
            "ledger_total_liabilities": _money("0"),
            "ledger_net_assets": _money("0"),
            "ledger_monthly_pnl_core": _money("0"),
            "ledger_monthly_pnl_all": _money("0"),
            "by_currency": [],
            "by_account": [],
        },
    }


def _analysis_envelope() -> dict[str, Any]:
    return {
        "result_meta": {
            "trace_id": "tr_ledger_pnl_analysis_test",
            "basis": "ledger",
            "result_kind": "ledger_pnl.analysis",
            "formal_use_allowed": False,
            "source_version": "sv_analysis_test",
            "rule_version": "rv_ledger_pnl_analysis_v1",
            "cache_version": "cv_ledger_pnl_analysis_v1",
            "cache_key": "ledger_pnl.analysis:2026-06-30:CNY",
            "requested_report_date": "2026-06-30",
            "resolved_report_date": "2026-06-30",
            "as_of_date": "2026-06-30",
            "date_basis": "ledger_report_date",
            "filters_applied": {
                "report_date": "2026-06-30",
                "currency": "CNY",
                "currency_basis": "CNY",
                "currency_basis_note": "CNX=综本；CNY=人民币账",
            },
            "evidence_rows": 1,
        },
        "result": {
            "report_date": "2026-06-30",
            "source_version": "sv_analysis_test",
            "currency_basis": "CNY",
            "analysis_status": "ready",
            "metric_status": "candidate",
            "basis_availability": {"CNX": "ready", "CNY": "ready"},
            "conclusion": {
                "direction": "positive",
                "other_effect": "neutral",
                "core_pnl": _money("10"),
                "other_5_pnl": _money("0"),
                "all_pnl": _money("10"),
            },
            "pnl_bridge": {
                "components": [
                    {
                        "metric_key": "core_pnl",
                        "metric_name": "核心损益",
                        "amount": _money("10"),
                    },
                    {
                        "metric_key": "other_5_pnl",
                        "metric_name": "其他 5* 科目损益",
                        "amount": _money("0"),
                    },
                ],
                "total": _money("10"),
                "residual": _money("0"),
            },
            "basis_comparison": [],
            "contributors": {
                "positive_total": _money("10"),
                "negative_total": _money("0"),
                "net_total": _money("10"),
                "top_positive": [],
                "top_negative": [],
            },
            "period_comparison": {
                "status": "no_previous_period",
                "previous_report_date": None,
                "previous_source_version": None,
                "rows": [],
            },
            "calculation_basis": {
                "core_pnl_prefixes": ["514", "516", "517"],
                "all_pnl_prefixes": ["5"],
                "other_5_pnl_formula": "all_pnl - core_pnl",
                "other_5_pnl_boundary": "arithmetic residual",
                "basis_difference_formula": "CNX - CNY",
                "basis_boundary": "overlapping accounting bases; not FX PnL",
                "basis_availability_boundary": "PnL analyzability only",
                "previous_period_rule": "latest earlier report date",
                "metric_boundary": "candidate only",
            },
        },
    }


def _account_detail_envelope() -> dict[str, Any]:
    return {
        "result_meta": {
            "trace_id": "tr_ledger_pnl_account_detail_test",
            "basis": "ledger",
            "result_kind": "ledger_pnl.account_detail",
            "formal_use_allowed": False,
            "source_version": "sv_current",
            "rule_version": "rv_ledger_pnl_account_detail_v1",
            "cache_version": "cv_ledger_pnl_account_detail_v1",
            "cache_key": (
                "ledger_pnl.account_detail:2026-06-30:CNY:55000000001"
            ),
            "fallback_mode": "none",
            "requested_report_date": "2026-06-30",
            "resolved_report_date": "2026-06-30",
            "as_of_date": "2026-06-30",
            "date_basis": "ledger_report_date",
            "filters_applied": {
                "report_date": "2026-06-30",
                "account_code": "55000000001",
                "currency": "CNY",
                "currency_basis": "CNY",
                "currency_basis_note": "CNX=综本；CNY=人民币账",
            },
            "evidence_rows": 1,
        },
        "result": {
            "report_date": "2026-06-30",
            "source_version": "sv_current",
            "currency_basis": "CNY",
            "analysis_status": "ready",
            "metric_status": "candidate",
            "account": {
                "account_code": "55000000001",
                "account_name": "当期所得税",
            },
            "period_comparison": {
                "status": "available",
                "previous_report_date": "2026-05-31",
                "previous_source_version": "sv_previous",
                "current_monthly_pnl": _money("-8"),
                "previous_monthly_pnl": _money("-6"),
                "change": _money("-2"),
                "current_evidence_rows": 1,
                "previous_evidence_rows": 1,
            },
            "basis_comparison": {
                "current": {
                    "report_date": "2026-06-30",
                    "source_version": "sv_current",
                    "cnx": _money("-10"),
                    "cny": _money("-8"),
                    "cnx_minus_cny": _money("-2"),
                    "availability": {"CNX": "ready", "CNY": "ready"},
                    "evidence_rows": {"CNX": 1, "CNY": 1},
                },
                "previous": {
                    "report_date": "2026-05-31",
                    "source_version": "sv_previous",
                    "cnx": _money("-7"),
                    "cny": _money("-6"),
                    "cnx_minus_cny": _money("-1"),
                    "availability": {"CNX": "ready", "CNY": "ready"},
                    "evidence_rows": {"CNX": 1, "CNY": 1},
                },
            },
            "canonical_evidence_rows": [
                {
                    "period": "current",
                    "report_date": "2026-06-30",
                    "source_version": "sv_current",
                    "account_code": "55000000001",
                    "account_name": "当期所得税",
                    "currency": "CNX",
                    "beginning_balance": _money("0"),
                    "ending_balance": _money("0"),
                    "monthly_pnl": _money("-10"),
                    "days_in_period": 30,
                },
                {
                    "period": "current",
                    "report_date": "2026-06-30",
                    "source_version": "sv_current",
                    "account_code": "55000000001",
                    "account_name": "当期所得税",
                    "currency": "CNY",
                    "beginning_balance": _money("0"),
                    "ending_balance": _money("0"),
                    "monthly_pnl": _money("-8"),
                    "days_in_period": 30,
                },
                {
                    "period": "previous",
                    "report_date": "2026-05-31",
                    "source_version": "sv_previous",
                    "account_code": "55000000001",
                    "account_name": "当期所得税",
                    "currency": "CNX",
                    "beginning_balance": _money("0"),
                    "ending_balance": _money("0"),
                    "monthly_pnl": _money("-7"),
                    "days_in_period": 31,
                },
                {
                    "period": "previous",
                    "report_date": "2026-05-31",
                    "source_version": "sv_previous",
                    "account_code": "55000000001",
                    "account_name": "当期所得税",
                    "currency": "CNY",
                    "beginning_balance": _money("0"),
                    "ending_balance": _money("0"),
                    "monthly_pnl": _money("-6"),
                    "days_in_period": 31,
                },
            ],
            "calculation_basis": {
                "account_match": "exact",
                "amount_field": "monthly_pnl",
                "change_formula": "current_monthly_pnl - previous_monthly_pnl",
                "basis_difference_formula": "CNX - CNY",
                "basis_boundary": "CNX - CNY is not FX PnL",
                "previous_period_rule": "latest available report date strictly earlier",
                "evidence_boundary": "canonical facts, not raw workbook rows",
                "metric_boundary": "candidate analytical evidence only; non-formal",
            },
        },
    }


def _account_detail_no_data_envelope() -> dict[str, Any]:
    envelope = deepcopy(_account_detail_envelope())
    envelope["result_meta"]["evidence_rows"] = 0
    envelope["result_meta"]["quality_flag"] = "warning"
    result = envelope["result"]
    result["analysis_status"] = "no_data"
    result["account"]["account_name"] = None
    result["period_comparison"] = {
        "status": "current_account_no_data",
        "previous_report_date": None,
        "previous_source_version": None,
        "current_monthly_pnl": None,
        "previous_monthly_pnl": None,
        "change": None,
        "current_evidence_rows": 0,
        "previous_evidence_rows": 0,
    }
    result["basis_comparison"] = {
        "current": {
            "report_date": "2026-06-30",
            "source_version": "sv_current",
            "cnx": None,
            "cny": None,
            "cnx_minus_cny": None,
            "availability": {"CNX": "no_data", "CNY": "no_data"},
            "evidence_rows": {"CNX": 0, "CNY": 0},
        },
        "previous": None,
    }
    result["canonical_evidence_rows"] = []
    return envelope


def _clear_active_settings_cache() -> None:
    settings_module = sys.modules.get("backend.app.governance.settings")
    if settings_module is None:
        return
    cache_clear = getattr(settings_module.get_settings, "cache_clear", None)
    if cache_clear is not None:
        cache_clear()


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    _clear_active_settings_cache()
    try:
        yield
    finally:
        _clear_active_settings_cache()


class FakeLedgerPnlService:
    class LedgerPnlRequestError(ValueError):
        pass

    class CandidateFinancialIndicatorRequestError(ValueError):
        pass

    class CandidateFinancialIndicatorConflictError(ValueError):
        pass

    def __init__(
        self,
        *,
        value_error: str | None = None,
        internal_value_error: bool = False,
    ) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.value_error = value_error
        self.internal_value_error = internal_value_error

    def _raise_value_error(self) -> None:
        if not self.value_error:
            return
        error_type = ValueError if self.internal_value_error else self.LedgerPnlRequestError
        raise error_type(self.value_error)

    def ledger_pnl_data_envelope(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("data", kwargs))
        self._raise_value_error()
        return _data_envelope()

    def ledger_pnl_summary_envelope(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("summary", kwargs))
        self._raise_value_error()
        return _summary_envelope()

    def ledger_pnl_analysis_envelope(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("analysis", kwargs))
        self._raise_value_error()
        return _analysis_envelope()

    def ledger_pnl_account_detail_envelope(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("account_detail", kwargs))
        self._raise_value_error()
        return _account_detail_envelope()

    def ledger_pnl_formal_financial_indicator_contract_envelope(
        self,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.calls.append(("formal_financial_indicators", kwargs))
        return {
            "result_meta": {
                "result_kind": "ledger_pnl.formal_financial_indicator_source_contract"
            },
            "result": {"report_month": kwargs["report_month"]},
        }

    def ledger_pnl_formal_indicator_rule_checks_envelope(
        self,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.calls.append(("formal_indicator_rule_checks", kwargs))
        return {
            "result_meta": {
                "result_kind": "ledger_pnl.formal_financial_indicator_rule_checks"
            },
            "result": {"report_month": kwargs["report_month"]},
        }

    def qdb_gl_monthly_analysis_dates_envelope(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("monthly_analysis_dates", kwargs))
        return {
            "result_meta": _read_result_meta("qdb-gl-monthly-analysis.dates"),
            "result": {"report_months": ["202606"]},
        }

    def qdb_gl_monthly_analysis_workbook_envelope(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("monthly_analysis_workbook", kwargs))
        self._raise_value_error()
        return {
            "result_meta": {"result_kind": "qdb-gl-monthly-analysis.workbook"},
            "result": {"report_month": kwargs["report_month"], "sheets": []},
        }

    def candidate_financial_indicator_envelope(
        self,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.calls.append(("candidate_financial_indicators", kwargs))
        from backend.app.services.candidate_financial_indicator_service import (
            candidate_financial_indicator_envelope,
        )

        return candidate_financial_indicator_envelope(
            source_dir="__route_test_missing_candidate_sources__",
            report_month=kwargs["report_month"],
            include_lineage=kwargs["include_lineage"],
            metric_id=kwargs["metric_id"],
        )

    def revalidate_candidate_financial_indicators(
        self,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.calls.append(("revalidate_candidate_financial_indicators", kwargs))
        from backend.app.services.candidate_financial_indicator_service import (
            revalidate_candidate_financial_indicators,
        )

        return revalidate_candidate_financial_indicators(
            source_dir="__route_test_missing_candidate_sources__",
            report_month=kwargs["report_month"],
            include_lineage=kwargs["include_lineage"],
            metric_id=kwargs["metric_id"],
            request=kwargs["request"],
        )


def _client_with_read_scope(
    tmp_path,
    monkeypatch,
    service: FakeLedgerPnlService,
) -> TestClient:
    route_module = load_module(
        "backend.app.api.routes.ledger_pnl",
        "backend/app/api/routes/ledger_pnl.py",
    )
    monkeypatch.setattr(route_module, "_svc", lambda: service)
    monkeypatch.setattr(route_module, "_candidate_svc", lambda: service)
    monkeypatch.setattr(route_module, "_monthly_analysis_svc", lambda: service, raising=False)

    sqlite_path = tmp_path / "ledger-pnl-route-read-scope.db"
    dsn = f"sqlite:///{sqlite_path.as_posix()}"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", dsn)
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    _clear_active_settings_cache()
    repo_module = load_module(
        "backend.app.repositories.user_scope_repo",
        "backend/app/repositories/user_scope_repo.py",
    )
    repo_module.UserScopeRepository(dsn).grant_scope(
        user_id="*",
        role=None,
        resource="ledger_pnl",
        action="read",
    )

    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app, raise_server_exceptions=False)
    client.headers.update(LEDGER_PNL_READ_HEADERS)
    return client


def _client_without_permission_check(
    monkeypatch,
    service: FakeLedgerPnlService,
) -> TestClient:
    route_module = load_module(
        "backend.app.api.routes.ledger_pnl",
        "backend/app/api/routes/ledger_pnl.py",
    )
    monkeypatch.setattr(route_module, "_svc", lambda: service)
    monkeypatch.setattr(route_module, "_candidate_svc", lambda: service)
    monkeypatch.setattr(route_module, "_monthly_analysis_svc", lambda: service, raising=False)
    monkeypatch.setattr(
        route_module,
        "_ensure_ledger_pnl_read_allowed",
        lambda _auth: None,
    )
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app, raise_server_exceptions=False)
    client.headers.update(LEDGER_PNL_READ_HEADERS)
    return client


def _client_without_read_scope(
    tmp_path,
    monkeypatch,
    service: FakeLedgerPnlService,
) -> TestClient:
    route_module = load_module(
        "backend.app.api.routes.ledger_pnl",
        "backend/app/api/routes/ledger_pnl.py",
    )
    monkeypatch.setattr(route_module, "_svc", lambda: service)
    monkeypatch.setattr(route_module, "_candidate_svc", lambda: service)
    monkeypatch.setattr(route_module, "_monthly_analysis_svc", lambda: service, raising=False)

    sqlite_path = tmp_path / "ledger-pnl-route-no-read-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    _clear_active_settings_cache()

    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app, raise_server_exceptions=False)
    client.headers.update(LEDGER_PNL_READ_HEADERS)
    return client


def test_settings_cache_teardown_clears_active_settings_function(
    tmp_path,
    monkeypatch,
):
    fixture_generator = _reset_settings_cache.__wrapped__()
    next(fixture_generator)
    route_module = load_module(
        "backend.app.api.routes.ledger_pnl",
        "backend/app/api/routes/ledger_pnl.py",
    )
    sqlite_path = tmp_path / "active-settings-cache.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")

    settings_module = sys.modules["backend.app.governance.settings"]
    original_get_settings = settings_module.get_settings
    active_get_settings = lru_cache(maxsize=1)(lambda: original_get_settings())
    monkeypatch.setattr(settings_module, "get_settings", active_get_settings)
    monkeypatch.setattr(route_module, "get_settings", active_get_settings)
    monkeypatch.setattr(
        route_module,
        "_ensure_ledger_pnl_read_allowed",
        lambda _auth: None,
    )
    monkeypatch.setattr(route_module, "_svc", lambda: FakeLedgerPnlService())
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)
    client.headers.update(LEDGER_PNL_READ_HEADERS)

    response = client.get(
        "/api/ledger-pnl/data",
        params={"date": "2026-03-31", "currency": "CNY"},
    )

    assert response.status_code == 200
    assert active_get_settings.cache_info().currsize > 0
    assert sys.modules["backend.app.governance.settings"] is settings_module
    assert settings_module.get_settings is active_get_settings

    with pytest.raises(StopIteration):
        next(fixture_generator)

    assert active_get_settings.cache_info().currsize == 0


def test_formal_indicator_rule_checks_route_uses_ledger_read_scope_and_service(
    tmp_path,
    monkeypatch,
):
    service = FakeLedgerPnlService()
    client = _client_with_read_scope(tmp_path, monkeypatch, service)

    response = client.get(
        "/api/ledger-pnl/formal-indicator-rule-checks",
        params={"report_month": "202603"},
    )

    assert response.status_code == 200
    assert response.json()["result"]["report_month"] == "202603"
    assert service.calls == [
        ("formal_indicator_rule_checks", {"report_month": "202603"})
    ]


def test_candidate_financial_indicators_route_uses_read_scope_and_fixed_source_dir(
    tmp_path,
    monkeypatch,
):
    service = FakeLedgerPnlService()
    client = _client_with_read_scope(tmp_path, monkeypatch, service)

    response = client.get(
        "/api/ledger-pnl/candidate-financial-indicators",
        params={
            "report_month": "202606",
            "include_lineage": "true",
            "metric_id": "income.interest.net",
        },
    )

    assert response.status_code == 200
    assert response.json()["result"]["calculation_status"] == "no_data"
    assert service.calls == [
        (
            "candidate_financial_indicators",
            {
                "source_dir": str(
                    sys.modules["backend.app.governance.settings"]
                    .get_settings()
                    .product_category_source_dir
                ),
                "report_month": "202606",
                "include_lineage": True,
                "metric_id": "income.interest.net",
            },
        )
    ]


def test_candidate_financial_indicators_route_declares_strict_response_model(
    monkeypatch,
):
    service = FakeLedgerPnlService()
    route_module = load_module(
        "backend.app.api.routes.ledger_pnl",
        "backend/app/api/routes/ledger_pnl.py",
    )
    monkeypatch.setattr(route_module, "_candidate_svc", lambda: service)

    candidate_route = next(
        route
        for route in route_module.router.routes
        if getattr(route, "path", None)
        == "/api/ledger-pnl/candidate-financial-indicators"
    )

    assert candidate_route.response_model.__name__ == (
        "CandidateFinancialIndicatorEnvelope"
    )


def test_candidate_financial_indicators_route_rejects_missing_read_scope(
    tmp_path,
    monkeypatch,
):
    service = FakeLedgerPnlService()
    client = _client_without_read_scope(tmp_path, monkeypatch, service)

    response = client.get(
        "/api/ledger-pnl/candidate-financial-indicators",
        params={"report_month": "202606"},
    )

    assert response.status_code == 403
    assert service.calls == []


@pytest.mark.parametrize(
    "params",
    [
        {"report_month": "202613"},
        {"report_month": "2026-06"},
        {"report_month": "202606", "metric_id": "Income.Invalid"},
        {"report_month": "202606", "metric_id": "income..invalid"},
        {"report_month": "202606", "metric_id": "income.invalid::wrong"},
    ],
)
def test_candidate_financial_indicators_route_rejects_invalid_query_values(
    monkeypatch,
    params,
):
    service = FakeLedgerPnlService()
    client = _client_without_permission_check(monkeypatch, service)

    response = client.get(
        "/api/ledger-pnl/candidate-financial-indicators",
        params=params,
    )

    assert response.status_code == 422
    assert service.calls == []


def test_candidate_financial_indicators_route_translates_only_typed_request_error(
    monkeypatch,
):
    service = FakeLedgerPnlService()

    def fail_request(**_kwargs: Any) -> dict[str, Any]:
        raise service.CandidateFinancialIndicatorRequestError(
            "Unknown candidate financial metric_id: 'income.unknown'."
        )

    monkeypatch.setattr(
        service,
        "candidate_financial_indicator_envelope",
        fail_request,
    )
    client = _client_without_permission_check(monkeypatch, service)

    response = client.get(
        "/api/ledger-pnl/candidate-financial-indicators",
        params={"report_month": "202606", "metric_id": "income.unknown"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Unknown candidate financial metric_id: 'income.unknown'."
    }


def test_candidate_financial_indicators_route_does_not_expose_internal_error(
    monkeypatch,
):
    service = FakeLedgerPnlService()

    def fail_internal(**_kwargs: Any) -> dict[str, Any]:
        raise ValueError("secret candidate workbook cell failure")

    monkeypatch.setattr(
        service,
        "candidate_financial_indicator_envelope",
        fail_internal,
    )
    client = _client_without_permission_check(monkeypatch, service)

    response = client.get(
        "/api/ledger-pnl/candidate-financial-indicators",
        params={"report_month": "202606"},
    )

    assert response.status_code == 500
    assert "secret candidate workbook cell failure" not in response.text


def test_candidate_revalidation_route_uses_read_scope_and_strict_receipt(
    tmp_path,
    monkeypatch,
):
    from backend.app.services.candidate_financial_indicator_service import (
        candidate_financial_indicator_envelope,
    )

    service = FakeLedgerPnlService()
    client = _client_with_read_scope(tmp_path, monkeypatch, service)
    base = candidate_financial_indicator_envelope(
        source_dir="__route_test_missing_candidate_sources__",
        report_month="202606",
        include_lineage=False,
        metric_id=None,
    )
    response = client.post(
        "/api/ledger-pnl/candidate-financial-indicators/revalidate",
        params={"report_month": "202606"},
        json={
            "base_candidate_idempotency_key": base["result"]["idempotency_key"],
            "base_evidence_pack_key": base["result"]["promotion_readiness"]["evidence_pack"]["evidence_pack_key"],
            "manual_overrides": {},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["contract_version"] == "candidate-financial-indicator-revalidation-v1"
    assert body["persisted"] is False
    assert body["formal_use_allowed"] is False
    assert body["result"]["result"]["formal_use_allowed"] is False
    assert service.calls[0][0] == "revalidate_candidate_financial_indicators"


def test_candidate_revalidation_route_reuses_read_authorization(
    tmp_path,
    monkeypatch,
):
    service = FakeLedgerPnlService()
    client = _client_without_read_scope(tmp_path, monkeypatch, service)

    response = client.post(
        "/api/ledger-pnl/candidate-financial-indicators/revalidate",
        params={"report_month": "202606"},
        json={
            "base_candidate_idempotency_key": "1" * 64,
            "base_evidence_pack_key": "2" * 64,
            "manual_overrides": {},
        },
    )

    assert response.status_code == 403
    assert service.calls == []


def test_candidate_revalidation_route_maps_stale_keys_to_conflict(
    monkeypatch,
):
    service = FakeLedgerPnlService()

    def conflict(**_kwargs: Any) -> dict[str, Any]:
        raise service.CandidateFinancialIndicatorConflictError("stale candidate evidence")

    monkeypatch.setattr(service, "revalidate_candidate_financial_indicators", conflict)
    client = _client_without_permission_check(monkeypatch, service)
    response = client.post(
        "/api/ledger-pnl/candidate-financial-indicators/revalidate",
        params={"report_month": "202606"},
        json={
            "base_candidate_idempotency_key": "1" * 64,
            "base_evidence_pack_key": "2" * 64,
            "manual_overrides": {},
        },
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "stale candidate evidence"}


def test_ledger_pnl_analysis_route_uses_ledger_read_scope_and_service(
    tmp_path,
    monkeypatch,
):
    service = FakeLedgerPnlService()
    client = _client_with_read_scope(tmp_path, monkeypatch, service)

    response = client.get(
        "/api/ledger-pnl/analysis",
        params={"date": "2026-06-30", "currency": "CNY"},
    )

    assert response.status_code == 200
    assert response.json()["result_meta"]["result_kind"] == "ledger_pnl.analysis"
    assert service.calls == [
        (
            "analysis",
            {
                "source_dir": str(
                    sys.modules["backend.app.governance.settings"]
                    .get_settings()
                    .product_category_source_dir
                ),
                "report_date": "2026-06-30",
                "currency": "CNY",
            },
        )
    ]


def test_ledger_pnl_monthly_analysis_routes_use_ledger_read_scope(
    tmp_path,
    monkeypatch,
):
    service = FakeLedgerPnlService()
    client = _client_with_read_scope(tmp_path, monkeypatch, service)

    dates_response = client.get("/api/ledger-pnl/monthly-analysis/dates")
    workbook_response = client.get(
        "/api/ledger-pnl/monthly-analysis/workbook",
        params={"report_month": "202606"},
    )

    assert dates_response.status_code == 200
    assert workbook_response.status_code == 200
    settings = sys.modules["backend.app.governance.settings"].get_settings()
    assert service.calls == [
        (
            "monthly_analysis_dates",
            {"source_dir": settings.product_category_source_dir},
        ),
        (
            "monthly_analysis_workbook",
            {
                "source_dir": settings.product_category_source_dir,
                "governance_dir": settings.governance_path,
                "report_month": "202606",
            },
        ),
    ]


def test_ledger_pnl_monthly_analysis_routes_reject_missing_ledger_scope(
    tmp_path,
    monkeypatch,
):
    service = FakeLedgerPnlService()
    client = _client_without_read_scope(tmp_path, monkeypatch, service)

    assert client.get("/api/ledger-pnl/monthly-analysis/dates").status_code == 403
    assert client.get(
        "/api/ledger-pnl/monthly-analysis/workbook",
        params={"report_month": "202606"},
    ).status_code == 403
    assert service.calls == []


@pytest.mark.parametrize("report_month", ["202613", "2026-06"])
def test_ledger_pnl_monthly_analysis_workbook_rejects_invalid_month(
    monkeypatch,
    report_month,
):
    service = FakeLedgerPnlService()
    client = _client_without_permission_check(monkeypatch, service)

    response = client.get(
        "/api/ledger-pnl/monthly-analysis/workbook",
        params={"report_month": report_month},
    )

    assert response.status_code == 422
    assert service.calls == []


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [(ValueError("month pair missing"), 404), (RuntimeError("build unavailable"), 503)],
)
def test_ledger_pnl_monthly_analysis_workbook_maps_service_errors(
    monkeypatch,
    error,
    expected_status,
):
    service = FakeLedgerPnlService()

    def fail_workbook(**_kwargs: Any) -> dict[str, Any]:
        raise error

    monkeypatch.setattr(service, "qdb_gl_monthly_analysis_workbook_envelope", fail_workbook)
    client = _client_without_permission_check(monkeypatch, service)

    response = client.get(
        "/api/ledger-pnl/monthly-analysis/workbook",
        params={"report_month": "202606"},
    )

    assert response.status_code == expected_status


def test_ledger_pnl_analysis_route_declares_strict_response_model(monkeypatch):
    service = FakeLedgerPnlService()
    route_module = load_module(
        "backend.app.api.routes.ledger_pnl",
        "backend/app/api/routes/ledger_pnl.py",
    )
    monkeypatch.setattr(route_module, "_svc", lambda: service)

    analysis_route = next(
        route
        for route in route_module.router.routes
        if getattr(route, "path", None) == "/api/ledger-pnl/analysis"
    )

    assert analysis_route.response_model.__name__ == "LedgerPnlAnalysisEnvelope"


def test_ledger_pnl_analysis_route_rejects_missing_read_scope(
    tmp_path,
    monkeypatch,
):
    service = FakeLedgerPnlService()
    client = _client_without_read_scope(tmp_path, monkeypatch, service)

    response = client.get(
        "/api/ledger-pnl/analysis",
        params={"date": "2026-06-30", "currency": "CNY"},
    )

    assert response.status_code == 403
    assert service.calls == []


def test_ledger_pnl_account_detail_route_uses_read_scope_and_service(
    tmp_path,
    monkeypatch,
):
    service = FakeLedgerPnlService()
    client = _client_with_read_scope(tmp_path, monkeypatch, service)

    response = client.get(
        "/api/ledger-pnl/account-detail",
        params={
            "date": "2026-06-30",
            "account_code": "55000000001",
            "currency": "CNY",
        },
    )

    assert response.status_code == 200
    assert response.json()["result_meta"]["result_kind"] == (
        "ledger_pnl.account_detail"
    )
    assert service.calls == [
        (
            "account_detail",
            {
                "source_dir": str(
                    sys.modules["backend.app.governance.settings"]
                    .get_settings()
                    .product_category_source_dir
                ),
                "report_date": "2026-06-30",
                "account_code": "55000000001",
                "currency": "CNY",
            },
        )
    ]


def test_ledger_pnl_account_detail_route_returns_200_for_valid_no_data(
    monkeypatch,
):
    service = FakeLedgerPnlService()

    def no_data_account_detail(**kwargs: Any) -> dict[str, Any]:
        service.calls.append(("account_detail", kwargs))
        return _account_detail_no_data_envelope()

    monkeypatch.setattr(
        service,
        "ledger_pnl_account_detail_envelope",
        no_data_account_detail,
    )
    client = _client_without_permission_check(monkeypatch, service)

    response = client.get(
        "/api/ledger-pnl/account-detail",
        params={
            "date": "2026-06-30",
            "account_code": "55000000001",
            "currency": "CNY",
        },
    )

    assert response.status_code == 200
    assert response.json()["result"]["analysis_status"] == "no_data"
    assert response.json()["result"]["period_comparison"]["current_monthly_pnl"] is None


def test_ledger_pnl_account_detail_route_declares_strict_response_model(monkeypatch):
    service = FakeLedgerPnlService()
    route_module = load_module(
        "backend.app.api.routes.ledger_pnl",
        "backend/app/api/routes/ledger_pnl.py",
    )
    monkeypatch.setattr(route_module, "_svc", lambda: service)

    detail_route = next(
        route
        for route in route_module.router.routes
        if getattr(route, "path", None) == "/api/ledger-pnl/account-detail"
    )

    assert detail_route.response_model.__name__ == "LedgerPnlAccountDetailEnvelope"


def test_ledger_pnl_account_detail_route_rejects_missing_read_scope(
    tmp_path,
    monkeypatch,
):
    service = FakeLedgerPnlService()
    client = _client_without_read_scope(tmp_path, monkeypatch, service)

    response = client.get(
        "/api/ledger-pnl/account-detail",
        params={"date": "2026-06-30", "account_code": "55000000001"},
    )

    assert response.status_code == 403
    assert service.calls == []


@pytest.mark.parametrize(
    "params",
    [
        {"date": "2026-02-30", "account_code": "55000000001"},
        {"date": "2026-06-30", "account_code": "550ABC"},
        {"date": "2026-06-30", "account_code": "4"},
        {"date": "2026-06-30", "account_code": "5" + "1" * 32},
        {
            "date": "2026-06-30",
            "account_code": "55000000001",
            "currency": "USD",
        },
    ],
)
def test_ledger_pnl_account_detail_route_rejects_invalid_query_values(
    monkeypatch,
    params,
):
    service = FakeLedgerPnlService()
    client = _client_without_permission_check(monkeypatch, service)

    response = client.get("/api/ledger-pnl/account-detail", params=params)

    assert response.status_code == 422
    assert service.calls == []


def test_ledger_pnl_account_detail_route_translates_caller_error_to_422(monkeypatch):
    service = FakeLedgerPnlService(value_error="Requested report date is not month-end.")
    client = _client_without_permission_check(monkeypatch, service)

    response = client.get(
        "/api/ledger-pnl/account-detail",
        params={"date": "2026-06-30", "account_code": "55000000001"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Requested report date is not month-end."}


def test_ledger_pnl_account_detail_route_does_not_expose_internal_value_error(monkeypatch):
    service = FakeLedgerPnlService(
        value_error="internal workbook cell failure",
        internal_value_error=True,
    )
    client = _client_without_permission_check(monkeypatch, service)

    response = client.get(
        "/api/ledger-pnl/account-detail",
        params={"date": "2026-06-30", "account_code": "55000000001"},
    )

    assert response.status_code == 500
    assert "internal workbook cell failure" not in response.text


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/api/ledger-pnl/data", {"date": "2026-02-30"}),
        ("/api/ledger-pnl/data", {"date": "20260331"}),
        ("/api/ledger-pnl/data", {"date": "2026-03-31", "currency": "USD"}),
        ("/api/ledger-pnl/data", {"date": "2026-03-31", "currency": "ALL"}),
        ("/api/ledger-pnl/summary", {"date": "2026-02-30"}),
        ("/api/ledger-pnl/summary", {"date": "20260331"}),
        ("/api/ledger-pnl/summary", {"date": "2026-03-31", "currency": "cnx"}),
        ("/api/ledger-pnl/summary", {"date": "2026-03-31", "currency": "ALL"}),
        ("/api/ledger-pnl/analysis", {"date": "2026-02-30"}),
        ("/api/ledger-pnl/analysis", {"date": "20260331"}),
        ("/api/ledger-pnl/analysis", {"date": "2026-03-31", "currency": "USD"}),
        ("/api/ledger-pnl/analysis", {"date": "2026-03-31", "currency": "ALL"}),
        (
            "/api/ledger-pnl/formal-financial-indicators",
            {"report_month": "202613"},
        ),
        (
            "/api/ledger-pnl/formal-financial-indicators",
            {"report_month": "2026-03"},
        ),
        (
            "/api/ledger-pnl/formal-indicator-rule-checks",
            {"report_month": "202600"},
        ),
        (
            "/api/ledger-pnl/formal-indicator-rule-checks",
            {"report_month": "2026-03"},
        ),
    ],
)
def test_ledger_pnl_routes_reject_invalid_query_values(
    monkeypatch,
    path,
    params,
):
    service = FakeLedgerPnlService()
    client = _client_without_permission_check(monkeypatch, service)

    response = client.get(path, params=params)

    assert response.status_code == 422
    assert service.calls == []


@pytest.mark.parametrize(
    ("path", "method_name"),
    [
        ("/api/ledger-pnl/data", "data"),
        ("/api/ledger-pnl/summary", "summary"),
        ("/api/ledger-pnl/analysis", "analysis"),
    ],
)
def test_ledger_pnl_data_routes_translate_service_value_error_to_422(
    monkeypatch,
    path,
    method_name,
):
    message = "Requested report date is not the source month-end."
    service = FakeLedgerPnlService(value_error=message)
    client = _client_without_permission_check(monkeypatch, service)

    response = client.get(
        path,
        params={"date": "2026-03-31", "currency": "CNY"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": message}
    assert service.calls[0][0] == method_name


@pytest.mark.parametrize(
    "path",
    [
        "/api/ledger-pnl/data",
        "/api/ledger-pnl/summary",
        "/api/ledger-pnl/analysis",
    ],
)
def test_ledger_pnl_data_routes_do_not_translate_internal_value_error(
    monkeypatch,
    path,
):
    internal_message = "workbook parser exposed an internal cell failure"
    service = FakeLedgerPnlService(
        value_error=internal_message,
        internal_value_error=True,
    )
    client = _client_without_permission_check(monkeypatch, service)

    response = client.get(
        path,
        params={"date": "2026-03-31", "currency": "CNY"},
    )

    assert response.status_code == 500
    assert internal_message not in response.text


@pytest.mark.parametrize(
    ("path", "method_name"),
    [
        ("/api/ledger-pnl/data", "data"),
        ("/api/ledger-pnl/summary", "summary"),
        ("/api/ledger-pnl/analysis", "analysis"),
    ],
)
def test_ledger_pnl_data_routes_pass_iso_date_strings_to_service(
    monkeypatch,
    path,
    method_name,
):
    service = FakeLedgerPnlService()
    client = _client_without_permission_check(monkeypatch, service)

    response = client.get(
        path,
        params={"date": "2026-03-31", "currency": "CNY"},
    )

    assert response.status_code == 200
    call_name, kwargs = service.calls[0]
    assert call_name == method_name
    assert kwargs["report_date"] == "2026-03-31"
    assert kwargs["currency"] == "CNY"
