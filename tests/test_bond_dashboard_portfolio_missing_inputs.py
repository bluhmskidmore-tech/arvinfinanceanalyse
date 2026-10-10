"""Portfolio read queries preserve missing yields and actual maturity dates."""

from datetime import date, timedelta
from decimal import Decimal

import duckdb
import pytest

from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
from backend.app.services import bond_dashboard_service as service

pytestmark = pytest.mark.unit
REPORT_DATE = "2026-03-31"


def _seed(tmp_path, positions):
    path = str(tmp_path / "portfolio-missing-inputs.duckdb")
    with duckdb.connect(path) as conn:
        conn.execute(
            """
            create table fact_formal_bond_analytics_daily (
                report_date date, portfolio_name varchar, asset_class_std varchar,
                instrument_code varchar, bond_type varchar,
                maturity_date date, years_to_maturity decimal(18, 8),
                market_value decimal(18, 2), face_value decimal(18, 2),
                ytm decimal(18, 8), modified_duration decimal(18, 8),
                amortized_cost decimal(18, 2), accrued_interest decimal(18, 2),
                coupon_rate decimal(18, 8), dv01 decimal(18, 8),
                is_credit boolean, convexity decimal(18, 8),
                spread_dv01 decimal(18, 8)
            )
            """
        )
        for position in positions:
            row = {
                "report_date": REPORT_DATE,
                "portfolio_name": "P1",
                "asset_class_std": "rate",
                "instrument_code": "BOND-1",
                "bond_type": "国债",
                "maturity_date": date(2031, 3, 31),
                "years_to_maturity": Decimal("5"),
                "market_value": Decimal("100"),
                "face_value": Decimal("100"),
                "ytm": Decimal("0.04"),
                "modified_duration": Decimal("4"),
                "amortized_cost": Decimal("100"),
                "accrued_interest": Decimal("0"),
                "coupon_rate": Decimal("0.04"),
                "dv01": Decimal("0.04"),
                "is_credit": False,
                "convexity": Decimal("20"),
                "spread_dv01": Decimal("0"),
                **position,
            }
            conn.execute(
                f"insert into fact_formal_bond_analytics_daily ({', '.join(row)}) "
                f"values ({', '.join('?' for _ in row)})",
                list(row.values()),
            )
    return BondAnalyticsRepository(path)


@pytest.mark.parametrize(
    ("yields", "expected"),
    [
        ([Decimal("0.04"), None], 0.04),
        ([Decimal("0.04"), None, Decimal("0"), Decimal("-0.01")], 0.01),
        ([None, None], None),
    ],
)
def test_headline_and_portfolio_yield_use_only_observed_ytm(tmp_path, yields, expected):
    # Missing YTM may coexist with positive proxy duration from par assumptions.
    repo = _seed(tmp_path, [{"ytm": ytm} for ytm in yields])

    headline = repo.fetch_dashboard_headline_kpis(REPORT_DATE)["current"]
    portfolio = repo.fetch_dashboard_portfolio_comparison(REPORT_DATE)[0]

    for row in (headline, portfolio):
        if expected is None:
            assert row["weighted_ytm"] is None
        else:
            assert float(row["weighted_ytm"]) == pytest.approx(expected)
        assert float(row["weighted_duration"]) == pytest.approx(4)
        assert row["total_market_value"] == Decimal("100") * len(yields)
        assert float(row["weighted_ytm_coverage_ratio"]) == pytest.approx(
            sum(ytm is not None for ytm in yields) / len(yields)
        )


def test_missing_ytm_stays_null_in_all_dashboard_payloads(tmp_path, monkeypatch):
    repo = _seed(tmp_path, [{"ytm": None}])
    monkeypatch.setattr(service, "_repo", lambda: repo)

    headline = service._kpi_block_from_row(repo.fetch_dashboard_headline_kpis(REPORT_DATE)["current"])
    distribution = service._bond_dashboard_yield_distribution_payload(REPORT_DATE)
    portfolio = service._bond_dashboard_portfolio_payload(REPORT_DATE)["items"][0]

    for payload in (headline, distribution, portfolio):
        assert payload["weighted_ytm"]["raw"] is None
        assert payload["weighted_ytm"]["display"] == "—"


