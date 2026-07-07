from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.services import pnl_by_business_candidate_insights as insights


def _ytd_item(row_key: str, business_type: str, avg_balance: str, *, source_note: str | None = None) -> dict[str, object]:
    return {
        "row_key": row_key,
        "business_type": business_type,
        "avg_balance": avg_balance,
        "source_note": source_note,
    }


def _ytd_envelope(items: list[dict[str, object]]) -> dict[str, object]:
    return {
        "result_meta": {"result_kind": "pnl.by_business_ytd", "basis": "formal", "formal_use_allowed": True},
        "result": {"items": items},
    }


def _monthly_item(
    row_key: str,
    business_type: str,
    ftp_net_pnl: str | None,
    *,
    source_note: str | None = None,
) -> dict[str, object]:
    return {
        "row_key": row_key,
        "business_type": business_type,
        "ftp_net_pnl": ftp_net_pnl,
        "source_note": source_note,
    }


def _monthly_bucket(month_key: str, items: list[dict[str, object]], *, summary_ftp_net_pnl: str | None) -> dict[str, object]:
    return {
        "month_key": month_key,
        "summary": {"ftp_net_pnl": summary_ftp_net_pnl},
        "items": items,
    }


def _monthly_envelope(months: list[dict[str, object]]) -> dict[str, object]:
    return {
        "result_meta": {"result_kind": "pnl.by_business_monthly", "basis": "formal", "formal_use_allowed": True},
        "result": {"months": months},
    }


def test_concentration_hhi_and_top3_share_sum_consistency(monkeypatch: pytest.MonkeyPatch) -> None:
    items = [
        _ytd_item("row_a", "国债", "600"),
        _ytd_item("row_b", "政策性金融债", "300"),
        _ytd_item("row_c", "同业存单", "100"),
    ]
    monkeypatch.setattr(
        insights.pnl_service,
        "pnl_by_business_ytd_envelope",
        lambda **_kwargs: _ytd_envelope(items),
    )

    result = insights.compute_business_type_concentration(
        duckdb_path="unused.duckdb",
        governance_dir="unused-governance",
        year=2026,
        as_of_date="2026-02-28",
    )

    assert result["hhi_pct"] is not None
    share_sum = sum(Decimal(str(row["share_pct"])) for row in result["rows"])
    assert abs(share_sum - Decimal("100")) <= Decimal("0.05")
    # HHI for 3 rows is bounded between the perfectly-even case (~33.33%) and full concentration (100%).
    assert Decimal("33") <= Decimal(str(result["hhi_pct"])) <= Decimal("100")
    assert Decimal(str(result["top_n_share_pct"])) == Decimal("100.00")


def test_concentration_excludes_detail_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    items = [
        _ytd_item("row_a", "国债", "700"),
        _ytd_item("row_a_detail_x", "国债", "500", source_note="其中项"),
        _ytd_item("row_b", "其中：外币委外", "9000"),
        _ytd_item("row_c", "政策性金融债", "300"),
    ]
    monkeypatch.setattr(
        insights.pnl_service,
        "pnl_by_business_ytd_envelope",
        lambda **_kwargs: _ytd_envelope(items),
    )

    result = insights.compute_business_type_concentration(
        duckdb_path="unused.duckdb",
        governance_dir="unused-governance",
        year=2026,
        as_of_date="2026-02-28",
    )

    row_keys = {row["row_key"] for row in result["rows"]}
    assert row_keys == {"row_a", "row_c"}
    assert Decimal(str(result["total_avg_balance"])) == Decimal("1000")


