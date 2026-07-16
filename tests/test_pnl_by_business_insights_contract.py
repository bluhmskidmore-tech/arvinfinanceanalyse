from __future__ import annotations

import json
from decimal import Decimal
from importlib import import_module
from pathlib import Path

import pytest


_FORMAL_COMPONENT_TABLES = [
    "fact_formal_pnl_fi",
    "fact_nonstd_pnl_bridge",
    "fact_formal_zqtz_balance_daily",
    "ZQTZ_ASSET_BOND_ROWS",
]


def _governed_analytical_component_envelope(
    *,
    result_kind: str,
    report_date: str,
    tables_used: list[str] | None = None,
) -> dict[str, object]:
    return {
        "result_meta": {
            "basis": "analytical",
            "formal_use_allowed": False,
            "result_kind": result_kind,
            "trace_id": f"tr_{result_kind.replace('.', '_')}_{report_date}",
            "source_surface": "formal_pnl",
            "quality_flag": "ok",
            "requested_report_date": report_date,
            "resolved_report_date": report_date,
            "as_of_date": report_date,
            "fallback_mode": "none",
            "fallback_date": None,
            "source_version": f"sv_{report_date}",
            "rule_version": "rv_pnl_phase2_materialize_v3",
            "cache_version": "cv_pnl_formal_v3",
            "vendor_version": "vv_none",
            "vendor_status": "ok",
            "tables_used": tables_used or list(_FORMAL_COMPONENT_TABLES),
        },
        "result": {
            "period_end_date": report_date,
            "as_of_date": report_date,
            "source_tables": tables_used or list(_FORMAL_COMPONENT_TABLES),
        },
    }


def _core():
    return import_module("backend.app.core_finance.pnl_by_business_insights")


def _ytd_item(
    row_key: str,
    business_type: str,
    avg_balance: str,
    *,
    ftp_net_yield_pct: str | None = "1.00",
    proportion: str = "0.99",
) -> dict[str, object]:
    return {
        "row_key": row_key,
        "business_type": business_type,
        "avg_balance": avg_balance,
        "ftp_net_annualized_yield_pct": ftp_net_yield_pct,
        "proportion": proportion,
        "source_note": None,
    }


def _monthly_bucket(
    month_key: str,
    values: dict[str, str | None],
) -> dict[str, object]:
    return {
        "month_key": month_key,
        "summary": {"ftp_net_pnl": "1.00"},
        "items": [
            {
                "row_key": row_key,
                "business_type": row_key.upper(),
                "ftp_net_pnl": value,
                "source_note": None,
            }
            for row_key, value in values.items()
        ],
    }


def test_concentration_uses_cny_equivalent_ytd_parent_average_balance() -> None:
    result = _core().build_business_type_concentration(
        items=[
            _ytd_item("row_a", "A", "600"),
            _ytd_item("row_b", "B", "300"),
            _ytd_item("row_c", "C", "100"),
            {
                **_ytd_item("row_a_detail", "A其中项", "9000"),
                "source_note": "其中项",
            },
        ],
        year=2026,
        as_of_date="2026-06-30",
        top_n=3,
    )

    assert result["currency_basis"] == "CNY_EQUIVALENT"
    assert result["population_basis"] == "YTD_AVG_BALANCE_PARENT_ROWS"
    assert result["total_avg_balance"] == Decimal("1000")
    assert result["hhi_pct"] == Decimal("46.00")
    assert result["top_n_share_pct"] == Decimal("100.00")
    assert [row["row_key"] for row in result["rows"]] == ["row_a", "row_b", "row_c"]


