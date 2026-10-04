"""W4.1 tests for /ui/home/snapshot endpoint and home_snapshot_envelope service."""
from __future__ import annotations

import importlib
from types import SimpleNamespace
from unittest.mock import patch

import pytest

EXPECTED_HOME_SNAPSHOT_CALIBERS = ("balance_sheet", "pnl")


@pytest.fixture(autouse=True)
def _isolate_home_snapshot_cache(monkeypatch: pytest.MonkeyPatch):
    """每个用例都从空缓存开始，避免上一条用例的 envelope 污染本条 mock。"""
    es = _executive_service()
    original_fast_path = es._fetch_product_category_home_headline_values
    # The production builder probes the product-category fast path before
    # dispatching to the builders that these tests replace. Keep this module
    # fully local while allowing each test to control the fallback builders.
    monkeypatch.setattr(es, "_fetch_product_category_home_headline_values", lambda *_a, **_k: {})
    es.invalidate_home_snapshot_cache()
    yield original_fast_path
    es.invalidate_home_snapshot_cache()


def _executive_service():
    """Always use the canonical `sys.modules` entry (golden tests may reload this module)."""
    return importlib.import_module("backend.app.services.executive_service")


def _date_context(
    *,
    balance: list[str],
    pnl: list[str],
    liability: list[str] | None = None,
    bond: list[str] | None = None,
) -> dict[str, list[str]]:
    return {
        "balance": balance,
        "liability": balance if liability is None else liability,
        "bond": balance if bond is None else bond,
        "pnl": pnl,
    }


def _home_snapshot_with_dates(
    monkeypatch: pytest.MonkeyPatch,
    *,
    context: dict[str, list[str]],
    report_date: str | None = None,
    allow_partial: bool = False,
) -> dict[str, object]:
    es = _executive_service()

    def product_headlines(
        selected_report_date: str,
    ) -> tuple[object, object, int, int]:
        ytd = es._product_category_ytd_headline_from_values(
            selected_report_date,
            {
                "grand_total": 120_000_000.0,
                "intermediate_business_income": 20_000_000.0,
            },
        )
        monthly = es._product_category_monthly_headline_from_values(
            selected_report_date,
            {"grand_total": 10_000_000.0},
        )
        assert ytd is not None
        assert monthly is not None
        return ytd, monthly, 0, 0

    monkeypatch.setattr(es, "_list_domain_date_context", lambda: context)
    monkeypatch.setattr(
        es,
        "executive_overview",
        lambda **_kwargs: {"result_meta": {}, "result": {"title": "overview", "metrics": []}},
    )
    monkeypatch.setattr(
        es,
        "executive_pnl_attribution",
        lambda report_date=None: {
            "result_meta": {},
            "result": {"title": "attribution", "total": "0", "segments": []},
        },
    )
    monkeypatch.setattr(es, "_build_product_category_headlines", product_headlines)
    return es.home_snapshot_envelope(report_date=report_date, allow_partial=allow_partial)