def test_ytm_coverage_uses_absolute_market_value_while_yield_keeps_signed_weighting(tmp_path):
    repo = _seed(
        tmp_path,
        [
            {"market_value": Decimal("100"), "ytm": Decimal("0.04")},
            {"market_value": Decimal("-50"), "ytm": Decimal("0.02")},
            {"market_value": Decimal("50"), "ytm": None},
        ],
    )

    headline = repo.fetch_dashboard_headline_kpis(REPORT_DATE)["current"]
    comparison = repo.fetch_dashboard_portfolio_comparison(REPORT_DATE)[0]

    for row in (headline, comparison):
        assert float(row["weighted_ytm"]) == pytest.approx(0.06)
        assert float(row["weighted_ytm_coverage_ratio"]) == pytest.approx(0.75)
        assert float(row["weighted_duration"]) == pytest.approx(4)


@pytest.mark.parametrize(
    ("yields", "expected_quality"),
    [
        ([Decimal("0.04"), None], "warning"),
        ([None], "warning"),
        ([Decimal("0"), Decimal("-0.01")], "ok"),
    ],
)
def test_ytm_coverage_is_disclosed_in_payloads_and_home_quality(
    tmp_path, monkeypatch, yields, expected_quality
):
    repo = _seed(tmp_path, [{"ytm": ytm} for ytm in yields])
    monkeypatch.setattr(service, "_repo", lambda: repo)
    headline = service._bond_dashboard_headline_payload(
        REPORT_DATE, None, repo.fetch_dashboard_headline_kpis(REPORT_DATE)
    )
    comparison = service._bond_dashboard_portfolio_payload(REPORT_DATE)
    distribution = service._bond_dashboard_yield_distribution_payload(REPORT_DATE)
    lineage = {"cache_version": "cv_test", "source_version": "sv_test", "rule_version": "rv_test"}
    coverage = sum(ytm is not None for ytm in yields) / len(yields)
    for metric in (headline["kpis"], comparison["items"][0], distribution):
        assert metric["weighted_ytm_coverage_ratio"]["raw"] == pytest.approx(coverage)
        assert metric["weighted_ytm_coverage_ratio"]["unit"] == "ratio"
    for payload in (headline, comparison, distribution):
        envelope = service._analytical_envelope_from_lineage(
            result_kind="bond_dashboard.test", report_date=REPORT_DATE,
            lineage=lineage, evidence_rows=len(yields), result_payload=payload,
        )
        assert envelope["result_meta"]["quality_flag"] == expected_quality
        assert envelope["result_meta"]["formal_use_allowed"] is False
    monkeypatch.setattr(
        service, "_bond_dashboard_home_summary_components",
        lambda _rd: ({"headline": headline, "portfolio_comparison": comparison}, lineage, len(yields)),
    )
    home = service.get_bond_dashboard_home_summary(date.fromisoformat(REPORT_DATE))
    assert home["result_meta"]["quality_flag"] == expected_quality
    assert home["result_meta"]["rule_version"] == "rv_test"


