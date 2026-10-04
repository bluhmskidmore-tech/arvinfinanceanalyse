"""W3.2 verification: pnl_attribution_service envelopes construct
explicit Numeric-dicts at the service layer; the schema coerce
validator is defense-in-depth, not the live code path."""
from __future__ import annotations

import importlib
import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

NUMERIC_KEYS = {"raw", "unit", "display", "precision", "sign_aware"}


def _pnl_svc():
    """Resolve at call time so tests stay aligned if other suites reload the module."""
    return importlib.import_module("backend.app.services.pnl_attribution_service")


def _strip_exact_sidecar_and_runtime_ids(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: _strip_exact_sidecar_and_runtime_ids(v)
            for k, v in value.items()
            if k not in {"generated_at", "raw_text", "trace_id"}
        }
    if isinstance(value, list):
        return [_strip_exact_sidecar_and_runtime_ids(item) for item in value]
    return value


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

    def require_current_formal_pnl_rule_version(self, *, year: int, as_of_date: str) -> None:
        assert year == 2026
        assert as_of_date in self.rows_by_date

    def count_untraced_formal_fi_rows_for_dates(self, report_dates: list[str]) -> dict[str, int]:
        return {report_date: 0 for report_date in report_dates}

    def fetch_by_business_rows(self, report_date: str) -> list[dict[str, Any]]:
        raise AssertionError(
            f"attribution must reuse pnl_by_business_envelope, not fetch_by_business_rows({report_date}) directly"
        )

    def fetch_by_business_summary_rows(self, report_date: str) -> list[dict[str, Any]]:
        return list(self.rows_by_date.get(report_date, []))

    def fetch_tpl_pnl_summary(self, report_date: str) -> dict[str, Any]:
        return {
            "tpl_fair_value_change": 1.0,
            "tpl_total_pnl": 2.0,
            "row_count": 1 if report_date in self.rows_by_date else 0,
        }

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


class _BatchSummaryRepo(_BusinessRepo):
    def __init__(self) -> None:
        super().__init__()
        self.business_batch_calls: list[tuple[str, ...]] = []
        self.tpl_batch_calls: list[tuple[str, ...]] = []

    def fetch_by_business_summary_rows(self, report_date: str) -> list[dict[str, Any]]:
        raise AssertionError(f"summary volume-rate path must batch business rows, got {report_date}")

    def fetch_by_business_summary_rows_by_report_date(
        self,
        report_dates: list[str],
    ) -> dict[str, list[dict[str, Any]]]:
        self.business_batch_calls.append(tuple(report_dates))
        return {report_date: list(self.rows_by_date.get(report_date, [])) for report_date in report_dates}

    def fetch_tpl_pnl_summary(self, report_date: str) -> dict[str, Any]:
        raise AssertionError(f"summary TPL market path must batch monthly reads, got {report_date}")

    def fetch_tpl_pnl_summary_by_report_date(self, report_dates: list[str]) -> dict[str, dict[str, Any]]:
        self.tpl_batch_calls.append(tuple(report_dates))
        return {
            report_date: {
                "tpl_fair_value_change": 1.0,
                "tpl_total_pnl": 2.0,
                "row_count": 1,
            }
            for report_date in report_dates
        }


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


class _TplMarketExactPnlRepo:
    def list_formal_fi_report_dates(self) -> list[str]:
        return ["2026-04-30", "2026-03-31"]

    def fetch_formal_fi_rows(self, report_date: str, *_args, **_kwargs) -> list[dict[str, Any]]:
        rows_by_date = {
            "2026-03-31": [
                {
                    "report_date": report_date,
                    "instrument_code": "TPL-EXACT-1",
                    "accounting_basis": "FVTPL",
                    "fair_value_change_516": "100500000.005",
                    "total_pnl": Decimal("100500000.015"),
                },
                {
                    "report_date": report_date,
                    "instrument_code": "AC-IGNORED",
                    "accounting_basis": "AC",
                    "fair_value_change_516": "999999999.99",
                    "total_pnl": "999999999.99",
                },
            ],
            "2026-04-30": [
                {
                    "report_date": report_date,
                    "instrument_code": "TPL-EXACT-2",
                    "accounting_basis": "FVTPL",
                    "fair_value_change_516": Decimal("-0.005"),
                    "total_pnl": "0.00",
                }
            ],
        }
        return rows_by_date.get(report_date, [])


class _TplMarketExactLegacyFloatPnlRepo:
    def list_formal_fi_report_dates(self) -> list[str]:
        return _TplMarketExactPnlRepo().list_formal_fi_report_dates()

    def fetch_formal_fi_rows(self, report_date: str, *_args, **_kwargs) -> list[dict[str, Any]]:
        rows = _TplMarketExactPnlRepo().fetch_formal_fi_rows(report_date, *_args, **_kwargs)
        converted: list[dict[str, Any]] = []
        for row in rows:
            copied = dict(row)
            for field_name in ("fair_value_change_516", "total_pnl"):
                value = copied.get(field_name)
                if isinstance(value, (Decimal, str)):
                    copied[field_name] = float(value)
            converted.append(copied)
        return converted