@pytest.mark.parametrize("view,error_kind", [("ytd", "runtime"), ("monthly", "runtime"), ("monthly", "missing")])
def test_home_snapshot_api_does_not_expose_headline_failure_payload(monkeypatch, tmp_path, caplog, view, error_kind):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.app.api.routes import executive as route
    from backend.app.services.product_category_pnl_service import ProductCategoryReadModelNotFoundError

    es = _executive_service()
    report_date = "2026-04-08"
    marker = "synthetic-private-headline-source"
    monkeypatch.setattr(es, "get_settings", lambda: SimpleNamespace(
        duckdb_path=tmp_path / "unused.duckdb", governance_path=tmp_path / "gov", ftp_rate_pct=1.0,
    ))
    monkeypatch.setattr(es, "_list_domain_date_context", lambda: _date_context(
        balance=[report_date], pnl=[] if error_kind == "missing" else [report_date],
    ))
    monkeypatch.setattr(es, "executive_overview", lambda **_kwargs: {
        "result_meta": {"quality_flag": "ok", "vendor_status": "ok"},
        "result": {"title": "Overview", "metrics": [{
            "id": "aum", "label": "Assets", "value": es._fmt_yi_amount(123_000_000).model_dump(mode="json"),
            "delta": "N/A", "tone": "neutral", "detail": "synthetic same-date asset",
        }]},
    })
    monkeypatch.setattr(es, "executive_pnl_attribution", lambda **_kwargs: {
        "result_meta": {"quality_flag": "ok", "vendor_status": "ok"},
        "result": es._pnl_attribution_unavailable_payload().model_dump(mode="json"),
    })

    def fail(*_args, **_kwargs):
        raise (ProductCategoryReadModelNotFoundError if error_kind == "missing" else RuntimeError)(marker)

    target = "resolve_product_category_ytd_payload_for_home_snapshot" if view == "ytd" else "product_category_pnl_envelope"
    monkeypatch.setattr(es, target, fail)
    other = "monthly" if view == "ytd" else "ytd"
    monkeypatch.setattr(es, f"_build_product_category_{other}_headline", lambda _date: None)
    # Authorization is separately covered; this route probe isolates response serialization.
    monkeypatch.setattr(route, "_ensure_executive_read_allowed", lambda _auth: None)
    monkeypatch.setattr(route, "home_snapshot_envelope", es.home_snapshot_envelope)
    app = FastAPI()
    app.dependency_overrides[route.get_auth_context] = lambda: SimpleNamespace(user_id="synthetic-user")
    app.include_router(route.router)
    response = TestClient(app).get("/ui/home/snapshot", params={"report_date": report_date, "allow_partial": error_kind == "missing"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["quality_flag"] == "warning"
    assert payload["result"][f"product_category_{view}"] is None
    filters = payload["result_meta"]["filters_applied"]
    assert f"product_category_{view}" in filters["degraded_components"]
    assert ("ProductCategoryReadModelNotFoundError" if error_kind == "missing" else "RuntimeError") in filters["degraded_reasons"][f"product_category_{view}"]
    assert payload["result"]["overview"]["metrics"][0]["value"]["raw"] == 123_000_000
    if error_kind == "missing":
        assert payload["result"]["report_date"] == report_date
        assert payload["result"]["domains_missing"] == ["pnl"]
        assert payload["result"]["domains_effective_date"] == {"balance_sheet": report_date}
    assert marker not in response.text
    assert marker not in caplog.text


def test_home_headline_fast_path_does_not_log_private_failure(
    monkeypatch, caplog, _isolate_home_snapshot_cache,
):
    es = _executive_service()
    marker = "synthetic-private-fast-path-source"

    def fail(*_args, **_kwargs):
        raise RuntimeError(marker)

    monkeypatch.setattr(es.ProductCategoryPnlRepository, "fetch_home_headline_values", fail)
    values = _isolate_home_snapshot_cache("unused-path", "2026-04-08", ["ytd", "monthly"])
    assert values.degraded is True
    assert values == {}
    assert "RuntimeError" in values.degraded_reason
    assert marker not in values.degraded_reason
    assert marker not in caplog.text


@pytest.mark.parametrize("allow_partial,effective,missing", [
    (False, {"balance_sheet": "2026-04-08"}, ["pnl"]),
    (True, {}, ["balance_sheet", "pnl"]),
    (True, {"balance_sheet": "2026-04-07"}, ["pnl"]),
    (True, {"balance_sheet": "2026-04-08"}, ["balance_sheet", "pnl"]),
])
def test_home_partial_still_rejects_unavailable_or_wrong_date_domains(allow_partial, effective, missing):
    from fastapi import HTTPException
    from backend.app.api.routes.executive import _require_landed_executive_surface

    with pytest.raises(HTTPException) as caught:
        _require_landed_executive_surface({
            "result_meta": {"vendor_status": "vendor_unavailable"},
            "result": {"mode": "partial", "report_date": "2026-04-08",
                       "domains_effective_date": effective, "domains_missing": missing},
        }, route_name="home_snapshot", allow_partial=allow_partial)
    assert caught.value.status_code == 503


@pytest.mark.parametrize("stage", ["fast", "ytd", "monthly"])
@pytest.mark.parametrize("error_kind", ["type", "attribute", "read_selection"])
def test_home_headline_propagates_programming_and_read_selection_errors(
    monkeypatch, tmp_path, _isolate_home_snapshot_cache, stage, error_kind,
):
    from backend.app.repositories.duckdb_read_context import DuckDBReadSelectionError

    es = _executive_service()
    error_type = {"type": TypeError, "attribute": AttributeError, "read_selection": DuckDBReadSelectionError}[error_kind]
    error = error_type("synthetic failure must propagate")

    def fail(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(es, "get_settings", lambda: SimpleNamespace(
        duckdb_path=tmp_path / "unused.duckdb", governance_path=tmp_path / "gov", ftp_rate_pct=1.0,
    ))
    if stage == "fast":
        monkeypatch.setattr(es.ProductCategoryPnlRepository, "fetch_home_headline_values", fail)

        def invoke():
            return _isolate_home_snapshot_cache("unused-path", "2026-04-08", ["ytd"])
    else:
        target = "resolve_product_category_ytd_payload_for_home_snapshot" if stage == "ytd" else "product_category_pnl_envelope"
        monkeypatch.setattr(es, target, fail)

        def invoke():
            return getattr(es, f"_build_product_category_{stage}_headline")("2026-04-08")
    with pytest.raises(error_type) as caught:
        invoke()
    assert caught.value is error


class TestHomeSnapshotDateSelection:
    def test_strict_intersection_empty_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        env = _home_snapshot_with_dates(
            monkeypatch,
            context=_date_context(balance=[], pnl=[]),
        )

        assert env["result_meta"]["vendor_status"] == "vendor_unavailable"
        assert env["result"]["report_date"] == ""
        assert set(env["result"]["domains_missing"]) == set(EXPECTED_HOME_SNAPSHOT_CALIBERS)
        assert env["result"]["domains_effective_date"] == {}

    def test_strict_intersection_nonempty_picks_max(self, monkeypatch: pytest.MonkeyPatch) -> None:
        env = _home_snapshot_with_dates(
            monkeypatch,
            context=_date_context(
                balance=["2026-04-08", "2026-04-07"],
                pnl=["2026-04-08", "2026-04-07", "2026-04-06"],
            ),
        )

        result = env["result"]
        assert result["report_date"] == "2026-04-08"
        assert result["domains_missing"] == []
        assert all(
            result["domains_effective_date"][domain] == "2026-04-08"
            for domain in EXPECTED_HOME_SNAPSHOT_CALIBERS
        )

    def test_strict_requested_in_intersection(self, monkeypatch: pytest.MonkeyPatch) -> None:
        env = _home_snapshot_with_dates(
            monkeypatch,
            context=_date_context(
                balance=["2026-04-08", "2026-04-07"],
                pnl=["2026-04-08", "2026-04-07"],
            ),
            report_date="2026-04-07",
        )

        result = env["result"]
        assert result["report_date"] == "2026-04-07"
        assert result["domains_missing"] == []

    def test_strict_requested_not_in_intersection_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        env = _home_snapshot_with_dates(
            monkeypatch,
            context=_date_context(balance=["2026-04-08"], pnl=["2026-04-07"]),
            report_date="2026-04-08",
        )

        assert env["result_meta"]["vendor_status"] == "vendor_unavailable"
        assert env["result"]["report_date"] == ""
        assert set(env["result"]["domains_missing"]) == set(EXPECTED_HOME_SNAPSHOT_CALIBERS)

    def test_partial_requested_labels_missing_domains(self, monkeypatch: pytest.MonkeyPatch) -> None:
        env = _home_snapshot_with_dates(
            monkeypatch,
            context=_date_context(
                balance=["2026-04-08", "2026-04-07"],
                pnl=["2026-04-07"],
            ),
            report_date="2026-04-08",
            allow_partial=True,
        )

        result = env["result"]
        assert result["report_date"] == "2026-04-08"
        assert "pnl" in result["domains_missing"]
        assert result["domains_effective_date"]["balance_sheet"] == "2026-04-08"
        assert "pnl" not in result["domains_effective_date"]
        assert env["result_meta"]["vendor_status"] == "vendor_unavailable"

    def test_missing_requested_pnl_discloses_gap_and_latest_strict_date(self, monkeypatch) -> None:
        env = _home_snapshot_with_dates(
            monkeypatch,
            context=_date_context(
                balance=["2026-08-31", "2026-08-28"],
                pnl=["2026-08-31", "2026-07-31"],
            ),
            report_date="2026-08-28",
        )

        assert env["result_meta"]["vendor_status"] == "vendor_unavailable"
        assert env["result"]["report_date"] == ""
        filters = env["result_meta"]["filters_applied"]
        assert filters["domains_missing"] == ["pnl"]
        assert filters["latest_available_report_date"] == "2026-08-31"
        assert filters["effective_report_dates"] == {}

    def test_missing_date_does_not_invent_recovery_date_without_intersection(self, monkeypatch) -> None:
        env = _home_snapshot_with_dates(
            monkeypatch,
            context=_date_context(balance=["2026-08-28"], pnl=["2026-08-31"]),
            report_date="2026-08-28",
        )

        assert env["result_meta"]["filters_applied"]["latest_available_report_date"] is None
        assert env["result"]["report_date"] == ""

    def test_partial_no_requested_uses_union_max(self, monkeypatch: pytest.MonkeyPatch) -> None:
        env = _home_snapshot_with_dates(
            monkeypatch,
            context=_date_context(balance=["2026-04-08"], pnl=["2026-04-07"]),
            allow_partial=True,
        )

        result = env["result"]
        assert result["report_date"] == "2026-04-08"
        assert {"pnl"} <= set(result["domains_missing"])
        assert env["result_meta"]["vendor_status"] == "vendor_unavailable"


class TestHomeSnapshotEnvelope:
    def test_returns_envelope_shape(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Shape coverage uses an explicit empty local date context rather than
        # opening the protected developer database.
        env = _home_snapshot_with_dates(
            monkeypatch,
            context=_date_context(balance=[], pnl=[]),
        )
        assert "result_meta" in env
        assert "result" in env
        # result payload is HomeSnapshotPayload-compatible dict
        result = env["result"]
        assert "report_date" in result
        assert "mode" in result
        assert "source_surface" in result
        assert result["source_surface"] == "executive_analytical"
        assert "overview" in result
        assert "attribution" in result
        assert "domains_missing" in result
        assert "domains_effective_date" in result
        assert "product_category_ytd" in result
        assert env["result_meta"]["result_kind"] == "home.snapshot"

    def test_strict_empty_returns_explicit_miss_envelope(self) -> None:
        es = _executive_service()
        with patch.object(es, "_list_domain_date_context") as mock_dates:
            mock_dates.return_value = {
                "balance": [],
                "pnl": [],
                "liability": [],
                "bond": [],
            }
            env = es.home_snapshot_envelope(report_date=None, allow_partial=False)
            assert env["result_meta"]["quality_flag"] == "error"
            assert env["result_meta"]["vendor_status"] == "vendor_unavailable"
            assert env["result"]["report_date"] == ""
            assert set(env["result"]["domains_missing"]) == set(EXPECTED_HOME_SNAPSHOT_CALIBERS)

    def test_strict_intersection_returns_unified_date(self) -> None:
        es = _executive_service()
        ytd = es._product_category_ytd_headline_from_values(
            "2026-04-08",
            {
                "grand_total": 120_000_000.0,
                "intermediate_business_income": 20_000_000.0,
            },
        )
        monthly = es._product_category_monthly_headline_from_values(
            "2026-04-08",
            {"grand_total": 10_000_000.0},
        )
        assert ytd is not None
        assert monthly is not None
        with patch.object(es, "_list_domain_date_context") as mock_dates:
            mock_dates.return_value = {
                "balance": ["2026-04-08"],
                "pnl": ["2026-04-08"],
                "liability": ["2026-04-08"],
                "bond": ["2026-04-08"],
            }
            with patch.object(es, "executive_overview") as mock_ov:
                with patch.object(es, "executive_pnl_attribution") as mock_attr:
                    with patch.object(
                        es,
                        "_build_product_category_headlines",
                        return_value=(ytd, monthly, 0, 0),
                    ):
                        mock_ov.return_value = {
                            "result_meta": {},
                            "result": {"title": "经营总览", "metrics": []},
                        }
                        mock_attr.return_value = {
                            "result_meta": {},
                            "result": {
                                "title": "经营贡献拆解",
                                "total": "+0.00 亿",
                                "segments": [],
                            },
                        }
                        env = es.home_snapshot_envelope(
                            report_date=None, allow_partial=False
                        )
            assert env["result"]["report_date"] == "2026-04-08"
            assert env["result"]["mode"] == "strict"
            assert env["result"]["domains_missing"] == []
            assert env["result_meta"]["quality_flag"] == "ok"

    def test_partial_mode_labels_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        es = _executive_service()
        with patch.object(es, "_list_domain_date_context") as mock_dates:
            mock_dates.return_value = {
                "balance": ["2026-04-08"],
                "pnl": [],  # missing entirely
                "liability": ["2026-04-08"],
                "bond": ["2026-04-08"],
            }
            with patch.object(es, "executive_overview") as mock_ov:
                with patch.object(es, "executive_pnl_attribution") as mock_attr:
                    with patch.object(es, "_build_product_category_headlines", return_value=(None, None, 0, 0)):
                        mock_ov.return_value = {
                            "result_meta": {},
                            "result": {"title": "经营总览", "metrics": []},
                        }
                        mock_attr.return_value = {
                            "result_meta": {},
                            "result": {
                                "title": "经营贡献拆解",
                                "total": "+0.00 亿",
                                "segments": [],
                            },
                        }
                        env = es.home_snapshot_envelope(
                            report_date="2026-04-08", allow_partial=True
                        )
            assert env["result"]["mode"] == "partial"
            assert "pnl" in env["result"]["domains_missing"]
            assert env["result_meta"]["quality_flag"] == "warning"

    def test_component_degradation_is_promoted_to_snapshot_warning(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        es = _executive_service()
        report_date = "2026-04-08"
        ytd = es._product_category_ytd_headline_from_values(
            report_date,
            {
                "grand_total": 120_000_000.0,
                "intermediate_business_income": 20_000_000.0,
            },
        )
        monthly = es._product_category_monthly_headline_from_values(
            report_date,
            {"grand_total": 10_000_000.0},
        )
        assert ytd is not None
        assert monthly is not None

        monkeypatch.setattr(
            es,
            "_list_domain_date_context",
            lambda: {
                "balance": [report_date],
                "pnl": [report_date],
                "liability": [report_date],
                "bond": [report_date],
            },
        )
        monkeypatch.setattr(
            es,
            "executive_overview",
            lambda **_kwargs: {
                "result_meta": {
                    "quality_flag": "ok",
                    "vendor_status": "ok",
                },
                "result": {"title": "经营总览", "metrics": []},
            },
        )
        monkeypatch.setattr(
            es,
            "executive_pnl_attribution",
            lambda report_date=None: {
                "result_meta": {
                    "quality_flag": "warning",
                    "vendor_status": "vendor_unavailable",
                },
                "result": es._pnl_attribution_unavailable_payload().model_dump(
                    mode="json"
                ),
            },
        )
        monkeypatch.setattr(
            es,
            "_build_product_category_headlines",
            lambda _report_date: (ytd, monthly, 0, 0),
        )

        env = es.home_snapshot_envelope(
            report_date=report_date,
            allow_partial=False,
        )

        assert env["result"]["domains_missing"] == []
        assert env["result_meta"]["quality_flag"] == "warning"
        assert env["result_meta"]["vendor_status"] == "vendor_unavailable"
        assert env["result_meta"]["filters_applied"]["degraded_components"] == [
            "attribution"
        ]

    def test_aum_lineage_warning_in_overview_is_promoted_to_snapshot_warning(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        es = _executive_service()
        report_date = "2026-04-08"
        ytd = es._product_category_ytd_headline_from_values(
            report_date,
            {
                "grand_total": 120_000_000.0,
                "intermediate_business_income": 20_000_000.0,
            },
        )
        monthly = es._product_category_monthly_headline_from_values(
            report_date,
            {"grand_total": 10_000_000.0},
        )
        assert ytd is not None
        assert monthly is not None

        monkeypatch.setattr(
            es,
            "_list_domain_date_context",
            lambda: {
                "balance": [report_date],
                "pnl": [report_date],
                "liability": [report_date],
                "bond": [report_date],
            },
        )
        monkeypatch.setattr(
            es,
            "executive_overview",
            lambda **_kwargs: {
                "result_meta": {
                    "quality_flag": "warning",
                    "vendor_status": "vendor_unavailable",
                },
                "result": {"title": "经营总览", "metrics": []},
            },
        )
        monkeypatch.setattr(
            es,
            "executive_pnl_attribution",
            lambda report_date=None: {
                "result_meta": {
                    "quality_flag": "ok",
                    "vendor_status": "ok",
                },
                "result": es._pnl_attribution_unavailable_payload().model_dump(
                    mode="json"
                ),
            },
        )
        monkeypatch.setattr(
            es,
            "_build_product_category_headlines",
            lambda _report_date: (ytd, monthly, 0, 0),
        )

        env = es.home_snapshot_envelope(
            report_date=report_date,
            allow_partial=False,
        )

        assert env["result"]["domains_missing"] == []
        assert env["result_meta"]["quality_flag"] == "warning"
        assert env["result_meta"]["vendor_status"] == "vendor_unavailable"
        assert env["result_meta"]["filters_applied"]["degraded_components"] == [
            "overview"
        ]

    def test_missing_product_headlines_are_promoted_to_snapshot_warning(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        es = _executive_service()
        report_date = "2026-04-08"
        monkeypatch.setattr(
            es,
            "_list_domain_date_context",
            lambda: {
                "balance": [report_date],
                "pnl": [report_date],
                "liability": [report_date],
                "bond": [report_date],
            },
        )
        monkeypatch.setattr(
            es,
            "executive_overview",
            lambda **_kwargs: {
                "result_meta": {
                    "quality_flag": "ok",
                    "vendor_status": "ok",
                },
                "result": {"title": "经营总览", "metrics": []},
            },
        )
        monkeypatch.setattr(
            es,
            "executive_pnl_attribution",
            lambda report_date=None: {
                "result_meta": {
                    "quality_flag": "ok",
                    "vendor_status": "ok",
                },
                "result": es._pnl_attribution_unavailable_payload().model_dump(
                    mode="json"
                ),
            },
        )
        monkeypatch.setattr(
            es,
            "_build_product_category_headlines",
            lambda _report_date: (None, None, 0, 0),
        )

        env = es.home_snapshot_envelope(
            report_date=report_date,
            allow_partial=False,
        )

        assert env["result"]["domains_missing"] == []
        assert env["result_meta"]["quality_flag"] == "warning"
        assert env["result_meta"]["vendor_status"] == "ok"
        assert env["result_meta"]["filters_applied"]["degraded_components"] == [
            "product_category_ytd",
            "product_category_monthly",
        ]

    def test_snapshot_reuses_domain_date_lists_for_overview(self, monkeypatch: pytest.MonkeyPatch) -> None:
        es = _executive_service()
        calls: list[tuple[str, str | None]] = []
        dates = ["2026-04-30", "2026-04-29"]

        class BalanceRepo:
            def __init__(self, *_a, **_k):
                pass

            def list_report_dates(self, currency_basis: str = "CNY"):
                raise AssertionError("snapshot should reuse precomputed balance dates")

            def fetch_zqtz_asset_market_value(self, *, report_date: str, currency_basis: str = "CNY"):
                return {"report_date": report_date, "total_market_value_amount": 100.0}

        class PnlRepo:
            def __init__(self, *_a, **_k):
                pass

            def list_formal_fi_report_dates(self):
                raise AssertionError("snapshot should reuse precomputed pnl dates")

            def sum_formal_total_pnl_through_report_date(self, report_date: str):
                return {"2026-04-30": 10.0, "2026-04-29": 9.0}[report_date]

        class LiabilityRepo:
            def __init__(self, *_a, **_k):
                pass

            def list_report_dates(self):
                raise AssertionError("snapshot should reuse precomputed liability dates")

            def fetch_zqtz_rows(self, report_date: str):
                return [{"source_version": "sv-z", "rule_version": "rv-z"}]

            def fetch_tyw_rows(self, report_date: str):
                return [{"source_version": "sv-t", "rule_version": "rv-t"}]

        class BondRepo:
            def __init__(self, *_a, **_k):
                pass

            def list_report_dates(self):
                raise AssertionError("snapshot should reuse precomputed bond dates")

            def fetch_risk_overview_snapshot(self, *, report_date: str):
                return {"report_date": report_date, "portfolio_dv01": 10.0}

        monkeypatch.setattr(es, "FormalZqtzBalanceMetricsRepository", BalanceRepo)
        monkeypatch.setattr(es, "PnlRepository", PnlRepo)
        monkeypatch.setattr(es, "LiabilityAnalyticsRepository", LiabilityRepo)
        monkeypatch.setattr(es, "BondAnalyticsRepository", BondRepo)
        monkeypatch.setattr(
            es,
            "compute_liability_yield_metrics",
            lambda report_date, _z, _t: {"report_date": report_date, "kpi": {"nim": 0.001}},
        )
        monkeypatch.setattr(es, "resolve_kpi_authority_gate", lambda **_k: {"status": "blocked"})
        monkeypatch.setattr(es, "resolve_completed_formal_build_lineage", lambda **_k: None)
        monkeypatch.setattr(es, "load_latest_bond_analytics_lineage", lambda **_k: None)
        monkeypatch.setattr(
            es,
            "executive_pnl_attribution",
            lambda report_date=None: {
                "result_meta": {},
                "result": es._pnl_attribution_unavailable_payload().model_dump(mode="json"),
            },
        )
        monkeypatch.setattr(es, "_build_product_category_ytd_headline", lambda _rd: None)
        monkeypatch.setattr(es, "_build_product_category_monthly_headline", lambda _rd: None)
        monkeypatch.setattr(
            es,
            "_list_domain_date_context",
            lambda: {
                "balance": dates,
                "pnl": dates,
                "liability": dates,
                "bond": dates,
            },
        )

        env = es.home_snapshot_envelope(report_date=None, allow_partial=False)

        assert env["result"]["report_date"] == "2026-04-30"
        assert calls == []

    def test_snapshot_uses_short_overview_history_window(self, monkeypatch: pytest.MonkeyPatch) -> None:
        es = _executive_service()
        dates = {
            "balance": ["2026-04-08"],
            "pnl": ["2026-04-08"],
            "liability": ["2026-04-08"],
            "bond": ["2026-04-08"],
        }
        captured: dict[str, object] = {}

        def fake_overview(**kwargs):
            captured.update(kwargs)
            return {"result_meta": {}, "result": {"title": "overview", "metrics": []}}

        monkeypatch.setattr(es, "_list_domain_date_context", lambda: dates)
        monkeypatch.setattr(es, "executive_overview", fake_overview)
        monkeypatch.setattr(
            es,
            "executive_pnl_attribution",
            lambda report_date=None: {
                "result_meta": {},
                "result": es._pnl_attribution_unavailable_payload().model_dump(mode="json"),
            },
        )
        monkeypatch.setattr(es, "_build_product_category_ytd_headline", lambda _rd: None)
        monkeypatch.setattr(es, "_build_product_category_monthly_headline", lambda _rd: None)

        env = es.home_snapshot_envelope(report_date=None, allow_partial=False)

        assert env["result"]["report_date"] == "2026-04-08"
        assert captured["report_date"] == "2026-04-08"
        assert captured["date_context"] == dates
        assert captured["history_points"] == 3
        assert es._HOME_SNAPSHOT_OVERVIEW_HISTORY_POINTS == 3

    def test_build_product_category_ytd_headline_matches_envelope_grand_total(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Parity: headline builder must echo product_category_pnl_envelope ytd grand_total / intermediate."""
        from backend.app.schemas.product_category_pnl import (
            ProductCategoryPnlPayload,
            ProductCategoryPnlRow,
        )

        es = _executive_service()

        def row_dict(cid: str, name: str, side: str, bni: str) -> dict[str, object]:
            return {
                "category_id": cid,
                "category_name": name,
                "side": side,
                "level": 0,
                "view": "ytd",
                "report_date": "2026-04-08",
                "baseline_ftp_rate_pct": "1.60",
                "cnx_scale": "0",
                "cny_scale": "0",
                "foreign_scale": "0",
                "cnx_cash": "0",
                "cny_cash": "0",
                "foreign_cash": "0",
                "cny_ftp": "0",
                "foreign_ftp": "0",
                "cny_net": "0",
                "foreign_net": "0",
                "business_net_income": bni,
                "weighted_yield": None,
                "is_total": True,
                "children": [],
                "scenario_rate_pct": None,
            }

        at = row_dict("asset_total", "资产合计", "asset", "9000000000")
        lt = row_dict("liability_total", "负债合计", "liability", "-1000000000")
        gt = row_dict("grand_total", "grand_total", "all", "1325000000")
        im = row_dict(
            "intermediate_business_income",
            "中间业务收入",
            "asset",
            "500000000",
        )
        pc_payload = ProductCategoryPnlPayload(
            report_date="2026-04-08",
            view="ytd",
            available_views=["ytd", "monthly"],
            scenario_rate_pct=None,
            rows=[
                ProductCategoryPnlRow.model_validate(im),
                ProductCategoryPnlRow.model_validate(at),
                ProductCategoryPnlRow.model_validate(lt),
                ProductCategoryPnlRow.model_validate(gt),
            ],
            asset_total=ProductCategoryPnlRow.model_validate(at),
            liability_total=ProductCategoryPnlRow.model_validate(lt),
            grand_total=ProductCategoryPnlRow.model_validate(gt),
        )

        def fake_resolve(_duck: str, _gov: str, rd: str, _ftp: float):
            assert rd == "2026-04-08"
            return pc_payload

        monkeypatch.setattr(es, "resolve_product_category_ytd_payload_for_home_snapshot", fake_resolve)
        headline = getattr(es, "_build_product_category_ytd_headline")("2026-04-08")
        assert headline is not None
        assert headline.summary_pnl.raw == pytest.approx(1325000000.0)
        assert headline.summary_pnl.display == "+13.25 亿"
        assert "grand_total.business_net_income" in headline.summary_pnl_detail
        assert headline.operating_income.raw == pytest.approx(1325000000.0)
        assert headline.intermediate_business_income.raw == pytest.approx(500000000.0)

    def test_home_snapshot_includes_product_category_ytd_from_fallback_resolver(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Snapshot payload must expose the same YTD headline built by the fallback resolver."""
        from backend.app.schemas.product_category_pnl import (
            ProductCategoryPnlPayload,
            ProductCategoryPnlRow,
        )

        es = _executive_service()

        def row_dict(cid: str, bni: str) -> dict[str, object]:
            return {
                "category_id": cid,
                "category_name": cid,
                "side": "all" if cid == "grand_total" else "asset",
                "level": 0,
                "view": "ytd",
                "report_date": "2026-04-08",
                "baseline_ftp_rate_pct": "1.60",
                "cnx_scale": "0",
                "cny_scale": "0",
                "foreign_scale": "0",
                "cnx_cash": "0",
                "cny_cash": "0",
                "foreign_cash": "0",
                "cny_ftp": "0",
                "foreign_ftp": "0",
                "cny_net": "0",
                "foreign_net": "0",
                "business_net_income": bni,
                "weighted_yield": None,
                "is_total": True,
                "children": [],
                "scenario_rate_pct": None,
            }

        at = row_dict("asset_total", "325000000")
        lt = {**row_dict("liability_total", "0"), "side": "liability"}
        gt = row_dict("grand_total", "325000000")
        im = row_dict("intermediate_business_income", "25000000")
        pc_payload = ProductCategoryPnlPayload(
            report_date="2026-04-08",
            view="ytd",
            available_views=["ytd", "monthly"],
            scenario_rate_pct=None,
            rows=[
                ProductCategoryPnlRow.model_validate(im),
                ProductCategoryPnlRow.model_validate(at),
                ProductCategoryPnlRow.model_validate(lt),
                ProductCategoryPnlRow.model_validate(gt),
            ],
            asset_total=ProductCategoryPnlRow.model_validate(at),
            liability_total=ProductCategoryPnlRow.model_validate(lt),
            grand_total=ProductCategoryPnlRow.model_validate(gt),
        )

        def fake_resolve(_duck: str, _gov: str, rd: str, _ftp: float):
            assert rd == "2026-04-08"
            return pc_payload

        monkeypatch.setattr(es, "resolve_product_category_ytd_payload_for_home_snapshot", fake_resolve)
        monkeypatch.setattr(es, "_build_product_category_monthly_headline", lambda _rd: None)

        with patch.object(es, "_list_domain_date_context") as mock_dates:
            mock_dates.return_value = {
                "balance": ["2026-04-08"],
                "pnl": ["2026-04-08"],
                "liability": ["2026-04-08"],
                "bond": ["2026-04-08"],
            }
            with patch.object(es, "executive_overview") as mock_ov:
                with patch.object(es, "executive_pnl_attribution") as mock_attr:
                    mock_ov.return_value = {
                        "result_meta": {},
                        "result": {"title": "operating overview", "metrics": []},
                    }
                    mock_attr.return_value = {
                        "result_meta": {},
                        "result": {
                            "title": "attribution",
                            "total": {
                                "raw": 0.0,
                                "unit": "yuan",
                                "display": "0",
                                "precision": 0,
                                "sign_aware": False,
                            },
                            "segments": [],
                        },
                    }
                    env = es.home_snapshot_envelope(
                        report_date="2026-04-08",
                        allow_partial=False,
                    )

        headline = env["result"]["product_category_ytd"]
        assert headline is not None
        assert headline["summary_pnl"]["raw"] == pytest.approx(325000000.0)
        assert headline["intermediate_business_income"]["raw"] == pytest.approx(25000000.0)
        assert "grand_total.business_net_income" in headline["summary_pnl_detail"]

    def test_build_product_category_monthly_headline_matches_monthly_grand_total(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Parity: homepage monthly headline must echo product_category_pnl_envelope monthly grand_total."""
        from backend.app.schemas.product_category_pnl import (
            ProductCategoryPnlPayload,
            ProductCategoryPnlRow,
        )

        es = _executive_service()

        def row_dict(cid: str, name: str, side: str, bni: str) -> dict[str, object]:
            return {
                "category_id": cid,
                "category_name": name,
                "side": side,
                "level": 0,
                "view": "monthly",
                "report_date": "2026-04-08",
                "baseline_ftp_rate_pct": "1.60",
                "cnx_scale": "0",
                "cny_scale": "0",
                "foreign_scale": "0",
                "cnx_cash": "0",
                "cny_cash": "0",
                "foreign_cash": "0",
                "cny_ftp": "0",
                "foreign_ftp": "0",
                "cny_net": "0",
                "foreign_net": "0",
                "business_net_income": bni,
                "weighted_yield": None,
                "is_total": True,
                "children": [],
                "scenario_rate_pct": None,
            }

        at = row_dict("asset_total", "资产合计", "asset", "200000000")
        lt = row_dict("liability_total", "负债合计", "liability", "99181927.65")
        gt = row_dict("grand_total", "grand_total", "all", "299181927.65")
        pc_payload = ProductCategoryPnlPayload(
            report_date="2026-04-08",
            view="monthly",
            available_views=["ytd", "monthly"],
            scenario_rate_pct=None,
            rows=[
                ProductCategoryPnlRow.model_validate(at),
                ProductCategoryPnlRow.model_validate(lt),
                ProductCategoryPnlRow.model_validate(gt),
            ],
            asset_total=ProductCategoryPnlRow.model_validate(at),
            liability_total=ProductCategoryPnlRow.model_validate(lt),
            grand_total=ProductCategoryPnlRow.model_validate(gt),
        )

        def fake_envelope(_duck: str, *, report_date: str, view: str, scenario_rate_pct=None):
            assert report_date == "2026-04-08"
            assert view == "monthly"
            assert scenario_rate_pct is None
            return {"result": pc_payload.model_dump(mode="json")}

        monkeypatch.setattr(es, "product_category_pnl_envelope", fake_envelope)
        headline = getattr(es, "_build_product_category_monthly_headline")("2026-04-08")
        assert headline is not None
        assert headline.monthly_income.raw == pytest.approx(299181927.65)
        assert headline.monthly_income.display == "+2.99 亿"
        assert "view=monthly" in headline.monthly_income_detail


class TestHomeSnapshotPayloadSchema:
    def test_roundtrip(self) -> None:
        from backend.app.schemas.common_numeric import Numeric
        from backend.app.schemas.executive_dashboard import (
            HomeSnapshotPayload,
            OverviewPayload,
            PnlAttributionPayload,
        )

        payload = HomeSnapshotPayload(
            report_date="2026-04-08",
            mode="strict",
            source_surface="executive_analytical",
            overview=OverviewPayload(title="经营总览", metrics=[]),
            attribution=PnlAttributionPayload(
                title="经营贡献拆解",
                total=Numeric(
                    raw=0.0,
                    unit="yuan",
                    display="0 亿",
                    precision=0,
                    sign_aware=False,
                ),
                segments=[],
            ),
            domains_missing=[],
            domains_effective_date={
                "balance_sheet": "2026-04-08",
                "pnl": "2026-04-08",
            },
        )
        dumped = payload.model_dump(mode="json")
        restored = HomeSnapshotPayload.model_validate(dumped)
        assert restored.report_date == "2026-04-08"
        assert restored.source_surface == "executive_analytical"
        assert restored.product_category_ytd is None
