from __future__ import annotations

from datetime import date
from decimal import Decimal

import duckdb
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from tests.helpers import ROOT, load_module

POLICY_BOND = "\u653f\u7b56\u6027\u91d1\u878d\u503a"
OTHER_BOND = "\u5176\u4ed6"
UNRATED = "\u65e0\u8bc4\u7ea7(\u5229\u7387\u503a\u7b49)"
FIXED = "\u56fa\u5b9a"
ISSUANCE_ASSET_CLASS = "\u53d1\u884c\u7c7b\u503a\u52b5"
INTERBANK_DEPOSIT = "\u540c\u4e1a\u5b58\u653e"
JOINT_STOCK_BANK = "\u80a1\u4efd\u5236\u94f6\u884c"


def _seed_workbook_snapshot_and_fx_tables(duckdb_path: str) -> None:
    snapshot_mod = load_module(
        "backend.app.repositories.snapshot_repo",
        "backend/app/repositories/snapshot_repo.py",
    )

    conn = duckdb.connect(duckdb_path, read_only=False)
    try:
        snapshot_mod.ensure_snapshot_tables(conn)
        conn.execute(
            """
            create table if not exists fx_daily_mid (
              trade_date date,
              base_currency varchar,
              quote_currency varchar,
              mid_rate decimal(24, 8),
              source_name varchar,
              is_business_day boolean,
              is_carry_forward boolean,
              source_version varchar
            )
            """
        )
        conn.execute(
            """
            insert into zqtz_bond_daily_snapshot (
              report_date, instrument_code, instrument_name, portfolio_name, cost_center,
              account_category, asset_class, bond_type, issuer_name, industry_name, rating,
              currency_code, face_value_native, market_value_native, amortized_cost_native,
              accrued_interest_native, coupon_rate, ytm_value, maturity_date, next_call_date,
              overdue_days, is_issuance_like, interest_mode, source_version, rule_version,
              ingest_batch_id, trace_id
            ) values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                "2025-12-31",
                "240001.IB",
                "Policy Bond A",
                "PortfolioA",
                "CC100",
                "\u53ef\u4f9b\u51fa\u552e\u503a\u5238",
                "\u53ef\u4f9b\u51fa\u552e\u7c7b\u8d44\u4ea7",
                POLICY_BOND,
                "IssuerA",
                "\u516c\u5171\u7ba1\u7406\u3001\u793e\u4f1a\u4fdd\u969c\u548c\u793e\u4f1a\u7ec4\u7ec7",
                "AAA",
                "CNY",
                Decimal("100"),
                Decimal("102"),
                Decimal("99"),
                Decimal("1"),
                Decimal("2.5"),
                Decimal("2.4"),
                "2027-12-31",
                None,
                0,
                False,
                FIXED,
                "sv-z-1",
                "rv-snap-1",
                "ib-z-1",
                "trace-z-1",
            ],
        )
        conn.execute(
            """
            insert into zqtz_bond_daily_snapshot (
              report_date, instrument_code, instrument_name, portfolio_name, cost_center,
              account_category, asset_class, bond_type, issuer_name, industry_name, rating,
              currency_code, face_value_native, market_value_native, amortized_cost_native,
              accrued_interest_native, coupon_rate, ytm_value, maturity_date, next_call_date,
              overdue_days, is_issuance_like, interest_mode, source_version, rule_version,
              ingest_batch_id, trace_id
            ) values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                "2025-12-31",
                "J11603010202",
                "USD Receivable Investment",
                "PortfolioB",
                "CC200",
                "\u94f6\u884c\u8d26\u6237",
                "\u5e94\u6536\u6295\u8d44\u6b3e\u9879",
                OTHER_BOND,
                "IssuerB",
                "\u672a\u5206\u7c7b",
                "",
                "USD",
                Decimal("50"),
                Decimal("50"),
                Decimal("50"),
                Decimal("0"),
                Decimal("0"),
                Decimal("0"),
                "2026-06-30",
                None,
                0,
                False,
                FIXED,
                "sv-z-1",
                "rv-snap-1",
                "ib-z-1",
                "trace-z-2",
            ],
        )
        conn.execute(
            """
            insert into zqtz_bond_daily_snapshot (
              report_date, instrument_code, instrument_name, portfolio_name, cost_center,
              account_category, asset_class, bond_type, issuer_name, industry_name, rating,
              currency_code, face_value_native, market_value_native, amortized_cost_native,
              accrued_interest_native, coupon_rate, ytm_value, maturity_date, next_call_date,
              overdue_days, is_issuance_like, interest_mode, source_version, rule_version,
              ingest_batch_id, trace_id
            ) values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                "2025-12-31",
                "NCD-ISSUE-1",
                "Issue CD",
                "LiabilityPortfolio",
                "CC300",
                ISSUANCE_ASSET_CLASS,
                ISSUANCE_ASSET_CLASS,
                "\u540c\u4e1a\u5b58\u5355",
                "IssuerC",
                "\u91d1\u878d\u4e1a",
                "",
                "CNY",
                Decimal("80"),
                Decimal("80"),
                Decimal("80"),
                Decimal("0.2"),
                Decimal("1.8"),
                Decimal("1.8"),
                "2026-03-31",
                None,
                0,
                True,
                FIXED,
                "sv-z-1",
                "rv-snap-1",
                "ib-z-1",
                "trace-z-3",
            ],
        )
        conn.execute(
            """
            insert into tyw_interbank_daily_snapshot (
              report_date, position_id, product_type, position_side, counterparty_name,
              account_type, special_account_type, core_customer_type, currency_code,
              principal_native, accrued_interest_native, funding_cost_rate, maturity_date,
              pledged_bond_code, source_version, rule_version, ingest_batch_id, trace_id
            ) values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                "2025-12-31",
                "asset-1",
                "\u62c6\u653e\u540c\u4e1a",
                "asset",
                "\u57ce\u5546\u884cA",
                "\u6295\u878d\u8d44\u7c7b",
                "\u4e00\u822c",
                "\u57ce\u5e02\u5546\u4e1a\u94f6\u884c",
                "CNY",
                Decimal("30"),
                Decimal("0.3"),
                Decimal("2.0"),
                "2026-01-31",
                None,
                "sv-t-1",
                "rv-snap-1",
                "ib-t-1",
                "trace-t-1",
            ],
        )
        conn.execute(
            """
            insert into tyw_interbank_daily_snapshot (
              report_date, position_id, product_type, position_side, counterparty_name,
              account_type, special_account_type, core_customer_type, currency_code,
              principal_native, accrued_interest_native, funding_cost_rate, maturity_date,
              pledged_bond_code, source_version, rule_version, ingest_batch_id, trace_id
            ) values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                "2025-12-31",
                "liability-1",
                INTERBANK_DEPOSIT,
                "liability",
                "\u80a1\u4efd\u884cB",
                "\u6e05\u7b97\u7c7b",
                "\u6258\u7ba1\u8d26\u6237",
                JOINT_STOCK_BANK,
                "CNY",
                Decimal("40"),
                Decimal("0.2"),
                Decimal("1.5"),
                "2026-01-15",
                None,
                "sv-t-1",
                "rv-snap-1",
                "ib-t-1",
                "trace-t-2",
            ],
        )
        conn.execute(
            """
            insert into fx_daily_mid values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "2025-12-31",
                "USD",
                "CNY",
                Decimal("7.2"),
                "CFETS",
                True,
                False,
                "sv-fx-1",
            ],
        )
    finally:
        conn.close()