class _TplMarketMixedPnlRepo:
    def list_formal_fi_report_dates(self) -> list[str]:
        return ["2026-04-30", "2026-03-31"]

    def fetch_formal_fi_rows(self, report_date: str, *_args, **_kwargs) -> list[dict[str, Any]]:
        rows_by_date = {
            "2026-03-31": [
                {
                    "report_date": report_date,
                    "instrument_code": "TPL-MIXED-1",
                    "accounting_basis": "FVTPL",
                    "fair_value_change_516": "100500000.005",
                    "total_pnl": "100500000.015",
                }
            ],
            "2026-04-30": [
                {
                    "report_date": report_date,
                    "instrument_code": "TPL-MIXED-2",
                    "accounting_basis": "FVTPL",
                    "fair_value_change_516": -0.005,
                    "total_pnl": 0.0,
                }
            ],
        }
        return rows_by_date.get(report_date, [])


class _TplMarketNonFinitePnlRepo(_TplMarketPnlRepo):
    def fetch_formal_fi_rows(self, report_date: str, *_args, **_kwargs) -> list[dict[str, Any]]:
        rows = super().fetch_formal_fi_rows(report_date, *_args, **_kwargs)
        if report_date == "2026-03-31":
            rows[0]["fair_value_change_516"] = float("nan")
        return rows


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


class _TplMarketChoiceMacroRepo:
    def dr007_on_or_before(self, trade_date: str, *, conn=None) -> tuple[float | None, str | None]:
        return (
            {
                "2026-03-31": 1.50,
                "2026-04-30": 1.40,
            }.get(trade_date),
            {
                "2026-03-31": "2026-03-29",
                "2026-04-30": "2026-04-30",
            }.get(trade_date),
        )


class _EmptyChoiceMacroRepo:
    def dr007_on_or_before(self, *_args, **_kwargs) -> tuple[None, None]:
        return None, None

    def dr007_on_or_before_many(self, *_args, **_kwargs) -> dict[str, tuple[None, None]]:
        return {}


class _BatchSummaryChoiceMacroRepo:
    def dr007_on_or_before(self, *_args, **_kwargs) -> tuple[float | None, str | None]:
        raise AssertionError("summary TPL market path must batch DR007 reads")

    def dr007_on_or_before_many(
        self,
        trade_dates: list[str],
        *,
        conn=None,
    ) -> dict[str, tuple[float | None, str | None]]:
        return {trade_date: (1.5, trade_date) for trade_date in trade_dates}


class _BatchSummaryCurveRepo:
    path = "unused.duckdb"

    def __init__(self) -> None:
        self.batch_calls: list[tuple[str, str, tuple[str, ...]]] = []

    def fetch_tenor_on_or_before_many(
        self,
        *,
        curve_type: str,
        tenor: str,
        trade_dates: list[str],
    ) -> dict[str, tuple[float | None, str | None]]:
        self.batch_calls.append((curve_type, tenor, tuple(trade_dates)))
        return {trade_date: (2.0, trade_date) for trade_date in trade_dates}


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


class _MonthEndCurveFallbackRepo:
    def list_report_dates(self) -> list[str]:
        return ["2026-06-30", "2026-05-31"]

    def fetch_bond_analytics_rows(self, *, report_date: str) -> list[dict[str, Any]]:
        return [
            {
                "report_date": report_date,
                "instrument_code": "BOND-1",
                "accounting_class": "FVOCI",
                "currency_code": "CNY",
                "asset_class_std": "rate",
                "tenor_bucket": "5Y",
                "market_value": 100_000_000.0,
                "coupon_rate": 0.03,
                "ytm": 0.03 if report_date == "2026-06-30" else 0.029,
                "macaulay_duration": 5.1,
                "modified_duration": 5.0,
                "convexity": 20.0,
                "years_to_maturity": 5.0,
                "maturity_date": "2031-06-30",
                "dv01": 50_000.0,
            }
        ]

    def fetch_curve(self, trade_date: str, curve_type: str) -> dict[str, Decimal]:
        assert curve_type == "treasury"
        return {
            "2026-05-29": {"5Y": Decimal("1.709"), "10Y": Decimal("1.709")},
            "2026-06-30": {"5Y": Decimal("1.733"), "10Y": Decimal("1.733")},
        }.get(trade_date, {})

    def fetch_latest_trade_date_on_or_before(self, curve_type: str, trade_date: str) -> str | None:
        assert curve_type == "treasury"
        return {
            "2026-05-31": "2026-05-29",
            "2026-06-30": "2026-06-30",
        }.get(trade_date)