def test_negative_ftp_warning_requires_six_observed_months_and_fifty_percent() -> None:
    months = {
        "2026-01": _monthly_bucket("2026-01", {"row_a": "-1", "row_b": "-1"}),
        "2026-02": _monthly_bucket("2026-02", {"row_a": "-1", "row_b": "-1"}),
        "2026-03": _monthly_bucket("2026-03", {"row_a": "1", "row_b": None}),
        "2026-04": _monthly_bucket("2026-04", {"row_a": "-1", "row_b": "-1"}),
        "2026-05": _monthly_bucket("2026-05", {"row_a": "1", "row_b": "-1"}),
        "2026-06": _monthly_bucket("2026-06", {"row_a": "1", "row_b": "1"}),
    }

    result = _core().build_negative_ftp_persistence(
        monthly_by_key=months,
        as_of_date="2026-06-30",
        lookback_months=12,
    )

    assert result["warning_threshold_pct"] == Decimal("50")
    assert result["minimum_observed_months"] == 6
    rows = {row["row_key"]: row for row in result["rows"]}
    assert rows["row_a"]["months_observed"] == 6
    assert rows["row_a"]["eligible"] is True
    assert rows["row_a"]["status"] == "eligible"
    assert rows["row_a"]["negative_ftp_month_share_pct"] == Decimal("50.00")
    assert rows["row_a"]["warning_triggered"] is True
    assert rows["row_b"]["months_observed"] == 5
    assert rows["row_b"]["eligible"] is False
    assert rows["row_b"]["status"] == "insufficient_observations"
    assert rows["row_b"]["negative_ftp_month_share_pct"] is None
    assert rows["row_b"]["negative_ftp_longest_streak_months"] is None
    assert rows["row_b"]["warning_triggered"] is False
    assert result["warning_row_count"] == 1


@pytest.mark.parametrize(
    ("months_observed", "expected_eligible"),
    [(0, False), (5, False), (6, True)],
)
def test_negative_ftp_metrics_fail_closed_at_minimum_observation_boundary(
    months_observed: int,
    expected_eligible: bool,
) -> None:
    monthly_by_key = {
        f"2026-{month:02d}": {
            "month_key": f"2026-{month:02d}",
            "summary": {"ftp_net_pnl": "-1"},
            "items": [
                {
                    "row_key": "row_a",
                    "business_type": "A",
                    "ftp_net_pnl": "-1",
                    "source_note": None,
                }
            ],
        }
        for month in range(1, months_observed + 1)
    }

    result = _core().build_negative_ftp_persistence(
        monthly_by_key=monthly_by_key,
        as_of_date="2026-06-30",
        lookback_months=6,
    )

    assert result["months_observed"] == months_observed
    assert result["eligible"] is expected_eligible
    assert result["status"] == (
        "eligible" if expected_eligible else "insufficient_observations"
    )
    assert result["negative_ftp_month_share_pct"] == (
        Decimal("100.00") if expected_eligible else None
    )
    assert result["negative_ftp_longest_streak_months"] == (
        months_observed if expected_eligible else None
    )
    if months_observed:
        row = result["rows"][0]
        assert row["eligible"] is expected_eligible
        assert row["negative_ftp_month_share_pct"] == (
            Decimal("100.00") if expected_eligible else None
        )
        assert row["negative_ftp_longest_streak_months"] == (
            months_observed if expected_eligible else None
        )


def test_share_drift_uses_prior_year_same_period_and_zero_for_new_or_exited_rows() -> (
    None
):
    current = {
        "total_avg_balance": Decimal("100"),
        "rows": [
            {"row_key": "row_a", "business_type": "A", "avg_balance": Decimal("60")},
            {"row_key": "row_b", "business_type": "B", "avg_balance": Decimal("40")},
        ],
    }
    baseline = {
        "total_avg_balance": Decimal("100"),
        "rows": [
            {"row_key": "row_b", "business_type": "B", "avg_balance": Decimal("25")},
            {"row_key": "row_c", "business_type": "C", "avg_balance": Decimal("75")},
        ],
    }

    result = _core().build_business_type_share_drift(
        current=current,
        baseline=baseline,
        year=2026,
        as_of_date="2026-06-30",
        baseline_year=2025,
        baseline_as_of_date="2025-06-30",
    )

    assert result["comparison_basis"] == "PRIOR_YEAR_SAME_PERIOD_YTD_AVG_BALANCE_SHARE"
    assert result["available"] is True
    assert result["availability_reason"] is None
    assert result["baseline_as_of_date"] == "2025-06-30"
    rows = {row["row_key"]: row for row in result["rows"]}
    assert rows["row_a"] == {
        "row_key": "row_a",
        "business_type": "A",
        "current_share_pct": Decimal("60.00"),
        "baseline_share_pct": Decimal("0.00"),
        "drift_pp": Decimal("60.00"),
        "lifecycle_status": "new",
    }
    assert rows["row_b"]["drift_pp"] == Decimal("15.00")
    assert rows["row_b"]["lifecycle_status"] == "continued"
    assert rows["row_c"]["current_share_pct"] == Decimal("0.00")
    assert rows["row_c"]["drift_pp"] == Decimal("-75.00")
    assert rows["row_c"]["lifecycle_status"] == "exited"


