"""W3.2 verification: pnl_attribution_service envelopes construct
explicit Numeric-dicts at the service layer; the schema coerce
validator is defense-in-depth, not the live code path."""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import pytest


NUMERIC_KEYS = {"raw", "unit", "display", "precision", "sign_aware"}


def _pnl_svc():
    """Resolve at call time so tests stay aligned if other suites reload the module."""
    return importlib.import_module("backend.app.services.pnl_attribution_service")


class _EmptyRepo:
    def list_formal_fi_report_dates(self) -> list[str]:
        return []

    def list_report_dates(self) -> list[str]:
        return []

    def fetch_formal_fi_rows(self, *_args, **_kwargs) -> list[dict[str, Any]]:
        return []

    def fetch_bond_analytics_rows(self, *_args, **_kwargs) -> list[dict[str, Any]]:
        return []

    def fetch_curve(self, *_args, **_kwargs) -> dict[str, Any] | None:
        return None


class _BusinessRepo:
    rows_by_date = {
        "2026-04-30": [
            {
                "report_date": "2026-04-30",
                "business_type_primary": "business_cd",
                "business_type": "business_cd",
                "currency_basis": "CNY",
                "interest_income_514": 100.0,
                "fair_value_change_516": 17.0,
                "capital_gain_517": 3.0,
                "manual_adjustment": 0.0,
                "total_pnl": 120.0,
                "scale_amount": 1_000.0,
                "yield_pct": 12.0,
                "pnl_row_count": 2,
                "balance_row_count": 2,
            }
        ],
        "2026-03-31": [
            {
                "report_date": "2026-03-31",
                "business_type_primary": "business_cd",
                "business_type": "business_cd",
                "currency_basis": "CNY",
                "interest_income_514": 70.0,
                "fair_value_change_516": 10.0,
                "capital_gain_517": 0.0,
                "manual_adjustment": 0.0,
                "total_pnl": 80.0,
                "scale_amount": 800.0,
                "yield_pct": 10.0,
                "pnl_row_count": 1,
                "balance_row_count": 1,
            }
        ],
    }

    def list_formal_fi_report_dates(self) -> list[str]:
        return ["2026-04-30", "2026-03-31"]

    def fetch_by_business_rows(self, report_date: str) -> list[dict[str, Any]]:
        raise AssertionError(
            f"attribution must reuse pnl_by_business_envelope, not fetch_by_business_rows({report_date}) directly"
        )

    def fetch_formal_fi_rows(self, *_args, **_kwargs) -> list[dict[str, Any]]:
        raise AssertionError("volume/composition attribution must use business balance rows")


class _SummaryRepo(_BusinessRepo):
    def fetch_formal_fi_rows(self, report_date: str, *_args, **_kwargs) -> list[dict[str, Any]]:
        return [
            {
                "report_date": report_date,
                "instrument_code": f"TPL-{report_date}",
                "portfolio_name": "Portfolio",
                "cost_center": "CostCenter",
                "currency_code": "CNY",
                "accounting_basis": "FVTPL",
                "fair_value_change_516": 1.0,
                "total_pnl": 2.0,
            }
        ]


class _TplMarketPnlRepo:
    def list_formal_fi_report_dates(self) -> list[str]:
        return ["2026-04-30", "2026-03-31", "2026-02-28"]

    def fetch_formal_fi_rows(self, report_date: str, *_args, **_kwargs) -> list[dict[str, Any]]:
        return [
            {
                "report_date": report_date,
                "instrument_code": f"TPL-{report_date}",
                "accounting_basis": "FVTPL",
                "fair_value_change_516": 10.0,
                "total_pnl": 12.0,
            }
        ]


class _TplMarketBondRepo:
    def list_report_dates(self) -> list[str]:
        return ["2026-04-30", "2026-03-31", "2026-02-28"]

    def fetch_bond_analytics_rows(self, *, report_date: str) -> list[dict[str, Any]]:
        return []