class _ExactCurveMaturityGapRepo:
    def list_report_dates(self) -> list[str]:
        return ["2026-07-31", "2026-06-30"]

    def fetch_bond_analytics_rows(self, *, report_date: str) -> list[dict[str, Any]]:
        valid_row = {
            "report_date": report_date,
            "instrument_code": "VALID-BOND",
            "asset_class_std": "rate",
            "tenor_bucket": "5Y",
            "market_value": 60_000_000.0,
            "coupon_rate": 0.03,
            "ytm": 0.03 if report_date == "2026-07-31" else 0.029,
            "macaulay_duration": 4.1,
            "modified_duration": 4.0,
            "convexity": 16.0,
            "years_to_maturity": 4.0,
            "maturity_date": "2030-07-31",
            "dv01": 24_000.0,
        }
        if report_date != "2026-07-31":
            return [valid_row]
        return [
            valid_row,
            {
                **valid_row,
                "instrument_code": "MISSING-MATURITY",
                "market_value": 30_000_000.0,
                "ytm": None,
                "macaulay_duration": 0.0,
                "modified_duration": 0.0,
                "convexity": 0.0,
                "years_to_maturity": 0.0,
                "maturity_date": None,
                "dv01": 0.0,
            },
            {
                **valid_row,
                "instrument_code": "MATURED-BUT-HELD",
                "market_value": 10_000_000.0,
                "ytm": None,
                "macaulay_duration": 0.0,
                "modified_duration": 0.0,
                "convexity": 0.0,
                "years_to_maturity": 0.0,
                "maturity_date": "2026-07-30",
                "dv01": 0.0,
            },
            {
                **valid_row,
                "instrument_code": "NONPOSITIVE-DURATION",
                "market_value": 5_000_000.0,
                "ytm": 0.025,
                "macaulay_duration": 0.0,
                "modified_duration": 0.0,
                "convexity": 0.0,
                "years_to_maturity": 2.0,
                "maturity_date": "2028-07-31",
                "dv01": 0.0,
            },
        ]

    def fetch_curve(self, trade_date: str, curve_type: str) -> dict[str, Decimal]:
        assert curve_type == "treasury"
        return {
            "2026-06-30": {"10Y": Decimal("1.70")},
            "2026-07-31": {"10Y": Decimal("1.75")},
        }.get(trade_date, {})

    def fetch_latest_trade_date_on_or_before(self, *_args, **_kwargs) -> str | None:
        raise AssertionError("exact curve dates must not use fallback lookup")


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
    monkeypatch.setattr(
        mod,
        "resolve_formal_manifest_lineage_with_completed_build",
        lambda **kwargs: _by_business_envelope(kwargs["report_date"])["result_meta"],
    )


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
    monkeypatch.setattr(mod, "_choice_macro_repo", lambda _path=None: _TplMarketChoiceMacroRepo())

    env = mod.tpl_market_correlation_envelope(months=2, report_date="2026-04-30")
    points = env["result"]["data_points"]

    assert [point["period"] for point in points] == ["2026-03", "2026-04"]
    assert points[0]["treasury_10y"]["raw"] == pytest.approx(0.02)
    assert points[0]["treasury_10y_change"]["raw"] == pytest.approx(10.0)
    assert points[1]["treasury_10y_change"]["raw"] == pytest.approx(30.0)
    assert points[0]["dr007"]["raw"] == pytest.approx(0.015)
    assert points[1]["dr007"]["raw"] == pytest.approx(0.014)


def test_tpl_market_envelope_preserves_lossless_raw_text_for_exact_amounts(monkeypatch: pytest.MonkeyPatch):
    mod = _pnl_svc()
    monkeypatch.setattr(mod, "_pnl_repo", lambda: _TplMarketExactPnlRepo())
    monkeypatch.setattr(mod, "_bond_repo", lambda: _TplMarketBondRepo())
    monkeypatch.setattr(mod, "_curve_repo", lambda: _TplMarketCurveRepo())
    monkeypatch.setattr(mod, "_choice_macro_repo", lambda _path=None: _TplMarketChoiceMacroRepo())

    env = mod.tpl_market_correlation_envelope(months=2, report_date="2026-04-30")
    result = env["result"]
    points = result["data_points"]

    assert result["total_tpl_fv_change"]["raw"] == pytest.approx(100_500_000.0)
    assert result["total_tpl_fv_change"]["raw_text"] == "100500000.000"
    assert result["total_tpl_fv_change"]["display"] == "+100,500,000.00"
    assert points[0]["tpl_fair_value_change"]["raw"] == pytest.approx(100_500_000.005)
    assert points[0]["tpl_fair_value_change"]["raw_text"] == "100500000.005"
    assert points[0]["tpl_total_pnl"]["raw_text"] == "100500000.015"
    assert points[1]["tpl_fair_value_change"]["raw_text"] == "-0.005"


def test_tpl_market_exact_sidecar_only_adds_raw_text_without_changing_legacy_payload(
    monkeypatch: pytest.MonkeyPatch,
):
    mod = _pnl_svc()
    monkeypatch.setattr(mod, "_pnl_repo", lambda: _TplMarketExactPnlRepo())
    monkeypatch.setattr(mod, "_bond_repo", lambda: _TplMarketBondRepo())
    monkeypatch.setattr(mod, "_curve_repo", lambda: _TplMarketCurveRepo())
    monkeypatch.setattr(mod, "_choice_macro_repo", lambda _path=None: _TplMarketChoiceMacroRepo())
    exact_env = mod.tpl_market_correlation_envelope(months=2, report_date="2026-04-30")

    monkeypatch.setattr(mod, "_pnl_repo", lambda: _TplMarketExactLegacyFloatPnlRepo())
    legacy_env = mod.tpl_market_correlation_envelope(months=2, report_date="2026-04-30")

    assert _strip_exact_sidecar_and_runtime_ids(exact_env) == _strip_exact_sidecar_and_runtime_ids(
        legacy_env
    )

    exact_total = Decimal(exact_env["result"]["total_tpl_fv_change"]["raw_text"])
    month_sum = sum(
        Decimal(point["tpl_fair_value_change"]["raw_text"])
        for point in exact_env["result"]["data_points"]
    )
    assert exact_total == month_sum