def test_share_drift_uses_raw_balances_before_final_rounding() -> None:
    result = _core().build_business_type_share_drift(
        current={
            "total_avg_balance": Decimal("3"),
            "rows": [
                {"row_key": "row_a", "business_type": "A", "avg_balance": Decimal("1")},
                {"row_key": "row_b", "business_type": "B", "avg_balance": Decimal("2")},
            ],
        },
        baseline={
            "total_avg_balance": Decimal("6"),
            "rows": [
                {"row_key": "row_a", "business_type": "A", "avg_balance": Decimal("1")},
                {"row_key": "row_b", "business_type": "B", "avg_balance": Decimal("5")},
            ],
        },
        year=2026,
        as_of_date="2026-06-30",
        baseline_year=2025,
        baseline_as_of_date="2025-06-30",
    )

    row_a = next(row for row in result["rows"] if row["row_key"] == "row_a")
    assert row_a["current_share_pct"] == Decimal("33.33")
    assert row_a["baseline_share_pct"] == Decimal("16.67")
    assert row_a["drift_pp"] == Decimal("16.67")


@pytest.mark.parametrize(
    ("current_total", "baseline", "reason"),
    [
        (
            Decimal("0"),
            {"total_avg_balance": Decimal("100"), "rows": []},
            "current_total_non_positive",
        ),
        (Decimal("100"), None, "baseline_missing"),
        (
            Decimal("100"),
            {"total_avg_balance": Decimal("0"), "rows": []},
            "baseline_total_non_positive",
        ),
    ],
)
def test_share_drift_fails_closed_when_either_denominator_is_unavailable(
    current_total: Decimal,
    baseline: dict[str, object] | None,
    reason: str,
) -> None:
    current = {
        "total_avg_balance": current_total if current_total > 0 else None,
        "rows": [
            {"row_key": "row_a", "business_type": "A", "avg_balance": Decimal("100")}
        ],
    }

    result = _core().build_business_type_share_drift(
        current=current,
        baseline=baseline,
        year=2026,
        as_of_date="2026-06-30",
        baseline_year=2025,
        baseline_as_of_date="2025-06-30",
    )

    assert result["available"] is False
    assert result["availability_reason"] == reason
    assert all(row["drift_pp"] is None for row in result["rows"])
    assert all(row["lifecycle_status"] == "unavailable" for row in result["rows"])


def test_scale_yield_quadrant_uses_average_balance_share_not_pnl_proportion() -> None:
    items = [
        _ytd_item("row_1", "A", "10", ftp_net_yield_pct="1", proportion="0.99"),
        _ytd_item("row_2", "B", "20", ftp_net_yield_pct="2", proportion="0.01"),
        _ytd_item("row_3", "C", "30", ftp_net_yield_pct="3", proportion="0.01"),
        _ytd_item("row_4", "D", "40", ftp_net_yield_pct="4", proportion="0.01"),
        _ytd_item("row_5", "E", "50", ftp_net_yield_pct="5", proportion="0.01"),
        _ytd_item("row_6", "F", "60", ftp_net_yield_pct="6", proportion="0.01"),
    ]

    result = _core().build_scale_yield_quadrant(
        items=items,
        year=2026,
        as_of_date="2026-06-30",
    )

    assert result["available"] is True
    assert result["minimum_eligible_rows"] == 6
    assert result["eligible_row_count"] == 6
    assert result["scale_basis"] == "YTD_AVG_BALANCE_SHARE"
    assert result["yield_basis"] == "FTP_NET_ANNUALIZED_YIELD_PCT"
    assert result["total_avg_balance"] == Decimal("210")
    assert result["ftp_net_annualized_yield_median_pct"] == Decimal("3.500000")
    rows = {row["row_key"]: row for row in result["rows"]}
    assert rows["row_1"]["scale_share_pct"] == Decimal("4.76")
    assert rows["row_1"]["quadrant_key"] == "SMALL_LOW"
    assert rows["row_6"]["scale_share_pct"] == Decimal("28.57")
    assert rows["row_6"]["quadrant_key"] == "LARGE_HIGH"


