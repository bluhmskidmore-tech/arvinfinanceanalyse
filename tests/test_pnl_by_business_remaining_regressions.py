from decimal import Decimal

import pytest

from backend.app.core_finance.pnl_by_business_insights import build_negative_ftp_persistence
from backend.app.schemas.pnl import PnlByBusinessNegativeFtpPersistenceSummary
from backend.app.services import pnl_service
from backend.app.services.pnl_by_business_adjustments import pnl_by_business_manual_adjustment_row
from backend.app.tasks.pnl_by_business_precompute import _build_pnl_by_business_analysis_payloads_for_precompute
from backend.app.tasks import pnl_by_business_precompute as precompute


@pytest.mark.parametrize("mode", ["monthly", "precomputed", "ytd"])
@pytest.mark.parametrize("case", ["manual", "ordinary", "closing", "missing"])
def test_main_tables_preserve_only_proven_manual_zero_funding(mode, case):
    row_def = next(r for r in pnl_service.ZQTZ_ASSET_BOND_ROWS if r["row_key"] == "asset_zqtz_interbank_cd")
    adjustment = {"report_date": "2026-07-31", "row_key": row_def["row_key"],
                  "business_type": row_def["row_label"], "adjustment_id": "approved-test",
                  "manual_adjustment": Decimal("100")}
    groups = {}
    module = precompute if mode == "precomputed" else pnl_service
    if mode == "ytd":
        pnl_service._apply_pnl_by_business_manual_adjustments_to_ytd_groups(
            settings=None, groups=groups, total_pnl=Decimal("0"),
            loaded_dates=["2026-07-31"], unallocated_items=[], approved_adjustments=[adjustment])
        if case == "ordinary":
            pnl_service._merge_balance_movement_business_record(groups, row_def, {
                "source_kind": "formal_fi", "interest_income": 0, "fair_value_change": 0,
                "capital_gain": 0, "manual_adjustment": 0, "total_pnl": 0})
    else:
        module._merge_monthly_business_pnl_row(groups, row_def, pnl_by_business_manual_adjustment_row(adjustment))
        if case == "ordinary":
            module._merge_monthly_business_pnl_row(groups, row_def, {"source_kind": "formal_fi", "total_pnl": 0})
    kwargs = dict(group=groups[row_def["row_key"]], avg_balance=Decimal("0"),
                  current_balance=Decimal("1" if case == "closing" else "0"),
                  total_pnl_for_proportion=Decimal("100"), calendar_days=31, ftp_rate_pct=Decimal("1.6"))
    if mode == "ytd":
        if case == "missing":
            kwargs["avg_balance"] = None
        item = pnl_service._ytd_business_item_from_group(**kwargs, balance_row={})
        summary = pnl_service._pnl_by_business_ytd_summary_from_items(
            [item], groups=groups, source_total_pnl=Decimal("100"), calendar_days=31, ftp_rate_pct=Decimal("1.6"))
    else:
        item = module._monthly_business_item_from_group(**kwargs, balance_available=case != "missing")
        summary = module._monthly_business_summary_from_items([item], 31, Decimal("1.6"), groups=groups)
    for result in (item, summary):
        assert result.total_pnl == Decimal("100")
        assert result.annualized_yield_pct is None
        assert result.ftp_cost == (Decimal("0") if case == "manual" else None)
        assert result.ftp_net_pnl == (Decimal("100") if case == "manual" else None)