class _TplMarketCurveRepo:
    path = "unused.duckdb"

    def fetch_latest_trade_date_on_or_before(self, curve_type: str, trade_date: str) -> str | None:
        assert curve_type == "treasury"
        return {
            "2026-02-28": "2026-02-28",
            "2026-03-31": "2026-03-29",
            "2026-04-30": "2026-04-30",
        }.get(trade_date)

    def fetch_curve(self, trade_date: str, curve_type: str) -> dict[str, Any]:
        assert curve_type == "treasury"
        curves = {
            "2026-02-28": {"10Y": 1.90},
            "2026-03-29": {"10Y": 2.00},
            "2026-04-30": {"10Y": 2.30},
        }
        return curves.get(trade_date, {})


class _CarryRollDownRepo:
    def list_report_dates(self) -> list[str]:
        return ["2026-04-30", "2026-03-31"]

    def fetch_bond_analytics_rows(self, *, report_date: str) -> list[dict[str, Any]]:
        return [
            {
                "report_date": report_date,
                "asset_class_std": "rate",
                "market_value": 500_000_000.0,
                "coupon_rate": 0.0285,
                "modified_duration": 4.2,
                "ytm": 0.028,
                "years_to_maturity": 5.0,
            }
        ]

    def fetch_curve(self, trade_date: str, curve_type: str) -> dict[str, Decimal]:
        assert trade_date == "2026-04-30"
        assert curve_type == "treasury"
        return {"4Y": Decimal("2.70"), "5Y": Decimal("2.85")}


def _by_business_envelope(report_date: str) -> dict[str, Any]:
    rows = list(_BusinessRepo.rows_by_date.get(report_date, []))
    return {
        "result_meta": {
            "trace_id": f"tr_pnl_by_business_{report_date}",
            "basis": "formal",
            "result_kind": "pnl.by_business",
            "formal_use_allowed": True,
            "source_version": "sv_pnl_by_business_test",
            "vendor_version": "vv_none",
            "rule_version": "rv_pnl_test",
            "cache_version": "cv_pnl_test",
            "quality_flag": "ok",
            "vendor_status": "ok",
            "fallback_mode": "none",
            "scenario_flag": False,
            "as_of_date": report_date,
            "generated_at": "2026-04-30T00:00:00Z",
            "tables_used": [],
            "filters_applied": {},
            "evidence_rows": sum(int(row.get("pnl_row_count") or 0) + int(row.get("balance_row_count") or 0) for row in rows),
            "next_drill": [],
        },
        "result": {
            "report_date": report_date,
            "source_tables": [
                "fact_formal_pnl_fi",
                "fact_nonstd_pnl_bridge",
                "fact_formal_zqtz_balance_daily",
            ],
            "summary": {
                "business_count": len(rows),
                "total_pnl": str(sum(float(row.get("total_pnl") or 0) for row in rows)),
                "total_scale_amount": str(sum(float(row.get("scale_amount") or 0) for row in rows)),
                "traced_pnl_row_count": sum(int(row.get("pnl_row_count") or 0) for row in rows),
                "untraced_pnl_row_count": 0,
            },
            "rows": rows,
        },
    }


def _by_business_warning_envelope(report_date: str) -> dict[str, Any]:
    envelope = _by_business_envelope(report_date)
    envelope["result_meta"] = {**envelope["result_meta"], "quality_flag": "warning"}
    envelope["result"] = {
        **envelope["result"],
        "warnings": ["正式 FI 明细存在未匹配余额行。"],
    }
    return envelope


class _CampisiRepo:
    def list_report_dates(self) -> list[str]:
        return ["2026-01-31", "2026-01-01"]

    def fetch_bond_analytics_rows(self, *, report_date: str) -> list[dict[str, Any]]:
        return [{"instrument_code": f"BOND-{report_date}"}]

    def fetch_curve(self, *_args, **_kwargs) -> dict[str, Any] | None:
        return {"3Y": 2.5}


@dataclass
class _CampisiCoreResult:
    num_days: int
    totals: dict[str, float]
    by_asset_class: list[dict[str, Any]]
    by_bond: list[dict[str, Any]]
    diagnostics: list[str]