def test_scale_yield_quadrant_fails_closed_below_minimum_sample() -> None:
    result = _core().build_scale_yield_quadrant(
        items=[
            _ytd_item(f"row_{index}", str(index), str(index)) for index in range(1, 6)
        ],
        year=2026,
        as_of_date="2026-06-30",
    )

    assert result["available"] is False
    assert result["eligible_row_count"] == 5
    assert result["scale_share_median_pct"] is None
    assert result["ftp_net_annualized_yield_median_pct"] is None
    assert result["rows"] == []


def test_formal_insights_envelope_propagates_cutoff_quality_and_approved_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.services import pnl_by_business_candidate_insights as service

    assert hasattr(service, "pnl_by_business_insights_envelope")

    def fake_ytd_envelope(*, duckdb_path, governance_dir, year, as_of_date=None):
        report_date = as_of_date or f"{year}-12-31"
        multiplier = Decimal("1") if year == 2026 else Decimal("0.8")
        items = [
            _ytd_item(
                f"row_{index}",
                chr(64 + index),
                str(Decimal(index * 10) * multiplier),
                ftp_net_yield_pct=str(index),
            )
            for index in range(1, 7)
        ]
        envelope = _governed_analytical_component_envelope(
            result_kind="pnl.by_business_ytd",
            report_date=report_date,
        )
        envelope["result_meta"]["quality_flag"] = "warning" if year == 2026 else "ok"
        envelope["result"].update({"year": year, "items": items})
        return envelope

    def fake_monthly_envelope(*, duckdb_path, governance_dir, year, as_of_date=None):
        report_date = as_of_date or f"{year}-12-31"
        envelope = _governed_analytical_component_envelope(
            result_kind="pnl.by_business_monthly",
            report_date=report_date,
        )
        envelope["result"]["months"] = []
        return envelope

    monkeypatch.setattr(
        service.pnl_service, "pnl_by_business_ytd_envelope", fake_ytd_envelope
    )
    monkeypatch.setattr(
        service.pnl_service, "pnl_by_business_monthly_envelope", fake_monthly_envelope
    )
    monkeypatch.setattr(
        service,
        "compute_untraced_reconciliation_trend",
        lambda **_kwargs: {
            "as_of_date": "2026-06-30",
            "lookback_months": 12,
            "available": True,
            "availability_reason": None,
            "rows": [],
        },
    )

    envelope = service.pnl_by_business_insights_envelope(
        duckdb_path="unused.duckdb",
        governance_dir="unused-governance",
        year=2026,
        as_of_date="2026-06-30",
    )

    meta = envelope["result_meta"]
    assert meta["result_kind"] == "pnl.by_business_insights"
    assert meta["basis"] == "formal"
    assert meta["formal_use_allowed"] is True
    assert meta["quality_flag"] == "warning"
    assert meta["requested_report_date"] == "2026-06-30"
    assert meta["resolved_report_date"] == "2026-06-30"
    assert meta["fallback_mode"] == "none"
    assert meta["date_basis"] == "formal_report_date_cutoff"
    assert set(meta["tables_used"]) >= {
        "fact_formal_pnl_fi",
        "fact_formal_zqtz_balance_daily",
    }

    result = envelope["result"]
    assert result["result_version"] == "v2"
    assert result["baseline_requested_report_date"] == "2025-06-30"
    assert result["baseline_resolved_report_date"] == "2025-06-30"
    assert result["baseline_fallback_mode"] == "none"
    assert {entry["component"] for entry in result["component_evidence"]} >= {
        "current_ytd",
        "baseline_ytd",
    }
    assert result["negative_ftp_persistence"]["eligible"] is False
    assert result["negative_ftp_persistence"]["status"] == "insufficient_observations"
    assert result["share_drift"]["baseline_as_of_date"] == "2025-06-30"
    assert result["scale_yield_quadrant"]["available"] is True
    assert result["reconciliation_diagnostics"]["rows"] == []