@pytest.mark.parametrize("report_date", ["2025-12-31", "2026-07-31", "2027-01-01"])
@pytest.mark.parametrize("dimension", ["monthly", "portfolio", "accounting", "currency", "cost_center", "instrument"])
@pytest.mark.parametrize("case", ["manual_only", "holding", "closing_only", "ordinary_zero_pnl", "balance_only_zero"])
def test_manual_ftp_matches_live_precompute_without_granting_holdings_an_exception(report_date, dimension, case):
    key = "asset_zqtz_interbank_cd"
    # Synthetic amount; the case checks funding eligibility, not a business reconciliation.
    adjustment = pnl_by_business_manual_adjustment_row({
        "row_key": key, "business_type": "同业存单", "report_date": report_date,
        "adjustment_id": "approved-test", "manual_adjustment": "1234567.89",
    })
    balance = {
        **adjustment, "instrument_name": "同业存单", "bond_type": "同业存单",
        "asset_class": "同业存单", "business_type_primary": "同业存单", "currency_code": "CNY",
        "avg_amount": Decimal("365000000") if case == "holding" else Decimal("0"),
        "current_amount": Decimal("365000000") if case in {"holding", "closing_only"} else Decimal("0"),
    }
    pnl_rows = [] if case == "balance_only_zero" else [adjustment]
    if case == "ordinary_zero_pnl":
        pnl_rows.append({**balance, "source_kind": "formal_fi", "manual_adjustment": Decimal("0"), "total_pnl": Decimal("0")})
    kwargs = {
        "pnl_rows": pnl_rows, "balance_rows": [balance], "loaded_dates": [report_date],
        "period_start": report_date, "period_end": report_date, "ftp_rate_pct": Decimal("1.6"),
    }
    live = pnl_service._build_pnl_by_business_analysis_rows(**kwargs, business_key=key, dimension=dimension)
    payloads = _build_pnl_by_business_analysis_payloads_for_precompute(**kwargs, year=int(report_date[:4]), source_tables=[])
    cached = next(p.rows for p in payloads if p.business_key == key and p.dimension == dimension)
    assert [r.model_dump() for r in cached] == [r.model_dump() for r in live]
    row, = live
    assert row.total_pnl == (Decimal("0") if case == "balance_only_zero" else Decimal("1234567.89"))
    if case == "manual_only":
        assert row.ftp_cost == 0
        assert row.ftp_net_pnl == row.total_pnl
        assert row.annualized_yield_pct is None
    elif case == "holding":
        assert row.ftp_cost > 0
        assert row.ftp_net_pnl == row.total_pnl - row.ftp_cost
    else:
        assert row.ftp_cost is None
        assert row.ftp_net_pnl is None


def test_pending_source_blocks_persistence_but_preserves_provisional_sequence_and_clears_after_resolution():
    month_keys = [f"2025-{m:02d}" for m in range(8, 13)] + [f"2026-{m:02d}" for m in range(1, 8)]
    months = {key: {"summary": {"ftp_net_pnl": "-1"}, "items": [
        {"row_key": "cd", "business_type": "同业存单", "ftp_net_pnl": "-1"},
    ]} for key in month_keys}
    issue = {"issue_id": "source-2025-11-20", "report_date": "2025-11-20", "status": "pending",
             "reason": "源表日期冲突", "source_file": "test.xls", "source_version": "sv_test"}
    months["2025-11"]["balance_quality_issues"] = [issue]
    pending = build_negative_ftp_persistence(monthly_by_key=months, as_of_date="2026-07-31")
    validated = PnlByBusinessNegativeFtpPersistenceSummary.model_validate(pending)
    assert validated.status == "source_pending"
    assert validated.eligible is False and validated.warning_row_count == 0
    assert validated.months_observed == 12  # No month silently dropped or filled.
    assert validated.negative_ftp_longest_streak_months == 12  # Provisional only.
    assert validated.balance_quality_issues[0].report_date == "2025-11-20"
    assert all(r.status == "source_pending" and not r.eligible and not r.warning_triggered for r in validated.rows)
    months["2025-11"]["balance_quality_issues"] = []
    resolved = build_negative_ftp_persistence(monthly_by_key=months, as_of_date="2026-07-31")
    assert resolved["status"] == "eligible" and resolved["warning_row_count"] == 1
    months["2024-11"] = {"balance_quality_issues": [issue]}
    assert build_negative_ftp_persistence(monthly_by_key=months, as_of_date="2026-07-31") == resolved