@pytest.fixture(autouse=True)
def _stub_repos(monkeypatch: pytest.MonkeyPatch):
    stub = _EmptyRepo()
    mod = _pnl_svc()
    monkeypatch.setattr(mod, "_pnl_repo", lambda: stub)
    monkeypatch.setattr(mod, "_bond_repo", lambda: stub)
    monkeypatch.setattr(mod, "_curve_repo", lambda: stub)


def _assert_numeric_dict(value: Any) -> None:
    assert isinstance(value, dict), f"expected Numeric-dict, got {type(value).__name__}: {value!r}"
    assert NUMERIC_KEYS <= set(value.keys()), f"missing keys in {value!r}"
    assert isinstance(value["unit"], str)


def test_volume_rate_envelope_empty_produces_numeric_dicts():
    env = _pnl_svc().volume_rate_attribution_envelope(report_date=None, compare_type="mom")
    result = env["result"]
    for k in ("total_current_pnl",):
        _assert_numeric_dict(result[k])
    # Optional totals present as dict or None
    for k in ("total_previous_pnl", "total_pnl_change", "total_volume_effect"):
        v = result.get(k)
        assert v is None or (isinstance(v, dict) and NUMERIC_KEYS <= set(v.keys()))


def test_tpl_market_envelope_empty_produces_numeric_dicts():
    env = _pnl_svc().tpl_market_correlation_envelope(months=12)
    result = env["result"]
    _assert_numeric_dict(result["total_tpl_fv_change"])


def test_tpl_market_uses_market_data_on_or_before_and_prior_month_change(monkeypatch: pytest.MonkeyPatch):
    mod = _pnl_svc()
    monkeypatch.setattr(mod, "_pnl_repo", lambda: _TplMarketPnlRepo())
    monkeypatch.setattr(mod, "_bond_repo", lambda: _TplMarketBondRepo())
    monkeypatch.setattr(mod, "_curve_repo", lambda: _TplMarketCurveRepo())
    monkeypatch.setattr(
        mod,
        "_dr007_on_or_before",
        lambda _duckdb_path, trade_date: (
            {
                "2026-03-31": 1.50,
                "2026-04-30": 1.40,
            }.get(trade_date),
            {
                "2026-03-31": "2026-03-29",
                "2026-04-30": "2026-04-30",
            }.get(trade_date),
        ),
    )

    env = mod.tpl_market_correlation_envelope(months=2, report_date="2026-04-30")
    points = env["result"]["data_points"]

    assert [point["period"] for point in points] == ["2026-03", "2026-04"]
    assert points[0]["treasury_10y"]["raw"] == pytest.approx(0.02)
    assert points[0]["treasury_10y_change"]["raw"] == pytest.approx(10.0)
    assert points[1]["treasury_10y_change"]["raw"] == pytest.approx(30.0)
    assert points[0]["dr007"]["raw"] == pytest.approx(0.015)
    assert points[1]["dr007"]["raw"] == pytest.approx(0.014)


def test_composition_envelope_empty_produces_numeric_dicts():
    env = _pnl_svc().pnl_composition_envelope(report_date=None)
    result = env["result"]
    for k in (
        "total_pnl",
        "total_interest_income",
        "total_fair_value_change",
        "total_capital_gain",
        "total_other_income",
        "interest_pct",
        "fair_value_pct",
        "capital_gain_pct",
        "other_pct",
    ):
        _assert_numeric_dict(result[k])