def test_formal_insights_fails_closed_on_component_fallback_vendor_and_baseline_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.services import pnl_by_business_candidate_insights as service

    def fake_ytd_envelope(*, duckdb_path, governance_dir, year, as_of_date=None):
        requested = as_of_date or f"{year}-12-31"
        resolved = "2025-05-31" if year == 2025 else requested
        fallback_mode = "latest_snapshot" if resolved != requested else "none"
        envelope = _governed_analytical_component_envelope(
            result_kind="pnl.by_business_ytd",
            report_date=requested,
        )
        envelope["result_meta"].update(
            {
                "resolved_report_date": resolved,
                "as_of_date": resolved,
                "fallback_mode": fallback_mode,
                "fallback_date": resolved if fallback_mode != "none" else None,
            }
        )
        envelope["result"].update(
            {
                "year": year,
                "period_end_date": resolved,
                "items": [
                    _ytd_item(
                        f"row_{index}",
                        chr(64 + index),
                        str(index * 10),
                        ftp_net_yield_pct=str(index),
                    )
                    for index in range(1, 7)
                ],
            }
        )
        return envelope

    def fake_monthly_envelope(*, duckdb_path, governance_dir, year, as_of_date=None):
        requested = as_of_date or f"{year}-12-31"
        months = []
        if year == 2026:
            months = [
                {
                    "month_key": f"2026-{month:02d}",
                    "summary": {"ftp_net_pnl": "-1"},
                    "items": [
                        {
                            "row_key": "row_1",
                            "business_type": "A",
                            "ftp_net_pnl": "-1",
                            "source_note": None,
                        }
                    ],
                }
                for month in range(1, 7)
            ]
        envelope = _governed_analytical_component_envelope(
            result_kind="pnl.by_business_monthly",
            report_date=requested,
        )
        envelope["result_meta"].update(
            {
                "fallback_mode": "latest_snapshot" if year == 2026 else "none",
                "fallback_date": "2026-06-29" if year == 2026 else None,
                "vendor_status": "vendor_stale" if year == 2026 else "ok",
            }
        )
        envelope["result"]["months"] = months
        return envelope

    monkeypatch.setattr(
        service.pnl_service, "pnl_by_business_ytd_envelope", fake_ytd_envelope
    )
    monkeypatch.setattr(
        service.pnl_service, "pnl_by_business_monthly_envelope", fake_monthly_envelope
    )
    monkeypatch.setattr(
        service,
        "compute_untraced_reconciliation_trend",
        lambda **_kwargs: {
            "as_of_date": "2026-06-30",
            "lookback_months": 12,
            "available": True,
            "availability_reason": None,
            "rows": [],
        },
    )

    with pytest.raises(RuntimeError, match="baseline_ytd:date_mismatch"):
        service.pnl_by_business_insights_envelope(
            duckdb_path="unused.duckdb",
            governance_dir="unused-governance",
            year=2026,
            as_of_date="2026-06-30",
        )