@pytest.mark.parametrize("observed_ytm", [Decimal("0.04"), None])
def test_bundle_keeps_partial_yield_coverage_and_warning_in_all_read_sections(tmp_path, monkeypatch, observed_ytm):
    repo = _seed(tmp_path, [{"ytm": observed_ytm}, {"ytm": None}])
    original_fetch = repo.fetch_dashboard_headline_kpis
    headline_reads = []

    def counted_headline(_self, *args, **kwargs):
        headline_reads.append(args[0])
        return original_fetch(*args, **kwargs)

    monkeypatch.setattr(type(repo), "fetch_dashboard_headline_kpis", counted_headline)
    monkeypatch.setattr(service, "_repo", lambda: repo)
    monkeypatch.setattr(service, "_prior_report_date", lambda _rd: None)
    monkeypatch.setattr(service, "_fact_rows", lambda _rd: [{}, {}])
    monkeypatch.setattr(
        service, "_facts_lineage",
        lambda _rd, _rows: {"cache_version": "cv_test", "source_version": "sv_test", "rule_version": "rv_test"},
    )

    bundle = service.get_bond_dashboard_bundle(
        report_date=date.fromisoformat(REPORT_DATE),
        sections=["headline-kpis", "yield-distribution", "portfolio-comparison"],
    )

    assert bundle["result"]["failed_sections"] == []
    assert headline_reads == [REPORT_DATE]
    assert bundle["result_meta"]["quality_flag"] == "warning"
    for section in bundle["result"]["sections"].values():
        assert section["result_meta"]["quality_flag"] == "warning"
    sections = bundle["result"]["sections"]
    for metric in (
        sections["headline-kpis"]["result"]["kpis"],
        sections["yield-distribution"]["result"],
        sections["portfolio-comparison"]["result"]["items"][0],
    ):
        if observed_ytm is None:
            assert metric["weighted_ytm"]["raw"] is None
            assert metric["weighted_ytm_coverage_ratio"]["raw"] == 0
        else:
            assert metric["weighted_ytm"]["raw"] == pytest.approx(0.04)
            assert metric["weighted_ytm_coverage_ratio"]["raw"] == pytest.approx(0.5)


def test_unknown_or_elapsed_maturity_is_disclosed_outside_future_buckets(tmp_path, monkeypatch):
    repo = _seed(
        tmp_path,
        [
            {"instrument_code": "SA123", "bond_type": "其他", "asset_class_std": "other",
             "maturity_date": None, "years_to_maturity": Decimal("0")},
            {"maturity_date": None, "years_to_maturity": Decimal("5")},
            {"maturity_date": date(2026, 3, 30), "years_to_maturity": Decimal("0")},
            {"maturity_date": date(2026, 3, 31), "years_to_maturity": Decimal("0")},
            {},
        ],
    )
    monkeypatch.setattr(service, "_repo", lambda: repo)

    payload = service._bond_dashboard_maturity_payload(REPORT_DATE)
    buckets = {row["maturity_bucket"]: row for row in payload["items"]}
    risk = repo.fetch_dashboard_risk_indicators(REPORT_DATE)

    assert "7天内" not in buckets
    assert buckets["基金未列到期日"]["bond_count"] == 1
    assert buckets["到期日未知"]["bond_count"] == 1
    assert buckets["已到期仍有余额"]["bond_count"] == 2
    assert buckets["基金未列到期日"]["total_market_value"]["raw"] == 100
    assert buckets["到期日未知"]["percentage"]["raw"] == pytest.approx(0.2)
    assert payload["total_market_value"]["raw"] == 500
    assert float(risk["reinvestment_ratio_1y"]) == 0


def test_maturity_buckets_and_reinvestment_use_exact_calendar_day_boundaries(tmp_path):
    # Stale years_to_maturity values must not override the known maturity date.
    maturity_days = [1, 7, 8, 30, 31, 90, 91, 365, 366, 1095, 1096, 1825, 1826]
    report_day = date.fromisoformat(REPORT_DATE)
    repo = _seed(
        tmp_path,
        [
            {"maturity_date": report_day + timedelta(days=days), "years_to_maturity": Decimal("0")}
            for days in maturity_days
        ],
    )

    rows = repo.fetch_dashboard_maturity_structure(REPORT_DATE)

    assert [(row["maturity_bucket"], row["bond_count"]) for row in rows] == [
        ("7天内", 2),
        ("8-30天", 2),
        ("31-90天", 2),
        ("91天-1年", 2),
        ("1-3年", 2),
        ("3-5年", 2),
        ("5年以上", 1),
    ]
    assert float(repo.fetch_dashboard_risk_indicators(REPORT_DATE)["reinvestment_ratio_1y"]) == pytest.approx(8 / 13)