def test_volume_rate_envelope_uses_business_balance_rows(monkeypatch: pytest.MonkeyPatch):
    mod = _pnl_svc()
    monkeypatch.setattr(mod, "_pnl_repo", lambda: _BusinessRepo())
    calls: list[str] = []

    def fake_by_business_envelope(*, duckdb_path: str, governance_dir: str, report_date: str) -> dict[str, Any]:
        calls.append(report_date)
        return _by_business_envelope(report_date)

    monkeypatch.setattr(mod.pnl_service, "pnl_by_business_envelope", fake_by_business_envelope)

    env = mod.volume_rate_attribution_envelope(report_date="2026-04-30", compare_type="mom")
    result = env["result"]
    meta = env["result_meta"]

    assert calls == ["2026-04-30", "2026-03-31"]
    assert result["total_current_pnl"]["raw"] == pytest.approx(120.0)
    assert result["total_previous_pnl"]["raw"] == pytest.approx(80.0)
    assert result["total_volume_effect"]["raw"] == pytest.approx(20.0)
    assert result["total_rate_effect"]["raw"] == pytest.approx(16.0)
    assert result["total_interaction_effect"]["raw"] == pytest.approx(4.0)
    assert result["items"][0]["category"] == "business_cd"
    assert meta["source_version"] == "sv_pnl_by_business_test"
    assert meta["as_of_date"] == "2026-04-30"
    assert "fact_formal_zqtz_balance_daily" in meta["tables_used"]


def test_composition_envelope_uses_business_balance_rows(monkeypatch: pytest.MonkeyPatch):
    mod = _pnl_svc()
    monkeypatch.setattr(mod, "_pnl_repo", lambda: _BusinessRepo())
    calls: list[str] = []

    def fake_by_business_envelope(*, duckdb_path: str, governance_dir: str, report_date: str) -> dict[str, Any]:
        calls.append(report_date)
        return _by_business_envelope(report_date)

    monkeypatch.setattr(mod.pnl_service, "pnl_by_business_envelope", fake_by_business_envelope)

    env = mod.pnl_composition_envelope(report_date="2026-04-30", include_trend=False)
    result = env["result"]
    meta = env["result_meta"]

    assert calls == ["2026-04-30"]
    assert result["total_pnl"]["raw"] == pytest.approx(120.0)
    assert result["total_interest_income"]["raw"] == pytest.approx(100.0)
    assert result["total_fair_value_change"]["raw"] == pytest.approx(17.0)
    assert result["total_capital_gain"]["raw"] == pytest.approx(3.0)
    assert result["items"][0]["category"] == "business_cd"
    assert meta["source_version"] == "sv_pnl_by_business_test"
    assert meta["as_of_date"] == "2026-04-30"


def test_attribution_analysis_summary_envelope_empty():
    env = _pnl_svc().attribution_analysis_summary_envelope(report_date=None)
    _assert_numeric_dict(env["result"]["primary_driver_pct"])


def test_attribution_analysis_summary_envelope_carries_subsurface_meta(monkeypatch: pytest.MonkeyPatch):
    mod = _pnl_svc()
    monkeypatch.setattr(mod, "_pnl_repo", lambda: _SummaryRepo())
    monkeypatch.setattr(mod, "_bond_repo", lambda: _EmptyRepo())
    monkeypatch.setattr(mod, "_curve_repo", lambda: _EmptyRepo())

    def fake_by_business_envelope(*, duckdb_path: str, governance_dir: str, report_date: str) -> dict[str, Any]:
        return _by_business_envelope(report_date)

    monkeypatch.setattr(mod.pnl_service, "pnl_by_business_envelope", fake_by_business_envelope)

    env = mod.attribution_analysis_summary_envelope(report_date="2026-04-30")
    meta = env["result_meta"]

    assert meta["source_version"] != "sv_pnl_attribution_empty_v1"
    assert meta["as_of_date"] == "2026-04-30"
    assert meta["filters_applied"]["requested_report_date"] == "2026-04-30"
    assert "fact_formal_zqtz_balance_daily" in meta["tables_used"]
    assert "yield_curve_daily" in meta["tables_used"]
    assert meta["evidence_rows"] > 0


def test_non_empty_business_warning_does_not_claim_empty_materialization(monkeypatch: pytest.MonkeyPatch):
    mod = _pnl_svc()
    monkeypatch.setattr(mod, "_pnl_repo", lambda: _BusinessRepo())

    def fake_by_business_envelope(*, duckdb_path: str, governance_dir: str, report_date: str) -> dict[str, Any]:
        return _by_business_warning_envelope(report_date)

    monkeypatch.setattr(mod.pnl_service, "pnl_by_business_envelope", fake_by_business_envelope)

    env = mod.volume_rate_attribution_envelope(report_date="2026-04-30", compare_type="mom")
    warnings = env["result"].get("warnings") or []

    assert env["result_meta"]["quality_flag"] == "warning"
    assert env["result_meta"]["evidence_rows"] > 0
    assert warnings
    assert not any("物化" in warning for warning in warnings)
    assert any("数据质量" in warning for warning in warnings)


