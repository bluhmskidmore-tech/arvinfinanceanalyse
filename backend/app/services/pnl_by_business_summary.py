"""PnL by-business（primary 对账）summary 聚合构造。

分列合计（514/516/517/手工调整/规模/合计损益/损益行数）必须与传入的明细
``rows`` 同一批正式数值逐列求和，不引入新计算口径。拆出独立模块仅为保持
``pnl_service.py`` 作为编排层（frontend debt 基线 routeHint 的既定路由）。
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.schemas.pnl import (
    PnlByBusinessRow,
    PnlByBusinessSummary,
    PnlByBusinessUntracedBreakdownRow,
)

_TWOPLACES = Decimal("0.01")


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(_TWOPLACES)


def build_pnl_by_business_summary(
    *,
    rows: list[PnlByBusinessRow],
    untraced_pnl_row_count: int,
    untraced_breakdown: list[PnlByBusinessUntracedBreakdownRow],
) -> PnlByBusinessSummary:
    return PnlByBusinessSummary(
        business_count=len(rows),
        total_pnl=_quantize(sum((row.total_pnl for row in rows), Decimal("0"))),
        total_scale_amount=_quantize(sum((row.scale_amount for row in rows), Decimal("0"))),
        interest_income_514=_quantize(sum((row.interest_income_514 for row in rows), Decimal("0"))),
        fair_value_change_516=_quantize(sum((row.fair_value_change_516 for row in rows), Decimal("0"))),
        capital_gain_517=_quantize(sum((row.capital_gain_517 for row in rows), Decimal("0"))),
        manual_adjustment=_quantize(sum((row.manual_adjustment for row in rows), Decimal("0"))),
        pnl_row_count=sum(row.pnl_row_count for row in rows),
        traced_pnl_row_count=sum(row.pnl_row_count for row in rows if row.balance_row_count > 0),
        untraced_pnl_row_count=untraced_pnl_row_count,
        untraced_breakdown=untraced_breakdown,
    )