def test_tpl_market_envelope_keeps_legacy_raw_only_amounts_without_raw_text(monkeypatch: pytest.MonkeyPatch):
    mod = _pnl_svc()
    monkeypatch.setattr(mod, "_pnl_repo", lambda: _TplMarketPnlRepo())
    monkeypatch.setattr(mod, "_bond_repo", lambda: _TplMarketBondRepo())
    monkeypatch.setattr(mod, "_curve_repo", lambda: _TplMarketCurveRepo())
    monkeypatch.setattr(mod, "_choice_macro_repo", lambda _path=None: _TplMarketChoiceMacroRepo())

    env = mod.tpl_market_correlation_envelope(months=2, report_date="2026-04-30")
    result = env["result"]

    assert "raw_text" not in result["total_tpl_fv_change"]
    assert "raw_text" not in result["data_points"][0]["tpl_fair_value_change"]


def test_tpl_market_envelope_does_not_claim_exact_raw_text_for_mixed_exact_and_float_inputs(
    monkeypatch: pytest.MonkeyPatch,
):
    mod = _pnl_svc()
    monkeypatch.setattr(mod, "_pnl_repo", lambda: _TplMarketMixedPnlRepo())
    monkeypatch.setattr(mod, "_bond_repo", lambda: _TplMarketBondRepo())
    monkeypatch.setattr(mod, "_curve_repo", lambda: _TplMarketCurveRepo())
    monkeypatch.setattr(mod, "_choice_macro_repo", lambda _path=None: _TplMarketChoiceMacroRepo())

    env = mod.tpl_market_correlation_envelope(months=2, report_date="2026-04-30")
    result = env["result"]

    assert "raw_text" not in result["total_tpl_fv_change"]
    assert result["data_points"][0]["tpl_fair_value_change"]["raw_text"] == "100500000.005"
    assert "raw_text" not in result["data_points"][1]["tpl_fair_value_change"]


def test_tpl_market_amount_sum_helper_keeps_legacy_or_zero_semantics():
    mod = _pnl_svc()
    rows = [
        {"accounting_basis": "FVTPL", "fair_value_change_516": True},
        {"accounting_basis": "FVTPL", "fair_value_change_516": None},
        {"accounting_basis": "FVTPL", "fair_value_change_516": ""},
        {"accounting_basis": "FVTPL", "fair_value_change_516": Decimal("2.5")},
        {"accounting_basis": "AC", "fair_value_change_516": Decimal("999.0")},
    ]

    assert mod._sum_tpl_accounting_amount(rows, "fair_value_change_516") == pytest.approx(3.5)


def test_tpl_market_amount_sum_helper_propagates_nan():
    mod = _pnl_svc()
    rows = [
        {"accounting_basis": "FVTPL", "fair_value_change_516": 1.0},
        {"accounting_basis": "FVTPL", "fair_value_change_516": float("nan")},
    ]

    assert math.isnan(mod._sum_tpl_accounting_amount(rows, "fair_value_change_516"))


def test_tpl_market_non_finite_amount_nulls_total_and_warns(monkeypatch: pytest.MonkeyPatch):
    mod = _pnl_svc()
    monkeypatch.setattr(mod, "_pnl_repo", lambda: _TplMarketNonFinitePnlRepo())
    monkeypatch.setattr(mod, "_bond_repo", lambda: _TplMarketBondRepo())
    monkeypatch.setattr(mod, "_curve_repo", lambda: _TplMarketCurveRepo())
    monkeypatch.setattr(mod, "_choice_macro_repo", lambda _path=None: _TplMarketChoiceMacroRepo())

    env = mod.tpl_market_correlation_envelope(months=2, report_date="2026-04-30")

    assert env["result"]["total_tpl_fv_change"]["raw"] is None
    assert env["result"]["correlation_coefficient"] is None
    assert env["result_meta"]["quality_flag"] == "warning"
    assert mod.TPL_NON_FINITE_PNL_WARN in env["result"]["warnings"]


def test_tpl_market_amount_sum_helper_propagates_inf():
    mod = _pnl_svc()
    rows = [
        {"accounting_basis": "FVTPL", "fair_value_change_516": float("inf")},
    ]

    assert math.isinf(mod._sum_tpl_accounting_amount(rows, "fair_value_change_516"))


def test_tpl_market_amount_sum_helper_raises_on_invalid_legacy_value():
    mod = _pnl_svc()
    rows = [
        {"accounting_basis": "FVTPL", "fair_value_change_516": "abc"},
    ]

    with pytest.raises(ValueError):
        mod._sum_tpl_accounting_amount(rows, "fair_value_change_516")


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        (None, None),
        ("", None),
        (True, None),
        (0.0, None),
        (1, None),
        (float("nan"), None),
        (float("inf"), None),
        ("abc", None),
        ("1e3", None),
        ("100500000.005", "100500000.005"),
        (Decimal("100500000.005"), "100500000.005"),
    ],
)
def test_tpl_market_exact_sidecar_is_fail_closed_by_input_shape(raw_value: Any, expected: str | None):
    mod = _pnl_svc()
    rows = [{"accounting_basis": "FVTPL", "fair_value_change_516": raw_value}]

    assert mod._sum_tpl_accounting_exact_amount_text(rows, "fair_value_change_516") == expected