def test_carry_roll_down_non_empty_meta_carries_bond_source(monkeypatch: pytest.MonkeyPatch):
    mod = _pnl_svc()
    repo = _CampisiRepo()
    monkeypatch.setattr(mod, "_bond_repo", lambda: repo)
    monkeypatch.setattr(mod, "_curve_repo", lambda: repo)

    env = mod.carry_roll_down_envelope(report_date="2026-01-31")
    meta = env["result_meta"]

    assert meta["source_version"] == "sv_pnl_attribution_formal_market_v1"
    assert meta["as_of_date"] == "2026-01-31"
    assert "fact_formal_bond_analytics_daily" in meta["tables_used"]
    assert meta["evidence_rows"] == 1


def test_carry_roll_down_envelope_empty():
    env = _pnl_svc().carry_roll_down_envelope(report_date=None)
    result = env["result"]
    for k in (
        "total_market_value",
        "portfolio_carry",
        "portfolio_rolldown",
        "portfolio_static_return",
        "total_carry_pnl",
        "total_rolldown_pnl",
        "total_static_pnl",
        "ftp_rate",
    ):
        _assert_numeric_dict(result[k])


def test_carry_roll_down_envelope_uses_current_curve_roll(monkeypatch: pytest.MonkeyPatch):
    mod = _pnl_svc()
    repo = _CarryRollDownRepo()
    monkeypatch.setattr(mod, "_bond_repo", lambda: repo)
    monkeypatch.setattr(mod, "_curve_repo", lambda: repo)

    env = mod.carry_roll_down_envelope(report_date="2026-04-30")
    result = env["result"]

    assert result["portfolio_rolldown"]["unit"] == "pct"
    assert result["portfolio_rolldown"]["raw"] == pytest.approx(0.0063)
    assert result["portfolio_rolldown"]["display"] == "+0.63%"
    assert result["total_rolldown_pnl"]["raw"] == pytest.approx(262_500.0)
    assert result["items"][0]["curve_slope"]["unit"] == "bp"
    assert result["items"][0]["curve_slope"]["raw"] == pytest.approx(15.0)


def test_spread_envelope_empty():
    env = _pnl_svc().spread_attribution_envelope(report_date=None, lookback_days=30)
    result = env["result"]
    for k in ("total_market_value", "portfolio_duration", "total_treasury_effect", "total_spread_effect", "total_price_change"):
        _assert_numeric_dict(result[k])


def test_krd_envelope_empty():
    env = _pnl_svc().krd_attribution_envelope(report_date=None, lookback_days=30)
    result = env["result"]
    for k in ("total_market_value", "portfolio_duration", "portfolio_dv01", "total_duration_effect", "max_contribution_value"):
        _assert_numeric_dict(result[k])


def test_advanced_summary_envelope_empty():
    env = _pnl_svc().advanced_attribution_summary_envelope(report_date=None)
    result = env["result"]
    for k in ("portfolio_carry", "portfolio_rolldown", "static_return_annualized", "treasury_effect_total", "spread_effect_total"):
        _assert_numeric_dict(result[k])


