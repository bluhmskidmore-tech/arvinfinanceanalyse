"""原币敞口富集必须按自然键关联，而不是按一个大面积不唯一的四元组。

`_attach_native_exposure_fields` 曾用 (instrument_code, portfolio_name, cost_center,
currency_code) 建字典并 `setdefault`。这个键在 `fact_formal_zqtz_balance_daily` 上
**每个 currency_basis 有 1,555 组重复**：2025-09-30 起同一只债券会同时计入 AC 与
OCI 两本账，展期/重分类期间同一 instrument_code 还会带两个到期日。于是第一行胜出，
其余每一行静默拿到**另一条腿**的原币市值——只读副本上 19 个损益日共 180 行被串行，
原币市值错配绝对值合计 624.03 亿。

这些重复行是合法持仓，绝不能去重；要修的是键。本文件锁三件事：

1. 同一只券的两本账 / 两个到期日各自拿到自己的原币金额，不再交叉；
2. 快照侧（无 accounting_basis 列）用 asset_class 作同一层判别，face_value_native 同样不串；
3. 键真的重复时**报错而不是静默取第一行**——键唯一之后，同键两行是事实表完整性
   失效，任取其一发布出去正是这次要根除的行为。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.services.pnl_bridge_service import _attach_native_exposure_fields


def _cny_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "report_date": "2026-07-31",
        "instrument_code": "240215",
        "portfolio_name": "FIOA",
        "cost_center": "5010",
        "accounting_basis": "AC",
        "asset_class": "持有至到期类资产",
        "maturity_date": "2034-07-19",
        "position_scope": "asset",
        "currency_basis": "CNY",
        "currency_code": "CNY",
        "market_value_amount": Decimal("769800540"),
        "accrued_interest_amount": Decimal("0"),
    }
    row.update(overrides)
    return row


def _native_row(**overrides: object) -> dict[str, object]:
    return _cny_row(**{"currency_basis": "native", **overrides})


def _snapshot_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "instrument_code": "240215",
        "portfolio_name": "FIOA",
        "cost_center": "5010",
        "asset_class": "持有至到期类资产",
        # 快照列是 DATE，事实表列是 VARCHAR：键必须能吸收这个类型差。
        "maturity_date": date(2034, 7, 19),
        "currency_code": "CNY",
        "face_value_native": Decimal("740000000"),
    }
    row.update(overrides)
    return row


class _StubBalanceRepo:
    def __init__(
        self,
        *,
        native_rows: list[dict[str, object]],
        snapshot_rows: list[dict[str, object]] | None = None,
    ) -> None:
        self._native_rows = native_rows
        self._snapshot_rows = snapshot_rows or []

    def fetch_formal_zqtz_rows(
        self, *, report_date: str, position_scope: str, currency_basis: str
    ) -> list[dict[str, object]]:
        assert (position_scope, currency_basis) == ("asset", "native")
        return [row for row in self._native_rows if row["report_date"] == report_date]

    def fetch_zqtz_snapshot_native_face_value_rows(
        self, *, report_date: str
    ) -> list[dict[str, object]]:
        assert report_date
        return list(self._snapshot_rows)


def _attach(
    balance_rows: list[dict[str, object]],
    native_rows: list[dict[str, object]],
    snapshot_rows: list[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    return _attach_native_exposure_fields(
        balance_repo=_StubBalanceRepo(native_rows=native_rows, snapshot_rows=snapshot_rows),
        report_date="2026-07-31",
        balance_rows=balance_rows,
    )


def test_two_accounting_books_of_one_bond_keep_their_own_native_amounts():
    """240215 24国开15 的真实形态：同一 cost center 下 AC 与 OCI 两条腿。

    旧键把两行折成一个键，OCI 腿因此拿到 AC 腿的 7.698 亿原币市值。
    """
    ac = _cny_row(accounting_basis="AC", market_value_amount=Decimal("769800540"))
    oci = _cny_row(
        accounting_basis="FVOCI",
        asset_class="可供出售类资产",
        market_value_amount=Decimal("135235230"),
    )

    enriched = _attach(
        [ac, oci],
        [
            _native_row(accounting_basis="AC", market_value_amount=Decimal("769800540")),
            _native_row(
                accounting_basis="FVOCI",
                asset_class="可供出售类资产",
                market_value_amount=Decimal("135235230"),
            ),
        ],
    )

    assert enriched[0]["market_value_native"] == Decimal("769800540")
    assert enriched[1]["market_value_native"] == Decimal("135235230")


def test_two_maturity_legs_of_one_instrument_are_not_cross_assigned():
    """031800572.IB 的真实形态：同一 (券, 组合, 成本中心, 币种) 下两个到期日，

    面值一正一负。键里没有 maturity_date 时两行互换原币市值——库里已固化的
    5 行 ``market_value_cny = -market_value_native`` 就是同一根因的另一个出口。
    """
    long_leg = _cny_row(
        instrument_code="031800572.IB",
        cost_center="",
        accounting_basis="FVOCI",
        asset_class="可供出售类资产",
        maturity_date="2024-02-21",
        market_value_amount=Decimal("14273208.63"),
    )
    short_leg = _cny_row(
        instrument_code="031800572.IB",
        cost_center="",
        accounting_basis="FVOCI",
        asset_class="可供出售类资产",
        maturity_date="2026-09-21",
        market_value_amount=Decimal("-14273208.63"),
    )

    enriched = _attach(
        [long_leg, short_leg],
        [
            _native_row(
                instrument_code="031800572.IB",
                cost_center="",
                accounting_basis="FVOCI",
                asset_class="可供出售类资产",
                maturity_date="2024-02-21",
                market_value_amount=Decimal("14273208.63"),
            ),
            _native_row(
                instrument_code="031800572.IB",
                cost_center="",
                accounting_basis="FVOCI",
                asset_class="可供出售类资产",
                maturity_date="2026-09-21",
                market_value_amount=Decimal("-14273208.63"),
            ),
        ],
    )

    assert enriched[0]["market_value_native"] == Decimal("14273208.63")
    assert enriched[1]["market_value_native"] == Decimal("-14273208.63")


def test_snapshot_face_values_key_on_asset_class_and_maturity_across_column_types():
    """快照没有 accounting_basis，只有 asset_class；maturity_date 两侧类型还不同。"""
    ac = _cny_row(accounting_basis="AC", asset_class="持有至到期类资产")
    oci = _cny_row(accounting_basis="FVOCI", asset_class="可供出售类资产")

    enriched = _attach(
        [ac, oci],
        [],
        snapshot_rows=[
            _snapshot_row(asset_class="持有至到期类资产", face_value_native=Decimal("740000000")),
            _snapshot_row(asset_class="可供出售类资产", face_value_native=Decimal("130000000")),
        ],
    )

    assert enriched[0]["face_value_native"] == Decimal("740000000")
    assert enriched[1]["face_value_native"] == Decimal("130000000")


def test_a_genuine_duplicate_natural_key_is_reported_rather_than_silently_first_wins():
    """键唯一之后，同键两行只可能是事实表坏了。

    ``setdefault`` 会挑第一行继续发布一个看不出问题的数字；现在必须让人看见，
    并且报文里要带上到底哪个键重了。
    """
    with pytest.raises(RuntimeError) as excinfo:
        _attach(
            [_cny_row()],
            [
                _native_row(market_value_amount=Decimal("1")),
                _native_row(market_value_amount=Decimal("2")),
            ],
        )

    message = str(excinfo.value)
    assert "Duplicate natural key" in message
    assert "fact_formal_zqtz_balance_daily" in message
    assert "accounting_basis" in message and "maturity_date" in message
    assert "240215" in message


def test_duplicate_snapshot_natural_key_is_reported_too():
    with pytest.raises(RuntimeError, match="zqtz_bond_daily_snapshot"):
        _attach(
            [_cny_row()],
            [],
            snapshot_rows=[
                _snapshot_row(face_value_native=Decimal("1")),
                _snapshot_row(face_value_native=Decimal("2")),
            ],
        )


def test_rows_without_a_native_counterpart_are_left_untouched():
    """没有对手行时不得凭空补数，也不得回退到别人的腿上。"""
    enriched = _attach([_cny_row(instrument_code="NO-NATIVE-01")], [_native_row()])

    assert "market_value_native" not in enriched[0]
    assert "accrued_interest_native" not in enriched[0]