@pytest.mark.parametrize("prior_year_mode", ["unavailable", "empty"])
def test_formal_insights_warns_on_incomplete_monthly_window(
    monkeypatch: pytest.MonkeyPatch,
    prior_year_mode: str,
) -> None:
    from backend.app.services import pnl_by_business_candidate_insights as service

    def fake_ytd_envelope(*, duckdb_path, governance_dir, year, as_of_date=None):
        report_date = as_of_date or f"{year}-12-31"
        envelope = _governed_analytical_component_envelope(
            result_kind="pnl.by_business_ytd",
            report_date=report_date,
        )
        envelope["result"].update(
            {
                "year": year,
                "items": [
                    _ytd_item(
                        f"row_{index}",
                        chr(64 + index),
                        str(index * 10),
                        ftp_net_yield_pct=str(index),
                    )
                    for index in range(1, 7)
                ],
            }
        )
        return envelope

    def fake_monthly_envelope(*, duckdb_path, governance_dir, year, as_of_date=None):
        if year == 2025 and prior_year_mode == "unavailable":
            raise ValueError("monthly year unavailable")
        report_date = as_of_date or f"{year}-12-31"
        envelope = _governed_analytical_component_envelope(
            result_kind="pnl.by_business_monthly",
            report_date=report_date,
        )
        envelope["result"]["months"] = (
            []
            if year == 2025
            else [
                {
                    "month_key": f"2026-{month:02d}",
                    "summary": {"ftp_net_pnl": "-1"},
                    "items": [
                        {
                            "row_key": "row_1",
                            "business_type": "A",
                            "ftp_net_pnl": "-1",
                            "source_note": None,
                        }
                    ],
                }
                for month in range(1, 7)
            ]
        )
        return envelope

    monkeypatch.setattr(
        service.pnl_service, "pnl_by_business_ytd_envelope", fake_ytd_envelope
    )
    monkeypatch.setattr(
        service.pnl_service, "pnl_by_business_monthly_envelope", fake_monthly_envelope
    )
    monkeypatch.setattr(
        service,
        "compute_untraced_reconciliation_trend",
        lambda **_kwargs: {
            "as_of_date": "2026-06-30",
            "lookback_months": 12,
            "available": True,
            "availability_reason": None,
            "rows": [],
        },
    )

    if prior_year_mode == "unavailable":
        with pytest.raises(RuntimeError, match="monthly_2025:component_unavailable"):
            service.pnl_by_business_insights_envelope(
                duckdb_path="unused.duckdb",
                governance_dir="unused-governance",
                year=2026,
                as_of_date="2026-06-30",
            )
        return

    envelope = service.pnl_by_business_insights_envelope(
        duckdb_path="unused.duckdb",
        governance_dir="unused-governance",
        year=2026,
        as_of_date="2026-06-30",
    )

    assert envelope["result"]["negative_ftp_persistence"]["eligible"] is True
    assert envelope["result"]["scale_yield_quadrant"]["available"] is True
    assert envelope["result"]["share_drift"]["available"] is True
    assert envelope["result_meta"]["quality_flag"] == "warning"
    assert envelope["result_meta"]["vendor_status"] == "ok"
    evidence = {
        entry["component"]: entry for entry in envelope["result"]["component_evidence"]
    }
    assert evidence["monthly_2025"]["requested_report_date"] == "2025-12-31"
    assert evidence["monthly_2025"]["quality_flag"] == "warning"
    assert evidence["monthly_2025"]["vendor_status"] == "ok"
    assert evidence["monthly_2025"]["resolved_report_date"] == "2025-12-31"


@pytest.mark.parametrize("raw_quality", [None, "missing", "future_quality"])
def test_component_missing_or_unknown_quality_fails_closed(
    raw_quality: str | None,
) -> None:
    from backend.app.services import pnl_by_business_candidate_insights as service

    meta: dict[str, object] = {
        "requested_report_date": "2026-06-30",
        "resolved_report_date": "2026-06-30",
        "fallback_mode": "none",
        "vendor_status": "ok",
    }
    if raw_quality is not None:
        meta["quality_flag"] = raw_quality
    envelope = {"result_meta": meta, "result": {}}

    evidence = service._component_evidence(
        "current_ytd",
        envelope,
        requested_default="2026-06-30",
    )

    assert evidence["quality_flag"] == "error"
    assert (
        service._insights_quality_flag(
            [envelope],
            baseline_available=True,
            concentration_available=True,
            quadrant_available=True,
            negative_ftp_available=True,
            monthly_source_complete=True,
        )
        == "error"
    )


