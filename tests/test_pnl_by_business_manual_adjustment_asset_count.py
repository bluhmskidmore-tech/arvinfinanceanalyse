from decimal import Decimal

import pytest

from backend.app.services import pnl_service as service
from backend.app.services.pnl_by_business_adjustments import (
    pnl_by_business_manual_adjustment_row,
)
from backend.app.tasks import pnl_by_business_precompute as precompute


ROW_DEF = next(
    row
    for row in service.ZQTZ_ASSET_BOND_ROWS
    if row["row_key"] == "asset_zqtz_interbank_cd"
)


def adjustment(number):
    return {
        "adjustment_id": str(number),
        "report_date": "2026-05-31",
        "row_key": ROW_DEF["row_key"],
        "business_type": ROW_DEF["row_label"],
        "manual_adjustment": Decimal("25"),
    }


@pytest.mark.parametrize("module", [service, precompute])
@pytest.mark.parametrize("real_code", [None, "real-cd"])
def test_monthly_adjustments_preserve_pnl_without_assets(module, real_code):
    groups = {}
    for number in range(3):
        module._merge_monthly_business_pnl_row(
            groups, ROW_DEF, pnl_by_business_manual_adjustment_row(adjustment(number))
        )
    if real_code:
        real_row = {"instrument_code": real_code, "total_pnl": Decimal("10")}
        # Repeated observations of the same real asset still count once.
        for _ in range(2):
            module._merge_monthly_business_pnl_row(groups, ROW_DEF, real_row)
    item = module._monthly_business_item_from_group(
        group=groups[ROW_DEF["row_key"]],
        avg_balance=Decimal("1000"),
        current_balance=Decimal("1000"),
        total_pnl_for_proportion=Decimal("100"),
        calendar_days=31,
        ftp_rate_pct=Decimal("1.6"),
    )
    assert item.asset_count == int(bool(real_code))
    assert item.manual_adjustment == Decimal("75")
    assert item.total_pnl == Decimal("95" if real_code else "75")


@pytest.mark.parametrize("real_code", [None, "real-cd"])
def test_ytd_adjustment_loader_preserves_pnl_without_assets(monkeypatch, real_code):
    monkeypatch.setattr(
        service,
        "_active_pnl_by_business_manual_adjustments",
        lambda *args, **kwargs: [adjustment(i) for i in range(3)],
    )
    groups = {}
    total = service._apply_pnl_by_business_manual_adjustments_to_ytd_groups(
        settings=None,
        groups=groups,
        total_pnl=Decimal("0"),
        loaded_dates=["2026-05-31"],
        unallocated_items=[],
        approved_adjustments=[adjustment(i) for i in range(3)],
    )
    assert total == Decimal("75")
    if real_code:
        service._merge_balance_movement_business_record(
            groups,
            ROW_DEF,
            {
                "bond_code": real_code,
                "interest_income": Decimal("10"),
                "fair_value_change": 0,
                "capital_gain": 0,
                "manual_adjustment": 0,
                "total_pnl": Decimal("10"),
            },
        )
    item = service._ytd_business_item_from_group(
        group=groups[ROW_DEF["row_key"]],
        balance_row={},
        avg_balance=Decimal("1000"),
        current_balance=Decimal("1000"),
        total_pnl_for_proportion=Decimal("100"),
        calendar_days=151,
        ftp_rate_pct=Decimal("1.6"),
    )
    assert item.assets_count == int(bool(real_code))
    assert item.manual_adjustment == Decimal("75")
    assert item.total_pnl == Decimal("85" if real_code else "75")


@pytest.mark.parametrize("with_real_asset", [False, True])
@pytest.mark.parametrize(
    "business_key,dimension", [(None, "bond_bucket"), (ROW_DEF["row_key"], "portfolio")]
)
def test_analysis_and_precompute_adjustment_counts_match(
    with_real_asset, business_key, dimension
):
    rows = [pnl_by_business_manual_adjustment_row(adjustment(i)) for i in range(3)]
    if with_real_asset:
        rows.append(
            {
                "source_kind": "zqtz",
                "report_date": "2026-05-31",
                "instrument_code": "real-cd",
                "instrument_name": "NCD",
                "sub_type": "NCD",
                "total_pnl": Decimal("10"),
                "portfolio_name": "TPL",
                "currency_basis": "CNY",
            }
        )
    kwargs = dict(
        pnl_rows=rows,
        balance_rows=[],
        loaded_dates=["2026-05-31"],
        period_start="2026-05-01",
        period_end="2026-05-31",
        ftp_rate_pct=Decimal("1.6"),
    )
    live = service._build_pnl_by_business_analysis_rows(
        **kwargs, business_key=business_key, dimension=dimension
    )
    cached = next(
        payload.rows
        for payload in precompute._build_pnl_by_business_analysis_payloads_for_precompute(
            **kwargs,
            year=2026,
            source_tables=[],
        )
        if payload.business_key == business_key and payload.dimension == dimension
    )
    for result in (live, cached):
        assert sum(row.asset_count for row in result) == int(with_real_asset)
        assert sum(row.total_pnl for row in result) == Decimal(
            "85" if with_real_asset else "75"
        )
        assert sum(row.manual_adjustment for row in result) == Decimal("75")