def test_tpl_market_exact_sidecar_rejects_mixed_exact_and_legacy_rows():
    mod = _pnl_svc()
    rows = [
        {"accounting_basis": "FVTPL", "fair_value_change_516": "100500000.005"},
        {"accounting_basis": "FVTPL", "fair_value_change_516": 0.0},
    ]

    assert mod._sum_tpl_accounting_exact_amount_text(rows, "fair_value_change_516") is None


def test_tpl_market_exact_sidecar_large_decimal_sum_keeps_all_fractional_digits():
    mod = _pnl_svc()
    repeated_value = Decimal("9999999999999999.99999999")
    rows = [
        {"accounting_basis": "FVTPL", "fair_value_change_516": repeated_value}
        for _ in range(10001)
    ]
    expected = "100009999999999999999.99989999"

    assert mod._sum_tpl_accounting_exact_amount_text(rows, "fair_value_change_516") == expected
    assert mod._sum_exact_decimal_texts([repeated_value] * 10001) == expected


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
    assert result["total_volume_effect"]["raw"] == pytest.approx(17.5)
    assert result["total_rate_effect"]["raw"] == pytest.approx(10.0)
    assert result["total_interaction_effect"]["raw"] == pytest.approx(2.5)
    assert result["total_fair_value_effect"]["raw"] == pytest.approx(7.0)
    assert result["total_capital_gain_effect"]["raw"] == pytest.approx(3.0)
    assert result["attribution_basis"] == "interest_income_and_direct_pnl"
    assert result["total_recon_error"]["raw"] == pytest.approx(0.0)
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


def test_attribution_analysis_summary_envelope_uses_fast_summary_path(monkeypatch: pytest.MonkeyPatch):
    mod = _pnl_svc()
    monkeypatch.setattr(mod, "_pnl_repo", lambda: _SummaryRepo())
    monkeypatch.setattr(mod, "_bond_repo", lambda: _EmptyRepo())
    monkeypatch.setattr(mod, "_curve_repo", lambda: _EmptyRepo())

    def fake_by_business_envelope(*, duckdb_path: str, governance_dir: str, report_date: str) -> dict[str, Any]:
        return _by_business_envelope(report_date)

    def fail_full_volume_rate(*_args, **_kwargs):
        raise AssertionError("summary must not build the full volume-rate workbench payload")

    def fail_full_tpl_market(*_args, **_kwargs):
        raise AssertionError("summary must not build the full TPL-market workbench payload")

    monkeypatch.setattr(mod.pnl_service, "pnl_by_business_envelope", fake_by_business_envelope)
    monkeypatch.setattr(mod, "volume_rate_attribution_envelope", fail_full_volume_rate)
    monkeypatch.setattr(mod, "tpl_market_correlation_envelope", fail_full_tpl_market)
    monkeypatch.setattr(mod, "_treasury_10y_on_or_before", lambda _repo, _date: (None, None))
    monkeypatch.setattr(mod, "_choice_macro_repo", lambda _path=None: _EmptyChoiceMacroRepo())

    env = mod.attribution_analysis_summary_envelope(report_date="2026-04-30")
    result = env["result"]
    meta = env["result_meta"]

    assert result["primary_driver"] == "volume"
    assert result["primary_driver_pct"]["raw"] == pytest.approx(0.438, rel=1e-3)
    assert result["primary_driver_pct"]["display"] == "+43.80%"
    assert meta["result_kind"] == "pnl_attribution.summary"
    assert meta["as_of_date"] == "2026-04-30"
    assert meta["evidence_rows"] > 0


def test_attribution_analysis_summary_envelope_batches_tpl_market_reads(monkeypatch: pytest.MonkeyPatch):
    mod = _pnl_svc()
    repo = _BatchSummaryRepo()
    curve = _BatchSummaryCurveRepo()
    monkeypatch.setattr(mod, "_pnl_repo", lambda: repo)
    monkeypatch.setattr(mod, "_bond_repo", lambda: _EmptyRepo())
    monkeypatch.setattr(mod, "_curve_repo", lambda: curve)

    def fake_by_business_envelope(*, duckdb_path: str, governance_dir: str, report_date: str) -> dict[str, Any]:
        return _by_business_envelope(report_date)

    def fail_single_curve(*_args, **_kwargs):
        raise AssertionError("summary TPL market path must batch treasury reads")

    monkeypatch.setattr(mod.pnl_service, "pnl_by_business_envelope", fake_by_business_envelope)
    monkeypatch.setattr(mod, "_treasury_10y_on_or_before", fail_single_curve)
    monkeypatch.setattr(mod, "_choice_macro_repo", lambda _path=None: _BatchSummaryChoiceMacroRepo())

    env = mod.attribution_analysis_summary_envelope(report_date="2026-04-30")

    assert env["result"]["primary_driver"] == "volume"
    assert repo.business_batch_calls == [("2026-04-30", "2026-03-31")]
    assert repo.tpl_batch_calls == [("2026-03-31", "2026-04-30")]
    assert curve.batch_calls == [("treasury", "10Y", ("2026-03-31", "2026-04-30", "2026-02-28"))]


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


