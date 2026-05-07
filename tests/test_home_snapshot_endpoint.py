"""W4.1 tests for /ui/home/snapshot endpoint and home_snapshot_envelope service."""
from __future__ import annotations

import importlib
from unittest.mock import patch

import pytest

from backend.app.schemas.executive_dashboard import HomeSnapshotPayload
from backend.app.services.executive_service import (
    _compute_unified_report_date,
    _HOME_SNAPSHOT_CALIBERS,
    invalidate_home_snapshot_cache,
)


@pytest.fixture(autouse=True)
def _isolate_home_snapshot_cache():
    """每个用例都从空缓存开始，避免上一条用例的 envelope 污染本条 mock。"""
    invalidate_home_snapshot_cache()
    yield
    invalidate_home_snapshot_cache()


def _executive_service():
    """Always use the canonical `sys.modules` entry (golden tests may reload this module)."""
    return importlib.import_module("backend.app.services.executive_service")


class TestComputeUnifiedReportDate:
    def test_strict_intersection_empty_returns_none(self) -> None:
        dates = {"balance_sheet": set(), "pnl": set()}
        rd, missing, effective = _compute_unified_report_date(
            requested=None, allow_partial=False, domain_dates=dates
        )
        assert rd is None
        assert set(missing) == set(_HOME_SNAPSHOT_CALIBERS)
        assert effective == {}

    def test_strict_intersection_nonempty_picks_max(self) -> None:
        dates = {
            "balance_sheet": {"2026-04-08", "2026-04-07"},
            "pnl": {"2026-04-08", "2026-04-07", "2026-04-06"},
        }
        rd, missing, effective = _compute_unified_report_date(
            requested=None, allow_partial=False, domain_dates=dates
        )
        assert rd == "2026-04-08"
        assert missing == []
        assert all(effective[d] == "2026-04-08" for d in _HOME_SNAPSHOT_CALIBERS)

    def test_strict_requested_in_intersection(self) -> None:
        dates = {
            "balance_sheet": {"2026-04-08", "2026-04-07"},
            "pnl": {"2026-04-08", "2026-04-07"},
        }
        rd, missing, effective = _compute_unified_report_date(
            requested="2026-04-07", allow_partial=False, domain_dates=dates
        )
        assert rd == "2026-04-07"
        assert missing == []

    def test_strict_requested_not_in_intersection_returns_none(self) -> None:
        dates = {
            "balance_sheet": {"2026-04-08"},
            "pnl": {"2026-04-07"},  # no common date with balance_sheet caliber set
        }
        rd, missing, effective = _compute_unified_report_date(
            requested="2026-04-08", allow_partial=False, domain_dates=dates
        )
        assert rd is None
        assert set(missing) == set(_HOME_SNAPSHOT_CALIBERS)

    def test_partial_requested_labels_missing_domains(self) -> None:
        dates = {
            "balance_sheet": {"2026-04-08", "2026-04-07"},
            "pnl": {"2026-04-07"},  # missing 04-08
        }
        rd, missing, effective = _compute_unified_report_date(
            requested="2026-04-08", allow_partial=True, domain_dates=dates
        )
        assert rd == "2026-04-08"
        assert "pnl" in missing
        assert effective["balance_sheet"] == "2026-04-08"
        assert effective["pnl"] == "2026-04-07"  # latest available

    def test_partial_no_requested_uses_union_max(self) -> None:
        dates = {
            "balance_sheet": {"2026-04-08"},
            "pnl": {"2026-04-07"},
        }
        rd, missing, effective = _compute_unified_report_date(
            requested=None, allow_partial=True, domain_dates=dates
        )
        assert rd == "2026-04-08"
        assert {"pnl"} <= set(missing)


class TestHomeSnapshotEnvelope:
    def test_returns_envelope_shape(self) -> None:
        # Run with default env (real duckdb); if repos can't open, it still must
        # return a valid envelope (possibly with empty payload).
        env = _executive_service().home_snapshot_envelope(report_date=None, allow_partial=False)
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
        with patch.object(es, "_list_domain_dates") as mock_dates:
            mock_dates.return_value = {
                "balance_sheet": set(),
                "pnl": set(),
            }
            env = es.home_snapshot_envelope(report_date=None, allow_partial=False)
            assert env["result_meta"]["quality_flag"] == "error"
            assert env["result_meta"]["vendor_status"] == "vendor_unavailable"
            assert env["result"]["report_date"] == ""
            assert set(env["result"]["domains_missing"]) == set(_HOME_SNAPSHOT_CALIBERS)

    def test_strict_intersection_returns_unified_date(self) -> None:
        es = _executive_service()
        with patch.object(es, "_list_domain_dates") as mock_dates:
            mock_dates.return_value = {
                "balance_sheet": {"2026-04-08"},
                "pnl": {"2026-04-08"},
            }
            with patch.object(es, "executive_overview") as mock_ov:
                with patch.object(es, "executive_pnl_attribution") as mock_attr:
                    with patch.object(es, "_build_product_category_ytd_headline", return_value=None):
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

    def test_partial_mode_labels_missing(self) -> None:
        es = _executive_service()
        with patch.object(es, "_list_domain_dates") as mock_dates:
            mock_dates.return_value = {
                "balance_sheet": {"2026-04-08"},
                "pnl": set(),  # missing entirely
            }
            with patch.object(es, "executive_overview") as mock_ov:
                with patch.object(es, "executive_pnl_attribution") as mock_attr:
                    with patch.object(es, "_build_product_category_ytd_headline", return_value=None):
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

        monkeypatch.setattr(
            "backend.app.services.executive_service.resolve_product_category_ytd_payload_for_home_snapshot",
            fake_resolve,
        )
        headline = getattr(es, "_build_product_category_ytd_headline")("2026-04-08")
        assert headline is not None
        assert headline.summary_pnl.raw == pytest.approx(1325000000.0)
        assert headline.summary_pnl.display == "+13.25 亿"
        assert "grand_total.business_net_income" in headline.summary_pnl_detail
        assert headline.operating_income.raw == pytest.approx(1325000000.0)
        assert headline.intermediate_business_income.raw == pytest.approx(500000000.0)

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

        monkeypatch.setattr(
            "backend.app.services.executive_service.product_category_pnl_envelope",
            fake_envelope,
        )
        headline = getattr(es, "_build_product_category_monthly_headline")("2026-04-08")
        assert headline is not None
        assert headline.monthly_income.raw == pytest.approx(299181927.65)
        assert headline.monthly_income.display == "+2.99 亿"
        assert "view=monthly" in headline.monthly_income_detail


class TestHomeSnapshotPayloadSchema:
    def test_roundtrip(self) -> None:
        from backend.app.schemas.executive_dashboard import (
            OverviewPayload,
            PnlAttributionPayload,
        )
        from backend.app.schemas.common_numeric import Numeric

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
