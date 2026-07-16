from __future__ import annotations

from decimal import Decimal

import duckdb
import pytest

from backend.app.repositories.pnl_repo import PnlRepository
from backend.app.services import pnl_by_business_candidate_insights as insights


def _ytd_item(
    row_key: str,
    business_type: str,
    avg_balance: str,
    *,
    source_note: str | None = None,
) -> dict[str, object]:
    return {
        "row_key": row_key,
        "business_type": business_type,
        "avg_balance": avg_balance,
        "source_note": source_note,
    }


def _ytd_envelope(
    items: list[dict[str, object]],
    *,
    report_date: str = "2026-02-28",
) -> dict[str, object]:
    return {
        "result_meta": {
            "result_kind": "pnl.by_business_ytd",
            "basis": "formal",
            "formal_use_allowed": True,
            "resolved_report_date": report_date,
        },
        "result": {"period_end_date": report_date, "items": items},
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


def _monthly_bucket(
    month_key: str, items: list[dict[str, object]], *, summary_ftp_net_pnl: str | None
) -> dict[str, object]:
    return {
        "month_key": month_key,
        "summary": {"ftp_net_pnl": summary_ftp_net_pnl},
        "items": items,
    }


def _monthly_envelope(months: list[dict[str, object]]) -> dict[str, object]:
    return {
        "result_meta": {
            "result_kind": "pnl.by_business_monthly",
            "basis": "formal",
            "formal_use_allowed": True,
        },
        "result": {"months": months},
    }


def test_concentration_hhi_and_top3_share_sum_consistency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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


def test_negative_ftp_persistence_handles_year_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[int, str | None]] = []

    def fake_monthly_envelope(*, duckdb_path, governance_dir, year, as_of_date=None):
        calls.append((year, as_of_date))
        if year == 2025:
            return _monthly_envelope(
                [
                    _monthly_bucket(
                        "2025-11",
                        [_monthly_item("row_a", "国债", "-1.00")],
                        summary_ftp_net_pnl="-1.00",
                    ),
                    _monthly_bucket(
                        "2025-12",
                        [_monthly_item("row_a", "国债", "2.00")],
                        summary_ftp_net_pnl="2.00",
                    ),
                ]
            )
        if year == 2026:
            return _monthly_envelope(
                [
                    _monthly_bucket(
                        "2026-01",
                        [_monthly_item("row_a", "国债", "-3.00")],
                        summary_ftp_net_pnl="-3.00",
                    ),
                    _monthly_bucket(
                        "2026-02",
                        [_monthly_item("row_a", "国债", "-4.00")],
                        summary_ftp_net_pnl="-4.00",
                    ),
                    _monthly_bucket(
                        "2026-03",
                        [_monthly_item("row_a", "国债", "5.00")],
                        summary_ftp_net_pnl="5.00",
                    ),
                ]
            )
        raise AssertionError(f"unexpected year requested: {year}")

    monkeypatch.setattr(
        insights.pnl_service, "pnl_by_business_monthly_envelope", fake_monthly_envelope
    )

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
    assert result["eligible"] is False
    assert result["status"] == "insufficient_observations"
    assert result["negative_ftp_month_share_pct"] is None
    assert result["negative_ftp_longest_streak_months"] is None


def test_negative_ftp_longest_streak_resets_on_positive_month() -> None:
    series = [
        ("2026-01", Decimal("-1")),
        ("2026-02", Decimal("-1")),
        ("2026-03", Decimal("1")),
        ("2026-04", Decimal("-1")),
    ]
    assert insights._longest_negative_streak(series) == 2


def test_share_drift_degrades_gracefully_when_baseline_year_has_no_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_items = [
        _ytd_item("row_a", "国债", "700"),
        _ytd_item("row_b", "政策性金融债", "300"),
    ]

    def fake_ytd_envelope(*, duckdb_path, governance_dir, year, as_of_date=None):
        if year == 2025:
            raise ValueError(f"No formal pnl rows found for year={year}.")
        return _ytd_envelope(
            current_items,
            report_date=as_of_date or f"{year}-12-31",
        )

    monkeypatch.setattr(
        insights.pnl_service, "pnl_by_business_ytd_envelope", fake_ytd_envelope
    )

    result = insights.compute_business_type_share_drift(
        duckdb_path="unused.duckdb",
        governance_dir="unused-governance",
        year=2026,
        as_of_date="2026-02-28",
    )

    assert result["baseline_available"] is False
    assert result["available"] is False
    assert result["availability_reason"] == "baseline_missing"
    assert result["baseline_as_of_date"] is None
    assert result["rows"]
    for row in result["rows"]:
        assert row["baseline_share_pct"] is None
        assert row["drift_pp"] is None