def test_workbook_weighted_term_years_matches_365_25_day_basis():
    workbook_module = load_module(
        "backend.app.core_finance.balance_analysis_workbook",
        "backend/app/core_finance/balance_analysis_workbook.py",
    )
    balance_module = load_module(
        "backend.app.core_finance.balance_analysis",
        "backend/app/core_finance/balance_analysis.py",
    )

    report_date = date(2026, 3, 1)
    rows = [
        balance_module.FormalZqtzBalanceFactRow(
            report_date=report_date,
            instrument_code="X1",
            instrument_name="X1",
            portfolio_name="P",
            cost_center="C",
            asset_class="\u4ea4\u6613\u6027\u8d44\u4ea7",
            bond_type=OTHER_BOND,
            issuer_name="I",
            industry_name="\u672a\u5206\u7c7b",
            rating="",
            invest_type_std="T",
            accounting_basis="FVTPL",
            position_scope="asset",
            currency_basis="native",
            currency_code="CNY",
            face_value_amount=Decimal("3"),
            market_value_amount=Decimal("3"),
            amortized_cost_amount=Decimal("3"),
            accrued_interest_amount=Decimal("0"),
            coupon_rate=Decimal("2.0"),
            ytm_value=None,
            maturity_date=date(2027, 3, 1),
            interest_mode=FIXED,
            is_issuance_like=False,
        ),
        balance_module.FormalZqtzBalanceFactRow(
            report_date=report_date,
            instrument_code="X2",
            instrument_name="X2",
            portfolio_name="P",
            cost_center="C",
            asset_class="\u4ea4\u6613\u6027\u8d44\u4ea7",
            bond_type=OTHER_BOND,
            issuer_name="I",
            industry_name="\u672a\u5206\u7c7b",
            rating="",
            invest_type_std="T",
            accounting_basis="FVTPL",
            position_scope="asset",
            currency_basis="native",
            currency_code="CNY",
            face_value_amount=Decimal("7"),
            market_value_amount=Decimal("7"),
            amortized_cost_amount=Decimal("7"),
            accrued_interest_amount=Decimal("0"),
            coupon_rate=Decimal("2.0"),
            ytm_value=None,
            maturity_date=date(2028, 3, 1),
            interest_mode=FIXED,
            is_issuance_like=False,
        ),
    ]

    d1 = (date(2027, 3, 1) - report_date).days
    d2 = (date(2028, 3, 1) - report_date).days
    expected = (
        Decimal("3") * Decimal(d1) / Decimal("365.25")
        + Decimal("7") * Decimal(d2) / Decimal("365.25")
    ) / Decimal("10")

    table = workbook_module._build_bond_business_type_table(rows)
    other_row = next(row for row in table["rows"] if row["bond_type"] == OTHER_BOND)
    assert Decimal(str(other_row["weighted_term_years"])) == expected