@pytest.mark.parametrize("module", [pnl_service, precompute])
@pytest.mark.parametrize("offset_balances", [True, False, None, "missing_closing"])
def test_summary_manual_exception_cannot_net_away_balance_only_positions(module, offset_balances):
    keys = ["asset_zqtz_interbank_cd", "asset_zqtz_treasury_bond", "asset_zqtz_local_government_bond"]
    definitions = {r["row_key"]: r for r in pnl_service.ZQTZ_ASSET_BOND_ROWS if r["row_key"] in keys}
    adjustments = [pnl_by_business_manual_adjustment_row({
        "report_date": "2026-07-31", "row_key": keys[0], "business_type": definitions[keys[0]]["row_label"],
        "adjustment_id": "a", "manual_adjustment": Decimal("100")})]
    if offset_balances is False:
        adjustments.append(pnl_by_business_manual_adjustment_row({
            "report_date": "2026-07-31", "row_key": keys[1], "business_type": definitions[keys[1]]["row_label"],
            "adjustment_id": "b", "manual_adjustment": Decimal("-100")}))
    amounts = dict(zip(keys, [0, 1000000 if offset_balances is True else 0, -1000000 if offset_balances is True else 0]))
    if offset_balances is None:
        amounts[keys[1]] = None
    balances = tuple({
        "report_date": f"2026-07-{day:02d}", "instrument_code": key,
        "instrument_name": definitions[key]["row_label"], "bond_type": definitions[key]["row_label"],
        "asset_class": definitions[key]["row_label"], "business_type_primary": definitions[key]["row_label"],
        "currency_code": "CNY", "avg_amount": None if amounts[key] is None else Decimal(amounts[key]),
        "current_amount": None if amounts[key] is None else Decimal(amounts[key]),
    } for day in range(1, 32) for key in keys
        if not (offset_balances == "missing_closing" and day == 31 and key == keys[1]))
    bucket, = module._build_pnl_by_business_monthly_buckets(
        pnl_rows=tuple(adjustments), balance_rows=balances, loaded_dates=["2026-07-31"], ftp_rate_pct=Decimal("1.6"))
    assert bucket.summary.avg_balance == bucket.summary.current_balance == 0
    assert bucket.summary.ftp_cost == (Decimal("0") if offset_balances is False else None)
    assert bucket.summary.ftp_net_pnl == (Decimal("0") if offset_balances is False else None)
    if module is pnl_service:
        groups = {key: pnl_service._new_balance_movement_pnl_group(definitions[key]) for key in keys}
        for index, row in enumerate(adjustments):
            pnl_service._merge_balance_movement_business_record(groups, definitions[keys[index]], {
                "source_kind": "manual_adjustment", "interest_income": 0, "fair_value_change": 0,
                "capital_gain": 0, "manual_adjustment": row["manual_adjustment"], "total_pnl": row["total_pnl"]})
        ytd = pnl_service._build_pnl_by_business_ytd_payload_from_groups(
            year=2026, loaded_dates=["2026-07-31"], total_pnl=bucket.source_total_pnl, groups=groups,
            duckdb_path="unused.duckdb", source_tables=[], ftp_rate_pct=Decimal("1.6"), balance_rows=list(balances))
        assert ytd.summary.ftp_cost == (Decimal("0") if offset_balances is False else None)
        assert ytd.summary.ftp_net_pnl == (Decimal("0") if offset_balances is False else None)
@pytest.mark.parametrize("module", [pnl_service, precompute])
@pytest.mark.parametrize("observed", [True, False, "null_average", "null_closing"])
def test_monthly_builder_requires_observed_zero_balances_for_manual_exception(module, observed):
    key = "asset_zqtz_interbank_cd"
    # Synthetic amount; the case checks funding eligibility, not a business reconciliation.
    adjustment = pnl_by_business_manual_adjustment_row({
        "report_date": "2026-07-31", "row_key": key, "business_type": "同业存单",
        "adjustment_id": "approved-test", "manual_adjustment": "100"})
    balances = tuple({**adjustment, "report_date": f"2026-07-{day:02d}",
                      "instrument_code": "real-cd", "instrument_name": "同业存单",
                      "bond_type": "同业存单", "asset_class": "同业存单",
                      "business_type_primary": "同业存单", "currency_code": "CNY",
                      "avg_amount": None if observed == "null_average" else Decimal("0"),
                      "current_amount": None if observed == "null_closing" else Decimal("0")}
                     for day in range(1, 32)) if observed else ()
    bucket, = module._build_pnl_by_business_monthly_buckets(
        pnl_rows=(adjustment,), balance_rows=balances,
        loaded_dates=["2026-07-31"], ftp_rate_pct=Decimal("1.6"))
    item = next(item for item in bucket.items if item.row_key == key)
    assert bucket.coverage_days == (31 if observed else 0)
    for result in (item, bucket.summary):
        assert result.total_pnl == Decimal("100")
        assert result.ftp_cost == (Decimal("0") if observed is True else None)
        assert result.ftp_net_pnl == (Decimal("100") if observed is True else None)
    if module is pnl_service:
        groups = {}
        row_def = next(r for r in pnl_service.ZQTZ_ASSET_BOND_ROWS if r["row_key"] == key)
        pnl_service._merge_balance_movement_business_record(groups, row_def, {
            "source_kind": "manual_adjustment", "interest_income": 0, "fair_value_change": 0,
            "capital_gain": 0, "manual_adjustment": 100, "total_pnl": 100})
        payload = pnl_service._build_pnl_by_business_ytd_payload_from_groups(
            year=2026, loaded_dates=["2026-07-31"], total_pnl=Decimal("100"), groups=groups,
            duckdb_path="unused.duckdb", source_tables=[], ftp_rate_pct=Decimal("1.6"),
            balance_rows=list(balances))
        item, = payload.items
        for result in (item, payload.summary):
            assert result.ftp_cost == (Decimal("0") if observed is True else None)
            assert result.ftp_net_pnl == (Decimal("100") if observed is True else None)