def test_negative_ftp_persistence_handles_year_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[int, str | None]] = []

    def fake_monthly_envelope(*, duckdb_path, governance_dir, year, as_of_date=None):
        calls.append((year, as_of_date))
        if year == 2025:
            return _monthly_envelope(
                [
                    _monthly_bucket("2025-11", [_monthly_item("row_a", "国债", "-1.00")], summary_ftp_net_pnl="-1.00"),
                    _monthly_bucket("2025-12", [_monthly_item("row_a", "国债", "2.00")], summary_ftp_net_pnl="2.00"),
                ]
            )
        if year == 2026:
            return _monthly_envelope(
                [
                    _monthly_bucket("2026-01", [_monthly_item("row_a", "国债", "-3.00")], summary_ftp_net_pnl="-3.00"),
                    _monthly_bucket("2026-02", [_monthly_item("row_a", "国债", "-4.00")], summary_ftp_net_pnl="-4.00"),
                    _monthly_bucket("2026-03", [_monthly_item("row_a", "国债", "5.00")], summary_ftp_net_pnl="5.00"),
                ]
            )
        raise AssertionError(f"unexpected year requested: {year}")

    monkeypatch.setattr(insights.pnl_service, "pnl_by_business_monthly_envelope", fake_monthly_envelope)

    result = insights.compute_negative_ftp_persistence(
        duckdb_path="unused.duckdb",
        governance_dir="unused-governance",
        as_of_date="2026-03-31",
        lookback_months=12,
    )

    # Both year=2025 (as_of_date=None -> all available months) and year=2026 (capped at the
    # requested as_of_date) must be queried to cover the trailing 12-month window.
    assert (2025, None) in calls
    assert (2026, "2026-03-31") in calls
    assert result["window_start_month"] == "2025-04"
    assert result["window_end_month"] == "2026-03"
    # Only the 5 months with actual bucket data are counted; the rest of the window is a gap.
    assert result["months_observed"] == 5
    assert result["negative_ftp_longest_streak_months"] <= 12


def test_negative_ftp_longest_streak_resets_on_positive_month() -> None:
    series = [
        ("2026-01", Decimal("-1")),
        ("2026-02", Decimal("-1")),
        ("2026-03", Decimal("1")),
        ("2026-04", Decimal("-1")),
    ]
    assert insights._longest_negative_streak(series) == 2


def test_share_drift_degrades_gracefully_when_baseline_year_has_no_data(monkeypatch: pytest.MonkeyPatch) -> None:
    current_items = [
        _ytd_item("row_a", "国债", "700"),
        _ytd_item("row_b", "政策性金融债", "300"),
    ]

    def fake_ytd_envelope(*, duckdb_path, governance_dir, year, as_of_date=None):
        if year == 2025:
            raise ValueError(f"No formal pnl rows found for year={year}.")
        return _ytd_envelope(current_items)

    monkeypatch.setattr(insights.pnl_service, "pnl_by_business_ytd_envelope", fake_ytd_envelope)

    result = insights.compute_business_type_share_drift(
        duckdb_path="unused.duckdb",
        governance_dir="unused-governance",
        year=2026,
        as_of_date="2026-02-28",
    )

    assert result["baseline_available"] is False
    assert result["baseline_as_of_date"] is None
    assert result["rows"]
    for row in result["rows"]:
        assert row["baseline_share_pct"] is None
        assert row["drift_pp"] is None


def test_candidate_insights_envelope_hardcodes_formal_use_allowed_false(monkeypatch: pytest.MonkeyPatch) -> None:
    items = [_ytd_item("row_a", "国债", "700"), _ytd_item("row_b", "政策性金融债", "300")]

    def fake_ytd_envelope(*, duckdb_path, governance_dir, year, as_of_date=None):
        envelope = _ytd_envelope(items)
        # Simulate an upstream envelope that (incorrectly) claims formal_use_allowed=True;
        # the candidate-insights envelope must never inherit this.
        envelope["result_meta"]["formal_use_allowed"] = True
        return envelope

    def fake_monthly_envelope(*, duckdb_path, governance_dir, year, as_of_date=None):
        envelope = _monthly_envelope(
            [_monthly_bucket("2026-02", [_monthly_item("row_a", "国债", "1.00")], summary_ftp_net_pnl="1.00")]
        )
        envelope["result_meta"]["formal_use_allowed"] = True
        return envelope

    monkeypatch.setattr(insights.pnl_service, "pnl_by_business_ytd_envelope", fake_ytd_envelope)
    monkeypatch.setattr(insights.pnl_service, "pnl_by_business_monthly_envelope", fake_monthly_envelope)

    envelope = insights.pnl_by_business_candidate_insights_envelope(
        duckdb_path="unused.duckdb",
        governance_dir="unused-governance",
        year=2026,
        as_of_date="2026-02-28",
    )

    assert envelope["result_meta"]["formal_use_allowed"] is False
    assert envelope["result_meta"]["basis"] == "analytical"