def test_spread_envelope_uses_prior_curve_snapshot_for_non_trading_month_end(
    monkeypatch: pytest.MonkeyPatch,
):
    mod = _pnl_svc()
    repo = _MonthEndCurveFallbackRepo()
    monkeypatch.setattr(mod, "_bond_repo", lambda: repo)
    monkeypatch.setattr(mod, "_curve_repo", lambda: repo)

    env = mod.spread_attribution_envelope(report_date="2026-06-30", lookback_days=30)

    assert env["result"]["total_treasury_effect"]["raw"] == pytest.approx(-120_000.0)
    assert env["result"]["total_spread_effect"]["raw"] == pytest.approx(-380_000.0)
    assert env["result_meta"]["quality_flag"] == "warning"
    assert env["result_meta"]["fallback_mode"] == "latest_snapshot"
    assert env["result_meta"]["fallback_date"] == "2026-05-29"


def test_krd_envelope_empty():
    env = _pnl_svc().krd_attribution_envelope(report_date=None, lookback_days=30)
    result = env["result"]
    for k in ("total_market_value", "portfolio_duration", "portfolio_dv01", "total_duration_effect", "max_contribution_value"):
        _assert_numeric_dict(result[k])


@pytest.mark.parametrize("missing_side", ["start", "end", "both"])
def test_krd_missing_curve_preserves_null_numeric_and_identifies_missing_side(monkeypatch, missing_side):
    mod = _pnl_svc()
    repo = _MonthEndCurveFallbackRepo()
    monkeypatch.setattr(mod, "_bond_repo", lambda: repo)
    monkeypatch.setattr(mod, "_curve_repo", lambda: repo)

    def treasury(_repo, as_of):
        side = "end" if as_of == "2026-06-30" else "start"
        return (None, None) if missing_side in {side, "both"} else (2.0, as_of)

    monkeypatch.setattr(mod, "_treasury_10y_on_or_before", treasury)
    env = mod._krd_attribution_envelope_uncached(report_date="2026-06-30", lookback_days=30)
    result = env["result"]
    assert result["total_duration_effect"]["raw"] is None
    assert result["max_contribution_value"]["raw"] is None
    assert result["max_contribution_tenor"] == ""
    assert result["buckets"][0]["duration_contribution"]["raw"] is None
    assert result["buckets"][0]["contribution_pct"]["raw"] is None
    assert result["calculation_status"] == "unavailable"
    assert env["result_meta"]["formal_use_allowed"] is False
    warnings = " ".join(result["warnings"])
    assert "期初" in warnings if missing_side in {"start", "both"} else "期末" in warnings
    assert "10Y" in warnings


def test_krd_without_eligible_risk_rows_cannot_be_used_as_formal_zero(monkeypatch):
    mod = _pnl_svc()

    class Repo(_ExactCurveMaturityGapRepo):
        def fetch_bond_analytics_rows(self, *, report_date):
            return [{**super().fetch_bond_analytics_rows(report_date=report_date)[0],
                     "maturity_date": None, "years_to_maturity": None, "modified_duration": None}]

    repo = Repo()
    monkeypatch.setattr(mod, "_bond_repo", lambda: repo)
    monkeypatch.setattr(mod, "_curve_repo", lambda: repo)
    env = mod._krd_attribution_envelope_uncached(report_date="2026-07-31", lookback_days=31)
    assert env["result"]["calculation_status"] == "unavailable"
    assert env["result"]["total_duration_effect"]["raw"] is None
    assert env["result_meta"]["formal_use_allowed"] is False


def test_krd_envelope_uses_prior_curve_snapshot_for_non_trading_month_end(
    monkeypatch: pytest.MonkeyPatch,
):
    mod = _pnl_svc()
    repo = _MonthEndCurveFallbackRepo()
    monkeypatch.setattr(mod, "_bond_repo", lambda: repo)
    monkeypatch.setattr(mod, "_curve_repo", lambda: repo)

    env = mod.krd_attribution_envelope(report_date="2026-06-30", lookback_days=30)

    assert env["result"]["total_duration_effect"]["raw"] == pytest.approx(-120_000.0)
    assert env["result"]["buckets"][0]["duration_contribution"]["raw"] == pytest.approx(-120_000.0)
    assert env["result_meta"]["quality_flag"] == "warning"
    assert env["result_meta"]["fallback_mode"] == "latest_snapshot"
    assert env["result_meta"]["fallback_date"] == "2026-05-29"