def test_candidate_insights_envelope_hardcodes_formal_use_allowed_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    items = [
        _ytd_item("row_a", "国债", "700"),
        _ytd_item("row_b", "政策性金融债", "300"),
    ]

    def fake_ytd_envelope(*, duckdb_path, governance_dir, year, as_of_date=None):
        envelope = _ytd_envelope(
            items,
            report_date=as_of_date or f"{year}-12-31",
        )
        # Simulate an upstream envelope that (incorrectly) claims formal_use_allowed=True;
        # the candidate-insights envelope must never inherit this.
        envelope["result_meta"]["formal_use_allowed"] = True
        return envelope

    def fake_monthly_envelope(*, duckdb_path, governance_dir, year, as_of_date=None):
        envelope = _monthly_envelope(
            [
                _monthly_bucket(
                    "2026-02",
                    [_monthly_item("row_a", "国债", "1.00")],
                    summary_ftp_net_pnl="1.00",
                )
            ]
        )
        envelope["result_meta"]["formal_use_allowed"] = True
        return envelope

    monkeypatch.setattr(
        insights.pnl_service, "pnl_by_business_ytd_envelope", fake_ytd_envelope
    )
    monkeypatch.setattr(
        insights.pnl_service, "pnl_by_business_monthly_envelope", fake_monthly_envelope
    )

    envelope = insights.pnl_by_business_candidate_insights_envelope(
        duckdb_path="unused.duckdb",
        governance_dir="unused-governance",
        year=2026,
        as_of_date="2026-02-28",
    )

    assert envelope["result_meta"]["formal_use_allowed"] is False
    assert envelope["result_meta"]["basis"] == "analytical"
    assert envelope["result_meta"]["cache_version"].endswith("_v2")
    assert envelope["result_meta"]["rule_version"].endswith("_v2")
    assert envelope["result"]["result_version"] == "v2"


