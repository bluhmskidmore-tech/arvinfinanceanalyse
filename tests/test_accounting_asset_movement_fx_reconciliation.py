from datetime import date
from decimal import Decimal as D

import duckdb
import pytest

from backend.app.core_finance.accounting_asset_movement import (
    GlAccountingAssetBalance,
    ZqtzAccountingAssetBalance,
    build_accounting_asset_movement_rows,
    reconcile_chain_fx_adjustments,
)
from backend.app.repositories.accounting_asset_movement_repo import (
    AccountingAssetMovementRepository,
)
from backend.app.tasks.accounting_asset_movement import (
    materialize_accounting_asset_movement_on_connection,
)


def test_position_book_amount_includes_interest_and_voucher_principal():
    day = date(2026, 8, 31)
    positions = [
        ZqtzAccountingAssetBalance(
            day,
            "AC",
            D(0),
            D(0),
            face_value_amount=D(50),
            accrued_interest_amount=D(3),
            is_voucher_treasury=True,
        ),
        ZqtzAccountingAssetBalance(
            day,
            "AC",
            D(120),
            D(100),
            face_value_amount=D(90),
            accrued_interest_amount=D(2),
        ),
        ZqtzAccountingAssetBalance(
            day, "FVOCI", D(80), D(70), accrued_interest_amount=D(4)
        ),
        ZqtzAccountingAssetBalance(
            day, "FVTPL", D(60), D(50), accrued_interest_amount=D(1)
        ),
    ]
    gl = [
        GlAccountingAssetBalance(day, code, amount, amount)
        for code, amount in [
            ("14201010001", D(155)),
            ("14401010001", D(84)),
            ("14101010001", D(61)),
        ]
    ]
    result = build_accounting_asset_movement_rows(
        report_date=day, zqtz_rows=positions, gl_rows=gl
    )
    assert [row.zqtz_amount for row in result] == [D(155), D(84), D(61)]
    assert {row.reconciliation_status for row in result} == {"matched"}
    # Already-valued vouchers must not receive face value a second time.
    positions[0] = ZqtzAccountingAssetBalance(
        day,
        "AC",
        D(50),
        D(50),
        face_value_amount=D(50),
        accrued_interest_amount=D(3),
        is_voucher_treasury=True,
    )
    assert build_accounting_asset_movement_rows(
        report_date=day, zqtz_rows=positions, gl_rows=gl
    )[0].zqtz_amount == D(155)


def test_fx_never_nets_offsetting_account_breaks():
    prior, current = [], []
    for code, error in [("14201010001", D(10)), ("14301040001", D(-10))]:
        for ccy, before, after in [
            ("CNY", D(100), D(100)),
            ("CNX", D(800), D(790) + error),
        ]:
            prior.append(
                GlAccountingAssetBalance(date(2026, 7, 31), code, before, before, ccy)
            )
            current.append(
                GlAccountingAssetBalance(date(2026, 8, 31), code, after, after, ccy)
            )
    assert (
        reconcile_chain_fx_adjustments(
            current_gl=current, prior_gl=prior, prior_rate=D(7), current_rate=D("6.9")
        )
        == {}
    )


@pytest.mark.parametrize(
    "defect",
    [None, "missing_rate", "mixed_currency", "domestic_break", "unexplained_break"],
)
def test_fx_adjusted_status_requires_complete_independent_evidence(
    tmp_path, monkeypatch, defect
):
    monkeypatch.setenv("MOSS_MOVEMENT_CONTROL_GATE", "off")
    db = tmp_path / "movement.duckdb"
    conn = duckdb.connect(str(db))
    conn.execute("""create table product_category_pnl_canonical_fact (
        report_date varchar, account_code varchar, currency varchar, beginning_balance decimal(24,8),
        ending_balance decimal(24,8), source_version varchar, rule_version varchar)""")
    conn.execute("""create table fact_formal_zqtz_balance_daily (
        report_date varchar, accounting_basis varchar, position_scope varchar, currency_basis varchar,
        currency_code varchar, market_value_amount decimal(24,8), amortized_cost_amount decimal(24,8),
        accrued_interest_amount decimal(24,8), face_value_amount decimal(24,8), bond_type varchar,
        source_version varchar, rule_version varchar)""")
    conn.execute("""create table fx_daily_mid (trade_date date, base_currency varchar, quote_currency varchar,
        mid_rate decimal(24,8), source_version varchar)""")
    for day, amount, rate in [
        ("2026-07-31", D(800), D(7)),
        ("2026-08-31", D(790), D("6.9")),
    ]:
        for ccy, value in [("CNX", amount), ("CNY", D(100))]:
            opening = value
            if day == "2026-08-31":
                if defect == "domestic_break" and ccy == "CNY":
                    opening += D(1)
                if defect == "unexplained_break" and ccy == "CNX":
                    opening += D(1)
            conn.execute(
                "insert into product_category_pnl_canonical_fact values (?, '14201010001', ?, ?, ?, 'sv-gl', 'rv-gl')",
                [day, ccy, opening, value],
            )
        conn.execute(
            "insert into fact_formal_zqtz_balance_daily values (?, 'AC', 'asset', 'CNY', 'USD', ?, ?, 2, 0, '', 'sv-pos', 'rv-pos')",
            [day, amount - D(2), amount - D(2)],
        )
        if defect != "missing_rate" or day == "2026-07-31":
            conn.execute(
                "insert into fx_daily_mid values (?, 'USD', 'CNY', ?, 'sv-fx')",
                [day, rate],
            )
    if defect == "mixed_currency":
        conn.execute(
            "insert into fact_formal_zqtz_balance_daily values ('2026-07-31', 'AC', 'asset', 'native', 'EUR', 1, 1, 0, 0, '', 'sv-pos', 'rv-pos')"
        )
    for column in ("instrument_code", "portfolio_name", "cost_center", "maturity_date"):
        conn.execute(
            f"alter table fact_formal_zqtz_balance_daily add column {column} varchar"
        )
    materialize_accounting_asset_movement_on_connection(conn, report_date="2026-07-31")
    rows = materialize_accounting_asset_movement_on_connection(
        conn, report_date="2026-08-31"
    )
    ac = next(row for row in rows if row.basis_bucket == "AC")
    assert ac.zqtz_amount == D(790)
    assert ac.previous_balance == (D(791) if defect == "unexplained_break" else D(790))
    assert ac.chain_status == ("fx_adjusted" if defect is None else "broken")
    assert ac.reconciliation_status == ("matched" if defect is None else "chain_broken")
    conn.close()
    payload = AccountingAssetMovementRepository(str(db)).fetch_recent_rows(
        report_date="2026-08-31"
    )
    ac_payload = next(
        row
        for row in payload
        if row["report_date"] == "2026-08-31" and row["basis_bucket"] == "AC"
    )
    if defect is None:
        assert ac_payload["chain_fx_adjustment"].quantize(D("0.01")) == D("-10.00")
        assert ac_payload["chain_fx_currency"] == "USD"
        assert ac_payload["chain_fx_current_rate"] == D("6.9")
    else:
        assert "chain_fx_adjustment" not in ac_payload
