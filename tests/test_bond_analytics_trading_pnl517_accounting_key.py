"""517 交易损益必须按「券 + 组合 + 成本中心 + 会计账簿」归位，一份只发一次。

`_pnl_position_key_from_bond_row` 曾构造 ``f"{inst}::{pn}::{cc}"``。
`fact_formal_bond_analytics_daily` 在这个键上有 **935 组重复、横跨 100 个 report_date**
（2025-09-30 起同一只债券同时计入 AC 与 OCI 两本账），而 `fact_formal_pnl_fi` 的
``capital_gain_517`` 本来就是**按会计账簿**报的。少了账簿这一维，每条腿都领走整个
持仓的 517：只读副本上 2026-02-28 的 trading_total 报成 67,839,687.13 而不是
66,158,328.64（+1,681,358.49），2026-05-31 报成 68,936,696.40 而不是 67,936,111.12
（+1,000,585.27）。

两侧词表并不相同（明细表说 AC/OCI/TPL，损益表说 AC/FVOCI/FVTPL），所以键的正确性
既包含维度也包含这层折算。非标桥接表根本没有会计维度，它那一份只能落在整个持仓上，
因此不能按账簿发放——但同样不允许每条腿各领一份。
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.services.bond_analytics_service import (
    _capital_gain_517_buckets,
    _distribute_capital_gain_517,
    _pnl_position_key_from_bond_row,
)

ZERO = Decimal("0")


def _bond_row(accounting_class: str, market_value: str, **overrides: object) -> dict:
    row: dict = {
        "instrument_code": "240215",
        "instrument_name": "24国开15",
        "portfolio_name": "FIOA",
        "cost_center": "5010",
        "accounting_class": accounting_class,
        "market_value": Decimal(market_value),
    }
    row.update(overrides)
    return row


def test_bond_row_key_carries_the_accounting_book():
    assert _pnl_position_key_from_bond_row(_bond_row("AC", "769800540")) == (
        "240215",
        "FIOA",
        "5010",
        "AC",
    )


class _StubPnlRepo:
    """按 `fact_formal_pnl_fi` / `fact_nonstd_pnl_bridge` 的原始词表返回 517。"""

    def __init__(self, buckets: dict) -> None:
        self._buckets = buckets

    def merged_capital_gain_517_by_position_and_accounting_for_dates(self, dates: list[str]) -> dict:
        assert dates
        return dict(self._buckets)


def _buckets(raw: dict) -> dict:
    return _capital_gain_517_buckets(_StubPnlRepo(raw), ["2026-02-28"])


def test_bond_and_pnl_accounting_vocabularies_fold_onto_one_token():
    """明细表 OCI / 损益表 FVOCI 必须落在同一个键上，否则两侧永远匹配不上。"""
    bond_key = _pnl_position_key_from_bond_row(_bond_row("OCI", "1"))
    buckets = _buckets({("240215", "FIOA", "5010", "FVOCI"): Decimal("1681358.49")})

    assert bond_key in buckets
    assert buckets[bond_key] == Decimal("1681358.49")


def test_the_other_accounting_book_no_longer_claims_the_same_517():
    """2026-02-28 的真实形态：517 属于 OCI 腿，AC 腿此前也领了一份同样金额。"""
    ac = _bond_row("AC", "306413700")
    oci = _bond_row("OCI", "100000000")

    trading, split_buckets = _distribute_capital_gain_517(
        [ac, oci], _buckets({("240215", "FIOA", "5010", "FVOCI"): Decimal("1681358.49")})
    )

    assert trading == [ZERO, Decimal("1681358.49")]
    assert sum(trading, ZERO) == Decimal("1681358.49")
    assert split_buckets == 0


def test_two_maturity_legs_of_one_book_split_the_bucket_instead_of_doubling_it():
    """同一账簿下仍可能有两条到期日腿，而损益事实没有到期日这一维。

    此时这份 517 属于整条持仓：可以按市值分摊，但绝不能两条腿各发一份。
    """
    long_leg = _bond_row("OCI", "300000000", maturity_date="2034-07-19")
    short_leg = _bond_row("OCI", "100000000", maturity_date="2030-07-19")

    trading, split_buckets = _distribute_capital_gain_517(
        [long_leg, short_leg], _buckets({("240215", "FIOA", "5010", "FVOCI"): Decimal("400")})
    )

    assert trading == [Decimal("300"), Decimal("100")]
    assert sum(trading, ZERO) == Decimal("400")
    assert split_buckets == 1


def test_the_account_less_nonstd_bucket_lands_on_the_position_once():
    """非标桥接表没有会计维度，它的键是空账簿：覆盖整条持仓，不是每本账各一份。"""
    ac = _bond_row("AC", "750000000")
    oci = _bond_row("OCI", "250000000")

    trading, split_buckets = _distribute_capital_gain_517(
        [ac, oci], _buckets({("240215", "FIOA", "5010", ""): Decimal("1000")})
    )

    assert trading == [Decimal("750"), Decimal("250")]
    assert sum(trading, ZERO) == Decimal("1000")
    assert split_buckets == 1


def test_allocation_closes_exactly_when_the_split_does_not_divide_evenly():
    """分摊只是把一份钱摊开，合计必须一分不差地等于原来那一份。"""
    rows = [_bond_row("OCI", "1"), _bond_row("OCI", "1"), _bond_row("OCI", "1")]

    trading, _ = _distribute_capital_gain_517(
        rows, _buckets({("240215", "FIOA", "5010", "FVOCI"): Decimal("100")})
    )

    assert sum(trading, ZERO) == Decimal("100")


def test_flat_rows_split_evenly_rather_than_dividing_by_zero():
    rows = [_bond_row("OCI", "0"), _bond_row("OCI", "0")]

    trading, _ = _distribute_capital_gain_517(
        rows, _buckets({("240215", "FIOA", "5010", "FVOCI"): Decimal("10")})
    )

    assert trading == [Decimal("5"), Decimal("5")]


def test_unmatched_bucket_is_not_invented_onto_some_other_row():
    """对不上的 517 保持原有处置：行仍为 0，由覆盖率告警去报，不能就近找个行塞进去。"""
    rows = [_bond_row("AC", "100")]

    trading, split_buckets = _distribute_capital_gain_517(
        rows, _buckets({("OTHER-BOND", "FIOA", "5010", "AC"): Decimal("777")})
    )

    assert trading == [ZERO]
    assert split_buckets == 0