@pytest.mark.parametrize(
    "envelope_name",
    ["spread_attribution_envelope", "krd_attribution_envelope"],
)
def test_duration_risk_exclusions_warn_even_with_exact_curve_dates(
    monkeypatch: pytest.MonkeyPatch,
    envelope_name: str,
):
    mod = _pnl_svc()
    repo = _ExactCurveMaturityGapRepo()
    monkeypatch.setattr(mod, "_bond_repo", lambda: repo)
    monkeypatch.setattr(mod, "_curve_repo", lambda: repo)

    env = getattr(mod, envelope_name)(report_date="2026-07-31", lookback_days=30)

    assert env["result_meta"]["filters_applied"]["treasury_curve_start_date"] == "2026-06-30"
    assert env["result_meta"]["filters_applied"]["treasury_curve_end_date"] == "2026-07-31"
    assert env["result_meta"]["quality_flag"] == "warning"


@pytest.mark.parametrize(
    "envelope_name",
    ["spread_attribution_envelope", "krd_attribution_envelope"],
)
def test_duration_risk_coverage_uses_explicit_numeric_units(
    monkeypatch: pytest.MonkeyPatch,
    envelope_name: str,
):
    mod = _pnl_svc()
    repo = _ExactCurveMaturityGapRepo()
    monkeypatch.setattr(mod, "_bond_repo", lambda: repo)
    monkeypatch.setattr(mod, "_curve_repo", lambda: repo)

    env = getattr(mod, envelope_name)(report_date="2026-07-31", lookback_days=30)
    coverage = env["result"]["risk_coverage"]

    assert coverage["total_row_count"] == 4
    assert coverage["covered_row_count"] == 1
    assert coverage["excluded_row_count"] == 3
    for key, expected_raw in (
        ("total_market_value", 105_000_000.0),
        ("covered_market_value", 60_000_000.0),
        ("excluded_market_value", 45_000_000.0),
    ):
        _assert_numeric_dict(coverage[key])
        assert coverage[key]["unit"] == "yuan"
        assert coverage[key]["raw"] == pytest.approx(expected_raw)

    assert coverage["coverage_pct"]["unit"] == "pct"
    assert coverage["coverage_pct"]["raw"] == pytest.approx(0.571429)
    assert coverage["excluded_pct"]["unit"] == "pct"
    assert coverage["excluded_pct"]["raw"] == pytest.approx(0.428571)

    exclusions = {item["reason"]: item for item in coverage["exclusions"]}
    assert exclusions["no_maturity"]["row_count"] == 1
    assert exclusions["no_maturity"]["market_value"]["unit"] == "yuan"
    assert exclusions["no_maturity"]["market_value"]["raw"] == pytest.approx(30_000_000.0)
    assert exclusions["matured_or_expired"]["row_count"] == 1
    assert exclusions["matured_or_expired"]["market_value"]["unit"] == "yuan"
    assert exclusions["matured_or_expired"]["market_value"]["raw"] == pytest.approx(10_000_000.0)
    assert exclusions["nonpositive_duration"]["row_count"] == 1
    assert exclusions["nonpositive_duration"]["market_value"]["unit"] == "yuan"
    assert exclusions["nonpositive_duration"]["market_value"]["raw"] == pytest.approx(5_000_000.0)


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


@pytest.mark.parametrize("status", ["partial", "unavailable"])
def test_legacy_campisi_summary_keeps_position_exclusion_and_nulls_empty_subtotal(monkeypatch, status):
    mod = _pnl_svc()
    repo = _CampisiRepo()
    monkeypatch.setattr(mod, "_bond_repo", lambda: repo)
    monkeypatch.setattr(mod, "_curve_repo", lambda: repo)
    monkeypatch.setattr(mod, "_try_fetch_formal_bridge", lambda **_kwargs: None)
    monkeypatch.setattr(mod, "fetch_credit_spread_market", lambda *_args: {})
    result = _CampisiCoreResult(
        num_days=30,
        totals={
            "market_value_start": 1000 if status == "partial" else 0,
            "total_return": 10 if status == "partial" else 0,
            "income_return": 0,
            "treasury_effect": 0,
            "spread_effect": 0,
            "selection_effect": 10 if status == "partial" else 0,
        },
        by_asset_class=[],
        by_bond=[],
        diagnostics=["principal_change_without_cashflows"],
    )
    result.effect_availability = {
        "position_change": {
            "status": status,
            "unavailable_bonds": 1,
            "unavailable_market_value_start": 1000,
            "unavailable_market_value_end": 2000,
        }
    }
    monkeypatch.setattr(mod, "_core_campisi", lambda **_kwargs: result)
    env = mod._campisi_attribution_envelope_uncached(
        start_date="2026-01-01", end_date="2026-01-31", lookback_days=30
    )
    payload = env["result"]
    assert payload["effect_availability"]["position_change"]["unavailable_market_value_end"] == 2000
    assert "可归因持仓小计" in payload["interpretation"]
    assert env["result_meta"]["formal_use_allowed"] is False
    assert env["result_meta"]["rule_version"] == "rv_pnl_attribution_workbench_v4"
    assert env["result_meta"]["cache_version"] == "cv_pnl_attribution_workbench_v4"
    if status == "partial":
        assert payload["total_market_value"]["raw"] == 1000
        assert payload["total_return"]["raw"] == 10
        assert payload["total_return_pct"]["raw"] == pytest.approx(0.01)
        assert payload["primary_driver"] == "selection"
    else:
        for key in mod.CampisiAttributionPayload._NUMERIC_FIELDS:
            if key != "total_market_value":
                assert payload[key]["raw"] is None
        assert payload["primary_driver"] == "unknown"