def test_advanced_summary_preserves_child_pct_numeric_values(monkeypatch: pytest.MonkeyPatch):
    mod = _pnl_svc()

    def child_meta(result_kind: str) -> dict[str, Any]:
        return {
            "result_kind": result_kind,
            "source_version": "sv_test",
            "tables_used": ["fact_formal_bond_analytics_daily"],
            "evidence_rows": 1,
        }

    def numeric(raw: float, unit: str, display: str) -> dict[str, Any]:
        return {
            "raw": raw,
            "unit": unit,
            "display": display,
            "precision": 2,
            "sign_aware": True,
        }

    monkeypatch.setattr(
        mod,
        "carry_roll_down_envelope",
        lambda report_date: {
            "result_meta": child_meta("pnl_attribution.carry_rolldown"),
            "result": {
                "report_date": "2026-04-30",
                "portfolio_carry": numeric(0.00319, "pct", "+0.32%"),
                "portfolio_rolldown": numeric(-0.000022, "pct", "-0.00%"),
                "portfolio_static_return": numeric(0.003168, "pct", "+0.32%"),
            },
        },
    )
    monkeypatch.setattr(
        mod,
        "spread_attribution_envelope",
        lambda report_date, lookback_days: {
            "result_meta": child_meta("pnl_attribution.spread"),
            "result": {
                "total_treasury_effect": numeric(740_968_491.27, "yuan", "+740,968,491.27"),
                "total_spread_effect": numeric(-595_536_064.43, "yuan", "-595,536,064.43"),
                "primary_driver": "treasury",
            },
        },
    )
    monkeypatch.setattr(
        mod,
        "krd_attribution_envelope",
        lambda report_date, lookback_days: {
            "result_meta": child_meta("pnl_attribution.krd"),
            "result": {
                "max_contribution_tenor": "20Y",
                "curve_shift_type": "bull_flattener",
            },
        },
    )

    env = mod.advanced_attribution_summary_envelope(report_date="2026-04-30")
    result = env["result"]

    assert result["portfolio_carry"]["raw"] == pytest.approx(0.00319)
    assert result["portfolio_carry"]["display"] == "+0.32%"
    assert result["static_return_annualized"]["raw"] == pytest.approx(0.003168)
    assert result["static_return_annualized"]["display"] == "+0.32%"


def test_campisi_envelope_empty():
    env = _pnl_svc().campisi_attribution_envelope(start_date=None, end_date=None, lookback_days=30)
    result = env["result"]
    for k in (
        "total_market_value",
        "total_return",
        "total_return_pct",
        "total_income",
        "total_treasury_effect",
        "total_spread_effect",
        "total_selection_effect",
        "income_contribution_pct",
        "treasury_contribution_pct",
        "spread_contribution_pct",
        "selection_contribution_pct",
    ):
        _assert_numeric_dict(result[k])


def test_campisi_envelope_adapts_core_result(monkeypatch: pytest.MonkeyPatch):
    mod = _pnl_svc()
    repo = _CampisiRepo()
    calls: dict[str, Any] = {}

    monkeypatch.setattr(mod, "_bond_repo", lambda: repo)
    monkeypatch.setattr(mod, "_curve_repo", lambda: repo)
    monkeypatch.setattr(
        mod,
        "merge_positions",
        lambda rows_start, rows_end: [{"bond_code": "BOND1", "market_value_start": 1000.0}],
    )
    monkeypatch.setattr(mod, "fetch_credit_spread_market", lambda _repo, _trade_date: {"credit_spread_aaa_3y": 50.0})

    def _fake_core(**kwargs: Any) -> _CampisiCoreResult:
        calls.update(kwargs)
        return _CampisiCoreResult(
            num_days=30,
            totals={
                "market_value_start": 1000.0,
                "total_return": 107.0,
                "income_return": 60.0,
                "treasury_effect": -10.0,
                "spread_effect": 57.0,
                "selection_effect": 0.0,
            },
            by_asset_class=[
                {
                    "asset_class": "credit AAA",
                    "market_value_start": 1000.0,
                    "weight_pct": 100.0,
                    "total_return": 107.0,
                    "total_return_pct": 10.7,
                    "income_return": 60.0,
                    "income_return_pct": 6.0,
                    "treasury_effect": -10.0,
                    "treasury_effect_pct": -1.0,
                    "spread_effect": 57.0,
                    "spread_effect_pct": 5.7,
                    "selection_effect": 0.0,
                    "selection_effect_pct": 0.0,
                }
            ],
            by_bond=[],
            diagnostics=["BOND1: accrued interest missing"],
        )

    monkeypatch.setattr(mod, "_core_campisi", _fake_core)

    env = mod.campisi_attribution_envelope(start_date="2026-01-01", end_date="2026-01-31", lookback_days=30)
    result = env["result"]

    assert calls["positions_merged"] == [{"bond_code": "BOND1", "market_value_start": 1000.0}]
    assert calls["market_start"]["treasury_3y"] == 2.5
    assert calls["market_end"]["credit_spread_aaa_3y"] == 50.0
    assert calls["start_date"] == date(2026, 1, 1)
    assert calls["end_date"] == date(2026, 1, 31)
    assert result["num_days"] == 30
    assert result["primary_driver"] == "mixed"
    assert result["warnings"] == ["BOND1: accrued interest missing", mod.QUALITY_WARN]
    assert result["total_income"]["raw"] == 60.0
    assert result["total_return_pct"]["raw"] == pytest.approx(0.107)
    assert result["total_return_pct"]["display"] == "+10.70%"
    assert result["income_contribution_pct"]["raw"] == pytest.approx(0.560748)
    assert result["items"][0]["category"] == "credit AAA"
    assert result["items"][0]["weight"]["raw"] == 1.0


