"""`/api/pnl-attribution/campisi/four-effects?detail=summary` 契约测试。

契约：summary 是完整 envelope 之后的投影（by_bond 置空），其余字段逐字段一致；
默认（不带 detail）路径与改动前完全一致；投影不污染运行时缓存。
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from backend.app.services import campisi_attribution_service as campisi_svc
from tests.helpers import load_module
from tests.test_campisi_attribution_service import (
    _bond_row,
    _clear_four_effects_cache,
    _flat_treasury,
    _install_full_service_fakes,
)

_PNL_ATTRIBUTION_READ_HEADERS = {
    "X-User-Id": "campisi-summary-read-user",
    "X-User-Role": "viewer",
}
# 两次独立调用会重建 envelope，trace_id/generated_at 每次生成；投影本身对 meta 原样保留
# （见 test_summary_projection_keeps_meta_and_other_fields_untouched 的严格断言）。
_VOLATILE_META_FIELDS = {"trace_id", "generated_at"}


def _install_four_effects_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_four_effects_cache()
    start_rows = [
        _bond_row(
            code="SUMMARY_BOND",
            market_value=Decimal("1000"),
            face_value=Decimal("1000"),
            accrued_interest=Decimal("0"),
            coupon_rate=Decimal("0.0300"),
            ytm=Decimal("0.0320"),
            rating="AAA",
            asset_class="credit",
        )
    ]
    end_rows = [{**start_rows[0], "market_value": Decimal("990")}]
    _install_full_service_fakes(
        monkeypatch,
        dates=["2026-01-31", "2026-01-01"],
        rows_by_date={
            "2026-01-01": start_rows,
            "2026-01-31": end_rows,
        },
        curves={
            ("2026-01-01", "treasury"): _flat_treasury(Decimal("2.00")),
            ("2026-01-31", "treasury"): _flat_treasury(Decimal("2.10")),
            ("2026-01-01", "credit_spread_aaa"): {"3Y": 30.0},
            ("2026-01-31", "credit_spread_aaa"): {"3Y": 30.0},
        },
    )


def test_summary_envelope_matches_full_field_by_field_except_empty_by_bond(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_four_effects_fixture(monkeypatch)

    full = campisi_svc.campisi_four_effects_envelope(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )
    summary = campisi_svc.campisi_four_effects_summary_envelope(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )

    assert full["result"]["by_bond"], "fixture must produce non-empty by_bond for full detail"
    assert summary["result"]["by_bond"] == []
    # 不新增标记字段（镜像 get_return_decomposition_summary 惯例）。
    assert set(summary["result"].keys()) == set(full["result"].keys())
    assert set(summary.keys()) == set(full.keys())
    assert {k: v for k, v in summary["result"].items() if k != "by_bond"} == {
        k: v for k, v in full["result"].items() if k != "by_bond"
    }
    assert {
        k: v for k, v in summary["result_meta"].items() if k not in _VOLATILE_META_FIELDS
    } == {k: v for k, v in full["result_meta"].items() if k not in _VOLATILE_META_FIELDS}


def test_summary_projection_keeps_meta_and_other_fields_untouched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_four_effects_fixture(monkeypatch)

    full = campisi_svc.campisi_four_effects_envelope(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )
    projected = campisi_svc._project_campisi_four_effects_summary(full)

    # 同一 envelope 的投影：meta（含 trace_id）与除 by_bond 外的 result 字段严格相等。
    assert projected["result_meta"] == full["result_meta"]
    assert projected["result"]["by_bond"] == []
    assert {k: v for k, v in projected["result"].items() if k != "by_bond"} == {
        k: v for k, v in full["result"].items() if k != "by_bond"
    }
    # 投影不得改写传入的完整 envelope。
    assert full["result"]["by_bond"]


def test_summary_call_does_not_pollute_cached_full_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_four_effects_fixture(monkeypatch)

    summary = campisi_svc.campisi_four_effects_summary_envelope(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )
    full_after_summary = campisi_svc.campisi_four_effects_envelope(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )

    assert summary["result"]["by_bond"] == []
    assert full_after_summary["result"]["by_bond"], (
        "summary projection must not empty by_bond for subsequent full-detail calls"
    )


def _stub_four_effects_envelope(by_bond: list[dict[str, object]]) -> dict[str, object]:
    """路由挂了严格 response_model 之后，桩必须是最小**合法** payload。

    这两个用例验证的是 detail 分发行为，不是 payload 内容；桩只需过校验。
    """
    return {
        "result_meta": {
            "result_kind": "campisi.four_effects",
            "trace_id": "stub-trace",
            "source_version": "sv_stub",
            "rule_version": "rv_stub",
            "cache_version": "cv_stub",
        },
        "result": {
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "report_date": "2026-01-31",
            "num_days": 30,
            "totals": {
                "market_value_start": 0,
                "income_return": 0,
                "treasury_effect": 0,
                "spread_effect": 0,
                "selection_effect": 0,
                "total_return": 0,
            },
            "by_asset_class": [],
            "by_bond": by_bond,
            "warnings": [],
        },
    }


_STUB_BOND_ROW: dict[str, object] = {
    "bond_code": "SUMMARY_BOND",
    "asset_class": "credit AAA",
    "maturity_bucket": "1-3Y",
    "mod_duration": 2.5,
    "market_value_start": 1000.0,
    "income_return": 1.0,
    "treasury_effect": 0.0,
    "spread_effect": 0.0,
    "selection_effect": -1.0,
    "total_return": 0.0,
    "has_accrued_interest": True,
    "treasury_effect_available": True,
    "spread_effect_available": True,
}


def _campisi_route_client_with_read_scope(tmp_path, monkeypatch) -> tuple[TestClient, object]:
    route_module = load_module(
        "backend.app.api.routes.campisi_attribution",
        "backend/app/api/routes/campisi_attribution.py",
    )
    sqlite_path = tmp_path / "campisi-summary-read-scope.db"
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
        resource="pnl_attribution",
        action="read",
    )
    # 路由现在走进程内 TTL 响应缓存，逐用例清空以避免跨用例命中。
    route_module.market_home_response_cache.invalidate()
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)
    client.headers.update(_PNL_ATTRIBUTION_READ_HEADERS)
    return client, route_module


def test_four_effects_detail_summary_dispatches_to_summary_envelope(tmp_path, monkeypatch) -> None:
    client, route_module = _campisi_route_client_with_read_scope(tmp_path, monkeypatch)
    called: dict[str, object] = {}

    class _StubService:
        def campisi_four_effects_summary_envelope(self, **kwargs):
            called["kwargs"] = kwargs
            return _stub_four_effects_envelope(by_bond=[])

        def campisi_four_effects_envelope(self, **_kwargs):
            raise AssertionError("full detail path should not be used for detail=summary")

    monkeypatch.setattr(route_module, "_svc", lambda: _StubService())

    response = client.get(
        "/api/pnl-attribution/campisi/four-effects",
        params={"end_date": "2026-01-31", "lookback_days": 30, "detail": "summary"},
    )

    assert response.status_code == 200, response.text
    assert called["kwargs"] == {
        "start_date": None,
        "end_date": "2026-01-31",
        "lookback_days": 30,
    }
    assert response.json()["result"]["by_bond"] == []
    get_settings.cache_clear()


def test_four_effects_default_detail_uses_full_envelope_with_unchanged_kwargs(
    tmp_path, monkeypatch
) -> None:
    client, route_module = _campisi_route_client_with_read_scope(tmp_path, monkeypatch)
    called: dict[str, object] = {}

    class _StubService:
        def campisi_four_effects_envelope(self, **kwargs):
            called["kwargs"] = kwargs
            return _stub_four_effects_envelope(by_bond=[dict(_STUB_BOND_ROW)])

        def campisi_four_effects_summary_envelope(self, **_kwargs):
            raise AssertionError("summary path should not be used without detail=summary")

    monkeypatch.setattr(route_module, "_svc", lambda: _StubService())

    # 默认（不带 detail）：与改动前完全一致地调用 campisi_four_effects_envelope。
    response = client.get(
        "/api/pnl-attribution/campisi/four-effects",
        params={"start_date": "2026-01-01", "end_date": "2026-01-31"},
    )

    assert response.status_code == 200, response.text
    assert called["kwargs"] == {
        "start_date": "2026-01-01",
        "end_date": "2026-01-31",
        "lookback_days": 30,
    }
    assert response.json()["result"]["by_bond"] == [_STUB_BOND_ROW]
    get_settings.cache_clear()