def test_campisi_envelope_adapts_core_result(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(_pnl_svc(), "_try_fetch_formal_bridge", lambda **kwargs: None)
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


def test_promote_helper_preserves_prebuilt_tpl_numeric_dict_even_when_raw_and_raw_text_disagree():
    from backend.app.schemas.pnl_attribution import TPLMarketCorrelationPayload

    payload = {
        "start_period": "2026-03",
        "end_period": "2026-03",
        "num_periods": 1,
        "correlation_coefficient": -0.62,
        "correlation_interpretation": "test",
        "total_tpl_fv_change": {
            "raw": 42_000_000.0,
            "raw_text": "-100500000",
            "unit": "yuan",
            "display": "+42,000,000.00",
            "precision": 2,
            "sign_aware": True,
        },
        "avg_treasury_10y_change": -7.5,
        "treasury_10y_total_change_bp": -7.5,
        "analysis_summary": "summary",
        "data_points": [
            {
                "period": "2026-03",
                "period_label": "2026年03月",
                "tpl_fair_value_change": {
                    "raw": 100_400_000.0,
                    "raw_text": "100500000",
                    "unit": "yuan",
                    "display": "+100,400,000.00",
                    "precision": 2,
                    "sign_aware": True,
                },
                "tpl_total_pnl": 100_400_000.0,
                "tpl_scale": 1_100_000_000.0,
                "treasury_10y": 2.2,
                "treasury_10y_change": -7.5,
                "dr007": 1.7,
            }
        ],
    }

    promoted = _pnl_svc()._promote_payload_numerics(payload, TPLMarketCorrelationPayload)

    assert promoted["total_tpl_fv_change"]["raw"] == pytest.approx(42_000_000.0)
    assert promoted["total_tpl_fv_change"]["raw_text"] == "-100500000"
    assert promoted["data_points"][0]["tpl_fair_value_change"]["raw_text"] == "100500000"


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


def test_krd_envelope_preserves_bp_and_pct_numeric_scales(
    monkeypatch: pytest.MonkeyPatch,
):
    mod = _pnl_svc()
    repo = _MonthEndCurveFallbackRepo()
    monkeypatch.setattr(mod, "_bond_repo", lambda: repo)
    monkeypatch.setattr(mod, "_curve_repo", lambda: repo)

    env = mod.krd_attribution_envelope(report_date="2026-06-30", lookback_days=30)
    bucket = env["result"]["buckets"][0]

    assert bucket["yield_change"]["unit"] == "bp"
    assert bucket["yield_change"]["raw"] == pytest.approx(10.0)
    assert bucket["weight"]["unit"] == "pct"
    assert bucket["weight"]["raw"] == pytest.approx(1.0)


@pytest.mark.parametrize("missing_field", ["coupon_rate", "modified_duration", "years_to_maturity"])
def test_carry_missing_inputs_propagate_numeric_null_and_quality_to_summary(monkeypatch, missing_field):
    mod = _pnl_svc()
    row = {
        "asset_class_std": "rate", "market_value": 100_000_000,
        "coupon_rate": 0.03, "modified_duration": 2.0, "years_to_maturity": 5.0,
        missing_field: None,
    }

    class Repo:
        def list_report_dates(self):
            return ["2026-06-30"]

        def fetch_bond_analytics_rows(self, **kwargs):
            return [row]

        def fetch_curve(self, *args):
            return {"1Y": 1, "10Y": 2}

    monkeypatch.setattr(mod, "_bond_repo", Repo)
    monkeypatch.setattr(mod, "_curve_repo", Repo)
    env = mod._carry_roll_down_envelope_uncached(report_date="2026-06-30", ftp_rate_pct=0)
    field = "carry" if missing_field == "coupon_rate" else "rolldown"
    for value, key, unit in [
        (env["result"], f"portfolio_{field}", "pct"),
        (env["result"], f"total_{field}_pnl", "yuan"),
        (env["result"]["items"][0], field, "pct"),
        (env["result"]["items"][0], f"{field}_pnl", "yuan"),
    ]:
        _assert_numeric_dict(value[key])
        assert value[key]["raw"] is None
        assert value[key]["unit"] == unit
    assert env["result"]["warnings"]
    assert env["result_meta"]["rule_version"] == "rv_pnl_attribution_workbench_v4"
    assert env["result_meta"]["cache_version"] == "cv_pnl_attribution_workbench_v4"
    assert env["result_meta"]["quality_flag"] == "warning"
    monkeypatch.setattr(mod, "carry_roll_down_envelope", lambda **kwargs: env)
    empty = {"result_meta": {}, "result": {}}
    monkeypatch.setattr(mod, "spread_attribution_envelope", lambda **kwargs: empty)
    monkeypatch.setattr(mod, "krd_attribution_envelope", lambda **kwargs: empty)
    summary = mod._advanced_attribution_summary_envelope_uncached(report_date="2026-06-30")
    assert summary["result"][f"portfolio_{field}"]["raw"] is None
    assert summary["result"]["static_return_annualized"]["raw"] is None
    assert summary["result_meta"]["quality_flag"] == "warning"