def test_promote_helper_passthrough_already_promoted():
    # Idempotency: a promoted dict goes through unchanged.
    from backend.app.schemas.common_numeric import numeric_from_raw
    from backend.app.schemas.pnl_attribution import VolumeRateAttributionPayload

    already = numeric_from_raw(raw=1.0, unit="yuan", sign_aware=True).model_dump(mode="json")
    payload = {
        "current_period": "2025-04",
        "previous_period": "",
        "compare_type": "mom",
        "total_current_pnl": already,
        "items": [],
        "has_previous_data": False,
    }
    promoted = _pnl_svc()._promote_payload_numerics(payload, VolumeRateAttributionPayload)
    assert promoted["total_current_pnl"] == already


def test_promote_helper_handles_nested_item_list():
    from backend.app.schemas.pnl_attribution import VolumeRateAttributionPayload

    payload = {
        "current_period": "2025-04",
        "previous_period": "2025-03",
        "compare_type": "mom",
        "total_current_pnl": 1e9,
        "items": [
            {
                "category": "TPL",
                "category_type": "asset",
                "level": 0,
                "current_scale": 1e11,
                "current_pnl": 5e8,
            }
        ],
        "has_previous_data": True,
    }
    promoted = _pnl_svc()._promote_payload_numerics(payload, VolumeRateAttributionPayload)
    assert isinstance(promoted["total_current_pnl"], dict)
    assert NUMERIC_KEYS <= set(promoted["total_current_pnl"].keys())
    item = promoted["items"][0]
    assert isinstance(item["current_scale"], dict)
    assert item["current_scale"]["unit"] == "yuan"
    assert item["current_scale"]["sign_aware"] is False
    assert isinstance(item["current_pnl"], dict)
    assert item["current_pnl"]["sign_aware"] is True


def test_promote_helper_treats_small_pct_values_as_percent_points():
    from backend.app.schemas.pnl_attribution import VolumeRateAttributionPayload

    payload = {
        "current_period": "2026-04",
        "previous_period": "2026-03",
        "compare_type": "mom",
        "total_current_pnl": 110_000.0,
        "items": [
            {
                "category": "A",
                "category_type": "asset",
                "level": 0,
                "current_scale": 100_000_000.0,
                "current_pnl": 110_000.0,
                "current_yield_pct": 0.11,
                "previous_scale": 100_000_000.0,
                "previous_pnl": 100_000.0,
                "previous_yield_pct": 0.10,
                "pnl_change_pct": 10.0,
                "volume_contribution_pct": 0.5,
            }
        ],
        "has_previous_data": True,
    }

    promoted = _pnl_svc()._promote_payload_numerics(payload, VolumeRateAttributionPayload)
    row = promoted["items"][0]

    assert row["current_yield_pct"]["raw"] == pytest.approx(0.0011)
    assert row["current_yield_pct"]["display"] == "+0.11%"
    assert row["previous_yield_pct"]["raw"] == pytest.approx(0.001)
    assert row["previous_yield_pct"]["display"] == "+0.10%"
    assert row["pnl_change_pct"]["display"] == "+10.00%"
    assert row["volume_contribution_pct"]["display"] == "+0.50%"