def test_component_missing_vendor_status_fails_closed() -> None:
    from backend.app.services import pnl_by_business_candidate_insights as service

    envelope = {
        "result_meta": {
            "quality_flag": "ok",
            "requested_report_date": "2026-06-30",
            "resolved_report_date": "2026-06-30",
            "fallback_mode": "none",
        },
        "result": {},
    }

    evidence = service._component_evidence(
        "current_ytd",
        envelope,
        requested_default="2026-06-30",
    )

    assert evidence["vendor_status"] == "vendor_unavailable"
    assert service._composite_vendor_status([envelope]) == "vendor_unavailable"


@pytest.mark.parametrize("raw_fallback_mode", [None, "future_mode"])
def test_component_missing_or_unknown_fallback_mode_fails_closed(
    raw_fallback_mode: str | None,
) -> None:
    from backend.app.services import pnl_by_business_candidate_insights as service

    meta: dict[str, object] = {
        "quality_flag": "ok",
        "vendor_status": "ok",
        "requested_report_date": "2026-06-30",
        "resolved_report_date": "2026-06-30",
    }
    if raw_fallback_mode is not None:
        meta["fallback_mode"] = raw_fallback_mode
    envelope = {"result_meta": meta, "result": {}}

    evidence = service._component_evidence(
        "current_ytd",
        envelope,
        requested_default="2026-06-30",
    )

    assert evidence["fallback_mode"] == "latest_snapshot"
    assert (
        service._insights_quality_flag(
            [envelope],
            baseline_available=True,
            concentration_available=True,
            quadrant_available=True,
            negative_ftp_available=True,
            monthly_source_complete=True,
        )
        == "warning"
    )


def test_component_missing_upstream_dates_cannot_manufacture_exact_evidence() -> None:
    from backend.app.services import pnl_by_business_candidate_insights as service

    envelope = {
        "result_meta": {
            "quality_flag": "ok",
            "vendor_status": "ok",
            "fallback_mode": "none",
        },
        "result": {},
    }

    evidence = service._component_evidence(
        "current_ytd",
        envelope,
        requested_default="2026-06-30",
    )

    assert evidence["requested_report_date"] == "2026-06-30"
    assert evidence["resolved_report_date"] is None
    assert evidence["fallback_mode"] == "latest_snapshot"


def test_component_evidence_exposes_and_admits_governed_formal_fact_lineage() -> None:
    from backend.app.services import pnl_by_business_candidate_insights as service

    evidence = service._component_evidence(
        "current_ytd",
        _governed_analytical_component_envelope(
            result_kind="pnl.by_business_ytd",
            report_date="2026-06-30",
        ),
        requested_default="2026-06-30",
    )

    assert evidence == {
        "component": "current_ytd",
        "requested_report_date": "2026-06-30",
        "resolved_report_date": "2026-06-30",
        "fallback_mode": "none",
        "quality_flag": "ok",
        "vendor_status": "ok",
        "basis": "analytical",
        "formal_use_allowed": False,
        "result_kind": "pnl.by_business_ytd",
        "trace_id": "tr_pnl_by_business_ytd_2026-06-30",
        "source_surface": "formal_pnl",
        "source_version": "sv_2026-06-30",
        "rule_version": "rv_pnl_phase2_materialize_v3",
        "cache_version": "cv_pnl_formal_v3",
        "tables_used": _FORMAL_COMPONENT_TABLES,
        "formal_source_admitted": True,
        "admission_reason": None,
    }


def test_component_evidence_rejects_refresh_bundle_source() -> None:
    from backend.app.services import pnl_by_business_candidate_insights as service

    evidence = service._component_evidence(
        "current_ytd",
        _governed_analytical_component_envelope(
            result_kind="pnl.by_business_ytd",
            report_date="2026-06-30",
            tables_used=[
                "data_input/pnl",
                "data_input/pnl_514",
                "fact_formal_zqtz_balance_daily",
                "ZQTZ_ASSET_BOND_ROWS",
                "fx_daily_mid",
            ],
        ),
        requested_default="2026-06-30",
    )

    assert evidence["formal_source_admitted"] is False
    assert evidence["admission_reason"] == "nonformal_source_tables"