def _create_untraced_reconciliation_tables(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table fact_formal_pnl_fi (
          report_date varchar,
          instrument_code varchar,
          portfolio_name varchar,
          cost_center varchar,
          currency_basis varchar
        )
        """
    )
    conn.execute(
        """
        create table fact_formal_zqtz_balance_daily (
          report_date varchar,
          instrument_code varchar,
          portfolio_name varchar,
          cost_center varchar,
          currency_basis varchar,
          position_scope varchar,
          business_type_primary varchar
        )
        """
    )


def test_untraced_trend_reuses_single_day_sql_and_caps_at_lookback_months(
    tmp_path,
) -> None:
    duckdb_path = tmp_path / "reconciliation-trend.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        _create_untraced_reconciliation_tables(conn)
        # 15 distinct month-end formal report dates, spanning a calendar-year boundary.
        fi_dates = [
            "2025-01-31",
            "2025-02-28",
            "2025-03-31",
            "2025-04-30",
            "2025-05-31",
            "2025-06-30",
            "2025-07-31",
            "2025-08-31",
            "2025-09-30",
            "2025-10-31",
            "2025-11-30",
            "2025-12-31",
            "2026-01-31",
            "2026-02-28",
            "2026-03-31",
        ]
        for report_date in fi_dates:
            conn.execute(
                "insert into fact_formal_pnl_fi values (?, ?, ?, ?, ?)",
                [report_date, "BOND-1", "Desk", "CC-1", "CNY"],
            )
            conn.execute(
                "insert into fact_formal_zqtz_balance_daily values (?, ?, ?, ?, ?, ?, ?)",
                [report_date, "BOND-1", "Desk", "CC-1", "CNY", "asset", "国债"],
            )
    finally:
        conn.close()

    result = insights.compute_untraced_reconciliation_trend(
        duckdb_path=str(duckdb_path),
        as_of_date="2026-03-31",
    )

    assert result["lookback_months"] == 12
    assert len(result["rows"]) <= 12
    valid_report_dates = set(fi_dates)
    for row in result["rows"]:
        assert row["report_date"] in valid_report_dates


def test_untraced_trend_handles_month_with_zero_total_rows_gracefully(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        PnlRepository,
        "list_formal_fi_report_dates",
        lambda self, **_kwargs: ["2026-01-31"],
    )
    monkeypatch.setattr(
        PnlRepository,
        "count_untraced_formal_fi_rows_for_dates",
        lambda self, report_dates: {rd: 0 for rd in report_dates},
    )
    monkeypatch.setattr(
        PnlRepository,
        "count_formal_fi_rows_for_dates",
        lambda self, report_dates: {rd: 0 for rd in report_dates},
    )

    result = insights.compute_untraced_reconciliation_trend(
        duckdb_path="unused.duckdb",
        as_of_date="2026-01-31",
        lookback_months=1,
    )

    assert len(result["rows"]) == 1
    row = result["rows"][0]
    assert row["total_row_count"] == 0
    assert row["untraced_row_count"] == 0
    assert row["untraced_share_pct"] is None


def test_untraced_trend_marks_storage_failure_as_source_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(_self, **_kwargs) -> list[str]:
        raise RuntimeError("Formal pnl storage is unavailable.")

    monkeypatch.setattr(PnlRepository, "list_formal_fi_report_dates", unavailable)

    result = insights.compute_untraced_reconciliation_trend(
        duckdb_path="missing.duckdb",
        as_of_date="2026-01-31",
        lookback_months=1,
    )

    assert result["available"] is False
    assert result["availability_reason"] == "source_unavailable"
    assert result["rows"] == []


def test_untraced_trend_marks_empty_window_as_no_observations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        PnlRepository,
        "list_formal_fi_report_dates",
        lambda _self, **_kwargs: [],
    )

    result = insights.compute_untraced_reconciliation_trend(
        duckdb_path="unused.duckdb",
        as_of_date="2026-01-31",
        lookback_months=1,
    )

    assert result["available"] is False
    assert result["availability_reason"] == "no_observations"
    assert result["rows"] == []


def test_untraced_trend_marks_missing_formal_fi_table_as_source_unavailable(
    tmp_path,
) -> None:
    duckdb_path = tmp_path / "missing-formal-fi-table.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    conn.close()

    result = insights.compute_untraced_reconciliation_trend(
        duckdb_path=str(duckdb_path),
        as_of_date="2026-01-31",
        lookback_months=1,
    )

    assert result["available"] is False
    assert result["availability_reason"] == "source_unavailable"
    assert result["rows"] == []


def test_untraced_trend_marks_batch_read_failure_as_source_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        PnlRepository,
        "list_formal_fi_report_dates",
        lambda _self, **_kwargs: ["2026-01-31"],
    )

    def unavailable(_self, _report_dates) -> dict[str, int]:
        raise RuntimeError("Formal pnl storage is unavailable.")

    monkeypatch.setattr(
        PnlRepository,
        "count_untraced_formal_fi_rows_for_dates",
        unavailable,
    )

    result = insights.compute_untraced_reconciliation_trend(
        duckdb_path="missing.duckdb",
        as_of_date="2026-01-31",
        lookback_months=1,
    )

    assert result["available"] is False
    assert result["availability_reason"] == "source_unavailable"
    assert result["rows"] == []


@pytest.mark.parametrize(
    "method_name",
    [
        "count_untraced_formal_fi_rows_for_dates",
        "count_formal_fi_rows_for_dates",
    ],
)
def test_untraced_batch_repository_reads_do_not_turn_open_failure_into_zero(
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
) -> None:
    def cannot_open(*_args, **_kwargs):
        raise duckdb.IOException("Cannot open database")

    monkeypatch.setattr(duckdb, "connect", cannot_open)
    repo = PnlRepository("missing.duckdb")

    with pytest.raises(RuntimeError, match="Formal pnl storage is unavailable"):
        getattr(repo, method_name)(["2026-01-31"])


def test_count_untraced_formal_fi_rows_for_dates_matches_single_date_calls(
    tmp_path,
) -> None:
    duckdb_path = tmp_path / "untraced-batch-regression.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        _create_untraced_reconciliation_tables(conn)
        # Day 1: fully traced via strict match (same cost_center).
        conn.execute(
            "insert into fact_formal_pnl_fi values (?, ?, ?, ?, ?)",
            ["2026-01-31", "BOND-1", "Desk", "CC-1", "CNY"],
        )
        conn.execute(
            "insert into fact_formal_zqtz_balance_daily values (?, ?, ?, ?, ?, ?, ?)",
            ["2026-01-31", "BOND-1", "Desk", "CC-1", "CNY", "asset", "国债"],
        )
        # Day 2: untraced (never seen in zqtz asset balance for that instrument at all).
        conn.execute(
            "insert into fact_formal_pnl_fi values (?, ?, ?, ?, ?)",
            ["2026-02-28", "BOND-2", "Desk", "CC-2", "CNY"],
        )
        # Day 3: traced via relaxed match, ignoring BOND- prefix and cost_center mismatch,
        # but ambiguous because two distinct business types exist for the same instrument.
        conn.execute(
            "insert into fact_formal_pnl_fi values (?, ?, ?, ?, ?)",
            ["2026-03-31", "BOND-3", "Desk", "CC-mismatch", "CNY"],
        )
        conn.execute(
            "insert into fact_formal_zqtz_balance_daily values (?, ?, ?, ?, ?, ?, ?)",
            ["2026-03-31", "3", "Desk", "CC-other", "CNY", "asset", "国债"],
        )
        conn.execute(
            "insert into fact_formal_zqtz_balance_daily values (?, ?, ?, ?, ?, ?, ?)",
            ["2026-03-31", "3", "Desk", "CC-other", "CNY", "asset", "政策性金融债"],
        )
        # Day 4: no formal rows at all (untraced count must be 0, not an error).
    finally:
        conn.close()

    repo = PnlRepository(str(duckdb_path))
    report_dates = ["2026-01-31", "2026-02-28", "2026-03-31", "2026-04-30"]

    batch_result = repo.count_untraced_formal_fi_rows_for_dates(report_dates)
    single_date_result = {
        report_date: repo.count_untraced_formal_fi_rows(report_date)
        for report_date in report_dates
    }

    assert batch_result == single_date_result
    assert single_date_result["2026-01-31"] == 0
    assert single_date_result["2026-02-28"] == 1
    assert single_date_result["2026-03-31"] == 1
    assert single_date_result["2026-04-30"] == 0