def test_promote_helper_keeps_tpl_rate_changes_in_bp():
    from backend.app.schemas.pnl_attribution import TPLMarketCorrelationPayload

    payload = {
        "start_period": "2026-02",
        "end_period": "2026-03",
        "num_periods": 2,
        "correlation_coefficient": -0.62,
        "correlation_interpretation": "test",
        "total_tpl_fv_change": 42_000_000.0,
        "avg_treasury_10y_change": -7.5,
        "treasury_10y_total_change_bp": -15.0,
        "analysis_summary": "summary",
        "data_points": [
            {
                "period": "2026-03",
                "period_label": "2026-03",
                "tpl_fair_value_change": 32_000_000.0,
                "tpl_total_pnl": 32_000_000.0,
                "tpl_scale": 1_100_000_000.0,
                "treasury_10y": 2.2,
                "treasury_10y_change": -15.0,
                "dr007": None,
            }
        ],
    }

    promoted = _pnl_svc()._promote_payload_numerics(payload, TPLMarketCorrelationPayload)

    assert promoted["avg_treasury_10y_change"]["unit"] == "bp"
    assert promoted["avg_treasury_10y_change"]["raw"] == pytest.approx(-7.5)
    assert promoted["treasury_10y_total_change_bp"]["raw"] == pytest.approx(-15.0)
    point = promoted["data_points"][0]
    assert point["treasury_10y_change"]["unit"] == "bp"
    assert point["treasury_10y_change"]["raw"] == pytest.approx(-15.0)
    assert point["treasury_10y"]["unit"] == "pct"
    assert point["treasury_10y"]["display"] == "+2.20%"


def test_promote_helper_keeps_spread_rate_changes_in_bp():
    from backend.app.schemas.pnl_attribution import SpreadAttributionPayload

    payload = {
        "report_date": "2026-04-30",
        "start_date": "2026-03-31",
        "end_date": "2026-04-30",
        "treasury_10y_start": 1.8171,
        "treasury_10y_end": 1.7473,
        "treasury_10y_change": -6.98,
        "total_market_value": 100_000_000.0,
        "portfolio_duration": 3.0,
        "total_treasury_effect": 2_094_000.0,
        "total_spread_effect": -300_000.0,
        "total_price_change": 1_794_000.0,
        "primary_driver": "treasury",
        "interpretation": "test",
        "items": [
            {
                "category": "rate",
                "category_type": "asset",
                "market_value": 100_000_000.0,
                "duration": 3.0,
                "weight": 100.0,
                "yield_change": -4.0,
                "treasury_change": -6.98,
                "spread_change": 2.98,
                "treasury_effect": 2_094_000.0,
                "spread_effect": -894_000.0,
                "total_price_effect": 1_200_000.0,
                "treasury_contribution_pct": 174.5,
                "spread_contribution_pct": 74.5,
            }
        ],
    }

    promoted = _pnl_svc()._promote_payload_numerics(payload, SpreadAttributionPayload)

    assert promoted["treasury_10y_start"]["unit"] == "pct"
    assert promoted["treasury_10y_start"]["raw"] == pytest.approx(0.018171)
    assert promoted["treasury_10y_change"]["unit"] == "bp"
    assert promoted["treasury_10y_change"]["raw"] == pytest.approx(-6.98)
    assert promoted["treasury_10y_change"]["display"] == "-6.98 bp"
    point = promoted["items"][0]
    assert point["yield_change"]["unit"] == "bp"
    assert point["yield_change"]["raw"] == pytest.approx(-4.0)
    assert point["treasury_change"]["unit"] == "bp"
    assert point["treasury_change"]["raw"] == pytest.approx(-6.98)
    assert point["spread_change"]["unit"] == "bp"
    assert point["spread_change"]["raw"] == pytest.approx(2.98)