def test_workbook_business_type_duration_ignores_rows_without_or_past_maturity():
    workbook_module = load_module(
        "backend.app.core_finance.balance_analysis_workbook",
        "backend/app/core_finance/balance_analysis_workbook.py",
    )
    balance_module = load_module(
        "backend.app.core_finance.balance_analysis",
        "backend/app/core_finance/balance_analysis.py",
    )

    rows = [
        balance_module.FormalZqtzBalanceFactRow(
            report_date=date(2025, 12, 31),
            instrument_code="A",
            instrument_name="A",
            portfolio_name="P",
            cost_center="C",
            asset_class="\u4ea4\u6613\u6027\u8d44\u4ea7",
            bond_type=OTHER_BOND,
            issuer_name="I",
            industry_name="\u672a\u5206\u7c7b",
            rating="",
            invest_type_std="T",
            accounting_basis="FVTPL",
            position_scope="asset",
            currency_basis="native",
            currency_code="CNY",
            face_value_amount=Decimal("10000"),
            market_value_amount=Decimal("10000"),
            amortized_cost_amount=Decimal("10000"),
            accrued_interest_amount=Decimal("0"),
            coupon_rate=Decimal("2.0"),
            ytm_value=None,
            maturity_date=None,
            interest_mode=FIXED,
            is_issuance_like=False,
        ),
        balance_module.FormalZqtzBalanceFactRow(
            report_date=date(2025, 12, 31),
            instrument_code="B",
            instrument_name="B",
            portfolio_name="P",
            cost_center="C",
            asset_class="\u4ea4\u6613\u6027\u8d44\u4ea7",
            bond_type=OTHER_BOND,
            issuer_name="I",
            industry_name="\u672a\u5206\u7c7b",
            rating="",
            invest_type_std="T",
            accounting_basis="FVTPL",
            position_scope="asset",
            currency_basis="native",
            currency_code="CNY",
            face_value_amount=Decimal("20000"),
            market_value_amount=Decimal("20000"),
            amortized_cost_amount=Decimal("20000"),
            accrued_interest_amount=Decimal("0"),
            coupon_rate=Decimal("2.0"),
            ytm_value=None,
            maturity_date=date(2030, 12, 31),
            interest_mode=FIXED,
            is_issuance_like=False,
        ),
        balance_module.FormalZqtzBalanceFactRow(
            report_date=date(2025, 12, 31),
            instrument_code="C",
            instrument_name="C",
            portfolio_name="P",
            cost_center="C",
            asset_class="\u4ea4\u6613\u6027\u8d44\u4ea7",
            bond_type=OTHER_BOND,
            issuer_name="I",
            industry_name="\u672a\u5206\u7c7b",
            rating="",
            invest_type_std="T",
            accounting_basis="FVTPL",
            position_scope="asset",
            currency_basis="native",
            currency_code="CNY",
            face_value_amount=Decimal("30000"),
            market_value_amount=Decimal("30000"),
            amortized_cost_amount=Decimal("30000"),
            accrued_interest_amount=Decimal("0"),
            coupon_rate=Decimal("2.0"),
            ytm_value=None,
            maturity_date=date(2025, 1, 1),
            interest_mode=FIXED,
            is_issuance_like=False,
        ),
    ]

    table = workbook_module._build_bond_business_type_table(rows)
    other_row = next(row for row in table["rows"] if row["bond_type"] == OTHER_BOND)
    assert Decimal(str(other_row["weighted_term_years"])) > Decimal("4")