@pytest.mark.parametrize(
    ("mutation", "expected_reason"),
    [
        (lambda envelope: envelope["result_meta"].pop("trace_id"), "missing_trace_id"),
        (
            lambda envelope: envelope["result_meta"].update(
                {
                    "requested_report_date": "2026-05-31",
                    "resolved_report_date": "2026-05-31",
                    "as_of_date": "2026-05-31",
                }
            ),
            "date_mismatch",
        ),
    ],
)
def test_component_evidence_rejects_missing_lineage_and_wrong_date(
    mutation,
    expected_reason: str,
) -> None:
    from backend.app.services import pnl_by_business_candidate_insights as service

    envelope = _governed_analytical_component_envelope(
        result_kind="pnl.by_business_ytd",
        report_date="2026-06-30",
    )
    mutation(envelope)

    evidence = service._component_evidence(
        "current_ytd",
        envelope,
        requested_default="2026-06-30",
    )

    assert evidence["formal_source_admitted"] is False
    assert evidence["admission_reason"] == expected_reason


def test_source_table_lineage_does_not_manufacture_formal_tables() -> None:
    from backend.app.services import pnl_by_business_candidate_insights as service

    refresh_envelope = _governed_analytical_component_envelope(
        result_kind="pnl.by_business_ytd",
        report_date="2026-06-30",
        tables_used=["data_input/pnl", "fact_formal_zqtz_balance_daily"],
    )

    assert service._source_tables([], reconciliation_available=False) == []
    assert service._source_tables(
        [refresh_envelope],
        reconciliation_available=False,
    ) == ["data_input/pnl", "fact_formal_zqtz_balance_daily"]


def test_reconciliation_unavailable_downgrades_outer_quality_to_warning() -> None:
    from backend.app.services import pnl_by_business_candidate_insights as service

    assert (
        service._insights_quality_flag(
            [],
            baseline_available=True,
            concentration_available=True,
            quadrant_available=True,
            negative_ftp_available=True,
            monthly_source_complete=True,
            reconciliation_available=False,
        )
        == "warning"
    )


def test_formal_insights_endpoint_fails_closed_on_unadmitted_component(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.services import pnl_by_business_candidate_insights as service

    golden_path = (
        Path(__file__).resolve().parent
        / "golden_samples"
        / "GS-PNL-BUSINESS-INSIGHTS-A"
        / "response.json"
    )
    payload = json.loads(golden_path.read_text(encoding="utf-8"))["result"]
    for entry in payload["component_evidence"]:
        result_kind = (
            "pnl.by_business_ytd"
            if entry["component"] in {"current_ytd", "baseline_ytd"}
            else "pnl.by_business_monthly"
        )
        entry.update(
            {
                "basis": "analytical",
                "formal_use_allowed": False,
                "result_kind": result_kind,
                "trace_id": f"tr_{entry['component']}",
                "source_surface": "formal_pnl",
                "rule_version": "rv_pnl_phase2_materialize_v3",
                "cache_version": "cv_pnl_formal_v3",
                "tables_used": list(_FORMAL_COMPONENT_TABLES),
                "formal_source_admitted": True,
                "admission_reason": None,
            }
        )
    payload["component_evidence"][0]["formal_source_admitted"] = False
    payload["component_evidence"][0]["admission_reason"] = "nonformal_source_tables"
    payload["reconciliation_diagnostics"].update(
        {"available": True, "availability_reason": None}
    )
    source_envelope = _governed_analytical_component_envelope(
        result_kind="pnl.by_business_ytd",
        report_date="2026-02-28",
    )
    monkeypatch.setattr(
        service,
        "_build_insights_components",
        lambda **_kwargs: (payload, [source_envelope], "2026-02-28", True),
    )

    with pytest.raises(
        RuntimeError,
        match="current_ytd:nonformal_source_tables",
    ):
        service.pnl_by_business_insights_envelope(
            duckdb_path="unused.duckdb",
            governance_dir="unused-governance",
            year=2026,
            as_of_date="2026-02-28",
        )


def test_formal_insights_get_route_is_registered() -> None:
    from backend.app.api.routes.pnl import router

    methods_by_path = {route.path: route.methods for route in router.routes}
    assert "/api/pnl/by-business-insights" in methods_by_path
    assert "GET" in methods_by_path["/api/pnl/by-business-insights"]
