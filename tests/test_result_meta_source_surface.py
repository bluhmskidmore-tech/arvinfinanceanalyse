"""W4.2: ResultMeta.source_surface field & executive / pnl service wiring."""
from __future__ import annotations

from typing import get_args

import pytest

from backend.app.schemas.result_meta import ResultMeta, SourceSurface
from backend.app.services import pnl_attribution_service as pa_svc


class TestResultMetaSourceSurface:
    def test_default_none(self) -> None:
        rm = ResultMeta(
            trace_id="tr_x",
            source_version="sv_x",
            rule_version="rv_x",
            cache_version="cv_x",
        )
        assert rm.source_surface is None

    @pytest.mark.parametrize(
        "value",
        [
            "executive_analytical",
            "formal_attribution",
            "formal_pnl",
            "formal_balance",
            "formal_liability",
            "bond_analytics",
            "risk_tensor",
        ],
    )
    def test_accepts_each_literal(self, value: str) -> None:
        rm = ResultMeta(
            trace_id="tr_x",
            source_version="sv_x",
            rule_version="rv_x",
            cache_version="cv_x",
            source_surface=value,
        )
        assert rm.source_surface == value
        assert value in get_args(SourceSurface)

    def test_rejects_unknown_literal(self) -> None:
        with pytest.raises(Exception):
            ResultMeta(
                trace_id="tr_x",
                source_version="sv_x",
                rule_version="rv_x",
                cache_version="cv_x",
                source_surface="not_a_surface",  # type: ignore[arg-type]
            )


class _EmptyRepo:
    def list_formal_fi_report_dates(self):
        return []

    def list_report_dates(self):
        return []

    def fetch_formal_fi_rows(self, *a, **k):
        return []

    def fetch_bond_analytics_rows(self, *a, **k):
        return []

    def fetch_curve(self, *a, **k):
        return None


@pytest.fixture(autouse=True)
def _stub_pa_repos(monkeypatch: pytest.MonkeyPatch):
    stub = _EmptyRepo()
    monkeypatch.setattr(pa_svc, "_pnl_repo", lambda: stub)
    monkeypatch.setattr(pa_svc, "_bond_repo", lambda: stub)
    monkeypatch.setattr(pa_svc, "_curve_repo", lambda: stub)


class TestPnlAttributionEnvelopesCarrySurface:
    @pytest.mark.parametrize(
        "envelope_builder",
        [
            lambda: pa_svc.volume_rate_attribution_envelope(report_date=None, compare_type="mom"),
            lambda: pa_svc.tpl_market_correlation_envelope(months=3),
            lambda: pa_svc.pnl_composition_envelope(report_date=None),
            lambda: pa_svc.attribution_analysis_summary_envelope(report_date=None),
            lambda: pa_svc.carry_roll_down_envelope(report_date=None),
            lambda: pa_svc.spread_attribution_envelope(report_date=None, lookback_days=30),
            lambda: pa_svc.krd_attribution_envelope(report_date=None, lookback_days=30),
            lambda: pa_svc.advanced_attribution_summary_envelope(report_date=None),
            lambda: pa_svc.campisi_attribution_envelope(start_date=None, end_date=None, lookback_days=30),
        ],
    )
    def test_envelope_result_meta_source_surface_is_formal_attribution(
        self, envelope_builder
    ) -> None:
        env = envelope_builder()
        rm = env["result_meta"]
        assert rm["source_surface"] == "formal_attribution", f"envelope={env!r}"


class TestExecutiveEnvelopesCarrySurface:
    """Executive envelopes require a heavier fixture set (DuckDB-backed services).
    Prefer importing a thin sub-surface: validate the /ui/home/snapshot payload via
    a pytest fixture already present in tests/test_executive_dashboard_endpoints.py.

    If that fixture is not trivially reusable here, leave a single smoke using the
    analytical meta builder with source_surface kwarg to prove the wiring compiles
    and the builder accepts the literal:
    """

    def test_analytical_builder_accepts_source_surface(self) -> None:
        from backend.app.services.formal_result_runtime import build_analytical_result_meta

        rm = build_analytical_result_meta(
            trace_id="tr_x",
            result_kind="executive.overview",
            cache_version="cv",
            source_version="sv",
            rule_version="rv",
            source_surface="executive_analytical",
        )
        assert rm.source_surface == "executive_analytical"

    def test_formal_builder_accepts_source_surface(self) -> None:
        from backend.app.services.formal_result_runtime import build_formal_result_meta

        rm = build_formal_result_meta(
            trace_id="tr_x",
            result_kind="executive.overview",
            cache_version="cv",
            source_version="sv",
            rule_version="rv",
            source_surface="executive_analytical",
        )
        assert rm.source_surface == "executive_analytical"