def test_workbook_campisi_uses_policy_bank_rate_as_benchmark():
    workbook_module = load_module(
        "backend.app.core_finance.balance_analysis_workbook",
        "backend/app/core_finance/balance_analysis_workbook.py",
    )
    balance_module = load_module(
        "backend.app.core_finance.balance_analysis",
        "backend/app/core_finance/balance_analysis.py",
    )

    rows = [
        balance_module.FormalZqtzBalanceFactRow(
            report_date=date(2025, 12, 31),
            instrument_code="P",
            instrument_name="P",
            portfolio_name="P",
            cost_center="C",
            asset_class="\u6301\u6709\u81f3\u5230\u671f\u7c7b\u8d44\u4ea7",
            bond_type=POLICY_BOND,
            issuer_name="I",
            industry_name="\u516c\u5171\u7ba1\u7406\u3001\u793e\u4f1a\u4fdd\u969c\u548c\u793e\u4f1a\u7ec4\u7ec7",
            rating="AAA",
            invest_type_std="H",
            accounting_basis="AC",
            position_scope="asset",
            currency_basis="native",
            currency_code="CNY",
            face_value_amount=Decimal("10000"),
            market_value_amount=Decimal("10000"),
            amortized_cost_amount=Decimal("10000"),
            accrued_interest_amount=Decimal("0"),
            coupon_rate=Decimal("2.0"),
            ytm_value=None,
            maturity_date=date(2027, 12, 31),
            interest_mode=FIXED,
            is_issuance_like=False,
        ),
        balance_module.FormalZqtzBalanceFactRow(
            report_date=date(2025, 12, 31),
            instrument_code="G",
            instrument_name="G",
            portfolio_name="P",
            cost_center="C",
            asset_class="\u53ef\u4f9b\u51fa\u552e\u7c7b\u8d44\u4ea7",
            bond_type="\u56fd\u503a",
            issuer_name="I",
            industry_name="\u516c\u5171\u7ba1\u7406\u3001\u793e\u4f1a\u4fdd\u969c\u548c\u793e\u4f1a\u7ec4\u7ec7",
            rating="",
            invest_type_std="A",
            accounting_basis="FVOCI",
            position_scope="asset",
            currency_basis="native",
            currency_code="CNY",
            face_value_amount=Decimal("10000"),
            market_value_amount=Decimal("10000"),
            amortized_cost_amount=Decimal("10000"),
            accrued_interest_amount=Decimal("0"),
            coupon_rate=Decimal("5.0"),
            ytm_value=None,
            maturity_date=date(2035, 12, 31),
            interest_mode=FIXED,
            is_issuance_like=False,
        ),
        balance_module.FormalZqtzBalanceFactRow(
            report_date=date(2025, 12, 31),
            instrument_code="C",
            instrument_name="C",
            portfolio_name="P",
            cost_center="C",
            asset_class="\u53ef\u4f9b\u51fa\u552e\u7c7b\u8d44\u4ea7",
            bond_type="\u4fe1\u7528\u503a\u5238-\u4f01\u4e1a",
            issuer_name="I",
            industry_name="\u5236\u9020\u4e1a",
            rating="AA+",
            invest_type_std="A",
            accounting_basis="FVOCI",
            position_scope="asset",
            currency_basis="native",
            currency_code="CNY",
            face_value_amount=Decimal("10000"),
            market_value_amount=Decimal("10000"),
            amortized_cost_amount=Decimal("10000"),
            accrued_interest_amount=Decimal("0"),
            coupon_rate=Decimal("6.0"),
            ytm_value=None,
            maturity_date=date(2028, 12, 31),
            interest_mode=FIXED,
            is_issuance_like=False,
        ),
    ]

    table = workbook_module._build_campisi_table(rows)
    corp_row = next(row for row in table["rows"] if row["bond_type"] == "\u4fe1\u7528\u503a\u5238-\u4f01\u4e1a")
    assert Decimal(str(corp_row["spread_bp"])) == Decimal("400")


def test_real_zqtz_parse_marks_asset_class_issue_rows_as_issuance_like():
    parse_mod = load_module(
        "backend.app.repositories.snapshot_row_parse",
        "backend/app/repositories/snapshot_row_parse.py",
    )
    source_file = "ZQTZSHOW-20260228.xls"
    rows = parse_mod.parse_zqtz_snapshot_rows_from_bytes(
        file_bytes=(ROOT / "data_input" / source_file).read_bytes(),
        ingest_batch_id="ib-real-zqtz",
        source_version="sv-real-zqtz",
        source_file=source_file,
        rule_version="rv-real-zqtz",
    )
    issue_rows = [row for row in rows if str(row.get("asset_class") or "") == ISSUANCE_ASSET_CLASS]
    assert issue_rows
    assert all(bool(row["is_issuance_like"]) for row in issue_rows[:10])


def test_real_tyw_parse_marks_tongye_cunfang_as_liability():
    parse_mod = load_module(
        "backend.app.repositories.snapshot_row_parse",
        "backend/app/repositories/snapshot_row_parse.py",
    )
    source_file = "TYWLSHOW-20260228.xls"
    rows = parse_mod.parse_tyw_snapshot_rows_from_bytes(
        file_bytes=(ROOT / "data_input" / source_file).read_bytes(),
        ingest_batch_id="ib-real-tyw",
        source_version="sv-real-tyw",
        source_file=source_file,
        rule_version="rv-real-tyw",
    )
    cunfang_rows = [row for row in rows if str(row.get("product_type") or "") == INTERBANK_DEPOSIT]
    assert cunfang_rows
    assert all(str(row["position_side"]) == "liability" for row in cunfang_rows[:10])


def test_balance_analysis_workbook_api_returns_governed_sections(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    _seed_workbook_snapshot_and_fx_tables(str(duckdb_path))

    task_mod = load_module(
        "backend.app.tasks.balance_analysis_materialize",
        "backend/app/tasks/balance_analysis_materialize.py",
    )
    task_mod.materialize_balance_analysis_facts.fn(
        report_date="2025-12-31",
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get(
        "/ui/balance-analysis/workbook",
        params={"report_date": "2025-12-31", "position_scope": "all", "currency_basis": "CNY"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["result_kind"] == "balance-analysis.workbook"
    assert payload["result"]["report_date"] == "2025-12-31"
    assert payload["result"]["position_scope"] == "all"
    assert payload["result"]["currency_basis"] == "CNY"

    card_keys = {card["key"] for card in payload["result"]["cards"]}
    assert {
        "bond_assets_excluding_issue",
        "interbank_assets",
        "interbank_liabilities",
        "issuance_liabilities",
        "net_position",
    } <= card_keys
    card_map = {card["key"]: card for card in payload["result"]["cards"]}
    assert Decimal(str(card_map["issuance_liabilities"]["value"])) > Decimal("0")
    assert Decimal(str(card_map["bond_assets_excluding_issue"]["value"])) == Decimal("0.015")

    table_keys = {table["key"] for table in payload["result"]["tables"]}
    assert {
        "bond_business_types",
        "maturity_gap",
        "issuance_business_types",
        "currency_split",
        "rating_analysis",
        "rate_distribution",
        "industry_distribution",
        "counterparty_types",
        "campisi_breakdown",
        "cross_analysis",
        "interest_modes",
    } <= table_keys
    table_map = {table["key"]: table for table in payload["result"]["tables"]}
    issuance_rows = table_map["issuance_business_types"]["rows"]
    assert any(row["bond_type"] == "\u540c\u4e1a\u5b58\u5355" for row in issuance_rows)
    counterparty_rows = table_map["counterparty_types"]["rows"]
    liability_row = next(row for row in counterparty_rows if row["counterparty_type"] == JOINT_STOCK_BANK)
    assert liability_row["liability_count"] == 1
    bond_rows = table_map["bond_business_types"]["rows"]
    policy_row = next(row for row in bond_rows if row["bond_type"] == POLICY_BOND)
    assert Decimal(str(policy_row["balance_amount"])) < Decimal("1")
    other_row = next(row for row in bond_rows if row["bond_type"] == OTHER_BOND)
    assert Decimal(str(other_row["balance_amount"])) == Decimal("0.005")

    get_settings.cache_clear()
